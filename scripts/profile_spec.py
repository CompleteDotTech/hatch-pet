"""Versioned animation contract shared by generation and deterministic stages."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from pathlib import Path

DEFAULT_PROFILE = Path(__file__).resolve().parents[1] / 'profiles' / 'codex-v1.json'
FORMATS = {'frames', 'atlas', 'gif', 'webp', 'browser'}
VALIDATION_KEYS = {
    'min_motion', 'max_size_ratio', 'max_baseline_shift', 'loop_warning_ratio',
    'near_duplicate_delta', 'palette_distance_warning', 'min_used_pixels',
}
GENERATION_KEYS = {'skill', 'requires_identity_reference', 'instructions', 'requirements'}
RESERVED_STATES = {'base', 'con', 'prn', 'aux', 'nul'} | {f'{prefix}{i}' for prefix in ('com', 'lpt') for i in range(1, 10)}


def _require(test, message):
    if not test:
        raise ValueError('invalid profile: ' + message)


def _object(value, keys, context):
    _require(isinstance(value, dict), context + ' must be an object')
    extra = set(value) - set(keys)
    _require(not extra, context + ' has unsupported keys: ' + ', '.join(sorted(map(str, extra))))


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _generation(value, context):
    _object(value, GENERATION_KEYS, context)
    value.setdefault('skill', 'imagegen')
    value.setdefault('requires_identity_reference', True)
    _require(value['skill'] == 'imagegen', context + '.skill must be imagegen')
    _require(value['requires_identity_reference'] is True, context + ' requires identity references')
    if 'instructions' in value:
        _require(isinstance(value['instructions'], str) and bool(value['instructions'].strip()), context + '.instructions must be nonempty text')
    if 'requirements' in value:
        _require(isinstance(value['requirements'], list) and all(isinstance(x, str) and x.strip() for x in value['requirements']), context + '.requirements must be a list of nonempty strings')


def validate_profile(profile: dict) -> dict:
    """Validate and normalize; reject silent typos and unsupported combinations."""
    p = copy.deepcopy(profile)
    _object(p, {'schema_version', 'id', 'layout', 'states', 'generation', 'validation', 'events', 'export'}, 'profile')
    _require(type(p.get('schema_version')) is int and p['schema_version'] == 1, 'schema_version must be 1')
    _require(isinstance(p.get('id'), str) and re.fullmatch(r'[a-z0-9][a-z0-9-]*', p['id']), 'id must be a stable lowercase slug')
    layout = p.get('layout')
    _object(layout, {'columns', 'cell_width', 'cell_height', 'rows', 'width', 'height'}, 'layout')
    for key in ('columns', 'cell_width', 'cell_height'):
        _require(type(layout.get(key)) is int and 0 < layout[key] <= 4096, 'layout.' + key + ' must be a positive integer <=4096')
    states = p.get('states')
    _require(isinstance(states, list) and 0 < len(states) <= 256, 'states must be a nonempty list (maximum 256)')
    p.setdefault('generation', {})
    _generation(p['generation'], 'generation')
    seen = {}
    for state in states:
        _object(state, {'id', 'frames', 'durations', 'purpose', 'alignment', 'motion', 'generation', 'allowed_derivations', 'validation'}, 'state')
        name = state.get('id')
        _require(isinstance(name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]*', name) and name not in seen, 'state ids must be unique safe slugs')
        _require(name not in RESERVED_STATES, name + ': reserved state id is not portable or conflicts with the base job')
        seen[name] = state
        _require(type(state.get('frames')) is int and 0 < state['frames'] <= layout['columns'], name + ': frame count must fit layout columns')
        _require(isinstance(state.get('purpose'), str) and bool(state['purpose'].strip()), name + ': purpose is required')
        timing = state.get('durations')
        _require(isinstance(timing, list) and len(timing) == state['frames'] and all(type(x) is int and 10 <= x <= 60000 for x in timing), name + ': one duration (10..60000 ms) is required per frame')
        state.setdefault('alignment', {})
        alignment = state['alignment']
        _object(alignment, {'coordinate_policy', 'scale_policy', 'padding', 'anchor', 'pivot', 'scale'}, name + '.alignment')
        alignment.setdefault('coordinate_policy', 'slot')
        alignment.setdefault('scale_policy', 'row')
        alignment.setdefault('padding', min(5, (min(layout['cell_width'], layout['cell_height']) - 1) // 2))
        alignment.setdefault('anchor', [0.5, 0.5])
        _require(isinstance(alignment['coordinate_policy'], str) and alignment['coordinate_policy'] in {'slot', 'center', 'baseline'}, name + ': unsupported coordinate_policy')
        _require(isinstance(alignment['scale_policy'], str) and alignment['scale_policy'] in {'row', 'shared', 'none'}, name + ': unsupported scale_policy')
        _require(type(alignment['padding']) is int and 0 <= alignment['padding'] < min(layout['cell_width'], layout['cell_height']) / 2, name + ': invalid padding')
        for point in ('anchor', 'pivot'):
            if point in alignment:
                value = alignment[point]
                _require(isinstance(value, list) and len(value) == 2 and all(_number(x) and 0 <= x <= 1 for x in value), name + ': ' + point + ' must contain two normalized coordinates')
        if 'scale' in alignment:
            _require(alignment['scale_policy'] == 'shared' and _number(alignment['scale']) and 0 < alignment['scale'] <= 100, name + ': explicit scale requires shared policy and a positive finite number <=100')
        state.setdefault('motion', 'gesture')
        _require(isinstance(state['motion'], str) and state['motion'] in {'quiet', 'vertical', 'directional', 'gesture', 'static'}, name + ': unsupported motion policy')
        state.setdefault('generation', {})
        _generation(state['generation'], name + '.generation')
        state.setdefault('allowed_derivations', [])
        _require(isinstance(state['allowed_derivations'], list), name + ': allowed_derivations must be a list')
        _require(len(state['allowed_derivations']) <= 1, name + ': at most one optional mirror source is supported')
        state.setdefault('validation', {})
        _object(state['validation'], VALIDATION_KEYS, name + '.validation')
        for key, value in state['validation'].items():
            _require(_number(value) and value >= 0, name + ': ' + key + ' must be a finite nonnegative number')
            if key in {'min_motion', 'near_duplicate_delta', 'max_baseline_shift'}:
                _require(value <= 1, name + ': ' + key + ' must be a fraction from 0 to 1')
            if key in {'max_size_ratio', 'loop_warning_ratio'}:
                _require(value >= 1, name + ': ' + key + ' must be at least 1')
            if key == 'min_used_pixels':
                _require(type(value) is int and value <= layout['cell_width'] * layout['cell_height'], name + ': min_used_pixels must be an integer within cell area')
    shared_scales = {state['alignment']['scale'] for state in states if state['alignment']['scale_policy'] == 'shared' and 'scale' in state['alignment']}
    _require(len(shared_scales) <= 1, 'shared scale states must use one common calibration value')
    if shared_scales:
        shared_scale = next(iter(shared_scales))
        for state in states:
            if state['alignment']['scale_policy'] == 'shared':
                state['alignment'].setdefault('scale', shared_scale)
    graph = {name: [] for name in seen}
    for state in states:
        sources = set()
        for derivation in state['allowed_derivations']:
            _object(derivation, {'kind', 'source', 'requires_explicit_approval'}, state['id'] + '.allowed_derivations')
            source_name = derivation.get('source')
            _require(derivation.get('kind') == 'horizontal-mirror' and isinstance(source_name, str) and source_name in seen and source_name != state['id'] and derivation.get('requires_explicit_approval') is True, state['id'] + ': only explicitly approved horizontal-mirror derivations are supported')
            _require(source_name not in sources, state['id'] + ': duplicate derivation source')
            sources.add(source_name)
            source = seen[source_name]
            _require(source['frames'] == state['frames'] and source['durations'] == state['durations'], state['id'] + ': mirrored source must use identical counts/timings')
            graph[state['id']].append(source_name)
    visiting, visited = set(), set()

    def visit(name):
        _require(name not in visiting, 'derivation cycle involving ' + name)
        if name in visited:
            return
        visiting.add(name)
        for source in graph[name]:
            visit(source)
        visiting.remove(name)
        visited.add(name)
    for name in graph:
        visit(name)
    p.setdefault('validation', {})
    _object(p['validation'], {'require_provenance', 'allow_detached_details'}, 'validation')
    p['validation'].setdefault('require_provenance', True)
    p['validation'].setdefault('allow_detached_details', False)
    for key, value in p['validation'].items():
        _require(type(value) is bool, 'validation.' + key + ' must be boolean')
    _require(p['validation']['require_provenance'] is True, 'validation.require_provenance must be true; accepting untraceable production assets is unsupported')
    p.setdefault('events', {})
    _require(isinstance(p['events'], dict) and all(isinstance(k, str) and k.strip() and isinstance(v, str) and v in seen for k, v in p['events'].items()), 'events must map nonempty event names to existing state ids')
    p.setdefault('export', {'formats': ['frames', 'atlas', 'browser'], 'static_state': states[0]['id'], 'static_frame': 0})
    export = p['export']
    _object(export, {'formats', 'static_state', 'static_frame', 'codex_compatible'}, 'export')
    formats = export.get('formats')
    _require(isinstance(formats, list) and bool(formats) and all(isinstance(x, str) and x in FORMATS for x in formats) and len(set(formats)) == len(formats), 'unsupported or repeated export formats')
    static_name = export.get('static_state')
    _require(isinstance(static_name, str) and static_name in seen, 'invalid static state')
    export.setdefault('static_frame', 0)
    _require(type(export['static_frame']) is int and 0 <= export['static_frame'] < seen[static_name]['frames'], 'invalid static frame')
    if 'codex_compatible' in export:
        _require(type(export['codex_compatible']) is bool, 'export.codex_compatible must be boolean')
    computed = {'rows': len(states), 'width': layout['columns'] * layout['cell_width'], 'height': len(states) * layout['cell_height']}
    for key, value in computed.items():
        _require(key not in layout or (type(layout[key]) is int and layout[key] == value), 'layout.' + key + ' disagrees with states and cells')
        layout[key] = value
    _require(layout['width'] * layout['height'] <= 64000000, 'atlas exceeds 64 million pixels')
    if export.get('codex_compatible'):
        default = json.loads(DEFAULT_PROFILE.read_text(encoding='utf-8'))
        _require([(x['id'], x['frames'], x['durations']) for x in states] == [(x['id'], x['frames'], x['durations']) for x in default['states']] and all(layout[k] == default['layout'][k] for k in ('columns', 'cell_width', 'cell_height')), 'codex_compatible requires the exact default contract')
    return p


def load_profile(path=None) -> dict:
    if isinstance(path, dict):
        return validate_profile(path)
    return validate_profile(json.loads(Path(path or DEFAULT_PROFILE).read_text(encoding='utf-8')))


def profile_hash(profile) -> str:
    return hashlib.sha256(json.dumps(load_profile(profile), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def profile_for_run(root: Path, override=None) -> dict:
    if override:
        return load_profile(override)
    for folder in (Path(root), Path(root).parent):
        candidate = folder / 'profile.json'
        if candidate.is_file():
            return load_profile(candidate)
    return load_profile()


def row_specs(profile=None):
    return [(state['id'], i, state['frames']) for i, state in enumerate(load_profile(profile)['states'])]


def indexed_frames(root: Path, state: str, count: int) -> list[Path]:
    folder = Path(root) / state
    expected = [folder / f'{i:02d}.png' for i in range(count)]
    actual = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in {'.png', '.webp', '.jpg', '.jpeg'}) if folder.is_dir() else []
    if sorted(expected) != actual:
        raise ValueError(f'{state}: expected exactly indexed 00.png..{count-1:02d}.png; missing={[p.name for p in expected if p not in actual]}, extra={[p.name for p in actual if p not in expected]}')
    return expected


def documentation_table(profile=None):
    p = load_profile(profile)
    return '| Row | State | Frames | Durations (ms) | Purpose |\n| ---: | --- | ---: | --- | --- |\n' + '\n'.join(f"| {i} | {s['id']} | {s['frames']} | {', '.join(map(str, s['durations']))} | {s['purpose'].replace('|', '/')} |" for i, s in enumerate(p['states'])) + '\n'


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile')
    parser.add_argument('--table', action='store_true')
    args = parser.parse_args()
    print(documentation_table(args.profile) if args.table else json.dumps(load_profile(args.profile), indent=2))
