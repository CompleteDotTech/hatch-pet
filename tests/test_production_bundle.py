"""Bundled transport preserves strict archive and review semantics; fixtures only."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import production_bundle as bundle
import production_workflow as workflow
import portable_runs
from production_fixture import build_fixture_project


class ProductionBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='hatch-bundle-test-')
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.project = self.home / 'original'
        build_fixture_project(self.project)
        self.target = {'kind': 'character', 'character_id': 'a', 'version': '1.0.0'}
        receipt = workflow.review_template(self.project, self.target)
        receipt['reviewer'] = {'kind': 'synthetic', 'id': 'bundle-regression', 'name': 'Synthetic archive gate only'}
        for dimension in receipt['dimensions'].values():
            dimension.update(verdict='pass', notes='Synthetic exact-byte transport regression; no art acceptance.',
                evidence=[{'path': 'art/a-body.png', 'sha256': workflow.file_hash(self.project / 'art/a-body.png'),
                           'method': 'automated_check', 'note': 'Fixture bytes only.'}])
        workflow.record_review(self.project, receipt)
        self.archive = self.home / 'complete.zip'
        workflow.archive_project(self.project, self.archive)
        self.parts = self.home / 'parts'
        bundle.create_bundle(self.archive, self.parts, part_size=1024)
        self.index = self.parts / bundle.BUNDLE_INDEX

    def read_index(self):
        return json.loads(self.index.read_text('utf-8'))

    def write_index(self, value):
        self.index.write_text(json.dumps(value), encoding='utf-8')

    def wrap_archive(self, archive):
        content = archive.read_bytes()
        part = self.parts / 'crafted.part'
        part.write_bytes(content)
        value = self.read_index()
        digest = hashlib.sha256(content).hexdigest()
        value['archive'] = {'format': 'zip', 'bytes': len(content), 'sha256': digest}
        value['parts'] = [{'path': part.name, 'bytes': len(content), 'sha256': digest}]
        self.write_index(value)

    def test_complete_roundtrip_preserves_identity_review_history_and_dependency_hashes(self):
        verified = bundle.verify_bundle(self.index)
        self.assertTrue(verified['verified'])
        self.assertGreater(verified['part_count'], 1)
        self.assertEqual(verified['archive_sha256'], workflow.file_hash(self.archive))
        destination = self.home / 'elsewhere' / 'restored'
        result = bundle.restore_bundle(self.index, destination)
        self.assertEqual(result['project_id'], 'fixture-project')
        self.assertEqual(workflow.dependency_snapshot(destination), workflow.dependency_snapshot(self.project))
        self.assertTrue(workflow.review_status(destination, self.target)['current_pass'])
        self.assertFalse(workflow.review_status(destination, self.target)['production_art_acceptance'])
        self.assertFalse(result['external_integration_verified'])
        self.assertEqual(result['verified_part_count'], verified['part_count'])

    def test_missing_or_tampered_parts_never_create_a_restore_destination(self):
        part = self.parts / self.read_index()['parts'][0]['path']
        original = part.read_bytes()
        for mutation, message in [('missing', 'missing bundle part'), ('tampered', 'part hash differs')]:
            with self.subTest(mutation=mutation):
                if mutation == 'missing':
                    part.unlink()
                else:
                    part.write_bytes(bytes([original[0] ^ 1]) + original[1:])
                destination = self.home / mutation
                with self.assertRaisesRegex(ValueError, message):
                    bundle.restore_bundle(self.index, destination)
                self.assertFalse(destination.exists())
                part.write_bytes(original)

    def test_reordered_parts_and_false_identity_cannot_bypass_whole_archive_checks(self):
        original = self.read_index()
        for mutation, message in [('order', 'assembled archive'), ('identity', 'identity or fixture label')]:
            value = copy.deepcopy(original)
            if mutation == 'order':
                value['parts'][0], value['parts'][1] = value['parts'][1], value['parts'][0]
            else:
                value['project_id'] = 'another-project'
            self.write_index(value)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, message):
                bundle.restore_bundle(self.index, self.home / mutation)
            self.assertFalse((self.home / mutation).exists())

    def test_unsafe_duplicate_symlink_and_oversized_parts_are_rejected(self):
        original = self.read_index()
        for mutation in ('traversal', 'duplicate', 'noncanonical', 'oversize'):
            value = copy.deepcopy(original)
            if mutation == 'traversal':
                value['parts'][0]['path'] = '../outside'
            elif mutation == 'duplicate':
                value['parts'][1]['path'] = value['parts'][0]['path']
            elif mutation == 'noncanonical':
                value['parts'][0]['path'] = './' + value['parts'][0]['path']
            else:
                value['parts'][0]['bytes'] = bundle.MAX_PART_BYTES + 1
            self.write_index(value)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                bundle.verify_bundle(self.index)
        self.write_index(original)
        part = self.parts / original['parts'][0]['path']
        outside = self.home / 'outside'
        part.rename(outside)
        part.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'outside|symlink'):
            bundle.verify_bundle(self.index)

    def test_bounded_transport_still_rejects_an_unsafe_inner_archive(self):
        archive = self.home / 'unsafe.zip'
        content = b'unsafe fixture content'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('../escape', content)
            output.writestr('archive-receipt.json', json.dumps({'schema_version': 2,
                'kind': 'hatch-production-project', 'project_schema': 1, 'project_id': 'fixture-project',
                'fixture': True, 'files': {'../escape': hashlib.sha256(content).hexdigest()}}))
        self.wrap_archive(archive)
        with self.assertRaisesRegex(ValueError, 'unsafe archive member'):
            bundle.restore_bundle(self.index, self.home / 'unsafe-restored')
        self.assertFalse((self.home / 'unsafe-restored').exists())
        self.assertFalse((self.home / 'escape').exists())

    def test_duplicate_json_keys_are_rejected_at_every_index_depth(self):
        original = self.index.read_text('utf-8')
        for needle in ('"schema_version": 1', '"format": "zip"'):
            value = original.replace(needle, needle + ', ' + needle, 1)
            self.index.write_text(value, encoding='utf-8')
            with self.subTest(needle=needle), self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
                bundle.restore_bundle(self.index, self.home / 'duplicate-json')
            self.assertFalse((self.home / 'duplicate-json').exists())

    def test_shared_legacy_archive_guard_rejects_noncanonical_names_and_duplicate_receipt_keys(self):
        for index, name in enumerate(('./payload.txt', 'a//payload.txt', 'a/./payload.txt', 'payload.txt/')):
            archive = self.home / f'alias-{index}.zip'
            content = b'canonical identity must not depend on extraction aliases'
            receipt = {'schema_version': 2, 'kind': 'hatch-production-project', 'project_schema': 1,
                       'workflow_schema': 2, 'project_id': 'fixture-project', 'fixture': True,
                       'files': {name: hashlib.sha256(content).hexdigest()}}
            with zipfile.ZipFile(archive, 'w') as output:
                output.writestr(name, content)
                output.writestr('archive-receipt.json', json.dumps(receipt))
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, 'unsafe archive member'):
                    portable_runs.verify_archive(archive)
                self.wrap_archive(archive)
                with self.assertRaisesRegex(ValueError, 'unsafe archive member'):
                    bundle.verify_bundle(self.index)
        archive = self.home / 'duplicate-receipt.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('payload.txt', b'x')
            output.writestr('archive-receipt.json', '{"schema_version":2,"schema_version":2,"files":{"payload.txt":"' +
                            hashlib.sha256(b'x').hexdigest() + '"}}')
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            portable_runs.verify_archive(archive)

    def test_existing_destinations_and_transport_limits_preserve_existing_files(self):
        destination = self.home / 'already-present'
        destination.mkdir()
        marker = destination / 'keep.txt'
        marker.write_text('Keep original bytes.', encoding='utf-8')
        for operation in (lambda: bundle.restore_bundle(self.index, destination),
                          lambda: bundle.create_bundle(self.archive, destination)):
            with self.assertRaisesRegex(ValueError, 'must not exist'):
                operation()
            self.assertEqual(marker.read_text('utf-8'), 'Keep original bytes.')
        with patch.object(bundle, 'MAX_BUNDLE_BYTES', 4), self.assertRaisesRegex(ValueError, 'transport bound'):
            bundle.verify_bundle(self.index)
        with patch.object(bundle, 'MAX_BUNDLE_PARTS', 1), self.assertRaisesRegex(ValueError, 'parts'):
            bundle.verify_bundle(self.index)

    def test_cli_verifies_bundle_and_rejects_invalid_inputs(self):
        script = Path(__file__).resolve().parents[1] / 'scripts' / 'production_bundle.py'
        result = subprocess.run([sys.executable, str(script), 'verify', '--bundle', str(self.index)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['verified'])
        invalid = subprocess.run([sys.executable, str(script), 'restore', '--bundle', str(self.index)],
                                 capture_output=True, text=True)
        self.assertEqual(invalid.returncode, 2)


if __name__ == '__main__':
    unittest.main()
