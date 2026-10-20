<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Assessment } from '../types'
import { getRegion, regions } from '../data/regions'
import AppIcon from './AppIcon.vue'
const props = defineProps<{ assessments: Assessment[]; timeline?: boolean }>()
defineEmits<{ start: []; inspect: [assessment: Assessment]; remove: [id: string] }>()
const search = ref('')
const area = ref('all')
const filtered = computed(() => props.assessments.filter(a => (area.value === 'all' || a.region === area.value) && `${getRegion(a.region).label} ${a.answers.symptom} ${a.answers.location}`.toLowerCase().includes(search.value.toLowerCase())))
function date(value: string) { return new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) }
</script>
<template>
  <div class="history-toolbar"><div class="history-filters"><label class="sr-only" for="history-search">Search saved assessments</label><input id="history-search" v-model="search" class="text-input" placeholder="Search assessments…"/><label class="sr-only" for="area-filter">Filter by body area</label><select id="area-filter" v-model="area" class="text-input"><option value="all">All body areas</option><option v-for="region in regions" :key="region.id" :value="region.id">{{ region.label }}</option></select></div><span class="text-muted">{{ filtered.length }} {{ filtered.length === 1 ? 'assessment' : 'assessments' }}</span></div>
  <div v-if="!filtered.length" class="panel large-empty"><span class="empty-icon"><AppIcon :name="timeline ? 'history' : 'clipboard'" :size="34"/></span><h2>{{ assessments.length ? 'No matching assessments' : 'Your story starts here' }}</h2><p>{{ assessments.length ? 'Try another search or body area.' : 'Complete and save a demo assessment to see it here. Everything stays in this browser.' }}</p><button v-if="!assessments.length" class="button-primary" @click="$emit('start')">Start an assessment<AppIcon name="arrowRight" :size="17"/></button><button v-else class="button-secondary" @click="search = ''; area = 'all'">Clear filters</button></div>
  <div v-else class="saved-assessments" :class="{ timeline }"><article v-for="item in filtered" :key="item.id" class="panel saved-assessment"><span class="saved-icon"><AppIcon :name="item.region" :size="25"/></span><div class="saved-main"><span class="saved-date">{{ date(item.createdAt) }}</span><h2>{{ getRegion(item.region).label }} assessment</h2><p>{{ item.answers.symptom }} <span>· {{ item.answers.location }}</span></p></div><div class="saved-pain"><span>Pain level</span><strong>{{ item.pain }}<small>/10</small></strong></div><span class="status-badge complete"><AppIcon name="complete" :size="14"/>Complete</span><button class="button-secondary" @click="$emit('inspect', item)">View summary<AppIcon name="chevronRight" :size="15"/></button><button class="icon-button danger-hover" :aria-label="`Delete ${getRegion(item.region).label} assessment`" @click="$emit('remove', item.id)"><AppIcon name="trash" :size="17"/></button></article></div>
</template>
