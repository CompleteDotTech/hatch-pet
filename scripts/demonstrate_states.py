"""Exercise selected state profiles using explicitly synthetic, ordered imports.

No character art is generated. The simple calibration shape tests profile
consumption, source provenance, extraction, timing, review gates and exports;
it does not establish the visual semantics of the catalog's production prompts.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

import hatch
from asset_contracts import sha
from demonstrate import fixture_review
from profile_spec import load_profile
from review_ui import build_review
from source_interface import import_source
from state_catalog import compile_selection, load_library, write_compilation, validate_selection_manifest

ROOT = Path(__file__).resolve().parents[1]
DEMONSTRATIONS = {
    'states-cat': 'expressive-cat.json',
    'states-agent': 'coding-assistant.json',
    'states-game': 'game-npc.json',
    'states-obs': 'obs-mascot.json',
    'states-accessibility': 'accessible-feedback.json',
}


def calibration_frame(spec, index, width, height):
    """A connected, asymmetric test shape with deterministic nonduplicate motion."""
    image = Image.new('RGBA', (width, height))
    draw = ImageDraw.Draw(image)
    phase = index / max(1, spec['frames'] - 1)
    center = width // 2
    y = height // 3
    if spec['motion'] == 'vertical':
        y -= round(12 * math.sin(math.pi * phase))
    draw.rounded_rectangle((center - 17, y, center + 17, y + 41), radius=7, fill='#b43c28')
    # This protrusion touches the body, stays inside the slot and makes each
    # animated frame measurably distinct without requesting detached permissions.
    # A one-pixel change can collapse when the pixel style's nearest-neighbor
    # extraction fits the source viewport inside destination padding. Make the
    # calibration motion large enough to remain distinct after that real path.
    arm = 20 + 3 * index
    draw.rectangle((center + 15, y + 17, center + arm, y + 22), fill='#b43c28')
    draw.rectangle((center - 9, y + 9, center - 5, y + 14), fill='#17222d')
    draw.rectangle((center - 15, y + 26, center - 11, y + 32), fill='#f5d09a')
    return image


def check_demonstration(destination, profile, selection):
    out = Path(destination)
    root, exported = out / 'run', out / 'export'
    validate_selection_manifest(selection, profile)
    metadata = hatch.read(exported / 'animation.json')
    receipt = hatch.read(exported / 'export-receipt.json')
    assert metadata['fixture'] and not metadata['integration_verified']
    assert metadata['state_selection']['current_profile_matches_selection']
    assert [s['id'] for s in metadata['states']] == selection['selected_states']
    assert all(sha(exported / path) == digest for path, digest in receipt['files'].items())
    actual_frames = 0
    for record, spec in zip(metadata['states'], profile['states']):
        assert [frame['duration_ms'] for frame in record['frames']] == spec['durations']
        assert record['playback'] == spec['playback']
        pixels = []
        for frame in record['frames']:
            with Image.open(exported / frame['path']) as image:
                assert image.size == (profile['layout']['cell_width'], profile['layout']['cell_height'])
                assert image.getbbox()
                pixels.append(image.convert('RGBA').tobytes())
                actual_frames += 1
        if len(pixels) > 1:
            assert len(set(pixels)) == len(pixels), 'synthetic animated frames must be distinct'
        with Image.open(exported / record['static']) as still:
            assert still.convert('RGBA').tobytes() == pixels[record['static_frame']]
    data = hatch.manifest(root)
    assert all(job.get('source_origin') == 'import' and 'import_receipt' in job
               and 'generation_receipt' not in job and job['attempts'] == 0 for job in data['jobs'])
    assert hatch.status(root, data)['reviewed']
    assert hatch.verify_package(out / 'package')['fixture']
    assert hatch.read(exported / 'state-selection.json') == selection
    assert (out / 'review/review.html').is_file()
    return {
        'ok': True, 'fixture': True, 'catalog_version': selection['catalog_version'],
        'profile_sha256': selection['profile_sha256'],
        'states': len(profile['states']), 'frames': actual_frames, 'model_calls': 0,
        'production_artwork_accepted': False, 'external_integration_verified': False,
        'artwork_description': 'Deterministic calibration shape; not a semantic character-performance demonstration.',
        'checks': ['compiled profile and selection hash binding', 'exact source import origin and zero generation claims',
            'strict extraction and atlas validation', 'distinct indexed fixture frames and exact exported timings',
            'per-state reduced-motion still pixels', 'export file hashes and original selection evidence',
            'fixture-only visual-review and package gates', 'offline review workspace'],
        'preview': 'export/preview.html', 'review': 'review/review.html',
    }


def demonstrate_states(name, destination, *, library=None):
    if name not in DEMONSTRATIONS:
        raise ValueError('unknown state demonstration: ' + name)
    out = Path(destination).resolve() / name
    if out.exists():
        raise ValueError('state demonstration output already exists: ' + str(out))
    lib = library or load_library()
    selection = hatch.read(ROOT / 'examples/state-selections' / DEMONSTRATIONS[name])
    # The same definitions use smaller cells for deterministic integration tests.
    result = compile_selection(selection, library=lib, cell_width=96, cell_height=96)
    profile, manifest = result['profile'], result['manifest']
    out.mkdir(parents=True)
    write_compilation(result, out / 'profile.json')
    identity = {'schema_version': 1, 'materials': ['synthetic calibration fixture'],
        'markings': ['one light rectangular marking on the anatomical right body'],
        'approved_props': manifest['required_props'], 'forbid_mirror': True}
    hatch.atomic(out / 'identity.json', identity)
    root = out / 'run'
    hatch.prepare(root, argparse.Namespace(replace_inputs=False, fixture_mode=True,
        profile=str(out / 'profile.json'), identity=str(out / 'identity.json'),
        pet_name=name, pet_notes='Explicit synthetic calibration shape; no production art or semantic visual acceptance.',
        reference=[], avoid=[], require=[], brand_source=[], style_preset='pixel', style_notes='Synthetic test only'))
    data = hatch.manifest(root)
    inputs = out / 'fixture-inputs'
    inputs.mkdir()
    width, height = profile['layout']['cell_width'], profile['layout']['cell_height']
    base = inputs / 'base.png'
    calibration_frame({'frames': 1, 'motion': 'static'}, 0, width, height).save(base)
    descriptor = inputs / 'base-source.json'
    hatch.atomic(descriptor, {'schema_version': 1, 'kind': 'import', 'layout': 'image', 'files': [base.name],
        'origin': 'Pillow synthetic calibration fixture; not model output or user artwork', 'fixture': True})
    import_source(root, data, 'base', descriptor, 'Explicit synthetic canonical calibration import.')
    hatch.record_base_review(root, data, 'Fixture checkpoint exercises the base gate; no production approval.', True)
    for spec in profile['states']:
        files = []
        for index in range(spec['frames']):
            path = inputs / f"{spec['id']}-{index:02d}.png"
            calibration_frame(spec, index, width, height).save(path)
            files.append(path.name)
        descriptor = inputs / (spec['id'] + '-source.json')
        hatch.atomic(descriptor, {'schema_version': 1, 'kind': 'import', 'layout': 'frames', 'files': files,
            'origin': 'Ordered deterministic state-library test fixtures; semantic artwork is not supplied', 'fixture': True})
        import_source(root, data, spec['id'], descriptor, 'Synthetic ordered import; no artwork quality claim.')
    hatch.validate(root, data)
    fixture_review(root, data)
    hatch.export(root, data, out / 'export')
    hatch.package(root, data, out / 'package')
    build_review(root, data, out / 'review')
    acceptance = check_demonstration(out, profile, manifest)
    hatch.atomic(out / 'acceptance.json', acceptance)
    return acceptance


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--all', action='store_true')
    choice.add_argument('--demo', choices=sorted(DEMONSTRATIONS))
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args(argv)
    library = load_library()
    names = list(DEMONSTRATIONS) if args.all else [args.demo]
    results = {name: demonstrate_states(name, args.output_dir, library=library) for name in names}
    print(json.dumps(results, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
