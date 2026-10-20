"""Required checks of real retained delivery bytes, plus labeled failure injection."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import production_delivery as delivery
import production_sources as sources
from production_demo import make_audio

PILOT = ROOT / 'examples/production-pilot'


class ProductionDeliveryTests(unittest.TestCase):
    def test_public_inventory_requires_every_original_and_authentic_review_artifact(self):
        result = delivery.verify_delivery(PILOT)
        self.assertTrue(result['verified'])
        self.assertEqual(result['bundles']['artwork']['file_count'], 36)
        self.assertEqual(result['bundles']['audio']['file_count'], 16)
        self.assertEqual(result['history']['records'], 20)
        self.assertEqual(result['history']['supporting_evidence_files'], 13)
        self.assertTrue(result['history']['evidence_verified'])
        self.assertFalse(result['history']['human_review'])
        self.assertFalse(result['new_approval_recorded'])
        self.assertEqual(len(result['acquisitions']), 4)

    def test_restoration_preserves_originals_ledger_and_two_scene_model_without_subprocesses(self):
        with tempfile.TemporaryDirectory(prefix='hatch-delivery-test-') as temporary:
            root = Path(temporary) / 'pilot'
            with patch('production_demo.subprocess.run', side_effect=AssertionError('No TTS or provider')):
                result = delivery.restore_pilot(PILOT, root)
            self.assertEqual([(x['id'], x['frames']) for x in result['scenes']],
                             [('seed-exchange', 432), ('garden-promise', 264)])
            self.assertEqual(result['clips'], 20)
            self.assertEqual(hashlib.sha256((root / 'production-workflow.json').read_bytes()).hexdigest(),
                             result['history']['sha256'])
            self.assertFalse((root / 'renders').exists())
            for original, restored in result['historical_artifact_paths'].items():
                self.assertTrue((root / restored).is_file())
                if original.startswith('renders/'):
                    self.assertTrue(restored.startswith('historical/renders/'))
            before = (root / 'audio/original/line-01.txt').stat().st_mtime_ns
            with patch('production_demo.subprocess.run', side_effect=AssertionError('No TTS')):
                make_audio(root)
            self.assertEqual((root / 'audio/original/line-01.txt').stat().st_mtime_ns, before)
            with self.assertRaisesRegex(ValueError, 'must not exist'):
                delivery.restore_pilot(PILOT, root)

    def test_missing_audio_fails_even_when_ffmpeg_is_available(self):
        with tempfile.TemporaryDirectory(prefix='hatch-no-tts-test-') as temporary:
            with patch('production_demo.shutil.which', return_value='/available/ffmpeg'), \
                    patch('production_demo.subprocess.run', side_effect=AssertionError('Unexpected synthesis')):
                with self.assertRaisesRegex(ValueError, 'explicit --synthesize-missing-audio'):
                    make_audio(Path(temporary))
            self.assertFalse(list(Path(temporary).rglob('*.wav')))

    def test_corrupt_original_prevents_project_publication(self):
        with tempfile.TemporaryDirectory(prefix='hatch-delivery-corrupt-') as temporary:
            source, destination = Path(temporary) / 'source', Path(temporary) / 'pilot'
            # This copy is a failure-injection specimen, never accepted as production.
            shutil.copytree(PILOT, source)
            index = json.loads((source / 'audio-source-bundle/sources-index.json').read_bytes())
            part = source / 'audio-source-bundle' / index['parts'][0]['path']
            raw = part.read_bytes()
            part.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                delivery.restore_pilot(source, destination)
            self.assertFalse(destination.exists())
            self.assertFalse(list(Path(temporary).glob('.hatch-pilot-build-*')))

    def test_altered_historical_chain_cannot_be_relabelled_as_authentic(self):
        with tempfile.TemporaryDirectory(prefix='hatch-history-test-') as temporary:
            sources.restore_source_bundle(PILOT / 'reviews-source-bundle', Path(temporary) / 'reviews')
            raw = (Path(temporary) / 'reviews/production-workflow.json').read_bytes()
            expected = json.loads((PILOT / delivery.MANIFEST).read_bytes())['history']
            value = json.loads(raw)
            value['reviews'][0]['receipt']['reviewer']['kind'] = 'human'
            with self.assertRaisesRegex(ValueError, 'pinned original'):
                delivery._history(json.dumps(value).encode(), expected)

    def test_report_write_failure_preserves_the_previous_valid_checkpoint(self):
        import verify_public_delivery as gate
        with tempfile.TemporaryDirectory(prefix='hatch-report-test-') as temporary:
            root = Path(temporary)
            path = root / 'report.json'
            gate.write_json(path, {'status': 'running', 'inventory': 'verified'})
            before = path.read_bytes()
            with patch.object(gate.os, 'fsync', side_effect=OSError(28, 'No space left on device')):
                with self.assertRaises(OSError):
                    gate.write_json(path, {'status': 'failed', 'error': 'later stage failed'})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(root.iterdir()), [path])


if __name__ == '__main__':
    unittest.main()
