"""Regenerate authored, versioned rig templates (no models or inferred anatomy)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from rig_contracts import validate_contract

ROOT = Path(__file__).resolve().parents[1]/'rig-templates'


def build_templates():
    def base(name, description, bounds, extends=(), pose='stance'):
        return dict(schema_version=1, kind='hatch-3d-rig-template', id=name, version='1.0.0', extends=list(extends),
                    description=description, rest_pose=pose, bones=[], constraints=[], ik=[], capabilities=[], sockets=[],
                    retarget_group=name, symmetry='explicit', rest_bounds=bounds,
                    fitting_notes='Approved 3D landmarks take precedence. Bounds and region centerlines need anatomical review.')
    def bone(t, name, parent, head, tail, *, role=None, deform=True, mirror=None):
        t['bones'].append(dict(id=name, role=role or name, parent=parent, head=head, tail=tail, deform=deform, mirror=mirror, roll=0.))
    def ball(t, name, angle=2.7):
        t['constraints'].append(dict(schema_version=1, id=name+'-limit', bone=name, type='ball', swing=angle))
    def chain(t, name, bones, pole, solver='two-bone'):
        t['ik'].append(dict(schema_version=1, id=name, bones=bones, solver=solver, pole=pole, tolerance=1e-5, iterations=64))
    def socket(t, name, bone_id, offset, role):
        t['sockets'].append(dict(schema_version=1, id=name, bone=bone_id,
            transform=dict(translation=offset, rotation=[0., 0., 0., 1.], scale=[1., 1., 1.]), role=role, owner='character'))
    custom = base('custom', 'An extensible root for explicitly authored arbitrary branching anatomy.', [[-1, 0, -1], [1, 2, 1]], pose='custom')
    bone(custom, 'root', None, [0, 0, 0], [0, .1, 0], deform=False)
    humanoid = base('humanoid', 'A stylized A-pose biped with optional articulated fingers, face joints and four limb IK chains.', [[-.85, 0, -.35], [.85, 2.05, .35]], ['custom'], 'A')
    bone(humanoid, 'pelvis', 'root', [0, .93, 0], [0, 1.13, 0])
    bone(humanoid, 'spine', 'pelvis', [0, 1.08, 0], [0, 1.31, 0])
    bone(humanoid, 'chest', 'spine', [0, 1.31, 0], [0, 1.49, 0])
    bone(humanoid, 'neck', 'chest', [0, 1.49, 0], [0, 1.63, 0])
    bone(humanoid, 'head', 'neck', [0, 1.63, 0], [0, 1.94, 0])
    bone(humanoid, 'jaw', 'head', [0, 1.66, .18], [0, 1.6, .25])
    for side, sign, other in [('left', -1, 'right'), ('right', 1, 'left')]:
        def b(name, parent, head, tail):
            bone(humanoid, name+'.'+side, parent+'.'+side if parent in ('clavicle', 'upper-arm', 'forearm', 'hand', 'thigh', 'shin', 'foot') else parent,
                 [sign*head[0], head[1], head[2]], [sign*tail[0], tail[1], tail[2]], mirror=name+'.'+other)
        b('clavicle', 'chest', [.07, 1.44, 0], [.24, 1.43, 0])
        b('upper-arm', 'clavicle', [.24, 1.43, 0], [.49, 1.17, .015])
        b('forearm', 'upper-arm', [.49, 1.17, .015], [.69, .98, .035])
        b('hand', 'forearm', [.69, .98, .035], [.76, .91, .035])
        b('thigh', 'pelvis', [.14, .93, 0], [.15, .52, .04])
        b('shin', 'thigh', [.15, .52, .04], [.15, .12, 0])
        b('foot', 'shin', [.15, .12, 0], [.15, .09, .18])
        b('toe', 'foot', [.15, .09, .18], [.15, .075, .25])
        b('eye', 'head', [.105, 1.79, .218], [.105, 1.79, .29])
        b('ear', 'head', [.245, 1.77, 0], [.30, 1.8, 0])
        for finger, z in [('thumb', -.04), ('index', -.02), ('middle', 0), ('ring', .02), ('pinky', .04)]:
            for segment in range(3):
                name=f'{finger}.{segment+1}.{side}';parent='hand.'+side if segment == 0 else f'{finger}.{segment}.{side}'
                head=[sign*(.745+segment*.028), .94-segment*.029, .035+z]
                tail=[sign*(.773+segment*.028), .911-segment*.029, .035+z]
                bone(humanoid, name, parent, head, tail, mirror=f'{finger}.{segment+1}.{other}')
                ball(humanoid, name, 1.8)
        for name in ('upper-arm', 'forearm', 'thigh', 'shin'):ball(humanoid, name+'.'+side)
        ball(humanoid, 'eye.'+side, .65)
        chain(humanoid, 'arm.'+side, ['upper-arm.'+side, 'forearm.'+side, 'hand.'+side], [sign*.65, 1.1, .8])
        chain(humanoid, 'leg.'+side, ['thigh.'+side, 'shin.'+side, 'foot.'+side], [sign*.15, .6, .8])
        socket(humanoid, 'grip.'+side, 'hand.'+side, [0, .055, 0], 'hand-grip')
    humanoid['capabilities']=['arms', 'legs', 'hands', 'fingers', 'face', 'eyes', 'mouth', 'head', 'feet']
    for name in ('spine', 'chest', 'neck', 'head'):ball(humanoid, name, .8)
    socket(humanoid, 'head-top', 'head', [0, .35, 0], 'head-accessory')
    socket(humanoid, 'back', 'chest', [0, .04, -.16], 'back-accessory')
    socket(humanoid, 'waist', 'pelvis', [0, .07, .16], 'waist-accessory')
    quadruped = base('quadruped', 'A four-legged animal with independent paws, articulated spine, jaw, eyes, ears and tail.', [[-.42, 0, -.9], [.42, 1.18, .95]], ['custom'])
    bone(quadruped, 'pelvis', 'root', [0, .72, -.35], [0, .74, -.10])
    bone(quadruped, 'spine', 'pelvis', [0, .74, -.10], [0, .77, .2])
    bone(quadruped, 'chest', 'spine', [0, .77, .2], [0, .80, .38])
    bone(quadruped, 'neck', 'chest', [0, .80, .38], [0, .96, .52])
    bone(quadruped, 'head', 'neck', [0, .96, .52], [0, 1.02, .79])
    bone(quadruped, 'jaw', 'head', [0, .87, .63], [0, .86, .85])
    for position, z in [('front', .32), ('rear', -.34)]:
        for side, sign, other in [('left', -1, 'right'), ('right', 1, 'left')]:
            suffix=position+'.'+side;mirror=position+'.'+other
            parent='chest' if position == 'front' else 'pelvis'
            bone(quadruped, 'upper-leg.'+suffix, parent, [sign*.22, .73, z], [sign*.24, .41, z+.045], mirror='upper-leg.'+mirror)
            bone(quadruped, 'lower-leg.'+suffix, 'upper-leg.'+suffix, [sign*.24, .41, z+.045], [sign*.24, .10, z], mirror='lower-leg.'+mirror)
            bone(quadruped, 'paw.'+suffix, 'lower-leg.'+suffix, [sign*.24, .10, z], [sign*.24, .065, z+.13], mirror='paw.'+mirror)
            chain(quadruped, 'leg.'+suffix, ['upper-leg.'+suffix, 'lower-leg.'+suffix, 'paw.'+suffix], [sign*.24, .4, z+.8])
            ball(quadruped, 'upper-leg.'+suffix);ball(quadruped, 'lower-leg.'+suffix)
            socket(quadruped, 'paw-socket.'+suffix, 'paw.'+suffix, [0, .06, 0], 'paw-contact')
    for i in range(4):
        bone(quadruped, f'tail.{i+1}', 'pelvis' if i == 0 else f'tail.{i}', [0, .73+i*.04, -.43-i*.13], [0, .77+i*.04, -.56-i*.13])
        ball(quadruped, f'tail.{i+1}', 1.)
    chain(quadruped, 'tail-target', ['tail.1', 'tail.2', 'tail.3', 'tail.4'], [0, 1.5, -1], 'fabrik')
    for side, sign, other in [('left', -1, 'right'), ('right', 1, 'left')]:
        bone(quadruped, 'eye.'+side, 'head', [sign*.10, 1.015, .845], [sign*.10, 1.015, .92], mirror='eye.'+other)
        bone(quadruped, 'ear.'+side, 'head', [sign*.19, 1.055, .52], [sign*.27, .89, .48], mirror='ear.'+other)
        ball(quadruped, 'eye.'+side, .65)
    quadruped['capabilities']=['legs', 'paws', 'tail', 'ears', 'eyes', 'face', 'head', 'mouth', 'quadruped']
    socket(quadruped, 'head-top', 'head', [0, .22, -.03], 'head-accessory')
    winged = base('winged-creature', 'A six-legged winged creature; inherits animal spine/tail and adds middle legs and branching articulated wings.', [[-1.2, 0, -1.1], [1.2, 1.3, .95]], ['quadruped'])
    for side, sign, other in [('left', -1, 'right'), ('right', 1, 'left')]:
        for name, parent, head, tail in [
            ('upper-leg.middle', 'spine', [.23, .73, 0], [.43, .40, .02]),
            ('lower-leg.middle', 'upper-leg.middle.'+side, [.43, .40, .02], [.49, .10, 0]),
            ('paw.middle', 'lower-leg.middle.'+side, [.49, .10, 0], [.49, .065, .13]),
            ('wing-root', 'chest', [.18, .84, .1], [.55, .91, -.06]),
            ('wing-tip', 'wing-root.'+side, [.55, .91, -.06], [1.03, 1.02, -.32])]:
            bone(winged, name+'.'+side, parent, [sign*head[0], head[1], head[2]], [sign*tail[0], tail[1], tail[2]], mirror=name+'.'+other)
            ball(winged, name+'.'+side, 1.5 if name.startswith('wing') else 2.7)
        chain(winged, 'leg.middle.'+side, ['upper-leg.middle.'+side, 'lower-leg.middle.'+side, 'paw.middle.'+side], [sign*.5, .4, .8])
        socket(winged, 'wing-socket.'+side, 'wing-root.'+side, [0, .1, 0], 'wing-accessory')
    winged['capabilities']=['wings', 'six-legs'];winged['retarget_group']='winged-creature'
    robot=base('robotic', 'Rigid articulated hinge arm with a prismatic gripper and explicit hard limits.', [[-.5, 0, -.4], [.8, 1.4, .4]], ['custom'], 'mechanical')
    for name, parent, head, tail in [('base','root',[0,.1,0],[0,.3,0]),('shoulder','base',[0,.3,0],[0,.8,0]),
        ('elbow','shoulder',[0,.8,0],[.45,.8,0]),('gripper','elbow',[.45,.8,0],[.60,.8,0]),
        ('jaw.left','gripper',[.58,.8,-.09],[.73,.8,-.09]),('jaw.right','gripper',[.58,.8,.09],[.73,.8,.09])]:
        bone(robot,name,parent,head,tail)
    for name in ('shoulder','elbow'):
        robot['constraints'].append(dict(schema_version=1,id=name+'-hinge',bone=name,type='hinge',axis=[0,0,1],minimum=-1.3,maximum=1.3))
    robot['constraints'].append(dict(schema_version=1,id='gripper-slide',bone='gripper',type='translation',axes=[1],minimum=0,maximum=.12))
    chain(robot,'robot-arm',['shoulder','elbow','gripper'],[0,0,1])
    socket(robot,'grip','gripper',[0,.15,0],'mechanical-grip')
    robot['capabilities']=['arms','gripper','rigid','prismatic'];robot['symmetry']='none'
    return {t['id']:t for t in [custom,humanoid,quadruped,winged,robot]}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    ROOT.mkdir(exist_ok=True)
    for name,template in build_templates().items():
        validate_contract(template,'RigTemplate');content=json.dumps(template,indent=2)+'\n';path=ROOT/(name+'.json')
        if args.check:
            if not path.is_file() or path.read_text('utf-8') != content:raise SystemExit('rig template drift: '+str(path))
        else:path.write_text(content,encoding='utf-8')


if __name__=='__main__':main()
