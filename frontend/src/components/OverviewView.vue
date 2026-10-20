<script setup lang="ts">
import AppIcon from './AppIcon.vue'
import { regions } from '../data/regions'
import type { RegionId } from '../types'
defineProps<{ savedCount: number; demo: boolean }>()
defineEmits<{ start: [region?: RegionId]; history: [] }>()
</script>
<template>
  <section class="overview-hero panel"><div><span class="eyebrow">MEET YOUR DIGITAL TWIN</span><h2>A little more understanding.<br/>One area at a time.</h2><p>Explore an interactive body, describe how you feel, and see your answers come together in a simple summary.</p><button class="button-primary" @click="$emit('start')">Explore your body<AppIcon name="arrowRight" :size="18"/></button></div><div class="overview-illustration" aria-hidden="true"><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><AppIcon name="body" :size="135"/><span class="floating-symbol one"><AppIcon name="chest" :size="24"/></span><span class="floating-symbol two"><AppIcon name="eyes" :size="26"/></span></div></section>
  <div class="overview-stats"><div class="panel"><AppIcon name="body"/><strong>6 body areas</strong><span>Explore from head to toe</span></div><div class="panel"><AppIcon name="chat"/><strong>{{ demo ? '5 guided steps' : 'Focused follow-ups' }}</strong><span>{{ demo ? 'Simple, scripted conversations' : 'One question at a time' }}</span></div><button class="panel" @click="$emit('history')"><AppIcon name="clipboard"/><strong>{{ savedCount }} saved assessments</strong><span>{{ demo ? 'View local demo history' : 'View consented account records' }} <AppIcon name="arrowRight" :size="14"/></span></button></div>
  <div class="section-heading"><h2>Where would you like to start?</h2><span>Choose an area to explore</span></div><div class="area-grid"><button v-for="region in regions" :key="region.id" class="panel area-card" @click="$emit('start', region.id)"><span class="area-card-icon"><AppIcon :name="region.id" :size="27"/></span><div><strong>{{ region.label }}</strong><span>{{ region.description }}</span></div><AppIcon name="chevronRight" :size="18"/></button></div>
  <div class="notice-banner"><AppIcon name="info" :size="20"/><p>{{ demo ? 'This is a scripted demonstration using mock data. It does not assess medical risk or provide a diagnosis.' : 'The AI assistant is a prototype. Its warning rules require clinical review. It does not replace a clinician’s examination or diagnosis.' }}</p></div>
</template>
