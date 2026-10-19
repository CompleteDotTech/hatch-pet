"""Pixels, dependency reuse, interruption recovery and offline PCM timing."""
from copy import deepcopy
import errno
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from production_contracts import load_project
from production_render import (AssetCache, _publish_scene_frame, audio_fixture, canonical,
    evaluate_frame, file_hash, local_matrix, mix_audio, mux_video, render_frame,
    render_layer, render_scene, render_shot, sample_at_frame, scaling,
    transform_point, validate_render)


def track(*pairs, interpolation="step"):
    return {"interpolation": interpolation, "keys": [{"frame": frame, "value": value} for frame, value in pairs]}


def fixture_project(root):
    """Small real-file test project; all artwork is explicitly synthetic."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root/"assets").mkdir(exist_ok=True)
    provenance = {"kind": "fixture", "fixture": True, "origin": "Synthetic renderer regression fixture; not production art"}

    def source(name, color, size=(4, 4)):
        path = root/"assets"/(name+".png")
        Image.new("RGBA", size, color).save(path)
        return {"path": path.relative_to(root).as_posix(), "sha256": file_hash(path),
                "size": list(size), "provenance": deepcopy(provenance)}

    def drawing(image):
        return {"viewpoint": "front", "costume": "default", "image": image, "alpha": "straight"}

    def component(name, role, image, pivot, parent=None, parent_anchor=None, anchors=None, z=0):
        return {"id": name, "role": role, "parent": parent, "parent_anchor": parent_anchor,
                "pivot": pivot, "offset": [0, 0], "anchors": anchors or {}, "z": z,
                "drawings": {"default": drawing(image)}, "default_drawing": "default", "visible": True}

    characters = []
    for name, color in (("alice", (220, 40, 30, 255)), ("bob", (30, 80, 220, 255))):
        torso = component("torso", "torso", source(name+"-torso", color), [2, 4],
                          anchors={"hand": [4, 2], "face": [2, 1]}, z=0)
        hand = component("hand", "hands", source(name+"-hand", (80, 200, 70, 255), (2, 2)),
                         [0, 1], "torso", "hand", {"grip": [1, 1]}, z=2)
        mouth = component("mouth", "mouth", source(name+"-mouth", (10, 10, 10, 255), (2, 2)),
                          [1, 1], "torso", "face", z=3)
        mouth["drawings"]["open"] = drawing(source(name+"-mouth-open", (255, 255, 255, 255), (2, 2)))
        characters.append({"id": name, "version": "1.0.0", "name": name.title(),
            "dimensions": {"width": 8, "height": 8}, "relative_scale": 1,
            "identity": {"proportions": {"head_body": 1}, "palette": {"body": "#dd4422"},
                         "materials": ["test paint"], "markings": [], "asymmetries": [],
                         "allowed_facings": ["front"], "forbid_mirror": True},
            "views": ["front"], "components": [torso, hand, mouth],
            "costumes": [{"id": "default", "differences": [], "drawings": {}}],
            "capabilities": {"action": ["walk", "idle"], "pose": ["stand"], "viewpoint": ["front"],
                             "facing": ["front"], "mouth": ["default", "open"]},
            "provenance": deepcopy(provenance)})
    cast = {"schema_version": 1, "kind": "cast", "id": "test-cast", "version": "1.0.0",
            "fixture": True, "characters": characters,
            "props": [{"id": "parcel", "version": "1.0.0", "name": "Test parcel",
                       "image": source("parcel", (255, 210, 10, 255), (2, 2)),
                       "pivot": [1, 1], "anchors": {"grip": [1, 1]}}]}
    clip = {"schema_version": 1, "kind": "clip", "id": "walk", "version": "1.0.0",
            "character": "alice@1.0.0", "viewpoint": "front", "facing": "front",
            "start_pose": "stand", "end_pose": "stand", "duration_frames": 4,
            "mode": "loop", "completion": "loop", "root": {"offset": track((0, [0, 0]), (4, [4, 0]), interpolation="linear")},
            "tracks": {}, "contacts": [], "events": [],
            "entry_points": [{"frame": 0, "pose": "stand"}], "exit_points": [{"frame": 3, "pose": "stand"}],
            "interpolation": {"max_frames": 4, "max_offset_per_frame": 10, "max_rotation_per_frame": 90},
            "interruptions": {"policy": "any", "frames": [], "cancel_pose": "stand", "max_transition_frames": 4},
            "displacement": [4, 0], "requirements": {"action": ["walk"], "pose": ["stand"]}, "full_frames": []}

    def instance(name, position, z):
        return {"id": name, "character": name+"@1.0.0", "viewpoint": "front", "facing": "front",
                "costume": "default", "position": position, "z": z, "tracks": {}, "requirements": {},
                "bindings": {}, "clips": ([{"clip": "walk@1.0.0", "start_frame": 0, "end_frame": 6,
                "transition": {"kind": "cut", "frames": 0}}] if name == "alice" else [])}

    shot = {"id": "first", "duration_frames": 6, "cast_scale": 1,
            "instances": [instance("alice", [8, 16], 10), instance("bob", [24, 16], 20)],
            "props": [{"id": "parcel", "prop": "parcel@1.0.0", "position": [32, 16], "z": 30,
                       "owner": None, "attachment": None, "tracks": {}, "ownership": []}],
            "interactions": [], "layers": [],
            "camera": {"position": track((0, [0, 0])), "zoom": track((0, 1)),
                       "bounds": {"max_pan_per_frame": 10, "min_zoom": .5, "max_zoom": 2}},
            "audio": [], "lighting": {"direction": "ambient", "color_treatment": "unchanged"},
            "explicit_requirements": ["Preserve test scale and source provenance"], "inferred_choices": []}
    second = deepcopy(shot)
    second["id"] = "second"
    scenes = [{"schema_version": 1, "kind": "scene", "id": "scene-one", "version": "1.0.0", "shots": [shot], "continuity": []},
              {"schema_version": 1, "kind": "scene", "id": "scene-two", "version": "1.0.0", "shots": [second], "continuity": []}]
    project = {"schema_version": 1, "kind": "project", "id": "render-test", "version": "1.0.0", "fixture": True,
               "cast": {}, "clips": [], "scenes": [],
               "render": {"width": 48, "height": 32, "fps": {"numerator": 12, "denominator": 1},
                          "color_space": "srgb", "alpha": "straight", "resampling": "nearest", "background": "#00000000"},
               "limits": {"max_frames": 512, "max_assets": 128, "max_source_pixels": 2000000,
                          "max_work_bytes": 134217728, "max_generation_calls": 0}}

    def save(name, value):
        path = root/name
        path.write_bytes(canonical(value)+b"\n")
        return {"path": name, "sha256": file_hash(path)}
    project["cast"] = save("cast.json", cast)
    project["clips"] = [save("walk.json", clip)]
    project["scenes"] = [save(scene["id"]+".json", scene) for scene in scenes]
    save("project.json", project)
    return load_project(root/"project.json")


def snapshot(root):
    return {path.relative_to(root).as_posix():
            ("file", file_hash(path), path.stat().st_mtime_ns) if path.is_file() else ("directory",)
            for path in root.rglob("*")}


class ProductionRenderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hatch-render-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.bundle = fixture_project(self.home/"project")

    def test_parent_pivot_anchor_camera_and_cast_scale(self):
        shot = self.bundle["shots"]["first"]
        alice = shot["instances"][0]
        alice["clips"] = []
        alice["tracks"] = {"body": {"torso": {"rotation": track((0, 90))}}}
        shot["camera"]["position"] = track((0, [2, 3]))
        shot["camera"]["zoom"] = track((0, 2))
        state = evaluate_frame(self.bundle, "first", 0)
        point = state["instances"]["alice"]["components"]["hand"]["anchors"]["grip"]
        self.assertAlmostEqual(point[0], 10)
        self.assertAlmostEqual(point[1], 19)
        part = next(layer for layer in state["layers"] if layer["id"] == "alice/hand")
        self.assertEqual([round(v) for v in transform_point(part["matrix"], [1, 1])], [16, 32])
        self.bundle["characters"]["alice@1.0.0"]["relative_scale"] = 2
        scaled = evaluate_frame(self.bundle, "first", 0)
        self.assertEqual(scaled["instances"]["alice"]["relative_scale"], 2)
        self.assertEqual([round(v) for v in scaled["instances"]["alice"]["components"]["hand"]["anchors"]["grip"]], [12, 22])

    def test_mask_alpha_and_filter_edges_with_a_one_image_cache(self):
        root = self.home/"raster"
        root.mkdir()
        Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(root/"red.png")
        mask = Image.new("RGBA", (4, 4))
        mask.paste((255, 255, 255, 128), (0, 0, 2, 4))
        mask.save(root/"mask.png")
        cache = AssetCache(root, max_bytes=64)
        self.addCleanup(cache.close)
        layer = {"id": "masked", "image": {"path": "red.png"}, "mask": {"path": "mask.png"},
                 "matrix": local_matrix(), "visible": True, "opacity": .5}
        image = render_layer(layer, (4, 4), cache, "nearest")
        self.assertEqual(image.getbbox(), (0, 0, 2, 4))
        self.assertEqual(image.getpixel((0, 0)), (255, 0, 0, 64))
        self.assertLessEqual(cache.peak_bytes, 64)
        edge = Image.new("RGBA", (2, 1))
        edge.putpixel((0, 0), (255, 0, 0, 255))
        edge.save(root/"edge.png")
        filtered = render_layer({"id": "edge", "image": {"path": "edge.png"}, "matrix": scaling(4)}, (8, 4), cache, "bilinear")
        partial = [filtered.getpixel((x, y)) for y in range(filtered.height) for x in range(filtered.width)
                   if 0 < filtered.getpixel((x, y))[3] < 255]
        self.assertTrue(partial)
        self.assertTrue(all(pixel[0] == 255 and pixel[1:3] == (0, 0) for pixel in partial))

    def test_independent_mouth_body_loop_and_full_frame(self):
        shot = self.bundle["shots"]["first"]
        shot["instances"][0]["tracks"] = {"mouth": {"mouth": {"drawing": track((0, "default"), (2, "open"))}}}
        first = evaluate_frame(self.bundle, "first", 0)
        fifth = evaluate_frame(self.bundle, "first", 5)
        self.assertEqual(fifth["instances"]["alice"]["position"], [13, 16])
        self.assertEqual(next(p for p in first["layers"] if p["id"] == "alice/mouth")["drawing"], "default")
        self.assertEqual(next(p for p in fifth["layers"] if p["id"] == "alice/mouth")["drawing"], "open")
        source = self.bundle["characters"]["alice@1.0.0"]["components"][0]["drawings"]["default"]["image"]
        self.bundle["clips"]["walk@1.0.0"]["full_frames"] = [{"start_frame": 1, "end_frame": 3,
            "image": source, "pivot": [2, 4], "viewpoint": "front"}]
        full = evaluate_frame(self.bundle, "first", 2)
        self.assertEqual([part["id"] for part in full["layers"] if part["track"] == "alice"], ["alice/full-frame"])
        self.assertIn("hand", full["instances"]["alice"]["components"])
        self.assertEqual(len([part for part in evaluate_frame(self.bundle, "first", 3)["layers"] if part["track"] == "alice"]), 3)

    def test_inherited_visibility_and_explicit_hidden_tracks_change_pixels(self):
        shot = self.bundle["shots"]["first"]
        shown, _ = render_frame(self.bundle, "first", 0)
        hidden, _ = render_frame(self.bundle, "first", 0, hidden_tracks={"alice"})
        self.assertNotEqual(shown.tobytes(), hidden.tobytes())
        shot["instances"][0]["tracks"] = {"body": {"torso": {"visible": track((0, False))}}}
        state = evaluate_frame(self.bundle, "first", 0)
        self.assertTrue(all(not part["visible"] for part in state["layers"] if part["track"] == "alice"))

    def test_shared_handoff_positions_ownership_and_prop_scale(self):
        shot = self.bundle["shots"]["first"]
        for actor in shot["instances"]:
            actor["clips"] = []
        self.bundle["characters"]["bob@1.0.0"]["relative_scale"] = 2
        shot["instances"][1]["position"] = [5, 18]
        first = {"instance": "alice", "component": "hand", "anchor": "grip"}
        second = {"instance": "bob", "component": "hand", "anchor": "grip"}
        prop = shot["props"][0]
        prop.update(owner="alice", attachment=first, position=[11, 14], ownership=[
            {"frame": 3, "from": "alice", "to": "bob", "attachment": second, "event": "handoff"}])
        shot["interactions"] = [{"id": "exchange", "frame": 3, "prop": "parcel", "position": [11, 14],
            "tolerance": .01, "participants": [{**first, "marker": "release"}, {**second, "marker": "grasp"}]}]
        self.assertEqual(evaluate_frame(self.bundle, "first", 2)["props"]["parcel"]["owner"], "alice")
        state = evaluate_frame(self.bundle, "first", 3)
        self.assertEqual(state["props"]["parcel"]["owner"], "bob")
        self.assertEqual(state["props"]["parcel"]["position"], [11, 14])
        self.assertTrue(all(p["distance"] == 0 for p in state["interactions"][0]["participants"]))
        layer = next(p for p in state["layers"] if p["id"] == "parcel")
        self.assertEqual(layer["world_matrix"][:4], [1, 0, 0, 1])
        shot["instances"][1]["position"][0] += 10
        with self.assertRaisesRegex(ValueError, "discontinuous ownership"):
            evaluate_frame(self.bundle, "first", 3)

    def test_partial_resume_exact_manifest_and_tampered_frame_recovery(self):
        destination = self.home/"incremental"
        partial = render_shot(self.bundle, "first", destination, max_frames=2)
        self.assertEqual(partial["completed_frames"], 2)
        self.assertEqual(partial["status"], "partial")
        with self.assertRaisesRegex(ValueError, "incomplete"):
            validate_render(destination)
        completed = render_shot(self.bundle, "first", destination)
        self.assertEqual(completed["operation"]["reused_frames"], 2)
        self.assertEqual(completed["operation"]["rendered_frames"], 4)
        expected = (destination/"render-manifest.json").read_bytes()
        repeated = render_shot(self.bundle, "first", destination)
        self.assertEqual(repeated["operation"]["reused_frames"], 6)
        self.assertEqual(expected, (destination/"render-manifest.json").read_bytes())
        (destination/"frames/000003.png").write_bytes(b"damaged")
        repaired = render_shot(self.bundle, "first", destination)
        self.assertEqual(repaired["operation"]["rendered_frames"], 1)
        self.assertEqual(expected, (destination/"render-manifest.json").read_bytes())
        self.assertEqual(validate_render(destination)["frame_count"], 6)

    def test_source_edit_rerenders_only_frames_using_changed_drawing(self):
        actor = self.bundle["shots"]["first"]["instances"][0]
        actor["tracks"] = {"mouth": {"mouth": {"drawing": track((0, "default"), (2, "open"), (4, "default"))}}}
        destination = self.home/"edit"
        original = render_shot(self.bundle, "first", destination)
        drawing = self.bundle["characters"]["alice@1.0.0"]["components"][2]["drawings"]["open"]["image"]
        path = self.bundle["root"]/drawing["path"]
        Image.new("RGBA", (2, 2), (150, 20, 200, 255)).save(path)
        drawing["sha256"] = file_hash(path)
        changed = render_shot(self.bundle, "first", destination)
        self.assertEqual(changed["operation"]["rendered_frames"], 2)
        self.assertEqual([i for i in range(6) if original["frames"][i]["sha256"] != changed["frames"][i]["sha256"]], [2, 3])

    def test_callback_interruption_leaves_last_completed_checkpoint(self):
        destination = self.home/"interrupt"
        def stop(progress):
            if progress["completed"] == 4:
                raise RuntimeError("deliberate interruption")
        with self.assertRaisesRegex(RuntimeError, "interruption"):
            render_shot(self.bundle, "first", destination, progress=stop)
        checkpoint = json.loads((destination/"render-manifest.json").read_text())
        self.assertEqual(checkpoint["completed_frames"], 4)
        resumed = render_shot(self.bundle, "first", destination)
        self.assertEqual(resumed["operation"]["reused_frames"], 4)
        self.assertEqual(resumed["operation"]["rendered_frames"], 2)

    def test_timing_only_revision_reuses_pixels_and_output_cache_is_bounded(self):
        destination = self.home/"timing"
        first = render_shot(self.bundle, "first", destination)
        self.bundle["project"]["render"]["fps"] = {"numerator": 24, "denominator": 1}
        revised = render_shot(self.bundle, "first", destination)
        self.assertEqual(revised["operation"]["reused_frames"], 6)
        self.assertEqual([entry["sha256"] for entry in first["frames"]], [entry["sha256"] for entry in revised["frames"]])
        self.assertEqual(revised["audio"]["sample_count"], first["audio"]["sample_count"]//2)
        with patch("production_render.MAX_RENDER_OUTPUT_BYTES", 1024):
            with self.assertRaisesRegex(ValueError, "output cache reached"):
                render_shot(self.bundle, "first", self.home/"bounded")

    def test_audio_rational_duration_offsets_gains_and_tampering(self):
        root = self.home/"audio"
        root.mkdir()
        fps = {"numerator": 30000, "denominator": 1001}
        fixture = audio_fixture(root/"cue.wav", duration_frames=30, fps=fps)
        tracks = [{"id": "cue", "file": {"path": "cue.wav", "sha256": fixture["sha256"]},
                   "start_frame": 3, "duration_frames": 27, "gain": .5}]
        result = mix_audio(root, tracks, root/"mix.wav", 30, fps)
        self.assertEqual(result["sample_count"], 48048)
        with wave.open(str(root/"mix.wav"), "rb") as source:
            start = sample_at_frame(3, 48000, fps)
            self.assertEqual(source.readframes(start), b"\0"*(start*4))
            self.assertEqual(struct.unpack("<hh", source.readframes(1)), (3000, 3000))
        self.assertEqual(mix_audio(root, tracks, root/"mix.wav", 30, fps)["sha256"], result["sha256"])
        (root/"cue.wav").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            mix_audio(root, tracks, root/"mix.wav", 30, fps)

    def test_offline_validation_detects_truncated_pcm_with_preserved_header(self):
        destination = self.home/"truncated"
        render_shot(self.bundle, "first", destination)
        audio = destination/"audio.wav"
        audio.write_bytes(audio.read_bytes()[:-4])
        manifest_path = destination/"render-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["audio"]["sha256"] = file_hash(audio)
        manifest_path.write_bytes(canonical(manifest))
        with self.assertRaisesRegex(ValueError, "truncated audio PCM"):
            validate_render(destination)

    def test_camera_resource_bounds_missing_attachment_and_path_escape(self):
        shot = self.bundle["shots"]["first"]
        shot["camera"]["position"] = track((0, [0, 0]), (1, [30, 0]))
        with self.assertRaisesRegex(ValueError, "camera pan"):
            evaluate_frame(self.bundle, "first", 1)
        shot["camera"]["position"] = track((0, [0, 0]))
        self.bundle["project"]["render"]["width"] = 100000
        with self.assertRaisesRegex(ValueError, "resolution"):
            render_shot(self.bundle, "first", self.home/"large")
        self.bundle["project"]["render"]["width"] = 48
        shot["props"][0].update(owner="alice", attachment={"instance": "alice", "component": "hand", "anchor": "missing"})
        with self.assertRaisesRegex(ValueError, "missing interaction attachment"):
            evaluate_frame(self.bundle, "first", 0)
        with self.assertRaisesRegex(ValueError, "escapes"):
            AssetCache(self.bundle["root"]).get({"path": "../outside.png"})

    def test_corrupt_and_foreign_shot_destinations_fail_before_writes(self):
        destination = self.home/"owned-shot"
        render_shot(self.bundle, "first", destination)
        expected = snapshot(destination)
        for resume in (True, False):
            with self.assertRaisesRegex(ValueError, "different project/shot"):
                render_shot(self.bundle, "second", destination, resume=resume)
            self.assertEqual(snapshot(destination), expected)
        (destination/"render-manifest.json").write_text("corrupt")
        expected = snapshot(destination)
        with self.assertRaisesRegex(ValueError, "corrupt"):
            render_shot(self.bundle, "first", destination)
        self.assertEqual(snapshot(destination), expected)

    def test_scene_collision_preserves_complete_outputs_and_render_kind(self):
        destination = self.home/"owned-scene"
        render_scene(self.bundle, "scene-one", destination)
        expected = snapshot(destination)
        foreign_project = deepcopy(self.bundle)
        foreign_project["project"]["id"] = "another-project"
        for resume in (True, False):
            for bundle, scene in ((self.bundle, "scene-two"), (foreign_project, "scene-one")):
                with self.subTest(resume=resume, scene=scene, project=bundle["project"]["id"]):
                    with self.assertRaisesRegex(ValueError, "different project/scene"):
                        render_scene(bundle, scene, destination, resume=resume)
                    self.assertEqual(snapshot(destination), expected)
        shot = self.home/"shot-kind"
        render_shot(self.bundle, "first", shot)
        expected = snapshot(shot)
        with self.assertRaisesRegex(ValueError, "render kind"):
            render_scene(self.bundle, "scene-one", shot)
        self.assertEqual(snapshot(shot), expected)

    def test_scene_collision_preserves_first_shot_partial_and_legacy_checkpoint(self):
        destination = self.home/"partial-scene"
        def stop(progress):
            if progress["completed"] == 2:
                raise RuntimeError("first-shot interruption")
        with self.assertRaisesRegex(RuntimeError, "first-shot interruption"):
            render_scene(self.bundle, "scene-one", destination, progress=stop)
        root_manifest = destination/"render-manifest.json"
        checkpoint = json.loads(root_manifest.read_text())
        self.assertEqual(checkpoint["status"], "partial")
        self.assertEqual(checkpoint["completed_frames"], 0)
        self.assertEqual(json.loads((destination/"shots/first/render-manifest.json").read_text())["completed_frames"], 2)
        for legacy in (False, True):
            if legacy:
                root_manifest.unlink()
            expected = snapshot(destination)
            for resume in (True, False):
                with self.assertRaisesRegex(ValueError, "different project/scene"):
                    render_scene(self.bundle, "scene-two", destination, resume=resume)
                self.assertEqual(snapshot(destination), expected)
        resumed = render_scene(self.bundle, "scene-one", destination)
        self.assertEqual(resumed["operation"]["reused_frames"], 2)
        self.assertEqual(resumed["operation"]["rendered_frames"], 4)
        self.assertTrue(validate_render(destination)["ok"])

    def test_scene_cut_and_hardlink_fallback_are_exact_and_atomic(self):
        scene = self.bundle["scenes"][0]
        scene["shots"].append(self.bundle["shots"]["second"])
        self.bundle["scenes"] = [scene]
        scene["shots"][1]["camera"]["position"] = track((0, [4, 0]))
        result = render_scene(self.bundle, "scene-one", self.home/"scene")
        self.assertEqual(result["frame_count"], 12)
        self.assertEqual([(s["start_frame"], s["end_frame"]) for s in result["shots"]], [(0, 6), (6, 12)])
        self.assertNotEqual(result["frames"][0]["sha256"], result["frames"][6]["sha256"])
        self.assertEqual(validate_render(self.home/"scene")["sample_count"], 48000)
        scene_frame = self.home/"scene/frames/000000.png"
        shot_frame = self.home/"scene/shots/first/frames/000000.png"
        other_frame = self.home/"scene/frames/000001.png"
        self.assertTrue(os.path.samefile(scene_frame, shot_frame))
        self.assertFalse(os.path.samefile(scene_frame, other_frame))
        other_hash, digest = file_hash(other_frame), file_hash(shot_frame)
        fallback = self.home/"fallback.png"
        with patch("production_render.os.link", side_effect=OSError(errno.EXDEV, "cross-device")):
            _publish_scene_frame(shot_frame, fallback, digest)
        self.assertEqual(file_hash(fallback), digest)
        self.assertFalse(os.path.samefile(fallback, shot_frame))
        fallback.write_bytes(b"preserve preceding complete destination")
        def fail_copy(source, target):
            Path(target).write_bytes(b"partial")
            raise OSError(errno.ENOSPC, "interrupted copy")
        with patch("production_render.os.link", side_effect=OSError(errno.EXDEV, "cross-device")), \
                patch("production_render.shutil.copyfile", side_effect=fail_copy):
            with self.assertRaisesRegex(OSError, "interrupted copy"):
                _publish_scene_frame(shot_frame, fallback, digest)
        self.assertEqual(fallback.read_bytes(), b"preserve preceding complete destination")
        self.assertFalse(list(self.home.glob(".scene-frame-*.tmp")))
        scene_frame.write_bytes(b"tampered identical frame storage")
        for directory in (self.home/"scene", self.home/"scene/shots/first"):
            with self.assertRaisesRegex(ValueError, "missing or changed"):
                validate_render(directory)
        self.assertEqual(file_hash(other_frame), other_hash)
        repaired = render_scene(self.bundle, "scene-one", self.home/"scene")
        self.assertEqual(repaired["operation"]["rendered_frames"], 1)
        self.assertEqual(file_hash(scene_frame), digest)
        self.assertTrue(os.path.samefile(scene_frame, shot_frame))
        self.assertTrue(validate_render(self.home/"scene")["ok"])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "optional ffmpeg/ffprobe unavailable")
    def test_actual_offline_movie_codec_frame_rate_and_audio_duration(self):
        render_shot(self.bundle, "first", self.home/"movie")
        receipt = mux_video(self.home/"movie")
        self.assertEqual(receipt["frame_count"], 6)
        self.assertEqual(receipt["fps"], {"numerator": 12, "denominator": 1})
        self.assertAlmostEqual(receipt["audio_duration_seconds"], .5, delta=receipt["audio_packet_tolerance_seconds"])


if __name__ == "__main__":
    unittest.main()
