"""Portable editor reconstruction, metadata fidelity and actual-consumer evidence."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import warnings
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image

from test_production_render import fixture_project
from production_render import atomic_json, file_hash, render_shot
from production_adapter import (exercise_krita, export_editor_handoff, export_openraster,
                                read_openraster, validate_handoff)


class ProductionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hatch-adapter-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.bundle = fixture_project(self.home/"project")
        self.bundle["project"]["render"]["background"] = "#ffeeddaa"
        self.render = self.home/"render"
        render_shot(self.bundle, "first", self.render)

    def test_openraster_structure_layer_order_and_exact_pixel_roundtrip(self):
        source = self.home/"drawing.ora"
        receipt = export_openraster(self.render, 2, source)
        self.assertTrue(receipt["roundtrip"]["pixel_exact"])
        with zipfile.ZipFile(source) as archive:
            self.assertEqual(archive.namelist()[0], "mimetype")
            self.assertEqual(archive.getinfo("mimetype").compress_type, zipfile.ZIP_STORED)
            self.assertEqual(archive.read("mimetype"), b"image/openraster")
            tree = ET.fromstring(archive.read("stack.xml"))
            self.assertEqual(tree[0][0].attrib["name"], "parcel")
            self.assertEqual(tree[0][-1].attrib["name"], "Render background")
        reconstructed, info = read_openraster(source)
        with Image.open(self.render/"frames/000002.png") as expected:
            self.assertEqual(reconstructed.tobytes(), expected.convert("RGBA").tobytes())
        self.assertTrue(info["merged_image_matches"])
        self.assertEqual(info["layer_count"], 8)
        reconstructed.close()

    def test_portable_handoff_sequence_audio_and_relocation(self):
        destination = self.home/"handoff"
        receipt = export_editor_handoff(self.render, destination, selected_frames=[0, 3, 5])
        self.assertEqual(receipt["application_integration"], "not-performed")
        self.assertEqual(receipt["frame_count"], 6)
        self.assertEqual(receipt["audio"]["sha256"], file_hash(destination/"audio.wav"))
        for index in range(6):
            self.assertEqual(file_hash(destination/"animation"/f"{index:06d}.png"), file_hash(self.render/"frames"/f"{index:06d}.png"))
        moved = self.home/"moved"
        shutil.copytree(destination, moved)
        self.assertTrue(validate_handoff(moved)["ok"])
        self.assertNotIn(str(self.home), (destination/"handoff.json").read_text())

    def test_tampered_sequence_and_unlisted_files_fail_without_deletion(self):
        destination = self.home/"handoff"
        export_editor_handoff(self.render, destination)
        unrelated = destination/"notes.txt"
        unrelated.write_text("Preserve this")
        with self.assertRaisesRegex(ValueError, "inventory differs"):
            validate_handoff(destination)
        with self.assertRaisesRegex(ValueError, "must be empty"):
            export_editor_handoff(self.render, destination)
        self.assertEqual(unrelated.read_text(), "Preserve this")
        unrelated.unlink()
        (destination/"animation/000003.png").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "missing or changed"):
            validate_handoff(destination)

    def test_nested_reserved_names_cannot_escape_exact_file_inventory(self):
        destination = self.home/"handoff"
        export_editor_handoff(self.render, destination)
        for relative in ("animation/handoff.json", "drawings/consumer-integration.json",
                         "animation/consumer-evidence/unlisted.txt"):
            path = destination/relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"preserve this unlisted nested evidence")
            with self.subTest(path=relative):
                with self.assertRaisesRegex(ValueError, "inventory differs"):
                    validate_handoff(destination)
                self.assertEqual(path.read_bytes(), b"preserve this unlisted nested evidence")
            path.unlink()
        self.assertTrue(validate_handoff(destination)["ok"])

    def test_consumer_evidence_symlinks_fail_before_external_calls_or_writes(self):
        destination = self.home/"handoff"
        export_editor_handoff(self.render, destination)
        external = self.home/"outside-evidence"
        external.mkdir()
        sentinel = external/"preserve.png"
        sentinel.write_bytes(b"outside this handoff")
        expected = (sentinel.read_bytes(), sentinel.stat().st_mtime_ns)
        for relative, target in (("consumer-evidence", external),
                                 ("consumer-evidence/krita-roundtrip.png", sentinel),
                                 ("consumer-integration.json", sentinel)):
            path = destination/relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to(target, target_is_directory=target.is_dir())
            with self.subTest(path=relative):
                with self.assertRaisesRegex(ValueError, "symlink"):
                    validate_handoff(destination)
                with patch("production_adapter.subprocess.run") as run:
                    with self.assertRaisesRegex(ValueError, "symlink"):
                        exercise_krita(destination, executable="must-not-run")
                    run.assert_not_called()
                self.assertEqual((sentinel.read_bytes(), sentinel.stat().st_mtime_ns), expected)
                self.assertEqual(list(external.iterdir()), [sentinel])
            path.unlink()
        self.assertTrue(validate_handoff(destination)["ok"])

    def test_handoff_metadata_is_bound_to_retained_render_and_audio(self):
        destination = self.home/"handoff"
        original = export_editor_handoff(self.render, destination)
        changes = [
            (("source_render_manifest_sha256",), "0"*64, "source render manifest hash"),
            (("fps",), {"numerator": 24, "denominator": 1}, "fps differs"),
            (("resolution",), [999, 1], "resolution differs"),
            (("frame_count",), 5, "frame_count differs"),
            (("fixture",), False, "fixture differs"),
            (("audio", "sample_count"), 1, "audio metadata"),
            (("audio", "sha256"), "0"*64, "audio metadata"),
            (("animation", "step"), 2, "animation import settings"),
            (("drawings", 0, "source_frame_sha256"), "0"*64, "drawing hashes"),
        ]
        for keys, value, message in changes:
            with self.subTest(keys=keys):
                altered = deepcopy(original)
                target = altered
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = value
                atomic_json(destination/"handoff.json", altered)
                with self.assertRaisesRegex(ValueError, message):
                    validate_handoff(destination)
        atomic_json(destination/"handoff.json", original)
        self.assertTrue(validate_handoff(destination)["ok"])

    def test_rebinding_file_inventory_cannot_hide_wrong_source_frame_or_manifest(self):
        destination = self.home/"handoff"
        original = export_editor_handoff(self.render, destination)
        target = destination/"animation/000003.png"
        original_pixels = target.read_bytes()
        shutil.copyfile(destination/"animation/000002.png", target)
        altered = deepcopy(original)
        altered["files"]["animation/000003.png"] = file_hash(target)
        atomic_json(destination/"handoff.json", altered)
        with self.assertRaisesRegex(ValueError, "animation differs from retained source"):
            validate_handoff(destination)
        target.write_bytes(original_pixels)
        retained = destination/"source-render-manifest.json"
        source = json.loads(retained.read_text())
        source["renderer"]["version"] = "tampered"
        atomic_json(retained, source)
        altered = deepcopy(original)
        altered["files"][retained.name] = file_hash(retained)
        atomic_json(destination/"handoff.json", altered)
        with self.assertRaisesRegex(ValueError, "source render manifest hash"):
            validate_handoff(destination)

    def test_actual_pcm_truncation_fails_even_if_all_metadata_hashes_are_rebound(self):
        destination = self.home/"handoff"
        handoff = export_editor_handoff(self.render, destination)
        audio = destination/"audio.wav"
        audio.write_bytes(audio.read_bytes()[:-4])
        retained = destination/"source-render-manifest.json"
        source = json.loads(retained.read_text())
        source["audio"]["sha256"] = file_hash(audio)
        atomic_json(retained, source)
        handoff["files"]["audio.wav"] = file_hash(audio)
        handoff["files"][retained.name] = file_hash(retained)
        handoff["source_render_manifest_sha256"] = file_hash(retained)
        handoff["audio"]["sha256"] = file_hash(audio)
        atomic_json(destination/"handoff.json", handoff)
        with self.assertRaisesRegex(ValueError, "truncated audio PCM"):
            validate_handoff(destination)

    def test_actual_pcm_duration_rejects_internally_rebound_frame_rate(self):
        destination = self.home/"handoff"
        handoff = export_editor_handoff(self.render, destination)
        retained = destination/"source-render-manifest.json"
        source = json.loads(retained.read_text())
        faster = {"numerator": 24, "denominator": 1}
        for record in (handoff, handoff["audio"], source, source["audio"], source["settings"]):
            record["fps"] = faster
        atomic_json(retained, source)
        handoff["files"][retained.name] = file_hash(retained)
        handoff["source_render_manifest_sha256"] = file_hash(retained)
        atomic_json(destination/"handoff.json", handoff)
        with self.assertRaisesRegex(ValueError, "actual PCM timing"):
            validate_handoff(destination)

    def test_malicious_ora_paths_duplicates_and_pixel_bound(self):
        source = self.home/"good.ora"
        export_openraster(self.render, 0, source)
        with zipfile.ZipFile(source) as archive:
            members = [(info, archive.read(info.filename)) for info in archive.infolist()]
        for name, added in (("path", ("../escape.png", b"no")), ("duplicate", ("mimetype", b"image/openraster"))):
            target = self.home/(name+".ora")
            with warnings.catch_warnings(), zipfile.ZipFile(target, "w") as archive:
                warnings.simplefilter("ignore", UserWarning)
                for info, data in members:
                    archive.writestr(info, data)
                archive.writestr(*added)
            with self.assertRaises(ValueError):
                read_openraster(target)
        target = self.home/"large.ora"
        with zipfile.ZipFile(target, "w") as archive:
            for info, data in members:
                if info.filename == "stack.xml":
                    tree = ET.fromstring(data)
                    tree.set("w", "1000000")
                    data = ET.tostring(tree)
                archive.writestr(info, data)
        with self.assertRaisesRegex(ValueError, "dimensions exceed"):
            read_openraster(target)
        self.assertFalse((self.home/"escape.png").exists())

    def test_layered_edit_roundtrip_preserves_edit_and_requires_new_approval(self):
        source = self.home/"drawing.ora"
        export_openraster(self.render, 0, source)
        target = self.home/"edited.ora"
        with zipfile.ZipFile(source) as archive, zipfile.ZipFile(target, "w") as edited:
            for info in archive.infolist():
                data = archive.read(info.filename)
                if info.filename == "stack.xml":
                    tree = ET.fromstring(data)
                    tree[0][0].set("visibility", "hidden")
                    data = ET.tostring(tree)
                edited.writestr(info, data)
        original, _ = read_openraster(source)
        modified, info = read_openraster(target)
        self.assertNotEqual(original.tobytes(), modified.tobytes())
        self.assertFalse(info["merged_image_matches"])
        original.close()
        modified.close()

    def test_unavailable_consumer_is_separate_from_adapter_success(self):
        destination = self.home/"handoff"
        export_editor_handoff(self.render, destination)
        with patch("production_adapter.shutil.which", return_value=None):
            report = exercise_krita(destination)
        self.assertTrue(report["exported_assets"])
        self.assertTrue(report["adapter_roundtrip_tested"])
        self.assertEqual(report["application_integration"], "not-performed")
        self.assertIn("unavailable", report["reason"])
        self.assertTrue(validate_handoff(destination)["ok"])

    @unittest.skipUnless(os.environ.get("HATCH_KRITA_EXECUTABLE") or shutil.which("krita"), "Krita not available; adapter tests remain separate from integration")
    def test_actual_local_krita_import_export_and_layer_roundtrip(self):
        destination = self.home/"handoff"
        export_editor_handoff(self.render, destination)
        report = exercise_krita(destination, executable=os.environ.get("HATCH_KRITA_EXECUTABLE"))
        self.assertEqual(report["application_integration"], "verified", report)
        self.assertTrue(report["layers_preserved"])
        self.assertEqual(report["timeline_integration"], "not-performed")


if __name__ == "__main__":
    unittest.main()
