"""Fresh contract regression tests, including malformed and selectively missing sources."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from production_contracts import (asset_key, file_sha, load_project, read_json, safe_path, schemas,
                                 validate_cast, validate_clip, validate_scene, validate_shot, validate_structure)
from production_fixture import (build_fixture_project, fixture_provenance, refresh_project_hashes,
                                track, write_json)


class ProductionContractTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = build_fixture_project(self.root)
        self.bundle = load_project(self.path)
        self.cast = copy.deepcopy(self.bundle['cast'])
        self.clip = copy.deepcopy(self.bundle['clips']['idle-a@1.0.0'])
        self.shot = copy.deepcopy(self.bundle['shots']['exchange'])

    def save_cast(self, cast=None):
        write_json(self.root / 'cast.json', cast or self.cast)
        refresh_project_hashes(self.root)

    def save_first_shot(self):
        scene = copy.deepcopy(self.bundle['scenes'][0])
        scene['shots'][0] = self.shot
        write_json(self.root / 'first-scene.json', scene)
        refresh_project_hashes(self.root)

    def validate_shot(self):
        return validate_shot(self.shot, self.bundle['characters'], self.bundle['clips'], self.bundle['props'], True)

    def test_schema_documents_match_the_runtime_contract_and_validate_the_fixture(self):
        import jsonschema
        root = Path(__file__).resolve().parents[1]
        for kind, schema in schemas().items():
            with self.subTest(kind=kind):
                self.assertEqual(schema, read_json(root / 'profiles' / ('production-' + kind + '.schema.json')))
                jsonschema.Draft202012Validator.check_schema(schema)
                value = {'project': self.bundle['project'], 'cast': self.cast, 'clip': self.clip,
                         'scene': self.bundle['scenes'][0], 'shot': self.shot}[kind]
                jsonschema.Draft202012Validator(schema).validate(value)

    def test_two_scenes_reuse_exact_character_versions_and_asset_inventory(self):
        self.assertEqual(['first-scene', 'second-scene'], [scene['id'] for scene in self.bundle['scenes']])
        self.assertEqual({'a@1.0.0', 'b@1.0.0'}, set(self.bundle['characters']))
        for shot in self.bundle['shots'].values():
            self.assertEqual(['a@1.0.0', 'b@1.0.0'], [actor['character'] for actor in shot['instances']])
        self.assertEqual(24, self.bundle['resources']['total_frames'])
        self.assertFalse(self.bundle['stale'])
        self.assertFalse(self.bundle['missing'])

    def test_versioned_assets_reject_duplicate_identity_but_allow_a_new_version(self):
        self.cast['characters'].append(copy.deepcopy(self.cast['characters'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate stable identity'):
            validate_cast(self.cast)
        self.cast['characters'][-1]['version'] = '1.0.1'
        validate_cast(self.cast)
        self.assertEqual('a@1.0.1', asset_key(self.cast['characters'][-1]))

    def test_unknown_fields_unsupported_versions_and_boolean_frames_fail_closed(self):
        for field, value in [('surprise', True), ('duration_frames', True), ('duration_frames', 1.5)]:
            candidate = copy.deepcopy(self.shot)
            candidate[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_structure(candidate, 'shot')
        for version in (2, True, '1'):
            candidate = copy.deepcopy(self.cast)
            candidate['schema_version'] = version
            with self.subTest(version=version), self.assertRaises(ValueError):
                validate_structure(candidate, 'cast')
        for version in ('latest', 'v1.0.0', '01.0.0', '1.0', '1.0.0-beta'):
            self.clip['version'] = version
            with self.subTest(version=version), self.assertRaises(ValueError):
                validate_structure(self.clip, 'clip')

    def test_hash_mismatch_is_fail_closed_and_diagnostic_mode_reports_actual_bytes(self):
        image = self.cast['characters'][0]['components'][0]['drawings']['default']['image']
        path = self.root / image['path']
        with Image.open(path) as source:
            changed = source.convert('RGBA')
        changed.putpixel((10, 10), (1, 2, 3, 255))
        changed.save(path)
        changed.close()
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            load_project(self.path)
        diagnostic = load_project(self.path, verify_hashes=False)
        self.assertEqual(image['sha256'], diagnostic['stale'][0]['expected'])
        self.assertEqual(file_sha(path), diagnostic['stale'][0]['actual'])

    def test_missing_leaf_assets_are_inventory_records_only_in_explicit_diagnostic_mode(self):
        image = self.cast['characters'][0]['components'][0]['drawings']['default']['image']
        (self.root / image['path']).unlink()
        with self.assertRaisesRegex(ValueError, 'missing dependency'):
            load_project(self.path)
        with self.assertRaisesRegex(ValueError, 'requires diagnostic'):
            load_project(self.path, allow_missing_assets=True)
        diagnostic = load_project(self.path, verify_hashes=False, allow_missing_assets=True)
        self.assertEqual([image['path']], [item['path'] for item in diagnostic['missing']])
        record = diagnostic['inventory'][image['path']]
        self.assertTrue(record['missing'])
        self.assertIsNone(record['sha256'])
        self.assertEqual(0, record['bytes'])
        self.assertEqual(image['sha256'], record['expected_sha256'])
        (self.root / 'idle-a.json').unlink()
        with self.assertRaisesRegex(ValueError, 'missing dependency'):
            load_project(self.path, verify_hashes=False, allow_missing_assets=True)

    def test_conflicting_expected_hashes_fail_even_when_the_asset_is_missing(self):
        part = self.cast['characters'][0]['components'][0]
        part['drawings']['extra'] = copy.deepcopy(part['drawings']['default'])
        part['drawings']['extra']['image']['sha256'] = '0' * 64
        image = part['drawings']['default']['image']
        (self.root / image['path']).unlink()
        self.save_cast()
        with self.assertRaisesRegex(ValueError, 'conflicting hashes'):
            load_project(self.path, verify_hashes=False, allow_missing_assets=True)

    def test_portable_paths_reject_traversal_absolute_drive_backslash_and_symlink(self):
        for bad in ('../cast.json', '/tmp/cast.json', 'C:/cast.json', 'art\\x.png', './cast.json', 'art//x.png', ''):
            with self.subTest(path=bad), self.assertRaisesRegex(ValueError, 'portable relative path'):
                safe_path(self.root, bad, must_exist=False)
        (self.root / 'linked.png').symlink_to(self.root / 'art/a-body.png')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            safe_path(self.root, 'linked.png')
        (self.root / 'linked-dir').symlink_to(self.root / 'art', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            safe_path(self.root, 'linked-dir/a-body.png', must_exist=False)

    def test_image_header_viewport_and_alpha_are_verified_before_rendering(self):
        image_ref = self.cast['characters'][0]['components'][0]['drawings']['default']['image']
        path = self.root / image_ref['path']
        image = Image.new('RGBA', (41, 40), '#cc5522')
        image.save(path)
        image.close()
        with self.assertRaisesRegex(ValueError, 'header dimensions'):
            load_project(self.path, verify_hashes=False)
        image = Image.new('RGB', (40, 40), '#cc5522')
        image.save(path)
        image.close()
        with self.assertRaisesRegex(ValueError, 'straight alpha'):
            load_project(self.path, verify_hashes=False)

    def test_fixture_provenance_and_review_cannot_become_production_acceptance(self):
        self.cast['fixture'] = False
        with self.assertRaisesRegex(ValueError, 'fixture provenance'):
            validate_cast(self.cast)
        self.cast['fixture'] = True
        review = self.cast['characters'][0]['view_reviews']['front']
        review['reviewer'] = None
        with self.assertRaisesRegex(ValueError, 'approved viewpoint requires'):
            validate_cast(self.cast)
        review['reviewer'] = 'fixture-builder'
        review['evidence'] = []
        with self.assertRaisesRegex(ValueError, 'approved viewpoint requires'):
            validate_cast(self.cast)

    def test_provenance_requires_explicit_derivation_and_acquisition_metadata(self):
        provenance = self.cast['characters'][0]['provenance']
        provenance['kind'] = 'derived'
        with self.assertRaisesRegex(ValueError, 'exact source and explicit operation'):
            validate_cast(self.cast)
        provenance['kind'] = 'imagegen'
        with self.assertRaisesRegex(ValueError, 'acquisition receipt'):
            validate_cast(self.cast)
        provenance['kind'] = 'import'
        provenance['model_call'] = {'id': None, 'model': None, 'parameters': None}
        with self.assertRaisesRegex(ValueError, 'unavailable_reason'):
            validate_cast(self.cast)

    def test_hierarchy_rejects_cycles_and_missing_grandparents_with_actionable_errors(self):
        parts = self.cast['characters'][0]['components']
        parts[1]['parent'], parts[1]['parent_anchor'] = 'hand', 'grip'
        parts[2]['parent'], parts[2]['parent_anchor'] = 'head', 'mouth'
        with self.assertRaisesRegex(ValueError, 'cycle'):
            validate_cast(self.cast)
        parts[2]['parent'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'missing parent'):
            validate_cast(self.cast)

    def test_pivots_masks_and_replacement_drawings_preserve_local_viewports(self):
        part = self.cast['characters'][0]['components'][3]
        part['pivot'] = [9, 3]
        with self.assertRaisesRegex(ValueError, 'inside.*viewport'):
            validate_cast(self.cast)
        part['pivot'] = [4, 3]
        part['drawings']['open']['image']['size'] = [10, 6]
        with self.assertRaisesRegex(ValueError, 'same component viewport'):
            validate_cast(self.cast)
        part['drawings']['open']['image']['size'] = [8, 6]
        part['mask'] = copy.deepcopy(part['drawings']['default']['image'])
        part['mask']['size'] = [8, 8]
        with self.assertRaisesRegex(ValueError, 'mask must match'):
            validate_cast(self.cast)

    def test_missing_viewpoint_never_falls_back_to_mirroring_front_art(self):
        self.shot['instances'][0]['viewpoint'] = 'back'
        with self.assertRaisesRegex(ValueError, 'unsupported viewpoint'):
            self.validate_shot()
        self.bundle['characters']['a@1.0.0']['views'].append('back')
        with self.assertRaisesRegex(ValueError, 'missing compatible drawing'):
            self.validate_shot()

    def test_clip_root_origin_and_displacement_endpoint_are_enforced(self):
        self.clip['root']['offset'] = track([3, 0], [30, 0])
        self.clip['displacement'] = [30, 0]
        with self.assertRaisesRegex(ValueError, 'begin at offset'):
            validate_clip(self.clip, self.bundle['characters'])
        self.clip['root']['offset'] = track([0, 0], [24, 0])
        with self.assertRaisesRegex(ValueError, 'displacement'):
            validate_clip(self.clip, self.bundle['characters'])
        self.clip['displacement'] = [24, 0]
        validate_clip(self.clip, self.bundle['characters'])

    def test_root_facing_tracks_cannot_bypass_identity_or_authored_view(self):
        self.clip['root']['facing'] = track('right')
        with self.assertRaisesRegex(ValueError, 'root facing'):
            validate_clip(self.clip, self.bundle['characters'])
        self.shot['instances'][0]['tracks']['root'] = {'facing': track('right')}
        with self.assertRaisesRegex(ValueError, 'root facing'):
            self.validate_shot()
        self.bundle['characters']['a@1.0.0']['identity']['allowed_facings'].append('right')
        with self.assertRaisesRegex(ValueError, 'root facing'):
            self.validate_shot()

    def test_independent_channels_cannot_silently_overwrite_the_same_property(self):
        self.clip['tracks']['gaze']['eyes']['visible'] = track(True)
        with self.assertRaisesRegex(ValueError, 'same component property'):
            validate_clip(self.clip, self.bundle['characters'])
        self.clip['tracks']['gaze']['eyes'].pop('visible')
        validate_clip(self.clip, self.bundle['characters'])

    def test_tracks_require_frame_zero_strict_order_and_discrete_step_values(self):
        for malformed in ({'interpolation': 'linear', 'keys': [{'frame': 1, 'value': 0}]},
                          {'interpolation': 'linear', 'keys': [{'frame': 0, 'value': 0}, {'frame': 0, 'value': 1}]},
                          {'interpolation': 'linear', 'keys': [{'frame': 0, 'value': 0}, {'frame': 13, 'value': 1}]}):
            self.clip['tracks']['body']['head']['rotation'] = malformed
            with self.assertRaises(ValueError):
                validate_clip(self.clip, self.bundle['characters'])
        self.clip['tracks']['body']['head']['rotation'] = track(0)
        self.clip['tracks']['mouth']['mouth']['drawing']['interpolation'] = 'linear'
        with self.assertRaisesRegex(ValueError, 'step interpolation'):
            validate_clip(self.clip, self.bundle['characters'])

    def test_integer_half_open_placement_contact_and_event_intervals_are_checked(self):
        self.shot['instances'][0]['clips'][0]['end_frame'] = 13
        with self.assertRaisesRegex(ValueError, 'integer frames'):
            self.validate_shot()
        self.clip['contacts'][0]['start_frame'] = 12
        with self.assertRaisesRegex(ValueError, 'integer frames'):
            validate_clip(self.clip, self.bundle['characters'])
        self.clip['contacts'][0]['start_frame'] = 0
        self.clip['events'][0]['frame'] = 12
        with self.assertRaisesRegex(ValueError, 'before completion'):
            validate_clip(self.clip, self.bundle['characters'])

    def test_owner_and_attachment_and_shared_event_must_agree(self):
        prop = self.shot['props'][0]
        prop['attachment']['instance'] = 'b'
        with self.assertRaisesRegex(ValueError, 'owner and attachment'):
            self.validate_shot()
        prop['attachment']['instance'] = 'a'
        prop['ownership'][0]['event'] = 'absent'
        with self.assertRaisesRegex(ValueError, 'synchronized shared interaction'):
            self.validate_shot()

    def test_handoff_requires_both_actual_clip_markers_at_the_same_frame(self):
        self.shot['interactions'][0]['participants'].pop()
        with self.assertRaisesRegex(ValueError, 'both.*participants'):
            self.validate_shot()
        self.shot = copy.deepcopy(self.bundle['shots']['exchange'])
        self.shot['interactions'][0]['participants'][1]['marker'] = 'absent'
        with self.assertRaisesRegex(ValueError, 'exactly one clip marker'):
            self.validate_shot()
        self.shot['interactions'][0]['participants'][1]['marker'] = 'grasp'
        self.shot['interactions'][0]['frame'] = 7
        self.shot['props'][0]['ownership'][0]['frame'] = 7
        with self.assertRaisesRegex(ValueError, 'exactly one clip marker'):
            self.validate_shot()

    def test_camera_rate_and_zoom_bounds_fail_closed(self):
        self.shot['camera']['position'] = track([0, 0], [40, 0], end=1)
        with self.assertRaisesRegex(ValueError, 'per-frame interpolation limit'):
            self.validate_shot()
        self.shot['camera']['position'] = track([0, 0])
        self.shot['camera']['zoom'] = track(3)
        with self.assertRaisesRegex(ValueError, 'zoom exceeds'):
            self.validate_shot()

    def test_cross_scene_scale_and_position_continuity_are_validated(self):
        second = copy.deepcopy(self.bundle['scenes'][1])
        second['shots'][0]['cast_scale'] = 1.1
        write_json(self.root / 'second-scene.json', second)
        refresh_project_hashes(self.root)
        with self.assertRaisesRegex(ValueError, 'relative scale mismatch'):
            load_project(self.path)
        second['shots'][0]['cast_scale'] = 1
        second['shots'][0]['instances'][0]['position'][0] += 1
        write_json(self.root / 'second-scene.json', second)
        refresh_project_hashes(self.root)
        with self.assertRaisesRegex(ValueError, 'position mismatch'):
            load_project(self.path)

    def test_cross_scene_prop_ownership_continuity_is_not_inferred_from_appearance(self):
        second = copy.deepcopy(self.bundle['scenes'][1])
        second['shots'][0]['props'][0].update(owner='a', attachment={'instance': 'a', 'component': 'hand', 'anchor': 'grip'})
        write_json(self.root / 'second-scene.json', second)
        refresh_project_hashes(self.root)
        with self.assertRaisesRegex(ValueError, 'prop ownership mismatch'):
            load_project(self.path)

    def test_resource_bounds_apply_before_expensive_rendering(self):
        original = copy.deepcopy(self.bundle['project'])
        for field, value in [('max_frames', 23), ('max_assets', 2), ('max_source_pixels', 100), ('max_work_bytes', 1000)]:
            project = copy.deepcopy(original)
            project['limits'][field] = value
            write_json(self.path, project)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'resource|working set'):
                load_project(self.path)
        project = copy.deepcopy(original)
        project['render']['fps']['numerator'] = 120
        write_json(self.path, project)
        with self.assertRaisesRegex(ValueError, '1 and 60 fps'):
            load_project(self.path)

    def test_json_duplicate_keys_nonfinite_and_excessive_nesting_are_rejected(self):
        path = self.root / 'bad.json'
        for text in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}', '[' * 100 + '0' + ']' * 100):
            path.write_text(text, encoding='utf-8')
            with self.subTest(text=text[:30]), self.assertRaises(ValueError):
                read_json(path)


if __name__ == '__main__':
    unittest.main()
