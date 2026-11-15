<script setup lang="ts">
import type { CancerTrack } from './model'

const props = defineProps<{ selected: CancerTrack; ready: Record<CancerTrack, boolean> }>()
const emit = defineEmits<{ select: [track: CancerTrack] }>()
// Hotspot positions on the reference figure and where each label sits.
const areas: { id: CancerTrack; label: string; x: number; y: number; lx: number; ly: number; anchor: 'start' | 'end' }[] = [
  { id: 'oral', label: 'Oral', x: 160, y: 70, lx: 62, ly: 58, anchor: 'end' },
  { id: 'lung', label: 'Lung', x: 145, y: 140, lx: 62, ly: 118, anchor: 'end' },
  { id: 'breast', label: 'Breast', x: 183, y: 156, lx: 262, ly: 128, anchor: 'start' },
  { id: 'skin', label: 'Skin', x: 104, y: 206, lx: 62, ly: 248, anchor: 'end' },
]
const order = areas.map(area => area.id)
function move(current: CancerTrack, step: number) {
  const next = order[(order.indexOf(current) + step + order.length) % order.length]!
  emit('select', next)
  requestAnimationFrame(() => (document.querySelector(`[data-map-area="${next}"]`) as SVGGElement | null)?.focus())
}
</script>

<template>
  <div class="cw-body-map">
    <svg viewBox="0 0 320 400" role="radiogroup" aria-label="Choose a body area on the reference figure" @keydown.down.prevent="move(props.selected, 1)" @keydown.right.prevent="move(props.selected, 1)" @keydown.up.prevent="move(props.selected, -1)" @keydown.left.prevent="move(props.selected, -1)">
      <defs><linearGradient id="cw-body-shade" x1="0" x2="1"><stop class="cw-body-stop-a" offset="0"/><stop class="cw-body-stop-b" offset=".5"/><stop class="cw-body-stop-a" offset="1"/></linearGradient></defs>
      <g transform="translate(30 20)" class="cw-figure" aria-hidden="true">
        <ellipse cx="130" cy="352" rx="62" ry="9" class="cw-figure-shadow"/>
        <path d="M113 65v14l-31 13c-9 5-13 17-15 31l-13 73c-2 11 9 16 15 5l18-60 2 66-5 112c0 14 17 15 20 2l17-91h18l17 91c3 13 20 12 20-2l-5-112 2-66 18 60c6 11 17 6 15-5l-13-73c-2-14-6-26-15-31l-31-13V65" class="cw-figure-body"/>
        <path d="M109 36c0-18 42-18 42 0v17c0 18-12 28-21 28s-21-10-21-28Z" class="cw-figure-body"/>
        <path d="M130 91v72m-3-63c-11 2-23 15-23 34 0 12 12 15 21 7zm6 0c11 2 23 15 23 34 0 12-12 15-21 7z" class="cw-figure-organ"/>
      </g>
      <g v-for="area in areas" :key="area.id" :data-map-area="area.id" class="cw-map-spot" :class="{ selected: selected === area.id, ready: ready[area.id] }"
         role="radio" :aria-checked="selected === area.id" :tabindex="selected === area.id ? 0 : -1" :aria-label="area.label + (ready[area.id] ? '' : ', no model ready')"
         @click="emit('select', area.id)" @keydown.enter.prevent="emit('select', area.id)" @keydown.space.prevent="emit('select', area.id)">
        <line :x1="area.x" :y1="area.y" :x2="area.lx + (area.anchor === 'end' ? 6 : -6)" :y2="area.ly" class="cw-map-leader"/>
        <circle :cx="area.x" :cy="area.y" r="24" class="cw-map-hit"/>
        <circle :cx="area.x" :cy="area.y" r="15" class="cw-map-ring"/>
        <circle :cx="area.x" :cy="area.y" r="6" class="cw-map-dot"/>
        <text :x="area.lx" :y="area.ly + 5" :text-anchor="area.anchor" class="cw-map-label">{{ area.label }}</text>
      </g>
    </svg>
    <p class="cw-map-caption">Select an area on the figure or in the list. The figure is a reference drawing, not your anatomy.</p>
  </div>
</template>
