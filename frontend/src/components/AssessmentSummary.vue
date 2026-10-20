<script setup lang="ts">
import type { Answers, RegionId } from '../types'
import { getRegion } from '../data/regions'
import AppIcon from './AppIcon.vue'
defineProps<{ region: RegionId | null; answers: Answers; pain: number; complete: boolean; saved: boolean; pending: boolean; consent: boolean }>()
defineEmits<{ save: []; export: [] }>()
</script>
<template>
  <section class="panel assessment-summary" aria-label="Assessment summary" aria-live="polite">
    <div class="summary-title"><span><AppIcon name="clipboard" :size="25"/></span><h2>Assessment summary</h2></div>
    <div class="summary-cell"><span class="summary-label">Body area</span><strong v-if="region" class="summary-area"><AppIcon :name="region" :size="18"/>{{ getRegion(region).label }}<span v-if="answers.location" class="summary-detail">· {{ answers.location }}</span></strong><span v-else class="text-muted">No area selected</span></div>
    <div class="summary-cell symptom-cell"><span class="summary-label">Symptoms</span><span class="summary-symptom">{{ answers.symptom || 'Waiting for your answers' }}</span><span v-if="answers.symptom" class="summary-detail">Pain {{ pain }}/10<span v-if="answers.onset"> · {{ answers.onset }}</span><span v-if="answers.character"> · {{ answers.character }}</span></span></div>
    <div class="summary-cell status-cell"><span class="summary-label">Status</span><span class="status-badge" :class="{ complete }"><AppIcon :name="complete ? 'complete' : 'clock'" :size="14"/>{{ complete ? 'Complete' : region ? 'In progress' : 'Not started' }}</span></div>
    <div v-if="complete" class="summary-actions"><button class="button-primary" :disabled="saved || pending || !consent" @click="$emit('save')"><AppIcon :name="saved ? 'check' : 'clipboard'" :size="16"/>{{ saved ? 'Saved' : 'Save' }}</button><button class="icon-button" aria-label="Export assessment as JSON" :disabled="pending" @click="$emit('export')"><AppIcon name="download" :size="18"/></button></div>
  </section>
</template>
