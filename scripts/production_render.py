#!/usr/bin/env python3
"""Bounded deterministic compositor for production project schema 1.

PNG frames and PCM WAV samples are the timing authority. Browser playback and
encoded movies are review conveniences, independently verified where possible.
No artwork generation, live application installation or settings changes occur.
"""
from __future__ import annotations

import array
from collections import OrderedDict
from contextlib import ExitStack
import errno
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import wave

from PIL import Image, ImageChops, ImageDraw, PngImagePlugin, __version__ as PILLOW_VERSION

RENDERER_VERSION = "1.0.0"
MAX_FRAME_PIXELS = 4096 * 2160
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_CACHE_BYTES = 64 * 1024 * 1024
MAX_AUDIO_TRACKS = 32
MAX_AUDIO_SAMPLES = 192000 * 60 * 30
MAX_AUDIO_BLOCK = 4096
MAX_RENDER_FRAMES = 18000
MAX_LAYERS = 256
MAX_RENDER_OUTPUT_BYTES = 4 * 1024 * 1024 * 1024
IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def object_hash(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_bytes(canonical(value) + b"\n")
    temporary.replace(path)


def renderer_identity():
    folder = Path(__file__).resolve().parent
    implementation = {name: file_hash(folder/name) for name in
                      ("production_render.py", "production_performance.py", "production_contracts.py")}
    return {"id": "hatch-reference-rgba", "version": RENDERER_VERSION,
            "code_sha256": object_hash(implementation), "implementation": implementation,
            "pillow": PILLOW_VERSION, "python": sys.version.split()[0],
            "compositing": "8-bit encoded-srgb source-over; straight output alpha",
            "filtering": "premultiplied-alpha affine except exact nearest"}


def safe_path(root, relative):
    root = Path(root).resolve()
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative or relative == ".":
        raise ValueError("source/output paths must be nonempty portable relative paths")
    value = Path(relative)
    if value.is_absolute() or ".." in value.parts:
        raise ValueError("path escapes project/output: " + relative)
    current = root
    for part in value.parts:
        current = current/part
        if current.is_symlink():
            raise ValueError("operational source/output path contains a symlink: " + relative)
    target = (root/value).resolve()
    if not target.is_relative_to(root):
        raise ValueError("path escapes project/output: " + relative)
    return target


def fps_fraction(value):
    if not isinstance(value, dict) or set(value) != {"numerator", "denominator"}:
        raise ValueError("fps requires integer numerator and denominator")
    numerator, denominator = value["numerator"], value["denominator"]
    if type(numerator) is not int or type(denominator) is not int or not 1 <= numerator <= 240000 or not 1 <= denominator <= 10000:
        raise ValueError("fps numerator/denominator exceed positive integer bounds")
    result = Fraction(numerator, denominator)
    if not Fraction(1, 1) <= result <= Fraction(120, 1):
        raise ValueError("production frame rate must be 1–120 fps")
    return result


def sample_at_frame(frame, rate, fps):
    """Nearest sample; ties round up using integer arithmetic."""
    f = fps_fraction(fps) if isinstance(fps, dict) else fps
    n = int(frame) * int(rate) * f.denominator
    return (2 * n + f.numerator) // (2 * f.numerator)


def multiply(left, right):
    a, b, c, d, e, f = left
    g, h, i, j, k, l = right
    return (a*g+c*h, b*g+d*h, a*i+c*j, b*i+d*j, a*k+c*l+e, b*k+d*l+f)


def translation(x, y):
    return (1.0, 0.0, 0.0, 1.0, float(x), float(y))


def scaling(x, y=None):
    return (float(x), 0.0, 0.0, float(x if y is None else y), 0.0, 0.0)


def rotation(degrees):
    angle = math.radians(degrees)
    c, s = math.cos(angle), math.sin(angle)
    return (c, s, -s, c, 0.0, 0.0)


def transform_point(matrix, point):
    a, b, c, d, e, f = matrix
    return [a*point[0]+c*point[1]+e, b*point[0]+d*point[1]+f]


def local_matrix(position=(0, 0), angle=0, scale=1, pivot=(0, 0)):
    sx, sy = scale if isinstance(scale, (tuple, list)) else (scale, scale)
    return multiply(multiply(multiply(translation(*position), rotation(angle)), scaling(sx, sy)),
                    translation(-pivot[0], -pivot[1]))


def inverse_pillow(matrix):
    a, b, c, d, e, f = matrix
    determinant = a*d-b*c
    if not math.isfinite(determinant) or abs(determinant) < 1e-10:
        raise ValueError("singular transform; scales must stay finite and nonzero")
    values = (d/determinant, -c/determinant, (c*f-d*e)/determinant,
              -b/determinant, a/determinant, (b*e-a*f)/determinant)
    if any(not math.isfinite(v) or abs(v) > 1e9 for v in values):
        raise ValueError("transform exceeds finite coordinate bounds")
    return values


def _save_png(image, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    info = PngImagePlugin.PngInfo()
    info.add(b"sRGB", b"\x00")
    image.save(temporary, format="PNG", compress_level=6, optimize=False, pnginfo=info)
    temporary.replace(path)


class AssetCache:
    """Hash-verified LRU of decoded source images, bounded independently of time."""
    def __init__(self, root, max_bytes=MAX_CACHE_BYTES, max_source_pixels=2000000, *, max_pixels=None):
        self.root = Path(root).resolve()
        self.max_bytes = min(MAX_CACHE_BYTES, max_bytes)
        if type(self.max_bytes) is not int or self.max_bytes < 4:
            raise ValueError("asset cache must have a positive bounded byte budget")
        self.max_source_pixels = max_source_pixels if max_pixels is None else max_pixels
        self.images = OrderedDict()
        self.used_bytes = 0
        self.peak_bytes = 0

    def source(self, reference):
        path = safe_path(self.root, reference["path"])
        if not path.is_file() or path.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError("source raster missing or exceeds 64 MiB encoded bound: " + reference["path"])
        digest = file_hash(path)
        if reference.get("sha256") and reference["sha256"] != digest:
            raise ValueError("source raster hash changed: " + reference["path"])
        return path, digest

    def get(self, reference):
        path, digest = self.source(reference)
        key = (path, digest)
        if key in self.images:
            self.images.move_to_end(key)
            return self.images[key]
        with Image.open(path) as opened:
            if opened.format not in ("PNG", "WEBP") or opened.width*opened.height > self.max_source_pixels:
                raise ValueError("source raster format or pixel count exceeds configured bound: " + reference["path"])
            if reference.get("size") and list(opened.size) != reference["size"]:
                raise ValueError("source raster dimensions differ from declared image-local viewport: " + reference["path"])
            if "A" not in opened.getbands() and "transparency" not in opened.info:
                raise ValueError("source raster requires an explicit alpha channel: " + reference["path"])
            size = opened.width*opened.height*4
            if size > self.max_bytes:
                raise ValueError("source raster exceeds decoded cache budget: " + reference["path"])
            while self.images and self.used_bytes+size > self.max_bytes:
                _, evicted = self.images.popitem(last=False)
                self.used_bytes -= evicted.width*evicted.height*4
                evicted.close()
            image = opened.convert("RGBA")
        self.images[key] = image
        self.used_bytes += size
        self.peak_bytes = max(self.peak_bytes, self.used_bytes)
        return image

    def close(self):
        for image in self.images.values():
            image.close()
        self.images.clear()
        self.used_bytes = 0


def _affine(image, size, matrix, resampling):
    filters = {"nearest": Image.Resampling.NEAREST, "bilinear": Image.Resampling.BILINEAR,
               "bicubic": Image.Resampling.BICUBIC}
    if resampling not in filters:
        raise ValueError("production affine resampling must be nearest, bilinear, or bicubic")
    original = image if resampling == "nearest" else image.convert("RGBa")
    transformed = original.transform(size, Image.Transform.AFFINE, inverse_pillow(matrix),
                                     resample=filters[resampling])
    if original is not image:
        original.close()
    if resampling == "nearest":
        return transformed
    output = transformed.convert("RGBA")
    transformed.close()
    return output


def render_layer(layer, size, cache, resampling="bicubic"):
    if not layer.get("visible", True):
        return Image.new("RGBA", size)
    source = cache.get(layer["image"])
    mask_ref = layer.get("mask")
    owned_source = False
    if mask_ref is not None:
        # Copy before the second cache read; a small LRU may evict the drawing.
        source = source.copy()
        owned_source = True
        mask = cache.get(mask_ref)
        if mask.size != source.size:
            source.close()
            raise ValueError("image-local mask dimensions must match component drawing: " + layer["id"])
        source.putalpha(ImageChops.multiply(source.getchannel("A"), mask.getchannel("A")))
    try:
        output = _affine(source, size, layer["matrix"], resampling)
    finally:
        if owned_source:
            source.close()
    opacity = layer.get("opacity", 1)
    if type(opacity) not in (int, float) or not math.isfinite(opacity) or not 0 <= opacity <= 1:
        output.close()
        raise ValueError("layer opacity must be between zero and one")
    if opacity != 1:
        output.putalpha(output.getchannel("A").point([round(i * opacity) for i in range(256)]))
    return output


def _color(value):
    if not isinstance(value, str) or len(value) != 9 or value[0] != "#":
        raise ValueError("render background must be #RRGGBBAA")
    try:
        return tuple(int(value[i:i+2], 16) for i in (1, 3, 5, 7))
    except ValueError as exc:
        raise ValueError("render background must be #RRGGBBAA") from exc


def _bundle(value):
    if isinstance(value, (str, Path)):
        from production_contracts import load_project
        return load_project(value)
    return value


def _settings(bundle, shot):
    settings = bundle["project"]["render"]
    width, height = settings["width"], settings["height"]
    if type(width) is not int or type(height) is not int or min(width, height) < 1 or width*height > MAX_FRAME_PIXELS:
        raise ValueError("render resolution exceeds bounded positive raster dimensions")
    fps_fraction(settings["fps"])
    if settings.get("color_space") != "srgb" or settings.get("alpha") != "straight":
        raise ValueError("renderer requires encoded sRGB and straight alpha output")
    if settings.get("resampling") not in ("nearest", "bilinear", "bicubic"):
        raise ValueError("resampling must be nearest, bilinear, or bicubic")
    _color(settings["background"])
    layers = len(shot.get("layers", []))+len(shot.get("props", []))
    layers += sum(len(bundle["characters"][instance["character"]]["components"])
                  for instance in shot.get("instances", []))
    if layers > MAX_LAYERS:
        raise ValueError("shot exceeds 256 raster layer budget")
    budget = bundle["project"].get("limits", {}).get("max_work_bytes", 256*1024*1024)
    cache_bytes = min(MAX_CACHE_BYTES, max(4, budget//2))
    estimate = cache_bytes+width*height*4*8
    if estimate > budget:
        raise ValueError("render raster work estimate exceeds max_work_bytes")
    return settings, cache_bytes, estimate


def _wave_info(root, reference, expected_rate=None):
    path = safe_path(root, reference["path"])
    if not path.is_file() or path.stat().st_size > 512 * 1024 * 1024:
        raise ValueError("audio file missing or larger than 512 MiB: " + reference["path"])
    digest = file_hash(path)
    if reference.get("sha256") and reference["sha256"] != digest:
        raise ValueError("audio source hash changed: " + reference["path"])
    try:
        with wave.open(str(path), "rb") as source:
            info = {"sample_rate": source.getframerate(), "channels": source.getnchannels(),
                    "sample_width": source.getsampwidth(), "sample_count": source.getnframes()}
            if source.getcomptype() != "NONE" or info["sample_width"] != 2 or info["channels"] not in (1, 2):
                raise ValueError("audio must be uncompressed PCM signed 16-bit mono or stereo WAV")
            if not 8000 <= info["sample_rate"] <= 192000 or info["sample_count"] > MAX_AUDIO_SAMPLES:
                raise ValueError("audio rate/sample count exceeds resource limits")
            if expected_rate and info["sample_rate"] != expected_rate:
                raise ValueError("audio sample rate mismatch; explicitly convert supplied audio before importing")
            if info["sample_count"]:
                source.setpos(info["sample_count"]-1)
                if len(source.readframes(1)) != info["channels"]*info["sample_width"]:
                    raise ValueError("truncated audio PCM payload: " + reference["path"])
    except wave.Error as exc:
        raise ValueError("invalid PCM WAV: " + reference["path"]) from exc
    return path, digest, info


def _sample(track, frame, default):
    from production_performance import evaluate_track
    return evaluate_track(track, frame, default) if track is not None else default


def _vector_add(left, right):
    return [left[0]+right[0], left[1]+right[1]]


def _owner_at(prop, frame, include_current=True):
    owner, attachment = prop.get("owner"), prop.get("attachment")
    for change in prop.get("ownership", []):
        if change["frame"] < frame or include_current and change["frame"] == frame:
            if change["from"] != owner:
                raise ValueError("contradictory previous owner for prop " + prop["id"])
            owner, attachment = change["to"], change.get("attachment")
    return owner, attachment


def _attachment_point(attachment, actors):
    try:
        return actors[attachment["instance"]]["components"][attachment["component"]]["anchors"][attachment["anchor"]]
    except KeyError as exc:
        raise ValueError("missing interaction attachment " + canonical(attachment).decode()) from exc


def _scene_id(bundle, shot_id):
    for scene in bundle["scenes"]:
        if any(shot["id"] == shot_id for shot in scene["shots"]):
            return scene["id"]
    raise ValueError("shot is not part of a project scene: " + shot_id)


def _output_record_valid(root, entry):
    try:
        path = safe_path(root, entry["path"])
        return path.is_file() and file_hash(path) == entry["sha256"]
    except (ValueError, OSError, KeyError, TypeError):
        return False


def _visual_signature(state, cache, identity):
    settings = state["settings"]
    sources, layers = {}, []
    for layer in state["layers"]:
        signature = {key: layer.get(key) for key in ("id", "track", "z", "matrix", "visible", "opacity")}
        for key in ("image", "mask"):
            reference = layer.get(key)
            if reference is None:
                signature[key] = None
            else:
                _, digest = cache.source(reference)
                source = {"path": reference["path"], "sha256": digest}
                sources[reference["path"]] = digest
                signature[key] = source
        layers.append(signature)
    value = {"renderer": identity, "resolution": [settings["width"], settings["height"]],
             "resampling": settings["resampling"], "background": settings["background"],
             "color_space": settings["color_space"], "alpha": settings["alpha"], "layers": layers}
    return object_hash(value), dict(sorted(sources.items())), layers


def _read_checkpoint(path):
    try:
        value = json.loads(path.read_text("utf-8"))
    except (ValueError, OSError) as exc:
        raise ValueError("render manifest is corrupt; restore it or render to a fresh destination") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("render manifest is corrupt or unsupported; use a fresh destination")
    return value


def _lock_output(path):
    """Acquire a nonblocking OS lock; process exit releases it automatically."""
    lock = path.open("a+b")
    try:
        try:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:
            import msvcrt
            if path.stat().st_size == 0:
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except (BlockingIOError, OSError) as exc:
        lock.close()
        raise ValueError("render destination is currently owned by another renderer") from exc
    return lock


def render_shot(bundle, shot_id, output_dir, *, resume=True, max_frames=None,
                track_layers=True, progress=None):
    """Render incrementally; all reused frames/layers are hash verified.

    The returned operation counters are ephemeral. Persisted manifests depend
    only on inputs and implementation identity, not cache hits or elapsed time.
    """
    bundle = _bundle(bundle)
    if shot_id not in bundle["shots"]:
        raise ValueError("unknown shot: " + str(shot_id))
    shot = bundle["shots"][shot_id]
    settings, cache_bytes, estimate = _settings(bundle, shot)
    duration = shot["duration_frames"]
    limit = min(MAX_RENDER_FRAMES, bundle["project"].get("limits", {}).get("max_frames", MAX_RENDER_FRAMES))
    if type(duration) is not int or not 1 <= duration <= limit:
        raise ValueError("shot frame count exceeds configured limit")
    if max_frames is not None and (type(max_frames) is not int or max_frames < 1):
        raise ValueError("max_frames must be a positive work budget")
    output_dir = Path(output_dir).resolve()

    def check_owner():
        manifest_path = safe_path(output_dir, "render-manifest.json")
        if manifest_path.exists():
            previous = _read_checkpoint(manifest_path)
            if (previous.get("kind") != "shot-render" or previous.get("shot_id") != shot_id
                    or previous.get("project_id") != bundle["project"]["id"]):
                raise ValueError("destination belongs to a different project/shot or render kind")

    check_owner()
    output_dir.mkdir(parents=True, exist_ok=True)
    with _lock_output(safe_path(output_dir, ".render.lock")):
        check_owner()
        return _render_shot_locked(bundle, shot_id, output_dir, settings, cache_bytes, estimate,
                                   resume, max_frames, track_layers, progress)


def _render_shot_locked(bundle, shot_id, output_dir, settings, cache_bytes, estimate,
                        resume, max_frames, track_layers, progress):
    shot = bundle["shots"][shot_id]
    duration = shot["duration_frames"]
    layer_bound = len(shot.get("layers", []))+len(shot.get("props", []))
    layer_bound += sum(len(bundle["characters"][instance["character"]]["components"])
                       for instance in shot.get("instances", []))
    metadata_estimate = duration*(1024*layer_bound+2048)
    if estimate+metadata_estimate > bundle["project"].get("limits", {}).get("max_work_bytes", 256*1024*1024):
        raise ValueError("render frame/layer manifest estimate exceeds max_work_bytes; split the shot or reduce layers")
    manifest_path = output_dir/"render-manifest.json"
    previous = _read_checkpoint(manifest_path) if resume and manifest_path.is_file() else {}
    old_frames = {entry["index"]: entry for entry in previous.get("frames", [])}
    signatures, known_layers = {}, {}
    for entry in previous.get("frames", []):
        signatures.setdefault(entry.get("evaluation_sha256"), entry)
        known_layers.update({layer["path"]: layer for layer in entry.get("layers", [])})
    identity = renderer_identity()
    from production_workflow import shot_dependencies
    scene_id = _scene_id(bundle, shot_id)
    dependencies = shot_dependencies(bundle["root"], scene_id, shot_id, project=bundle)
    manifest = {"schema_version": 1, "kind": "shot-render", "renderer": identity,
                "project_id": bundle["project"]["id"], "scene_id": scene_id, "shot_id": shot_id,
                "fixture": bundle["project"]["fixture"], "status": "partial", "settings": settings,
                "fps": settings["fps"], "resolution": [settings["width"], settings["height"]],
                "frame_count": duration, "dependencies": dependencies, "frames": [], "audio": None,
                "resource_estimate": {"raster_work_bytes": estimate, "cache_bytes": cache_bytes,
                                      "frame_manifest_work_bytes": metadata_estimate,
                                      "frame_buffer_count": "bounded independent of shot duration"},
                "preview_is_timing_authority": False}
    manifest["dialogue"] = [{"id": track["id"], "speaker": track.get("speaker"),
                              "start_frame": track["start_frame"],
                              "end_frame": track["start_frame"]+track["duration_frames"],
                              "text": track.get("text", ""), "mouth_cues": track.get("mouth_cues", [])}
                             for track in shot.get("audio", [])]
    cache = AssetCache(bundle["root"], cache_bytes,
                       bundle["project"].get("limits", {}).get("max_source_pixels", 2000000))
    rendered_count, reused_count, reused_layers = 0, 0, 0
    sizes = {path: path.stat().st_size for directory in (output_dir/"frames", output_dir/"layers")
             if directory.is_dir() for path in directory.glob("*.png") if path.is_file()}
    output_bytes = sum(sizes.values())

    def bounded_save(image, target):
        nonlocal output_bytes
        reserve = image.width*image.height*4+65536
        if output_bytes-sizes.get(target, 0)+reserve > MAX_RENDER_OUTPUT_BYTES:
            raise ValueError("render output cache reached 4 GiB bound; preserve/archive it and use a fresh destination or smaller shot")
        _save_png(image, target)
        actual = target.stat().st_size
        output_bytes += actual-sizes.get(target, 0)
        sizes[target] = actual

    try:
        for index in range(duration):
            state = evaluate_frame(bundle, shot_id, index)
            signature, sources, layer_signatures = _visual_signature(state, cache, identity)
            prior = old_frames.get(index)
            if prior is None or prior.get("evaluation_sha256") != signature:
                prior = signatures.get(signature)
            layer_ok = prior is not None and (not track_layers or
                bool(prior.get("layers")) and all(_output_record_valid(output_dir, x) for x in prior["layers"]))
            relative = "frames/" + f"{index:06d}.png"
            if prior is not None and prior.get("evaluation_sha256") == signature and layer_ok and _output_record_valid(output_dir, prior):
                if prior["path"] != relative:
                    target = safe_path(output_dir, relative)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    original = safe_path(output_dir, prior["path"])
                    actual = original.stat().st_size
                    if output_bytes-sizes.get(target, 0)+actual > MAX_RENDER_OUTPUT_BYTES:
                        raise ValueError("render output cache reached 4 GiB bound; use a fresh destination or smaller shot")
                    temporary = target.with_name(target.name+".partial")
                    shutil.copyfile(original, temporary)
                    temporary.replace(target)
                    output_bytes += actual-sizes.get(target, 0)
                    sizes[target] = actual
                entry = {**prior, "index": index, "path": relative, "sources": sources}
                reused_count += 1
            else:
                if max_frames is not None and rendered_count >= max_frames:
                    break
                image = Image.new("RGBA", (settings["width"], settings["height"]), _color(settings["background"]))
                layer_entries = []
                for layer, layer_signature in zip(state["layers"], layer_signatures):
                    key = object_hash({"renderer": identity, "size": list(image.size),
                                       "resampling": settings["resampling"], "layer": layer_signature})
                    layer_path = "layers/" + key + ".png"
                    layer_target = safe_path(output_dir, layer_path)
                    expected = known_layers.get(layer_path)
                    if track_layers and expected is not None and _output_record_valid(output_dir, expected):
                        with Image.open(layer_target) as opened:
                            if opened.format != "PNG" or opened.size != image.size or opened.mode != "RGBA":
                                raise ValueError("cached preview layer resolution/alpha changed: " + layer_path)
                            raster = opened.convert("RGBA")
                        reused_layers += 1
                    else:
                        raster = render_layer(layer, image.size, cache, settings["resampling"])
                        if track_layers:
                            bounded_save(raster, layer_target)
                    image.alpha_composite(raster)
                    raster.close()
                    if track_layers:
                        record = {"id": layer["id"], "track": layer["track"], "z": layer["z"],
                                  "path": layer_path, "sha256": file_hash(layer_target)}
                        layer_entries.append(record)
                        known_layers[layer_path] = record
                target = safe_path(output_dir, relative)
                bounded_save(image, target)
                image.close()
                entry = {"index": index, "path": relative, "sha256": file_hash(target),
                         "evaluation_sha256": signature, "sources": sources, "layers": layer_entries}
                rendered_count += 1
            entry["events"] = {key: value["performance"].get("events", [])
                               for key, value in state["instances"].items() if value["performance"].get("events")}
            entry["interactions"] = state["interactions"]
            manifest["frames"].append(entry)
            signatures.setdefault(signature, entry)
            manifest["completed_frames"] = len(manifest["frames"])
            atomic_json(manifest_path, manifest)
            if progress is not None:
                progress({"frame": index, "completed": len(manifest["frames"]), "total": duration,
                          "rendered": rendered_count, "reused": reused_count})
        if len(manifest["frames"]) == duration:
            audio = shot.get("audio", [])
            rate = _wave_info(bundle["root"], audio[0]["file"])[2]["sample_rate"] if audio else 48000
            manifest["audio"] = mix_audio(bundle["root"], audio, output_dir/"audio.wav", duration,
                                           settings["fps"], sample_rate=rate)
            manifest["status"] = "complete"
            atomic_json(manifest_path, manifest)
            write_preview(output_dir, manifest)
        else:
            manifest["recovery"] = "Rerun the same render command; all completed files are hash-verified before reuse."
            atomic_json(manifest_path, manifest)
        return {**manifest, "operation": {"rendered_frames": rendered_count, "reused_frames": reused_count,
                                          "reused_layers": reused_layers, "peak_cache_bytes": cache.peak_bytes}}
    finally:
        cache.close()


def write_preview(output_dir, manifest=None):
    output_dir = Path(output_dir)
    manifest = manifest or json.loads((output_dir/"render-manifest.json").read_text("utf-8"))
    template = Path(__file__).resolve().parents[1]/"assets/production-preview.html"
    script = template.with_suffix(".js")
    metadata = canonical(manifest).decode("utf-8").replace("<", "\\u003c").replace("&", "\\u0026")
    html = template.read_text("utf-8").replace("__METADATA__", metadata).replace("__PREVIEW__", script.read_text("utf-8"))
    (output_dir/"preview.html").write_text(html, encoding="utf-8")
    return output_dir/"preview.html"


def validate_render(output_dir, *, require_complete=True):
    """Offline image hashes, frame count, rational timestamps, and PCM duration."""
    output_dir = Path(output_dir)
    manifest = _read_checkpoint(output_dir/"render-manifest.json")
    if manifest.get("kind") not in ("shot-render", "scene-render"):
        raise ValueError("unsupported render manifest")
    frames = manifest["frames"]
    if require_complete and (manifest["status"] != "complete" or len(frames) != manifest["frame_count"]):
        raise ValueError("render is incomplete; resume it before final timing validation")
    if type(manifest["frame_count"]) is not int or not 1 <= manifest["frame_count"] <= MAX_RENDER_FRAMES:
        raise ValueError("render frame count exceeds bounded positive range")
    if [entry["index"] for entry in frames] != list(range(len(frames))):
        raise ValueError("render frame indices are not exact and contiguous")
    size = manifest["resolution"]
    if not isinstance(size, list) or len(size) != 2 or any(type(n) is not int or n < 1 for n in size) or size[0]*size[1] > MAX_FRAME_PIXELS:
        raise ValueError("render resolution exceeds bounded positive range")
    for entry in frames:
        for record, label in [(entry, "rendered frame"), *[(layer, "preview layer") for layer in entry.get("layers", [])]]:
            if not _output_record_valid(output_dir, record):
                raise ValueError(label + " missing or changed: " + record["path"])
            with Image.open(safe_path(output_dir, record["path"])) as image:
                if image.format != "PNG" or list(image.size) != size or image.mode != "RGBA":
                    raise ValueError(label + " format/resolution/alpha mismatch: " + record["path"])
                image.verify()
    audio = manifest.get("audio")
    if manifest["status"] == "complete":
        if not audio or not _output_record_valid(output_dir, audio):
            raise ValueError("mixed audio is missing or changed")
        _, _, info = _wave_info(output_dir, audio)
        expected = sample_at_frame(manifest["frame_count"], audio["sample_rate"], manifest["fps"])
        if info["sample_count"] != expected or any(info[key] != audio[key] for key in info):
            raise ValueError("offline audiovisual duration/channel/rate/sample count mismatch")
    fps = fps_fraction(manifest["fps"])
    duration = Fraction(manifest["frame_count"], 1)/fps
    return {"ok": True, "kind": "offline-frame-and-pcm-validation", "frame_count": len(frames),
            "fps": manifest["fps"], "duration": {"numerator": duration.numerator, "denominator": duration.denominator},
            "sample_count": audio["sample_count"] if audio else None,
            "render_manifest_sha256": file_hash(output_dir/"render-manifest.json"),
            "visual_review": "not-performed", "application_integration": "not-performed"}


def _publish_scene_frame(source, destination, expected_hash):
    """Atomically link each scene frame only to its identical own shot frame."""
    source, destination = Path(source), Path(destination)
    if file_hash(source) != expected_hash:
        raise ValueError("shot frame changed during scene assembly: " + str(source))
    if destination.is_file() and os.path.samefile(source, destination):
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".scene-frame-", suffix=".tmp", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(name)
    temporary.unlink()
    try:
        try:
            os.link(source, temporary)
        except OSError as exc:
            if exc.errno not in {errno.EXDEV, errno.EPERM, errno.EACCES, errno.ENOSYS, errno.ENOTSUP, errno.EMLINK}:
                raise
            if destination.is_file() and file_hash(destination) == expected_hash:
                return
            shutil.copyfile(source, temporary)
        if file_hash(temporary) != expected_hash:
            raise ValueError("scene frame publication does not match its shot source")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _check_scene_destination(output_dir, project_id, scene_id):
    """Reject foreign/corrupt scene ownership before changing any output.

    Older first-shot interruptions may have only a shot checkpoint. Its retained
    scene/project identity is checked even when a caller disables cache reuse.
    """
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError("scene render destination must be a directory")
    manifest_path = safe_path(output_dir, "render-manifest.json")
    candidates = [(manifest_path, "scene-render", None),
                  (safe_path(output_dir, "render-manifest.json.partial"), "scene-render", None)]
    shots_dir = safe_path(output_dir, "shots")
    for path in sorted(shots_dir.glob("*/render-manifest.json*")):
        if path.name in ("render-manifest.json", "render-manifest.json.partial"):
            candidates.append((safe_path(output_dir, path.relative_to(output_dir).as_posix()),
                               "shot-render", path.parent.name))
    owned = False
    for path, kind, shot_id in candidates:
        if not path.exists():
            continue
        retained = _read_checkpoint(path)
        if (retained.get("kind") != kind or retained.get("project_id") != project_id
                or retained.get("scene_id") != scene_id
                or shot_id is not None and retained.get("shot_id") != shot_id):
            raise ValueError("destination belongs to a different project/scene or render kind")
        owned = True
    if not owned and (any((output_dir/name).exists() for name in ("frames", "layers", "audio.wav"))
                      or shots_dir.is_dir() and any(shots_dir.iterdir())):
        raise ValueError("scene destination has output without an ownership checkpoint; use a fresh destination")
    return manifest_path.is_file()


def render_scene(bundle, scene_id, output_dir, *, resume=True, track_layers=True, progress=None):
    """Render shot caches and assemble exact cuts with bounded immutable links."""
    bundle = _bundle(bundle)
    scene = next((x for x in bundle["scenes"] if x["id"] == scene_id), None)
    if scene is None:
        raise ValueError("unknown scene: " + str(scene_id))
    output_dir = Path(output_dir).resolve()
    _check_scene_destination(output_dir, bundle["project"]["id"], scene_id)
    settings = bundle["project"]["render"]
    count = sum(shot["duration_frames"] for shot in scene["shots"])
    if count > min(MAX_RENDER_FRAMES, bundle["project"].get("limits", {}).get("max_frames", MAX_RENDER_FRAMES)):
        raise ValueError("scene frame count exceeds configured render budget; split into scenes")
    for shot in scene["shots"]:
        if _settings(bundle, shot)[0] != settings:
            raise ValueError("all shots in a scene must share explicit raster/color/FPS settings")
    output_dir.mkdir(parents=True, exist_ok=True)
    with _lock_output(safe_path(output_dir, ".scene.lock")):
        has_checkpoint = _check_scene_destination(output_dir, bundle["project"]["id"], scene_id)
        return _render_scene_locked(bundle, scene, output_dir, settings, count, has_checkpoint,
                                    resume, track_layers, progress)


def _render_scene_locked(bundle, scene, output_dir, settings, count, has_checkpoint,
                         resume, track_layers, progress):
    manifest = {"schema_version": 1, "kind": "scene-render", "renderer": renderer_identity(),
                "project_id": bundle["project"]["id"], "scene_id": scene["id"],
                "fixture": bundle["project"]["fixture"], "status": "partial",
                "settings": settings, "fps": settings["fps"],
                "resolution": [settings["width"], settings["height"]], "frame_count": count,
                "dependencies": {}, "frames": [], "shots": [], "dialogue": [], "audio": None,
                "completed_frames": 0, "preview_is_timing_authority": False}
    if not has_checkpoint:
        atomic_json(output_dir/"render-manifest.json", manifest)
    timeline_start, mixed_tracks = 0, []
    operations = {"rendered_frames": 0, "reused_frames": 0}
    for shot in scene["shots"]:
        relative_root = "shots/"+shot["id"]
        shot_output = safe_path(output_dir, relative_root)
        rendered = render_shot(bundle, shot["id"], shot_output, resume=resume,
                               track_layers=track_layers, progress=progress)
        for key in operations:
            operations[key] += rendered["operation"][key]
        manifest["dependencies"].update(rendered["dependencies"])
        manifest["shots"].append({"id": shot["id"], "start_frame": timeline_start,
                                  "end_frame": timeline_start+shot["duration_frames"],
                                  "path": relative_root+"/render-manifest.json",
                                  "sha256": file_hash(shot_output/"render-manifest.json")})
        for entry in rendered["frames"]:
            index = timeline_start+entry["index"]
            relative = "frames/"+f"{index:06d}.png"
            _publish_scene_frame(safe_path(shot_output, entry["path"]), safe_path(output_dir, relative), entry["sha256"])
            layers = [{**layer, "path": relative_root+"/"+layer["path"]} for layer in entry.get("layers", [])]
            manifest["frames"].append({**entry, "index": index, "path": relative,
                                       "shot_id": shot["id"], "shot_frame": entry["index"], "layers": layers})
        for track in shot.get("audio", []):
            mixed_tracks.append({**track, "id": shot["id"]+"/"+track["id"],
                                 "start_frame": timeline_start+track["start_frame"]})
            manifest["dialogue"].append({"id": shot["id"]+"/"+track["id"], "speaker": track.get("speaker"),
                                         "start_frame": timeline_start+track["start_frame"],
                                         "end_frame": timeline_start+track["start_frame"]+track["duration_frames"],
                                         "text": track.get("text", ""),
                                         "mouth_cues": [{**cue, "start_frame": timeline_start+cue["start_frame"],
                                                         "end_frame": timeline_start+cue["end_frame"]}
                                                        for cue in track.get("mouth_cues", [])]})
        timeline_start += shot["duration_frames"]
        manifest["completed_frames"] = len(manifest["frames"])
        atomic_json(output_dir/"render-manifest.json", manifest)
    rate = _wave_info(bundle["root"], mixed_tracks[0]["file"])[2]["sample_rate"] if mixed_tracks else 48000
    manifest["audio"] = mix_audio(bundle["root"], mixed_tracks, output_dir/"audio.wav", count,
                                   settings["fps"], sample_rate=rate)
    manifest["status"] = "complete"
    atomic_json(output_dir/"render-manifest.json", manifest)
    write_preview(output_dir, manifest)
    return {**manifest, "operation": operations}


def mux_video(output_dir, *, filename="review.mp4", ffmpeg=None, ffprobe=None):
    """Encode a local review movie and inspect its actual decoded stream timing."""
    output_dir = Path(output_dir).resolve()
    validate_render(output_dir)
    manifest = json.loads((output_dir/"render-manifest.json").read_text("utf-8"))
    executable, probe = ffmpeg or shutil.which("ffmpeg"), ffprobe or shutil.which("ffprobe")
    if not executable or not probe:
        raise ValueError("optional ffmpeg and ffprobe are required for movie output; PNG/WAV remain complete")
    target = safe_path(output_dir, filename)
    if target.suffix != ".mp4":
        raise ValueError("review mux supports .mp4; PNG/WAV retain lossless RGBA/PCM masters")
    fps = fps_fraction(manifest["fps"])
    temporary = target.with_name(target.stem+".partial.mp4")
    command = [str(executable), "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
               "-framerate", f"{fps.numerator}/{fps.denominator}", "-start_number", "0",
               "-i", str(output_dir/"frames/%06d.png"), "-i", str(output_dir/manifest["audio"]["path"]),
               "-map", "0:v:0", "-map", "1:a:0", "-frames:v", str(manifest["frame_count"]),
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
               "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:a", "aac", "-b:a", "160k",
               "-threads", "1", "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:v", "+bitexact",
               "-movflags", "+faststart", str(temporary)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise ValueError("ffmpeg review mux failed: " + result.stderr[-2000:])
    inspected = subprocess.run([str(probe), "-v", "error", "-count_frames", "-show_streams",
                                "-show_format", "-of", "json", str(temporary)],
                               capture_output=True, text=True, timeout=120)
    if inspected.returncode:
        raise ValueError("ffprobe could not verify encoded review movie: " + inspected.stderr[-1000:])
    data = json.loads(inspected.stdout)
    videos = [x for x in data["streams"] if x["codec_type"] == "video"]
    audios = [x for x in data["streams"] if x["codec_type"] == "audio"]
    if len(videos) != 1 or len(audios) != 1 or int(videos[0].get("nb_read_frames", -1)) != manifest["frame_count"]:
        raise ValueError("encoded review movie has incorrect video/audio stream or frame count")
    if Fraction(videos[0]["avg_frame_rate"]) != fps:
        raise ValueError("encoded review movie FPS does not match production contract")
    expected = float(Fraction(manifest["frame_count"], 1)/fps)
    audio_duration = float(audios[0].get("duration", 0))
    tolerance = 1024/manifest["audio"]["sample_rate"]+1e-5
    if abs(audio_duration-expected) > tolerance:
        raise ValueError("encoded audio duration exceeds one AAC packet from the offline master")
    temporary.replace(target)
    receipt = {"schema_version": 1, "kind": "local-review-mux", "path": filename,
               "sha256": file_hash(target), "source_manifest_sha256": file_hash(output_dir/"render-manifest.json"),
               "frame_count": manifest["frame_count"], "fps": manifest["fps"],
               "audio_duration_seconds": audio_duration, "audio_packet_tolerance_seconds": tolerance,
               "alpha": "flattened for H.264 review; use PNG master for RGBA",
               "offline_master_validation": "passed", "application_integration": "not-performed"}
    atomic_json(output_dir/"mux-receipt.json", receipt)
    return receipt


def contact_sheet(output_dir, destination=None, *, frame_indices=None, columns=4, cell_width=320):
    """Bounded storyboard from actual rendered pixels and original frame indices."""
    output_dir = Path(output_dir)
    manifest = json.loads((output_dir/"render-manifest.json").read_text("utf-8"))
    if not manifest["frames"]:
        raise ValueError("no rendered frames available for contact sheet")
    if frame_indices is None:
        count = min(16, len(manifest["frames"]))
        frame_indices = sorted({round(i*(len(manifest["frames"])-1)/max(1, count-1)) for i in range(count)})
    if not 1 <= len(frame_indices) <= 64 or not 1 <= columns <= 8 or not 64 <= cell_width <= 640:
        raise ValueError("contact sheet bounds: at most 64 frames, 1–8 columns, 64–640 pixel cells")
    if any(type(i) is not int or i < 0 or i >= len(manifest["frames"]) for i in frame_indices):
        raise ValueError("contact sheet index outside current rendered frame range")
    aspect = manifest["resolution"][1]/manifest["resolution"][0]
    cell_height = round(cell_width*aspect)+28
    rows = math.ceil(len(frame_indices)/columns)
    if columns*cell_width*rows*cell_height > 16000000:
        raise ValueError("contact sheet exceeds 16-million-pixel budget")
    result = Image.new("RGB", (columns*cell_width, rows*cell_height), "#f4f1e8")
    draw = ImageDraw.Draw(result)
    fps = fps_fraction(manifest["fps"])
    for offset, index in enumerate(frame_indices):
        entry = manifest["frames"][index]
        if not _output_record_valid(output_dir, entry):
            raise ValueError("contact sheet source frame is missing or changed")
        x, y = (offset%columns)*cell_width, (offset//columns)*cell_height
        with Image.open(safe_path(output_dir, entry["path"])) as image:
            preview = image.convert("RGBA").resize((cell_width, cell_height-28), Image.Resampling.LANCZOS)
            result.paste(preview, (x, y), preview)
            preview.close()
        draw.text((x+8, y+cell_height-22), f"Frame {index} · {float(Fraction(index, 1)/fps):.3f} s", fill="#27332d")
    destination = Path(destination) if destination else output_dir/"storyboard.png"
    _save_png(result, destination)
    result.close()
    return {"path": str(destination), "sha256": file_hash(destination), "frame_indices": frame_indices,
            "fixture": manifest["fixture"], "visual_review": "not-performed"}


def mix_audio(root, tracks, output, frame_count, fps, sample_rate=48000, channels=2):
    """Mix signed 16-bit WAV in 4096-sample blocks with integer frame offsets.

    Every input already has the requested sample rate. No hidden resampling or
    alignment is attempted. Positive rational gain is rounded to nearest integer;
    clipping is counted. Silence is explicitly padded to the exact shot duration.
    """
    if type(frame_count) is not int or not 1 <= frame_count <= MAX_RENDER_FRAMES:
        raise ValueError("audio frame count exceeds positive render bounds")
    if type(sample_rate) is not int or not 8000 <= sample_rate <= 192000 or channels not in (1, 2):
        raise ValueError("output PCM requires 8–192 kHz and one or two channels")
    if not isinstance(tracks, list) or len(tracks) > MAX_AUDIO_TRACKS:
        raise ValueError("at most 32 audio tracks may be mixed")
    count = sample_at_frame(frame_count, sample_rate, fps)
    if count > MAX_AUDIO_SAMPLES:
        raise ValueError("mixed audio duration exceeds resource limit")
    prepared = []
    for track in tracks:
        reference = track.get("file", track.get("audio", track.get("source")))
        if not isinstance(reference, dict):
            raise ValueError("audio track requires a hash-bound audio source")
        path, digest, info = _wave_info(root, reference, sample_rate)
        start = track.get("start", track.get("start_frame", 0))
        source_start = track.get("source_start", track.get("source_start_frame", 0))
        end = track.get("end", track.get("end_frame", start+track.get("duration_frames", frame_count-start)))
        if any(type(x) is not int for x in (start, source_start, end)) or not 0 <= start < end <= frame_count or source_start < 0:
            raise ValueError("audio track has invalid integer frame interval")
        offset = sample_at_frame(source_start, sample_rate, fps)
        if offset > info["sample_count"]:
            raise ValueError("audio source_start lies beyond supplied samples")
        gain = track.get("gain", 1)
        if type(gain) not in (int, float) or not math.isfinite(gain) or not 0 <= gain <= 4:
            raise ValueError("audio gain must be finite and within 0–4")
        gain = Fraction(str(gain))
        prepared.append({"path": path, "relative_path": reference["path"], "sha256": digest,
                         "info": info, "start_sample": sample_at_frame(start, sample_rate, fps),
                         "end_sample": sample_at_frame(end, sample_rate, fps), "source_sample": offset,
                         "gain": gain, "id": track.get("id", "audio-" + str(len(prepared)))})
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".partial")
    clipped = 0
    with ExitStack() as stack:
        for entry in prepared:
            entry["stream"] = stack.enter_context(wave.open(str(entry["path"]), "rb"))
        destination = stack.enter_context(wave.open(str(temporary), "wb"))
        destination.setnchannels(channels)
        destination.setsampwidth(2)
        destination.setframerate(sample_rate)
        destination.setnframes(count)
        for begin in range(0, count, MAX_AUDIO_BLOCK):
            length = min(MAX_AUDIO_BLOCK, count-begin)
            accum = [0] * (length*channels)
            for entry in prepared:
                first = max(begin, entry["start_sample"])
                last = min(begin+length, entry["end_sample"],
                           entry["start_sample"]+entry["info"]["sample_count"]-entry["source_sample"])
                if first >= last:
                    continue
                source = entry["stream"]
                source.setpos(entry["source_sample"]+first-entry["start_sample"])
                values = array.array("h", source.readframes(last-first))
                if sys.byteorder != "little":
                    values.byteswap()
                source_channels = entry["info"]["channels"]
                if len(values) != (last-first)*source_channels:
                    raise ValueError("truncated audio PCM payload: " + entry["relative_path"])
                gain = entry["gain"]
                for index in range(last-first):
                    for channel in range(channels):
                        if channels == 1 and source_channels == 2:
                            value = Fraction(values[index*2]+values[index*2+1], 2)
                        else:
                            value = values[index*source_channels+(channel if source_channels > 1 else 0)]
                        accum[(first-begin+index)*channels+channel] += round(value*gain)
            result = array.array("h")
            for value in accum:
                if value < -32768 or value > 32767:
                    clipped += 1
                result.append(max(-32768, min(32767, value)))
            if sys.byteorder != "little":
                result.byteswap()
            destination.writeframesraw(result.tobytes())
    temporary.replace(output)
    sources = [{"id": e["id"], "path": e["relative_path"], "sha256": e["sha256"],
                "start_sample": e["start_sample"], "end_sample": e["end_sample"],
                "source_sample": e["source_sample"],
                "gain": {"numerator": e["gain"].numerator, "denominator": e["gain"].denominator},
                **e["info"]} for e in prepared]
    return {"path": output.name, "sha256": file_hash(output), "sample_rate": sample_rate,
            "channels": channels, "sample_width": 2, "sample_count": count,
            "fps": fps, "frame_count": frame_count, "sources": sources,
            "clipped_samples": clipped,
            "timing": "sample at frame = nearest integer(frame × rate × fps denominator / fps numerator)",
            "mix_sha256": object_hash({"sources": sources, "frame_count": frame_count,
                                        "fps": fps, "sample_rate": sample_rate, "channels": channels})}


def audio_fixture(output, duration_frames=24, fps=None, sample_rate=48000, frequency=440):
    """Create a reproducible test-only square-wave cue; never speech or production art."""
    fps = fps or {"numerator": 12, "denominator": 1}
    count = sample_at_frame(duration_frames, sample_rate, fps)
    if count > MAX_AUDIO_SAMPLES or not 1 <= frequency <= sample_rate//2:
        raise ValueError("audio fixture bounds exceeded")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        for begin in range(0, count, MAX_AUDIO_BLOCK):
            values = array.array("h", (6000 if ((index*frequency*2)//sample_rate)%2 == 0 else -6000
                                      for index in range(begin, min(count, begin+MAX_AUDIO_BLOCK))))
            if sys.byteorder != "little":
                values.byteswap()
            stream.writeframesraw(values.tobytes())
    return {"path": output.name, "sha256": file_hash(output), "sample_rate": sample_rate,
            "sample_count": count, "provenance": {"kind": "fixture", "fixture": True,
            "origin": "Deterministic signed PCM square wave; test cue only"}}


def _character_layers(bundle, shot, instance, frame, camera):
    character = bundle["characters"][instance["character"]]
    from production_performance import evaluate_instance_performance
    state = evaluate_instance_performance(bundle, shot, instance, frame)
    modifiers = state["components"]
    components = {part["id"]: part for part in character["components"]}
    if set(modifiers)-set(components):
        raise ValueError("performance references missing components: " + ", ".join(sorted(set(modifiers)-set(components))))
    root_position = state["position"]
    scale = state["scale"]
    actor_matrix = local_matrix(root_position, scale=scale)
    visible = state["visible"]
    matrices, visibility, visiting, anchor_positions, layers = {}, {}, set(), {}, []
    costume = next((x for x in character["costumes"] if x["id"] == instance["costume"]), None)
    if costume is None:
        raise ValueError("missing costume " + instance["costume"] + " for " + instance["id"])

    def build(component_id):
        if component_id in matrices:
            return matrices[component_id]
        if component_id in visiting:
            raise ValueError("component hierarchy cycle at " + component_id)
        if component_id not in components:
            raise ValueError("missing component parent " + component_id)
        visiting.add(component_id)
        part = components[component_id]
        changes = modifiers.get(component_id, {})
        offset = _vector_add(part.get("offset", [0, 0]), changes.get("offset", [0, 0]))
        parent = part.get("parent")
        if parent is not None:
            parent_matrix = build(parent)
            anchor_name = part.get("parent_anchor")
            if anchor_name not in components[parent].get("anchors", {}):
                raise ValueError("broken parent anchor " + str(anchor_name) + " on " + component_id)
            position = _vector_add(components[parent]["anchors"][anchor_name], offset)
            inherited_visibility = visibility[parent]
        else:
            parent_matrix, position, inherited_visibility = actor_matrix, offset, visible
        matrix = multiply(parent_matrix, local_matrix(position, changes.get("rotation", 0), pivot=part["pivot"]))
        matrices[component_id] = matrix
        visibility[component_id] = inherited_visibility and changes.get("visible", part.get("visible", True))
        anchor_positions[component_id] = {name: transform_point(matrix, point)
                                          for name, point in part.get("anchors", {}).items()}
        visiting.remove(component_id)
        return matrix

    for part in character["components"]:
        build(part["id"])
    for part in character["components"]:
        changes = modifiers.get(part["id"], {})
        selected = changes.get("drawing", costume.get("drawings", {}).get(part["id"], part["default_drawing"]))
        if selected not in part["drawings"]:
            raise ValueError("missing replaceable drawing " + str(selected) + " on " + part["id"])
        drawing = part["drawings"][selected]
        if drawing["viewpoint"] != instance["viewpoint"]:
            raise ValueError("incompatible viewpoint drawing on " + instance["id"] + "/" + part["id"])
        if drawing.get("alpha", "straight") != "straight":
            raise ValueError("unsupported source alpha declaration on " + part["id"])
        layers.append({"id": instance["id"]+"/"+part["id"], "track": instance["id"],
                       "component": part["id"], "drawing": selected,
                       "character": instance["character"], "image": drawing["image"],
                       "matrix": list(multiply(camera, matrices[part["id"]])),
                       "world_matrix": list(matrices[part["id"]]),
                       "z": instance.get("z", 0)+part.get("z", 0),
                       "visible": visibility[part["id"]], "mask": part.get("mask"), "opacity": 1})
    full = state.get("full_frame")
    if full is not None:
        if full["viewpoint"] != instance["viewpoint"]:
            raise ValueError("full-frame override viewpoint is incompatible")
        matrix = multiply(actor_matrix, translation(-full["pivot"][0], -full["pivot"][1]))
        layers = [{"id": instance["id"]+"/full-frame", "track": instance["id"],
                   "character": instance["character"], "image": full["image"],
                   "matrix": list(multiply(camera, matrix)), "world_matrix": list(matrix),
                   "z": instance.get("z", 0), "visible": visible, "mask": None, "opacity": 1}]
    return layers, {"id": instance["id"], "character": instance["character"],
                    "position": root_position, "relative_scale": scale,
                    "facing": state["facing"],
                    "visible": visible, "components": {key: {"matrix": list(matrix),
                    "anchors": anchor_positions[key], "visible": visibility[key]}
                    for key, matrix in matrices.items()}, "performance": state}


def _prop_point(prop, frame, actors, attachment):
    if attachment is not None:
        return _attachment_point(attachment, actors)
    return _sample(prop.get("tracks", {}).get("position"), frame, prop["position"])


def evaluate_frame(bundle, shot_id, frame):
    """Return inspectable world anchors and camera-space raster operations.

    Every coordinate is measured in source/world pixels, Y down. Instance scale
    is cast_scale × character.relative_scale. Root paths add to cumulative clip
    displacement. A child pivot attaches to its parent's named source anchor.
    Draw order is increasing (instance z + component z), then declaration order.
    """
    bundle = _bundle(bundle)
    if shot_id not in bundle["shots"]:
        raise ValueError("unknown shot: " + str(shot_id))
    shot = bundle["shots"][shot_id]
    if type(frame) is not int or not 0 <= frame < shot["duration_frames"]:
        raise ValueError("frame index is outside the shot's exclusive edit boundary")
    settings, _, _ = _settings(bundle, shot)
    camera_spec = shot.get("camera", {})
    position = _sample(camera_spec.get("position"), frame, [0, 0])
    zoom = _sample(camera_spec.get("zoom"), frame, 1)
    bounds = camera_spec.get("bounds", {"min_zoom": .1, "max_zoom": 10, "max_pan_per_frame": 10000})
    if not bounds["min_zoom"] <= zoom <= bounds["max_zoom"]:
        raise ValueError("camera zoom exceeds declared bounds")
    if frame:
        previous = _sample(camera_spec.get("position"), frame-1, [0, 0])
        if math.dist(position, previous) > bounds["max_pan_per_frame"]+1e-8:
            raise ValueError("camera pan exceeds declared per-frame bound")
    camera = multiply(scaling(zoom), translation(-position[0], -position[1]))
    layers, actors = [], {}
    for layer in shot.get("layers", []):
        parallax = layer.get("parallax", 1)
        matrix = multiply(multiply(scaling(zoom), translation(-position[0]*parallax, -position[1]*parallax)),
                          translation(*layer["position"]))
        layers.append({"id": layer["id"], "track": layer["id"], "image": layer["image"],
                       "matrix": list(matrix), "z": layer["z"], "opacity": layer.get("opacity", 1),
                       "visible": True, "mask": None})
    for instance in shot.get("instances", []):
        actor_layers, actor = _character_layers(bundle, shot, instance, frame, camera)
        if actor["id"] in actors:
            raise ValueError("duplicate actor instance: " + actor["id"])
        actors[actor["id"]] = actor
        layers.extend(actor_layers)
    prop_assets = {p["id"]+"@"+p["version"]: p for p in bundle["cast"].get("props", [])}
    props = {}
    for prop in shot.get("props", []):
        if prop["prop"] not in prop_assets:
            raise ValueError("missing versioned prop: " + prop["prop"])
        asset = prop_assets[prop["prop"]]
        owner, attachment = _owner_at(prop, frame)
        if owner is not None and owner not in actors:
            raise ValueError("missing prop owner: " + str(owner))
        if attachment is not None and attachment["instance"] != owner:
            raise ValueError("prop attachment contradicts current owner: " + prop["id"])
        point = _prop_point(prop, frame, actors, attachment)
        for change in prop.get("ownership", []):
            if change["frame"] == frame:
                _, prior_attachment = _owner_at(prop, frame, False)
                prior_point = _prop_point(prop, frame, actors, prior_attachment)
                if math.dist(point, prior_point) > 2+1e-8:
                    raise ValueError("discontinuous ownership change for " + prop["id"] +
                                     "; align both attachment pivots within 2 world pixels")
        angle = _sample(prop.get("tracks", {}).get("rotation"), frame, 0)
        matrix = local_matrix(point, angle, pivot=asset["pivot"])
        visibility = _sample(prop.get("tracks", {}).get("visible"), frame, True)
        layers.append({"id": prop["id"], "track": prop["id"], "prop": prop["prop"],
                       "image": asset["image"], "matrix": list(multiply(camera, matrix)),
                       "world_matrix": list(matrix), "z": prop["z"], "opacity": 1,
                       "visible": visibility, "mask": None})
        props[prop["id"]] = {"owner": owner, "attachment": attachment,
                             "position": point, "visible": visibility,
                             "anchors": {name: transform_point(matrix, p) for name, p in asset.get("anchors", {}).items()}}
    interactions = []
    for interaction in shot.get("interactions", []):
        if interaction["frame"] != frame:
            continue
        target, tolerance = interaction["position"], interaction["tolerance"]
        measured = []
        if interaction["prop"] not in props:
            raise ValueError("interaction refers to missing prop " + interaction["prop"])
        if math.dist(props[interaction["prop"]]["position"], target) > tolerance+1e-8:
            raise ValueError("prop does not meet shared interaction position: " + interaction["id"])
        for participant in interaction["participants"]:
            point = _attachment_point(participant, actors)
            distance = math.dist(point, target)
            if distance > tolerance+1e-8:
                raise ValueError("unreachable shared contact in " + interaction["id"]+": "+participant["instance"]+
                                 " is "+str(round(distance, 3))+" pixels away; tolerance "+str(tolerance))
            measured.append({"instance": participant["instance"], "point": point, "distance": distance})
        interactions.append({"id": interaction["id"], "position": target, "participants": measured})
    if len(layers) > MAX_LAYERS:
        raise ValueError("shot exceeds 256 composited layers")
    layers.sort(key=lambda entry: entry["z"])
    return {"shot_id": shot_id, "frame": frame, "camera": {"position": position, "zoom": zoom,
            "matrix": list(camera)}, "settings": settings, "layers": layers,
            "instances": actors, "props": props, "interactions": interactions}


def render_frame(bundle, shot_id, frame, cache=None, hidden_tracks=None):
    bundle = _bundle(bundle)
    state = evaluate_frame(bundle, shot_id, frame)
    settings = state["settings"]
    owned_cache = cache is None
    cache = cache or AssetCache(bundle["root"], max_pixels=bundle["project"].get("limits", {}).get("max_source_pixels", 2000000))
    output = Image.new("RGBA", (settings["width"], settings["height"]), _color(settings["background"]))
    try:
        for layer in state["layers"]:
            if layer["track"] not in (hidden_tracks or ()):
                rendered = render_layer(layer, output.size, cache, settings["resampling"])
                output.alpha_composite(rendered)
                rendered.close()
        return output, state
    finally:
        if owned_cache:
            cache.close()
