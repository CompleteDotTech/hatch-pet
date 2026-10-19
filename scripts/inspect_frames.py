#!/usr/bin/env python3
"""Validate exact frame sets, current extraction provenance, and uncertain metrics."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
from statistics import median

from PIL import Image, ImageChops, ImageStat
from asset_contracts import extraction_projection
from extract_strip_frames import (EXTRACTION_ALGORITHM, EXTRACTION_SCHEMA,
    SEGMENTATION_STRATEGY, atomic_json, connected_components, digest,
    extraction_configuration, load_extraction_config, object_hash, pixels, extractor_fingerprint)

IMAGE_SUFFIXES = {'.png', '.webp', '.jpg', '.jpeg'}
CELL_WIDTH, CELL_HEIGHT = 192, 208


def alpha_nonzero_count(image):
    return sum((image if image.mode == 'L' else image.getchannel('A')).histogram()[1:])


def edge_alpha_count(image, margin):
    width, height = image.size
    return sum(alpha_nonzero_count(image.crop(box)) for box in ((0, 0, width, margin), (0, height - margin, width, height), (0, 0, margin, height), (width - margin, 0, width, height)))


def color_distance(left, right):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


def chroma_adjacent_count(image, chroma_key, threshold):
    return 0 if chroma_key is None else sum(a > 16 and color_distance((r, g, b), chroma_key) <= threshold for r, g, b, a in pixels(image))


def frame_files(path):
    return sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES) if path.is_dir() else []


def load_manifest(root):
    path = Path(root) / 'frames-manifest.json'
    if not path.exists():
        raise ValueError('missing extraction provenance: frames-manifest.json')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('schema_version') != EXTRACTION_SCHEMA or data.get('algorithm') != EXTRACTION_ALGORITHM or not isinstance(data.get('rows'), list):
        raise ValueError('unsupported or malformed extraction provenance schema/algorithm; re-extract from retained sources')
    rows = data['rows']
    if any(not isinstance(row, dict) or not isinstance(row.get('state'), str) for row in rows) or len({row['state'] for row in rows}) != len(rows):
        raise ValueError('malformed or duplicate extraction rows')
    return {row['state']: row for row in rows}


def load_chroma_key(root):
    try:
        return tuple(load_extraction_config(Path(root).parent)['chroma_key'])
    except (KeyError, ValueError, TypeError, OSError):
        return None


def _hash(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _positive_int(value):
    return type(value) is int and value > 0


def _valid_evidence(evidence, count, source_size):
    if not isinstance(evidence, dict) or evidence.get('strategy') != SEGMENTATION_STRATEGY or evidence.get('confidence') != 'geometry-consistent-semantic-review-required':
        return False
    if evidence.get('alpha_connectivity') != 8 or evidence.get('alpha_threshold') != 0 or type(evidence.get('core_alpha_threshold')) is not int or not 1 <= evidence['core_alpha_threshold'] <= 127 or evidence.get('source_size') != list(source_size):
        return False
    slots = evidence.get('slots')
    if not isinstance(slots, list) or len(slots) != count:
        return False
    width, height = source_size
    for index, slot in enumerate(slots):
        if not isinstance(slot, dict) or slot.get('slot') != index or type(slot.get('slot')) is not int:
            return False
        bounds = slot.get('bounds')
        if not isinstance(bounds, list) or len(bounds) != 4 or any(type(v) is not int for v in bounds):
            return False
        left, top, right, bottom = bounds
        if not (round(index * width / count) <= left < right <= round((index + 1) * width / count) and 0 <= top < bottom <= height):
            return False
        if any(not _positive_int(slot.get(key)) for key in ('components', 'core_components', 'major_components', 'pixels', 'core_pixels')):
            return False
        if slot['major_components'] != 1 or slot['core_pixels'] > slot['pixels'] or slot['pixels'] > (right - left) * (bottom - top) or slot.get('narrow_bridge', True) is not None:
            return False
    return True


def validate_provenance(root, state, files, row, profile=None):
    """Hashes are necessary but insufficient: validate shape and current policy too."""
    errors = []
    if not isinstance(row, dict) or row.get('schema_version') != EXTRACTION_SCHEMA or row.get('algorithm') != EXTRACTION_ALGORITHM or row.get('state') != state:
        return [f'{state}: missing or unsupported row extraction provenance']
    if row.get('method') != 'stable-slots':
        errors.append(f'{state}: unsupported extraction strategy')
    if row.get('extractor_sha256') != extractor_fingerprint():
        errors.append(f'{state}: extractor implementation changed; re-extract from retained sources')
    indices = row.get('frame_indices')
    if not isinstance(indices, list) or any(type(v) is not int for v in indices) or indices != list(range(len(files))) or row.get('frames') != [p.resolve().relative_to(Path(root).resolve()).as_posix() for p in files]:
        errors.append(f'{state}: provenance frame ordering does not match exact files')
    hashes = row.get('frame_hashes')
    if not isinstance(hashes, list) or not all(_hash(v) for v in hashes) or hashes != [digest(p) for p in files]:
        errors.append(f'{state}: stale extracted frame hashes')
    source_value = row.get('source_path')
    source = (Path(root).parent / source_value).resolve() if isinstance(source_value, str) else Path()
    if (Path(root).parent / 'imagegen-jobs.json').is_file():
        run_root = Path(root).parent.resolve()
        expected_source = run_root / 'decoded' / (state + '.png')
        if source != expected_source or expected_source.resolve() != expected_source:
            errors.append(f'{state}: source provenance must identify the current prepared decoded/{state}.png')
    source_size = None
    if not isinstance(source_value, str) or not source.is_file() or not _hash(row.get('source_sha256')) or row.get('source_sha256') != digest(source):
        errors.append(f'{state}: missing or stale source provenance')
    else:
        try:
            with Image.open(source) as image:
                source_size = image.size
        except OSError:
            errors.append(f'{state}: extraction source cannot be decoded')
    settings = row.get('settings')
    annotation_path = Path(root).parent / 'annotations' / (state + '.json')
    annotated_evidence = None
    if row.get('annotation_sha256') != (digest(annotation_path) if annotation_path.is_file() else None):
        errors.append(f'{state}: changed extraction annotation; re-extract and review')
    if annotation_path.is_file() and source_size is not None:
        try:
            from extraction_annotations import annotated_source
            from extract_strip_frames import mask_background, analyze_slots
            config = load_extraction_config(Path(root).parent)
            with Image.open(source) as opened:
                masked, _ = mask_background(opened, tuple(config['chroma_key']), config['key_threshold'], config['background'], config['holes'], config['edge_cleanup'])
            count = next(s['frames'] for s in profile['states'] if s['id'] == state)
            normalized, overrides = annotated_source(masked, count, json.loads(annotation_path.read_text(encoding='utf-8')), digest(source))
            _, annotated_evidence = analyze_slots(normalized, count, profile['validation']['allow_detached_details'], overrides)
            source_size = normalized.size
            if row.get('evidence') != annotated_evidence:
                errors.append(f'{state}: annotated segmentation evidence does not match source')
        except (ValueError, KeyError, TypeError, StopIteration) as exc:
            errors.append(f'{state}: invalid annotation: {exc}')
    if not isinstance(settings, dict) or not _hash(row.get('settings_sha256')) or row.get('settings_sha256') != object_hash(settings):
        errors.append(f'{state}: malformed or stale extraction settings')
    root = Path(root)
    for field, path in (('request_sha256', root.parent / 'pet_request.json'), ('extraction_settings_sha256', root.parent / 'extraction-settings.json')):
        expected = (object_hash(extraction_configuration(profile, state, load_extraction_config(root.parent))) if field == 'extraction_settings_sha256' else digest(path)) if path.is_file() else None
        if field not in row or row[field] != expected:
            errors.append(f'{state}: stale {"request" if field == "request_sha256" else "calibrated extraction settings"} provenance; extract after preparing changed inputs')
    if profile and (not _hash(row.get('profile_sha256')) or row.get('profile_sha256') != object_hash(extraction_projection(profile, state))):
        errors.append(f'{state}: stale profile provenance')
    if isinstance(settings, dict) and source_size is not None:
        try:
            recorded = settings.get('configuration')
            method = recorded.get('requested_method') if isinstance(recorded, dict) else None
            if method not in ('auto', 'components', 'slots', 'stable-slots'):
                raise ValueError('unsupported requested extraction method')
            current = extraction_configuration(profile, state, load_extraction_config(root.parent), method)
            if recorded != current:
                raise ValueError('recorded extraction configuration differs from current request/profile/calibration')
            spec = next(s for s in profile['states'] if s['id'] == state) if profile else {'frames': len(files)}
            layout = (profile or {}).get('layout', {})
            size = [layout.get('cell_width', 192), layout.get('cell_height', 208)]
            slot_width, height = source_size[0] / spec['frames'], source_size[1]
            available = [value - 2 * current['padding'] for value in size]
            expected_scale = current['requested_scale']
            if expected_scale is None:
                expected_scale = min(available[0] / math.ceil(slot_width), available[1] / height, 1.0)
            expected_fields = {'alignment': current['alignment'], 'source_viewport': [slot_width, 0, height], 'source_size': list(source_size), 'scale': expected_scale, 'cell_size': size, 'padding': current['padding'], 'anchor': current['anchor'], 'resampling': current['resampling']}
            if any(settings.get(key) != value for key, value in expected_fields.items()):
                raise ValueError('recorded viewport/scale differs from source and current policy')
        except (ValueError, KeyError, TypeError, StopIteration, ZeroDivisionError) as exc:
            errors.append(f'{state}: invalid extraction configuration: {exc}')
    if source_size is None or (annotated_evidence is None and not _valid_evidence(row.get('evidence'), len(files), source_size)):
        errors.append(f'{state}: missing or malformed segmentation evidence')
    mask = row.get('mask')
    if not isinstance(mask, dict) or mask.get('mode') not in ('alpha', 'edge-connected-chroma') or type(mask.get('removed_pixels')) is not int or mask['removed_pixels'] < 0 or type(mask.get('cleaned_edge_pixels')) is not int or mask['cleaned_edge_pixels'] < 0 or not isinstance(mask.get('warnings'), list) or not all(isinstance(v, str) for v in mask.get('warnings', [])):
        errors.append(f'{state}: missing or malformed transparency evidence')
    return errors


def delta(left, right):
    if left.size != right.size:
        return 1.0
    return sum(ImageStat.Stat(ImageChops.difference(left, right)).mean) / (4 * 255)


def palette(image):
    samples = [p for p in pixels(image) if p[3] > 0]
    weight = sum(p[3] for p in samples)
    return [sum(p[i] * p[3] for p in samples) / weight if weight else 0 for i in range(3)]


def temporal_metrics(images, spec):
    if not images:
        return {}, []
    bounds = [image.getbbox() for image in images]
    areas = [alpha_nonzero_count(image) for image in images]
    baselines = [box[3] for box in bounds if box]
    palettes = [palette(image) for image in images]
    pairs = [{'from': i, 'to': j, 'delta': round(delta(images[i], images[j]), 7), 'exact': images[i].size == images[j].size and images[i].tobytes() == images[j].tobytes()} for i in range(len(images)) for j in range(i + 1, len(images))]
    adjacent = [delta(images[i], images[i + 1]) for i in range(len(images) - 1)]
    loop = delta(images[-1], images[0])
    cfg, motion = spec.get('validation', {}), spec.get('motion', 'quiet' if spec.get('id') == 'idle' else 'gesture')
    near = cfg.get('near_duplicate_delta', .0003)
    minimum = cfg.get('min_motion', 0 if motion == 'static' else .00015 if motion == 'quiet' else .0005)
    baseline_limit = cfg.get('max_baseline_shift', .05 if motion == 'quiet' else .65 if motion == 'vertical' else .18)
    size_limit = cfg.get('max_size_ratio', 1.5)
    palette_limit = cfg.get('palette_distance_warning', 35)
    loop_ratio = cfg.get('loop_warning_ratio', 3.0)
    maximum_palette = max((color_distance(left, right) for left in palettes for right in palettes), default=0)
    area_ratio = max(areas) / max(1, min(areas))
    baseline_span = max(baselines) - min(baselines) if baselines else 0
    baseline_fraction = baseline_span / images[0].height
    warnings = []
    if len(images) > 1 and max(adjacent, default=0) < minimum:
        warnings.append('insufficient measured visible motion; visual review must establish intended animation')
    if motion != 'static' and any(pair['exact'] for pair in pairs):
        warnings.append('exact duplicate frames present; assess intentional holds')
    elif motion != 'static' and any(pair['delta'] < near for pair in pairs):
        warnings.append('near-duplicate frames present')
    loop_threshold = max(.002, median(adjacent) * loop_ratio) if adjacent else 0
    if adjacent and loop > loop_threshold:
        warnings.append('loop discontinuity exceeds adjacent-frame change')
    if area_ratio > size_limit:
        warnings.append('unexpected occupied-area change; pose change and size popping need visual discrimination')
    if baseline_fraction > baseline_limit:
        warnings.append('unexpected baseline change for configured state motion policy')
    if maximum_palette > palette_limit:
        warnings.append('palette drift or changing visible surface proportions')
    ordering_threshold = max(.003, median(adjacent) * 3) if adjacent else 0
    if len(adjacent) > 2 and max(adjacent) > ordering_threshold:
        warnings.append('suspicious frame ordering: an adjacent transition is an outlier')
    return {'pairwise': pairs, 'adjacent_delta': adjacent, 'loop_delta': loop, 'occupied_area_ratio': area_ratio, 'baseline_span': baseline_span, 'baseline_fraction': baseline_fraction, 'maximum_palette_distance': maximum_palette, 'palettes': palettes, 'occupied_pixels': areas, 'bounds': bounds, 'motion_policy': motion, 'thresholds': {'near_duplicate_delta': near, 'min_motion': minimum, 'max_baseline_shift': baseline_limit, 'max_size_ratio': size_limit, 'palette_distance_warning': palette_limit, 'loop_warning_ratio': loop_ratio, 'computed_loop_delta': loop_threshold, 'computed_ordering_delta': ordering_threshold}, 'uncertainty': 'Measurements cannot establish identity, facing direction, action semantics, or whether a change is intentional.'}, warnings


def inspect_state(frames_root, state, expected_count, manifest_rows, chroma_key, args):
    files, errors, warnings, frames, images = frame_files(frames_root / state), [], [], [], []
    row = manifest_rows.get(state, {})
    expected = [f'{i:02d}.png' for i in range(expected_count)]
    if [path.name for path in files] != expected:
        errors.append(f'{state}: expected exact ordered frame files {expected}, found {[p.name for p in files]}')
    profile = getattr(args, 'profile_data', None)
    spec = next((s for s in (profile or {}).get('states', []) if s['id'] == state), {'id': state})
    errors += validate_provenance(frames_root, state, files, row, profile)
    layout = (profile or {}).get('layout', {})
    size = (layout.get('cell_width', 192), layout.get('cell_height', 208))
    minimum = spec.get('validation', {}).get('min_used_pixels',
              min(getattr(args, 'min_used_pixels', 400), max(1, round(size[0] * size[1] * .01))))
    for index, path in enumerate(files):
        try:
            with Image.open(path) as opened:
                image = opened.convert('RGBA')
        except Exception as exc:
            errors.append(f'{state} {path.name}: cannot decode: {exc}')
            continue
        images.append(image)
        area = alpha_nonzero_count(image)
        edge = edge_alpha_count(image, getattr(args, 'edge_margin', 2))
        frames.append({'index': index, 'file': str(path), 'sha256': digest(path), 'bbox': image.getbbox(), 'nontransparent_pixels': area, 'edge_pixels': edge, 'components': len(connected_components(image))})
        if image.size != size:
            errors.append(f'{state} {index}: wrong dimensions {image.size}, expected {size}')
        if area < minimum:
            errors.append(f'{state} {index}: empty or too sparse ({area} pixels)')
        if edge > getattr(args, 'edge_pixel_threshold', 24):
            warnings.append(f'{state} {index}: {edge} edge pixels; inspect clipping')
        if any(alpha == 0 and (red or green or blue) for red, green, blue, alpha in pixels(image)):
            errors.append(f'{state} {index}: transparent RGB residue')
    metrics, messages = temporal_metrics(images, spec)
    warnings += messages
    if isinstance(row.get('mask'), dict) and isinstance(row['mask'].get('warnings'), list):
        warnings += [value for value in row['mask']['warnings'] if isinstance(value, str)]
    return {'state': state, 'expected_frames': expected_count, 'actual_frames': len(files), 'extraction_method': row.get('method'), 'ok': not errors, 'errors': errors, 'warnings': warnings, 'frames': frames, 'metrics': metrics}


def consistency_metrics(rows):
    """Cross-row measurements flag possible calibration drift without judging poses."""
    measured = [row for row in rows if row['metrics'].get('occupied_pixels')]
    sizes = {row['state']: median(row['metrics']['occupied_pixels']) for row in measured}
    positive = [area for area in sizes.values() if area > 0]
    ratio = max(positive) / min(positive) if positive else 1.0
    palettes = {row['state']: [sum(color[channel] for color in row['metrics']['palettes']) / len(row['metrics']['palettes'])
                for channel in range(3)] for row in measured if row['metrics'].get('palettes')}
    palette_distance = max((color_distance(a, b) for a in palettes.values() for b in palettes.values()), default=0)
    area_limit = max((row['metrics']['thresholds']['max_size_ratio'] for row in measured), default=1.8)
    palette_limit = max((row['metrics']['thresholds']['palette_distance_warning'] for row in measured), default=35)
    warnings = []
    if ratio > area_limit:
        warnings.append('cross-row occupied-area change; inspect shared scale calibration and intended pose differences')
    if palette_distance > palette_limit:
        warnings.append('cross-row palette difference; inspect color drift and changing visible surfaces')
    return {'median_occupied_pixels_by_state': sizes, 'maximum_row_area_ratio': ratio,
            'mean_palette_by_state': palettes, 'maximum_palette_distance': palette_distance,
            'thresholds': {'max_size_ratio': area_limit, 'palette_distance_warning': palette_limit},
            'warnings': warnings, 'uncertainty': 'Different actions can change silhouette area and visible colors; these values do not prove cross-row identity or size consistency.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames-root', required=True)
    parser.add_argument('--json-out', required=True)
    parser.add_argument('--profile')
    parser.add_argument('--min-used-pixels', type=int, default=400)
    parser.add_argument('--edge-margin', type=int, default=2)
    parser.add_argument('--edge-pixel-threshold', type=int, default=24)
    parser.add_argument('--require-components', action='store_true', help='Compatibility flag; current extraction provenance is always required.')
    parser.add_argument('--allow-stable-slots', action='store_true')
    # Compatibility arguments are retained; profile thresholds control current metrics.
    parser.add_argument('--chroma-adjacent-threshold', type=float, default=150)
    parser.add_argument('--chroma-adjacent-pixel-threshold', type=int, default=800)
    parser.add_argument('--small-outlier-ratio', type=float, default=.35)
    parser.add_argument('--large-outlier-ratio', type=float, default=2.75)
    args = parser.parse_args()
    root = Path(args.frames_root).resolve()
    from profile_spec import load_profile
    args.profile_data = load_profile(args.profile or (root.parent / 'profile.json' if (root.parent / 'profile.json').exists() else None))
    try:
        manifest, initial = load_manifest(root), []
        extra = set(manifest) - {state['id'] for state in args.profile_data['states']}
        if extra:
            initial.append('unexpected extraction states: ' + ', '.join(sorted(extra)))
    except (ValueError, TypeError, KeyError) as exc:
        manifest, initial = {}, [str(exc)]
    rows = [inspect_state(root, state['id'], state['frames'], manifest, load_chroma_key(root), args) for state in args.profile_data['states']]
    errors = initial + [error for row in rows for error in row['errors']]
    warnings = [warning for row in rows for warning in row['warnings']]
    consistency = consistency_metrics(rows)
    warnings += consistency['warnings']
    result = {'schema_version': EXTRACTION_SCHEMA, 'ok': not errors, 'frames_root': str(root), 'errors': errors, 'warnings': warnings, 'rows': rows, 'consistency_metrics': consistency, 'visual_review_required': True}
    atomic_json(Path(args.json_out).resolve(), result)
    print(json.dumps({key: value for key, value in result.items() if key != 'rows'}, indent=2))
    raise SystemExit(0 if result['ok'] else 1)


if __name__ == '__main__':
    main()
