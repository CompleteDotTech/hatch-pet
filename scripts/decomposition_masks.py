"""Bounded source-space masks. Pixel geometry is deterministic; labels are supplied.

Masks express ownership, not opacity: 0/255 membership is applied once to the
source's original alpha. This avoids multiplying antialiased edges twice.
"""
from __future__ import annotations

from collections import Counter
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat

from asset_contracts import MAX_SOURCE_PIXELS, check_image, strict_keys
from extract_strip_frames import connected_components, mask_background, parse_hex_color, pixels

MAX_COMPONENTS = 128
MAX_MASK_PIXELS = 64_000_000
MAX_RUNS = 2_000_000
MAX_TOTAL_RUNS = 250_000


def binary(mask):
    return mask.convert('L').point(lambda value: 255 if value else 0)


def count(mask):
    return mask.histogram()[255]


def intersect(a, b):
    return ImageChops.multiply(a, b)


def subtract(a, b):
    return ImageChops.subtract(a, b)


def union(a, b):
    return ImageChops.lighter(a, b)


def point(value, size, label='point'):
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in value) or
            not 0 <= value[0] <= size[0] or not 0 <= value[1] <= size[1]):
        raise ValueError(label + ' must contain two finite source-canvas coordinates')
    return value


def mask_to_runs(mask, max_runs=MAX_TOTAL_RUNS):
    """Return sorted horizontal [y, x0, x1) runs; no pixel-sized JSON arrays."""
    data = mask.tobytes()
    width, height = mask.size
    runs = []
    for y in range(height):
        row = data[y * width:(y + 1) * width]
        start = None
        for x, value in enumerate(row + b'\0'):
            if value and start is None:
                start = x
            elif not value and start is not None:
                runs.append([y, start, x])
                if len(runs) > max_runs:
                    raise ValueError('decomposition aggregate mask-run resource bound exceeded; simplify masks or choose a smaller source')
                start = None
    return runs


def decode_mask(spec, size, base=None, image=None):
    """Read one exact mask, polygon union, or explicitly labeled color selection.

    A path mask is a full-canvas grayscale 0/255 PNG. Color/seed selectors are
    optional deterministic assistance; they never invent semantic labels.
    """
    if not isinstance(spec, dict) or len(spec) != 1:
        raise ValueError('mask must have exactly one of path, runs, polygons, or colors')
    width, height = size
    if width * height > MAX_SOURCE_PIXELS:
        raise ValueError('mask exceeds source pixel bound')
    out = Image.new('L', size)
    draw = ImageDraw.Draw(out)
    if 'path' in spec:
        if not isinstance(spec['path'], str) or not spec['path'].strip():
            raise ValueError('mask path must be nonempty text')
        path = Path(spec['path'])
        path = (Path(base or Path.cwd()) / path).resolve()
        if path.suffix.lower() != '.png':
            raise ValueError('ownership masks must be lossless grayscale PNG files')
        check_image(path)
        with Image.open(path) as raw:
            if raw.size != size or raw.mode not in ('1', 'L'):
                raise ValueError('mask must be full-canvas single-channel 1/L, without scaling')
            out = raw.convert('L')
        if any(out.histogram()[1:255]):
            raise ValueError('ownership masks must be binary 0/255; source alpha is preserved separately')
    elif 'runs' in spec:
        runs = spec['runs']
        if not isinstance(runs, list) or len(runs) > min(MAX_RUNS, width * height):
            raise ValueError('mask runs exceed bounded list size')
        previous = None
        for run in runs:
            if (not isinstance(run, list) or len(run) != 3 or
                    any(type(v) is not int for v in run)):
                raise ValueError('mask run requires integer [y,x0,x1]')
            y, x0, x1 = run
            if not 0 <= y < height or not 0 <= x0 < x1 <= width:
                raise ValueError('mask run lies outside the source canvas')
            if previous is not None and (y < previous[0] or (y == previous[0] and x0 < previous[2])):
                raise ValueError('mask runs must be sorted and non-overlapping')
            draw.line((x0, y, x1 - 1, y), fill=255)
            previous = run
    elif 'polygons' in spec:
        polygons = spec['polygons']
        if not isinstance(polygons, list) or not 0 < len(polygons) <= 4096:
            raise ValueError('mask polygons require 1..4096 polygons')
        total = 0
        for polygon in polygons:
            if not isinstance(polygon, list) or not 3 <= len(polygon) <= 10000:
                raise ValueError('each polygon requires 3..10000 points')
            total += len(polygon)
            if total > 100000:
                raise ValueError('polygon vertex resource bound exceeded')
            draw.polygon([tuple(point(p, size, 'polygon point')) for p in polygon], fill=255)
    elif 'colors' in spec:
        selection = spec['colors']
        strict_keys(selection, {'values', 'tolerance', 'seeds', 'within'}, 'color selection')
        if image is None:
            raise ValueError('color masks require the original source image')
        colors = selection.get('values', [])
        if not isinstance(colors, list) or not 1 <= len(colors) <= 32:
            raise ValueError('color selection needs 1..32 explicit #RRGGBB colors')
        values = [parse_hex_color(value) for value in colors]
        tolerance = selection.get('tolerance', 0)
        if type(tolerance) not in (int, float) or not math.isfinite(tolerance) or not 0 <= tolerance <= 64:
            raise ValueError('color tolerance must be finite and between 0 and 64')
        candidates = bytes(255 if p[3] and any(max(abs(p[c] - v[c]) for c in range(3)) <= tolerance
            for v in values) else 0 for p in pixels(image.convert('RGBA')))
        out = Image.frombytes('L', size, candidates)
        if 'within' in selection:
            within = decode_mask({'polygons': selection['within']}, size)
            out = intersect(out, within)
        if 'seeds' in selection:
            seeds = selection['seeds']
            if not isinstance(seeds, list) or not 1 <= len(seeds) <= 1024:
                raise ValueError('color seeds require 1..1024 source pixel points')
            seed_indices = set()
            for seed in seeds:
                point(seed, size, 'color seed')
                if any(type(v) is not int for v in seed) or seed[0] >= width or seed[1] >= height:
                    raise ValueError('color seeds must be integer pixel coordinates inside canvas')
                idx = seed[1] * width + seed[0]
                if not out.tobytes()[idx]:
                    raise ValueError('color seed does not match the selected colors')
                seed_indices.add(idx)
            rgba = Image.new('RGBA', size)
            rgba.putalpha(out)
            selected = bytearray(width * height)
            for component in connected_components(rgba):
                if seed_indices.intersection(component['pixels']):
                    for idx in component['pixels']:
                        selected[idx] = 255
            out = Image.frombytes('L', size, bytes(selected))
    else:
        raise ValueError('unsupported mask representation; use path, runs, polygons, or colors')
    return out


def apply_mask(image, mask):
    """Extract original RGBA. All four source channels survive on supported pixels."""
    result = image.convert('RGBA').copy()
    result.putalpha(ImageChops.multiply(result.getchannel('A'), mask))
    # Invisible RGB is canonical zero in derived assets, never in the archived source.
    transparent = Image.new('RGBA', image.size)
    return Image.composite(result, transparent, binary(result.getchannel('A')))


def identify_foreground(image, mode='auto', supplied=None, base=None, key=None, threshold=0):
    alpha = image.getchannel('A')
    support = binary(alpha)
    warnings = []
    if type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 <= threshold <= 64:
        raise ValueError('background key threshold must be finite and between 0 and 64')
    transparent_count = alpha.histogram()[0]
    substantial_transparency = transparent_count >= max(1, image.width * image.height * .01)
    if supplied is not None:
        mask = intersect(decode_mask(supplied, image.size, base, image), support)
        method, confidence, needs_review = 'annotated-mask', 1.0, True
    elif mode in ('alpha', 'keep') or (mode == 'auto' and substantial_transparency):
        mask = support
        method, confidence, needs_review = 'source-alpha', 1.0, False
        if mode == 'keep':
            method, confidence, needs_review = 'explicit-keep', 1.0, True
        elif alpha.getextrema()[0] == 255:
            warnings.append('Opaque alpha does not establish a character foreground; confirm or supply a mask.')
            confidence, needs_review = 0.0, True
    else:
        width, height = image.size
        rgb = image.convert('RGB')
        border = list(pixels(rgb.crop((0, 0, width, 1)))) + list(pixels(rgb.crop((0, height - 1, width, height))))
        border += list(pixels(rgb.crop((0, 0, 1, height)))) + list(pixels(rgb.crop((width - 1, 0, width, height))))
        color, occurrences = Counter(border).most_common(1)[0]
        if key is not None:
            color = parse_hex_color(key) if isinstance(key, str) else tuple(key)
        fraction = sum(max(abs(p[i] - color[i]) for i in range(3)) <= threshold for p in border) / len(border)
        if mode in ('solid', 'chroma') or (mode == 'auto' and fraction >= .98):
            # Existing edge-connected infrastructure, with color-changing cleanup disabled.
            cleaned, detail = mask_background(image, color, threshold, 'chroma', 'preserve', False)
            mask = binary(cleaned.getchannel('A'))
            method, confidence, needs_review = 'edge-connected-solid', fraction, True
            warnings.extend(detail['warnings'])
            warnings.append('Background membership is inferred; source RGB is never decontaminated or repainted.')
        else:
            mask = support
            method, confidence, needs_review = 'unresolved-complex-background', 0.0, True
            warnings.append('Complex background requires an explicit foreground mask or reviewed correction.')
    if not count(mask):
        raise ValueError('empty character foreground after background selection')
    return mask, {'method': method, 'confidence': confidence, 'review_required': needs_review, 'warnings': warnings}


def character_candidates(foreground):
    """Geometric suspicion only: disconnected regions do not prove separate characters."""
    connected = connected_components(foreground)
    if not connected:
        return []
    largest = max(c['area'] for c in connected)
    major = [c for c in connected if c['area'] >= max(4, largest * .15)]
    return [{'id': 'region-' + str(i + 1), 'bbox': list(c['bbox']), 'pixels': c['area'],
             'semantic_character': False, 'confidence': .25} for i, c in enumerate(sorted(major, key=lambda c: c['bbox'])[:128])]


def quality(image, foreground, pixel_art):
    alpha = foreground.getchannel('A')
    bbox = alpha.getbbox()
    colors = foreground.convert('RGB').getcolors(maxcolors=256)
    visible = count(binary(alpha))
    partial = sum(alpha.histogram()[1:255])
    extrema = ImageStat.Stat(foreground.convert('L'), mask=binary(alpha))
    edge = foreground.convert('L').filter(ImageFilter.FIND_EDGES)
    edge_mean = ImageStat.Stat(edge, mask=binary(alpha)).mean[0]
    warnings = []
    if min(image.size) < 32:
        warnings.append('Low-resolution source: subpixel facial or joint geometry cannot be recovered.')
    if bbox and (bbox[0] == 0 or bbox[1] == 0 or bbox[2] == image.width or bbox[3] == image.height):
        warnings.append('Foreground touches canvas boundary; inspect possible source clipping.')
    if extrema.stddev[0] < 3:
        warnings.append('Little luminance variation; semantic boundaries may need manual annotations.')
    if not pixel_art and min(image.size) >= 128 and edge_mean < 2:
        warnings.append('Low edge contrast may limit boundary accuracy; inspect source focus.')
    return {'width': image.width, 'height': image.height, 'foreground_pixels': visible,
            'partial_alpha_pixels': partial, 'foreground_bbox': list(bbox) if bbox else None,
            'unique_colors_up_to_256': len(colors) if colors is not None else '>256',
            'luminance_stddev': extrema.stddev[0], 'edge_contrast_mean': edge_mean,
            'pixel_art': pixel_art, 'resampling': 'nearest' if pixel_art else 'none',
            'source_resized': False, 'warnings': warnings}


def palette(image, limit=16):
    # Quantize only a sample for identity notes; component pixels are untouched.
    sample = image.copy()
    sample.thumbnail((256, 256), Image.Resampling.NEAREST)
    visible = [p[:3] for p in pixels(sample) if p[3] >= 128]
    if not visible:
        visible = [p[:3] for p in pixels(sample) if p[3]]
    if not visible:
        return {}
    selected = Counter(visible).most_common(limit)
    return {'source-color-' + str(i + 1): '#' + ''.join(f'{v:02X}' for v in color)
            for i, (color, _) in enumerate(selected)}
