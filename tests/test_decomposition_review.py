"""Real source-bound corrections and optional browser editing, with authored fixtures.

No semantic-model calls or paid services are used. The browser test exercises the
downloaded receipt against actual core extraction rather than mocking UI actions.
Set HATCH_DECOMPOSITION_BROWSER_TEST=1 with Playwright/Chromium installed to run it.
"""
import copy
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from asset_contracts import sha
from character_decomposition import (component_signature, create_decomposition,
    load_decomposition, recompose)
from decomposition_fixtures import make_fixture
from decomposition_review import (apply_review, build_review, review_template,
    restore_revision)


class DecompositionReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hatch-decomposition-review-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / 'run'
        self.fixture = make_fixture(self.home / 'art', 'cartoon')
        self.data = create_decomposition(self.fixture.source, self.root,
            annotations=self.fixture.annotation, fixture=True)

    def receipt(self):
        receipt = review_template(self.root)
        receipt.update(author='Synthetic-fixture reviewer',
            note='Known authored fixture inspected to exercise exact mask and review contracts; no production art acceptance.')
        return receipt

    def accept_all(self):
        receipt = self.receipt()
        receipt['reviews'] = [{'id': c['id'], 'status': 'approved', 'inspected': True,
            'note': 'Authored component geometry, source pixels, and semantic label inspected in this fixture.'}
            for c in receipt['annotation']['components']]
        return apply_review(self.root, receipt)

    def test_editor_is_self_contained_immutable_evidence(self):
        source_hash = sha(self.fixture.source)
        manifest_hash = sha(self.root / 'decomposition.json')
        result = build_review(self.root, self.home / 'desk')
        html = Path(result['review_ui']).read_text()
        self.assertIn('data:image/png;base64,', html)
        self.assertIn('Immutable original image', html)
        self.assertIn('Download bound correction JSON', html)
        self.assertIn('Split selected with polygon', html)
        self.assertIn('Foreground brush: remove', html)
        self.assertIn('Place attachment', html)
        self.assertNotIn('__DECOMPOSITION_DATA__', html)
        self.assertFalse(result['accepted'])
        self.assertEqual(sha(self.fixture.source), source_hash)
        self.assertEqual(sha(self.root / 'decomposition.json'), manifest_hash)
        self.assertFalse((self.root / 'review').exists())
        with self.assertRaisesRegex(ValueError, 'must be new'):
            build_review(self.root, self.home / 'desk')
        with self.assertRaises(ValueError):
            build_review(self.root, self.root / 'desk')

    def test_stale_manifest_wrong_source_and_unknown_fields_fail_before_mutation(self):
        before = sha(self.root / 'decomposition.json')
        for mutation, error in (
            (lambda value: value.update(source_sha256='f' * 64), 'exact original source'),
            (lambda value: value.update(base_manifest_sha256='f' * 64), 'stale'),
            (lambda value: value.update(trust_everything=True), 'supported keys'),
            (lambda value: value.update(author=''), 'author'),
            (lambda value: value['annotation'].update(source_sha256='f' * 64), 'exact original source'),
        ):
            with self.subTest(error=error):
                value = self.receipt()
                mutation(value)
                with self.assertRaisesRegex(ValueError, error):
                    apply_review(self.root, value)
                self.assertEqual(sha(self.root / 'decomposition.json'), before)

    def test_component_inspection_and_evidence_required_and_review_is_bound(self):
        value = self.receipt()
        value['reviews'] = [{'id': 'mouth', 'status': 'approved', 'note': 'Synthetic test'}]
        with self.assertRaisesRegex(ValueError, 'inspection'):
            apply_review(self.root, value)
        value['reviews'][0]['inspected'] = True
        value['reviews'][0]['note'] = ''
        with self.assertRaisesRegex(ValueError, 'evidence note'):
            apply_review(self.root, value)
        value['reviews'][0]['note'] = 'Inspected exact source-supported mouth mask.'
        result = apply_review(self.root, value)
        self.assertFalse(result['accepted'])
        self.assertEqual(result['component_reviews']['mouth'], 'approved')
        mouth = next(c for c in load_decomposition(self.root)['components'] if c['id'] == 'mouth')
        self.assertEqual(mouth['review']['signature'], component_signature(mouth))
        with self.assertRaisesRegex(ValueError, 'stale'):
            apply_review(self.root, value)
        self.assertTrue(self.accept_all()['accepted'])

    def test_independent_metadata_repair_preserves_other_assets_and_reviews(self):
        self.accept_all()
        before = {c['id']: copy.deepcopy(c) for c in load_decomposition(self.root)['components']}
        source_hash = sha(self.fixture.source)
        value = self.receipt()
        mouth = next(c for c in value['annotation']['components'] if c['id'] == 'mouth')
        mouth.update(name='Closed smiling mouth', category='facial/expression', pivot=[48, 45],
                     z_index=50, attachments=[{'id': 'face-link', 'point': [48, 45],
                         'target_id': 'head', 'confidence': 0.75}])
        result = apply_review(self.root, value)
        self.assertEqual(result['changed_components'], ['mouth'])
        self.assertEqual(result['component_reviews']['mouth'], 'pending')
        current = {c['id']: c for c in load_decomposition(self.root)['components']}
        self.assertEqual(current['head'], before['head'])
        self.assertEqual(current['mouth']['asset']['sha256'], before['mouth']['asset']['sha256'])
        self.assertEqual(current['mouth']['provenance']['kind'], 'manually-corrected')
        self.assertEqual(current['mouth']['attachments'][0]['target_id'], 'head')
        self.assertEqual(current['mouth']['pivot'], [48, 45])
        self.assertEqual(sha(self.fixture.source), source_hash)
        self.assertEqual(recompose(self.root).tobytes(), self.fixture.expected.tobytes())

    def test_real_disconnected_mask_split_and_merge_round_trip(self):
        value = self.receipt()
        original = next(c for c in value['annotation']['components'] if c['id'] == 'eye-highlights')
        separated = copy.deepcopy(original)
        separated.update(id='anatomical-left-highlight', name='Anatomical left eye highlight', side='left')
        separated['mask']['runs'] = [r for r in original['mask']['runs'] if r[1] > 48]
        original['mask']['runs'] = [r for r in original['mask']['runs'] if r[1] < 48]
        value['annotation']['components'].append(separated)
        result = apply_review(self.root, value)
        self.assertIn('anatomical-left-highlight', result['changed_components'])
        current = load_decomposition(self.root)
        self.assertEqual(len(current['components']), len(self.data['components']) + 1)
        component = next(c for c in current['components'] if c['id'] == 'anatomical-left-highlight')
        with Image.open(self.root / component['asset']['path']) as image:
            self.assertEqual(image.mode, 'RGBA')
            self.assertEqual(image.size, (2, 2))
            self.assertEqual(image.getpixel((0, 0)), (255, 255, 255, 255))
        self.assertEqual(recompose(self.root).tobytes(), self.fixture.expected.tobytes())
        value = self.receipt()
        original = next(c for c in value['annotation']['components'] if c['id'] == 'eye-highlights')
        other = next(c for c in value['annotation']['components'] if c['id'] == 'anatomical-left-highlight')
        original['mask']['runs'] = sorted(original['mask']['runs'] + other['mask']['runs'])
        value['annotation']['components'].remove(other)
        result = apply_review(self.root, value)
        self.assertEqual(result['removed_components'], ['anatomical-left-highlight'])
        self.assertEqual(recompose(self.root).tobytes(), self.fixture.expected.tobytes())

    def test_bad_geometry_is_rejected_without_changing_current_manifest(self):
        value = self.receipt()
        value['annotation']['components'][0]['mask'] = {'runs': [[0, 0, 1000000]]}
        before = sha(self.root / 'decomposition.json')
        with self.assertRaisesRegex(ValueError, 'outside the source|outside.*canvas'):
            apply_review(self.root, value)
        self.assertEqual(sha(self.root / 'decomposition.json'), before)
        self.assertTrue(load_decomposition(self.root)['validation']['ok'])

    def test_foreground_and_mask_correction_keep_original_and_report_residual(self):
        from decomposition_masks import decode_mask, mask_to_runs
        value = self.receipt()
        mouth = next(c for c in value['annotation']['components'] if c['id'] == 'mouth')
        mask = decode_mask(mouth['mask'], self.fixture.size)
        before = sha(self.fixture.source)
        erased = next((x, y) for y in range(mask.height) for x in range(mask.width) if mask.getpixel((x, y)))
        mask.putpixel(erased, 0)
        mouth['mask'] = {'runs': mask_to_runs(mask)}
        result = apply_review(self.root, value)
        self.assertTrue(result['validation']['ok'])
        self.assertEqual(result['validation']['unassigned_foreground_pixels'], 1)
        self.assertEqual(sha(self.fixture.source), before)
        self.assertEqual(recompose(self.root).tobytes(), self.fixture.expected.tobytes())
        value = self.receipt()
        unassigned = next(c for c in value['annotation']['components'] if c['category'] == 'unassigned')
        value['reviews'] = [{'id': unassigned['id'], 'status': 'approved', 'inspected': True,
                             'note': 'Cannot approve a semantically unknown residual.'}]
        current_hash = sha(self.root / 'decomposition.json')
        with self.assertRaisesRegex(ValueError, 'unassigned foreground'):
            apply_review(self.root, value)
        self.assertEqual(sha(self.root / 'decomposition.json'), current_hash)

    def test_rejected_component_can_be_repaired_and_approved_independently(self):
        self.accept_all()
        value = self.receipt()
        value['reviews'] = [{'id': 'mouth', 'status': 'rejected', 'inspected': True,
            'note': 'Mouth needs a corrected expression label and pivot.'}]
        rejected = apply_review(self.root, value)
        self.assertFalse(rejected['accepted'])
        value = self.receipt()
        mouth = next(c for c in value['annotation']['components'] if c['id'] == 'mouth')
        mouth.update(name='Smile', pivot=[48, 45])
        value['reviews'] = [{'id': 'mouth', 'status': 'approved', 'inspected': True,
            'note': 'Viewed corrected smile label, original mouth pixels and canvas pivot.'}]
        repaired = apply_review(self.root, value)
        self.assertTrue(repaired['accepted'])
        self.assertEqual(repaired['changed_components'], ['mouth'])

    def test_restore_previous_accepted_correction_preserves_exact_approval(self):
        approved = self.accept_all()
        original = load_decomposition(self.root)
        value = self.receipt()
        next(c for c in value['annotation']['components'] if c['id'] == 'mouth')['name'] = 'Temporary label'
        self.assertFalse(apply_review(self.root, value)['accepted'])
        result = restore_revision(self.root, approved['revision'], 'Fixture restorer',
                                  'Restore the previously inspected fixture annotations.')
        self.assertTrue(result['accepted'])
        restored = load_decomposition(self.root)
        self.assertEqual(restored['components'], original['components'])
        self.assertEqual(len(result['restored_component_reviews']), len(original['components']))
        self.assertEqual(recompose(self.root).tobytes(), self.fixture.expected.tobytes())

    def test_revision_tampering_and_invalid_restore_fail_before_rebuild(self):
        approved = self.accept_all()
        value = self.receipt()
        value.pop('annotation')
        value.pop('reviews')
        value['restore_revision'] = 999
        before = sha(self.root / 'decomposition.json')
        with self.assertRaisesRegex(ValueError, 'unknown.*revision'):
            apply_review(self.root, value)
        self.assertEqual(sha(self.root / 'decomposition.json'), before)
        snapshot = self.root / f'review/revisions/{approved["revision"]:06d}/annotation.json'
        snapshot.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'has changed'):
            restore_revision(self.root, approved['revision'], 'Fixture restorer', 'Tampered history must fail.')
        self.assertEqual(sha(self.root / 'decomposition.json'), before)

    @unittest.skipUnless(os.environ.get('HATCH_DECOMPOSITION_BROWSER_TEST') == '1',
                         'Set HATCH_DECOMPOSITION_BROWSER_TEST=1 for real local Playwright editor validation.')
    def test_browser_edits_split_merge_masks_pivots_verdicts_and_applies_receipt(self):
        from playwright.sync_api import sync_playwright
        desk = build_review(self.root, self.home / 'desk')
        with sync_playwright() as playwright:
            launch = {'headless': True, 'args': ['--no-sandbox', '--disable-dev-shm-usage']}
            if os.environ.get('HATCH_BROWSER_EXECUTABLE'):
                launch['executable_path'] = os.environ['HATCH_BROWSER_EXECUTABLE']
            browser = playwright.chromium.launch(**launch)
            page = browser.new_page(viewport={'width': 1600, 'height': 1100}, accept_downloads=True)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(Path(desk['review_ui']).as_uri())
            page.wait_for_function("document.querySelector('#live-metrics').textContent.includes('Source foreground:')")
            # A legal component id must never access inherited Object members.
            page.locator('#new-name').fill('Constructor-shaped fixture detail')
            page.locator('#new-id').fill('constructor')
            page.locator('#add').click()
            self.assertEqual(page.evaluate('selected'), 'constructor')
            self.assertTrue(page.locator('#inferred-details').is_hidden())
            self.assertTrue(page.locator('#asset').is_hidden())
            page.locator('#undo').click()
            # Absorb a non-immediate ancestor without creating mouth→head→mouth.
            page.locator('#components button').filter(has_text='Mouth').click()
            page.locator('#merge-target').select_option('torso')
            page.locator('#merge').click()
            self.assertIsNone(page.evaluate("annotation.components.find(c=>c.id==='mouth').parent_id"))
            self.assertEqual(page.evaluate("annotation.components.find(c=>c.id==='head').parent_id"), 'mouth')
            page.locator('#undo').click()
            page.locator('#components button').filter(has_text='Eye Highlights').click()
            page.locator('#new-name').fill('Anatomical left eye highlight')
            page.locator('#new-id').fill('anatomical-left-highlight')
            page.locator('#new-category').fill('detail/highlight')
            page.locator('#tool').select_option('split')
            for x, y in ((54, 29), (59, 29), (59, 34), (54, 34)):
                page.locator('#editor').click(position={'x': x, 'y': y})
            page.locator('#commit-polygon').click()
            self.assertEqual(page.evaluate('annotation.components.length'), len(self.data['components']) + 1)
            page.locator('#merge-target').select_option('eye-highlights')
            page.locator('#merge').click()
            self.assertEqual(page.evaluate('annotation.components.length'), len(self.data['components']))
            page.locator('#undo').click()
            self.assertEqual(page.evaluate('annotation.components.length'), len(self.data['components']) + 1)
            page.locator('#redo').click()
            self.assertEqual(page.evaluate('annotation.components.length'), len(self.data['components']))
            page.locator('#components button').filter(has_text='Torso').click()
            page.locator('#name').fill('Body torso')
            page.locator('#category').fill('anatomy/torso')
            page.locator('#save-meta').click()
            page.locator('#pivot-x').fill('48')
            page.locator('#pivot-y').fill('65')
            page.locator('#save-pivot').click()
            page.locator('#attachment-id').fill('neck')
            page.locator('#attachment-target').select_option('head')
            page.locator('#attachment-x').fill('48')
            page.locator('#attachment-y').fill('46')
            page.locator('#save-attachment').click()
            page.locator('#radius').fill('1')
            page.locator('#tool').select_option('paint')
            page.locator('#editor').click(position={'x': 35, 'y': 31})
            page.locator('#isolate').click()
            self.assertGreater(page.evaluate('hidden.size'), 0)
            page.locator('#show-all').click()
            self.assertEqual(page.evaluate('hidden.size'), 0)
            page.locator('#zoom').select_option('4')
            self.assertEqual(page.locator('#editor').evaluate('(e)=>e.style.width'), str(self.fixture.size[0] * 4) + 'px')
            page.locator('#inspected').check()
            page.locator('#review-note').fill('Synthetic torso source pixels, mask changes, neck attachment, and pivot inspected.')
            page.locator('#approve').click()
            page.locator('#author').fill('Synthetic browser reviewer')
            page.locator('#note').fill('Browser split/merge, mask assignment, metadata, pivot, attachment and per-component review exercise.')
            screenshot = os.environ.get('HATCH_DECOMPOSITION_SCREENSHOT', '/tmp/decomposition-review.png')
            page.screenshot(path=screenshot, full_page=True)
            with page.expect_download() as download_info:
                page.locator('#download').click()
            receipt = self.home / 'downloaded-review.json'
            download_info.value.save_as(receipt)
            # Bound actual edit snapshots by bytes as well as entry count. A
            # small injected budget verifies eviction without allocating 64 MiB.
            history_budget = page.evaluate('undo[undo.length-1].bytes * 2')
            page.evaluate('limit => trimHistory(limit)', history_budget)
            history_size = page.evaluate('[...undo,...redo].reduce((sum,item)=>sum+item.bytes,0)')
            self.assertLessEqual(history_size, history_budget)
            self.assertEqual(errors, [])
            browser.close()
        result = apply_review(self.root, receipt)
        self.assertTrue(result['validation']['ok'])
        self.assertEqual(result['component_reviews']['torso'], 'approved')
        current = load_decomposition(self.root)
        torso = next(c for c in current['components'] if c['id'] == 'torso')
        self.assertEqual(torso['name'], 'Body torso')
        self.assertEqual(torso['pivot'], [48, 65])
        self.assertEqual(torso['attachments'][0]['id'], 'neck')
        self.assertEqual(recompose(self.root).tobytes(), self.fixture.expected.tobytes())


if __name__ == '__main__':
    unittest.main()
