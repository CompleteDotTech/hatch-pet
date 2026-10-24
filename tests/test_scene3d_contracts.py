"""Scene3D schema, semantic, exact-time and real-file closure regression tests.

No NumPy import: these also exercise the optional-dependency boundary in 2D CI.
"""
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator

from rig_errors import RigError, decode_json
from scene3d_contracts import (canonical_bytes, definitions, document_hash, frame_time,
    load_project, portable_path, read_document, schemas, validate_document)
from scene3d_example import build_example, node

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples' / 'scene3d-contracts'


def fixture(name):
    return json.loads((EXAMPLE / (name + '.json')).read_text())


class SceneContractTests(unittest.TestCase):
    def test_every_generated_schema_is_current_and_valid(self):
        self.assertEqual(len(schemas()), 8)
        for name, schema in schemas().items():
            with self.subTest(name=name):
                Draft202012Validator.check_schema(schema)
                self.assertEqual(json.loads((ROOT / 'profiles' / name).read_text()), schema)

    def test_all_document_kinds_roundtrip_structural_runtime_parity(self):
        for path in EXAMPLE.glob('*.json'):
            with self.subTest(path=path.name):
                value = read_document(path)
                schema = schemas()[value['kind'] + '.schema.json']
                self.assertFalse(list(Draft202012Validator(schema).iter_errors(value)))
                self.assertEqual(decode_json(canonical_bytes(value)), value)
        self.assertIs(validate_document(node('example'), 'node')['visible'], True)

    def test_closed_schemas_reject_unknown_fields_at_every_depth(self):
        for change in ('top', 'node', 'transform', 'reference', 'world'):
            doc = fixture('example-scene')
            target = {'top': doc, 'node': doc['nodes'][0],
                      'transform': doc['nodes'][0]['transform'], 'reference': doc['dependencies'][0],
                      'world': doc['world']}[change]
            target['surprise'] = True
            with self.subTest(change=change), self.assertRaises(RigError):
                validate_document(doc)

    def test_versions_and_types_are_strict(self):
        for field, value in [('schema_version', True), ('schema_version', 2),
                             ('version', '01.0.0'), ('kind', 'hatch-3d-rig'), ('id', 'a/b')]:
            doc = fixture('example-scene')
            doc[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(RigError):
                validate_document(doc)

    def test_semantic_errors_are_distinct_from_structural_schema(self):
        doc = fixture('example-scene')
        doc['nodes'][0]['transform']['rotation'] = [0, 0, 0, 0]
        self.assertFalse(list(Draft202012Validator(schemas()['scene3d-scene.schema.json']).iter_errors(doc)))
        with self.assertRaisesRegex(RigError, 'normalized'):
            validate_document(doc)

    def test_invalid_quaternions_scales_and_nonfinite_values(self):
        for field, values in [('rotation', [[0, 0, 0, 0], [0, 0, 0, 0.5], [0, 0, 0, 2]]),
                              ('scale', [[0, 1, 1], [-1, 1, 1], [1e-9, 1, 1], [1e-7, 1e6, 1]])]:
            for value in values:
                doc = fixture('example-scene')
                doc['nodes'][0]['transform'][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(RigError):
                    validate_document(doc)
        for bad in (float('nan'), float('inf'), -float('inf')):
            doc = fixture('example-scene')
            doc['nodes'][0]['transform']['translation'][0] = bad
            with self.subTest(bad=bad), self.assertRaises(RigError):
                validate_document(doc)

    def test_graph_rejects_duplicate_dangling_parent_cycles_and_roots(self):
        for mode in ('duplicate', 'dangling', 'cycle', 'bad-roots', 'second-root'):
            doc = fixture('example-scene')
            if mode == 'duplicate':
                doc['nodes'].append(deepcopy(doc['nodes'][0]))
            elif mode == 'dangling':
                doc['nodes'][1]['parent'] = 'missing'
            elif mode == 'cycle':
                doc['nodes'][1]['parent'] = 'camera'
                doc['nodes'][2]['parent'] = 'mesh'
            elif mode == 'bad-roots':
                doc['roots'] = ['mesh']
            else:
                doc['nodes'][1]['parent'] = None
            with self.subTest(mode=mode), self.assertRaises(RigError):
                validate_document(doc)

    def test_bounded_deep_graph_and_forward_parent_declaration(self):
        doc = fixture('example-scene')
        doc['nodes'].reverse()
        validate_document(doc)
        doc['nodes'] = [node('n' + str(i), parent='n' + str(i-1) if i else None) for i in range(129)]
        doc['roots'], doc['cameras'] = ['n0'], []
        with self.assertRaisesRegex(RigError, '128'):
            validate_document(doc)

    def test_collections_camera_and_light_inventories(self):
        for mode in ('collection', 'layer', 'camera', 'light', 'camera-far', 'camera-fov'):
            doc = fixture('example-scene')
            if mode == 'collection':
                doc['nodes'][0]['collections'] = ['unknown']
            elif mode == 'layer':
                doc['nodes'][0]['layers'] = ['unknown']
            elif mode == 'camera':
                doc['cameras'] = ['root']
            elif mode == 'light':
                doc['lights'] = ['mesh']
            elif mode == 'camera-far':
                doc['nodes'][2]['camera']['far'] = 0.01
            else:
                doc['nodes'][2]['camera']['vertical_fov'] = 4
            with self.subTest(mode=mode), self.assertRaises(RigError):
                validate_document(doc)

    def test_node_owned_fields_and_explicit_billboard_marker(self):
        for mode in ('missing-camera', 'camera-on-mesh', 'unmarked-billboard', 'prefab-on-group'):
            doc = fixture('example-scene')
            if mode == 'missing-camera':
                del doc['nodes'][2]['camera']
            elif mode == 'camera-on-mesh':
                doc['nodes'][1]['camera'] = doc['nodes'][2]['camera']
            elif mode == 'unmarked-billboard':
                doc['nodes'][1]['type'] = 'billboard_2d'
                doc['nodes'][1]['billboard'] = False
            else:
                doc['nodes'][0]['prefab'] = fixture('project')['prefabs'][0]
            with self.subTest(mode=mode), self.assertRaises(RigError):
                validate_document(doc)

    def test_constraints_and_attachments_cannot_add_evaluation_cycles(self):
        doc = fixture('example-scene')
        doc['nodes'][0]['constraints'] = [dict(id='follow', type='copy-transform', target='mesh', influence=1)]
        with self.assertRaisesRegex(RigError, 'Cyclic'):
            validate_document(doc)
        doc = fixture('example-scene')
        doc['nodes'][1]['attachment'] = dict(owner='camera', socket='root',
                                            offset=deepcopy(doc['nodes'][0]['transform']))
        with self.assertRaisesRegex(RigError, 'socket'):
            validate_document(doc)

    def test_duplicate_material_slots_are_rejected(self):
        doc = fixture('example-scene')
        r = deepcopy(doc['dependencies'][0])
        r['kind'] = 'material'
        doc['nodes'][1]['material_overrides'] = [dict(slot='surface', material=r)] * 2
        with self.assertRaisesRegex(RigError, 'Duplicate material'):
            validate_document(doc)

    def test_bounds_and_prefab_overrides_are_semantic(self):
        doc = fixture('triangle')
        doc['bounds']['minimum'][0] = 2
        with self.assertRaisesRegex(RigError, 'Inverted bounds'):
            validate_document(doc)
        doc = fixture('example-prefab')
        doc['overrides'] = [dict(node='missing', visible=False)]
        with self.assertRaisesRegex(RigError, 'Dangling prefab'):
            validate_document(doc)

    def test_fixture_provenance_never_becomes_production(self):
        doc = fixture('triangle')
        doc['provenance']['fixture'] = False
        with self.assertRaisesRegex(RigError, 'fixture'):
            validate_document(doc)
        doc = fixture('project')
        doc['status'] = 'production'
        with self.assertRaisesRegex(RigError, 'fixture'):
            validate_document(doc)

    def test_exact_rational_frame_time_and_terminal_boundary(self):
        self.assertEqual(frame_time(720, dict(numerator=24, denominator=1)), Fraction(30))
        self.assertEqual(frame_time(24000, dict(numerator=24000, denominator=1001)), Fraction(1001))
        for bad in [dict(numerator=0, denominator=1), dict(numerator=True, denominator=1),
                    dict(numerator=48, denominator=2), dict(numerator=241, denominator=1)]:
            with self.subTest(bad=bad), self.assertRaises(RigError):
                frame_time(1, bad)
        with self.assertRaises(RigError):
            frame_time(True, dict(numerator=24, denominator=1))

    def test_track_timing_interpolation_and_value_dimensions(self):
        for mode in ('duplicate', 'reverse', 'out-of-range', 'bad-fps', 'quaternion',
                     'dimension', 'boolean', 'scale', 'interpolation'):
            doc = fixture('example-animation')
            track = doc['tracks'][0]
            if mode == 'duplicate':
                track['keys'][1]['frame'] = 0
            elif mode == 'reverse':
                track['keys'].reverse()
            elif mode == 'out-of-range':
                track['keys'][1]['frame'] = 25
            elif mode == 'bad-fps':
                doc['fps'] = dict(numerator=48, denominator=2)
            elif mode == 'quaternion':
                track['property'], track['interpolation'] = 'rotation', 'slerp'
                track['keys'][0]['value'] = [0, 0, 0, 0]
            elif mode == 'dimension':
                track['keys'][0]['value'] = [0, 1, 2, 3]
            elif mode == 'boolean':
                track['property'], track['interpolation'] = 'visible', 'step'
            elif mode == 'scale':
                track['property'] = 'scale'
                track['keys'][0]['value'] = [-1, 1, 1]
            else:
                track['interpolation'] = 'slerp'
            with self.subTest(mode=mode), self.assertRaises(RigError):
                validate_document(doc)
        doc = fixture('example-animation')
        self.assertEqual(validate_document(doc)['tracks'][0]['keys'][-1]['frame'], 24)

    def test_clip_and_temporal_ranges_are_nonempty_half_open(self):
        doc = fixture('example-shot')
        clip = fixture('project')['animations'][0]
        doc['bindings'] = [dict(target='mesh', clip=clip, start_frame=3, end_frame=3, speed=1, loop=False)]
        with self.assertRaisesRegex(RigError, 'clip interval'):
            validate_document(doc)
        doc = fixture('example-render')
        doc['start_frame'] = doc['end_frame']
        with self.assertRaisesRegex(RigError, 'nonempty'):
            validate_document(doc)

    def test_exact_time_cannot_raise_unstructured_errors_on_integral_floats(self):
        for field in ('fps', 'duration', 'key'):
            doc = fixture('example-animation')
            if field == 'fps':
                doc['fps']['numerator'] = 24.0
            elif field == 'duration':
                doc['duration_frames'] = 24.0
            else:
                doc['tracks'][0]['keys'][0]['frame'] = 0.0
            with self.subTest(field=field), self.assertRaisesRegex(RigError, 'JSON integer'):
                validate_document(doc)

    def test_timestamps_and_evidence_free_review_status_rejected(self):
        for value in ('yesterday', '2026-10-23', '2026-10-22T00:00:00Z'):
            doc = fixture('project')
            doc['modified_at'] = value
            with self.subTest(value=value), self.assertRaises(RigError):
                validate_document(doc)
        doc = fixture('triangle')
        doc['review']['status'] = 'approved'
        with self.assertRaisesRegex(RigError, 'receipts'):
            validate_document(doc)

    def test_canonical_serialization_is_stable_without_mutation(self):
        doc = fixture('example-scene')
        original = deepcopy(doc)
        reordered = dict(reversed(list(doc.items())))
        self.assertEqual(document_hash(doc), document_hash(reordered))
        self.assertEqual(doc, original)

    def test_duplicate_keys_depth_and_nonfinite_json_rejected(self):
        for payload in ['{"schema_version":1,"schema_version":2}', '{"v":NaN}', '[' * 70 + '0' + ']' * 70]:
            with self.subTest(payload=payload[:40]), self.assertRaises(RigError):
                decode_json(payload)

    def test_nonportable_paths_rejected(self):
        for path in ('../x', '/x', 'a//b', 'a/./b', 'a/../b', 'C:/x', 'a\\b',
                     'file:uri', 'a\x00b', 'a/NUL.txt', 'a/COM1', 'a/x.', 'a/x ', 'e\u0301.json'):
            with self.subTest(path=repr(path)), self.assertRaises(RigError):
                portable_path(path)
        self.assertEqual(portable_path('assets/épreuve.obj'), 'assets/épreuve.obj')


class SceneClosureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'
        shutil.copytree(EXAMPLE, self.root)

    def rehash(self):
        # Rebind genuine changes bottom-up, preserving exact raw-byte hashes.
        documents = {p.name: json.loads(p.read_text()) for p in self.root.glob('*.json')}
        from scene3d_contracts import all_refs
        done = {}
        def visit(name):
            if name in done:
                return done[name]
            if name in documents:
                doc = documents[name]
                for r in all_refs(doc):
                    r['sha256'] = visit(r['path'])
                payload = canonical_bytes(doc)
                (self.root / name).write_bytes(payload)
            else:
                payload = (self.root / name).read_bytes()
            done[name] = hashlib.sha256(payload).hexdigest()
            return done[name]
        visit('project.json')

    def write(self, name, doc):
        (self.root / name).write_text(json.dumps(doc))
        self.rehash()

    def test_checked_in_real_geometry_package_hashes_and_fresh_process(self):
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()}
        bundle = load_project(self.root)
        self.assertEqual(len(bundle['documents']), 7)
        self.assertEqual(len(bundle['inventory']), 8)
        self.assertEqual(bundle['status'], 'hash-and-contract-verified')
        self.assertIn(b'f 1 2 3', (self.root / 'triangle.obj').read_bytes())
        process = subprocess.run([sys.executable, str(ROOT / 'scripts/scene3d_contracts.py'), str(self.root)],
                                  capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)['files'], 8)
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()})

    def test_example_builder_produces_same_validated_documents(self):
        generated = Path(self.temp.name) / 'generated'
        result = build_example(generated)
        self.assertEqual(result['inventory'], load_project(EXAMPLE)['inventory'])
        with self.assertRaises(FileExistsError):
            build_example(generated)

    def test_changed_and_missing_source_bytes_fail_closed(self):
        (self.root / 'triangle.obj').write_bytes(b'different original')
        with self.assertRaisesRegex(RigError, 'hash mismatch'):
            load_project(self.root)
        (self.root / 'triangle.obj').unlink()
        with self.assertRaisesRegex(RigError, 'Missing regular'):
            load_project(self.root)

    def test_directory_and_symlink_dependency_rejected(self):
        original = (self.root / 'triangle.obj').read_bytes()
        (self.root / 'triangle.obj').unlink()
        (self.root / 'triangle.obj').mkdir()
        with self.assertRaisesRegex(RigError, 'Missing regular'):
            load_project(self.root)
        (self.root / 'triangle.obj').rmdir()
        outside = Path(self.temp.name) / 'outside.obj'
        outside.write_bytes(original)
        try:
            (self.root / 'triangle.obj').symlink_to(outside)
        except (OSError, NotImplementedError):
            # Windows can lack symlink privileges; non-regular input covered above.
            return
        with self.assertRaisesRegex(RigError, 'symlink'):
            load_project(self.root)

    def test_wrong_reference_identity_cannot_hide_behind_correct_file_hash(self):
        project = fixture('project')
        project['assets'][0]['id'] = 'wrong-id'
        # No content changed, only reference identity; correct raw hash stays valid.
        (self.root / 'project.json').write_bytes(canonical_bytes(project))
        with self.assertRaisesRegex(RigError, 'identity/version'):
            load_project(self.root)

    def test_raw_reference_first_cannot_bypass_manifest_identity_validation(self):
        project = fixture('project')
        # Catalog is processed before assets; malicious inputs cannot cause an
        # already hash-verified raw file to skip its later typed validation.
        project['asset_catalog'] = deepcopy(project['assets'][0])
        project['asset_catalog']['kind'] = 'catalog'
        project['assets'][0]['id'] = 'wrong-id'
        (self.root / 'project.json').write_bytes(canonical_bytes(project))
        with self.assertRaisesRegex(RigError, 'identity/version'):
            load_project(self.root)

    def test_manifest_lock_coverage_required(self):
        project = fixture('project')
        project['dependency_lock'] = [r for r in project['dependency_lock'] if r['kind'] != 'scene3d-asset']
        (self.root / 'project.json').write_bytes(canonical_bytes(project))
        with self.assertRaisesRegex(RigError, 'lock'):
            load_project(self.root)

    def test_missing_shot_camera_and_node_are_not_admitted(self):
        shot = fixture('example-shot')
        shot['camera'] = 'missing-camera'
        self.write('example-shot.json', shot)
        with self.assertRaisesRegex(RigError, 'camera'):
            load_project(self.root)
        shot['camera'] = 'camera'
        shot['tracks'] = [dict(target='missing-node', property='visible', interpolation='step',
                              keys=[dict(frame=0, value=True)])]
        self.write('example-shot.json', shot)
        with self.assertRaisesRegex(RigError, 'missing node'):
            load_project(self.root)

    def test_render_cannot_exceed_actual_shot_duration(self):
        render = fixture('example-render')
        render['end_frame'] = 25
        self.write('example-render.json', render)
        with self.assertRaisesRegex(RigError, 'range exceeds'):
            load_project(self.root)

    def test_resource_byte_count_compared_with_actual_content(self):
        asset = fixture('triangle')
        asset['resources']['bytes'] += 1
        self.write('triangle.json', asset)
        with self.assertRaisesRegex(RigError, 'byte count'):
            load_project(self.root)

    def test_project_enforces_file_node_frame_and_byte_budgets(self):
        for field, value in [('max_files', 1), ('max_nodes', 2), ('max_frames', 23), ('max_bytes', 1)]:
            project = fixture('project')
            project['budgets'][field] = value
            (self.root / 'project.json').write_bytes(canonical_bytes(project))
            with self.subTest(field=field), self.assertRaisesRegex(RigError, 'budget'):
                load_project(self.root)

    def test_case_aliases_and_conflicting_hashes_are_rejected(self):
        for mode in ('alias', 'hash'):
            project = fixture('project')
            project['validation'] = [dict(path='Triangle.obj' if mode == 'alias' else 'triangle.obj',
                                          sha256=fixture('triangle')['content']['sha256'] if mode == 'alias' else '0'*64)]
            (self.root / 'project.json').write_bytes(canonical_bytes(project))
            with self.subTest(mode=mode), self.assertRaisesRegex(RigError, 'alias|Conflicting'):
                load_project(self.root)

    def test_asset_kind_checked_against_actual_geometry_node_manifest(self):
        asset = fixture('triangle')
        asset['asset_type'] = 'material'
        self.write('triangle.json', asset)
        with self.assertRaisesRegex(RigError, 'non-geometric'):
            load_project(self.root)

    def test_legacy_project_bridge_uses_actual_v1_kind_and_keeps_source_bytes(self):
        from production_fixture import build_fixture_project
        from production_contracts import load_project as load_legacy
        legacy_root = self.root / 'legacy'
        build_fixture_project(legacy_root)
        payload = (legacy_root / 'project.json').read_bytes()
        legacy = json.loads(payload)
        pointer = dict(id=legacy['id'], version=legacy['version'], kind='project',
                       path='legacy/project.json', sha256=hashlib.sha256(payload).hexdigest())
        project = fixture('project')
        project['linked_2d_project'] = pointer
        project['dependency_lock'].append(pointer)
        (self.root / 'project.json').write_bytes(canonical_bytes(project))
        self.assertEqual(load_project(self.root)['project']['linked_2d_project'], pointer)
        self.assertEqual((legacy_root / 'project.json').read_bytes(), payload)
        self.assertEqual(load_legacy(legacy_root)['project']['kind'], 'project')
        project['linked_2d_project']['id'] = 'incorrect-legacy-id'
        (self.root / 'project.json').write_bytes(canonical_bytes(project))
        with self.assertRaisesRegex(RigError, 'identity/version'):
            load_project(self.root)

    def test_legacy_pointer_cannot_reuse_a_preloaded_scene_manifest(self):
        project = fixture('project')
        pointer = deepcopy(project['scenes'][0])
        pointer['kind'] = 'project'
        project['linked_2d_project'] = pointer
        project['dependency_lock'].append(pointer)
        (self.root / 'project.json').write_bytes(canonical_bytes(project))
        with self.assertRaises(RigError):
            load_project(self.root)

    def test_cli_failure_is_structured_nonzero_and_nonmutating(self):
        (self.root / 'triangle.obj').unlink()
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/scene3d_contracts.py'), str(self.root)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(json.loads(result.stderr)['ok'])
        self.assertNotIn('Traceback', result.stderr)
        self.assertFalse((self.root / 'triangle.obj').exists())

    def test_optional_3d_imports_remain_unnecessary_for_loading(self):
        code = '''import sys,importlib.abc
sys.path.insert(0, 'scripts')
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in ('numpy','bpy','pygltflib'): raise ImportError(fullname)
sys.meta_path.insert(0,Block())
from scene3d_contracts import load_project
assert len(load_project('examples/scene3d-contracts')['documents']) == 7
'''
        result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
