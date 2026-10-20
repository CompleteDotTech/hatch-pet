"""Deterministic edits of observed layers, exported separately from faithful sources.

These operations never reconstruct hidden pixels. Recolor is an explicit flat RGB
replacement (texture is replaced); transforms resample supplied pixels only.
"""
from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile

from PIL import Image, ImageChops

from asset_contracts import MAX_SOURCE_PIXELS, hash_object, sha
from decomposition_masks import palette
from decomposition_package import _copy_inventory, _inventory, _validated
from decomposition_reuse import derive_identity
from decomposition_spec import safe_path

MAX_TRANSFORM_PIXELS = MAX_SOURCE_PIXELS * 4
_OPERATIONS = {'hide', 'recolor', 'transform', 'reorder'}


def _number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(label + ' must be a finite number')
    return float(value)


def _settings(operation, color, offset, rotation, scale, z_index):
    if operation not in _OPERATIONS:
        raise ValueError('layer edit operation must be hide, recolor, transform, or reorder')
    if offset is None:
        offset = [0, 0]
    if not isinstance(offset, (list, tuple)) or len(offset) != 2:
        raise ValueError('layer offset requires exactly two finite source-space coordinates')
    offset = [_number(value, 'layer offset') for value in offset]
    rotation, scale = _number(rotation, 'layer rotation'), _number(scale, 'layer scale')
    if abs(rotation) > 36000 or not 0 < scale <= 16:
        raise ValueError('layer rotation is bounded to 36000 degrees and scale must be in (0, 16]')
    if z_index is not None and (type(z_index) is not int or not -100000 <= z_index <= 100000):
        raise ValueError('layer z-index must be an integer from -100000 to 100000')
    if operation == 'recolor':
        if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise ValueError('flat recolor requires an explicit #RRGGBB color')
    elif color is not None:
        raise ValueError('color is supported only by the recolor layer edit')
    if operation == 'reorder' and z_index is None:
        raise ValueError('reorder requires an explicit z-index')
    if operation != 'reorder' and z_index is not None:
        raise ValueError('z-index is supported only by reorder')
    if operation != 'transform' and (offset != [0, 0] or rotation != 0 or scale != 1):
        raise ValueError('offset, rotation, and scale are supported only by transform')
    return {'operation': operation, 'color': color.upper() if color else None, 'offset': offset,
            'rotation_degrees_clockwise': rotation, 'scale': scale, 'z_index': z_index}


def _flat_color(image, color):
    rgb = bytes(int(color[index:index + 2], 16) for index in (1, 3, 5))
    pixels = bytearray(image.tobytes())
    for index in range(0, len(pixels), 4):
        if pixels[index + 3]:
            pixels[index:index + 3] = rgb
    return Image.frombytes('RGBA', image.size, bytes(pixels))


def _mapped(point, pivot, settings):
    angle = math.radians(settings['rotation_degrees_clockwise'] % 360)
    cosine, sine = math.cos(angle), math.sin(angle)
    x, y = point[0] - pivot[0], point[1] - pivot[1]
    scale = settings['scale']
    dx, dy = settings['offset']
    return [pivot[0] + scale * (cosine * x - sine * y) + dx,
            pivot[1] + scale * (sine * x + cosine * y) + dy]


def _transform(image, component, settings, canvas, pixel_art):
    bbox = component['bbox']
    pivot = component['pivot'] or [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]
    # Exact identity/translation avoid an unnecessary interpolation pass.
    rotation = settings['rotation_degrees_clockwise'] % 360
    dx, dy = settings['offset']
    if rotation == 0 and settings['scale'] == 1 and dx.is_integer() and dy.is_integer():
        updated = [bbox[0] + int(dx), bbox[1] + int(dy), bbox[2] + int(dx), bbox[3] + int(dy)]
        if min(updated[:2]) < 0 or updated[2] > canvas[0] or updated[3] > canvas[1]:
            raise ValueError('layer transform would clip component ' + component['id'])
        return image.copy(), updated, _mapped(pivot, pivot, settings)
    corners = [_mapped([x, y], pivot, settings) for x, y in ((bbox[0], bbox[1]), (bbox[2], bbox[1]),
                                                           (bbox[0], bbox[3]), (bbox[2], bbox[3]))]
    pad = 1 if pixel_art else math.ceil(settings['scale'] * 2) + 2
    left = math.floor(min(point[0] for point in corners)) - pad
    top = math.floor(min(point[1] for point in corners)) - pad
    right = math.ceil(max(point[0] for point in corners)) + pad
    bottom = math.ceil(max(point[1] for point in corners)) + pad
    size = (right - left, bottom - top)
    if size[0] * size[1] > MAX_TRANSFORM_PIXELS:
        raise ValueError('transformed layer exceeds the bounded 8-million-pixel work surface')
    if right <= 0 or bottom <= 0 or left >= canvas[0] or top >= canvas[1]:
        raise ValueError('layer transform would move the component outside its canvas')
    angle = math.radians(rotation)
    cosine, sine = math.cos(angle), math.sin(angle)
    inverse = 1 / settings['scale']
    matrix = (cosine * inverse, sine * inverse,
              pivot[0] - bbox[0] + (cosine * (left - pivot[0] - dx) + sine * (top - pivot[1] - dy)) * inverse,
              -sine * inverse, cosine * inverse,
              pivot[1] - bbox[1] + (-sine * (left - pivot[0] - dx) + cosine * (top - pivot[1] - dy)) * inverse)
    transformed = image.transform(size, Image.Transform.AFFINE, matrix,
                                  resample=Image.Resampling.NEAREST if pixel_art else Image.Resampling.BICUBIC,
                                  fillcolor=(0, 0, 0, 0))
    visible = transformed.getchannel('A').getbbox()
    if visible is None:
        raise ValueError('layer transform removes every visible pixel; increase scale or use hide explicitly')
    updated = [left + visible[0], top + visible[1], left + visible[2], top + visible[3]]
    if min(updated[:2]) < 0 or updated[2] > canvas[0] or updated[3] > canvas[1]:
        raise ValueError('layer transform would clip visible pixels of component ' + component['id'])
    return transformed.crop(visible), updated, _mapped(pivot, pivot, settings)


def _dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def edit_layers(root, destination, component_ids, operation, color=None, offset=None,
                rotation=0.0, scale=1.0, z_index=None):
    """Export an edited static character and editable layers without modifying its source."""
    root, destination = Path(root).expanduser().resolve(), Path(destination).expanduser().resolve()
    if destination.exists() or destination == root or destination.is_relative_to(root) or root.is_relative_to(destination):
        raise ValueError('layer edits require a new variant directory outside the decomposition source')
    settings = _settings(operation, color, offset, rotation, scale, z_index)
    if not isinstance(component_ids, (list, tuple)) or not component_ids or any(not isinstance(value, str) for value in component_ids) or len(set(component_ids)) != len(component_ids):
        raise ValueError('layer edits require a nonempty unique component identifier list')
    manifest, _, accepted = _validated(root)
    by_id = {component['id']: component for component in manifest['components']}
    for identifier in component_ids:
        if identifier not in by_id:
            raise ValueError('unknown component for layer edit: ' + identifier)
        if by_id[identifier]['review']['status'] == 'rejected':
            raise ValueError('repair rejected component before editing: ' + identifier)
    if operation == 'reorder' and z_index + len(component_ids) - 1 > 100000:
        raise ValueError('requested consecutive layer order exceeds z-index bound')
    size = (manifest['canvas']['width'], manifest['canvas']['height'])
    if any(abs(value) > max(size) * 16 for value in settings['offset']):
        raise ValueError('layer offset exceeds the bounded source-space edit range')
    source_inventory = _inventory(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.decomposition-layer-edit-', dir=destination.parent))
    try:
        records, identity_components = [], []
        for component in manifest['components']:
            selected = component['id'] in component_ids
            path = safe_path(root, component['asset']['path'])
            if sha(path) != component['asset']['sha256']:
                raise ValueError('decomposition source component changed before layer edit')
            with Image.open(path) as opened:
                image = opened.convert('RGBA')
            if sha(path) != component['asset']['sha256']:
                raise ValueError('decomposition source component changed during layer edit')
            bbox = list(component['bbox'])
            pivot = copy.deepcopy(component['pivot'])
            attachments = copy.deepcopy(component['attachments'])
            order = component['z_index']
            visible = not (selected and operation == 'hide')
            if selected and operation == 'recolor':
                image = _flat_color(image, settings['color'])
            if selected and operation == 'transform':
                image, bbox, pivot = _transform(image, component, settings, size, manifest['canvas']['pixel_art'])
                original_pivot = component['pivot'] or [(component['bbox'][0] + component['bbox'][2]) / 2,
                                                        (component['bbox'][1] + component['bbox'][3]) / 2]
                for attachment in attachments:
                    attachment['point'] = _mapped(attachment['point'], original_pivot, settings)
                for point in [pivot, *(attachment['point'] for attachment in attachments)]:
                    if point is not None and not (0 <= point[0] <= size[0] and 0 <= point[1] <= size[1]):
                        raise ValueError('layer transform moves a pivot or attachment outside the canvas')
            if selected and operation == 'reorder':
                order = z_index + list(component_ids).index(component['id'])
            relative = 'layers/' + component['id'] + '.png'
            (stage / relative).parent.mkdir(parents=True, exist_ok=True)
            image.save(stage / relative, format='PNG')
            record = {'id': component['id'], 'name': component['name'], 'category': component['category'],
                      'parent_id': component['parent_id'], 'side': component['side'], 'visible': visible,
                      'bbox': bbox, 'position': bbox[:2], 'pivot': pivot, 'attachments': attachments,
                      'transform': {'position': bbox[:2], 'rotation': 0.0, 'scale': [1.0, 1.0], 'local_origin': bbox[:2]},
                      'source_transform': component['transform'],
                      'z_index': order, 'asset': {'path': relative, 'sha256': sha(stage / relative)},
                      'source_asset': component['asset'], 'source_mask': component['mask'],
                      'source_provenance': component['provenance'], 'source_review': component['review'],
                      'changed': selected, 'operation': operation if selected else 'unchanged'}
            records.append(record)
            if visible:
                identity_components.append({**component, 'bbox': bbox, 'pivot': pivot, 'attachments': attachments})
        flattened = Image.new('RGBA', size)
        for record in sorted(records, key=lambda item: (item['z_index'], item['id'])):
            if record['visible']:
                with Image.open(stage / record['asset']['path']) as layer:
                    flattened.alpha_composite(layer.convert('RGBA'), tuple(record['position']))
        flattened.save(stage / 'edited.png', format='PNG')
        with Image.open(root / manifest['foreground']['path']) as original:
            difference = ImageChops.difference(original.convert('RGBA'), flattened)
        differences = difference.tobytes()
        different_pixels = sum(any(differences[index:index + 4]) for index in range(0, len(differences), 4))
        identity_manifest = {**manifest, 'components': identity_components,
                             'extensions': {**manifest['extensions'], 'palette': palette(flattened)}}
        # An old explicit palette may require a new human decision after recolor.
        # Preserve all other explicit identity fields; measure visible variant colors.
        if operation == 'recolor' and isinstance(identity_manifest['extensions'].get('identity'), dict):
            identity_manifest['extensions']['identity'] = {key: value for key, value in identity_manifest['extensions']['identity'].items() if key != 'palette'}
        identity = derive_identity(identity_manifest)
        _dump(stage / 'identity.json', identity)
        source_snapshot = stage / 'source' / 'decomposition'
        source_snapshot.mkdir(parents=True)
        _copy_inventory(root, source_snapshot, source_inventory)
        snapshot_manifest, _, _ = _validated(source_snapshot)
        if snapshot_manifest != manifest:
            raise ValueError('decomposition source changed during layer edit')
        record = {'schema_version': 1, 'kind': 'character-layer-edit',
                  'character': manifest['character'], 'canvas': manifest['canvas'],
                  'source': {'source_sha256': manifest['source']['sha256'],
                             'decomposition_sha256': source_inventory['decomposition.json'],
                             'origin': manifest['source']['origin'], 'fixture': manifest['source']['fixture'],
                             'revision': manifest['revision'], 'accepted': accepted,
                             'snapshot_path': 'source/decomposition', 'snapshot_files': source_inventory,
                             'snapshot_inventory_sha256': hash_object(source_inventory)},
                  'operation': {**settings, 'components': list(component_ids)}, 'layers': records,
                  'output': {'path': 'edited.png', 'sha256': sha(stage / 'edited.png')},
                  'identity': {'path': 'identity.json', 'sha256': sha(stage / 'identity.json')},
                  'review': {'status': 'pending', 'note': 'The edited variant requires fresh visual review; historical component approvals cover the source only.'},
                  'validation': {'ok': True, 'clipped_pixels': 0, 'canvas_preserved': True,
                                 'source_fidelity_required': False, 'different_pixels_from_source': different_pixels,
                                 'hidden_geometry_filled': False, 'new_artwork_generated': False},
                  'appearance_policy': 'Flat recolor replaces selected RGB colors and texture while preserving every selected alpha value.' if operation == 'recolor' else 'Only existing observed pixel layers are changed; no concealed anatomy is filled.',
                  'transform_policy': 'Rotation is clockwise in source coordinates around each selected pivot, or its visible bounding-box center. Child layers and joints are not automatically solved.',
                  'resampling': 'nearest' if manifest['canvas']['pixel_art'] else 'bicubic',
                  'animation_ready': False, 'codex_pet_package': False}
        _dump(stage / 'edit.json', record)
        descriptor = {'schema_version': 1, 'kind': 'import', 'layout': 'image', 'files': ['edited.png'],
                      'origin': 'Deterministic character layer edit (' + operation + '), source SHA-256 ' + manifest['source']['sha256'] + ', edit manifest SHA-256 ' + sha(stage / 'edit.json') + '; ' + manifest['source']['origin'] + '. The variant requires visual review; no hidden geometry was filled.',
                      'fixture': manifest['source']['fixture']}
        _dump(stage / 'base-source.json', descriptor)
        files = _inventory(stage)
        _dump(stage / 'edit-receipt.json', {'schema_version': 1, 'kind': 'character-layer-edit-export',
                                         'files': files, 'inventory_sha256': hash_object(files),
                                         'fixture': manifest['source']['fixture'], 'accepted': False})
        if _inventory(root) != source_inventory:
            raise ValueError('decomposition source changed during layer edit')
        if destination.exists():
            raise ValueError('layer variant destination appeared during export; no existing files were replaced')
        os.replace(stage, destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {'export': str(destination), 'edited_image': str(destination / 'edited.png'),
            'operation': operation, 'components': list(component_ids), 'fixture': manifest['source']['fixture'],
            'review_required': True, 'new_artwork_generated': False, 'hidden_geometry_filled': False,
            'source_modified': False, 'different_pixels_from_source': different_pixels,
            'base_import_descriptor': str(destination / 'base-source.json'),
            'appearance_policy': record['appearance_policy'], 'codex_pet_package': False}
