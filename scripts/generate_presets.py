"""Maintain the small purpose-specific preset catalog and its exact quick starts."""
import argparse
import json
from pathlib import Path
from profile_spec import load_profile

ROOT = Path(__file__).resolve().parents[1]
SPECS = [
    ('assembly', 'U01', 96, [('exploded', 1), ('insert', 1), ('tighten', 1), ('test', 1)], ['cards'],
     'A bracket, post and screw progress from separated parts to an assembled fixture. Keep one orthographic view and constant component dimensions.',
     'Approved component drawings, dimensions and assembly sequence.',
     'Mechanical owner checks order, mating surfaces, tools and safety instructions before real assembly.',
     'Provide product-specific tolerances, fastener torque and safety instructions; verify printed scale.'),
    ('process', 'U02', 96, [('reservoir', 3), ('evaporation', 3), ('condensation', 3), ('rain', 3)], ['cards', 'browser'],
     'A simplified water cycle: reservoir, upward vapor, cloud condensation, falling rain. Illustrations are symbolic, not a fluid simulation.',
     'Approved process model, stage descriptions and scientific references.',
     'Subject-matter educator must check causal order, labels, omissions and audience suitability.',
     'Supply curricular sources and expert content review; embed the exported page in the lesson.'),
    ('configurator', 'U03', 96, [('red-glaze', 1), ('blue-glaze', 1), ('gold-glaze', 1)], ['browser', 'cards'],
     'The same front orthographic mug with only the approved glaze color changing. Preserve viewpoint, handle geometry and body dimensions.',
     'Product front view, palette swatches and approved variant differences.',
     'Check identical silhouette/viewpoint and ensure only glaze differs; match physical color separately.',
     'Wire selections to real SKU data and approved product imagery; browser selection alone is not commerce integration.'),
    ('flipbook', 'U04', 64, [('bounce', 12)], ['flipbook', 'browser'],
     'A single ball bounces vertically through twelve ordered drawings with a fixed diameter and ground baseline.',
     'Ordered motion frames, target print size and intended viewing direction.',
     'Check frame order, constant ball diameter, retained vertical displacement and physical test assembly.',
     'Print at 100%, cut, bind in order or assemble slit cylinder; physically test rotation speed.'),
    ('communication', 'U05', 96, [('drink', 2), ('rest', 2), ('help', 2)], ['board', 'browser', 'cards'],
     'Readable cup, bed and raised-hand pictograms, with matching descriptions and still alternatives. No clinical validation is implied.',
     'User-approved vocabulary, accessible descriptions and pictograms.',
     'Check recognition, descriptions, contrast and personal/cultural suitability with intended users.',
     'Fit vocabulary and access method to the user; external assistive app integration and clinical assessment are separate.'),
    ('perception', 'U06', 64, [('low-contrast', 4), ('high-contrast', 4)], ['stimuli', 'browser'],
     'Equal-diameter disks translate through the same positions; the controlled difference is luminance contrast.',
     'Condition definitions, source images, trial design and intended frame durations.',
     'Check size/position equality and intended condition differences; review study design and ethics where applicable.',
     'Use a calibrated display and measured onset timing, randomization and experiment software. Ordinary browser timing is not laboratory precision.'),
    ('regression', 'U07', 64, [('alpha-edge', 3), ('hole', 3), ('detached', 3), ('order', 3)], ['browser', 'gif', 'webp', 'stimuli'],
     'Deterministic graphics fixtures: partial alpha edges, transparent holes, detached details and color-coded frame order. Fixtures only.',
     'Fixture geometry and expected pixels, codec-specific reconstruction tolerances.',
     'Inspect compositor backgrounds and compare decoded pixels; GIF binary alpha is intentionally lossy.',
     'Import these labeled fixtures into the target compositor and record renderer/codec versions; no live compositor is exercised here.'),
    ('cursor', 'U08', 32, [('busy', 6)], ['cursor', 'browser'],
     'A pixel pointer with fixed hotspot at (4,4) and a six-frame activity marker. Keep pointer geometry stable.',
     'Ordered cursor frames, integer hotspot and per-frame durations.',
     'Check hotspot alignment, pointer legibility and animation at actual size on light/dark backgrounds.',
     'Load the Xcursor file in an Xcursor-capable consumer or adapt the local page; OS cursor settings are never changed.'),
    ('protocol', 'U09', 96, [('idle', 1), ('request', 3), ('ack', 2), ('done', 1), ('fault', 1)], ['browser', 'cards'],
     'A sender/receiver protocol progresses from idle through request, acknowledgment and done; timeout leads to fault. Events must follow legal transitions.',
     'State/event table, legal transitions, cancellation and timeout policy.',
     'Protocol owner checks event legality, priority, interruption and completion behavior against the actual algorithm.',
     'Connect real protocol events after reviewing concurrency and failure semantics; this is an illustrative local consumer.'),
    ('craft', 'U10', 24, [('rosette', 1), ('diamond', 1)], ['craft'],
     'Grid-aligned rosette and diamond motifs in a named four-color palette for bead or embroidery planning.',
     'Palette, grid dimensions, motif source and physical material pitch.',
     'Check grid dimensions, palette mapping, symbol readability and practical construction with a swatch.',
     'Choose actual bead/thread colors, pitch and technique; the pack is a planning source, not a validated stitch instruction.')
]


def build():
    files, catalog = {}, {}
    for name, use, size, states, formats, semantics, inputs, review, external in SPECS:
        records = []
        for state, count in states:
            motion = 'static' if count == 1 else 'vertical' if name == 'flipbook' else 'gesture'
            records.append({'id': state, 'frames': count, 'durations': [80 if name in ('flipbook', 'cursor') else 120] * count,
                'purpose': semantics + ' Stage/condition: ' + state + '.', 'motion': motion,
                'alignment': {'coordinate_policy': 'slot', 'scale_policy': 'shared', 'scale': 1,
                              'padding': 0, 'resampling': 'nearest', 'anchor': [0.5, 0.5]},
                'playback': {'mode': 'hold' if count == 1 else 'loop'}})
        profile = {'schema_version': 2, 'id': name + '-v2', 'layout': {'columns': max(n for _, n in states), 'cell_width': size, 'cell_height': size},
            'states': records, 'generation': {'instructions': semantics, 'requirements': [review, 'Keep frames within the source viewport and retain approved references.']},
            'validation': {'require_provenance': True, 'allow_detached_details': True},
            'events': {state: state for state, _ in states},
            'export': {'formats': ['frames', 'atlas'] + formats, 'static_state': states[0][0], 'static_frame': 0,
                'options': {'labels': {state: state.replace('-', ' ') for state, _ in states}, 'content_review': review, 'cell_mm': 40, 'dpi': 150}}}
        if name == 'perception':
            profile['export']['options']['conditions'] = {'low-contrast': 'disk luminance 120 on transparent field', 'high-contrast': 'disk luminance 230 on transparent field'}
        if name == 'craft':
            profile['export']['options']['palette'] = {'ink': '#203830', 'leaf': '#408060', 'flower': '#D05040', 'gold': '#E0B050'}
        if name == 'cursor':
            profile['export']['options']['hotspot'] = [4, 4]
        if name == 'protocol':
            profile['states'][1]['playback'] = {'mode': 'once', 'interruptible': False}
            profile['states'][2]['playback'] = {'mode': 'once', 'completion': 'done'}
            profile['events'] = {'send': 'request', 'receive-ack': 'ack', 'timeout': 'fault', 'reset': 'idle'}
            profile['playback'] = {'initial': 'idle', 'cancel_state': 'idle', 'queue_limit': 4, 'events': {
                'send': {'target': 'request', 'from': ['idle'], 'priority': 1, 'restart': False},
                'receive-ack': {'target': 'ack', 'from': ['request'], 'priority': 2, 'interrupt': 'never'},
                'timeout': {'target': 'fault', 'from': ['request', 'ack'], 'priority': 3, 'interrupt': 'higher'},
                'reset': {'target': 'idle', 'priority': 4}}}
        load_profile(profile)
        files[ROOT / 'presets' / (name + '.json')] = json.dumps(profile, indent=2) + '\n'
        catalog[name] = {'use': use, 'profile': name + '.json', 'inputs': inputs, 'semantics': semantics,
            'review_requirements': review, 'external_consumer': external,
            'output_constraints': f'{size}x{size} transparent cells; explicit ordered frames; ' + ', '.join(formats)}
    files[ROOT / 'presets/catalog.json'] = json.dumps(catalog, indent=2) + '\n'
    doc = ['# Ten practical asset workflows', '', 'Generated by `python scripts/generate_presets.py`; validate drift with `--check`.', '',
           'All demonstrations use deterministic Pillow drawings labeled as fixtures and import them explicitly. The synthetic review records exercise gates only. For real artwork, prepare with the preset, import approved art or use installed imagegen handoffs, validate and visually review before packaging.', '',
           'Run all: `python scripts/demonstrate.py --all --output-dir output/capability-demos`.', '']
    for name, value in catalog.items():
        doc += [f'## {value["use"]} / {name}', '', value['semantics'], '',
                '**Inputs:** ' + value['inputs'], '', '**Constraints:** ' + value['output_constraints'], '',
                '**Review:** ' + value['review_requirements'], '', '**External consumer still needs:** ' + value['external_consumer'], '',
                '```powershell', f'python scripts/demonstrate.py --preset {name} --output-dir output/{name}-demo',
                f'python scripts/hatch.py prepare --run-dir output/{name}-production --profile presets/{name}.json --pet-name {name} --pet-notes "{value["inputs"]}"',
                '```', '', f'Inspect `output/{name}-demo/{name}/export/` and `acceptance.json`; the latter is generated by meaningful checks in `demonstrate.acceptance`, not by creating placeholders.', '']
    files[ROOT / 'references/additional-uses.md'] = '\n'.join(doc)
    return files


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    for path, text in build().items():
        if args.check:
            if not path.is_file() or path.read_text(encoding='utf-8') != text:
                raise SystemExit('generated preset/docs drift: ' + str(path))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
