<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { clinicalApi } from './api'
import { translate, type StringKey } from './i18n'
import type { ClinicalLocale, ExtractionResult, MemoryFact, MemoryKind, MemoryState } from './types'

const props = defineProps<{ locale: ClinicalLocale; refreshKey: number }>()
const emit = defineEmits<{ changed: [consented: boolean] }>()
const t = (key: StringKey, values: Record<string, string | number> = {}) => translate(props.locale, key, values)
const KINDS: MemoryKind[] = ['condition', 'medication', 'allergy', 'procedure', 'risk_factor']
const memory = ref<MemoryState | null>(null)
const busy = ref(false), error = ref(''), consent = ref(false), retention = ref(365)
const draft = reactive({ kind: 'medication' as MemoryKind, label: '', details: '' })
const editing = ref<string | null>(null), editLabel = ref('')
const extraction = ref<ExtractionResult | null>(null), uploading = ref(false)
const active = computed(() => (memory.value?.facts ?? []).filter(fact => fact.status === 'active' || fact.status === 'resolved'))
const pending = computed(() => (memory.value?.facts ?? []).filter(fact => fact.status === 'pending_confirmation'))
const corrected = computed(() => (memory.value?.facts ?? []).filter(fact => fact.status === 'corrected'))

async function run<T>(action: () => Promise<T>) {
  busy.value = true; error.value = ''
  try { return await action() } catch (e) { error.value = e instanceof Error ? e.message : t('error_generic'); return undefined } finally { busy.value = false }
}
async function load() { const result = await run(() => clinicalApi.memory()); if (result) { memory.value = result; emit('changed', !!result.consent) } }
async function grant() { if (!consent.value) return; await run(() => clinicalApi.grantMemory(retention.value)); consent.value = false; await load() }
async function revoke() { if (!window.confirm(t('revoke_confirm'))) return; await run(() => clinicalApi.revokeMemory()); extraction.value = null; await load() }
async function add() {
  if (!draft.label.trim()) return
  await run(() => clinicalApi.addFact({ kind: draft.kind, label: draft.label.trim(), details: draft.details.trim() || null }))
  draft.label = ''; draft.details = ''; await load()
}
function startEdit(fact: MemoryFact) { editing.value = fact.id; editLabel.value = fact.label }
async function saveEdit(fact: MemoryFact) { if (!editLabel.value.trim()) return; await run(() => clinicalApi.correctFact(fact.id, { label: editLabel.value.trim() })); editing.value = null; await load() }
async function remove(fact: MemoryFact) { if (!window.confirm(`${t('delete')}: ${fact.label}?`)) return; await run(() => clinicalApi.deleteFact(fact.id)); await load() }
async function decide(fact: MemoryFact, decision: 'confirm' | 'reject') { await run(() => clinicalApi.confirmFact(fact.id, decision)); await load() }
async function exportAll() {
  const data = await run(() => clinicalApi.exportMemory())
  if (!data) return
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a'); link.href = url; link.download = 'humantwin-patient-memory.json'; link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
async function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (file.size > 5 * 1024 * 1024 || !/\.(txt|pdf)$/i.test(file.name)) { error.value = `${t('unsupported')}: .txt / .pdf ≤ 5 MB`; return }
  uploading.value = true; error.value = ''
  try { extraction.value = await clinicalApi.upload(file); await load() } catch (e) { error.value = e instanceof Error ? e.message : t('error_generic') } finally { uploading.value = false }
}
const kindLabel = (kind: string) => t(`kind_${kind}` as StringKey)
const provenanceLabel = (value: string) => value === 'document_extract' ? t('prov_document_extract') : value === 'clinician_confirmed' ? t('prov_clinician_confirmed') : t('prov_patient_memory')
onMounted(load)
watch(() => props.refreshKey, load)
</script>

<template>
  <section class="ct-panel ct-memory" :aria-label="t('tab_memory')">
    <div class="ct-panel-head"><h2>{{ t('tab_memory') }}</h2>
      <div v-if="memory?.consent" class="ct-actions"><button type="button" class="button-secondary" :disabled="busy" @click="exportAll">{{ t('export') }}</button>
        <button type="button" class="ct-link danger" :disabled="busy" @click="revoke">{{ t('revoke') }}</button></div>
    </div>
    <p v-if="error" class="ct-error" role="alert">{{ error }}</p>
    <div v-if="memory && !memory.consent" class="ct-consent-box">
      <p>{{ t('memory_off') }}</p>
      <label class="ct-consent"><input v-model="consent" type="checkbox" />{{ t('memory_consent') }}</label>
      <label class="ct-inline">{{ t('retention') }} <select v-model.number="retention"><option v-for="days in [30, 90, 365, 730]" :key="days" :value="days">{{ t('days', { n: days }) }}</option></select></label>
      <button type="button" class="button-primary" :disabled="!consent || busy" @click="grant">{{ t('turn_on') }}</button>
    </div>
    <template v-else-if="memory?.consent">
      <p class="ct-muted ct-small">{{ t('retention') }}: {{ t('days', { n: memory.consent.retention_days }) }}</p>
      <ul class="ct-memory-list">
        <li v-for="fact in active" :key="fact.id">
          <span class="ct-badge neutral">{{ kindLabel(fact.kind) }}</span>
          <template v-if="editing === fact.id">
            <input v-model="editLabel" type="text" maxlength="200" :aria-label="t('label')" />
            <button type="button" class="button-primary" :disabled="busy" @click="saveEdit(fact)">{{ t('save_item') }}</button>
            <button type="button" class="ct-link" @click="editing = null">{{ t('cancel') }}</button>
          </template>
          <template v-else>
            <strong>{{ fact.label }}</strong><span v-if="fact.details" class="ct-muted"> — {{ fact.details }}</span>
            <span class="ct-badge prov">{{ provenanceLabel(fact.provenance) }}</span>
            <span v-if="fact.location" class="ct-muted ct-small">{{ t('from_page', { page: fact.location.page, line: fact.location.line }) }}</span>
            <button type="button" class="ct-link" :disabled="busy" @click="startEdit(fact)">{{ t('correct') }}</button>
            <button type="button" class="ct-link danger" :disabled="busy" @click="remove(fact)">{{ t('delete') }}</button>
          </template>
        </li>
      </ul>
      <form class="ct-add-fact" @submit.prevent="add">
        <select v-model="draft.kind" :aria-label="t('label')"><option v-for="kind in KINDS" :key="kind" :value="kind">{{ kindLabel(kind) }}</option></select>
        <input v-model="draft.label" type="text" maxlength="200" :placeholder="t('label')" :aria-label="t('label')" />
        <input v-model="draft.details" type="text" maxlength="500" :placeholder="t('details')" :aria-label="t('details')" />
        <button type="submit" class="button-secondary" :disabled="busy || !draft.label.trim()">{{ t('add') }}</button>
      </form>
      <div v-if="pending.length" class="ct-pending">
        <h3>{{ t('pending') }}</h3>
        <ul><li v-for="fact in pending" :key="fact.id">
          <span class="ct-badge neutral">{{ kindLabel(fact.kind) }}</span> <strong>{{ fact.label }}</strong>
          <span v-if="fact.location" class="ct-muted ct-small"> · {{ t('from_page', { page: fact.location.page, line: fact.location.line }) }} — “{{ fact.location.text }}”</span>
          <button type="button" class="button-primary" :disabled="busy" @click="decide(fact, 'confirm')">{{ t('confirm') }}</button>
          <button type="button" class="ct-link" :disabled="busy" @click="decide(fact, 'reject')">{{ t('reject') }}</button>
        </li></ul>
      </div>
      <details v-if="corrected.length"><summary>{{ t('corrected_history') }} ({{ corrected.length }})</summary>
        <ul><li v-for="fact in corrected" :key="fact.id"><s>{{ fact.label }}</s> <span class="ct-muted ct-small">{{ new Date(fact.updated_at).toLocaleDateString() }}</span></li></ul>
      </details>
    </template>
    <div class="ct-upload">
      <h3>{{ t('upload_title') }}</h3>
      <p class="ct-note">{{ t('upload_body') }}</p>
      <label class="button-secondary ct-file"><input type="file" accept=".txt,.pdf,text/plain,application/pdf" :disabled="uploading" @change="upload" />{{ uploading ? t('uploading') : t('choose_file') }}</label>
      <div v-if="extraction" class="ct-extraction" role="status">
        <p v-if="extraction.unsupported_reason" class="ct-error">{{ t('unsupported') }}: {{ extraction.unsupported_reason }}</p>
        <p v-if="extraction.injection_flags.length" class="ct-warn">{{ t('injection_warning') }} ({{ extraction.injection_flags.map(flag => t('from_page', { page: flag.page, line: flag.line })).join('; ') }})</p>
        <h4 v-if="extraction.items.length">{{ t('found_items') }}</h4>
        <ul><li v-for="item in extraction.items" :key="item.id"><strong>{{ item.label }}</strong>: {{ item.value }} <span class="ct-muted ct-small">· {{ t('from_page', { page: item.location.page, line: item.location.line }) }} · {{ item.certainty }}</span></li></ul>
        <p v-if="extraction.items.length && !extraction.stored_for_confirmation" class="ct-note">{{ t('not_stored') }}</p>
      </div>
    </div>
  </section>
</template>
