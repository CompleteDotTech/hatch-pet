"""Reproducible synthetic acting reel with measurable transitions and contact.

All artwork is original geometric fixture material and all audio is a square-wave
test cue. It exercises production mechanics without claiming production art review.
"""
from __future__ import annotations

import argparse
import copy
import html
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

from production_contracts import asset_key, file_sha, load_project, read_json
from production_fixture import build_fixture_project, fixture_provenance, refresh_project_hashes, track, write_json
from production_performance import evaluate_instance_performance, prop_owner


def keyed(values, interpolation='linear'):
    return {'interpolation': interpolation,
            'keys': [{'frame': frame, 'value': copy.deepcopy(value)} for frame, value in values]}


def build_regression_project(root):
    """Extend the unchanged minimal factory with five explicit performance shots."""
    root = Path(root)
    build_fixture_project(root)
    cast = read_json(root / 'cast.json')
    project = read_json(root / 'project.json')

    def image_ref(name, size, painter):
        path = root / 'art' / (name + '.png')
        image = Image.new('RGBA', size)
        painter(ImageDraw.Draw(image))
        image.save(path)
        image.close()
        return {'path': path.relative_to(root).as_posix(), 'sha256': file_sha(path),
                'size': list(size), 'provenance': fixture_provenance()}

    def drawing(image):
        return {'viewpoint': 'front', 'costume': 'default', 'image': image, 'alpha': 'straight'}

    for character in cast['characters']:
        cid = character['id']
        color = character['identity']['palette']['body']
        character['dimensions'] = {'width': 40, 'height': 80}
        parts = {part['id']: part for part in character['components']}
        parts['body']['anchors'].update({'hip-left': [12, 36], 'hip-right': [28, 36]})
        parts['head']['anchors']['brows'] = [10, 4]
        for side in ('left', 'right'):
            source = image_ref(cid + '-' + side + '-leg', (8, 20),
                               lambda pen, fill=color: pen.rounded_rectangle((1, 0, 6, 19), radius=3, fill=fill))
            character['components'].append({'id': side + '-leg', 'role': 'limb', 'parent': 'body',
                'parent_anchor': 'hip-' + side, 'pivot': [4, 0], 'offset': [0, 0], 'anchors': {'sole': [4, 20]},
                'z': -1, 'drawings': {'default': drawing(source)}, 'default_drawing': 'default', 'mask': None, 'visible': True})
        brow_default = image_ref(cid + '-brows', (12, 4), lambda pen: pen.line((1, 2, 10, 2), fill='#292335'))
        brow_happy = image_ref(cid + '-brows-happy', (12, 4),
                              lambda pen: (pen.line((1, 2, 3, 1, 5, 2), fill='#292335'),
                                           pen.line((7, 2, 9, 1, 11, 2), fill='#292335')))
        character['components'].append({'id': 'brows', 'role': 'brows', 'parent': 'head', 'parent_anchor': 'brows',
            'pivot': [6, 2], 'offset': [0, 0], 'anchors': {}, 'z': 4,
            'drawings': {'default': drawing(brow_default), 'happy': drawing(brow_happy)},
            'default_drawing': 'default', 'mask': None, 'visible': True})
        grasp = image_ref(cid + '-hand-grasp', (8, 8),
                          lambda pen, fill=color: (pen.ellipse((0, 0, 7, 7), fill=fill),
                                                  pen.line((2, 3, 5, 3), fill='#292335')))
        parts['hand']['drawings']['grasp'] = drawing(grasp)
        arm_drawings = {}
        for index in range(13):
            length = max(4, index * 2)
            source = image_ref(cid + '-arm-' + str(index).zfill(2), (32, 8),
                lambda pen, length=length, fill=color: pen.rounded_rectangle((0, 1, length, 6), radius=2, fill=fill))
            arm_drawings['reach-' + str(index).zfill(2)] = drawing(source)
        arm_drawings['default'] = copy.deepcopy(arm_drawings['reach-00'])
        character['components'].append({'id': 'arm', 'role': 'limb', 'parent': 'body', 'parent_anchor': 'hand',
            'pivot': [0, 4], 'offset': [0, 0], 'anchors': {}, 'z': 1, 'drawings': arm_drawings,
            'default_drawing': 'default', 'mask': None, 'visible': True})
        for dimension, values in {
            'action': ['sit', 'stand', 'reach', 'hold', 'stop', 'listen', 'tumble'],
            'pose': ['walking', 'reaching', 'holding', 'releasing', 'reaction', 'tumble'],
            'contact': ['foot:ground'], 'intensity': ['medium'], 'hand': ['grasp']}.items():
            character['capabilities'][dimension] = list(dict.fromkeys(character['capabilities'].get(dimension, []) + values))
    write_json(root / 'cast.json', cast)

    backgrounds = {}
    for name, label in [('locomotion', 'IDLE > WALK > STOP'), ('sit-stand', 'STAND > SIT > STAND'),
                        ('reach-grasp-release', 'REACH > GRASP > HOLD > RELEASE'),
                        ('facial-dialogue', 'BODY / FACE / GAZE / MOUTH'), ('full-frame-override', 'EXPLICIT FULL-FRAME OVERRIDE')]:
        def paint(pen, label=label):
            pen.rectangle((0, 0, 319, 199), fill='#F8F0E0')
            pen.line((0, 188, 319, 188), fill='#B8B09F', width=2)
            pen.text((10, 10), label, fill='#292335')
            pen.text((10, 26), 'SYNTHETIC FIXTURE', fill='#875241')
        backgrounds[name] = image_ref('reg-' + name + '-background', (320, 200), paint)

    clips = {}
    def clip(name, start='standing', end='standing', duration=12, mode='once', body=None, root_delta=None,
             action=None, contacts=None, events=None, full_frames=None):
        value = {'schema_version': 1, 'kind': 'clip', 'id': 'reg-' + name, 'version': '1.0.0',
            'character': 'a@1.0.0', 'viewpoint': 'front', 'facing': 'front', 'start_pose': start, 'end_pose': end,
            'duration_frames': duration, 'mode': mode, 'completion': 'loop' if mode == 'loop' else 'hold',
            'root': {'offset': track([0, 0], root_delta, end=duration) if root_delta else track([0, 0])},
            'tracks': {'body': body} if body else {}, 'contacts': contacts or [], 'events': events or [],
            'entry_points': [{'frame': 0, 'pose': start}], 'exit_points': [{'frame': duration - 1, 'pose': end}],
            'interpolation': {'max_frames': 6, 'max_offset_per_frame': 8, 'max_rotation_per_frame': 30},
            'interruptions': {'policy': 'never', 'frames': [], 'cancel_pose': end, 'max_transition_frames': 6},
            'displacement': root_delta or [0, 0],
            'requirements': {'action': [action or name], 'pose': list(dict.fromkeys([start, end]))},
            'full_frames': full_frames or []}
        clips[name] = value
        return value

    clip('idle', mode='loop')
    clip('walk-start', end='walking', duration=6, action='walk',
         body={'right-leg': {'offset': track([0, 0], [-12, 0], end=5)}})
    contacts = [{'start_frame': start, 'end_frame': end, 'component': part, 'anchor': 'sole', 'kind': 'foot', 'target': 'ground'}
                for start, end, part in [(0, 6, 'left-leg'), (6, 12, 'right-leg')]]
    clip('walk', 'walking', 'walking', mode='loop', root_delta=[24, 0], contacts=contacts, body={
        'left-leg': {'offset': keyed([(0, [0, 0]), (6, [-12, 0]), (9, [-6, -6]), (12, [0, 0])])},
        'right-leg': {'offset': keyed([(0, [-12, 0]), (3, [-6, -6]), (6, [0, 0]), (12, [-12, 0])])}})
    clip('stop', 'walking', 'standing', duration=6, root_delta=[6, 0],
         body={'right-leg': {'offset': track([-12, 0], [0, 0], end=5)}})
    sitting = {'body': {'offset': track([0, 12])}, 'left-leg': {'rotation': track(70)}, 'right-leg': {'rotation': track(-70)}}
    clip('sit', end='sitting', body={'body': {'offset': track([0, 0], [0, 12], end=11)},
         'left-leg': {'rotation': track(0, 70, end=11)}, 'right-leg': {'rotation': track(0, -70, end=11)}})
    clip('seated', 'sitting', 'sitting', mode='hold', body=sitting, action='hold')
    clip('stand', 'sitting', 'standing', body={'body': {'offset': track([0, 12], [0, 0], end=11)},
         'left-leg': {'rotation': track(70, 0, end=11)}, 'right-leg': {'rotation': track(-70, 0, end=11)}})
    reach_keys = [(frame, 'reach-' + str(round(frame * 12 / 11)).zfill(2)) for frame in range(12)]
    clip('reach', end='reaching', body={'hand': {'offset': track([0, 0], [24, 0], end=11)},
                                      'arm': {'drawing': keyed(reach_keys, 'step')}})
    reached = {'hand': {'offset': track([24, 0]), 'drawing': track('grasp')}, 'arm': {'drawing': track('reach-12')}}
    def hand_contact(duration):
        return [{'start_frame': 0, 'end_frame': duration, 'component': 'hand', 'anchor': 'grip', 'kind': 'hand', 'target': 'cup'}]
    clip('grasp', 'reaching', 'holding', duration=6, body=copy.deepcopy(reached), contacts=hand_contact(6),
         events=[{'frame': 0, 'id': 'grasp', 'type': 'attach', 'component': 'hand', 'anchor': 'grip', 'target': 'cup'}])
    clip('hold', 'holding', 'holding', mode='hold', body=copy.deepcopy(reached), contacts=hand_contact(12))
    released = copy.deepcopy(reached)
    released['hand']['drawing'] = track('default')
    clip('release', 'holding', 'releasing', duration=6, body=released, contacts=hand_contact(1),
         events=[{'frame': 0, 'id': 'release', 'type': 'release', 'component': 'hand', 'anchor': 'grip', 'target': 'cup'}])
    retract_keys = [(frame, 'reach-' + str(12 - round(frame * 12 / 11)).zfill(2)) for frame in range(12)]
    clip('retract', 'releasing', 'standing', action='reach', body={
        'hand': {'offset': track([24, 0], [0, 0], end=11)}, 'arm': {'drawing': keyed(retract_keys, 'step')}})

    full_images = []
    for name, reverse in [('a', False), ('b', True)]:
        def paint(pen, reverse=reverse):
            pen.ellipse((5, 21, 34, 56), fill='#CB5B35')
            pen.ellipse((8 if reverse else 3, 6, 29 if reverse else 24, 27), fill='#CB5B35')
            pen.line((6, 47, 34, 61) if reverse else (5, 61, 33, 45), fill='#CB5B35', width=6)
            pen.ellipse((12, 15, 15, 18), fill='#292335')
            pen.arc((11, 18, 22, 25), 0, 180, fill='#292335', width=1)
        full_images.append(image_ref('full-pose-' + name, (40, 80), paint))
    clip('full-frame', duration=36, action='tumble', full_frames=[
        {'start_frame': 12, 'end_frame': 18, 'image': full_images[0], 'pivot': [20, 64], 'viewpoint': 'front'},
        {'start_frame': 18, 'end_frame': 24, 'image': full_images[1], 'pivot': [20, 64], 'viewpoint': 'front'}])
    idle_b = copy.deepcopy(clips['idle'])
    idle_b.update(id='reg-idle-b', character='b@1.0.0')
    clips['idle-b'] = idle_b
    for value in clips.values():
        project['clips'].append(write_json(root / (value['id'] + '.json'), value))

    def actor(identity, position, placements):
        return {'id': identity, 'character': identity + '@1.0.0', 'viewpoint': 'front', 'facing': 'front',
            'costume': 'default', 'position': position, 'z': 10,
            'clips': [{'clip': asset_key(clips[name]), 'start_frame': start, 'end_frame': end,
                       'transition': {'kind': 'cut', 'frames': 0}} for name, start, end in placements],
            'tracks': {}, 'requirements': {'expression': ['neutral'], 'gaze': ['partner']}, 'bindings': {}}

    def shot(name, duration, actors):
        return {'id': name, 'duration_frames': duration, 'cast_scale': 1, 'instances': actors,
            'props': [], 'interactions': [], 'audio': [],
            'layers': [{'id': 'background', 'image': backgrounds[name], 'position': [0, 0], 'z': -100,
                        'opacity': 1, 'parallax': 1}],
            'camera': {'position': track([0, 0]), 'zoom': track(1),
                       'bounds': {'max_pan_per_frame': 16, 'min_zoom': .5, 'max_zoom': 2}},
            'lighting': {'direction': 'ambient', 'color_treatment': 'unchanged'},
            'explicit_requirements': ['Original synthetic regression fixture; exercise editable performance mechanics.'],
            'inferred_choices': ['Geometric drawings and square-wave audio carry no production artwork acceptance.']}

    locomotion = shot('locomotion', 60, [actor('a', [80, 170], [
        ('idle', 0, 12), ('walk-start', 12, 18), ('walk', 18, 42), ('stop', 42, 48), ('idle', 48, 60)])])
    sit_stand = shot('sit-stand', 60, [actor('a', [160, 162], [
        ('idle', 0, 12), ('sit', 12, 24), ('seated', 24, 36), ('stand', 36, 48), ('idle', 48, 60)])])
    reach = shot('reach-grasp-release', 72, [actor('a', [120, 150], [
        ('idle', 0, 12), ('reach', 12, 24), ('grasp', 24, 30), ('hold', 30, 42),
        ('release', 42, 48), ('retract', 48, 60), ('idle', 60, 72)])])
    reach['instances'][0]['bindings'] = {'cup': 'cup-object'}
    reach['props'] = [{'id': 'cup-object', 'prop': 'cup@1.0.0', 'position': [160, 130], 'z': 20,
        'owner': None, 'attachment': None, 'tracks': {}, 'ownership': [
            {'frame': 24, 'from': None, 'to': 'a', 'attachment': {'instance': 'a', 'component': 'hand', 'anchor': 'grip'}, 'event': 'pickup'},
            {'frame': 42, 'from': 'a', 'to': None, 'attachment': None, 'event': 'putdown'}]}]
    reach['interactions'] = [{'id': event, 'frame': frame, 'prop': 'cup-object', 'position': [160, 130], 'tolerance': 0,
        'participants': [{'instance': 'a', 'component': 'hand', 'anchor': 'grip', 'marker': marker}]}
        for event, frame, marker in [('pickup', 24, 'grasp'), ('putdown', 42, 'release')]]
    facial = shot('facial-dialogue', 48, [actor('a', [100, 150], [('idle', 0, 48)]),
                                         actor('b', [220, 150], [('idle-b', 0, 48)])])
    for instance in facial['instances']:
        instance['bindings'] = {'partner': 'b' if instance['id'] == 'a' else 'a'}
        instance['requirements'].update(expression=['neutral', 'happy'], intensity=['medium'])
        instance['tracks'] = {
            'body': {'head': {'rotation': keyed([(0, 0), (18, -5), (26, 5), (34, 0)])}},
            'face': {'eyes': {'visible': keyed([(0, True), (4, False), (5, True), (26, False), (27, True)], 'step')},
                     'brows': {'drawing': keyed([(0, 'default'), (20, 'happy'), (42, 'default')], 'step')}},
            'gaze': {'eyes': {'offset': track([1 if instance['id'] == 'a' else -1, 0])}},
            'mouth': {'mouth': {'drawing': keyed([(0, 'default'), (8, 'open'), (16, 'default'), (20, 'open'), (26, 'default')]
                        if instance['id'] == 'a' else [(0, 'default'), (30, 'open'), (40, 'default')], 'step')}}}
    from production_render import audio_fixture
    for identity, start, duration, frequency, cues in [('a', 8, 18, 220, [(8, 16), (20, 26)]),
                                                      ('b', 30, 12, 330, [(30, 40)])]:
        path = root / 'audio' / ('fixture-' + identity + '.wav')
        audio = audio_fixture(path, duration_frames=duration, sample_rate=24000, frequency=frequency)
        facial['audio'].append({'id': 'cue-' + identity,
            'file': {'path': path.relative_to(root).as_posix(), 'sha256': audio['sha256']},
            'start_frame': start, 'duration_frames': duration, 'speaker': identity,
            'text': 'Square-wave fixture cue ' + identity.upper() + '; no spoken dialogue.',
            'provenance': audio['provenance'], 'gain': .25,
            'mouth_cues': [{'start_frame': a, 'end_frame': b, 'shape': 'open'} for a, b in cues]})
    full = shot('full-frame-override', 36, [actor('a', [160, 150], [('full-frame', 0, 36)])])
    full['cast_scale'] = 1.5
    scene = {'schema_version': 1, 'kind': 'scene', 'id': 'regression-performances', 'version': '1.0.0',
             'shots': [locomotion, sit_stand, reach, facial, full], 'continuity': []}
    project['scenes'].append(write_json(root / 'regression-scene.json', scene))
    project['limits'].update(max_frames=1200, max_assets=256, max_generation_calls=0)
    write_json(root / 'project.json', project)
    return refresh_project_hashes(root)


def inspect_regression_behaviour(bundle):
    """Check evaluated geometry at actual authored intervals; no art verdict is inferred."""
    from production_render import evaluate_frame
    locomotion = bundle['shots']['locomotion']
    actor = locomotion['instances'][0]
    frames = [0, 30, 48, 59]
    positions = [evaluate_instance_performance(bundle, locomotion, actor, frame)['position'] for frame in frames]
    expected = [[80, 170], [104, 170], [134, 170], [134, 170]]
    if positions != expected:
        raise ValueError('synthetic locomotion root displacement changed: ' + repr(positions))
    planted = []
    for start, end, part in [(18, 24, 'left-leg'), (24, 30, 'right-leg'), (30, 36, 'left-leg'), (36, 42, 'right-leg')]:
        points = [evaluate_frame(bundle, 'locomotion', frame)['instances']['a']['components'][part]['anchors']['sole']
                  for frame in range(start, end)]
        drift = max(math.dist(points[0], point) for point in points)
        if drift > 1e-6:
            raise ValueError('synthetic planted foot slips: ' + part + ' at ' + str(start) + ' by ' + str(drift))
        planted.append({'start_frame': start, 'end_frame': end, 'component': part, 'world_anchor': points[0], 'max_drift_pixels': drift})
    sit = bundle['shots']['sit-stand']
    sitting = [evaluate_instance_performance(bundle, sit, sit['instances'][0], frame)['components']['body']['offset']
               for frame in (0, 24, 48)]
    if sitting != [[0, 0], [0, 12], [0, 0]]:
        raise ValueError('synthetic stand/sit/stand offsets changed')
    prop = bundle['shots']['reach-grasp-release']['props'][0]
    owners = [prop_owner(prop, frame)['owner'] for frame in (23, 24, 41, 42)]
    if owners != [None, 'a', 'a', None]:
        raise ValueError('synthetic grasp/release timing changed')
    contacts = [evaluate_frame(bundle, 'reach-grasp-release', frame)['interactions'] for frame in (24, 42)]
    facial = bundle['shots']['facial-dialogue']
    facial_states = [evaluate_instance_performance(bundle, facial, facial['instances'][0], frame)['components'] for frame in (0, 21, 44)]
    brows = [state['brows']['drawing'] for state in facial_states]
    if brows != ['default', 'happy', 'default'] or facial_states[1]['eyes']['offset'] != [1, 0] or facial_states[1]['mouth']['drawing'] != 'open':
        raise ValueError('synthetic independent expression, gaze or mouth tracks changed')
    counts = [len([layer for layer in evaluate_frame(bundle, 'full-frame-override', frame)['layers'] if layer['track'] == 'a'])
              for frame in (0, 15, 21, 30)]
    if counts != [9, 1, 1, 9]:
        raise ValueError('synthetic full-frame override boundaries changed')
    return {'schema_version': 1, 'fixture': True, 'production_art_acceptance': False,
        'locomotion': {'frames': frames, 'positions': positions, 'planted_contacts': planted},
        'sit_stand': {'frames': [0, 24, 48], 'body_offsets': sitting},
        'grasp_release': {'frames': [23, 24, 41, 42], 'owners': owners, 'contacts': contacts},
        'expression': {'frames': [0, 21, 44], 'brow_drawings': brows,
            'frame_21': {'gaze_offset': facial_states[1]['eyes']['offset'], 'mouth': facial_states[1]['mouth']['drawing'],
                         'head_rotation': facial_states[1]['head']['rotation']}},
        'full_frame_override': {'frames': [0, 15, 21, 30], 'character_layer_counts': counts},
        'audio': {'kind': 'deterministic PCM square-wave fixture cues', 'spoken_dialogue': False,
                  'tracks': [audio['file']['path'] for audio in facial['audio']]},
        'limitations': ['Geometry and PCM checks are synthetic regression evidence.',
                        'No production artwork, spoken dialogue, auditory review or human review is claimed.']}


def _record_synthetic_reviews(root, bundle, render_paths):
    from production_workflow import record_review, review_template
    evidence = {'path': 'performance-evidence.json', 'sha256': file_sha(root / 'performance-evidence.json'),
                'note': 'Deterministic synthetic performance assertions; no production artwork approval.', 'method': 'automated_check'}
    targets = [({'kind': 'character', 'character_id': char['id'], 'version': char['version']}, None)
               for char in bundle['characters'].values()]
    targets += [({'kind': 'clip', 'clip_id': clip['id'], 'version': clip['version']}, None) for clip in bundle['clips'].values()]
    for scene in bundle['scenes']:
        for shot in scene['shots']:
            manifest_path = render_paths[scene['id']] + '/shots/' + shot['id'] + '/render-manifest.json'
            targets.append(({'kind': 'shot', 'scene_id': scene['id'], 'shot_id': shot['id']}, manifest_path))
    for target, manifest in targets:
        receipt = review_template(root, target, render_manifest=manifest, project=bundle)
        receipt['reviewer'] = {'kind': 'synthetic', 'id': 'regression-demo', 'name': 'Synthetic regression gate'}
        for dimension, verdict in receipt['dimensions'].items():
            chosen = copy.deepcopy(evidence)
            if manifest and dimension in ('final_artifacts', 'timing_av_sync'):
                frame_path = (Path(manifest).parent / 'frames/000000.png').as_posix()
                chosen = {'path': frame_path, 'sha256': file_sha(root / frame_path), 'frames': [0],
                          'note': 'Exact completed synthetic raster inventory verified by the renderer.', 'method': 'automated_check'}
            verdict.update(verdict='pass', notes='Synthetic regression contract passed; no production visual or human approval.', evidence=[chosen])
        record_review(root, receipt)


def render_regression_demo(root, *, movie=False):
    from production_render import contact_sheet, mux_video, render_scene, validate_render
    from production_workflow import coverage_report, dependency_snapshot
    root = Path(root).resolve()
    bundle = load_project(build_regression_project(root))
    evidence = inspect_regression_behaviour(bundle)
    write_json(root / 'performance-evidence.json', evidence)
    scenes, paths = [], {}
    for scene in bundle['scenes']:
        relative = 'renders/' + scene['id']
        destination = root / relative
        manifest = render_scene(bundle, scene['id'], destination)
        validation = validate_render(destination)
        storyboard = contact_sheet(destination, root / (scene['id'] + '-storyboard.png'), cell_width=240)
        resumed = render_scene(bundle, scene['id'], destination)
        # Per-shot checkpoint statistics are recorded by the renderer and tested separately.
        if (resumed['status'] != 'complete' or len(resumed['frames']) != len(manifest['frames']) or
                resumed['operation']['rendered_frames'] != 0 or resumed['operation']['reused_frames'] != manifest['frame_count']):
            raise ValueError('synthetic scene resume did not preserve the complete frame inventory')
        film = mux_video(destination) if movie else None
        paths[scene['id']] = relative
        scenes.append({'scene_id': scene['id'], 'frame_count': manifest['frame_count'],
            'render_manifest': relative + '/render-manifest.json', 'preview': relative + '/index.html',
            'storyboard': Path(storyboard['path']).relative_to(root).as_posix(),
            'movie': relative + '/' + film['path'] if film else None, 'validated': bool(validation.get('valid', True)),
            'complete': manifest['status'] == 'complete', 'resume_operation': resumed['operation']})
    _record_synthetic_reviews(root, bundle, paths)
    coverage = coverage_report(root)
    write_json(root / 'coverage-report.json', coverage)
    write_json(root / 'dependency-snapshot.json', dependency_snapshot(root))
    acceptance = {'schema_version': 1, 'fixture': True, 'human_review': False, 'production_art_acceptance': False,
        'external_integration': False, 'scene_renders': scenes, 'coverage_ready': coverage['ready'],
        'performance_evidence': 'performance-evidence.json',
        'note': 'All receipts are explicitly synthetic automated regression gates.'}
    write_json(root / 'acceptance.json', acceptance)
    rows = '\n'.join('- [' + item['scene_id'] + '](' + item['preview'] + '): ' + str(item['frame_count']) +
                     ' frames; [storyboard](' + item['storyboard'] + ')' +
                     ('; [review movie](' + item['movie'] + ')' if item['movie'] else '') + '.' for item in scenes)
    (root / 'README.md').write_text('# Synthetic production regression demonstration\n\n'
        'This project contains original geometric fixture artwork and deterministic PCM test cues. '
        'It has no production artwork approval, spoken dialogue, auditory review, human review or external application integration.\n\n'
        'The main 23-second, 276-frame reel shows idle/walk/stop with planted feet, stand/sit/stand, '
        'reach/grasp/hold/release, independent body/face/gaze/mouth acting, and an explicit full-frame override. '
        'Two additional one-second scenes reuse the exact same two character versions and cup asset.\n\n'
        + rows + '\n\n'
        'Editable sources are `project.json`, `cast.json`, clip JSON, scene JSON, `art/` and `audio/`. '
        'See [performance evidence](performance-evidence.json), [coverage](coverage-report.json) and '
        '[acceptance](acceptance.json) for exact current scope. Review receipts identify synthetic checks separately.\n\n'
        'Rebuild with `python scripts/production_regression_demo.py --output-dir examples/production-fixture --movie` '
        'from the repository root. If delivery uses a complete-project bundle, restore it before opening master previews '
        'or asking for current artifact review status.\n', encoding='utf-8')
    links = ''.join('<li><a href="' + html.escape(item['preview'], quote=True) + '">' + html.escape(item['scene_id']) +
                    '</a> — ' + str(item['frame_count']) + ' frames</li>' for item in scenes)
    (root / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Synthetic performance fixtures</title>'
        '<h1>Synthetic performance regression fixtures</h1><p>Geometric test artwork and square-wave cues. '
        'No production artwork, spoken dialogue or human approval is claimed.</p><ul>' + links + '</ul>'
        '<p><a href="performance-evidence.json">Measured performance evidence</a></p>', encoding='utf-8')
    return acceptance


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', default='examples/production-fixture')
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--movie', action='store_true')
    args = parser.parse_args(argv)
    if args.build_only:
        path = build_regression_project(args.output_dir)
        bundle = load_project(path)
        print(json.dumps({'project': str(path), 'evidence': inspect_regression_behaviour(bundle)}, indent=2))
    else:
        print(json.dumps(render_regression_demo(args.output_dir, movie=args.movie), indent=2))


if __name__ == '__main__':
    main()
