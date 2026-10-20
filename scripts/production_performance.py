"""Integer-frame production evaluation, reconstructed with retained public APIs.

The renderer uses this evaluator directly. Reconstruction must be freshly tested;
historical pre-loss test results are not evidence for these files.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math

from production_contracts import CHANNELS, DIMENSIONS, MAX_FRAMES, asset_key


def _frame(frame):
    if type(frame) is not int or not 0 <= frame <= MAX_FRAMES:
        raise ValueError('frame must be a bounded nonnegative integer')


def evaluate_track(track, frame, default=None):
    _frame(frame)
    if track is None:
        return copy.deepcopy(default)
    keys = track['keys']
    previous = keys[0]
    if frame <= previous['frame']:
        return copy.deepcopy(previous['value'])
    for following in keys[1:]:
        if frame < following['frame']:
            if track['interpolation'] == 'step':
                return copy.deepcopy(previous['value'])
            fraction = (frame - previous['frame']) / (following['frame'] - previous['frame'])
            a, b = previous['value'], following['value']
            if isinstance(a, list):
                return [a[i] + (b[i] - a[i]) * fraction for i in range(len(a))]
            return a + (b - a) * fraction
        previous = following
    return copy.deepcopy(previous['value'])


def evaluate_clip(clip, frame):
    """Return independent root/body/face/gaze/mouth state and exact local markers."""
    _frame(frame)
    n = clip['duration_frames']
    complete = frame >= n
    cycles = 0
    if clip['mode'] == 'loop':
        cycles, local = divmod(frame, n)
        root_local = local
    elif clip['mode'] == 'hold':
        local = root_local = 0
    else:
        local = min(frame, n - 1)
        root_local = min(frame, n)
        if complete and clip['completion'] == 'return-to-start':
            local = 0
    result = {'frame': local, 'complete': complete and clip['mode'] != 'loop',
              'root': {'offset': evaluate_track(clip['root'].get('offset'), root_local, [0, 0]),
                       'facing': evaluate_track(clip['root'].get('facing'), local, clip['facing']),
                       'visible': not (complete and clip['completion'] == 'exit')},
              **{channel: {} for channel in CHANNELS}, 'full_frame': None,
              'contacts': [], 'events': []}
    result['root']['offset'] = [result['root']['offset'][i] + cycles * clip['displacement'][i] for i in range(2)]
    for channel in CHANNELS:
        for component, tracks in clip['tracks'].get(channel, {}).items():
            result[channel][component] = {prop: evaluate_track(track, local) for prop, track in tracks.items()}
    for override in clip['full_frames']:
        if override['start_frame'] <= local < override['end_frame']:
            result['full_frame'] = copy.deepcopy(override)
            break
    result['contacts'] = [copy.deepcopy(c) for c in clip['contacts'] if c['start_frame'] <= local < c['end_frame']]
    if clip['mode'] == 'loop' or (frame < n and (clip['mode'] != 'hold' or frame == 0)):
        result['events'] = [copy.deepcopy(e) for e in clip['events'] if e['frame'] == local]
    return result


def selected_drawing(component, viewpoint, costume, character=None):
    if character:
        variant = next((c for c in character['costumes'] if c['id'] == costume), None)
        if variant:
            name = variant['drawings'].get(component['id'])
            if name:
                drawing = component['drawings'][name]
                if drawing['viewpoint'] == viewpoint and drawing['costume'] == costume:
                    return name
    default = component['default_drawing']
    drawing = component['drawings'][default]
    if drawing['viewpoint'] == viewpoint and drawing['costume'] == costume:
        return default
    choices = sorted(name for name, value in component['drawings'].items()
                     if value['viewpoint'] == viewpoint and value['costume'] == costume)
    if not choices:
        raise ValueError('missing compatible drawing for ' + component['id'] + '/' + viewpoint + '/' + costume)
    return choices[0]


def _defaults(character, instance):
    return {component['id']: {'offset': [0, 0], 'rotation': 0, 'visible': component['visible'],
            'drawing': selected_drawing(component, instance['viewpoint'], instance['costume'], character)}
            for component in character['components']}


def _properties(character, instance, evaluated):
    properties = _defaults(character, instance)
    for channel in CHANNELS:
        for cid, changes in evaluated.get(channel, {}).items():
            properties[cid].update(copy.deepcopy(changes))
    return properties


def _blend_properties(previous, current, fraction):
    result = copy.deepcopy(current)
    for cid in result:
        for prop in ('offset', 'rotation'):
            a, b = previous[cid][prop], current[cid][prop]
            result[cid][prop] = ([a[i] + (b[i] - a[i]) * fraction for i in range(2)]
                                if prop == 'offset' else a + (b - a) * fraction)
    return result


def evaluate_instance_performance(bundle, shot, instance, frame):
    """Compose clip root displacement and independent shot property overrides."""
    _frame(frame)
    if frame > shot['duration_frames']:
        raise ValueError('frame exceeds shot duration')
    if isinstance(instance, str):
        instance = next(i for i in shot['instances'] if i['id'] == instance)
    char = bundle['characters'][instance['character']]
    properties = _defaults(char, instance)
    root_offset = [0, 0]
    state = None
    active_events = []
    previous_properties = copy.deepcopy(properties)
    for placement in instance['clips']:
        if frame < placement['start_frame']:
            break
        clip = bundle['clips'][placement['clip']]
        duration = placement['end_frame'] - placement['start_frame']
        elapsed = min(frame - placement['start_frame'], duration)
        state = evaluate_clip(clip, elapsed)
        active_events = state['events'] if frame < placement['end_frame'] else []
        current = _properties(char, instance, state)
        transition = placement['transition']
        if transition['kind'] == 'interpolate' and elapsed < transition['frames']:
            current = _blend_properties(previous_properties, current, elapsed / transition['frames'])
        root_offset = [root_offset[i] + state['root']['offset'][i] for i in range(2)]
        properties = current
        if frame < placement['end_frame']:
            break
        previous_properties = copy.deepcopy(current)
    for channel in CHANNELS:
        for cid, changes in instance['tracks'].get(channel, {}).items():
            for prop, track in changes.items():
                properties[cid][prop] = evaluate_track(track, frame)
    root_tracks = instance['tracks'].get('root', {})
    extra = evaluate_track(root_tracks.get('offset'), frame, [0, 0])
    root_offset = [root_offset[i] + extra[i] for i in range(2)]
    return {'instance': instance['id'], 'character': instance['character'], 'frame': frame,
        'components': properties, 'position': [instance['position'][i] + root_offset[i] for i in range(2)],
        'scale': char['relative_scale'] * shot['cast_scale'],
        'facing': evaluate_track(root_tracks.get('facing'), frame,
                                 state['root']['facing'] if state else instance['facing']),
        'visible': evaluate_track(root_tracks.get('visible'), frame,
                                  state['root']['visible'] if state else True),
        'full_frame': state['full_frame'] if state else None,
        'contacts': state['contacts'] if state else [], 'events': active_events}


def prop_owner(prop, frame):
    _frame(frame)
    owner, attachment = prop['owner'], prop['attachment']
    for change in prop['ownership']:
        if change['frame'] > frame:
            break
        owner, attachment = change['to'], change['attachment']
    return {'owner': owner, 'attachment': copy.deepcopy(attachment)}


def interruption_plan(clip, frame, target_pose, blend_frames=0):
    _frame(frame)
    if type(blend_frames) is not int or blend_frames < 0:
        raise ValueError('cancellation requires a bounded transition')
    rules = clip['interruptions']
    local = frame % clip['duration_frames'] if clip['mode'] == 'loop' else min(frame, clip['duration_frames'] - 1)
    complete = clip['mode'] == 'once' and frame >= clip['duration_frames']
    if not complete and (rules['policy'] == 'never' or (rules['policy'] == 'at-markers' and local not in rules['frames'])):
        raise ValueError('interruption/cancellation forbidden at frame ' + str(local))
    if blend_frames > min(rules['max_transition_frames'], clip['interpolation']['max_frames']):
        raise ValueError('cancellation exceeds bounded transition length')
    pose = clip['end_pose'] if complete else rules['cancel_pose']
    if pose != target_pose and blend_frames == 0:
        raise ValueError('target requires compatible cancel_pose or explicit bounded transition')
    return {'allowed': True, 'frame': frame, 'local_frame': local, 'cancel_pose': pose,
            'target_pose': target_pose, 'blend_frames': blend_frames}


def planned_requirements(bundle, shot_id):
    shot = bundle['shots'][shot_id]
    result, seen = [], set()
    def add(instance, dimension, value, start, end, source):
        identity = (shot_id, instance['id'], instance['character'], dimension, value, start, end, source)
        if identity in seen:
            return
        seen.add(identity)
        digest = hashlib.sha256(json.dumps(identity, separators=(',', ':')).encode()).hexdigest()[:20]
        result.append({'id': 'req-' + digest, 'shot': shot_id, 'instance': instance['id'],
            'character': instance['character'], 'dimension': dimension, 'value': value,
            'start_frame': start, 'end_frame': end, 'source': source})
    for instance in shot['instances']:
        for dimension in ('viewpoint', 'facing', 'costume'):
            add(instance, dimension, instance[dimension], 0, shot['duration_frames'], 'explicit')
        for dimension, values in instance['requirements'].items():
            for value in values:
                add(instance, dimension, value, 0, shot['duration_frames'], 'explicit')
        for placement in instance['clips']:
            clip = bundle['clips'][placement['clip']]
            requirements = copy.deepcopy(clip['requirements'])
            requirements['pose'] = list(dict.fromkeys(requirements.get('pose', []) + [clip['start_pose'], clip['end_pose']]))
            for dimension, values in requirements.items():
                for value in values:
                    add(instance, dimension, value, placement['start_frame'], placement['end_frame'], 'clip')
        for audio in shot['audio']:
            if audio['speaker'] == instance['id']:
                for cue in audio['mouth_cues']:
                    add(instance, 'mouth', cue['shape'], cue['start_frame'], cue['end_frame'], 'explicit')
    return result


def incompatible_requirements(character, requirements):
    result = []
    for restriction in character.get('restrictions', []):
        matching = {dimension: [r for r in requirements if r['dimension'] == dimension and r['value'] in values]
                    for dimension, values in restriction['when'].items()}
        if not matching or any(not rows for rows in matching.values()):
            continue
        boundaries = sorted({f for rows in matching.values() for row in rows for f in (row['start_frame'], row['end_frame'])})
        intervals = []
        for start, end in zip(boundaries, boundaries[1:]):
            if all(any(r['start_frame'] <= start and end <= r['end_frame'] for r in rows) for rows in matching.values()):
                if intervals and intervals[-1][1] == start:
                    intervals[-1][1] = end
                else:
                    intervals.append([start, end])
        if intervals:
            result.append({'when': copy.deepcopy(restriction['when']), 'reason': restriction['reason'], 'intervals': intervals})
    return result


def validate_transition_limits(bundle):
    for shot in bundle['shots'].values():
        for instance in shot['instances']:
            char = bundle['characters'][instance['character']]
            prior_clip = None
            for placement in instance['clips']:
                clip = bundle['clips'][placement['clip']]
                transition = placement['transition']
                if transition['kind'] == 'interpolate':
                    begin, length = placement['start_frame'], transition['frames']
                    before = (evaluate_instance_performance(bundle, shot, instance, begin - 1)['components']
                              if begin else _defaults(char, instance))
                    first = evaluate_instance_performance(bundle, shot, instance, begin)['components']
                    for cid in first:
                        if first[cid]['drawing'] != before[cid]['drawing']:
                            raise ValueError('cannot interpolate different drawings on ' + cid + '; supply explicit transition artwork')
                    limits = dict(clip['interpolation'])
                    if prior_clip:
                        for name in limits:
                            limits[name] = min(limits[name], prior_clip['interpolation'][name])
                    for elapsed in range(length + 1):
                        current = evaluate_instance_performance(bundle, shot, instance, begin + elapsed)['components']
                        for cid in current:
                            for prop in ('offset', 'rotation'):
                                a, b = before[cid][prop], current[cid][prop]
                                delta = math.dist(a, b) if prop == 'offset' else abs((b - a + 180) % 360 - 180)
                                if delta > limits['max_' + prop + '_per_frame'] + 1e-7:
                                    raise ValueError(cid + '.' + prop + ' interpolation limit at blend frame ' + str(elapsed))
                        before = current
                prior_clip = clip


def validate_continuity(bundle):
    for scene in bundle['scenes']:
        for link in scene['continuity']:
            before, after = bundle['shots'][link['from_shot']], bundle['shots'][link['to_shot']]
            for character in link['characters']:
                left = [i for i in before['instances'] if i['character'] == character]
                right = [i for i in after['instances'] if i['character'] == character]
                if not left or not right or len(left) != len(right):
                    raise ValueError('continuity missing or ambiguous character instances: ' + character)
                right_by_id = {i['id']: i for i in right}
                for actor in left:
                    next_actor = right[0] if len(right) == 1 else right_by_id.get(actor['id'])
                    if next_actor is None:
                        raise ValueError('continuity requires matching instance IDs for repeated characters')
                    if 'costume' in link['requirements'] and actor['costume'] != next_actor['costume']:
                        raise ValueError('continuity costume mismatch for ' + character)
                    if 'scale' in link['requirements'] and abs(before['cast_scale'] - after['cast_scale']) > 1e-9:
                        raise ValueError('continuity relative scale mismatch for ' + character)
                    if 'position' in link['requirements']:
                        a = evaluate_instance_performance(bundle, before, actor, before['duration_frames'])['position']
                        b = evaluate_instance_performance(bundle, after, next_actor, 0)['position']
                        if math.dist(a, b) > 1e-6:
                            raise ValueError('continuity position mismatch for ' + character)
            if 'prop_ownership' in link['requirements']:
                def owners(shot, frame):
                    actors = {i['id']: i['character'] for i in shot['instances']}
                    return {p['id']: (p['prop'], actors.get(prop_owner(p, frame)['owner'])) for p in shot['props']}
                if owners(before, before['duration_frames']) != owners(after, 0):
                    raise ValueError('continuity prop ownership mismatch')


def dialogue_timing(bundle, shot_id):
    shot = bundle['shots'][shot_id]
    return {'shot': shot_id, 'duration_frames': shot['duration_frames'],
        'fps': copy.deepcopy(bundle['project']['render']['fps']), 'audio': copy.deepcopy(shot['audio']),
        'mouth_overrides': [{'instance': i['id'], 'character': i['character'], 'tracks': copy.deepcopy(i['tracks']['mouth'])}
                            for i in shot['instances'] if 'mouth' in i['tracks']],
        'note': 'Audio cues and mouth tracks remain editable; alignment alone does not establish convincing acting.'}
