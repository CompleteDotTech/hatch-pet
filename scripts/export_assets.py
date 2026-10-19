#!/usr/bin/env python3
"""Export validated-profile frames to portable local assets and an event-driven browser preview.

Export is deterministic file conversion, not acceptance, installation, or app integration.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image
from profile_spec import profile_for_run, profile_hash, indexed_frames
from compose_atlas import compose_from_frames, save_outputs
from render_animation_previews import save_preview


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_export_receipt(output_dir, profile):
    """Finalize after callers add metrics/provenance; receipts cover every exported file."""
    out = Path(output_dir)
    files = {p.relative_to(out).as_posix(): sha256(p) for p in sorted(out.rglob('*'))
             if p.is_file() and p.relative_to(out).as_posix() != 'export-receipt.json'}
    receipt = {'schema_version': 1, 'profile_sha256': profile_hash(profile),
               'files': files, 'integration_verified': False}
    (out/'export-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    return receipt


def browser_document(metadata):
    # Embedding the exported metadata supports both file:// and OBS local-file sources.
    encoded=json.dumps(metadata, separators=(',',':')).replace('<','\\u003c')
    return '''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Animation preview</title>
<style>body{font:16px system-ui;background:transparent;color:#444}main{display:grid;justify-items:center;gap:1rem}img{object-fit:contain;image-rendering:auto}label,button{margin:.25rem}body.overlay .controls{display:none}</style>
<main><img id="character" alt="Animated character"><div class="controls"><label>State <select id="state"></select></label><label><input id="still" type="checkbox"> Reduced motion</label><button id="event">Send local event</button><output id="status" aria-live="polite"></output><p id="origin"></p></div></main>
<script>
const metadata = METADATA;
const character=document.querySelector('#character'), selector=document.querySelector('#state'), still=document.querySelector('#still');
let selected=metadata.states[0], frameIndex=0, timer;
character.width=metadata.layout.cell_width; character.height=metadata.layout.cell_height;
document.querySelector('#origin').textContent=metadata.fixture?'Deterministic test fixture. Not production artwork.':'';
const preloaded=metadata.states.flatMap(state=>state.frames.map(frame=>{const img=new Image();img.src=frame.path;return img}));
const reduced=matchMedia('(prefers-reduced-motion: reduce)');still.checked=reduced.matches;
for(const state of metadata.states){const option=document.createElement('option');option.value=state.id;option.textContent=state.id;selector.append(option)}
function render(){clearTimeout(timer); const frame=selected.frames[frameIndex];character.src=still.checked?selected.static:frame.path;character.alt=selected.purpose;character.dataset.state=selected.id;character.dataset.frameIndex=String(frame.index);character.dataset.durationMs=String(frame.duration_ms);document.querySelector('#status').textContent=selected.id+' / '+frame.index;if(!still.checked)timer=setTimeout(()=>{frameIndex=(frameIndex+1)%selected.frames.length;render()},frame.duration_ms)}
function selectState(id){const state=metadata.states.find(s=>s.id===id);if(!state)return false;selected=state;selector.value=id;frameIndex=still.checked?state.static_frame:0;render();return true}
function dispatchLocalEvent(name){const id=metadata.events[name];return id?selectState(id):false}
selector.onchange=()=>selectState(selector.value);still.onchange=()=>selectState(selected.id);
reduced.addEventListener('change',event=>{still.checked=event.matches;selectState(selected.id)});
window.hatchPet={selectState,dispatchLocalEvent,metadata,get playback(){return {state:selected.id,index:frameIndex,reducedMotion:still.checked}}};
window.addEventListener('hatch-pet-event',event=>dispatchLocalEvent(event.detail));
// Local example: window.dispatchEvent(new CustomEvent('hatch-pet-event',{detail:'working'}));
let eventIndex=0;document.querySelector('#event').onclick=()=>{const names=Object.keys(metadata.events);if(names.length)dispatchLocalEvent(names[eventIndex++%names.length])};
const params=new URLSearchParams(location.search);if(params.get('overlay')==='1')document.body.classList.add('overlay');
selectState(params.get('state')||metadata.static_state);
</script></html>'''.replace('METADATA',encoded)


def export_assets(frames_root, output_dir, profile=None):
    root=Path(frames_root).resolve(); out=Path(output_dir).resolve()
    if out==root or out in root.parents or root in out.parents:
        raise ValueError('export directory and frame source must be separate trees')
    p=profile_for_run(root, profile)
    if out.exists() and any(out.iterdir()):
        raise ValueError('export destination must be empty')
    formats=p['export']['formats']
    # Validate every file before writing any output.
    inputs={s['id']:indexed_frames(root,s['id'],s['frames']) for s in p['states']}
    for files in inputs.values():
        for path in files:
            with Image.open(path) as frame:
                if frame.size != (p['layout']['cell_width'],p['layout']['cell_height']):
                    raise ValueError(f'{path}: frame dimensions differ from profile')
    out.mkdir(parents=True,exist_ok=True)
    run_manifest=root.parent/'imagegen-jobs.json'
    fixture=json.loads(run_manifest.read_text(encoding='utf-8')).get('fixture_mode',False) if run_manifest.is_file() else False
    metadata={'schema_version':1,'profile_id':p['id'],'profile_sha256':profile_hash(p),'layout':p['layout'],'events':p['events'],'static_state':p['export']['static_state'],'states':[],'fixture':fixture,'integration_verified':False,'source':'deterministic export; artwork origin is recorded in extraction provenance'}
    write_frames='frames' in formats or 'browser' in formats
    for state in p['states']:
        frames=[]; records=[]
        for index,path in enumerate(inputs[state['id']]):
            with Image.open(path) as opened:
                frame=opened.convert('RGBA');frames.append(frame)
                relative=f'frames/{state["id"]}/{index:02d}.png'
                if write_frames:
                    target=out/relative;target.parent.mkdir(parents=True,exist_ok=True);frame.save(target)
                records.append({'index':index,'path':relative if write_frames else None,'duration_ms':state['durations'][index],'source_sha256':sha256(path),'column':index})
        static_frame=p['export']['static_frame'] if state['id']==p['export']['static_state'] else 0
        records_state={'id':state['id'],'purpose':state['purpose'],'row':len(metadata['states']),'frames':records,'static_frame':static_frame,'alignment':state['alignment']}
        if 'gif' in formats:
            relative=f'animations/{state["id"]}.gif';save_preview(frames,state['durations'],out/relative);records_state['gif']=relative
        if 'webp' in formats:
            target=out/'animations'/f'{state["id"]}.webp';target.parent.mkdir(parents=True,exist_ok=True)
            frames[0].save(target,format='WEBP',save_all=True,append_images=frames[1:],duration=state['durations'],loop=0,lossless=True,exact=True)
            records_state['webp']=target.relative_to(out).as_posix()
        static_path=out/'static'/f'{state["id"]}.png';static_path.parent.mkdir(parents=True,exist_ok=True);frames[static_frame].save(static_path)
        records_state['static']=static_path.relative_to(out).as_posix()
        metadata['states'].append(records_state)
    if 'atlas' in formats:
        save_outputs(compose_from_frames(root,p),out/'spritesheet.png',out/'spritesheet.webp')
        metadata['atlas']={'png':'spritesheet.png','webp':'spritesheet.webp'}
    (out/'profile.json').write_text(json.dumps(p,indent=2)+'\n',encoding='utf-8')
    (out/'animation.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    if 'browser' in formats:
        (out/'preview.html').write_text(browser_document(metadata),encoding='utf-8')
    write_export_receipt(out,p)
    return metadata


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames-root',required=True);parser.add_argument('--output-dir',required=True);parser.add_argument('--profile')
    args=parser.parse_args(); result=export_assets(args.frames_root,args.output_dir,args.profile)
    print(json.dumps({'ok':True,'profile_id':result['profile_id'],'output_dir':str(Path(args.output_dir).resolve()),'integration_verified':False},indent=2))

if __name__=='__main__':
    main()
