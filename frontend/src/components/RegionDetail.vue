<script setup lang="ts">
import type { RegionId } from '../types'
import AppIcon from './AppIcon.vue'
import { getRegion } from '../data/regions'
defineProps<{ region: RegionId }>()
</script>
<template>
  <div class="region-detail" aria-hidden="true">
    <div class="detail-circle">
      <svg v-if="region === 'eyes'" viewBox="0 0 180 180"><defs><radialGradient id="face"><stop stop-color="#eef5f5"/><stop offset="1" stop-color="#bacacc"/></radialGradient><radialGradient id="glow"><stop stop-color="#54cbd1" stop-opacity=".65"/><stop offset="1" stop-color="#54cbd1" stop-opacity="0"/></radialGradient><radialGradient id="iris"><stop offset=".3" stop-color="#174751"/><stop offset=".4" stop-color="#5ca3aa"/><stop offset=".85" stop-color="#85b8bb"/><stop offset="1" stop-color="#436c76"/></radialGradient></defs><path d="M16 0H180V180H-8Q43 147 31 102Q13 63 16 0" fill="url(#face)"/><path d="M45 24Q87 29 139 19L153 52Q99 45 64 66L57 117Q43 141 25 139L42 126L32 114Z" fill="#a9bfc2" opacity=".35"/><ellipse cx="110" cy="86" rx="78" ry="66" fill="url(#glow)"/><path d="M59 71Q99 45 148 68" fill="none" stroke="#758e92" stroke-width="5" stroke-linecap="round" opacity=".6"/><path d="M53 91Q99 52 151 86Q108 120 53 91" fill="#eaf5f3" stroke="#74969b" stroke-width="2"/><ellipse cx="104" cy="87" rx="21" ry="22" fill="url(#iris)"/><ellipse cx="104" cy="87" rx="9" ry="12" fill="#224950"/><circle cx="111" cy="79" r="5" fill="white" opacity=".9"/><path d="M53 91Q99 52 151 86" fill="none" stroke="#537d84" stroke-width="3"/><path d="M54 99Q98 127 149 97" fill="none" stroke="#9ebbbd" stroke-width="2"/><path d="M35 102Q22 122 21 145Q35 152 43 143" fill="none" stroke="#a0b5ba" stroke-width="3"/></svg>
      <div v-else class="detail-symbol"><AppIcon :name="region" :size="66"/><span>{{ getRegion(region).label }}</span></div>
    </div>
    <span class="detail-caption">{{ region === 'eyes' ? 'Eye region' : getRegion(region).description }}</span>
  </div>
</template>
