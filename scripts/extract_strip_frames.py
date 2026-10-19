#!/usr/bin/env python3
"""Extract conservative equal-slot rows while preserving source coordinates and scale."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import uuid

from PIL import Image
from profile_spec import load_profile
from asset_contracts import RESAMPLING, check_image, extraction_projection

_DEFAULT = load_profile()
CELL_WIDTH, CELL_HEIGHT = _DEFAULT['layout']['cell_width'], _DEFAULT['layout']['cell_height']
ROW_FRAME_COUNTS = {s['id']: s['frames'] for s in _DEFAULT['states']}
EXTRACTION_SCHEMA = 4
EXTRACTION_ALGORITHM = 'bounded-viewports-v4'
SEGMENTATION_STRATEGY = 'equal-slot-boundaries-8-connected-core-and-bridge-checks'
CONFIG_DEFAULTS = {'background': 'auto', 'key_threshold': 48.0, 'holes': 'preserve', 'edge_cleanup': True}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def object_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def extractor_fingerprint():
    scripts = Path(__file__).parent
    return object_hash({name: digest(scripts / name) for name in
                        ('extract_strip_frames.py', 'extraction_annotations.py', 'asset_contracts.py')})


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def extraction_ownership(root):
    """The OS releases this lock after interruption; the lock file is not ownership."""
    root = Path(root).resolve()
    lock = root / '.extraction.lock'
    if lock.resolve() != lock:
        raise ValueError('extraction lock must not be a symbolic link')
    with lock.open('a+b') as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError('another extractor owns this frames directory') from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def parse_states(raw):
    states = list(ROW_FRAME_COUNTS) if raw.strip().lower() == 'all' else [x.strip() for x in raw.split(',') if x.strip()]
    if not states or len(states) != len(set(states)) or set(states) - set(ROW_FRAME_COUNTS):
        raise ValueError('states must be distinct supported state identifiers')
    return states


def parse_hex_color(value):
    if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        raise ValueError('expected #RRGGBB')
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def load_extraction_config(run_root):
    """Resolve immutable request defaults and the separately versioned calibration."""
    root = Path(run_root)
    request_path, settings_path = root / 'pet_request.json', root / 'extraction-settings.json'
    request = json.loads(request_path.read_text(encoding='utf-8')) if request_path.is_file() else {}
    settings = json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.is_file() else {}
    if not isinstance(request, dict) or not isinstance(settings, dict) or not isinstance(request.get('extraction', {}), dict):
        raise ValueError('extraction request/settings must be JSON objects')
    config = {**CONFIG_DEFAULTS, **request.get('extraction', {}), **settings}
    if config.get('shared_scale') is None:
        config.pop('shared_scale', None)
    key = config.get('chroma_key', request.get('chroma_key', {'hex': '#00FF00'}))
    if isinstance(key, dict):
        key = key.get('hex') or ('#' + ''.join(f'{c:02X}' for c in key.get('rgb', [])))
    config['chroma_key'] = list(parse_hex_color(key))
    validate_extraction_config(config)
    return config


def validate_extraction_config(config):
    if config.get('background') not in ('auto', 'alpha', 'chroma'):
        raise ValueError('extraction background must be auto, alpha, or chroma')
    threshold = config.get('key_threshold')
    if type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 <= threshold <= 442:
        raise ValueError('extraction key_threshold must be a finite number from 0 to 442')
    if config.get('holes') not in ('preserve', 'key') or type(config.get('edge_cleanup')) is not bool:
        raise ValueError('extraction holes must be preserve/key and edge_cleanup must be boolean')
    if config.get('shared_scale') is not None and (type(config['shared_scale']) not in (int, float) or not math.isfinite(config['shared_scale']) or not 0 < config['shared_scale'] <= 100):
        raise ValueError('extraction shared_scale must be finite, positive, and <=100')


def load_chroma_key(decoded_dir, override):
    return parse_hex_color(override) if override else tuple(load_extraction_config(Path(decoded_dir).parent)['chroma_key'])


def normalize(image):
    rgba = image.convert('RGBA')
    data = bytearray(rgba.tobytes())
    for i in range(0, len(data), 4):
        if not data[i + 3]:
            data[i:i + 3] = b'\x00\x00\x00'
    return Image.frombytes('RGBA', rgba.size, bytes(data))


def color_distance(r, g, b, key):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip((r, g, b), key)))


def pixels(image):
    """Pillow 14-compatible pixel access, retaining support for earlier releases."""
    return image.get_flattened_data() if hasattr(image, 'get_flattened_data') else image.getdata()


def _edge_indices(width, height):
    return set(range(width)) | set(range((height - 1) * width, height * width)) | set(range(0, width * height, width)) | set(range(width - 1, width * height, width))


def _neighbors(i, width, height, diagonal=False):
    x, y = i % width, i // width
    offsets = ((-1, 0), (1, 0), (0, -1), (0, 1))
    if diagonal:
        offsets += ((-1, -1), (-1, 1), (1, -1), (1, 1))
    for dx, dy in offsets:
        nx, ny = x + dx, y + dy
        if 0 <= nx < width and 0 <= ny < height:
            yield ny * width + nx


def mask_background(image, key, threshold=48, mode='auto', holes='preserve', edge_cleanup=True):
    """Remove connected key background, preserving enclosed colors unless opted in.

    Edge cleanup only unmixes a boundary pixel when a nearby foreground sample and
    the known key explain its color. It never performs blanket color erosion.
    """
    validate_extraction_config({'background': mode, 'key_threshold': threshold, 'holes': holes, 'edge_cleanup': edge_cleanup})
    rgba = image.convert('RGBA')
    data = list(pixels(rgba))
    width, height = rgba.size
    edges = _edge_indices(width, height)
    candidate = [color_distance(*p[:3], key) <= threshold for p in data]
    key_edge_fraction = sum(candidate[i] and data[i][3] > 0 for i in edges) / max(1, len(edges))
    transparent_edge_fraction = sum(data[i][3] == 0 for i in edges) / max(1, len(edges))
    has_alpha = any(p[3] < 255 for p in data)
    has_zero = any(p[3] == 0 for p in data)
    authoritative_alpha = has_zero and not (key_edge_fraction >= .5 and transparent_edge_fraction < .5)
    warnings = []
    if mode == 'alpha' or (mode == 'auto' and authoritative_alpha):
        if not has_zero:
            warnings.append('alpha mode has no fully transparent pixels; inspect opaque background')
        return normalize(rgba), {'mode': 'alpha', 'removed_pixels': 0, 'cleaned_edge_pixels': 0, 'warnings': warnings, 'key_edge_fraction': key_edge_fraction}
    if mode == 'auto' and has_alpha:
        warnings.append('incidental alpha did not establish a transparent background; used edge-connected chroma')
    seen = bytearray(len(data))
    stack = [i for i in edges if candidate[i] or data[i][3] == 0]
    for i in stack:
        seen[i] = 1
    while stack:
        i = stack.pop()
        for j in _neighbors(i, width, height):
            if not seen[j] and (candidate[j] or data[j][3] == 0):
                seen[j] = 1
                stack.append(j)
    interior = sum(candidate[i] and not seen[i] and data[i][3] > 0 for i in range(len(data)))
    if holes == 'key':
        for i, matches in enumerate(candidate):
            if matches:
                seen[i] = 1
        if interior:
            warnings.append(f'explicit holes=key removed {interior} enclosed key-adjacent pixels; inspect foreground collisions')
    elif interior:
        warnings.append(f'{interior} enclosed key-adjacent pixels preserved; use alpha or explicitly classify key-colored holes')
    output = data[:]
    for i, removed in enumerate(seen):
        if removed:
            output[i] = (0, 0, 0, 0)
    cleaned = 0
    if edge_cleanup:
        for i, pixel in enumerate(data):
            if seen[i] or not pixel[3] or not any(seen[j] for j in _neighbors(i, width, height, True)):
                continue
            x, y = i % width, i // width
            samples = []
            for ny in range(max(0, y - 2), min(height, y + 3)):
                for nx in range(max(0, x - 2), min(width, x + 3)):
                    j = ny * width + nx
                    if not seen[j] and data[j][3] >= pixel[3] and not candidate[j]:
                        samples.append(data[j])
            if not samples:
                continue
            foreground = max(samples, key=lambda p: color_distance(*p[:3], key))
            vector = [foreground[c] - key[c] for c in range(3)]
            norm = sum(v * v for v in vector)
            if not norm:
                continue
            coverage = sum((pixel[c] - key[c]) * vector[c] for c in range(3)) / norm
            residual = math.sqrt(sum((pixel[c] - key[c] - coverage * vector[c]) ** 2 for c in range(3)))
            if .05 < coverage < .98 and residual <= min(12, max(2, threshold * .2)):
                output[i] = (*foreground[:3], max(1, round(pixel[3] * coverage)))
                cleaned += 1
    removed = sum(seen)
    if not removed:
        warnings.append('no edge-connected key background found; alpha or source repair may be required')
    out = Image.new('RGBA', rgba.size)
    out.putdata(output)
    return normalize(out), {'mode': 'edge-connected-chroma', 'removed_pixels': removed, 'cleaned_edge_pixels': cleaned, 'enclosed_key_pixels': interior, 'holes': holes, 'warnings': warnings, 'key_edge_fraction': key_edge_fraction}


def remove_chroma_background(image, chroma_key, threshold):
    return mask_background(image, chroma_key, threshold)[0]


def connected_components(image, alpha_threshold=0):
    width, height = image.size
    data = image.getchannel('A').tobytes()
    visited = bytearray(len(data))
    result = []
    for start, alpha in enumerate(data):
        if alpha <= alpha_threshold or visited[start]:
            continue
        stack, pixels = [start], []
        visited[start] = 1
        left, top, right, bottom = width, height, 0, 0
        while stack:
            i = stack.pop()
            pixels.append(i)
            x, y = i % width, i // width
            left, top, right, bottom = min(left, x), min(top, y), max(right, x + 1), max(bottom, y + 1)
            for j in _neighbors(i, width, height, True):
                if not visited[j] and data[j] > alpha_threshold:
                    visited[j] = 1
                    stack.append(j)
        bbox = (left, top, right, bottom)
        result.append({'pixels': pixels, 'area': len(pixels), 'bbox': bbox, 'center_x': (left + right) / 2})
    return result


def component_bounds(group):
    return (min(c['bbox'][0] for c in group), min(c['bbox'][1] for c in group), max(c['bbox'][2] for c in group), max(c['bbox'][3] for c in group))


def _bridge_evidence(component, width):
    """Detect broad silhouettes connected only through a long, thin horizontal neck."""
    left, top, right, bottom = component['bbox']
    if right - left < 12 or bottom - top < 8:
        return None
    columns = [0] * (right - left)
    for i in component['pixels']:
        columns[i % width - left] += 1
    threshold = max(1, int(max(columns) * .08))
    minimum_gap = max(3, math.ceil((right - left) * .06))
    start = None
    for offset, count in enumerate(columns + [max(columns)]):
        if count <= threshold:
            start = offset if start is None else start
            continue
        if start is not None and offset - start >= minimum_gap:
            before, after = sum(columns[:start]), sum(columns[offset:])
            if min(before, after) >= component['area'] * .25:
                return {'columns': [left + start, left + offset], 'maximum_neck_pixels': threshold, 'side_areas': [before, after]}
        start = None
    return None


def analyze_slots(strip, frame_count, allow_detached=False, overrides=None):
    if strip.width < frame_count:
        raise ValueError('source narrower than frame count')
    groups, core_groups = [[] for _ in range(frame_count)], [[] for _ in range(frame_count)]
    slot_width = strip.width / frame_count
    maximum_alpha = strip.getchannel('A').getextrema()[1]
    if maximum_alpha < 16:
        raise ValueError('no sufficiently visible pose; alpha is below 16')
    core_threshold = min(127, max(1, maximum_alpha // 2))
    for destination, components in ((groups, connected_components(strip)), (core_groups, connected_components(strip, core_threshold))):
        for component in components:
            left, top, right, bottom = component['bbox']
            slot = min(frame_count - 1, int(component['center_x'] / slot_width))
            if left < round(slot * slot_width) or right > round((slot + 1) * slot_width):
                raise ValueError(f'merged or boundary-crossing pose at {component["bbox"]}; regenerate with clear slot gutters')
            destination[slot].append(component)
    evidence = []
    for index, group in enumerate(groups):
        permissions = (overrides or {}).get(index, [])
        def permits(box, kind):
            from extraction_annotations import contains
            return any(p['permit'] == kind and contains(p['bounds'], box) for p in permissions)
        if not group or not core_groups[index]:
            raise ValueError(f'missing pose in slot {index}')
        ordered = sorted(group, key=lambda c: c['area'], reverse=True)
        cores = sorted(core_groups[index], key=lambda c: c['area'], reverse=True)
        major = [c for c in cores if c['area'] >= max(4, cores[0]['area'] * .20)]
        if len(major) > 1 and any(not permits(c['bbox'], 'disconnected') for c in major[1:]):
            raise ValueError(f'ambiguous extra complete pose or disconnected major part in slot {index}: {len(major)} opaque-core components; inspect faint connections and regenerate')
        bridge = _bridge_evidence(cores[0], strip.width)
        if bridge and not permits(cores[0]['bbox'], 'bridge'):
            raise ValueError(f'ambiguous merged poses in slot {index}: broad silhouettes connected through a narrow bridge at columns {bridge["columns"]}; inspect source')
        if ordered[1:] and not allow_detached:
            main = ordered[0]['bbox']
            limit = max(3, min(main[2] - main[0], main[3] - main[1]) * .2)
            for component in ordered[1:]:
                box = component['bbox']
                gap = max(main[0] - box[2], box[0] - main[2], main[1] - box[3], box[1] - main[3], 0)
                if gap > limit and not permits(box, 'disconnected'):
                    raise ValueError(f'uncertain detached detail in slot {index} at {box}; profile must permit detached details or source needs repair')
        evidence.append({'slot': index, 'bounds': list(component_bounds(group)), 'components': len(group), 'core_components': len(cores), 'major_components': len(major), 'pixels': sum(c['area'] for c in group), 'core_pixels': sum(c['area'] for c in cores), 'narrow_bridge': None})
    return groups, {'strategy': SEGMENTATION_STRATEGY, 'confidence': 'geometry-consistent-semantic-review-required', 'slots': evidence, 'alpha_connectivity': 8, 'alpha_threshold': 0, 'core_alpha_threshold': core_threshold, 'source_size': list(strip.size)}


def component_frame_groups(strip, frame_count):
    return analyze_slots(strip, frame_count)[0]


def render_slots(strip, frame_count, cell_size=(192, 208), alignment='source', scale=None, padding=5, anchor=(.5, .5), resampling='lanczos'):
    """Use one viewport and one scale for the row; slot coordinates preserve jumping."""
    slot_width, viewport_height = strip.width / frame_count, strip.height
    if resampling not in RESAMPLING:
        raise ValueError('unsupported resampling filter')
    if alignment not in ('source', 'row', 'center', 'bottom'):
        raise ValueError(f'unsupported alignment {alignment}')
    if type(padding) is not int or not 0 <= padding < min(cell_size) / 2:
        raise ValueError('padding must leave a positive cell viewport')
    if len(anchor) != 2 or any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1 for x in anchor):
        raise ValueError('anchor must contain two finite normalized coordinates')
    boxes = [strip.crop((round(i * slot_width), 0, round((i + 1) * slot_width), viewport_height)).getbbox() for i in range(frame_count)]
    if any(box is None for box in boxes):
        raise ValueError('cannot render a missing pose')
    top, bottom = 0, viewport_height
    if alignment == 'row':
        top, bottom = min(b[1] for b in boxes), max(b[3] for b in boxes)
    view_height = bottom - top
    available = (cell_size[0] - padding * 2, cell_size[1] - padding * 2)
    chosen = min(available[0] / math.ceil(slot_width), available[1] / view_height, 1.0) if scale is None else scale
    if type(chosen) not in (int, float) or not math.isfinite(chosen) or not 0 < chosen <= 100:
        raise ValueError('scale must be finite, positive, and <=100')
    if math.ceil(slot_width) * chosen > available[0] + 1e-9 or view_height * chosen > available[1] + 1e-9:
        raise ValueError('shared scale clips padded source viewport; use a smaller calibration scale')
    result = []
    for i in range(frame_count):
        view = strip.crop((round(i * slot_width), top, round((i + 1) * slot_width), bottom))
        if alignment in ('center', 'bottom'):
            box = view.getbbox()
            sprite = view.crop(box)
            view = Image.new('RGBA', view.size)
            view.alpha_composite(sprite, ((view.width - sprite.width) // 2, (view.height - sprite.height) // 2 if alignment == 'center' else view.height - sprite.height))
        view = view.resize((max(1, round(view.width * chosen)), max(1, round(view.height * chosen))), RESAMPLING[resampling])
        offset = (padding + round((available[0] - view.width) * anchor[0]), padding + round((available[1] - view.height) * anchor[1]))
        canvas = Image.new('RGBA', cell_size)
        canvas.alpha_composite(view, offset)
        result.append(normalize(canvas))
    return result, {'alignment': alignment, 'source_viewport': [slot_width, top, view_height], 'source_size': list(strip.size), 'scale': chosen, 'cell_size': list(cell_size), 'padding': padding, 'anchor': list(anchor), 'resampling': resampling,
                    'source_bounds': boxes, 'output_bounds': [list(f.getbbox()) for f in result],
                    'baseline_pixels': [f.getbbox()[3] for f in result], 'viewport_offset': list(offset)}


def extract_component_frames(strip, frame_count):
    analyze_slots(strip, frame_count)
    return render_slots(strip, frame_count)[0]


def extract_slot_frames(strip, frame_count):
    return extract_component_frames(strip, frame_count)


def extract_stable_slot_frames(strip, frame_count):
    return extract_component_frames(strip, frame_count)


def fit_to_cell(image):
    return render_slots(image, 1)[0][0]


def fit_viewport_to_cell(image):
    return fit_to_cell(image)


def extraction_configuration(profile, state, config, method='auto', alignment=None, scale=None):
    spec = next((s for s in (profile or {}).get('states', []) if s['id'] == state), {})
    policy = spec.get('alignment', {'coordinate_policy': 'slot', 'scale_policy': 'row', 'padding': 5})
    coordinate = policy.get('coordinate_policy', 'slot')
    chosen_alignment = alignment or {'slot': 'source', 'center': 'center', 'baseline': 'bottom'}[coordinate]
    scale_policy = policy.get('scale_policy', 'row')
    chosen_scale = scale
    if chosen_scale is None and scale_policy == 'none':
        chosen_scale = 1.0
    if chosen_scale is None and scale_policy == 'shared':
        chosen_scale = config.get('shared_scale') or policy.get('scale')
        if chosen_scale is None:
            raise ValueError('shared scale policy requires extraction-settings.json shared_scale calibration')
    return {'chroma_key': list(config['chroma_key']), 'key_threshold': float(config['key_threshold']), 'background': config['background'], 'holes': config['holes'], 'edge_cleanup': config['edge_cleanup'], 'requested_method': method, 'alignment': chosen_alignment, 'scale_policy': scale_policy, 'requested_scale': chosen_scale, 'padding': policy.get('padding', 5), 'anchor': list(policy.get('anchor', [.5, .5])), 'resampling': policy.get('resampling', 'lanczos')}


def extract_state(strip_path, state, output_root, chroma_key, threshold, method, profile=None, alpha_mode='auto', alignment=None, scale=None, extraction_config=None):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', state):
        raise ValueError('state must be a safe lowercase identifier')
    config = {**CONFIG_DEFAULTS, 'chroma_key': list(chroma_key), 'key_threshold': threshold, 'background': alpha_mode, **(extraction_config or {})}
    validate_extraction_config(config)
    spec = next((s for s in (profile or {}).get('states', []) if s['id'] == state), {})
    count = spec.get('frames', ROW_FRAME_COUNTS.get(state))
    if not count:
        raise ValueError(f'unknown state {state}')
    policy = extraction_configuration(profile, state, config, method, alignment, scale)
    check_image(strip_path)
    with Image.open(strip_path) as source:
        strip, mask = mask_background(source, tuple(config['chroma_key']), config['key_threshold'], config['background'], config['holes'], config['edge_cleanup'])
    annotation_path = Path(output_root).parent / 'annotations' / (state + '.json')
    annotation = json.loads(annotation_path.read_text(encoding='utf-8')) if annotation_path.is_file() else None
    original_size = list(strip.size)
    overrides = None
    try:
        if annotation:
            from extraction_annotations import annotated_source
            strip, overrides = annotated_source(strip, count, annotation, digest(strip_path))
        _, evidence = analyze_slots(strip, count, (profile or {}).get('validation', {}).get('allow_detached_details', False), overrides)
    except ValueError as exc:
        from extraction_annotations import diagnostic
        diagnostic(strip, count, Path(output_root).parent / 'qa/extraction-diagnostics', state, exc, annotation)
        raise
    layout = (profile or {}).get('layout', {})
    try:
        frames, viewport = render_slots(strip, count, (layout.get('cell_width', 192), layout.get('cell_height', 208)), policy['alignment'], policy['requested_scale'], policy['padding'], policy['anchor'], policy['resampling'])
    except ValueError as exc:
        from extraction_annotations import diagnostic
        diagnostic(strip, count, Path(output_root).parent / 'qa/extraction-diagnostics', state, exc, annotation)
        raise
    output_root = Path(output_root).resolve()
    state_dir = output_root / state
    if state_dir.resolve() != state_dir:
        raise ValueError(f'{state}: frame directory is a symbolic link or junction; refusing to overwrite another asset tree')
    state_dir.mkdir(parents=True, exist_ok=True)
    expected = {f'{i:02d}.png' for i in range(count)}
    extras = [p.name for p in state_dir.iterdir() if p.suffix.lower() in ('.png', '.webp', '.jpg', '.jpeg') and p.name not in expected]
    if extras:
        raise ValueError(f'ambiguous extra files in {state}: {extras}')
    for name in expected:
        if (state_dir / name).resolve() != state_dir / name:
            raise ValueError(f'{state}: frame {name} is a symbolic link; refusing to overwrite another asset')
    paths = []
    for i, frame in enumerate(frames):
        path = (state_dir / f'{i:02d}.png').resolve()
        temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            frame.save(temporary, format='PNG')
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        paths.append(path)
    settings = {'configuration': policy, **viewport}
    run_root = Path(output_root).parent
    provenance = {'request_sha256': digest(run_root / 'pet_request.json') if (run_root / 'pet_request.json').is_file() else None,
                  'extraction_settings_sha256': object_hash(policy) if (run_root / 'extraction-settings.json').is_file() else None,
                  'calibration_file_sha256': digest(run_root / 'extraction-settings.json') if (run_root / 'extraction-settings.json').is_file() else None}
    source_path = Path(strip_path).resolve()
    portable_source = source_path.relative_to(run_root.resolve()).as_posix() if source_path.is_relative_to(run_root.resolve()) else str(source_path)
    return {'state': state, 'schema_version': EXTRACTION_SCHEMA, 'algorithm': EXTRACTION_ALGORITHM, 'extractor_sha256': extractor_fingerprint(), 'frames': [p.relative_to(output_root).as_posix() for p in paths], 'frame_indices': list(range(count)), 'frame_hashes': [digest(p) for p in paths], 'method': 'stable-slots', 'source_path': portable_source, 'source_sha256': digest(strip_path), 'settings': settings, 'settings_sha256': object_hash(settings), 'profile_sha256': object_hash(extraction_projection(profile, state)) if profile else None, 'evidence': evidence, 'mask': mask, 'original_source_size': original_size, 'annotation_sha256': digest(annotation_path) if annotation else None, **provenance}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--decoded-dir', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--states', default='all')
    parser.add_argument('--profile')
    parser.add_argument('--chroma-key')
    parser.add_argument('--key-threshold', type=float)
    parser.add_argument('--method', choices=('auto', 'components', 'slots', 'stable-slots'), default='auto')
    parser.add_argument('--alpha-mode', choices=('auto', 'alpha', 'chroma'))
    parser.add_argument('--alignment', choices=('source', 'row', 'center', 'bottom'))
    parser.add_argument('--scale', type=float)
    args = parser.parse_args()
    decoded, out = Path(args.decoded_dir).resolve(), Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    profile = load_profile(args.profile or (decoded.parent / 'profile.json' if (decoded.parent / 'profile.json').exists() else None))
    global ROW_FRAME_COUNTS
    ROW_FRAME_COUNTS = {s['id']: s['frames'] for s in profile['states']}
    states = parse_states(args.states)
    config = load_extraction_config(decoded.parent)
    overrides = {'chroma_key': list(parse_hex_color(args.chroma_key)) if args.chroma_key else None, 'key_threshold': args.key_threshold, 'background': args.alpha_mode}
    for key, value in overrides.items():
        if value is not None:
            if (decoded.parent / 'pet_request.json').exists() and config[key] != value:
                raise ValueError(f'{key} differs from prepared settings; recalibrate through the controller so affected prompts and outputs are invalidated')
            config[key] = value
    if (args.alignment is not None or args.scale is not None) and (decoded.parent / 'pet_request.json').exists():
        raise ValueError('prepared runs take alignment/scale from profile and extraction-settings.json; update those settings before regeneration')
    validate_extraction_config(config)
    with extraction_ownership(out):
        manifest_path = out / 'frames-manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {'schema_version': EXTRACTION_SCHEMA, 'rows': []}
        if manifest.get('schema_version') != EXTRACTION_SCHEMA and set(states) != set(ROW_FRAME_COUNTS):
            raise ValueError('old extraction schema requires one full extraction before partial repairs')
        old_rows = manifest.get('rows', []) if manifest.get('schema_version') == EXTRACTION_SCHEMA else []
        if not isinstance(old_rows, list) or any(not isinstance(r, dict) or r.get('state') not in ROW_FRAME_COUNTS for r in old_rows) or len({r['state'] for r in old_rows}) != len(old_rows):
            raise ValueError('malformed extraction manifest; preserve it and regenerate all rows into a clean frames directory')
        rows = {row['state']: row for row in old_rows}
        for state in states:
            source = decoded / f'{state}.png'
            if not source.is_file():
                raise ValueError(f'missing generated strip: {source}')
            row = extract_state(source, state, out, tuple(config['chroma_key']), config['key_threshold'], args.method, profile, config['background'], args.alignment, args.scale, config)
            rows[state] = row
            manifest.update({'schema_version': EXTRACTION_SCHEMA, 'algorithm': EXTRACTION_ALGORITHM, 'ok': True, 'chroma_key': {'rgb': list(config['chroma_key']), 'threshold': config['key_threshold']}, 'rows': [rows[s] for s in ROW_FRAME_COUNTS if s in rows]})
            atomic_json(manifest_path, manifest)
    print(json.dumps({'ok': True, 'states': states, 'frames_root': str(out)}))


if __name__ == '__main__':
    main()
