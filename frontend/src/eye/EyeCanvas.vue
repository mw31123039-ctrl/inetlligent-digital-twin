<script setup lang="ts">
import { onBeforeUnmount,onMounted,ref,watch } from 'vue'
import * as T from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'
import { disposeScene } from '../three/disposeScene'
import { buildEyeModel } from './model'
import type { EyeView } from './types'
const props=defineProps<{side:'left'|'right';view:EyeView;selected:string;hidden:string[];isolated:boolean;reducedMotion:boolean}>()
const emit=defineEmits<{select:[id:string];hover:[id:string];error:[]}>()
const host=ref<HTMLDivElement>()
let renderer:T.WebGLRenderer,scene:T.Scene,camera:T.PerspectiveCamera,controls:OrbitControls,model:T.Group,observer:ResizeObserver,frame=0
let environment:T.WebGLRenderTarget|undefined
let down={x:0,y:0},disposed=false
const ray=new T.Raycaster(),pointer=new T.Vector2()
function reset(){if(!camera)return;if(props.view==='external')camera.position.set(0,.025,4.9);else camera.position.set(props.view==='posterior'?0:2.2,props.view==='section'?2:1,props.view==='posterior'?-5:5);controls.target.set(0,0,props.view==='exploded'?-.15:0);camera.zoom=1;camera.updateProjectionMatrix();controls.update()}
function zoom(amount:number){if(!camera)return;camera.position.sub(controls.target).multiplyScalar(amount>0?.82:1.22).clampLength(2.1,11).add(controls.target);controls.update()}
function rotate(amount:number){if(!camera)return;const spherical=new T.Spherical().setFromVector3(camera.position.clone().sub(controls.target));spherical.theta+=amount;camera.position.copy(controls.target).add(new T.Vector3().setFromSpherical(spherical));controls.update()}
function rebuild(){if(!scene)return;if(model){scene.remove(model);disposeScene(model)}model=buildEyeModel(props.side,props.view);scene.add(model);reset();highlight()}
function highlight(){
 if(!model)return
 for(const object of model.children){
  object.visible=!props.hidden.includes(object.userData.group)&&(!props.isolated||object.name===props.selected)&&(!object.userData.naturalHidden||object.name===props.selected||props.isolated)
  object.traverse(child=>{if(child instanceof T.Mesh&&!Array.isArray(child.material)&&child.material.userData.lidMask)child.material.userData.lidMask.value=props.isolated?0:1;if(child instanceof T.Mesh&&child.material instanceof T.MeshStandardMaterial){const selected=object.name===props.selected&&props.view!=='external';child.material.emissive.set(selected?'#38b9c1':'#000000');child.material.emissiveIntensity=selected?.12:0
   const shell=['eye.sclera','eye.episclera','eye.bulbar-conjunctiva','eye.choroid','eye.retina','eye.posterior-vitreous-interface'].includes(object.name)
   if(shell&&!object.userData.natural){const opacity=props.view==='transparent'?.13:object.name==='eye.sclera'?1:.62;child.material.transparent=opacity<1;child.material.opacity=opacity;child.material.depthWrite=opacity>.7}
  }})
 }
}
function hit(event:PointerEvent){if(!renderer)return '';const rect=renderer.domElement.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);ray.setFromCamera(pointer,camera);const objects=model.children.filter(child=>child.visible);const hits=ray.intersectObjects(objects,true).filter(h=>h.object.visible);return (hits.find(h=>!h.object.userData.pickThrough)||hits[0])?.object.userData.anatomyId||''}
function move(event:PointerEvent){emit('hover',hit(event))}
function up(event:PointerEvent){if(Math.hypot(event.clientX-down.x,event.clientY-down.y)<7){const id=hit(event);if(id)emit('select',id)}}
function key(event:KeyboardEvent){if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();rotate(event.key==='ArrowLeft'?-.2:.2)}else if(['+','=','-'].includes(event.key)){event.preventDefault();zoom(event.key==='-'?-1:1)}else if(event.key==='Home'||event.key==='r'){event.preventDefault();reset()}}
function tick(){if(disposed)return;controls.update();renderer.render(scene,camera);frame=requestAnimationFrame(tick)}
function lost(event:Event){event.preventDefault();emit('error')}
function irisTextureReady(){let loaded=false;model?.getObjectByName('eye.iris')?.traverse(child=>{if(child instanceof T.Mesh&&child.material instanceof T.MeshStandardMaterial&&child.material.map?.name==='MakeHuman-CC0-reference-iris'&&child.material.map.image?.width>1)loaded=true});return loaded}
onMounted(()=>{try{
 scene=new T.Scene();camera=new T.PerspectiveCamera(38,1,.02,40);renderer=new T.WebGLRenderer({alpha:true,antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.75));renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.05
 host.value!.appendChild(renderer.domElement);renderer.domElement.addEventListener('webglcontextlost',lost)
 const pmrem=new T.PMREMGenerator(renderer),room=new RoomEnvironment();environment=pmrem.fromScene(room,.05);scene.environment=environment.texture;scene.environmentIntensity=.55;room.dispose();pmrem.dispose()
 scene.add(new T.HemisphereLight('#fff7ef','#8e8790',1.1));const light=new T.DirectionalLight('#fff3e6',2.1);light.position.set(-3,4,5);scene.add(light);const rim=new T.DirectionalLight('#dce9f0',.8);rim.position.set(3,1,-4);scene.add(rim)
 controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=!props.reducedMotion;controls.enablePan=false;controls.minDistance=2.1;controls.maxDistance=11;controls.touches.ONE=T.TOUCH.ROTATE;controls.touches.TWO=T.TOUCH.DOLLY_PAN
 observer=new ResizeObserver(()=>{if(!host.value)return;const w=host.value.clientWidth,h=host.value.clientHeight;if(!w||!h)return;camera.aspect=w/h;camera.fov=w<h?50:38;camera.updateProjectionMatrix();renderer.setSize(w,h)});observer.observe(host.value!);rebuild();tick()
 }catch{emit('error')}})
watch(()=>[props.side,props.view],rebuild)
watch(()=>[props.selected,props.hidden,props.isolated],highlight,{deep:true})
onBeforeUnmount(()=>{disposed=true;cancelAnimationFrame(frame);observer?.disconnect();controls?.dispose();if(scene){disposeScene(scene);scene.clear()}environment?.dispose();renderer?.domElement.removeEventListener('webglcontextlost',lost);renderer?.dispose();renderer?.forceContextLoss();renderer?.domElement.remove()})
defineExpose({reset,zoom,rotate,getSnapshot:()=>({side:props.side,view:props.view,structures:model?.children.map(o=>o.name),selected:props.selected,irisTextureReady:irisTextureReady(),visible:model?.children.filter(o=>o.visible).map(o=>o.name)})})
</script>
<template><div ref="host" class="eye-canvas" tabindex="0" role="group" aria-label="Interactive schematic eye. Arrow keys rotate, plus and minus zoom, Home resets. Use the anatomy list to select every structure by keyboard." @keydown="key" @pointerdown="down={x:$event.clientX,y:$event.clientY}" @pointermove="move" @pointerup="up" @pointerleave="emit('hover','')"/></template>
