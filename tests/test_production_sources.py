"""Exact small-part transport tests; all input bytes and provenance are synthetic."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import production_sources as sources


class ProductionSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='hatch-source-test-')
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.original = self.home / 'original'
        for relative in ('originals', 'references', 'provenance'):
            (self.original / relative).mkdir(parents=True, exist_ok=True)
        content = random.Random(73).randbytes(sources.MAX_PART_BYTES * 2 + 37)
        (self.original / 'originals/source.bin').write_bytes(content)
        (self.original / 'references/canonical.bin').write_bytes(content)
        receipt = {'kind': 'fixture', 'fixture': True, 'source_sha256': hashlib.sha256(content).hexdigest(),
                   'note': 'Synthetic source bytes and provenance; no production artwork or provider call.'}
        self.provenance_bytes = (json.dumps(receipt, separators=(',', ':')) + '\n').encode()
        (self.original / 'provenance/receipt.json').write_bytes(self.provenance_bytes)
        self.paths = ['originals/source.bin', 'references/canonical.bin', 'provenance/receipt.json']
        self.parts = self.home / 'parts'
        self.created = sources.create_source_bundle(self.original, self.paths, self.parts,
            fixture=True, origin='Synthetic transport regression only.',
            provenance_paths=['provenance/receipt.json'])
        self.index = self.parts / sources.SOURCE_INDEX

    def read(self):
        return json.loads(self.index.read_text('utf-8'))

    def write(self, value):
        self.index.write_text(json.dumps(value), encoding='utf-8')

    def assert_no_destination(self, name='restored'):
        self.assertFalse((self.home / name).exists())
        self.assertFalse(list(self.home.glob('.hatch-source-restore-*')))

    def test_roundtrip_preserves_exact_original_paths_bytes_hashes_and_provenance(self):
        verified = sources.verify_source_bundle(self.index)
        self.assertTrue(verified['verified'])
        self.assertEqual(verified['file_count'], 3)
        self.assertFalse(verified['provider_called'])
        self.assertFalse(verified['production_art_acceptance'])
        destination = self.home / 'restored'
        result = sources.restore_source_bundle(self.parts, destination)
        self.assertEqual(result['provenance_paths'], ['provenance/receipt.json'])
        self.assertEqual(sorted(path.relative_to(destination).as_posix() for path in destination.rglob('*') if path.is_file()), sorted(self.paths))
        for relative in self.paths:
            self.assertEqual((destination / relative).read_bytes(), (self.original / relative).read_bytes())
        self.assertEqual((destination / 'provenance/receipt.json').read_bytes(), self.provenance_bytes)

    def test_identical_files_share_bounded_content_addressed_parts(self):
        index = self.read()
        by_path = {file['path']: file for file in index['files']}
        self.assertEqual(by_path['originals/source.bin']['parts'], by_path['references/canonical.bin']['parts'])
        self.assertEqual(len(index['parts']), 4)
        self.assertLess(index['unique_part_bytes'], index['total_bytes'])
        for part in index['parts']:
            self.assertLessEqual(part['bytes'], 65535)
            self.assertEqual(part['path'], 'parts/' + part['sha256'] + '.bin')
            self.assertEqual(hashlib.sha256((self.parts / part['path']).read_bytes()).hexdigest(), part['sha256'])

    def test_missing_tampered_and_extra_parts_are_rejected_without_promotion(self):
        first = self.parts / self.read()['parts'][0]['path']
        original = first.read_bytes()
        first.unlink()
        with self.assertRaisesRegex(ValueError, 'missing or extra'):
            sources.restore_source_bundle(self.index, self.home / 'restored')
        self.assert_no_destination()
        first.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            sources.restore_source_bundle(self.index, self.home / 'restored')
        self.assert_no_destination()
        first.write_bytes(original)
        (self.parts / 'extra.bin').write_bytes(b'Unlisted bytes')
        with self.assertRaisesRegex(ValueError, 'missing or extra'):
            sources.verify_source_bundle(self.index)

    def test_order_and_full_original_hash_remain_authoritative_after_part_verification(self):
        original = self.read()
        value = copy.deepcopy(original)
        file = next(file for file in value['files'] if file['path'] == 'originals/source.bin')
        file['parts'][0], file['parts'][1] = file['parts'][1], file['parts'][0]
        self.write(value)
        with self.assertRaisesRegex(ValueError, 'assembled source file hash'):
            sources.restore_source_bundle(self.index, self.home / 'restored')
        self.assert_no_destination()
        value = copy.deepcopy(original)
        value['files'][0]['sha256'] = '0' * 64
        self.write(value)
        with self.assertRaisesRegex(ValueError, 'assembled source file hash'):
            sources.verify_source_bundle(self.index)

    def test_duplicate_json_keys_and_duplicate_inventory_members_are_rejected(self):
        raw = self.index.read_text('utf-8')
        for needle in ('"fixture": true', '"kind": "hatch-production-sources"'):
            self.index.write_text(raw.replace(needle, needle + ', ' + needle, 1), encoding='utf-8')
            with self.subTest(needle=needle), self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
                sources.restore_source_bundle(self.index, self.home / 'restored')
            self.assert_no_destination()
        self.index.write_text(raw.replace('"sha256": "', '"sha256": "' + '0' * 64 + '", "sha256": "', 1), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            sources.verify_source_bundle(self.index)
        original = json.loads(raw)
        for key in ('parts', 'files'):
            value = copy.deepcopy(original)
            value[key].append(copy.deepcopy(value[key][0]))
            self.write(value)
            with self.subTest(key=key), self.assertRaises(ValueError):
                sources.verify_source_bundle(self.index)

    def test_traversal_aliases_symlinks_and_source_path_conflicts_are_rejected(self):
        original = self.read()
        for path in ('../escape', '/absolute', './originals/source.bin', 'originals//source.bin', 'C:escape'):
            value = copy.deepcopy(original)
            value['files'][0]['path'] = path
            self.write(value)
            with self.subTest(path=path), self.assertRaises(ValueError):
                sources.restore_source_bundle(self.index, self.home / 'restored')
            self.assert_no_destination()
        self.write(original)
        part = self.parts / original['parts'][0]['path']
        outside = self.home / 'outside.bin'
        part.rename(outside)
        part.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'outside|symlink'):
            sources.verify_source_bundle(self.index)
        part.unlink()
        outside.rename(part)
        value = copy.deepcopy(original)
        value['files'][0]['path'] = 'parent'
        value['files'][1]['path'] = 'parent/child'
        self.write(value)
        with self.assertRaisesRegex(ValueError, 'parent file'):
            sources.verify_source_bundle(self.index)

    def test_resource_limits_apply_to_parts_original_files_references_and_total_bytes(self):
        original = self.read()
        for name, mutate in [
            ('part', lambda value: value['parts'][0].update(bytes=sources.MAX_PART_BYTES + 1)),
            ('file', lambda value: value['files'][0].update(bytes=sources.MAX_FILE_BYTES + 1)),
            ('total', lambda value: value.update(total_bytes=sources.MAX_TOTAL_BYTES + 1)),
            ('bool', lambda value: value.update(unique_part_bytes=True))]:
            value = copy.deepcopy(original)
            mutate(value)
            self.write(value)
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'resource bound'):
                sources.verify_source_bundle(self.index)
        self.write(original)
        with patch.object(sources, 'MAX_PARTS', 1), self.assertRaisesRegex(ValueError, 'part bound|part inventory'):
            sources.verify_source_bundle(self.index)
        with patch.object(sources, 'MAX_PART_REFERENCES', 1), self.assertRaisesRegex(ValueError, 'part-reference'):
            sources.verify_source_bundle(self.index)
        with self.assertRaisesRegex(ValueError, 'part_size'):
            sources.create_source_bundle(self.original, self.paths, self.home / 'too-large',
                                         fixture=True, origin='Synthetic', part_size=65536)

    def test_interrupted_staging_preserves_atomic_destination_and_can_retry(self):
        original_copy = sources._copy_and_verify
        def interrupt(index_root, index, parts, destination=None):
            (destination / 'partial.bin').write_bytes(b'Incomplete private staging')
            raise KeyboardInterrupt('Synthetic interruption')
        with patch.object(sources, '_copy_and_verify', side_effect=interrupt), self.assertRaises(KeyboardInterrupt):
            sources.restore_source_bundle(self.index, self.home / 'restored')
        self.assert_no_destination()
        result = sources.restore_source_bundle(self.index, self.home / 'restored')
        self.assertTrue(result['verified'])
        self.assertEqual(sources._copy_and_verify, original_copy)

    def test_existing_destinations_dangling_links_and_unlisted_provenance_are_preserved(self):
        destination = self.home / 'occupied'
        destination.mkdir()
        marker = destination / 'keep.txt'
        marker.write_text('Do not replace', encoding='utf-8')
        for operation in (lambda: sources.restore_source_bundle(self.index, destination),
                          lambda: sources.create_source_bundle(self.original, self.paths, destination,
                                                               fixture=True, origin='Synthetic')):
            with self.assertRaisesRegex(ValueError, 'must not exist'):
                operation()
            self.assertEqual(marker.read_text('utf-8'), 'Do not replace')
        dangling = self.home / 'dangling'
        dangling.symlink_to(self.home / 'missing')
        with self.assertRaisesRegex(ValueError, 'must not exist'):
            sources.restore_source_bundle(self.index, dangling)
        with self.assertRaisesRegex(ValueError, 'subset'):
            sources.create_source_bundle(self.original, self.paths, self.home / 'bad-provenance',
                fixture=True, origin='Synthetic', provenance_paths=['not-in-inventory.json'])

    def test_source_changes_during_creation_cannot_publish_a_mixed_snapshot(self):
        original_hash = sources._hash_bounded
        def change_source(path, size):
            digest = original_hash(path, size)
            original = path.read_bytes()
            path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
            return digest
        destination = self.home / 'changed-source'
        with patch.object(sources, '_hash_bounded', side_effect=change_source), self.assertRaisesRegex(ValueError, 'source changed'):
            sources.create_source_bundle(self.original, ['originals/source.bin'], destination,
                                         fixture=True, origin='Synthetic source mutation gate.')
        self.assertFalse(destination.exists())
        self.assertFalse(list(self.home.glob('.hatch-source-parts-*')))

    def test_empty_selected_file_is_preserved_without_invented_parts(self):
        empty = self.original / 'empty.txt'
        empty.write_bytes(b'')
        destination = self.home / 'empty-parts'
        result = sources.create_source_bundle(self.original, ['empty.txt'], destination,
                                              fixture=True, origin='Synthetic empty-file gate.')
        self.assertEqual(result['unique_part_count'], 0)
        restored = self.home / 'empty-restored'
        sources.restore_source_bundle(destination, restored)
        self.assertEqual((restored / 'empty.txt').read_bytes(), b'')

    def test_cli_verification_restore_and_required_origin_label(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/production_sources.py'
        verified = subprocess.run([sys.executable, str(script), 'verify', '--bundle', str(self.index)],
                                  capture_output=True, text=True)
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertTrue(json.loads(verified.stdout)['verified'])
        destination = self.home / 'cli-restored'
        restored = subprocess.run([sys.executable, str(script), 'restore', '--bundle', str(self.index),
                                   '--destination', str(destination)], capture_output=True, text=True)
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual((destination / 'provenance/receipt.json').read_bytes(), self.provenance_bytes)
        invalid = subprocess.run([sys.executable, str(script), 'create', '--root', str(self.original),
                                  '--file', self.paths[0], '--destination', str(self.home / 'missing-label'),
                                  '--origin', 'Synthetic'], capture_output=True, text=True)
        self.assertEqual(invalid.returncode, 2)


if __name__ == '__main__':
    unittest.main()
