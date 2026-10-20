<script setup lang="ts">
import type { AiChatState } from '../types/ai'
defineProps<{ state: AiChatState }>()
defineEmits<{ save: []; consent: [value: boolean] }>()
function exportSummary(text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }))
  const link = document.createElement('a'); link.href = url; link.download = 'humantwin-clinician-summary.txt'; link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
</script>
<template>
  <section v-if="state.envelope" class="panel ai-summary" aria-label="AI assessment summary">
    <div class="ai-summary-heading"><h2>Assessment summary</h2><span class="ai-urgency-chip" :class="state.envelope.assessment.urgency.level">{{ ({ not_established: 'Urgency not established', routine: 'Routine assessment', soon: 'Assessment soon', same_day: 'Urgent today', emergency: 'Emergency help now' })[state.envelope.assessment.urgency.level] }}</span></div>
    <div class="ai-summary-grid"><div><h3>User-reported facts</h3><p v-if="!state.envelope.assessment.facts.length">No symptoms recorded yet.</p><dl><div v-for="(fact, index) in state.envelope.assessment.facts" :key="index"><dt>{{ fact.field.replaceAll('_', ' ') }}</dt><dd>{{ fact.value }}</dd></div></dl></div><div><h3>Possible explanations · uncertain AI interpretation</h3><p v-if="!state.envelope.assessment.possible_explanations.length">No supported AI explanation is available. The cause remains uncertain.</p><article v-for="explanation in state.envelope.assessment.possible_explanations" :key="explanation.condition"><strong>{{ explanation.condition }} may be one possibility</strong><p>{{ explanation.interpretation }}</p><span class="ai-source-ids">Supporting references: {{ explanation.source_ids.join(', ') }}</span></article><h3>Recommended next action</h3><p>{{ state.envelope.assessment.recommended_next_action }}</p></div></div>
    <details class="ai-missing"><summary>Information still missing ({{ state.envelope.assessment.unanswered_questions.length }})</summary><ul><li v-for="item in state.envelope.assessment.unanswered_questions" :key="item">{{ item }}</li></ul><p>Examination findings and tests are not available in this chat.</p></details>
    <div v-if="state.envelope.assessment.supporting_sources.length" class="ai-sources"><h3>Retrieved medical sources</h3><article v-for="source in state.envelope.assessment.supporting_sources" :key="source.id"><a :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.title }} · NHS</a><span>{{ source.id }}</span><blockquote>{{ source.excerpt }}</blockquote></article></div>
    <ul class="ai-limitations"><li v-for="limitation in state.envelope.assessment.limitations" :key="limitation">{{ limitation }}</li></ul>
    <details><summary>Summary to share with a clinician</summary><pre class="ai-clinician-summary">{{ state.envelope.assessment.clinician_summary }}</pre><button class="button-secondary" @click="exportSummary(state.envelope.assessment.clinician_summary)">Download clinician summary</button></details>
    <div v-if="!state.readOnly" class="ai-save"><label class="ai-consent"><input type="checkbox" :checked="state.storageConsent" :disabled="state.pending || state.saved" @change="$emit('consent', ($event.target as HTMLInputElement).checked)" /><span>I consent to saving this conversation and assessment in my account, encrypted in the application database, until I delete it. Saving is optional.</span></label><button class="button-primary" :disabled="!state.storageConsent || state.pending || state.saved" @click="$emit('save')">{{ state.saved ? 'Saved with consent' : 'Save with consent' }}</button></div>
    <p class="ai-review-note">Triage rules {{ state.envelope.assessment.triage_rules_version }} · Not clinically validated. AI interpretations do not establish a diagnosis.</p>
  </section>
</template>
