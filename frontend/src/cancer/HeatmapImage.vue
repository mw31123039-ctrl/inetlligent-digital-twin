<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { heatmapCaption, paintHeatmap } from './report'
import type { CancerTrack, Heatmap } from './model'

const props = defineProps<{ src: string; heatmap: Heatmap | null; track: CancerTrack; alt: string }>()
const showHeatmap = ref(true), opacity = ref(.7), aspect = ref(1)
const canvas = ref<HTMLCanvasElement | null>(null)
const caption = computed(() => props.heatmap ? heatmapCaption(props.heatmap, props.track) : '')
const visible = computed(() => !!props.heatmap && showHeatmap.value)

function draw() {
  if (!canvas.value || !props.heatmap) return
  canvas.value.width = 192
  canvas.value.height = Math.max(8, Math.round(192 / aspect.value))
  paintHeatmap(canvas.value, props.heatmap, opacity.value)
}
function loaded(event: Event) {
  const image = event.target as HTMLImageElement
  if (image.naturalWidth && image.naturalHeight) aspect.value = image.naturalWidth / image.naturalHeight
  void nextTick(draw)
}
watch(() => [props.heatmap, opacity.value, showHeatmap.value], () => nextTick(draw))
watch(() => props.heatmap, value => { showHeatmap.value = !!value })
onMounted(draw)
</script>

<template>
  <figure class="cw-heatmap">
    <div class="cw-heatmap-toolbar" v-if="heatmap">
      <div class="cw-segmented" role="group" aria-label="Image view">
        <button type="button" :aria-pressed="!showHeatmap" :class="{ active: !showHeatmap }" @click="showHeatmap = false">Image</button>
        <button type="button" :aria-pressed="showHeatmap" :class="{ active: showHeatmap }" @click="showHeatmap = true">Heatmap</button>
      </div>
      <label class="cw-opacity" :class="{ disabled: !showHeatmap }">Overlay<input v-model.number="opacity" type="range" min="0.2" max="1" step="0.05" :disabled="!showHeatmap" aria-label="Heatmap overlay strength"/></label>
    </div>
    <div class="cw-heatmap-frame" :style="{ aspectRatio: String(aspect) }">
      <img :src="src" :alt="alt" @load="loaded"/>
      <canvas v-show="visible" ref="canvas" aria-hidden="true"></canvas>
    </div>
    <figcaption v-if="heatmap">
      <span class="cw-legend" aria-hidden="true">Low<i></i>High</span>
      <span>{{ caption }} It shows model behaviour, not a tumour boundary.</span>
    </figcaption>
    <figcaption v-else>No heatmap was produced for this result.</figcaption>
  </figure>
</template>
