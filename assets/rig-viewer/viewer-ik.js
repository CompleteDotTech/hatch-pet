/* Bounded spatial editing of actual Three.js bones. Native JSON remains authoritative. */
import * as THREE from 'three';
const position=o=>o.getWorldPosition(new THREE.Vector3());
function clampLocal(node,bone,constraints){
  const rest=new THREE.Quaternion().fromArray(bone.rest.rotation),relative=rest.clone().invert().multiply(node.quaternion).normalize();
  for(const c of constraints.filter(c=>c.bone===bone.id)){
    if(c.type==='ball'){
      const angle=2*Math.acos(Math.min(1,Math.abs(relative.w)));
      if(angle>c.swing)relative.slerp(new THREE.Quaternion(),1-c.swing/angle);
    }else if(c.type==='hinge'){
      const axis=new THREE.Vector3().fromArray(c.axis).normalize();let along=relative.x*axis.x+relative.y*axis.y+relative.z*axis.z;
      let angle=2*Math.atan2(along,relative.w);while(angle>Math.PI)angle-=2*Math.PI;while(angle< -Math.PI)angle+=2*Math.PI;
      relative.setFromAxisAngle(axis,THREE.MathUtils.clamp(angle,c.minimum,c.maximum));
    }
  }
  node.quaternion.copy(rest.multiply(relative).normalize());
}
export function solveViewerIK(model,objects,rig,chain,target){
  model.updateMatrixWorld(true);const nodes=chain.bones.map(id=>objects.get(id));
  if(nodes.some(n=>!n))throw new Error('IK chain has a missing scene bone.');
  const points=nodes.map(position),root=points[0].clone(),goal=new THREE.Vector3().fromArray(target);
  const lengths=points.slice(1).map((p,i)=>p.distanceTo(points[i])),reach=lengths.reduce((a,b)=>a+b,0),distance=root.distanceTo(goal);
  const originalEndRotation=nodes.at(-1).getWorldQuaternion(new THREE.Quaternion());let iterations=1;
  if(chain.solver==='two-bone'){
    const l1=lengths[0],l2=lengths[1],direction=goal.clone().sub(root);if(direction.length()<1e-9)direction.set(0,1,0);direction.normalize();
    const d=THREE.MathUtils.clamp(distance,Math.abs(l1-l2)+1e-8,l1+l2-1e-8),a=(l1*l1-l2*l2+d*d)/(2*d),h=Math.sqrt(Math.max(0,l1*l1-a*a));
    let pole=new THREE.Vector3().fromArray(chain.pole).sub(root);pole.addScaledVector(direction,-pole.dot(direction));
    if(pole.length()<1e-8){pole=new THREE.Vector3(0,0,1);pole.addScaledVector(direction,-pole.dot(direction));}
    if(pole.length()<1e-8)pole.set(1,0,0);pole.normalize();points[1].copy(root).addScaledVector(direction,a).addScaledVector(pole,h);points[2].copy(root).addScaledVector(direction,d);
  }else{
    if(distance>=reach){const direction=goal.clone().sub(root).normalize();for(let i=1;i<points.length;i++)points[i].copy(points[i-1]).addScaledVector(direction,lengths[i-1]);}
    else for(iterations=0;iterations<Math.min(chain.iterations,128);iterations++){
      points.at(-1).copy(goal);for(let i=points.length-2;i>=0;i--){const direction=points[i].clone().sub(points[i+1]).normalize();points[i].copy(points[i+1]).addScaledVector(direction,lengths[i]);}
      points[0].copy(root);for(let i=1;i<points.length;i++){const direction=points[i].clone().sub(points[i-1]).normalize();points[i].copy(points[i-1]).addScaledVector(direction,lengths[i-1]);}
      if(points.at(-1).distanceTo(goal)<=chain.tolerance)break;
    }
  }
  const definitions=new Map(rig.skeleton.bones.map(b=>[b.id,b]));
  for(let i=0;i<nodes.length-1;i++){
    model.updateMatrixWorld(true);const from=position(nodes[i+1]).sub(position(nodes[i])).normalize(),to=points[i+1].clone().sub(points[i]).normalize();
    const delta=new THREE.Quaternion().setFromUnitVectors(from,to),world=nodes[i].getWorldQuaternion(new THREE.Quaternion());
    const parent=nodes[i].parent.getWorldQuaternion(new THREE.Quaternion());nodes[i].quaternion.copy(parent.invert().multiply(delta).multiply(world).normalize());
    clampLocal(nodes[i],definitions.get(chain.bones[i]),rig.controllers.constraints);
  }
  model.updateMatrixWorld(true);const end=nodes.at(-1),parent=end.parent.getWorldQuaternion(new THREE.Quaternion());
  end.quaternion.copy(parent.invert().multiply(originalEndRotation));model.updateMatrixWorld(true);
  const residual=position(end).distanceTo(goal);
  return {residual_m:residual,reachable:distance<=reach+1e-7,converged:residual<=Math.max(chain.tolerance,.001),iterations,
    edits:Object.fromEntries(chain.bones.map((id,i)=>[id,{translation:nodes[i].position.toArray(),rotation:nodes[i].quaternion.toArray()}])),
    constraint_support:'Ball and hinge limits; full native constraints are rechecked when the saved pose is applied.'};
}
