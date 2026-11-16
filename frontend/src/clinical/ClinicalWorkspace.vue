<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppIcon from '../components/AppIcon.vue'
import { clinicalApi } from './api'
import { nodeLabel, regionOf } from './anatomy'
import AnatomyNavigator from './AnatomyNavigator.vue'
import AnatomyTwin3D, { type TwinMarker } from './AnatomyTwin3D.vue'
import AssessmentPanel from './AssessmentPanel.vue'
import ClinicianSummary from './ClinicianSummary.vue'
import { direction, locales, translate, type StringKey } from './i18n'
import InterviewPanel from './InterviewPanel.vue'
import MemoryPanel from './MemoryPanel.vue'
import TimelinePanel from './TimelinePanel.vue'
import { useClinicalSession } from './useClinicalSession'
import WhatChanged from './WhatChanged.vue'
import type { ClinicalLocale, SavedAssessmentDetail, SavedAssessmentSummary } from './types'
import './clinical.css'

const props = defineProps<{ user: { id: number; email: string } | null; reducedMotion: boolean }>()
const emit = defineEmits<{ 'sign-in': [] }>()
const session = useClinicalSession()
const { state, nodes, assessment, messages } = session
const t = (key: StringKey, values: Record<string, string | number> = {}) => translate(state.locale, key, values)
const tab = ref<'assess' | 'timeline' | 'memory' | 'coverage'>('assess')
const focusId = ref<string | null>(null)
const storageConsent = ref(false), linkPrevious = ref(false), timelineKey = ref(0), memoryKey = ref(0)
const memoryConsented = ref(false), latestSaved = ref<SavedAssessmentSummary | null>(null)
const rememberIds = ref<string[]>([]), remembered = ref(false), workspace = ref<HTMLElement>()

const started = computed(() => !!state.envelope || !!state.viewing)
const urgent = computed(() => assessment.value?.phase === 'urgent')
const canSave = computed(() => !!state.envelope && !state.viewing && state.envelope.messages.some(m => m.role === 'user'))
const rememberable = computed(() => (state.envelope?.assessment.patient_facts ?? []).filter(f => ['medication', 'allergy', 'history'].includes(f.kind) && f.status === 'present' && f.provenance === 'patient_answer'))
const markers = computed<TwinMarker[]>(() => {
  const refs = assessment.value?.anatomical_references
  if (refs?.length) return refs.filter(ref => nodes.value.get(ref.id)?.anchor).map(ref => ({ id: ref.id, role: ref.role, side: ref.side, label: ref.label }))
  const node = nodes.value.get(state.anatomyId)
  return node?.anchor ? [{ id: node.id, role: 'selected', side: state.side, label: nodeLabel(nodes.value, node.id, state.locale) }] : []
})
const focusRef = computed(() => assessment.value?.anatomical_references.find(ref => ref.id === focusId.value) ?? null)
const focusFacts = computed(() => (assessment.value?.patient_facts ?? []).filter(fact => focusRef.value?.fact_ids.includes(fact.id) && fact.extractor !== 'derived'))
const focusExplanations = computed(() => (assessment.value?.possible_explanations ?? []).filter(item => focusRef.value?.explanation_ids.includes(item.id)))
const coverage = computed(() => state.catalog?.coverage)

function chooseLocale(value: ClinicalLocale) { session.setLocale(value) }
function selectAnatomy(id: string) { if (!started.value) session.selectAnatomy(id); focusId.value = id }
async function start() {
  remembered.value = false; storageConsent.value = false
  if (await session.start()) focusId.value = state.anatomyId
}
async function answer(text: string, codes: string[], correctionId?: string) {
  remembered.value = false
  await session.answer(text, codes, correctionId)
}
async function save() {
  if (!storageConsent.value) return
  const id = await session.save(linkPrevious.value ? latestSaved.value?.id : null)
  if (id) { timelineKey.value++; storageConsent.value = false; rememberIds.value = rememberable.value.map(f => f.id); void loadLatest() }
}
async function remember() {
  if (!state.savedId || !rememberIds.value.length) return
  try { await clinicalApi.rememberFromAssessment(state.savedId, rememberIds.value); remembered.value = true; memoryKey.value++ } catch (error) { state.error = error instanceof Error ? error.message : t('error_generic') }
}
function restart() { session.reset(true); focusId.value = null; tab.value = 'assess' }
function openSaved(detail: SavedAssessmentDetail) {
  session.view(detail); state.anatomyId = detail.anatomy.id; state.side = detail.anatomy.side; focusId.value = detail.assessment.anatomy.id; tab.value = 'assess'
  workspace.value?.scrollIntoView({ behavior: props.reducedMotion ? 'auto' : 'smooth', block: 'start' })
}
async function loadLatest() {
  if (!props.user) { latestSaved.value = null; return }
  try {
    const list = (await clinicalApi.list()).assessments.sort((a, b) => b.created_at.localeCompare(a.created_at))
    latestSaved.value = list.find(item => regionOf(nodes.value, item.anatomy.id) === regionOf(nodes.value, state.anatomyId) && item.id !== state.savedId) ?? null
  } catch { latestSaved.value = null }
}
async function loadMemoryConsent() {
  if (!props.user) { memoryConsented.value = false; return }
  try { memoryConsented.value = !!(await clinicalApi.memory()).consent } catch { memoryConsented.value = false }
}
watch(() => assessment.value?.anatomy.id, id => { if (id && !focusId.value) focusId.value = id })
watch(() => [state.anatomyId, props.user?.id] as const, () => { void loadLatest() })
onMounted(async () => { await session.init(); void loadLatest(); void loadMemoryConsent() })
onBeforeUnmount(session.dispose)
</script>

<template>
  <div ref="workspace" class="clinical-workspace" :dir="direction(state.locale)" :lang="state.locale">
    <header class="ct-header">
      <div>
        <h2 class="ct-title"><AppIcon name="sparkles" :size="22" />{{ t('title') }}</h2>
        <p class="ct-muted">{{ t('subtitle') }}</p>
      </div>
      <div class="ct-header-actions">
        <span class="ct-badge warn">{{ t('draft_notice') }}</span>
        <label class="ct-inline">{{ t('language') }}
          <select :value="state.locale" @change="chooseLocale(($event.target as HTMLSelectElement).value as ClinicalLocale)">
            <option v-for="item in locales" :key="item.id" :value="item.id">{{ item.label }}</option>
          </select>
        </label>
      </div>
    </header>
    <p class="ct-emergency" role="note"><AppIcon name="error" :size="18" />{{ t('emergency_notice') }}</p>
    <p v-if="state.status && !state.status.available" class="ct-warn" role="status">{{ t('service_down') }}</p>
    <p v-else-if="state.status" class="ct-muted ct-small">{{ state.status.language_model_configured ? t('lm_on') : t('lm_off') }}</p>

    <nav class="ct-tabs ct-main-tabs" role="tablist" :aria-label="t('title')">
      <button v-for="name in (['assess', 'timeline', 'memory', 'coverage'] as const)" :key="name" type="button" role="tab" :aria-selected="tab === name" @click="tab = name">{{ t(`tab_${name}` as StringKey) }}</button>
    </nav>

    <div v-show="tab === 'assess'" class="ct-grid">
      <div class="ct-col ct-col-anatomy">
        <AnatomyNavigator v-if="state.catalog" :catalog="state.catalog" :nodes="nodes" :selected-id="state.anatomyId" :side="state.side" :locale="state.locale" :locked="started"
          @select="selectAnatomy" @side="state.side = $event" />
        <p v-else-if="state.catalogError" class="ct-error" role="alert">{{ state.catalogError }} <button type="button" class="ct-link" @click="session.init()">{{ t('retry') }}</button></p>
        <p v-else role="status">{{ t('loading') }}</p>
        <AnatomyTwin3D v-if="state.catalog" :nodes="nodes" :markers="markers" :focus-id="focusId" :reduced-motion="reducedMotion" :locale="state.locale" @select="focusId = $event" />
        <section v-if="focusRef" class="ct-panel ct-focus" aria-live="polite">
          <div class="ct-panel-head"><h3>{{ focusRef.label }}</h3><span class="ct-badge neutral">{{ t(`role_${focusRef.role}` as StringKey) }}</span></div>
          <p v-if="focusRef.relation_note" class="ct-note">{{ focusRef.relation_note }}</p>
          <template v-if="focusFacts.length"><h4>{{ t('related_facts') }}</h4><ul><li v-for="fact in focusFacts" :key="fact.id">{{ fact.label }}<span v-if="fact.status !== 'present'" class="ct-muted"> ({{ t(fact.status === 'absent' ? 'st_absent' : 'st_uncertain') }})</span></li></ul></template>
          <template v-if="focusExplanations.length"><h4>{{ t('related_explanations') }}</h4><ul><li v-for="item in focusExplanations" :key="item.id">{{ item.name }} — {{ t(item.fit) }}</li></ul></template>
          <p v-if="!focusFacts.length && !focusExplanations.length" class="ct-muted">{{ t('nothing_linked') }}</p>
          <p class="ct-small ct-muted">{{ t('marker_note') }}</p>
        </section>
      </div>

      <div class="ct-col ct-col-interview">
        <div v-if="state.viewing" class="ct-viewing" role="status">{{ t('viewing_saved') }} <button type="button" class="ct-link" @click="session.view(null)">{{ t('back_live') }}</button></div>
        <section v-if="!user" class="ct-panel ct-signin">
          <h2>{{ t('sign_in_title') }}</h2><p>{{ t('sign_in_body') }}</p>
          <button type="button" class="button-primary" @click="emit('sign-in')">{{ t('sign_in') }}</button>
        </section>
        <section v-else-if="!started" class="ct-panel ct-start">
          <h2>{{ nodeLabel(nodes, state.anatomyId, state.locale) }}<span v-if="state.side !== 'unknown' && state.side !== 'midline'" class="ct-muted"> · {{ t(`side_${state.side}` as StringKey) }}</span></h2>
          <label class="ct-consent"><input v-model="state.processingAck" type="checkbox" />{{ t('ack') }}</label>
          <label v-if="memoryConsented" class="ct-consent"><input v-model="state.useMemory" type="checkbox" />{{ t('use_memory') }}</label>
          <button type="button" class="button-primary" :disabled="!state.processingAck || state.pending || !state.status?.available" @click="start">{{ state.pending ? t('starting') : t('start') }}</button>
        </section>
        <InterviewPanel v-if="started" :messages="messages" :assessment="assessment" :pending="state.pending" :stages="state.stages" :locale="state.locale" :read-only="!!state.viewing" @answer="answer" />
        <p v-if="state.error" class="ct-error" role="alert">{{ state.error }}</p>
        <p v-if="state.notice" class="ct-warn" role="status">{{ state.notice }}</p>
        <button v-if="started" type="button" class="button-secondary ct-restart" :disabled="state.pending" @click="restart"><AppIcon name="reset" :size="16" />{{ t('restart') }}</button>
      </div>

      <div v-if="assessment && assessment.phase !== 'complaint'" class="ct-col ct-col-result">
        <WhatChanged v-if="!state.viewing" :previous="state.previous" :next="assessment" :locale="state.locale" />
        <AssessmentPanel :assessment="assessment" :locale="state.locale" :nodes="nodes" :reduced-motion="reducedMotion" @focus="focusId = $event" />
        <ClinicianSummary :assessment="assessment" :locale="state.locale" />
        <section v-if="canSave" class="ct-panel ct-save">
          <h3>{{ t('save_title') }}</h3>
          <template v-if="!state.savedId">
            <label class="ct-consent"><input v-model="storageConsent" type="checkbox" />{{ t('save_consent') }}</label>
            <label v-if="latestSaved" class="ct-consent"><input v-model="linkPrevious" type="checkbox" />{{ t('link_previous') }}</label>
            <button type="button" class="button-primary" :disabled="!storageConsent || state.pending" @click="save">{{ t('save') }}</button>
            <p class="ct-note ct-small">{{ t('save_recomputed') }}</p>
          </template>
          <template v-else>
            <p class="ct-ok" role="status"><AppIcon name="complete" :size="18" />{{ t('saved') }}</p>
            <div v-if="memoryConsented && rememberable.length && !remembered" class="ct-remember">
              <h4>{{ t('remember_title') }}</h4><p class="ct-note">{{ t('remember_body') }}</p>
              <label v-for="fact in rememberable" :key="fact.id" class="ct-consent"><input v-model="rememberIds" type="checkbox" :value="fact.id" />{{ fact.label }}</label>
              <button type="button" class="button-secondary" :disabled="!rememberIds.length" @click="remember">{{ t('remember') }}</button>
            </div>
            <p v-if="remembered" class="ct-ok" role="status">{{ t('remembered') }}</p>
          </template>
        </section>
        <p v-if="urgent" class="ct-note">{{ t('urgent_stop') }}</p>
      </div>
    </div>

    <TimelinePanel v-if="tab === 'timeline' && user" :locale="state.locale" :refresh-key="timelineKey" @open="openSaved" />
    <MemoryPanel v-if="tab === 'memory' && user" :locale="state.locale" :refresh-key="memoryKey" @changed="memoryConsented = $event" />
    <section v-if="(tab === 'timeline' || tab === 'memory') && !user" class="ct-panel ct-signin">
      <h2>{{ t('sign_in_title') }}</h2><button type="button" class="button-primary" @click="emit('sign-in')">{{ t('sign_in') }}</button>
    </section>
    <section v-if="tab === 'coverage' && coverage" class="ct-panel ct-coverage">
      <h2>{{ t('coverage_title') }}</h2>
      <p>{{ t('coverage_counts', { conditions: coverage.conditions, flags: coverage.red_flags, sources: coverage.sources }) }}</p>
      <p class="ct-muted ct-small" dir="ltr">{{ coverage.snapshot_version }} · {{ coverage.clinical_review_status }}</p>
      <h3>{{ t('by_region') }}</h3>
      <div class="ct-coverage-grid">
        <div v-for="(items, region) in coverage.by_region" :key="region"><h4>{{ nodeLabel(nodes, String(region), state.locale) }}</h4>
          <ul><li v-for="item in items" :key="item.id">{{ item.name[state.locale] }}<span v-if="item.urgent_condition" class="ct-badge danger">{{ t('urgent_condition') }}</span></li></ul></div>
      </div>
      <h3>{{ t('known_gaps') }}</h3><ul dir="ltr"><li v-for="gap in coverage.known_gaps" :key="gap">{{ gap }}</li></ul>
      <template v-if="coverage.sources_review_overdue.length"><h3>{{ t('overdue_sources') }}</h3><p dir="ltr" class="ct-small">{{ coverage.sources_review_overdue.join(', ') }}</p></template>
    </section>
  </div>
</template>
