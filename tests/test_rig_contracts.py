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
