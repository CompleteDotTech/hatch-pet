"""Bounded print, board, stimulus, cursor and craft exporters over indexed PNG cells."""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path
import struct
import textwrap

from PIL import Image, ImageDraw, ImageFont, features
from asset_contracts import RESAMPLING, sha
from extract_strip_frames import pixels


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def records(out, metadata):
    for state in metadata['states']:
        for frame in state['frames']:
            yield state, frame, out / frame['path']


def print_cards(out, profile, metadata, flipbook=False):
    if not features.check('freetype2'):
        raise ValueError('print exports require Pillow FreeType support for legible labels')
    options = profile['export'].get('options', {})
    dpi = int(options.get('dpi', 150))
    page_size = (round(210 / 25.4 * dpi), round(297 / 25.4 * dpi))
    cell = round(options.get('cell_mm', 40) / 25.4 * dpi)
    font = ImageFont.load_default(size=max(12, round(dpi / 72 * 9)))
    heading_font = ImageFont.load_default(size=max(16, round(dpi / 72 * 12)))
    if cell * 2 + 160 > page_size[0]:
        raise ValueError('print cell_mm exceeds the supported two-column printable page')
    pages, layout = [], []
    frames = list(records(out, metadata))
    if ((len(frames) + 5) // 6) * page_size[0] * page_size[1] * 3 > 256 * 1024 * 1024:
        raise ValueError('print export exceeds 256 MiB page-buffer bound; export a smaller sequence')
    for start in range(0, len(frames), 6):
        page = Image.new('RGB', page_size, 'white')
        draw = ImageDraw.Draw(page)
        draw.text((50, 25), ('FLIPBOOK / cut, stack by number; bind left margin' if flipbook else 'STEP CARDS / ordered illustration sequence'), fill='black', font=heading_font)
        for slot, (state, frame, path) in enumerate(frames[start:start + 6]):
            col, row = slot % 2, slot // 2
            x, y = 55 + col * (page_size[0] // 2), 90 + row * ((page_size[1] - 100) // 3)
            with Image.open(path) as source:
                image = source.convert('RGBA')
            factor = cell / max(image.size)
            image = image.resize((round(image.width * factor), round(image.height * factor)), RESAMPLING[state['alignment'].get('resampling', 'lanczos')])
            page.paste(image, (x + 22, y + 20), image)
            label = options.get('labels', {}).get(state['id'], state['purpose'])
            caption = f'{start + slot + 1:03d} / {state["id"]} / frame {frame["index"]}: {label}'
            lines = textwrap.wrap(caption, max(10, int((cell + 20) / (font.size * .58))))
            for line, text in enumerate(lines[:3]):
                if line == 2 and len(lines) > 3:
                    text = text[:-3] + '...'
                draw.text((x + 10, y + cell + 35 + line * (font.size + 3)), text, fill='black', font=font)
            draw.rectangle((x, y, x + cell + 45, y + cell + 110), outline='#777777')
            if flipbook:
                draw.line((x + 15, y, x + 15, y + cell + 110), fill='#777777')
            layout.append({'order': start + slot, 'state': state['id'], 'frame': frame['index'],
                           'page': len(pages), 'cell_mm': options.get('cell_mm', 40),
                           'rendered_viewport_pixels': list(image.size), 'source_sha256': sha(path), 'label': label})
        pages.append(page)
    prefix = 'flipbook' if flipbook else 'cards'
    pages[0].save(out / (prefix + '.pdf'), save_all=True, append_images=pages[1:], resolution=dpi)
    pages[0].save(out / (prefix + '-page-1.png'))
    write_json(out / (prefix + '.json'), {'schema_version': 1, 'dpi': dpi, 'page_mm': [210, 297],
        'page_count': len(pages), 'frames': layout, 'content_review': options.get('content_review', 'Review content before use.'),
        'print_instruction': 'Print at 100%, disable fit-to-page, and verify dimensions with a ruler.'})
    if flipbook:
        first = metadata['states'][0]
        strip_width, height = cell * len(first['frames']), cell + 60
        if strip_width > 16384 or strip_width * height > 16_000_000:
            raise ValueError('zoetrope print strip exceeds supported dimensions; use fewer frames or smaller cell_mm')
        strip = Image.new('RGB', (strip_width, height), 'white')
        draw = ImageDraw.Draw(strip)
        for i, frame in enumerate(first['frames']):
            with Image.open(out / frame['path']) as source:
                image = source.convert('RGBA')
                factor = cell / max(image.size)
                image = image.resize((round(image.width * factor), round(image.height * factor)), RESAMPLING[first['alignment'].get('resampling', 'lanczos')])
            strip.paste(image, (cell * i + (cell - image.width) // 2, 60 + (cell - image.height) // 2), image)
            draw.line((cell * i + cell // 2, 0, cell * i + cell // 2, 45), fill='black', width=2)
            draw.text((cell * i + 5, 35), str(i + 1), fill='black', font=font)
        strip.save(out / 'zoetrope.png')
        strip.save(out / 'zoetrope.pdf', resolution=dpi)
        write_json(out / 'zoetrope.json', {'frame_order': [f['index'] for f in first['frames']],
            'slits': len(first['frames']), 'cell_mm': options.get('cell_mm', 40),
            'assembly': 'Print at 100%. Cut a separate slit band at the marks. Join matching ends into a cylinder; keep frames upright and ordered. Physical viewing speed needs manual adjustment.'})


def board(out, profile, metadata):
    labels = profile['export'].get('options', {}).get('labels', {})
    buttons = ''.join('<button data-state="' + html.escape(s['id']) + '" data-src="' + html.escape(s['static']) + '"><img width="96" src="' + html.escape(s['static']) + '" alt=""><span>' + html.escape(labels.get(s['id'], s['purpose'])) + '</span></button>' for s in metadata['states'])
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><title>Visual communication board</title>
<style>body{font:20px Georgia;background:#f4f1e8;color:#243c36;padding:24px}button{padding:16px;margin:10px;max-width:240px;font:inherit;background:white;border:2px solid #456}button img,button span{display:block}button:focus-visible{outline:4px solid #c63}iframe{display:block;width:100%;height:550px;border:1px solid #aaa}</style>
<h1>Visual communication board</h1><p>Local illustration example. No clinical validation is claimed. Each option has a readable description and still image.</p>
<div id="board">BUTTONS</div><p id="selection" role="status"></p><img id="static" alt="Selected static alternative"><iframe title="Selected action sequence" src="preview.html"></iframe>
<script>document.querySelectorAll('button').forEach(b=>b.onclick=()=>{document.querySelector('#selection').textContent=b.textContent;const i=document.querySelector('#static');i.src=b.dataset.src;i.alt=b.textContent;document.querySelector('iframe').src='preview.html?state='+encodeURIComponent(b.dataset.state)});</script></html>'''
    (out / 'board.html').write_text(document.replace('BUTTONS', buttons), encoding='utf-8')


def stimuli(out, profile, metadata):
    conditions = profile['export'].get('options', {}).get('conditions', {})
    with (out / 'stimuli.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['state', 'frame', 'condition', 'path', 'source_sha256', 'export_sha256', 'intended_ms', 'timing_limit'])
        writer.writeheader()
        for state, frame, path in records(out, metadata):
            writer.writerow({'state': state['id'], 'frame': frame['index'], 'condition': conditions.get(state['id'], state['id']),
                'path': frame['path'], 'source_sha256': frame['source_sha256'], 'export_sha256': sha(path),
                'intended_ms': frame['duration_ms'], 'timing_limit': 'Browser timers, refresh and visibility vary; not laboratory precision.'})
    write_json(out / 'stimuli-protocol.json', {'schema_version': 1, 'units': 'milliseconds', 'presentation_order': 'state order then frame index',
        'required_external_work': 'Experiment design, randomization, ethics/content review as appropriate, display calibration and measured frame-onset timestamps.',
        'timing': 'Intended durations only. Not measured physical display timings.'})


def premultiplied(image):
    data = bytearray()
    for red, green, blue, alpha in pixels(image.convert('RGBA')):
        data += struct.pack('<I', (alpha << 24) | (round(red * alpha / 255) << 16) | (round(green * alpha / 255) << 8) | round(blue * alpha / 255))
    return bytes(data)


def write_xcursor(path, frames, durations, hotspot):
    """Xcursor image chunks use little endian premultiplied ARGB pixels."""
    count = len(frames)
    chunks, table, offset = [], [], 16 + count * 12
    nominal = max(frames[0].size)
    for image, delay in zip(frames, durations):
        chunk = struct.pack('<9I', 36, 0xfffd0002, nominal, 1, image.width, image.height, *hotspot, delay) + premultiplied(image)
        table.append(struct.pack('<3I', 0xfffd0002, nominal, offset))
        chunks.append(chunk); offset += len(chunk)
    Path(path).write_bytes(struct.pack('<4I', 0x72756358, 16, 0x10000, count) + b''.join(table) + b''.join(chunks))


def read_xcursor(path):
    """Strict structural decoder for validation; returns stored premultiplied pixels."""
    if Path(path).stat().st_size > 64 * 1024 * 1024:
        raise ValueError('Xcursor file exceeds 64 MiB decoder bound')
    raw = Path(path).read_bytes()
    if len(raw) < 16:
        raise ValueError('truncated Xcursor header')
    magic, header, version, count = struct.unpack_from('<4I', raw)
    if (magic, header, version) != (0x72756358, 16, 0x10000) or not 1 <= count <= 64 or 16 + count * 12 > len(raw):
        raise ValueError('unsupported Xcursor header')
    result, end = [], 16 + count * 12
    for i in range(count):
        kind, nominal, offset = struct.unpack_from('<3I', raw, 16 + i * 12)
        if offset != end or offset + 36 > len(raw):
            raise ValueError('invalid Xcursor chunk offset')
        length, ctype, size, cversion, w, h, x, y, delay = struct.unpack_from('<9I', raw, offset)
        if (kind, length, ctype, size, cversion) != (0xfffd0002, 36, kind, nominal, 1) or not (0 < w <= 256 and 0 < h <= 256 and x < w and y < h and 10 <= delay <= 60000):
            raise ValueError('invalid Xcursor image chunk')
        end = offset + 36 + w * h * 4
        if end > len(raw):
            raise ValueError('truncated Xcursor pixels')
        result.append({'size': [w, h], 'hotspot': [x, y], 'duration_ms': delay, 'argb': raw[offset + 36:end]})
    if end != len(raw):
        raise ValueError('unexpected trailing Xcursor bytes')
    return result


def cursor(out, profile, metadata):
    hotspot = profile['export']['options']['hotspot']
    for state in metadata['states']:
        images = []
        for frame in state['frames']:
            with Image.open(out / frame['path']) as image:
                images.append(image.convert('RGBA'))
        path = out / (state['id'] + '.xcursor')
        durations = [f['duration_ms'] for f in state['frames']]
        write_xcursor(path, images, durations, hotspot)
        decoded = read_xcursor(path)
        if any(row['argb'] != premultiplied(image) or row['duration_ms'] != delay for row, image, delay in zip(decoded, images, durations)):
            raise ValueError('Xcursor reconstruction mismatch')
    first = metadata['states'][0]
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><title>Local animated cursor adapter</title>
<style>body{font:20px Georgia;background:#f4f1e8;padding:32px}#area{height:380px;border:2px dashed #345;position:relative;cursor:none;overflow:hidden}#cursor{position:absolute;pointer-events:none;display:none}</style>
<h1>Local cursor test surface</h1><p>Move over the surface. This adapter changes only this page. Operating system cursor settings are untouched.</p><div id="area" tabindex="0"><img id="cursor" alt="Animated pointer"></div>
<script>const frames=FRAMES,hotspot=HOTSPOT;let i=0,timer,deadline;const area=document.querySelector('#area'),cursor=document.querySelector('#cursor'),reduced=matchMedia('(prefers-reduced-motion: reduce)');function show(){cursor.src=frames[i].path}function tick(){i=(i+1)%frames.length;show();deadline+=frames[i].duration_ms;timer=setTimeout(tick,Math.max(0,deadline-performance.now()))}area.onpointerenter=()=>{clearTimeout(timer);i=0;show();cursor.style.display='block';deadline=performance.now()+frames[0].duration_ms;if(!reduced.matches)timer=setTimeout(tick,frames[0].duration_ms)};area.onpointermove=e=>{const r=area.getBoundingClientRect();cursor.style.left=(e.clientX-r.left-area.clientLeft-hotspot[0])+'px';cursor.style.top=(e.clientY-r.top-area.clientTop-hotspot[1])+'px'};function stop(){clearTimeout(timer);cursor.style.display='none'}area.onpointerleave=stop;window.onblur=stop;document.addEventListener('visibilitychange',()=>{if(document.hidden)stop()});reduced.onchange=stop;window.cursorDemo={hotspot,frames};</script></html>'''
    (out / 'cursor-demo.html').write_text(document.replace('FRAMES', json.dumps(first['frames'])).replace('HOTSPOT', json.dumps(hotspot)), encoding='utf-8')
    write_json(out / 'cursor.json', {'schema_version': 1, 'hotspot': hotspot, 'format': 'Xcursor image chunks v1',
        'alpha': 'premultiplied ARGB; partial-alpha RGB rounding is intrinsic', 'live_settings_changed': False,
        'external_requirement': 'An Xcursor-capable consumer must load the chosen state file. Windows/macOS require a separate native adapter.'})


def craft(out, profile, metadata):
    if not features.check('freetype2'):
        raise ValueError('craft print legends require Pillow FreeType support')
    palette = profile['export']['options']['palette']
    colors = [tuple(bytes.fromhex(value[1:])) for value in palette.values()]
    symbols = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ012345'
    patterns = []
    for state in metadata['states']:
        with Image.open(out / state['static']) as opened:
            image = opened.convert('RGBA')
        grid, counts = [], {name: 0 for name in palette}
        for y in range(image.height):
            row = []
            for x in range(image.width):
                red, green, blue, alpha = image.getpixel((x, y))
                if alpha < 128:
                    row.append('.'); continue
                index = min(range(len(colors)), key=lambda i: sum((a - b) ** 2 for a, b in zip(colors[i], (red, green, blue))))
                row.append(symbols[index]); counts[list(palette)[index]] += 1
            grid.append(''.join(row))
        tile = 20
        grid_font = ImageFont.load_default(size=13)
        legend_font = ImageFont.load_default(size=19)
        sheet = Image.new('RGB', (max(520, image.width * tile + 40), image.height * tile + 100 + len(palette) * 28), 'white')
        draw = ImageDraw.Draw(sheet)
        for y, row in enumerate(grid):
            for x, symbol in enumerate(row):
                if symbol != '.':
                    index = symbols.index(symbol)
                    draw.rectangle((20 + x * tile, 20 + y * tile, 20 + (x + 1) * tile, 20 + (y + 1) * tile), fill=colors[index], outline='#777777')
                    ink = 'black' if sum(colors[index]) > 380 else 'white'
                    draw.text((24 + x * tile, 22 + y * tile), symbol, fill=ink, font=grid_font)
        for i, (name, color) in enumerate(palette.items()):
            draw.text((20, 40 + image.height * tile + i * 28), f'{symbols[i]} = {name} {color} ({counts[name]} cells)', fill='black', font=legend_font)
        path = f'pattern-{state["id"]}.png'
        sheet.save(out / path)
        sheet.save(out / f'pattern-{state["id"]}.pdf', resolution=150)
        patterns.append({'state': state['id'], 'width': image.width, 'height': image.height, 'grid': grid,
                         'legend': {symbols[i]: {'name': name, 'color': palette[name]} for i, name in enumerate(palette)},
                         'counts': counts, 'preview': path, 'source_sha256': sha(out / state['static'])})
    write_json(out / 'craft.json', {'schema_version': 1, 'empty_symbol': '.', 'patterns': patterns,
        'quantization': 'Nearest palette RGB; alpha below 128 becomes empty. Review detail loss.',
        'external_requirement': 'Choose material/thread equivalents, physical pitch and construction method; test a swatch.'})


def export_extensions(out, profile, metadata):
    formats = profile['export']['formats']
    for name, function in [('cards', print_cards), ('board', board), ('stimuli', stimuli), ('cursor', cursor), ('craft', craft)]:
        if name in formats:
            function(out, profile, metadata)
    if 'flipbook' in formats:
        print_cards(out, profile, metadata, flipbook=True)
