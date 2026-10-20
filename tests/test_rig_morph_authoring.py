from copy import deepcopy
import tempfile
import unittest
import numpy as np
from rig_test_helpers import fixture
from rig_facial import create_morph_target,edit_morph_target,expression_catalog,apply_expressions
from rig_skeleton import neutral_pose
from rig_errors import RigError,timestamp
from rig_corrections import apply_rig_corrections
from rig_models import rig_signature,load_rig


class RigMorphAuthoringTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.rig=fixture(self.temp.name)
    def test_create_and_edit_preserve_base_and_exact_topology(self):
        mesh=self.rig.geometry.meshes[0];base=mesh.positions.copy();delta=np.zeros_like(base);delta[2,2]=.15
        target=create_morph_target(mesh,'smile',deltas=delta);self.assertNotIn('smile',mesh.morphs)
        np.testing.assert_array_equal(target.positions,base);self.assertAlmostEqual(target.morphs['smile']['POSITION'][2,2],.15)
        edited=edit_morph_target(target,'smile',{2:[0,0,.2]});self.assertAlmostEqual(edited.morphs['smile']['POSITION'][2,2],.2)
        with self.assertRaises(RigError):create_morph_target(mesh,'bad',deltas=[[0,0,0]])
    def test_visemes_and_semantic_controls_require_real_authored_targets(self):
        r=self.rig;mesh=r.geometry.meshes[0];r.geometry.meshes[0]=create_morph_target(mesh,'viseme_aa',deltas=np.zeros_like(mesh.positions))
        report=expression_catalog(r);self.assertEqual(report['availability']['viseme-aa']['status'],'available')
        self.assertEqual(report['availability']['smile']['status'],'unavailable');self.assertFalse(report['automatic_geometry_generation'])
        self.assertEqual(len(report['visemes']),15)
    def test_left_right_expression_qualification_does_not_affect_other_meshes(self):
        r=self.rig;other=deepcopy(r.geometry.meshes[0]);other.id='other-eye';r.geometry.meshes.append(other)
        r.manifest['facial']['expressions']['wink']=dict(schema_version=1,morphs={'strip::blink':1.},bones={},incompatible=[])
        result=apply_expressions(r,neutral_pose(r.skeleton),{'wink':.7});self.assertIn('strip',result['morphs']);self.assertNotIn('other-eye',result['morphs'])
    def test_morph_correction_versions_derived_geometry_and_preserves_source(self):
        r=self.rig;before=r.manifest['source']['sha256'];version=r.manifest['geometry']['version']
        correction=dict(schema_version=1,kind='hatch-3d-rig-correction',rig_id=r.manifest['id'],rig_version=r.manifest['version'],
            expected_sha256=rig_signature(r.manifest),author='fixture',reason='Edit actual morph vertices',created_at=timestamp(),
            edits=[dict(operation='morph',target='strip',value=dict(action='edit',name='blink',assignments={'0':[0,0,.3]}))])
        updated,_=apply_rig_corrections(r,correction);self.assertNotEqual(updated.manifest['geometry']['version'],version)
        self.assertEqual(load_rig(r.root).manifest['source']['sha256'],before);self.assertTrue(updated.weights)
    def test_neutral_face_releases_authored_controls_and_preserves_body_morph(self):
        r=self.rig;r.manifest['facial']['expressions']['blink']=dict(schema_version=1,morphs={'blink':1.},bones={},incompatible=[])
        pose=apply_expressions(r,neutral_pose(r.skeleton),{'blink':1.})
        pose['morphs']['strip']['body-shape']=.4
        neutral=apply_expressions(r,pose,{})
        self.assertNotIn('blink',neutral['morphs']['strip']);self.assertEqual(neutral['morphs']['strip']['body-shape'],.4)
