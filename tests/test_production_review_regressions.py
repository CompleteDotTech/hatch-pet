"""Independent review reproductions use temporary synthetic data only."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from production_contracts import file_sha, load_project, read_json
from production_fixture import build_fixture_project, refresh_project_hashes, write_json
from production_render import render_shot
import production_workflow as workflow


class ProductionReviewRegressionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='hatch-review-audit-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.project = build_fixture_project(self.root)

    def receipt(self, target, dimensions, manifest=None, evidence='art/a-body.png'):
        receipt = workflow.review_template(self.root, target, dimensions, manifest)
        receipt['reviewer'] = {'kind': 'synthetic', 'id': 'review-regression',
                               'name': 'Synthetic review rejection regression only'}
        for dimension in receipt['dimensions'].values():
            dimension.update(verdict='pass', notes='Synthetic evidence gate; no visual or production artwork acceptance.',
                evidence=[{'path': evidence, 'sha256': file_sha(self.root / evidence),
                           'method': 'automated_check', 'note': 'Temporary fixture input only.'}])
        return receipt

    def test_schema_optional_character_metadata_does_not_crash_coverage_or_reviews(self):
        target = {'kind': 'character', 'character_id': 'a', 'version': '1.0.0'}
        before = workflow.review_template(self.root, target)['dimensions']['identity_construction']['dependencies']
        cast = read_json(self.root / 'cast.json')
        for key in ('restrictions', 'references', 'view_reviews'):
            cast['characters'][0].pop(key)
        write_json(self.root / 'cast.json', cast)
        refresh_project_hashes(self.root)
        load_project(self.project)
        report = workflow.coverage_report(self.root)
        self.assertTrue(report['validated'])
        self.assertFalse(report['ready'])
        receipt = self.receipt(target, ['identity_construction'])
        self.assertEqual(before, receipt['dimensions']['identity_construction']['dependencies'])
        workflow.record_review(self.root, receipt)
        self.assertTrue(workflow.review_status(self.root, target)['current_pass'])

    def test_mixed_receipt_keeps_passing_dimensions_and_repair_completes_acceptance(self):
        # This is a policy simulation only. _save is mocked: no production
        # receipt is persisted and no fixture source or provenance is relabeled.
        bundle = load_project(self.project)
        bundle['project']['fixture'] = False
        state = workflow._new_state(bundle)
        target = {'kind': 'clip', 'clip_id': 'idle-a', 'version': '1.0.0'}
        with patch.object(workflow, '_bundle', return_value=bundle), \
                patch.object(workflow, '_state', return_value=state), \
                patch.object(workflow, '_save'):
            mixed = self.receipt(target, None)
            mixed['reviewer'] = {'kind': 'assistant', 'id': 'in-memory-policy-simulation',
                                 'name': 'In-memory review aggregation simulation only'}
            for dimension in mixed['dimensions'].values():
                dimension['evidence'][0]['method'] = 'visual_inspection'
            mixed['dimensions']['contacts_interactions']['verdict'] = 'fail'
            result = workflow.record_review(self.root, mixed)
            self.assertFalse(result['production_art_acceptance'])  # Aggregate receipt still failed.
            status = workflow.review_status(self.root, target)
            self.assertTrue(status['dimensions']['pose_motion']['production_art_acceptance'])
            self.assertTrue(status['dimensions']['timing_av_sync']['production_art_acceptance'])
            self.assertFalse(status['dimensions']['contacts_interactions']['production_art_acceptance'])
            self.assertFalse(status['production_art_acceptance'])
            repair = copy.deepcopy(mixed)
            repair['dimensions'] = {'contacts_interactions': repair['dimensions']['contacts_interactions']}
            repair['dimensions']['contacts_interactions']['verdict'] = 'pass'
            workflow.record_review(self.root, repair)
            status = workflow.review_status(self.root, target)
            self.assertTrue(status['current_pass'])
            self.assertTrue(status['production_art_acceptance'])
            self.assertEqual(2, status['history_count'])
            bundle['project']['fixture'] = True
            self.assertFalse(workflow.review_status(self.root, target)['production_art_acceptance'])
        self.assertFalse((self.root / workflow.WORKFLOW_FILE).exists())
        self.assertTrue(read_json(self.project)['fixture'])

    def test_final_visual_gate_rejects_audio_only_and_expires_prior_permissive_receipts(self):
        render = render_shot(load_project(self.project), 'exchange', self.root / 'renders/exchange')
        target = {'kind': 'shot', 'scene_id': 'first-scene', 'shot_id': 'exchange'}
        manifest = 'renders/exchange/render-manifest.json'
        audio = self.receipt(target, ['final_artifacts'], manifest, 'renders/exchange/audio.wav')
        for kind, method in [('synthetic', 'automated_check'), ('assistant', 'timed_playback')]:
            invalid = copy.deepcopy(audio)
            invalid['reviewer']['kind'] = kind
            invalid['dimensions']['final_artifacts']['evidence'][0]['method'] = method
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'visual frame or layer'):
                workflow.record_review(self.root, invalid)
        self.assertEqual(0, workflow.review_status(self.root, target)['history_count'])
        for image in [render['frames'][0], render['frames'][0]['layers'][0]]:
            valid = self.receipt(target, ['final_artifacts'], manifest, 'renders/exchange/' + image['path'])
            result = workflow.record_review(self.root, valid)
            self.assertFalse(result['production_art_acceptance'])
            self.assertEqual('pass', workflow.review_status(self.root, target)['dimensions']['final_artifacts']['status'])
        # Simulate a receipt emitted by the former permissive version. Existing
        # histories remain intact, but their evidence must satisfy the new gate.
        with patch.object(workflow, '_has_final_visual_evidence', return_value=True):
            workflow.record_review(self.root, audio)
        status = workflow.review_status(self.root, target)
        self.assertEqual(3, status['history_count'])
        self.assertEqual('stale', status['dimensions']['final_artifacts']['status'])
        self.assertIn('no inspected bound visual', status['dimensions']['final_artifacts']['stale_reason'])


if __name__ == '__main__':
    unittest.main()
