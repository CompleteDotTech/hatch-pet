"""Contract boundaries exercised with real meshes and retained adapter evidence."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator
from pygltflib import GLTF2

from rig_test_helpers import fixture
from rig_contracts import schemas, validate_contract
from rig_errors import RigError, sha256
from rig_gltf import export_gltf
from rig_ik import solve_ik, validate_chain
from rig_jobs import save_rig
from rig_models import load_rig
from rig_skeleton import neutral_pose, skeleton_from_heads
from rig_skinning import generate_skin_weights
from rig_validation import validate_rig

ROOT = Path(__file__).resolve().parents[1]


class RigContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rig = fixture(self.root)

    def malformed_controllers(self):
        original = self.rig.manifest['controllers']
        missing = deepcopy(original)
        missing['ik'][0]['bones'][-1] = 'missing'
        duplicate = deepcopy(original)
        duplicate['ik'].append(deepcopy(duplicate['ik'][0]))
        disconnected = deepcopy(original)
        disconnected['ik'][0]['bones'] = ['b0', 'b2', 'b1']
        repeated_bone = deepcopy(original)
        repeated_bone['ik'][0]['bones'] = ['b0', 'b1', 'b1']
        invalid_orientation = deepcopy(original)
        invalid_orientation['ik'][0]['orientation'] = [0, 0, 0, 0]
        return {'missing-bone': missing, 'duplicate-id': duplicate,
                'disconnected-chain': disconnected, 'repeated-bone': repeated_bone,
                'invalid-orientation': invalid_orientation}

    def test_unused_controller_declarations_are_structurally_validated(self):
        # The clips have no contacts, so no solver invocation could accidentally
        # supply validation for these otherwise unused declarations.
        self.assertTrue(all(not clip['contacts'] for clip in self.rig.clips.values()))
        self.assertTrue(validate_rig(self.rig)['ok'])
        for name, controllers in self.malformed_controllers().items():
            with self.subTest(name=name):
                invalid = deepcopy(self.rig)
                invalid.manifest['controllers'] = controllers
                report = validate_rig(invalid)
                self.assertFalse(report['ok'])
                self.assertEqual(report['checks'][0]['name'], 'structure')
                self.assertEqual(report['checks'][0]['status'], 'failed')

    def test_export_rejects_invalid_controllers_before_writing(self):
        output = self.root / 'preserved.glb'
        output.write_bytes(b'previous output remains intact')
        original = output.read_bytes()
        for name, controllers in self.malformed_controllers().items():
            with self.subTest(name=name):
                invalid = deepcopy(self.rig)
                invalid.manifest['controllers'] = controllers
                with self.assertRaises(RigError):
                    export_gltf(invalid, output)
                self.assertEqual(output.read_bytes(), original)

    def chain_fixture(self, solver, segment_length):
        root = self.root / f'{solver}-{segment_length}'
        rig = fixture(root, animated=False)
        # Every authored bone is one meter long. The IK segments are the
        # distances between evaluated joint origins, which can still collapse.
        rig.manifest['skeleton'] = skeleton_from_heads([
            dict(id=f'b{i}', role=f'joint-{i}', parent=f'b{i-1}' if i else None,
                 head=[0, i * segment_length, 0],
                 tail=[0, i * segment_length + 1, 0], deform=True)
            for i in range(3)
        ], source='procedural-fixture', reference='IK segment boundary fixture', confidence=1.)
        rig.manifest['controllers']['ik'][0]['solver'] = solver
        rig.weights = generate_skin_weights(rig.geometry, rig.skeleton)
        save_rig(rig, operation='test-ik-segment-boundary')
        return load_rig(rig.root)

    def test_unused_chains_reject_unmeasurable_rest_segments_before_export(self):
        for solver in ('two-bone', 'fabrik'):
            for length in (0., 1e-9, 1e-8):
                with self.subTest(solver=solver, segment_length=length):
                    rig = self.chain_fixture(solver, length)
                    self.assertFalse(rig.clips)
                    report = validate_rig(rig)
                    self.assertFalse(report['ok'])
                    self.assertEqual(report['checks'][0]['name'], 'structure')
                    self.assertEqual(report['checks'][0]['status'], 'failed')
                    chain = rig.manifest['controllers']['ik'][0]
                    with self.assertRaises(RigError) as error:
                        validate_chain(rig.skeleton, chain)
                    self.assertEqual(error.exception.report['code'], 'RIG_IK_LENGTH')
                    for extension in ('glb', 'gltf'):
                        output = rig.root / ('preserved.' + extension)
                        original = b'previous output remains intact'
                        output.write_bytes(original)
                        with self.assertRaises(RigError) as error:
                            export_gltf(rig, output)
                        self.assertEqual(error.exception.report['code'], 'RIG_IK_LENGTH')
                        self.assertEqual(output.read_bytes(), original)

    def test_measurable_chain_boundaries_remain_usable(self):
        for solver in ('two-bone', 'fabrik'):
            for length in (1.01e-8, 1.):
                with self.subTest(solver=solver, segment_length=length):
                    rig = self.chain_fixture(solver, length)
                    self.assertFalse(rig.clips)
                    self.assertTrue(validate_rig(rig)['ok'])
                    chain = rig.manifest['controllers']['ik'][0]
                    solved = solve_ik(rig.skeleton, neutral_pose(rig.skeleton),
                                      chain, [0, 2 * length, 0])
                    self.assertTrue(solved.converged, solved.report())
                    for extension in ('glb', 'gltf'):
                        output = rig.root / ('accepted.' + extension)
                        receipt = export_gltf(rig, output)
                        self.assertEqual(receipt['sha256'], sha256(output))

    def test_runtime_pose_keeps_segment_length_guard(self):
        for solver in ('two-bone', 'fabrik'):
            chain = deepcopy(self.rig.manifest['controllers']['ik'][0])
            chain['solver'] = solver
            validate_chain(self.rig.skeleton, chain)
            for bone in ('b1', 'b2'):
                for length in (0., 1e-9, 1e-8):
                    with self.subTest(solver=solver, bone=bone, segment_length=length):
                        pose = neutral_pose(self.rig.skeleton)
                        pose['bones'][bone] = {'translation': [0, length, 0]}
                        with self.assertRaises(RigError) as error:
                            solve_ik(self.rig.skeleton, pose, chain, [0, 2, 0])
                        self.assertEqual(error.exception.report['code'], 'RIG_IK_LENGTH')

    def test_real_glb_and_gltf_receipts_match_published_schema_and_bytes(self):
        schema = schemas()['rig-export.schema.json']
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        for extension in ('glb', 'gltf'):
            with self.subTest(extension=extension):
                output = self.root / ('character.' + extension)
                receipt = export_gltf(self.rig, output)
                validator.validate(receipt)
                self.assertIs(validate_contract(receipt, 'RigExportReceipt'), receipt)
                self.assertEqual(receipt['sha256'], sha256(output))
                self.assertEqual(receipt['format'], extension)
                self.assertFalse(receipt['independently_verified'])
                imported = GLTF2().load(str(output))
                self.assertEqual(len(imported.skins), receipt['skins'])
                self.assertEqual([clip.name for clip in imported.animations], receipt['animations'])
                self.assertIsNotNone(imported.meshes[0].primitives[0].attributes.JOINTS_0)
                self.assertGreater(len(imported.animations[0].channels), 0)

    def test_export_receipt_rejects_unknown_fields_and_unearned_verification(self):
        receipt = export_gltf(self.rig, self.root / 'receipt.glb')
        mutations = [lambda r: r.update(extra=True),
                     lambda r: r.update(independently_verified=True),
                     lambda r: r.update(format='obj'),
                     lambda r: r.update(sha256='not-a-hash'),
                     lambda r: r.update(schema_version=2),
                     lambda r: r.update(joints=0)]
        for mutate in mutations:
            invalid = deepcopy(receipt)
            mutate(invalid)
            with self.assertRaises(RigError):
                validate_contract(invalid, 'RigExportReceipt')
        with self.assertRaises(RigError):
            validate_contract(validate_rig(self.rig), 'RigExportReceipt')

    def test_retained_blender_report_contract_requires_reopen_evidence(self):
        # This is schema coverage of retained real Blender output, not a new
        # Blender execution. Opt-in integration tests execute both modes.
        path = ROOT / 'examples/rig-3d/robotic/validation/blender.json'
        receipt = json.loads(path.read_text())
        receipt.update(schema_version=1, format='blend')
        validate_contract(receipt, 'RigExportReceipt')
        validator = Draft202012Validator(schemas()['rig-export.schema.json'])
        validator.validate(receipt)
        for field in ('roundtrip_sha256', 'roundtrip_path', 'compared_vertices',
                      'max_vertex_error_m', 'max_joint_error_m', 'tolerance_m'):
            invalid = deepcopy(receipt)
            invalid.pop(field)
            with self.subTest(missing=field), self.assertRaises(RigError):
                validate_contract(invalid, 'RigExportReceipt')
        invalid = deepcopy(receipt)
        invalid['reopened'] = False
        with self.assertRaises(RigError):
            validate_contract(invalid, 'RigExportReceipt')
