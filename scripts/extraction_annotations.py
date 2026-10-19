"""Source-bound rectangular viewports and exact component permissions, never a bypass."""
import json
import re
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw
from asset_contracts import strict_keys, text, sha, hash_object, MAX_SOURCE_PIXELS


def rectangle(value, size):
    if not isinstance(value, list) or len(value) != 4 or any(type(x) is not int for x in value):
        raise ValueError('annotation rectangles require four integer coordinates')
    x0, y0, x1, y1 = value
    if not 0 <= x0 < x1 <= size[0] or not 0 <= y0 < y1 <= size[1]:
        raise ValueError('annotation rectangle outside source or empty')
    return value


def contains(outer, inner):
    return outer[0] <= inner[0] and outer[1] <= inner[1] and outer[2] >= inner[2] and outer[3] >= inner[3]


def annotated_source(strip, count, annotation, source_hash):
    from extract_strip_frames import connected_components
    strict_keys(annotation, {'schema_version', 'source_sha256', 'author', 'note', 'frames'}, 'annotation')
    if type(annotation.get('schema_version')) is not int or annotation['schema_version'] != 1 or annotation.get('source_sha256') != source_hash or not re.fullmatch('[0-9a-f]{64}', str(source_hash)):
        raise ValueError('annotation must bind the exact source sha256 and schema_version 1')
    text(annotation.get('author'), 'annotation author')
    text(annotation.get('note'), 'annotation rationale')
    records = annotation.get('frames')
    if not isinstance(records, list) or len(records) != count:
        raise ValueError('annotation must specify exactly one rectangle for each ordered frame')
    bounds = []
    for record in records:
        strict_keys(record, {'rect', 'allow_components'}, 'annotation frame')
        bounds.append(rectangle(record.get('rect'), strip.size))
        allowed = record.get('allow_components', [])
        if not isinstance(allowed, list):
            raise ValueError('allow_components must list exact component permissions')
        for item in allowed:
            strict_keys(item, {'bounds', 'permit', 'reason'}, 'component permission')
            rectangle(item.get('bounds'), strip.size)
            if not contains(record['rect'], item['bounds']) or item.get('permit') not in ('disconnected', 'bridge'):
                raise ValueError('component permission must identify an in-frame disconnected component or bridge')
            text(item.get('reason'), 'component permission reason')
    for index, a in enumerate(bounds):
        for b in bounds[index + 1:]:
            if min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1]):
                raise ValueError('annotation frame rectangles overlap')
    components = connected_components(strip)
    for component in components:
        if sum(contains(box, component['bbox']) for box in bounds) != 1:
            raise ValueError('annotation clips, omits or ambiguously assigns a component: ' + str(component['bbox']))
    known = {tuple(c['bbox']) for c in components}
    for record in records:
        if any(tuple(item['bounds']) not in known for item in record.get('allow_components', [])):
            raise ValueError('annotation permission must match an actual complete alpha component')
    width = max(b[2] - b[0] for b in bounds)
    height = max(b[3] - b[1] for b in bounds)
    if width * height * count > MAX_SOURCE_PIXELS:
        raise ValueError('annotated normalized viewport exceeds source pixel bound')
    out = Image.new('RGBA', (width * count, height))
    overrides = {}
    for index, (record, box) in enumerate(zip(records, bounds)):
        out.paste(strip.crop(box), (index * width, 0))
        overrides[index] = []
        for item in record.get('allow_components', []):
            b = item['bounds']
            overrides[index].append({**item, 'bounds': [b[0] - box[0] + index * width,
                b[1] - box[1], b[2] - box[0] + index * width, b[3] - box[1]]})
    return out, overrides


def diagnostic(strip, count, folder, state, error, annotation=None):
    from extract_strip_frames import connected_components, atomic_json
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    thumbnail = strip.copy()
    thumbnail.thumbnail((1600, 1000), Image.Resampling.NEAREST)
    width = max(480, thumbnail.width)
    lines = textwrap.wrap(str(error), max(40, (width - 12) // 6))
    padding = 14 * (len(lines) + 2)
    preview = Image.new('RGB', (width, thumbnail.height + padding), '#eeeeee')
    preview.paste(thumbnail, (0, padding), thumbnail)
    draw = ImageDraw.Draw(preview)
    for index, line in enumerate(lines):
        draw.text((4, 4 + index * 14), line, fill='black')
    draw.text((4, padding - 16), 'Red: component bounds. Blue: default slot boundaries.', fill='black')
    sx, sy = thumbnail.width / strip.width, thumbnail.height / strip.height
    components = connected_components(strip)
    for component in components:
        x0, y0, x1, y1 = component['bbox']
        draw.rectangle((round(x0 * sx), round(y0 * sy) + padding,
                        max(round(x0 * sx), round(x1 * sx) - 1),
                        max(round(y0 * sy), round(y1 * sy) - 1) + padding), outline='red', width=1)
    for index in range(1, count):
        x = round(index * thumbnail.width / count)
        draw.line((x, padding, x, preview.height - 1), fill='blue', width=1)
    preview.save(folder / (state + '.png'))
    atomic_json(folder / (state + '.json'), {'error': str(error), 'source_size': list(strip.size), 'preview_scale': [sx, sy],
        'blue': 'default slot boundaries', 'red': 'alpha component bounds',
        'components': [{k: c[k] for k in ('bbox', 'area')} for c in components], 'annotation': annotation})
