"""Build an offline, artifact-bound review workspace outside the mutable run."""
import json
from pathlib import Path
import shutil


def build_review(root, data, destination):
    import hatch
    from export_assets import export_assets
    template = hatch.review_template(root, data)
    out = hatch._destination(root, destination)
    if out.exists():
        raise ValueError('review destination must be new; rebuild after artifact changes')
    profile = hatch.load_profile(root / 'profile.json')
    profile['export']['formats'] = ['frames', 'browser']
    export_assets(root / 'frames', out, profile)
    evidence = []
    paths = [(root / 'references/canonical-base.png', 'Canonical identity'), (root / 'qa/contact-sheet.png', 'Extracted frames, in state and frame order')]
    paths += [(hatch.resolve_ref(root, r['copied_path'], data.get('original_root')), r.get('role', 'identity') + ': ' + r.get('note', 'Required original reference')) for r in hatch.read(root / 'pet_request.json').get('references', [])]
    paths += [(root / j['output_path'], j['id'] + ' / source strip / ' + hatch.source_origin(j)) for j in data['jobs'] if j['id'] != 'base']
    (out / 'evidence').mkdir()
    for index, (source, label) in enumerate(paths):
        target = out / 'evidence' / (str(index) + source.suffix)
        shutil.copy2(source, target)
        evidence.append({'path': target.relative_to(out).as_posix(), 'name': label, 'sha256': hatch.digest(source)})
    hatch.atomic(out / 'review-template.json', template)
    hatch.atomic(out / 'identity.json', hatch.read(root / 'pet_request.json').get('identity', {}))
    style = hatch.style_provenance(root, data)
    hatch.atomic(out / 'style-provenance.json', style)
    payload = json.dumps({'template': template, 'evidence': evidence,
        'identity': hatch.read(root / 'pet_request.json').get('identity', {}),
        'style': style,
        'origins': {j['id']: hatch.source_origin(j) for j in data['jobs']}}).replace('<', '\\u003c')
    shell = (Path(__file__).parents[1] / 'assets/review.html').read_text(encoding='utf-8')
    (out / 'review.html').write_text(shell.replace('__REVIEW_DATA__', payload), encoding='utf-8')
    return {'review_ui': str(out / 'review.html'), 'receipt_template': str(out / 'review-template.json'),
            'accepted': False, 'instructions': 'Inspect evidence, fill each dimension and warning note, download JSON and submit through hatch.py review.'}
