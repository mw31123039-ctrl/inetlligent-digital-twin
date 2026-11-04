<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { bodyParts, partLabel, type PatientSide, type AnatomyView } from '../data/bodyParts'
import type { RegionId } from '../types'
const props = defineProps<{ part: RegionId; side: PatientSide; view: AnatomyView }>()
const emit = defineEmits<{ ready: []; error: [message: string] }>()
const scale = ref(1), pan = ref({ x: 0, y: 0 })
const pointers = new Map<number, { x: number; y: number }>()
let lastDistance = 0, dragged = false
const source = computed(() => bodyParts[props.part].illustrations[props.view])
function zoom(delta: number) { scale.value = Math.max(.75, Math.min(4, scale.value * (delta > 0 ? 1.18 : .85))) }
function reset() { scale.value = 1; pan.value = { x: 0, y: 0 }; pointers.clear(); lastDistance = 0; dragged = false }
function down(event: PointerEvent) {
  pointers.set(event.pointerId, { x: event.clientX, y: event.clientY }); lastDistance = 0
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
}
function move(event: PointerEvent) {
  const previous = pointers.get(event.pointerId); if (!previous) return
  pointers.set(event.pointerId, { x: event.clientX, y: event.clientY })
  const points = [...pointers.values()]
  if (points.length === 2) {
    const distance = Math.hypot(points[0]!.x - points[1]!.x, points[0]!.y - points[1]!.y)
    if (lastDistance) scale.value = Math.max(.75, Math.min(4, scale.value * distance / lastDistance))
    lastDistance = distance
  }
  const divisor = points.length > 1 ? 2 : 1
  pan.value = { x: Math.max(-180, Math.min(180, pan.value.x + (event.clientX - previous.x) / divisor)), y: Math.max(-160, Math.min(160, pan.value.y + (event.clientY - previous.y) / divisor)) }
  dragged = true
}
function up(event: PointerEvent) { pointers.delete(event.pointerId); lastDistance = 0 }
function key(event: KeyboardEvent) {
  if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
    event.preventDefault(); pan.value = { x: Math.max(-180, Math.min(180, pan.value.x + (event.key === 'ArrowLeft' ? -20 : event.key === 'ArrowRight' ? 20 : 0))), y: Math.max(-160, Math.min(160, pan.value.y + (event.key === 'ArrowUp' ? -20 : event.key === 'ArrowDown' ? 20 : 0))) }
  } else if (['+', '=', '-'].includes(event.key)) { event.preventDefault(); zoom(event.key === '-' ? -1 : 1) }
  else if (event.key.toLowerCase() === 'r' || event.key === 'Home') { event.preventDefault(); reset() }
}
watch(source, reset)
defineExpose({ reset, zoom, getSnapshot: () => ({ scale: scale.value, pan: pan.value, view: props.view, dragged }) })
</script>
<template>
  <div class="anatomy-illustration" tabindex="0" role="application" :aria-label="`2D ${partLabel(part, side)} illustration. Drag or use arrow keys to pan; pinch, scroll, plus or minus to zoom; R resets.`" @pointerdown="down" @pointermove="move" @pointerup="up" @pointercancel="up" @lostpointercapture="up" @wheel.prevent="zoom($event.deltaY < 0 ? 1 : -1)" @keydown="key">
    <img v-if="source" :key="source" :src="source" :alt="`${partLabel(part, side)}, ${view === 'section' ? 'cross-section' : view} anatomical illustration`" draggable="false" :style="{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})` }" @load="emit('ready')" @error="emit('error', 'This illustration could not load. Retry or choose another anatomical view.')" />
    <p v-else class="illustration-missing">This view needs a licensed anatomical illustration.</p>
  </div>
</template>
