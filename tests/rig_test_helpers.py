from copy import deepcopy
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from test_rig_math import chain_skeleton
from test_rig_skinning import test_geometry
from rig_gltf import export_geometry
from rig_jobs import create_run,save_rig
from rig_skinning import generate_skin_weights
from rig_animation import clip_from_poses
from rig_skeleton import neutral_pose,rotate_bone
from rig_math import axis_angle


def fixture(parent,*,name='fixture',animated=True):
    parent=Path(parent);geometry=test_geometry();delta=np.zeros_like(geometry.meshes[0].positions);delta[:,2]=.2
    geometry.meshes[0].morphs['blink']={'POSITION':delta}
    source=parent/(name+'.glb');export_geometry(geometry,source,provenance={'fixture':True})
    rig=create_run(source,parent/name,identifier=name);rig.manifest['skeleton']=chain_skeleton(3)
    rig.manifest['controllers']['ik']=[dict(schema_version=1,id='arm',bones=['b0','b1','b2'],solver='two-bone',pole=[0,0,1],tolerance=1e-6,iterations=32)]
    rig.manifest['facial']['expressions']={'blink':dict(schema_version=1,morphs={'blink':1.},bones={},incompatible=[])}
    rig.weights=generate_skin_weights(rig.geometry,rig.skeleton)
    if animated:
        poses=[neutral_pose(rig.skeleton),rotate_bone(rig.skeleton,neutral_pose(rig.skeleton),'b1',axis_angle([0,0,1],.8)),neutral_pose(rig.skeleton)]
        rig.clips['bend']=clip_from_poses(rig,'bend',[0.,.5,1.],poses,fps=12,loop=True)
        rig.clips['neutral']=clip_from_poses(rig,'neutral',[0.,1.],[poses[0],poses[0]],fps=12,loop=True)
    save_rig(rig,operation='test-fixture');return rig
