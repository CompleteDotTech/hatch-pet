"""Independent coordinate expectations and malformed-transform regression tests."""
from copy import deepcopy
import math
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from rig_errors import RigError
from rig_math import (BLENDER_FROM_CANONICAL, axis_angle, compose, decompose, qbetween,
                      qmatrix, quaternion, slerp, transform_points)
from rig_skeleton import evaluate_fk, neutral_pose, rotate_bone, skeleton_from_heads, validate_skeleton


def chain_skeleton(count=3):
    return skeleton_from_heads([dict(id=f'b{i}', role=f'joint-{i}', parent=f'b{i-1}' if i else None,
        head=[0, i, 0], tail=[0, i+1, 0], deform=True) for i in range(count)],
        source='procedural-fixture', reference='Independent unit chain', confidence=1.)


class RigMathTests(unittest.TestCase):
    def test_column_vector_transform_against_literal_matrix(self):
        expected = np.array([[0, -3, 0, 4], [2, 0, 0, 5], [0, 0, 4, 6], [0, 0, 0, 1.]])
        actual = compose([4, 5, 6], [0, 0, math.sqrt(.5), math.sqrt(.5)], [2, 3, 4])
        np.testing.assert_allclose(actual, expected, atol=1e-12)
        np.testing.assert_allclose(transform_points(actual, np.array([[1, 2, 3.]])), [[-2, 7, 18]], atol=1e-12)

    def test_blender_conversion_is_proper_and_reversible(self):
        np.testing.assert_allclose(transform_points(BLENDER_FROM_CANONICAL, np.array([[1, 2, 3.]])), [[1, -3, 2]])
        self.assertAlmostEqual(np.linalg.det(BLENDER_FROM_CANONICAL), 1)

    def test_slerp_handles_opposite_sign_and_half_angle(self):
        q = slerp([0, 0, 0, 1], [0, 0, 1, 0], .5)
        np.testing.assert_allclose(qmatrix(q) @ [1, 0, 0], [0, 1, 0], atol=1e-12)
        np.testing.assert_allclose(slerp(q, -q, .2), q, atol=1e-12)

    def test_antiparallel_rotation_is_finite_and_exact(self):
        np.testing.assert_allclose(qmatrix(qbetween([0, 1, 0], [0, -1, 0])) @ [0, 1, 0], [0, -1, 0], atol=1e-12)

    def test_invalid_transforms_fail_closed(self):
        for q in ([0, 0, 0, 0], [float('nan'), 0, 0, 1]):
            with self.assertRaises(RigError):quaternion(q)
        with self.assertRaises(RigError):compose(scale=[1, 0, 1])
        shear = np.eye(4);shear[0, 1] = .3
        with self.assertRaises(RigError):decompose(shear)

    def test_fk_parent_rotation_propagates_without_mutation(self):
        skeleton = chain_skeleton();saved = deepcopy(skeleton)
        pose = rotate_bone(skeleton, neutral_pose(skeleton), 'b0', axis_angle([0, 0, 1], math.pi/2))
        world = evaluate_fk(skeleton, pose)
        np.testing.assert_allclose(world['b2'][:3, 3], [-2, 0, 0], atol=1e-12)
        self.assertEqual(skeleton, saved)
        np.testing.assert_allclose(evaluate_fk(skeleton)['b2'][:3, 3], [0, 2, 0])

    def test_duplicate_cycle_missing_parent_and_false_head_are_rejected(self):
        for mutate in (lambda s:s['bones'].append(deepcopy(s['bones'][0])),
                       lambda s:s['bones'][1].update(parent='b2'),
                       lambda s:s['bones'][2].update(parent='missing'),
                       lambda s:s['bones'][1].update(head=[7, 7, 7])):
            skeleton = chain_skeleton();mutate(skeleton)
            with self.assertRaises(RigError):validate_skeleton(skeleton)

    def test_seeded_random_trees_reconstruct_independent_translations(self):
        rng = np.random.default_rng(6381)
        for _ in range(20):
            heads = rng.normal(size=(20, 3))
            specs = [dict(id=f'b{i}', role=f'part-{i}', parent=None if i == 0 else f'b{rng.integers(i)}',
                          head=head.tolist(), tail=(head+[0, .3, 0]).tolist()) for i, head in enumerate(heads)]
            skeleton = skeleton_from_heads(specs)
            world = evaluate_fk(skeleton)
            np.testing.assert_allclose(np.array([world[f'b{i}'][:3, 3] for i in range(20)]), heads, atol=1e-10)
