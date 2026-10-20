"""State-library authoring contracts and real existing-profile compilation.

These tests generate metadata and labeled fixture shapes only. No test receipt
claims a production illustration or a semantic animation review.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from asset_contracts import MAX_SOURCE_PIXELS, check_resources, hash_object
from profile_spec import DEFAULT_PROFILE, load_profile, profile_hash
from state_catalog import (DEFAULT_LIBRARY, IDENTITY_REQUIREMENTS, StateLibrary,
                           compile_profile, compile_selection, load_library,
                           preview_states, validate_selection, validate_selection_manifest,
                           write_compilation)


def miniature_documents():
    """Small independent authoring fixture for malformed-input/graph tests."""
    states = []
    for name, meaning, requires, props, mode in [
        ('idle', 'Calm body breathing', [], [], 'loop'),
        ('happy', 'Open smile and lifted relaxed posture', [], [], 'once'),
        ('wing-stretch', 'Extend approved wings outward then fold them', ['wings'], [], 'once'),
        ('writing', 'Trace deliberate strokes with an approved pencil', ['hands'], ['pencil'], 'loop'),
        ('run-left', 'Leftward locomotion with alternating planted feet', ['legs'], [], 'loop'),
        ('run-right', 'Rightward locomotion with alternating planted feet', ['legs'], [], 'loop'),
    ]:
        direction = name.removeprefix('run-') if name.startswith('run-') else 'front'
        states.append({
            'id': name, 'name': name.replace('-', ' ').title(), 'category': 'neutral', 'family': 'body-language',
            'tags': ['character', name], 'aliases': ['joyful'] if name == 'happy' else [],
            'description': meaning, 'archetypes': ['any'],
            'anatomy': {'requires_all': requires, 'requires_any': [], 'excludes': [], 'fallback': 'idle'},
            'animation': {'id': name, 'frames': 3, 'durations': [120, 180, 240], 'purpose': meaning,
                          'motion': 'directional' if name.startswith('run-') else 'quiet',
                          'alignment': {'coordinate_policy': 'slot', 'scale_policy': 'shared', 'padding': 5},
                          'generation': {'skill': 'imagegen', 'requires_identity_reference': True,
                                         'instructions': meaning + ': anticipation, expression, and settled recovery.',
                                         'requirements': ['Preserve the canonical silhouette and anatomy.']},
                          'allowed_derivations': [], 'validation': {'min_motion': 0.0001},
                          'playback': {'mode': mode, 'interruptible': True}},
            'animation_recipe': 'three-phase',
            'poses': ['Neutral preparation', meaning, 'Settle with identity intact'],
            'expression': 'Use approved body features to communicate ' + meaning.lower() + '.',
            'direction': {'facing': direction, 'travel': direction if name.startswith('run-') else 'none',
                          'mirror_policy': 'explicit-approval-only', 'dependencies': []},
            'events': ['state:' + name], 'priority': 10, 'interrupt': 'higher', 'repeat': 'coalesce',
            'legal_transitions': ['idle'], 'completion': 'idle' if mode == 'once' else None, 'recovery': 'idle',
            'reduced_motion': {'mode': 'static', 'frame': 1, 'description': 'Hold the most legible ' + name + ' pose.'},
            'props': {'required': props, 'optional': []},
            'negative_constraints': ['No floating effects or invented limbs.'],
            'semantic_review': ['Action must match ' + meaning.lower() + '.'],
            'compatibility': {'codex': False, 'custom_profile': True},
            'examples': ['Select ' + name + ' for a bounded custom character profile.'],
        })
    states[0]['legal_transitions'] = [state['id'] for state in states]
    catalog = {'schema_version': 1, 'catalog_version': '1.0.0',
               'categories': [{'id': 'neutral', 'name': 'Neutral', 'description': 'Fixture family'}], 'states': states}
    packs = {'schema_version': 1, 'packs': [
        {'id': 'core', 'name': 'Core', 'description': 'Small fixture selection',
         'states': ['idle', 'happy'], 'includes': [], 'exclude': [], 'selection_only': False},
        {'id': 'creature', 'name': 'Creature', 'description': 'Winged fixture behaviors',
         'states': ['wing-stretch', 'happy'], 'includes': ['core'], 'exclude': [], 'selection_only': False},
        {'id': 'studio', 'name': 'Studio', 'description': 'A discovery superset needing a subset',
         'states': [state['id'] for state in states], 'includes': [], 'exclude': [], 'selection_only': True},
    ]}
    archetypes = {'schema_version': 1,
                  'capabilities': [{'id': name, 'name': name.title(), 'description': 'Approved ' + name}
                                   for name in ('body', 'wings', 'hands', 'legs', 'eyes')],
                  'archetypes': [
                      {'id': 'generic', 'name': 'Generic', 'description': 'Body only', 'capabilities': ['body']},
                      {'id': 'bird', 'name': 'Bird', 'description': 'Bird fixture', 'capabilities': ['body', 'wings', 'legs']},
                      {'id': 'humanoid', 'name': 'Humanoid', 'description': 'Human fixture', 'capabilities': ['body', 'hands', 'legs', 'eyes']},
                  ]}
    recipes = {'schema_version': 1, 'recipes': [{
        'id': 'greeting', 'name': 'Greeting', 'description': 'Idle then joy then recovery',
        'states': ['idle', 'happy'], 'initial': 'idle', 'cancel_state': 'idle',
        'steps': ['idle', 'happy', 'idle'], 'completion': {'happy': 'idle'},
        'events': {'greet': {'target': 'happy', 'from': ['idle'], 'priority': 10, 'interrupt': 'higher', 'restart': False}},
        'queue_limit': 4,
    }]}
    animation = {'schema_version': 1, 'recipes': [
        {'id': 'three-phase', 'name': 'Three phase', 'description': 'Preparation, expression, recovery',
         'frames': 3, 'durations': [120, 180, 240],
         'key_phases': ['Preparation', 'Expression', 'Recovery'], 'loop_seam': 'Match ending and beginning anchors.'},
        {'id': 'two-phase', 'name': 'Two phase', 'description': 'Expression and recovery',
         'frames': 2, 'durations': [300, 400],
         'key_phases': ['Expression', 'Recovery'], 'loop_seam': 'Quietly return to the first pose.'},
    ]}
    return catalog, packs, archetypes, recipes, animation


def miniature_library():
    return StateLibrary(*miniature_documents())


class CompilerContractTests(unittest.TestCase):
    def setUp(self):
        self.documents = miniature_documents()
        self.lib = StateLibrary(*self.documents)

    def compile(self, **kwargs):
        return compile_profile(library=self.lib, **kwargs)

    def test_selected_aliases_and_overlapping_packs_deduplicate_without_mutation(self):
        original = copy.deepcopy(self.lib.states)
        result = self.compile(states=['happy', 'joyful', 'happy'], packs=['core', 'core'])
        self.assertEqual(result['manifest']['selected_states'], ['happy', 'idle'])
        self.assertEqual(result['profile']['schema_version'], 1)
        self.assertEqual(result['profile']['states'][0]['playback']['completion'], 'idle')
        self.assertEqual(self.lib.states, original)
        self.assertTrue(result['manifest']['selection_reasons']['happy'])
        self.assertEqual(profile_hash(result['profile']), result['manifest']['profile_sha256'])

    def test_catalog_metadata_is_separate_and_prompts_use_the_complete_semantics(self):
        result = self.compile(states=['happy'])
        state = result['profile']['states'][0]
        self.assertNotIn('category', state)
        self.assertNotIn('anatomy', state)
        self.assertEqual(state['playback']['reduced_motion_frame'], 1)
        for expected in ('Open smile', 'Key poses', 'Expression and body language', 'Orientation', 'Reduced-motion pose'):
            self.assertIn(expected, state['generation']['instructions'])
        for requirement in IDENTITY_REQUIREMENTS:
            self.assertIn(requirement, state['generation']['requirements'])
        self.assertTrue(any('Semantic visual review' in text for text in state['generation']['requirements']))
        self.assertFalse(result['profile']['export']['codex_compatible'])
        self.assertTrue(result['profile']['validation']['require_provenance'])
        self.assertEqual(result['manifest']['artwork_status'], 'definitions-only')

    def test_incompatible_explicit_anatomy_fails_and_substitution_is_explicit(self):
        with self.assertRaisesRegex(ValueError, 'requires anatomy: wings'):
            self.compile(states=['wing-stretch'])
        with self.assertRaisesRegex(ValueError, 'requires anatomy: wings'):
            self.compile(states=['wing-stretch'], anatomy_policy='filter')
        result = self.compile(states=['wing-stretch'], anatomy_policy='substitute')
        self.assertEqual(result['manifest']['selected_states'], ['idle'])
        self.assertEqual(result['manifest']['substitutions'][0]['requested'], 'wing-stretch')
        self.assertEqual(result['manifest']['substitutions'][0]['selected'], 'idle')
        self.assertEqual(self.compile(states=['wing-stretch'], archetype='bird')['manifest']['selected_states'], ['wing-stretch', 'idle'])

    def test_filter_is_only_an_explicit_policy_and_preserves_omission_reasons(self):
        with self.assertRaisesRegex(ValueError, 'requires anatomy'):
            self.compile(packs=['creature'])
        result = self.compile(packs=['creature'], anatomy_policy='filter')
        self.assertEqual(result['manifest']['selected_states'], ['idle', 'happy'])
        self.assertEqual(result['manifest']['omitted'][0]['state'], 'wing-stretch')
        self.assertIn('wings', result['manifest']['omitted'][0]['reason'])

    def test_capability_override_is_exact_and_props_need_explicit_approval(self):
        with self.assertRaisesRegex(ValueError, 'pencil'):
            self.compile(states=['writing'], archetype='humanoid')
        result = self.compile(states=['writing'], archetype='humanoid', approved_props=['pencil'])
        self.assertEqual(result['manifest']['required_props'], ['pencil'])
        with self.assertRaisesRegex(ValueError, 'hands'):
            self.compile(states=['writing'], archetype='humanoid', capabilities=['body'], approved_props=['pencil'])
        with self.assertRaisesRegex(ValueError, 'unknown capabilities'):
            self.compile(states=['idle'], capabilities=['made-up-body-part'])

    def test_direction_generation_stays_separate_and_dependencies_are_bounded(self):
        result = self.compile(states=['run-left', 'run-right'], archetype='humanoid')
        self.assertEqual([state['allowed_derivations'] for state in result['profile']['states']], [[], [], []])
        self.assertIn('facing left; travel left', result['profile']['states'][0]['generation']['instructions'])
        self.assertIn('facing right; travel right', result['profile']['states'][1]['generation']['instructions'])
        self.documents[0]['states'][4]['direction']['dependencies'] = ['run-right']
        lib = StateLibrary(*self.documents)
        result = compile_profile(states=['run-left'], archetype='humanoid', library=lib)
        self.assertEqual(result['manifest']['selected_states'], ['run-left', 'idle', 'run-right'])
        with self.assertRaisesRegex(ValueError, 'exceeding max_states=2'):
            compile_profile(states=['run-left'], archetype='humanoid', library=lib, max_states=2)

    def test_global_state_limits_atlas_memory_and_source_limits_are_preserved(self):
        with self.assertRaisesRegex(ValueError, 'max_states above 32'):
            self.compile(states=['idle'], max_states=33)
        with self.assertRaisesRegex(ValueError, 'exceeding max_states=1'):
            self.compile(states=['happy'], max_states=1)
        with self.assertRaisesRegex(ValueError, 'frame count must fit'):
            self.compile(states=['idle'], columns=2)
        with self.assertRaisesRegex(ValueError, 'source pixel limit'):
            self.compile(states=['idle'], cell_width=1024, cell_height=1024)
        with self.assertRaisesRegex(ValueError, 'raster working set|64 million pixels'):
            self.compile(states=['idle'], columns=4096, cell_width=192, cell_height=208)
        result = self.compile(states=['idle'], max_states=64, allow_large=True)
        self.assertLessEqual(result['manifest']['estimates']['largest_source_strip_pixels'], MAX_SOURCE_PIXELS)
        self.assertEqual(check_resources(result['profile'])['total_frames'], result['manifest']['estimates']['frame_count'])

    def test_complete_studio_requires_subset_and_limit_does_not_trim_dependencies(self):
        with self.assertRaisesRegex(ValueError, 'selection-only packs'):
            self.compile(packs=['studio'])
        result = self.compile(packs=['studio'], states=['joyful'])
        self.assertEqual(result['manifest']['selected_states'], ['happy', 'idle'])
        limited = self.compile(packs=['studio'], limit=2)
        self.assertEqual(limited['manifest']['selected_states'], ['idle', 'happy'])
        self.assertEqual(len(limited['manifest']['omitted']), 4)
        self.assertTrue(all(item['reason'] == 'explicit selection limit' for item in limited['manifest']['omitted']))

    def test_legal_outgoing_transitions_compile_to_enforced_event_sources(self):
        result = self.compile(states=['happy', 'run-left'], archetype='humanoid')
        rules = result['profile']['playback']['events']
        self.assertEqual(rules['state:run-left']['from'], ['run-left', 'idle'])
        self.assertNotIn('happy', rules['state:run-left']['from'])
        self.assertEqual(set(rules['state:idle']['from']), {'happy', 'run-left', 'idle'})
        self.documents[0]['states'][0]['legal_transitions'].remove('happy')
        with self.assertRaisesRegex(ValueError, 'inaccessible states'):
            StateLibrary(*self.documents)

    def test_recipe_uses_only_explicit_event_graph_and_real_completion(self):
        result = self.compile(recipe='greeting')
        self.assertEqual(result['profile']['events'], {'greet': 'happy'})
        self.assertEqual(result['profile']['playback']['events']['greet']['from'], ['idle'])
        self.assertFalse(any(event.startswith('state:') for event in result['profile']['events']))
        happy = next(state for state in result['profile']['states'] if state['id'] == 'happy')
        self.assertEqual(happy['playback']['completion'], 'idle')
        self.assertEqual(result['profile']['playback']['queue_limit'], 4)
        with self.assertRaisesRegex(ValueError, 'complete event graph'):
            self.compile(recipe='greeting', states=['wing-stretch'], archetype='bird')

    def test_reduced_motion_profile_is_one_intentional_static_pose_per_state(self):
        result = self.compile(states=['happy'], reduced_motion=True)
        for state in result['profile']['states']:
            self.assertEqual((state['frames'], state['motion'], state['playback']['mode']), (1, 'static', 'hold'))
            self.assertEqual(state['validation']['min_motion'], 0)
            self.assertEqual(state['playback']['reduced_motion_frame'], 0)
            self.assertNotIn('completion', state['playback'])
            self.assertIn('exactly one static expressive pose', state['generation']['instructions'])
        self.assertEqual(result['manifest']['estimates']['frame_count'], 2)
        recipe = self.compile(recipe='greeting', reduced_motion=True)['profile']
        self.assertEqual(recipe['events'], {'greet': 'happy', 'next:happy': 'idle'})
        self.assertEqual(recipe['playback']['events']['next:happy']['from'], ['happy'])

    def test_reusable_animation_recipe_is_explicit_and_updates_real_timing(self):
        result = self.compile(states=['happy'], animation_recipes={'joyful': 'two-phase'})
        state = result['profile']['states'][0]
        self.assertEqual((state['frames'], state['durations']), (2, [300, 400]))
        self.assertIn('Selected animation recipe two-phase', state['generation']['instructions'])
        with self.assertRaisesRegex(ValueError, 'unselected state'):
            self.compile(states=['idle'], animation_recipes={'happy': 'two-phase'})
        with self.assertRaisesRegex(ValueError, 'conflicting animation recipe aliases'):
            self.compile(states=['happy'], animation_recipes={'happy': 'two-phase', 'joyful': 'three-phase'})

    def test_serialization_manifest_hash_and_reproducible_selection(self):
        first = self.compile(states=['joyful'], packs=['core'], cell_width=96, cell_height=96)
        second = self.compile(states=['joyful'], packs=['core'], cell_width=96, cell_height=96)
        self.assertEqual(first, second)
        self.assertEqual(compile_selection(first['manifest']['selection'], library=self.lib), first)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'character.json'
            paths = write_compilation(first, path)
            self.assertEqual(paths['selection_manifest'], str(path.with_suffix('.selection.json')))
            self.assertEqual(load_profile(path), first['profile'])
            self.assertEqual(json.loads(path.with_suffix('.selection.json').read_text()), first['manifest'])
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, 'already exists'):
                write_compilation(second, path)
            self.assertEqual(path.read_bytes(), before)

    def test_manifest_validates_binding_anatomy_and_cannot_claim_artwork(self):
        result = self.compile(states=['happy'])
        profile, manifest = result['profile'], result['manifest']
        corrupted = copy.deepcopy(manifest); corrupted['artwork_status'] = 'production'
        with self.assertRaisesRegex(ValueError, 'manifest hash mismatch'):
            validate_selection_manifest(corrupted, profile)
        corrupted['manifest_sha256'] = hash_object({key: value for key, value in corrupted.items() if key != 'manifest_sha256'})
        with self.assertRaisesRegex(ValueError, 'cannot claim production'):
            validate_selection_manifest(corrupted, profile)
        different = copy.deepcopy(profile); different['states'][0]['durations'][0] += 10
        with self.assertRaisesRegex(ValueError, 'profile hash mismatch'):
            validate_selection_manifest(manifest, different)
        corrupt = copy.deepcopy(manifest); corrupt['state_requirements']['happy']['requires_all'] = ['wings']
        corrupt['manifest_sha256'] = hash_object({key: value for key, value in corrupt.items() if key != 'manifest_sha256'})
        with self.assertRaisesRegex(ValueError, 'anatomy is incompatible'):
            validate_selection_manifest(corrupt, profile)

    def test_search_by_alias_category_action_and_anatomy_never_claims_codex(self):
        self.assertEqual([record['id'] for record in self.lib.search('joyful')], ['happy'])
        self.assertEqual([record['id'] for record in self.lib.search('locomotion', archetype='humanoid')], ['run-left', 'run-right'])
        self.assertNotIn('wing-stretch', [record['id'] for record in self.lib.search(archetype='generic')])
        self.assertIn('wing-stretch', [record['id'] for record in self.lib.search(archetype='bird')])
        self.assertEqual(self.lib.search(compatibility='codex'), [])
        with self.assertRaisesRegex(ValueError, 'unknown category'):
            self.lib.search(category='unrecognized')

    def test_preview_without_artwork_reports_ungenerated_and_no_paths(self):
        result = preview_states(['joyful', 'idle'], library=self.lib)
        self.assertEqual([state['id'] for state in result['states']], ['happy', 'idle'])
        self.assertTrue(all(state['status'] == 'not-generated' and not state['frames'] and not state['production_artwork'] for state in result['states']))
        self.assertIsNone(result['preview_html'])
        self.assertFalse(result['artwork_generated'])

    def test_malformed_saved_selection_rejects_unsupported_and_unsafe_values(self):
        for value in ({'schema_version': True}, {'schema_version': 1, 'style': 'plush'},
                      {'schema_version': 1, 'states': ['../escape']},
                      {'schema_version': 1, 'layout': {'scale': 1}},
                      {'schema_version': 1, 'max_states': 0},
                      {'schema_version': 1, 'approved_props': 'pencil'},
                      {'schema_version': 1, 'animation_recipes': {'happy': []}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_selection(value)

    def test_catalog_malformed_definitions_aliases_references_and_thresholds_fail(self):
        mutations = [
            lambda docs: docs[0].update(schema_version=True),
            lambda docs: docs[0]['states'].append(copy.deepcopy(docs[0]['states'][0])),
            lambda docs: docs[0]['states'][1].update(id='CON'),
            lambda docs: docs[0]['states'][1].update(category=[]),
            lambda docs: docs[0]['states'][1].update(extra=True),
            lambda docs: docs[0]['states'][1].update(aliases=['idle']),
            lambda docs: docs[0]['states'][2].update(aliases=['joyful']),
            lambda docs: docs[0]['states'][1].update(animation_recipe=[]),
            lambda docs: docs[0]['states'][1]['animation'].update(frames=65),
            lambda docs: docs[0]['states'][1]['animation'].update(durations=[0, 180, 240]),
            lambda docs: docs[0]['states'][1]['animation']['validation'].update(min_motion=-1),
            lambda docs: docs[0]['states'][1]['animation']['validation'].update(min_motion=float('nan')),
            lambda docs: docs[0]['states'][1]['animation']['generation'].update(requires_identity_reference=False),
            lambda docs: docs[0]['states'][1]['anatomy'].update(requires_all=['unapproved-limb']),
            lambda docs: docs[0]['states'][1]['anatomy'].update(requires_all=['wings'], excludes=['wings']),
            lambda docs: docs[0]['states'][1]['direction'].update(mirror_policy='automatic'),
            lambda docs: docs[0]['states'][1]['direction'].update(dependencies=['missing']),
            lambda docs: docs[0]['states'][1].update(legal_transitions=['missing']),
            lambda docs: docs[0]['states'][1].update(completion='happy'),
            lambda docs: docs[0]['states'][1].update(events=['state:idle']),
            lambda docs: docs[0]['states'][1]['compatibility'].update(codex=0, custom_profile=1),
            lambda docs: docs[0]['states'][1]['reduced_motion'].update(frame=3),
        ]
        for mutate in mutations:
            docs = miniature_documents(); mutate(docs)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                StateLibrary(*docs)

    def test_pack_and_recipe_missing_dependencies_cycles_and_inaccessible_recovery_fail(self):
        mutations = [
            lambda docs: docs[1]['packs'][0].update(states=['missing']),
            lambda docs: docs[1]['packs'][0].update(includes=['missing']),
            lambda docs: docs[1]['packs'][0].update(includes=['creature']),
            lambda docs: docs[1]['packs'][0].update(exclude=['idle', 'happy']),
            lambda docs: docs[3]['recipes'][0].update(completion={'happy': 'missing'}),
            lambda docs: docs[3]['recipes'][0].update(completion={'happy': 'idle', 'idle': 'happy'}),
            lambda docs: docs[3]['recipes'][0]['events']['greet'].update(target='missing'),
            lambda docs: docs[3]['recipes'][0]['events']['greet'].update(**{'from': ['happy']}),
            lambda docs: docs[3]['recipes'][0].update(completion={}),
            lambda docs: docs[3]['recipes'][0].update(states=['idle', 'happy', 'writing']),
        ]
        for mutate in mutations:
            docs = miniature_documents(); mutate(docs)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                StateLibrary(*docs)

    def test_custom_pack_files_are_data_only_conflicts_rejected_and_order_stable(self):
        names = ('catalog.json', 'packs.json', 'archetypes.json', 'recipes.json', 'animation-recipes.json')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, doc in zip(names, miniature_documents()):
                (root / name).write_text(json.dumps(doc))
            custom = root / 'custom.json'
            custom.write_text(json.dumps({'schema_version': 1, 'packs': [{
                'id': 'my-core', 'name': 'My Core', 'description': 'Narrow reused pack',
                'states': ['joyful'], 'includes': ['core'], 'exclude': ['idle'], 'selection_only': False}]}))
            lib = load_library(root, pack_files=[custom, custom])
            self.assertEqual(lib.expand_pack('my-core'), ['happy'])
            self.assertEqual(compile_profile(packs=['my-core'], library=lib)['manifest']['selected_states'], ['happy', 'idle'])
            value = json.loads(custom.read_text()); value['packs'][0]['id'] = 'core'
            custom.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'conflicts with existing definition'):
                load_library(root, pack_files=[custom])
            custom.write_text('{"schema_version":1,"schema_version":1,"packs":[]}')
            with self.assertRaisesRegex(ValueError, 'duplicate JSON object key'):
                load_library(root, pack_files=[custom])

    def test_additive_custom_state_needs_explicit_entry_and_cannot_replace_builtin_semantics(self):
        documents = miniature_documents()
        new_state = copy.deepcopy(documents[0]['states'][1])
        new_state.update(id='custom-bow', name='Custom bow', aliases=[], events=['state:custom-bow'])
        new_state['animation']['id'] = 'custom-bow'
        extension = {'schema_version': 1, 'catalog_version': '1.0.0', 'categories': [],
                     'states': [new_state], 'entry_transitions': {'idle': ['custom-bow']}}
        names = ('catalog.json', 'packs.json', 'archetypes.json', 'recipes.json', 'animation-recipes.json')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, doc in zip(names, documents): (root / name).write_text(json.dumps(doc))
            path = root / 'extension.json'; path.write_text(json.dumps(extension))
            original = load_library(root)
            extended = load_library(root, catalog_files=[path, path])
            result = compile_profile(states=['custom-bow'], library=extended)
            self.assertEqual(result['manifest']['selected_states'], ['custom-bow', 'idle'])
            self.assertIn('idle', result['profile']['playback']['events']['state:custom-bow']['from'])
            self.assertNotIn('custom-bow', original.states['idle']['legal_transitions'])
            self.assertNotEqual(original.sha256, extended.sha256)
            self.assertTrue(any(record['name'] == path.name for record in result['manifest']['source_files']))
            mutations = [
                lambda value: value.pop('entry_transitions'),
                lambda value: value.update(entry_transitions=[]),
                lambda value: value.update(entry_transitions={'missing': ['custom-bow']}),
                lambda value: value.update(entry_transitions={'idle': ['missing']}),
                lambda value: value.update(entry_transitions={'idle': ['happy']}),
                lambda value: value.update(entry_transitions={'idle': ['custom-bow', 'custom-bow']}),
                lambda value: value['states'][0]['animation'].update(purpose=''),
                lambda value: value['states'].append({**copy.deepcopy(documents[0]['states'][0]), 'name': 'Silently replaced idle'}),
            ]
            for mutate in mutations:
                value = copy.deepcopy(extension); mutate(value)
                path.write_text(json.dumps(value))
                with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                    load_library(root, catalog_files=[path])


class PackagedCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = load_library()

    def test_all_packaged_canonical_states_compile_individually_through_real_contract(self):
        self.assertGreaterEqual(len(self.lib.states), 200)
        self.assertGreaterEqual(len(self.lib.categories), 16)
        for name, definition in self.lib.states.items():
            with self.subTest(state=name):
                anatomy = definition['anatomy']
                capabilities = set(anatomy['requires_all'])
                if 'body' not in anatomy['excludes']:
                    capabilities.add('body')
                if anatomy['requires_any'] and not capabilities.intersection(anatomy['requires_any']):
                    capabilities.add(next(value for value in anatomy['requires_any'] if value not in anatomy['excludes']))
                capabilities = sorted(capabilities)
                props = list(definition['props']['required'])
                archetype = definition['archetypes'][0] if definition['archetypes'] != ['any'] else 'generic'
                result = compile_profile(states=[name], capabilities=capabilities, archetype=archetype,
                                         approved_props=props, library=self.lib)
                self.assertIn(name, result['manifest']['selected_states'])
                self.assertLessEqual(len(result['profile']['states']), 32)
                self.assertEqual(load_profile(result['profile']), result['profile'])
                self.assertTrue(all(state['generation']['instructions'] for state in result['profile']['states']))
                self.assertFalse(result['profile']['export']['codex_compatible'])
                self.assertEqual(result['manifest']['estimates']['model_calls_baseline'], len(result['profile']['states']) + 1)
                static = compile_profile(states=[name], capabilities=capabilities, archetype=archetype,
                                         approved_props=props, library=self.lib, reduced_motion=True)
                self.assertTrue(all(state['frames'] == 1 and state['playback']['mode'] == 'hold'
                                    for state in static['profile']['states']))

    def test_every_pack_resolves_and_bounded_subset_compiles(self):
        self.assertGreaterEqual(len(self.lib.packs), 16)
        props = sorted({prop for state in self.lib.states.values() for prop in state['props']['required']})
        for name in self.lib.packs:
            with self.subTest(pack=name):
                members = self.lib.expand_pack(name)
                self.assertEqual(len(members), len(set(members)))
                self.assertTrue(set(members) <= set(self.lib.states))
                result = compile_profile(packs=[name], limit=16, capabilities=list(self.lib.capabilities),
                                         approved_props=props, anatomy_policy='filter', library=self.lib)
                self.assertTrue(result['profile']['states'])
                self.assertLessEqual(len(result['profile']['states']), 32)

    def test_every_transition_recipe_compiles_and_enforces_only_its_own_events(self):
        props = sorted({prop for state in self.lib.states.values() for prop in state['props']['required']})
        for name, recipe in self.lib.recipes.items():
            with self.subTest(recipe=name):
                result = compile_profile(recipe=name, capabilities=list(self.lib.capabilities),
                                         approved_props=props, library=self.lib)
                profile = result['profile']
                self.assertEqual(set(profile['events']), set(recipe['events']))
                self.assertEqual(profile['playback']['initial'], recipe['initial'])
                self.assertEqual(profile['playback']['cancel_state'], recipe['cancel_state'])
                states = {state['id']: state for state in profile['states']}
                for source, target in recipe['completion'].items():
                    self.assertEqual(states[source]['playback']['mode'], 'once')
                    self.assertEqual(states[source]['playback']['completion'], target)
                static = compile_profile(recipe=name, capabilities=list(self.lib.capabilities),
                                         approved_props=props, library=self.lib, reduced_motion=True)['profile']
                for source, target in recipe['completion'].items():
                    self.assertEqual(static['events']['next:' + source], target)

    def test_default_codex_bytes_and_normalized_contract_are_unchanged_by_compilation(self):
        raw, before = DEFAULT_PROFILE.read_bytes(), profile_hash(load_profile())
        compile_profile(states=['idle'], library=self.lib)
        self.assertEqual(DEFAULT_PROFILE.read_bytes(), raw)
        self.assertEqual(profile_hash(load_profile()), before)
        default = load_profile()
        self.assertEqual((default['layout']['columns'], default['layout']['rows'], default['layout']['cell_width'], default['layout']['cell_height']), (8, 9, 192, 208))
        self.assertEqual([state['id'] for state in default['states']], ['idle', 'running-right', 'running-left', 'waving', 'jumping', 'failed', 'waiting', 'running', 'review'])
        self.assertEqual([state['durations'] for state in default['states']], [
            [280, 110, 110, 140, 140, 320], [120] * 7 + [220], [120] * 7 + [220],
            [140, 140, 140, 280], [140] * 4 + [280], [140] * 7 + [240],
            [150] * 5 + [260], [120] * 5 + [220], [150] * 5 + [280]])

    def test_task_running_is_semantically_distinct_from_directional_locomotion(self):
        running = self.lib.states[self.lib.resolve('running')]
        left = self.lib.states[self.lib.resolve('running-left')]
        right = self.lib.states[self.lib.resolve('running-right')]
        self.assertNotEqual(running['id'], left['id'])
        self.assertNotEqual(running['id'], right['id'])
        self.assertEqual(running['direction']['travel'], 'none')
        self.assertEqual(left['direction']['travel'], 'left')
        self.assertEqual(right['direction']['travel'], 'right')

    def test_saved_worked_selections_compile_into_the_actual_json_schema(self):
        import jsonschema
        schema = json.loads((ROOT / 'profiles/profile.schema.json').read_text())
        validator = jsonschema.validators.validator_for(schema)(schema)
        paths = sorted((ROOT / 'examples/state-selections').glob('*.json'))
        self.assertGreaterEqual(len(paths), 6)
        for path in paths:
            with self.subTest(selection=path.name):
                selection = json.loads(path.read_text())
                result = compile_selection(selection, library=self.lib)
                validator.validate(result['profile'])
                self.assertEqual(compile_selection(result['manifest']['selection'], library=self.lib), result)
                if path.name == 'expressive-cat.json':
                    self.assertEqual(len(result['profile']['states']), 25)
                    self.assertFalse(result['manifest']['required_props'])
                if path.name == 'reference-studio.json':
                    self.assertLessEqual(len(result['profile']['states']), 32)


if __name__ == '__main__':
    unittest.main()
