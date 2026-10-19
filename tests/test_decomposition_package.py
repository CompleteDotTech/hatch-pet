"""Decomposition transport safety and exact round trips; fixtures are synthetic."""
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from asset_contracts import hash_object, sha
from decomposition_package import RECEIPT, _inventory, export_decomposition, import_decomposition, verify_package
from decomposition_fixtures import make_fixture, FIXTURE_ORIGIN
from character_decomposition import create_decomposition, load_decomposition, save_manifest, component_signature


def approved_fixture(root, name='creature'):
    fixture = make_fixture(root / 'art', name)
    run = root / 'decomposition'
    manifest = create_decomposition(fixture.source, run, annotations=fixture.annotation,
                                    origin=FIXTURE_ORIGIN, fixture=True, pixel_art=name == 'pixel')
    for component in manifest['components']:
        component['review'] = {'status': 'approved', 'author': 'Synthetic gate test',
                               'note': 'Authored fixture review tests binding only; no general semantic acceptance claim.',
                               'signature': component_signature(component)}
    save_manifest(run, manifest)
    return fixture, run, manifest


class DecompositionRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hatch-decomposition-roundtrip-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def test_directory_and_zip_preserve_approved_metadata_placements_and_source_bytes(self):
        fixture, run, manifest = approved_fixture(self.home)
        expected_manifest = (run / 'decomposition.json').read_bytes()
        for suffix in ('', '.zip'):
            with self.subTest(suffix=suffix):
                package = self.home / ('portable' + suffix)
                result = export_decomposition(run, package, require_approved=True)
                self.assertTrue(result['accepted'])
                self.assertTrue(result['fixture'])
                restored = self.home / ('restored-zip' if suffix else 'restored-directory')
                result = import_decomposition(package, restored)
                loaded = load_decomposition(restored)
                self.assertTrue(result['accepted'])
                self.assertEqual((restored / 'decomposition.json').read_bytes(), expected_manifest)
                self.assertEqual(loaded['components'], manifest['components'])
                self.assertEqual((restored / loaded['source']['path']).read_bytes(), fixture.source.read_bytes())
                self.assertEqual((restored / 'identity.json').read_bytes(), (run / 'identity.json').read_bytes())
                self.assertEqual(len(list((restored / 'review/imports').glob('package-*.json'))), 1)
                self.assertFalse((restored / RECEIPT).exists())

    def test_repeated_zip_exports_are_byte_identical(self):
        _, run, _ = approved_fixture(self.home, 'pixel')
        export_decomposition(run, self.home / 'one.zip')
        export_decomposition(run, self.home / 'two.zip')
        self.assertEqual(sha(self.home / 'one.zip'), sha(self.home / 'two.zip'))

    def test_pending_evaluation_exports_do_not_pass_approved_gate(self):
        fixture = make_fixture(self.home / 'art', 'cartoon')
        run = self.home / 'decomposition'
        create_decomposition(fixture.source, run, annotations=fixture.annotation, origin=FIXTURE_ORIGIN, fixture=True)
        result = export_decomposition(run, self.home / 'evaluation')
        self.assertFalse(result['accepted'])
        self.assertEqual(result['semantic_status'], 'pending')
        with self.assertRaisesRegex(ValueError, 'approval'):
            export_decomposition(run, self.home / 'unwritten', require_approved=True)
        self.assertFalse((self.home / 'unwritten').exists())

    def test_transport_receipt_cannot_promote_fixture_or_review_labels(self):
        _, run, _ = approved_fixture(self.home, 'pixel')
        package = self.home / 'portable'
        export_decomposition(run, package)
        receipt = json.loads((package / RECEIPT).read_text())
        receipt['fixture'] = False
        (package / RECEIPT).write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, 'labels disagree'):
            import_decomposition(package, self.home / 'unwritten')
        self.assertFalse((self.home / 'unwritten').exists())

    def test_corrupt_source_assets_or_stale_reviews_cannot_export(self):
        _, run, manifest = approved_fixture(self.home, 'pixel')
        component = manifest['components'][0]
        component['name'] = 'Changed without review'
        (run / 'decomposition.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'stale component review'):
            export_decomposition(run, self.home / 'unwritten')
        self.assertFalse((self.home / 'unwritten').exists())


class DecompositionTransportSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hatch-decomposition-package-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def package(self):
        source = self.home / 'package'
        source.mkdir()
        for name in ('decomposition.json', 'identity.json', 'validation.json', 'provenance.json'):
            (source / name).write_text('{}\n', encoding='utf-8')
        files = _inventory(source)
        receipt = {'schema_version': 1, 'kind': 'character-decomposition-package', 'files': files,
                   'inventory_sha256': hash_object(files), 'decomposition_sha256': files['decomposition.json'],
                   'identity_sha256': files['identity.json'], 'source_sha256': 'a' * 64,
                   'fixture': True, 'accepted': False, 'semantic_status': 'pending',
                   'versions': {}, 'codex_pet_package': False}
        (source / RECEIPT).write_text(json.dumps(receipt), encoding='utf-8')
        return source, receipt

    def zip(self, source, extra=None):
        target = self.home / 'package.zip'
        with zipfile.ZipFile(target, 'w') as archive:
            for path in source.iterdir():
                archive.write(path, path.name)
            if extra:
                archive.writestr(*extra)
        return target

    def test_directory_and_zip_transport_hashes_agree(self):
        source, receipt = self.package()
        self.assertEqual(verify_package(source), receipt)
        self.assertEqual(verify_package(self.zip(source)), receipt)

    def test_changed_directory_or_unlisted_file_fails(self):
        source, _ = self.package()
        (source / 'identity.json').write_text('{"tampered":true}')
        with self.assertRaisesRegex(ValueError, 'hashes changed'):
            verify_package(source)
        (source / 'identity.json').write_text('{}\n')
        (source / 'not-in-inventory.txt').write_text('unexpected')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            verify_package(source)

    def test_changed_zip_payload_fails(self):
        source, _ = self.package()
        (source / 'identity.json').write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            verify_package(self.zip(source))

    def test_traversal_aliases_backslashes_and_ads_are_rejected_before_writes(self):
        for name in ('../outside.txt', '/outside.txt', 'a/../outside.txt', 'a//b.txt', './outside.txt', 'a\\b.txt', 'a:b.txt',
                     'CON.txt', 'nested/nul.png', 'trailing.', 'trailing ', 'bad?.txt', 'bad\nname.txt'):
            with self.subTest(name=name):
                source, _ = self.package()
                archive = self.zip(source, (name, 'unsafe'))
                with self.assertRaisesRegex(ValueError, 'unsafe'):
                    import_decomposition(archive, self.home / 'unwritten')
                self.assertFalse((self.home / 'unwritten').exists())
                archive.unlink()
                for path in source.iterdir():
                    path.unlink()
                source.rmdir()

    def test_symlink_archive_member_is_rejected(self):
        source, _ = self.package()
        info = zipfile.ZipInfo('link')
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            verify_package(self.zip(source, (info, '../outside')))

    def test_symlink_directory_member_is_rejected(self):
        source, _ = self.package()
        external = self.home / 'external.txt'
        external.write_text('must remain external')
        try:
            (source / 'link.txt').symlink_to(external)
        except OSError as exc:
            self.skipTest('symlinks unavailable: ' + str(exc))
        with self.assertRaisesRegex(ValueError, 'symbolic links'):
            verify_package(source)

    def test_unexpected_archive_entry_fails(self):
        source, _ = self.package()
        with self.assertRaisesRegex(ValueError, 'members differ'):
            verify_package(self.zip(source, ('extra.txt', 'unexpected')))

    def test_case_colliding_archive_members_fail(self):
        source, _ = self.package()
        with self.assertRaisesRegex(ValueError, 'duplicate paths'):
            verify_package(self.zip(source, ('IDENTITY.json', '{}')))

    def test_receipt_cannot_claim_codex_pet_format_or_untyped_approval(self):
        for field, invalid in (('codex_pet_package', True), ('accepted', 'yes'), ('fixture', 1), ('schema_version', True)):
            with self.subTest(field=field):
                source, receipt = self.package()
                receipt[field] = invalid
                (source / RECEIPT).write_text(json.dumps(receipt))
                with self.assertRaises(ValueError):
                    verify_package(source)
                for path in source.iterdir():
                    path.unlink()
                source.rmdir()

    def test_malformed_archive_is_clear_failure(self):
        source = self.home / 'bad.zip'
        source.write_text('This is not a ZIP archive.')
        with self.assertRaisesRegex(ValueError, 'invalid decomposition package'):
            verify_package(source)

    def test_duplicate_receipt_json_keys_fail(self):
        source, _ = self.package()
        receipt = (source / RECEIPT).read_text()
        (source / RECEIPT).write_text(receipt[:-1] + ', "accepted": true}')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            verify_package(source)


if __name__ == '__main__':
    unittest.main()
