"""Authored character fixtures for deterministic extraction tests, never model evidence.

Every layer has known semantic intent because this file draws it.  Visible masks are
computed from authored geometry, independently of the decomposition implementation.
They are not an automatic semantic segmenter's predictions.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


FIXTURE_ORIGIN = 'Hatch Pet authored synthetic character fixture; not production artwork or model output.'
FIXTURE_NAMES = ('cartoon', 'overlap', 'accessories', 'creature', 'pixel', 'alpha', 'complex', 'multiple')


@dataclass
class CharacterFixture:
    root: Path
    source: Path
    foreground: Path
    foreground_mask: Path
    annotation: Path
    components: list[dict]
    expected: Image.Image
    size: tuple[int, int]
    name: str


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _layer(size, identifier, category, color, shapes, parent=None, side=None,
           hidden=False, confidence=1.0):
    image = Image.new('RGBA', size)
    draw = ImageDraw.Draw(image)
    for kind, coords in shapes:
        if kind == 'rounded':
            draw.rounded_rectangle(coords, radius=max(1, (coords[2] - coords[0]) // 5), fill=color)
        elif kind == 'line':
            draw.line(coords, fill=color, width=2)
        else:
            getattr(draw, kind)(coords, fill=color)
    return {'id': identifier, 'name': identifier.replace('-', ' ').title(), 'category': category,
            'parent': parent, 'side': side, 'hidden': hidden, 'confidence': confidence, 'image': image}


def _cartoon(variant):
    size = (96, 112)
    # Anatomical left is on the viewer's right for this front-facing character.
    layer = lambda identifier, category, color, shapes, **kwargs: _layer(size, identifier, category, color, shapes, **kwargs)
    parts = [
        layer('anatomical-right-leg', 'anatomy/leg', '#CA7947', [('rounded', (29, 78, 43, 104))], parent='torso', side='right'),
        layer('anatomical-left-leg', 'anatomy/leg', '#CA7947', [('rounded', (53, 78, 67, 104))], parent='torso', side='left'),
        layer('torso', 'anatomy/torso', '#DA9360', [('rounded', (24, 44, 71, 88))], hidden=True),
        layer('anatomical-right-arm', 'anatomy/arm', '#E9AB78', [('rounded', (12, 46, 28, 79))], parent='torso', side='right'),
        layer('anatomical-left-arm', 'anatomy/arm', '#E9AB78', [('rounded', (68, 46, 84, 79))], parent='torso', side='left'),
        layer('head', 'anatomy/head', '#F0B585', [('ellipse', (22, 12, 73, 56))], parent='torso', hidden=True),
        layer('anatomical-right-ear', 'anatomy/ear', '#D98B53', [('ellipse', (15, 23, 27, 39))], parent='head', side='right'),
        layer('anatomical-left-ear', 'anatomy/ear', '#D98B53', [('ellipse', (68, 23, 80, 39))], parent='head', side='left'),
        layer('anatomical-right-eye', 'face/eye', '#253547', [('ellipse', (34, 29, 41, 37))], parent='head', side='right'),
        layer('anatomical-left-eye', 'face/eye', '#253547', [('ellipse', (55, 29, 62, 37))], parent='head', side='left'),
        layer('eye-highlights', 'detail/highlight', '#FFFFFF', [('rectangle', (35, 30, 36, 31)), ('rectangle', (56, 30, 57, 31))], parent='head'),
        layer('mouth', 'face/mouth', '#913D45', [('rounded', (42, 43, 54, 46))], parent='head'),
    ]
    if variant in ('overlap', 'accessories'):
        parts = [p for p in parts if p['id'] != 'anatomical-left-arm']
        parts.append(layer('anatomical-left-arm', 'anatomy/arm', '#E9AB78', [('polygon', [(68, 50), (81, 53), (63, 76), (35, 74), (36, 63), (60, 64)])],
                           parent='torso', side='left', hidden=True, confidence=.68))
    if variant == 'overlap':
        parts.append(layer('held-or-attached-object', 'accessory/uncertain', '#4F8CAA', [('ellipse', (29, 62, 45, 77))],
                           parent='anatomical-left-arm', confidence=.35, hidden=True))
    if variant == 'accessories':
        parts.extend([
            layer('hat', 'clothing/hat', '#466889', [('polygon', [(28, 24), (32, 5), (63, 5), (68, 24)]), ('rounded', (18, 20, 78, 27))], parent='head'),
            layer('scarf', 'clothing/scarf', '#C0375C', [('rounded', (24, 52, 69, 60)), ('polygon', [(28, 57), (39, 57), (34, 83), (23, 79)])], parent='torso'),
            layer('badge', 'accessory/badge', '#F2D067', [('polygon', [(58, 63), (62, 68), (60, 75), (54, 74), (52, 68)])], parent='torso'),
            layer('cup', 'accessory/held-item', '#50ACAC', [('rounded', (27, 64, 39, 77)), ('ellipse', (36, 65, 44, 74))], parent='anatomical-left-arm'),
        ])
    if variant == 'alpha':
        # Fractional alpha is deliberately original artwork, not segmentation fuzz.
        parts.insert(0, layer('soft-outline', 'detail/translucent-outline', (79, 142, 172, 72), [('ellipse', (9, 8, 86, 107))], hidden=True))
        parts.append(layer('translucent-sparkles', 'detail/highlight', (210, 250, 255, 127), [('ellipse', (2, 17, 6, 21)), ('ellipse', (88, 74, 92, 78))], parent='head'))
    return size, parts


def _creature():
    size = (144, 112)
    layer = lambda identifier, category, color, shapes, **kwargs: _layer(size, identifier, category, color, shapes, **kwargs)
    return size, [
        layer('tail', 'anatomy/tail', '#327570', [('polygon', [(87, 61), (107, 66), (119, 53), (133, 40), (126, 72), (100, 83), (83, 73)])], parent='torso'),
        layer('far-wing', 'anatomy/wing', '#54897B', [('polygon', [(65, 59), (75, 7), (90, 23), (101, 43), (89, 37), (86, 48), (78, 43)])], parent='torso', hidden=True),
        layer('far-front-foot', 'anatomy/foot', '#286559', [('rounded', (34, 71, 46, 98))], parent='torso'),
        layer('far-rear-foot', 'anatomy/foot', '#286559', [('rounded', (82, 72, 96, 98))], parent='torso'),
        layer('torso', 'anatomy/torso', '#4DA486', [('ellipse', (30, 39, 108, 89))], hidden=True),
        layer('near-front-foot', 'anatomy/foot', '#77BD97', [('rounded', (43, 73, 56, 101))], parent='torso'),
        layer('near-rear-foot', 'anatomy/foot', '#77BD97', [('rounded', (86, 76, 101, 101))], parent='torso'),
        layer('head', 'anatomy/head', '#77BD97', [('ellipse', (12, 30, 51, 66)), ('rounded', (7, 47, 39, 66))], parent='torso', hidden=True),
        layer('horns', 'anatomy/horn', '#ECE5B3', [('polygon', [(22, 37), (16, 14), (31, 32)]), ('polygon', [(37, 33), (34, 13), (46, 36)])], parent='head'),
        layer('eye', 'face/eye', '#192E34', [('ellipse', (20, 41, 25, 47))], parent='head'),
        layer('nostril', 'face/nostril', '#24514E', [('ellipse', (10, 52, 13, 55))], parent='head'),
        layer('near-wing', 'anatomy/wing', '#B1CC9D', [('polygon', [(57, 58), (69, 21), (78, 33), (82, 53), (76, 45), (72, 54), (65, 49)])], parent='torso', hidden=True),
        # Multiple disconnected spots intentionally constitute one semantic marking.
        layer('flank-spots', 'detail/marking', '#225A59', [('ellipse', (76, 65, 82, 70)), ('ellipse', (89, 56, 94, 61)), ('ellipse', (95, 71, 101, 76))], parent='torso'),
    ]


def _pixel():
    size = (32, 40)
    layer = lambda identifier, category, color, shapes, **kwargs: _layer(size, identifier, category, color, shapes, **kwargs)
    return size, [
        layer('antenna', 'anatomy/antenna', '#FFD05B', [('rectangle', (15, 1, 16, 5))], parent='head'),
        layer('torso', 'anatomy/robot-chassis', '#507D98', [('rectangle', (8, 19, 23, 31))], hidden=True),
        layer('anatomical-right-leg', 'anatomy/leg', '#234454', [('rectangle', (9, 31, 13, 36))], parent='torso', side='right'),
        layer('anatomical-left-leg', 'anatomy/leg', '#234454', [('rectangle', (18, 31, 22, 36))], parent='torso', side='left'),
        layer('anatomical-right-arm', 'anatomy/arm', '#77A8A4', [('rectangle', (3, 20, 7, 29))], parent='torso', side='right'),
        layer('anatomical-left-arm', 'anatomy/arm', '#77A8A4', [('rectangle', (24, 20, 28, 29))], parent='torso', side='left'),
        layer('head', 'anatomy/robot-head', '#77A8A4', [('rectangle', (6, 6, 25, 18))], parent='torso', hidden=True),
        layer('eyes', 'face/eye', '#1E3346', [('rectangle', (10, 10, 12, 13)), ('rectangle', (19, 10, 21, 13))], parent='head'),
        layer('mouth', 'face/mouth', '#1E3346', [('rectangle', (12, 16, 19, 16))], parent='head'),
        layer('status-lights', 'detail/marking', '#FFD05B', [('rectangle', (11, 23, 12, 24)), ('rectangle', (19, 23, 20, 24))], parent='torso'),
        layer('badge', 'accessory/badge', '#FF6D59', [('rectangle', (15, 27, 17, 29))], parent='torso'),
    ]


def _multiple():
    size, parts = _pixel()
    canvas_size = (80, size[1] + 12)
    combined = []
    for prefix, offset in [('first', (2, 6)), ('second', (45, 6))]:
        for component in parts:
            image = Image.new('RGBA', canvas_size)
            image.paste(component['image'], offset)
            combined.append({**component, 'id': prefix + '-' + component['id'],
                             'parent': prefix + '-' + component['parent'] if component['parent'] else None,
                             'image': image})
    return canvas_size, combined


def make_fixture(destination, name='cartoon', image_format='PNG'):
    """Write a small source, independent truth masks and source-bound annotations."""
    if name not in FIXTURE_NAMES:
        raise ValueError('unknown authored fixture ' + str(name))
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    masks_dir = root / 'truth-masks'
    masks_dir.mkdir()
    if name in ('creature', 'complex'):
        size, layers = _creature()
    elif name == 'pixel':
        size, layers = _pixel()
    elif name == 'multiple':
        size, layers = _multiple()
    else:
        size, layers = _cartoon(name)
    foreground = Image.new('RGBA', size)
    for layer in layers:
        foreground = Image.alpha_composite(foreground, layer['image'])
    truth_foreground = root / 'truth-foreground.png'
    foreground.save(truth_foreground)
    image = foreground.copy()
    if name == 'complex':
        backdrop = Image.new('RGBA', size)
        for y in range(size[1]):
            for x in range(size[0]):
                backdrop.putpixel((x, y), (30 + x % 180, 45 + (x * y) % 150, 75 + (y * 3) % 170, 255))
        image = Image.alpha_composite(backdrop, image)
    image_format = image_format.upper()
    suffix = {'PNG': '.png', 'JPEG': '.jpg', 'WEBP': '.webp'}[image_format]
    source = root / ('source' + suffix)
    if image_format == 'JPEG':
        flattened = Image.new('RGB', size, '#FFFFFF')
        flattened.paste(image, mask=image.getchannel('A'))
        flattened.save(source, format='JPEG', quality=95, subsampling=0)
    else:
        image.save(source, format=image_format, **({'lossless': True, 'exact': True} if image_format == 'WEBP' else {}))
    foreground_mask = root / 'truth-foreground-mask.png'
    foreground.getchannel('A').point(lambda alpha: 255 if alpha else 0).save(foreground_mask)
    occupied = Image.new('L', size)
    components = []
    for layer_order, layer in reversed(list(enumerate(layers))):
        shape = layer['image'].getchannel('A').point(lambda alpha: 255 if alpha else 0)
        visible = ImageChops.subtract(shape, occupied)
        occupied = ImageChops.lighter(occupied, shape)
        if not visible.getbbox():
            raise AssertionError('authored fixture has an entirely hidden component: ' + layer['id'])
        mask_path = masks_dir / (layer['id'] + '.png')
        visible.save(mask_path)
        bbox = list(visible.getbbox())
        components.append({key: value for key, value in layer.items() if key != 'image'} | {
            'mask': mask_path.relative_to(root).as_posix(), 'bbox': bbox, 'z_index': layer_order,
            'pivot': [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]})
    components.reverse()
    annotation = root / 'annotation.json'
    # Hash the supplied file, not a normalized PNG or an image of its pixels.
    annotation_components = []
    for component in components:
        annotation_components.append({
            'id': component['id'], 'name': component['name'], 'category': component['category'],
            'parent_id': component['parent'], 'z_index': component['z_index'],
            'side': component['side'] or 'center', 'mask': {'path': component['mask']},
            'pivot': component['pivot'], 'attachments': [], 'confidence': component['confidence'],
            'occlusion': {'status': 'partial' if component['hidden'] else 'visible',
                          'occluded_by': [],
                          'note': 'Only authored visible pixels are assigned; hidden shape is not supplied.' if component['hidden'] else 'Authored visible fixture geometry.'},
            'notes': [FIXTURE_ORIGIN]})
    spec = {'schema_version': 1, 'source_sha256': file_hash(source),
            'author': 'Hatch Pet deterministic fixture author', 'note': FIXTURE_ORIGIN,
            'orientation': 'front' if name not in ('creature', 'complex') else 'left',
            'components': annotation_components, 'extensions': {'fixture_name': name, 'fixture': True}}
    if name == 'complex':
        spec['foreground_mask'] = {'path': foreground_mask.name}
    annotation.write_text(json.dumps(spec, indent=2) + '\n', encoding='utf-8')
    return CharacterFixture(root, source, truth_foreground, foreground_mask, annotation, components,
                            foreground, size, name)
