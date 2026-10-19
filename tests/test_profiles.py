"""Profile and preparation regressions; every image here is a labeled fixture."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from profile_spec import DEFAULT_PROFILE, load_profile, profile_hash
from prepare_pet_run import build_constraints, discovery_guidance, make_jobs, regenerate_prompts


class ProfileTests(unittest.TestCase):
    def raw(self):
        return json.loads(DEFAULT_PROFILE.read_text(encoding='utf-8'))

    def test_default_contract_is_unchanged(self):
        p = load_profile()
        self.assertEqual((p['layout']['columns'], p['layout']['rows'], p['layout']['cell_width'], p['layout']['cell_height'], p['layout']['width'], p['layout']['height']), (8, 9, 192, 208, 1536, 1872))
        self.assertEqual([(s['id'], s['frames'], s['durations']) for s in p['states']], [
            ('idle', 6, [280, 110, 110, 140, 140, 320]),
            ('running-right', 8, [120] * 7 + [220]),
            ('running-left', 8, [120] * 7 + [220]),
            ('waving', 4, [140] * 3 + [280]),
            ('jumping', 5, [140] * 4 + [280]),
            ('failed', 8, [140] * 7 + [240]),
            ('waiting', 6, [150] * 5 + [260]),
            ('running', 6, [120] * 5 + [220]),
            ('review', 6, [150] * 5 + [280]),
        ])
        self.assertEqual(profile_hash(p), profile_hash(load_profile(p)))
        self.assertTrue(all(s['generation'].get('instructions') for s in p['states']))

    def test_examples_are_supported_profiles_with_semantic_instructions(self):
        paths = sorted((ROOT / 'examples').glob('*.json'))
        self.assertEqual(len(paths), 10)
        for path in paths:
            with self.subTest(path=path.name):
                p = load_profile(path)
                self.assertTrue(all(s['generation'].get('instructions') for s in p['states']))
                self.assertIn('browser', p['export']['formats'])
                self.assertTrue(p['events'])

    def test_unsupported_or_malformed_profile_values_rejected(self):
        mutations = [
            lambda p: p.update(schema_version=True),
            lambda p: p.update(extra=True),
            lambda p: p['layout'].update(columns=True),
            lambda p: p['layout'].update(rows=99),
            lambda p: p['states'][0].update(motion={}),
            lambda p: p['states'][0].update(id='base'),
            lambda p: p['states'][0].update(id='nul'),
            lambda p: p['states'][0].update(generation=[]),
            lambda p: p['states'][0]['generation'].update(requires_identity_reference=False),
            lambda p: p['states'][0]['alignment'].update(pivot=[True, 0.5]),
            lambda p: p['states'][0]['alignment'].update(scale=1.0),
            lambda p: p['states'][0]['validation'].update(minimum_motion=0.5),
            lambda p: p['states'][0]['validation'].update(min_motion=float('nan')),
            lambda p: p['states'][0]['validation'].update(max_size_ratio=True),
            lambda p: p['states'][0]['validation'].update(max_baseline_shift=2),
            lambda p: p['states'][2]['allowed_derivations'].extend(p['states'][2]['allowed_derivations']),
            lambda p: p['validation'].update(allow_detached_details='yes'),
            lambda p: p['validation'].update(require_provenance=False),
            lambda p: p['validation'].update(mystery=True),
            lambda p: p['export'].update(formats=['frames', 'frames']),
            lambda p: p['export'].update(static_frame=True),
            lambda p: p['events'].update(missing='missing-state'),
        ]
        for mutate in mutations:
            p = self.raw()
            mutate(p)
            with self.subTest(mutation=mutate), self.assertRaisesRegex(ValueError, 'invalid profile:'):
                load_profile(p)

    def test_derivation_cycle_rejected(self):
        p = self.raw()
        p['states'][1]['allowed_derivations'] = [{'kind': 'horizontal-mirror', 'source': 'running-left', 'requires_explicit_approval': True}]
        with self.assertRaisesRegex(ValueError, 'derivation cycle'):
            load_profile(p)

    def test_shared_scale_is_one_calibration_across_rows(self):
        p = self.raw()
        p['states'][0]['alignment'].update(scale_policy='shared', scale=0.7)
        p['states'][1]['alignment'].update(scale_policy='shared')
        normalized = load_profile(p)
        self.assertEqual(normalized['states'][1]['alignment']['scale'], 0.7)
        p['states'][1]['alignment']['scale'] = 0.8
        with self.assertRaisesRegex(ValueError, 'one common calibration'):
            load_profile(p)

    def test_custom_name_does_not_create_an_unconfigured_derivation(self):
        p = self.raw()
        p['states'][2]['allowed_derivations'] = []
        jobs = make_jobs(Path.cwd(), [], p)
        left = next(job for job in jobs if job['id'] == 'running-left')
        self.assertEqual(left['depends_on'], ['base'])
        self.assertFalse(left['derivation_policy']['may_derive'])


class PreparationTests(unittest.TestCase):
    def prepare(self, run, *args):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/prepare_pet_run.py'), '--output-dir', str(run), '--profile', str(ROOT / 'examples/web-status.json'), '--pet-name', 'Fixture', *args], capture_output=True, text=True, encoding='utf-8')

    def test_constraints_and_style_survive_prompt_rebuild(self):
        with tempfile.TemporaryDirectory(prefix='hatch-profile-test-') as td:
            root = Path(td)
            discovery = root / 'brand.json'
            discovery.write_text(json.dumps({'avoid': ['red cape', 'tiny lettering'], 'sources': ['https://example.test/brand'], 'uncertainty': 'Fixture source only.'}), encoding='utf-8')
            run = root / 'run'
            result = self.prepare(run, '--require', 'red cape', '--avoid', 'glossy plastic', '--style-preset', 'plush', '--style-notes', 'visible soft stitching', '--brand-discovery-file', str(discovery))
            self.assertEqual(result.returncode, 0, result.stderr)
            request = json.loads((run / 'pet_request.json').read_text())
            profile = load_profile(run / 'profile.json')
            self.assertEqual(request['constraints']['brand_avoid'], ['red cape', 'tiny lettering'])
            self.assertEqual(request['constraints']['effective_brand_avoid'], ['tiny lettering'])
            self.assertTrue(request['constraints']['conflicts'])
            retry = run / 'prompts/row-retries/ready.md'
            retry.write_text(retry.read_text() + '\nRepair required: preserve the left ear.\nKeep the white tip.\n')
            original_base = (run / 'prompts/base-pet.md').read_bytes()
            touched = regenerate_prompts(run, request, profile, {'background': 'chroma', 'chroma_key': {'hex': '#00FFFF'}})
            self.assertEqual(len(touched), 6)
            self.assertEqual((run / 'prompts/base-pet.md').read_bytes(), original_base)
            for relative in touched:
                prompt = (run / relative).read_text()
                for term in ('red cape', 'glossy plastic', 'visible soft stitching', 'https://example.test/brand', 'Fixture source only.', '#00FFFF'):
                    self.assertIn(term, prompt)
            self.assertIn('Repair required: preserve the left ear.', retry.read_text())
            self.assertIn('Keep the white tip.', retry.read_text())
            self.assertEqual(json.loads((run / 'pet_request.json').read_text()), request)

    def test_explicit_conflict_fails_before_writing_output(self):
        with tempfile.TemporaryDirectory(prefix='hatch-profile-test-') as td:
            run = Path(td) / 'run'
            result = self.prepare(run, '--require', 'Red Cape', '--avoid', 'red cape')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('conflicting explicit require/avoid', result.stderr)
            self.assertFalse(run.exists())

    def test_force_cannot_reuse_stale_decoded_assets(self):
        with tempfile.TemporaryDirectory(prefix='hatch-profile-test-') as td:
            run = Path(td) / 'run'
            (run / 'decoded').mkdir(parents=True)
            original = run / 'decoded/stale.png'
            original.write_bytes(b'untouched fixture marker')
            result = self.prepare(run, '--force')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(original.read_bytes(), b'untouched fixture marker')
            self.assertFalse((run / 'imagegen-jobs.json').exists())

    def test_markdown_discovery_avoids_are_preserved(self):
        with tempfile.TemporaryDirectory(prefix='hatch-profile-test-') as td:
            path = Path(td) / 'discovery.md'
            path.write_text('avoid:\n- neon colors\n- tiny labels\n\nSources: https://example.test/style\n')
            discovery = discovery_guidance(path)
            self.assertEqual(discovery['avoid'], ['neon colors', 'tiny labels'])
            self.assertEqual(discovery['sources'], ['https://example.test/style'])
            with self.assertRaisesRegex(ValueError, 'must be a list'):
                build_constraints({'require': 'not-a-list'}, [], [], discovery)

    def test_custom_prompts_use_profile_not_codex_names(self):
        with tempfile.TemporaryDirectory(prefix='hatch-profile-test-') as td:
            run = Path(td) / 'run'
            result = self.prepare(run)
            self.assertEqual(result.returncode, 0, result.stderr)
            prompt = (run / 'prompts/rows/working.md').read_text()
            self.assertIn('Process a request with a small purposeful hand movement', prompt)
            self.assertIn('true transparent alpha', prompt)
            self.assertNotIn('Codex', prompt)
            jobs = json.loads((run / 'imagegen-jobs.json').read_text())['jobs']
            for job in jobs[1:]:
                self.assertIn('references/canonical-base.png', [item['path'] for item in job['input_images']])


if __name__ == '__main__':
    unittest.main()
