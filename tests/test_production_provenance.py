"""Exact supporting provenance is validated and invalidates only its consumers."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from production_contracts import file_sha, load_project, read_json
from production_fixture import build_fixture_project, fixture_provenance, refresh_project_hashes, write_json
from production_render import render_shot
from production_workflow import record_review, review_status, review_template, shot_dependencies


class ProductionProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='hatch-provenance-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.project = build_fixture_project(self.root)

    def reference(self, relative):
        return {'path': relative, 'sha256': file_sha(self.root / relative)}

    def test_character_provenance_sources_and_supporting_references_expire_only_consumers(self):
        for relative in ('original-design.txt', 'construction-receipt.json'):
            (self.root / relative).write_text('Original synthetic supporting evidence: ' + relative + '\n')
        cast = read_json(self.root / 'cast.json')
        cast['characters'][0]['provenance'].update({
            'source': self.reference('original-design.txt'),
            'references': [self.reference('construction-receipt.json')]})
        write_json(self.root / 'cast.json', cast)
        second = read_json(self.root / 'second-scene.json')
        second['shots'][0]['instances'] = [second['shots'][0]['instances'][1]]
        second['shots'][0]['instances'][0]['bindings'].pop('partner')
        second['continuity'][0]['characters'] = ['b@1.0.0']
        write_json(self.root / 'second-scene.json', second)
        refresh_project_hashes(self.root)
        bundle = load_project(self.project)
        before = {shot: shot_dependencies(self.root, scene_id, shot, project=bundle)
                  for scene_id, shot in [('first-scene', 'exchange'), ('second-scene', 'reuse')]}
        targets = [{'kind': 'character', 'character_id': 'a', 'version': '1.0.0'},
                   {'kind': 'shot', 'scene_id': 'first-scene', 'shot_id': 'exchange'}]
        for target in targets:
            receipt = review_template(self.root, target, ['identity_construction'])
            receipt['reviewer'] = {'kind': 'synthetic', 'id': 'provenance-regression',
                                   'name': 'Synthetic supporting provenance gate only'}
            receipt['dimensions']['identity_construction'].update({
                'verdict': 'pass', 'notes': 'Synthetic fixture bytes only; no construction art acceptance.',
                'evidence': [{**self.reference('art/a-body.png'), 'method': 'automated_check',
                             'note': 'Synthetic image integrity.'}]})
            record_review(self.root, receipt)
        for relative in ('original-design.txt', 'construction-receipt.json'):
            with self.subTest(reference=relative):
                path = self.root / relative
                old = path.read_bytes()
                try:
                    path.write_bytes(old + b'Changed supporting provenance.\n')
                    with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                        load_project(self.project)
                    diagnostic = load_project(self.project, verify_hashes=False)
                    after = shot_dependencies(self.root, 'first-scene', 'exchange', project=diagnostic)
                    self.assertNotEqual(before['exchange']['provenance_file:' + relative], after['provenance_file:' + relative])
                    self.assertEqual(before['reuse'], shot_dependencies(self.root, 'second-scene', 'reuse', project=diagnostic))
                    for target in targets:
                        status = review_status(self.root, target)['dimensions']['identity_construction']
                        self.assertEqual('stale', status['status'])
                        self.assertIn('provenance_file:' + relative, status['changed_dependencies'])
                finally:
                    path.write_bytes(old)

    def test_audio_supporting_receipt_and_text_tampering_invalidates_only_the_consuming_shot(self):
        original = self.root / 'audio/original.wav'
        original.parent.mkdir()
        with wave.open(str(original), 'wb') as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(8000)
            stream.writeframes(b'\x01\x00' * 8000)
        (self.root / 'audio/line.wav').write_bytes(original.read_bytes())
        (self.root / 'audio/text.txt').write_text('Explicit synthetic cue; no speech or art acceptance.\n')
        write_json(self.root / 'audio/receipt.json', {
            'kind': 'synthetic-audio-test-record', 'source': self.reference('audio/original.wav'),
            'text': self.reference('audio/text.txt'), 'method': 'Locally authored test PCM.'})
        bundle = load_project(self.project)
        scene = copy.deepcopy(bundle['scenes'][0])
        scene['shots'][0]['audio'] = [{
            'id': 'test-cue', 'file': self.reference('audio/line.wav'), 'start_frame': 0,
            'duration_frames': 12, 'speaker': 'a', 'text': 'Synthetic cue', 'gain': 1,
            'mouth_cues': [], 'provenance': {**fixture_provenance(),
                'source': self.reference('audio/original.wav'),
                'references': [self.reference('audio/receipt.json'), self.reference('audio/text.txt')]}}]
        write_json(self.root / 'first-scene.json', scene)
        refresh_project_hashes(self.root)
        bundle = load_project(self.project)
        before = {shot: shot_dependencies(self.root, scene_id, shot, project=bundle)
                  for scene_id, shot in [('first-scene', 'exchange'), ('second-scene', 'reuse')]}
        render_shot(bundle, 'exchange', self.root / 'renders/exchange', track_layers=False)
        target = {'kind': 'shot', 'scene_id': 'first-scene', 'shot_id': 'exchange'}
        receipt = review_template(self.root, target, ['timing_av_sync'],
                                  'renders/exchange/render-manifest.json')
        receipt['reviewer'] = {'kind': 'synthetic', 'id': 'provenance-regression',
                               'name': 'Synthetic provenance gate only'}
        receipt['dimensions']['timing_av_sync'].update({
            'verdict': 'pass', 'notes': 'Synthetic PCM integrity gate; no auditory or artwork acceptance.',
            'evidence': [{**self.reference('renders/exchange/audio.wav'),
                         'method': 'automated_check', 'note': 'Synthetic exact-byte PCM evidence.'}]})
        record_review(self.root, receipt)
        self.assertEqual('pass', review_status(self.root, target)['dimensions']['timing_av_sync']['status'])

        for relative in ('audio/text.txt', 'audio/receipt.json'):
            with self.subTest(reference=relative):
                path = self.root / relative
                old = path.read_bytes()
                try:
                    path.write_bytes(old + b'\nchanged supporting provenance\n')
                    with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                        load_project(self.project)
                    diagnostic = load_project(self.project, verify_hashes=False)
                    self.assertIn(relative, [item['path'] for item in diagnostic['stale']])
                    after = shot_dependencies(self.root, 'first-scene', 'exchange', project=diagnostic)
                    self.assertNotEqual(before['exchange']['audio_file:' + relative], after['audio_file:' + relative])
                    self.assertEqual(before['reuse'], shot_dependencies(self.root, 'second-scene', 'reuse', project=diagnostic))
                    status = review_status(self.root, target)['dimensions']['timing_av_sync']
                    self.assertEqual('stale', status['status'])
                    self.assertIn('audio_file:' + relative, status['changed_dependencies'])
                finally:
                    path.write_bytes(old)
        self.assertEqual('pass', review_status(self.root, target)['dimensions']['timing_av_sync']['status'])


if __name__ == '__main__':
    unittest.main()
