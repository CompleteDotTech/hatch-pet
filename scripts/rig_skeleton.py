"""Editable arbitrary skeletons, exact FK and explicit rest/pose boundaries."""
from __future__ import annotations

from copy import deepcopy
import numpy as np
from rig_contracts import DEFAULT_LIMITS, validate_contract
from rig_errors import require
from rig_math import (IDENTITY_Q, bone_matrix, decompose, qmul, quaternion,
                      transform_matrix, transform_points, vector)


def hierarchy_order(skeleton: dict) -> list[str]:
    bones = skeleton['bones']
    index = {b['id']: b for b in bones}
    require(len(index) == len(bones) and bool(bones), 'RIG_DUPLICATE_BONE', 'Skeleton needs unique bone IDs.')
    roots = [b['id'] for b in bones if b['parent'] is None]
    require(roots == [skeleton['root']], 'RIG_ROOT', 'Exactly one declared skeleton root is required.', observed=roots)
    result, active, done = [], set(), set()

    def visit(name: str):
        require(name in index, 'RIG_PARENT', 'Missing parent bone: ' + str(name))
        require(name not in active, 'RIG_HIERARCHY_CYCLE', 'Skeleton hierarchy contains a cycle.', asset=name)
        if name in done:
            return
        active.add(name)
        parent = index[name]['parent']
        if parent is not None:
            visit(parent)
        active.remove(name); done.add(name); result.append(name)

    for name in index:
        visit(name)
    return result


def evaluate_fk(skeleton: dict, pose: dict | None = None) -> dict[str, np.ndarray]:
    """Evaluate absolute local TRS overrides; omitted properties use the rest pose."""
    bones = {b['id']: b for b in skeleton['bones']}
    overrides = (pose or {}).get('bones', {})
    require(set(overrides) <= set(bones), 'RIG_POSE_REFERENCE', 'Pose targets a missing bone.')
    result = {}
    for name in hierarchy_order(skeleton):
        bone = bones[name]
        local = dict(bone['rest'])
        local.update(overrides.get(name, {}))
        quaternion(local['rotation'], strict=True)
        transform = transform_matrix(local)
        result[name] = result[bone['parent']] @ transform if bone['parent'] else transform
        require(np.isfinite(result[name]).all(), 'RIG_NONFINITE', 'Evaluated transform is nonfinite.', asset=name)
    return result


def validate_skeleton(skeleton: dict, limits=None) -> dict:
    validate_contract(skeleton, 'Skeleton')
    require(len(skeleton['bones']) <= (limits or DEFAULT_LIMITS)['bones'], 'RIG_LIMIT_BONES', 'Bone budget exceeded.')
    world = evaluate_fk(skeleton)
    bones = {b['id']: b for b in skeleton['bones']}
    for bone in bones.values():
        name = bone['id']
        head, tail = vector(bone['head']), vector(bone['tail'])
        length = float(np.linalg.norm(tail-head))
        require(length > 1e-8 and abs(length-bone['length']) <= 1e-6 * max(1., length),
                'RIG_BONE_LENGTH', 'Bone length must match distinct head/tail positions.', asset=name)
        require(np.allclose(world[name][:3, 3], head, atol=1e-6), 'RIG_REST_MISMATCH',
                'Local rest transforms do not reconstruct the declared head.', asset=name)
        decompose(world[name])
        mirror = bone['mirror']
        require(mirror is None or (mirror in bones and mirror != name and bones[mirror]['mirror'] == name),
                'RIG_MIRROR', 'Mirror partners must exist and be reciprocal.', asset=name)
    return dict(bones=len(bones), roots=1, cycles=0, finite_transforms=True)


def skeleton_from_heads(specs: list[dict], *, identifier='skeleton', version='1.0.0',
                        source='geometry-fit', reference='Template fitted to geometry bounds', confidence=.45) -> dict:
    require(bool(specs), 'RIG_NO_BONES', 'A template must supply bones.')
    worlds = {b['id']: bone_matrix(b['head'], b['tail'], b.get('roll', 0)) for b in specs}
    bones = []
    for spec in specs:
        parent = spec['parent']
        require(parent is None or parent in worlds, 'RIG_PARENT', 'Template parent is missing.')
        local = np.linalg.inv(worlds[parent]) @ worlds[spec['id']] if parent else worlds[spec['id']]
        bones.append(dict(schema_version=1, id=spec['id'], role=spec['role'], parent=parent,
                          rest=decompose(local), head=list(map(float, spec['head'])),
                          tail=list(map(float, spec['tail'])), length=float(np.linalg.norm(vector(spec['tail'])-vector(spec['head']))),
                          roll=float(spec.get('roll', 0)), deform=spec.get('deform', True), mirror=spec.get('mirror'),
                          evidence=dict(source=source, reference=reference, confidence=confidence)))
    roots = [b['id'] for b in bones if b['parent'] is None]
    require(len(roots) == 1, 'RIG_ROOT', 'Template must have exactly one root.')
    result = dict(schema_version=1, id=identifier, version=version, root=roots[0], bones=bones)
    validate_skeleton(result)
    return result


def neutral_pose(skeleton: dict, identifier='neutral') -> dict:
    return dict(schema_version=1, kind='hatch-3d-pose', id=identifier, rig_version=skeleton['version'], bones={}, morphs={})


def rotate_bone(skeleton: dict, pose: dict, bone_id: str, delta) -> dict:
    """Set a rotation relative to rest, without accumulating previous calls."""
    result = deepcopy(pose)
    bone = next((b for b in skeleton['bones'] if b['id'] == bone_id), None)
    require(bone is not None, 'RIG_POSE_REFERENCE', 'Bone does not exist: ' + bone_id)
    result['bones'].setdefault(bone_id, {})['rotation'] = quaternion(qmul(bone['rest']['rotation'], delta)).tolist()
    return result


def bone_tail(skeleton: dict, name: str, world: dict, rest: dict | None = None) -> np.ndarray:
    rest = rest or evaluate_fk(skeleton)
    bone = next(b for b in skeleton['bones'] if b['id'] == name)
    local = transform_points(np.linalg.inv(rest[name]), np.array([bone['tail']]))
    return transform_points(world[name], local)[0]


def inspect_skeleton(skeleton: dict, pose=None) -> list[dict]:
    rest, world = evaluate_fk(skeleton), evaluate_fk(skeleton, pose)
    return [dict(id=b['id'], role=b['role'], parent=b['parent'], local_rest=b['rest'],
                 world_rest=rest[b['id']].tolist(), world_pose=world[b['id']].tolist(),
                 head=world[b['id']][:3, 3].tolist(), tail=bone_tail(skeleton, b['id'], world, rest).tolist(),
                 deform=b['deform'], evidence=b['evidence']) for b in skeleton['bones']]


def mirror_pose(skeleton: dict, pose: dict, *, approved: bool = False) -> dict:
    require(approved, 'RIG_MIRROR_APPROVAL', 'Mirroring requires explicit symmetry approval.')
    world, rest = evaluate_fk(skeleton, pose), evaluate_fk(skeleton)
    reflection = np.diag([-1., 1., 1., 1.])
    bones = {b['id']: b for b in skeleton['bones']}
    target_world = {}
    for name in hierarchy_order(skeleton):
        source = bones[name]['mirror'] or name
        delta = world[source] @ np.linalg.inv(rest[source])
        target_world[name] = reflection @ delta @ reflection @ rest[name]
    result = neutral_pose(skeleton, pose.get('id', 'pose')+'-mirrored')
    result['morphs'] = deepcopy(pose.get('morphs', {}))
    for name in hierarchy_order(skeleton):
        parent = bones[name]['parent']
        local = np.linalg.inv(target_world[parent]) @ target_world[name] if parent else target_world[name]
        result['bones'][name] = decompose(local)
    return result
