"""Explicit reconstructed-art ingestion with synthetic receipts, never live model calls."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from asset_contracts import sha
from character_decomposition import (create_decomposition, load_decomposition,
    rebuild_from_annotation, recompose, save_manifest, validate_decomposition)
from decomposition_assisted import fail_reconstruction, ingest_reconstruction, request_reconstruction
from decomposition_fixtures import FIXTURE_ORIGIN, make_fixture
from decomposition_review import apply_review, review_template


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    return Path(path)


class AssistedDecompositionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='hatch-assisted-decomposition-')
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.root = self.home / 'run'
        self.fixture = make_fixture(self.home / 'fixture', 'overlap')
        self.data = create_decomposition(self.fixture.source, self.root, annotations=self.fixture.annotation,
            fixture=True, origin=FIXTURE_ORIGIN, mode='assisted')
        arm = next(c for c in self.fixture.components if c['id'] == 'anatomical-left-arm')
        self.hidden = self.fixture.root / arm['mask']

    def request(self, identifier='torso', hidden=None):
        return request_reconstruction(self.root, identifier,
            'Authored fixture only: exercise hidden-pixel ownership behind opaque front art.',
            hidden_mask=hidden or self.hidden, allow_reconstruction=True)

    def receipt(self, job):
        value = copy.deepcopy(job['receipt_template'])
        value.update(author='Synthetic fixture ingestion test',
                     note='Code-authored test raster exercises the gate. No imagegen call or production artwork acceptance.')
        value['model_call'] = {'id': None, 'model': None, 'parameters': None,
                               'unavailable_reason': 'No model was called; this is explicitly a deterministic fixture.'}
        return value

    def generated(self, size=None, mode='RGBA', name='synthetic-output.png'):
        source = self.home / name
        # Deliberately changes every observed pixel in the proposed output. Only
        # permitted hidden pixels may be consumed; original visible pixels must win.
        Image.new(mode, size or self.fixture.size, '#8C54A0').save(source)
        return source

    def accept_all_fixture_components(self):
        value = review_template(self.root)
        value.update(author='Synthetic fixture review-gate test',
                     note='Tests approval freshness only; this receipt is not production visual acceptance.')
        value['reviews'] = [{'id': c['id'], 'status': 'approved', 'inspected': True,
                             'note': 'Authored fixture component used to exercise the review gate.'}
                            for c in self.data['components']]
        apply_review(self.root, value)

    def test_ingest_preserves_observed_pixels_provenance_and_unaffected_approvals(self):
        self.accept_all_fixture_components()
        before = load_decomposition(self.root)
        before_hashes = {c['id']: c['asset']['sha256'] for c in before['components']}
        before_source = self.fixture.source.read_bytes()
        job = self.request()
        self.assertFalse(job['model_called'])
        self.assertEqual(job['receipt_template']['generation_skill'], '$fixture')
        self.assertEqual(len(job['input_images']), 3)
        self.assertEqual({v['role'] for v in job['input_images']}, {'identity', 'edit-target', 'mask-guide'})
        generated = self.generated()
        result = ingest_reconstruction(self.root, 'torso', generated,
            write_json(self.home / 'receipt.json', self.receipt(job)), allow_reconstruction=True)
        self.assertTrue(result['original_asset_preserved'])
        self.assertTrue(result['review_required'])
        self.assertFalse(result['model_called_by_controller'])
        current = load_decomposition(self.root)
        self.assertEqual(before_source, self.fixture.source.read_bytes())
        self.assertEqual(before_hashes, {c['id']: c['asset']['sha256'] for c in current['components']})
        torso = next(c for c in current['components'] if c['id'] == 'torso')
        reconstructed = torso['provenance']['reconstruction']
        self.assertEqual(torso['provenance']['kind'], 'segmented-observed')
        self.assertEqual(reconstructed['kind'], 'inferred')
        self.assertEqual(reconstructed['status'], 'pending-review')
        self.assertEqual(reconstructed['observed_asset'], torso['asset'])
        self.assertEqual(reconstructed['source_sha256'], sha(self.fixture.source))
        self.assertEqual(reconstructed['original_output']['sha256'], sha(generated))
        self.assertEqual((self.root / reconstructed['original_output']['path']).read_bytes(), generated.read_bytes())
        self.assertIsNone(reconstructed['model_call']['id'])
        self.assertEqual(torso['review']['status'], 'pending')
        self.assertTrue(all(c['review']['status'] == 'approved' for c in current['components'] if c['id'] != 'torso'))
        validation = validate_decomposition(self.root, current)
        self.assertTrue(validation['faithful_fidelity_passed'])
        self.assertEqual(validation['reconstruction_error']['max_channel_error'], 0)
        self.assertGreater(validation['generated_content_pixels'], 0)
        self.assertEqual(validation['semantic_status'], 'pending')
        self.assertEqual(recompose(self.root).tobytes(), self.fixture.expected.tobytes())
        self.assertEqual(recompose(self.root, inferred=True).tobytes(), self.fixture.expected.tobytes())
        with Image.open(self.root / reconstructed['inferred_mask']['path']) as mask, Image.open(self.hidden) as allowed:
            self.assertEqual(mask.tobytes(), allowed.tobytes())
        # A duplicate ingest cannot silently replace the component again.
        with self.assertRaisesRegex(ValueError, 'active'):
            ingest_reconstruction(self.root, 'torso', generated, self.home / 'receipt.json', allow_reconstruction=True)

    def test_faithful_mode_and_missing_explicit_opt_in_reject_without_claims(self):
        with self.assertRaisesRegex(ValueError, 'explicit|allow-reconstruction'):
            request_reconstruction(self.root, 'torso', 'fixture', hidden_mask=self.hidden)
        self.assertFalse((self.root / 'reconstruction/jobs.json').exists())
        faithful = self.home / 'faithful'
        create_decomposition(self.fixture.source, faithful, annotations=self.fixture.annotation,
                             fixture=True, origin=FIXTURE_ORIGIN)
        with self.assertRaisesRegex(ValueError, 'assisted'):
            request_reconstruction(faithful, 'torso', 'fixture', hidden_mask=self.hidden, allow_reconstruction=True)
        self.assertFalse((faithful / 'reconstruction/jobs.json').exists())

    def test_hidden_region_must_be_behind_an_opaque_front_layer(self):
        with self.assertRaisesRegex(ValueError, 'hidden region'):
            request_reconstruction(self.root, 'torso', 'fixture', allow_reconstruction=True)
        with self.assertRaisesRegex(ValueError, 'hidden region'):
            self.request(hidden={'runs': [[0, 0, 2]]})
        self.assertFalse((self.root / 'reconstruction/jobs.json').exists())

    def test_same_active_component_resumes_without_duplicate_claim_and_other_waits(self):
        first = self.request()
        resumed = self.request()
        self.assertEqual(first['token'], resumed['token'])
        self.assertTrue(resumed['resumed'])
        self.assertFalse(resumed['model_called'])
        with self.assertRaisesRegex(ValueError, 'active reconstruction'):
            self.request('head')
        jobs = json.loads((self.root / 'reconstruction/jobs.json').read_text())
        self.assertEqual(len(jobs['jobs']), 1)
        failed = fail_reconstruction(self.root, first['token'], 'Synthetic failure exercises retry; no provider called.')
        self.assertTrue(failed['original_component_preserved'])
        next_job = self.request()
        self.assertNotEqual(next_job['token'], first['token'])
        self.assertEqual(sha(self.fixture.source), self.data['source']['sha256'])

    def test_per_component_attempt_budget_stops_at_three_claims(self):
        for _ in range(3):
            job = self.request()
            fail_reconstruction(self.root, job['token'], 'Fixture failure for attempt-budget test.')
        with self.assertRaisesRegex(ValueError, 'component attempt budget'):
            self.request()
        self.assertEqual(len(json.loads((self.root / 'reconstruction/jobs.json').read_text())['jobs']), 3)

    def test_total_claim_budget_stops_at_sixteen_without_spending_inference(self):
        identifiers = ['torso', 'head', 'anatomical-right-leg', 'anatomical-left-leg',
                       'anatomical-right-eye', 'anatomical-left-eye']
        highlights = next(c for c in self.fixture.components if c['id'] == 'eye-highlights')
        for index in range(16):
            job = self.request(identifiers[index % len(identifiers)], self.fixture.root / highlights['mask'])
            self.assertFalse(job['model_called'])
            fail_reconstruction(self.root, job['token'], 'Fixture-only total-claim bound exercise.')
        with self.assertRaisesRegex(ValueError, 'total claim budget'):
            self.request('anatomical-right-eye', self.fixture.root / highlights['mask'])
        self.assertTrue(load_decomposition(self.root)['validation']['faithful_fidelity_passed'])

    def test_bad_token_hash_fixture_or_provider_claim_is_rejected_without_ingest(self):
        job = self.request()
        generated = self.generated()
        original = self.receipt(job)
        alterations = [
            (lambda receipt: receipt.update(token='stale-token'), 'active'),
            (lambda receipt: receipt.update(source_sha256='0' * 64), 'claimed inputs'),
            (lambda receipt: receipt.update(fixture=False), 'fixture'),
            (lambda receipt: receipt.update(generation_skill='$imagegen'), 'fixture'),
            (lambda receipt: receipt['model_call'].update(id=job['token']), 'provider'),
        ]
        before = sha(self.root / 'decomposition.json')
        for alter, expected in alterations:
            receipt = copy.deepcopy(original)
            alter(receipt)
            path = write_json(self.home / 'bad-receipt.json', receipt)
            with self.subTest(expected=expected), self.assertRaisesRegex(ValueError, expected):
                ingest_reconstruction(self.root, 'torso', generated, path, allow_reconstruction=True)
            self.assertEqual(sha(self.root / 'decomposition.json'), before)
        self.assertEqual(self.request()['token'], job['token'])

    def test_reconstruction_metadata_cannot_diverge_from_its_original_receipt(self):
        job = self.request()
        ingest_reconstruction(self.root, 'torso', self.generated(),
            write_json(self.home / 'receipt.json', self.receipt(job)), allow_reconstruction=True)
        manifest = load_decomposition(self.root)
        original = (self.root / 'decomposition.json').read_bytes()
        torso = next(c for c in manifest['components'] if c['id'] == 'torso')
        original_receipt = self.root / torso['provenance']['reconstruction']['receipt']['path']
        receipt_hash = sha(original_receipt)
        sidecar_hashes = {name: sha(self.root / name) for name in
                          ('decomposition.json', 'identity.json', 'validation.json', 'provenance.json')}
        changes = [
            ('model_call', lambda value: value['model_call'].update(id='altered-for-fixture-integrity-test')),
            ('note', lambda value: value.update(note='Altered note must not replace the retained ingestion evidence.')),
        ]
        for label, change in changes:
            altered = copy.deepcopy(manifest)
            reconstructed = next(c for c in altered['components'] if c['id'] == 'torso')['provenance']['reconstruction']
            change(reconstructed)
            with self.subTest(field=label, operation='save'), self.assertRaisesRegex(ValueError, 'receipt|grounding|metadata|provenance'):
                save_manifest(self.root, altered)
            self.assertEqual(sidecar_hashes, {name: sha(self.root / name) for name in sidecar_hashes})
            self.assertEqual(receipt_hash, sha(original_receipt))
            altered = copy.deepcopy(manifest)
            reconstructed = next(c for c in altered['components'] if c['id'] == 'torso')['provenance']['reconstruction']
            change(reconstructed)
            write_json(self.root / 'decomposition.json', altered)
            try:
                with self.subTest(field=label, operation='load'), self.assertRaisesRegex(ValueError, 'receipt|grounding|metadata|provenance|validation signature'):
                    load_decomposition(self.root)
            finally:
                (self.root / 'decomposition.json').write_bytes(original)
        self.assertTrue(load_decomposition(self.root)['validation']['ok'])

    def test_missing_model_metadata_requires_an_explicit_unavailable_reason(self):
        job = self.request()
        source = self.generated()
        before = sha(self.root / 'decomposition.json')
        invalid_metadata = [None, {}, {'id': None, 'model': None, 'parameters': None},
                            {'id': None, 'model': None, 'parameters': None, 'unavailable_reason': ''},
                            {'id': None, 'model': 'fixture-model-label', 'parameters': None, 'unavailable_reason': ''},
                            {'id': 'fixture-call-label', 'model': None, 'parameters': None, 'unavailable_reason': '   '}]
        for metadata in invalid_metadata:
            receipt = self.receipt(job)
            receipt['model_call'] = metadata
            with self.subTest(metadata=metadata), self.assertRaisesRegex(ValueError, 'metadata|reason|model call'):
                ingest_reconstruction(self.root, 'torso', source,
                    write_json(self.home / 'missing-metadata.json', receipt), allow_reconstruction=True)
            self.assertEqual(sha(self.root / 'decomposition.json'), before)
        self.assertEqual(self.request()['token'], job['token'])

    def test_wrong_dimensions_mode_internal_source_or_empty_hidden_output_reject(self):
        job = self.request()
        receipt = write_json(self.home / 'receipt.json', self.receipt(job))
        wrong = self.generated(size=(20, 20), name='small.png')
        rgb = self.generated(mode='RGB', name='rgb.png')
        empty = self.home / 'empty-hidden.png'
        Image.new('RGBA', self.fixture.size).save(empty)
        before = sha(self.root / 'decomposition.json')
        for source, expected in [(wrong, 'full-canvas'), (rgb, 'RGBA'), (empty, 'permitted hidden'),
                                 (self.root / 'original.png', 'outside')]:
            with self.subTest(source=source.name), self.assertRaisesRegex(ValueError, expected):
                ingest_reconstruction(self.root, 'torso', source, receipt, allow_reconstruction=True)
            self.assertEqual(sha(self.root / 'decomposition.json'), before)

    def test_changed_component_or_grounding_input_rejects_old_claim(self):
        job = self.request()
        receipt = write_json(self.home / 'receipt.json', self.receipt(job))
        generated = self.generated()
        prompt = self.root / job['prompt']
        saved = prompt.read_bytes()
        prompt.write_text('Changed grounding prompt; invalidate the claim.', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'grounding input changed'):
            ingest_reconstruction(self.root, 'torso', generated, receipt, allow_reconstruction=True)
        prompt.write_bytes(saved)
        annotation = json.loads((self.root / 'annotations/current.json').read_text())
        torso = next(c for c in annotation['components'] if c['id'] == 'torso')
        torso['name'] = 'Corrected observed torso'
        rebuild_from_annotation(self.root, annotation, author='Synthetic fixture author', reason='Tests stale component ownership.')
        with self.assertRaisesRegex(ValueError, 'component/source changed'):
            ingest_reconstruction(self.root, 'torso', generated, receipt, allow_reconstruction=True)
        fail_reconstruction(self.root, job['token'], 'Explicitly failed stale fixture claim after component correction.')
        self.assertNotEqual(self.request()['token'], job['token'])

    def test_inferred_content_approval_requires_explicit_acknowledgement(self):
        job = self.request()
        ingest_reconstruction(self.root, 'torso', self.generated(),
            write_json(self.home / 'receipt.json', self.receipt(job)), allow_reconstruction=True)
        review = review_template(self.root)
        review.update(author='Fixture inferred-review gate', note='Tests acknowledgement only, not artwork acceptance.')
        review['reviews'] = [{'id': 'torso', 'status': 'approved', 'inspected': True,
                              'note': 'Synthetic component approval requires inferred-content acknowledgement.'}]
        with self.assertRaisesRegex(ValueError, 'inferred content|reconstruction review'):
            apply_review(self.root, review)
        review['reviews'][0]['inferred_acknowledged'] = True
        result = apply_review(self.root, review)
        self.assertEqual(result['component_reviews']['torso'], 'approved')
        current = load_decomposition(self.root)
        torso = next(c for c in current['components'] if c['id'] == 'torso')
        self.assertEqual(torso['provenance']['reconstruction']['status'], 'approved')


if __name__ == '__main__':
    unittest.main()
