"""Actual static layer edits, strict geometry, alpha preservation, and import reuse."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from asset_contracts import sha
from character_decomposition import create_decomposition, component_signature, save_manifest
from decomposition_fixtures import make_fixture, FIXTURE_ORIGIN
from decomposition_layers import edit_layers, _transform, _settings
from decomposition_package import _inventory
from fixture_workflow import hatch, small_profile
from source_interface import import_source
from extract_strip_frames import pixels


class DecompositionLayerEditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hatch-layer-edit-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.fixture = make_fixture(self.home / 'art', 'pixel')
        self.root = self.home / 'decomposition'
        self.manifest = create_decomposition(self.fixture.source, self.root, annotations=self.fixture.annotation,
                                            origin=FIXTURE_ORIGIN, fixture=True, pixel_art=True)
        self.before = _inventory(self.root)

    def record(self, destination):
        return json.loads((destination / 'edit.json').read_text())

    def assert_source_unchanged(self):
        self.assertEqual(_inventory(self.root), self.before)

    def test_flat_recolor_changes_actual_selected_pixels_preserving_all_alpha(self):
        destination = self.home / 'red-badge'
        result = edit_layers(self.root, destination, ['badge'], 'recolor', color='#AB1234')
        record = self.record(destination)
        badge = next(component for component in self.manifest['components'] if component['id'] == 'badge')
        with Image.open(self.root / badge['asset']['path']) as original, Image.open(destination / 'layers/badge.png') as edited:
            self.assertEqual(edited.getchannel('A').tobytes(), original.getchannel('A').tobytes())
            for pixel in pixels(edited):
                if pixel[3]:
                    self.assertEqual(pixel[:3], (171, 18, 52))
        for component in self.manifest['components']:
            if component['id'] != 'badge':
                self.assertEqual(sha(destination / ('layers/' + component['id'] + '.png')), component['asset']['sha256'])
        with Image.open(self.root / 'foreground.png') as original, Image.open(destination / 'edited.png') as edited:
            self.assertEqual(original.getchannel('A').tobytes(), edited.getchannel('A').tobytes())
            self.assertEqual(edited.getpixel((16, 28)), (171, 18, 52, 255))
            self.assertNotEqual(edited.tobytes(), original.tobytes())
        self.assertIn('texture', result['appearance_policy'])
        self.assertFalse(record['validation']['hidden_geometry_filled'])
        self.assertFalse(record['validation']['source_fidelity_required'])
        self.assertEqual(record['review']['status'], 'pending')
        self.assert_source_unchanged()

    def test_recolor_preserves_fractional_source_alpha(self):
        fixture = make_fixture(self.home / 'alpha-art', 'alpha')
        root = self.home / 'alpha-decomposition'
        manifest = create_decomposition(fixture.source, root, annotations=fixture.annotation, origin=FIXTURE_ORIGIN, fixture=True)
        component = next(component for component in manifest['components'] if component['id'] == 'translucent-sparkles')
        destination = self.home / 'yellow-sparkles'
        edit_layers(root, destination, ['translucent-sparkles'], 'recolor', color='#FFFF00')
        with Image.open(root / component['asset']['path']) as original, Image.open(destination / 'layers/translucent-sparkles.png') as edited:
            self.assertIn(127, list(pixels(edited.getchannel('A'))))
            self.assertEqual(original.getchannel('A').tobytes(), edited.getchannel('A').tobytes())

    def test_hide_keeps_the_layer_asset_and_leaves_real_holes_without_fill(self):
        destination = self.home / 'no-badge'
        result = edit_layers(self.root, destination, ['badge'], 'hide')
        record = self.record(destination)
        badge = next(layer for layer in record['layers'] if layer['id'] == 'badge')
        self.assertFalse(badge['visible'])
        self.assertTrue((destination / badge['asset']['path']).is_file())
        with Image.open(destination / 'edited.png') as edited:
            self.assertEqual(edited.getpixel((16, 28))[3], 0)
            self.assertGreater(edited.getpixel((10, 24))[3], 0)
        self.assertFalse(result['hidden_geometry_filled'])
        self.assert_source_unchanged()

    def test_integer_translation_preserves_exact_asset_pixels_and_new_placement(self):
        destination = self.home / 'moved-badge'
        edit_layers(self.root, destination, ['badge'], 'transform', offset=[3, 0])
        record = self.record(destination)
        moved = next(layer for layer in record['layers'] if layer['id'] == 'badge')
        original = next(component for component in self.manifest['components'] if component['id'] == 'badge')
        self.assertEqual(moved['bbox'], [original['bbox'][0] + 3, original['bbox'][1], original['bbox'][2] + 3, original['bbox'][3]])
        self.assertEqual(moved['asset']['sha256'], original['asset']['sha256'])
        with Image.open(destination / 'edited.png') as edited:
            self.assertEqual(edited.getpixel((16, 28))[3], 0)
            self.assertEqual(edited.getpixel((19, 28)), (255, 109, 89, 255))
        self.assert_source_unchanged()

    def test_pixel_art_rotation_retains_palette_and_disconnected_pixels(self):
        destination = self.home / 'rotated-eyes'
        edit_layers(self.root, destination, ['eyes'], 'transform', rotation=90)
        record = self.record(destination)
        rotated = next(layer for layer in record['layers'] if layer['id'] == 'eyes')
        original = next(component for component in self.manifest['components'] if component['id'] == 'eyes')
        with Image.open(self.root / original['asset']['path']) as before, Image.open(destination / rotated['asset']['path']) as after:
            self.assertEqual(after.size, (before.height, before.width))
            self.assertEqual(set(pixels(after)), set(pixels(before)))
            self.assertEqual(sum(alpha > 0 for alpha in pixels(after.getchannel('A'))),
                             sum(alpha > 0 for alpha in pixels(before.getchannel('A'))))
        self.assertEqual(record['resampling'], 'nearest')
        self.assert_source_unchanged()

    def test_reorder_updates_real_layer_structure_without_claiming_new_pixels(self):
        destination = self.home / 'new-order'
        edit_layers(self.root, destination, ['badge', 'eyes'], 'reorder', z_index=-20)
        record = self.record(destination)
        self.assertEqual(next(layer for layer in record['layers'] if layer['id'] == 'badge')['z_index'], -20)
        self.assertEqual(next(layer for layer in record['layers'] if layer['id'] == 'eyes')['z_index'], -19)
        # Faithful ownership masks are disjoint. Changing their order alone should
        # not fabricate previously hidden content or alter their observed pixels.
        with Image.open(destination / 'edited.png') as edited, Image.open(self.root / 'foreground.png') as original:
            self.assertEqual(edited.tobytes(), original.tobytes())
        self.assertEqual(record['validation']['different_pixels_from_source'], 0)
        self.assert_source_unchanged()

    def test_clipping_invalid_colors_and_unsafe_targets_leave_no_variant(self):
        cases = [(['badge'], 'transform', {'offset': [100, 0]}),
                 (['badge'], 'transform', {'scale': 0}),
                 (['badge'], 'transform', {'rotation': float('nan')}),
                 (['badge'], 'recolor', {'color': 'red'}),
                 (['badge'], 'recolor', {'color': '#FFFFFF', 'offset': [1, 0]}),
                 (['missing'], 'hide', {}), (['badge', 'badge'], 'hide', {}),
                 (['badge'], 'reorder', {'z_index': True})]
        for components, operation, kwargs in cases:
            with self.subTest(operation=operation, kwargs=kwargs):
                with self.assertRaises(ValueError):
                    edit_layers(self.root, self.home / 'unwritten', components, operation, **kwargs)
                self.assertFalse((self.home / 'unwritten').exists())
                self.assert_source_unchanged()

    def test_large_transformed_work_surface_fails_before_raster_allocation(self):
        component = {'id': 'large', 'bbox': [0, 0, 1000, 1000], 'pivot': [500, 500]}
        image = Image.new('RGBA', (1000, 1000), '#FFFFFF')
        settings = _settings('transform', None, [0, 0], 0, 16, None)
        with self.assertRaisesRegex(ValueError, 'work surface'):
            _transform(image, component, settings, (1400, 1400), True)

    def test_rejected_component_requires_independent_repair_before_editing(self):
        component = next(component for component in self.manifest['components'] if component['id'] == 'badge')
        component['review'] = {'status': 'rejected', 'author': 'Fixture reviewer', 'note': 'Test independent repair gate.',
                               'signature': component_signature(component)}
        save_manifest(self.root, self.manifest)
        with self.assertRaisesRegex(ValueError, 'repair rejected'):
            edit_layers(self.root, self.home / 'unwritten', ['badge'], 'hide')
        self.assertFalse((self.home / 'unwritten').exists())

    def test_variant_receipt_and_import_descriptor_reuse_actual_edited_art(self):
        destination = self.home / 'variant'
        edit_layers(self.root, destination, ['badge'], 'recolor', color='#123456')
        receipt = json.loads((destination / 'edit-receipt.json').read_text())
        self.assertEqual({name: sha(destination / name) for name in receipt['files']}, receipt['files'])
        self.assertEqual((destination / 'source/decomposition/decomposition.json').read_bytes(),
                         (self.root / 'decomposition.json').read_bytes())
        profile = self.home / 'profile.json'
        hatch.atomic(profile, small_profile())
        forward = self.home / 'forward'
        hatch.prepare(forward, argparse.Namespace(replace_inputs=False, fixture_mode=True, profile=str(profile),
                                                  pet_name='Edited fixture', pet_notes='Explicit deterministic recolor fixture.',
                                                  identity=str(destination / 'identity.json'),
                                                  reference=[str(destination / 'edited.png')]))
        data = hatch.manifest(forward)
        imported = import_source(forward, data, 'base', destination / 'base-source.json',
                                 'Imported deterministic recolor for fixture test; visual review remains required.')
        self.assertFalse(imported['imagegen_output'])
        self.assertIn(sha(destination / 'edit.json'), hatch.job_for(data, 'base')['import_receipt']['origin'])
        with Image.open(forward / 'references/canonical-base.png') as canonical, Image.open(destination / 'edited.png') as edited:
            self.assertEqual(canonical.tobytes(), edited.tobytes())


if __name__ == '__main__':
    unittest.main()
