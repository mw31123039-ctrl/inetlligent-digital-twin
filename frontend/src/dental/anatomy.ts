import * as T from 'three'
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js'
import { teeth, toothById, type Tooth, type Appliance, type DentalView } from './model'
import { caseToothOffset, jawOffset, type DentalSimulation } from './caseModel'

/** Original, dimensionless teaching geometry. No patient-specific reconstruction. */
const enamel = () => new T.MeshPhysicalMaterial({ color: '#f1ead5', roughness: .23, metalness: 0, clearcoat: .7, clearcoatRoughness: .2, sheen: .15, sheenColor: new T.Color('#fffaf1'), side: T.DoubleSide })
const material = (color: string, roughness = .5, metalness = 0) => new T.MeshStandardMaterial({ color, roughness, metalness, side: T.DoubleSide })
function mesh(geometry: T.BufferGeometry, mat: T.Material) { return new T.Mesh(geometry, mat) }
const widths = [.29,.255,.285,.32,.34,.43,.43,.395]
const depths = [.245,.24,.29,.37,.40,.47,.47,.44]
const heights = [.59,.55,.63,.49,.47,.46,.43,.4]
export function toothPose(tooth: Tooth, opening: number) {
  const a = (tooth.position - .5) / 8 * 1.51, side = tooth.side === 'right' ? -1 : 1
  const jawScale = tooth.jaw === 'upper' ? 1 : .94
  const normal = new T.Vector3(side * 2.7 * Math.sin(a), 0, 1.55 * Math.cos(a)).normalize()
  return { position: new T.Vector3(side * 1.55 * Math.sin(a) * jawScale, tooth.jaw === 'upper' ? .62 : -.59 - opening * .95, (2.7 * Math.cos(a) - 1.3) * jawScale), yaw: Math.atan2(normal.x, normal.z), normal, sign: tooth.jaw === 'upper' ? -1 : 1 }
}
function crownGeometry(tooth: Tooth, section = false) {
  const width = widths[tooth.position - 1]!, depth = depths[tooth.position - 1]!, height = heights[tooth.position - 1]!
  const vertices: number[] = [], colors: number[] = [], indices: number[] = [], rings = 24, segments = 48
  const color = new T.Color()
  for (let j = 0; j <= rings; j++) {
    const t = j / rings
    const profile = .74 + .26 * Math.sin(t * Math.PI * .88)
    for (let i = 0; i <= segments; i++) {
      const a = (section ? Math.PI : 0) + i / segments * (section ? Math.PI : Math.PI * 2)
      const ca = Math.cos(a), sa = Math.sin(a)
      const exponent = tooth.kind === 'incisor' ? .52 : tooth.kind === 'molar' ? .63 : .83
      let x = Math.sign(ca) * Math.abs(ca) ** exponent * width * .5 * profile
      let z = Math.sign(sa) * Math.abs(sa) ** exponent * depth * .5 * profile
      let top = height
      if (tooth.kind === 'canine') { const tip = Math.max(0,(t - .65)/.35); x *= 1 - tip * .72; z *= 1 - tip * .54; top = height * (1 + .03*Math.cos(a*3)) }
      if (tooth.kind === 'incisor') { z *= 1 - .38*t; top += .012*Math.cos(a*3) }
      if (tooth.kind === 'premolar' || tooth.kind === 'molar') top += .032*Math.cos(a * (tooth.kind === 'molar' ? 4 : 2))
      vertices.push(x, t*top, z)
      color.set('#f7f0df').lerp(new T.Color('#cfb58a'), (1-t)**3*.38)
      colors.push(color.r,color.g,color.b)
    }
  }
  for (let j=0;j<rings;j++) for (let i=0;i<segments;i++) { const a=j*(segments+1)+i,b=a+segments+1;indices.push(a,b,a+1,b,b+1,a+1) }
  // Sculpt an occlusal surface with cusp peaks and a shallow central fossa.
  const boundary = rings*(segments+1), center = vertices.length/3
  vertices.push(0,height-(tooth.kind==='molar'||tooth.kind==='premolar'?.045:0),0);colors.push(1,.963,.88)
  for(let i=0;i<segments;i++) indices.push(boundary+i,boundary+i+1,center)
  const neck = vertices.length/3; vertices.push(0,0,0); colors.push(.85,.77,.62)
  for(let i=0;i<segments;i++)indices.push(i+1,i,neck)
  const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.Float32BufferAttribute(vertices,3));geometry.setAttribute('color',new T.Float32BufferAttribute(colors,3));geometry.setIndex(indices);geometry.computeVertexNormals()
  return geometry
}
function tube(points: T.Vector3[], radius: number, mat: T.Material, segments = 60) { return mesh(new T.TubeGeometry(new T.CatmullRomCurve3(points),segments,radius,7,false),mat) }
function toothBody(tooth: Tooth, section: boolean) {
  const group = new T.Group(), mat=enamel(); mat.vertexColors=true
  const crown=mesh(crownGeometry(tooth,section),mat);crown.name='enamel';group.add(crown)
  if (!section && (tooth.kind === 'molar' || tooth.kind === 'premolar')) {
    const w=widths[tooth.position-1]!,d=depths[tooth.position-1]!,h=heights[tooth.position-1]!
    const fissure=tube([new T.Vector3(-w*.28,h+.004,d*.08),new T.Vector3(-w*.09,h-.025,0),new T.Vector3(w*.13,h-.023,-d*.06),new T.Vector3(w*.29,h,d*.1)],.0035,material('#bda684'),16)
    group.add(fissure)
  }
  if (section) {
    const dentin=mesh(crownGeometry(tooth,true),material('#d6b978'));dentin.name='dentin';dentin.scale.set(.83,.9,.81);dentin.position.z=-.003;group.add(dentin)
    const pulp=mesh(new T.SphereGeometry(1,24,16),material('#c76469'));pulp.name='pulp';pulp.scale.set(.045,.15,.035);pulp.position.set(0,.19,.003);group.add(pulp)
    const roots=tooth.roots
    for(let i=0;i<roots;i++){
      const x=(i-(roots-1)/2)*.11
      const root=mesh(new T.ConeGeometry(.065,.75,20,1,false,Math.PI/2,Math.PI),material('#d5bd8e'));root.name='root';root.position.set(x,-.34,0);root.rotation.z=Math.PI+(i-(roots-1)/2)*.17;group.add(root)
      const canal=tube([new T.Vector3(0,.18,.004),new T.Vector3(x,-.12,.008),new T.Vector3(x*1.28,-.65,.012)],.009,material('#b8505c'),20);canal.name='pulp';group.add(canal)
    }
  }
  group.traverse(o=>{o.userData.toothFdi=tooth.fdi})
  return group
}
function bracket(appliance: Appliance, color: string) {
  const group=new T.Group(),metal=material(appliance==='ceramic'?'#e9e7df':'#9caeb7',appliance==='ceramic'?.23:.2,appliance==='ceramic'?.08:.9)
  const base=mesh(new RoundedBoxGeometry(.18,.15,.045,3,.015),metal);group.add(base)
  for(const x of [-.058,.058])for(const y of [-.04,.04]){const wing=mesh(new RoundedBoxGeometry(.058,.046,.055,2,.011),metal);wing.position.set(x,y,.026);group.add(wing)}
  const slot=mesh(new T.BoxGeometry(.145,.021,.015),material('#34434a',.3,.8));slot.position.z=.055;group.add(slot)
  const elastic=mesh(new T.TorusGeometry(.066,.011,8,28),material(color,.4));elastic.scale.y=.83;elastic.position.z=.062;group.add(elastic)
  return group
}
function gingiva(jaw: 'upper'|'lower',opening: number) {
  const vertices:number[]=[],indices:number[]=[],uSteps=96,vSteps=18,ys=jaw==='upper'?.77:-.75-opening*.95,scale=jaw==='upper'?1:.94
  for(let i=0;i<=uSteps;i++){
    const a=-1.55+i/uSteps*3.1,nx=2.7*Math.sin(a),nz=1.55*Math.cos(a),l=Math.hypot(nx,nz)
    for(let j=0;j<=vSteps;j++){const b=j/vSteps*Math.PI*2;vertices.push(1.55*Math.sin(a)*scale+nx/l*Math.cos(b)*.205,ys+Math.sin(b)*.20,(2.7*Math.cos(a)-1.3)*scale+nz/l*Math.cos(b)*.205)}
  }
  for(let i=0;i<uSteps;i++)for(let j=0;j<vSteps;j++){const a=i*(vSteps+1)+j,b=a+vSteps+1;indices.push(a,b,a+1,a+1,b,b+1)}
  const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.Float32BufferAttribute(vertices,3));geometry.setIndex(indices);geometry.computeVertexNormals()
  const gum=mesh(geometry,new T.MeshPhysicalMaterial({color:'#c77e87',roughness:.43,clearcoat:.18,side:T.DoubleSide}));gum.name=`gingiva-${jaw}`;gum.userData.pickThrough=true;return gum
}
export function buildDentalAtlas(options: { view: DentalView; selected: number; appliance: Appliance; elastic: string; opening: number; simulation?: DentalSimulation }) {
  const {view,selected,appliance,elastic,opening,simulation}=options,group=new T.Group();group.name='original-permanent-tooth-atlas'
  function displayPose(t: Tooth) {
    const pose=toothPose(t,opening),delta=caseToothOffset(t,simulation),jaw=jawOffset(t.jaw,simulation)
    pose.position.add(new T.Vector3(delta.x+jaw.x,delta.y+jaw.y,delta.z+jaw.z));pose.yaw+=T.MathUtils.degToRad(delta.rotation)
    return {...pose,hidden:delta.hidden}
  }
  if(view==='section'){
    const t=toothById(selected)!;const tooth=toothBody(t,true);tooth.scale.setScalar(3.1);tooth.position.y=.05;tooth.rotation.y=-.2;group.add(tooth);return group
  }
  for(const jaw of ['upper','lower'] as const){
    if(view==='upper'&&jaw==='lower'||view==='lower'&&jaw==='upper')continue
    const gum=gingiva(jaw,opening),shift=jawOffset(jaw,simulation);gum.position.set(shift.x,shift.y,shift.z);group.add(gum)
    const arch=teeth.filter(t=>t.jaw===jaw&&!caseToothOffset(t,simulation).hidden)
    for(const t of arch){
      const pose=displayPose(t),tooth=toothBody(t,false)
      tooth.name=`tooth-${t.fdi}`;tooth.position.copy(pose.position);tooth.rotation.y=pose.yaw;tooth.scale.y=pose.sign
      if(appliance!=='none'&&t.position<=6){const brace=bracket(appliance,elastic);brace.position.set(0,heights[t.position-1]!*.47,depths[t.position-1]!*.5+.03);brace.name='bracket';tooth.add(brace)}
      tooth.traverse(o=>{o.userData.toothFdi=t.fdi});group.add(tooth)
    }
    if(appliance!=='none'){
      const ordered=arch.filter(t=>t.position<=6).sort((a,b)=>displayPose(a).position.x-displayPose(b).position.x)
      const points=ordered.map(t=>{const p=displayPose(t);return p.position.clone().add(new T.Vector3(Math.sin(p.yaw),0,Math.cos(p.yaw)).multiplyScalar(depths[t.position-1]!*.5+.09)).add(new T.Vector3(0,p.sign*heights[t.position-1]!*.47,0))})
      const wire=tube(points,.012,material('#b8c7d1',.2,.94),100);wire.name=`archwire-${jaw}`;wire.userData.pickThrough=true;group.add(wire)
    }
  }
  group.updateMatrixWorld(true)
  return group
}
