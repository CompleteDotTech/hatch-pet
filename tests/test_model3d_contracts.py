"""Real generated meshes and adversarial checks for the additive contract boundary."""
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import struct
from concurrent.futures import ThreadPoolExecutor
from unittest import mock
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from model3d_contracts import COORDINATES, KINDS, LIMITS, schemas, validate_contract
from model3d_validation import validate_document, validate_file
from rig_errors import RigError, decode_json


def payload(root, name, media='application/json'):
    data = (root / name).read_bytes()
    return dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), media_type=media)


def provenance():
    return dict(origin='procedural-fixture', fixture=True, description='Synthetic engineering mesh; not production artwork.',
                tools=[dict(name='rig_gltf.export_geometry', version='1.0.0')], evidence=[],
                license=dict(identifier=None, attribution=None, redistribution='unknown', evidence=None))


def asset_fixture(root, identifier='fixture', *, suffix='.glb'):
    from rig_gltf import export_geometry
    from rig_import import load_character_model
    from test_rig_skinning import test_geometry
    # The importer returns canonical paths (macOS /private/var and Windows
    # expanded short names); derive the inventory from the same existing root.
    root = root.resolve()
    path = root / (identifier + suffix)
    export_geometry(test_geometry(), path, provenance={'fixture': True})
    if suffix == '.gltf':
        content = json.loads(path.read_text())
        for index, buffer in enumerate(content.get('buffers', [])):
            uri = buffer['uri']
            if uri.startswith('data:'):
                name = f'{identifier}-{index}.bin'
                (root / name).write_bytes(base64.b64decode(uri.split(',', 1)[1], validate=True))
                buffer['uri'] = name
        path.write_text(json.dumps(content), encoding='utf-8')
    model = load_character_model(path)
    files = [payload(root, p.relative_to(root).as_posix(),
                     'model/gltf-binary' if p.suffix == '.glb' else
                     'model/gltf+json' if p.suffix == '.gltf' else 'application/octet-stream')
             for p in model.source_files]
    geometry = next(f for f in files if f['path'] == path.name)
    source = dict(schema_version=1, kind='model3d-source', id='original', version='1.0.0',
                  file=geometry, role='geometry', provenance=provenance(), camera=dict(status='unknown'))
    return dict(schema_version=1, kind='model3d-asset', id=identifier, version='1.0.0', category='character',
                coordinate_system=deepcopy(COORDINATES), sources=[source], files=files, geometry=geometry,
                measurements=dict(vertices=model.geometry.vertex_count, triangles=model.geometry.triangle_count,
                                  bounds=dict(minimum=model.report['bounds'][0], maximum=model.report['bounds'][1])),
                parts=[dict(schema_version=1, kind='model3d-part', id='body', name='Body', parent=None,
                            local_transform=dict(translation=[0, 0, 0], rotation=[0, 0, 0, 1], scale=[1, 1, 1]),
                            mesh_ids=[m.id for m in model.geometry.meshes], material_ids=[],
                            source_ids=['original'], uncertainty_ids=[])],
                materials=[], dependencies=[], uncertainties=[], provenance=provenance(),
                review=dict(status='pending', evidence=[]), limits=deepcopy(LIMITS))


def write_document(root, name, document):
    (root / name).write_text(json.dumps(document), encoding='utf-8')
    return payload(root, name)


def request_fixture(sources):
    return dict(schema_version=1, kind='model3d-request', id='request', version='1.0.0', asset_id='fixture',
        category='prop', method='import', description='Import the specified mesh.', negative_constraints=[],
        sources=deepcopy(sources), coordinate_system=deepcopy(COORDINATES), dimensions_m=[1,1,1],
        scale_evidence='estimated', intended_use='editing', formats=['glb'], semantic_parts=['body'],
        allowed_assumptions=[], identity=None, style=None, provider=None, seed=0, limits=deepcopy(LIMITS))


class Model3DContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.asset = asset_fixture(self.root)

    def assertInvalid(self, document, code=None, *, payloads=False):
        with self.assertRaises(RigError) as caught:
            validate_document(document, self.root) if payloads else validate_contract(document)
        if code:
            self.assertEqual(caught.exception.report['code'], code)

    def test_generated_schema_parity_and_schema_isolation(self):
        from jsonschema import Draft202012Validator
        schema = schemas()['model3d.schema.json']
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(self.asset)
        self.assertEqual(json.loads((ROOT / 'profiles/model3d.schema.json').read_text()), schema)
        schema['$defs']['asset']['properties'].clear()
        self.assertTrue(schemas()['model3d.schema.json']['$defs']['asset']['properties'])

    def test_real_glb_and_external_gltf_payloads(self):
        for asset in (self.asset, asset_fixture(self.root, 'external', suffix='.gltf')):
            with self.subTest(asset=asset['id']):
                result = validate_document(asset, self.root)
                self.assertTrue(result['contract_valid'])
                self.assertTrue(result['payloads_verified'])
                self.assertTrue(result['geometry_inspected'])
                self.assertGreater(result['geometry'][0]['inspection']['vertices'], 0)
                self.assertEqual(result['visual_approval'], 'not-assessed')
                self.assertEqual(result['provider_execution'], 'not-assessed')

    def test_fixture_and_inspection_support_aliased_workspace_root(self):
        actual = self.root / 'actual-workspace'
        actual.mkdir()
        alias = self.root / 'workspace-alias'
        try:
            alias.symlink_to(actual, target_is_directory=True)
        except OSError as exc:
            self.skipTest('Host cannot create directory symlinks: ' + str(exc))
        link_target = alias.readlink()
        canonical_root = actual / 'project'
        canonical_root.mkdir()
        aliased_root = alias / 'project'
        for suffix in ('.glb', '.gltf'):
            with self.subTest(suffix=suffix):
                asset = asset_fixture(aliased_root, 'aliased-' + suffix[1:], suffix=suffix)
                report = validate_document(asset, aliased_root)
                self.assertTrue(report['payloads_verified'])
                self.assertTrue(report['geometry_inspected'])
                self.assertEqual(report, validate_document(asset, canonical_root))
                for record in asset['files']:
                    self.assertFalse(Path(record['path']).is_absolute())
                    self.assertEqual((aliased_root / record['path']).read_bytes(),
                                     (canonical_root / record['path']).read_bytes())
        self.assertTrue(alias.is_symlink())
        self.assertEqual(alias.readlink(), link_target)

    def test_obj_boundary_and_independent_glb_reader(self):
        from pygltflib import GLTF2
        from rig_import import load_character_model
        independent = GLTF2().load(str(self.root / 'fixture.glb'))
        vertex_count = sum(independent.accessors[p.attributes.POSITION].count
                           for mesh in independent.meshes for p in mesh.primitives)
        self.assertEqual(vertex_count, self.asset['measurements']['vertices'])
        obj = self.root / 'tetra.obj'
        obj.write_text('o tetra\nv 0 0 0\nv 1 0 0\nv 0 1 0\nv 0 0 1\n'
                       'f 1 3 2\nf 1 2 4\nf 1 4 3\nf 2 3 4\n', encoding='utf-8')
        model = load_character_model(obj)
        record = payload(self.root, 'tetra.obj', 'model/obj')
        doc = deepcopy(self.asset)
        doc.update(geometry=record, files=[record])
        doc['sources'][0]['file'] = record
        doc['parts'][0]['mesh_ids'] = [mesh.id for mesh in model.geometry.meshes]
        doc['measurements'] = dict(vertices=model.geometry.vertex_count, triangles=model.geometry.triangle_count,
                                   bounds=dict(minimum=model.report['bounds'][0], maximum=model.report['bounds'][1]))
        report = validate_document(doc, self.root)
        self.assertTrue(report['geometry_inspected'])
        self.assertEqual(report['geometry'][0]['inspection']['triangles'], 4)

    def test_structural_only_never_claims_verified_payload(self):
        (self.root / 'fixture.glb').unlink()
        report = validate_document(self.asset, structural_only=True)
        self.assertTrue(report['contract_valid'])
        self.assertFalse(report['payloads_verified'])
        self.assertFalse(report['geometry_inspected'])
        self.assertInvalid(self.asset, payloads=True)

    def test_missing_and_same_size_corrupt_payload(self):
        path = self.root / 'fixture.glb'
        original = path.read_bytes()
        path.write_bytes(b'x' + original[1:])
        self.assertInvalid(self.asset, 'MODEL3D_HASH', payloads=True)
        path.write_bytes(original + b'x')
        self.assertInvalid(self.asset, 'MODEL3D_SIZE', payloads=True)
        path.unlink()
        self.assertInvalid(self.asset, payloads=True)

    def test_hash_consistent_fake_mesh_is_rejected(self):
        (self.root / 'fixture.glb').write_bytes(b'not a real glb file')
        record = payload(self.root, 'fixture.glb', 'model/gltf-binary')
        self.asset.update(geometry=record, files=[record])
        self.asset['sources'][0]['file'] = record
        self.assertInvalid(self.asset, payloads=True)

    def test_actual_counts_bounds_and_mesh_bindings(self):
        for mutate in (lambda x: x['measurements'].update(vertices=1),
                       lambda x: x['measurements']['bounds'].update(maximum=[100, 100, 100]),
                       lambda x: x['parts'][0].update(mesh_ids=['imaginary'])):
            doc = deepcopy(self.asset)
            mutate(doc)
            self.assertInvalid(doc, payloads=True)

    def test_unknown_version_field_nonfinite_bool_and_duplicate_json(self):
        for mutate in (lambda x: x.update(schema_version=2), lambda x: x.update(secret=True),
                       lambda x: x.update(version='01.0.0'),
                       lambda x: x['measurements'].update(vertices=True),
                       lambda x: x['parts'][0]['local_transform'].update(translation=[float('nan'), 0, 0])):
            doc = deepcopy(self.asset)
            mutate(doc)
            self.assertInvalid(doc)
        for data in (b'{"kind":"model3d-asset","kind":"model3d-source"}', b'{"a":Infinity}'):
            with self.assertRaises(RigError):
                decode_json(data)

    def test_invalid_quaternion_scale_parent_cycle_and_dangling_references(self):
        for field, value in [('rotation', [0, 0, 0, 0]), ('rotation', [0, 0, 0, 2]),
                             ('scale', [0, 1, 1]), ('scale', [-1, 1, 1]), ('scale', [1e-12, 1, 1])]:
            doc = deepcopy(self.asset)
            doc['parts'][0]['local_transform'][field] = value
            self.assertInvalid(doc)
        for field, value in [('parent', 'missing'), ('parent', 'body'), ('source_ids', ['missing']),
                             ('material_ids', ['missing']), ('uncertainty_ids', ['missing'])]:
            doc = deepcopy(self.asset)
            doc['parts'][0][field] = value
            self.assertInvalid(doc)
        doc = deepcopy(self.asset)
        second = deepcopy(doc['parts'][0])
        second.update(id='second', parent='body', mesh_ids=[])
        doc['parts'][0]['parent'] = 'second'
        doc['parts'].append(second)
        self.assertInvalid(doc, 'MODEL3D_CYCLE')

    def test_path_traversal_aliases_and_conflicting_hash_records(self):
        for path in ('../escape', '/absolute', 'C:/drive', 'a\\b', 'a/../b', 'a//b', 'aux.txt', 'a. ', 'e\u0301.glb'):
            with self.subTest(path=path):
                doc = deepcopy(self.asset)
                doc['provenance']['evidence'] = [dict(doc['geometry'], path=path)]
                self.assertInvalid(doc)
        for record in (dict(self.asset['geometry'], sha256='0'*64),
                       dict(self.asset['geometry'], path='FIXTURE.GLB')):
            doc = deepcopy(self.asset)
            doc['provenance']['evidence'] = [record]
            self.assertInvalid(doc)

    def test_symlink_and_special_file_payload_rejected(self):
        target = self.root / 'fixture.glb'
        moved = self.root / 'actual.glb'
        target.rename(moved)
        try:
            target.symlink_to(moved)
        except OSError as exc:
            self.skipTest('Host cannot create symlinks: ' + str(exc))
        self.assertInvalid(self.asset, payloads=True)

    def test_actual_external_resource_must_be_in_inventory(self):
        doc = asset_fixture(self.root, 'external', suffix='.gltf')
        extra = next(r for r in doc['files'] if r['path'] != doc['geometry']['path'])
        doc['files'].remove(extra)
        # Another legitimate reference makes the bytes available to the snapshot,
        # but it must not conceal an incomplete runtime inventory.
        doc['provenance']['evidence'].append(extra)
        self.assertInvalid(doc, 'MODEL3D_INVENTORY', payloads=True)
        doc['provenance']['evidence'].clear()
        self.assertInvalid(doc, payloads=True)

    def test_recursive_dependency_closure_identity_and_budget(self):
        child = asset_fixture(self.root, 'child')
        child_record = write_document(self.root, 'child.json', child)
        self.asset['dependencies'] = [dict(id='child', version='1.0.0', manifest=child_record)]
        result = validate_document(self.asset, self.root)
        self.assertEqual(result['dependency_asset_count'], 1)
        self.assertEqual(len(result['geometry']), 2)
        self.asset['dependencies'][0]['version'] = '2.0.0'
        self.assertInvalid(self.asset, 'MODEL3D_REFERENCE', payloads=True)
        self.asset['dependencies'][0]['version'] = '1.0.0'
        self.asset['limits']['files'] = 2
        self.assertInvalid(self.asset, 'MODEL3D_BUDGET', payloads=True)

    def test_dependency_cycle_by_immutable_identity(self):
        # The root document is supplied directly, so self-referential byte hashes
        # are unnecessary: an alternate manifest cannot re-enter the active ID.
        alternate = deepcopy(self.asset)
        record = write_document(self.root, 'alternate.json', alternate)
        child = asset_fixture(self.root, 'child')
        child['dependencies'] = [dict(id='fixture', version='1.0.0', manifest=record)]
        child_record = write_document(self.root, 'child.json', child)
        self.asset['dependencies'] = [dict(id='child', version='1.0.0', manifest=child_record)]
        self.assertInvalid(self.asset, 'MODEL3D_CYCLE', payloads=True)

    def test_cached_dependency_depth_and_version_conflict(self):
        leaf = asset_fixture(self.root, 'leaf')
        leaf_record = write_document(self.root, 'leaf.json', leaf)
        child = asset_fixture(self.root, 'child')
        child['dependencies'] = [dict(id='leaf', version='1.0.0', manifest=leaf_record)]
        child_record = write_document(self.root, 'child.json', child)
        middle = asset_fixture(self.root, 'middle')
        middle['dependencies'] = [dict(id='child', version='1.0.0', manifest=child_record)]
        middle_record = write_document(self.root, 'middle.json', middle)
        self.asset['dependencies'] = [dict(id='child', version='1.0.0', manifest=child_record),
                                      dict(id='middle', version='1.0.0', manifest=middle_record)]
        self.asset['limits']['dependency_depth'] = 2
        self.assertInvalid(self.asset, 'MODEL3D_DEPTH', payloads=True)
        self.asset['limits']['dependency_depth'] = 3
        self.assertTrue(validate_document(self.asset, self.root)['geometry_inspected'])
        altered = deepcopy(leaf)
        altered['provenance']['description'] += ' Different manifest with the same immutable version.'
        altered_record = write_document(self.root, 'altered.json', altered)
        middle['dependencies'] = [dict(id='leaf', version='1.0.0', manifest=altered_record)]
        middle_record = write_document(self.root, 'middle.json', middle)
        self.asset['dependencies'][1]['manifest'] = middle_record
        self.assertInvalid(self.asset, 'MODEL3D_VERSION_CONFLICT', payloads=True)

    def test_child_depth_budget_is_not_weakened_by_root(self):
        leaf = asset_fixture(self.root, 'leaf')
        leaf_record = write_document(self.root, 'leaf.json', leaf)
        child = asset_fixture(self.root, 'child')
        child['dependencies'] = [dict(id='leaf', version='1.0.0', manifest=leaf_record)]
        child_record = write_document(self.root, 'child.json', child)
        middle = asset_fixture(self.root, 'middle')
        middle['dependencies'] = [dict(id='child', version='1.0.0', manifest=child_record)]
        middle['limits']['dependency_depth'] = 1
        middle_record = write_document(self.root, 'middle.json', middle)
        self.asset['dependencies'] = [dict(id='middle', version='1.0.0', manifest=middle_record)]
        self.assertInvalid(self.asset, 'MODEL3D_DEPTH', payloads=True)

    def test_fixture_and_review_claim_boundaries(self):
        doc = deepcopy(self.asset)
        doc['provenance'].update(origin='imported', fixture=False)
        self.assertInvalid(doc, 'MODEL3D_PROVENANCE')
        doc = deepcopy(self.asset)
        doc['review']['status'] = 'approved'
        self.assertInvalid(doc, 'MODEL3D_REVIEW')
        for item in [doc['provenance'], doc['sources'][0]['provenance']]:
            item.update(origin='imported', fixture=False)
        doc['review']['status'] = 'pending'
        self.assertInvalid(doc, 'MODEL3D_PROVENANCE', payloads=True)

    def test_budget_limits_and_duplicate_parts(self):
        doc = deepcopy(self.asset)
        doc['limits']['file_bytes'] = 1
        self.assertInvalid(doc, 'MODEL3D_BUDGET')
        doc = deepcopy(self.asset)
        doc['parts'].append(deepcopy(doc['parts'][0]))
        self.assertInvalid(doc, 'MODEL3D_DUPLICATE')

    def test_uncertainty_requires_evidence_not_invented_confidence(self):
        entry = dict(schema_version=1, kind='model3d-uncertainty', id='u', target='body',
                     classification='procedurally-inferred', message='Hidden surfaces were authored, not observed.',
                     evidence=['original'], confidence=None, confidence_method=None, status='pending')
        validate_contract(entry)
        entry['confidence'] = .9
        self.assertInvalid(entry, 'MODEL3D_CONFIDENCE')
        entry['confidence_method'] = 'documented numeric test'
        validate_contract(entry)
        entry['evidence'] = []
        self.assertInvalid(entry, 'MODEL3D_CONFIDENCE')

    def test_source_camera_does_not_invent_unknown_calibration(self):
        source = deepcopy(self.asset['sources'][0])
        source['camera']['projection'] = 'orthographic'
        self.assertInvalid(source, 'MODEL3D_CAMERA')
        source['camera'] = dict(status='supplied', projection='orthographic',
            camera_to_world=[1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1], image_size=[32,32],
            orthographic_size=[1,1], evidence=source['file'])
        validate_contract(source)
        source['camera']['camera_to_world'][0] = -1
        self.assertInvalid(source, 'MODEL3D_CAMERA')

    def test_material_color_space_and_unknown_fields(self):
        record = dict(self.asset['geometry'], path='color.png', media_type='image/png')
        material = dict(schema_version=1, kind='model3d-material', id='mat', version='1.0.0', name='Mat',
                        slot=0, base_color=[.5,.5,.5,1], metallic=0, roughness=.5,
                        alpha_mode='OPAQUE', alpha_cutoff=.5, double_sided=False,
                        textures=dict(normal=dict(file=record, texcoord=0, color_space='linear-data')),
                        provenance=provenance())
        validate_contract(material)
        material['textures']['normal']['color_space'] = 'srgb'
        self.assertInvalid(material, 'MODEL3D_COLOR_SPACE')

    def test_source_and_request_modality_boundaries(self):
        source = deepcopy(self.asset['sources'][0])
        source['file']['media_type'] = 'image/png'
        self.assertInvalid(source, 'MODEL3D_SOURCE')
        source = deepcopy(self.asset['sources'][0])
        source['role'] = 'front'
        self.assertInvalid(source, 'MODEL3D_SOURCE')
        request = request_fixture(self.asset['sources'])
        request['method'] = 'silhouette'
        self.assertInvalid(request, 'MODEL3D_SOURCE')

    def test_job_and_export_are_claims_not_execution(self):
        request_file = write_document(self.root, 'input.json', request_fixture(self.asset['sources']))
        job = dict(schema_version=1, kind='model3d-job', id='job', request=request_file, asset_id='fixture',
                   status='completed', attempts=1, maximum_attempts=2, outputs=[self.asset['geometry']],
                   error=None, dependencies=[], limits=deepcopy(LIMITS))
        result = validate_document(job, self.root)
        self.assertEqual(result['provider_execution'], 'not-assessed')
        self.assertFalse(result['geometry_inspected'])
        job['outputs'] = []
        self.assertInvalid(job, 'MODEL3D_JOB')
        job['status'] = 'failed'
        self.assertInvalid(job, 'MODEL3D_JOB')
        asset_file = write_document(self.root, 'asset.json', self.asset)
        export = dict(schema_version=1, kind='model3d-export', id='export',
                      asset=dict(id='fixture', version='1.0.0', manifest=asset_file), format='glb',
                      status='complete', files=[self.asset['geometry']], tools=[dict(name='native', version='1.0.0')],
                      losses=[], independent_inspection=None, limits=deepcopy(LIMITS))
        self.assertTrue(validate_document(export, self.root)['geometry_inspected'])
        export['files'] = []
        self.assertInvalid(export, 'MODEL3D_EXPORT')

    def test_request_schema_and_provider_isolation(self):
        request = request_fixture(self.asset['sources'])
        validate_contract(request)
        request['method'] = 'provider'
        self.assertInvalid(request, 'MODEL3D_PROVIDER')
        request['provider'] = dict(id='unconfigured', model=None, network_authorized=False)
        result = validate_document(request, self.root)
        self.assertEqual(result['provider_execution'], 'not-assessed')
        request['method'], request['provider'] = 'visual-hull', None
        self.assertInvalid(request, 'MODEL3D_CAMERA')

    def test_read_only_cli_and_missing_payload_exit(self):
        write_document(self.root, 'asset.json', self.asset)
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        command = [sys.executable, '-B', str(ROOT / 'scripts/model3d.py'), 'validate', '--file', str(self.root / 'asset.json')]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['geometry_inspected'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        (self.root / 'fixture.glb').unlink()
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stderr)['ok'])
        self.assertNotIn('Traceback', result.stderr)

    def test_image_format_and_decode_budget(self):
        from PIL import Image
        Image.new('RGB', (8, 8)).save(self.root / 'texture.png')
        source = deepcopy(self.asset['sources'][0])
        source.update(role='texture', file=payload(self.root, 'texture.png', 'image/png'))
        self.assertTrue(validate_document(source, self.root)['payloads_verified'])
        source['file']['media_type'] = 'image/jpeg'
        self.assertInvalid(source, 'MODEL3D_FORMAT', payloads=True)
        source['file']['media_type'] = 'image/png'
        self.asset['sources'].append(dict(source, id='texture'))
        self.asset['limits']['memory_bytes'] = 1
        self.assertInvalid(self.asset, 'MODEL3D_BUDGET', payloads=True)
        (self.root / 'texture.png').write_bytes(b'not an image')
        source['file'] = payload(self.root, 'texture.png', 'image/png')
        self.assertInvalid(source, 'MODEL3D_IMAGE', payloads=True)

    def test_job_request_must_be_a_matching_request_contract(self):
        reference = write_document(self.root, 'request.json', {'invented': 'success'})
        job = dict(schema_version=1, kind='model3d-job', id='job', request=reference, asset_id='fixture',
                   status='queued', attempts=0, maximum_attempts=1, outputs=[], error=None,
                   dependencies=[], limits=deepcopy(LIMITS))
        self.assertInvalid(job, 'MODEL3D_REFERENCE', payloads=True)
        request = request_fixture(self.asset['sources'])
        request['asset_id'] = 'different'
        job['request'] = write_document(self.root, 'request.json', request)
        self.assertInvalid(job, 'MODEL3D_REFERENCE', payloads=True)

    def test_malformed_model_has_structured_cli_failure(self):
        # Correct GLB header/chunk lengths do not establish valid glTF content.
        data = b'[]  '
        binary = struct.pack('<4sII', b'glTF', 2, 20 + len(data)) + struct.pack('<I4s', len(data), b'JSON') + data
        (self.root / 'fixture.glb').write_bytes(binary)
        record = payload(self.root, 'fixture.glb', 'model/gltf-binary')
        self.asset.update(geometry=record, files=[record])
        self.asset['sources'][0]['file'] = record
        write_document(self.root, 'asset.json', self.asset)
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/model3d.py'), 'validate',
                                 '--file', str(self.root / 'asset.json')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stderr)['ok'])
        self.assertNotIn('Traceback', result.stderr)

    def test_snapshot_is_not_mixed_with_later_source_edits(self):
        from rig_import import load_character_model
        path = self.root / 'fixture.glb'
        original = path.read_bytes()
        def inspect_snapshot(frozen, **kwargs):
            self.assertNotEqual(Path(frozen).parent, self.root)
            path.write_bytes(b'x' + original[1:])
            return load_character_model(frozen, **kwargs)
        with mock.patch('rig_import.load_character_model', side_effect=inspect_snapshot):
            report = validate_document(self.asset, self.root)
        self.assertTrue(report['geometry_inspected'])
        self.assertEqual(report['geometry'][0]['geometry_sha256'], hashlib.sha256(original).hexdigest())
        self.assertInvalid(self.asset, 'MODEL3D_HASH', payloads=True)

    def test_concurrent_readers_and_fresh_directory_restoration(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: validate_document(self.asset, self.root), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        with tempfile.TemporaryDirectory() as directory:
            fresh = Path(directory)
            for record in results[0]['files']:
                destination = fresh / record['path']
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes((self.root / record['path']).read_bytes())
            write_document(fresh, 'asset.json', self.asset)
            restored = validate_file(fresh / 'asset.json')
            self.assertEqual(restored, results[0])
            (fresh / self.asset['geometry']['path']).unlink()
            with self.assertRaises(RigError):
                validate_file(fresh / 'asset.json')

    def test_schema_discovery_does_not_import_numpy(self):
        command = [sys.executable, '-B', '-c',
                   'import sys;sys.path.insert(0,' + repr(str(ROOT / 'scripts')) + ');'
                   'import model3d_contracts;model3d_contracts.schemas();assert "numpy" not in sys.modules']
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
