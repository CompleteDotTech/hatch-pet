"""Exercise discovery and compilation through the real CLI and existing exporter."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_state_catalog import ROOT, miniature_documents
sys.path.insert(0, str(ROOT / 'scripts'))
from state_catalog import compile_profile, load_library, preview_states, write_compilation
from profile_spec import load_profile


class StateCatalogCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hatch-catalog-cli-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.directory = self.home / 'state-library'; self.directory.mkdir()
        documents = miniature_documents()
        # This raster fixture uses row-normalized source shapes. Production
        # shared-scale profiles still require the existing calibration workflow.
        for state in documents[0]['states']:
            state['animation']['alignment']['scale_policy'] = 'row'
        for name, document in zip(('catalog.json', 'packs.json', 'archetypes.json', 'recipes.json', 'animation-recipes.json'), documents):
            (self.directory / name).write_text(json.dumps(document))

    def cli(self, *args, hatch=False):
        script = ROOT / 'scripts' / ('hatch.py' if hatch else 'state_catalog.py')
        command = [sys.executable, str(script)] + (['states'] if hatch else [])
        return subprocess.run(command + list(args) + ['--library', str(self.directory)],
                              capture_output=True, text=True, encoding='utf-8', cwd=ROOT)

    def okay(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_discovery_through_hatch_lists_every_definition_and_searches_aliases(self):
        listing = self.okay(self.cli('list', '--json', hatch=True))
        self.assertEqual(listing['count'], 6)
        self.assertEqual([state['id'] for state in listing['states']], sorted(state['id'] for state in listing['states']))
        result = self.okay(self.cli('search', 'joyful', '--json'))
        self.assertEqual([state['id'] for state in result['states']], ['happy'])
        self.assertTrue(all(state['artwork_status'] == 'definitions-only' for state in listing['states']))

    def test_filters_pack_archetype_recipe_and_state_inspection_are_functional(self):
        states = self.okay(self.cli('list', '--archetype', 'bird', '--json'))['states']
        self.assertIn('wing-stretch', [state['id'] for state in states])
        self.assertNotIn('writing', [state['id'] for state in states])
        pack = self.okay(self.cli('packs', 'creature'))['packs'][0]
        self.assertEqual(pack['resolved_states'], ['idle', 'happy', 'wing-stretch'])
        self.assertTrue(self.okay(self.cli('archetypes'))['capabilities'])
        self.assertEqual(self.okay(self.cli('recipes', 'greeting'))['recipes'][0]['steps'], ['idle', 'happy', 'idle'])
        self.assertEqual(self.okay(self.cli('recipes', '--animation', 'two-phase'))['recipes'][0]['frames'], 2)
        detail = self.okay(self.cli('show', 'joyful'))
        self.assertEqual(detail['state']['id'], 'happy')
        self.assertIn('generation', detail['state']['animation'])
        self.assertEqual(self.okay(self.cli('validate'))['states'], 6)

    def test_compile_saved_selection_writes_bound_sidecar_and_preserves_style_pipeline(self):
        selection = self.home / 'selection.json'
        selection.write_text(json.dumps({'schema_version': 1, 'profile_id': 'my-character', 'states': ['joyful'],
                                         'packs': ['core'], 'layout': {'cell_width': 96, 'cell_height': 96}}))
        profile_path = self.home / 'compiled.json'
        result = self.okay(self.cli('compile', '--selection', str(selection), '--output', str(profile_path), hatch=True))
        self.assertEqual(result['selected_states'], ['happy', 'idle'])
        self.assertEqual(result['estimates']['model_calls_baseline'], 3)
        self.assertEqual(result['selection_manifest'], str(self.home / 'compiled.selection.json'))
        profile = load_profile(profile_path)
        self.assertEqual(profile['schema_version'], 1)
        run = self.home / 'run'
        prepare = subprocess.run([sys.executable, str(ROOT / 'scripts/prepare_pet_run.py'),
                                  '--profile', str(profile_path), '--output-dir', str(run),
                                  '--pet-name', 'Fixture', '--pet-notes', 'Labeled synthetic test request', '--style-preset', 'plush'],
                                 capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
        self.assertEqual(prepare.returncode, 0, prepare.stderr)
        prompt = (run / 'prompts' / 'rows' / 'happy.md').read_text()
        self.assertIn('Open smile', prompt)
        self.assertIn('plush', prompt.lower())
        self.assertIn('Semantic visual review', prompt)
        self.assertIn('approved canonical', prompt)
        self.assertTrue((run / 'state-selection.json').is_file())
        request = json.loads((run / 'pet_request.json').read_text())
        self.assertEqual(request['state_selection']['path'], 'state-selection.json')
        self.assertFalse((run / 'references/canonical-base.png').exists())

    def test_compile_rejects_unbounded_incompatible_or_malformed_before_writing(self):
        for options, expected in [
            (['--pack', 'studio'], 'selection-only'),
            (['--state', 'wing-stretch'], 'requires anatomy'),
            (['--state', 'writing', '--archetype', 'humanoid'], 'approved props'),
            (['--state', 'idle', '--max-states', '64'], 'allow-large'),
            (['--state', 'happy', '--columns', '1'], 'frame count must fit'),
            (['--state', 'unknown'], 'unknown state'),
        ]:
            with self.subTest(options=options):
                target = self.home / 'should-not-exist.json'
                result = self.cli('compile', *options, '--output', str(target))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)
                self.assertFalse(target.exists())
                self.assertFalse(target.with_suffix('.selection.json').exists())

    def test_substitution_static_subset_and_no_overwrite_are_visible(self):
        path = self.home / 'static.json'
        result = self.okay(self.cli('compile', '--state', 'wing-stretch', '--anatomy-policy', 'substitute',
                                   '--reduced-motion', '--output', str(path)))
        self.assertEqual(result['selected_states'], ['idle'])
        self.assertEqual(result['substitutions'][0]['requested'], 'wing-stretch')
        self.assertEqual(load_profile(path)['states'][0]['frames'], 1)
        previous = path.read_bytes()
        rejected = self.cli('compile', '--state', 'idle', '--output', str(path))
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn('already exists', rejected.stderr)
        self.assertEqual(path.read_bytes(), previous)
        limited = self.okay(self.cli('compile', '--pack', 'studio', '--limit', '2'))
        self.assertEqual(limited['manifest']['selected_states'], ['idle', 'happy'])

    def test_custom_pack_option_and_comma_separated_selectors(self):
        custom = self.home / 'custom-packs.json'
        custom.write_text(json.dumps({'schema_version': 1, 'packs': [{
            'id': 'tiny', 'name': 'Tiny', 'description': 'Custom portable data',
            'states': ['joyful'], 'includes': [], 'exclude': [], 'selection_only': False}]}))
        result = self.okay(self.cli('compile', '--pack-file', str(custom), '--pack', 'tiny', '--states', 'idle,happy,joyful'))
        self.assertEqual(result['manifest']['selected_states'], ['idle', 'happy'])
        self.assertTrue(any(source['name'] == custom.name for source in result['manifest']['source_files']))

    def test_ungenerated_preview_is_explicit(self):
        result = self.okay(self.cli('preview', 'happy'))
        self.assertEqual(result['states'][0]['status'], 'not-generated')
        self.assertFalse(result['states'][0]['frames'])
        self.assertIsNone(result['preview_html'])
        self.assertFalse(result['catalog_binding']['profile_matches'])

    def test_real_export_preview_uses_existing_pngs_fixture_status_and_hashes(self):
        from fixture_workflow import fixture_strip
        from export_assets import export_assets, write_export_receipt
        lib = load_library(self.directory)
        compiled = compile_profile(states=['happy'], cell_width=96, cell_height=96, library=lib)
        frames = self.home / 'fixture' / 'frames'; frames.mkdir(parents=True)
        (frames.parent / 'imagegen-jobs.json').write_text(json.dumps({'fixture_mode': True}))
        for state in compiled['profile']['states']:
            strip = fixture_strip(state, (96, 96))
            folder = frames / state['id']; folder.mkdir()
            for index in range(state['frames']):
                strip.crop((index * 96, 0, (index + 1) * 96, 96)).save(folder / f'{index:02d}.png')
        destination = self.home / 'export'
        export_assets(frames, destination, compiled['profile'])
        discovery = preview_states(['happy'], library=lib, export_dir=destination)
        self.assertEqual(discovery['states'][0]['status'], 'available-fixture')
        self.assertEqual(len(discovery['states'][0]['frames']), 3)
        self.assertFalse(discovery['states'][0]['production_artwork'])
        self.assertFalse(discovery['states'][0]['matches_catalog_selection'])
        self.assertEqual(discovery['preview_html'], str(destination / 'preview.html'))
        (destination / 'state-selection.json').write_text(json.dumps(compiled['manifest']))
        write_export_receipt(destination, compiled['profile'])
        discovery = self.okay(self.cli('preview', 'happy', '--export-dir', str(destination)))
        self.assertEqual(discovery['catalog_binding']['status'], 'matching-bound-selection')
        self.assertTrue(discovery['states'][0]['matches_catalog_selection'])
        self.assertTrue(discovery['states'][0]['fixture'])
        (destination / 'frames' / 'happy' / '00.png').write_bytes(b'changed fixture')
        failed = self.cli('preview', 'happy', '--export-dir', str(destination))
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn('changed artifact', failed.stderr)


if __name__ == '__main__':
    unittest.main()
