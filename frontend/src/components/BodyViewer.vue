<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import type { RegionId, ViewMode } from '../types'
import { getRegion, regions } from '../data/regions'
import type { HumanView } from '../three/humanViewerConfig'
import AppIcon from './AppIcon.vue'
import Body2D from './Body2D.vue'
import RegionDetail from './RegionDetail.vue'
const HumanBodyViewer = defineAsyncComponent(() => import('./HumanBodyViewer.vue'))
const props = defineProps<{ selected: RegionId | null; reducedMotion: boolean }>()
defineEmits<{ select: [id: RegionId] }>()
const mode = ref<ViewMode>('3d')
const view = ref<HumanView>('front')
const back = computed(() => view.value === 'back')
const zoom = ref(1)
const loading = ref(true)
const progress = ref<number | null>(null)
const paused = ref(false)
const error = ref('')
const rendererKey = ref(0)
const viewer = ref<{ reset(): void; setView?(view: HumanView): void }>()
const calloutStyle = computed(() => ({ top: `${({ eyes: 11, head: 6, chest: 31, abdomen: 43, arms: 48, legs: 70 } as const)[props.selected ?? 'eyes']}%`, left: props.selected === 'arms' ? '63%' : '51%' }))
function changeMode(value: ViewMode) { if (mode.value === value) return; mode.value = value; error.value = ''; loading.value = value === '3d'; progress.value = null; view.value = 'front'; zoom.value = 1 }
function adjustZoom(delta: number) { zoom.value = Math.max(.75, Math.min(1.7, zoom.value + delta)) }
function changeView(value: HumanView) { view.value = value; if (mode.value === '3d') viewer.value?.setView?.(value) }
function reset() { zoom.value = 1; view.value = 'front'; viewer.value?.reset() }
function retry() { error.value = ''; loading.value = true; progress.value = null; rendererKey.value++ }
watch(() => props.selected, value => { if (value === 'eyes') changeView('front') })
</script>
<template>
  <section class="panel viewer-panel" aria-label="Interactive body explorer">
    <div class="viewer-topbar"><div class="segmented mode-toggle" aria-label="Body display mode"><button :class="{ chosen: mode === '2d' }" :aria-pressed="mode === '2d'" @click="changeMode('2d')">2D</button><button :class="{ chosen: mode === '3d' }" :aria-pressed="mode === '3d'" @click="changeMode('3d')"><AppIcon name="layers" :size="14"/>3D</button></div><span class="viewer-live"><i></i> INTERACTIVE MODEL</span></div>
    <div class="body-stage" :aria-busy="loading && mode === '3d'">
      <Body2D v-if="mode === '2d'" ref="viewer" :selected="selected" :back="back" :zoom="zoom" @select="$emit('select', $event)" @zoom="adjustZoom" />
      <HumanBodyViewer v-else-if="!error" :key="rendererKey" ref="viewer" :selected="selected" :view="view" :zoom="zoom" :reduced-motion="reducedMotion" :paused="paused" @ready="loading = false" @progress="progress = $event" @error="error = $event; loading = false" @select="$emit('select', $event)" @orientation="view = $event" @zoom="zoom = $event" />
      <div v-if="loading && mode === '3d' && !error" class="viewer-state" role="status"><span class="spinner"></span><strong>Preparing your digital twin</strong><span>Loading the textured human model{{ progress === null ? '…' : ` · ${progress}%` }}</span><progress class="human-load-progress" aria-label="Human model loading progress" :value="progress ?? undefined" max="100"></progress></div>
      <div v-if="error" class="viewer-state viewer-error" role="alert"><AppIcon name="error" :size="32"/><strong>3D viewer unavailable</strong><p>{{ error }}</p><div class="flex gap-2"><button class="button-secondary" @click="retry">Retry 3D</button><button class="button-primary" @click="changeMode('2d')">Use 2D instead</button></div></div>
      <template v-if="mode === '2d' && selected && !back"><div class="body-callout" :style="calloutStyle"><span class="callout-point"></span><span class="callout-line"></span><span class="callout-tag">{{ getRegion(selected).label }}</span></div><RegionDetail :region="selected" /></template>
      <span class="orientation-label">{{ ({ front: 'ANTERIOR', back: 'POSTERIOR', left: 'LEFT SIDE', right: 'RIGHT SIDE' })[view] }} VIEW</span>
      <button v-if="mode === '3d' && !loading && !error" class="motion-toggle" :aria-pressed="paused || reducedMotion" :disabled="reducedMotion" @click="paused = !paused">{{ reducedMotion ? 'Motion reduced' : paused ? 'Resume motion' : 'Pause motion' }}</button>
    </div>
    <div class="viewer-controls" :class="{ 'human-controls': mode === '3d' }"><div class="zoom-controls"><button class="icon-button" aria-label="Zoom in" :disabled="zoom >= 1.7" @click="adjustZoom(.15)"><AppIcon name="plus" :size="18"/></button><button class="icon-button" aria-label="Zoom out" :disabled="zoom <= .75" @click="adjustZoom(-.15)"><AppIcon name="minus" :size="18"/></button><button class="reset-button" @click="reset"><AppIcon name="reset" :size="15"/><span>Reset</span></button></div><span class="viewer-hint"><AppIcon name="mouse" :size="19"/>{{ mode === '3d' ? 'Drag to rotate' : 'Drag to pan' }}<i>·</i>Scroll to zoom</span><div class="segmented orientation-toggle" aria-label="Body orientation"><button :class="{ chosen: view === 'front' }" :aria-pressed="view === 'front'" @click="changeView('front')">Front</button><button :class="{ chosen: back }" :aria-pressed="back" @click="changeView('back')">Back</button><template v-if="mode === '3d'"><button :class="{ chosen: view === 'left' }" :aria-pressed="view === 'left'" @click="changeView('left')">Left side</button><button :class="{ chosen: view === 'right' }" :aria-pressed="view === 'right'" @click="changeView('right')">Right side</button></template></div></div>
    <div class="region-selector"><span>SELECT AN AREA</span><div><button v-for="region in regions" :key="region.id" :class="{ selected: selected === region.id }" :aria-pressed="selected === region.id" @click="$emit('select', region.id)"><AppIcon :name="region.id" :size="15"/>{{ region.label }}</button></div></div>
  </section>
</template>
