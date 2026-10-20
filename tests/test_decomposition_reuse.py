"""Measured identity and reverse-to-forward reuse, without any inference service."""
import copy
import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from decomposition_reuse import derive_identity, operation_contract, _reuse_profile, prepare_from_decomposition
from decomposition_fixtures import make_fixture, FIXTURE_ORIGIN
from character_decomposition import create_decomposition, load_decomposition
from fixture_workflow import hatch, small_profile, record_fixture_review
from source_interface import import_source
from asset_contracts import sha
from portable_runs import archive_run, restore_run
import style_registry


class DecompositionForwardReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hatch-decomposition-forward-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.fixture = make_fixture(self.home / 'art', 'pixel')
        self.decomposition = self.home / 'decomposition'
        self.manifest = create_decomposition(self.fixture.source, self.decomposition,
                                            annotations=self.fixture.annotation, origin=FIXTURE_ORIGIN,
                                            fixture=True, pixel_art=True)

    def test_reuse_imports_observed_base_and_binds_selected_reference_provenance(self):
        forward = self.home / 'forward'
        result = prepare_from_decomposition(self.decomposition, forward,
                                            component_ids=['eyes', 'badge'], operation='wave')
        data = hatch.manifest(forward)
        request = hatch.read(forward / 'pet_request.json')
        base = hatch.job_for(data, 'base')
        self.assertEqual(base['source_origin'], 'import')
        self.assertNotIn('generation_receipt', base)
        self.assertNotIn('model_call', base)
        self.assertTrue(data['fixture_mode'])
        self.assertTrue(result['base_review_required'])
        self.assertFalse(result['new_artwork_produced'])
        self.assertFalse(result['codex_conversion_requested'])
        self.assertEqual(request['decomposition']['source_sha256'], sha(self.fixture.source))
        self.assertEqual(request['decomposition']['semantic_status'], 'pending')
        self.assertEqual(request['references'][1]['decomposition_component']['component_id'], 'eyes')
        self.assertEqual(request['references'][2]['decomposition_component']['component_id'], 'badge')
        self.assertEqual(request['references'][1]['role'], 'detail')
        self.assertEqual(request['decomposition'], base['import_receipt']['decomposition'])
        snapshot = forward / request['decomposition']['snapshot_path']
        self.assertEqual((snapshot / 'decomposition.json').read_bytes(), (self.decomposition / 'decomposition.json').read_bytes())
        self.assertEqual((snapshot / 'source/original.png').read_bytes(), self.fixture.source.read_bytes())
        with Image.open(forward / 'references/canonical-base.png') as canonical, Image.open(self.decomposition / 'foreground.png') as observed:
            self.assertEqual(canonical.convert('RGBA').tobytes(), observed.convert('RGBA').tobytes())
        with self.assertRaisesRegex(ValueError, 'base.review|base review|base-review'):
            hatch.claim(forward, data, 'wave')
        hatch.record_base_review(forward, data, 'Synthetic imported source inspected; no production claim.', True)
        handoff = hatch.claim(forward, data, 'wave')
        self.assertEqual(len(handoff['input_images']), 5)
        self.assertIn('eyes', handoff['input_images'][1]['note'])
        self.assertEqual(handoff['identity'], request['identity'])
        self.assertIn('required provenance-tracked references', Path(handoff['prompt']).read_text(encoding='utf-8'))

    def test_targeted_changes_use_edit_target_roles_and_preserve_other_components(self):
        forward = self.home / 'forward'
        result = prepare_from_decomposition(self.decomposition, forward, component_ids=['badge'],
                                            operation='recolor', operation_note='Change the badge to #FF0000.')
        request = hatch.read(forward / 'pet_request.json')
        self.assertEqual(request['references'][1]['role'], 'edit-target')
        self.assertFalse(result['operation']['requires_new_artwork'])
        prompt = (forward / 'prompts/rows/recolor.md').read_text(encoding='utf-8')
        self.assertIn('Only component IDs badge', prompt)
        self.assertIn('#FF0000', prompt)
        self.assertIn('Preserve', prompt)
        self.assertFalse(result['new_artwork_produced'])

    def test_catalog_guidance_preserves_imported_style_and_frozen_forward_provenance(self):
        """A different requested medium cannot relabel or restyle imported pixels."""
        forward = self.home / 'style-forward'
        original_manifest = (self.decomposition / 'decomposition.json').read_bytes()
        prepare_from_decomposition(self.decomposition, forward,
            argparse.Namespace(style_preset='watercolor', style_modifier=['cozy'],
                style_notes='Keep the supplied robot artwork and its stepped edges unchanged.'),
            component_ids=['eyes'], operation='wave')
        request = hatch.read(forward / 'pet_request.json')
        snapshot = style_registry.validate_snapshot(request['resolved_style'])
        data = hatch.manifest(forward)
        self.assertEqual(snapshot['resolved_id'], 'watercolor')
        self.assertEqual(request['style_modifiers'], ['cozy'])
        self.assertEqual(data['style_sha256'], snapshot['sha256'])
        self.assertEqual(request['style_contract'], snapshot['contract'])
        settings = hatch.read(forward / 'extraction-settings.json')
        self.assertEqual(settings['canonical_source_origin'], 'import')
        self.assertEqual(hatch.load_profile(forward / 'profile.json')['states'][0]['alignment']['resampling'], 'nearest')
        self.assertTrue(any('resampling differs' in warning for warning in settings['style_warnings']))
        with Image.open(forward / 'references/canonical-base.png') as canonical, Image.open(self.decomposition / 'foreground.png') as observed:
            self.assertEqual(canonical.convert('RGBA').tobytes(), observed.convert('RGBA').tobytes())
        prompt = (forward / 'prompts/rows/wave.md').read_text(encoding='utf-8')
        self.assertIn('The canonical base is imported artwork.', prompt)
        self.assertIn('does not authorize restyling this imported base', prompt)
        self.assertIn(snapshot['contract'], prompt)
        self.assertIn('Explicit profile alignment settings take precedence', prompt)
        original_request = (forward / 'pet_request.json').read_bytes()
        hatch.record_base_review(forward, data,
            'Synthetic pixel artwork import inspected; catalog guidance does not relabel its source.', True)
        with patch.object(style_registry, '_installed_catalog',
                          side_effect=AssertionError('Imported saved runs must use their frozen style snapshot.')):
            handoff = hatch.claim(forward, data, 'wave')
            self.assertEqual(handoff['resolved_style'], snapshot)
            self.assertEqual(handoff['input_images'][1]['role'], 'detail')
            self.assertIn('eyes', handoff['input_images'][1]['note'])
            hatch.fail(forward, data, 'wave', handoff['token'],
                       'Synthetic handoff verification only; no model call or new artwork.')
            archive_run(forward, data, self.home / 'style-forward.zip')
            restored = self.home / 'restored-style-forward'
            restore_run(self.home / 'style-forward.zip', restored)
            restored_data = hatch.manifest(restored)
            self.assertEqual((restored / 'pet_request.json').read_bytes(), original_request)
            self.assertEqual(restored_data['style_sha256'], snapshot['sha256'])
            style_origin = hatch.style_provenance(restored, restored_data)
            self.assertEqual(style_origin['resolved_style'], snapshot)
            self.assertEqual(style_origin['source_origins']['base'], 'import')
            self.assertEqual(hatch.job_for(restored_data, 'base')['import_receipt']['decomposition'], request['decomposition'])
            self.assertEqual((restored / 'references/decomposition/decomposition.json').read_bytes(), original_manifest)
        self.assertEqual((self.decomposition / 'decomposition.json').read_bytes(), original_manifest)

    def test_compiled_state_selection_survives_decomposition_reuse_and_retry(self):
        from state_catalog import compile_profile
        from state_selection import prepared_selection

        compiled = compile_profile(states=['idle', 'waving'], archetype='humanoid',
                                   cell_width=96, cell_height=96)
        profile = self.home / 'selected-profile.json'
        selection = self.home / 'selected-states.json'
        hatch.atomic(profile, compiled['profile'])
        hatch.atomic(selection, compiled['manifest'])
        forward = self.home / 'selected-forward'
        prepare_from_decomposition(self.decomposition, forward,
            argparse.Namespace(profile=str(profile), state_selection=str(selection)),
            component_ids=['eyes'])
        data = hatch.manifest(forward)
        request = hatch.read(forward / 'pet_request.json')
        self.assertEqual(prepared_selection(forward), compiled['manifest'])
        self.assertEqual([job['id'] for job in data['jobs']], ['base', 'idle', 'waving'])
        self.assertEqual(hatch.job_for(data, 'base')['source_origin'], 'import')
        self.assertEqual(request['references'][1]['decomposition_component']['component_id'], 'eyes')
        hatch.record_base_review(forward, data, 'Synthetic imported character inspected.', True)
        first = hatch.claim(forward, data, 'waving')
        hatch.fail(forward, data, 'waving', first['token'], 'Synthetic retry; no model call.')
        second = hatch.claim(forward, data, 'waving')
        self.assertNotEqual(first['token'], second['token'])
        self.assertEqual(first['input_images'], second['input_images'])
        self.assertEqual(prepared_selection(forward), compiled['manifest'])
        self.assertEqual(second['identity'], request['identity'])
        self.assertIn('eyes', second['input_images'][1]['note'])

    def test_unknown_references_or_required_approval_leave_no_partial_forward_run(self):
        for selected, args in ((['not-a-component'], None), (['eyes'], argparse.Namespace(require_approved=True))):
            with self.subTest(selected=selected, args=args):
                with self.assertRaises(ValueError):
                    prepare_from_decomposition(self.decomposition, self.home / 'unwritten', args,
                                               component_ids=selected)
                self.assertFalse((self.home / 'unwritten').exists())

    def test_explicit_codex_profile_retains_the_existing_fixed_contract(self):
        profile_path = Path(__file__).resolve().parents[1] / 'profiles/codex-v1.json'
        result = prepare_from_decomposition(self.decomposition, self.home / 'forward',
                                            argparse.Namespace(profile=str(profile_path)))
        self.assertTrue(result['codex_conversion_requested'])
        data = hatch.manifest(self.home / 'forward')
        self.assertEqual(len(data['jobs']), 10)
        self.assertTrue(all(job['status'] == 'pending' for job in data['jobs'] if job['id'] != 'base'))

    def test_forward_limits_use_the_existing_budget_contract(self):
        forward = self.home / 'forward'
        prepare_from_decomposition(self.decomposition, forward,
                                   argparse.Namespace(max_attempts=2, max_calls=3, estimate_units=4.0, unit_budget=12.0))
        limits = hatch.manifest(forward)['limits']
        self.assertEqual(limits['attempts_per_job'], 2)
        self.assertEqual(limits['generation_calls'], 3)
        self.assertEqual(limits['estimated_units_per_call'], 4.0)
        self.assertEqual(limits['unit_budget'], 12.0)
        self.assertEqual(hatch.job_for(hatch.manifest(forward), 'base')['attempts'], 0)

    def test_reverse_to_forward_import_validate_review_package_and_restore(self):
        """New animation artwork is explicitly authored fixture input, never model output."""
        profile = small_profile()
        for state in profile['states']:
            state['alignment']['resampling'] = 'nearest'
        profile_path = self.home / 'forward-profile.json'
        hatch.atomic(profile_path, profile)
        forward = self.home / 'forward'
        prepare_from_decomposition(self.decomposition, forward, argparse.Namespace(profile=str(profile_path)),
                                   component_ids=['eyes'])
        data = hatch.manifest(forward)
        hatch.record_base_review(forward, data, 'Authored synthetic character import; inspected for fixture gate tests.', True)
        sources = self.home / 'new-animation-art'
        sources.mkdir()
        with Image.open(self.decomposition / 'foreground.png') as opened:
            observed = opened.convert('RGBA')
        for state in profile['states']:
            names = []
            for index in range(state['frames']):
                frame = Image.new('RGBA', (96, 96))
                x = 32 + (index % 2)
                y = 40 - (index * 4 if state['id'] == 'jump' else 0)
                frame.alpha_composite(observed, (x, y))
                name = state['id'] + '-' + str(index) + '.png'
                frame.save(sources / name)
                names.append('new-animation-art/' + name)
            descriptor = self.home / (state['id'] + '-source.json')
            hatch.atomic(descriptor, {'schema_version': 1, 'kind': 'import', 'layout': 'frames',
                                     'files': names, 'origin': FIXTURE_ORIGIN + ' Newly authored test animation frames.', 'fixture': True})
            import_source(forward, data, state['id'], descriptor, 'Reviewed synthetic source order for pipeline gate testing.')
        validation = hatch.validate(forward, data)
        record_fixture_review(forward, data)
        packaged = hatch.package(forward, data, self.home / 'generation-package')
        self.assertTrue(hatch.status(forward, data)['reviewed'])
        self.assertTrue((self.home / 'generation-package').is_dir())
        archive_run(forward, data, self.home / 'forward.zip')
        restored = self.home / 'restored-forward'
        restore_run(self.home / 'forward.zip', restored)
        self.assertTrue(hatch.status(restored, hatch.manifest(restored))['reviewed'])
        self.assertEqual((restored / 'references/decomposition/decomposition.json').read_bytes(),
                         (self.decomposition / 'decomposition.json').read_bytes())
        self.assertTrue(all('generation_receipt' not in job for job in data['jobs']))


def identity_fixture():
    return {'canvas': {'width': 100, 'height': 80, 'pixel_art': True},
            'extensions': {'palette': {'coat': '#123456', 'scarf': '#aaBBcc'}},
            'components': [
                {'id': 'wing', 'name': 'Left feathered wing', 'category': 'anatomy', 'side': 'left',
                 'bbox': [5, 10, 25, 50], 'provenance': {'kind': 'segmented-observed'}, 'review': {'status': 'pending'}},
                {'id': 'scarf', 'name': 'Blue scarf', 'category': 'accessories', 'side': 'center',
                 'bbox': [30, 20, 70, 30], 'provenance': {'kind': 'segmented-observed'}, 'review': {'status': 'approved'}},
                {'id': 'spots', 'name': 'Disconnected white spots', 'category': 'markings', 'side': 'unknown',
                 'bbox': [10, 12, 90, 70], 'provenance': {'kind': 'segmented-observed'}, 'review': {'status': 'pending'}},
                {'id': 'mistake', 'name': 'Unapproved hat', 'category': 'accessories', 'side': 'center',
                 'bbox': [30, 10, 60, 20], 'provenance': {'kind': 'segmented-observed'}, 'review': {'status': 'rejected'}}]}


class DecompositionIdentityTests(unittest.TestCase):
    def test_measured_identity_keeps_palette_nonhuman_parts_and_sides(self):
        fixture = identity_fixture()
        original = copy.deepcopy(fixture)
        identity = derive_identity(fixture)
        self.assertEqual(identity['palette'], {'coat': '#123456', 'scarf': '#AABBCC'})
        self.assertEqual(identity['proportions']['wing_width_to_canvas'], 0.2)
        self.assertEqual(identity['proportions']['wing_height_to_canvas'], 0.5)
        self.assertEqual(identity['approved_props'], ['Blue scarf'])
        self.assertIn('Disconnected white spots', identity['markings'][0])
        self.assertIn('anatomical left', identity['asymmetries'][0])
        self.assertTrue(identity['forbid_mirror'])
        self.assertEqual(identity['materials'], [])
        self.assertEqual(identity['directions'], {})
        self.assertNotIn('mistake_width_to_canvas', identity['proportions'])
        self.assertEqual(fixture, original)

    def test_explicit_identity_wins_without_invented_hidden_materials(self):
        fixture = identity_fixture()
        fixture['extensions']['identity'] = {'schema_version': 1, 'palette': {'coat': '#AABBCC'},
                                             'forbid_mirror': False, 'materials': ['Approved felt texture']}
        identity = derive_identity(fixture)
        self.assertEqual(identity['palette']['coat'], '#AABBCC')
        self.assertFalse(identity['forbid_mirror'])
        self.assertEqual(identity['materials'], ['Approved felt texture'])

    def test_inferred_prop_is_not_silently_called_observed_identity(self):
        fixture = identity_fixture()
        fixture['components'][1]['provenance']['kind'] = 'inferred'
        identity = derive_identity(fixture)
        self.assertEqual(identity['approved_props'], [])

    def test_hierarchical_categories_prepopulate_props_and_markings(self):
        fixture = identity_fixture()
        fixture['components'][1]['category'] = 'clothing/scarf'
        fixture['components'][2]['category'] = 'detail/marking'
        identity = derive_identity(fixture)
        self.assertEqual(identity['approved_props'], ['Blue scarf'])
        self.assertIn('Disconnected white spots', identity['markings'][0])

    def test_layer_edits_and_new_artwork_have_explicit_different_contracts(self):
        static = operation_contract('recolor', ['scarf'], 'Change blue to red.')
        artwork = operation_contract('wave')
        self.assertFalse(static['requires_new_artwork'])
        self.assertTrue(artwork['requires_new_artwork'])
        self.assertFalse(static['hidden_geometry_available'])
        self.assertIn('no layer edit', static['execution'])
        self.assertIn('no layer edit', artwork['execution'])
        for operation in ('replace', 'recolor', 'hide', 'transform', 'reorder', 'preserve-except'):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(ValueError, 'component'):
                    operation_contract(operation, note='Requested change.')
                with self.assertRaisesRegex(ValueError, 'note'):
                    operation_contract(operation, ['scarf'])

    def test_unknown_or_duplicate_operation_targets_fail(self):
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            operation_contract('invent-all-anatomy')
        with self.assertRaisesRegex(ValueError, 'repeat'):
            operation_contract('recolor', ['scarf', 'scarf'], 'red')

    def test_invalid_palette_annotation_fails_instead_of_disappearing(self):
        fixture = identity_fixture()
        fixture['extensions']['palette']['scarf'] = 'not-a-color'
        with self.assertRaisesRegex(ValueError, 'palette'):
            derive_identity(fixture)

    def test_default_forward_profile_is_neutral_and_keeps_nearest_neighbor(self):
        profile = _reuse_profile(identity_fixture(), operation_contract('animate'))
        self.assertEqual(profile['schema_version'], 2)
        self.assertEqual([state['id'] for state in profile['states']], ['new-state'])
        self.assertEqual(profile['states'][0]['alignment']['resampling'], 'nearest')
        self.assertFalse(profile['export']['codex_compatible'])
        self.assertEqual((profile['layout']['cell_width'], profile['layout']['cell_height']), (100, 80))


if __name__ == '__main__':
    unittest.main()
