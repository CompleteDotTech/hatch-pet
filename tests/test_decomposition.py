"""Real raster extraction and fail-closed contracts with authored semantic fixtures.

These tests prove deterministic mechanics for supplied annotations.  They do not
certify general-purpose visual understanding or production artwork acceptance.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from asset_contracts import MAX_SOURCE_PIXELS, sha, validate_identity
from decomposition_fixtures import FIXTURE_ORIGIN, file_hash, make_fixture
from profile_spec import load_profile
import character_decomposition as decomposition
from decomposition_masks import MAX_COMPONENTS, MAX_MASK_PIXELS
from decomposition_spec import MANIFEST_SCHEMA, schemas, validate_structure
from extract_strip_frames import pixels

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def visible_difference(first, second):
    """Compare alpha exactly and RGB only where either source is visible."""
    first, second = first.convert('RGBA'), second.convert('RGBA')
    if first.size != second.size:
        return True
    alpha = ImageChops.lighter(first.getchannel('A'), second.getchannel('A'))
    rgb = ImageChops.difference(first.convert('RGB'), second.convert('RGB'))
    visible = Image.new('RGB', first.size)
    visible.paste(rgb, mask=alpha.point(lambda value: 255 if value else 0))
    return bool(visible.getbbox() or ImageChops.difference(first.getchannel('A'), second.getchannel('A')).getbbox())


class DecompositionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='hatch-decomposition-test-')
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.root = self.home / 'run'

    def fixture(self, name='cartoon', image_format='PNG'):
        return make_fixture(self.home / ('fixture-' + name + '-' + image_format.lower()), name, image_format)

    def build(self, fixture, **kwargs):
        return decomposition.create_decomposition(
            fixture.source, self.root, annotations=fixture.annotation,
            fixture=True, origin=FIXTURE_ORIGIN, **kwargs)

    def assert_faithful(self, fixture, manifest):
        report = decomposition.validate_decomposition(self.root, manifest)
        self.assertTrue(report['ok'], report)
        self.assertTrue(report['faithful_fidelity_passed'], report)
        self.assertEqual(report['reconstruction_error']['max_channel_error'], 0)
        self.assertEqual(report['reconstruction_error']['rmse'], 0)
        self.assertEqual(report['source_pixel_coverage'], 1)
        self.assertTrue(report['alpha_preserved'])
        self.assertEqual(report['semantic_status'], 'pending')
        with Image.open(self.root / 'previews/reconstructed.png') as reconstructed:
            self.assertFalse(visible_difference(reconstructed, fixture.expected))
        self.assertEqual(manifest['source']['sha256'], file_hash(fixture.source))
        self.assertTrue(manifest['source']['fixture'])

    def test_semantic_parts_share_a_connected_source_but_have_true_masks(self):
        fixture = self.fixture()
        before = fixture.source.read_bytes()
        manifest = self.build(fixture)
        self.assert_faithful(fixture, manifest)
        self.assertEqual(before, fixture.source.read_bytes())
        self.assertEqual({c['id'] for c in manifest['components']}, {c['id'] for c in fixture.components})
        by_id = {c['id']: c for c in manifest['components']}
        for truth in fixture.components:
            component = by_id[truth['id']]
            self.assertEqual(component['bbox'], truth['bbox'])
            self.assertEqual(component['parent_id'], truth['parent'])
            self.assertEqual(component['category'], truth['category'])
            self.assertEqual(sha(self.root / component['asset']['path']), component['asset']['sha256'])
            self.assertEqual(sha(self.root / component['mask']['path']), component['mask']['sha256'])
            with Image.open(self.root / component['asset']['path']) as asset:
                self.assertEqual(asset.mode, 'RGBA')
                self.assertEqual(asset.size, (truth['bbox'][2] - truth['bbox'][0], truth['bbox'][3] - truth['bbox'][1]))
                self.assertEqual(asset.getchannel('A').getbbox(), (0, 0, asset.width, asset.height))
                with Image.open(fixture.root / truth['mask']) as mask:
                    expected = fixture.expected.crop(truth['bbox'])
                    expected.putalpha(ImageChops.multiply(expected.getchannel('A'), mask.crop(truth['bbox'])))
                self.assertFalse(visible_difference(asset, expected), truth['id'])
        head = by_id['head']
        with Image.open(self.root / head['asset']['path']) as image:
            # Curved edges and punched-out facial ownership are retained.
            self.assertGreater(image.getchannel('A').histogram()[0], 0)
        self.assertEqual(by_id['anatomical-left-eye']['side'], 'left')
        self.assertGreater(by_id['anatomical-left-eye']['bbox'][0], by_id['anatomical-right-eye']['bbox'][0])

    def test_disconnected_highlights_remain_one_semantic_component(self):
        fixture = self.fixture()
        manifest = self.build(fixture)
        highlights = next(c for c in manifest['components'] if c['id'] == 'eye-highlights')
        with Image.open(self.root / highlights['asset']['path']) as asset:
            self.assertEqual(sum(value > 0 for value in pixels(asset.getchannel('A'))), 8)
            self.assertEqual(asset.getpixel((asset.width // 2, 0))[3], 0)
        self.assertEqual(highlights['parent_id'], 'head')

    def test_semantic_polygon_and_seeded_color_masks_extract_actual_source_pixels(self):
        fixture = self.fixture()
        annotation = read_json(fixture.annotation)
        for component in annotation['components']:
            component['mask']['path'] = str(fixture.root / component['mask']['path'])
        by_id = {component['id']: component for component in annotation['components']}
        by_id['eye-highlights']['mask'] = {'polygons': [
            [[35, 30], [36, 30], [36, 31], [35, 31]],
            [[56, 30], [57, 30], [57, 31], [56, 31]]
        ]}
        by_id['anatomical-left-eye']['mask'] = {'colors': {'values': ['#253547'], 'tolerance': 0,
            'seeds': [[59, 34]], 'within': [[[50, 25], [66, 25], [66, 40], [50, 40]]]}}
        manifest = decomposition.create_decomposition(fixture.source, self.root, annotations=annotation,
            fixture=True, origin=FIXTURE_ORIGIN)
        self.assert_faithful(fixture, manifest)
        left_eye = next(c for c in manifest['components'] if c['id'] == 'anatomical-left-eye')
        truth = next(c for c in fixture.components if c['id'] == 'anatomical-left-eye')
        self.assertEqual(left_eye['bbox'], truth['bbox'])

    def test_fractional_membership_masks_are_rejected_without_damaging_source_alpha(self):
        fixture = self.fixture('alpha')
        annotation = read_json(fixture.annotation)
        bad_mask = self.home / 'fractional-membership.png'
        Image.new('L', fixture.size, 128).save(bad_mask)
        annotation['components'] = [dict(annotation['components'][0], parent_id=None, mask={'path': str(bad_mask)})]
        with self.assertRaisesRegex(ValueError, 'binary|0/255'):
            decomposition.create_decomposition(fixture.source, self.root, annotations=annotation, fixture=True)
        self.assertFalse(self.root.exists())
        self.assertEqual(annotation['source_sha256'], file_hash(fixture.source))

    def test_occluded_arm_keeps_observed_pixels_and_uncertainty(self):
        fixture = self.fixture('overlap')
        manifest = self.build(fixture)
        self.assert_faithful(fixture, manifest)
        by_id = {c['id']: c for c in manifest['components']}
        self.assertEqual(by_id['torso']['occlusion']['status'], 'partial')
        self.assertEqual(by_id['held-or-attached-object']['confidence'], .35)
        self.assertNotEqual(by_id['held-or-attached-object']['review']['status'], 'approved')
        self.assertTrue(all(c['provenance']['kind'] != 'inferred' for c in manifest['components']))

    def test_multiple_accessories_keep_independent_assets_and_hierarchy(self):
        fixture = self.fixture('accessories')
        manifest = self.build(fixture)
        self.assert_faithful(fixture, manifest)
        by_id = {c['id']: c for c in manifest['components']}
        self.assertEqual(by_id['hat']['parent_id'], 'head')
        self.assertEqual(by_id['cup']['parent_id'], 'anatomical-left-arm')
        self.assertEqual(len({by_id[name]['asset']['path'] for name in ('hat', 'scarf', 'badge', 'cup')}), 4)

    def test_nonhuman_anatomy_is_data_driven_and_not_padded_with_humanoid_parts(self):
        fixture = self.fixture('creature')
        manifest = self.build(fixture)
        self.assert_faithful(fixture, manifest)
        identifiers = {component['id'] for component in manifest['components']}
        self.assertTrue({'tail', 'near-wing', 'far-wing', 'horns', 'flank-spots'} <= identifiers)
        self.assertFalse(any('hand' in identifier or 'arm' in identifier for identifier in identifiers))

    def test_pixel_art_keeps_native_dimensions_alpha_and_palette(self):
        fixture = self.fixture('pixel')
        manifest = self.build(fixture, pixel_art=True)
        self.assert_faithful(fixture, manifest)
        self.assertTrue(manifest['canvas']['pixel_art'])
        self.assertEqual((manifest['canvas']['width'], manifest['canvas']['height']), fixture.size)
        source_palette = {pixel[:3] for pixel in pixels(fixture.expected) if pixel[3]}
        for component in manifest['components']:
            with Image.open(self.root / component['asset']['path']) as asset:
                self.assertTrue({pixel[:3] for pixel in pixels(asset) if pixel[3]} <= source_palette)
                self.assertTrue({pixel[3] for pixel in pixels(asset)} <= {0, 255})

    def test_fractional_original_alpha_is_not_applied_twice(self):
        fixture = self.fixture('alpha')
        self.assertTrue(any(0 < pixel[3] < 255 for pixel in pixels(fixture.expected)))
        manifest = self.build(fixture)
        self.assert_faithful(fixture, manifest)

    def test_complex_background_uses_explicit_foreground_and_preserves_input(self):
        fixture = self.fixture('complex')
        before = fixture.source.read_bytes()
        manifest = self.build(fixture)
        self.assert_faithful(fixture, manifest)
        self.assertEqual(before, fixture.source.read_bytes())
        with Image.open(fixture.source) as original, Image.open(self.root / 'foreground.png') as foreground:
            self.assertEqual(original.getpixel((0, 0))[3], 255)
            self.assertEqual(foreground.getpixel((0, 0))[3], 0)
            self.assertEqual(foreground.size, original.size)

    def test_no_annotation_route_is_honestly_pending_despite_perfect_pixels(self):
        fixture = self.fixture()
        manifest = decomposition.create_decomposition(fixture.source, self.root, fixture=True, origin=FIXTURE_ORIGIN)
        report = decomposition.validate_decomposition(self.root, manifest)
        self.assertTrue(report['faithful_fidelity_passed'])
        self.assertEqual(report['semantic_status'], 'pending')
        self.assertTrue(all(c['review']['status'] != 'approved' for c in manifest['components']))
        self.assertNotEqual({c['id'] for c in manifest['components']}, {c['id'] for c in fixture.components})
        self.assertFalse(manifest['analysis']['semantic_model_called'])
        self.assertEqual(manifest['analysis']['mode'], 'manual-pending')
        self.assertFalse(manifest['rig']['animation_ready'])

    def test_multiple_character_suspicion_requires_explicit_selection_or_grouping(self):
        fixture = self.fixture('multiple')
        manifest = decomposition.create_decomposition(fixture.source, self.root, fixture=True, origin=FIXTURE_ORIGIN)
        self.assertTrue(manifest['analysis']['multiple_characters_suspected'])
        self.assertFalse(manifest['analysis']['selection_resolved'])
        self.assertTrue(all(c['semantic_character'] is False for c in manifest['analysis']['candidates']))
        selected_root = self.home / 'selected-character'
        selected = decomposition.create_decomposition(fixture.source, selected_root,
            selection=[0, 0, 40, 52], annotations=fixture.annotation, fixture=True, origin=FIXTURE_ORIGIN)
        self.assertTrue(selected['analysis']['selection_resolved'])
        self.assertEqual(selected['analysis']['selection'], [0, 0, 40, 52])
        self.assertTrue(all(c['id'].startswith('first-') for c in selected['components']))
        with Image.open(selected_root / 'foreground.png') as image:
            self.assertIsNone(image.crop((40, 0, 80, 52)).getbbox())
        self.assertEqual(selected['canvas']['width'], 80)

    def test_complex_background_without_mask_stays_unresolved(self):
        fixture = self.fixture('complex')
        manifest = decomposition.create_decomposition(fixture.source, self.root, fixture=True, origin=FIXTURE_ORIGIN)
        self.assertEqual(manifest['foreground']['method'], 'unresolved-complex-background')
        self.assertTrue(manifest['foreground']['review_required'])
        self.assertEqual(manifest['foreground']['confidence'], 0)
        self.assertTrue(manifest['foreground']['warnings'])
        self.assertEqual(manifest['validation']['semantic_status'], 'pending')

    def test_solid_edge_background_is_removed_without_repainting_foreground(self):
        fixture = self.fixture()
        source = self.home / 'solid-background.png'
        opaque = Image.new('RGBA', fixture.size, '#12EF4D')
        opaque.alpha_composite(fixture.expected)
        opaque.save(source)
        manifest = decomposition.create_decomposition(source, self.root, fixture=True, origin=FIXTURE_ORIGIN)
        self.assertEqual(manifest['foreground']['method'], 'edge-connected-solid')
        with Image.open(self.root / 'foreground.png') as foreground:
            self.assertFalse(visible_difference(foreground, fixture.expected))
        self.assertTrue(manifest['foreground']['review_required'])

    def test_unassigned_pixels_are_retained_but_semantic_approval_is_pending(self):
        fixture = self.fixture()
        annotation = read_json(fixture.annotation)
        annotation['components'] = [dict(annotation['components'][0], parent_id=None)]
        annotation['components'][0]['mask']['path'] = str(fixture.root / annotation['components'][0]['mask']['path'])
        manifest = decomposition.create_decomposition(fixture.source, self.root, annotations=annotation, fixture=True, origin=FIXTURE_ORIGIN)
        report = decomposition.validate_decomposition(self.root, manifest)
        self.assertTrue(report['faithful_fidelity_passed'])
        self.assertGreater(report['unassigned_foreground_pixels'], 0)
        self.assertEqual(report['semantic_status'], 'pending')
        self.assertEqual(report['gap_pixels'], 0)
        with Image.open(self.root / 'previews/reconstructed.png') as reconstructed:
            self.assertFalse(visible_difference(reconstructed, fixture.expected))

    def test_overlapping_proposals_are_measured_and_visible_ownership_is_unique(self):
        fixture = self.fixture()
        annotation = read_json(fixture.annotation)
        for component in annotation['components']:
            component['mask']['path'] = str(fixture.root / component['mask']['path'])
        by_id = {component['id']: component for component in annotation['components']}
        with Image.open(by_id['head']['mask']['path']) as head, Image.open(by_id['anatomical-left-eye']['mask']['path']) as eye:
            overlap = ImageChops.lighter(head, eye)
            path = self.home / 'overlapping-head.png'
            overlap.save(path)
        by_id['head']['mask'] = {'path': str(path)}
        manifest = decomposition.create_decomposition(fixture.source, self.root, annotations=annotation, fixture=True, origin=FIXTURE_ORIGIN)
        self.assert_faithful(fixture, manifest)
        self.assertGreater(manifest['extensions']['segmentation_diagnostics']['proposal_overlap_pixels'], 0)
        self.assertEqual(manifest['validation']['unexpected_overlap_pixels'], 0)

    def test_accepted_formats_preserve_decoded_source_colors_and_raw_file_hashes(self):
        for image_format in ('JPEG', 'WEBP'):
            with self.subTest(image_format=image_format):
                fixture = self.fixture('cartoon', image_format)
                output = self.home / ('run-' + image_format)
                manifest = decomposition.create_decomposition(
                    fixture.source, output, annotations=fixture.annotation,
                    foreground_mask=fixture.foreground_mask, fixture=True, origin=FIXTURE_ORIGIN)
                report = decomposition.validate_decomposition(output, manifest)
                self.assertTrue(report['faithful_fidelity_passed'])
                self.assertEqual(manifest['source']['sha256'], file_hash(fixture.source))
                with Image.open(fixture.source) as image, Image.open(output / 'foreground.png') as foreground:
                    self.assertEqual(image.size, foreground.size)
                    with Image.open(fixture.foreground_mask) as mask:
                        expected = image.convert('RGBA')
                        expected.putalpha(ImageChops.multiply(expected.getchannel('A'), mask))
                    self.assertFalse(visible_difference(foreground, expected))

    def test_bundled_real_art_import_has_fidelity_but_no_semantic_certificate(self):
        source = self.home / 'historical-pip.png'
        with Image.open(ROOT / 'assets/pet/spritesheet.webp') as atlas:
            atlas.crop((0, 0, 192, 208)).save(source)
        manifest = decomposition.create_decomposition(source, self.root, origin='Bundled historical Pip artwork; existing repository sample.')
        report = decomposition.validate_decomposition(self.root, manifest)
        self.assertTrue(report['faithful_fidelity_passed'])
        self.assertEqual(report['semantic_status'], 'pending')
        self.assertFalse(manifest['source']['fixture'])

    def test_wrong_source_hash_rejects_before_creating_run(self):
        fixture = self.fixture()
        annotation = read_json(fixture.annotation)
        annotation['source_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'source|hash'):
            decomposition.create_decomposition(fixture.source, self.root, annotations=annotation)
        self.assertFalse(self.root.exists())

    def test_unknown_fields_invalid_confidence_and_hierarchy_cycles_fail(self):
        fixture = self.fixture()
        original = read_json(fixture.annotation)
        # Give dictionary annotations portable inline masks, avoiding cwd dependence.
        for component in original['components']:
            component['mask']['path'] = str(fixture.root / component['mask']['path'])
        changes = [
            lambda value: value.update(unimplemented_model='imaginary-service'),
            lambda value: value['components'][0].update(confidence=float('nan')),
            lambda value: value['components'][0].update(confidence=1.5),
            lambda value: value['components'][0].update(parent_id='does-not-exist'),
            lambda value: value['components'][2].update(parent_id='head'),
            lambda value: value['components'][0].update(id='../outside'),
            lambda value: value.update(schema_version=True),
        ]
        for change in changes:
            annotation = copy.deepcopy(original)
            change(annotation)
            with self.subTest(annotation=annotation), self.assertRaises(ValueError):
                decomposition.create_decomposition(fixture.source, self.root, annotations=annotation)
            self.assertFalse(self.root.exists())

    def test_masks_must_match_canvas_and_be_valid_not_just_rectangles(self):
        fixture = self.fixture()
        for invalid in ({'rect': [0, 0, 96, 112]}, {'runs': [[0, 0, 1000]]}):
            annotation = read_json(fixture.annotation)
            annotation['components'] = [dict(annotation['components'][0], parent_id=None, mask=invalid)]
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                decomposition.create_decomposition(fixture.source, self.root, annotations=annotation)
            self.assertFalse(self.root.exists())
        wrong_mask = self.home / 'wrong-size.png'
        Image.new('L', (4, 4), 255).save(wrong_mask)
        annotation = read_json(fixture.annotation)
        annotation['components'] = [dict(annotation['components'][0], parent_id=None, mask={'path': str(wrong_mask)})]
        with self.assertRaisesRegex(ValueError, 'size|dimension|canvas'):
            decomposition.create_decomposition(fixture.source, self.root, annotations=annotation)
        self.assertFalse(self.root.exists())

    def test_empty_invalid_animated_and_unsupported_inputs_are_rejected(self):
        empty = self.home / 'empty.png'
        Image.new('RGBA', (32, 32)).save(empty)
        invalid = self.home / 'invalid.png'
        invalid.write_bytes(b'not an image')
        unsupported = self.home / 'unsupported.gif'
        Image.new('RGBA', (10, 10), 'red').save(unsupported)
        animated = self.home / 'animated.webp'
        frames = [Image.new('RGBA', (10, 10), color) for color in ('red', 'blue')]
        frames[0].save(animated, save_all=True, append_images=frames[1:], duration=100, loop=0)
        for source in (empty, invalid, unsupported, animated):
            with self.subTest(source=source.name), self.assertRaises((ValueError, OSError)):
                decomposition.create_decomposition(source, self.root)
            self.assertFalse(self.root.exists())

    def test_oversized_input_is_rejected_without_a_package(self):
        source = self.home / 'oversized.png'
        Image.new('RGB', (2001, 1000), '#314159').save(source)
        self.assertGreater(2001 * 1000, MAX_SOURCE_PIXELS)
        with self.assertRaisesRegex(ValueError, 'pixels|bound|large'):
            decomposition.create_decomposition(source, self.root)
        self.assertFalse(self.root.exists())

    def test_component_count_and_expanded_mask_allocations_are_bounded(self):
        fixture = self.fixture()
        annotation = read_json(fixture.annotation)
        single = dict(annotation['components'][0], parent_id=None)
        single['mask'] = {'runs': [[0, 0, 1]]}
        annotation['components'] = [dict(single, id='part-' + str(index)) for index in range(MAX_COMPONENTS + 1)]
        with self.assertRaisesRegex(ValueError, 'bound|count|maximum'):
            decomposition.create_decomposition(fixture.source, self.root, annotations=annotation)
        self.assertFalse(self.root.exists())
        # A 1-megapixel source is valid alone, but 65 full-size ownership masks
        # exceed the separately bounded expanded working set. No large masks
        # need to be decoded to establish that bound.
        source = self.home / 'large-valid.png'
        Image.new('RGBA', (1000, 1000), 'red').save(source)
        annotation['source_sha256'] = file_hash(source)
        annotation['components'] = [dict(single, id='part-' + str(index))
                                    for index in range(MAX_MASK_PIXELS // 1_000_000 + 1)]
        with self.assertRaisesRegex(ValueError, 'bound|working|allocation'):
            decomposition.create_decomposition(source, self.root, annotations=annotation, background='keep')
        self.assertFalse(self.root.exists())

    def test_published_schemas_match_runtime_and_allow_only_explicit_extensions(self):
        import jsonschema
        fixture = self.fixture()
        manifest = self.build(fixture)
        for filename, schema in schemas().items():
            self.assertEqual(read_json(ROOT / 'profiles' / filename), schema)
            jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(manifest, schemas()['decomposition.schema.json'])
        jsonschema.validate(read_json(fixture.annotation), schemas()['decomposition-annotations.schema.json'])
        extended = copy.deepcopy(manifest)
        extended['extensions']['example-studio'] = {'costume_group': 'winter'}
        validate_structure(extended, MANIFEST_SCHEMA)
        jsonschema.validate(extended, schemas()['decomposition.schema.json'])
        extended['undeclared_top_level_contract'] = True
        with self.assertRaises(ValueError):
            validate_structure(extended, MANIFEST_SCHEMA)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(extended, schemas()['decomposition.schema.json'])

    def test_existing_run_is_never_overwritten(self):
        fixture = self.fixture()
        self.build(fixture)
        before = (self.root / 'decomposition.json').read_bytes()
        with self.assertRaises(ValueError):
            self.build(fixture)
        self.assertEqual(before, (self.root / 'decomposition.json').read_bytes())

    def test_asset_and_mask_tampering_cannot_pass_load_or_fidelity_validation(self):
        fixture = self.fixture()
        manifest = self.build(fixture)
        component = manifest['components'][0]
        path = self.root / component['asset']['path']
        saved = path.read_bytes()
        Image.new('RGBA', (2, 2), '#C0FFEE').save(path)
        with self.assertRaises(ValueError):
            decomposition.load_decomposition(self.root)
        path.write_bytes(saved)
        mask = self.root / component['mask']['path']
        Image.new('L', fixture.size, 0).save(mask)
        with self.assertRaises(ValueError):
            decomposition.load_decomposition(self.root)

    def test_quality_and_rig_metadata_must_match_recomputed_source_evidence(self):
        fixture = self.fixture()
        manifest = self.build(fixture)
        original = (self.root / 'decomposition.json').read_bytes()
        sidecar_hashes = {name: sha(self.root / name) for name in
                          ('decomposition.json', 'identity.json', 'validation.json', 'provenance.json')}
        changes = [
            ('quality', lambda value: value['quality'].update(
                edge_contrast_mean=value['quality']['edge_contrast_mean'] + 1)),
            ('rig', lambda value: value['rig'].update(status='unrigged')),
        ]
        for label, change in changes:
            altered = copy.deepcopy(manifest)
            change(altered)
            with self.subTest(field=label, operation='save'), self.assertRaisesRegex(ValueError, 'quality|rig|metadata|validation'):
                decomposition.save_manifest(self.root, altered)
            self.assertEqual(sidecar_hashes, {name: sha(self.root / name) for name in sidecar_hashes})
            altered = copy.deepcopy(manifest)
            change(altered)
            (self.root / 'decomposition.json').write_text(json.dumps(altered), encoding='utf-8')
            try:
                with self.subTest(field=label, operation='load'), self.assertRaisesRegex(ValueError, 'quality|rig|metadata|validation'):
                    decomposition.load_decomposition(self.root)
            finally:
                (self.root / 'decomposition.json').write_bytes(original)
        self.assertTrue(decomposition.load_decomposition(self.root)['validation']['ok'])

    def test_identity_is_compatible_with_existing_generation_contract(self):
        fixture = self.fixture('accessories')
        self.build(fixture)
        identity = read_json(self.root / 'identity.json')
        checked = validate_identity(identity, load_profile())
        self.assertTrue(checked['palette'])
        self.assertTrue(checked['forbid_mirror'])
        self.assertTrue({'Hat', 'Scarf', 'Badge', 'Cup'} <= set(checked['approved_props']))
        self.assertTrue(any('Eye Highlights' in marking for marking in checked['markings']))


if __name__ == '__main__':
    unittest.main()
