<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as T from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'
import { STLLoader } from 'three/addons/loaders/STLLoader.js'
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { disposeScene } from '../three/disposeScene'
import { buildDentalAtlas } from './anatomy'
import type { Appliance, DentalScan, DentalView } from './model'
import type { DentalSimulation } from './caseModel'
const props=withDefaults(defineProps<{ view: DentalView; selected: number; structure?:string; appliance: Appliance; elastic: string; opening: number; reducedMotion: boolean; scan: DentalScan | null; simulation?: DentalSimulation }>(),{structure:'all'})
const emit=defineEmits<{ select: [id:number]; error: [message:string]; ready: [] }>()
const host=ref<HTMLDivElement>(),busy=ref(true)
let scene:T.Scene,camera:T.PerspectiveCamera,renderer:T.WebGLRenderer,controls:OrbitControls,model:T.Group|undefined,environment:T.WebGLRenderTarget|undefined,observer:ResizeObserver,visibility:IntersectionObserver
let frame=0,generation=0,disposed=false,active=true,down={x:0,y:0},errorSent=false
const ray=new T.Raycaster(),pointer=new T.Vector2()
function reset(){if(!camera)return;const scan=!!props.scan;camera.position.set(props.view==='side'?6.6:props.view==='section'?1.9:0,props.view==='upper'?-6:props.view==='lower'?6:scan?.5:.65,props.view==='upper'||props.view==='lower'?.8:props.view==='side'?.2:props.view==='section'?7.4:scan?7.2:5.8);controls.target.set(0,props.view==='section'?-.23:scan?0:-.12,scan?0:.05);camera.zoom=1;camera.updateProjectionMatrix();controls.update()}
function zoom(delta:number){if(!camera)return;camera.position.sub(controls.target).multiplyScalar(delta>0?.83:1.2).clampLength(2,14).add(controls.target);controls.update()}
function rotate(delta:number){if(!camera)return;const s=new T.Spherical().setFromVector3(camera.position.clone().sub(controls.target));s.theta+=delta;camera.position.copy(controls.target).add(new T.Vector3().setFromSpherical(s));controls.update()}
function orient(axis:'x'|'y'|'z'){if(model&&props.scan){model.rotation[axis]+=Math.PI/2;reset()}}
function highlight(){model?.traverse(o=>{if(o instanceof T.Mesh&&o.material instanceof T.MeshStandardMaterial){const selected=!props.scan&&o.userData.toothFdi===props.selected&&(props.view!=='section'||props.structure==='all'||o.name===props.structure);o.material.emissive.set(selected?'#148c86':'#000000');o.material.emissiveIntensity=selected?.17:0}})}
async function loadScan(scan:DentalScan){
 const group=new T.Group();group.name='local-unsegmented-dental-scan'
 try{
  for(const part of scan.parts){
   let object:T.Object3D
   if(part.format==='stl'){
    const geometry=new STLLoader().parse(part.bytes);if(!geometry.getAttribute('position')?.count)throw new Error('STL has no surface geometry.');geometry.computeVertexNormals();object=new T.Mesh(geometry,new T.MeshPhysicalMaterial({color:'#ded3bc',roughness:.4,clearcoat:.12,side:T.DoubleSide}))
   }else if(part.format==='obj')object=new OBJLoader().parse(new TextDecoder().decode(part.bytes))
   else{
    const manager=new T.LoadingManager();manager.setURLModifier(url=>{if(url.startsWith('data:')||url.startsWith('blob:'))return url;throw new Error('Use a self-contained GLB. External resource URLs are disabled.')})
    object=(await new GLTFLoader(manager).parseAsync(part.bytes,'')).scene
   }
   object.name=part.name
   let vertices=0;object.traverse(o=>{if(o instanceof T.Mesh)vertices+=o.geometry.getAttribute('position')?.count??0})
   if(!vertices||vertices>3000000){disposeScene(object);throw new Error('Scan needs 1–3,000,000 mesh vertices.')}
   group.add(object)
  }
  group.updateMatrixWorld(true);const bounds=new T.Box3().setFromObject(group),size=bounds.getSize(new T.Vector3()),center=bounds.getCenter(new T.Vector3()),extent=Math.max(size.x,size.y,size.z)
  if(!Number.isFinite(extent)||extent<1e-6)throw new Error('Scan has invalid dimensions.')
  // Shared transform preserves the source relationship of an upper/lower pair.
  for(const child of group.children)child.position.sub(center)
  group.scale.setScalar(4.3/extent);group.updateMatrixWorld(true);return group
 }catch(error){disposeScene(group);throw error}
}
async function rebuild(resetCamera=true){
 if(!scene)return;const version=++generation;busy.value=true
 try{
  const next=props.scan?await loadScan(props.scan):buildDentalAtlas(props)
  if(disposed||version!==generation){disposeScene(next);return}
  if(model){scene.remove(model);disposeScene(model)}model=next;scene.add(model);highlight();if(resetCamera)reset();busy.value=false;errorSent=false;emit('ready')
 }catch(e){if(!disposed&&version===generation){if(model){scene.remove(model);disposeScene(model);model=undefined}busy.value=false;emit('error',e instanceof Error?e.message:'The model could not be opened.')}}
}
function select(event:PointerEvent){if(!renderer||props.scan||!model||Math.hypot(event.clientX-down.x,event.clientY-down.y)>6)return;const rect=renderer.domElement.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);scene.updateMatrixWorld(true);ray.setFromCamera(pointer,camera);const hit=ray.intersectObject(model,true).find(h=>h.object.userData.toothFdi&&!h.object.userData.pickThrough);if(hit)emit('select',hit.object.userData.toothFdi)}
function key(event:KeyboardEvent){if(['ArrowLeft','ArrowRight','Home','r','+','=','-'].includes(event.key)){event.preventDefault();if(event.key==='ArrowLeft'||event.key==='ArrowRight')rotate(event.key==='ArrowLeft'?-.2:.2);else if(['Home','r'].includes(event.key))reset();else zoom(event.key==='-'?-1:1)}}
function lost(event:Event){event.preventDefault();if(!errorSent){errorSent=true;emit('error','The graphics connection was lost. Retry the viewer or use the tooth chart.')}}
function tick(){if(disposed)return;if(active&&!document.hidden){controls.update();renderer.render(scene,camera)}frame=requestAnimationFrame(tick)}
onMounted(()=>{try{
 scene=new T.Scene();camera=new T.PerspectiveCamera(38,1,.03,80);renderer=new T.WebGLRenderer({alpha:true,antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.65));renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.08
 renderer.domElement.addEventListener('webglcontextlost',lost);host.value!.appendChild(renderer.domElement)
 const pmrem=new T.PMREMGenerator(renderer),room=new RoomEnvironment();environment=pmrem.fromScene(room,.04);scene.environment=environment.texture;scene.environmentIntensity=.65;room.dispose();pmrem.dispose()
 scene.add(new T.HemisphereLight('#fffcf5','#718e8c',2));const keyLight=new T.DirectionalLight('#fff7e8',3.1);keyLight.position.set(-3,5,5);scene.add(keyLight);const fill=new T.DirectionalLight('#d3eff4',1.4);fill.position.set(4,1,-2);scene.add(fill)
 controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=!props.reducedMotion;controls.dampingFactor=.1;controls.minDistance=2;controls.maxDistance=14;controls.maxPolarAngle=Math.PI-.05;controls.minPolarAngle=.05;controls.enablePan=true
 observer=new ResizeObserver(()=>{const r=host.value!.getBoundingClientRect();if(r.width&&r.height){camera.aspect=r.width/r.height;camera.updateProjectionMatrix();renderer.setSize(r.width,r.height)}});observer.observe(host.value!)
 visibility=new IntersectionObserver(entries=>{active=entries.some(e=>e.isIntersecting)});visibility.observe(host.value!)
 void rebuild();tick()
}catch(e){busy.value=false;emit('error',e instanceof Error?e.message:'3D graphics are unavailable.')}})
watch(()=>[props.view,props.scan?.id],()=>void rebuild())
watch(()=>[props.appliance,props.elastic,props.opening],()=>{if(!props.scan)void rebuild(false)})
watch(()=>props.simulation,()=>{if(!props.scan)void rebuild(false)},{deep:true})
watch(()=>props.selected,()=>{if(props.view==='section')void rebuild(false);else highlight()})
watch(()=>props.structure,highlight)
watch(()=>props.reducedMotion,value=>{if(controls)controls.enableDamping=!value})
onBeforeUnmount(()=>{disposed=true;generation++;cancelAnimationFrame(frame);observer?.disconnect();visibility?.disconnect();controls?.dispose();if(scene){disposeScene(scene);scene.clear()}environment?.dispose();renderer?.domElement.removeEventListener('webglcontextlost',lost);renderer?.dispose();renderer?.forceContextLoss();renderer?.domElement.remove()})
defineExpose({reset,zoom,orient,getSnapshot:()=>({selected:props.selected,view:props.view,scan:props.scan?.id??null,teeth:model?.children.filter(o=>o.name.startsWith('tooth-')).length??0,brackets:model?(()=>{let n=0;model!.traverse(o=>{if(o.name==='bracket')n++});return n})():0,camera:camera?.position.toArray(),busy:busy.value})})
</script>
<template><div ref="host" class="dental-canvas" tabindex="0" role="group" :aria-busy="busy" :aria-label="scan?'Interactive dental scan. Drag to rotate; scroll to zoom. Arrow keys rotate and Home resets.':'Interactive 3D tooth atlas. Click a tooth or use the numbered chart. Arrow keys rotate, plus and minus zoom, Home resets.'" @keydown="key" @pointerdown="down={x:$event.clientX,y:$event.clientY}" @pointerup="select"><span v-if="busy" class="dental-loading" role="status">Preparing dental geometry…</span></div></template>
