<script setup lang="ts">
import { computed, defineAsyncComponent, inject, onBeforeUnmount, onErrorCaptured, ref, watch } from 'vue'
import type { RegionId, ViewMode } from '../types'
import { bodyParts, partLabel, type PatientSide, type AnatomyView } from '../data/bodyParts'
import AnatomyIllustration from './AnatomyIllustration.vue'
import AppIcon from './AppIcon.vue'
import EyeAtlas from '../eye/EyeAtlas.vue'
import { createEyeContext,eyeContextKey } from '../eye/context'
const eye=inject(eyeContextKey)||createEyeContext()
const BodyPart3D = defineAsyncComponent({ loader: () => import('./BodyPart3D.vue'), onError(_error, retry, fail, attempts) { if (attempts <= 1) retry(); else fail() } })
const props = defineProps<{ part: RegionId; side: PatientSide; mode: ViewMode; reducedMotion: boolean }>()
defineEmits<{ back: []; side: [value: PatientSide]; mode: [value: ViewMode] }>()
const config = computed(() => bodyParts[props.part])
const legendColors: Record<RegionId, string[]> = { eyes: ['#e0d5c6', '#5e9393', '#273b46', '#bfdcde', '#d5b97e'], head: ['#d99996', '#bd858a', '#e6cbb3'], chest: ['#d99399', '#ae4d58', '#e2c5ae', '#dfcfb1'], abdomen: ['#a65a50', '#dfa09a', '#bd7e79', '#a55155'], arms: ['#efdfbd', '#e3d1b0', '#f0dfbd', '#c27970'], legs: ['#efdfbd', '#f0dfbd', '#e3d1b0', '#efdfc6'] }
const view = ref<AnatomyView>('front'), loading = ref(true), error = ref(''), autoRotate = ref(false), rendererKey = ref(0)
const chestView = ref<'surface'|'vascular'>('surface')
const visibleStructures = computed(() => props.part==='chest'&&props.mode==='3d'?(chestView.value==='surface'?['Lung lobes','Heart','Trachea']:['Pulmonary branches','Heart','Trachea','Ribs']):config.value.structures)
const viewer = ref<{ reset(): void; zoom(delta: number): void; getSnapshot(): unknown }>()
const backButton = ref<HTMLButtonElement>()
const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
const systemReduced = ref(preference.matches)
function motionChanged(event: MediaQueryListEvent) { systemReduced.value = event.matches; if (event.matches) autoRotate.value = false }
preference.addEventListener('change', motionChanged)
onBeforeUnmount(() => preference.removeEventListener('change', motionChanged))
onErrorCaptured(() => { error.value = 'The viewer could not load. Retry or select another display mode.'; loading.value = false; return false })
const availableViews = computed(() => (['front', 'side', 'section'] as const).filter(item => config.value.illustrations[item]))
function focusEyeChat() { document.querySelector<HTMLElement>('.eye-inline-assistant')?.focus() }
function reset() { viewer.value?.reset() }
function zoom(delta: number) { viewer.value?.zoom(delta) }
function retry() { loading.value = true; error.value = ''; rendererKey.value++ }
watch(() => [props.part, props.side, props.mode, view.value, chestView.value], () => { loading.value = true; error.value = ''; autoRotate.value = false })
watch(() => props.part, () => { view.value = 'front'; chestView.value = 'surface' })
defineExpose({ reset, zoom, focus: () => backButton.value?.focus({ preventScroll: true }), getSnapshot: () => viewer.value?.getSnapshot() })
</script>
<template>
  <div v-if="part === 'eyes'" class="body-part-viewer eye-part-detail" :data-part="part" :data-mode="mode" :data-side="side" :aria-busy="false"><div class="part-heading"><button ref="backButton" class="back-to-body" @click="$emit('back')"><AppIcon name="arrowLeft" :size="15"/>Back to full body</button><div><span class="anatomy-eyebrow">INTERACTIVE EYE ANATOMY</span><h2>{{partLabel(part,side)}}</h2><p>63 selectable structures · internal layers, tears, retina, nerves and muscles</p></div></div><div class="patient-side-selector"><span>Patient’s side</span><div class="segmented" aria-label="Patient side"><button v-for="item in (['left','right'] as const)" :key="item" :aria-pressed="side===item" @click="$emit('side',item)">{{item==='left'?'Left':'Right'}}</button></div></div><EyeAtlas ref="viewer" :side="side" :locale="eye.session.locale" :reduced-motion="reducedMotion" :selected="eye.selected.value" :compact="true" :display="mode" @select="eye.explore" @report="focusEyeChat"/></div>
  <div v-else class="body-part-viewer" :data-part="part" :data-mode="mode" :data-side="side" :aria-busy="loading">
    <div class="part-heading"><button ref="backButton" class="back-to-body" @click="$emit('back')"><AppIcon name="arrowLeft" :size="15"/>Back to full body</button><div><span class="anatomy-eyebrow">ANATOMY EXPLORER</span><h2>{{ partLabel(part, side) }}</h2><p>{{ config.description }}</p></div></div>
    <div v-if="config.paired" class="patient-side-selector"><span>Patient’s side</span><div class="segmented" aria-label="Patient side"><button v-for="item in (['left', 'right'] as const)" :key="item" :aria-pressed="side === item" :class="{ chosen: side === item }" @click="$emit('side', item)">{{ item === 'left' ? 'Left' : 'Right' }}</button></div><small>Left / right from the patient’s perspective</small></div>
    <div v-if="part === 'chest' && mode === '3d'" class="part-source-choice"><div class="segmented" role="group" aria-label="Chest anatomy view"><button :aria-pressed="chestView === 'surface'" :class="{ chosen: chestView === 'surface' }" @click="chestView = 'surface'">Organ surfaces</button><button :aria-pressed="chestView === 'vascular'" :class="{ chosen: chestView === 'vascular' }" @click="chestView = 'vascular'">Vessels and ribs</button></div></div><div class="part-model-stage">
      <BodyPart3D v-if="mode === '3d' && !error" :key="`3d-${rendererKey}`" ref="viewer" :part="part" :side="side" :reduced-motion="reducedMotion" :auto-rotate="autoRotate" :variant="chestView" @ready="loading = false" @error="error = $event; loading = false" />
      <AnatomyIllustration v-else-if="mode === '2d' && !error" :key="`2d-${rendererKey}`" ref="viewer" :part="part" :side="side" :view="view" @ready="loading = false" @error="error = $event; loading = false" />
      <div v-if="loading && !error" class="viewer-state part-loading" role="status"><span class="spinner"/><strong>Loading {{ partLabel(part, side).toLowerCase() }}</strong><span>Preparing your {{ mode === '3d' ? '3D model' : 'anatomical illustration' }}</span></div>
      <div v-if="error" class="viewer-state viewer-error" role="alert"><AppIcon name="error" :size="28"/><strong>{{ mode === '3d' ? '3D model unavailable' : 'Illustration unavailable' }}</strong><p>{{ error }}</p><div class="part-error-actions"><button class="button-secondary" @click="retry">Retry {{ mode === '3d' ? 'model' : 'illustration' }}</button><button v-if="mode === '3d'" class="button-primary" @click="$emit('mode', '2d')">Use 2D instead</button></div></div>
    </div>
    <div class="part-tools"><span class="part-interaction-hint"><AppIcon name="mouse" :size="15"/>{{ mode === '3d' ? 'Drag to rotate · Scroll to zoom' : 'Drag to pan · Scroll to zoom' }}</span><label v-if="mode === '3d'" class="auto-rotate"><input v-model="autoRotate" type="checkbox" :disabled="reducedMotion || systemReduced || loading || !!error"/>Auto Rotate</label><div v-else class="segmented anatomy-views" aria-label="Anatomical illustration view"><button v-for="item in availableViews" :key="item" :class="{ chosen: view === item }" :aria-pressed="view === item" @click="view = item">{{ item === 'section' ? 'Cross-section' : item === 'front' ? 'Front' : 'Side' }}</button></div></div>
    <div class="anatomy-legend" aria-label="Visible anatomical structures"><span v-for="(structure, index) in visibleStructures" :key="structure"><i :style="{ background: legendColors[part][index], borderColor: legendColors[part][index] }"/>{{ structure }}</span></div>
    <span v-if="mode === '3d' && part === 'chest' && chestView === 'surface'" class="anatomy-caption">Z-Anatomy reference surfaces · <a href="https://github.com/LluisV/Z-Anatomy" target="_blank" rel="noopener noreferrer">Lluís Vinent Juanico and contributors / Gauthier Kervyn / BodyParts3D</a> · <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener noreferrer">CC BY-SA 4.0</a> · Illustrative colors; not a patient scan</span><span v-else-if="mode === '3d'" class="anatomy-caption">Reference meshes: <a href="https://dbarchive.biosciencedbc.jp/en/bodyparts3d/" target="_blank" rel="noopener noreferrer">BodyParts3D</a>, © The Database Center for Life Science · <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer">CC BY 4.0</a> · Illustrative colors; not a patient scan</span><span v-else class="anatomy-caption">Schematic anatomy · Educational illustration</span>
  </div>
</template>
