"""Deterministic CPU triangle renderer for inspectable poses and transparent frames.

Uses real evaluated mesh vertices and a z-buffer. The portable CPU renderer uses
material base colors; the Three.js/Blender previews provide full texture shading.
"""
from __future__ import annotations
import math
import time as clock
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from rig_animation import evaluate_animation
from rig_errors import atomic_json, require, sha256
from rig_math import unit
from rig_models import rig_signature
from rig_skeleton import evaluate_fk, neutral_pose
from rig_skinning import evaluate_deformation


def render_rig_preview(rig,destination=None,*,clip=None,time=0.,pose=None,width=512,height=512,
                       camera='three-quarter',transparent=False,skeleton=False,bounds=None):
    require(type(width) is int and type(height) is int and 64<=width<=2048 and 64<=height<=2048,
            'RIG_RENDER_SIZE','Use dimensions from 64 to 2048 pixels.')
    require(camera in ('front','side','back','three-quarter'),'RIG_CAMERA','Unknown camera view.')
    if pose is None:pose=evaluate_animation(rig,clip,time)['pose'] if clip else neutral_pose(rig.skeleton)
    evaluated=evaluate_deformation(rig,pose,normals=True)
    all_points=np.concatenate([v['positions'] for v in evaluated.values()])
    if bounds is None:
        original=np.concatenate([m.positions for m in rig.geometry.meshes]);lower=np.minimum(original.min(axis=0),all_points.min(axis=0));upper=np.maximum(original.max(axis=0),all_points.max(axis=0))
    else:lower,upper=np.asarray(bounds)
    center=(lower+upper)*.5
    eye={'front':[0,0,1],'side':[1,0,0],'back':[0,0,-1],'three-quarter':[2.3,1.1,3.8]}[camera]
    forward=unit(eye);right=unit(np.cross([0,1,0],forward));up=np.cross(forward,right)
    basis=np.stack([right,up,forward],axis=1)
    corners=np.array([[x,y,z] for x in (lower[0],upper[0]) for y in (lower[1],upper[1]) for z in (lower[2],upper[2])]);view=(corners-center)@basis
    extent=np.maximum(np.ptp(view[:,:2],axis=0),.1);scale=min(width*.78/extent[0],height*.80/extent[1])
    def project(points):
        value=(np.asarray(points)-center)@basis
        return np.column_stack([width*.5+value[:,0]*scale,height*.49-value[:,1]*scale,value[:,2]])
    rgba=np.zeros((height,width,4),dtype=np.uint8)
    if not transparent:
        top=np.array([17,26,39]);bottom=np.array([32,48,63])
        rgba[:,:,:3]=(top[None,None,:]+(bottom-top)[None,None,:]*np.linspace(0,1,height)[:,None,None]).astype(np.uint8);rgba[:,:,3]=255
    depth=np.full((height,width),-np.inf,dtype=np.float32);light=unit([-1,2,3])
    for mesh in rig.geometry.meshes:
        positions=evaluated[mesh.id]['positions'];normals=evaluated[mesh.id]['normals'];screen=project(positions)
        material=rig.geometry.materials[mesh.material];base=np.array(material.get('pbrMetallicRoughness',{}).get('baseColorFactor',[.7,.7,.7,1.]))
        # glTF base colors are linear; output uses the sRGB transfer function.
        intensity=.30+.70*np.maximum(0,normals@light)
        colors=np.clip(base[:3][None,:]*intensity[:,None],0,1)
        colors=np.where(colors<=.0031308,colors*12.92,1.055*colors**(1/2.4)-.055)*255
        for triangle in mesh.triangles:
            tri=screen[triangle];x0=max(0,int(np.floor(tri[:,0].min())));x1=min(width-1,int(np.ceil(tri[:,0].max())))
            y0=max(0,int(np.floor(tri[:,1].min())));y1=min(height-1,int(np.ceil(tri[:,1].max())))
            if x1<x0 or y1<y0:continue
            a,b,c=tri;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(den)<1e-10:continue
            ys,xs=np.mgrid[y0:y1+1,x0:x1+1];xs=xs+.5;ys=ys+.5
            wa=((b[1]-c[1])*(xs-c[0])+(c[0]-b[0])*(ys-c[1]))/den
            wb=((c[1]-a[1])*(xs-c[0])+(a[0]-c[0])*(ys-c[1]))/den;wc=1-wa-wb
            z=wa*a[2]+wb*b[2]+wc*c[2];region=depth[y0:y1+1,x0:x1+1]
            mask=(wa>=-1e-7)&(wb>=-1e-7)&(wc>=-1e-7)&(z>region)
            if not np.any(mask):continue
            color=wa[:,:,None]*colors[triangle[0]]+wb[:,:,None]*colors[triangle[1]]+wc[:,:,None]*colors[triangle[2]]
            rgba[y0:y1+1,x0:x1+1,:3][mask]=np.clip(color[mask],0,255).astype(np.uint8)
            rgba[y0:y1+1,x0:x1+1,3][mask]=round(base[3]*255);region[mask]=z[mask]
    result=Image.fromarray(rgba)
    if skeleton:
        draw=ImageDraw.Draw(result);world=evaluate_fk(rig.skeleton,pose)
        for bone in rig.skeleton['bones']:
            if bone['parent']:
                p=project([world[bone['parent']][:3,3],world[bone['id']][:3,3]])
                draw.line([tuple(p[0,:2]),tuple(p[1,:2])],fill=(255,195,91,230),width=2)
    if destination:
        target=Path(destination);target.parent.mkdir(parents=True,exist_ok=True);result.save(target)
    return result


def render_pose_sheet(rig,destination,*,cell=320):
    clips=list(rig.clips);require(clips,'RIG_RENDER_ANIMATION','Pose sheet needs executable animations.')
    columns=3;rows=math.ceil(len(clips)/columns);sheet=Image.new('RGB',(columns*cell,rows*(cell+50)+76),(13,21,32))
    draw=ImageDraw.Draw(sheet)
    try:
        font=ImageFont.truetype('DejaVuSans.ttf',18);title=ImageFont.truetype('DejaVuSans.ttf',25)
    except OSError:font=title=ImageFont.load_default()
    draw.text((22,14),rig.manifest['id'].replace('-',' ').title(),font=title,fill='#f0f5f7')
    draw.text((22,48),'REAL TRIANGLE DEFORMATION  /  SYNTHETIC ENGINEERING FIXTURE',font=font,fill='#8ca8bb')
    samples=[]
    for i,name in enumerate(clips):
        t=.75 if 'blink' in name else .32 if 'wing' in name else .5 if name in ('head-turn','gaze') else .65 if name in ('walk','trot','tail-wag') else 1.
        t=min(t,rig.clips[name]['duration']);x=(i%columns)*cell;y=76+(i//columns)*(cell+50)
        picture=render_rig_preview(rig,clip=name,time=t,width=cell,height=cell)
        sheet.paste(picture.convert('RGB'),(x,y));draw.text((x+14,y+cell+10),name.replace('-',' ').title()+f'  ·  {t:.2f}s',font=font,fill='#d8e6ee')
        samples.append(dict(clip=name,time=t))
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True);sheet.save(destination)
    return dict(path=str(destination),sha256=sha256(destination),rig_sha256=rig_signature(rig.manifest),samples=samples,
                renderer='CPU z-buffer over native skinned triangles',texture_shading='base-color-only',visual_review='pending')


def render_frame_sequence(rig,destination,*,clip,fps=12,width=256,height=256,camera='three-quarter',transparent=True):
    require(clip in rig.clips,'RIG_CLIP','Unknown clip.')
    require(type(fps) is int and 1<=fps<=rig.manifest['limits']['fps'],'RIG_FRAME_RATE','Frame rate exceeds the limit.')
    destination=Path(destination);require(not destination.exists(),'RIG_RENDER_EXISTS','Use a new output directory.')
    duration=rig.clips[clip]['duration'];count=int(math.ceil(duration*fps))
    require(count*width*height*4*3+rig.geometry.vertex_count*3*8*6<=rig.manifest['limits']['memory_bytes'],
            'RIG_RENDER_BUDGET','Frame sequence exceeds its estimated processing memory budget.')
    destination.mkdir(parents=True);frames=[];images=[]
    lower=np.full(3,np.inf);upper=np.full(3,-np.inf);deadline=clock.monotonic()+rig.manifest['limits']['timeout_seconds']
    for i in range(count):
        require(clock.monotonic()<deadline,'RIG_RENDER_TIMEOUT','Frame processing exceeded its deadline.',preserved=str(destination))
        pose=evaluate_animation(rig,clip,i/fps)['pose']
        for value in evaluate_deformation(rig,pose).values():
            lower=np.minimum(lower,value['positions'].min(axis=0));upper=np.maximum(upper,value['positions'].max(axis=0))
    bounds=[lower.tolist(),upper.tolist()]
    for i in range(count):
        require(clock.monotonic()<deadline,'RIG_RENDER_TIMEOUT','Frame processing exceeded its deadline.',preserved=str(destination))
        pose=evaluate_animation(rig,clip,i/fps)['pose']
        name=f'frame-{i:04d}.png';image=render_rig_preview(rig,destination/name,pose=pose,width=width,height=height,
                                                        camera=camera,transparent=transparent,bounds=bounds)
        frames.append(dict(path=name,sha256=sha256(destination/name),time=i/fps,duration=min(1/fps,duration-i/fps)));images.append(image)
    if images:images[0].save(destination/'animation.webp',save_all=True,append_images=images[1:],duration=round(1000/fps),loop=0,lossless=True)
    report=dict(schema_version=1,kind='hatch-3d-rendered-frames',rig_sha256=rig_signature(rig.manifest),
                source_sha256=rig.manifest['source']['sha256'],fixture=rig.manifest['source']['fixture'],
                clip=clip,fps=fps,duration=duration,width=width,height=height,camera=camera,bounds=bounds,
                transparent=transparent,frames=frames,review_status='pending',
                note='Derived 2D frames retain 3D provenance; existing 2D packaging and visual review gates still apply.')
    atomic_json(destination/'frames.json',report);return report
