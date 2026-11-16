<script setup lang="ts">
import { computed, ref } from 'vue'
import { translate, type StringKey } from './i18n'
import type { ClinicalAssessment, ClinicalLocale } from './types'

const props = defineProps<{ assessment: ClinicalAssessment; locale: ClinicalLocale }>()
const t = (key: StringKey) => translate(props.locale, key)
const copied = ref(false)
const summary = computed(() => props.assessment.clinician_summary)
const text = computed(() => {
  const s = summary.value, v = props.assessment.versions
  const block = (title: string, items: string[]) => items.length ? [title, ...items.map(item => `  - ${item}`), ''] : []
  return [
    'HUMANTWIN CLINICAL SUMMARY (draft decision support; not a diagnosis; not clinically validated)', s.headline, '',
    ...block('PATIENT-REPORTED (not verified):', s.patient_reported), ...block('FROM RECORDS:', s.from_records),
    `OBSERVATIONS: ${s.observations_note}`, '', ...block('AI INTERPRETATIONS (suggestions, not diagnoses):', s.interpretations),
    `URGENCY: ${s.urgency}`, '', ...block('MISSING:', s.missing), ...block('CONTRADICTIONS:', s.contradictions),
    `PROVENANCE: ${s.provenance_note}`, `VERSIONS: engine ${v.engine}; knowledge ${v.knowledge}; snapshot ${v.snapshot}; anatomy ${v.anatomy}; language model ${v.language_model ?? 'none'}`,
  ].join('\n')
})
async function copy() {
  try { await navigator.clipboard.writeText(text.value); copied.value = true; window.setTimeout(() => { copied.value = false }, 2000) } catch { copied.value = false }
}
function download() {
  const url = URL.createObjectURL(new Blob([text.value], { type: 'text/plain;charset=utf-8' }))
  const link = document.createElement('a'); link.href = url; link.download = 'humantwin-clinician-summary.txt'; link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
</script>

<template>
  <details class="ct-panel ct-clinician">
    <summary><h3>{{ t('clinician') }}</h3></summary>
    <p class="ct-note">{{ t('clinician_note') }}</p>
    <div dir="ltr" lang="en" class="ct-clinician-body">
      <p><strong>{{ summary.headline }}</strong></p>
      <h4>Patient-reported (not verified)</h4><ul><li v-for="item in summary.patient_reported" :key="item">{{ item }}</li></ul>
      <template v-if="summary.from_records.length"><h4>From records</h4><ul><li v-for="item in summary.from_records" :key="item">{{ item }}</li></ul></template>
      <h4>Observations</h4><p>{{ summary.observations_note }}</p>
      <h4>AI interpretations (suggestions, not diagnoses)</h4><ul><li v-for="item in summary.interpretations" :key="item">{{ item }}</li></ul>
      <h4>Urgency</h4><p>{{ summary.urgency }}</p>
      <template v-if="summary.missing.length"><h4>Missing</h4><p>{{ summary.missing.join(', ') }}</p></template>
      <template v-if="summary.contradictions.length"><h4>Contradictions</h4><ul><li v-for="item in summary.contradictions" :key="item">{{ item }}</li></ul></template>
      <p class="ct-small ct-muted">{{ summary.provenance_note }}</p>
    </div>
    <div class="ct-actions">
      <button type="button" class="button-secondary" @click="copy">{{ copied ? t('copied') : t('copy') }}</button>
      <button type="button" class="button-secondary" @click="download">{{ t('download') }}</button>
    </div>
  </details>
</template>
