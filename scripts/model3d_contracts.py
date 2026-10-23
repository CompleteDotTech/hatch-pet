"""Additive Model3D v1 contracts; schema discovery imports no numeric backend.

These contracts describe intent and exact payload references. Validation never
turns a declared provider result, job state, license claim or review into evidence.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import math
import unicodedata

from rig_contracts import COORDINATES, obj, arr, ref
from rig_errors import RigError, finite_json, portable_name, require

VERSION = '1.0.0'
LIMITS = dict(file_bytes=256 * 1024**2, total_bytes=1024**3, files=4096,
              vertices=1_000_000, triangles=2_000_000, parts=4096,
              dependency_depth=16, memory_bytes=2 * 1024**3)
KINDS = {name: 'model3d-' + name for name in
         ('request', 'source', 'asset', 'part', 'material', 'uncertainty', 'job', 'export')}


def _document(kind, fields, optional=()):
    fields = dict(schema_version={'const': 1}, kind={'const': KINDS[kind]}, **fields)
    return obj(fields, [key for key in fields if key not in optional])


@lru_cache(maxsize=1)
def _definitions():
    text = dict(type='string', minLength=1, maxLength=4096)
    short = dict(type='string', minLength=1, maxLength=128)
    identifier = dict(type='string', pattern=r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$')
    version = dict(type='string', maxLength=64, pattern=r'^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$')
    digest = dict(type='string', pattern=r'^[0-9a-f]{64}$')
    number = dict(type='number', minimum=-1e9, maximum=1e9)
    positive = dict(type='number', exclusiveMinimum=0, maximum=1e9)
    fraction = dict(type='number', minimum=0, maximum=1)
    integer = dict(type='integer', minimum=0, maximum=2_000_000_000)
    boolean = dict(type='boolean')
    nullable_text = {'anyOf': [text, {'type': 'null'}]}
    vec = arr(number, 3, 3)
    file = obj(dict(path=dict(type='string', minLength=1, maxLength=1024),
                    sha256=digest, bytes=dict(type='integer', minimum=1, maximum=LIMITS['file_bytes']),
                    media_type={'enum': ['model/gltf-binary', 'model/gltf+json', 'model/obj',
                                         'application/octet-stream', 'application/json',
                                         'image/png', 'image/jpeg', 'image/webp', 'text/plain']}))
    budget = obj({key: dict(type='integer', minimum=1, maximum=value) for key, value in LIMITS.items()})
    transform = obj(dict(translation=vec, rotation=arr(number, 4, 4), scale=arr(positive, 3, 3)))
    bounds = obj(dict(minimum=vec, maximum=vec))
    tool = obj(dict(name=short, version=nullable_text))
    license_claim = obj(dict(identifier=nullable_text, attribution=nullable_text,
                             redistribution={'enum': ['unknown', 'restricted', 'permitted']},
                             evidence={'anyOf': [ref('file'), {'type': 'null'}]}))
    provenance = obj(dict(origin={'enum': ['imported', 'generated', 'derived', 'authored', 'procedural-fixture']},
                          fixture=boolean, description=text, tools=arr(tool, 0, 32),
                          evidence=arr(ref('file'), 0, 128), license=license_claim))
    asset_ref = obj(dict(id=identifier, version=version, manifest=ref('file')))
    source = _document('source', dict(id=identifier, version=version, file=ref('file'),
        role={'enum': ['geometry', 'front', 'back', 'left', 'right', 'top', 'bottom',
                       'detail', 'identity', 'sketch', 'texture', 'annotation', 'mask', 'depth', 'profile']},
        provenance=provenance,
        camera=obj(dict(status={'enum': ['unknown', 'supplied', 'estimated']},
                        projection={'enum': ['perspective', 'orthographic']},
                        camera_to_world=arr(number, 16, 16),
                        image_size=arr(dict(type='integer', minimum=1, maximum=32768), 2, 2),
                        intrinsics=arr(number, 9, 9), orthographic_size=arr(positive, 2, 2),
                        evidence=ref('file')), ['status'])))
    uncertainty = _document('uncertainty', dict(id=identifier, target=identifier,
        classification={'enum': ['observed', 'multi-view-constrained', 'procedurally-inferred',
                                  'model-inferred', 'manually-authored', 'unknown']},
        message=text, evidence=arr(identifier, 0, 128),
        confidence={'anyOf': [fraction, {'type': 'null'}]},
        confidence_method=nullable_text,
        status={'enum': ['pending', 'accepted', 'corrected']}))
    texture = obj(dict(file=ref('file'), texcoord={'enum': [0, 1]},
                       color_space={'enum': ['srgb', 'linear-data']}))
    material = _document('material', dict(id=identifier, version=version, name=short,
        slot=dict(type='integer', minimum=0, maximum=4095),
        base_color=arr(fraction, 4, 4), metallic=fraction, roughness=fraction,
        alpha_mode={'enum': ['OPAQUE', 'MASK', 'BLEND']}, alpha_cutoff=fraction,
        double_sided=boolean,
        textures=obj({name: texture for name in ('base_color', 'normal', 'metallic_roughness',
                                                'occlusion', 'emissive')}, []),
        provenance=provenance))
    part = _document('part', dict(id=identifier, name=short,
        parent={'anyOf': [identifier, {'type': 'null'}]}, local_transform=transform,
        mesh_ids=arr(identifier, 0, 4096), material_ids=arr(identifier, 0, 4096),
        source_ids=arr(identifier, 0, 128), uncertainty_ids=arr(identifier, 0, 128)))
    request = _document('request', dict(id=identifier, version=version, asset_id=identifier,
        category={'enum': ['character', 'prop', 'environment', 'architecture', 'general']},
        method={'enum': ['import', 'procedural', 'silhouette', 'revolution', 'heightfield',
                         'visual-hull', 'provider']},
        description=text, negative_constraints=arr(text, 0, 128),
        sources=arr(ref('source'), 0, 128), coordinate_system={'const': COORDINATES},
        dimensions_m=arr(positive, 3, 3),
        scale_evidence={'enum': ['supplied', 'estimated', 'measured']},
        intended_use={'enum': ['realtime', 'cinematic', 'web', 'mobile', 'print', 'editing']},
        formats=arr({'enum': ['glb', 'gltf', 'obj', 'blend']}, 1, 4),
        semantic_parts=arr(identifier, 0, 4096), allowed_assumptions=arr(text, 0, 128),
        identity={'anyOf': [ref('file'), {'type': 'null'}]},
        style={'anyOf': [ref('file'), {'type': 'null'}]},
        provider={'anyOf': [obj(dict(id=identifier, model=nullable_text,
                                      network_authorized=boolean)), {'type': 'null'}]},
        seed=dict(type='integer', minimum=0, maximum=2**32-1), limits=ref('limits')))
    asset = _document('asset', dict(id=identifier, version=version,
        category={'enum': ['character', 'prop', 'environment', 'architecture', 'general']},
        coordinate_system={'const': COORDINATES},
        sources=arr(ref('source'), 1, 128), files=arr(ref('file'), 1, LIMITS['files']),
        geometry=ref('file'),
        measurements=obj(dict(vertices=dict(type='integer', minimum=1, maximum=LIMITS['vertices']),
                              triangles=dict(type='integer', minimum=1, maximum=LIMITS['triangles']),
                              bounds=ref('bounds'))),
        parts=arr(ref('part'), 1, LIMITS['parts']), materials=arr(ref('material'), 0, 4096),
        dependencies=arr(ref('asset-reference'), 0, 256),
        uncertainties=arr(ref('uncertainty'), 0, 1024), provenance=provenance,
        review=obj(dict(status={'enum': ['pending', 'approved', 'rejected']},
                        evidence=arr(ref('file'), 0, 128))), limits=ref('limits')))
    job = _document('job', dict(id=identifier, request=ref('file'), asset_id=identifier,
        status={'enum': ['queued', 'preparing', 'running', 'waiting-provider', 'validating',
                         'awaiting-review', 'completed', 'failed', 'cancelled', 'interrupted']},
        attempts=dict(type='integer', minimum=0, maximum=100),
        maximum_attempts=dict(type='integer', minimum=1, maximum=100),
        outputs=arr(ref('file'), 0, LIMITS['files']),
        error={'anyOf': [obj(dict(code=identifier, message=text, retryable=boolean)), {'type': 'null'}]},
        dependencies=arr(ref('asset-reference'), 0, 256), limits=ref('limits')))
    export = _document('export', dict(id=identifier, asset=ref('asset-reference'),
        format={'enum': ['glb', 'gltf', 'obj', 'blend', 'archive']},
        status={'enum': ['partial', 'complete', 'failed']}, files=arr(ref('file'), 0, LIMITS['files']),
        tools=arr(tool, 1, 32), losses=arr(text, 0, 128),
        independent_inspection={'anyOf': [ref('file'), {'type': 'null'}]}, limits=ref('limits')))
    return dict(file=file, limits=budget, transform=transform, bounds=bounds,
                provenance=provenance, **{'asset-reference': asset_ref},
                source=source, uncertainty=uncertainty, material=material, part=part,
                request=request, asset=asset, job=job, export=export)


def schemas():
    """Fresh schema objects; callers cannot mutate the canonical definitions."""
    return {'model3d.schema.json': {
        '$schema': 'https://json-schema.org/draft/2020-12/schema',
        'title': 'Hatch Pet Model3D v1 contracts',
        'description': 'Structural contracts only. Runtime checks semantic references and actual payloads separately.',
        '$defs': deepcopy(_definitions()), 'oneOf': [ref(name) for name in KINDS]}}


def file_references(value):
    """Yield declared payloads, including nested source, license and review files."""
    if isinstance(value, dict):
        if set(value) == {'path', 'sha256', 'bytes', 'media_type'}:
            yield value
        else:
            for child in value.values():
                yield from file_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from file_references(child)


def _unique(items, label):
    identifiers = [item['id'] for item in items]
    require(len(identifiers) == len(set(identifiers)), 'MODEL3D_DUPLICATE',
            'Duplicate ' + label + ' identity.', stage='model3d')
    return set(identifiers)


def _transform(value):
    require(abs(math.hypot(*value['rotation']) - 1) <= 1e-6,
            'MODEL3D_QUATERNION', 'Rotation must be a unit XYZW quaternion.', stage='model3d')
    require(all(v >= 1e-9 for v in value['scale']), 'MODEL3D_TRANSFORM',
            'Scale is below the supported nonsingular transform bound.', stage='model3d')


def _semantic(value):
    kind = value['kind']
    if kind == KINDS['part']:
        _transform(value['local_transform'])
        require(value['parent'] != value['id'], 'MODEL3D_CYCLE', 'A part cannot parent itself.')
        for field in ('mesh_ids', 'material_ids', 'source_ids', 'uncertainty_ids'):
            require(len(value[field]) == len(set(value[field])), 'MODEL3D_DUPLICATE', 'Duplicate ' + field)
    elif kind == KINDS['source']:
        media = value['file']['media_type']
        if value['role'] == 'geometry':
            require(media in ('model/gltf-binary', 'model/gltf+json', 'model/obj'),
                    'MODEL3D_SOURCE', 'A geometry source must declare a supported real model format.')
        if value['role'] in ('front', 'back', 'left', 'right', 'top', 'bottom', 'detail', 'sketch', 'texture', 'mask', 'depth'):
            require(media.startswith('image/'), 'MODEL3D_SOURCE', 'This source role requires an image payload.')
        camera = value['camera']
        if camera['status'] == 'unknown':
            require(set(camera) == {'status'}, 'MODEL3D_CAMERA', 'Unknown calibration cannot contain camera measurements.')
        else:
            required = {'projection', 'camera_to_world', 'image_size', 'evidence'}
            require(required <= camera.keys(), 'MODEL3D_CAMERA', 'Calibration requires measured or supplied evidence and a complete camera.')
            optical = 'intrinsics' if camera['projection'] == 'perspective' else 'orthographic_size'
            other = 'orthographic_size' if optical == 'intrinsics' else 'intrinsics'
            require(optical in camera and other not in camera, 'MODEL3D_CAMERA', 'Camera optics must match projection.')
            matrix = camera['camera_to_world']
            require(matrix[12:] == [0, 0, 0, 1], 'MODEL3D_CAMERA', 'Row-major camera-to-world matrix must be affine.')
            columns = [[matrix[row * 4 + col] for row in range(3)] for col in range(3)]
            for i in range(3):
                for j in range(3):
                    require(abs(sum(a*b for a, b in zip(columns[i], columns[j])) - (i == j)) <= 1e-6,
                            'MODEL3D_CAMERA', 'Camera rotation must be orthonormal.')
            a, b, c = columns
            determinant = a[0]*(b[1]*c[2]-b[2]*c[1])-b[0]*(a[1]*c[2]-a[2]*c[1])+c[0]*(a[1]*b[2]-a[2]*b[1])
            require(determinant > 0, 'MODEL3D_CAMERA', 'Camera basis must be right-handed.')
            if optical == 'intrinsics':
                k = camera[optical]
                require(k[0] > 0 and k[4] > 0 and k[3] == 0 and k[6:] == [0, 0, 1],
                        'MODEL3D_CAMERA', 'Invalid perspective intrinsic matrix.')
    elif kind == KINDS['uncertainty']:
        require((value['confidence'] is None) == (value['confidence_method'] is None),
                'MODEL3D_CONFIDENCE', 'A confidence number requires its measurement method; unknown confidence stays null.')
        require(value['confidence'] is None or bool(value['evidence']), 'MODEL3D_CONFIDENCE',
                'Measured confidence requires source evidence.')
    elif kind == KINDS['material']:
        for name, texture in value['textures'].items():
            expected = 'srgb' if name in ('base_color', 'emissive') else 'linear-data'
            require(texture['color_space'] == expected, 'MODEL3D_COLOR_SPACE', 'Incorrect texture interpretation: ' + name)
            require(texture['file']['media_type'].startswith('image/'), 'MODEL3D_TEXTURE', 'A texture must reference image data.')
    elif kind in (KINDS['request'], KINDS['asset']):
        sources = _unique(value['sources'], 'source')
        for source in value['sources']:
            _semantic(source)
        if kind == KINDS['request']:
            require((value['provider'] is not None) == (value['method'] == 'provider'),
                    'MODEL3D_PROVIDER', 'Only provider requests may select a provider, and must name one.')
            if value['method'] not in ('provider', 'procedural'):
                require(bool(sources), 'MODEL3D_SOURCE', 'This method requires supplied source evidence.')
            if value['method'] == 'import':
                require(any(s['role'] == 'geometry' for s in value['sources']),
                        'MODEL3D_SOURCE', 'Mesh import requests need a genuine geometry source.')
            if value['method'] in ('silhouette', 'heightfield'):
                require(any(s['file']['media_type'].startswith('image/') for s in value['sources']),
                        'MODEL3D_SOURCE', 'This reconstruction request needs image evidence.')
            if value['method'] == 'visual-hull':
                require(len(value['sources']) >= 2 and all(s['camera']['status'] != 'unknown' and s['file']['media_type'].startswith('image/') for s in value['sources']),
                        'MODEL3D_CAMERA', 'Visual hull requests require at least two calibrated observations.')
            for field in ('formats', 'semantic_parts'):
                require(len(value[field]) == len(set(value[field])), 'MODEL3D_DUPLICATE', 'Duplicate ' + field)
            return
        parts = _unique(value['parts'], 'part')
        materials = _unique(value['materials'], 'material')
        uncertainties = _unique(value['uncertainties'], 'uncertainty')
        require(len({m['slot'] for m in value['materials']}) == len(value['materials']),
                'MODEL3D_DUPLICATE', 'Material slots must be unique.')
        parent = {part['id']: part['parent'] for part in value['parts']}
        assigned = set()
        for part in value['parts']:
            _semantic(part)
            require(part['parent'] is None or part['parent'] in parts, 'MODEL3D_REFERENCE', 'Missing part parent.')
            for field, allowed in [('material_ids', materials), ('source_ids', sources), ('uncertainty_ids', uncertainties)]:
                require(set(part[field]) <= allowed, 'MODEL3D_REFERENCE', 'Missing ' + field + ' reference.')
            require(not assigned.intersection(part['mesh_ids']), 'MODEL3D_PART', 'Whole-mesh bindings cannot have multiple semantic owners.')
            assigned.update(part['mesh_ids'])
            seen, current = set(), part['id']
            while current is not None:
                require(current not in seen, 'MODEL3D_CYCLE', 'Part hierarchy contains a cycle.')
                require(len(seen) < 64, 'MODEL3D_DEPTH', 'Part hierarchy exceeds 64 levels.')
                seen.add(current)
                current = parent.get(current)
        for material in value['materials']:
            _semantic(material)
        for uncertainty in value['uncertainties']:
            _semantic(uncertainty)
            require(uncertainty['target'] in parts | {value['id']}, 'MODEL3D_REFERENCE', 'Missing uncertainty target.')
            require(set(uncertainty['evidence']) <= sources, 'MODEL3D_REFERENCE', 'Missing uncertainty source evidence.')
        require(value['geometry'] in value['files'], 'MODEL3D_INVENTORY', 'Primary geometry must occur in the exact file inventory.')
        require(value['geometry']['media_type'] in ('model/gltf-binary', 'model/gltf+json', 'model/obj'),
                'MODEL3D_GEOMETRY', 'Canonical inspection requires a real GLB/glTF/OBJ model.')
        bounds = value['measurements']['bounds']
        require(all(a <= b for a, b in zip(bounds['minimum'], bounds['maximum'])), 'MODEL3D_BOUNDS', 'Bounds are inverted.')
        require(all(value['measurements'][k] <= value['limits'][k] for k in ('vertices', 'triangles')) and
                len(parts) <= value['limits']['parts'], 'MODEL3D_BUDGET', 'Declared geometry exceeds its budget.')
        if value['review']['status'] == 'approved':
            require(bool(value['review']['evidence']), 'MODEL3D_REVIEW', 'An approval claim must reference evidence; it is not authenticated by schema validation.')
        if any(s['provenance']['fixture'] for s in value['sources']):
            require(value['provenance']['fixture'], 'MODEL3D_PROVENANCE', 'Fixture sources cannot become non-fixture assets.')
    elif kind == KINDS['job']:
        require(value['attempts'] <= value['maximum_attempts'], 'MODEL3D_ATTEMPTS', 'Attempt budget exceeded.')
        if value['status'] == 'completed':
            require(bool(value['outputs']) and value['error'] is None, 'MODEL3D_JOB', 'Completed jobs require outputs and cannot contain an active error.')
        if value['status'] == 'failed':
            require(value['error'] is not None, 'MODEL3D_JOB', 'Failed jobs require an actionable error.')
    elif kind == KINDS['export'] and value['status'] == 'complete':
        require(bool(value['files']), 'MODEL3D_EXPORT', 'A complete export needs actual file references.')
    for item in (value.get('provenance'),):
        if item is not None and item['origin'] == 'procedural-fixture':
            require(item['fixture'], 'MODEL3D_PROVENANCE', 'Procedural fixture origin requires fixture=true.')
    dependencies = value.get('dependencies', [])
    identities = [(item['id'], item['version']) for item in dependencies]
    require(len(identities) == len(set(identities)), 'MODEL3D_DUPLICATE', 'Duplicate exact asset dependency.')
    require((value.get('id'), value.get('version')) not in identities,
            'MODEL3D_CYCLE', 'An asset cannot depend on itself.')


def validate_contract(value):
    """Validate strict shape and local semantics; never read files or run tools."""
    finite_json(value)
    require(isinstance(value, dict) and value.get('kind') in KINDS.values(),
            'MODEL3D_KIND', 'Expected an independently versioned model3d document.', stage='model3d')
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise RigError('MODEL3D_DEPENDENCY', 'Install requirements-rig.txt for contract validation.', stage='model3d') from exc
    name = next(key for key, kind in KINDS.items() if kind == value['kind'])
    schema = schemas()['model3d.schema.json']
    schema.pop('oneOf')
    schema['$ref'] = '#/$defs/' + name
    error = next(Draft202012Validator(schema).iter_errors(value), None)
    if error:
        path = '/' + '/'.join(map(str, error.absolute_path))
        raise RigError('MODEL3D_SCHEMA', error.message[:2048], stage='model3d', asset=path)
    _semantic(value)
    files, aliases = {}, {}
    for item in file_references(value):
        path = portable_name(item['path'])
        alias = unicodedata.normalize('NFC', path).casefold()
        require(path == unicodedata.normalize('NFC', path), 'MODEL3D_PATH', 'Paths must use Unicode NFC.')
        require(alias not in aliases or aliases[alias] == path, 'MODEL3D_PATH', 'Case-colliding portable paths.')
        require(path not in files or files[path] == item, 'MODEL3D_HASH_CONFLICT', 'Conflicting records for the same path.')
        aliases[alias], files[path] = path, item
    limits = value.get('limits', LIMITS)
    require(len(files) <= limits['files'] and sum(item['bytes'] for item in files.values()) <= limits['total_bytes'] and
            all(item['bytes'] <= limits['file_bytes'] for item in files.values()),
            'MODEL3D_BUDGET', 'Declared payload inventory exceeds its resource budget.')
    return value
