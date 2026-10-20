"""Small reproducible geometric project for development, never artwork acceptance."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from PIL import Image, ImageDraw

from production_contracts import file_sha


def fixture_provenance():
    return {'kind': 'fixture', 'origin': 'Original geometric synthetic test artwork.', 'fixture': True}


def track(value, final=None, end=12, interpolation=None):
    interpolation = interpolation or ('step' if isinstance(value, (str, bool)) else 'linear')
    keys = [{'frame': 0, 'value': copy.deepcopy(value)}]
    if final is not None:
        keys.append({'frame': end, 'value': copy.deepcopy(final)})
    return {'interpolation': interpolation, 'keys': keys}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    return {'path': path.name, 'sha256': file_sha(path)}


def refresh_project_hashes(root):
    root = Path(root)
    path = root / 'project.json'
    project = json.loads(path.read_text(encoding='utf-8'))
    for reference in [project['cast'], *project['clips'], *project['scenes']]:
        reference['sha256'] = file_sha(root / reference['path'])
    write_json(path, project)
    return path


def build_fixture_project(root):
    """Write a shared two-character cast, two clips and two twelve-frame scenes."""
    root = Path(root)
    (root / 'art').mkdir(parents=True, exist_ok=True)

    def picture(name, size, fill, shape='rounded'):
        path = root / 'art' / (name + '.png')
        image = Image.new('RGBA', size)
        draw = ImageDraw.Draw(image)
        box = (1, 1, size[0] - 2, size[1] - 2)
        if shape == 'ellipse':
            draw.ellipse(box, fill=fill)
        elif shape == 'line':
            draw.line((1, size[1] // 2, size[0] - 2, size[1] // 2), fill=fill, width=1)
        else:
            draw.rounded_rectangle(box, radius=min(size) // 4, fill=fill)
        image.save(path)
        image.close()
        return {'path': path.relative_to(root).as_posix(), 'sha256': file_sha(path),
                'size': list(size), 'provenance': fixture_provenance()}

    characters = []
    for identity, color in [('a', '#CB5B35'), ('b', '#438C92')]:
        def drawing(image):
            return {'viewpoint': 'front', 'costume': 'default', 'image': image, 'alpha': 'straight'}
        def component(cid, role, parent, parent_anchor, pivot, anchors, size, fill, z=0, shape='rounded'):
            return {'id': cid, 'role': role, 'parent': parent, 'parent_anchor': parent_anchor,
                'pivot': pivot, 'offset': [0, 0], 'anchors': anchors, 'z': z,
                'drawings': {'default': drawing(picture(identity + '-' + cid, size, fill, shape))},
                'default_drawing': 'default', 'mask': None, 'visible': True}
        parts = [
            component('body', 'body', None, None, [20, 40],
                      {'neck': [20, 4], 'hand': [36 if identity == 'a' else 4, 20], 'foot': [20, 40]}, (40, 40), color),
            component('head', 'head', 'body', 'neck', [10, 20],
                      {'mouth': [10, 14], 'eyes': [10, 7]}, (20, 20), color, 1, 'ellipse'),
            component('hand', 'hands', 'body', 'hand', [4, 4], {'grip': [4, 4]}, (8, 8), color, 2, 'ellipse'),
            component('mouth', 'mouth', 'head', 'mouth', [4, 3], {}, (8, 6), '#292335', 3, 'line'),
            component('eyes', 'eyes', 'head', 'eyes', [6, 2], {}, (12, 4), '#292335', 3, 'ellipse')]
        parts[3]['drawings']['open'] = drawing(picture(identity + '-mouth-open', (8, 6), '#292335', 'ellipse'))
        body_image = parts[0]['drawings']['default']['image']
        characters.append({'id': identity, 'version': '1.0.0', 'name': identity.upper(),
            'dimensions': {'width': 40, 'height': 60}, 'relative_scale': 1,
            'identity': {'proportions': {'head_to_body': .5}, 'palette': {'body': color},
                         'materials': ['Geometric synthetic fixture'], 'markings': [], 'asymmetries': [],
                         'allowed_facings': ['front'], 'forbid_mirror': True},
            'views': ['front'], 'view_reviews': {'front': {'status': 'approved', 'kind': 'synthetic',
                'reviewer': 'fixture-builder', 'evidence': [{key: body_image[key] for key in ('path', 'sha256')}],
                'note': 'Synthetic contract evidence only; no production artwork or human approval.'}},
            'components': parts, 'costumes': [{'id': 'default', 'differences': [], 'drawings': {}}],
            'capabilities': {'action': ['idle', 'walk', 'grasp', 'release'], 'pose': ['standing', 'sitting', 'neutral'],
                'viewpoint': ['front'], 'facing': ['front'], 'expression': ['neutral', 'happy'], 'intensity': ['low'],
                'gaze': ['partner'], 'mouth': ['default', 'open'], 'hand': ['default', 'open'],
                'costume': ['default'], 'prop_state': ['free', 'held'], 'contact': ['hand:cup']},
            'restrictions': [], 'references': [], 'provenance': fixture_provenance()})
    prop = {'id': 'cup', 'version': '1.0.0', 'name': 'Synthetic cup',
            'image': picture('cup', (8, 8), '#E3B746'), 'pivot': [4, 8], 'anchors': {'grip': [4, 8]}}
    cast = {'schema_version': 1, 'kind': 'cast', 'id': 'fixture-cast', 'version': '1.0.0',
            'fixture': True, 'characters': characters, 'props': [prop]}
    cast_ref = write_json(root / 'cast.json', cast)
    clips = []
    for identity in ('a', 'b'):
        blink = {'interpolation': 'step', 'keys': [{'frame': 0, 'value': True},
                 {'frame': 8, 'value': False}, {'frame': 9, 'value': True}]}
        mouth = {'interpolation': 'step', 'keys': [{'frame': 0, 'value': 'default'},
                 {'frame': 4, 'value': 'open'}, {'frame': 8, 'value': 'default'}]}
        clip = {'schema_version': 1, 'kind': 'clip', 'id': 'idle-' + identity, 'version': '1.0.0',
            'character': identity + '@1.0.0', 'viewpoint': 'front', 'facing': 'front',
            'start_pose': 'standing', 'end_pose': 'standing', 'duration_frames': 12,
            'mode': 'once', 'completion': 'hold', 'root': {'offset': track([0, 0])},
            'tracks': {'body': {'head': {'rotation': track(0)}}, 'face': {'eyes': {'visible': blink}},
                       'gaze': {'eyes': {'offset': track([0, 0])}}, 'mouth': {'mouth': {'drawing': mouth}}},
            'contacts': [{'start_frame': 0, 'end_frame': 12, 'component': 'hand', 'anchor': 'grip', 'kind': 'hand', 'target': 'cup'}],
            'events': [{'frame': 6, 'id': 'release' if identity == 'a' else 'grasp',
                        'type': 'release' if identity == 'a' else 'attach', 'component': 'hand', 'anchor': 'grip', 'target': 'cup'}],
            'entry_points': [{'frame': 0, 'pose': 'standing'}], 'exit_points': [{'frame': 11, 'pose': 'standing'}],
            'interpolation': {'max_frames': 6, 'max_offset_per_frame': 8, 'max_rotation_per_frame': 30},
            'interruptions': {'policy': 'at-markers', 'frames': [6], 'cancel_pose': 'standing', 'max_transition_frames': 6},
            'displacement': [0, 0], 'requirements': {'action': ['idle'], 'pose': ['standing'], 'gaze': ['partner']},
            'full_frames': []}
        clips.append(write_json(root / ('idle-' + identity + '.json'), clip))

    def actor(identity, x):
        return {'id': identity, 'character': identity + '@1.0.0', 'viewpoint': 'front', 'facing': 'front',
            'costume': 'default', 'position': [x, 140], 'z': 10,
            'clips': [{'clip': 'idle-' + identity + '@1.0.0', 'start_frame': 0, 'end_frame': 12,
                       'transition': {'kind': 'cut', 'frames': 0}}],
            'tracks': {}, 'requirements': {'gaze': ['partner'], 'expression': ['neutral']},
            'bindings': {'cup': 'cup-object', 'partner': 'b' if identity == 'a' else 'a'}}

    shot = {'id': 'exchange', 'duration_frames': 12, 'cast_scale': 1,
        'instances': [actor('a', 100), actor('b', 132)],
        'props': [{'id': 'cup-object', 'prop': 'cup@1.0.0', 'position': [116, 120], 'z': 20,
            'owner': 'a', 'attachment': {'instance': 'a', 'component': 'hand', 'anchor': 'grip'}, 'tracks': {},
            'ownership': [{'frame': 6, 'from': 'a', 'to': 'b',
                'attachment': {'instance': 'b', 'component': 'hand', 'anchor': 'grip'}, 'event': 'handoff'}]}],
        'interactions': [{'id': 'handoff', 'frame': 6, 'prop': 'cup-object',
            'participants': [{'instance': 'a', 'component': 'hand', 'anchor': 'grip', 'marker': 'release'},
                             {'instance': 'b', 'component': 'hand', 'anchor': 'grip', 'marker': 'grasp'}],
            'position': [116, 120], 'tolerance': 0}],
        'layers': [], 'camera': {'position': track([0, 0]), 'zoom': track(1),
            'bounds': {'max_pan_per_frame': 16, 'min_zoom': .5, 'max_zoom': 2}},
        'audio': [], 'lighting': {'direction': 'ambient', 'color_treatment': 'unchanged'},
        'explicit_requirements': ['Synthetic software contract fixture.'],
        'inferred_choices': ['Original geometric artwork; no production visual approval.']}
    first = {'schema_version': 1, 'kind': 'scene', 'id': 'first-scene', 'version': '1.0.0', 'shots': [shot], 'continuity': []}
    reuse = copy.deepcopy(shot)
    reuse['id'] = 'reuse'
    reuse['props'][0].update(owner='b', attachment={'instance': 'b', 'component': 'hand', 'anchor': 'grip'}, ownership=[])
    reuse['interactions'] = []
    reuse['camera']['zoom'] = track(1.1)
    second = {'schema_version': 1, 'kind': 'scene', 'id': 'second-scene', 'version': '1.0.0', 'shots': [reuse],
        'continuity': [{'from_shot': 'exchange', 'to_shot': 'reuse', 'characters': ['a@1.0.0', 'b@1.0.0'],
            'requirements': ['costume', 'scale', 'prop_ownership', 'position'], 'note': 'Reuse exact cast versions and completed ownership.'}]}
    scene_refs = [write_json(root / 'first-scene.json', first), write_json(root / 'second-scene.json', second)]
    project = {'schema_version': 1, 'kind': 'project', 'id': 'fixture-project', 'version': '1.0.0', 'fixture': True,
        'cast': cast_ref, 'clips': clips, 'scenes': scene_refs,
        'render': {'width': 320, 'height': 200, 'fps': {'numerator': 12, 'denominator': 1},
                   'color_space': 'srgb', 'alpha': 'straight', 'resampling': 'nearest', 'background': '#00000000'},
        'limits': {'max_frames': 120, 'max_assets': 128, 'max_source_pixels': 2000000,
                   'max_work_bytes': 256 * 1024 * 1024, 'max_generation_calls': 0}}
    write_json(root / 'project.json', project)
    return root / 'project.json'
