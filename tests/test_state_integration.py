"""Catalog selections consume the real source, review and export contracts."""
import argparse
import copy
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

from fixture_workflow import build_run, hatch, record_fixture_review, small_profile
from profile_spec import load_profile
from state_selection import prepared_selection

ROOT = Path(__file__).resolve().parents[1]


class StateLifecycleIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hatch-state-integration-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def compiled(self, states=None, **options):
        from state_catalog import compile_profile
        result = compile_profile(states=states or ['idle', 'running', 'review', 'failed'],
            archetype='humanoid', cell_width=96, cell_height=96, **options)
        path = self.home / 'character.json'
        hatch.atomic(path, result['profile'])
        hatch.atomic(path.with_suffix('.selection.json'), result['manifest'])
        return path, result

    def prepare(self, profile, identity=None):
        identity_path = None
        if identity is not None:
            identity_path = self.home / 'identity.json'
            hatch.atomic(identity_path, identity)
        args = argparse.Namespace(replace_inputs=False, fixture_mode=True, profile=str(profile),
            pet_name='Catalog fixture', pet_notes='Synthetic fixture; no production artwork',
            reference=[], avoid=[], require=[], brand_source=[],
            identity=str(identity_path) if identity_path else None)
        root = self.home / 'run'
        hatch.prepare(root, args)
        return root, hatch.manifest(root)

    def test_codex_profile_is_byte_for_byte_unchanged(self):
        self.assertEqual(hashlib.sha256((ROOT / 'profiles/codex-v1.json').read_bytes()).hexdigest(),
            'f4e0279f8634ea53ef544ecb49b9a71ec2565c61ec5b8e63163ecc5ead478a6b')
        default = load_profile()
        self.assertEqual([s['id'] for s in default['states']],
            ['idle', 'running-right', 'running-left', 'waving', 'jumping', 'failed', 'waiting', 'running', 'review'])
        self.assertEqual((default['layout']['columns'], default['layout']['cell_width'],
            default['layout']['cell_height']), (8, 192, 208))

    def test_preparation_binds_catalog_and_preserves_imagegen_handoffs(self):
        path, result = self.compiled()
        root, data = self.prepare(path)
        self.assertEqual(prepared_selection(root), result['manifest'])
        self.assertEqual(len(data['jobs']), len(result['profile']['states']) + 1)
        self.assertFalse(result['profile']['export']['codex_compatible'])
        self.assertTrue(all(job['status'] == 'pending' for job in data['jobs']))
        with self.assertRaises(ValueError):
            hatch.claim(root, data, 'running')
        for spec in result['profile']['states']:
            job = hatch.job_for(data, spec['id'])
            prompt = (root / job['prompt_file']).read_text(encoding='utf-8')
            self.assertIn(spec['generation']['instructions'], prompt)
            self.assertIn('Frame durations in playback order:', prompt)
            self.assertIn('installed imagegen skill', prompt)
            self.assertIn('canonical base and all original references', prompt)
            self.assertTrue(any(item['path'] == 'references/canonical-base.png' for item in job['input_images']))
            self.assertTrue(any('layout guide' in item['role'] for item in job['input_images']))
            self.assertFalse(job['allow_prompt_only_generation'])
        self.assertIn('state-selection.json', hatch.artifact_hashes(root))

    def test_wrong_profile_binding_fails_before_run_creation(self):
        path, result = self.compiled()
        manifest = copy.deepcopy(result['manifest'])
        manifest['profile_sha256'] = '0' * 64
        from asset_contracts import hash_object
        manifest.pop('manifest_sha256')
        manifest['manifest_sha256'] = hash_object(manifest)
        hatch.atomic(path.with_suffix('.selection.json'), manifest)
        with self.assertRaisesRegex(ValueError, 'profile'):
            self.prepare(path)
        self.assertFalse((self.home / 'run').exists())

    def test_required_prop_needs_independent_identity_approval(self):
        catalog = hatch.read(ROOT / 'state-library/catalog.json')
        state = next(s for s in catalog['states'] if s['props']['required'])
        from state_catalog import load_library
        library = load_library()
        # Supply every declared capability only to compile this synthetic test's
        # metadata. Preparation must still enforce explicit identity prop approval.
        raw = hatch.read(ROOT / 'state-library/archetypes.json')
        capabilities = [entry['id'] if isinstance(entry, dict) else entry for entry in raw['capabilities']]
        path, result = self.compiled([state['id']], capabilities=capabilities,
            approved_props=state['props']['required'], library=library)
        with self.assertRaisesRegex(ValueError, 'identity.approved_props'):
            self.prepare(path, {'schema_version': 1})
        root, _ = self.prepare(path, {'schema_version': 1, 'approved_props': result['manifest']['required_props']})
        self.assertEqual(prepared_selection(root)['required_props'], result['manifest']['required_props'])

    def test_direction_constraints_reject_conflicting_identity(self):
        path, _ = self.compiled(['running-left'])
        with self.assertRaisesRegex(ValueError, 'direction'):
            self.prepare(path, {'schema_version': 1, 'directions': {'running-left': 'right'}})

    def test_selection_tampering_blocks_lifecycle(self):
        path, _ = self.compiled()
        root, _ = self.prepare(path)
        altered = hatch.read(root / 'state-selection.json')
        altered['artwork_status'] = 'reviewed-production'
        hatch.atomic(root / 'state-selection.json', altered)
        with self.assertRaisesRegex(ValueError, 'changed after preparation'):
            hatch.manifest(root)

    def test_archive_preserves_original_selection_after_profile_revision(self):
        from portable_runs import archive_run, restore_run
        from state_selection import export_selection
        path, result = self.compiled()
        root, data = self.prepare(path)
        revised = load_profile(root / 'profile.json')
        revised['states'][0]['durations'][0] += 10
        updated = self.home / 'revised-profile.json'
        hatch.atomic(updated, revised)
        hatch.revise_profile(root, data, updated)
        self.assertEqual(prepared_selection(root), result['manifest'])
        snapshot = self.home / 'run.zip'
        archive_run(root, hatch.manifest(root), snapshot)
        restored = self.home / 'restored'
        restore_run(snapshot, restored)
        self.assertEqual(prepared_selection(restored), result['manifest'])
        self.assertEqual(hatch.manifest(restored)['run_id'], data['run_id'])
        exported = self.home / 'selection-export'
        exported.mkdir()
        provenance = export_selection(restored, exported, load_profile(restored / 'profile.json'))
        self.assertFalse(provenance['current_profile_matches_selection'])
        self.assertEqual(provenance['original_profile_sha256'], result['manifest']['profile_sha256'])
        self.assertEqual(hatch.read(exported / 'state-selection.json'), result['manifest'])

    def test_hatch_catalog_errors_have_nonzero_exit_status(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/hatch.py'), 'states',
            'show', 'this-is-not-a-canonical-state'], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Traceback', result.stderr)


class EncodedPlaybackIntegration(unittest.TestCase):
    def test_once_hold_and_static_alternatives_survive_actual_export(self):
        with tempfile.TemporaryDirectory(prefix='hatch-state-encodings-') as td:
            home = Path(td)
            profile = small_profile()
            profile['states'][0]['playback'] = {'mode': 'once', 'completion': 'jump', 'reduced_motion_frame': 2}
            profile['states'][1]['playback'] = {'mode': 'hold', 'hold_frame': 1, 'reduced_motion_frame': 2}
            root = home / 'run'
            data = build_run(root, profile)
            with self.assertRaisesRegex(ValueError, 'review'):
                hatch.package(root, data, home / 'unreviewed-package')
            record_fixture_review(root, data)
            hatch.export(root, data, home / 'export')
            metadata = hatch.read(home / 'export/animation.json')
            self.assertTrue(metadata['fixture'])
            self.assertFalse(metadata['integration_verified'])
            for state in metadata['states']:
                self.assertEqual(state['static_frame'], 2)
                with Image.open(home / 'export' / state['static']) as static:
                    with Image.open(home / 'export' / state['frames'][2]['path']) as frame:
                        self.assertEqual(static.convert('RGBA').tobytes(), frame.convert('RGBA').tobytes())
            with Image.open(home / 'export/animations/rest.gif') as gif:
                self.assertNotIn('loop', gif.info)
                self.assertEqual(gif.n_frames, 3)
            with Image.open(home / 'export/animations/rest.webp') as webp:
                self.assertEqual(webp.info['loop'], 1)
                self.assertEqual(webp.n_frames, 3)
            for suffix in ('gif', 'webp'):
                with Image.open(home / 'export' / ('animations/jump.' + suffix)) as image:
                    self.assertEqual(image.n_frames, 1)
            hatch.package(root, data, home / 'package')
            self.assertTrue(hatch.verify_package(home / 'package')['fixture'])


class SavedSelectionWorkflows(unittest.TestCase):
    def test_saved_examples_and_custom_pack_are_bounded_and_consumable(self):
        from state_catalog import compile_selection, compile_profile, load_library
        expected = {'expressive-cat': 25, 'coding-assistant': 49, 'game-npc': 29,
            'obs-mascot': 25, 'accessible-feedback': 14, 'reference-studio': 32,
            'stream-conversation': 5}
        library = load_library()
        paths = sorted((ROOT / 'examples/state-selections').glob('*.json'))
        self.assertEqual({path.stem for path in paths}, set(expected))
        for path in paths:
            with self.subTest(selection=path.name):
                compiled = compile_selection(hatch.read(path), library=library)
                profile, evidence = compiled['profile'], compiled['manifest']
                self.assertEqual(len(profile['states']), expected[path.stem])
                self.assertFalse(profile['export']['codex_compatible'])
                self.assertEqual(evidence['artwork_status'], 'definitions-only')
                self.assertLessEqual(evidence['estimates']['frame_count'], 1024)
                self.assertEqual(evidence['estimates']['model_calls_baseline'], expected[path.stem] + 1)
        extended = load_library(pack_files=[ROOT / 'examples/state-packs/quiet-companion.json'])
        result = compile_profile(states=['idle'], packs=['quiet-companion'], archetype='cat', library=extended)
        self.assertEqual(result['manifest']['selected_states'], ['idle', 'relaxed-idle', 'content', 'listening'])

    def test_reduced_motion_demo_exercises_real_import_review_export_pipeline(self):
        from demonstrate_states import demonstrate_states
        with tempfile.TemporaryDirectory(prefix='hatch-state-demo-') as directory:
            accepted = demonstrate_states('states-accessibility', directory)
            self.assertTrue(accepted['ok'])
            self.assertTrue(accepted['fixture'])
            self.assertEqual((accepted['states'], accepted['frames']), (14, 14))
            self.assertEqual(accepted['model_calls'], 0)
            self.assertFalse(accepted['production_artwork_accepted'])
            self.assertFalse(accepted['external_integration_verified'])


if __name__ == '__main__':
    unittest.main()
