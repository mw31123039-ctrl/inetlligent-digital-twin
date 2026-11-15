<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { RegionId, ViewMode } from '../types'
import { explorerRegions as regions } from '../data/regions'
import { bodyParts, type PatientSide } from '../data/bodyParts'
import type { HumanView } from '../three/humanViewerConfig'
import AppIcon from './AppIcon.vue'
import Body2D from './Body2D.vue'
import BodyPartViewer from './BodyPartViewer.vue'
import BodyDisplayControls from '../avatar/BodyDisplayControls.vue'
import { useBodyDisplay } from '../avatar/context'
const HumanBodyViewer = defineAsyncComponent(() => import('../avatar/HumanAvatarView.vue'))
const props = defineProps<{ selected: RegionId | null; reducedMotion: boolean; side?: PatientSide; initialPart?: RegionId | null }>()
const emit = defineEmits<{ select: [id: RegionId, side?: PatientSide]; side: [value: PatientSide]; dental: [mode: 'pain' | 'braces'] }>()
const bodyDisplay = useBodyDisplay()
const hasBodyModel = computed(() => bodyDisplay.mode.value !== 'personal' || !!bodyDisplay.personalUrl.value)
const mode = ref<ViewMode>('3d'), view = ref<HumanView>('front'), zoom = ref(1)
const loading = ref(hasBodyModel.value), progress = ref<number | null>(null), paused = ref(false), error = ref(''), rendererKey = ref(0)
const detailPart = ref<RegionId | null>(null), patientSide = ref<PatientSide>(props.side ?? 'left')
const phase = ref<'full' | 'focusing' | 'revealing' | 'detail'>('full')
const fullVisible = computed(() => phase.value === 'full' || phase.value === 'focusing')
const viewer = ref<{ reset(): void; setView?(view: HumanView): void; focusPart?(part: RegionId, side: PatientSide): Promise<void> }>()
const detail = ref<{ reset(): void; zoom(delta: number): void; focus(): void }>()
const panel = ref<HTMLElement>()
let generation = 0
const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
const reduced = () => props.reducedMotion || preference.matches
function changeMode(value: ViewMode) {
  if (mode.value === value) return
  generation++; if (detailPart.value) phase.value = 'detail'
  mode.value = value; error.value = ''; loading.value = value === '3d'; progress.value = null; view.value = 'front'; zoom.value = 1
}
function adjustZoom(delta: number) { if (detailPart.value && !fullVisible.value) detail.value?.zoom(delta); else zoom.value = Math.max(.75, Math.min(1.7, zoom.value + delta)) }
function changeView(value: HumanView) { view.value = value; if (mode.value === '3d') viewer.value?.setView?.(value) }
function reset() { if (detailPart.value && !fullVisible.value) detail.value?.reset(); else { zoom.value = 1; view.value = 'front'; viewer.value?.reset() } }
function retry() { error.value = ''; loading.value = true; progress.value = null; rendererKey.value++ }
function changeSide(value: PatientSide) { patientSide.value = value; emit('side', value) }
function openVisiblePart(id: RegionId, side?: PatientSide) { void openPart(id, side) }
async function openPart(id: RegionId, side?: PatientSide, notify = true) {
  const version = ++generation
  patientSide.value = side ?? (detailPart.value === id ? patientSide.value : 'left')
  detailPart.value = id
  if (notify) emit('select', id, bodyParts[id].paired ? patientSide.value : undefined)
  if (phase.value === 'full' || phase.value === 'focusing') {
    phase.value = 'focusing'
    if (mode.value === '3d' && !loading.value && !error.value) await viewer.value?.focusPart?.(id, patientSide.value)
    else if (!reduced()) await new Promise(resolve => setTimeout(resolve, 620))
  }
  if (version !== generation) return
  phase.value = 'revealing'
  await nextTick(); if (panel.value?.contains(document.activeElement)) detail.value?.focus()
  if (!reduced()) await new Promise(resolve => setTimeout(resolve, 420))
  if (version === generation) phase.value = 'detail'
}
function back() { generation++; detailPart.value = null; phase.value = 'full'; zoom.value = 1; view.value = 'front'; viewer.value?.reset(); void nextTick(() => panel.value?.querySelector<HTMLButtonElement>('.region-selector button.selected')?.focus({ preventScroll: true })) }
watch(() => props.selected, id => { if (!id) back(); else if (id !== detailPart.value) void openPart(id, props.side, false) })
watch(() => props.side, side => { if (side) patientSide.value = side })
watch([bodyDisplay.mode, bodyDisplay.personalUrl, bodyDisplay.rotation, bodyDisplay.account], () => {
  generation++; detailPart.value = null; phase.value = 'full'; mode.value = '3d'; view.value = 'front'; zoom.value = 1
  error.value = ''; loading.value = hasBodyModel.value; progress.value = null; rendererKey.value++
})
onBeforeUnmount(() => { generation++ })
onMounted(()=>{const initial=props.initialPart??(window.location.hash==='#eye-chat'?'eyes':null);if(initial)void openPart(initial,props.side??'left',false)})
defineExpose({ getSnapshot: () => ({ phase: phase.value, part: detailPart.value, mode: mode.value, side: patientSide.value }) })
</script>
<template>
  <section ref="panel" class="panel viewer-panel" aria-label="Interactive body explorer" @keydown.esc.stop="back">
    <div class="viewer-topbar"><div class="segmented mode-toggle" aria-label="Body display mode"><button :class="{ chosen: mode === '2d' }" :aria-pressed="mode === '2d'" @click="changeMode('2d')">2D</button><button :class="{ chosen: mode === '3d' }" :aria-pressed="mode === '3d'" @click="changeMode('3d')"><AppIcon name="layers" :size="14"/>3D</button></div><span class="viewer-live"><i/>{{ detailPart ? 'ANATOMICAL DETAIL' : 'INTERACTIVE MODEL' }}</span></div>
    <BodyDisplayControls/>
    <div class="body-stage" :class="{ 'detail-stage': !!detailPart, 'is-revealing': phase === 'revealing', 'motion-reduced': reducedMotion }" :data-phase="phase" :aria-busy="phase === 'focusing' || phase === 'revealing'">
      <div v-show="fullVisible" class="full-body-layer" :class="{ 'is-focusing': phase === 'focusing' }">
        <Body2D v-if="mode === '2d'" ref="viewer" :selected="selected" :back="view === 'back'" :zoom="zoom" @select="openVisiblePart" @zoom="adjustZoom"/>
        <HumanBodyViewer v-else-if="!error" :key="rendererKey" ref="viewer" :selected="selected" :side="patientSide" :view="view" :zoom="zoom" :reduced-motion="reducedMotion" :paused="paused" @ready="loading = false" @progress="progress = $event" @error="error = $event; loading = false" @select="openVisiblePart" @orientation="view = $event" @zoom="zoom = $event"/>
        <div v-if="loading && mode === '3d' && !error" class="viewer-state" role="status"><span class="spinner"/><strong>Preparing your digital twin</strong><span>Loading the textured human model{{ progress === null ? '…' : ` · ${progress}%` }}</span><progress class="human-load-progress" aria-label="Human model loading progress" :value="progress ?? undefined" max="100"/></div>
        <div v-if="error" class="viewer-state viewer-error" role="alert"><AppIcon name="error" :size="32"/><strong>3D viewer unavailable</strong><p>{{ error }}</p><div class="part-error-actions"><button class="button-secondary" @click="retry">Retry 3D</button><button class="button-primary" @click="changeMode('2d')">Use 2D instead</button></div></div>
        <span class="orientation-label">{{ ({ front: 'ANTERIOR', back: 'POSTERIOR', left: 'LEFT SIDE', right: 'RIGHT SIDE' })[view] }} VIEW</span>
        <button v-if="mode === '3d' && !loading && !error && bodyDisplay.mode.value === 'realistic'" class="motion-toggle" :aria-pressed="paused || reducedMotion" :disabled="reducedMotion" @click="paused = !paused">{{ reducedMotion ? 'Motion reduced' : paused ? 'Resume motion' : 'Pause motion' }}</button>
      </div>
      <div v-if="detailPart" v-show="!fullVisible" class="detail-surface" :class="{ 'part-reveal': phase === 'revealing' }"><BodyPartViewer ref="detail" :part="detailPart" :side="patientSide" :mode="mode" :reduced-motion="reducedMotion" @back="back" @side="changeSide" @mode="changeMode"/></div>
      <span class="sr-only" role="status" aria-live="polite">{{ phase === 'focusing' ? `Opening ${detailPart}` : phase === 'detail' ? `${detailPart} detail ready` : phase === 'full' ? 'Full body view' : '' }}</span>
    </div>
    <div class="viewer-controls human-controls"><div class="zoom-controls"><button class="icon-button" aria-label="Zoom in" @click="adjustZoom(.15)"><AppIcon name="plus" :size="18"/></button><button class="icon-button" aria-label="Zoom out" @click="adjustZoom(-.15)"><AppIcon name="minus" :size="18"/></button><button class="reset-button" :aria-label="detailPart ? 'Reset View' : 'Reset'" @click="reset"><AppIcon name="reset" :size="15"/><span>{{ detailPart ? 'Reset View' : 'Reset' }}</span></button></div><span v-if="!detailPart" class="viewer-hint"><AppIcon name="mouse" :size="19"/>{{ mode === '3d' ? 'Drag to rotate' : 'Drag to pan' }} · Scroll to zoom</span><div v-if="!detailPart" class="segmented orientation-toggle" aria-label="Body orientation"><button v-for="item in (mode === '3d' ? ['front', 'back', 'left', 'right'] as const : ['front', 'back'] as const)" :key="item" :class="{ chosen: view === item }" :aria-pressed="view === item" @click="changeView(item)">{{ ({ front: 'Front', back: 'Back', left: 'Left side', right: 'Right side' })[item] }}</button></div><span v-else class="detail-controls-note">{{ mode === '3d' ? '360° exploration' : '2D anatomical atlas' }}</span></div>
    <div class="region-selector"><span>SELECT AN AREA</span><div><button v-for="region in regions" :key="region.id" :class="{ selected: selected === region.id }" :aria-pressed="selected === region.id" @click="openPart(region.id)"><AppIcon :name="region.id" :size="15"/>{{ region.label }}</button><button class="dental-region-launch" @click="emit('dental','pain')"><AppIcon name="tooth" :size="15"/>Dental pain</button><button class="dental-region-launch" @click="emit('dental','braces')"><AppIcon name="braces" :size="15"/>Braces & bite</button></div></div>
    <p class="body-representation-note">{{ bodyDisplay.mode.value === 'realistic' ? 'A textured reference person. Appearance does not represent the signed-in user or measure their health.' : bodyDisplay.mode.value === 'anatomy' ? 'Selected reference organs and bones from BodyParts3D. This is educational anatomy, not a scan of the user.' : 'Your supplied 3D appearance stays in this tab. Body-area locations are approximate; internal detail remains reference anatomy.' }}</p>
  </section>
</template>
