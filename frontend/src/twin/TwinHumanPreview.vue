<script setup lang="ts">
import { defineAsyncComponent, ref } from 'vue'
import type { RegionId } from '../types'
import type { PatientSide } from '../data/bodyParts'
import { regionLabels, type HumanView } from '../three/humanViewerConfig'
import AppIcon from '../components/AppIcon.vue'
const HumanBodyViewer = defineAsyncComponent(() => import('../components/HumanBodyViewer.vue'))
defineProps<{ selected?: RegionId | null; side?: PatientSide; reducedMotion?: boolean }>()
const emit = defineEmits<{ explore: [region: RegionId, side?: PatientSide] }>()
const view = ref<HumanView>('front'), zoom = ref(1), loaded = ref(false), error = ref(''), key = ref(0)
function retry() { error.value = ''; loaded.value = false; key.value++ }
</script>
<template>
  <div class="twin-human-preview">
    <div class="twin-human-heading"><span class="twin-eyebrow">TEXTURED 3D HUMAN</span><span>Reference adult</span></div>
    <div class="twin-human-stage">
      <HumanBodyViewer v-if="!error" :key="key" :selected="selected ?? null" :side="side ?? 'left'" :view="view" :zoom="zoom" :reduced-motion="reducedMotion ?? false" @ready="loaded = true" @error="error = $event" @orientation="view = $event" @zoom="zoom = $event" @select="(region, patientSide) => emit('explore', region, patientSide)"/>
      <p v-if="!loaded && !error" class="twin-human-status" role="status">Loading the textured human…</p>
      <div v-if="error" class="twin-human-status" role="alert"><p>{{ error }}</p><button class="button-secondary" @click="retry">Retry 3D human</button></div>
    </div>
    <div class="twin-human-tools"><button aria-label="Zoom human in" @click="zoom = Math.min(1.7, zoom + .15)"><AppIcon name="plus" :size="15"/></button><button aria-label="Zoom human out" @click="zoom = Math.max(.75, zoom - .15)"><AppIcon name="minus" :size="15"/></button><button :aria-pressed="view === 'front'" @click="view = 'front'">Front</button><button :aria-pressed="view === 'back'" @click="view = 'back'">Back</button></div>
    <div class="twin-human-regions" role="group" aria-label="Explore body region"><button v-for="(label, id) in regionLabels" :key="id" @click="emit('explore', id, selected === id ? side : undefined)">{{ selected === id ? 'Explore ' : '' }}{{ label }}</button></div>
    <p class="twin-caption">Drag to rotate; select a body area to explore it. This reference avatar is not a reconstruction of the study subject.</p>
  </div>
</template>
