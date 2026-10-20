"""Adversarial, local-only provenance, recovery, and review-integrity regressions."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from asset_contracts import sha
from character_decomposition import (component_signature, create_decomposition,
    load_decomposition, rebuild_from_annotation, recover_decomposition, save_manifest)
from decomposition_assisted import fail_reconstruction, ingest_reconstruction, request_reconstruction
from decomposition_fixtures import make_fixture
from decomposition_package import RECEIPT, _inventory, export_decomposition
from decomposition_review import apply_review, review_template
from decomposition_spec import check_slug
from extract_strip_frames import atomic_json


class DecompositionIntegrityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='hatch-decomposition-integrity-')
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.fixture = make_fixture(self.home / 'fixture', 'cartoon')
        self.root = self.home / 'run'
        self.data = create_decomposition(self.fixture.source, self.root,
            annotations=self.fixture.annotation, fixture=True)

    def approve(self, root=None):
        root = root or self.root
        value = review_template(root)
        value.update(author='Synthetic adversarial-fixture reviewer',
            note='Fixture-only review attestation tests hash and provenance gates; no model call or production acceptance.')
        value['reviews'] = [{'id': c['id'], 'status': 'approved', 'inspected': True,
            'inferred_acknowledged': True, 'note': 'Known authored test geometry and any inferred fixture pixels inspected.'}
            for c in value['annotation']['components']]
        return apply_review(root, value)

    def assisted(self):
        fixture = make_fixture(self.home / 'overlap', 'overlap')
        root = self.home / 'assisted'
        create_decomposition(fixture.source, root, annotations=fixture.annotation,
                             fixture=True, mode='assisted')
        arm = next(c for c in fixture.components if c['id'] == 'anatomical-left-arm')
        claim = request_reconstruction(root, 'torso', 'Fixture-only hidden reconstruction exercise.',
            hidden_mask=fixture.root / arm['mask'], allow_reconstruction=True)
        source = self.home / 'synthetic-inferred.png'
        Image.new('RGBA', fixture.size, '#8C54A0').save(source)
        receipt = copy.deepcopy(claim['receipt_template'])
        receipt.update(author='Synthetic fixture author', note='Authored synthetic output; no provider called.')
        path = self.home / 'inferred-receipt.json'
        atomic_json(path, receipt)
        ingest_reconstruction(root, 'torso', source, path, allow_reconstruction=True)
        return root, fixture

    def interrupted_change(self, name, phase='prepared', metadata_only=False):
        """Interrupt a real repair after its validated stage and journal exist."""
        root = self.home / name
        export_decomposition(self.root, root)
        original_files = _inventory(root, exclude_receipt=False)
        receipt_bytes = (root / RECEIPT).read_bytes()
        journal = root.parent / ('.' + root.name + '.decomposition-transaction.json')

        def interrupt_promotion(path):
            if journal.exists():
                raise OSError('Synthetic interruption after writing the promotion journal')
            return recover_decomposition(path)

        with patch('character_decomposition.recover_decomposition', side_effect=interrupt_promotion):
            with self.assertRaisesRegex(OSError, 'Synthetic interruption'):
                if metadata_only:
                    manifest = load_decomposition(root)
                    mouth = next(c for c in manifest['components'] if c['id'] == 'mouth')
                    mouth['review'] = {'status': 'rejected',
                        'author': 'Synthetic interrupted-review fixture',
                        'note': 'Fixture verdict exercises atomic review metadata and sidecars.',
                        'signature': component_signature(mouth)}
                    save_manifest(root, manifest)
                else:
                    annotation = json.loads((root / 'annotations/current.json').read_text())
                    next(c for c in annotation['components'] if c['id'] == 'mouth')['name'] = 'Recovered mouth label'
                    rebuild_from_annotation(root, annotation,
                        author='Synthetic interrupted-repair fixture',
                        reason='Repair a single component before interrupting the real promotion.')
        record = json.loads(journal.read_text())
        stage, backup = Path(record['stage']), Path(record['backup'])
        self.assertEqual(_inventory(root, exclude_receipt=False), original_files)
        self.assertEqual(record['old_files'], original_files)
        self.assertEqual(record['new_files'], _inventory(stage, exclude_receipt=False))
        self.assertIn(RECEIPT, record['old_files'])
        self.assertEqual(record['old_files'][RECEIPT], record['new_files'][RECEIPT])
        self.assertNotEqual(record['old_manifest_sha256'], record['new_manifest_sha256'])
        self.assertFalse(backup.exists())
        if phase in ('backed-up', 'promoted'):
            os.replace(root, backup)
        if phase == 'promoted':
            os.replace(stage, root)
        return root, stage, backup, journal, record, receipt_bytes

    def test_orientation_change_requires_fresh_semantic_approval(self):
        self.assertTrue(self.approve()['accepted'])
        original_hash = sha(self.fixture.source)
        annotation = json.loads((self.root / 'annotations/current.json').read_text())
        annotation['orientation'] = 'back'
        result = rebuild_from_annotation(self.root, annotation,
            author='Synthetic orientation-correction test',
            reason='Changing front to back changes the meaning of anatomical left/right.')
        self.assertEqual(result['character']['orientation'], 'back')
        self.assertEqual(result['review']['status'], 'pending')
        self.assertTrue(all(c['review']['status'] == 'pending' for c in result['components']))
        self.assertEqual(sha(self.fixture.source), original_hash)

    def test_normalized_art_cannot_be_relabelled_as_a_different_unchanged_raw_source(self):
        original_bytes = self.fixture.source.read_bytes()
        altered = self.home / 'altered.png'
        with Image.open(self.fixture.source) as image:
            rgba = image.convert('RGBA')
            rgba.putpixel((48, 65), (0, 200, 0, 255))
            rgba.save(altered)
        annotation = json.loads(self.fixture.annotation.read_text())
        annotation['source_sha256'] = sha(altered)
        for component in annotation['components']:
            component['mask']['path'] = str((self.fixture.annotation.parent / component['mask']['path']).resolve())
        other = self.home / 'other-run'
        manifest = create_decomposition(altered, other, annotations=annotation, fixture=True)
        # A transport producer may recompute any manifest hash. Validation must
        # derive observed RGBA from the archived raw source, not trust original.png.
        (other / manifest['source']['path']).write_bytes(original_bytes)
        manifest['source']['sha256'] = sha(self.fixture.source)
        current_annotation = json.loads((other / 'annotations/current.json').read_text())
        current_annotation['source_sha256'] = manifest['source']['sha256']
        atomic_json(other / 'annotations/current.json', current_annotation)
        manifest['annotation']['sha256'] = sha(other / 'annotations/current.json')
        for component in manifest['components']:
            component['provenance']['source_sha256'] = manifest['source']['sha256']
        before_save = _inventory(other, exclude_receipt=False)
        with self.assertRaises(ValueError):
            save_manifest(other, manifest)
            load_decomposition(other)
        self.assertEqual(_inventory(other, exclude_receipt=False), before_save)
        self.assertEqual(self.fixture.source.read_bytes(), original_bytes)

    def test_reconstruction_failure_cannot_follow_an_external_directory_symlink(self):
        external = self.home / 'outside-run'
        external.mkdir()
        jobs = external / 'jobs.json'
        atomic_json(jobs, {'schema_version': 1,
            'limits': {'attempts_per_component': 3, 'concurrency': 1, 'total_claims': 16},
            'jobs': [{'status': 'running', 'token': 'probe', 'component_id': 'torso'}]})
        before = jobs.read_bytes()
        try:
            (self.root / 'reconstruction').symlink_to(external, target_is_directory=True)
        except OSError as exc:
            self.skipTest('Host cannot create the local symlink fixture: ' + str(exc))
        with self.assertRaises(ValueError):
            fail_reconstruction(self.root, 'probe', 'A symlink must never redirect a run mutation.')
        self.assertEqual(jobs.read_bytes(), before)
        self.assertTrue((self.root / 'source').is_dir())

    def test_recovery_never_deletes_an_unverified_sibling_backup(self):
        backup = self.home / '.run-decomposition-backup-unrelated'
        backup.mkdir()
        sentinel = backup / 'user-note.txt'
        sentinel.write_text('Unrelated sibling work must survive an invalid recovery journal.')
        before = sha(self.root / 'decomposition.json')
        atomic_json(self.home / '.run.decomposition-transaction.json', {
            'stage': str(self.home / '.run-decomposition-edit-missing'),
            'backup': str(backup), 'old_manifest_sha256': 'a' * 64,
            'new_manifest_sha256': before})
        with self.assertRaises((ValueError, OSError)):
            recover_decomposition(self.root)
        self.assertTrue(sentinel.is_file())
        self.assertEqual(sha(self.root / 'decomposition.json'), before)

    def test_interrupted_repair_recovers_each_promotion_phase_and_keeps_transport_receipt(self):
        for phase in ('prepared', 'backed-up', 'promoted'):
            with self.subTest(phase=phase):
                root, stage, backup, journal, record, receipt_bytes = self.interrupted_change(
                    'recover-' + phase, phase)
                recover_decomposition(root)
                self.assertEqual(_inventory(root, exclude_receipt=False), record['new_files'])
                self.assertEqual((root / RECEIPT).read_bytes(), receipt_bytes)
                manifest = load_decomposition(root)
                mouth = next(c for c in manifest['components'] if c['id'] == 'mouth')
                self.assertEqual(mouth['name'], 'Recovered mouth label')
                self.assertTrue(manifest['validation']['ok'])
                self.assertEqual((root / manifest['source']['path']).read_bytes(), self.fixture.source.read_bytes())
                self.assertFalse(stage.exists())
                self.assertFalse(backup.exists())
                self.assertFalse(journal.exists())

    def test_interrupted_recovery_refuses_edited_transport_receipts_without_deleting_evidence(self):
        cases = (('prepared', 'root'), ('prepared', 'stage'),
                 ('backed-up', 'backup'), ('promoted', 'root'))
        for phase, target in cases:
            with self.subTest(phase=phase, target=target):
                root, stage, backup, journal, record, receipt_bytes = self.interrupted_change(
                    'receipt-' + phase + '-' + target, phase)
                paths = {'root': root, 'stage': stage, 'backup': backup}
                # The changed file is outside the semantic manifest's hashes;
                # the exact recovery inventory must still detect its alteration.
                (paths[target] / RECEIPT).write_bytes(receipt_bytes + b'\n')
                before = {key: _inventory(path, exclude_receipt=False) if path.exists() else None
                          for key, path in paths.items()}
                journal_bytes = journal.read_bytes()
                with self.assertRaisesRegex(ValueError, 'changed or unrelated files'):
                    recover_decomposition(root)
                self.assertEqual(journal.read_bytes(), journal_bytes)
                for key, path in paths.items():
                    self.assertEqual(_inventory(path, exclude_receipt=False) if path.exists() else None,
                                     before[key])

    def test_interrupted_metadata_save_keeps_original_sidecars_until_recovered(self):
        root, stage, backup, journal, record, receipt_bytes = self.interrupted_change(
            'metadata-recovery', metadata_only=True)
        original = load_decomposition(root)
        self.assertEqual(next(c for c in original['components'] if c['id'] == 'mouth')['review']['status'], 'pending')
        staged = load_decomposition(stage)
        self.assertEqual(next(c for c in staged['components'] if c['id'] == 'mouth')['review']['status'], 'rejected')
        recover_decomposition(root)
        self.assertEqual(_inventory(root, exclude_receipt=False), record['new_files'])
        self.assertEqual((root / RECEIPT).read_bytes(), receipt_bytes)
        self.assertEqual(load_decomposition(root)['review']['status'], 'rejected')
        self.assertFalse(stage.exists())
        self.assertFalse(backup.exists())
        self.assertFalse(journal.exists())

    def test_unrelated_correction_preserves_inferred_component_and_its_approval(self):
        root, fixture = self.assisted()
        self.approve(root)
        old = next(c for c in load_decomposition(root)['components'] if c['id'] == 'torso')
        annotation = json.loads((root / 'annotations/current.json').read_text())
        next(c for c in annotation['components'] if c['id'] == 'mouth')['name'] = 'Corrected mouth label'
        result = rebuild_from_annotation(root, annotation, author='Fixture-only repair',
            reason='Only the mouth label changes; inferred torso and its observed anchor are unchanged.')
        current = next(c for c in result['components'] if c['id'] == 'torso')
        self.assertEqual(current, old)
        self.assertEqual(current['review']['status'], 'approved')
        self.assertEqual(sha(root / current['asset']['path']), old['asset']['sha256'])

    def test_core_cannot_accept_approved_component_with_pending_hidden_artwork(self):
        root, fixture = self.assisted()
        self.approve(root)
        manifest = load_decomposition(root)
        torso = next(c for c in manifest['components'] if c['id'] == 'torso')
        torso['provenance']['reconstruction']['status'] = 'pending-review'
        torso['review'] = {'status': 'approved', 'author': 'Fixture-only observed reviewer',
            'note': 'This review does not accept the hidden alternate.', 'signature': component_signature(torso)}
        try:
            save_manifest(root, manifest)
        except ValueError:
            return
        # Keeping the observed verdict is safe only if the entire decomposition
        # explicitly remains pending while its hidden alternate needs review.
        self.assertNotEqual(load_decomposition(root)['review']['status'], 'approved')

    def test_mask_run_budget_applies_across_components_before_large_allocation(self):
        source = self.home / 'bounded-fixture.png'
        image = Image.new('RGBA', (20, 10))
        draw = ImageDraw.Draw(image)
        components = []
        for index, x in enumerate((1, 7, 13)):
            draw.rectangle((x, 2, x + 3, 5), fill=(50 + index * 70, 100, 150, 255))
            components.append({'id': 'piece-' + str(index), 'name': 'Authored piece ' + str(index),
                'category': 'fixture-piece', 'mask': {'runs': [[y, x, x + 4] for y in range(2, 6)]}})
        image.save(source)
        annotation = {'schema_version': 1, 'source_sha256': sha(source),
            'author': 'Synthetic resource-bound test', 'note': 'Each mask is small; their aggregate must be bounded.',
            'components': components}
        destination = self.home / 'over-budget'
        with patch('character_decomposition.MAX_TOTAL_RUNS', 8):
            with self.assertRaisesRegex(ValueError, 'mask-run resource bound'):
                create_decomposition(source, destination, annotations=annotation, fixture=True)
        self.assertFalse(destination.exists())
        self.assertTrue(source.is_file())

    def test_component_identifiers_reject_trailing_control_characters(self):
        for identifier in ('torso\n', 'torso\r', 'torso\t', 'aux', 'con'):
            with self.subTest(identifier=repr(identifier)), self.assertRaises(ValueError):
                check_slug(identifier)


if __name__ == '__main__':
    unittest.main()
