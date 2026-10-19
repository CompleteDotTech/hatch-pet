"""Produce and verify all ten deterministic fixture demonstrations. No model or live app calls."""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
import re
import sys

from PIL import Image, ImageDraw
import hatch
from asset_contracts import sha
from profile_spec import load_profile
from source_interface import import_source
from extract_strip_frames import connected_components, pixels

ROOT = Path(__file__).resolve().parents[1]


def drawing(kind, state, index, count, size):
    if kind == 'craft':
        image = Image.new('RGBA', (size, size))
        colors = ['#203830', '#408060', '#D05040', '#E0B050']
        for y in range(size):
            for x in range(size):
                dx, dy = abs(x - size // 2), abs(y - size // 2)
                radius = dx + dy if state == 'diamond' else max(dx, dy) + min(dx, dy) // 2
                if radius < size // 2 - 1:
                    image.putpixel((x, y), tuple(bytes.fromhex(colors[(radius // 2) % 4][1:])) + (255,))
        return image
    if kind == 'cursor':
        image = Image.new('RGBA', (size, size)); d = ImageDraw.Draw(image)
        d.polygon([(4,4),(4,23),(9,18),(13,27),(17,25),(13,16),(21,16)], fill='#203830', outline='#e0b050')
        theta = 2 * math.pi * index / count
        x, y = round(24 + 3 * math.cos(theta)), round(7 + 3 * math.sin(theta))
        d.rectangle((x-1,y-1,x+1,y+1), fill='#d05040')
        return image
    im = Image.new('RGBA', (96,96)); d = ImageDraw.Draw(im)
    ink, blue, red, gold = '#203830', '#408090', '#D05040', '#E0B050'
    if kind == 'assembly':
        d.rectangle((18,65,78,77), fill=blue)
        top = 20 if state == 'exploded' else 38
        d.rectangle((43,top,53,66 if state != 'exploded' else 52), fill='#929a94')
        if state in ('tighten','test'):
            d.rectangle((36,33,60,40), fill=gold);d.line((40,36,56,36), fill=ink, width=2)
        else:
            d.rectangle((36,7,60,14), fill=gold)
        if state == 'test':
            d.line((67,32,72,38,85,22), fill='#408060', width=4)
    elif kind == 'process':
        d.rectangle((13,73,82,82), fill=blue)
        if state in ('condensation','rain'):
            for x,y in ((30,24),(46,18),(62,24)):
                d.ellipse((x-13,y-11,x+13,y+11), fill='#b0bbc0')
        if state == 'evaporation':
            for x in (27,48,69):
                y=54-index*5;d.line((x,65,x,y), fill=gold,width=3);d.polygon([(x,y-6),(x-5,y+2),(x+5,y+2)], fill=gold)
        if state == 'rain':
            for x in (30,48,66):
                y=40+index*7;d.line((x,y,x-3,y+8),fill=blue,width=3)
        if state == 'reservoir':
            d.line((18,70-index,77,70-index), fill='#70b8c8',width=3)
    elif kind == 'configurator':
        color={'red-glaze':red,'blue-glaze':blue,'gold-glaze':gold}[state]
        d.ellipse((57,28,84,64), fill=ink);d.ellipse((62,34,78,58),fill=(0,0,0,0))
        d.rounded_rectangle((22,23,68,77),radius=8,fill=color,outline=ink,width=3)
        d.ellipse((22,19,68,32), fill=ink);d.ellipse((27,22,63,28),fill='#dedbd1')
    elif kind == 'flipbook':
        y=round(66-42*math.sin(math.pi*index/(count-1)))
        d.ellipse((38,y-10,58,y+10),fill=red)
    elif kind == 'communication':
        if state=='drink':
            d.rectangle((26,30,63,75),fill=blue);d.arc((55,36,81,63),-90,90,fill=ink,width=5)
            d.line((36,21-index*4,36,11-index*3),fill=gold,width=3)
        elif state=='rest':
            d.rectangle((17,48,80,65),fill=blue);d.rectangle((17,30,24,78),fill=ink);d.rectangle((75,56,81,78),fill=ink);d.rectangle((28,42-index*2,43,48),fill=gold)
        else:
            d.rectangle((39,33,63,72),fill=gold);d.rectangle((44,15-index*3,50,45),fill=gold);d.rectangle((31,42,43,53),fill=gold)
    elif kind=='perception':
        level=120 if state=='low-contrast' else 230
        x=31+index*10;d.ellipse((x-10,38,x+10,58),fill=(level,level,level,255))
    elif kind=='regression':
        if state=='alpha-edge':
            d.ellipse((20,20,76,76),fill=(50,120,190,64+index*64));d.ellipse((30,30,66,66),fill=(50,120,190,255))
        elif state=='hole':
            d.ellipse((20,20,76,76),fill=gold);d.ellipse((35,35,61,61),fill=(0,0,0,0));d.rectangle((44+index,19,49+index,28),fill=red)
        elif state=='detached':
            d.rectangle((28,28,63,73),fill=blue);d.rectangle((70,12+index*4,76,18+index*4),fill=gold)
        else:
            d.rectangle((25+index*5,30,55+index*5,65),fill=(40+index*70,60,40,255))
    elif kind=='protocol':
        d.rectangle((8,34,31,61),outline=ink,width=3);d.rectangle((65,34,88,61),outline=ink,width=3)
        if state=='request':
            x=34+index*8;d.polygon([(x,43),(x+9,48),(x,53)],fill=blue)
        elif state=='ack':
            x=55-index*9;d.polygon([(x,43),(x-9,48),(x,53)],fill=gold)
        elif state=='done':d.line((39,47,46,55,58,36),fill='#408060',width=4)
        elif state=='fault':d.line((39,36,57,57),fill=red,width=4);d.line((57,36,39,57),fill=red,width=4)
    else:
        raise ValueError('unknown deterministic demonstration: ' + kind)
    return im.resize((size,size),Image.Resampling.NEAREST)


def fixture_review(root, data):
    receipt=hatch.review_template(root,data)
    receipt['reviewer']='deterministic demonstration gate exerciser; not a production art reviewer'
    receipt['evidence']={'canonical_reference_viewed':True,'contact_sheet_viewed':True,'playback_states':list(receipt['rows'])}
    for row in receipt['rows'].values():
        row.update(verdict='pass',notes='Synthetic gate exercise only. No semantic production acceptance.')
        for dim in row['dimensions'].values():dim.update(verdict='pass',notes='Fixture test exercises this explicit review dimension.')
        row['warning_notes']={w:'Fixture warning-handling test; real artwork requires a visual judgment.' for w in row['warning_notes']}
    path=root.parent/'fixture-review.json';hatch.atomic(path,receipt);hatch.review(root,data,path)


def acceptance(kind, out, profile):
    """Executable, distinct acceptance criteria; assertions fail the demonstration."""
    export=out/'export';metadata=hatch.read(export/'animation.json')
    receipt=hatch.read(export/'export-receipt.json')
    assert all(sha(export/name)==value for name,value in receipt['files'].items())
    assert metadata['fixture'] and not metadata['integration_verified']
    assert [s['id'] for s in metadata['states']]==[s['id'] for s in profile['states']]
    images={}
    for state in metadata['states']:
        images[state['id']]=[]
        for frame in state['frames']:
            with Image.open(export/frame['path']) as opened:image=opened.convert('RGBA')
            assert image.size==(profile['layout']['cell_width'],profile['layout']['cell_height']) and image.getbbox()
            images[state['id']].append(image)
    checks=['receipt hashes match all output files','fixture and integration boundaries explicit','all ordered frames decode at exact cell size']
    if kind in ('assembly','process'):
        cards=hatch.read(export/'cards.json')
        expected=sum(len(s['frames']) for s in metadata['states'])
        assert len(cards['frames'])==expected and [x['order'] for x in cards['frames']]==list(range(expected))
        pdf=(export/'cards.pdf').read_bytes()
        assert pdf.startswith(b'%PDF') and len(re.findall(rb'/Type /Page\b',pdf))==cards['page_count']
        assert cards['content_review']==profile['export']['options']['content_review']
        with Image.open(export/'cards-page-1.png') as page:
            assert sum(pixel[:3]==(64,128,144) for pixel in pixels(page))>2000, 'printed illustration is too small'
        checks+=['printable PDF page tree and card order checked','content-review requirements retained']
    elif kind=='configurator':
        variants=[values[0] for values in images.values()]
        assert len({im.getchannel('A').tobytes() for im in variants})==1
        assert len({im.tobytes() for im in variants})==3
        checks+=['identical viewpoint alpha geometry across three distinct glaze variants']
    elif kind=='flipbook':
        frames=images['bounce'];ys=[im.getbbox()[1] for im in frames]
        assert max(ys)-min(ys)>20
        assert len({sum(im.getchannel('A').histogram()[1:]) for im in frames})==1
        assert hatch.read(export/'zoetrope.json')['frame_order']==list(range(12))
        assert len(hatch.read(export/'flipbook.json')['frames'])==12
        checks+=['12 ordered print frames and slits','constant ball area and retained jump displacement']
    elif kind=='communication':
        board=(export/'board.html').read_text(encoding='utf-8')
        assert all(s['id'] in board and s['static'] in board for s in metadata['states'])
        checks+=['selectable board includes every described static alternative']
    elif kind=='perception':
        low,high=images['low-contrast'],images['high-contrast']
        assert all(a.getchannel('A').tobytes()==b.getchannel('A').tobytes() for a,b in zip(low,high))
        assert all(a.tobytes()!=b.tobytes() for a,b in zip(low,high))
        with (export/'stimuli.csv').open(encoding='utf-8') as stream:
            rows=list(csv.DictReader(stream))
        assert len(rows)==8 and len({r['condition'] for r in rows})==2
        assert all(r['timing_limit'] and sha(export/r['path'])==r['export_sha256'] for r in rows)
        checks+=['controlled geometry with distinct contrast','condition/timing/source hash table verified']
    elif kind=='regression':
        assert any(0<a<255 for a in pixels(images['alpha-edge'][0].getchannel('A')))
        assert images['hole'][0].getpixel((32,32))[3]==0
        assert len(connected_components(images['detached'][0]))==2
        for state in metadata['states']:
            with Image.open(export/state['webp']) as encoded:
                assert encoded.n_frames==len(state['frames'])
                for i,im in enumerate(images[state['id']]):
                    encoded.seek(i);assert encoded.convert('RGBA').tobytes()==im.tobytes()
        checks+=['partial alpha, actual holes and detached details survive extraction','animated lossless WebP reconstructs every pixel/frame']
    elif kind=='cursor':
        from asset_exporters import read_xcursor,premultiplied
        rows=read_xcursor(export/'busy.xcursor')
        assert len(rows)==6
        assert all(r['hotspot']==[4,4] and r['duration_ms']==80 and r['argb']==premultiplied(im) for r,im in zip(rows,images['busy']))
        checks+=['Xcursor headers, offsets, frame order, hotspots, timing and premultiplied pixels reconstruct']
    elif kind=='protocol':
        assert profile['playback']['events']['receive-ack']['from']==['request']
        assert profile['states'][2]['playback']['completion']=='done'
        assert 'hatchPet' in (export/'preview.html').read_text(encoding='utf-8')
        checks+=['legal-event contract exported; actual transitions covered by browser regression']
    elif kind=='craft':
        for pattern in hatch.read(export/'craft.json')['patterns']:
            assert len(pattern['grid'])==24 and all(len(row)==24 for row in pattern['grid'])
            symbols=''.join(pattern['grid']);assert set(symbols)<=set(pattern['legend'])|{'.'}
            assert sum(pattern['counts'].values())==sum(c!='.' for c in symbols)
        checks+=['24x24 grids, palette symbols, legends and material counts checked']
    return {'ok':True,'fixture':True,'production_artwork_accepted':False,'external_integration_verified':False,'checks':checks}


def demonstrate(kind, destination):
    catalog=hatch.read(ROOT/'presets/catalog.json')
    if kind not in catalog:raise ValueError('unknown preset; choose '+', '.join(catalog))
    out=Path(destination).resolve()/kind
    if out.exists():raise ValueError('demonstration output already exists: '+str(out))
    out.mkdir(parents=True)
    entry=catalog[kind];profile=load_profile(ROOT/'presets'/entry['profile']);size=profile['layout']['cell_width']
    root=out/'run';sources=out/'fixture-inputs';sources.mkdir()
    identity={'schema_version':1,'markings':[entry['semantics']], 'materials':['symbolic deterministic fixture'], 'forbid_mirror':True}
    hatch.atomic(out/'identity.json',identity)
    hatch.prepare(root,argparse.Namespace(replace_inputs=False,fixture_mode=True,profile=str(ROOT/'presets'/entry['profile']),
        pet_name=kind,pet_notes=entry['semantics'],description='Deterministic asset-production demonstration.',reference=[],avoid=[],require=[],brand_source=[],
        identity=str(out/'identity.json'),style_preset='pixel',style_notes='Synthetic fixture only'))
    data=hatch.manifest(root)
    first=profile['states'][0]
    base=sources/'base.png';drawing(kind,first['id'],0,first['frames'],size).save(base)
    descriptor=sources/'base-source.json'
    hatch.atomic(descriptor,{'schema_version':1,'kind':'import','layout':'image','files':['base.png'],
        'origin':'Pillow deterministic '+kind+' fixture; not imagegen output','fixture':True})
    import_source(root,data,'base',descriptor,'Fixture import validation and source-origin test.')
    hatch.record_base_review(root,data,'Synthetic canonical checkpoint; gate exercise only.',True)
    for state in profile['states']:
        paths=[]
        for index in range(state['frames']):
            path=sources/f'{state["id"]}-{index:02d}.png';drawing(kind,state['id'],index,state['frames'],size).save(path);paths.append(path.name)
        descriptor=sources/(state['id']+'-source.json')
        hatch.atomic(descriptor,{'schema_version':1,'kind':'import','layout':'frames','files':paths,
            'origin':'Ordered Pillow deterministic '+kind+' fixtures; not imagegen output','fixture':True})
        import_source(root,data,state['id'],descriptor,'Synthetic frame import; semantics need real-content review.')
        source=root/'decoded'/f'{state["id"]}.png'
        with Image.open(source) as image:components=connected_components(image.convert('RGBA'))
        frames=[]
        for index in range(state['frames']):
            box=[index*size,0,(index+1)*size,size]
            subset=[c for c in components if box[0]<=c['bbox'][0] and c['bbox'][2]<=box[2]]
            permissions=[]
            for comp in subset:
                for permit in ('disconnected','bridge'):
                    permissions.append({'bounds':list(comp['bbox']),'permit':permit,'reason':'Known synthetic fixture geometry; this exact component is intended.'})
            frames.append({'rect':box,'allow_components':permissions})
        annotation={'schema_version':1,'source_sha256':sha(source),'author':'deterministic fixture generator',
                    'note':'Explicit known fixture components; never authorizes unknown artwork.','frames':frames}
        path=sources/(state['id']+'-annotation.json');hatch.atomic(path,annotation);hatch.annotate(root,data,state['id'],path)
    hatch.validate(root,data);fixture_review(root,data)
    hatch.export(root,data,out/'export');hatch.package(root,data,out/'package')
    from review_ui import build_review
    build_review(root,data,out/'review')
    result=acceptance(kind,out,profile)
    result.update(use=entry['use'],external_consumer=entry['external_consumer'])
    hatch.atomic(out/'acceptance.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--all',action='store_true');group.add_argument('--preset')
    parser.add_argument('--output-dir',required=True)
    args=parser.parse_args()
    names=list(hatch.read(ROOT/'presets/catalog.json')) if args.all else [args.preset]
    results={name:demonstrate(name,args.output_dir) for name in names}
    print(json.dumps(results,indent=2))
