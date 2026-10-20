"""Explicit installed-imagegen handoffs for occluded geometry, with observed anchors.

The controller emits claims and validates ingested artifacts; it never performs
an imagegen call. Limits bound claims, not a provider account or invented prices.
"""
from __future__ import annotations

import copy
from pathlib import Path
import shutil
import tempfile
import uuid

from PIL import Image

from asset_contracts import check_image, hash_object, sha, strict_keys, text
from character_decomposition import (_content_image, _image, _previews, _pending, load_decomposition,
    read_json, save_manifest, _promote_decomposition)
from decomposition_masks import apply_mask, binary, count, decode_mask, intersect, subtract, union
from decomposition_spec import MODEL_CALL, component_signature, safe_path, validate_structure
from extract_strip_frames import atomic_json


def _jobs(root):
    path = safe_path(root, 'reconstruction/jobs.json')
    value = read_json(path) if path.exists() else {'schema_version': 1,
        'limits': {'attempts_per_component': 3, 'concurrency': 1, 'total_claims': 16}, 'jobs': []}
    strict_keys(value, {'schema_version', 'limits', 'jobs'}, 'reconstruction jobs')
    if type(value.get('schema_version')) is not int or value['schema_version'] != 1 or not isinstance(value.get('jobs'), list):
        raise ValueError('invalid reconstruction handoff state')
    limits = value.get('limits')
    strict_keys(limits, {'attempts_per_component', 'concurrency', 'total_claims'}, 'reconstruction limits')
    for key in ('attempts_per_component', 'concurrency', 'total_claims'):
        if type(limits.get(key)) is not int or not 1 <= limits[key] <= 128:
            raise ValueError('reconstruction limits must be integers in 1..128')
    for job in value['jobs']:
        if job.get('status') not in ('running', 'failed', 'ingested') or not isinstance(job.get('token'), str):
            raise ValueError('invalid reconstruction job state')
    return value


def _component(manifest, identifier):
    matches = [c for c in manifest['components'] if c['id'] == identifier]
    if len(matches) != 1:
        raise ValueError('choose one existing component for reconstruction')
    if matches[0]['category'] == 'unassigned':
        raise ValueError('identify the component before reconstructing its hidden shape')
    return matches[0]


def _require_enabled(manifest, allowed):
    if allowed is not True or manifest['mode'] != 'assisted':
        raise ValueError('hidden reconstruction requires an assisted-mode run and explicit --allow-reconstruction')


def request_reconstruction(root, identifier, note, hidden_mask=None, allow_reconstruction=False):
    root = Path(root).resolve()
    manifest = load_decomposition(root)
    _require_enabled(manifest, allow_reconstruction)
    text(note, 'reconstruction request note')
    component = _component(manifest, identifier)
    jobs = _jobs(root)
    existing = next((j for j in jobs['jobs'] if j['component_id'] == identifier and j['status'] == 'running'), None)
    if existing:
        return {**existing, 'resumed': True, 'model_called': False}
    if len(jobs['jobs']) >= jobs['limits']['total_claims']:
        raise ValueError('reconstruction total claim budget exhausted')
    if sum(j['component_id'] == identifier for j in jobs['jobs']) >= jobs['limits']['attempts_per_component']:
        raise ValueError('reconstruction component attempt budget exhausted')
    if sum(j['status'] == 'running' for j in jobs['jobs']) >= jobs['limits']['concurrency']:
        raise ValueError('reconcile the active reconstruction claim before starting another')
    size = (manifest['canvas']['width'], manifest['canvas']['height'])
    # A conservative default only considers documented front occluders. The
    # artifact author must still identify which of their pixels contain the part.
    allowed = Image.new('L', size)
    foreground = _image(root, manifest['foreground']).convert('RGBA')
    opaque = foreground.getchannel('A').point(lambda p: 255 if p == 255 else 0)
    front_ids = {c['id'] for c in manifest['components']
                 if (c['z_index'], c['id']) > (component['z_index'], component['id'])}
    front_support = Image.new('L', size)
    for other in manifest['components']:
        if other['id'] in front_ids:
            front_support = union(front_support, _image(root, other['mask']).convert('L'))
    if hidden_mask is not None:
        spec = {'path': str(Path(hidden_mask).resolve())} if isinstance(hidden_mask, (str, Path)) else hidden_mask
        allowed = decode_mask(spec, size, root)
    else:
        for other in manifest['components']:
            if other['id'] in component['occlusion']['occluded_by']:
                allowed = union(allowed, _image(root, other['mask']).convert('L'))
    allowed = intersect(allowed, intersect(front_support, opaque))
    if not count(allowed):
        raise ValueError('no supported hidden region behind opaque front layers; provide --hidden-mask or record valid occluded_by relationships')
    token = uuid.uuid4().hex
    folder = 'reconstruction/claims/' + token
    permitted = _content_image(root, folder, 'allowed-hidden', allowed)
    prompt = ('Use case: identity-preserve\nAsset type: hidden geometry for a source-bound character component\n'
        'Primary request: reconstruct only the hidden continuation of ' + component['name'] + '. ' + note + '\n'
        'Input images: original character as identity reference; observed component as the edit target; '
        'allowed-hidden mask as a visual placement guide (white permits inferred pixels).\n'
        f'Composition: full original canvas {size[0]}x{size[1]}, unshifted source coordinates.\n'
        'Constraints: preserve original style, colors, texture, scale, orientation and all observed boundaries. '
        'Return one PNG with a genuinely transparent background. Draw only this component, complete behind its recorded occluders. '
        'Do not add new accessories or anatomy. Ingestion retains original observed pixels and uses only permitted hidden pixels.\n'
        'Follow the installed imagegen skill. Inspect all local images before editing. Attach the actual images using '
        'referenced_image_paths when all have local paths, otherwise use its supported recent-image mechanism, never both. '
        'The mask is a reference image, not an invented imagegen mask argument. No provider API or automatic call is made by this request.\n')
    prompt_path = safe_path(root, folder + '/prompt.txt')
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding='utf-8')
    inputs = {manifest['source']['normalized_path']: manifest['source']['normalized_sha256'],
              component['asset']['path']: component['asset']['sha256'], permitted['path']: permitted['sha256'],
              prompt_path.relative_to(root).as_posix(): sha(prompt_path)}
    receipt = {'schema_version': 1, 'kind': 'decomposition-reconstruction', 'token': token,
        'component_id': identifier, 'component_signature': component_signature(component),
        'source_sha256': manifest['source']['sha256'], 'input_hashes': inputs,
        'generation_skill': '$fixture' if manifest['source']['fixture'] else '$imagegen',
        'fixture': manifest['source']['fixture'], 'author': '', 'note': '',
        'model_call': {'id': None, 'model': None, 'parameters': None,
                       'unavailable_reason': 'Record genuine provider metadata if exposed; do not substitute the Hatch token.'}}
    job = {'token': token, 'component_id': identifier, 'component_signature': component_signature(component),
        'source_sha256': manifest['source']['sha256'], 'status': 'running', 'allowed_mask': permitted,
        'input_hashes': inputs, 'receipt_template': receipt, 'prompt': folder + '/prompt.txt',
        'input_images': [{'path': p, 'sha256': h, 'role': role} for (p, h), role in zip(list(inputs.items())[:3], ('identity', 'edit-target', 'mask-guide'))],
        'model_called': False}
    jobs['jobs'].append(job)
    atomic_json(safe_path(root, 'reconstruction/jobs.json'), jobs)
    atomic_json(root / folder / 'receipt-template.json', receipt)
    return job


def fail_reconstruction(root, token, reason):
    root = Path(root).resolve()
    text(reason, 'reconstruction failure note')
    jobs = _jobs(root)
    job = next((j for j in jobs['jobs'] if j['token'] == token and j['status'] == 'running'), None)
    if job is None:
        raise ValueError('reconstruction token is not active')
    job.update(status='failed', failure_note=reason)
    atomic_json(safe_path(root, 'reconstruction/jobs.json'), jobs)
    return {'failed': token, 'component_id': job['component_id'], 'original_component_preserved': True}


def ingest_reconstruction(root, identifier, source, receipt_path, allow_reconstruction=False):
    root = Path(root).resolve()
    manifest = load_decomposition(root)
    _require_enabled(manifest, allow_reconstruction)
    component = _component(manifest, identifier)
    receipt = read_json(receipt_path)
    from decomposition_package import _inventory
    old_files = _inventory(root, exclude_receipt=False)
    strict_keys(receipt, {'schema_version', 'kind', 'token', 'component_id', 'component_signature', 'source_sha256',
        'input_hashes', 'generation_skill', 'fixture', 'author', 'note', 'model_call'}, 'reconstruction receipt')
    jobs = _jobs(root)
    job = next((j for j in jobs['jobs'] if j['token'] == receipt.get('token') and j['status'] == 'running'), None)
    if job is None or job['component_id'] != identifier:
        raise ValueError('reconstruction receipt must name the active component/token')
    if type(receipt.get('schema_version')) is not int or receipt['schema_version'] != 1 or receipt.get('kind') != 'decomposition-reconstruction':
        raise ValueError('unsupported reconstruction receipt')
    for key in ('component_id', 'component_signature', 'source_sha256', 'input_hashes'):
        if receipt.get(key) != job[key]:
            raise ValueError('reconstruction receipt differs from the claimed inputs: ' + key)
    if job['component_signature'] != component_signature(component) or job['source_sha256'] != manifest['source']['sha256']:
        raise ValueError('reconstruction component/source changed; fail the stale claim before retrying')
    for path, expected in job['input_hashes'].items():
        if sha(safe_path(root, path)) != expected:
            raise ValueError('reconstruction grounding input changed; fail the stale claim before retrying')
    if receipt.get('fixture') is not manifest['source']['fixture'] or receipt.get('generation_skill') != ('$fixture' if manifest['source']['fixture'] else '$imagegen'):
        raise ValueError('reconstruction receipt must retain the actual fixture/imagegen origin')
    text(receipt.get('author'), 'reconstruction receipt author')
    text(receipt.get('note'), 'reconstruction inspection note')
    call = receipt.get('model_call')
    strict_keys(call, {'id', 'model', 'parameters', 'unavailable_reason'}, 'model call metadata')
    validate_structure(call, MODEL_CALL, 'reconstruction model call metadata')
    if (call.get('id') is None or call.get('model') is None) and not call.get('unavailable_reason', '').strip():
        raise ValueError('unavailable model call metadata requires an explicit unavailable_reason')
    if call.get('id') == job['token']:
        raise ValueError('a Hatch claim token is not a provider call identifier')
    source = Path(source).resolve()
    if source.is_relative_to(root):
        raise ValueError('reconstruction source must be the original output outside this decomposition')
    check_image(source)
    output_hash = sha(source)
    with Image.open(source) as generated:
        if generated.format != 'PNG' or generated.mode != 'RGBA' or generated.size != (manifest['canvas']['width'], manifest['canvas']['height']):
            raise ValueError('reconstruction output must be full-canvas RGBA PNG without resizing')
        generated = generated.copy()
    allowed = _image(root, job['allowed_mask']).convert('L')
    inferred_mask = intersect(binary(generated.getchannel('A')), allowed)
    if not count(inferred_mask):
        raise ValueError('reconstruction supplied no pixels in the explicitly permitted hidden region')
    hidden = apply_mask(generated, inferred_mask)
    observed = _image(root, component['asset']).convert('RGBA')
    completed = hidden.copy()
    completed.alpha_composite(observed, tuple(component['bbox'][:2]))
    bbox = list(completed.getchannel('A').getbbox())
    stage = Path(tempfile.mkdtemp(prefix='.' + root.name + '-decomposition-edit-', dir=root.parent))
    journal = root.parent / ('.' + root.name + '.decomposition-transaction.json')
    try:
        shutil.copytree(root, stage, dirs_exist_ok=True)
        folder = 'reconstruction/results/' + job['token']
        output_path = safe_path(stage, folder + '/original-output.png')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, output_path)
        if sha(output_path) != output_hash or sha(source) != output_hash:
            raise ValueError('reconstruction source changed during ingestion')
        atomic_json(stage / folder / 'receipt.json', receipt)
        target = _component(manifest, identifier)
        target['provenance']['reconstruction'] = {'kind': 'inferred', 'status': 'pending-review',
            'asset': _content_image(stage, folder, 'completed', completed.crop(bbox)), 'bbox': bbox,
            'inferred_mask': _content_image(stage, folder, 'inferred', inferred_mask), 'allowed_mask': job['allowed_mask'],
            'original_output': {'path': folder + '/original-output.png', 'sha256': output_hash},
            'receipt': {'path': folder + '/receipt.json', 'sha256': sha(stage / folder / 'receipt.json')},
            'observed_asset': copy.deepcopy(target['asset']), 'source_sha256': manifest['source']['sha256'],
            'token': job['token'], 'input_hashes': job['input_hashes'], 'fixture': manifest['source']['fixture'],
            'model_call': call, 'note': receipt['note']}
        target['review'] = _pending()
        target['uncertainty'].append('Hidden artwork was inferred and needs independent visual review; observed asset remains unchanged.')
        manifest['revision'] += 1
        history = stage / 'annotations/history' / (f'{manifest["revision"] - 1:06d}-' + sha(root / 'decomposition.json')[:12])
        history.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(root / 'decomposition.json', history / 'decomposition.json')
        shutil.copyfile(root / 'annotations/current.json', history / 'annotation.json')
        jobs['jobs'][jobs['jobs'].index(job)].update(status='ingested', output_sha256=output_hash,
            receipt=target['provenance']['reconstruction']['receipt'])
        atomic_json(stage / 'reconstruction/jobs.json', jobs)
        _previews(stage, manifest)
        from character_decomposition import recompose, _save_image
        _save_image(stage, 'previews/assisted-reconstruction.png', recompose(stage, manifest, inferred=True))
        save_manifest(stage, manifest, transactional=False)
        load_decomposition(stage)
        _promote_decomposition(root, stage, old_files)
        return {'ingested': identifier, 'inferred_pixels': count(inferred_mask), 'original_asset_preserved': True,
                'review_required': True, 'fixture': manifest['source']['fixture'], 'model_called_by_controller': False}
    finally:
        if stage.exists() and not journal.exists():
            shutil.rmtree(stage)
