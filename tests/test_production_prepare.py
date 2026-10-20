"""Input preservation at the production artwork acquisition boundary."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import hatch
import prepare_production_art as acquisition


def snapshot(root):
    result = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[relative] = ('symlink', str(path.readlink()))
        elif path.is_file():
            result[relative] = ('file', hashlib.sha256(path.read_bytes()).hexdigest())
        elif path.is_dir():
            result[relative] = ('directory',)
    return result


class ProductionPrepareTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def assert_rejected_without_changes(self, destination):
        before = snapshot(self.root)
        with patch.object(hatch, 'prepare') as prepare:
            with self.assertRaisesRegex(ValueError, 'already exists'):
                acquisition.prepare(destination, 'milo')
            prepare.assert_not_called()
        self.assertEqual(before, snapshot(self.root))

    def test_existing_run_preserves_custom_profile_identity_and_history(self):
        destination = self.root / 'milo'
        destination.mkdir()
        (destination / 'keep-original.txt').write_bytes(b'preserved run history\n')
        (self.root / 'milo-profile.json').write_bytes(b'{"custom_profile": true}\n')
        (self.root / 'milo-identity.json').write_bytes(b'{"custom_identity": true}\n')
        self.assert_rejected_without_changes(destination)

    def test_existing_empty_directory_and_file_destinations_are_rejected(self):
        empty = self.root / 'empty'
        empty.mkdir()
        self.assert_rejected_without_changes(empty)
        regular = self.root / 'regular'
        regular.write_bytes(b'prior file\n')
        self.assert_rejected_without_changes(regular)

    def test_existing_and_dangling_destination_symlinks_are_not_followed(self):
        existing = self.root / 'existing'
        existing.mkdir()
        (existing / 'prior.txt').write_bytes(b'prior target\n')
        for name, target in [('linked', existing), ('dangling', self.root / 'absent')]:
            with self.subTest(name=name):
                destination = self.root / name
                destination.symlink_to(target, target_is_directory=True)
                self.assert_rejected_without_changes(destination)

    def test_each_sibling_file_or_directory_collision_preserves_all_inputs(self):
        for kind in ('file', 'directory'):
            for sibling in ('milo-profile.json', 'milo-identity.json'):
                with self.subTest(kind=kind, sibling=sibling):
                    parent = self.root / (kind + '-' + sibling)
                    parent.mkdir()
                    path = parent / sibling
                    if kind == 'directory':
                        path.mkdir()
                        (path / 'prior.txt').write_bytes(b'prior directory content\n')
                    else:
                        path.write_bytes(b'prior input\n')
                    self.assert_rejected_without_changes(parent / 'milo')

    def test_each_sibling_symlink_collision_preserves_link_and_target(self):
        for dangling in (False, True):
            for sibling in ('milo-profile.json', 'milo-identity.json'):
                with self.subTest(dangling=dangling, sibling=sibling):
                    parent = self.root / (str(dangling) + '-' + sibling)
                    parent.mkdir()
                    target = parent / 'target.json'
                    if not dangling:
                        target.write_bytes(b'prior linked input\n')
                    (parent / sibling).symlink_to(target)
                    self.assert_rejected_without_changes(parent / 'milo')

    def test_existing_recovery_journal_is_preserved(self):
        (self.root / '.milo.prepare.json').write_bytes(b'{"prior_transaction": true}\n')
        self.assert_rejected_without_changes(self.root / 'milo')

    def test_destination_cannot_alias_a_sibling_input(self):
        before = snapshot(self.root)
        with patch.object(hatch, 'prepare') as prepare:
            with self.assertRaisesRegex(ValueError, 'must be distinct'):
                acquisition.prepare(self.root / 'milo-profile.json', 'milo')
            prepare.assert_not_called()
        self.assertEqual(before, snapshot(self.root))

    def test_input_created_after_preflight_is_not_overwritten(self):
        identity = (self.root / 'milo-identity.json').resolve()
        original_open = Path.open

        def concurrent_open(path, mode='r', *args, **kwargs):
            if path == identity and mode == 'x':
                with original_open(path, 'wb') as output:
                    output.write(b'concurrent input\n')
            return original_open(path, mode, *args, **kwargs)

        with patch.object(Path, 'open', new=concurrent_open), patch.object(hatch, 'prepare') as prepare:
            with self.assertRaises(FileExistsError):
                acquisition.prepare(self.root / 'milo', 'milo')
            prepare.assert_not_called()
        self.assertEqual(b'concurrent input\n', identity.read_bytes())
        self.assertFalse((self.root / 'milo-profile.json').exists())
        self.assertFalse((self.root / 'milo').exists())

    def test_local_prepare_failure_rolls_back_only_new_sibling_inputs(self):
        marker = self.root / 'unrelated.txt'
        marker.write_bytes(b'prior unrelated file\n')
        before = snapshot(self.root)
        with patch.object(hatch, 'prepare', side_effect=ValueError('local preparation failed')):
            with self.assertRaisesRegex(ValueError, 'local preparation failed'):
                acquisition.prepare(self.root / 'milo', 'milo')
        self.assertEqual(before, snapshot(self.root))

    def test_failure_cleanup_preserves_an_input_replaced_by_another_writer(self):
        identity = self.root / 'milo-identity.json'
        replacement = self.root / 'replacement.json'
        replacement.write_bytes(b'newly supplied input\n')

        def failed_prepare(*args):
            replacement.replace(identity)
            raise ValueError('local preparation failed')

        with patch.object(hatch, 'prepare', side_effect=failed_prepare):
            with self.assertRaisesRegex(ValueError, 'local preparation failed'):
                acquisition.prepare(self.root / 'milo', 'milo')
        self.assertEqual(b'newly supplied input\n', identity.read_bytes())
        self.assertFalse((self.root / 'milo-profile.json').exists())
        self.assertFalse((self.root / 'milo').exists())

    def test_new_prepare_creates_bounded_nonfixture_imagegen_jobs_without_generation(self):
        for character in acquisition.CHARACTERS:
            with self.subTest(character=character):
                destination = self.root / character
                result = acquisition.prepare(destination, character)
                manifest = hatch.manifest(destination)
                request = hatch.read(destination / 'pet_request.json')
                profile = hatch.read(destination / 'profile.json')
                self.assertEqual(str(destination.resolve()), result['run'])
                self.assertIsNone(result['previous'])
                self.assertEqual(result['run_id'], manifest['run_id'])
                self.assertFalse(manifest['fixture_mode'])
                self.assertEqual({'attempts_per_job': 1, 'concurrency': 1, 'generation_calls': 2},
                                 {key: manifest['limits'][key] for key in
                                  ('attempts_per_job', 'concurrency', 'generation_calls')})
                self.assertEqual(['base', 'parts'], [job['id'] for job in manifest['jobs']])
                self.assertTrue(all(job['status'] == 'pending' and job['attempts'] == 0
                                    and job['generation_skill'] == '$imagegen'
                                    and 'generation_receipt' not in job and 'token' not in job
                                    for job in manifest['jobs']))
                self.assertEqual(acquisition.CHARACTERS[character]['palette'], request['identity']['palette'])
                self.assertEqual(acquisition.CHARACTERS[character]['asymmetries'], request['identity']['asymmetries'])
                self.assertTrue(request['identity']['forbid_mirror'])
                self.assertEqual(profile, json.loads((self.root / (character + '-profile.json')).read_text(encoding="utf-8")))
                self.assertEqual([1000], profile['states'][0]['durations'])
                self.assertTrue((destination / 'references/layout-guides/parts.png').is_file())
                self.assertFalse(list((destination / 'decoded').glob('*.png')))
                self.assertTrue((self.root / (character + '-identity.json')).is_file())


if __name__ == '__main__':
    unittest.main()
