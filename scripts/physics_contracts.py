"""Strict, additive physics v1 data contracts; no solver is imported or executed.

JSON Schema supplies structural bounds. Runtime validation additionally checks
reference closure, exact time, geometry, control authority and aggregate budgets.
The existence of a configuration or cache manifest never proves solver support.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
from functools import lru_cache
import argparse
import copy
import json
import math
import os
import stat
import unicodedata
from pathlib import Path
from typing import Any

from rig_contracts import COORDINATES, arr, obj, ref
from rig_errors import RigError, decode_json, finite_json, object_hash, portable_name

VERSION = '1.0.0'
CATEGORIES = ('rigid-body', 'character', 'cloth', 'soft-body', 'hair', 'particles', 'gas', 'liquid', 'fracture')
PHYSICAL_UNITS = dict(mass='kilogram', force='newton', torque='newton-meter',
                      velocity='meter/second', angular_velocity='radian/second', density='kilogram/meter^3')
DEFAULT_GRAVITY = [0., -9.81, 0.]


@dataclass(frozen=True)
class Diagnostic:
    """Typed failure details; diagnostic success does not grant visual approval."""
    code: str
    message: str
    path: str = ''
    category: str = 'invalid-input'
    retryable: bool = False


class PhysicsError(ValueError):
    def __init__(self, code: str, message: str, path: str = '', *, category='invalid-input'):
        super().__init__(message)
        self.diagnostic = Diagnostic(code, message, path, category)
        self.report = asdict(self.diagnostic)


def require(condition: bool, code: str, message: str, path: str = '') -> None:
    if not condition:
        raise PhysicsError(code, message, path)


@lru_cache(maxsize=1)
def definitions() -> dict:
    # Bounds protect validation itself as well as future admission. Version 1
    # deliberately has no untyped backend-options dictionary.
    text = dict(type='string', minLength=1, maxLength=1024)
    identifier = dict(type='string', pattern=r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$')
    version = dict(type='string', pattern=r'^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$')
    digest = dict(type='string', pattern=r'^[0-9a-f]{64}$')
    number = dict(type='number', minimum=-1e12, maximum=1e12)
    nonnegative = dict(type='number', minimum=0, maximum=1e12)
    positive = dict(type='number', exclusiveMinimum=0, maximum=1e12)
    unit = dict(type='number', minimum=0, maximum=1)
    integer = dict(type='integer', minimum=0, maximum=2**31-1)
    count = dict(type='integer', minimum=1, maximum=2**31-1)
    vector = arr(number, 3, 3)
    positive_vector = arr(positive, 3, 3)
    quaternion = arr(dict(type='number', minimum=-1, maximum=1), 4, 4)
    nullable_id = {'anyOf': [identifier, {'type': 'null'}]}
    rate = obj(dict(numerator=count, denominator=count))
    frame_range = obj(dict(start=integer, end=count))
    # Physics positions are rigid transforms: no ambiguous animated/nonuniform scale.
    transform = obj(dict(translation=vector, rotation=quaternion))
    asset = obj(dict(id=identifier, version=version, path=text, sha256=digest,
                     kind={'enum': ['geometry', 'rig', 'animation', 'scene', 'material', 'texture', 'physics-world', 'physics-cache']}))
    file_ref = obj(dict(path=text, sha256=digest, bytes=integer))
    # Coefficients are canonical requests. A future adapter must either verify
    # the declared combination rule or reject it; no override is implied.
    material = obj(dict(id=identifier, density=positive, static_friction=nonnegative,
                        dynamic_friction=nonnegative, restitution=unit, linear_damping=unit,
                        angular_damping=unit, collision_margin=nonnegative,
                        pbr_material=nullable_id,
                        combination={'const': 'bullet-product'}))
    sphere = obj(dict(type={'const': 'sphere'}, radius=positive))
    box = obj(dict(type={'const': 'box'}, size=positive_vector))
    capsule = obj(dict(type={'enum': ['capsule', 'cylinder']}, radius=positive, height=positive,
                       axis={'enum': ['X', 'Y', 'Z']}))
    mesh = obj(dict(type={'enum': ['convex-hull', 'triangle-mesh']}, source=identifier,
                    vertices=arr(vector, 4, 100000),
                    triangles=arr(arr(integer, 3, 3), 4, 200000)))
    compound = obj(dict(type={'const': 'compound'}, children=arr(obj(dict(
        transform=ref('Transform'), shape=ref('ColliderShape'))), 1, 64)))
    shape = {'oneOf': [sphere, box, capsule, mesh, compound]}
    collider = obj(dict(id=identifier, transform=transform, shape=shape,
                        material=identifier, group=dict(type='integer', minimum=1, maximum=2**32-1),
                        mask=dict(type='integer', minimum=0, maximum=2**32-1), sensor={'type': 'boolean'}))
    mass = obj(dict(kilograms=nonnegative, center_of_mass=vector,
                    inertia=arr(arr(number, 3, 3), 3, 3)))
    body = obj(dict(id=identifier, category={'enum': ['rigid-body', 'character', 'fracture']},
                    mode={'enum': ['static', 'dynamic', 'kinematic']},
                    authority={'enum': ['static', 'physics', 'animation']}, parent=nullable_id,
                    asset=nullable_id, transform=transform, mass=mass,
                    linear_velocity=vector, angular_velocity=vector,
                    colliders=arr(collider, 1, 64), animation=nullable_id,
                    character_controller=obj(dict(max_speed=positive, step_height=nonnegative,
                        slope_limit_radians=dict(type='number',minimum=0,maximum=math.pi/2))),
                    fracture=obj(dict(source=identifier, fragments=arr(identifier, 2, 10000),
                        break_force=positive, break_torque=positive))),
                ['id', 'category', 'mode', 'authority', 'parent', 'asset', 'transform', 'mass',
                 'linear_velocity', 'angular_velocity', 'colliders', 'animation'])
    joint = obj(dict(id=identifier, type={'enum': ['fixed', 'hinge', 'slider', 'ball', 'spring', 'generic-6dof']},
                     body_a=identifier, body_b=identifier, anchor_a=transform, anchor_b=transform,
                     axis=vector, limits=arr(number, 2, 2), stiffness=nonnegative,
                     damping=nonnegative, motor_velocity=number, motor_max_force=nonnegative,
                     break_force=positive, collide_connected={'type': 'boolean'}),
                ['id', 'type', 'body_a', 'body_b', 'anchor_a', 'anchor_b', 'axis', 'limits',
                 'stiffness', 'damping', 'motor_velocity', 'motor_max_force', 'collide_connected'])
    force = obj(dict(id=identifier, type={'enum': ['force', 'impulse', 'torque', 'wind', 'drag', 'turbulence', 'vortex']},
                     bodies=arr(identifier, 1, 10000), vector=vector, point=vector,
                     frame_range=frame_range, strength=nonnegative, seed=integer,
                     categories=arr({'enum': list(CATEGORIES)}, 1, len(CATEGORIES))))
    # Categories needing solvers beyond rigid bodies carry explicit bounded
    # contracts, not fake outputs or claims that their solver already exists.
    deformable = obj(dict(id=identifier, category={'enum': ['cloth', 'soft-body', 'hair']},
                          geometry=identifier, material=identifier, parent=nullable_id,
                          pins=arr(integer, 0, 100000), vertex_count=count,
                          stiffness=positive, damping=unit, mass=positive,
                          colliders=arr(identifier, 0, 10000)))
    particles = obj(dict(id=identifier, category={'const': 'particles'}, geometry=identifier,
                         count=count, lifetime_seconds=positive, seed=integer,
                         mass=positive, radius=positive, initial_velocity=vector,
                         colliders=arr(identifier, 0, 10000)))
    volume = obj(dict(id=identifier, category={'enum': ['gas', 'liquid']},
                      transform=transform, size=positive_vector,
                      resolution=arr(dict(type='integer', minimum=1, maximum=4096), 3, 3),
                      density=positive, viscosity=nonnegative, temperature=positive,
                      combustion={'type': 'boolean'}, emitters=arr(identifier, 1, 10000),
                      colliders=arr(identifier, 0, 10000)))
    component = {'oneOf': [deformable, particles, volume]}
    event = obj(dict(id=identifier, frame=integer, sequence=integer,
                     type={'enum': ['grab', 'release', 'throw', 'impulse', 'break', 'enable', 'disable']},
                     target=identifier, actor=nullable_id, vector=vector))
    budgets = obj(dict(bodies=count, colliders=count, vertices=count, particles=count,
                       volume_cells=count, steps=count, duration_seconds=positive,
                       memory_bytes=count, cache_bytes=count, timeout_seconds=positive))
    solver = obj(dict(backend={'enum': ['blender', 'pybullet']}, adapter_version=version,
                      fixed_step=rate, substeps=dict(type='integer', minimum=1, maximum=1024),
                      iterations=dict(type='integer', minimum=1, maximum=1000),
                      seed=integer, quality={'enum': ['draft', 'preview', 'production', 'custom']},
                      required_categories=arr({'enum': list(CATEGORIES)}, 1, len(CATEGORIES)),
                      reproducibility={'enum': ['verified-cache-replay', 'pinned-numerical', 'approximate', 'not-guaranteed']}))
    world = obj(dict(schema_version={'const': 1}, kind={'const': 'hatch-3d-physics-world'},
                     id=identifier, version=version, coordinate_system={'const': COORDINATES},
                     physical_units={'const': PHYSICAL_UNITS}, scene=asset,
                     fps=rate, frame_range=frame_range, gravity=vector,
                     solver=solver, budgets=budgets, assets=arr(asset, 0, 10000),
                     materials=arr(material, 1, 1000), bodies=arr(body, 0, 10000),
                     components=arr(component, 0, 10000), joints=arr(joint, 0, 10000),
                     forces=arr(force, 0, 10000), events=arr(event, 0, 100000)))
    backend = obj(dict(id={'enum': ['blender', 'pybullet']}, adapter_version=version,
                       solver_name=text, solver_version=text, application_version=text,
                       platform=text, precision={'enum': ['float32', 'float64', 'mixed']},
                       device={'enum': ['cpu', 'gpu']}, executable_sha256=digest))
    usage = obj(dict(elapsed_seconds=nonnegative, peak_memory_bytes=integer,
                     output_bytes=integer, solver_steps=integer))
    job = obj(dict(schema_version={'const': 1}, kind={'const': 'hatch-3d-physics-job'},
                   id=identifier, world=asset, world_sha256=digest, backend=backend,
                   output_directory=text, input_files=arr(file_ref, 1, 10000),
                   frame_range=frame_range, fps=rate, fixed_step=rate,
                   substeps=dict(type='integer', minimum=1, maximum=1024),
                   budgets=budgets, status={'enum': ['pending', 'running', 'succeeded', 'failed', 'cancelled', 'interrupted']},
                   attempt=dict(type='integer', minimum=1, maximum=100),
                   recovery={'enum': ['clean-restart', 'verified-checkpoint']},
                   checkpoint={'anyOf': [file_ref, {'type': 'null'}]}, usage=usage))
    cache = obj(dict(schema_version={'const': 1}, kind={'const': 'hatch-3d-physics-cache'},
                     id=identifier, world_sha256=digest, physics_input_sha256=digest,
                     backend=backend, frame_range=frame_range, fps=rate, fixed_step=rate,
                     substeps=dict(type='integer', minimum=1, maximum=1024),
                     sample_count=count, files=arr(file_ref, 1, 10000),
                     upstream_hashes=arr(digest, 0, 10000), seed=integer,
                     reproducibility={'enum': ['verified-cache-replay', 'pinned-numerical', 'approximate', 'not-guaranteed']},
                     numerical_tolerance=positive, usage=usage,
                     fixture={'type': 'boolean'}, review_status={'enum': ['unreviewed', 'rejected', 'approved']}))
    diagnostic = obj(dict(code=identifier, message=text, path=dict(type='string', maxLength=2048),
                          category={'enum': ['invalid-input', 'capability-gap', 'setup-error', 'numerical-instability',
                          'timeout', 'resource-exhaustion', 'cache-corruption', 'backend-crash']},
                          retryable={'type': 'boolean'}))
    return dict(Rate=rate, FrameRange=frame_range, Transform=transform, AssetRef=asset,
                FileRef=file_ref, PhysicalMaterial=material, ColliderShape=shape,
                Collider=collider, PhysicsBody=body, PhysicsJoint=joint, PhysicsForce=force,
                PhysicsComponent=component, PhysicsEvent=event, PhysicsBudgets=budgets,
                SolverSettings=solver, BackendIdentity=backend, ResourceUsage=usage,
                PhysicsWorld=world, PhysicsJob=job, PhysicsCache=cache, PhysicsDiagnostic=diagnostic)


KINDS = dict(world='PhysicsWorld', job='PhysicsJob', cache='PhysicsCache', diagnostic='PhysicsDiagnostic')


def _reachable_definitions(root: str) -> dict:
    found = set()
    pending = [root]
    while pending:
        name = pending.pop()
        if name in found:
            continue
        found.add(name)
        for item, _ in _walk(definitions()[name]):
            if isinstance(item, dict) and '$ref' in item:
                pending.append(item['$ref'].removeprefix('#/$defs/'))
    return {name: copy.deepcopy(value) for name, value in definitions().items() if name in found}


def schemas() -> dict:
    return {'physics-3d-' + key + '.schema.json': {
        '$schema': 'https://json-schema.org/draft/2020-12/schema',
        '$id': 'https://gethatch.pet/schemas/physics-3d-' + key + '-v1',
        'title': name + ' v1',
        'description': 'Structural bounds; runtime additionally validates graph, geometry, time and aggregate budgets. No solver capability is implied.',
        '$defs': _reachable_definitions(name), '$ref': '#/$defs/' + name,
    } for key, name in KINDS.items()}


@lru_cache(maxsize=32)
def _validator(kind: str):
    require(kind in definitions(), 'PHYSICS_SCHEMA_KIND', 'Unknown physics contract: ' + kind)
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise PhysicsError('PHYSICS_DEPENDENCY', 'Contract validation requires jsonschema.', category='setup-error') from exc
    return Draft202012Validator({'$defs': definitions(), '$ref': '#/$defs/' + kind})


def _walk(value: Any, path=''):
    yield value, path
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk(item, path + '/' + key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, path + '/' + str(index))


def _common(value: Any) -> None:
    for item, path in _walk(value):
        if not isinstance(item, dict):
            continue
        if ('path' in item and 'sha256' in item) or 'output_directory' in item:
            field = 'output_directory' if 'output_directory' in item else 'path'
            try:
                canonical = portable_name(item[field])
            except RigError as exc:
                raise PhysicsError('PHYSICS_PATH', str(exc), path + '/' + field) from exc
            require(canonical == item[field] and unicodedata.normalize('NFC', canonical) == canonical, 'PHYSICS_PATH', 'Path must already be canonical POSIX/NFC.', path + '/' + field)
        if set(item) == {'numerator', 'denominator'}:
            require(math.gcd(item['numerator'], item['denominator']) == 1,
                    'PHYSICS_RATE', 'Rationals must be reduced.', path)
        if set(item) == {'start', 'end'}:
            require(item['start'] < item['end'], 'PHYSICS_RANGE', 'Ranges are nonempty and half-open.', path)
        if 'rotation' in item:
            require(abs(sum(x*x for x in item['rotation']) - 1) <= 1e-5,
                    'PHYSICS_QUATERNION', 'XYZW quaternion must have unit length.', path + '/rotation')
        if 'files' in item or 'input_files' in item:
            files = item.get('files', item.get('input_files'))
            aliases = [unicodedata.normalize('NFC', file['path']).casefold() for file in files]
            require(len(aliases) == len(set(aliases)), 'PHYSICS_PATH_ALIAS', 'Duplicate or case-alias file paths.', path)


def _unique(items, path):
    result = {}
    for item in items:
        require(item['id'] not in result, 'PHYSICS_DUPLICATE_ID', 'Duplicate ID: ' + item['id'], path)
        result[item['id']] = item
    return result


def _acyclic(items: dict, path: str):
    # Iterative coloring avoids recursion at the 10,000-object admission bound.
    finished = set()
    for identifier in items:
        chain = set()
        current = identifier
        while current is not None and current not in finished:
            require(current in items, 'PHYSICS_REFERENCE', 'Unknown parent: ' + current, path)
            require(current not in chain, 'PHYSICS_CYCLE', 'Cyclic parent ownership.', path)
            chain.add(current)
            current = items[current]['parent']
        finished.update(chain)


def _shape(shape: dict, assets: dict, path: str, *, dynamic: bool) -> tuple[int, int]:
    """Validate actual supplied proxy triangles, returning vertex/triangle counts.

    Convexity/manifold/backend-specific supported shape checks belong to #171;
    the contract does not promote this input to a verified collision hull.
    """
    kind = shape['type']
    if kind == 'compound':
        counts = [_shape(child['shape'], assets, path + '/children', dynamic=dynamic) for child in shape['children']]
        return sum(a for a, _ in counts), sum(b for _, b in counts)
    if kind not in ('convex-hull', 'triangle-mesh'):
        return 0, 0
    require(shape['source'] in assets and assets[shape['source']]['kind'] == 'geometry',
            'PHYSICS_REFERENCE', 'Collision mesh needs a geometry asset reference.', path)
    require(not dynamic or kind != 'triangle-mesh', 'PHYSICS_GEOMETRY', 'Dynamic concave triangle meshes require decomposition.', path)
    vertices, triangles = shape['vertices'], shape['triangles']
    seen = set()
    for triangle in triangles:
        require(len(set(triangle)) == 3 and max(triangle) < len(vertices),
                'PHYSICS_GEOMETRY', 'Invalid triangle index.', path)
        key = tuple(sorted(triangle))
        require(key not in seen, 'PHYSICS_GEOMETRY', 'Duplicate triangle.', path)
        seen.add(key)
        a, b, c = (vertices[index] for index in triangle)
        ab, ac = [b[i]-a[i] for i in range(3)], [c[i]-a[i] for i in range(3)]
        cross = [ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2], ab[0]*ac[1]-ab[1]*ac[0]]
        require(sum(x*x for x in cross) > 1e-24, 'PHYSICS_GEOMETRY', 'Degenerate collision triangle.', path)
    if kind == 'convex-hull':
        origin = vertices[0]
        edge = next(([v[i]-origin[i] for i in range(3)] for v in vertices[1:] if v != origin), None)
        normal = None
        if edge is not None:
            for vertex in vertices[1:]:
                delta = [vertex[i]-origin[i] for i in range(3)]
                candidate = [edge[1]*delta[2]-edge[2]*delta[1], edge[2]*delta[0]-edge[0]*delta[2], edge[0]*delta[1]-edge[1]*delta[0]]
                if sum(x*x for x in candidate) > 1e-24:
                    normal = candidate
                    break
        require(normal is not None and any(abs(sum(normal[i]*(v[i]-origin[i]) for i in range(3))) > 1e-18 for v in vertices),
                'PHYSICS_GEOMETRY', 'Convex collision hull must enclose a nonzero 3D volume.', path)
    return len(vertices), len(triangles)


def _world(world: dict) -> None:
    assets = _unique(world['assets'], '/assets')
    require(world['scene']['kind'] == 'scene', 'PHYSICS_REFERENCE', 'World scene must reference a scene resource.', '/scene')
    materials = _unique(world['materials'], '/materials')
    bodies = _unique(world['bodies'], '/bodies')
    components = _unique(world['components'], '/components')
    require(not (set(bodies) & set(components)), 'PHYSICS_DUPLICATE_ID', 'Body and component IDs must be distinct.')
    entities = {**bodies, **components}
    _acyclic({key: item for key, item in entities.items() if 'parent' in item}, '/bodies')
    _unique(world['joints'], '/joints'); _unique(world['forces'], '/forces'); _unique(world['events'], '/events')
    required = world['solver']['required_categories']
    require(len(required) == len(set(required)), 'PHYSICS_CATEGORY', 'Duplicate required category.')
    actual_categories = {item['category'] for item in entities.values()}
    require(actual_categories <= set(required), 'PHYSICS_CATEGORY', 'Every category must be explicitly required from the backend.')
    colliders = 0; vertices = 0; particles = 0; cells = 0
    for identifier, material in materials.items():
        if material['pbr_material'] is not None:
            require(material['pbr_material'] in assets and assets[material['pbr_material']]['kind'] == 'material',
                    'PHYSICS_REFERENCE', 'Unknown PBR material.', '/materials/' + identifier)
        require(material['dynamic_friction'] <= material['static_friction'], 'PHYSICS_MATERIAL',
                'Dynamic friction cannot exceed static friction.', '/materials/' + identifier)
    aliases = [unicodedata.normalize('NFC', item['path']).casefold() for item in world['assets']]
    require(len(aliases) == len(set(aliases)), 'PHYSICS_PATH_ALIAS', 'Asset paths must not alias.', '/assets')
    collider_ids = set()
    for identifier, body in bodies.items():
        path = '/bodies/' + identifier
        mode = body['mode']
        require(('character_controller' in body) == (body['category'] == 'character'), 'PHYSICS_CATEGORY', 'Character category requires exactly one controller definition.', path)
        require(('fracture' in body) == (body['category'] == 'fracture'), 'PHYSICS_CATEGORY', 'Fracture category requires a source and break thresholds.', path)
        if 'fracture' in body:
            fracture = body['fracture']
            require(fracture['source'] in assets and assets[fracture['source']]['kind'] == 'geometry' and
                    len(set(fracture['fragments'])) == len(fracture['fragments']) and
                    set(fracture['fragments']) <= set(bodies) and identifier not in fracture['fragments'],
                    'PHYSICS_REFERENCE', 'Fracture fragments must be distinct referenced bodies.', path)
        require(mode != 'dynamic' or body['parent'] is None, 'PHYSICS_AUTHORITY', 'Dynamic transforms are world-owned and cannot have a transform parent.', path)
        require(body['authority'] == {'static': 'static', 'dynamic': 'physics', 'kinematic': 'animation'}[mode],
                'PHYSICS_AUTHORITY', 'Mode and transform authority conflict.', path)
        require((body['animation'] is None) == (mode != 'kinematic'), 'PHYSICS_AUTHORITY',
                'Only kinematic bodies require an authored animation reference.', path)
        for field, kind in [('asset', 'geometry'), ('animation', 'animation')]:
            if body[field] is not None:
                require(body[field] in assets and assets[body[field]]['kind'] == kind,
                        'PHYSICS_REFERENCE', 'Unknown ' + field + ' reference.', path)
        mass = body['mass']
        require((mass['kilograms'] > 0) == (mode == 'dynamic'), 'PHYSICS_MASS',
                'Dynamic mass must be positive; static/kinematic mass must be zero.', path)
        inertia = mass['inertia']
        inertia_scale = max(abs(x) for row in inertia for x in row)
        tolerance = inertia_scale * 1e-10
        require(all(abs(inertia[i][j] - inertia[j][i]) <= tolerance for i in range(3) for j in range(3)),
                'PHYSICS_INERTIA', 'Inertia tensor must be symmetric.', path)
        if mode == 'dynamic':
            a,b,c = inertia[0]; _,d,e = inertia[1]; _,_,f = inertia[2]
            determinant = a*d*f + 2*b*c*e - a*e*e - d*c*c - f*b*b
            require(a > 0 and a*d-b*b > 0 and determinant > 0, 'PHYSICS_INERTIA', 'Dynamic inertia must be positive definite.', path)
            # Principal inertias satisfy triangle inequalities. PSD of
            # trace(I)/2*identity-I is equivalent and avoids an eigensolver.
            h = (a+d+f)/2
            x,y,z = h-a,h-d,h-f
            moment_det = x*y*z - 2*b*c*e - x*e*e - y*c*c - z*b*b
            require(min(x,y,z) >= -tolerance and x*y-b*b >= -tolerance*inertia_scale and x*z-c*c >= -tolerance*inertia_scale and y*z-e*e >= -tolerance*inertia_scale and moment_det >= -tolerance*inertia_scale**2,
                    'PHYSICS_INERTIA', 'Tensor violates physical principal-moment inequalities.', path)
        else:
            require(all(value == 0 for row in inertia for value in row) and all(x == 0 for x in body['linear_velocity'] + body['angular_velocity']),
                    'PHYSICS_MASS', 'Static/kinematic initial mass inertia and simulated velocities must be zero.', path)
        for collider in body['colliders']:
            require(collider['id'] not in collider_ids, 'PHYSICS_DUPLICATE_ID', 'Collider IDs must be unique in a world.', path)
            collider_ids.add(collider['id'])
            require(collider['material'] in materials, 'PHYSICS_REFERENCE', 'Unknown physical material.', path)
            count, _ = _shape(collider['shape'], assets, path + '/colliders', dynamic=mode == 'dynamic')
            vertices += count; colliders += 1
    for identifier, component in components.items():
        path = '/components/' + identifier
        if 'geometry' in component:
            require(component['geometry'] in assets and assets[component['geometry']]['kind'] == 'geometry',
                    'PHYSICS_REFERENCE', 'Unknown component geometry.', path)
        if 'material' in component:
            require(component['material'] in materials, 'PHYSICS_REFERENCE', 'Unknown component physical material.', path)
        require(set(component['colliders']) <= set(bodies), 'PHYSICS_REFERENCE', 'Unknown collider body.', path)
        if 'pins' in component:
            require(len(set(component['pins'])) == len(component['pins']) and all(x < component['vertex_count'] for x in component['pins']),
                    'PHYSICS_GEOMETRY', 'Invalid or duplicate pinned vertices.', path)
            vertices += component['vertex_count']
        if component['category'] == 'particles': particles += component['count']
        if component['category'] in ('gas', 'liquid'):
            cells += math.prod(component['resolution'])
            require(set(component['emitters']) <= set(bodies), 'PHYSICS_REFERENCE', 'Unknown volume emitter body.', path)
            require(not component['combustion'] or component['category'] == 'gas', 'PHYSICS_CATEGORY', 'Liquid cannot request combustion.', path)
    for joint in world['joints']:
        path = '/joints/' + joint['id']
        require(joint['body_a'] in bodies and joint['body_b'] in bodies and joint['body_a'] != joint['body_b'],
                'PHYSICS_REFERENCE', 'Joint endpoints must be distinct existing bodies.', path)
        require(any(bodies[joint[key]]['mode'] == 'dynamic' for key in ('body_a', 'body_b')),
                'PHYSICS_AUTHORITY', 'Joint needs a dynamic endpoint.', path)
        require(abs(sum(x*x for x in joint['axis']) - 1) <= 1e-5, 'PHYSICS_AXIS', 'Joint axis must be unit length.', path)
        require(joint['limits'][0] <= joint['limits'][1], 'PHYSICS_RANGE', 'Joint limits are reversed.', path)
    span = world['frame_range']; previous = (-1,-1)
    for event in world['events']:
        key = (event['frame'], event['sequence'])
        require(previous < key and span['start'] <= event['frame'] < span['end'], 'PHYSICS_TIME', 'Events must be ordered, unique, and inside the half-open range.', '/events')
        previous = key
        require(event['target'] in entities and (event['actor'] is None or event['actor'] in entities), 'PHYSICS_REFERENCE', 'Unknown event entity.', '/events')
    for force in world['forces']:
        require(set(force['bodies']) <= set(entities) and len(force['bodies']) == len(set(force['bodies'])), 'PHYSICS_REFERENCE', 'Unknown or duplicate force target.', '/forces')
        require(set(force['categories']) <= set(required) and all(entities[key]['category'] in force['categories'] for key in force['bodies']),
                'PHYSICS_CATEGORY', 'Force applicability must include every target category.', '/forces')
        force_span = force['frame_range']
        require(span['start'] <= force_span['start'] < force_span['end'] <= span['end'], 'PHYSICS_TIME', 'Force range escapes world range.', '/forces')
    duration = Fraction(span['end']-span['start'], 1) / _fraction(world['fps'])
    steps = math.ceil(duration / _fraction(world['solver']['fixed_step'])) * world['solver']['substeps']
    budget = world['budgets']
    usage = dict(bodies=len(bodies), colliders=colliders, vertices=vertices, particles=particles, volume_cells=cells,
                 steps=steps, duration_seconds=duration)
    for key, used in usage.items():
        require(used <= budget[key], 'PHYSICS_BUDGET', 'Configured ' + key + ' exceeds admission budget.', '/budgets/' + key)


def _fraction(rate: dict) -> Fraction:
    return Fraction(rate['numerator'], rate['denominator'])


def validate_contract(value: Any, kind: str = 'PhysicsWorld') -> Any:
    """Validate without mutation or filesystem writes; return the original value.

    This establishes configuration validity only. Backend admission, file-byte
    verification, real execution and reviewed visual output are separate gates.
    """
    try:
        finite_json(value)
    except RigError as exc:
        raise PhysicsError('PHYSICS_JSON', str(exc)) from exc
    error = next(_validator(kind).iter_errors(value), None)
    if error:
        raise PhysicsError('PHYSICS_SCHEMA', error.message, '/' + '/'.join(map(str, error.absolute_path)))
    _common(value)
    if kind == 'PhysicsWorld': _world(value)
    if kind in ('PhysicsJob', 'PhysicsCache'):
        if kind == 'PhysicsJob':
            duration = Fraction(value['frame_range']['end']-value['frame_range']['start'],1) / _fraction(value['fps'])
            steps = math.ceil(duration/_fraction(value['fixed_step'])) * value['substeps']
            require(duration <= value['budgets']['duration_seconds'] and steps <= value['budgets']['steps'],
                    'PHYSICS_BUDGET', 'Configured job range exceeds duration or step budget.')
            require(value['world']['kind'] == 'physics-world' and value['world']['sha256'] == value['world_sha256'],
                    'PHYSICS_REFERENCE', 'Job world reference must bind exact world bytes.')
            require((value['checkpoint'] is not None) == (value['recovery'] == 'verified-checkpoint'),
                    'PHYSICS_RECOVERY', 'Verified checkpoint recovery requires a bound checkpoint file.')
        else:
            require(value['sample_count'] == value['frame_range']['end']-value['frame_range']['start'],
                    'PHYSICS_CACHE_RANGE', 'Cache must declare one sample per half-open output frame.')
            require(value['usage']['output_bytes'] == sum(file['bytes'] for file in value['files']),
                    'PHYSICS_CACHE_SIZE', 'Cache usage must equal inventoried output bytes.')
    return value


def load_contract(path: str | Path, kind: str = 'PhysicsWorld') -> Any:
    # Nonblocking open rejects FIFOs without waiting for a writer. Descriptor
    # validation bounds actual reads; no path is created or modified.
    path = Path(path)
    require(not path.is_symlink(), 'PHYSICS_PATH', 'Contract input cannot be a symlink.')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_NOFOLLOW', 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise PhysicsError('PHYSICS_IO', 'Cannot open contract input: ' + str(exc)) from exc
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise PhysicsError('PHYSICS_IO', 'Contract input must be a regular file.')
    with os.fdopen(descriptor, 'rb') as stream:
        payload = stream.read(32*1024*1024 + 1)
    try:
        value = decode_json(payload)
    except RigError as exc:
        raise PhysicsError('PHYSICS_JSON', str(exc)) from exc
    return validate_contract(value, kind)


def document_hash(value: Any, kind: str = 'PhysicsWorld') -> str:
    validate_contract(value, kind)
    return object_hash(value)


def material_preset(name: str, *, pbr_material: str | None = None) -> dict:
    """Reusable engineering starting points, not measured material certificates."""
    presets = {'rubber': (1100., .8, .6, .5), 'wood': (700., .5, .3, .2),
               'metal': (7800., .4, .3, .1), 'ice': (917., .1, .03, .05)}
    require(name in presets, 'PHYSICS_MATERIAL', 'Unknown physical material preset.')
    density, static_friction, dynamic_friction, restitution = presets[name]
    result = dict(id=name, density=density, static_friction=static_friction,
                  dynamic_friction=dynamic_friction, restitution=restitution,
                  linear_damping=.04, angular_damping=.1, collision_margin=.001,
                  pbr_material=pbr_material, combination='bullet-product')
    return validate_contract(result, 'PhysicalMaterial')


def combine_materials(left: dict, right: dict) -> dict:
    """Bullet's default friction-product/clamp and restitution-product arithmetic.

    Adapters must verify the actual pinned backend and reject unsupported separate
    static/dynamic mappings. This arithmetic is not backend capability evidence.
    """
    validate_contract(left, 'PhysicalMaterial'); validate_contract(right, 'PhysicalMaterial')
    return {key: min(10., left[key]*right[key]) if key != 'restitution' else left[key]*right[key]
            for key in ('static_friction', 'dynamic_friction', 'restitution')}


def generate_schemas(*, check=False, directory: Path | None = None) -> None:
    directory = directory or Path(__file__).resolve().parents[1] / 'profiles'
    for name, schema in schemas().items():
        path = directory / name
        content = json.dumps(schema, indent=2) + '\n'
        if check:
            require(path.read_text(encoding='utf-8') == content, 'PHYSICS_SCHEMA_DRIFT', 'Schema drift: ' + name)
        else:
            path.write_text(content, encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='check generated schemas without writing')
    arguments = parser.parse_args()
    generate_schemas(check=arguments.check)
