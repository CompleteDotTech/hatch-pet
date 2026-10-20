#!/usr/bin/env python3
"""Create inspectable synthetic decomposition, portable reload and forward input.

This exercise supplies authored masks. No semantic model or image generation is
called, no human approval is fabricated, and forward animation remains pending.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))

from asset_contracts import sha
from character_decomposition import create_decomposition, load_decomposition, validate_decomposition
from decomposition_fixtures import FIXTURE_NAMES, FIXTURE_ORIGIN, make_fixture
from decomposition_package import export_decomposition, import_decomposition
from decomposition_reuse import prepare_from_decomposition


def build_example(destination, case):
    output = Path(destination).resolve()
    if output.exists():
        raise ValueError('choose a new fixture output directory; existing evidence is not overwritten')
    output.mkdir(parents=True)
    fixture = make_fixture(output / 'inputs', case)
    source_before = sha(fixture.source)
    run = output / 'run'
    manifest = create_decomposition(fixture.source, run, annotations=fixture.annotation,
        name='Synthetic ' + case, character_id='fixture-' + case,
        origin=FIXTURE_ORIGIN, fixture=True, pixel_art=case == 'pixel')
    validation = validate_decomposition(run, manifest)
    if not validation['faithful_fidelity_passed'] or sha(fixture.source) != source_before:
        raise RuntimeError('fixture must preserve the original source and pass exact recomposition')
    exported = output / 'package'
    export_decomposition(run, exported)
    restored = output / 'restored'
    import_decomposition(exported, restored)
    reloaded = load_decomposition(restored)
    if reloaded['components'] != manifest['components'] or reloaded['source'] != manifest['source']:
        raise RuntimeError('portable reload changed component placement or source provenance')
    selected = [component['id'] for component in manifest['components'] if component['id'] == 'head']
    if not selected:
        selected = [manifest['components'][0]['id']]
    forward = output / 'forward'
    prepare_from_decomposition(restored, forward, component_ids=selected, operation='animate')
    result = {'fixture': True, 'fixture_origin': FIXTURE_ORIGIN, 'case': case,
              'deterministic_passed': True, 'source_unchanged': True,
              'component_count': len(manifest['components']),
              'faithful_fidelity_passed': validation['faithful_fidelity_passed'],
              'semantic_acceptance': 'pending; authored fixtures do not prove general-purpose segmentation',
              'production_artwork': False, 'model_calls': 0, 'animation_frames_generated': 0,
              'source': str(fixture.source), 'run': str(run), 'package': str(exported),
              'reloaded': str(restored), 'forward_run': str(forward),
              'preview': str(run / 'previews/comparison.png'),
              'next_step': 'Inspect the decomposition review desk; review the imported forward base before claiming new-artwork jobs.'}
    (output / 'acceptance.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--case', choices=FIXTURE_NAMES, default='creature')
    parser.add_argument('--all', action='store_true', help='Create every deterministic case in a separate subdirectory.')
    args = parser.parse_args()
    destination = Path(args.output_dir).expanduser()
    cases = FIXTURE_NAMES if args.all else (args.case,)
    results = [build_example(destination / case if args.all else destination, case) for case in cases]
    print(json.dumps(results if args.all else results[0], indent=2))


if __name__ == '__main__':
    main()
