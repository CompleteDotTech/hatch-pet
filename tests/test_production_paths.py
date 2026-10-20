"""Portable review references emitted by the scene demonstration."""
from pathlib import Path, PurePosixPath, PureWindowsPath
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import production_regression_demo as demo
from portable_runs import verify_archive


class ProductionReviewPathTests(unittest.TestCase):
    def test_archive_rejects_raw_names_hidden_by_zipfile_normalization(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'alias.zip'
            payload = b'exact payload'
            receipt = {'schema_version': 1, 'files': {
                'payload.bin': hashlib.sha256(payload).hexdigest()}}
            with zipfile.ZipFile(path, 'w') as archive:
                member = zipfile.ZipInfo()
                member.filename = member.orig_filename = 'payload.bin\x00disguised'
                archive.writestr(member, payload)
                archive.writestr('archive-receipt.json', json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, 'unsafe'):
                verify_archive(path)

    def test_synthetic_frame_evidence_is_portable_on_both_path_flavours(self):
        bundle = {'characters': {}, 'clips': {}, 'scenes': [
            {'id': 'scene', 'shots': [{'id': 'shot'}]}]}
        for flavour in (PurePosixPath, PureWindowsPath):
            with self.subTest(flavour=flavour.__name__), \
                    patch.object(demo, 'Path', flavour), \
                    patch.object(demo, 'file_sha', return_value='a' * 64), \
                    patch('production_workflow.review_template', return_value={
                        'dimensions': {'final_artifacts': {}, 'timing_av_sync': {}}}), \
                    patch('production_workflow.record_review') as record:
                demo._record_synthetic_reviews(Path('project'), bundle, {'scene': 'renders/scene'})
                receipt = record.call_args.args[1]
                for dimension in ('final_artifacts', 'timing_av_sync'):
                    evidence = receipt['dimensions'][dimension]['evidence'][0]
                    self.assertEqual(evidence['path'], 'renders/scene/shots/shot/frames/000000.png')
                    self.assertEqual(evidence['method'], 'automated_check')
