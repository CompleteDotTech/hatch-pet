"""Actual retained production art, reusable acting, contact and speech evidence.

These checks inspect current non-fixture sources and a few actual raster frames.
They do not replace visual review or render the full films inside a unit test.
"""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

from PIL import Image, ImageChops

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY/"scripts"))
from production_contracts import load_project
from production_demo import build_pilot, original_provenance
from production_performance import evaluate_track
from production_render import AssetCache, evaluate_frame, file_hash, render_frame, render_layer, transform_point
from production_sources import restore_source_bundle
from production_workflow import shot_dependencies

DEFAULT_PILOT = REPOSITORY/"examples"/"production-pilot"


def read_json(path):
    return json.loads(Path(path).read_text("utf-8"))


def construction_files(root):
    """Only outputs made by the offline recipe, not reviews or full renders."""
    outputs = ("project.json", "cast.json", "evidence/authored-geometry.json",
        "evidence/contact-frame-84.json", "evidence/arrival-construction.png",
        "evidence/exchange-construction.png", "evidence/garden-construction.png")
    result = {name: file_hash(root/name) for name in outputs}
    for name in ("clips", "scenes", "art/components", "art/scenery", "audio"):
        for path in sorted((root/name).rglob("*")):
            if path.is_file() and not path.is_symlink():
                result[path.relative_to(root).as_posix()] = file_hash(path)
    return result


def build_without_external_generation(root):
    """Retained speech may be padded; synthesizing it again is not a rebuild."""
    failure = AssertionError("retained-source rebuild attempted an external subprocess")
    with patch("production_demo.subprocess.run", side_effect=failure), \
            patch("production_demo.subprocess.Popen", side_effect=failure), \
            patch("production_demo.shutil.which", return_value=None):
        return build_pilot(root)


class ProductionPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        supplied = os.environ.get("HATCH_PRODUCTION_PILOT")
        legacy = os.environ.get("HATCH_PRODUCTION_PILOT_ROOT")
        if supplied and legacy and Path(supplied).resolve() != Path(legacy).resolve():
            raise ValueError("HATCH_PRODUCTION_PILOT and HATCH_PRODUCTION_PILOT_ROOT disagree")
        explicit = supplied or legacy
        cls.root = Path(explicit).resolve() if explicit else DEFAULT_PILOT
        if cls.root.is_file() and cls.root.name == "project.json":
            cls.root = cls.root.parent
        if explicit and not (cls.root/"project.json").is_file():
            raise ValueError("explicit pilot root has no project.json; restore its source bundle and run production_demo.py first")
        source = DEFAULT_PILOT/"source-bundle"/"sources-index.json"
        complete = DEFAULT_PILOT/"complete-project"/"production-bundle.json"
        if not explicit and (source.is_file() or complete.is_file()):
            temporary = tempfile.TemporaryDirectory(prefix="hatch-pilot-materialized-")
            cls.addClassCleanup(temporary.cleanup)
            cls.root = Path(temporary.name)/"pilot"
            if source.is_file():
                restored = restore_source_bundle(source, cls.root)
                if restored["fixture"] or restored["provider_called"]:
                    raise ValueError("pilot source transport must retain actual artwork without a provider call")
                audio_index = DEFAULT_PILOT/"audio-source-bundle"/"sources-index.json"
                if not audio_index.is_file():
                    raise ValueError("exact retained pilot audio-source-bundle is missing; do not resynthesize speech")
                speech = Path(temporary.name)/"retained-speech"
                restored_audio = restore_source_bundle(audio_index, speech)
                if restored_audio["fixture"] or restored_audio["provider_called"]:
                    raise ValueError("pilot speech transport must preserve its original non-fixture source")
                shutil.copytree(speech/"audio", cls.root/"audio")
                build_without_external_generation(cls.root)
            else:
                from production_bundle import restore_bundle
                restore_bundle(complete, cls.root)
        if not (cls.root/"project.json").is_file():
            if (cls.root/"art/originals").is_dir():
                raise ValueError("retained pilot originals are present but project.json is missing; build the pilot")
            else:
                raise unittest.SkipTest("actual production pilot originals and source bundle are unavailable")
        cls.bundle = load_project(cls.root/"project.json")
        if cls.bundle["project"]["fixture"]:
            raise ValueError("a synthetic fixture cannot satisfy actual production pilot tests")

    def actor_raster(self, shot, frame, name):
        state = evaluate_frame(self.bundle, shot, frame)
        result = Image.new("RGBA", (640, 360))
        cache = AssetCache(self.root)
        try:
            for layer in state["layers"]:
                if layer["track"] == name:
                    raster = render_layer(layer, result.size, cache, "bicubic")
                    result.alpha_composite(raster)
                    raster.close()
        finally:
            cache.close()
        return result

    def test_retained_imagegen_history_and_exact_originals_are_nonfixture(self):
        self.assertEqual(set(self.bundle["characters"]), {"milo@3.0.0", "luma@3.0.0"})
        attempts, originals = 0, set()
        for name in ("milo", "luma"):
            history = read_json(self.root/"acquisition"/name/"imagegen-jobs.json")
            self.assertFalse(history["fixture_mode"])
            self.assertTrue(history["run_id"])
            self.assertEqual({job["id"] for job in history["jobs"]}, {"base", "parts"})
            for job in history["jobs"]:
                self.assertEqual(job["status"], "generated")
                self.assertEqual(job["source_origin"], "imagegen")
                attempts += job["attempts"]
                provenance = original_provenance(self.root, name, job["id"])
                self.assertFalse(provenance["fixture"])
                self.assertEqual(provenance["source_sha256"], job["source_hash"])
                originals.add(job["source_hash"])
                receipt = self.root/provenance["acquisition"]["receipt_path"]
                self.assertEqual(file_hash(receipt), provenance["acquisition"]["receipt_sha256"])
                self.assertEqual(read_json(receipt)["receipt_template"], job["generation_receipt"])
                call = job["model_call"]
                self.assertTrue(call.get("id") or call.get("unavailable_reason"),
                                "unexposed provider metadata must be recorded as unavailable")
        self.assertEqual(len(originals), 4)
        self.assertGreaterEqual(attempts, len(originals))
        self.assertLessEqual(attempts, self.bundle["project"]["limits"]["max_generation_calls"])
        lost = read_json(self.root/"acquisition/lost-prior-artifacts.json")
        self.assertTrue(lost, "lost acquisition history must stay separate from current retained sources")

    def test_two_scenes_reuse_one_versioned_cast_and_twenty_clips(self):
        settings = self.bundle["project"]["render"]
        self.assertEqual((settings["width"], settings["height"]), (640, 360))
        self.assertEqual(settings["fps"], {"numerator": 12, "denominator": 1})
        durations = {scene["id"]: sum(shot["duration_frames"] for shot in scene["shots"])
                     for scene in self.bundle["scenes"]}
        self.assertEqual(durations, {"seed-exchange": 432, "garden-promise": 264})
        self.assertEqual([durations[name]/12 for name in ("seed-exchange", "garden-promise")], [36, 22])
        self.assertEqual(len(self.bundle["clips"]), 20)
        for name in ("milo", "luma"):
            clips = [clip for clip in self.bundle["clips"].values() if clip["character"] == name+"@3.0.0"]
            self.assertEqual({clip["id"][len(name)+1:] for clip in clips},
                {"idle", "walk-left", "walk-right", "walk-start", "stop", "reaction", "reach", "hold", "release", "exchange"})
        used = []
        for scene in self.bundle["scenes"]:
            scene_clips = set()
            for shot in scene["shots"]:
                self.assertEqual(shot["cast_scale"], .56)
                self.assertEqual({actor["character"] for actor in shot["instances"]}, set(self.bundle["characters"]))
                for actor in shot["instances"]:
                    self.assertEqual((actor["viewpoint"], actor["facing"], actor["costume"]), ("front", "front", "everyday"))
                    scene_clips.update(item["clip"] for item in actor["clips"])
            used.append(scene_clips)
        self.assertTrue({"milo-idle@3.0.0", "luma-idle@3.0.0"}.issubset(used[0] & used[1]))
        self.assertTrue(used[1].issubset(set(self.bundle["clips"])))

    def test_registered_drawing_variants_have_real_alpha_and_fixed_scale(self):
        for character in self.bundle["characters"].values():
            self.assertTrue(character["identity"]["forbid_mirror"])
            self.assertEqual(character["identity"]["allowed_facings"], ["front"])
            for part in character["components"]:
                sizes = {tuple(drawing["image"]["size"]) for drawing in part["drawings"].values()}
                self.assertEqual(len(sizes), 1, part["id"]+" must retain one registered drawing canvas")
                for drawing in part["drawings"].values():
                    source = drawing["image"]
                    self.assertFalse(source["provenance"]["fixture"])
                    self.assertEqual(source["provenance"]["kind"], "derived")
                    self.assertEqual(file_hash(self.root/source["path"]), source["sha256"])
                    with Image.open(self.root/source["path"]) as image:
                        self.assertEqual(image.mode, "RGBA")
                        self.assertEqual(list(image.size), source["size"])
                        self.assertEqual(image.getchannel("A").getextrema(), (0, 255))
                        self.assertIsNotNone(image.getchannel("A").getbbox())
                if part.get("mask"):
                    with Image.open(self.root/part["mask"]["path"]) as mask:
                        self.assertEqual(tuple(part["mask"]["size"]), next(iter(sizes)))
                        self.assertEqual(mask.getchannel("A").getextrema(), (0, 255))
        state = evaluate_frame(self.bundle, "exchange", 84)
        for name, expected in (("milo", .616), ("luma", .56)):
            self.assertAlmostEqual(state["instances"][name]["relative_scale"], expected)
            torso = state["instances"][name]["components"]["torso"]["matrix"]
            self.assertAlmostEqual(math.hypot(torso[0], torso[1]), expected)
            self.assertAlmostEqual(math.hypot(torso[2], torso[3]), expected)

    def test_actual_authored_foot_stances_stay_planted_in_world_pixels(self):
        intervals = [("arrival", 24, 36, "left"), ("arrival", 36, 48, "right"),
                     ("departure", 2, 14, "right"), ("departure", 14, 26, "left"),
                     ("departure", 26, 38, "right")]
        for shot, first, end, side in intervals:
            for name in ("milo", "luma"):
                points = [evaluate_frame(self.bundle, shot, frame)["instances"][name]
                    ["components"]["leg-"+side]["anchors"]["sole"] for frame in range(first, end)]
                drift = max(math.dist(points[0], point) for point in points)
                self.assertLess(drift, 1e-6, f"{shot}/{name}/{side} stance {first}:{end} slipped {drift} world pixels")
                self.assertAlmostEqual(points[0][1], 326, places=6,
                    msg=f"{shot}/{name}/{side} contact must meet the authored ground")
        # The walk also really travels, and the unplanted foot actually lifts.
        earlier = evaluate_frame(self.bundle, "arrival", 24)["instances"]["milo"]
        later = evaluate_frame(self.bundle, "arrival", 35)["instances"]["milo"]
        self.assertAlmostEqual(later["position"][0]-earlier["position"][0], 48.125)
        lifted = evaluate_frame(self.bundle, "arrival", 30)["instances"]["milo"]
        self.assertLess(lifted["components"]["leg-right"]["anchors"]["sole"][1],
                        earlier["components"]["leg-right"]["anchors"]["sole"][1]-5)

    def test_shared_handoff_is_exact_and_discontinuous_tampering_fails(self):
        target = read_json(self.root/"evidence/authored-geometry.json")["position"]
        for frame, owner in ((83, "milo"), (84, "luma"), (85, "luma")):
            state = evaluate_frame(self.bundle, "exchange", frame)
            self.assertEqual(state["props"]["seed-packet"]["owner"], owner)
            self.assertLess(math.dist(state["props"]["seed-packet"]["position"], target), 1e-6)
            for name, side in (("milo", "right"), ("luma", "left")):
                grip = state["instances"][name]["components"]["hand-"+side]["anchors"]["grip"]
                self.assertLess(math.dist(grip, target), 1e-6)
        state = evaluate_frame(self.bundle, "exchange", 84)
        for name, marker in (("milo", "give"), ("luma", "receive")):
            self.assertIn(marker, [event["id"] for event in state["instances"][name]["performance"]["events"]])
        layer = next(item for item in state["layers"] if item["id"] == "seed-packet")
        self.assertEqual(layer["world_matrix"][:4], [1, 0, 0, 1])
        screen = transform_point(state["camera"]["matrix"], target)
        pivot = self.bundle["props"]["seed-packet@1.0.0"]["pivot"]
        self.assertLess(math.dist(transform_point(layer["matrix"], pivot), screen), 1e-6)
        broken = deepcopy(self.bundle)
        broken["shots"]["exchange"]["instances"][1]["position"][0] += 3
        with self.assertRaisesRegex(ValueError, "discontinuous ownership"):
            evaluate_frame(broken, "exchange", 84)

    def test_actual_alpha_proves_entrances_exits_and_layer_visibility(self):
        for name in ("milo", "luma"):
            for shot, frame in (("arrival", 0), ("departure", 119)):
                raster = self.actor_raster(shot, frame, name)
                try:
                    self.assertIsNone(raster.getchannel("A").getbbox(), f"{name} did not fully clear {shot}")
                finally:
                    raster.close()
            raster = self.actor_raster("arrival", 96, name)
            try:
                box = raster.getchannel("A").getbbox()
                self.assertIsNotNone(box)
                self.assertGreater(box[2]-box[0], 90)
                self.assertGreater(box[3]-box[1], 150)
                # Actual painted parts contain substantial color variation.
                colors = raster.getcolors(maxcolors=1000000)
                self.assertGreater(len(colors), 1000)
            finally:
                raster.close()
        shown, _ = render_frame(self.bundle, "exchange", 84)
        hidden, _ = render_frame(self.bundle, "exchange", 84, hidden_tracks={"milo"})
        try:
            self.assertIsNotNone(ImageChops.difference(shown, hidden).getbbox(alpha_only=False))
        finally:
            shown.close()
            hidden.close()

    def test_body_face_gaze_and_mouth_are_independently_evaluated(self):
        first = evaluate_frame(self.bundle, "exchange", 48)
        later = evaluate_frame(self.bundle, "exchange", 70)
        self.assertNotEqual(first["instances"]["milo"]["components"]["arm-right"]["matrix"],
                            later["instances"]["milo"]["components"]["arm-right"]["matrix"])
        self.assertNotEqual(first["instances"]["milo"]["performance"]["components"]["eyes"]["offset"],
                            later["instances"]["milo"]["performance"]["components"]["eyes"]["offset"])
        self.assertEqual(later["instances"]["milo"]["performance"]["components"]["brows"]["drawing"], "raised")
        changed = deepcopy(self.bundle)
        actor = changed["shots"]["exchange"]["instances"][0]
        actor["tracks"]["mouth"] = {"mouth": {"drawing": {"interpolation": "step", "keys": [{"frame": 0, "value": "a"}]}}}
        altered = evaluate_frame(changed, "exchange", 70)
        for component in ("torso", "arm-right", "head", "eyes"):
            self.assertEqual(later["instances"]["milo"]["components"][component]["matrix"],
                             altered["instances"]["milo"]["components"][component]["matrix"])
        before, _ = render_frame(self.bundle, "exchange", 70)
        after, _ = render_frame(changed, "exchange", 70)
        try:
            self.assertNotEqual(before.tobytes(), after.tobytes())
        finally:
            before.close()
            after.close()

    def test_stops_and_declared_scene_continuity_preserve_world_state(self):
        for name, expected_x in (("milo", 230), ("luma", 410)):
            for frame in (84, 96, 119, 143):
                state = evaluate_frame(self.bundle, "arrival", frame)["instances"][name]
                self.assertEqual(state["position"], [expected_x, 326])
        for scene in self.bundle["scenes"]:
            for link in scene["continuity"]:
                previous = self.bundle["shots"][link["from_shot"]]
                before = evaluate_frame(self.bundle, previous["id"], previous["duration_frames"]-1)
                after = evaluate_frame(self.bundle, link["to_shot"], 0)
                self.assertEqual(before["props"]["seed-packet"]["owner"], after["props"]["seed-packet"]["owner"])
                for name in ("milo", "luma"):
                    self.assertEqual(before["instances"][name]["character"], after["instances"][name]["character"])
                    self.assertEqual(before["instances"][name]["relative_scale"], after["instances"][name]["relative_scale"])
                    if "position" in link["requirements"]:
                        self.assertEqual(before["instances"][name]["position"], after["instances"][name]["position"])
        garden = self.bundle["shots"]["garden"]
        self.assertEqual(garden["props"][0]["owner"], "luma")
        self.assertNotEqual(garden["layers"][0]["image"]["sha256"], self.bundle["shots"]["arrival"]["layers"][0]["image"]["sha256"])

    def test_actual_speech_sources_padding_and_mouth_cues_are_hash_bound(self):
        lines = []
        for shot in self.bundle["shots"].values():
            self.assertEqual(len(shot["audio"]), 1)
            for audio in shot["audio"]:
                lines.append(audio["id"])
                self.assertFalse(audio["provenance"]["fixture"])
                self.assertEqual(file_hash(self.root/audio["file"]["path"]), audio["file"]["sha256"])
                with wave.open(str(self.root/audio["file"]["path"]), "rb") as stream:
                    self.assertEqual((stream.getframerate(), stream.getnchannels(), stream.getsampwidth()), (48000, 1, 2))
                    self.assertEqual(stream.getnframes(), audio["duration_frames"]*4000)
                    samples = stream.readframes(stream.getnframes())
                    self.assertTrue(any(samples), "speech must contain actual nonzero PCM")
                provenance = audio["provenance"]
                source = provenance["source"]
                self.assertEqual(file_hash(self.root/source["path"]), source["sha256"])
                operation = json.loads(provenance["operation"]["note"])
                receipt = read_json(self.root/operation["tts_receipt"]["path"])
                self.assertEqual(file_hash(self.root/operation["tts_receipt"]["path"]), operation["tts_receipt"]["sha256"])
                self.assertEqual(receipt["audio"], source)
                self.assertEqual(receipt["text"], operation["text"])
                self.assertEqual((self.root/operation["text"]["path"]).read_text(encoding="utf-8"), audio["text"])
                self.assertEqual(file_hash(self.root/operation["text"]["path"]), operation["text"]["sha256"])
                with wave.open(str(self.root/source["path"]), "rb") as original:
                    unpadded = original.readframes(original.getnframes())
                self.assertEqual(samples[:len(unpadded)], unpadded)
                self.assertFalse(any(samples[len(unpadded):]))
                actor = next(item for item in shot["instances"] if item["id"] == audio["speaker"])
                drawing = actor["tracks"]["mouth"]["mouth"]["drawing"]
                self.assertTrue(any(cue["shape"] != "neutral" for cue in audio["mouth_cues"]))
                for cue in audio["mouth_cues"]:
                    self.assertGreaterEqual(cue["start_frame"], audio["start_frame"])
                    self.assertLessEqual(cue["end_frame"], audio["start_frame"]+audio["duration_frames"])
                    for frame in (cue["start_frame"], cue["end_frame"]-1):
                        self.assertEqual(evaluate_track(drawing, frame), cue["shape"])
                self.assertEqual(evaluate_track(drawing, audio["start_frame"]+audio["duration_frames"]), "neutral")
        self.assertEqual(len(set(lines)), 5)

    def test_dialogue_revision_changes_its_exact_scope_without_new_art(self):
        before = shot_dependencies(self.root, "seed-exchange", "exchange", project=self.bundle)
        unrelated = shot_dependencies(self.root, "garden-promise", "garden", project=self.bundle)
        changed = deepcopy(self.bundle)
        audio = changed["shots"]["exchange"]["audio"][0]
        cue = next(cue for cue in audio["mouth_cues"] if cue["shape"] != "neutral")
        cue["shape"] = "o" if cue["shape"] != "o" else "a"
        after = shot_dependencies(self.root, "seed-exchange", "exchange", project=changed)
        self.assertNotEqual(before, after)
        self.assertEqual(unrelated, shot_dependencies(self.root, "garden-promise", "garden", project=changed))
        self.assertEqual(changed["cast"], self.bundle["cast"])
        self.assertEqual(changed["clips"], self.bundle["clips"])

    def test_rebuilding_retained_sources_makes_no_new_generation_or_tts_call(self):
        expected = construction_files(self.root)
        with tempfile.TemporaryDirectory(prefix="hatch-pilot-rebuild-") as temporary:
            destination = Path(temporary)/"pilot"
            index = DEFAULT_PILOT/"source-bundle"/"sources-index.json"
            if index.is_file():
                restored = restore_source_bundle(index, destination)
                self.assertFalse(restored["fixture"])
                self.assertFalse(restored["provider_called"])
                self.assertFalse(restored["visual_review_performed"])
            else:
                destination.mkdir()
                shutil.copytree(self.root/"acquisition", destination/"acquisition")
                shutil.copytree(self.root/"art/originals", destination/"art/originals")
            shutil.copytree(self.root/"audio/original", destination/"audio/original")
            history = {path.relative_to(destination): file_hash(path)
                       for path in (destination/"acquisition").rglob("*") if path.is_file()}
            result = build_without_external_generation(destination)
            self.assertFalse(result["provider_called"])
            self.assertFalse(result["fixture"])
            self.assertFalse(result["visual_review_performed"])
            self.assertEqual(construction_files(destination), expected)
            self.assertEqual({path: file_hash(destination/path) for path in history}, history)

    def test_fixture_relabel_and_original_tamper_cannot_reuse_acquisition(self):
        with tempfile.TemporaryDirectory(prefix="hatch-pilot-provenance-") as temporary:
            destination = Path(temporary)
            shutil.copytree(self.root/"acquisition", destination/"acquisition")
            shutil.copytree(self.root/"art/originals", destination/"art/originals")
            path = destination/"acquisition/milo/imagegen-jobs.json"
            original = path.read_bytes()
            record = read_json(path)
            record["fixture_mode"] = True
            path.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, "actual ingested imagegen"):
                original_provenance(destination, "milo", "base")
            path.write_bytes(original)
            source = destination/"art/originals/milo-turnaround-v3.png"
            retained = source.read_bytes()
            source.write_bytes(retained[:-1]+bytes([retained[-1]^1]))
            with self.assertRaisesRegex(ValueError, "original source differs"):
                original_provenance(destination, "milo", "base")

    def test_representative_real_frames_are_deterministic_and_visually_distinct(self):
        pixels = []
        for shot, frame in (("arrival", 96), ("exchange", 84), ("garden", 12)):
            first, _ = render_frame(self.bundle, shot, frame)
            second, _ = render_frame(self.bundle, shot, frame)
            try:
                self.assertEqual(first.mode, "RGBA")
                self.assertEqual(first.size, (640, 360))
                self.assertEqual(first.tobytes(), second.tobytes())
                pixels.append(first.tobytes())
            finally:
                first.close()
                second.close()
        self.assertEqual(len(set(pixels)), 3)


if __name__ == "__main__":
    unittest.main()
