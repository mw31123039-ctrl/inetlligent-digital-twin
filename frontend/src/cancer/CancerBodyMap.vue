<script setup lang="ts">
import type { CancerTrack } from './model'
defineProps<{ selected: CancerTrack }>()
defineEmits<{ select: [track: CancerTrack] }>()
const areas: { id: CancerTrack; label: string; x: number; y: number }[] = [
  { id: 'oral', label: 'Mouth', x: 130, y: 48 }, { id: 'lung', label: 'Lungs', x: 119, y: 116 },
  { id: 'breast', label: 'Breast', x: 151, y: 132 }, { id: 'skin', label: 'Skin', x: 75, y: 182 },
]
</script>
<template>
  <div class="care-body-map">
    <svg viewBox="0 0 260 360" role="img" aria-label="Reference body map showing available image review areas; no patient anatomy or cancer location is inferred">
      <defs><linearGradient id="care-body-shade" x1="0" x2="1"><stop stop-color="#d5e6dd"/><stop offset=".5" stop-color="#edf4ed"/><stop offset="1" stop-color="#cbdfd4"/></linearGradient></defs>
      <ellipse cx="130" cy="339" rx="56" ry="9" fill="#dce8de"/>
      <path d="M113 65v14l-31 13c-9 5-13 17-15 31l-13 73c-2 11 9 16 15 5l18-60 2 66-5 112c0 14 17 15 20 2l17-91h18l17 91c3 13 20 12 20-2l-5-112 2-66 18 60c6 11 17 6 15-5l-13-73c-2-14-6-26-15-31l-31-13V65" fill="url(#care-body-shade)" stroke="#9cbfb0" stroke-width="1.5"/>
      <path d="M109 36c0-18 42-18 42 0v17c0 18-12 28-21 28s-21-10-21-28Z" fill="url(#care-body-shade)" stroke="#9cbfb0" stroke-width="1.5"/>
      <path d="M130 91v72m-3-63c-11 2-23 15-23 34 0 12 12 15 21 7zm6 0c11 2 23 15 23 34 0 12-12 15-21 7z" fill="#b9d6c7" stroke="#9abdad" stroke-width="1.2"/>
      <path d="M112 173c9-9 27-8 35 2m-38 11c12-7 28-6 39 3m-41 11c14-5 27-5 41 1" fill="none" stroke="#b2cbbd" stroke-width="2" stroke-linecap="round"/>
      <g v-for="area in areas" :key="area.id" role="button" tabindex="0" :aria-label="'Review ' + area.label" :aria-pressed="selected === area.id" @click="$emit('select', area.id)" @keydown.enter.prevent="$emit('select', area.id)" @keydown.space.prevent="$emit('select', area.id)" class="care-body-hotspot" :class="{ selected: selected === area.id }">
        <circle :cx="area.x" :cy="area.y" r="14" class="care-hotspot-ring"/><circle :cx="area.x" :cy="area.y" r="5" class="care-hotspot-dot"/>
      </g>
    </svg>
    <div class="care-map-caption"><span>Reference anatomy</span><span>Choose a review area</span></div>
  </div>
</template>
