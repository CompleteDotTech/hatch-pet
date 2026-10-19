"""Focused raster/provenance regressions. All artwork here is synthetic fixture data."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import extract_strip_frames as extraction
import inspect_frames as inspection
from profile_spec import load_profile


def fixture_profile(states=1):
    profile = copy.deepcopy(load_profile())
    profile['states'] = profile['states'][:states]
    for state in profile['states']:
        state['frames'], state['durations'] = 2, [110, 220]
    for key in ('rows', 'width', 'height'):
        profile['layout'].pop(key, None)
    profile['events'] = {}
    profile['export'] = {'formats': ['frames'], 'static_state': 'idle', 'static_frame': 0}
    return load_profile(profile)


def fixture_strip(height=100):
    image = Image.new('RGBA', (200, height))
    draw = ImageDraw.Draw(image)
    draw.rectangle((34, 40, 65, 71), fill=(220, 30, 20, 255))
    draw.rectangle((134, 20, 165, 51), fill=(220, 30, 20, 255))
    return image


class StrictRasterTests(unittest.TestCase):
    def test_small_profile_cells_validate_without_large_cell_occupancy_assumptions(self):
        profile = load_profile({'schema_version': 1, 'id': 'tiny-v1',
            'layout': {'columns': 1, 'cell_width': 16, 'cell_height': 16},
            'states': [{'id': 'tiny', 'frames': 1, 'durations': [100], 'purpose': 'Tiny status display', 'motion': 'static'}]})
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / 'source.png'
            image = Image.new('RGBA', (16, 16))
            ImageDraw.Draw(image).rectangle((4, 4, 11, 11), fill='red')
            image.save(source)
            frames = root / 'frames'
            row = extraction.extract_state(source, 'tiny', frames, (0, 255, 0), 48, 'auto', profile)
            result = inspection.inspect_state(frames, 'tiny', 1, {'tiny': row}, None,
                                               argparse.Namespace(profile_data=profile))
            self.assertTrue(result['ok'], result['errors'])

    def test_cross_row_palette_drift_is_reported(self):
        red = Image.new('RGBA', (20, 20), (255, 0, 0, 255))
        blue = Image.new('RGBA', (20, 20), (0, 0, 255, 255))
        rows = [{'state': name, 'metrics': inspection.temporal_metrics([image], {'motion': 'static'})[0]}
                for name, image in [('red', red), ('blue', blue)]]
        result = inspection.consistency_metrics(rows)
        self.assertGreater(result['maximum_palette_distance'], result['thresholds']['palette_distance_warning'])
        self.assertTrue(any('palette' in value for value in result['warnings']))

    def test_incidental_alpha_does_not_disable_chroma(self):
        image = Image.new('RGBA', (100, 100), (0, 255, 0, 255))
        ImageDraw.Draw(image).rectangle((30, 30, 70, 70), fill='red')
        image.putpixel((0, 0), (0, 255, 0, 254))
        out, receipt = extraction.mask_background(image, (0, 255, 0))
        self.assertEqual(receipt['mode'], 'edge-connected-chroma')
        self.assertEqual(out.getpixel((99, 99)), (0, 0, 0, 0))
        self.assertEqual(out.getpixel((50, 50)), (255, 0, 0, 255))

    def test_existing_alpha_preserves_holes_edges_and_green_details(self):
        image = fixture_strip()
        image.putpixel((33, 39), (0, 255, 0, 100))
        image.putpixel((40, 45), (12, 99, 33, 0))
        out, receipt = extraction.mask_background(image, (0, 255, 0))
        self.assertEqual(receipt['mode'], 'alpha')
        self.assertEqual(out.getpixel((33, 39)), (0, 255, 0, 100))
        self.assertEqual(out.getpixel((40, 45)), (0, 0, 0, 0))
        extraction.analyze_slots(out, 2)

    def test_chroma_edge_is_unmixed_without_eroding_opaque_foreground(self):
        image = Image.new('RGBA', (80, 60), (0, 255, 0, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((21, 15, 60, 45), fill='red')
        draw.line((20, 15, 20, 45), fill=(128, 127, 0, 255))
        out, receipt = extraction.mask_background(image, (0, 255, 0), mode='chroma')
        self.assertGreater(receipt['cleaned_edge_pixels'], 0)
        self.assertEqual(out.getpixel((30, 30)), (255, 0, 0, 255))
        self.assertEqual(out.getpixel((20, 30))[:3], (255, 0, 0))
        self.assertAlmostEqual(out.getpixel((20, 30))[3], 128, delta=1)

    def test_key_holes_require_explicit_choice(self):
        image = Image.new('RGBA', (80, 60), (0, 255, 0, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 10, 60, 50), fill='red')
        draw.rectangle((30, 20, 35, 25), fill=(0, 255, 0, 255))
        preserved, _ = extraction.mask_background(image, (0, 255, 0), mode='chroma')
        removed, receipt = extraction.mask_background(image, (0, 255, 0), mode='chroma', holes='key')
        self.assertEqual(preserved.getpixel((32, 22))[3], 255)
        self.assertEqual(removed.getpixel((32, 22)), (0, 0, 0, 0))
        self.assertTrue(receipt['warnings'])

    def test_faint_and_opaque_connections_cannot_hide_extra_poses(self):
        for alpha, message in ((1, 'extra complete pose'), (255, 'narrow bridge')):
            with self.subTest(alpha=alpha):
                image = Image.new('RGBA', (200, 100))
                draw = ImageDraw.Draw(image)
                draw.rectangle((10, 40, 39, 69), fill='red')
                draw.rectangle((60, 40, 89, 69), fill='red')
                draw.rectangle((39, 50, 60, 50), fill=(255, 0, 0, alpha))
                draw.rectangle((135, 40, 164, 69), fill='red')
                with self.assertRaisesRegex(ValueError, message):
                    extraction.analyze_slots(image, 2)

    def test_permitted_detached_details_are_kept(self):
        image = fixture_strip()
        image.putpixel((5, 5), (0, 0, 255, 255))
        with self.assertRaisesRegex(ValueError, 'detached detail'):
            extraction.analyze_slots(image, 2)
        groups, evidence = extraction.analyze_slots(image, 2, allow_detached=True)
        self.assertEqual(len(groups[0]), 2)
        self.assertEqual(evidence['slots'][0]['pixels'], 32 * 32 + 1)

    def test_padding_and_anchor_control_shared_viewport(self):
        image = fixture_strip()
        left, left_settings = extraction.render_slots(image, 2, (150, 150), padding=0, anchor=(0, 0))
        right, _ = extraction.render_slots(image, 2, (150, 150), padding=0, anchor=(1, 1))
        self.assertEqual(right[0].getbbox()[0] - left[0].getbbox()[0], 50)
        self.assertEqual(right[0].getbbox()[1] - left[0].getbbox()[1], 50)
        padded, padded_settings = extraction.render_slots(image, 2, (150, 150), padding=35)
        self.assertEqual(left_settings['scale'], 1)
        self.assertEqual(padded_settings['scale'], .8)
        self.assertGreaterEqual(padded[0].getbbox()[0], 35)

    def test_shared_calibration_keeps_source_size_across_row_viewports(self):
        first, settings_first = extraction.render_slots(fixture_strip(100), 2, scale=.5)
        second, settings_second = extraction.render_slots(fixture_strip(140), 2, scale=.5)
        first_box, second_box = first[0].getbbox(), second[0].getbbox()
        self.assertEqual(first_box[2] - first_box[0], second_box[2] - second_box[0])
        self.assertEqual(first_box[3] - first_box[1], second_box[3] - second_box[1])
        self.assertEqual(settings_first['scale'], settings_second['scale'])

    def test_profile_thresholds_are_measured_and_state_aware(self):
        first = Image.new('RGBA', (100, 100))
        second = Image.new('RGBA', (100, 100))
        ImageDraw.Draw(first).rectangle((20, 20, 40, 40), fill='red')
        ImageDraw.Draw(second).rectangle((21, 40, 41, 60), fill='red')
        settings = {'min_motion': .99, 'max_baseline_shift': .05, 'max_size_ratio': 1.1, 'loop_warning_ratio': 2}
        metric, warnings = inspection.temporal_metrics([first, second], {'motion': 'quiet', 'validation': settings})
        self.assertEqual(metric['thresholds']['min_motion'], .99)
        self.assertEqual(metric['thresholds']['max_baseline_shift'], .05)
        self.assertTrue(any('insufficient' in warning for warning in warnings))
        self.assertTrue(any('baseline' in warning for warning in warnings))
        _, jumping = inspection.temporal_metrics([first, second], {'motion': 'vertical'})
        self.assertFalse(any('baseline' in warning for warning in jumping))
        _, static = inspection.temporal_metrics([first, first], {'motion': 'static'})
        self.assertFalse(any('insufficient' in warning or 'duplicate' in warning for warning in static))

    def test_extraction_lock_recovers_after_process_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            script = 'import sys,os;sys.path.insert(0,sys.argv[1]);from extract_strip_frames import extraction_ownership;from pathlib import Path\nwith extraction_ownership(Path(sys.argv[2])): os._exit(0)'
            subprocess.run([sys.executable, '-c', script, str(Path(extraction.__file__).parent), directory], check=True)
            with extraction.extraction_ownership(Path(directory)):
                self.assertTrue((Path(directory) / '.extraction.lock').is_file())

    def test_extraction_lock_excludes_a_second_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            script = 'import sys;sys.path.insert(0,sys.argv[1]);from extract_strip_frames import extraction_ownership;from pathlib import Path\nwith extraction_ownership(Path(sys.argv[2])): print("unexpected owner")'
            with extraction.extraction_ownership(Path(directory)):
                result = subprocess.run([sys.executable, '-c', script, str(Path(extraction.__file__).parent), directory], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('another extractor owns', result.stderr)

    def test_optional_null_shared_scale_means_no_calibration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'pet_request.json').write_text('{"extraction":{"shared_scale":null}}', encoding='utf-8')
            config = extraction.load_extraction_config(root)
            self.assertNotIn('shared_scale', config)
            self.assertIsNone(extraction.extraction_configuration(fixture_profile(), 'idle', config)['requested_scale'])

    def test_extraction_refuses_linked_state_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.png'
            fixture_strip().save(source)
            frames, outside = root / 'frames', root / 'outside'
            frames.mkdir()
            outside.mkdir()
            try:
                (frames / 'idle').symlink_to(outside, target_is_directory=True)
            except OSError:
                if os.name != 'nt':
                    self.skipTest('symbolic links are unavailable on this host')
                # Directory junctions require no symbolic-link privilege on Windows.
                script = root / 'create-junction.ps1'
                script.write_text('param([string]$LinkPath, [string]$TargetPath)\nNew-Item -ItemType Junction -Path $LinkPath -Target $TargetPath -ErrorAction Stop | Out-Null\n', encoding='utf-8')
                subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script), str(frames / 'idle'), str(outside)], check=True, capture_output=True)
            with self.assertRaisesRegex(ValueError, 'symbolic link or junction'):
                extraction.extract_state(source, 'idle', frames, (0, 255, 0), 48, 'auto', fixture_profile())
            self.assertEqual(list(outside.iterdir()), [])


class StrictProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.frames = self.root / 'frames'
        self.source = self.root / 'idle.png'
        self.profile = fixture_profile()
        (self.root / 'pet_request.json').write_text('{}', encoding='utf-8')
        fixture_strip().save(self.source)
        self.row = extraction.extract_state(self.source, 'idle', self.frames, (0, 255, 0), 48, 'auto', self.profile)

    def validate(self, row=None):
        return inspection.validate_provenance(self.frames, 'idle', inspection.frame_files(self.frames / 'idle'), row or self.row, self.profile)

    def test_complete_current_provenance_passes(self):
        self.assertEqual(self.validate(), [])

    def test_hashed_empty_settings_and_shape_only_evidence_are_rejected(self):
        row = copy.deepcopy(self.row)
        row['settings'] = {}
        row['settings_sha256'] = extraction.object_hash({})
        row['evidence'] = {'slots': [None, None]}
        errors = self.validate(row)
        self.assertTrue(any('configuration' in error for error in errors))
        self.assertTrue(any('segmentation' in error for error in errors))

    def test_stale_calibration_and_forged_current_hash_do_not_pass(self):
        calibration = self.root / 'extraction-settings.json'
        calibration.write_text('{"background":"alpha","key_threshold":36}', encoding='utf-8')
        self.assertTrue(any('calibrated extraction' in error for error in self.validate()))
        row = copy.deepcopy(self.row)
        row['extraction_settings_sha256'] = extraction.digest(calibration)
        self.assertTrue(any('configuration' in error for error in self.validate(row)))

    def test_exact_indices_and_source_content_are_checked(self):
        row = copy.deepcopy(self.row)
        row['frame_indices'] = [True, 1]
        self.assertTrue(any('ordering' in error for error in self.validate(row)))
        fixture_strip(120).save(self.source)
        self.assertTrue(any('source provenance' in error for error in self.validate()))

    def test_prepared_run_rejects_substituted_source_path(self):
        (self.root / 'imagegen-jobs.json').write_text('{}', encoding='utf-8')
        self.assertTrue(any('current prepared decoded/idle.png' in error for error in self.validate()))

    def test_extra_files_block_inspection(self):
        (self.frames / 'idle' / '02.png').write_bytes((self.frames / 'idle' / '00.png').read_bytes())
        args = argparse.Namespace(profile_data=self.profile)
        result = inspection.inspect_state(self.frames, 'idle', 2, {'idle': self.row}, None, args)
        self.assertFalse(result['ok'])
        self.assertTrue(any('exact ordered' in error for error in result['errors']))

    def test_malformed_manifest_and_old_algorithm_are_rejected(self):
        manifest = self.frames / 'frames-manifest.json'
        for value in ({'schema_version': 2, 'rows': [self.row]}, {'schema_version': 3, 'algorithm': 'unknown', 'rows': [self.row]}):
            manifest.write_text(json.dumps(value), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'unsupported or malformed'):
                inspection.load_manifest(self.frames)


if __name__ == '__main__':
    unittest.main()
