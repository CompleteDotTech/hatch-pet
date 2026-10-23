"""Read-only Model3D verification over a bounded, hash-verified temporary snapshot.

All manifest paths are relative to one explicitly selected project root, including
paths inside dependency manifests. No registry, job store or renderer is created.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.metadata
import platform
import os
from pathlib import Path
import stat
import struct
import tempfile
import unicodedata

from model3d_contracts import KINDS, LIMITS, VERSION, file_references, validate_contract
from rig_errors import RigError, MAX_JSON_BYTES, object_hash, read_json, require, safe_path, sha256


@contextmanager
def _open_payload(root, name):
    """Use existing portable-path rules and reject link/special-file payloads.

On platforms with openat/O_NOFOLLOW, hold each directory descriptor so a parent
rename cannot redirect the read. The portable fallback rechecks the path and
file identity; hostile concurrent directory replacement still needs OS isolation.
    """
    target = safe_path(root, name, exists=True)
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NONBLOCK', 0)
    descriptors = []
    try:
        if os.open in os.supports_dir_fd and hasattr(os, 'O_NOFOLLOW'):
            directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            descriptors.append(os.open(root, directory_flags))
            parts = Path(name).parts
            for part in parts[:-1]:
                descriptors.append(os.open(part, directory_flags, dir_fd=descriptors[-1]))
            fd = os.open(parts[-1], flags | os.O_NOFOLLOW, dir_fd=descriptors[-1])
        else:
            fd = os.open(target, flags)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            require(stat.S_ISREG(before.st_mode), 'MODEL3D_FILE', 'Payload must be a regular file.', asset=name)
            current = safe_path(root, name, exists=True).stat()
            require((current.st_dev, current.st_ino) == (before.st_dev, before.st_ino),
                    'MODEL3D_CHANGED', 'Payload changed while opening.', asset=name)
            yield stream, before
            after = os.fstat(stream.fileno())
            current = safe_path(root, name, exists=True).stat()
            require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                    (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) and
                    (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns, current.st_ctime_ns) ==
                    (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                    'MODEL3D_CHANGED', 'Payload changed during verification.', asset=name)
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


class _Snapshot:
    def __init__(self, root, destination, limits):
        self.root, self.destination, self.limits = root, destination, limits
        self.files, self.aliases = {}, {}
        self.total = 0

    def capture(self, record):
        name = record['path']
        alias = unicodedata.normalize('NFC', name).casefold()
        require(alias not in self.aliases or self.aliases[alias] == name,
                'MODEL3D_PATH', 'Dependency closure contains path aliases.', asset=name)
        require(name not in self.files or self.files[name] == record,
                'MODEL3D_HASH_CONFLICT', 'Dependency closure contains conflicting payload declarations.', asset=name)
        if name in self.files:
            return self.destination / name
        require(len(self.files) < self.limits['files'] and record['bytes'] <= self.limits['file_bytes'] and
                self.total + record['bytes'] <= self.limits['total_bytes'],
                'MODEL3D_BUDGET', 'Expanded payload closure exceeds its resource budget.', asset=name)
        target = self.destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        digest, total = hashlib.sha256(), 0
        with _open_payload(self.root, name) as (source, info), target.open('xb') as output:
            require(info.st_size == record['bytes'], 'MODEL3D_SIZE', 'Payload size does not match its declaration.', asset=name)
            for chunk in iter(lambda: source.read(min(1024**2, record['bytes'] + 1)), b''):
                total += len(chunk)
                require(total <= record['bytes'], 'MODEL3D_SIZE', 'Payload grew beyond its declared size.', asset=name)
                digest.update(chunk)
                output.write(chunk)
        require(total == record['bytes'] and digest.hexdigest() == record['sha256'],
                'MODEL3D_HASH', 'Payload content does not match its declared SHA-256.', asset=name)
        if record['media_type'].startswith('image/'):
            try:
                from PIL import Image, UnidentifiedImageError
                with Image.open(target) as image:
                    expected = {'image/png': 'PNG', 'image/jpeg': 'JPEG', 'image/webp': 'WEBP'}
                    require(image.format == expected[record['media_type']], 'MODEL3D_FORMAT',
                            'Image encoding does not match its media declaration.', asset=name)
                    require(image.width * image.height <= min(16_777_216, self.limits['memory_bytes'] // 16),
                            'MODEL3D_BUDGET', 'Decoded texture exceeds its pixel/memory budget.', asset=name)
                    require(getattr(image, 'n_frames', 1) == 1, 'MODEL3D_TEXTURE',
                            'This contract accepts static source textures only.', asset=name)
                    image.load()
            except ImportError as exc:
                raise RigError('MODEL3D_DEPENDENCY', 'Pillow is required to inspect source images.') from exc
            except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
                raise RigError('MODEL3D_IMAGE', 'Image payload cannot be decoded safely.', asset=name) from exc
        self.files[name] = dict(record)
        self.aliases[alias] = name
        self.total += total
        return target


def _inspect_asset(document, snapshot):
    """Decode genuine geometry through the repository's existing import authority."""
    try:
        from rig_contracts import DEFAULT_LIMITS
        from rig_import import load_character_model
    except ImportError as exc:
        raise RigError('MODEL3D_DEPENDENCY', 'Install Pillow and requirements-rig.txt for geometry inspection.', stage='model3d') from exc
    record = document['geometry']
    expected = {'model/gltf-binary': '.glb', 'model/gltf+json': '.gltf', 'model/obj': '.obj'}
    require(Path(record['path']).suffix.lower() == expected[record['media_type']],
            'MODEL3D_FORMAT', 'Declared model media type and supported extension disagree.')
    limits = document['limits']
    backend_limits = dict(DEFAULT_LIMITS, source_bytes=limits['file_bytes'],
                          dependency_bytes=limits['total_bytes'], vertices=limits['vertices'],
                          triangles=limits['triangles'], memory_bytes=limits['memory_bytes'])
    try:
        model = load_character_model(snapshot.destination / record['path'], limits=backend_limits)
    except RigError:
        raise
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError, struct.error) as exc:
        raise RigError('MODEL3D_MODEL', 'Malformed model rejected at the existing importer boundary.',
                       stage='model3d', asset=record['path']) from exc
    actual_dependencies = {p.relative_to(snapshot.destination).as_posix() for p in model.source_files}
    inventory = {r['path'] for r in document['files']}
    require(actual_dependencies <= inventory, 'MODEL3D_INVENTORY',
            'Actual model resources are absent from the asset file inventory.',
            observed=sorted(actual_dependencies - inventory))
    geometry = model.geometry
    ids = {mesh.id for mesh in geometry.meshes}
    declared_ids = {name for part in document['parts'] for name in part['mesh_ids']}
    require(declared_ids == ids, 'MODEL3D_MESH_BINDING',
            'Semantic part bindings must cover the actual decoded mesh identities exactly.',
            expected=sorted(ids), observed=sorted(declared_ids))
    for material in document['materials']:
        require(material['slot'] < len(geometry.materials), 'MODEL3D_MATERIAL', 'Material slot is absent from the model.')
    measured = document['measurements']
    require(measured['vertices'] == geometry.vertex_count and measured['triangles'] == geometry.triangle_count,
            'MODEL3D_MEASUREMENTS', 'Declared counts differ from actual decoded geometry.',
            expected=dict(vertices=geometry.vertex_count, triangles=geometry.triangle_count), observed=measured)
    actual_bounds = model.report['bounds']
    for name, actual in [('minimum', actual_bounds[0]), ('maximum', actual_bounds[1])]:
        require(all(abs(a-b) <= 1e-6 * max(1., abs(a), abs(b)) for a, b in zip(actual, measured['bounds'][name])),
                'MODEL3D_MEASUREMENTS', 'Declared bounds differ from actual geometry; tolerance is 1e-6 relative/absolute meters.')
    require(not model.report.get('fixture') or document['provenance']['fixture'],
            'MODEL3D_PROVENANCE', 'Embedded fixture provenance cannot be relabeled as production.')
    from rig_jobs import code_signature
    return dict(asset_id=document['id'], version=document['version'],
                rig_implementation_sha256=code_signature(),
                software={name: importlib.metadata.version(name) for name in ('numpy', 'Pillow')},
                geometry_sha256=record['sha256'], importer='rig_import.load_character_model',
                inspection=model.report, mesh_ids=sorted(ids),
                skin_bindings=len(model.weights), animation_clips=len(model.clips),
                material_parameter_equivalence='not-assessed', visual_approval='not-assessed')


def validate_document(document, root=None, *, structural_only=False):
    """Validate shape, semantics and the complete declared immutable file closure.

The default path decodes each referenced asset's real geometry. A structural-only
report explicitly leaves payloads and geometry unverified. Returns observations,
not production readiness, an authenticated review, or a successful generation job.
Raises RigError for expected invalid input; does not modify the selected root.
    """
    validate_contract(document)
    report = dict(schema_version=1, kind='model3d-validation', implementation_version=VERSION,
                  document_kind=document['kind'], document_sha256=object_hash(document),
                  implementation_sha256=object_hash({p.name: sha256(p) for p in
                      sorted(Path(__file__).parent.glob('model3d*.py'))}),
                  software=dict(python=platform.python_version(), jsonschema=importlib.metadata.version('jsonschema')),
                  contract_valid=True, payloads_verified=False, geometry_inspected=False,
                  provider_execution='not-assessed', visual_approval='not-assessed',
                  licensing_approval='not-assessed', geometry=[], files=[])
    if structural_only:
        report['mode'] = 'structural-only'
        return report
    require(root is not None, 'MODEL3D_ROOT', 'Payload validation needs an explicit project root.')
    root = Path(root).absolute()
    require(root.is_dir() and not root.is_symlink(), 'MODEL3D_ROOT', 'Choose a regular project directory, not a link.')
    root = root.resolve()
    active, identities, results = set(), {}, {}
    with tempfile.TemporaryDirectory(prefix='hatch-model3d-verify-') as temporary:
        snapshot = _Snapshot(root, Path(temporary), document.get('limits', LIMITS))

        def visit(value, depth):
            validate_contract(value)
            require(depth <= snapshot.limits['dependency_depth'], 'MODEL3D_DEPTH', 'Asset dependency depth exceeds the selected budget.')
            key = (value.get('id'), value.get('version')) if value['kind'] == KINDS['asset'] else None
            require(key is None or key not in active, 'MODEL3D_CYCLE', 'Asset dependency cycle detected.')
            if key is not None:
                active.add(key)
            names, height = set(), 0
            for record in file_references(value):
                snapshot.capture(record)
                names.add(record['path'])
            if value['kind'] == KINDS['job']:
                record = value['request']
                require(record['media_type'] == 'application/json' and record['bytes'] <= MAX_JSON_BYTES,
                        'MODEL3D_MANIFEST', 'Job requests require bounded JSON documents.')
                request = read_json(snapshot.destination / record['path'])
                require(isinstance(request, dict) and request.get('kind') == KINDS['request'] and
                        request.get('asset_id') == value['asset_id'],
                        'MODEL3D_REFERENCE', 'Job request must identify the same target asset.')
                request_names, request_height = visit(request, depth + 1)
                names.update(request_names)
                height = request_height + 1
            dependencies = list(value.get('dependencies', []))
            if value['kind'] == KINDS['export']:
                dependencies.append(value['asset'])
            for dependency in dependencies:
                record = dependency['manifest']
                require(record['media_type'] == 'application/json' and record['bytes'] <= MAX_JSON_BYTES,
                        'MODEL3D_MANIFEST', 'Dependency manifests require bounded JSON payloads.')
                child = read_json(snapshot.destination / record['path'])
                child_key = dependency['id'], dependency['version']
                require(isinstance(child, dict) and child.get('kind') == KINDS['asset'] and
                        (child.get('id'), child.get('version')) == child_key,
                        'MODEL3D_REFERENCE', 'Dependency manifest does not match its exact asset identity.')
                require(child_key not in active, 'MODEL3D_CYCLE', 'Asset dependency cycle detected.')
                require(child_key not in identities or identities[child_key] == record['sha256'],
                        'MODEL3D_VERSION_CONFLICT', 'An immutable asset version has conflicting manifest hashes.')
                identities[child_key] = record['sha256']
                if child_key not in results:
                    results[child_key] = visit(child, depth + 1)
                child_names, child_height = results[child_key]
                height = max(height, child_height + 1)
                require(depth + height <= snapshot.limits['dependency_depth'],
                        'MODEL3D_DEPTH', 'Cached dependency closure exceeds the selected depth budget.')
                names.update(child_names)
                if value['kind'] == KINDS['asset'] and child['provenance']['fixture']:
                    require(value['provenance']['fixture'], 'MODEL3D_PROVENANCE', 'Fixture dependencies cannot become production assets.')
            limits = value.get('limits', LIMITS)
            require(height <= limits['dependency_depth'], 'MODEL3D_DEPTH', 'Transitive dependencies exceed a document depth budget.')
            require(len(names) <= limits['files'] and sum(snapshot.files[n]['bytes'] for n in names) <= limits['total_bytes'],
                    'MODEL3D_BUDGET', 'Transitive payload closure exceeds an asset budget.')
            if value['kind'] == KINDS['asset']:
                report['geometry'].append(_inspect_asset(value, snapshot))
                active.remove(key)
            return names, height

        visit(document, 0)
        report.update(mode='verified-snapshot', payloads_verified=True,
                      geometry_inspected=bool(report['geometry']),
                      files=[snapshot.files[name] for name in sorted(snapshot.files)],
                      verified_bytes=snapshot.total,
                      dependency_asset_count=len(identities),
                      path_race_protection='directory-descriptors' if os.open in os.supports_dir_fd and hasattr(os, 'O_NOFOLLOW')
                      else 'portable-recheck-needs-isolation-against-hostile-writers')
    return report


def validate_file(path, root=None, *, structural_only=False):
    path = Path(path).absolute()
    selected_root = Path(root).absolute() if root is not None else path.parent
    require(not selected_root.is_symlink() and selected_root.is_dir(), 'MODEL3D_ROOT', 'Choose a regular project directory.')
    try:
        relative = path.relative_to(selected_root).as_posix()
    except ValueError as exc:
        raise RigError('MODEL3D_PATH', 'Manifest is outside the selected project root.', stage='model3d') from exc
    with _open_payload(selected_root, relative) as (stream, info):
        require(info.st_size <= MAX_JSON_BYTES, 'MODEL3D_MANIFEST', 'Manifest exceeds the JSON budget.')
        from rig_errors import decode_json
        document = decode_json(stream.read(MAX_JSON_BYTES + 1))
    return validate_document(document, selected_root, structural_only=structural_only)
