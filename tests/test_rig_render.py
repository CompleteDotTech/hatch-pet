from pathlib import Path
import tempfile
import unittest
import numpy as np
from rig_test_helpers import fixture
from rig_render import render_rig_preview,render_frame_sequence
from rig_errors import RigError,sha256


class RigRenderTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.rig=fixture(self.temp.name)
    def test_rasterized_geometry_changes_and_transparent_background_is_real(self):
        a=np.asarray(render_rig_preview(self.rig,clip='bend',time=0,width=128,height=128,transparent=True,camera='front'))
        b=np.asarray(render_rig_preview(self.rig,clip='bend',time=.5,width=128,height=128,transparent=True,camera='front'))
        self.assertGreater(np.count_nonzero(a[:,:,3]),50);self.assertGreater(np.count_nonzero(a[:,:,3]==0),100)
        self.assertGreater(np.count_nonzero(a!=b),50)
    def test_frame_bridge_retains_camera_timing_provenance_and_hashes(self):
        root=Path(self.temp.name)/'frames';report=render_frame_sequence(self.rig,root,clip='bend',fps=4,width=64,height=64)
        self.assertEqual(len(report['frames']),4);self.assertAlmostEqual(sum(f['duration'] for f in report['frames']),1.)
        self.assertTrue(report['fixture']);self.assertTrue(report['transparent']);self.assertEqual(report['review_status'],'pending')
        for frame in report['frames']:self.assertEqual(sha256(root/frame['path']),frame['sha256'])
        self.assertTrue((root/'animation.webp').is_file())
    def test_frame_memory_budget_fails_before_allocation(self):
        self.rig.manifest['limits']['memory_bytes']=4096
        with self.assertRaises(RigError):render_frame_sequence(self.rig,Path(self.temp.name)/'big',clip='bend',fps=60,width=2048,height=2048)
