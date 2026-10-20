<script setup lang="ts">
import { ref } from 'vue'
import type { RegionId } from '../types'
defineProps<{ selected: RegionId | null; back: boolean; zoom: number }>()
const emit = defineEmits<{ select: [id: RegionId]; zoom: [delta: number] }>()
const pan = ref({ x: 0, y: 0 })
let start: { x: number; y: number; px: number; py: number } | null = null
function down(e: PointerEvent) { start = { x: e.clientX, y: e.clientY, px: pan.value.x, py: pan.value.y }; (e.currentTarget as SVGElement).setPointerCapture(e.pointerId) }
function move(e: PointerEvent) { if (start) pan.value = { x: Math.max(-100, Math.min(100, start.px + e.clientX - start.x)), y: Math.max(-100, Math.min(100, start.py + e.clientY - start.y)) } }
function up(e: PointerEvent) {
  if (start && Math.hypot(e.clientX - start.x, e.clientY - start.y) < 5) {
    const target = document.elementFromPoint(e.clientX, e.clientY)?.closest('[data-region]')
    if (target) emit('select', target.getAttribute('data-region') as RegionId)
  }
  start = null
}
function reset() { pan.value = { x: 0, y: 0 } }
defineExpose({ reset })
</script>
<template>
  <svg class="body-svg" viewBox="0 0 400 650" role="img" aria-label="Interactive 2D body. Choose a body area using the region buttons below." @pointerdown="down" @pointermove="move" @pointerup="up" @pointercancel="start = null" @wheel.prevent="$emit('zoom', $event.deltaY < 0 ? 0.1 : -0.1)">
    <defs><linearGradient id="skin" x1="0" x2="1"><stop stop-color="#b7c4c9"/><stop offset=".42" stop-color="#f1f5f5"/><stop offset="1" stop-color="#b9c7cc"/></linearGradient><linearGradient id="selected" x1="0" x2="1"><stop stop-color="#58c6cb"/><stop offset=".5" stop-color="#b4eeed"/><stop offset="1" stop-color="#46bcc4"/></linearGradient><radialGradient id="ground"><stop stop-color="#183743" stop-opacity=".14"/><stop offset="1" stop-color="#183743" stop-opacity="0"/></radialGradient></defs>
    <ellipse cx="200" cy="618" rx="100" ry="16" fill="url(#ground)"/>
    <g :transform="`translate(${200 + pan.x},${320 + pan.y}) scale(${zoom}) translate(-200,-320)`" stroke="#a6b9bf" stroke-width="1.25" stroke-linejoin="round">
      <g data-region="legs" :class="{ selected: selected === 'legs' }" class="body-region">
        <path d="M159 344 Q143 370 151 410 L160 465 Q151 492 160 544 L166 586 Q154 598 150 610 Q167 620 188 610 L190 579 L191 493 L200 420 L209 493 L210 579 L212 610 Q235 620 250 610 Q246 598 234 586 L240 544 Q249 492 240 465 L249 410 Q257 370 241 344Z"/>
        <path class="anatomy-line" d="M200 365V420M160 465Q173 476 190 466M210 466Q227 476 240 465M172 492L178 565M228 492L222 565"/>
      </g>
      <g data-region="arms" :class="{ selected: selected === 'arms' }" class="body-region">
        <path d="M147 154 Q119 148 113 185 L101 248 L81 315 L66 333 L59 352 Q59 361 64 357 L76 341 L63 372 Q63 380 69 374 L84 346 L75 380 Q77 385 81 379 L94 349 L89 374 Q92 380 96 370 L106 338 L105 319 L125 273 L147 214Z"/>
        <path d="M253 154 Q281 148 287 185 L299 248 L319 315 L334 333 L341 352 Q341 361 336 357 L324 341 L337 372 Q337 380 331 374 L316 346 L325 380 Q323 385 319 379 L306 349 L311 374 Q308 380 304 370 L294 338 L295 319 L275 273 L253 214Z"/>
        <path class="anatomy-line" d="M119 191L116 242M102 266L88 311M281 191L284 242M298 266L312 311"/>
      </g>
      <g data-region="abdomen" :class="{ selected: selected === 'abdomen' }" class="body-region"><path d="M153 246 Q163 277 154 311 Q144 342 159 364 Q177 375 200 367 Q223 375 241 364 Q256 342 246 311 Q237 277 247 246Z"/><path class="anatomy-line" d="M173 278Q200 286 227 278M174 306Q200 315 226 306M174 335L200 352L226 335"/><circle v-if="!back" cx="200" cy="308" r="2" fill="#93a6ad" stroke="none"/></g>
      <g data-region="chest" :class="{ selected: selected === 'chest' }" class="body-region"><path d="M179 120 L176 143 Q158 146 147 154 Q133 166 137 191 L153 246 Q199 259 247 246 L263 191 Q267 166 253 154 Q242 146 224 143 L221 120Z"/><path class="anatomy-line" :d="back ? 'M200 155V241M150 171L186 198L165 232M250 171L214 198L235 232' : 'M148 180Q173 170 198 182Q222 170 252 180M151 218Q173 233 198 218M202 218Q227 233 249 218M200 181V233'"/></g>
      <g data-region="head" :class="{ selected: selected === 'head' }" class="body-region"><ellipse cx="162" cy="85" rx="7" ry="14"/><ellipse cx="238" cy="85" rx="7" ry="14"/><path d="M163 70 Q161 26 200 25 Q239 26 237 70 L234 104 Q226 131 200 134 Q174 131 166 104Z"/><g v-if="!back" class="anatomy-line"><path d="M198 78L193 98Q200 102 206 98M188 114Q200 118 212 114M176 71Q184 67 191 71M209 71Q216 67 224 71"/></g></g>
      <g v-if="!back" data-region="eyes" class="body-region eye-region" :class="{ selected: selected === 'eyes' }"><rect x="166" y="70" width="68" height="24" rx="8" fill="transparent" stroke="none"/><ellipse cx="183" cy="82" rx="14" ry="10"/><ellipse cx="217" cy="82" rx="14" ry="10"/><path d="M173 82Q183 74 193 82Q183 89 173 82ZM207 82Q217 74 227 82Q217 89 207 82Z" fill="#f6ffff"/><circle cx="183" cy="81" r="3.7" fill="#568e99"/><circle cx="217" cy="81" r="3.7" fill="#568e99"/></g>
    </g>
  </svg>
</template>
