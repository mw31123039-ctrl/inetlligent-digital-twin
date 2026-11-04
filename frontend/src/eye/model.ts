import * as T from 'three'
import { structures } from './content'
import type { EyeStructure, EyeView } from './types'
import { naturalEyeStructures } from './naturalEye'

export const eyeColors:Record<string,string>={surface:'#ce8f8c',tears:'#65c6ce',cornea:'#91d5df',coats:'#eee1ca',focus:'#58a6a3',fluid:'#65cce8',vitreous:'#a4d4de',retina:'#d37d65',nerve:'#e8c884',orbit:'#d9b4a0'}
export const nasalDirection=(side:'left'|'right')=>side==='left'?-1:1
export function anatomicalPosition(structure:EyeStructure,side:'left'|'right'):T.Vector3 {
 return new T.Vector3(structure.position[0]!*nasalDirection(side),structure.position[1],structure.position[2])
}
export function viewShows(structure:EyeStructure,view:EyeView){
 if(structure.shape==='micro')return view===(structure.group==='cornea'?'corneal-detail':'retinal-detail')
 if(view==='corneal-detail')return ['cornea','limbus'].some(id=>structure.id===`eye.${id}`)
 if(view==='retinal-detail')return ['retina','macula','fovea'].some(id=>structure.id===`eye.${id}`)
 if(view==='external')return ['surface','tears'].includes(structure.group)||['eye.cornea','eye.limbus','eye.iris','eye.pupil','eye.sclera'].includes(structure.id)
 if(view==='posterior')return ['retina','nerve'].includes(structure.group)
 if(view==='section')return !['surface','orbit'].includes(structure.group)
 return true
}
function mat(color:string,opacity=1){return new T.MeshStandardMaterial({color,roughness:.5,metalness:.02,side:T.DoubleSide,transparent:opacity<1,opacity,depthWrite:opacity>.7})}
function line(points:T.Vector3[],radius:number,material:T.Material){return new T.Mesh(new T.TubeGeometry(new T.CatmullRomCurve3(points),24,radius,6,false),material)}
function mesh(geometry:T.BufferGeometry,material:T.Material){return new T.Mesh(geometry,material)}
function body(structure:EyeStructure,view:EyeView){
 const g=new T.Group(),s=structure.scale,color=eyeColors[structure.group]!,material=mat(color)
 const sphere=()=>new T.SphereGeometry(1,32,20)
 const ring=(radius:number,tube:number)=>new T.TorusGeometry(radius,tube,8,64)
 switch(structure.shape){
  case 'opening':{
   // The pupil is a real hole in the iris. Only a border and invisible hit disc are added.
   const border=mesh(ring(1,.012),mat('#284c54'));g.add(border)
   const hit=mesh(new T.CircleGeometry(1,40),new T.MeshBasicMaterial({transparent:true,opacity:0,depthWrite:false,side:T.DoubleSide}));hit.userData.annotationOnly=true;g.add(hit);break
  }
  case 'iris':{
   const iris=mesh(new T.RingGeometry(.39,1,64),mat('#438783'));g.add(iris)
   for(let i=0;i<48;i++){const a=i/48*Math.PI*2;g.add(line([new T.Vector3(Math.cos(a)*.42,Math.sin(a)*.42,.01),new T.Vector3(Math.cos(a)*.96,Math.sin(a)*.96,.01)],.006,mat(i%2?'#8abcb0':'#244c54')))}break
  }
  case 'ring':g.add(mesh(ring(1,.065),material));break
  case 'shell':{
   const half=view==='section'?Math.PI:Math.PI*2
   const outer=mesh(new T.SphereGeometry(1,48,30,0,half,.72,Math.PI-.72),material)
   outer.rotation.x=Math.PI/2;g.add(outer);break
  }
  case 'cap':{
   const cap=mesh(new T.SphereGeometry(1,40,20,0,Math.PI*2,0,Math.PI/2),mat(color,.28));cap.rotation.x=Math.PI/2;g.add(cap);break
  }
  case 'lid':{
   const points=[];for(let i=0;i<=24;i++){const t=i/24;points.push(new T.Vector3((t-.5)*2,Math.sin(t*Math.PI)*.38,Math.sin(t*Math.PI)*.3))}
   g.add(line(points,.24,material));break
  }
  case 'lashes':{
   for(let i=0;i<20;i++){const x=-.92+i/19*1.84;g.add(line([new T.Vector3(x,0,0),new T.Vector3(x*1.04,.5,.2),new T.Vector3(x*1.1,.85,.45)],.012,mat('#353236')))}break
  }
  case 'glands':{
   for(let i=0;i<12;i++){const a=mesh(sphere(),mat('#ebbc79'));a.scale.set(.035,.8,.4);a.position.x=-.9+i/11*1.8;g.add(a)}break
  }
  case 'spokes':{
   for(let i=0;i<28;i++){const a=i/28*Math.PI*2;g.add(line([new T.Vector3(Math.cos(a)*.62,Math.sin(a)*.62,0),new T.Vector3(Math.cos(a),Math.sin(a),0)],.008,mat('#e6d5ad')))}break
  }
  case 'processes':{
   for(let i=0;i<32;i++){const a=i/32*Math.PI*2,p=mesh(sphere(),material);p.scale.set(.08,.14,.3);p.position.set(Math.cos(a),Math.sin(a),0);g.add(p)}break
  }
  case 'vessels':{
   for(let i=0;i<7;i++){const a=(i/7)*Math.PI*2;const start=new T.Vector3(0,0,0),mid=new T.Vector3(Math.cos(a)*.4,Math.sin(a)*.5,.07),end=new T.Vector3(Math.cos(a)*.9,Math.sin(a)*.85,.18);g.add(line([start,mid,end],.014,mat(i%2?'#b14e48':'#926073')))}break
  }
  case 'nerve':g.add(mesh(new T.CylinderGeometry(1,.85,2,24),material));g.children[0]!.rotation.x=Math.PI/2;break
  case 'tube':g.add(mesh(new T.CylinderGeometry(1,1,2,16),material));break
  case 'orbit':{
   const orbit=mesh(new T.TorusGeometry(1,.065,10,6),mat('#d8c6af'));g.add(orbit)
   for(let i=0;i<6;i++){const a=i/6*Math.PI*2;g.add(line([new T.Vector3(Math.cos(a),Math.sin(a),0),new T.Vector3(Math.cos(a)*.72,Math.sin(a)*.72,-.6),new T.Vector3(.2,0,-1)],.025,mat('#d8c6af')))}break
  }
  case 'oblique':g.add(line([new T.Vector3(-1,.15,-1),new T.Vector3(0,.65,0),new T.Vector3(1,-.15,1)],.18,mat('#bd7771')));break
  case 'patch':g.add(mesh(new T.SphereGeometry(1,24,12),material));break
  default:g.add(mesh(sphere(),mat(structure.shape==='muscle'?'#bd7771':color,['volume','fat'].includes(structure.shape)?.12:structure.shape==='lens'?.46:1)))
 }
 g.scale.set(s[0]!,s[1]!,s[2]!);return g
}
export function buildEyeModel(side:'left'|'right',view:EyeView){
 const group=new T.Group();group.name=`educational-eye-${side}`
 const natural=view==='external'?naturalEyeStructures(side):null
 const visible=structures.filter(s=>viewShows(s,view))
 const micro=visible.filter(s=>s.shape==='micro')
 for(const structure of visible){
  let object:T.Group
  if(natural?.has(structure.id)){
   object=natural.get(structure.id)!
  }else if(structure.shape==='micro'){
   object=new T.Group()
   const index=micro.indexOf(structure),height=structure.id==='eye.corneal-stroma'?.55:.16
   const layer=mesh(new T.BoxGeometry(2.15,height,.65),mat(['#a8dce5','#dfc597','#e8dbbe','#87bdb9','#577e8d'][index%5]!))
   object.add(layer);object.position.set(0,.75-index*.4,0)
   if(structure.id==='eye.photoreceptors')for(let i=0;i<18;i++){const rod=mesh(new T.CylinderGeometry(.025,.025,.45,8),mat(i%3?'#86b8a6':'#d29f75'));rod.position.set(-.95+i*.11,.29,0);object.add(rod)}
  }else{
   object=body(structure,view);object.position.copy(anatomicalPosition(structure,side))
   if(['corneal-detail','retinal-detail'].includes(view)){object.scale.multiplyScalar(.6);object.position.set(1.65,-.6-(visible.filter(s=>s.shape!=='micro').indexOf(structure))*.45,0)}
   if(view==='exploded'){
    const index=['surface','tears','cornea','fluid','focus','vitreous','coats','retina','nerve','orbit'].indexOf(structure.group)
    object.position.z+=(4-index)*.34
   }
  }
  object.name=structure.id;object.userData.anatomyId=structure.id;object.userData.group=structure.group
  if(natural&&!object.userData.natural)object.userData.naturalHidden=true
  object.traverse(child=>{child.userData.anatomyId=structure.id})
  // Reflect nasal and temporal paths, including vessel branches, rather than changing labels with the camera.
  if(['vessels','oblique'].includes(structure.shape))object.scale.x*=nasalDirection(side)
  group.add(object)
 }
 return group
}
