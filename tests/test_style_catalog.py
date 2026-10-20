"""Visual-style contracts and lifecycle regressions; no production images are generated.

Every shipped style is prepared with real prompts and layout guides. The few tests
that acquire raster sources use the explicitly labeled fixture workflow: they test
provenance and review gates, not the aesthetic quality of imagegen output.
"""
import argparse
from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from textwrap import dedent
import unittest
from unittest.mock import patch

from PIL import Image
from jsonschema import Draft202012Validator

from fixture_workflow import (
    build_run, hatch, record_fixture_review, small_profile,
)
from portable_runs import archive_run, restore_run
from profile_spec import load_profile
from source_interface import import_source
import prepare_pet_run as preparation
import style_registry as registry


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_STYLES = (
    'auto', 'pixel', 'plush', 'clay', 'sticker', 'flat-vector', '3d-toy',
    'painterly', 'brand-inspired',
)
INSTRUCTION_FIELDS = {
    'materials', 'forms', 'linework', 'shading', 'palette', 'texture', 'rendering',
}
THEMES = {
    'fantasy', 'cyberpunk', 'steampunk', 'cottagecore', 'solarpunk', 'gothic',
    'whimsical', 'cozy', 'nautical', 'botanical', 'celestial', 'futuristic',
    'spooky', 'seasonal',
}
# Normalized user-requested coverage targets; a declared alias is a valid selector.
COVERAGE_TARGETS = {
    'pixel-games': ('pixel-art 8-bit 16-bit 32-bit isometric-pixel-art dithered-pixel-art '
                    'voxel retro-handheld lcd-game arcade-sprite monochrome-handheld '
                    'limited-palette-pixel-art pixel-outline retro-console hand-painted-game-sprite').split(),
    'cartoon-vector': ('flat-vector sticker cel-shaded soft-vector geometric-cartoon rubber-hose-animation '
                       'saturday-morning-cartoon modern-mascot editorial-cartoon doodle kawaii chibi '
                       'minimal-outline thick-outline cutout-cartoon classic-animation expressive-character-illustration').split(),
    'anime-comics': ('anime retro-anime manga-ink webtoon comic-book newspaper-comic indie-comic graphic-novel '
                     'halftone-comic inked-illustration childrens-storybook picture-book-illustration '
                     'european-comic superhero-cartoon cinematic-animation').split(),
    'painting-drawing': ('painterly watercolor gouache acrylic oil-paint impasto pastel chalk crayon colored-pencil '
                         'graphite charcoal ink-wash sumi-e tempera marker airbrush pencil-sketch ink-sketch colored-ink').split(),
    'printmaking': ('woodcut linocut screen-print risograph lithograph etching engraving stippling block-print '
                    'cyanotype monotype newsprint stencil-print halftone-print vintage-illustrated-print').split(),
    'sculpture-toys': ('3d-toy low-poly-3d stylized-3d clay polymer-clay plasticine vinyl-toy resin-figure '
                       'collectible-figurine porcelain ceramic wooden-toy carved-wood stone-sculpture metal-sculpture '
                       'stop-motion-puppet inflatable-toy balloon-sculpture miniature-diorama').split(),
    'textile-fiber': ('plush felt needle-felt felt-applique embroidery cross-stitch crochet amigurumi knitted '
                      'patchwork quilted woven-tapestry yarn-art tufted-rug fabric-collage sock-puppet hand-sewn-doll').split(),
    'paper-craft': ('paper-cutout layered-paper papercraft origami paper-quilling torn-paper-collage mixed-media-collage '
                    'scrapbook cardboard-cutout shadow-puppet pop-up-book construction-paper-art handmade-greeting-card-art').split(),
    'glass-materials': ('stained-glass frosted-glass blown-glass enamel-pin cloisonne mosaic-tile perler-beads beadwork '
                        'crystal gemstone holographic-foil metallic-foil iridescent-finish rubber-figurine jelly-toy '
                        'wax-sculpture carved-soap resin-art').split(),
    'historical-retro': ('art-deco art-nouveau mid-century-modern 1960s-television-animation 1970s-storybook 1980s-retro '
                         '1990s-animation y2k pulp-illustration retrofuturism synthwave vaporwave vintage-advertising '
                         'vintage-illustration illuminated-manuscript vintage-toy-packaging').split(),
    'graphic-design': ('bauhaus memphis-design geometric-minimalism monochrome duotone pastel-flat neon-outline '
                       'gradient-illustration silhouette negative-space-illustration stencil-graphics editorial-minimalism '
                       'bold-geometric-illustration organic-abstract decorative-pattern-illustration').split(),
    'electronic-experimental': ('hologram wireframe ascii-inspired-graphics dot-matrix led-matrix e-ink crt-display '
                                'retro-terminal glitch-art thermal-printer blueprint-illustration technical-schematic '
                                'futuristic-hud low-resolution-digital-display chrome-3d').split(),
}


def run_preparer(destination, style='watercolor', profile=None, extra=()):
    """Exercise the actual CLI entry point, preserving its module-level defaults."""
    argv = [str(ROOT / 'scripts/prepare_pet_run.py'), '--output-dir', str(destination),
            '--pet-name', 'Style contract fixture', '--pet-notes',
            'An approved compact otter with a white left ear.', '--style-preset', style,
            '--style-notes', 'Retain the user-approved white left ear.']
    if profile is not None:
        argv += ['--profile', str(profile)]
    argv += list(extra)
    output = io.StringIO()
    with patch.object(sys, 'argv', argv), redirect_stdout(output), \
            patch.object(preparation, 'ATLAS', copy.deepcopy(preparation.ATLAS)), \
            patch.object(preparation, 'ROWS', copy.deepcopy(preparation.ROWS)):
        preparation.main()
    return (hatch.read(destination / 'pet_request.json'),
            hatch.read(destination / 'imagegen-jobs.json'), json.loads(output.getvalue()))


def style_entry(catalog, name='watercolor'):
    return next(style for style in catalog['styles'] if style['id'] == name)


def assert_prompt_instructions(test, prompt, snapshot):
    test.assertIn(snapshot['contract'], prompt)
    for field, instruction in snapshot['style']['instructions'].items():
        test.assertIn(instruction, prompt, field)
    for avoidance in snapshot['style']['negative_constraints']:
        test.assertIn(avoidance, prompt)
    for modifier in snapshot['modifiers']:
        test.assertIn(modifier['instructions'], prompt)
        for avoidance in modifier['negative_constraints']:
            test.assertIn(avoidance, prompt)
    test.assertIn(snapshot['style_notes'], prompt)


class CatalogIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = registry.load_catalog()

    def test_at_least_150_distinct_techniques_excluding_selectors_and_treatments(self):
        catalog = self.catalog
        ids = [style['id'] for style in catalog['styles']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(set(ORIGINAL_STYLES) <= set(ids))
        techniques = [style for style in catalog['styles'] if style['kind'] == 'technique']
        self.assertGreaterEqual(len(techniques), 150)
        # This catches duplicate specifications; it does not certify visual quality.
        self.assertEqual(len(techniques), len({registry.digest(s['instructions']) for s in techniques}))
        self.assertGreaterEqual(len(catalog['categories']), 13)
        self.assertEqual({s['category'] for s in catalog['styles']},
                         {c['id'] for c in catalog['categories']})
        self.assertTrue(THEMES <= {m['id'] for m in catalog['modifiers']})
        self.assertFalse(THEMES & set(ids), 'Themes must not inflate the visual-style count.')
        for palette_treatment in ('monochrome', 'duotone', 'pastel-flat', 'limited-palette-pixel-art'):
            self.assertEqual(style_entry(catalog, palette_treatment)['kind'], 'treatment')

    def test_every_entry_has_all_artistic_dimensions_and_actionable_metadata(self):
        for style in self.catalog['styles']:
            with self.subTest(style=style['id']):
                self.assertEqual(set(style['instructions']), INSTRUCTION_FIELDS)
                self.assertTrue(all(len(v.strip()) >= 20 for v in style['instructions'].values()))
                self.assertGreaterEqual(len(style['negative_constraints']), 2)
                self.assertTrue(style['use_cases'])
                self.assertTrue(style['limitations'])
                self.assertEqual(set(style['applicability']), {'character', 'sequence', 'icon', 'print', 'grid'})
                self.assertTrue(style['compatibility']['notes'])
                self.assertGreaterEqual(len(style['compatibility']['scaling']), 20)

    def test_every_requested_coverage_target_is_selectable_in_its_artistic_category(self):
        for category, targets in COVERAGE_TARGETS.items():
            for target in targets:
                with self.subTest(category=category, target=target):
                    self.assertEqual(registry.resolve_style(target)['style']['category'], category)

    def test_validation_returns_a_copy_without_modifying_the_source(self):
        source = copy.deepcopy(self.catalog)
        validated = registry.validate_catalog(source)
        self.assertEqual(validated, source)
        validated['styles'][0]['instructions']['materials'] = 'Changed only in the returned copy.'
        self.assertEqual(source, self.catalog)

    def test_structural_schema_accepts_all_catalog_documents_and_snapshots(self):
        schema = hatch.read(ROOT / 'profiles/style-catalog.schema.json')
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        for path in sorted((ROOT / 'styles').glob('*.json')):
            with self.subTest(document=path.name):
                validator.validate(hatch.read(path))
        validator.validate(self.catalog)
        for style in self.catalog['styles']:
            with self.subTest(snapshot=style['id']):
                validator.validate(registry.resolve_style(style['id']))

    def test_schema_rejects_unknown_fields_and_missing_instruction_dimensions(self):
        validator = Draft202012Validator(hatch.read(ROOT / 'profiles/style-catalog.schema.json'))
        bad = copy.deepcopy(self.catalog)
        bad['arbitrary_plugin'] = 'unapproved.py'
        self.assertFalse(validator.is_valid(bad))
        bad = copy.deepcopy(self.catalog)
        del bad['styles'][0]['instructions']['rendering']
        self.assertFalse(validator.is_valid(bad))

    def test_invalid_metadata_duplicates_aliases_and_conflicting_restrictions_are_rejected(self):
        def entry(value):
            return style_entry(value)

        mutations = [
            ('unknown root field', lambda c: c.update(executable='arbitrary.py')),
            ('unsupported schema', lambda c: c.update(schema_version=2)),
            ('boolean schema', lambda c: c.update(schema_version=True)),
            ('nonfinite schema', lambda c: c.update(schema_version=float('nan'))),
            ('invalid version', lambda c: c.update(catalog_version='latest')),
            ('duplicate category', lambda c: c['categories'].append(copy.deepcopy(c['categories'][0]))),
            ('duplicate style', lambda c: c['styles'].append(copy.deepcopy(c['styles'][0]))),
            ('unknown style field', lambda c: entry(c).update(plugin='execute.py')),
            ('unsafe ID', lambda c: entry(c).update(id='../watercolor')),
            ('unsafe text', lambda c: entry(c).update(name='Watercolor\x1b[2J')),
            ('unknown category', lambda c: entry(c).update(category='missing-category')),
            ('invalid kind', lambda c: entry(c).update(kind='theme')),
            ('missing tags', lambda c: entry(c).update(tags=[])),
            ('alias conflicts with ID', lambda c: entry(c)['aliases'].append('pixel')),
            ('duplicate aliases', lambda c: entry(c).update(aliases=['water-wash', 'water-wash'])),
            ('alias reused by styles', lambda c: [s['aliases'].append('duplicated-other-name') for s in c['styles'][:2]]),
            ('unsafe alias', lambda c: entry(c).update(aliases=['../../outside'])),
            ('missing instructions', lambda c: entry(c)['instructions'].pop('linework')),
            ('unknown instruction field', lambda c: entry(c)['instructions'].update(backend='external')),
            ('empty instruction', lambda c: entry(c)['instructions'].update(materials='')),
            ('generic repeated dimensions', lambda c: entry(c).update(instructions={k: 'Identical generic instructions for every dimension.' for k in INSTRUCTION_FIELDS})),
            ('excessive instruction', lambda c: entry(c)['instructions'].update(rendering='x' * 10000)),
            ('missing negatives', lambda c: entry(c).update(negative_constraints=[])),
            ('contradictory instructions', lambda c: entry(c)['negative_constraints'].append(entry(c)['instructions']['materials'])),
            ('missing use cases', lambda c: entry(c).update(use_cases=[])),
            ('missing limitations', lambda c: entry(c).update(limitations=[])),
            ('invalid applicability', lambda c: entry(c)['applicability'].update(grid='universal')),
            ('invalid filter', lambda c: entry(c)['compatibility'].update(resampling='magic')),
            ('hard edges with smoothing', lambda c: entry(c)['compatibility'].update(edge_mode='hard', resampling='lanczos')),
            ('required alpha permits chroma', lambda c: entry(c)['compatibility'].update(alpha='required', chroma='supported')),
            ('unsupported chroma lacks required alpha', lambda c: entry(c)['compatibility'].update(alpha='supported', chroma='unsupported')),
            ('unknown recommended modifier', lambda c: entry(c).update(recommended_modifiers=['missing-theme'])),
            ('duplicate modifier', lambda c: c['modifiers'].append(copy.deepcopy(c['modifiers'][0]))),
            ('unknown modifier conflict', lambda c: c['modifiers'][0]['conflicts'].append('missing-theme')),
            ('self-conflicting modifier', lambda c: c['modifiers'][0]['conflicts'].append(c['modifiers'][0]['id'])),
        ]
        for label, mutate in mutations:
            with self.subTest(defect=label):
                bad = copy.deepcopy(self.catalog)
                mutate(bad)
                with self.assertRaises(ValueError):
                    registry.validate_catalog(bad)

    def test_loader_rejects_duplicate_json_fields_and_unsafe_category_paths(self):
        with tempfile.TemporaryDirectory(prefix='hatch-style-invalid-') as td:
            path = Path(td) / 'catalog.json'
            path.write_text('{"schema_version":1,"schema_version":1}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'duplicate JSON'):
                registry.load_catalog(path)
            hatch.atomic(path, {'schema_version': 1, 'catalog_version': '1.0.0',
                                'categories': [{'id': '../outside', 'name': 'Invalid traversal'}]})
            with self.assertRaises(ValueError):
                registry.load_catalog(path)

    def test_loader_checks_indexed_category_identity_and_rejects_executable_metadata(self):
        with tempfile.TemporaryDirectory(prefix='hatch-style-loader-') as td:
            root = Path(td)
            style = copy.deepcopy(style_entry(self.catalog))
            category = next(c for c in self.catalog['categories'] if c['id'] == style['category'])
            index = {'schema_version': 1, 'catalog_version': '1.0.0', 'categories': [category]}
            category_path = root / (category['id'] + '.json')
            hatch.atomic(root / 'catalog.json', index)
            hatch.atomic(root / 'modifiers.json', {'schema_version': 1, 'modifiers': self.catalog['modifiers']})
            hatch.atomic(category_path, {'schema_version': 1, 'category': category['id'], 'styles': [style]})
            self.assertEqual(registry.load_catalog(root / 'catalog.json')['styles'], [style])
            hatch.atomic(category_path, {'schema_version': 1, 'category': 'different-category', 'styles': [style]})
            with self.assertRaisesRegex(ValueError, 'category file does not match'):
                registry.load_catalog(root / 'catalog.json')
            hatch.atomic(category_path, {'schema_version': 1, 'category': category['id'], 'styles': [style],
                                        'loader': 'unapproved-backend.py'})
            with self.assertRaisesRegex(ValueError, 'unknown fields'):
                registry.load_catalog(root / 'catalog.json')

    def test_loader_rejects_directories_and_symlinks_before_reading_json(self):
        with tempfile.TemporaryDirectory(prefix='hatch-style-file-kinds-') as td:
            root = Path(td)
            directory = root / 'directory.json'
            directory.mkdir()
            target = root / 'regular.json'
            target.write_text('{}', encoding='utf-8')
            link = root / 'symlink.json'
            link.symlink_to(target)
            for path in (directory, link):
                with self.subTest(kind=path.name), self.assertRaisesRegex(ValueError, 'regular JSON file'):
                    registry.load_catalog(path)

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'Named pipes are not available on this platform.')
    def test_loader_rejects_named_pipes_without_blocking(self):
        with tempfile.TemporaryDirectory(prefix='hatch-style-fifo-') as td:
            fifo = Path(td) / 'catalog.json'
            os.mkfifo(fifo)
            script = dedent('''
                import sys
                sys.path.insert(0, sys.argv[1])
                import style_registry
                try:
                    style_registry.load_catalog(sys.argv[2])
                except ValueError as error:
                    assert 'regular JSON file' in str(error), str(error)
                else:
                    raise AssertionError('Named pipes must never be read as catalog data.')
            ''')
            # Bound the child process: a regression that opens a FIFO must fail
            # this test rather than block the complete test suite indefinitely.
            result = subprocess.run([sys.executable, '-c', script, str(ROOT / 'scripts'), str(fifo)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_catalog_categories_reject_reserved_com_and_lpt_device_filenames(self):
        with tempfile.TemporaryDirectory(prefix='hatch-style-device-names-') as td:
            path = Path(td) / 'catalog.json'
            for prefix in ('com', 'lpt'):
                for number in range(1, 10):
                    reserved = prefix + str(number)
                    with self.subTest(category=reserved):
                        hatch.atomic(path, {'schema_version': 1, 'catalog_version': '1.0.0',
                                            'categories': [{'id': reserved, 'name': 'Reserved device filename'}]})
                        with self.assertRaisesRegex(ValueError, 'reserved category filename'):
                            registry.load_catalog(path)
                        bad = copy.deepcopy(self.catalog)
                        bad['categories'][0]['id'] = reserved
                        with self.assertRaisesRegex(ValueError, 'reserved category filename'):
                            registry.validate_catalog(bad)

    def test_cross_stitch_documents_disconnected_component_extraction_requirements(self):
        style = style_entry(self.catalog, 'cross-stitch')
        self.assertEqual(style['applicability']['character'], 'adapted')
        self.assertEqual(style['applicability']['sequence'], 'adapted')
        guidance = ' '.join(style['limitations'] + style['compatibility']['notes']).lower()
        for term in ('disconnected', 'source-bound', 'annotations', 'validation gates'):
            self.assertIn(term, guidance)


class StyleResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = registry.load_catalog()

    def test_every_alias_selects_the_same_full_entry_without_inflating_counts(self):
        for entry in self.catalog['styles']:
            for alias in entry['aliases']:
                with self.subTest(style=entry['id'], alias=alias):
                    selected = registry.resolve_style(alias, context='')
                    canonical = registry.resolve_style(entry['id'], context='')
                    self.assertEqual(selected['style'], canonical['style'])
                    self.assertEqual(selected['resolved_id'], canonical['resolved_id'])
                    self.assertEqual(selected['requested_id'], alias)
        self.assertEqual(set(preparation.STYLE_PRESETS), {s['id'] for s in self.catalog['styles']})

    def test_auto_uses_artistic_cues_and_preserves_reference_and_brand_paths(self):
        selected = registry.resolve_style('auto', context='A watercolor otter with broad washes.')
        self.assertEqual(selected['resolved_id'], 'watercolor')
        self.assertEqual(selected['requested_id'], 'auto')
        self.assertEqual(selected['selection']['method'], 'auto-keyword')
        no_cue = registry.resolve_style('auto')
        self.assertEqual(no_cue['resolved_id'], 'flat-vector')
        reference = registry.resolve_style('auto', has_references=True)
        self.assertEqual(reference['selection']['method'], 'reference-guided')
        self.assertIn('reference', reference['contract'].lower())
        branded = registry.resolve_style('auto', has_brand=True)
        self.assertEqual(branded['resolved_id'], 'brand-inspired')
        avoided = registry.resolve_style('auto', context='Avoid watercolor; preserve the supplied identity.')
        self.assertNotEqual(avoided['resolved_id'], 'watercolor')

    def test_explicit_avoidances_override_auto_keywords_and_default_style(self):
        for style_id in ('watercolor', 'flat-vector'):
            entry = style_entry(self.catalog, style_id)
            for spelling in (entry['id'], entry['name'], *entry['aliases']):
                with self.subTest(style=style_id, spelling=spelling):
                    selected = registry.resolve_style('auto', context=entry['name'] + ' mascot.',
                                                      avoidances=[spelling])
                    self.assertNotEqual(selected['resolved_id'], style_id)
                    self.assertIn(selected['resolved_id'], {s['id'] for s in self.catalog['styles']})
                    registry.validate_snapshot(selected)
                    if style_id == 'flat-vector':
                        default = registry.resolve_style('auto', avoidances=(spelling,))
                        self.assertNotEqual(default['resolved_id'], 'flat-vector')
        selected = registry.resolve_style('auto', context='Watercolor mascot.',
                                          avoidances=['watercolour', 'flat-vector', 'sticker', 'plush', 'pixel'])
        self.assertNotIn(selected['resolved_id'], {'watercolor', 'flat-vector', 'sticker', 'plush', 'pixel'})

    def test_conflicting_explicit_styles_fail_with_avoidance_guidance(self):
        for style_id in ('watercolor', 'flat-vector'):
            entry = style_entry(self.catalog, style_id)
            for selector in (entry['id'], *entry['aliases']):
                for avoidance in (entry['id'], entry['name'], *entry['aliases']):
                    with self.subTest(selector=selector, avoidance=avoidance):
                        with self.assertRaisesRegex(ValueError, 'explicit avoidance.*--style-preset.*--avoid'):
                            registry.resolve_style(selector, avoidances=(avoidance,))

    def test_preparation_applies_explicit_style_avoidances_before_writing_a_run(self):
        with tempfile.TemporaryDirectory(prefix='hatch-style-avoidance-') as td:
            root = Path(td) / 'allowed'
            request, _, _ = run_preparer(root, 'auto', extra=('--avoid', 'watercolour',
                            '--avoid', 'flat-vector', '--pet-notes', 'A watercolor otter.'))
            self.assertNotIn(request['resolved_style']['resolved_id'], {'watercolor', 'flat-vector'})
            self.assertTrue({'watercolour', 'flat-vector'} <= set(request['constraints']['avoid']))
            for path in (root / 'prompts').rglob('*.md'):
                assert_prompt_instructions(self, path.read_text(encoding="utf-8"), request['resolved_style'])
                self.assertIn('watercolour', path.read_text(encoding="utf-8"))
            rejected = Path(td) / 'rejected'
            with self.assertRaisesRegex(ValueError, 'explicit avoidance'):
                run_preparer(rejected, 'watercolor', extra=('--avoid', 'watercolour'))
            self.assertFalse(rejected.exists())

    def test_every_modifier_and_alias_is_composable_and_separate_from_style(self):
        for modifier in self.catalog['modifiers']:
            for spelling in [modifier['id'], *modifier['aliases']]:
                with self.subTest(modifier=spelling):
                    resolved = registry.resolve_style('flat-vector', modifiers=[spelling])
                    self.assertEqual(resolved['resolved_id'], 'flat-vector')
                    self.assertEqual(resolved['modifiers'], [modifier])
                    self.assertIn(modifier['instructions'], resolved['contract'])
                    self.assertTrue(all(n in resolved['contract'] for n in modifier['negative_constraints']))

    def test_unknown_styles_modifiers_duplicate_selection_and_conflicts_fail_clearly(self):
        with self.assertRaisesRegex(ValueError, 'unknown style.*styles --search'):
            registry.resolve_style('style-that-is-not-installed')
        with self.assertRaisesRegex(ValueError, 'unknown modifier'):
            registry.resolve_style('pixel', modifiers=['unavailable-theme'])
        with self.assertRaisesRegex(ValueError, 'duplicate modifier'):
            registry.resolve_style('pixel', modifiers=['cozy', 'cozy'])
        with self.assertRaisesRegex(ValueError, 'at most four'):
            registry.resolve_style('pixel', modifiers=list(THEMES)[:5])
        conflicting = copy.deepcopy(self.catalog)
        left, right = conflicting['modifiers'][:2]
        left['conflicts'] = [right['id']]
        right['conflicts'] = [left['id']]
        registry.validate_catalog(conflicting)
        with self.assertRaisesRegex(ValueError, 'conflicting modifiers'):
            registry.resolve_style('pixel', modifiers=[left['id'], right['id']], catalog=conflicting)

    def test_snapshot_is_complete_independent_and_hash_bound(self):
        source = copy.deepcopy(self.catalog)
        snapshot = registry.resolve_style('watercolor', notes='Keep the approved violet markings.',
                                          modifiers=['cozy'], catalog=source)
        self.assertEqual(snapshot['catalog_sha256'], registry.digest(source))
        self.assertEqual(snapshot['sha256'], registry.digest({k: v for k, v in snapshot.items() if k != 'sha256'}))
        self.assertEqual(registry.validate_snapshot(snapshot), snapshot)
        source['styles'][0]['description'] = 'Changed in a future catalog; frozen runs retain the old data.'
        self.assertNotEqual(snapshot['catalog_sha256'], registry.digest(source))
        self.assertEqual(registry.validate_snapshot(snapshot), snapshot)
        self.assertIn('take precedence', snapshot['contract'])
        self.assertIn('Keep the approved violet markings.', snapshot['contract'])
        for field in ('contract', 'style_notes', 'catalog_version', 'resolved_id'):
            with self.subTest(tampered=field):
                bad = copy.deepcopy(snapshot)
                bad[field] += '-tampered'
                with self.assertRaises(ValueError):
                    registry.validate_snapshot(bad)
        bad = copy.deepcopy(snapshot)
        bad['style']['instructions']['plugin'] = 'Do not accept arbitrary executable hooks.'
        bad['sha256'] = registry.digest({k: v for k, v in bad.items() if k != 'sha256'})
        with self.assertRaises(ValueError):
            registry.validate_snapshot(bad)

    def test_unsafe_or_excessive_user_notes_are_rejected_before_generation(self):
        for notes in ('hidden\x00instruction', 'erase\x1b[2Jterminal', 'x' * 4001):
            with self.subTest(notes_length=len(notes)), self.assertRaises(ValueError):
                registry.resolve_style('watercolor', notes=notes)

    def test_new_declarative_entry_reaches_preparation_without_generation_code_changes(self):
        catalog = copy.deepcopy(self.catalog)
        new = copy.deepcopy(style_entry(catalog))
        new.update(id='fixture-brush-study', name='Fixture brush study', aliases=[])
        new['instructions']['rendering'] = 'Render broad interlocking brush planes with stable clipped wet edges and a clear closed silhouette.'
        catalog['styles'].append(new)
        registry.validate_catalog(catalog)
        with tempfile.TemporaryDirectory(prefix='hatch-added-style-') as td, \
                patch.object(registry, '_installed_catalog', return_value=catalog):
            request, _, _ = run_preparer(Path(td) / 'run', new['id'])
            self.assertEqual(request['resolved_style']['style'], new)
            assert_prompt_instructions(self, (Path(td) / 'run/prompts/base-pet.md').read_text(encoding="utf-8"),
                                       request['resolved_style'])


class PreparedStyleTests(unittest.TestCase):
    """One independently reported preparation test for every registered visual style."""

    def check_style(self, entry):
        with tempfile.TemporaryDirectory(prefix='hatch-prepared-style-') as td:
            root = Path(td) / 'run'
            request, jobs, result = run_preparer(root, entry['id'])
            snapshot = request['resolved_style']
            registry.validate_snapshot(snapshot)
            self.assertTrue(result['ok'])
            self.assertEqual(request['schema_version'], 3)
            self.assertEqual(snapshot['requested_id'], entry['id'])
            self.assertEqual(request['style_contract'], snapshot['contract'])
            expected = load_profile()
            self.assertEqual(load_profile(root / 'profile.json'), expected)
            self.assertEqual(request['atlas'], expected['layout'])
            self.assertEqual((expected['layout']['columns'], expected['layout']['cell_width'],
                              expected['layout']['cell_height'], expected['layout']['rows']), (8, 192, 208, 9))
            self.assertEqual(len(jobs['jobs']), 10)
            self.assertEqual([row['frames'] for row in request['rows']], [6, 8, 8, 4, 5, 8, 6, 6, 6])
            for path in sorted((root / 'prompts').rglob('*.md')):
                prompt = path.read_text(encoding='utf-8')
                with self.subTest(prompt=path.relative_to(root).as_posix()):
                    assert_prompt_instructions(self, prompt, snapshot)
                    self.assertIn('installed imagegen skill', prompt)
                    self.assertLess(len(prompt), 25000, 'A single selected style should not expand the entire catalog into prompts.')
            self.assertEqual(len(list((root / 'prompts').rglob('*.md'))), 19)
            for state in expected['states']:
                self.assertTrue((root / f"references/layout-guides/{state['id']}.png").is_file())
            for job in jobs['jobs'][1:]:
                self.assertEqual(job['generation_skill'], '$imagegen')
                self.assertEqual(job['depends_on'], ['base'])
                self.assertIn('references/canonical-base.png', [ref['path'] for ref in job['input_images']])


class OriginalPresetCompatibilityTests(unittest.TestCase):
    def test_legacy_style_presets_interface_is_an_ordinary_cached_dictionary(self):
        mapping = preparation.STYLE_PRESETS
        self.assertIs(type(mapping), dict)
        self.assertIs(mapping, preparation.STYLE_PRESETS)
        self.assertTrue(set(ORIGINAL_STYLES) <= set(mapping))

    def check_original(self, style):
        self.assertIn(style, preparation.STYLE_PRESETS)
        self.assertIsInstance(preparation.STYLE_PRESETS[style], str)
        contract = preparation.resolved_style_contract(style, 'Preserve the approved small nose.')
        self.assertIsInstance(contract, str)
        self.assertIn('Preserve the approved small nose.', contract)
        snapshot = registry.resolve_style(style)
        self.assertIn(snapshot['resolved_id'], preparation.STYLE_PRESETS)
        self.assertTrue(snapshot['contract'])


class ProfileStyleCompatibilityTests(unittest.TestCase):
    def check_profile(self, path):
        with tempfile.TemporaryDirectory(prefix='hatch-style-profile-') as td:
            root = Path(td) / 'run'
            request, _, _ = run_preparer(root, 'watercolor', path)
            expected = load_profile(path)
            self.assertEqual(load_profile(root / 'profile.json'), expected)
            snapshot = request['resolved_style']
            for prompt_path in (root / 'prompts').rglob('*.md'):
                prompt = prompt_path.read_text(encoding='utf-8')
                assert_prompt_instructions(self, prompt, snapshot)
                self.assertIn(expected['generation']['instructions'], prompt)
            for state in expected['states']:
                prompt = (root / f"prompts/rows/{state['id']}.md").read_text(encoding='utf-8')
                self.assertIn(state['purpose'], prompt)
                self.assertIn(f"exactly {state['frames']} complete poses", prompt)

    def test_alpha_chroma_and_resampling_warnings_are_actionable_and_do_not_mutate_profiles(self):
        profile = small_profile()
        original = copy.deepcopy(profile)
        pixel = registry.resolve_style('pixel')
        warnings = registry.compatibility_warnings(pixel, profile, 'alpha', resampling='lanczos')
        self.assertTrue(any('resampling differs' in w and 'nearest' in w for w in warnings))
        exact = registry.compatibility_warnings(pixel, profile, 'alpha', resampling='nearest')
        self.assertFalse(any('resampling differs' in w for w in exact))
        watercolor = registry.resolve_style('watercolor')
        warnings = registry.compatibility_warnings(watercolor, profile, 'alpha', resampling='nearest')
        self.assertTrue(any('resampling differs' in w for w in warnings))
        self.assertTrue(any('GIF' in w for w in warnings))
        self.assertEqual(profile, original)
        for style in registry.load_catalog()['styles']:
            if style['compatibility']['chroma'] != 'supported':
                with self.subTest(chroma=style['id']):
                    # Exercise auto's reference-preserving guidance here; without
                    # references it correctly resolves to the flat-vector default.
                    snapshot = registry.resolve_style(style['id'], has_references=style['id'] == 'auto')
                    warnings = registry.compatibility_warnings(snapshot, profile, 'chroma')
                    self.assertTrue(any('chroma is ' + style['compatibility']['chroma'] in w and '--background alpha' in w for w in warnings))
                    self.assertFalse(any('chroma is ' in w for w in registry.compatibility_warnings(snapshot, profile, 'alpha')))

    def test_explicit_profile_filters_win_and_grid_limitations_are_reported(self):
        profile = load_profile(ROOT / 'presets/craft.json')
        before = copy.deepcopy(profile)
        snapshot = registry.resolve_style('watercolor')
        warnings = registry.compatibility_warnings(snapshot, profile, 'alpha')
        self.assertTrue(any('resampling differs' in w for w in warnings))
        self.assertTrue(any('craft' in w or 'grid' in w for w in warnings))
        self.assertEqual(profile, before)

    def test_effective_extraction_filter_uses_saved_style_fallback_and_preserves_legacy_defaults(self):
        from extract_strip_frames import extraction_configuration, load_extraction_config
        with tempfile.TemporaryDirectory(prefix='hatch-style-filter-') as td:
            root = Path(td) / 'run'
            request, _, _ = run_preparer(root, 'pixel')
            profile = load_profile(root / 'profile.json')
            config = load_extraction_config(root)
            self.assertEqual(extraction_configuration(profile, 'idle', config)['resampling'], 'nearest')
            profile['states'][0]['alignment']['resampling'] = 'bicubic'
            self.assertEqual(extraction_configuration(profile, 'idle', config)['resampling'], 'bicubic')
            # An old request without a style filter keeps the original Lanczos default.
            profile['states'][0]['alignment'].pop('resampling')
            request['extraction'].pop('resampling')
            hatch.atomic(root / 'pet_request.json', request)
            historical = load_extraction_config(root)
            self.assertEqual(extraction_configuration(profile, 'idle', historical)['resampling'], 'lanczos')
            self.assertEqual(profile['layout']['cell_width'], 192)
            self.assertEqual(profile['layout']['cell_height'], 208)

    def test_invalid_json_resampling_types_raise_actionable_value_errors(self):
        from extract_strip_frames import load_extraction_config
        with tempfile.TemporaryDirectory(prefix='hatch-style-invalid-filter-') as td:
            root = Path(td)
            values = (None, [], {}, True, False, 0, 1, 1.5, ['nearest'], {'filter': 'nearest'})
            for source in ('request', 'settings'):
                for value in values:
                    with self.subTest(source=source, resampling=value):
                        hatch.atomic(root / 'pet_request.json',
                                     {'extraction': {'resampling': value}} if source == 'request' else {})
                        hatch.atomic(root / 'extraction-settings.json',
                                     {'resampling': value} if source == 'settings' else {})
                        with self.assertRaisesRegex(ValueError, 'resampling'):
                            load_extraction_config(root)


class StyleDiscoveryTests(unittest.TestCase):
    def test_cli_outputs_utf8_with_a_legacy_host_encoding(self):
        env = dict(os.environ, PYTHONIOENCODING='cp1252')
        for arguments in (('styles', '--json'), ('style', '--style-preset', 'watercolor')):
            with self.subTest(arguments=arguments):
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/hatch.py'), *arguments],
                                        capture_output=True, env=env, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8'))
                text = result.stdout.decode('utf-8')
                if arguments[0] == 'styles':
                    self.assertEqual(json.loads(text)['styles'], registry.load_catalog()['styles'])
                else:
                    self.assertIn('Watercolor', text)

    def cli(self, *args, good=True):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/hatch.py'), *args],
                                capture_output=True, text=True, encoding='utf-8')
        if good:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_public_listing_exposes_all_entries_and_independent_counts_without_run(self):
        catalog = registry.load_catalog()
        value = json.loads(self.cli('styles', '--json').stdout)
        self.assertEqual(value['matched'], len(catalog['styles']))
        self.assertEqual(value['styles'], catalog['styles'])
        self.assertEqual(value['counts']['selectable'], len(catalog['styles']))
        self.assertEqual(value['counts']['techniques'], sum(s['kind'] == 'technique' for s in catalog['styles']))
        self.assertEqual(value['catalog_sha256'], registry.digest(catalog))
        self.assertEqual(sum(c['count'] for c in value['categories']), len(catalog['styles']))
        human = self.cli('styles').stdout
        for original in ORIGINAL_STYLES:
            self.assertIn(original, human)

    def test_search_matches_keywords_names_aliases_and_categories(self):
        catalog = registry.load_catalog()
        for category in catalog['categories']:
            with self.subTest(category=category['id']):
                value = json.loads(self.cli('styles', '--category', category['id'], '--json').stdout)
                expected = [s for s in catalog['styles'] if s['category'] == category['id']]
                self.assertEqual(value['styles'], expected)
        for query in ('watercolor', 'Watercolor', 'water', 'painting'):
            with self.subTest(search=query):
                value = json.loads(self.cli('styles', '--search', query, '--json').stdout)
                self.assertGreater(value['matched'], 0)
        value = json.loads(self.cli('styles', '--search', 'no-such-style-zzzz', '--json').stdout)
        self.assertEqual(value['matched'], 0)
        self.assertEqual(value['styles'], [])
        self.cli('styles', '--category', '../invalid', '--json', good=False)

    def test_style_detail_and_modifier_discovery_expose_full_metadata(self):
        catalog = registry.load_catalog()
        style = style_entry(catalog)
        value = json.loads(self.cli('style', '--style-preset', style['id'], '--json').stdout)
        self.assertEqual(value['style'], style)
        human = self.cli('style', '--style-preset', style['id']).stdout
        for instruction in style['instructions'].values():
            self.assertIn(instruction, human)
        self.assertIn('Compatibility', human)
        modifiers = json.loads(self.cli('style-modifiers', '--json').stdout)
        self.assertEqual(modifiers['modifiers'], catalog['modifiers'])
        self.assertIn('--style-modifier', self.cli('style-modifiers').stdout)
        missing = self.cli('style', '--style-preset', 'unavailable-style', '--json', good=False)
        self.assertIn('unknown style', missing.stderr)

    def test_auto_detail_warnings_describe_the_displayed_auto_entry(self):
        value = json.loads(self.cli('style', '--style-preset', 'auto', '--profile',
                                   str(ROOT / 'profiles/codex-v1.json'),
                                   '--background', 'chroma', '--json').stdout)
        self.assertEqual(value['style']['id'], 'auto')
        self.assertEqual(value['style']['compatibility']['chroma'], 'caution')
        self.assertTrue(any('auto: chroma is caution' in warning for warning in value['warnings']))
        self.assertFalse(any('flat-vector' in warning for warning in value['warnings']))

    def test_controller_preserves_style_flags_and_unknown_style_does_not_create_run(self):
        with tempfile.TemporaryDirectory(prefix='hatch-style-cli-') as td:
            root = Path(td) / 'run'
            self.cli('prepare', '--run-dir', str(root), '--pet-name', 'Fixture',
                     '--style-preset', 'watercolor', '--style-modifier', 'cozy',
                     '--style-modifier', 'botanical', '--style-notes', 'Keep the approved small nose.')
            request = hatch.read(root / 'pet_request.json')
            self.assertEqual(request['resolved_style']['resolved_id'], 'watercolor')
            self.assertEqual([m['id'] for m in request['resolved_style']['modifiers']], ['cozy', 'botanical'])
            self.assertEqual(request['resolved_style']['style_notes'], 'Keep the approved small nose.')
            missing = Path(td) / 'unwritten'
            with redirect_stderr(io.StringIO()), self.assertRaises((ValueError, SystemExit)):
                run_preparer(missing, 'unavailable-style')
            self.assertFalse(missing.exists())

    def test_explicit_chroma_mode_produces_a_warning_without_silently_switching_generation(self):
        required_alpha = next(s for s in registry.load_catalog()['styles']
                              if s['compatibility']['chroma'] == 'unsupported')
        with tempfile.TemporaryDirectory(prefix='hatch-style-chroma-') as td:
            root = Path(td) / 'run'
            self.cli('prepare', '--run-dir', str(root), '--pet-name', 'Fixture',
                     '--style-preset', required_alpha['id'], '--background', 'chroma',
                     '--chroma-key', '#00FF00')
            handoff = json.loads(self.cli('claim', '--run-dir', str(root), '--job', 'base').stdout)
            self.assertFalse(handoff['tool_arguments']['transparent_background'])
            self.assertTrue(any('chroma is unsupported' in w and '--background alpha' in w
                                for w in handoff['style_warnings']))
            request = hatch.read(root / 'pet_request.json')
            self.assertEqual(request['extraction']['background'], 'chroma')
            self.assertEqual(request['atlas']['cell_width'], 192)


class FrozenStyleLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='hatch-style-lifecycle-')
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.root = self.home / 'run'

    def test_catalog_changes_cannot_restyle_retries_repairs_resume_or_archives(self):
        data = build_run(self.root, validate=False)
        request_bytes = (self.root / 'pet_request.json').read_bytes()
        snapshot = hatch.read(self.root / 'pet_request.json')['resolved_style']
        for job in data['jobs']:
            claims = [e for e in job['history'] if e['event'] == 'claim']
            self.assertTrue(claims)
            self.assertEqual(claims[-1]['resolved_style'], snapshot)
        with patch.object(registry, '_installed_catalog', side_effect=AssertionError('A saved run must not reload the installed catalog.')):
            hatch.repair(self.root, data, 'jump', 'Retain the white left ear while fixing the landing.')
            first = hatch.claim(self.root, data, 'jump')
            self.assertEqual(first['resolved_style'], snapshot)
            hatch.fail(self.root, data, 'jump', first['token'], 'Synthetic failed attempt, no production call.')
            second = hatch.claim(self.root, data, 'jump')
            self.assertEqual(second['resolved_style'], snapshot)
            self.assertIn('row-retries', second['prompt'])
            assert_prompt_instructions(self, Path(second['prompt']).read_text(encoding="utf-8"), snapshot)
            resumed = hatch.resume(self.root, data)
            self.assertEqual(resumed['claims'][0]['token'], second['token'])
            self.assertEqual(hatch.job_for(data, 'jump')['history'][-1]['resolved_style'], snapshot)
            hatch.fail(self.root, data, 'jump', second['token'], 'Reconcile synthetic attempt before archival.')
            archive = self.home / 'frozen.zip'
            archive_run(self.root, data, archive)
            restored = self.home / 'restored'
            restore_run(archive, restored)
            self.assertEqual((restored / 'pet_request.json').read_bytes(), request_bytes)
            restored_data = hatch.manifest(restored)
            self.assertEqual(restored_data['run_id'], data['run_id'])
            self.assertEqual(hatch.read(restored / 'pet_request.json')['resolved_style'], snapshot)
            for path in (self.root / 'prompts').rglob('*.md'):
                self.assertEqual(path.read_bytes(), (restored / path.relative_to(self.root)).read_bytes())

    def test_fresh_process_loads_and_configures_saved_run_without_installed_catalog(self):
        build_run(self.root, validate=False)
        original = (self.root / 'pet_request.json').read_bytes()
        snapshot = hatch.read(self.root / 'pet_request.json')['resolved_style']
        script = dedent('''
            import argparse
            import json
            from pathlib import Path
            import sys
            sys.path.insert(0, sys.argv[1])
            import style_registry
            def unavailable_catalog():
                raise AssertionError('Saved runs must not load the active style catalog.')
            style_registry._installed_catalog = unavailable_catalog
            assert 'prepare_pet_run' not in sys.modules
            import prepare_pet_run
            import hatch
            from profile_spec import load_profile
            root = Path(sys.argv[2])
            original = (root / 'pet_request.json').read_bytes()
            request = hatch.read(root / 'pet_request.json')
            profile = load_profile(root / 'profile.json')
            settings = hatch.read(root / 'extraction-settings.json')
            paths = prepare_pet_run.regenerate_prompts(root, request, profile, settings, include_base=True)
            assert 'prompts/base-pet.md' in paths
            assert any('/row-retries/' in path for path in paths)
            data = hatch.manifest(root)
            configured = hatch.configure(root, data, argparse.Namespace(
                background='chroma', holes=None, shared_scale=None,
                key_threshold=None, chroma_key='#0000FF'))
            assert 'background' in configured['changed']
            assert (root / 'pet_request.json').read_bytes() == original
            snapshot = request['resolved_style']
            assert hatch.manifest(root)['style_sha256'] == snapshot['sha256']
            for path in paths:
                assert snapshot['contract'] in (root / path).read_text(encoding='utf-8'), path
            print(json.dumps({'sha256': snapshot['sha256'], 'regenerated': paths}))
        ''')
        result = subprocess.run([sys.executable, '-c', script, str(ROOT / 'scripts'), str(self.root)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['sha256'], snapshot['sha256'])
        self.assertEqual((self.root / 'pet_request.json').read_bytes(), original)
        for path in (self.root / 'prompts').rglob('*.md'):
            assert_prompt_instructions(self, path.read_text(encoding="utf-8"), snapshot)

    def test_configure_and_generation_profile_revisions_keep_frozen_contract_and_user_constraints(self):
        data = build_run(self.root, validate=False)
        request = hatch.read(self.root / 'pet_request.json')
        snapshot = request['resolved_style']
        original = (self.root / 'pet_request.json').read_bytes()
        hatch.repair(self.root, data, 'jump', 'Retain the left ear and repair only the landing.')
        with patch.object(registry, '_installed_catalog', side_effect=AssertionError('Catalog changed after preparation.')):
            hatch.configure(self.root, data, argparse.Namespace(background='chroma', holes=None,
                            shared_scale=None, key_threshold=None, chroma_key='#0000FF'))
            profile = load_profile(self.root / 'profile.json')
            profile['states'][1]['purpose'] += '; retain the original approved landing pose'
            revised = self.home / 'revised-profile.json'
            hatch.atomic(revised, profile)
            hatch.revise_profile(self.root, data, revised)
        self.assertEqual((self.root / 'pet_request.json').read_bytes(), original)
        for folder in ('rows', 'row-retries'):
            prompt = (self.root / f'prompts/{folder}/jump.md').read_text(encoding="utf-8")
            assert_prompt_instructions(self, prompt, snapshot)
            for value in ('red body', 'glitter', 'Retain the left ear', '#0000FF', 'original approved landing pose'):
                self.assertIn(value, prompt)

    def test_resampling_configuration_reextracts_without_regeneration_and_requires_fresh_review(self):
        data = build_run(self.root)
        record_fixture_review(self.root, data)
        before = {job['id']: {'receipt': copy.deepcopy(job['generation_receipt']),
                              'output': job['output_hash'], 'attempts': job['attempts']}
                  for job in data['jobs']}
        request = (self.root / 'pet_request.json').read_bytes()
        result = hatch.configure(self.root, data, argparse.Namespace(resampling='nearest', chroma_key=None))
        self.assertIn('resampling', result['changed'])
        self.assertFalse(result['model_call_required'])
        self.assertEqual(result['pending'], [])
        self.assertEqual([j['status'] for j in data['jobs']], ['generated'] * 3)
        self.assertFalse(hatch.status(self.root, data)['reviewed'])
        self.assertEqual((self.root / 'pet_request.json').read_bytes(), request)
        for job in data['jobs']:
            self.assertEqual(job['generation_receipt'], before[job['id']]['receipt'])
            self.assertEqual(job['output_hash'], before[job['id']]['output'])
            self.assertEqual(job['attempts'], before[job['id']]['attempts'])
        hatch.record_base_review(self.root, data, 'Synthetic changed-filter review checkpoint only.', True)
        hatch.validate(self.root, data)
        rows = hatch.read(self.root / 'frames/frames-manifest.json')['rows']
        self.assertTrue(all(row['settings']['configuration']['resampling'] == 'nearest' for row in rows))
        self.assertFalse(hatch.status(self.root, data)['reviewed'])

    def test_legacy_saved_contract_is_used_without_adding_a_snapshot_or_migrating(self):
        request, _, _ = run_preparer(self.root, 'plush')
        request.pop('resolved_style')
        request['style_preset'] = 'historical-removed-style'
        request['style_contract'] = 'Historical style specification: felt surface, violet seams, fixed broad stitched eyes.'
        hatch.atomic(self.root / 'pet_request.json', request)
        original = (self.root / 'pet_request.json').read_bytes()
        with patch.object(registry, '_installed_catalog', side_effect=AssertionError('Historical style must be read from the run.')):
            preparation.regenerate_prompts(self.root, request, load_profile(), request['extraction'], include_base=True)
        self.assertEqual((self.root / 'pet_request.json').read_bytes(), original)
        for path in (self.root / 'prompts').rglob('*.md'):
            self.assertIn(request['style_contract'], path.read_text(encoding="utf-8"))

    def test_historical_controller_manifest_without_style_metadata_still_resumes(self):
        hatch.prepare(self.root, argparse.Namespace(replace_inputs=False, fixture_mode=True,
                      pet_name='Legacy fixture', pet_notes='An unchanged historical fixture identity.',
                      reference=[], require=[], avoid=[], brand_source=[]))
        request = hatch.read(self.root / 'pet_request.json')
        for key in ('resolved_style', 'style_modifiers', 'style_warnings'):
            request.pop(key, None)
        request['extraction'].pop('resampling', None)
        request['style_contract'] = 'Historical flat-vector contract retained verbatim.'
        hatch.atomic(self.root / 'pet_request.json', request)
        data = hatch.read(self.root / 'imagegen-jobs.json')
        data.pop('style_sha256', None)
        hatch.save(self.root, data)
        original = (self.root / 'pet_request.json').read_bytes()
        with patch.object(registry, '_installed_catalog', side_effect=AssertionError('No catalog lookup is needed for historical resume.')):
            checked = hatch.manifest(self.root)
            resumed = hatch.resume(self.root, checked)
        self.assertEqual(checked['schema_version'], 3)
        self.assertEqual(resumed['run_id'], data['run_id'])
        self.assertEqual(resumed['status'], 'pending')
        self.assertEqual((self.root / 'pet_request.json').read_bytes(), original)

    def test_imports_keep_original_pixels_and_origin_while_style_remains_requested_guidance(self):
        data = build_run(self.root, validate=False)
        original_request = (self.root / 'pet_request.json').read_bytes()
        hatch.repair(self.root, data, 'base', 'Use explicitly imported fixture art, preserving its existing rendering.')
        for name in ('base', 'rest', 'jump'):
            descriptor = self.home / ('import-' + name + '.json')
            source = self.home / 'fixture-sources' / (name + '.png')
            source_bytes = source.read_bytes()
            hatch.atomic(descriptor, {'schema_version': 1, 'kind': 'import',
                         'layout': 'image' if name == 'base' else 'strip',
                         'files': [str(source)], 'origin': 'Explicit synthetic fixture import; no imagegen output.', 'fixture': True})
            result = import_source(self.root, data, name, descriptor, 'Synthetic import-origin regression only.')
            job = hatch.job_for(data, name)
            self.assertFalse(result['imagegen_output'])
            self.assertEqual(job['source_origin'], 'import')
            self.assertNotIn('generation_receipt', job)
            self.assertNotIn('model_call', job)
            self.assertEqual(source.read_bytes(), source_bytes)
            with Image.open(source) as before, Image.open(self.root / job['output_path']) as after:
                self.assertEqual(before.convert('RGBA').tobytes(), after.convert('RGBA').tobytes())
            if name == 'base':
                prompt = (self.root / 'prompts/rows/rest.md').read_text(encoding="utf-8").lower()
                self.assertIn('import', prompt)
                hatch.record_base_review(self.root, data, 'Synthetic imported base review gate exercise only.', True)
        hashes = {j['id']: hatch.digest(self.root / j['output_path']) for j in data['jobs']}
        hatch.configure(self.root, data, argparse.Namespace(background='chroma', holes=None,
                        shared_scale=None, key_threshold=None, chroma_key='#0000FF'))
        self.assertEqual([j['status'] for j in data['jobs']], ['generated'] * 3)
        self.assertEqual({j['id']: hatch.digest(self.root / j['output_path']) for j in data['jobs']}, hashes)
        self.assertEqual((self.root / 'pet_request.json').read_bytes(), original_request)

    def test_import_origin_cannot_be_relabelled_as_imagegen_with_unchanged_receipts_and_review(self):
        data = build_run(self.root, validate=False)
        hatch.repair(self.root, data, 'rest', 'Replace this state with an explicitly imported synthetic fixture.')
        descriptor = self.home / 'import-rest.json'
        source = self.home / 'fixture-sources/rest.png'
        hatch.atomic(descriptor, {'schema_version': 1, 'kind': 'import', 'layout': 'strip',
                                 'files': [str(source)], 'fixture': True,
                                 'origin': 'Synthetic imported fixture; not imagegen artwork.'})
        import_source(self.root, data, 'rest', descriptor, 'Fixture origin-label tamper regression only.')
        hatch.validate(self.root, data)
        record_fixture_review(self.root, data)
        job = hatch.job_for(data, 'rest')
        original_receipt = copy.deepcopy(job['import_receipt'])
        original_review = (self.root / 'qa/visual-review.json').read_bytes()
        self.assertTrue(hatch.status(self.root, data)['reviewed'])
        self.assertEqual(hatch.style_provenance(self.root, data)['source_origins']['rest'], 'import')

        job['source_origin'] = 'imagegen'
        hatch.save(self.root, data)
        self.assertEqual(job['import_receipt'], original_receipt)
        self.assertEqual((self.root / 'qa/visual-review.json').read_bytes(), original_review)
        self.assertEqual(hatch.style_provenance(self.root, data)['source_origins']['rest'], 'import')
        with self.assertRaisesRegex(ValueError, 'source origin.*receipt'):
            hatch.manifest(self.root)

        # Historical jobs may omit the convenience label; their receipt still
        # supplies the real origin and remains acceptable to manifest loading.
        del job['source_origin']
        hatch.save(self.root, data)
        checked = hatch.manifest(self.root)
        self.assertEqual(hatch.style_provenance(self.root, checked)['source_origins']['rest'], 'import')
        self.assertNotIn('generation_receipt', hatch.job_for(checked, 'rest'))

    def test_fixture_labels_must_agree_with_generation_and_import_receipts(self):
        data = build_run(self.root, validate=False)
        hatch.repair(self.root, data, 'rest', 'Import a labeled synthetic fixture for provenance checks.')
        descriptor = self.home / 'fixture-origin-import.json'
        hatch.atomic(descriptor, {'schema_version': 1, 'kind': 'import', 'layout': 'strip',
                                 'files': [str(self.home / 'fixture-sources/rest.png')],
                                 'fixture': True, 'origin': 'Synthetic fixture import, not production artwork.'})
        import_source(self.root, data, 'rest', descriptor, 'Exercise matching fixture labels only.')
        hatch.validate(self.root, data)
        record_fixture_review(self.root, data)
        original_jobs = copy.deepcopy(data['jobs'])
        original_review = (self.root / 'qa/visual-review.json').read_bytes()
        self.assertTrue(hatch.status(self.root, data)['reviewed'])

        data['fixture_mode'] = False
        hatch.save(self.root, data)
        self.assertEqual(data['jobs'], original_jobs)
        self.assertEqual((self.root / 'qa/visual-review.json').read_bytes(), original_review)
        with self.assertRaisesRegex(ValueError, 'source receipt fixture label differs from the run: base'):
            hatch.manifest(self.root)

        data['fixture_mode'] = True
        job = hatch.job_for(data, 'rest')
        job['import_receipt']['fixture'] = False
        hatch.save(self.root, data)
        self.assertEqual((self.root / 'qa/visual-review.json').read_bytes(), original_review)
        with self.assertRaisesRegex(ValueError, 'source receipt fixture label differs from the run: rest'):
            hatch.manifest(self.root)

        job['import_receipt']['fixture'] = True
        for source_job in data['jobs']:
            source_job.pop('source_origin', None)
        hatch.save(self.root, data)
        checked = hatch.manifest(self.root)
        self.assertEqual(hatch.style_provenance(self.root, checked)['source_origins'],
                         {'base': 'fixture', 'rest': 'import', 'jump': 'fixture'})

    def test_export_and_package_retain_hash_bound_style_and_require_existing_review_gates(self):
        data = build_run(self.root)
        snapshot = hatch.read(self.root / 'pet_request.json')['resolved_style']
        evaluation = self.home / 'evaluation-export'
        hatch.export(self.root, data, evaluation)
        provenance = hatch.read(evaluation / 'provenance.json')
        self.assertEqual(provenance['resolved_style'], snapshot)
        self.assertTrue(provenance['fixture'])
        self.assertIsNone(provenance['visual_review'])
        self.assertIn('provenance.json', hatch.read(evaluation / 'export-receipt.json')['files'])
        with self.assertRaisesRegex(ValueError, 'visual review'):
            hatch.package(self.root, data, self.home / 'unreviewed-package')
        warnings = hatch.style_warnings(self.root)
        self.assertTrue(warnings, 'The fixture profile exports GIF and must acknowledge soft-edge limits.')
        template = hatch.review_template(self.root, data)
        for row in template['rows'].values():
            self.assertTrue(set(warnings) <= set(row['warning_notes']))
        record_fixture_review(self.root, data)
        incomplete = hatch.read(self.root / 'qa/visual-review.json')
        incomplete['rows']['rest']['warning_notes'].pop(warnings[0])
        invalid_review = self.home / 'incomplete-style-review.json'
        hatch.atomic(invalid_review, incomplete)
        with self.assertRaisesRegex(ValueError, 'every current warning'):
            hatch.review(self.root, data, invalid_review)
        destination = self.home / 'package'
        hatch.package(self.root, data, destination)
        style_provenance = hatch.read(destination / 'style-provenance.json')
        self.assertEqual(style_provenance['resolved_style'], snapshot)
        receipt = hatch.verify_package(destination)
        self.assertTrue(receipt['fixture'])
        self.assertEqual(receipt['schema_version'], 2)
        self.assertIn('style-provenance.json', receipt['files'])
        self.assertIn('style-provenance.json', hatch.read(destination / 'export-receipt.json')['files'])
        hatch.atomic(destination / 'style-provenance.json', {'resolved_style': None})
        with self.assertRaisesRegex(ValueError, 'hashes/contents'):
            hatch.verify_package(destination)

    def test_malformed_snapshot_is_rejected_by_controller_manifest(self):
        data = build_run(self.root, validate=False)
        request = hatch.read(self.root / 'pet_request.json')
        request['resolved_style']['style']['instructions']['materials'] += ' altered'
        hatch.atomic(self.root / 'pet_request.json', request)
        with self.assertRaises(ValueError):
            hatch.manifest(self.root)
        self.assertEqual(data['schema_version'], 3)

    def test_manifest_style_hash_requires_an_intact_resolved_snapshot(self):
        data = build_run(self.root, validate=False)
        request = hatch.read(self.root / 'pet_request.json')
        self.assertEqual(data['style_sha256'], request['resolved_style']['sha256'])
        for mode in ('missing', 'null'):
            with self.subTest(snapshot=mode):
                altered = copy.deepcopy(request)
                if mode == 'missing':
                    del altered['resolved_style']
                else:
                    altered['resolved_style'] = None
                hatch.atomic(self.root / 'pet_request.json', altered)
                with self.assertRaisesRegex(ValueError, 'style hash requires.*resolved style snapshot'):
                    hatch.manifest(self.root)


def prepared_case(entry):
    def test(self):
        self.check_style(entry)
    test.__doc__ = 'Prepare real base/state/retry prompts and guides for ' + entry['id'] + '.'
    return test


def original_case(style):
    def test(self):
        self.check_original(style)
    return test


def profile_case(path):
    def test(self):
        self.check_profile(path)
    return test


for _entry in registry.load_catalog()['styles']:
    setattr(PreparedStyleTests, 'test_prepare_' + _entry['id'].replace('-', '_'), prepared_case(_entry))

for _style in ORIGINAL_STYLES:
    setattr(OriginalPresetCompatibilityTests, 'test_original_' + _style.replace('-', '_'), original_case(_style))

for _path in sorted((ROOT / 'examples').glob('*.json')) + sorted((ROOT / 'presets').glob('*.json')):
    if _path.name != 'catalog.json':
        setattr(ProfileStyleCompatibilityTests, 'test_profile_' + _path.parent.name + '_' + _path.stem.replace('-', '_'), profile_case(_path))


if __name__ == '__main__':
    unittest.main()
