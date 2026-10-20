"""Tests require actual vertex movement and reject removed/corrupt bindings."""
from copy import deepcopy
import math
from pathlib import Path
import tempfile
import unittest
import numpy as np

from test_rig_math import chain_skeleton
from rig_errors import RigError
from rig_math import axis_angle
from rig_models import Geometry, Mesh, RigAsset, SkinWeights, load_geometry, load_weights, save_geometry, save_weights
from rig_skeleton import evaluate_fk, neutral_pose, rotate_bone
from rig_skinning import (copy_weights, edit_weights, evaluate_deformation, generate_skin_weights,
                          smooth_weights, validate_skin)


def test_geometry():
    return Geometry([Mesh('strip', np.array([[.1, 0, 0], [-.1, 0, 0], [.1, 2, 0], [-.1, 2, 0.]]),
                          np.array([[0, 1, 2], [1, 3, 2]]))], [dict(name='fixture')])


def bound_fixture():
    skeleton = chain_skeleton(2);geometry = test_geometry()
    world = evaluate_fk(skeleton)
    skin = SkinWeights('strip', ['b0', 'b1'], np.array([[0, 0, 0, 0], [0, 0, 0, 0], [1, 0, 0, 0], [1, 0, 0, 0]], dtype=np.uint16),
                       np.array([[1, 0, 0, 0.]]*4), np.array([np.linalg.inv(world['b0']), np.linalg.inv(world['b1'])]))
    return RigAsset({'skeleton': skeleton}, geometry, {'strip': skin})


class RigSkinningTests(unittest.TestCase):
    def test_known_pivot_rotation_moves_real_vertices(self):
        rig = bound_fixture()
        pose = rotate_bone(rig.skeleton, neutral_pose(rig.skeleton), 'b1', axis_angle([0, 0, 1], math.pi/2))
        vertices = evaluate_deformation(rig, pose)['strip']['positions']
        np.testing.assert_allclose(vertices[2], [-1, 1.1, 0], atol=1e-12)
        np.testing.assert_allclose(vertices[:2], rig.geometry.meshes[0].positions[:2], atol=1e-12)
        self.assertGreater(np.linalg.norm(vertices-rig.geometry.meshes[0].positions), 1)

    def test_bind_pose_reconstructs_geometry(self):
        rig = bound_fixture();report = validate_skin(rig.weights['strip'], rig.geometry.meshes[0], rig.skeleton)
        self.assertLess(report['inverse_bind_max_error'], 1e-12)
        np.testing.assert_allclose(evaluate_deformation(rig)['strip']['positions'], rig.geometry.meshes[0].positions)

    def test_removed_skin_and_zero_weights_cannot_pass(self):
        rig = bound_fixture();rig.weights = {}
        with self.assertRaises(RigError):evaluate_deformation(rig)
        rig = bound_fixture();rig.weights['strip'].weights[:] = 0
        with self.assertRaises(RigError):validate_skin(rig.weights['strip'], rig.geometry.meshes[0], rig.skeleton)

    def test_wrong_joint_matrix_nonfinite_and_negative_weights_fail(self):
        for change in (lambda s:s.indices.__setitem__((0, 0), 9),
                       lambda s:s.weights.__setitem__((0, 0), -.1),
                       lambda s:s.weights.__setitem__((0, 0), np.nan),
                       lambda s:s.inverse_bind.__setitem__((0, 0, 3), 1)):
            rig = bound_fixture();change(rig.weights['strip'])
            with self.assertRaises(RigError):validate_skin(rig.weights['strip'], rig.geometry.meshes[0], rig.skeleton)

    def test_diffusion_distance_rigid_and_locked_manual_weights(self):
        geometry = test_geometry();skeleton = chain_skeleton(2)
        for method in ('distance', 'diffusion', 'rigid'):
            weights = generate_skin_weights(geometry, skeleton, method=method)
            self.assertLess(validate_skin(weights['strip'], geometry.meshes[0], skeleton)['weight_sum_max_error'], 1e-12)
        weight = edit_weights(weights['strip'], {0: {'b1': 1}})
        updated = generate_skin_weights(geometry, skeleton, previous={'strip': weight})['strip']
        self.assertEqual(updated.joints[int(updated.indices[0, 0])], 'b1')
        self.assertEqual(updated.locked.tolist(), [0])
        copied = copy_weights(updated, {1: 0})
        smoothed = smooth_weights(geometry.meshes[0], copied)
        np.testing.assert_allclose(smoothed.weights[0], copied.weights[0])

    def test_actual_morph_delta_is_applied_before_skinning(self):
        rig = bound_fixture();mesh = rig.geometry.meshes[0]
        delta = np.zeros_like(mesh.positions);delta[:, 2] = .4
        mesh.morphs['expression'] = {'POSITION': delta}
        pose = neutral_pose(rig.skeleton);pose['morphs'] = {'strip': {'expression': .5}}
        np.testing.assert_allclose(evaluate_deformation(rig, pose)['strip']['positions'][:, 2], [.2]*4)

    def test_portable_binary_roundtrip_and_tamper_detection(self):
        rig = bound_fixture()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            descriptor = save_geometry(root, rig.geometry)
            duplicate = save_geometry(root, rig.geometry)
            self.assertEqual(descriptor, duplicate)
            np.testing.assert_allclose(load_geometry(root, descriptor).meshes[0].positions, rig.geometry.meshes[0].positions)
            descriptor = save_weights(root, rig.weights['strip'])
            np.testing.assert_allclose(load_weights(root, descriptor).weights, rig.weights['strip'].weights)
            (root/descriptor['data']['path']).write_bytes(b'corrupt')
            with self.assertRaises(RigError):load_weights(root, descriptor)
