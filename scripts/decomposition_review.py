"""Offline semantic-mask editing and exact-source-bound, versioned human review.

The browser edits annotations, never the supplied image. Applying the downloaded
receipt uses the deterministic decomposition pipeline. A receipt is an
attestation by its named reviewer, not evidence of automatic semantic analysis.
The CLI owns the run lock when calling the mutation functions in this module.
"""
from __future__ import annotations

import base64
import copy
import json
from pathlib import Path
import shutil
import tempfile
import time

from asset_contracts import hash_object, resolve_ref, sha, strict_keys, text


MAX_RECEIPT_BYTES = 32 * 1024 * 1024
REVIEW_KIND = 'character-decomposition-review'


def _read(path):
    path = Path(path)
    if path.stat().st_size > MAX_RECEIPT_BYTES:
        raise ValueError('decomposition review JSON exceeds the 32 MiB bound')

    def unique(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('duplicate JSON field: ' + key)
            value[key] = item
        return value

    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)


def _atomic(path, value):
    from hatch import atomic
    atomic(path, value)


def _core():
    import character_decomposition
    return character_decomposition


def _accepted(manifest):
    return manifest.get('review', {}).get('status') == 'approved' and manifest.get('validation', {}).get('ok') is True


def _history(root, source_hash):
    path = resolve_ref(root, 'review/revisions/index.json')
    if not path.exists():
        return {'schema_version': 1, 'source_sha256': source_hash, 'revisions': []}
    value = _read(path)
    strict_keys(value, {'schema_version', 'source_sha256', 'revisions'}, 'decomposition review history')
    if value.get('schema_version') != 1 or value.get('source_sha256') != source_hash or not isinstance(value.get('revisions'), list):
        raise ValueError('decomposition review history is not bound to this source')
    known = set()
    for item in value['revisions']:
        if not isinstance(item, dict) or type(item.get('id')) is not int or item['id'] < 1 or item['id'] in known:
            raise ValueError('invalid decomposition review revision index')
        known.add(item['id'])
    return value


def _snapshot(root, manifest, author, note):
    """Retain enough exact state to reapply a correction and audit its approvals."""
    history = _history(root, manifest['source']['sha256'])
    manifest_hash = sha(root / 'decomposition.json')
    if history['revisions'] and history['revisions'][-1]['manifest_sha256'] == manifest_hash:
        return history['revisions'][-1]['id']
    revision = max((r['id'] for r in history['revisions']), default=0) + 1
    parent = history['revisions'][-1]['id'] if history['revisions'] else None
    folder = resolve_ref(root, 'review/revisions')
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'{revision:06d}'
    if target.exists():
        raise ValueError('review revision already exists; retain and inspect interrupted history')
    stage = Path(tempfile.mkdtemp(prefix='.revision-', dir=folder))
    try:
        shutil.copyfile(root / 'decomposition.json', stage / 'decomposition.json')
        shutil.copyfile(resolve_ref(root, manifest['annotation']['path']), stage / 'annotation.json')
        record = {'id': revision, 'parent_id': parent, 'author': author, 'note': note,
                  'created_at': time.time(), 'manifest_sha256': manifest_hash,
                  'annotation_sha256': sha(stage / 'annotation.json'),
                  'accepted': _accepted(manifest)}
        _atomic(stage / 'snapshot.json', {'schema_version': 1,
            'source_sha256': manifest['source']['sha256'], **record})
        stage.rename(target)
        history['revisions'].append(record)
        _atomic(folder / 'index.json', history)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return revision


def review_template(root):
    root = Path(root).resolve()
    manifest = _core().load_decomposition(root)
    return {'schema_version': 1, 'kind': REVIEW_KIND,
            'source_sha256': manifest['source']['sha256'],
            'base_manifest_sha256': sha(root / 'decomposition.json'),
            'author': '', 'note': '',
            'annotation': _read(resolve_ref(root, manifest['annotation']['path'])),
            'reviews': []}


def _validate_envelope(root, value, manifest):
    strict_keys(value, {'schema_version', 'kind', 'source_sha256', 'base_manifest_sha256',
        'author', 'note', 'annotation', 'reviews', 'restore_revision'}, 'decomposition review receipt')
    if type(value.get('schema_version')) is not int or value['schema_version'] != 1 or value.get('kind') != REVIEW_KIND:
        raise ValueError('decomposition review requires schema_version 1 and character-decomposition-review kind')
    if value.get('source_sha256') != manifest['source']['sha256']:
        raise ValueError('decomposition review must bind the exact original source sha256')
    if value.get('base_manifest_sha256') != sha(root / 'decomposition.json'):
        raise ValueError('decomposition review is stale: rebuild the desk for the exact current manifest')
    text(value.get('author'), 'review author')
    text(value.get('note'), 'review evidence / correction rationale')
    if len(value['author']) > 8192 or len(value['note']) > 16384:
        raise ValueError('review author or rationale exceeds supported text bounds')
    if 'restore_revision' in value:
        if value.get('annotation') is not None or value.get('reviews'):
            raise ValueError('restoration cannot be mixed with new annotations or approvals')
        if type(value['restore_revision']) is not int or value['restore_revision'] < 1:
            raise ValueError('restore_revision must be a positive integer')
        return
    annotation = value.get('annotation')
    if not isinstance(annotation, dict) or annotation.get('source_sha256') != manifest['source']['sha256']:
        raise ValueError('corrected annotation must bind the exact original source sha256')
    records = annotation.get('components')
    if not isinstance(records, list) or any(not isinstance(c, dict) or not isinstance(c.get('id'), str) for c in records):
        raise ValueError('corrected annotation requires component records with ids')
    known = {c['id']: c for c in records}
    reviews = value.get('reviews', [])
    if not isinstance(reviews, list) or len(reviews) > len(known):
        raise ValueError('review verdicts must be a list with at most one verdict per component')
    current = {c['id']: c for c in manifest['components']}
    seen = set()
    for verdict in reviews:
        strict_keys(verdict, {'id', 'status', 'note', 'inspected', 'inferred_acknowledged'}, 'component review verdict')
        identifier = verdict.get('id')
        if identifier not in known or identifier in seen:
            raise ValueError('review verdict must name a unique corrected component')
        seen.add(identifier)
        if verdict.get('status') not in ('pending', 'approved', 'rejected'):
            raise ValueError('component verdict must be pending, approved, or rejected')
        for key in ('inspected', 'inferred_acknowledged'):
            if key in verdict and type(verdict[key]) is not bool:
                raise ValueError('component review ' + key + ' must be boolean')
        if verdict['status'] != 'pending':
            text(verdict.get('note'), 'component review evidence note')
            if verdict.get('inspected') is not True:
                raise ValueError('component approval/rejection requires explicit source and mask inspection')
        if not isinstance(verdict.get('note', ''), str) or len(verdict.get('note', '')) > 16384:
            raise ValueError('component review note exceeds supported text bounds')
        if verdict['status'] == 'approved' and known[identifier].get('category') == 'unassigned':
            raise ValueError('unassigned foreground cannot be semantically approved; identify and recategorize it first')
        provenance = current.get(identifier, {}).get('provenance', {})
        if verdict['status'] == 'approved' and (provenance.get('kind') == 'inferred' or provenance.get('reconstruction')) and verdict.get('inferred_acknowledged') is not True:
            raise ValueError('inferred content requires explicit reconstruction review acknowledgement')


def _annotation_content(value):
    return {k: v for k, v in value.items() if k not in ('author', 'note')}


def apply_review(root, receipt):
    """Apply real corrected masks, recompose, and bind explicit component verdicts.

    The exact manifest guard prevents an older offline desk from overwriting a
    newer correction or accepting obsolete pixels. Geometry errors fail through
    the same core validator as initial extraction.
    """
    root = Path(root).resolve()
    core = _core()
    manifest = core.load_decomposition(root)
    value = copy.deepcopy(receipt) if isinstance(receipt, dict) else _read(receipt)
    _validate_envelope(root, value, manifest)
    if 'restore_revision' in value:
        return restore_revision(root, value['restore_revision'], value['author'], value['note'])
    previous_annotation = _read(resolve_ref(root, manifest['annotation']['path']))
    corrected = copy.deepcopy(value['annotation'])
    corrected.update(author=value['author'], note=value['note'])
    changed = hash_object(_annotation_content(corrected)) != hash_object(_annotation_content(previous_annotation))
    before = {c['id']: core.component_signature(c) for c in manifest['components']}
    previous_revision = _snapshot(root, manifest, value['author'], 'Before correction: ' + value['note'])
    if changed:
        core.rebuild_from_annotation(root, corrected, reason=value['note'], author=value['author'])
        manifest = core.load_decomposition(root)
    components = {c['id']: c for c in manifest['components']}
    for verdict in value.get('reviews', []):
        component = components[verdict['id']]
        reconstruction = component['provenance'].get('reconstruction')
        if reconstruction and verdict.get('inferred_acknowledged') is True:
            reconstruction['status'] = verdict['status'] if verdict['status'] != 'pending' else 'pending-review'
        component['review'] = {'status': verdict['status'], 'author': value['author'],
            'note': verdict.get('note', ''),
            'signature': core.component_signature(component) if verdict['status'] != 'pending' else None}
    core.save_manifest(root, manifest)
    manifest = core.load_decomposition(root)
    current_revision = _snapshot(root, manifest, value['author'], value['note'])
    receipt_path = resolve_ref(root, f'review/receipts/{current_revision:06d}-{hash_object(value)[:16]}.json')
    _atomic(receipt_path, value)
    return {'reviewed': True, 'annotation_changed': changed,
        'previous_revision': previous_revision, 'revision': current_revision,
        'changed_components': [c['id'] for c in manifest['components']
                               if before.get(c['id']) != core.component_signature(c)],
        'removed_components': sorted(set(before) - set(components)),
        'component_reviews': {c['id']: c['review']['status'] for c in manifest['components']},
        'accepted': _accepted(manifest),
        'validation': manifest.get('validation'), 'receipt': receipt_path.relative_to(root).as_posix(),
        'model_call_required': False}


def restore_revision(root, revision, author, note):
    """Reapply an audited annotation snapshot; never manufacture prior approval."""
    root = Path(root).resolve()
    text(author, 'restoration author')
    text(note, 'restoration rationale')
    if type(revision) is not int or revision < 1:
        raise ValueError('decomposition review revision must be a positive integer')
    core = _core()
    current = core.load_decomposition(root)
    history = _history(root, current['source']['sha256'])
    record = next((item for item in history['revisions'] if item['id'] == revision), None)
    if record is None:
        raise ValueError('unknown decomposition review revision')
    folder = resolve_ref(root, f'review/revisions/{revision:06d}')
    if sha(folder / 'decomposition.json') != record['manifest_sha256'] or sha(folder / 'annotation.json') != record['annotation_sha256']:
        raise ValueError('decomposition review revision has changed; restoration refused')
    saved = _read(folder / 'decomposition.json')
    annotation = _read(folder / 'annotation.json')
    if saved['source']['sha256'] != current['source']['sha256'] or annotation['source_sha256'] != current['source']['sha256']:
        raise ValueError('decomposition review revision has the wrong original source hash')
    # Historical assets remain content-addressed in the run. Check every saved
    # raster and inferred-art receipt before changing the current annotation.
    from decomposition_spec import MANIFEST_SCHEMA, safe_path, validate_structure
    validate_structure(saved, MANIFEST_SCHEMA, 'saved decomposition revision')
    for component in saved['components']:
        descriptors = [component['asset'], component['mask']]
        provenance = component['provenance']
        if provenance.get('original_asset'):
            descriptors.append(provenance['original_asset'])
        if provenance.get('reconstruction'):
            descriptors.extend(provenance['reconstruction'][key]
                for key in ('asset', 'inferred_mask', 'allowed_mask', 'receipt', 'original_output'))
        for descriptor in descriptors:
            path = safe_path(root, descriptor['path'])
            if not path.is_file() or sha(path) != descriptor['sha256']:
                raise ValueError('historical component artifact is missing or changed: ' + descriptor['path'])
    previous_revision = _snapshot(root, current, author, 'Before restoration: ' + note)
    core.rebuild_from_annotation(root, annotation, reason='Restore revision ' + str(revision) + ': ' + note, author=author)
    manifest = core.load_decomposition(root)
    previous = {c['id']: c for c in saved['components']}
    restored_reviews = []
    for component in manifest['components']:
        former = previous.get(component['id'])
        verdict = former.get('review', {}) if former else {}
        # Rebuilding a previously accepted annotation records a new correction
        # author. Restore the older provenance only for exactly the same material
        # geometry/pixels and verified immutable historical reconstruction files.
        material = lambda c: {k: v for k, v in c.items() if k not in ('provenance', 'review')}
        if former and material(component) == material(former):
            provenance = former['provenance']
            component['provenance'] = copy.deepcopy(provenance)
        if verdict.get('status') in ('approved', 'rejected') and verdict.get('signature') == core.component_signature(component):
            component['review'] = copy.deepcopy(verdict)
            restored_reviews.append(component['id'])
    core.save_manifest(root, manifest)
    manifest = core.load_decomposition(root)
    current_revision = _snapshot(root, manifest, author, 'Restored revision ' + str(revision) + ': ' + note)
    return {'restored': revision, 'previous_revision': previous_revision, 'revision': current_revision,
            'restored_component_reviews': restored_reviews,
            'component_reviews': {c['id']: c['review']['status'] for c in manifest['components']},
            'accepted': _accepted(manifest),
            'model_call_required': False}


def _data_uri(root, path):
    path = resolve_ref(root, path)
    return 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode('ascii')


def build_review(root, destination):
    """Build a self-contained local editor, without changing the reviewed run."""
    from hatch import _destination
    root = Path(root).resolve()
    core = _core()
    manifest = core.load_decomposition(root)
    out = _destination(root, destination)
    if out == root or out.is_relative_to(root) or root.is_relative_to(out):
        raise ValueError('decomposition review destination must be outside the mutable run')
    if out.exists():
        raise ValueError('review destination must be new; rebuild after decomposition changes')
    template = review_template(root)
    history = _history(root, manifest['source']['sha256'])
    payload = {'template': template, 'manifest': manifest,
               'original': _data_uri(root, manifest['source']['normalized_path']),
               'revisions': history['revisions'],
               'assets': {c['id']: _data_uri(root, c['asset']['path']) for c in manifest['components']},
               'inferred_assets': {c['id']: _data_uri(root, c['provenance']['reconstruction']['asset']['path'])
                   for c in manifest['components'] if c['provenance'].get('reconstruction')},
               'inferred_masks': {c['id']: _data_uri(root, c['provenance']['reconstruction']['inferred_mask']['path'])
                   for c in manifest['components'] if c['provenance'].get('reconstruction')}}
    rendered = REVIEW_HTML.replace('__DECOMPOSITION_DATA__', json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c'))
    out.mkdir(parents=True)
    (out / 'review.html').write_text(rendered, encoding='utf-8')
    _atomic(out / 'review-template.json', template)
    return {'review_ui': str(out / 'review.html'), 'receipt_template': str(out / 'review-template.json'),
            'accepted': False, 'offline': True,
            'instructions': 'Inspect source and masks, edit and recompose, download the bound JSON, then submit with hatch.py decompose-review. A download does not apply or approve changes.'}


REVIEW_HTML = r'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hatch / Character decomposition review</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f1e8;color:#233c36;font:15px system-ui,sans-serif}header{padding:20px 24px;border-bottom:2px solid #233c36}h1{font:30px Georgia,serif;margin:0 0 8px}h2{font-size:17px;margin:18px 0 10px}main{display:grid;grid-template-columns:300px minmax(0,1fr) 300px;gap:18px;padding:18px}aside,section{min-width:0}label{display:block;margin:9px 0}label.inline{display:inline-flex;align-items:center;gap:7px;margin-right:12px}button,input,select,textarea{font:inherit;border:1px solid #879a8d;border-radius:3px;padding:7px;background:#fffef9;color:#233c36}button{cursor:pointer}button.primary{background:#244c3f;color:#fff}button:disabled{opacity:.45;cursor:default}textarea,input[type=text],select{width:100%}input[type=number]{width:84px}input[type=checkbox]{width:auto}textarea{min-height:64px}button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:3px solid #a53a22}fieldset{border:1px solid #a7b4a6;margin:16px 0;padding:12px}.notice{background:#e4eadd;padding:12px;overflow-wrap:anywhere}.warning{color:#89361f}.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:10px 0}.toolbar select{width:auto;max-width:220px}.views{display:grid;grid-template-columns:1fr 1fr;gap:12px}.viewport{height:480px;overflow:auto;border:1px solid #879a8d;background:repeating-conic-gradient(#d5d5d5 0% 25%,#fff 0% 50%) 0/16px 16px;position:relative}canvas{display:block;image-rendering:pixelated;touch-action:none}figcaption,small{font:12px ui-monospace,monospace;overflow-wrap:anywhere}figure{margin:0}#components{max-height:550px;overflow:auto;padding:0;list-style:none}#components li{display:flex;align-items:center;gap:6px;border-bottom:1px solid #c4cebf;padding:6px}#components li.active{background:#dce6d5}#components button{min-width:0;flex:1;text-align:left;background:transparent;border:none;overflow-wrap:anywhere}#components small{display:block;color:#596d60}#status{white-space:pre-wrap;min-height:2em}#asset,#inferred-asset,#inferred-mask{max-width:100%;max-height:200px;background:repeating-conic-gradient(#ddd 0% 25%,white 0% 50%) 0/16px 16px;image-rendering:pixelated}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:8px}.grid2 input{width:100%}.attachment{border-top:1px solid #b7c3b0;padding:8px 0}.attachment input{max-width:100%}details{margin:10px 0}pre{white-space:pre-wrap;font-size:11px;overflow-wrap:anywhere}.danger{border-color:#a53a22;color:#89361f}@media(max-width:1180px){main{grid-template-columns:260px minmax(0,1fr)}aside:last-child{grid-column:1/-1}.views{grid-template-columns:1fr 1fr}}@media(max-width:750px){main{display:block}.views{grid-template-columns:1fr}.viewport{height:350px}}
</style>
<header><h1>Hatch / Character decomposition review</h1><small id="provenance"></small></header>
<main>
<aside><p class="notice">Inspect semantic meaning as well as pixel coverage. Changes stay in this desk until you download and submit the bound correction JSON.</p><h2>Components</h2><div class="toolbar"><button id="show-all">Show all</button><button id="isolate">Isolate</button><button id="hide-all">Hide all</button></div><ul id="components"></ul><fieldset><legend>New semantic component</legend><label>Name <input id="new-name" type="text" placeholder="Visible left ear"></label><label>Identifier <input id="new-id" type="text" placeholder="left-ear"></label><label>Category <input id="new-category" type="text" value="anatomy"></label><button id="add">Add empty component</button><p><small>Paint or assign a polygon before submitting. No missing anatomy is invented.</small></p></fieldset><fieldset><legend>Merge components</legend><label>Merge selected component with <select id="merge-target"></select></label><button id="merge">Merge visible pixel masks</button><p><button id="remove-component" class="danger">Remove selected component label</button></p><small>Its source pixels remain available as unassigned foreground. Child and attachment references are detached for review.</small></fieldset><details><summary>Validation and uncertainty</summary><pre id="diagnostics"></pre></details></aside>
<section><div class="toolbar"><label class="inline">Zoom <select id="zoom"><option value="0.5">50%</option><option value="1" selected>100%</option><option value="2">200%</option><option value="4">400%</option><option value="8">800%</option><option value="16">1600%</option></select></label><button id="undo">Undo edit</button><button id="redo">Redo edit</button><label class="inline"><input type="checkbox" id="overlay" checked> Mask overlay</label><label class="inline"><input type="checkbox" id="boxes"> Bounds</label><label class="inline"><input type="checkbox" id="show-pivots" checked> Pivots</label></div><div class="views"><figure><figcaption>Immutable original image</figcaption><div class="viewport" id="original-viewport"><canvas id="original-canvas"></canvas></div></figure><figure><figcaption>Recomposition / mask editor · canvas coordinates</figcaption><div class="viewport" id="editor-viewport"><canvas id="editor"></canvas></div></figure></div><div class="toolbar"><label class="inline">Tool <select id="tool"><option value="inspect">Inspect</option><option value="paint">Assign brush</option><option value="erase">Erase from component</option><option value="polygon">Assign polygon</option><option value="split">Split selected with polygon</option><option value="foreground-add">Foreground brush: add</option><option value="foreground-erase">Foreground brush: remove</option><option value="pivot">Place pivot</option><option value="attachment">Place attachment</option></select></label><label class="inline">Brush radius <input id="radius" type="number" min="1" max="512" value="3"></label><button id="commit-polygon">Apply polygon</button><button id="cancel-polygon">Cancel polygon</button></div><p><small>Brush assignment transfers observed source pixels between components. Erasing leaves an unassigned region. Foreground tools explicitly identify source pixels; alpha is always taken from the immutable original. Polygon split uses the New semantic component fields.</small></p><p id="coordinates"><small>Coordinates: —</small></p><p id="live-metrics" class="notice"></p><div id="status" role="status" aria-live="polite"></div><fieldset><legend>Save correction and review</legend><label>Reviewer / correction author <input id="author" type="text" required></label><label>Evidence and rationale <textarea id="note" required placeholder="Describe the mask, anatomy, occlusion, and placement changes you inspected."></textarea></label><button id="download" class="primary">Download bound correction JSON</button><p><small>Apply with <code>python scripts/hatch.py decompose-review --run-dir YOUR-RUN --receipt decomposition-review.json</code>, then build a fresh desk to inspect the deterministic validation and saved result.</small></p></fieldset><fieldset id="restore-field"><legend>Restore a saved correction</legend><label>Revision <select id="revision"></select></label><button id="restore">Download restoration request</button><p><small>Restoration is source-bound and checked on submission. An unchanged component can retain its exact earlier approval. Reopen the desk after restoration.</small></p></fieldset></section>
<aside><h2>Selected component</h2><p id="selection-summary"></p><img id="asset" alt="Previously extracted component asset"><p><small id="asset-note">Saved asset before local edits; the editor displays current mask changes.</small></p><details id="inferred-details" hidden><summary>Inferred alternate and generated-pixel mask</summary><p class="warning">These pixels were reconstructed, not extracted from the source. These saved alternate assets precede any local mask edits.</p><img id="inferred-asset" alt="Inferred alternate component artwork"><img id="inferred-mask" alt="Source-canvas mask: white identifies inferred pixels"><pre id="inferred-provenance"></pre></details><fieldset id="metadata"><legend>Semantic metadata</legend><label>Name <input id="name" type="text"></label><label>Category <input id="category" type="text"></label><label>Parent <select id="parent"></select></label><label>Anatomical side <select id="side"><option>unknown</option><option>left</option><option>right</option><option>center</option></select></label><label>Character orientation <select id="orientation"><option>unknown</option><option>front</option><option>back</option><option>left</option><option>right</option></select></label><label>Layer order (higher is in front) <input id="z" type="number" step="1"></label><label>Semantic confidence <input id="confidence" type="number" min="0" max="1" step="0.05"></label><label>Occlusion <select id="occlusion"><option>visible</option><option>partial</option><option>unknown</option></select></label><label>Occluded by (component ids, comma separated) <input id="occluded-by" type="text"></label><label>Occlusion evidence <textarea id="occlusion-note"></textarea></label><button id="save-meta">Apply metadata</button></fieldset><fieldset><legend>Pivot and attachments</legend><div class="grid2"><label>Pivot X <input id="pivot-x" type="number" step="0.5"></label><label>Pivot Y <input id="pivot-y" type="number" step="0.5"></label></div><div class="toolbar"><button id="save-pivot">Set pivot</button><button id="clear-pivot">Clear pivot</button></div><label>Attachment identifier <input id="attachment-id" type="text" value="joint"></label><label>Attached component <select id="attachment-target"></select></label><div class="grid2"><label>Attachment X <input id="attachment-x" type="number" step="0.5" value="0"></label><label>Attachment Y <input id="attachment-y" type="number" step="0.5" value="0"></label></div><label>Attachment confidence <input id="attachment-confidence" type="number" min="0" max="1" step="0.05" value="0.5"></label><button id="save-attachment">Add / replace attachment</button><div id="attachments"></div><p><small>Pivots are canvas coordinates. Guessed attachment geometry still needs explicit human review; it does not establish a complete rig.</small></p></fieldset><fieldset><legend>Individual component verdict</legend><p id="verdict-current"></p><label class="inline"><input type="checkbox" id="inspected"> I inspected its meaning, mask, source pixels, and placement</label><label class="inline"><input type="checkbox" id="inferred"> I also inspected any inferred artwork</label><label>Evidence / independent repair note <textarea id="review-note"></textarea></label><div class="toolbar"><button id="approve">Approve component</button><button id="reject" class="danger">Reject component</button><button id="pending">Needs review</button></div><p><small>Editing a component resets its local verdict. Other components retain their saved reviews when their signatures remain unchanged.</small></p></fieldset></aside>
</main>
<script>
'use strict';
const data=__DECOMPOSITION_DATA__;
const $=id=>document.getElementById(id), clone=value=>JSON.parse(JSON.stringify(value)), own=(object,key)=>Object.prototype.hasOwnProperty.call(object,key)?object[key]:undefined;
const MAX_HISTORY_BYTES=64*1024*1024;
const W=data.manifest.canvas.width,H=data.manifest.canvas.height,NP=W*H;
let annotation=clone(data.template.annotation),selected=annotation.components[0]?.id||null;
let hidden=new Set(),verdicts={},undo=[],redo=[],polygon=[],drawing=false,strokeBefore=null,lastPoint=null;
const source=new Image(),sourceCanvas=document.createElement('canvas');sourceCanvas.width=W;sourceCanvas.height=H;
const sourceCtx=sourceCanvas.getContext('2d',{willReadFrequently:true});let sourcePixels=null;
const original=$('original-canvas'),editor=$('editor');for(const canvas of [original,editor]){canvas.width=W;canvas.height=H}
const ctx=editor.getContext('2d',{willReadFrequently:true});
const scratch=document.createElement('canvas');scratch.width=W;scratch.height=H;const sx=scratch.getContext('2d',{willReadFrequently:true});
const palette=['#f18339','#307fe2','#d84586','#29a56a','#9365d2','#dfb224','#238b98','#db5252'];
function message(value,error=false){$('status').textContent=value;$('status').className=error?'warning':''}
function active(){return annotation.components.find(c=>c.id===selected)}
function runsToBytes(mask){const bytes=new Uint8Array(NP);for(const [y,x0,x1] of mask?.runs||[])bytes.fill(1,y*W+x0,y*W+x1);return bytes}
function bytesToMask(bytes){const runs=[];for(let y=0;y<H;y++){for(let x=0;x<W;){while(x<W&&!bytes[y*W+x])x++;const start=x;while(x<W&&bytes[y*W+x])x++;if(start<x)runs.push([y,start,x])}}return {runs}}
function maskHas(mask,x,y){for(const [row,x0,x1] of mask?.runs||[]){if(row>y)return false;if(row===y&&x>=x0&&x<x1)return true}return false}
function countMask(mask){return (mask?.runs||[]).reduce((n,r)=>n+r[2]-r[1],0)}
function maskBounds(mask){let a=W,b=H,c=0,d=0;for(const [y,x0,x1] of mask?.runs||[]){a=Math.min(a,x0);b=Math.min(b,y);c=Math.max(c,x1);d=Math.max(d,y+1)}return c>a&&d>b?[a,b,c,d]:null}
function remember(){return JSON.stringify({annotation,verdicts,selected})}
function historyEntry(state){return {state,bytes:new TextEncoder().encode(state).length}}
function trimHistory(limit=MAX_HISTORY_BYTES){let bytes=[...undo,...redo].reduce((sum,item)=>sum+item.bytes,0);while((bytes>limit||undo.length+redo.length>40)&&(undo.length||redo.length)){const item=undo.length?undo.shift():redo.shift();bytes-=item.bytes}}
function checkpoint(before){const after=remember();if(before!==after){undo.push(historyEntry(before));redo=[];trimHistory()}buttons()}
function invalidate(ids){for(const id of ids)verdicts[id]={id,status:'pending',note:'Changed in this desk; fresh component inspection required.',inspected:false,inferred_acknowledged:false}}
function edit(fn){const before=remember();try{fn();checkpoint(before);refresh()}catch(error){const previous=JSON.parse(before);annotation=previous.annotation;verdicts=previous.verdicts;selected=previous.selected;refresh();message(error.message,true)}}
function buttons(){$('undo').disabled=!undo.length;$('redo').disabled=!redo.length;$('commit-polygon').disabled=polygon.length<3;$('cancel-polygon').disabled=!polygon.length}
function populateSelect(element,components,emptyLabel,oldValue){element.replaceChildren();const blank=document.createElement('option');blank.value='';blank.textContent=emptyLabel;element.append(blank);for(const c of components){const option=document.createElement('option');option.value=c.id;option.textContent=c.name+' ('+c.id+')';element.append(option)}element.value=oldValue||''}
function descendantIds(id){const found=new Set([id]);let changed=true;while(changed){changed=false;for(const c of annotation.components)if(found.has(c.parent_id)&&!found.has(c.id)){found.add(c.id);changed=true}}return found}
function renderList(){const list=$('components');list.replaceChildren();for(const c of [...annotation.components].sort((a,b)=>b.z_index-a.z_index||a.id.localeCompare(b.id))){const li=document.createElement('li');li.className=c.id===selected?'active':'';const visible=document.createElement('input');visible.type='checkbox';visible.checked=!hidden.has(c.id);visible.setAttribute('aria-label','Show '+c.name);visible.onchange=()=>{visible.checked?hidden.delete(c.id):hidden.add(c.id);draw()};const button=document.createElement('button'),label=document.createElement('span'),small=document.createElement('small');label.textContent=c.name;const saved=data.manifest.components.find(v=>v.id===c.id);small.textContent=c.category+' · '+(own(verdicts,c.id)?.status||saved?.review.status||'pending')+' · '+countMask(c.mask)+' px';button.append(label,small);button.onclick=()=>{selected=c.id;polygon=[];refresh()};li.append(visible,button);list.append(li)}}
function refreshMeta(){const c=active();$('selection-summary').textContent=c?c.id+' · mask '+JSON.stringify(maskBounds(c.mask)):'Select or add a component';for(const field of $('metadata').querySelectorAll('input,select,button'))field.disabled=!c;const asset=own(data.assets,c?.id);$('asset').hidden=!asset;if(asset)$('asset').src=asset;const inferredAsset=own(data.inferred_assets,c?.id);$('inferred-details').hidden=!inferredAsset;if(inferredAsset){$('inferred-asset').src=inferredAsset;$('inferred-mask').src=own(data.inferred_masks,c.id);$('inferred-provenance').textContent=JSON.stringify(data.manifest.components.find(v=>v.id===c.id).provenance.reconstruction,null,2)}if(!c)return;$('name').value=c.name;$('category').value=c.category;const excluded=descendantIds(c.id);populateSelect($('parent'),annotation.components.filter(v=>!excluded.has(v.id)),'Character root',c.parent_id);$('side').value=c.side;$('orientation').value=annotation.orientation;$('z').value=c.z_index;$('confidence').value=c.confidence;$('occlusion').value=c.occlusion.status;$('occluded-by').value=c.occlusion.occluded_by.join(', ');$('occlusion-note').value=c.occlusion.note;$('pivot-x').value=c.pivot?.[0]??'';$('pivot-y').value=c.pivot?.[1]??'';populateSelect($('merge-target'),annotation.components.filter(v=>v.id!==c.id),'Choose component','');populateSelect($('attachment-target'),annotation.components.filter(v=>v.id!==c.id),'No target','');const saved=data.manifest.components.find(v=>v.id===c.id);const verdict=own(verdicts,c.id);$('verdict-current').textContent='Status: '+(verdict?.status||saved?.review.status||'pending')+' · '+(saved?.provenance.kind||'manually corrected on submission');$('review-note').value=verdict?.note||saved?.review.note||'';$('inspected').checked=verdict?.inspected||false;$('inferred').checked=verdict?.inferred_acknowledged||false;const attachments=$('attachments');attachments.replaceChildren();for(const item of c.attachments){const row=document.createElement('div');row.className='attachment';const label=document.createElement('small');label.textContent=item.id+' '+JSON.stringify(item.point)+' → '+(item.target_id||'none')+' · confidence '+item.confidence;const remove=document.createElement('button');remove.textContent='Remove';remove.onclick=()=>edit(()=>{c.attachments=c.attachments.filter(a=>a.id!==item.id);invalidate([c.id])});row.append(label,remove);attachments.append(row)}}
function refresh(){renderList();refreshMeta();draw();buttons()}
function drawMask(mask,color,alpha){ctx.fillStyle=color;ctx.globalAlpha=alpha;for(const [y,x0,x1] of mask.runs)ctx.fillRect(x0,y,x1-x0,1);ctx.globalAlpha=1}
function draw(){if(!sourcePixels)return;const pixels=ctx.createImageData(W,H),coverage=new Uint16Array(NP),foreground=runsToBytes(annotation.foreground_mask);let displayed=0;for(const c of [...annotation.components].sort((a,b)=>a.z_index-b.z_index||a.id.localeCompare(b.id))){for(const [y,x0,x1] of c.mask.runs){for(let x=x0;x<x1;x++){const i=y*W+x;coverage[i]++;if(hidden.has(c.id)||!foreground[i])continue;const p=i*4;pixels.data[p]=sourcePixels[p];pixels.data[p+1]=sourcePixels[p+1];pixels.data[p+2]=sourcePixels[p+2];pixels.data[p+3]=sourcePixels[p+3];displayed++}}}if(!hidden.size)for(let i=0;i<NP;i++)if(foreground[i]&&!coverage[i]){const p=i*4;pixels.data[p]=sourcePixels[p];pixels.data[p+1]=sourcePixels[p+1];pixels.data[p+2]=sourcePixels[p+2];pixels.data[p+3]=sourcePixels[p+3]}ctx.clearRect(0,0,W,H);ctx.putImageData(pixels,0,0);let gaps=0,overlaps=0,foregroundCount=0;for(let i=0;i<NP;i++){if(foreground[i]&&sourcePixels[i*4+3]){foregroundCount++;if(!coverage[i])gaps++;if(coverage[i]>1)overlaps++}}$('live-metrics').textContent='Source foreground: '+foregroundCount+' px · unassigned: '+gaps+' px (retained from source) · overlapping assignments: '+overlaps+' px. '+(hidden.size?'Some layers are hidden for inspection. ':'')+'Saved validation runs when you apply. Alpha comes from the source.';const c=active();if($('overlay').checked&&c)drawMask(c.mask,palette[Math.max(0,annotation.components.indexOf(c))%palette.length],.38);const zoom=Number($('zoom').value);ctx.lineWidth=1/zoom;if($('boxes').checked)for(const v of annotation.components){const box=maskBounds(v.mask);if(box){ctx.strokeStyle=v.id===selected?'#f00':'#1586cf';ctx.strokeRect(box[0],box[1],box[2]-box[0],box[3]-box[1])}}if($('show-pivots').checked&&c){if(c.pivot){ctx.strokeStyle='#e01265';const [x,y]=c.pivot,r=5/zoom;ctx.beginPath();ctx.moveTo(x-r,y);ctx.lineTo(x+r,y);ctx.moveTo(x,y-r);ctx.lineTo(x,y+r);ctx.stroke()}for(const a of c.attachments){ctx.strokeStyle='#254fde';ctx.beginPath();ctx.arc(a.point[0],a.point[1],4/zoom,0,Math.PI*2);ctx.stroke()}}if(polygon.length){ctx.strokeStyle='#e11336';ctx.fillStyle='#e1133633';ctx.beginPath();ctx.moveTo(...polygon[0]);for(const p of polygon.slice(1))ctx.lineTo(...p);if(polygon.length>2)ctx.closePath();ctx.fill();ctx.stroke();for(const p of polygon)ctx.fillRect(p[0]-1/zoom,p[1]-1/zoom,2/zoom,2/zoom)}}
function sourcePoint(event){const rect=editor.getBoundingClientRect();return [Math.max(0,Math.min(W-1,Math.floor((event.clientX-rect.left)*W/rect.width))),Math.max(0,Math.min(H-1,Math.floor((event.clientY-rect.top)*H/rect.height)))]}
function applySelection(selection,kind){const c=active();if(!c&&!kind.startsWith('foreground-'))throw Error('Select a component first.');const foreground=runsToBytes(annotation.foreground_mask),touched=new Set();if(kind==='foreground-add'){for(let i=0;i<NP;i++)if(selection[i]&&sourcePixels[i*4+3])foreground[i]=1;annotation.foreground_mask=bytesToMask(foreground);invalidate(annotation.components.map(v=>v.id));return}if(kind==='foreground-erase'){for(let i=0;i<NP;i++)if(selection[i])foreground[i]=0;annotation.foreground_mask=bytesToMask(foreground);for(const component of annotation.components){const mask=runsToBytes(component.mask);let changed=false;for(let i=0;i<NP;i++)if(selection[i]&&mask[i]){mask[i]=0;changed=true}if(changed){component.mask=bytesToMask(mask);touched.add(component.id)}}invalidate([...touched]);return}for(const component of annotation.components){const mask=runsToBytes(component.mask);let changed=false;for(let i=0;i<NP;i++){if(!selection[i])continue;if(component.id===c.id){const next=kind==='erase'?0:(foreground[i]&&sourcePixels[i*4+3]?1:mask[i]);if(mask[i]!==next){mask[i]=next;changed=true}}else if(kind!=='erase'&&mask[i]){mask[i]=0;changed=true}}if(changed){component.mask=bytesToMask(mask);touched.add(component.id)}}invalidate([...touched])}
function brush(points){const selectedPixels=new Uint8Array(NP),radius=Number($('radius').value);if(!Number.isFinite(radius)||radius<1||radius>512)throw Error('Brush radius must be 1..512 source pixels.');for(const [cx,cy] of points)for(let y=Math.max(0,Math.floor(cy-radius));y<=Math.min(H-1,Math.ceil(cy+radius));y++)for(let x=Math.max(0,Math.floor(cx-radius));x<=Math.min(W-1,Math.ceil(cx+radius));x++)if((x-cx)**2+(y-cy)**2<=radius*radius)selectedPixels[y*W+x]=1;applySelection(selectedPixels,$('tool').value);draw()}
function interpolated(a,b){const count=Math.max(Math.abs(b[0]-a[0]),Math.abs(b[1]-a[1])),points=[];for(let i=0;i<=count;i++)points.push([a[0]+(b[0]-a[0])*(count?i/count:0),a[1]+(b[1]-a[1])*(count?i/count:0)]);return points}
function newComponent(){const id=$('new-id').value.trim(),name=$('new-name').value.trim(),category=$('new-category').value.trim();if(!/^[a-z][a-z0-9-]{0,63}$/.test(id))throw Error('Identifier must start with a lowercase letter and use at most 64 lowercase letters, digits, or hyphens.');if(annotation.components.some(c=>c.id===id))throw Error('That component identifier already exists.');if(!name||!category)throw Error('Provide a component name and semantic category.');return {id,name,category,parent_id:null,z_index:Math.max(0,...annotation.components.map(c=>c.z_index))+1,side:'unknown',mask:{runs:[]},pivot:null,attachments:[],confidence:0.5,occlusion:{status:'unknown',occluded_by:[],note:'Needs source-image inspection.'},notes:['Manually identified in the decomposition review desk.']}}
function pointValue(x,y){const point=[Number(x),Number(y)];if(x===''||y===''||!point.every(Number.isFinite)||point[0]<0||point[0]>W||point[1]<0||point[1]>H)throw Error('Point must be finite canvas coordinates inside '+W+' × '+H+'.');return point}
function attach(point){const c=active();if(!c)throw Error('Select a component first.');const id=$('attachment-id').value.trim(),confidence=Number($('attachment-confidence').value);if(!/^[a-z][a-z0-9-]{0,63}$/.test(id)||!Number.isFinite(confidence)||confidence<0||confidence>1)throw Error('Attachment needs an identifier and confidence 0..1.');const target_id=$('attachment-target').value||null;c.attachments=c.attachments.filter(a=>a.id!==id);c.attachments.push({id,point,target_id,confidence});invalidate([c.id])}
editor.addEventListener('pointerdown',event=>{if(!sourcePixels)return;const point=sourcePoint(event),tool=$('tool').value;if(tool==='inspect'){const found=[...annotation.components].sort((a,b)=>b.z_index-a.z_index).find(c=>!hidden.has(c.id)&&maskHas(c.mask,...point));if(found){selected=found.id;refresh()}return}if(tool==='polygon'||tool==='split'){polygon.push(point);draw();buttons();return}if(tool==='pivot'){edit(()=>{if(!active())throw Error('Select a component.');active().pivot=point;invalidate([selected])});return}if(tool==='attachment'){edit(()=>attach(point));return}strokeBefore=remember();drawing=true;lastPoint=point;editor.setPointerCapture(event.pointerId);try{brush([point])}catch(error){message(error.message,true);drawing=false}});
editor.addEventListener('pointermove',event=>{const point=sourcePoint(event);$('coordinates').textContent='Coordinates: '+point.join(', ');if(drawing){try{brush(interpolated(lastPoint,point));lastPoint=point}catch(error){message(error.message,true)}}});
function endStroke(){if(drawing){drawing=false;checkpoint(strokeBefore);refresh();strokeBefore=null;lastPoint=null}}editor.addEventListener('pointerup',endStroke);editor.addEventListener('pointercancel',endStroke);
$('commit-polygon').onclick=()=>edit(()=>{if(polygon.length<3)throw Error('Add at least three polygon vertices.');sx.clearRect(0,0,W,H);sx.fillStyle='#fff';sx.beginPath();sx.moveTo(...polygon[0]);for(const p of polygon.slice(1))sx.lineTo(...p);sx.closePath();sx.fill();const rgba=sx.getImageData(0,0,W,H).data,selection=new Uint8Array(NP);for(let i=0;i<NP;i++)selection[i]=rgba[i*4+3]>=128?1:0;if($('tool').value==='split'){const original=active();if(!original)throw Error('Select a component to split.');const child=newComponent(),mask=runsToBytes(original.mask),newMask=new Uint8Array(NP);for(let i=0;i<NP;i++)if(selection[i]&&mask[i]){newMask[i]=1;mask[i]=0}if(!newMask.some(Boolean)||!mask.some(Boolean))throw Error('A split must leave nonempty visible pixels in both components.');original.mask=bytesToMask(mask);child.mask=bytesToMask(newMask);child.parent_id=original.parent_id;child.side=original.side;annotation.components.push(child);invalidate([original.id,child.id]);selected=child.id}else applySelection(selection,'paint');polygon=[]});
$('cancel-polygon').onclick=()=>{polygon=[];draw();buttons()};$('tool').onchange=()=>{polygon=[];draw();buttons()};
$('add').onclick=()=>edit(()=>{const component=newComponent();annotation.components.push(component);selected=component.id;invalidate([component.id]);message('Added an empty component. Assign its visible source pixels with the brush or a polygon before submitting.')});
$('merge').onclick=()=>edit(()=>{const c=active(),other=annotation.components.find(v=>v.id===$('merge-target').value);if(!c||!other)throw Error('Choose two components to merge.');const mask=runsToBytes(c.mask),second=runsToBytes(other.mask);for(let i=0;i<NP;i++)if(second[i])mask[i]=1;c.mask=bytesToMask(mask);if(descendantIds(other.id).has(c.id))c.parent_id=other.parent_id;c.notes.push('Merged visible pixels from '+other.id+'.');const touched=[c.id];for(const v of annotation.components){if(v.id===other.id)continue;if(v.parent_id===other.id){v.parent_id=c.id;touched.push(v.id)}for(const a of v.attachments)if(a.target_id===other.id){a.target_id=v.id===c.id?null:c.id;touched.push(v.id)}if(v.occlusion.occluded_by.includes(other.id)){v.occlusion.occluded_by=[...new Set(v.occlusion.occluded_by.map(id=>id===other.id?c.id:id))].filter(id=>id!==v.id);touched.push(v.id)}}annotation.components=annotation.components.filter(v=>v.id!==other.id);delete verdicts[other.id];hidden.delete(other.id);invalidate(touched)});
$('remove-component').onclick=()=>edit(()=>{const c=active();if(!c)throw Error('Select a component.');const touched=[];for(const v of annotation.components){if(v.parent_id===c.id){v.parent_id=null;touched.push(v.id)}for(const a of v.attachments)if(a.target_id===c.id){a.target_id=null;touched.push(v.id)}if(v.occlusion.occluded_by.includes(c.id)){v.occlusion.occluded_by=v.occlusion.occluded_by.filter(id=>id!==c.id);touched.push(v.id)}}annotation.components=annotation.components.filter(v=>v.id!==c.id);delete verdicts[c.id];hidden.delete(c.id);selected=annotation.components[0]?.id||null;invalidate(touched)});
$('save-meta').onclick=()=>edit(()=>{const c=active();if(!c)throw Error('Select a component.');const name=$('name').value.trim(),category=$('category').value.trim(),confidence=Number($('confidence').value),z_index=Number($('z').value);if(!name||!category||!Number.isFinite(confidence)||confidence<0||confidence>1||!Number.isInteger(z_index))throw Error('Provide a name, category, integer layer order, and confidence 0..1.');const occluded_by=$('occluded-by').value.split(',').map(v=>v.trim()).filter(Boolean);if(occluded_by.some(id=>id===c.id||!annotation.components.some(v=>v.id===id)))throw Error('Occluded-by ids must name other existing components.');const orientation=$('orientation').value,ids=orientation!==annotation.orientation?annotation.components.map(v=>v.id):[c.id];annotation.orientation=orientation;Object.assign(c,{name,category,parent_id:$('parent').value||null,side:$('side').value,z_index,confidence,occlusion:{status:$('occlusion').value,occluded_by:[...new Set(occluded_by)],note:$('occlusion-note').value.trim()}});invalidate(ids)});
$('save-pivot').onclick=()=>edit(()=>{if(!active())throw Error('Select a component.');active().pivot=pointValue($('pivot-x').value,$('pivot-y').value);invalidate([selected])});$('clear-pivot').onclick=()=>edit(()=>{if(!active())throw Error('Select a component.');active().pivot=null;invalidate([selected])});$('save-attachment').onclick=()=>edit(()=>attach(pointValue($('attachment-x').value,$('attachment-y').value)));
function setVerdict(status){edit(()=>{const c=active();if(!c)throw Error('Select a component.');const inspected=$('inspected').checked,inferred_acknowledged=$('inferred').checked,note=$('review-note').value.trim();const saved=data.manifest.components.find(v=>v.id===c.id);if(status!=='pending'&&(!inspected||!note))throw Error('Confirm source/mask inspection and enter an evidence note.');if(status==='approved'&&c.category==='unassigned')throw Error('Identify and recategorize unassigned foreground before approving it.');if(status==='approved'&&(saved?.provenance.kind==='inferred'||saved?.provenance.reconstruction)&&!inferred_acknowledged)throw Error('Explicitly acknowledge inspection of inferred content.');verdicts[c.id]={id:c.id,status,note,inspected,inferred_acknowledged}})}$('approve').onclick=()=>setVerdict('approved');$('reject').onclick=()=>setVerdict('rejected');$('pending').onclick=()=>setVerdict('pending');
$('undo').onclick=()=>{if(!undo.length)return;const previous=undo.pop();redo.push(historyEntry(remember()));const snapshot=JSON.parse(previous.state);trimHistory();annotation=snapshot.annotation;verdicts=snapshot.verdicts;selected=snapshot.selected;polygon=[];refresh()};$('redo').onclick=()=>{if(!redo.length)return;const following=redo.pop();undo.push(historyEntry(remember()));const snapshot=JSON.parse(following.state);trimHistory();annotation=snapshot.annotation;verdicts=snapshot.verdicts;selected=snapshot.selected;polygon=[];refresh()};
$('show-all').onclick=()=>{hidden.clear();refresh()};$('hide-all').onclick=()=>{hidden=new Set(annotation.components.map(c=>c.id));refresh()};$('isolate').onclick=()=>{hidden=new Set(annotation.components.filter(c=>c.id!==selected).map(c=>c.id));refresh()};
function zoom(){const factor=Number($('zoom').value);for(const c of [original,editor]){c.style.width=W*factor+'px';c.style.height=H*factor+'px'}draw()}$('zoom').onchange=zoom;for(const name of ['overlay','boxes','show-pivots'])$(name).onchange=draw;
let syncScroll=false;for(const [from,to] of [[$('original-viewport'),$('editor-viewport')],[$('editor-viewport'),$('original-viewport')]])from.onscroll=()=>{if(syncScroll)return;syncScroll=true;to.scrollTop=from.scrollTop;to.scrollLeft=from.scrollLeft;requestAnimationFrame(()=>{syncScroll=false})};
function envelope(){const author=$('author').value.trim(),note=$('note').value.trim();if(!author||!note)throw Error('Enter the reviewer / correction author and an evidence-based rationale.');return {schema_version:1,kind:data.template.kind,source_sha256:data.template.source_sha256,base_manifest_sha256:data.template.base_manifest_sha256,author,note}}
function download(value,filename){const serialized=JSON.stringify(value,null,2);if(new TextEncoder().encode(serialized).length>32*1024*1024)throw Error('Correction JSON exceeds 32 MiB; use fewer regions per review.');const blob=new Blob([serialized],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);message('Downloaded '+filename+'. Submit through hatch.py decompose-review, then rebuild the desk to inspect the saved recomposition and validation.')}
$('download').onclick=()=>{try{if(drawing||polygon.length)throw Error('Finish the active stroke or polygon before saving.');if(annotation.components.some(c=>!countMask(c.mask)))throw Error('Every component must contain observed pixels; paint, merge, or undo empty components first.');const value=envelope();value.annotation=clone(annotation);value.annotation.author=value.author;value.annotation.note=value.note;value.reviews=Object.values(verdicts);download(value,'decomposition-review.json')}catch(error){message(error.message,true)}};
$('restore').onclick=()=>{try{const value=envelope();value.restore_revision=Number($('revision').value);if(!value.restore_revision)throw Error('Choose an existing saved revision.');download(value,'decomposition-restore.json')}catch(error){message(error.message,true)}};
$('restore-field').hidden=!data.revisions.length;for(const item of data.revisions){const option=document.createElement('option');option.value=item.id;option.textContent=item.id+' · '+(item.accepted?'accepted':'needs review')+' · '+item.note;$('revision').append(option)}
$('provenance').textContent=(data.manifest.source.fixture?'SYNTHETIC FIXTURE — review exercises the workflow. ':'Source: '+data.manifest.source.origin+' · ')+W+' × '+H+' px · original SHA-256 '+data.template.source_sha256;
$('diagnostics').textContent=JSON.stringify({validation:data.manifest.validation,components:data.manifest.components.map(c=>({id:c.id,confidence:c.confidence,uncertainty:c.uncertainty,occlusion:c.occlusion}))},null,2);
source.onload=()=>{sourceCtx.drawImage(source,0,0);sourcePixels=sourceCtx.getImageData(0,0,W,H).data;original.getContext('2d').drawImage(source,0,0);zoom();refresh()};source.onerror=()=>message('Embedded immutable source could not be decoded.',true);source.src=data.original;
</script></html>'''
