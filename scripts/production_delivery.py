"""Verify and reconstruct the public Milo/Luma delivery from pinned original bytes.

No network, image provider, TTS process, or review submission is used here. The
historical ledger and evidence remain historical when the renderer changes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from asset_contracts import hash_object
import production_sources as sources

MANIFEST = 'delivery-manifest.json'
BUNDLES = {
    'artwork': 'source-bundle',
    'audio': 'audio-source-bundle',
    'reviews': 'reviews-source-bundle',
    'evidence': 'evidence-source-bundle',
    'reconstruction': 'project-source-bundle',
}


def _read(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > sources.MAX_INDEX_BYTES * 2:
        raise ValueError('delivery metadata is missing or exceeds its byte bound: ' + str(path))
    return json.loads(path.read_bytes(), object_pairs_hook=sources._unique_object)


def _manifest(pilot):
    pilot = Path(pilot).resolve()
    value = _read(sources._path(pilot, MANIFEST))
    if (value.get('schema_version') != 1 or value.get('kind') != 'hatch-public-production-delivery'
            or value.get('fixture') is not False or value.get('project_id') != 'milo-luma-pilot'
            or set(value.get('bundles', {})) != set(BUNDLES)):
        raise ValueError('unsupported or incomplete public production delivery manifest')
    for section in ('project_files', 'supporting_files', 'public_files'):
        items = value.get(section)
        if not isinstance(items, list) or not 1 <= len(items) <= sources.MAX_FILES:
            raise ValueError('delivery requires a bounded ' + section + ' inventory')
        names = []
        for item in items:
            sources._keys(item, ('path', 'bytes', 'sha256'), section)
            sources._path(pilot, item['path'])
            sources._sha(item['sha256'], section + '.sha256')
            sources._integer(item['bytes'], 0, sources.MAX_FILE_BYTES, section + '.bytes')
            names.append(item['path'])
        if len(names) != len(set(names)):
            raise ValueError('duplicate delivery file path')
        sources._portable_inventory(names)
    return pilot, value


def _same_file(path, record):
    return (path.is_file() and not path.is_symlink()
            and path.stat().st_size == record['bytes']
            and sources._hash_bounded(path, record['bytes']) == record['sha256'])


def _model_differences(pilot, project, records):
    """Expose bounded byte/pixel diagnostics without accepting a changed model."""
    from PIL import Image, features

    def first_difference(expected, actual, at='$'):
        if type(expected) is not type(actual):
            return {'field': at, 'expected': expected, 'actual': actual}
        if isinstance(expected, dict):
            if set(expected) != set(actual):
                return {'field': at, 'expected_keys': sorted(expected), 'actual_keys': sorted(actual)}
            for key in sorted(expected):
                found = first_difference(expected[key], actual[key], at + '.' + key)
                if found is not None:
                    return found
        elif isinstance(expected, list):
            if len(expected) != len(actual):
                return {'field': at, 'expected_length': len(expected), 'actual_length': len(actual)}
            for number, (left, right) in enumerate(zip(expected, actual)):
                found = first_difference(left, right, at + '[' + str(number) + ']')
                if found is not None:
                    return found
        elif expected != actual:
            return {'field': at, 'expected': expected, 'actual': actual}
        return None

    def references(value):
        if isinstance(value, dict):
            if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
                yield value
            for child in value.values():
                yield from references(child)
        elif isinstance(value, list):
            for child in value:
                yield from references(child)

    changed, images = [], {}
    for record in records:
        path = sources._path(project, record['path'])
        if _same_file(path, record):
            continue
        expected, actual = _read(sources._path(pilot, record['path'])), _read(path)
        changed.append({'path': record['path'], 'expected_sha256': record['sha256'],
                        'actual_sha256': sources._hash_bounded(path, path.stat().st_size),
                        'first_difference': first_difference(expected, actual)})
        for reference in references(expected):
            relative = reference['path']
            if not relative.endswith('.png') or relative in images or len(images) >= 8:
                continue
            image_path = sources._path(project, relative)
            if not image_path.is_file():
                continue
            digest = sources._hash_bounded(image_path, image_path.stat().st_size)
            if digest != reference['sha256']:
                with Image.open(image_path) as image:
                    rgba = image.convert('RGBA')
                    images[relative] = {'expected_sha256': reference['sha256'], 'actual_sha256': digest,
                        'size': list(rgba.size), 'rgba_sha256': hashlib.sha256(rgba.tobytes()).hexdigest()}
    return {'files': changed, 'images': images, 'pillow_zlib': features.version('zlib')}


def _bundle_bytes(bundle, index, relative):
    entry = next((item for item in index['files'] if item['path'] == relative), None)
    if entry is None:
        raise ValueError('required original is not in the delivery: ' + relative)
    data = b''.join(sources._path(bundle, part).read_bytes() for part in entry['parts'])
    if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
        raise ValueError('original changed after delivery verification: ' + relative)
    return data


def _history(raw, expected):
    if hashlib.sha256(raw).hexdigest() != expected['sha256']:
        raise ValueError('historical review bytes differ from the pinned original ledger')
    state = json.loads(raw, object_pairs_hook=sources._unique_object)
    if (state.get('schema_version') != 2 or state.get('project_id') != 'milo-luma-pilot'
            or state.get('fixture') is not False or len(state.get('reviews', [])) != expected['records']):
        raise ValueError('historical review identity, label or record count differs')
    prior, kinds, evidence = None, set(), {}
    for entry in state['reviews']:
        if (entry.get('previous_sha256') != prior
                or entry.get('sha256') != hash_object({k: v for k, v in entry.items() if k != 'sha256'})):
            raise ValueError('historical review chain differs from its original linked records')
        receipt = entry['receipt']
        kind = receipt['reviewer']['kind']
        if (receipt.get('fixture') is not False or kind not in ('assistant', 'human')
                or entry['human_review'] is not (kind == 'human')):
            raise ValueError('historical reviewer identity or evidence class differs')
        kinds.add(kind)
        for dimension in receipt['dimensions'].values():
            for item in dimension['evidence']:
                evidence.setdefault(item['path'], set()).add(item['sha256'])
        prior = entry['sha256']
    if prior != expected['last_review_sha256'] or sorted(kinds) != expected['reviewer_kinds']:
        raise ValueError('historical review chain tip or reviewer kinds differ')
    return {'sha256': expected['sha256'], 'records': len(state['reviews']),
            'last_review_sha256': prior, 'reviewer_kinds': sorted(kinds),
            'human_review': 'human' in kinds, 'chain_verified': True}, evidence


def verify_delivery(pilot):
    """Fail closed on every required bundle, source receipt and historical artifact."""
    pilot, manifest = _manifest(pilot)
    reports, indexes, originals = {}, {}, {}
    for role, directory in BUNDLES.items():
        record = manifest['bundles'][role]
        if record.get('path') != directory:
            raise ValueError('delivery bundle path differs from its supported role')
        report = sources.verify_source_bundle(pilot / directory)
        if report['fixture']:
            raise ValueError('a synthetic bundle cannot satisfy public production delivery')
        for key in ('bundle_sha256', 'file_count', 'unique_part_count', 'total_bytes', 'unique_part_bytes'):
            if report[key] != record.get(key):
                raise ValueError('pinned delivery inventory differs: ' + role + '.' + key)
        reports[role] = {key: report[key] for key in record if key != 'path'}
        indexes[role] = _read(pilot / directory / sources.SOURCE_INDEX)
        for item in report['files']:
            if item['path'] in originals and originals[item['path']]['sha256'] != item['sha256']:
                raise ValueError('delivery bundles contain conflicting original files')
            originals[item['path']] = item
    sources._portable_inventory(originals)
    for item in manifest['project_files'] + manifest['supporting_files']:
        if not _same_file(sources._path(pilot, item['path']), item):
            raise ValueError('pinned public project/evidence file differs: ' + item['path'])
        if item['path'] in originals and originals[item['path']]['sha256'] != item['sha256']:
            raise ValueError('public metadata differs from its immutable source transport')
        originals[item['path']] = item

    for item in manifest['public_files']:
        if not _same_file(sources._path(pilot, item['path']), item):
            raise ValueError('pinned public demonstration file differs: ' + item['path'])

    # Every dependency in the original serialized model must resolve to exact
    # transported bytes, including its original derived PNG and padded PCM files.
    from production_contracts import _walk_refs
    for item in manifest['project_files']:
        for reference, label in _walk_refs(_read(pilot / item['path']), item['path']):
            if originals.get(reference['path'], {}).get('sha256') != reference['sha256']:
                raise ValueError('original model dependency is missing or differs: ' + label)

    def metadata(role, path):
        return json.loads(_bundle_bytes(pilot / BUNDLES[role], indexes[role], path),
                          object_pairs_hook=sources._unique_object)

    acquisitions = []
    for name in ('milo', 'luma'):
        state = metadata('artwork', 'acquisition/' + name + '/imagegen-jobs.json')
        if state.get('fixture_mode') is not False:
            raise ValueError('original acquisition cannot be a fixture')
        for job, suffix in (('base', 'turnaround'), ('parts', 'parts')):
            record = next(item for item in state['jobs'] if item['id'] == job)
            original = 'art/originals/' + name + '-' + suffix + '-v3.png'
            receipt = metadata('artwork', 'acquisition/handoffs/' + name + '-' + job + '.json')
            if (record['status'] != 'generated' or record['source_origin'] != 'imagegen'
                    or record['source_hash'] != originals[original]['sha256']
                    or receipt['receipt_template'] != record['generation_receipt']):
                raise ValueError('original artwork no longer matches its authentic acquisition')
            acquisitions.append({'character': name, 'job': job, 'path': original,
                                 'sha256': record['source_hash'], 'attempts': record['attempts']})
    for number in range(1, 6):
        record = metadata('audio', f'audio/original/line-{number:02}.json')
        for field in ('audio', 'text'):
            reference = record[field]
            if originals.get(reference['path'], {}).get('sha256') != reference['sha256']:
                raise ValueError('original speech no longer matches its authentic TTS receipt')
        if record.get('kind') != 'local-tts-record' or not record.get('voice') or not record.get('engine'):
            raise ValueError('original speech lacks its engine and voice provenance')
    raw = _bundle_bytes(pilot / BUNDLES['reviews'], indexes['reviews'], 'production-workflow.json')
    history, evidence = _history(raw, manifest['history'])
    for relative, hashes in evidence.items():
        if hashes != {originals.get(relative, {}).get('sha256')}:
            raise ValueError('authentic review supporting evidence is missing or differs: ' + relative)
    return {'verified': True, 'schema_version': 1, 'project_id': manifest['project_id'],
            'version': manifest['version'], 'fixture': False, 'bundles': reports,
            'acquisitions': acquisitions, 'original_audio_recordings': 5,
            'history': {**history, 'supporting_evidence_files': len(evidence), 'evidence_verified': True},
            'public_files_verified': len(manifest['public_files']),
            'provider_called': False, 'tts_called': False, 'visual_review_performed': False,
            'new_approval_recorded': False,
            'scope': 'Original byte integrity, provenance and historical evidence; current render acceptance remains separately scoped.'}


def restore_pilot(pilot, destination):
    """Stage all original inputs and the reconstruction before publishing a new directory."""
    destination = sources._new_destination(destination)
    pilot, manifest = _manifest(pilot)
    verified = verify_delivery(pilot)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.hatch-pilot-build-', dir=destination.parent) as temporary:
        stage = Path(temporary)
        project = stage / 'project'
        sources.restore_source_bundle(pilot / BUNDLES['artwork'], project)
        for role in ('audio', 'reviews', 'evidence', 'reconstruction'):
            sources.restore_source_bundle(pilot / BUNDLES[role], stage / role)
        shutil.copytree(stage / 'audio/audio', project / 'audio')
        from production_contracts import load_project
        # Restore the original serialized model and derived asset bytes. Native
        # PNG encoders and libm authoring results vary by platform; reauthoring
        # them would change the very hashes the historical records preserve.
        reconstruction = _read(pilot / BUNDLES['reconstruction'] / sources.SOURCE_INDEX)
        for item in reconstruction['files']:
            target = sources._path(project, item['path'])
            if target.exists():
                raise ValueError('original project transport conflicts with another source: ' + item['path'])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(sources._path(stage / 'reconstruction', item['path']), target)
        differences = _model_differences(pilot, project, manifest['project_files'])
        if differences['files']:
            raise ValueError('reconstructed model differs from the retained project; '
                             + json.dumps(differences, sort_keys=True))
        for item in manifest['supporting_files']:
            target = sources._path(project, item['path'])
            if target.exists():
                if not _same_file(target, item):
                    raise ValueError('reconstruction conflicts with retained evidence: ' + item['path'])
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(sources._path(pilot, item['path']), target)
        shutil.copyfile(stage / 'reviews/production-workflow.json', project / 'production-workflow.json')
        media_index = _read(pilot / BUNDLES['evidence'] / sources.SOURCE_INDEX)
        mapping = {}
        for item in media_index['files']:
            # Historical sampled frames must not create an incomplete live render
            # destination or silently stand in for a newly rendered manifest.
            relative = ('historical/' + item['path'] if item['path'].startswith('renders/') else item['path'])
            target = sources._path(project, relative)
            if target.exists():
                raise ValueError('historical evidence conflicts with a reconstructed file')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(sources._path(stage / 'evidence', item['path']), target)
            mapping[item['path']] = relative
        # Recheck every original after staging; publication must never alter source bytes.
        for role in ('artwork', 'audio', 'reviews', 'reconstruction'):
            index = _read(pilot / BUNDLES[role] / sources.SOURCE_INDEX)
            for item in index['files']:
                if not _same_file(sources._path(project, item['path']), item):
                    raise ValueError('reconstruction changed an immutable original: ' + item['path'])
        bundle = load_project(project)
        sources.workflow._state(project, bundle)
        report = {**verified, 'reconstructed': True, 'characters': len(bundle['characters']),
                  'clips': len(bundle['clips']),
                  'scenes': [{'id': scene['id'], 'frames': sum(shot['duration_frames'] for shot in scene['shots'])}
                             for scene in bundle['scenes']],
                  'recipe_reauthored': False,
                  'reconstruction_method': 'Exact original model and derived assets from pinned transports; no native PNG re-encoding or floating-point authoring.',
                  'historical_artifact_paths': mapping,
                  'review_freshness': 'Original ledger retained verbatim. Historical sampled frames are separate; final render reviews must be revalidated against the current renderer and complete outputs.'}
        (project / 'delivery-restoration.json').write_bytes(
            (json.dumps(report, sort_keys=True, indent=2) + '\n').encode('utf-8'))
        sources._publish_stage(project, destination)
    return {**report, 'restored': str(destination)}
