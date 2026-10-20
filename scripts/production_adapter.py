#!/usr/bin/env python3
"""Portable Krita handoff: PNG/WAV animation and layered OpenRaster snapshots.

Raster snapshots bake rig transforms and masks. Source rigs, claims and reviews
remain in the production project; edited art needs an explicit new asset version.
"""
from __future__ import annotations

import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image, ImageChops

from production_render import (MAX_FRAME_PIXELS, MAX_RENDER_FRAMES, _color,
    _output_record_valid, _wave_info, atomic_json, file_hash, fps_fraction,
    safe_path, sample_at_frame, validate_render)

ADAPTER_VERSION = "1.0.0"
MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 4096
MAX_HANDOFF_BYTES = 2 * 1024 * 1024 * 1024
SOURCES = {
    "openraster_files": "https://www.openraster.org/baseline/file-layout-spec.html",
    "openraster_stack": "https://www.openraster.org/baseline/layer-stack-spec.html",
    "krita_frames": "https://docs.krita.org/en/reference_manual/import_animation.html",
    "krita_audio": "https://docs.krita.org/en/reference_manual/audio_for_animation.html",
    "krita_cli": "https://docs.krita.org/en/reference_manual/linux_command_line.html",
}


def _png_bytes(image):
    stream = io.BytesIO()
    image.save(stream, format="PNG", compress_level=6, optimize=False)
    return stream.getvalue()


def _zip_write(archive, name, data, compression=zipfile.ZIP_DEFLATED):
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = compression
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data)


def export_openraster(render_dir, frame_index, destination):
    """Export an exact rendered frame's separated layers as OpenRaster 0.0.6."""
    render_dir = Path(render_dir).resolve()
    manifest = json.loads((render_dir/"render-manifest.json").read_text("utf-8"))
    if type(frame_index) is not int or not 0 <= frame_index < len(manifest["frames"]):
        raise ValueError("OpenRaster frame index is outside the completed render range")
    entry = manifest["frames"][frame_index]
    if not _output_record_valid(render_dir, entry):
        raise ValueError("source frame missing or altered before OpenRaster export")
    if not entry.get("layers"):
        raise ValueError("OpenRaster handoff needs a render with separated track layers")
    if any(not _output_record_valid(render_dir, layer) for layer in entry["layers"]):
        raise ValueError("source layer missing or altered before OpenRaster export")
    width, height = manifest["resolution"]
    if width*height > MAX_FRAME_PIXELS:
        raise ValueError("OpenRaster canvas exceeds raster budget")
    size_bytes = sum(safe_path(render_dir, layer["path"]).stat().st_size for layer in entry["layers"])
    if size_bytes > MAX_ARCHIVE_BYTES//2:
        raise ValueError("OpenRaster layer payload exceeds adapter allocation budget")
    image_xml = ET.Element("image", {"version": "0.0.6", "w": str(width), "h": str(height),
                                      "name": manifest.get("scene_id", "scene")+" frame "+str(frame_index)})
    stack = ET.SubElement(image_xml, "stack")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name+".partial")
    layer_records = []
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        _zip_write(archive, "mimetype", b"image/openraster", zipfile.ZIP_STORED)
        for index, layer in enumerate(reversed(entry["layers"])):
            relative = f"data/layer{index:04d}.png"
            ET.SubElement(stack, "layer", {"name": layer["id"], "src": relative, "x": "0", "y": "0",
                                           "opacity": "1.0", "visibility": "visible", "composite-op": "svg:src-over"})
            _zip_write(archive, relative, safe_path(render_dir, layer["path"]).read_bytes())
            layer_records.append({"name": layer["id"], "src": relative, "source_sha256": layer["sha256"]})
        background = _color(manifest["settings"]["background"])
        if background[3]:
            relative = "data/background.png"
            ET.SubElement(stack, "layer", {"name": "Render background", "src": relative,
                                           "x": "0", "y": "0", "opacity": "1.0", "visibility": "visible",
                                           "composite-op": "svg:src-over"})
            image = Image.new("RGBA", (width, height), background)
            _zip_write(archive, relative, _png_bytes(image))
            image.close()
        _zip_write(archive, "stack.xml", ET.tostring(image_xml, encoding="utf-8", xml_declaration=True))
        _zip_write(archive, "mergedimage.png", safe_path(render_dir, entry["path"]).read_bytes())
        with Image.open(safe_path(render_dir, entry["path"])) as opened:
            thumbnail = opened.convert("RGBA")
            thumbnail.thumbnail((256, 256), Image.Resampling.LANCZOS)
            _zip_write(archive, "Thumbnails/thumbnail.png", _png_bytes(thumbnail))
            thumbnail.close()
    temporary.replace(destination)
    composed, restored = read_openraster(destination)
    try:
        with Image.open(safe_path(render_dir, entry["path"])) as opened:
            same = composed.tobytes() == opened.convert("RGBA").tobytes()
    finally:
        composed.close()
    if not same:
        raise ValueError("OpenRaster roundtrip did not reconstruct the reference frame exactly")
    return {"schema_version": 1, "adapter_version": ADAPTER_VERSION, "path": destination.name,
            "sha256": file_hash(destination), "frame_index": frame_index,
            "source_frame_sha256": entry["sha256"], "layers": layer_records,
            "roundtrip": {"tested": True, "pixel_exact": True, "layer_count": restored["layer_count"]},
            "application_integration": "not-performed", "format": "OpenRaster 0.0.6 baseline source-over"}


def _member_path(value):
    if not value or "\\" in value:
        raise ValueError("unsafe archive member path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or ":" in value or value != path.as_posix():
        raise ValueError("unsafe archive member path: " + value)
    return path


def read_openraster(source):
    """Validate a bounded source-over ORA and reconstruct it without extraction.

    Integer offsets, visibility, opacity and isolated groups remain editable.
    Unsupported blending/effects fail instead of being silently approximated.
    """
    source = Path(source)
    if source.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("OpenRaster file exceeds 1 GiB bound")
    try:
        archive = zipfile.ZipFile(source)
    except zipfile.BadZipFile as exc:
        raise ValueError("invalid OpenRaster ZIP wrapper") from exc
    with archive:
        infos = archive.infolist()
        names = [entry.filename for entry in infos]
        if not infos or len(infos) > MAX_ARCHIVE_MEMBERS or len(set(names)) != len(names):
            raise ValueError("OpenRaster has duplicate members or exceeds member budget")
        if sum(entry.file_size for entry in infos) > MAX_ARCHIVE_BYTES:
            raise ValueError("OpenRaster decompressed content exceeds 1 GiB bound")
        for entry in infos:
            if entry.orig_filename != entry.filename:
                raise ValueError("unsafe normalized OpenRaster member: " + entry.orig_filename)
            _member_path(entry.filename.rstrip("/"))
            if stat.S_ISLNK(entry.external_attr >> 16) or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise ValueError("OpenRaster links and nonbaseline compression are unsupported")
        if names[0] != "mimetype" or infos[0].compress_type != zipfile.ZIP_STORED or archive.read("mimetype") != b"image/openraster":
            raise ValueError("OpenRaster requires first, uncompressed, exact mimetype member")
        if not {"stack.xml", "mergedimage.png", "Thumbnails/thumbnail.png"}.issubset(names):
            raise ValueError("OpenRaster is missing stack, merged image, or required thumbnail")
        if archive.getinfo("stack.xml").file_size > 1024*1024:
            raise ValueError("OpenRaster XML exceeds 1 MiB bound")
        xml = archive.read("stack.xml")
        if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
            raise ValueError("OpenRaster XML entities are unsupported")
        try:
            root = ET.fromstring(xml)
            width, height = int(root.attrib["w"]), int(root.attrib["h"])
        except (ET.ParseError, KeyError, ValueError) as exc:
            raise ValueError("OpenRaster stack XML or dimensions are invalid") from exc
        if root.tag != "image" or min(width, height) < 1 or width*height > MAX_FRAME_PIXELS:
            raise ValueError("OpenRaster image dimensions exceed raster budget")
        if root.attrib.get("version") not in {"0.0."+str(index) for index in range(1, 7)}:
            raise ValueError("unsupported OpenRaster version; export a 0.0.1–0.0.6 baseline document")
        if len(root) != 1 or root[0].tag != "stack":
            raise ValueError("OpenRaster must have one root layer stack")
        layer_records = []

        def read_png(name):
            _member_path(name)
            if name not in names or not name.endswith(".png"):
                raise ValueError("OpenRaster references a missing or unsupported raster: " + name)
            if archive.getinfo(name).file_size > 64*1024*1024:
                raise ValueError("OpenRaster encoded layer exceeds 64 MiB bound")
            with archive.open(name) as stream, Image.open(stream) as image:
                if image.format != "PNG" or image.width*image.height > MAX_FRAME_PIXELS:
                    raise ValueError("OpenRaster layer exceeds pixel budget or is not PNG")
                return image.convert("RGBA")

        def compose(node, depth=0):
            if depth > 8 or width*height*4*(depth+4) > 256*1024*1024:
                raise ValueError("OpenRaster group depth exceeds bounded compositor memory")
            if node.attrib.get("composite-op", "svg:src-over") != "svg:src-over":
                raise ValueError("unsupported OpenRaster blend; flatten that effect before explicit import")
            if node.tag == "layer":
                name = node.attrib.get("src", "")
                image = read_png(name)
                try:
                    x, y = int(node.attrib.get("x", "0")), int(node.attrib.get("y", "0"))
                except ValueError as exc:
                    image.close()
                    raise ValueError("OpenRaster layer offset must be integer pixels") from exc
                output = Image.new("RGBA", (width, height))
                output.alpha_composite(image, (x, y))
                image.close()
                layer_records.append({"name": node.attrib.get("name", ""), "src": name,
                                      "x": x, "y": y, "visibility": node.attrib.get("visibility", "visible")})
            elif node.tag == "stack":
                if node.attrib.get("isolation", "isolate") != "isolate":
                    raise ValueError("unsupported non-isolated OpenRaster group; isolate it before import")
                output = Image.new("RGBA", (width, height))
                for child in reversed(node):
                    rendered = compose(child, depth+1)
                    output.alpha_composite(rendered)
                    rendered.close()
            else:
                raise ValueError("unsupported OpenRaster element; flatten the effect before explicit import")
            try:
                opacity = float(node.attrib.get("opacity", "1"))
            except ValueError as exc:
                output.close()
                raise ValueError("OpenRaster opacity must be finite and within 0–1") from exc
            visibility = node.attrib.get("visibility", "visible")
            if not math.isfinite(opacity) or not 0 <= opacity <= 1 or visibility not in ("visible", "hidden"):
                output.close()
                raise ValueError("OpenRaster opacity or visibility is invalid")
            if visibility == "hidden":
                opacity = 0
            if opacity != 1:
                output.putalpha(output.getchannel("A").point([round(i*opacity) for i in range(256)]))
            return output

        output = compose(root[0])
        merged = read_png("mergedimage.png")
        merged_exact = merged.size == output.size and merged.tobytes() == output.tobytes()
        merged.close()
        thumbnail = read_png("Thumbnails/thumbnail.png")
        if max(thumbnail.size) > 256:
            thumbnail.close()
            output.close()
            raise ValueError("OpenRaster thumbnail exceeds 256 pixel limit")
        thumbnail.close()
        return output, {"format": root.attrib.get("version"), "resolution": [width, height],
                        "layers": layer_records, "layer_count": len(layer_records),
                        "merged_image_matches": merged_exact, "members": names}


def export_editor_handoff(render_dir, destination, *, selected_frames=None):
    render_dir, destination = Path(render_dir).resolve(), Path(destination).resolve()
    validation = validate_render(render_dir)
    manifest = json.loads((render_dir/"render-manifest.json").read_text("utf-8"))
    if destination == render_dir or destination.is_relative_to(render_dir):
        raise ValueError("editor handoff must be outside the render tree")
    if selected_frames is None:
        selected_frames = sorted({0, manifest["frame_count"]-1,
                                 *[shot["start_frame"] for shot in manifest.get("shots", [])]})
    if (not 1 <= len(selected_frames) <= 32 or len(set(selected_frames)) != len(selected_frames)
            or any(type(x) is not int or x < 0 or x >= manifest["frame_count"] for x in selected_frames)):
        raise ValueError("choose 1–32 distinct completed frames for layered drawing handoff")
    estimated = sum(safe_path(render_dir, frame["path"]).stat().st_size for frame in manifest["frames"])
    estimated += safe_path(render_dir, manifest["audio"]["path"]).stat().st_size
    estimated += sum(safe_path(render_dir, layer["path"]).stat().st_size
                     for index in selected_frames for layer in manifest["frames"][index].get("layers", []))
    if estimated > MAX_HANDOFF_BYTES:
        raise ValueError("editor handoff exceeds 2 GiB file budget; export smaller shots")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("editor handoff destination must be empty; preserve earlier handoffs as evidence")
    destination.mkdir(parents=True, exist_ok=True)
    (destination/"animation").mkdir()
    for frame in manifest["frames"]:
        shutil.copyfile(safe_path(render_dir, frame["path"]), destination/"animation"/f"{frame['index']:06d}.png")
    shutil.copyfile(safe_path(render_dir, manifest["audio"]["path"]), destination/"audio.wav")
    shutil.copyfile(render_dir/"render-manifest.json", destination/"source-render-manifest.json")
    snapshots = [export_openraster(render_dir, frame, destination/"drawings"/f"frame-{frame:06d}.ora")
                 for frame in selected_frames]
    fps = manifest["fps"]
    instructions = f"""# Krita editing handoff

This handoff contains {'synthetic test fixtures' if manifest['fixture'] else 'production raster artwork'}.
Adapter tests are format and pixel checks. They do not confer visual approval.

## Edit drawings

Open a `drawings/frame-NNNNNN.ora` in Krita. Paint layers preserve draw order;
transforms, masks and camera motion are baked into pixels. Save a working KRA.
Export edits to transparent PNG, import as a new asset version, and review them.

## Edit animation

Create a {manifest['resolution'][0]} × {manifest['resolution'][1]} 8-bit sRGB document.
Set the animation rate to {fps['numerator']}/{fps['denominator']} fps and end frame to
{manifest['frame_count']-1}. Use File → Import Animation Frames, select every numbered
PNG in `animation/`, ascending numerical order, start at 0, step 1.
Load `audio.wav` from the Timeline audio menu. Keep the WAV beside the document;
Krita stores its path. If your editor cannot represent this rational frame rate,
preserve the PNG/WAV master and use an editor that can conform its exact timing.

The numbered animation frames are flattened. OpenRaster provides drawing edits;
neither import reconstructs the source rig or an editable transform timeline.

## Official format and consumer references

- OpenRaster file layout: {SOURCES['openraster_files']}
- OpenRaster layer stack: {SOURCES['openraster_stack']}
- Krita frame import: {SOURCES['krita_frames']}
- Krita audio: {SOURCES['krita_audio']}
- Krita local export command: {SOURCES['krita_cli']}
"""
    (destination/"EDITING.md").write_text(instructions, encoding="utf-8")
    files = {path.relative_to(destination).as_posix(): file_hash(path)
             for path in sorted(destination.rglob("*")) if path.is_file()}
    result = {"schema_version": 1, "kind": "krita-portable-handoff", "adapter_version": ADAPTER_VERSION,
              "fixture": manifest["fixture"], "source_render_manifest_sha256": validation["render_manifest_sha256"],
              "frame_count": manifest["frame_count"], "fps": fps, "resolution": manifest["resolution"],
              "audio": {**manifest["audio"], "path": "audio.wav"},
              "animation": {"pattern": "animation/%06d.png", "start_frame": 0, "step": 1},
              "drawings": [{**item, "path": "drawings/"+item["path"]} for item in snapshots],
              "files": files, "exported_assets": True, "adapter_roundtrip_tested": True,
              "application_integration": "not-performed", "format_sources": SOURCES,
              "limitations": ["No native rig or editable transform timeline is reconstructed in Krita.",
                              "PNG animation import is a documented handoff; actual consumer exercise is separate.",
                              "OpenRaster snapshots bake transforms/masks but preserve raster layer order."]}
    atomic_json(destination/"handoff.json", result)
    validate_handoff(destination)
    return result


def validate_handoff(destination):
    """Verify retained source identity, actual animation timing, audio and ORA pixels."""
    destination = Path(destination).resolve()
    manifest = json.loads(safe_path(destination, "handoff.json").read_text("utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("kind") != "krita-portable-handoff":
        raise ValueError("unsupported editor handoff")
    actual = set()
    for path in destination.rglob("*"):
        relative = path.relative_to(destination)
        # Consumer evidence is auxiliary only at its designated root path.
        # Check even excluded paths so a forged evidence symlink cannot redirect
        # a later real consumer export outside this handoff.
        safe_path(destination, relative.as_posix())
        if not path.is_file():
            if not path.is_dir():
                raise ValueError("handoff contains an unsupported special file")
            continue
        if relative.as_posix() in ("handoff.json", "consumer-integration.json") or relative.parts[0] == "consumer-evidence":
            continue
        actual.add(relative.as_posix())
    if actual != set(manifest["files"]):
        raise ValueError("handoff file inventory differs; record edited assets as new versions")
    total = 0
    for name, digest in manifest["files"].items():
        path = safe_path(destination, name)
        total += path.stat().st_size
        if total > MAX_HANDOFF_BYTES:
            raise ValueError("editor handoff exceeds 2 GiB file budget")
        if not path.is_file() or file_hash(path) != digest:
            raise ValueError("editor handoff file missing or changed: " + name)
    retained = safe_path(destination, "source-render-manifest.json")
    if ("source-render-manifest.json" not in manifest["files"]
            or file_hash(retained) != manifest.get("source_render_manifest_sha256")):
        raise ValueError("handoff source render manifest hash does not match retained evidence")
    source = json.loads(retained.read_text("utf-8"))
    if (source.get("schema_version") != 1 or source.get("kind") not in ("scene-render", "shot-render")
            or source.get("status") != "complete"):
        raise ValueError("handoff source render manifest must describe a completed supported render")
    for key in ("fixture", "frame_count", "fps", "resolution"):
        if manifest.get(key) != source.get(key):
            raise ValueError("handoff " + key + " differs from its retained source render manifest")
    count = source["frame_count"]
    if type(count) is not int or not 1 <= count <= MAX_RENDER_FRAMES:
        raise ValueError("editor frame count exceeds positive render bounds")
    if [entry["index"] for entry in source["frames"]] != list(range(count)):
        raise ValueError("retained source render indices are not exact and contiguous")
    size = source["resolution"]
    if not isinstance(size, list) or len(size) != 2 or any(type(n) is not int or n < 1 for n in size) or size[0]*size[1] > MAX_FRAME_PIXELS:
        raise ValueError("handoff source resolution exceeds bounded positive raster dimensions")
    fps_fraction(source["fps"])
    if source.get("settings", {}).get("fps") != source["fps"] or [source["settings"].get("width"), source["settings"].get("height")] != size:
        raise ValueError("retained source settings disagree with frame timing or resolution")
    if manifest.get("animation") != {"pattern": "animation/%06d.png", "start_frame": 0, "step": 1}:
        raise ValueError("handoff animation import settings change source frame timing")
    frames = sorted((destination/"animation").glob("*.png"))
    if [path.name for path in frames] != [f"{index:06d}.png" for index in range(count)]:
        raise ValueError("editor frame sequence does not reconstruct exact ordering")
    for entry, path in zip(source["frames"], frames):
        if file_hash(path) != entry["sha256"]:
            raise ValueError("handoff animation differs from retained source frame: " + str(entry["index"]))
        with Image.open(path) as image:
            if image.format != "PNG" or image.mode != "RGBA" or list(image.size) != size:
                raise ValueError("handoff frame format/resolution/alpha differs from source contract")
            image.verify()
    source_audio = source.get("audio")
    if not isinstance(source_audio, dict) or manifest.get("audio") != {**source_audio, "path": "audio.wav"}:
        raise ValueError("handoff audio metadata differs from retained source render manifest")
    audio = manifest["audio"]
    _, _, pcm = _wave_info(destination, audio)
    expected = sample_at_frame(count, audio["sample_rate"], source["fps"])
    if (pcm["sample_count"] != expected or any(pcm[key] != audio.get(key) for key in pcm)
            or audio.get("fps") != source["fps"] or audio.get("frame_count") != count):
        raise ValueError("handoff actual PCM timing/rate/channels differ from retained source contract")
    if not isinstance(manifest.get("drawings"), list) or not 1 <= len(manifest["drawings"]) <= 32:
        raise ValueError("handoff requires 1–32 layered drawing records")
    drawing_indices = set()
    for record in manifest["drawings"]:
        index = record["frame_index"]
        if type(index) is not int or not 0 <= index < count or index in drawing_indices:
            raise ValueError("handoff drawing frame index is invalid or repeated")
        drawing_indices.add(index)
        path = safe_path(destination, record["path"])
        if (manifest["files"].get(record["path"]) != record["sha256"]
                or record["source_frame_sha256"] != source["frames"][index]["sha256"]):
            raise ValueError("handoff drawing hashes do not match retained file and source frame")
        reconstructed, info = read_openraster(path)
        try:
            with Image.open(destination/"animation"/f"{index:06d}.png") as frame:
                if (list(reconstructed.size) != size or reconstructed.tobytes() != frame.convert("RGBA").tobytes()
                        or not info["merged_image_matches"]):
                    raise ValueError("OpenRaster roundtrip disagrees with numbered PNG frame")
        finally:
            reconstructed.close()
    return {"ok": True, "exported_assets": True, "adapter_roundtrip_tested": True,
            "frame_count": len(frames), "drawings": len(manifest["drawings"]),
            "application_integration": "not-performed", "handoff_sha256": file_hash(destination/"handoff.json")}


def exercise_krita(destination, *, executable=None, timeout=60):
    """Exercise an available Krita in temporary isolated configuration.

    Tests actual ORA → PNG and ORA → ORA file roundtrips. Timeline import is a
    distinct manual consumer exercise. No software is installed or configured.
    """
    destination = Path(destination).resolve()
    validate_handoff(destination)
    manifest = json.loads((destination/"handoff.json").read_text("utf-8"))
    executable = executable or shutil.which("krita")
    report = {"schema_version": 1, "consumer": "Krita", "exported_assets": True,
              "adapter_roundtrip_tested": True, "application_integration": "not-performed",
              "timeline_integration": "not-performed", "handoff_sha256": file_hash(destination/"handoff.json")}
    report_path = safe_path(destination, "consumer-integration.json")
    evidence = safe_path(destination, "consumer-evidence")
    output_paths = {suffix: safe_path(destination, "consumer-evidence/krita-roundtrip."+suffix)
                    for suffix in ("png", "ora")}
    if not executable:
        report["reason"] = "Krita executable is unavailable in this environment. No application was installed."
        atomic_json(report_path, report)
        return report
    evidence.mkdir(exist_ok=True)
    source = safe_path(destination, manifest["drawings"][0]["path"])
    commands = []
    try:
        with tempfile.TemporaryDirectory(prefix="hatch-krita-") as temporary:
            environment = dict(os.environ)
            environment.update({"QT_QPA_PLATFORM": "offscreen", "XDG_CONFIG_HOME": temporary+"/config",
                                "XDG_CACHE_HOME": temporary+"/cache", "XDG_DATA_HOME": temporary+"/data"})
            version = subprocess.run([str(executable), "--version"], env=environment, capture_output=True,
                                     text=True, timeout=timeout)
            report["version"] = (version.stdout+version.stderr).strip()[:1000]
            for suffix in ("png", "ora"):
                output = output_paths[suffix]
                command = [str(executable), str(source), "--export", "--export-filename", str(output)]
                run = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=timeout)
                commands.append({"arguments": ["krita", source.name, "--export", "--export-filename", output.name],
                                 "returncode": run.returncode, "diagnostics": (run.stdout+run.stderr)[-4000:]})
                if run.returncode or not output.is_file():
                    raise ValueError("Available Krita could not import and export the layered snapshot.")
            original, original_info = read_openraster(source)
            restored, restored_info = read_openraster(evidence/"krita-roundtrip.ora")
            with Image.open(evidence/"krita-roundtrip.png") as output:
                exported = output.convert("RGBA")
                same_size = exported.size == original.size and restored.size == original.size
                differences = ImageChops.difference(original, exported).getextrema() if same_size else None
                maximum = max(pair[1] for pair in differences) if differences else 255
                restored_delta = max(pair[1] for pair in ImageChops.difference(original, restored).getextrema()) if same_size else 255
                exported.close()
            original.close()
            restored.close()
            layers_preserved = restored_info["layer_count"] == original_info["layer_count"]
            report.update(application_integration="verified" if same_size and maximum <= 1 and restored_delta <= 1 and layers_preserved else "failed",
                          commands=commands, maximum_png_channel_difference=maximum,
                          maximum_ora_channel_difference=restored_delta, layers_preserved=layers_preserved)
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        report.update(application_integration="failed", commands=commands, reason=str(exc))
    atomic_json(report_path, report)
    return report
