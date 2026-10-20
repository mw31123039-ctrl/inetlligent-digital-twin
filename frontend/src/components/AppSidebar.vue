<script setup lang="ts">
import type { Navigation } from '../types'
import AppIcon from './AppIcon.vue'
defineProps<{ active: Navigation; open: boolean; demo: boolean }>()
defineEmits<{ navigate: [page: Navigation]; close: [] }>()
const links: { label: Navigation; icon: string }[] = [{ label: 'Overview', icon: 'overview' }, { label: 'Body explorer', icon: 'body' }, { label: 'Assessments', icon: 'clipboard' }, { label: 'History', icon: 'history' }, { label: 'Settings', icon: 'settings' }]
</script>
<template>
  <button v-if="open" class="sidebar-scrim" aria-label="Close navigation" @click="$emit('close')"></button>
  <aside class="sidebar" :class="{ 'is-open': open }" aria-label="Main navigation">
    <div class="sidebar-eyebrow">YOUR WORKSPACE</div>
    <nav><button v-for="link in links" :key="link.label" class="nav-link" :aria-label="link.label" :title="link.label" :class="{ active: active === link.label }" :aria-current="active === link.label ? 'page' : undefined" @click="$emit('navigate', link.label)"><AppIcon :name="link.icon" :size="21" /><span>{{ link.label }}</span><span v-if="active === link.label" class="nav-dot"></span></button></nav>
    <div class="sidebar-bottom"><div class="demo-card"><span class="demo-symbol"><AppIcon name="shield" :size="21" /></span><strong>A guided space to explore</strong><p>{{ demo ? 'Explore the scripted questionnaire with mock inputs.' : 'AI symptom intake with explicit save consent. Clinical review is required.' }}</p><span class="local-note"><i></i> {{ demo ? 'Demo data stays in this browser' : 'AI processing may use an external provider' }}</span></div><div class="sidebar-version"><span>HumanTwin</span><span>v1.0 demo</span></div></div>
  </aside>
</template>
