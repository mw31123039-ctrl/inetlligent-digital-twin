<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'
import { buildHumanRig } from '../three/buildHumanRig'
import { disposeScene } from '../three/disposeScene'
import { humanModelConfig, regionLabels, viewAngles, viewFromAngle, type HumanModelConfig, type HumanView } from '../three/humanViewerConfig'
import type { RegionId } from '../types'

const props = withDefaults(defineProps<{
  selected: RegionId | null
  view: HumanView
  zoom: number
  reducedMotion: boolean
  paused?: boolean
  modelConfig?: HumanModelConfig
}>(), { paused: false, modelConfig: () => humanModelConfig })
const emit = defineEmits<{
  select: [id: RegionId]; error: [message: string]; ready: []
  progress: [percent: number | null]; orientation: [view: HumanView]; zoom: [value: number]
}>()
const host = ref<HTMLDivElement>()
const label = ref<HTMLDivElement>()
const ready = ref(false)
let renderer: THREE.WebGLRenderer | undefined
let scene: THREE.Scene | undefined
let camera: THREE.PerspectiveCamera | undefined
let controls: OrbitControls | undefined
let rig: ReturnType<typeof buildHumanRig> | undefined
let mixer: THREE.AnimationMixer | undefined
let environment: THREE.WebGLRenderTarget | undefined
let loadingManager: THREE.LoadingManager | undefined
let observer: ResizeObserver | undefined
let frame = 0
let disposed = false
let failed = false
let active = true
let previousTime = 0
let distance = 4.2
let tween: { from: THREE.Spherical; to: THREE.Spherical; start: number } | undefined
const target = new THREE.Vector3(0, .92, 0)
const pointer = new THREE.Vector2()
const raycaster = new THREE.Raycaster()
const pointers = new Set<number>()
let down: { id: number; x: number; y: number; moved: boolean } | undefined
const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)')
let systemReducedMotion = motionPreference.matches
const reduceMotion = () => props.reducedMotion || systemReducedMotion

function fail(message: string) {
  if (disposed || failed) return
  failed = true
  cancelAnimationFrame(frame)
  loadingManager?.abort()
  emit('error', message)
}

function projectLabel() {
  if (!rig || !camera || !host.value || !label.value || !props.selected) return
  const point = rig.anchor(props.selected)
  const projected = point.clone().project(camera)
  const rect = host.value.getBoundingClientRect()
  // Eye labels stay hidden behind the head when the face points away.
  const visible = projected.z > -1 && projected.z < 1 && Math.abs(projected.x) < .94 && Math.abs(projected.y) < .94 && (props.selected !== 'eyes' || camera.position.z > .2)
  label.value.style.visibility = visible ? 'visible' : 'hidden'
  label.value.style.left = `${THREE.MathUtils.clamp((projected.x + 1) / 2 * rect.width, 14, rect.width - 90)}px`
  label.value.style.top = `${(1 - projected.y) / 2 * rect.height}px`
}

function render() {
  if (disposed || failed || !renderer || !scene || !camera) return
  renderer.render(scene, camera)
  projectLabel()
}

function animate(now: number) {
  if (disposed || failed) return
  const delta = previousTime ? Math.min((now - previousTime) / 1000, .05) : 0
  previousTime = now
  if (active && !document.hidden) {
    if (!props.paused && !reduceMotion()) mixer?.update(delta)
    if (tween && camera && controls) {
      const t = reduceMotion() ? 1 : Math.min(1, (now - tween.start) / 550)
      const ease = t * t * (3 - 2 * t)
      const current = new THREE.Spherical(
        THREE.MathUtils.lerp(tween.from.radius, tween.to.radius, ease),
        THREE.MathUtils.lerp(tween.from.phi, tween.to.phi, ease),
        THREE.MathUtils.lerp(tween.from.theta, tween.to.theta, ease),
      )
      camera.position.copy(target).add(new THREE.Vector3().setFromSpherical(current))
      if (t === 1) tween = undefined
    }
    controls?.update()
    render()
  }
  frame = requestAnimationFrame(animate)
}

function moveCamera(view: HumanView, zoom = props.zoom, immediate = false) {
  if (!camera || !controls) return
  controls.enableDamping = false
  controls.update()
  controls.enableDamping = !reduceMotion()
  const from = new THREE.Spherical().setFromVector3(camera.position.clone().sub(target))
  const theta = from.theta + Math.atan2(Math.sin(viewAngles[view] - from.theta), Math.cos(viewAngles[view] - from.theta))
  const to = new THREE.Spherical(distance / zoom, Math.PI / 2, theta)
  if (immediate || reduceMotion()) {
    tween = undefined
    camera.position.copy(target).add(new THREE.Vector3().setFromSpherical(to))
    controls.update()
    render()
  } else tween = { from, to, start: performance.now() }
}

function resize() {
  if (!host.value || !camera || !renderer || !controls) return
  const { width, height } = host.value.getBoundingClientRect()
  if (width <= 0 || height <= 0) return
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
  // Fit both height and width, including the arms, on narrow mobile canvases.
  const halfFov = THREE.MathUtils.degToRad(camera.fov / 2)
  distance = Math.max(1.03 / Math.tan(halfFov), .68 / (Math.tan(halfFov) * camera.aspect))
  controls.minDistance = distance / 1.7
  controls.maxDistance = distance / .75
  tween = undefined
  if (!ready.value) moveCamera(props.view, props.zoom, true)
  else {
    const offset = camera.position.clone().sub(target).normalize()
    camera.position.copy(target).addScaledVector(offset, distance / props.zoom)
    controls.update()
    render()
  }
}

function pointerDown(event: PointerEvent) {
  pointers.add(event.pointerId)
  if (pointers.size === 1 && event.isPrimary && event.button === 0) down = { id: event.pointerId, x: event.clientX, y: event.clientY, moved: false }
  else down = undefined
}
function pointerMove(event: PointerEvent) {
  if (down && Math.hypot(event.clientX - down.x, event.clientY - down.y) > 5) down.moved = true
}
function pointerCancel(event: PointerEvent) { pointers.delete(event.pointerId); down = undefined }
function pointerUp(event: PointerEvent) {
  const click = down && down.id === event.pointerId && !down.moved && pointers.size === 1 && Math.hypot(event.clientX - down.x, event.clientY - down.y) <= 5
  pointers.delete(event.pointerId)
  down = undefined
  if (!click || !rig || !camera || !host.value || !ready.value) return
  const rect = host.value.getBoundingClientRect()
  pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1)
  scene?.updateMatrixWorld(true)
  raycaster.setFromCamera(pointer, camera)
  const region = rig.pick(raycaster, camera.position)
  if (region) emit('select', region)
}
function contextLost(event: Event) {
  event.preventDefault()
  fail('The 3D viewer lost its graphics connection. Retry 3D, or continue with the 2D body.')
}
function handleKey(event: KeyboardEvent) {
  if (!camera || !controls) return
  if (['+', '=', '-'].includes(event.key)) {
    emit('zoom', THREE.MathUtils.clamp(props.zoom + (event.key === '-' ? -.15 : .15), .75, 1.7))
    event.preventDefault()
  }
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    tween = undefined
    camera.position.sub(target).applyAxisAngle(new THREE.Vector3(0, 1, 0), event.key === 'ArrowLeft' ? -.2 : .2).add(target)
    controls.update()
    reportCamera()
    event.preventDefault()
  }
}
function reportCamera() {
  if (!camera || !controls) return
  const offset = camera.position.clone().sub(target)
  const view = viewFromAngle(Math.atan2(offset.x, offset.z))
  if (view !== props.view) emit('orientation', view)
  const zoom = distance / offset.length()
  if (Math.abs(zoom - props.zoom) > .02) emit('zoom', THREE.MathUtils.clamp(zoom, .75, 1.7))
}
function preferenceChanged(event: MediaQueryListEvent) {
  systemReducedMotion = event.matches
  if (controls) controls.enableDamping = !reduceMotion()
}
function reset() { moveCamera('front', 1) }
function setView(view: HumanView) { moveCamera(view) }

// Useful to embedding screens and browser verification; never exposes the scene for mutation.
function getSnapshot() {
  return {
    loaded: ready.value, animationTime: mixer?.time ?? 0,
    animated: !!mixer && !props.paused && !reduceMotion(),
    camera: camera?.position.toArray(), ...rig?.diagnostics(),
    regions: rig && camera && host.value ? Object.fromEntries((Object.keys(regionLabels) as RegionId[]).map(id => {
      const point = rig!.anchor(id).project(camera!)
      return [id, { x: (point.x + 1) / 2 * host.value!.clientWidth, y: (1 - point.y) / 2 * host.value!.clientHeight }]
    })) : {},
  }
}
defineExpose({ reset, setView, getSnapshot })

onMounted(async () => {
  try {
    if (!host.value) return
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.05
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    host.value.appendChild(renderer.domElement)
    renderer.domElement.addEventListener('webglcontextlost', contextLost)
    scene = new THREE.Scene()
    camera = new THREE.PerspectiveCamera(30, 1, .03, 30)
    camera.position.set(0, target.y, distance)
    scene.add(new THREE.HemisphereLight(0xffffff, 0x8c9ca8, 1.5))
    const key = new THREE.DirectionalLight(0xfff4e9, 2.5)
    key.position.set(-1.5, 7, 3)
    key.castShadow = true
    key.shadow.mapSize.set(1024, 1024)
    Object.assign(key.shadow.camera, { left: -1.6, right: 1.6, top: 2, bottom: -1.5, near: .1, far: 12 })
    key.shadow.normalBias = .015
    key.shadow.bias = -.0002
    key.shadow.radius = 4
    scene.add(key)
    const fill = new THREE.DirectionalLight(0xdceeff, 1)
    fill.position.set(3, 2, -2)
    scene.add(fill)
    const pmrem = new THREE.PMREMGenerator(renderer)
    const room = new RoomEnvironment()
    environment = pmrem.fromScene(room, .04)
    scene.environment = environment.texture
    scene.environmentIntensity = .35
    room.dispose()
    pmrem.dispose()
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(20, 20), new THREE.ShadowMaterial({ opacity: .065, depthWrite: false }))
    ground.rotation.x = -Math.PI / 2
    ground.position.y = -.005
    ground.receiveShadow = true
    scene.add(ground)
    const contactCanvas = document.createElement('canvas')
    contactCanvas.width = contactCanvas.height = 128
    const contactContext = contactCanvas.getContext('2d')!
    const gradient = contactContext.createRadialGradient(64, 64, 4, 64, 64, 64)
    gradient.addColorStop(0, 'rgba(35,55,65,.16)')
    gradient.addColorStop(.45, 'rgba(35,55,65,.06)')
    gradient.addColorStop(1, 'rgba(35,55,65,0)')
    contactContext.fillStyle = gradient
    contactContext.fillRect(0, 0, 128, 128)
    const contact = new THREE.Mesh(new THREE.PlaneGeometry(.8, .45), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(contactCanvas), transparent: true, depthWrite: false }))
    contact.rotation.x = -Math.PI / 2
    contact.position.y = .001
    scene.add(contact)
    controls = new OrbitControls(camera, renderer.domElement)
    controls.target.copy(target)
    controls.enableDamping = !reduceMotion()
    controls.dampingFactor = .09
    controls.enablePan = false
    controls.minPolarAngle = Math.PI * .28
    controls.maxPolarAngle = Math.PI * .7
    controls.addEventListener('start', () => { tween = undefined })
    controls.addEventListener('end', reportCamera)
    observer = new ResizeObserver(resize)
    observer.observe(host.value)
    const visibility = new IntersectionObserver(entries => { active = entries[0]?.isIntersecting ?? true })
    visibility.observe(host.value)
    intersectionObserver = visibility
    motionPreference.addEventListener('change', preferenceChanged)
    resize()
    frame = requestAnimationFrame(animate)
    emit('progress', null)
    const manager = loadingManager = new THREE.LoadingManager()
    manager.onProgress = (_url, loaded, total) => { if (!disposed && !failed) emit('progress', Math.min(99, Math.round(loaded / total * 100))) }
    // A finite timeout also covers stalled external textures in replacement GLTFs.
    loadTimeout = window.setTimeout(() => fail('The human model took too long to load. Check your connection and retry 3D.'), 45_000)
    const gltf = await new GLTFLoader(manager).loadAsync(props.modelConfig.url, progress => {
      if (!disposed && !failed) emit('progress', progress.total ? Math.min(95, Math.round(progress.loaded / progress.total * 95)) : null)
    })
    window.clearTimeout(loadTimeout)
    if (disposed || failed) { disposeScene(gltf.scene); return }
    // Add before validation so partially configured replacement models are cleaned on failure.
    scene.add(gltf.scene)
    rig = buildHumanRig(gltf.scene, gltf.animations, props.modelConfig)
    mixer = new THREE.AnimationMixer(gltf.scene)
    mixer.clipAction(rig.idle).play()
    mixer.update(0)
    rig.highlight(props.selected)
    ready.value = true
    emit('progress', 100)
    render()
    emit('ready')
  } catch (error) {
    window.clearTimeout(loadTimeout)
    const reason = error instanceof Error ? error.message : ''
    fail(!renderer ? 'Your browser could not start the WebGL 3D viewer. Try again or continue using the interactive 2D body.' : reason.startsWith('Human model:') ? `${reason} Retry 3D or use the 2D body.` : 'The textured human model could not load. Check your connection and retry 3D. You can continue using the 2D body.')
  }
})
let intersectionObserver: IntersectionObserver | undefined
let loadTimeout = 0
watch(() => props.selected, id => { rig?.highlight(id); projectLabel() })
watch(() => props.view, value => {
  if (!camera || tween) { if (tween) moveCamera(value); return }
  const angle = Math.atan2(camera.position.x, camera.position.z)
  if (viewFromAngle(angle) !== value) moveCamera(value)
})
watch(() => props.zoom, value => {
  if (!camera || !controls) return
  const from = new THREE.Spherical().setFromVector3(camera.position.clone().sub(target))
  if (Math.abs(distance / from.radius - value) < .02) return
  tween = { from, to: new THREE.Spherical(distance / value, tween?.to.phi ?? from.phi, tween?.to.theta ?? from.theta), start: performance.now() }
})
watch(() => props.reducedMotion, () => { if (controls) controls.enableDamping = !reduceMotion() })
onBeforeUnmount(() => {
  disposed = true
  cancelAnimationFrame(frame)
  window.clearTimeout(loadTimeout)
  loadingManager?.abort()
  observer?.disconnect()
  intersectionObserver?.disconnect()
  motionPreference.removeEventListener('change', preferenceChanged)
  controls?.dispose()
  mixer?.stopAllAction()
  if (rig && mixer) mixer.uncacheRoot(rig.root)
  renderer?.domElement.removeEventListener('webglcontextlost', contextLost)
  if (scene) { disposeScene(scene); scene.clear() }
  environment?.dispose()
  renderer?.dispose()
  renderer?.forceContextLoss()
  renderer?.domElement.remove()
  pointers.clear()
})
</script>

<template>
  <div ref="host" class="body-canvas human-body-viewer" tabindex="0" role="application"
    :aria-busy="!ready" :aria-label="`Animated 3D human body${selected ? `. Selected: ${regionLabels[selected]}` : ''}. Drag to rotate, pinch or scroll to zoom. Arrow keys rotate, plus and minus zoom. Use the region buttons for keyboard selection.`"
    @pointerdown="pointerDown" @pointermove="pointerMove" @pointerup="pointerUp" @pointercancel="pointerCancel" @keydown="handleKey">
    <div v-if="ready && selected" ref="label" class="human-region-label" aria-hidden="true"><span></span>{{ regionLabels[selected] }}</div>
  </div>
</template>
