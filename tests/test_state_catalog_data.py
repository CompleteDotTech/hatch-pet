"""Semantic and authoring quality gates for the shipped state-library data."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from state_catalog import load_library


class StateCatalogDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = load_library()
        cls.raw = json.loads((ROOT / 'state-library' / 'catalog.json').read_text())

    def test_all_requested_families_have_substantial_semantic_coverage(self):
        expected = {
            'neutral-idle', 'positive-emotions', 'difficult-emotions', 'cognition',
            'locomotion', 'social-gestures', 'pet-daily-life', 'agent-workflows',
            'activities-hobbies', 'game-rpg', 'streaming-communication',
            'environmental-reactions', 'narrative-cinematic',
            'transitions-microexpressions', 'lifecycle-progression', 'accessibility',
        }
        self.assertEqual(set(self.library.categories), expected)
        self.assertGreaterEqual(len(self.library.states), 200)
        for category in expected:
            with self.subTest(category=category):
                self.assertGreaterEqual(sum(s['category'] == category for s in self.library.states.values()), 10)

    def test_each_animated_frame_has_a_distinct_deliberate_pose(self):
        descriptions, instructions, sequences = set(), set(), set()
        for state in self.library.states.values():
            with self.subTest(state=state['id']):
                animation = state['animation']
                self.assertEqual(len(state['poses']), animation['frames'])
                self.assertEqual(len(set(state['poses'])), animation['frames'])
                self.assertNotIn(state['description'], descriptions)
                self.assertNotIn(animation['generation']['instructions'], instructions)
                self.assertNotIn(tuple(state['poses']), sequences)
                descriptions.add(state['description'])
                instructions.add(animation['generation']['instructions'])
                sequences.add(tuple(state['poses']))
                self.assertTrue(all(len(pose.split()) >= 3 for pose in state['poses']))
                timing = ', '.join(map(str, animation['durations']))
                self.assertIn('Timing in milliseconds: ' + timing + '.', animation['generation']['instructions'])

    def test_no_generated_prose_has_double_periods_or_self_idle_comparison(self):
        for state in self.library.states.values():
            with self.subTest(state=state['id']):
                self.assertNotIn('..', state['animation']['generation']['instructions'])
                self.assertTrue(all('..' not in item for item in state['semantic_review']))
        idle_review = ' '.join(self.library.states['idle']['semantic_review'])
        self.assertNotIn('differs from ordinary idle', idle_review)
        self.assertNotIn('distinct from ordinary idle', idle_review)

    def test_two_blinks_have_separate_closure_frames(self):
        state = self.library.states['double-blinking']
        self.assertEqual(state['animation']['frames'], 5)
        self.assertIn('closed', state['poses'][1])
        self.assertIn('reopen', state['poses'][2])
        self.assertIn('closed', state['poses'][3])
        self.assertEqual(state['animation']['playback']['mode'], 'once')

    def test_true_static_states_have_one_frame_and_no_fake_motion_requirement(self):
        static = [s for s in self.library.states.values() if s['animation']['motion'] == 'static']
        self.assertGreaterEqual(len(static), 5)
        for state in static:
            with self.subTest(state=state['id']):
                self.assertEqual(state['animation']['frames'], 1)
                self.assertEqual(state['animation']['playback']['mode'], 'hold')
                self.assertEqual(state['animation']['validation']['min_motion'], 0)
                self.assertIn('intentionally static', ' '.join(state['animation']['generation']['requirements']))
                self.assertEqual(state['reduced_motion']['frame'], 0)

    def test_expression_static_alternatives_retain_the_meaningful_apex(self):
        for name in ('happy', 'positive-surprise', 'angry', 'afraid', 'successful', 'failed', 'warning', 'nonverbal-confirmation'):
            with self.subTest(state=name):
                state = self.library.states[name]
                self.assertEqual(state['reduced_motion']['frame'], 2)
                self.assertIn(state['poses'][2], state['reduced_motion']['description'])

    def test_direction_is_independent_and_task_running_cannot_be_locomotion(self):
        running = self.library.states['running']
        self.assertEqual(running['direction']['travel'], 'none')
        self.assertEqual(running['animation']['motion'], 'gesture')
        self.assertIn('never foot-running', running['animation']['generation']['instructions'])
        for suffix in ('left', 'right'):
            state = self.library.states['running-' + suffix]
            self.assertEqual(state['direction']['travel'], suffix)
            self.assertEqual(state['direction']['facing'], suffix)
            self.assertEqual(state['animation']['allowed_derivations'], [])
            self.assertIn('independently', ' '.join(state['animation']['generation']['requirements']))
        self.assertTrue(all(s['compatibility'] == {'codex': False, 'custom_profile': True} for s in self.library.states.values()))

    def test_synonyms_resolve_without_duplicate_animation_states(self):
        aliases = {
            'joyful': 'happy', 'cheerful': 'happy', 'irritated': 'annoyed',
            'frightened': 'afraid', 'reviewing': 'review', 'working': 'running',
            'processing': 'running', 'wave': 'waving', 'blink': 'blinking',
            'level-up': 'leveling-up', 'voice-activity': 'speaking',
        }
        for alias, canonical in aliases.items():
            with self.subTest(alias=alias):
                self.assertEqual(self.library.resolve(alias), canonical)
                self.assertNotIn(alias, self.library.states)

    def test_anatomy_specific_actions_cannot_add_features_to_generic_body(self):
        for name, capability in {
            'clapping': 'hands', 'tail-wagging': 'tail', 'ear-twitching': 'ears',
            'flying': 'wings', 'speaking': 'mouth', 'blinking': 'eyes',
            'fin-fanning': 'fins', 'antenna-probing': 'antennae',
            'tentacle-waving': 'tentacles', 'shell-retreating': 'shell',
        }.items():
            with self.subTest(state=name):
                self.assertIn(capability, self.library.states[name]['anatomy']['requires_all'])
                self.assertTrue(self.library.incompatibilities(name, 'generic'))
        self.assertNotIn('hands', self.library.character_capabilities('cat'))
        self.assertNotIn('wings', self.library.character_capabilities('generic'))
        self.assertFalse(self.library.incompatibilities('paw-grooming', 'cat'))

    def test_prop_and_appearance_dependencies_remain_explicit(self):
        for name, token in {
            'typing': 'keyboard', 'eating': 'food', 'painting': 'paintbrush',
            'hatch': 'hatch-enclosure', 'evolve': 'approved-evolved-variant',
            'transform': 'approved-transformed-variant',
        }.items():
            with self.subTest(state=name):
                self.assertIn(token, self.library.states[name]['props']['required'])
                self.assertTrue(self.library.incompatibilities(name, 'humanoid'))
                self.assertIn(token, ' '.join(self.library.states[name]['animation']['generation']['requirements']))

    def test_complete_studio_is_selection_only_and_covers_every_definition(self):
        studio = self.library.packs['complete-character-studio']
        self.assertTrue(studio['selection_only'])
        self.assertEqual(set(self.library.expand_pack('complete-character-studio')), set(self.library.states))
        self.assertEqual(len(self.library.packs), 16)

    def test_machine_schema_reuses_runtime_state_contract_and_extension_entry_edges(self):
        schema = json.loads((ROOT / 'state-library' / 'schema.json').read_text())
        self.assertFalse(schema['$defs']['state']['additionalProperties'])
        self.assertEqual(schema['$defs']['state']['properties']['animation']['$ref'],
                         '../profiles/profile.schema.json#/properties/states/items')
        self.assertIn('entry_transitions', schema['$defs']['catalog_extension']['properties'])
        self.assertEqual(set(schema['$defs']['state']['required']), set(self.raw['states'][0]))

    def test_documented_index_contains_each_canonical_id_once(self):
        index = (ROOT / 'state-library' / 'CATALOG.md').read_text()
        entries = re.findall(r'^\| `([a-z0-9-]+)` \|', index, flags=re.MULTILINE)
        self.assertEqual(len(entries), len(set(entries)))
        self.assertEqual(set(entries), set(self.library.states))


if __name__ == '__main__':
    unittest.main()
