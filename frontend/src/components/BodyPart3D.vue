<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as T from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'
import { bodyParts, partLabel, type PatientSide } from '../data/bodyParts'
import { disposeScene } from '../three/disposeScene'
import type { RegionId } from '../types'

const props = defineProps<{ part: RegionId; side: PatientSide; reducedMotion: boolean; autoRotate: boolean; variant?: 'surface' | 'vascular' }>()
const emit = defineEmits<{ ready: []; error: [message: string] }>()
const host = ref<HTMLDivElement>()
let scene: T.Scene, camera: T.PerspectiveCamera, renderer: T.WebGLRenderer, controls: OrbitControls
let model: T.Group | undefined, observer: ResizeObserver | undefined, frame = 0, generation = 0, disposed = false, failed = false
let lastTime = 0
let loadingManager: T.LoadingManager | undefined, loadTimeout = 0
let environment:T.WebGLRenderTarget|undefined
const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
const reduced = () => props.reducedMotion || preference.matches

function fail(message: string) { if (!disposed) { failed = true; cancelAnimationFrame(frame); emit('error', message) } }
function reset() {
  if (!controls) return
  controls.reset(); controls.target.set(0, 0, 0); camera.position.fromArray(bodyParts[props.part].camera); camera.zoom = 1
  camera.updateProjectionMatrix(); controls.update()
}
function zoom(delta: number) {
  if (!camera || !controls) return
  const offset = camera.position.clone().sub(controls.target)
  const distance = T.MathUtils.clamp(offset.length() * (delta > 0 ? .83 : 1.2), controls.minDistance, controls.maxDistance)
  camera.position.copy(controls.target).add(offset.setLength(distance)); controls.update()
}
function key(event: KeyboardEvent) {
  if (!controls) return
  const arrows = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown']
  if (arrows.includes(event.key)) {
    event.preventDefault()
    if (event.shiftKey) {
      const movement = new T.Vector3(event.key === 'ArrowLeft' ? -.1 : event.key === 'ArrowRight' ? .1 : 0, event.key === 'ArrowUp' ? .1 : event.key === 'ArrowDown' ? -.1 : 0, 0).applyQuaternion(camera.quaternion)
      controls.target.add(movement); camera.position.add(movement)
    } else {
      const offset = camera.position.clone().sub(controls.target)
      const spherical = new T.Spherical().setFromVector3(offset)
      spherical.theta += event.key === 'ArrowLeft' ? -.18 : event.key === 'ArrowRight' ? .18 : 0
      spherical.phi = T.MathUtils.clamp(spherical.phi + (event.key === 'ArrowUp' ? -.15 : event.key === 'ArrowDown' ? .15 : 0), .02, Math.PI - .02)
      camera.position.copy(controls.target).add(new T.Vector3().setFromSpherical(spherical))
    }
    controls.update()
  } else if (['+', '=', '-'].includes(event.key)) { event.preventDefault(); zoom(event.key === '-' ? -1 : 1) }
  else if (event.key.toLowerCase() === 'r' || event.key === 'Home') { event.preventDefault(); reset() }
}
function resize() {
  if (!host.value || !renderer) return
  // Layout dimensions exclude the opening transform; a scaled bounding rect would
  // leave the canvas too small and off-center after the reveal animation finishes.
  const width = host.value.clientWidth, height = host.value.clientHeight
  if (!width || !height) return
  camera.aspect = width / height
  // Preserve framing on narrow screens without changing model scale.
  camera.fov = width < height ? T.MathUtils.radToDeg(2 * Math.atan(Math.tan(T.MathUtils.degToRad(35 / 2)) / camera.aspect)) : 35
  camera.updateProjectionMatrix(); renderer.setSize(width, height)
}
function tick(time: number) {
  if (disposed || failed) return
  const delta = lastTime ? Math.min((time - lastTime) / 1000, .05) : 0; lastTime = time
  if (!document.hidden && host.value?.getBoundingClientRect().width) {
    controls.autoRotate = props.autoRotate && !reduced()
    controls.update(delta)
    // Clamp orbit target and move camera by the same delta to bound mouse/touch/keyboard panning.
    const before = controls.target.clone(); controls.target.clampLength(0, .65)
    camera.position.add(controls.target.clone().sub(before))
    renderer.render(scene, camera)
  }
  frame = requestAnimationFrame(tick)
}
async function load() {
  const version = ++generation
  loadingManager?.abort(); window.clearTimeout(loadTimeout)
  loadTimeout = window.setTimeout(() => { if (version === generation) { loadingManager?.abort(); fail('The detailed model took too long to load. Retry or use its 2D illustration.') } }, 30_000)
  try {
    if (model) { scene.remove(model); disposeScene(model); model = undefined }
    const config = bodyParts[props.part].model
    loadingManager = new T.LoadingManager()
    const candidate = config.kind === 'procedural' ? (await config.load())(props.side) : (await new GLTFLoader(loadingManager).loadAsync(props.variant==='vascular'&&config.alternateUrl?config.alternateUrl:config.sideUrls?.[props.side] ?? config.url)).scene
    if (disposed || version !== generation) { disposeScene(candidate); return }
    window.clearTimeout(loadTimeout)
    model = candidate; scene.add(candidate); reset(); emit('ready')
  } catch { if (version === generation) { window.clearTimeout(loadTimeout); fail('The detailed model could not load. Retry, or explore its 2D illustration.') } }
}
function contextLost(event: Event) { event.preventDefault(); fail('The graphics connection was lost. Retry 3D, or switch to the 2D illustration.') }
function preferenceChanged() { if (controls) controls.enableDamping = !reduced() }
function getSnapshot() {
  let meshes = 0, triangles = 0, textures = 0
  model?.traverse(object => { if (object instanceof T.Mesh) {
    meshes++; triangles += (object.geometry.index?.count ?? object.geometry.attributes.position!.count) / 3
    if (object.material instanceof T.MeshStandardMaterial && object.material.map) textures++
  } })
  return { part: props.part, side: props.side, meshes, triangles, textures, camera: camera?.position.toArray(), target: controls?.target.toArray(), autoRotate: controls?.autoRotate, structures: model?.children.map(child => child.name) }
}
defineExpose({ reset, zoom, getSnapshot })
onMounted(() => {
  try {
    scene = new T.Scene(); camera = new T.PerspectiveCamera(35, 1, .03, 60)
    renderer = new T.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.75)); renderer.outputColorSpace = T.SRGBColorSpace
    renderer.toneMapping = T.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.0
    host.value!.appendChild(renderer.domElement); renderer.domElement.addEventListener('webglcontextlost', contextLost)
    const pmrem=new T.PMREMGenerator(renderer),room=new RoomEnvironment();environment=pmrem.fromScene(room,.05);scene.environment=environment.texture;scene.environmentIntensity=.5;room.dispose();pmrem.dispose()
    scene.add(new T.HemisphereLight('#fff9f3', '#8ca5b4', 1.2))
    const keyLight = new T.DirectionalLight('#fff1df', 2.1); keyLight.position.set(-3, 4, 5); scene.add(keyLight)
    const fill = new T.DirectionalLight('#d9e8ee', .7); fill.position.set(3, 1, 2); scene.add(fill)
    const rim = new T.DirectionalLight('#ffffff', .9); rim.position.set(-1, 2, -4); scene.add(rim)
    controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = !reduced(); controls.dampingFactor = .09; controls.enablePan = true
    controls.minDistance = 2; controls.maxDistance = 12; controls.autoRotateSpeed = 1.25
    controls.minPolarAngle = .01; controls.maxPolarAngle = Math.PI - .01
    controls.touches.ONE = T.TOUCH.ROTATE; controls.touches.TWO = T.TOUCH.DOLLY_PAN
    controls.addEventListener('start', () => host.value?.focus({ preventScroll: true }))
    observer = new ResizeObserver(resize); observer.observe(host.value!); resize()
    preference.addEventListener('change', preferenceChanged)
    frame = requestAnimationFrame(tick); void load()
  } catch { fail('Your browser could not start WebGL. You can still explore the detailed 2D illustrations.') }
})
watch(() => [props.part, props.side, props.variant], () => { if (controls) void load() })
watch(() => props.reducedMotion, preferenceChanged)
onBeforeUnmount(() => {
  disposed = true; generation++; cancelAnimationFrame(frame); observer?.disconnect(); controls?.dispose()
  loadingManager?.abort(); window.clearTimeout(loadTimeout)
  preference.removeEventListener('change', preferenceChanged)
  if (scene) { disposeScene(scene); scene.clear() }
  environment?.dispose()
  renderer?.domElement.removeEventListener('webglcontextlost', contextLost)
  renderer?.dispose(); renderer?.forceContextLoss(); renderer?.domElement.remove()
})
</script>
<template>
  <div ref="host" class="anatomy-canvas" tabindex="0" role="application" :aria-label="`3D ${partLabel(part, side)}. Drag to rotate 360 degrees. Scroll or pinch to zoom. Right-drag or two-finger drag to pan. Arrow keys rotate; Shift and arrows pan; plus and minus zoom; R resets.`" @keydown="key" />
</template>
