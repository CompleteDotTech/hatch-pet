"""Canonical library v1 contracts; payload integrity is separate from 3D readiness.

The library is a facade over immutable file records, not a replacement for native
rig/production/state/style authorities. No review or geometry approval is inferred.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from datetime import datetime
import hashlib
import json
import re

from rig_errors import RigError, decode_json, finite_json, object_hash

SCHEMA_VERSION = 1
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_VERSION_BYTES = 256 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
ID_PATTERN = r'^[a-z][a-z0-9_-]{0,63}$'
VERSION_PATTERN = r'^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'
KINDS = ('character', 'rig', 'animation', 'prop', 'material', 'texture', 'environment',
         'light', 'camera', 'prefab', 'reference', 'legacy-pet', 'legacy-cast', 'legacy-clip')


def obj(fields, required=None):
    return dict(type='object', additionalProperties=False, properties=fields,
                required=list(fields if required is None else required))


def arr(items, minimum=0, maximum=256, unique=False):
    return dict(type='array', items=items, minItems=minimum, maxItems=maximum,
                uniqueItems=unique)


def text(maximum=4096):
    return dict(type='string', minLength=1, maxLength=maximum)


def enum(*values):
    return dict(enum=list(values))


def ref(name):
    return {'$ref': '#/$defs/' + name}


ID = dict(type='string', pattern=ID_PATTERN, maxLength=64)
VERSION = dict(type='string', pattern=VERSION_PATTERN, maxLength=32)
SHA = dict(type='string', pattern=r'^[0-9a-f]{64}$')
BOOL = dict(type='boolean')
STRINGS = arr(text(256), maximum=128, unique=True)
FILE_PATH = dict(type='string', minLength=1, maxLength=1024,
                 pattern=r'^[A-Za-z0-9_][A-Za-z0-9_./-]*$')


def definitions():
    exact = obj(dict(id=ID, version=VERSION, sha256=SHA))
    file = obj(dict(path=FILE_PATH, role=ID, sha256=SHA,
                    bytes=dict(type='integer', minimum=1, maximum=MAX_FILE_BYTES),
                    format=enum('glb', 'gltf', 'obj', 'png', 'jpeg', 'webp', 'json', 'binary'),
                    mime_type=text(128), required=BOOL))
    identity = obj(dict(id=ID, namespace=ID, library=ID, slug=ID, name=text(256),
                        kind=enum(*KINDS), subtype=text(128), created_at=text(64),
                        attribution=text(), owner=text(256)))
    dependency = obj(dict(target=exact, purpose=text(256), required=BOOL,
                          origin=enum('authored', 'imported', 'discovered'),
                          relationship=enum('direct', 'transitive'), capabilities=STRINGS))
    metadata = obj(dict(description=text(), category=ID, author=text(256), publisher=text(256),
                        source_url=text(), license=text(256), allowed_uses=STRINGS,
                        keywords=STRINGS, style_refs=arr(exact), capabilities=STRINGS,
                        review_status=enum('unreviewed', 'reviewed-externally')))
    compatibility = obj(dict(coordinate_system=enum('right-handed-y-up-z-forward', 'legacy-2d'),
                             unit_scale=dict(type='number', exclusiveMinimum=0, maximum=1e6),
                             rig_signature=arr(SHA, maximum=1), skeleton_signature=arr(SHA, maximum=1),
                             material_capabilities=STRINGS, texture_channels=STRINGS,
                             animation_channels=STRINGS, renderers=STRINGS, formats=STRINGS,
                             extensions=STRINGS, consumer_capabilities=STRINGS))
    preview = obj(dict(type=enum('thumbnail', 'turntable', 'motion', 'material'),
                       source_version_sha256=SHA, backend=text(256), backend_version=text(128),
                       settings_sha256=SHA, camera_sha256=SHA, lighting_sha256=SHA,
                       file=ref('AssetFile'), width=dict(type='integer', minimum=1, maximum=8192),
                       height=dict(type='integer', minimum=1, maximum=8192),
                       status=enum('generated', 'verified-externally')))
    provenance = obj(dict(method=enum('import', 'generated', 'derived', 'fixture'), origin=text(),
                          fixture=BOOL, sources=arr(ref('AssetFile'), 1),
                          provider=arr(obj(dict(name=text(256), receipt=ref('AssetFile'))), maximum=1),
                          tools=arr(obj(dict(name=text(256), version=text(128)))),
                          parents=arr(exact), edits=STRINGS,
                          license_evidence=arr(ref('AssetFile'), 1),
                          permissions=arr(ref('AssetFile')), uncertainty=STRINGS))
    publication = obj(dict(visibility=enum('private', 'project-local'),
                           distribution=enum('not-evaluated', 'restricted'),
                           license_evaluation=enum('not-evaluated', 'evidence-retained'),
                           inventory=arr(FILE_PATH, 1, unique=True),
                           verification=enum('payload-verified'),
                           integration=enum('not-exercised', 'native-reference')))
    version = obj(dict(schema_version={'const': 1}, kind={'const': 'asset-library-version'},
                       identity=ref('AssetIdentity'), version=VERSION, files=arr(ref('AssetFile'), 1),
                       dependencies=arr(ref('AssetDependency')), metadata=ref('AssetMetadata'),
                       compatibility=ref('AssetCompatibility'), previews=arr(ref('AssetPreview')),
                       provenance=ref('AssetProvenance'), publication=ref('AssetPublication'),
                       manifest_sha256=SHA))
    annotations = obj(dict(schema_version={'const': 1}, asset=exact,
                           revision=dict(type='integer', minimum=0, maximum=2**53-1),
                           tags=STRINGS, favorite=BOOL, note=dict(type='string', maxLength=4096)))
    return dict(AssetIdentity=identity, AssetVersion=version, AssetFile=file,
                AssetDependency=dependency, AssetMetadata=metadata,
                AssetCompatibility=compatibility, AssetPreview=preview,
                AssetProvenance=provenance, AssetPublication=publication,
                AssetAnnotations=annotations, AssetRef=exact)


def schemas():
    definitions_by_name = definitions()
    result = {}
    for name in definitions_by_name:
        selected, pending = {}, [name]
        while pending:
            current = pending.pop()
            if current in selected:
                continue
            selected[current] = definitions_by_name[current]
            def references(node):
                if isinstance(node, dict):
                    if '$ref' in node:
                        pending.append(node['$ref'].rsplit('/', 1)[-1])
                    for child in node.values():
                        references(child)
                elif isinstance(node, list):
                    for child in node:
                        references(child)
            references(selected[current])
        result['asset-library-' + name.removeprefix('Asset').lower() + '.schema.json'] = {
            '$schema': 'https://json-schema.org/draft/2020-12/schema',
            'title': name + ' v1', '$defs': selected, '$ref': '#/$defs/' + name}
    return result


@lru_cache(maxsize=16)
def _validator(kind):
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise RigError('LIBRARY_DEPENDENCY', 'Library validation requires the declared jsonschema dependency.') from exc
    if kind not in definitions():
        raise RigError('LIBRARY_SCHEMA_KIND', 'Unknown library contract kind.', asset=str(kind))
    return Draft202012Validator({'$defs': definitions(), '$ref': '#/$defs/' + kind})


def portable_path(value):
    """Restrict new logical names; legacy file spelling is retained by adapters."""
    if not isinstance(value, str) or not re.fullmatch(FILE_PATH['pattern'], value) or len(value) > 1024:
        raise RigError('LIBRARY_PATH', 'Expected a bounded portable relative file path.', asset=str(value))
    for part in value.split('/'):
        if (not part or part in ('.', '..') or part.endswith('.') or
            part.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}):
            raise RigError('LIBRARY_PATH', 'Unsafe or reserved path component.', asset=value)
    return value


def validate(value, kind='AssetVersion'):
    finite_json(value)
    if len(canonical_bytes(value)) > MAX_MANIFEST_BYTES:
        raise RigError('LIBRARY_LIMIT', 'Contract exceeds 1 MiB.')
    error = next(_validator(kind).iter_errors(value), None)
    if error:
        raise RigError('LIBRARY_SCHEMA', error.message, stage=kind,
                       asset='.'.join(map(str, error.absolute_path)))
    # Nested file records, including original sources/license/preview evidence,
    # obey the same path policy rather than only the runtime payload list.
    def paths(node):
        if isinstance(node, dict):
            if {'path', 'role', 'sha256', 'bytes'} <= node.keys():
                portable_path(node['path'])
            for child in node.values(): paths(child)
        elif isinstance(node, list):
            for child in node: paths(child)
    paths(value)
    if kind == 'AssetVersion':
        try:
            created = datetime.fromisoformat(value['identity']['created_at'].replace('Z', '+00:00'))
            if created.tzinfo is None:
                raise ValueError('timezone required')
        except ValueError as exc:
            raise RigError('LIBRARY_DATE', 'created_at must be an ISO-8601 timestamp with timezone.') from exc
        names = [f['path'].casefold() for f in value['files']]
        if len(set(names)) != len(names):
            raise RigError('LIBRARY_ALIAS', 'Duplicate or case-aliased payload names.')
        ordered = sorted(names)
        if any(b.startswith(a + '/') for a, b in zip(ordered, ordered[1:])):
            raise RigError('LIBRARY_ALIAS', 'File paths cannot also be directories.')
        if sum(f['bytes'] for f in value['files']) > MAX_VERSION_BYTES:
            raise RigError('LIBRARY_LIMIT', 'Version payload exceeds 256 MiB.')
        if not any(f['required'] for f in value['files']):
            raise RigError('LIBRARY_REQUIRED', 'At least one runtime payload must be required.')
        files = {f['path']: f for f in value['files']}
        if set(value['publication']['inventory']) != set(files):
            raise RigError('LIBRARY_INVENTORY', 'Publication inventory must exactly match the payloads.')
        p = value['provenance']
        if p['method'] == 'fixture' and not p['fixture']:
            raise RigError('LIBRARY_ORIGIN', 'Fixture origin cannot be relabeled as production content.')
        if p['method'] == 'derived' and not p['parents']:
            raise RigError('LIBRARY_LINEAGE', 'Derived content requires exact retained parent versions.')
        known_hashes = {x['target']['sha256'] for x in value['dependencies']} | {x['sha256'] for x in p['parents']}
        if any(preview['source_version_sha256'] not in known_hashes for preview in value['previews']):
            raise RigError('LIBRARY_PREVIEW', 'Preview source must be an exact retained dependency or parent version.')
        if p['method'] == 'generated' and not p['provider']:
            raise RigError('LIBRARY_PROVIDER', 'Generated content requires actual retained provider evidence.')
        for record in p['sources'] + p['license_evidence'] + p['permissions'] + [x['receipt'] for x in p['provider']] + [x['file'] for x in value['previews']]:
            if files.get(record['path']) != record:
                raise RigError('LIBRARY_EVIDENCE', 'Evidence must name an exact inventoried payload.', asset=record['path'])
        dependencies = [(x['target']['id'], x['target']['version']) for x in value['dependencies']]
        if len(set(dependencies)) != len(dependencies):
            raise RigError('LIBRARY_DEPENDENCY', 'Dependencies must be unique exact versions.')
        if (value['identity']['id'], value['version']) in dependencies:
            raise RigError('LIBRARY_DEPENDENCY', 'A version cannot depend on itself.')
        if value['manifest_sha256'] != manifest_hash(value):
            raise RigError('LIBRARY_MANIFEST_HASH', 'Manifest hash does not match its immutable content.')
    return value


def manifest_hash(value):
    return object_hash({k: v for k, v in value.items() if k != 'manifest_sha256'})


def seal(value):
    result = deepcopy(value)
    result['manifest_sha256'] = manifest_hash(result)
    return validate(result)


def load_manifest(payload):
    if len(payload) > MAX_MANIFEST_BYTES:
        raise RigError('LIBRARY_LIMIT', 'Manifest exceeds 1 MiB.')
    return validate(decode_json(payload))


def canonical_bytes(value):
    finite_json(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
