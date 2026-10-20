"""Behavioral performance tests for authored motion, cancellation and independent acting."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from production_contracts import (asset_key, load_project, planned_requirements, validate_clip,
                                 validate_shot, validate_track)
from production_fixture import build_fixture_project, track
from production_performance import (dialogue_timing, evaluate_clip, evaluate_instance_performance,
    evaluate_track, incompatible_requirements, interruption_plan, prop_owner, validate_transition_limits)


class ProductionPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.bundle = load_project(build_fixture_project(self.directory.name))
        self.clip = copy.deepcopy(self.bundle['clips']['idle-a@1.0.0'])
        self.shot = copy.deepcopy(self.bundle['shots']['exchange'])

    def clean_clip(self, identity='test-clip', start='standing', end='standing', mode='once', duration=12):
        clip = copy.deepcopy(self.clip)
        clip.update(id=identity, start_pose=start, end_pose=end, mode=mode, duration_frames=duration,
                    completion='loop' if mode == 'loop' else 'hold', tracks={}, contacts=[], events=[],
                    entry_points=[{'frame': 0, 'pose': start}], exit_points=[{'frame': duration - 1, 'pose': end}],
                    interruptions={'policy': 'never', 'frames': [], 'cancel_pose': end, 'max_transition_frames': 6})
        return clip

    def simple_shot(self, duration=24):
        shot = copy.deepcopy(self.shot)
        shot.update(id='test', duration_frames=duration, props=[], interactions=[], audio=[])
        shot['instances'] = [shot['instances'][0]]
        shot['instances'][0].update(clips=[], tracks={}, bindings={}, requirements={})
        return shot

    def place(self, clip, start, end, blend=0):
        return {'clip': asset_key(clip), 'start_frame': start, 'end_frame': end,
                'transition': {'kind': 'interpolate' if blend else 'cut', 'frames': blend}}

    def install(self, shot, clips, validate=True):
        for clip in clips:
            self.bundle['clips'][asset_key(clip)] = clip
            if validate:
                validate_clip(clip, self.bundle['characters'])
        self.bundle['shots'] = {shot['id']: shot}
        self.bundle['scenes'] = []
        if validate:
            validate_shot(shot, self.bundle['characters'], self.bundle['clips'], self.bundle['props'], True)
        return shot['instances'][0]

    def test_linear_and_step_tracks_use_exact_integer_frames(self):
        self.assertEqual(5, evaluate_track(track(0, 10, end=10), 5))
        self.assertEqual([5, 10], evaluate_track(track([0, 0], [10, 20], end=10), 5))
        discrete = track('default', 'open', end=5)
        self.assertEqual('default', evaluate_track(discrete, 4))
        self.assertEqual('open', evaluate_track(discrete, 5))
        for frame in (True, .5, -1, 18001):
            with self.subTest(frame=frame), self.assertRaisesRegex(ValueError, 'integer'):
                evaluate_track(discrete, frame)

    def test_evaluation_returns_copies_without_mutating_authored_keys(self):
        source = track([0, 0], [12, 6])
        snapshot = copy.deepcopy(source)
        result = evaluate_track(source, 12)
        result[0] = 900
        self.assertEqual(snapshot, source)
        evaluated = evaluate_clip(self.clip, 6)
        evaluated['root']['offset'][0] = 999
        evaluated['events'][0]['id'] = 'changed'
        self.assertEqual([0, 0], self.clip['root']['offset']['keys'][0]['value'])
        self.assertEqual('release', self.clip['events'][0]['id'])

    def test_loop_displacement_accumulates_at_integer_cycle_boundaries(self):
        clip = self.clean_clip(mode='loop')
        clip['root']['offset'] = track([0, 0], [60, 0])
        clip['displacement'] = [60, 0]
        validate_clip(clip, self.bundle['characters'])
        self.assertEqual([30, 0], evaluate_clip(clip, 6)['root']['offset'])
        self.assertEqual([60, 0], evaluate_clip(clip, 12)['root']['offset'])
        self.assertEqual([125, 0], evaluate_clip(clip, 25)['root']['offset'])

    def test_once_completion_preserves_root_and_declares_hold_return_or_exit(self):
        clip = self.clean_clip()
        clip['root']['offset'] = track([0, 0], [60, 0])
        clip['displacement'] = [60, 0]
        clip['tracks']['body'] = {'head': {'rotation': track(0, 24)}}
        state = evaluate_clip(clip, 12)
        self.assertEqual(22, state['body']['head']['rotation'])
        self.assertEqual([60, 0], state['root']['offset'])
        self.assertTrue(state['complete'])
        clip['completion'] = 'return-to-start'
        state = evaluate_clip(clip, 20)
        self.assertEqual(0, state['body']['head']['rotation'])
        self.assertEqual([60, 0], state['root']['offset'])
        clip['completion'] = 'exit'
        self.assertFalse(evaluate_clip(clip, 12)['root']['visible'])

    def test_hold_is_static_and_emits_only_entry_events(self):
        clip = self.clean_clip(mode='hold')
        clip['events'] = [{'id': 'entered', 'type': 'marker', 'frame': 0}]
        clip['tracks'] = {'body': {'head': {'rotation': track(10)}}}
        validate_clip(clip, self.bundle['characters'])
        self.assertEqual(1, len(evaluate_clip(clip, 0)['events']))
        self.assertEqual([], evaluate_clip(clip, 7)['events'])
        self.assertEqual(10, evaluate_clip(clip, 24)['body']['head']['rotation'])
        clip['tracks']['body']['head']['rotation'] = track(10, 20)
        with self.assertRaisesRegex(ValueError, 'hold clip cannot contain changing tracks'):
            validate_clip(clip, self.bundle['characters'])

    def test_body_face_gaze_and_mouth_channels_remain_independent(self):
        self.clip['tracks']['body']['head']['rotation'] = track(0, 24)
        self.clip['tracks']['gaze']['eyes']['offset'] = track([0, 0], [3, 0])
        state = evaluate_clip(self.clip, 6)
        self.assertEqual(12, state['body']['head']['rotation'])
        self.assertEqual([1.5, 0], state['gaze']['eyes']['offset'])
        self.assertEqual('open', state['mouth']['mouth']['drawing'])
        self.clip['tracks']['mouth']['mouth']['drawing'] = track('default')
        changed = evaluate_clip(self.clip, 6)
        for channel in ('body', 'face', 'gaze'):
            self.assertEqual(state[channel], changed[channel])

    def test_shot_mouth_override_preserves_clip_body_and_cast_scale(self):
        shot = self.shot
        actor = shot['instances'][0]
        actor['tracks'] = {'mouth': {'mouth': {'drawing': track('default')}}}
        shot['cast_scale'] = 1.5
        before = evaluate_instance_performance(self.bundle, self.shot, actor, 6)
        self.assertEqual('default', before['components']['mouth']['drawing'])
        self.assertTrue(before['components']['eyes']['visible'])
        self.assertEqual(0, before['components']['head']['rotation'])
        self.assertEqual(1.5, before['scale'])
        self.assertEqual([100, 140], before['position'])

    def test_prop_ownership_changes_on_the_exact_shared_frame_without_mutating_metadata(self):
        prop = self.shot['props'][0]
        self.assertEqual('a', prop_owner(prop, 5)['owner'])
        state = prop_owner(prop, 6)
        self.assertEqual('b', state['owner'])
        state['attachment']['component'] = 'changed'
        self.assertEqual('hand', prop['ownership'][0]['attachment']['component'])

    def test_contacts_are_half_open_and_markers_are_exact_frame_events(self):
        self.clip['contacts'][0].update(start_frame=2, end_frame=8)
        self.assertEqual([], evaluate_clip(self.clip, 1)['contacts'])
        self.assertEqual(1, len(evaluate_clip(self.clip, 2)['contacts']))
        self.assertEqual(1, len(evaluate_clip(self.clip, 7)['contacts']))
        self.assertEqual([], evaluate_clip(self.clip, 8)['contacts'])
        self.assertEqual([], evaluate_clip(self.clip, 5)['events'])
        self.assertEqual('release', evaluate_clip(self.clip, 6)['events'][0]['id'])
        self.assertEqual([], evaluate_clip(self.clip, 7)['events'])

    def test_interruptions_obey_markers_cancel_pose_and_transition_bounds(self):
        with self.assertRaisesRegex(ValueError, 'forbidden'):
            interruption_plan(self.clip, 5, 'standing')
        self.assertTrue(interruption_plan(self.clip, 6, 'standing')['allowed'])
        with self.assertRaisesRegex(ValueError, 'compatible cancel_pose'):
            interruption_plan(self.clip, 6, 'sitting')
        self.assertEqual(3, interruption_plan(self.clip, 6, 'sitting', 3)['blend_frames'])
        with self.assertRaisesRegex(ValueError, 'bounded transition'):
            interruption_plan(self.clip, 6, 'sitting', 7)
        self.clip['interruptions']['policy'] = 'never'
        with self.assertRaisesRegex(ValueError, 'forbidden'):
            interruption_plan(self.clip, 6, 'standing')

    def test_early_once_placement_requires_an_authorized_interruption(self):
        shot, outgoing, incoming = self.simple_shot(12), self.clean_clip('out'), self.clean_clip('in')
        shot['instances'][0]['clips'] = [self.place(outgoing, 0, 6), self.place(incoming, 6, 12)]
        with self.assertRaisesRegex(ValueError, 'forbidden'):
            self.install(shot, [outgoing, incoming])
        outgoing['interruptions'].update(policy='at-markers', frames=[6])
        self.install(shot, [outgoing, incoming])

    def test_loop_midcycle_cuts_require_authored_exit_or_cancellation_policy(self):
        shot, outgoing, incoming = self.simple_shot(24), self.clean_clip('out', mode='loop'), self.clean_clip('in')
        shot['instances'][0]['clips'] = [self.place(outgoing, 0, 6), self.place(incoming, 6, 24)]
        with self.assertRaisesRegex(ValueError, 'forbidden'):
            self.install(shot, [outgoing, incoming])
        outgoing['exit_points'].append({'frame': 5, 'pose': 'standing'})
        self.install(shot, [outgoing, incoming])
        outgoing['exit_points'].pop()
        shot['instances'][0]['clips'] = [self.place(outgoing, 0, 12), self.place(incoming, 12, 24)]
        self.install(shot, [outgoing, incoming])

    def test_pose_mismatch_requires_an_explicit_bounded_transition(self):
        shot = self.simple_shot()
        outgoing, incoming = self.clean_clip('out', end='sitting'), self.clean_clip('in')
        shot['instances'][0]['clips'] = [self.place(outgoing, 0, 12), self.place(incoming, 12, 24)]
        with self.assertRaisesRegex(ValueError, 'incompatible pose cut'):
            self.install(shot, [outgoing, incoming])
        shot['instances'][0]['clips'][1]['transition'] = {'kind': 'interpolate', 'frames': 4}
        self.install(shot, [outgoing, incoming])

    def test_numeric_transition_checks_rates_and_rejects_unblended_drawing_changes(self):
        shot = self.simple_shot()
        outgoing, incoming = self.clean_clip('out'), self.clean_clip('in')
        outgoing['tracks'] = {'body': {'head': {'rotation': track(0)}}}
        incoming['tracks'] = {'body': {'head': {'rotation': track(90)}}}
        outgoing['interpolation']['max_rotation_per_frame'] = 10
        incoming['interpolation']['max_rotation_per_frame'] = 10
        shot['instances'][0]['clips'] = [self.place(outgoing, 0, 12), self.place(incoming, 12, 24, 3)]
        self.install(shot, [outgoing, incoming])
        with self.assertRaisesRegex(ValueError, 'interpolation limit'):
            validate_transition_limits(self.bundle)
        incoming['tracks']['body']['head']['rotation'] = track(20)
        validate_transition_limits(self.bundle)
        incoming['tracks']['mouth'] = {'mouth': {'drawing': track('open')}}
        with self.assertRaisesRegex(ValueError, 'different drawings'):
            validate_transition_limits(self.bundle)

    def test_step_numeric_track_checks_the_actual_jump_not_key_spacing(self):
        value = track(0, 90, end=12, interpolation='step')
        with self.assertRaisesRegex(ValueError, 'per-frame interpolation limit'):
            validate_track(value, 12, 'turn', 'number', 10)
        value['interpolation'] = 'linear'
        validate_track(value, 12, 'turn', 'number', 10)

    def test_transition_validates_the_moving_target_at_every_blended_frame(self):
        shot = self.simple_shot()
        outgoing, incoming = self.clean_clip('out'), self.clean_clip('in')
        outgoing['tracks'] = {'body': {'head': {'rotation': track(0)}}}
        incoming['tracks'] = {'body': {'head': {'rotation': track(40, 80, end=4)}}}
        outgoing['interpolation']['max_rotation_per_frame'] = 10
        incoming['interpolation']['max_rotation_per_frame'] = 10
        shot['instances'][0]['clips'] = [self.place(outgoing, 0, 12), self.place(incoming, 12, 24, 4)]
        actor = self.install(shot, [outgoing, incoming])
        self.assertEqual(12.5, evaluate_instance_performance(self.bundle, shot, actor, 13)['components']['head']['rotation'])
        with self.assertRaisesRegex(ValueError, 'blend frame 1'):
            validate_transition_limits(self.bundle)

    def test_idle_walk_stop_accumulates_world_displacement_without_scale_pulsing(self):
        shot = self.simple_shot(36)
        idle, walk, stop = self.clean_clip('idle'), self.clean_clip('walk'), self.clean_clip('stop')
        walk['root']['offset'] = track([0, 0], [60, 0])
        walk['displacement'] = [60, 0]
        shot['instances'][0]['clips'] = [self.place(idle, 0, 12), self.place(walk, 12, 24), self.place(stop, 24, 36)]
        actor = self.install(shot, [idle, walk, stop])
        positions = [evaluate_instance_performance(self.bundle, shot, actor, frame)['position'][0] for frame in (11, 18, 24, 35)]
        self.assertEqual([100, 130, 160, 160], positions)
        self.assertEqual({1}, {evaluate_instance_performance(self.bundle, shot, actor, f)['scale'] for f in range(36)})

    def test_authored_sit_reach_hold_release_and_reaction_pose_chains_compose(self):
        for poses in (['standing', 'sitting', 'standing'], ['standing', 'reaching', 'holding', 'holding', 'standing'],
                      ['neutral', 'reaction', 'neutral']):
            shot = self.simple_shot((len(poses) - 1) * 12)
            clips = [self.clean_clip('pose-' + str(index), start=a, end=b) for index, (a, b) in enumerate(zip(poses, poses[1:]))]
            shot['instances'][0]['clips'] = [self.place(clip, index * 12, (index + 1) * 12) for index, clip in enumerate(clips)]
            with self.subTest(poses=poses):
                self.install(shot, clips)

    def test_planned_coverage_is_independent_and_binds_intervals_character_versions_and_sources(self):
        requirements = planned_requirements(self.bundle, 'exchange')
        self.assertLess(len(requirements), 40)
        self.assertEqual(len(requirements), len({row['id'] for row in requirements}))
        self.assertTrue({'viewpoint', 'facing', 'costume', 'pose', 'action', 'gaze'} <= {row['dimension'] for row in requirements})
        self.assertEqual({'a@1.0.0', 'b@1.0.0'}, {row['character'] for row in requirements})
        self.assertEqual({'explicit', 'clip'}, {row['source'] for row in requirements})
        self.assertEqual({(0, 12)}, {(row['start_frame'], row['end_frame']) for row in requirements})

    def test_restriction_requires_temporal_overlap_of_independent_dimensions(self):
        character = {'restrictions': [{'when': {'viewpoint': ['back'], 'mouth': ['open']}, 'reason': 'Mouth is occluded.'}]}
        requirements = [{'dimension': 'viewpoint', 'value': 'back', 'start_frame': 0, 'end_frame': 6},
                        {'dimension': 'mouth', 'value': 'open', 'start_frame': 6, 'end_frame': 12}]
        self.assertEqual([], incompatible_requirements(character, requirements))
        requirements[1]['start_frame'] = 5
        self.assertEqual([[5, 6]], incompatible_requirements(character, requirements)[0]['intervals'])

    def test_dialogue_preserves_editable_cues_and_explicit_mouth_overrides(self):
        self.shot['audio'] = [{'id': 'line', 'file': {'path': 'audio.wav', 'sha256': '0' * 64},
            'start_frame': 2, 'duration_frames': 6, 'speaker': 'a', 'text': 'Synthetic cue timing.',
            'provenance': {'kind': 'fixture', 'origin': 'Test cue metadata', 'fixture': True}, 'gain': .5,
            'mouth_cues': [{'start_frame': 3, 'end_frame': 5, 'shape': 'open'}]}]
        self.shot['instances'][0]['tracks']['mouth'] = {'mouth': {'drawing': track('default')}}
        validate_shot(self.shot, self.bundle['characters'], self.bundle['clips'], self.bundle['props'], True)
        self.bundle['shots']['exchange'] = self.shot
        timing = dialogue_timing(self.bundle, 'exchange')
        self.assertEqual('Synthetic cue timing.', timing['audio'][0]['text'])
        self.assertEqual('a', timing['mouth_overrides'][0]['instance'])
        requirement = next(r for r in planned_requirements(self.bundle, 'exchange') if r['dimension'] == 'mouth')
        self.assertEqual((3, 5, 'explicit'), (requirement['start_frame'], requirement['end_frame'], requirement['source']))
        self.shot['audio'][0]['mouth_cues'].append({'start_frame': 4, 'end_frame': 7, 'shape': 'open'})
        with self.assertRaisesRegex(ValueError, 'nonoverlapping'):
            validate_shot(self.shot, self.bundle['characters'], self.bundle['clips'], self.bundle['props'], True)

    def test_full_frame_override_has_exact_boundaries_and_preserves_root_motion(self):
        image = copy.deepcopy(self.bundle['characters']['a@1.0.0']['components'][0]['drawings']['default']['image'])
        image['size'] = [40, 60]
        self.clip['full_frames'] = [{'start_frame': 2, 'end_frame': 4, 'image': image, 'pivot': [20, 60], 'viewpoint': 'front'}]
        validate_clip(self.clip, self.bundle['characters'])
        self.assertIsNone(evaluate_clip(self.clip, 1)['full_frame'])
        self.assertEqual(image, evaluate_clip(self.clip, 2)['full_frame']['image'])
        self.assertIsNotNone(evaluate_clip(self.clip, 3)['full_frame'])
        self.assertIsNone(evaluate_clip(self.clip, 4)['full_frame'])
        self.assertEqual([0, 0], evaluate_clip(self.clip, 3)['root']['offset'])
        self.clip['full_frames'][0]['image']['size'] = [41, 60]
        with self.assertRaisesRegex(ValueError, 'canonical character viewport'):
            validate_clip(self.clip, self.bundle['characters'])


class ProductionRegressionDemoTests(unittest.TestCase):
    def setUp(self):
        from production_regression_demo import build_regression_project
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.bundle = load_project(build_regression_project(self.root))

    def test_regression_factory_is_reproducible_and_measures_real_authored_intervals(self):
        from production_regression_demo import build_regression_project, inspect_regression_behaviour
        with tempfile.TemporaryDirectory() as other:
            second = load_project(build_regression_project(other))
            self.assertEqual(self.bundle['project'], second['project'])
            self.assertEqual(self.bundle['inventory'], second['inventory'])
        self.assertEqual(['first-scene', 'second-scene', 'regression-performances'], [s['id'] for s in self.bundle['scenes']])
        self.assertEqual(300, self.bundle['resources']['total_frames'])
        self.assertEqual(0, self.bundle['project']['limits']['max_generation_calls'])
        evidence = inspect_regression_behaviour(self.bundle)
        self.assertTrue(evidence['fixture'])
        self.assertFalse(evidence['production_art_acceptance'])
        self.assertEqual([[80, 170], [104, 170], [134, 170], [134, 170]], evidence['locomotion']['positions'])
        self.assertEqual([0, 0, 0, 0], [item['max_drift_pixels'] for item in evidence['locomotion']['planted_contacts']])
        self.assertEqual([[0, 0], [0, 12], [0, 0]], evidence['sit_stand']['body_offsets'])
        self.assertEqual([None, 'a', 'a', None], evidence['grasp_release']['owners'])
        self.assertEqual(['default', 'happy', 'default'], evidence['expression']['brow_drawings'])
        self.assertEqual({'gaze_offset': [1, 0], 'mouth': 'open', 'head_rotation': -1.25}, evidence['expression']['frame_21'])
        self.assertEqual([9, 1, 1, 9], evidence['full_frame_override']['character_layer_counts'])
        self.assertFalse(evidence['audio']['spoken_dialogue'])

    def test_each_authored_sequence_changes_actual_composited_rgba_pixels(self):
        from production_render import render_frame
        for shot, a, b in [('locomotion', 0, 30), ('sit-stand', 0, 24), ('reach-grasp-release', 0, 30),
                           ('facial-dialogue', 0, 21), ('full-frame-override', 0, 15)]:
            with self.subTest(shot=shot):
                first, _ = render_frame(self.bundle, shot, a)
                second, _ = render_frame(self.bundle, shot, b)
                try:
                    self.assertEqual(('RGBA', (320, 200)), (first.mode, first.size))
                    self.assertEqual(('RGBA', (320, 200)), (second.mode, second.size))
                    self.assertNotEqual(first.tobytes(), second.tobytes())
                finally:
                    first.close()
                    second.close()

    def test_planted_foot_check_catches_a_real_stance_compensation_error(self):
        from production_regression_demo import inspect_regression_behaviour
        clip = self.bundle['clips']['reg-walk@1.0.0']
        clip['tracks']['body']['left-leg']['offset']['keys'][1]['value'] = [-10, 0]
        with self.assertRaisesRegex(ValueError, 'planted foot slips'):
            inspect_regression_behaviour(self.bundle)

    def test_grasp_render_fails_when_the_hand_does_not_reach_the_owned_prop(self):
        from production_render import evaluate_frame
        clip = self.bundle['clips']['reg-grasp@1.0.0']
        clip['tracks']['body']['hand']['offset'] = track([20, 0])
        with self.assertRaisesRegex(ValueError, 'discontinuous ownership change'):
            evaluate_frame(self.bundle, 'reach-grasp-release', 24)

    def test_full_frame_override_replaces_only_character_layers_on_exact_boundaries(self):
        from production_render import evaluate_frame
        for frame, count in [(11, 9), (12, 1), (17, 1), (18, 1), (23, 1), (24, 9)]:
            state = evaluate_frame(self.bundle, 'full-frame-override', frame)
            layers = [layer for layer in state['layers'] if layer['track'] == 'a']
            with self.subTest(frame=frame):
                self.assertEqual(count, len(layers))
                self.assertEqual([160, 150], state['instances']['a']['position'])
                self.assertEqual(1.5, state['instances']['a']['relative_scale'])
                self.assertEqual(9, len(state['instances']['a']['components']))
                if count == 1:
                    self.assertTrue(layers[0]['image']['path'].endswith('full-pose-' + ('a' if frame < 18 else 'b') + '.png'))

    def test_offline_pcm_matches_cue_start_end_samples_and_exact_total_duration(self):
        import array
        import wave
        from production_render import mix_audio
        shot = self.bundle['shots']['facial-dialogue']
        path = self.root / 'mixed-fixture.wav'
        result = mix_audio(self.root, shot['audio'], path, 48, self.bundle['project']['render']['fps'], sample_rate=24000, channels=2)
        self.assertEqual((96000, 24000, 2, 0), (result['sample_count'], result['sample_rate'], result['channels'], result['clipped_samples']))
        self.assertEqual([(16000, 52000), (60000, 84000)], [(s['start_sample'], s['end_sample']) for s in result['sources']])
        with wave.open(str(path), 'rb') as stream:
            self.assertEqual((2, 2, 24000, 96000), (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getnframes()))
            samples = array.array('h', stream.readframes(stream.getnframes()))
        if sys.byteorder != 'little':
            samples.byteswap()
        for index, audible in [(0, False), (15999, False), (16000, True), (51999, True), (52000, False),
                                (60000, True), (83999, True), (84000, False), (95999, False)]:
            with self.subTest(sample=index):
                self.assertEqual(audible, bool(samples[index * 2]))
                self.assertEqual(samples[index * 2], samples[index * 2 + 1])


if __name__ == '__main__':
    unittest.main()
