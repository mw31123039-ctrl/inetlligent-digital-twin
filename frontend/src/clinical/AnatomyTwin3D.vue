<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'
import { buildHumanRig } from '../three/buildHumanRig'
import { disposeScene } from '../three/disposeScene'
import { humanModelConfig } from '../three/humanViewerConfig'
import { anchorPositions, type BoneKey, type Vec3 } from './anatomy'
import { translate, type StringKey } from './i18n'
import type { AnatomyNode, ClinicalLocale, ClinicalSide } from './types'

export interface TwinMarker { id: string; role: 'selected' | 'reported' | 'finding' | 'related'; side: ClinicalSide; label: string }
const props = defineProps<{ nodes: Map<string, AnatomyNode>; markers: TwinMarker[]; focusId: string | null; reducedMotion: boolean; locale: ClinicalLocale }>()
const emit = defineEmits<{ select: [id: string] }>()
const t = (key: StringKey) => translate(props.locale, key)
const host = ref<HTMLDivElement>()
const ready = ref(false), failed = ref(false), mode = ref<'3d' | 'list'>('3d')
const COLORS: Record<TwinMarker['role'], number> = { selected: 0x14a3b0, reported: 0xe0952a, finding: 0x8a63d2, related: 0x6f8fae }
const ROLE_ORDER: TwinMarker['role'][] = ['selected', 'reported', 'finding', 'related']
const listed = computed(() => [...props.markers].sort((a, b) => ROLE_ORDER.indexOf(a.role) - ROLE_ORDER.indexOf(b.role)))

let renderer: THREE.WebGLRenderer | undefined, scene: THREE.Scene | undefined, camera: THREE.PerspectiveCamera | undefined, controls: OrbitControls | undefined
let environment: THREE.WebGLRenderTarget | undefined, observer: ResizeObserver | undefined, frame = 0, disposed = false, dirty = true
const markerGroup = new THREE.Group()
const bones = new Map<BoneKey, Vec3>()
const target = new THREE.Vector3(0, .92, 0)
let tween: { from: THREE.Vector3; to: THREE.Vector3; targetFrom: THREE.Vector3; targetTo: THREE.Vector3; start: number } | undefined
const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
const reduce = () => props.reducedMotion || motion.matches
const raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2()
let down: { x: number; y: number } | undefined

function positionsFor(marker: TwinMarker): Vec3[] {
  const node = props.nodes.get(marker.id)
  if (!node || !bones.size) return []
  return anchorPositions(node, marker.side, key => bones.get(key) ?? [0, 0, 0])
}

function rebuildMarkers() {
  for (const child of [...markerGroup.children]) {
    markerGroup.remove(child)
    const mesh = child as THREE.Mesh
    mesh.geometry?.dispose()
    ;(mesh.material as THREE.Material)?.dispose()
  }
  for (const marker of props.markers) {
    const node = props.nodes.get(marker.id)
    const radius = node?.kind === 'tooth' ? .0055 : node?.kind === 'region' ? .018 : .011
    for (const position of positionsFor(marker)) {
      const core = new THREE.Mesh(new THREE.SphereGeometry(radius, 20, 14), new THREE.MeshBasicMaterial({ color: COLORS[marker.role], transparent: true, opacity: .92, depthTest: false }))
      core.position.set(...position)
      core.renderOrder = 10
      core.userData = { id: marker.id, role: marker.role }
      markerGroup.add(core)
      if (marker.role === 'selected' || marker.id === props.focusId) {
        const halo = new THREE.Mesh(new THREE.SphereGeometry(radius * 2.2, 20, 14), new THREE.MeshBasicMaterial({ color: COLORS[marker.role], transparent: true, opacity: .22, depthTest: false, depthWrite: false }))
        halo.position.set(...position)
        halo.renderOrder = 9
        halo.userData = { id: marker.id, halo: true }
        markerGroup.add(halo)
      }
    }
  }
  dirty = true
}

function focusOn(id: string | null, immediate = false) {
  if (!camera || !controls) return
  const marker = props.markers.find(item => item.id === id) ?? props.markers.find(item => item.role === 'selected')
  const points = marker ? positionsFor(marker) : []
  const point = points.length ? points.reduce((sum, p) => sum.add(new THREE.Vector3(...p)), new THREE.Vector3()).divideScalar(points.length) : target.clone()
  const node = marker ? props.nodes.get(marker.id) : undefined
  const close = !node ? 4 : node.kind === 'tooth' ? .55 : node.id.startsWith('eye.') || node.id.startsWith('mouth.') || node.id.startsWith('head.') || node.id === 'body.eyes' ? .9 : node.kind === 'region' ? 2.6 : 1.6
  const direction = camera.position.clone().sub(controls.target).normalize()
  if (direction.z < .2) direction.set(direction.x * .4, direction.y, 1).normalize()
  const destination = point.clone().addScaledVector(direction, close)
  if (immediate || reduce()) { camera.position.copy(destination); controls.target.copy(point); controls.update(); dirty = true; return }
  tween = { from: camera.position.clone(), to: destination, targetFrom: controls.target.clone(), targetTo: point, start: performance.now() }
}

function animate(now: number) {
  if (disposed) return
  if (tween && camera && controls) {
    const progress = Math.min(1, (now - tween.start) / 650)
    const ease = progress * progress * (3 - 2 * progress)
    camera.position.lerpVectors(tween.from, tween.to, ease)
    controls.target.lerpVectors(tween.targetFrom, tween.targetTo, ease)
    if (progress === 1) tween = undefined
    dirty = true
  }
  if (!reduce()) {
    const pulse = 1 + Math.sin(now / 320) * .18
    for (const child of markerGroup.children) if (child.userData.halo) { child.scale.setScalar(pulse); dirty = true }
  }
  if (controls?.update()) dirty = true
  if (dirty && renderer && scene && camera) { renderer.render(scene, camera); dirty = false }
  frame = requestAnimationFrame(animate)
}

function resize() {
  if (!host.value || !renderer || !camera) return
  const { width, height } = host.value.getBoundingClientRect()
  if (width <= 0 || height <= 0) return
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
  dirty = true
}

function pointerDown(event: PointerEvent) { down = { x: event.clientX, y: event.clientY } }
function pointerUp(event: PointerEvent) {
  if (!down || !camera || !host.value || Math.hypot(event.clientX - down.x, event.clientY - down.y) > 5) { down = undefined; return }
  down = undefined
  const rect = host.value.getBoundingClientRect()
  pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1)
  raycaster.setFromCamera(pointer, camera)
  const hit = raycaster.intersectObjects(markerGroup.children.filter(child => !child.userData.halo), false)[0]
  if (hit) emit('select', hit.object.userData.id as string)
}

onMounted(async () => {
  try {
    if (!host.value) return
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.6))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    host.value.prepend(renderer.domElement)
    renderer.domElement.addEventListener('webglcontextlost', event => { event.preventDefault(); failed.value = true; mode.value = 'list' })
    scene = new THREE.Scene()
    camera = new THREE.PerspectiveCamera(30, 1, .02, 30)
    camera.position.set(0, .95, 4.2)
    scene.add(new THREE.HemisphereLight(0xffffff, 0x8c9ca8, 1.6))
    const key = new THREE.DirectionalLight(0xfff4e9, 2.2)
    key.position.set(-1.5, 6, 3)
    scene.add(key)
    const pmrem = new THREE.PMREMGenerator(renderer)
    const room = new RoomEnvironment()
    environment = pmrem.fromScene(room, .04)
    scene.environment = environment.texture
    scene.environmentIntensity = .35
    room.dispose(); pmrem.dispose()
    scene.add(markerGroup)
    controls = new OrbitControls(camera, renderer.domElement)
    controls.target.copy(target)
    controls.enablePan = false
    controls.enableDamping = !reduce()
    controls.minDistance = .35
    controls.maxDistance = 6
    controls.addEventListener('change', () => { dirty = true })
    controls.addEventListener('start', () => { tween = undefined })
    observer = new ResizeObserver(resize)
    observer.observe(host.value)
    resize()
    frame = requestAnimationFrame(animate)
    const gltf = await new GLTFLoader().loadAsync(humanModelConfig.url)
    if (disposed) { disposeScene(gltf.scene); return }
    scene.add(gltf.scene)
    const rig = buildHumanRig(gltf.scene, gltf.animations, humanModelConfig)
    rig.highlight(null)
    for (const [keyName, boneName] of Object.entries(humanModelConfig.bones)) {
      const bone = gltf.scene.getObjectByName(boneName)
      if (bone) bones.set(keyName as BoneKey, bone.getWorldPosition(new THREE.Vector3()).toArray() as Vec3)
    }
    rebuildMarkers()
    ready.value = true
    focusOn(props.focusId, true)
  } catch {
    failed.value = true
    mode.value = 'list'
  }
})
watch(() => [props.markers, props.nodes] as const, () => { rebuildMarkers(); if (ready.value && !props.focusId) focusOn(null) }, { deep: true })
watch(() => props.focusId, id => { rebuildMarkers(); focusOn(id) })
onBeforeUnmount(() => {
  disposed = true
  cancelAnimationFrame(frame)
  observer?.disconnect()
  controls?.dispose()
  if (scene) { disposeScene(scene); scene.clear() }
  environment?.dispose()
  renderer?.dispose()
  renderer?.forceContextLoss()
  renderer?.domElement.remove()
})
</script>

<template>
  <section class="ct-twin" :aria-label="t('three_d')">
    <div class="ct-twin-toolbar">
      <div class="ct-segmented" role="group" :aria-label="t('three_d')">
        <button type="button" :aria-pressed="mode === '3d'" :disabled="failed" @click="mode = '3d'">{{ t('three_d') }}</button>
        <button type="button" :aria-pressed="mode === 'list'" @click="mode = 'list'">{{ t('list_view') }}</button>
      </div>
      <ul class="ct-legend" aria-hidden="true">
        <li v-for="role in ROLE_ORDER" :key="role"><i :class="`ct-dot ${role}`"></i>{{ t(`role_${role}` as StringKey) }}</li>
      </ul>
    </div>
    <div v-show="mode === '3d' && !failed" ref="host" class="ct-twin-canvas" role="img" :aria-label="`${t('marker_note')}. ${listed.map(m => m.label).join(', ')}`"
      @pointerdown="pointerDown" @pointerup="pointerUp">
      <p v-if="!ready" class="ct-twin-loading" role="status">{{ t('loading3d') }}</p>
      <p class="ct-twin-caption">{{ t('marker_note') }}</p>
    </div>
    <p v-if="failed" class="ct-note" role="status">{{ t('no_webgl') }}</p>
    <ul class="ct-marker-list" :class="{ compact: mode === '3d' && !failed }">
      <li v-for="marker in listed" :key="`${marker.id}-${marker.role}`">
        <button type="button" :class="['ct-marker-button', marker.role, { focused: marker.id === focusId }]" :aria-pressed="marker.id === focusId" @click="emit('select', marker.id)">
          <i :class="`ct-dot ${marker.role}`" aria-hidden="true"></i><span>{{ marker.label }}</span><small>{{ t(`role_${marker.role}` as StringKey) }}</small>
        </button>
      </li>
    </ul>
  </section>
</template>
