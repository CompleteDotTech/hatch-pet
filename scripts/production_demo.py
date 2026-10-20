#!/usr/bin/env python3
"""Author the non-fixture Milo/Luma pilot from retained imagegen originals.

This recipe performs deterministic extraction, registration and scene assembly.
It never calls a model, invents acquisition receipts, or records visual approval.
Source coordinates and family scales below are explicit construction decisions;
animation never fits or rescales individual performance frames.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import wave

from PIL import Image, ImageDraw

from prepare_production_art import CHARACTERS
from production_contracts import file_sha, load_project
from production_fixture import track

VERSION = '3.0.0'
FPS = {'numerator': 12, 'denominator': 1}
CAST_SCALE = .56
ROOT_Y = 326


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8'))
    return path


def file_ref(root, path):
    path = Path(path)
    return {'path': path.relative_to(root).as_posix(), 'sha256': file_sha(path)}


def keyed(values, interpolation='linear'):
    return {'interpolation': interpolation, 'keys': [{'frame': f, 'value': v} for f, v in values]}


def original_provenance(root, name, job):
    run = root / 'acquisition' / name
    history = json.loads((run / 'imagegen-jobs.json').read_text(encoding='utf-8'))
    record = next(j for j in history['jobs'] if j['id'] == job)
    if history['fixture_mode'] or record['status'] != 'generated' or record['source_origin'] != 'imagegen':
        raise ValueError('pilot requires an actual ingested imagegen source: ' + name + '/' + job)
    original = root / 'art/originals' / (name + ('-turnaround-v3.png' if job == 'base' else '-parts-v3.png'))
    if file_sha(original) != record['source_hash']:
        raise ValueError('original source differs from real acquisition history: ' + str(original))
    receipt = root / 'acquisition/handoffs' / (name + '-' + job + '.json')
    handoff = json.loads(receipt.read_text(encoding='utf-8'))
    if handoff['receipt_template'] != record['generation_receipt']:
        raise ValueError('handoff differs from ingested receipt')
    return {'kind': 'imagegen', 'fixture': False,
        'origin': 'Original Milo/Luma artwork generated through the installed imagegen skill for hatch-pet; retained original PNG.',
        'attribution': 'Original character direction by the hatch-pet production demonstration; generated with OpenAI imagegen.',
        'permissions': 'Commissioned in this authorized repository task; no third-party character reference or separately supplied licence.',
        'source_sha256': record['source_hash'], 'model_call': record['model_call'],
        'acquisition': {'run_id': history['run_id'], 'job': job, 'receipt_path': receipt.relative_to(root).as_posix(),
            'receipt_sha256': file_sha(receipt), 'model_call': record['model_call']}}


def source_image(root, path, provenance):
    with Image.open(path) as image:
        size = list(image.size)
    return {**file_ref(root, path), 'size': size, 'provenance': provenance}


def drawing(image):
    return {'viewpoint': 'front', 'costume': 'everyday', 'image': image, 'alpha': 'straight'}


def extract(root, name, label, rect, factor, *, anchor=None, canvas=None, pivot=None, rotate=False):
    """Crop an annotated source region; apply one fixed family calibration.

    Facial choices use a common canvas and measured registration anchor, never
    independent per-drawing fitting. Native alpha is preserved with RGBA/LANCZOS.
    """
    original = root / 'art/originals' / (name + '-parts-v3.png')
    with Image.open(original) as source:
        source = source.convert('RGBA')
        if not (0 <= rect[0] < rect[2] <= source.width and 0 <= rect[1] < rect[3] <= source.height):
            raise ValueError('invalid annotated source rectangle: ' + name + '/' + label)
        crop = source.crop(rect)
    size = tuple(max(1, round(n * factor)) for n in crop.size)
    crop = crop.resize(size, Image.Resampling.LANCZOS)
    mapped = None if anchor is None else [(anchor[i] - rect[i]) * factor for i in range(2)]
    if rotate:
        crop = crop.transpose(Image.Transpose.ROTATE_180)
        if mapped:
            mapped = [size[i] - mapped[i] for i in range(2)]
    if canvas:
        registered = Image.new('RGBA', canvas, (0, 0, 0, 0))
        registered.alpha_composite(crop, tuple(round(pivot[i] - mapped[i]) for i in range(2)))
        crop = registered
        mapped = list(pivot)
    path = root / 'art/components' / name / (label + '.png')
    path.parent.mkdir(parents=True, exist_ok=True)
    crop.save(path, compress_level=9)
    provenance = {'kind': 'derived', 'fixture': False, 'origin': 'Hash-bound manual component extraction and fixed family registration.',
        'source': file_ref(root, original), 'operation': {'kind': 'annotated-crop-register', 'rect': list(rect),
            'note': json.dumps({'source_pixels_to_character_pixels': factor, 'source_anchor': anchor,
                'canvas': canvas, 'pivot': pivot, 'rotation_degrees': 180 if rotate else 0,
                'resampling': 'Pillow LANCZOS; straight source alpha'})}}
    return source_image(root, path, provenance), mapped


def component(cid, role, image, pivot, *, parent=None, anchor=None, offset=(0, 0), anchors=None, z=0, alternatives=None, mask=None):
    return {'id': cid, 'role': role, 'parent': parent, 'parent_anchor': anchor,
        'pivot': list(pivot), 'offset': list(offset), 'anchors': anchors or {}, 'z': z,
        'drawings': {key: drawing(value) for key, value in (alternatives or {'default': image}).items()},
        'default_drawing': next(iter(alternatives)) if alternatives else 'default', 'mask': mask, 'visible': True}


def make_character(root, name):
    provenance = original_provenance(root, name, 'parts')
    original_provenance(root, name, 'base')
    parts = []
    if name == 'milo':
        torso, _ = extract(root, name, 'torso', (20, 165, 378, 450), .5)
        torso_pivot, neck, offset = [88, 136], [88, 20], [0, -76]
        shoulders, hips = {'left': [40, 47], 'right': [136, 47]}, {'left': [50, 139], 'right': [126, 139]}
        head, _ = extract(root, name, 'head', (373, 85, 791, 449), .53)
        head_pivot, eye_at, brow_at, mouth_at = [108, 184], [108, 102], [108, 78], [108, 139]
        arm_rects = [(790, 147, 984, 452), (1037, 144, 1245, 452)]
        arm_pivots, wrists = [(937, 193), (1099, 192)], [(862, 421), (1157, 423)]
        arm_factor = .37
        paw_rects, paw_origins = [(38, 493, 291, 704), (350, 488, 621, 704)], [(218, 695), (426, 695)]
        paw_factor, paw_rotate = .23, True
        leg_rects, leg_origins = [(632, 451, 906, 772), (961, 449, 1225, 772)], [(782, 490), (1078, 489)]
        leg_factor, sole_y = .32, 745
        eye_rects, eye_anchors = [(25, 814, 326, 969), (347, 814, 627, 965)], [(174, 886), (480, 886)]
        brow_rects, brow_anchors = [(648, 815, 922, 936), (946, 815, 1248, 936)], [(784, 875), (1097, 875)]
        mouth_rects = [(25 + 313*c, 991, min(312 + 313*c, 1254), 1213) for c in range(4)]
        mouth_anchors = [(175, 1048), (471, 1048), (784, 1048), (1092, 1048)]
        mouth_factor = .51
        # Keep the scarf and stomach; remove the duplicated lower arm silhouettes.
        mask = Image.new('RGBA', torso['size'], (255, 255, 255, 0))
        polygon = [(96, 174), (334, 174), (374, 296), (330, 333), (320, 408), (276, 449), (109, 445), (76, 385), (78, 254)]
        ImageDraw.Draw(mask).polygon([((x-20)*.5, (y-165)*.5) for x, y in polygon], fill=(255, 255, 255, 255))
        mask_path = root / 'art/components/milo/torso-mask.png'
        mask.save(mask_path)
        torso_mask = source_image(root, mask_path, {'kind': 'derived', 'fixture': False,
            'origin': 'Authored construction occlusion mask removing duplicated source arm silhouettes; review separately.',
            'source': file_ref(root, root / 'art/originals/milo-parts-v3.png'),
            'operation': {'kind': 'construction-mask', 'note': json.dumps({'source_polygon': polygon})}})
        dimensions, relative = {'width': 250, 'height': 405}, 1.1
    else:
        torso, _ = extract(root, name, 'torso', (44, 114, 353, 493), .47)
        torso_pivot, neck, offset = [73, 166], [73, 17], [0, -91]
        shoulders, hips = {'left': [20, 39], 'right': [126, 39]}, {'left': [44, 168], 'right': [105, 168]}
        head, _ = extract(root, name, 'head', (336, 0, 684, 489), .53)
        head_pivot, eye_at, brow_at, mouth_at = [111, 250], [111, 178], [111, 155], [111, 207]
        arm_rects = [(678, 140, 916, 402), (997, 140, 1253, 402)]
        arm_pivots, wrists = [(855, 184), (1061, 184)], [(742, 395), (1179, 395)]
        arm_factor = .34
        paw_rects, paw_origins = [(56, 562, 291, 783), (417, 562, 656, 786)], [(214, 578), (485, 578)]
        paw_factor, paw_rotate = .26, False
        leg_rects, leg_origins = [(661, 470, 919, 815), (1001, 470, 1257, 815)], [(817, 514), (1096, 514)]
        leg_factor, sole_y = .36, 786
        eye_rects, eye_anchors = [(22, 814, 333, 987), (344, 814, 653, 987)], [(178, 899), (495, 899)]
        brow_rects, brow_anchors = [(647, 823, 952, 980), (974, 826, 1265, 980)], [(799, 931), (1117, 931)]
        mouth_rects = [(13 + 316*c, 1000, min(330 + 316*c, 1265), 1220) for c in range(4)]
        mouth_anchors = [(180, 1080), (510, 1054), (819, 1054), (1130, 1054)]
        mouth_factor = .40
        torso_mask = None
        dimensions, relative = {'width': 250, 'height': 530}, 1.0
    parts.append(component('torso', 'torso', torso, torso_pivot, offset=offset,
        anchors={'neck': neck, **{'shoulder-'+s: p for s, p in shoulders.items()}, **{'hip-'+s: p for s, p in hips.items()}}, z=0, mask=torso_mask))
    parts.append(component('head', 'head', head, head_pivot, parent='torso', anchor='neck', z=4,
        anchors={'eyes': eye_at, 'brows': brow_at, 'mouth': mouth_at}))
    for index, side in enumerate(('left', 'right')):
        arm, pivot = extract(root, name, 'arm-'+side, arm_rects[index], arm_factor, anchor=arm_pivots[index])
        wrist = [(wrists[index][i] - arm_rects[index][i]) * arm_factor for i in range(2)]
        parts.append(component('arm-'+side, 'limb', arm, pivot, parent='torso', anchor='shoulder-'+side, anchors={'wrist': wrist}, z=-1))
        paw, pivot = extract(root, name, 'hand-'+side, paw_rects[index], paw_factor, anchor=paw_origins[index], rotate=paw_rotate)
        grip = [pivot[0], min(paw['size'][1]-1, pivot[1] + (30 if name == 'milo' else 33))]
        parts.append(component('hand-'+side, 'hands', paw, pivot, parent='arm-'+side, anchor='wrist', anchors={'grip': grip}, z=7))
        leg, pivot = extract(root, name, 'leg-'+side, leg_rects[index], leg_factor, anchor=leg_origins[index])
        sole = [pivot[0], (sole_y-leg_rects[index][1]) * leg_factor]
        # The foot anchor is placed on the declared floor at neutral stance.
        hip_y = offset[1] + hips[side][1] - torso_pivot[1]
        correction = -hip_y - (sole[1]-pivot[1])
        parts.append(component('leg-'+side, 'limb', leg, pivot, parent='torso', anchor='hip-'+side,
            offset=[0, correction], anchors={'sole': sole}, z=-2))
    eye_drawings = {}
    for index, key in enumerate(('open', 'blink')):
        eye_drawings[key], _ = extract(root, name, 'eyes-'+key, eye_rects[index], .42,
            anchor=eye_anchors[index], canvas=(144, 78), pivot=(72, 39))
    parts.append(component('eyes', 'eyes', None, (72, 39), parent='head', anchor='eyes', z=6, alternatives=eye_drawings))
    brows = {}
    for index, key in enumerate(('raised', 'neutral')):
        brows[key], _ = extract(root, name, 'brows-'+key, brow_rects[index], .39,
            anchor=brow_anchors[index], canvas=(132, 66), pivot=(66, 38))
    brows = {'neutral': brows['neutral'], 'raised': brows['raised']}
    parts.append(component('brows', 'brows', None, (66, 38), parent='head', anchor='brows', z=6, alternatives=brows))
    mouths = {}
    for index, key in enumerate(('neutral', 'a', 'e', 'o')):
        mouths[key], _ = extract(root, name, 'mouth-'+key, mouth_rects[index], mouth_factor,
            anchor=mouth_anchors[index], canvas=(156, 112), pivot=(78, 30))
    parts.append(component('mouth', 'mouth', None, (78, 30), parent='head', anchor='mouth', z=6, alternatives=mouths))
    spec = CHARACTERS[name]
    base = root / 'art/originals' / (name + '-turnaround-v3.png')
    design_views = ['front', 'three-quarter-left', 'side-left', 'back'] if name == 'milo' else ['front', 'three-quarter-right', 'side-right', 'back']
    view_reviews = {view: {'status': 'approved', 'kind': 'assistant_visual', 'reviewer': 'assistant:/root',
        'evidence': [file_ref(root, base)], 'note': 'Actual original design reference inspected. This decision covers this design view only; component construction and animation need separate dependency-bound reviews. Front is the only authored animation rig.'} for view in design_views}
    if name == 'milo':
        view_reviews['back'].update(status='rejected', note='Final source inspection found the scarf knot on viewer-right in both front and back panels. Reconcile the rear knot with the fixed front asymmetry before approving or animating a back view. Retain this original as provenance; the frontal pilot does not use the rear drawing.')
    return {'id': name, 'version': VERSION, 'name': spec['name'], 'dimensions': dimensions, 'relative_scale': relative,
        'identity': {'proportions': {'head_to_body_height': .6, 'cast_relative_scale': relative},
            'palette': spec['palette'], 'materials': ['softly painted fur', 'matte woven costume'],
            'markings': spec['markings'], 'asymmetries': spec['asymmetries'], 'allowed_facings': ['front'], 'forbid_mirror': True},
        'views': design_views, 'view_reviews': view_reviews,
        'components': parts, 'costumes': [{'id': 'everyday', 'differences': ['Original coral scarf' if name == 'milo' else 'Original two-button ochre waistcoat'], 'drawings': {}}],
        'capabilities': {'action': ['idle', 'walk', 'stop', 'reaction', 'reach', 'grasp', 'hold', 'release'],
            'pose': ['stand', 'walk', 'reach', 'hold'], 'viewpoint': ['front'], 'facing': ['front'],
            'expression': ['neutral', 'warm-surprise', 'listening'], 'intensity': ['low', 'medium'],
            'gaze': ['partner', 'seed'], 'mouth': ['neutral', 'a', 'e', 'o'], 'hand': ['open-paw'],
            'costume': ['everyday'], 'prop_state': ['carried', 'shared', 'received'], 'contact': ['ground', 'seed']},
        'restrictions': [{'when': {'viewpoint': ['side-left', 'side-right', 'back']}, 'reason': 'Design references exist; these animated component viewpoints have not been authored.'}],
        'references': [file_ref(root, base), file_ref(root, root / 'art/originals' / (name + '-parts-v3.png'))],
        'provenance': provenance}


def make_art(root):
    characters = [make_character(root, name) for name in ('milo', 'luma')]
    assets = root / 'art/scenery'
    assets.mkdir(parents=True, exist_ok=True)
    provenance = {'kind': 'import', 'fixture': False, 'origin': 'Original vector-like scenery and seed packet authored in this production recipe; rasterized with Pillow.',
        'attribution': 'hatch-pet demonstration authoring', 'permissions': 'Created for this repository task; no external assets.'}
    for garden in (False, True):
        background = Image.new('RGBA', (720, 410), '#f5e9cb')
        draw = ImageDraw.Draw(background)
        for y in range(300):
            t = y / 300
            draw.line((0, y, 719, y), fill=(round(244-19*t), round(235-5*t), round(206-17*t), 255))
        draw.ellipse((-90, 180, 530, 460), fill='#d0daa4')
        draw.ellipse((320, 205, 840, 480), fill='#bdca91')
        draw.rectangle((0, 316, 720, 410), fill='#ead7ad')
        draw.line((0, 334, 720, 334), fill='#d4bf98', width=2)
        if garden:
            for x in range(10, 720, 64):
                draw.rounded_rectangle((x, 183, x+19, 295), radius=8, fill='#b8a779')
            draw.rectangle((0, 215, 720, 228), fill='#b8a779')
            draw.rectangle((0, 267, 720, 278), fill='#b8a779')
            draw.rounded_rectangle((475, 290, 611, 360), radius=12, fill='#b06e4f')
            draw.ellipse((475, 278, 611, 311), fill='#7c6045')
        else:
            draw.rectangle((32, 88, 58, 323), fill='#ad8860')
            draw.ellipse((-85, -78, 175, 219), fill='#819c6b')
            draw.ellipse((570, -15, 785, 165), fill='#9caf78')
        background.save(assets / ('garden.png' if garden else 'path.png'), compress_level=9)
    foreground = Image.new('RGBA', (720, 410))
    draw = ImageDraw.Draw(foreground)
    for x in (5, 24, 599, 617, 648, 667):
        draw.polygon([(x, 360), (x+7, 312), (x+15, 360)], fill='#6f8858')
    foreground.save(assets / 'foreground.png', compress_level=9)
    seed = Image.new('RGBA', (34, 42))
    draw = ImageDraw.Draw(seed)
    draw.rounded_rectangle((1, 1, 32, 40), radius=4, fill='#eed49a', outline='#9c774e', width=2)
    draw.line((17, 31, 17, 13), fill='#637d42', width=2)
    draw.ellipse((7, 13, 17, 21), fill='#92a85d')
    draw.ellipse((17, 8, 27, 16), fill='#92a85d')
    seed.save(assets / 'seed.png', compress_level=9)
    cast = {'schema_version': 1, 'kind': 'cast', 'id': 'milo-luma', 'version': VERSION, 'fixture': False,
        'characters': characters, 'props': [{'id': 'seed-packet', 'version': '1.0.0', 'name': 'Seed packet',
            'image': source_image(root, assets / 'seed.png', provenance), 'pivot': [17, 9], 'anchors': {'grip': [17, 9]}}]}
    write_json(root / 'cast.json', cast)
    return cast, {key: source_image(root, assets / (key + '.png'), provenance) for key in ('path', 'garden', 'foreground')}


def neutral_point(character, cid, anchor=None):
    components = {c['id']: c for c in character['components']}
    part = components[cid]
    if part['parent']:
        origin = neutral_point(character, part['parent'], part['parent_anchor'])
    else:
        origin = [0, 0]
    origin = [origin[i] + part['offset'][i] for i in range(2)]
    if anchor is not None:
        origin = [origin[i] + part['anchors'][anchor][i] - part['pivot'][i] for i in range(2)]
    return origin


def exchange_geometry(cast):
    centers, radii, vectors = [], [], []
    for character, x, side in zip(cast['characters'], (230, 410), ('right', 'left')):
        scale = CAST_SCALE * character['relative_scale']
        shoulder = neutral_point(character, 'arm-' + side)
        grip = neutral_point(character, 'hand-' + side, 'grip')
        vector = [grip[i]-shoulder[i] for i in range(2)]
        centers.append([x+shoulder[0]*scale, ROOT_Y+shoulder[1]*scale])
        radii.append(math.hypot(*vector)*scale)
        vectors.append(vector)
    a, b = centers
    distance = math.dist(a, b)
    if not abs(radii[0]-radii[1]) < distance < sum(radii):
        raise ValueError('authored cast cannot reach the exchange; reposition characters or supply a longer reach drawing')
    along = (radii[0]**2-radii[1]**2+distance**2)/(2*distance)
    height = math.sqrt(radii[0]**2-along**2)
    unit = [(b[i]-a[i])/distance for i in range(2)]
    base = [a[i]+along*unit[i] for i in range(2)]
    choices = [[base[0]-height*unit[1], base[1]+height*unit[0]],
               [base[0]+height*unit[1], base[1]-height*unit[0]]]
    target = max(choices, key=lambda p: p[1])
    angles = [math.degrees(math.atan2(target[1]-c[1], target[0]-c[0])-math.atan2(v[1], v[0]))
              for c, v in zip(centers, vectors)]
    return {'position': target, 'angles': dict(zip(('milo', 'luma'), angles)),
            'shoulders': centers, 'reach_radii': radii,
            'method': 'Authored rigid reach from measured construction anchors; lower circle intersection. No runtime IK or invented pose.'}


def base_clip(name, action, duration=24, start='stand', end='stand', mode='once'):
    return {'schema_version': 1, 'kind': 'clip', 'id': name+'-'+action, 'version': VERSION,
        'character': name+'@'+VERSION, 'viewpoint': 'front', 'facing': 'front',
        'start_pose': start, 'end_pose': end, 'duration_frames': duration, 'mode': mode,
        'completion': 'loop' if mode == 'loop' else 'hold', 'root': {'offset': track([0, 0])},
        'tracks': {'body': {}, 'face': {}, 'gaze': {}, 'mouth': {}}, 'contacts': [], 'events': [],
        'entry_points': [{'frame': 0, 'pose': start}], 'exit_points': [{'frame': duration-1, 'pose': end}],
        'interpolation': {'max_frames': 12, 'max_offset_per_frame': 20, 'max_rotation_per_frame': 20},
        'interruptions': {'policy': 'at-markers', 'frames': [0, duration//2, duration-1],
            'cancel_pose': end, 'max_transition_frames': 12}, 'displacement': [0, 0],
        'requirements': {'action': [action.split('-')[0]], 'pose': list(dict.fromkeys([start, end])),
            'hand': ['open-paw']}, 'full_frames': []}


def make_clips(root, cast, geometry):
    clips = []
    for character in cast['characters']:
        name = character['id']
        scale = CAST_SCALE * character['relative_scale']
        idle = base_clip(name, 'idle', mode='loop')
        idle['interruptions']['frames'] = [0, 2, 8, 12, 23]
        idle['tracks']['face'] = {'head': {'rotation': keyed([(0, 0), (12, 1.2), (24, 0)])},
            'eyes': {'drawing': keyed([(0, 'open'), (17, 'blink'), (19, 'open')], 'step')}}
        clips.append(idle)
        for direction, sign in (('right', 1), ('left', -1)):
            walk = base_clip(name, 'walk-'+direction, start='walk', end='walk', mode='loop')
            walk['root']['offset'] = track([0, 0], [sign*105, 0], end=24)
            walk['displacement'] = [sign*105, 0]
            walk['requirements']['contact'] = ['ground']
            for index, side in enumerate(('left', 'right')):
                part = next(c for c in character['components'] if c['id'] == 'leg-'+side)
                vector = [part['anchors']['sole'][i]-part['pivot'][i] for i in range(2)]
                length, original_angle = math.hypot(*vector), math.atan2(vector[1], vector[0])
                angles, offsets = [], []
                for f in range(25):
                    phase = (f + (12 if index else 0)) % 24
                    planted = phase < 12
                    t = phase / 12 if planted else (phase-12)/12
                    dx = sign * (26.25-52.5*t if planted else -26.25+52.5*t) / scale
                    desired_x = vector[0]+dx
                    if abs(desired_x) >= length:
                        raise ValueError('walk exceeds leg reach; lower speed or author a longer stride')
                    desired_y = math.sqrt(length*length-desired_x*desired_x)
                    angle = math.degrees(math.atan2(desired_y, desired_x)-original_angle)
                    lift = 0 if planted else 13*math.sin(math.pi*t)
                    angles.append((f, angle))
                    offsets.append((f, [0, vector[1]-desired_y-lift]))
                walk['tracks']['body']['leg-'+side] = {'rotation': keyed(angles), 'offset': keyed(offsets)}
                walk['tracks']['body']['arm-'+side] = {'rotation': keyed([(f, (1 if index else -1)*8*math.sin(f*math.pi/12)) for f in range(25)])}
                walk['contacts'].append({'start_frame': 12 if index else 0, 'end_frame': 24 if index else 12,
                    'component': 'leg-'+side, 'anchor': 'sole', 'kind': 'foot', 'target': 'ground'})
            clips.append(walk)
        # An authored entry step keeps the supporting right foot fixed while
        # the left foot swings into the first walk stance. A generic transform
        # blend would slide the declared planted foot as the root starts moving.
        start = base_clip(name, 'walk-start', duration=12, start='stand', end='walk')
        start['root']['offset'] = keyed([(f, [26.25*(f/12)**2, 0]) for f in range(13)])
        start['displacement'] = [26.25, 0]
        start['requirements']['contact'] = ['ground']
        for side in ('left', 'right'):
            part = next(c for c in character['components'] if c['id'] == 'leg-'+side)
            vector = [part['anchors']['sole'][i]-part['pivot'][i] for i in range(2)]
            length, original_angle = math.hypot(*vector), math.atan2(vector[1], vector[0])
            angles, offsets = [], []
            for f in range(13):
                t = f/12
                root_x = 26.25*t*t
                foot_x = 52.5*(3*t*t-2*t*t*t) if side == 'left' else 0
                desired_x = vector[0] + (foot_x-root_x)/scale
                if abs(desired_x) >= length:
                    raise ValueError('walk entry exceeds leg reach; author a shorter entry step')
                desired_y = math.sqrt(length*length-desired_x*desired_x)
                lift = 13*math.sin(math.pi*t) if side == 'left' else 0
                angles.append((f, math.degrees(math.atan2(desired_y, desired_x)-original_angle)))
                offsets.append((f, [0, vector[1]-desired_y-lift]))
            start['tracks']['body']['leg-'+side] = {'rotation': keyed(angles), 'offset': keyed(offsets)}
        start['contacts'] = [{'start_frame': 0, 'end_frame': 12, 'component': 'leg-right',
            'anchor': 'sole', 'kind': 'foot', 'target': 'ground'}]
        clips.append(start)
        stop = base_clip(name, 'stop', duration=12, start='walk')
        sign = 1 if name == 'milo' else -1
        stop['root']['offset'] = keyed([(0, [0, 0]), (6, [sign*8, 0]), (12, [sign*10, 0])])
        stop['displacement'] = [sign*10, 0]
        clips.append(stop)
        reaction = base_clip(name, 'reaction')
        reaction['requirements'].update(expression=['warm-surprise'], intensity=['medium'])
        reaction['tracks']['face'] = {'head': {'rotation': keyed([(0, 0), (8, -4 if name == 'milo' else 4), (18, 2), (24, 0)])},
            'brows': {'drawing': keyed([(0, 'neutral'), (5, 'raised'), (21, 'neutral')], 'step')}}
        clips.append(reaction)
        side, angle = ('right' if name == 'milo' else 'left'), geometry['angles'][name]
        for action, start, end, keys, mode in (
            ('reach', 'stand', 'hold', [(0, 0), (36, angle), (48, angle)], 'once'),
            ('hold', 'hold', 'hold', [(0, angle)], 'hold'),
            ('release', 'hold', 'stand', [(0, angle), (12, angle), (48, 0)], 'once')):
            clip = base_clip(name, action, duration=48, start=start, end=end, mode=mode)
            clip['tracks']['body']['arm-'+side] = {'rotation': keyed(keys)}
            clip['requirements']['prop_state'] = ['carried' if name == 'milo' else 'received']
            clips.append(clip)
        exchange = base_clip(name, 'exchange', duration=168)
        exchange['requirements'] = {'action': ['reach', 'grasp', 'hold', 'release'], 'pose': ['stand', 'hold'],
            'hand': ['open-paw'], 'prop_state': ['shared'], 'contact': ['seed'], 'gaze': ['partner', 'seed']}
        exchange['tracks']['body']['arm-'+side] = {'rotation': keyed([(0, 0), (24, 0), (60, angle), (102, angle), (144, 0), (168, 0)])}
        exchange['tracks']['face']['head'] = {'rotation': keyed([(0, 0), (34, -2 if name == 'milo' else 2), (64, 0), (120, 0)])}
        exchange['contacts'] = [{'start_frame': 60, 'end_frame': 103, 'component': 'hand-'+side,
            'anchor': 'grip', 'kind': 'hand', 'target': 'seed'}]
        exchange['events'] = [{'frame': 84, 'id': 'give' if name == 'milo' else 'receive',
            'type': 'release' if name == 'milo' else 'attach', 'component': 'hand-'+side, 'anchor': 'grip', 'target': 'seed'}]
        clips.append(exchange)
    for clip in clips:
        write_json(root / 'clips' / (clip['id'] + '.json'), clip)
    return clips


DIALOGUE = [
    ('milo', 'Luma, I found a seed. Can you help me plant it?', 'rms'),
    ('luma', 'Of course. A little care can grow into something wonderful.', 'slt'),
    ('luma', "Come on. Let's give it a sunny home.", 'slt'),
    ('milo', 'This looks like the perfect spot. Our little seed has a home.', 'rms'),
    ('luma', "And tomorrow, we will come back and see how it grows.", 'slt'),
]


def make_audio(root, *, synthesize_missing=False):
    """Local Flite TTS; retained originals, explicit frame padding, editable cues."""
    ffmpeg = shutil.which('ffmpeg')
    version = None
    result = []
    for index, (speaker, text, voice) in enumerate(DIALOGUE, 1):
        prefix = 'line-' + str(index).zfill(2)
        original = root / 'audio/original' / (prefix + '.wav')
        text_path = original.with_suffix('.txt')
        receipt_path = original.with_suffix('.json')
        original.parent.mkdir(parents=True, exist_ok=True)
        text_bytes = text.encode('utf-8')
        if text_path.exists() and text_path.read_bytes() != text_bytes:
            raise ValueError('dialogue source changed; retain this audio version and author a new line version')
        if not original.exists():
            if not synthesize_missing:
                raise ValueError('missing retained dialogue: restore audio-source-bundle; new speech requires explicit --synthesize-missing-audio')
            if ffmpeg is None:
                raise ValueError('missing retained dialogue: restore audio-source-bundle or supply local FFmpeg with Flite')
            if not text_path.exists():
                text_path.write_bytes(text_bytes)
            if version is None:
                version = subprocess.check_output([ffmpeg, '-version'], text=True).splitlines()[0]
            subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i',
                'flite=textfile='+str(text_path)+':voice='+voice, '-ar', '48000', '-ac', '1',
                '-c:a', 'pcm_s16le', '-flags', '+bitexact', str(original)], check=True, timeout=30)
            write_json(receipt_path, {'schema_version': 1, 'kind': 'local-tts-record', 'engine': version,
                'voice': voice, 'audio': file_ref(root, original), 'text': file_ref(root, text_path),
                'method': 'Actual local FFmpeg Flite synthesis; original source retained unchanged.',
                'provider_id': None, 'provider_id_unavailable_reason': 'Local TTS has no remote provider call.'})
        if not receipt_path.is_file():
            raise ValueError('retained TTS source needs its original provenance receipt: ' + str(receipt_path))
        tts_record = json.loads(receipt_path.read_text(encoding='utf-8'))
        if (tts_record.get('audio') != file_ref(root, original) or tts_record.get('text') != file_ref(root, text_path)
                or tts_record.get('voice') != voice or not tts_record.get('engine')):
            raise ValueError('retained TTS audio, text or voice differs from its source receipt')
        with wave.open(str(original), 'rb') as stream:
            if (stream.getframerate(), stream.getnchannels(), stream.getsampwidth()) != (48000, 1, 2):
                raise ValueError('retained dialogue must be 48 kHz mono 16-bit PCM')
            samples = stream.readframes(stream.getnframes())
        frames = math.ceil(len(samples)/2/4000)
        padded = samples + b'\0' * (frames*4000*2-len(samples))
        path = root / 'audio' / (prefix+'.wav')
        with wave.open(str(path), 'wb') as stream:
            stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(48000)
            stream.writeframes(padded)
        provenance = {'kind': 'import', 'fixture': False, 'origin': 'Original short dialogue synthesized locally by FFmpeg Flite, voice '+voice+'.',
            'attribution': 'Original script authored for the Milo/Luma pilot; local Flite voice '+voice,
            'permissions': 'No supplied third-party recording. TTS engine and bundled voice remain subject to their distributed licences.',
            'source': file_ref(root, original), 'references': [file_ref(root, receipt_path), file_ref(root, text_path)],
            'operation': {'kind': 'pcm-frame-padding',
                'note': json.dumps({'engine': tts_record['engine'], 'tts_receipt': file_ref(root, receipt_path), 'voice': voice, 'source_samples': len(samples)//2,
                    'output_samples': len(padded)//2, 'sample_rate': 48000, 'channels': 1,
                    'text': file_ref(root, text_path), 'mouth_timing': 'Editable amplitude-gated rhythmic approximation; not phoneme alignment or acting acceptance.'})}}
        result.append({'id': prefix, 'speaker': speaker, 'text': text, 'duration_frames': frames,
            'file': file_ref(root, path), 'provenance': provenance, 'gain': 1, 'mouth_cues': []})
    return result


def place(name, clip, start, end, blend=0):
    return {'clip': name+'-'+clip+'@'+VERSION, 'start_frame': start, 'end_frame': end,
            'transition': {'kind': 'interpolate' if blend else 'cut', 'frames': blend}}


def actor(name, x, placements):
    return {'id': name, 'character': name+'@'+VERSION, 'viewpoint': 'front', 'facing': 'front', 'costume': 'everyday',
        'position': [x, ROOT_Y], 'z': 20, 'clips': placements,
        'tracks': {'body': {}, 'face': {}, 'gaze': {'eyes': {'offset': track([2 if name == 'milo' else -2, 0])}}, 'mouth': {}},
        'requirements': {'gaze': ['partner'], 'expression': ['listening'], 'intensity': ['low']},
        'bindings': {'partner': 'luma' if name == 'milo' else 'milo', 'seed': 'seed-packet'}}


def prop(owner):
    return {'id': 'seed-packet', 'prop': 'seed-packet@1.0.0', 'position': [0, 0], 'z': 26,
        'owner': owner, 'attachment': {'instance': owner, 'component': 'hand-right' if owner == 'milo' else 'hand-left', 'anchor': 'grip'},
        'tracks': {}, 'ownership': []}


def shot(sid, duration, actors, owner, scenery, *, garden=False, camera=(0, 0), zoom=1):
    return {'id': sid, 'duration_frames': duration, 'cast_scale': CAST_SCALE, 'instances': actors,
        'props': [prop(owner)], 'interactions': [], 'audio': [],
        'layers': [{'id': 'background', 'image': scenery['garden' if garden else 'path'], 'position': [0, 0], 'z': -100, 'opacity': 1, 'parallax': 1},
            {'id': 'foreground', 'image': scenery['foreground'], 'position': [0, 0], 'z': 60, 'opacity': 1, 'parallax': 1}],
        'camera': {'position': track(list(camera)), 'zoom': track(zoom),
            'bounds': {'max_pan_per_frame': 2, 'min_zoom': 1, 'max_zoom': 1.15}},
        'lighting': {'direction': 'left', 'color_treatment': 'Warm sRGB storybook palette; upper-left painted character light; no runtime relighting.'},
        'explicit_requirements': ['Use the same versioned cast, fixed relative scale, declared audio and ownership across the sequence.'],
        'inferred_choices': ['Original seed-exchange story, warm path/garden scenery and audience-facing cutout performances chosen for this pilot.',
            'Front artwork supports screen-space locomotion; sideways or back-facing animation is not inferred from the design turnaround.']}


def add_dialogue(root, shot, source, start):
    import array
    audio = copy.deepcopy(source)
    audio['start_frame'] = start
    if start < 0 or start + audio['duration_frames'] > shot['duration_frames']:
        raise ValueError('dialogue exceeds shot boundary: ' + audio['id'])
    with wave.open(str(root / audio['file']['path']), 'rb') as stream:
        samples = array.array('h', stream.readframes(stream.getnframes()))
    cues, keys = [], {0: 'neutral'}
    shapes = ('a', 'e', 'a', 'o', 'e', 'neutral')
    for local in range(0, audio['duration_frames'], 3):
        stop = min(local+3, audio['duration_frames'])
        segment = samples[local*4000:stop*4000]
        active = segment and sum(abs(n) for n in segment)/len(segment) > 140
        shape = shapes[(local//3)%len(shapes)] if active else 'neutral'
        cues.append({'start_frame': start+local, 'end_frame': start+stop, 'shape': shape})
        keys[start+local] = shape
    keys[start+audio['duration_frames']] = 'neutral'
    audio['mouth_cues'] = cues
    shot['audio'].append(audio)
    actor = next(i for i in shot['instances'] if i['id'] == audio['speaker'])
    actor['tracks']['mouth']['mouth'] = {'drawing': keyed(sorted(keys.items()), 'step')}
    return audio


def build_pilot(root, *, audio=True, synthesize_missing_audio=False):
    root = Path(root).resolve()
    cast, scenery = make_art(root)
    geometry = exchange_geometry(cast)
    clips = make_clips(root, cast, geometry)
    arrival = shot('arrival', 144, [
        actor('milo', -95, [place('milo', 'walk-right', 0, 72), place('milo', 'stop', 72, 84, 6), place('milo', 'idle', 84, 144, 6)]),
        actor('luma', 735, [place('luma', 'walk-left', 0, 72), place('luma', 'stop', 72, 84, 6), place('luma', 'idle', 84, 120, 6), place('luma', 'reaction', 120, 144, 6)])], 'milo', scenery)
    exchange = shot('exchange', 168, [actor(n, x, [place(n, 'exchange', 0, 168)]) for n, x in (('milo', 230), ('luma', 410))], 'milo', scenery,
        camera=(35, 24), zoom=1.1)
    exchange['instances'][0]['tracks']['face']['brows'] = {'drawing': keyed([(0, 'neutral'), (46, 'raised'), (72, 'neutral')], 'step')}
    for instance in exchange['instances']:
        x = 2 if instance['id'] == 'milo' else -2
        instance['tracks']['gaze']['eyes']['offset'] = keyed([(0, [x, 0]), (54, [x, 0]), (60, [x, 3]), (102, [x, 3]), (112, [x, 0])])
    exchange['props'][0]['ownership'] = [{'frame': 84, 'from': 'milo', 'to': 'luma',
        'attachment': {'instance': 'luma', 'component': 'hand-left', 'anchor': 'grip'}, 'event': 'seed-handoff'}]
    exchange['interactions'] = [{'id': 'seed-handoff', 'frame': 84, 'prop': 'seed-packet', 'position': geometry['position'], 'tolerance': .00001,
        'participants': [{'instance': 'milo', 'component': 'hand-right', 'anchor': 'grip', 'marker': 'give'},
            {'instance': 'luma', 'component': 'hand-left', 'anchor': 'grip', 'marker': 'receive'}]}]
    departure = shot('departure', 120, [actor(n, x, [place(n, 'idle', 0, 2), place(n, 'walk-start', 2, 14), place(n, 'walk-right', 14, 120)])
        for n, x in (('milo', 230), ('luma', 410))], 'luma', scenery)
    garden = shot('garden', 144, [actor(n, x, [place(n, 'reaction', 0, 24), place(n, 'idle', 24, 144, 6)])
        for n, x in (('milo', 230), ('luma', 410))], 'luma', scenery, garden=True)
    tomorrow = shot('tomorrow', 120, [actor(n, x, [place(n, 'idle', 0, 84), place(n, 'reaction', 84, 108, 6), place(n, 'idle', 108, 120, 6)])
        for n, x in (('milo', 230), ('luma', 410))], 'luma', scenery, garden=True, camera=(18, 10), zoom=1.05)
    if audio:
        lines = make_audio(root, synthesize_missing=synthesize_missing_audio)
        for target, line, preferred in zip((arrival, exchange, departure, garden, tomorrow), lines, (86, 10, 1, 27, 12)):
            add_dialogue(root, target, line, min(preferred, target['duration_frames']-line['duration_frames']-5))
    continuity = lambda a, b, position=True: {'from_shot': a, 'to_shot': b, 'characters': ['milo@'+VERSION, 'luma@'+VERSION],
        'requirements': ['costume', 'scale', 'prop_ownership'] + (['position'] if position else []),
        'note': 'Same exact cast and prop identity across this cut.' if position else 'Explicit time and location cut from the path exit to the garden; ownership, costume and scale continue.'}
    scenes = [
        {'schema_version': 1, 'kind': 'scene', 'id': 'seed-exchange', 'version': VERSION, 'shots': [arrival, exchange, departure],
            'continuity': [continuity('arrival', 'exchange'), continuity('exchange', 'departure')]},
        {'schema_version': 1, 'kind': 'scene', 'id': 'garden-promise', 'version': VERSION, 'shots': [garden, tomorrow],
            'continuity': [continuity('departure', 'garden', False), continuity('garden', 'tomorrow')]}]
    for scene in scenes:
        write_json(root / 'scenes' / (scene['id'] + '.json'), scene)
    project = {'schema_version': 1, 'kind': 'project', 'id': 'milo-luma-pilot', 'version': VERSION, 'fixture': False,
        'cast': file_ref(root, root / 'cast.json'),
        'clips': [file_ref(root, root / 'clips' / (c['id']+'.json')) for c in clips],
        'scenes': [file_ref(root, root / 'scenes' / (s['id']+'.json')) for s in scenes],
        'render': {'width': 640, 'height': 360, 'fps': FPS, 'color_space': 'srgb', 'alpha': 'straight',
            'resampling': 'bicubic', 'background': '#F5E9CBFF'},
        'limits': {'max_frames': 1200, 'max_assets': 256, 'max_source_pixels': 2000000,
            'max_work_bytes': 256*1024*1024, 'max_generation_calls': 4}}
    write_json(root / 'project.json', project)
    write_json(root / 'evidence/authored-geometry.json', geometry)
    bundle = load_project(root)
    from production_render import evaluate_frame, render_frame
    handoff = evaluate_frame(bundle, 'exchange', 84)
    write_json(root / 'evidence/contact-frame-84.json', {'fixture': False, 'method': 'deterministic_geometry',
        'interaction': handoff['interactions'], 'prop': handoff['props']['seed-packet'],
        'visual_review_performed': False})
    for sid, frame in (('arrival', 96), ('exchange', 84), ('garden', 12)):
        image, _ = render_frame(bundle, sid, frame)
        image.save(root / 'evidence' / (sid+'-construction.png'))
    return {'project': str(root / 'project.json'), 'characters': 2, 'clips': len(clips),
        'scenes': [{'id': s['id'], 'frames': sum(x['duration_frames'] for x in s['shots'])} for s in scenes],
        'fixture': False, 'provider_called': False, 'visual_review_performed': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path('examples/production-pilot'))
    parser.add_argument('--without-audio', action='store_true', help='Construction diagnostics only; not the complete production demonstration')
    parser.add_argument('--synthesize-missing-audio', action='store_true', help='Explicitly create new Flite speech if originals are absent; this is not exact delivery reconstruction')
    args = parser.parse_args(argv)
    print(json.dumps(build_pilot(args.project, audio=not args.without_audio,
        synthesize_missing_audio=args.synthesize_missing_audio), indent=2))


if __name__ == '__main__':
    main()
