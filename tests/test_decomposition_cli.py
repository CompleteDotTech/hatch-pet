"""Exercise public Hatch commands across reverse import, review, portability and reuse."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

from decomposition_fixtures import FIXTURE_ORIGIN, make_fixture

ROOT = Path(__file__).resolve().parents[1]


class DecompositionCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='hatch-decomposition-cli-')
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.run = self.home / 'run'
        self.fixture = make_fixture(self.home / 'fixture', 'creature')

    def execute(self, command, *arguments, run=None, succeeds=True):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/hatch.py'), command,
            '--run-dir', str(run or self.run), *map(str, arguments)],
            capture_output=True, text=True, timeout=60, cwd=ROOT)
        if succeeds:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        return result

    def create(self):
        return self.execute('decompose', '--source', self.fixture.source,
            '--annotations', self.fixture.annotation, '--fixture-mode', '--origin', FIXTURE_ORIGIN,
            '--pet-name', 'CLI fixture creature', '--pet-id', 'cli-fixture-creature')

    def test_documented_cli_reverse_to_forward_path_keeps_actual_artifact_evidence(self):
        created = self.create()
        self.assertEqual(created['character']['id'], 'cli-fixture-creature')
        self.assertTrue(created['fixture'])
        self.assertEqual(created['review']['status'], 'pending')
        status = self.execute('decompose-status')
        self.assertEqual(status['source_sha256'], created['source_sha256'])
        self.assertFalse(status['animation_ready'])
        analyzed = self.execute('decompose-analyze')
        self.assertFalse(analyzed['semantic_model_called'])
        validated = self.execute('decompose-validate')
        self.assertTrue(validated['faithful_fidelity_passed'])
        self.assertEqual(validated['source_pixel_coverage'], 1)
        preview = self.home / 'recomposition'
        result = self.execute('decompose-recompose', '--destination', preview)
        self.assertFalse(result['include_inferred'])
        with Image.open(preview / 'reconstructed.png') as image:
            self.assertEqual(image.tobytes(), self.fixture.expected.tobytes())
        review = self.home / 'review-desk'
        desk = self.execute('decompose-review-ui', '--destination', review)
        self.assertFalse(desk['accepted'])
        self.assertTrue((review / 'review.html').is_file())
        package = self.home / 'package.zip'
        self.execute('decompose-export', '--destination', package)
        restored = self.home / 'restored'
        self.execute('decompose-import', '--source', package, run=restored)
        reloaded = self.execute('decompose-status', run=restored)
        self.assertEqual(status['source_sha256'], reloaded['source_sha256'])
        self.assertEqual(status['components'], reloaded['components'])
        forward = self.home / 'forward'
        self.execute('decompose-prepare', '--destination', forward, '--component', 'near-wing', '--operation', 'wave', run=restored)
        request = json.loads((forward / 'pet_request.json').read_text())
        self.assertFalse(request['decomposition']['imagegen_output'])
        self.assertTrue(request['decomposition']['fixture'])
        self.assertEqual(request['decomposition']['source_sha256'], created['source_sha256'])
        self.assertEqual(request['decomposition']['selected_components'][0]['component_id'], 'near-wing')
        self.execute('base-review', '--note', 'Synthetic CLI fixture checkpoint; not production artwork acceptance.',
                     '--accept-color-warning', run=forward)
        handoff = self.execute('claim', '--job', 'wave', run=forward)
        self.assertTrue(handoff['token'])
        self.assertTrue(handoff['input_images'])
        # Preparing and claiming work has still not generated or imported a state.
        manifest = json.loads((forward / 'imagegen-jobs.json').read_text())
        states = [job for job in manifest['jobs'] if job['id'] != 'base']
        self.assertTrue(states)
        self.assertTrue(all(job['status'] != 'generated' for job in states))

    def test_cli_static_recolor_creates_an_actual_variant_importable_as_a_new_base(self):
        self.create()
        source_before = (self.run / 'decomposition.json').read_bytes()
        variant = self.home / 'recolored'
        result = self.execute('decompose-edit', '--destination', variant, '--component', 'near-wing',
                              '--operation', 'recolor', '--color', '#CC2244')
        self.assertFalse(result['new_artwork_generated'])
        self.assertFalse(result['source_modified'])
        self.assertFalse(result['hidden_geometry_filled'])
        self.assertGreater(result['different_pixels_from_source'], 0)
        self.assertEqual(source_before, (self.run / 'decomposition.json').read_bytes())
        with Image.open(variant / 'edited.png') as image:
            self.assertEqual(image.getchannel('A').tobytes(), self.fixture.expected.getchannel('A').tobytes())
        forward = self.home / 'edited-forward'
        self.execute('prepare', '--fixture-mode', '--profile', ROOT / 'examples/game-npc.json',
                     '--pet-name', 'Edited fixture creature', '--reference', variant / 'edited.png',
                     '--identity', variant / 'identity.json', run=forward)
        imported = self.execute('import-source', '--job', 'base', '--receipt', variant / 'base-source.json',
                     '--note', 'Inspected code-authored recolor fixture; normal visual gate remains required.', run=forward)
        self.assertFalse(imported['imagegen_output'])
        manifest = json.loads((forward / 'imagegen-jobs.json').read_text())
        base = next(job for job in manifest['jobs'] if job['id'] == 'base')
        self.assertEqual(base['source_origin'], 'import')
        self.assertNotIn('generation_receipt', base)

    def test_cli_correction_and_review_revision_restore_use_bound_receipts(self):
        self.create()
        review = self.home / 'review'
        desk = self.execute('decompose-review-ui', '--destination', review)
        receipt = json.loads(Path(desk['receipt_template']).read_text())
        receipt.update(author='CLI synthetic fixture reviewer',
                       note='Exercise the correction and restoration command path, not visual artwork acceptance.')
        wing = next(c for c in receipt['annotation']['components'] if c['id'] == 'near-wing')
        original_name = wing['name']
        wing['name'] = 'Corrected near wing label'
        path = self.home / 'correction.json'
        path.write_text(json.dumps(receipt), encoding='utf-8')
        applied = self.execute('decompose-review', '--receipt', path)
        self.assertIn('near-wing', applied['changed_components'])
        restored = self.execute('decompose-restore', '--review-revision', 1,
            '--author', 'CLI synthetic fixture reviewer', '--note', 'Restore known earlier fixture label.')
        self.assertEqual(restored['restored'], 1)
        current = json.loads((self.run / 'decomposition.json').read_text())
        self.assertEqual(next(c for c in current['components'] if c['id'] == 'near-wing')['name'], original_name)
        self.assertTrue(current['validation']['faithful_fidelity_passed'])

    def test_cli_missing_source_and_bad_selection_leave_no_final_run(self):
        self.execute('decompose', succeeds=False)
        self.assertFalse(self.run.exists())
        failure = self.execute('decompose', '--source', self.fixture.source, '--select', '0,0,10', succeeds=False)
        self.assertIn('4 comma-separated', failure.stdout + failure.stderr)
        self.assertFalse(self.run.exists())

    def test_cli_pending_export_cannot_be_represented_as_approved(self):
        self.create()
        destination = self.home / 'accepted-package'
        failure = self.execute('decompose-export', '--destination', destination, '--require-approved', succeeds=False)
        self.assertIn('approval', failure.stdout + failure.stderr)
        self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
