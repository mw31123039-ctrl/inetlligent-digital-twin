<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import AppIcon from '../components/AppIcon.vue'
import { nodeLabel } from './anatomy'
import { translate, type StringKey } from './i18n'
import SourceCard from './SourceCard.vue'
import type { AnatomyNode, ClinicalAssessment, ClinicalLocale, EvidenceItem } from './types'

const props = defineProps<{ assessment: ClinicalAssessment; locale: ClinicalLocale; nodes: Map<string, AnatomyNode>; reducedMotion: boolean }>()
const emit = defineEmits<{ focus: [id: string] }>()
const t = (key: StringKey, values: Record<string, string | number> = {}) => translate(props.locale, key, values)
const openCitation = ref<string | null>(null)
const tabs = ref<Record<string, 'supporting' | 'conflicting' | 'missing'>>({})
const revealed = ref(props.assessment.summary.length)
let timer: number | undefined

const citations = computed(() => new Map(props.assessment.citations.map(citation => [citation.id, citation])))
const facts = computed(() => props.assessment.patient_facts.filter(fact => fact.extractor !== 'derived' && fact.kind !== 'screen'))
const screenFacts = computed(() => props.assessment.patient_facts.filter(fact => fact.kind === 'screen'))
const factLabels = computed(() => new Map(props.assessment.patient_facts.map(fact => [fact.id, fact.label])))
const openContradictions = computed(() => props.assessment.contradictions.filter(item => !item.resolved))
const selectedCitation = computed(() => openCitation.value ? citations.value.get(openCitation.value) ?? null : null)

// The summary is only revealed after the whole envelope passed server-side validation.
watch(() => props.assessment.summary, summary => {
  window.clearInterval(timer)
  const reduce = props.reducedMotion || window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduce) { revealed.value = summary.length; return }
  revealed.value = 0
  timer = window.setInterval(() => { revealed.value = Math.min(summary.length, revealed.value + 4); if (revealed.value >= summary.length) window.clearInterval(timer) }, 16)
})
onBeforeUnmount(() => window.clearInterval(timer))

function tab(id: string) { return tabs.value[id] ?? 'supporting' }
function itemFacts(item: EvidenceItem) { return item.fact_ids.map(id => factLabels.value.get(id)).filter(Boolean).join(', ') }
function toggleCitation(id: string) { openCitation.value = openCitation.value === id ? null : id }
</script>

<template>
  <section class="ct-panel ct-assessment" :aria-label="t('tab_assess')">
    <div class="ct-summary-card">
      <div class="ct-panel-head"><h2>{{ t('summary') }}</h2><span class="ct-badge">{{ assessment.phase.replace('_', ' ') }}</span></div>
      <p class="ct-summary-text" aria-live="polite">{{ assessment.summary.slice(0, revealed) }}<span v-if="revealed < assessment.summary.length" class="ct-caret" aria-hidden="true"></span></p>
      <p class="ct-note ct-small">{{ t('revealing') }}</p>
    </div>

    <div class="ct-urgency-card" :class="assessment.urgency.level">
      <div class="ct-panel-head"><h3>{{ t('urgency') }}</h3><span class="ct-level" :class="assessment.urgency.level">{{ t(`lvl_${assessment.urgency.level}` as StringKey) }}</span></div>
      <p class="ct-pathway"><strong>{{ assessment.urgency.pathway_label }}</strong></p>
      <p>{{ assessment.urgency.action }}</p>
      <ul v-if="assessment.urgency.reasons.length" class="ct-reasons" :aria-label="t('reasons')">
        <li v-for="reason in assessment.urgency.reasons" :key="reason.rule_id">{{ reason.text }}
          <button v-for="id in reason.citation_ids" :key="id" type="button" class="ct-cite" :aria-expanded="openCitation === id" @click="toggleCitation(id)">{{ id }}</button>
        </li>
      </ul>
      <p class="ct-small"><span :class="['ct-badge', assessment.urgency.safety_screen_completed ? 'ok' : 'warn']">{{ assessment.urgency.safety_screen_completed ? t('screen_done') : t('screen_pending') }}</span>
        <span v-if="assessment.urgency.persisted_from_prior" class="ct-badge warn">{{ t('persisted') }}</span></p>
    </div>

    <SourceCard v-if="selectedCitation" :citation="selectedCitation" :locale="locale" @close="openCitation = null" />

    <div class="ct-explanations">
      <h3>{{ t('explanations') }}</h3>
      <p class="ct-note">{{ t('not_diagnosis') }}</p>
      <p v-if="assessment.explanation_status !== 'supported'" class="ct-status" role="status">{{ t(`status_${assessment.explanation_status}` as StringKey) }}</p>
      <article v-for="explanation in assessment.possible_explanations" :key="explanation.id" class="ct-explanation">
        <header>
          <strong>{{ explanation.name }}</strong>
          <span :class="['ct-badge', explanation.fit === 'fits' ? 'ok' : 'neutral']">{{ t(explanation.fit) }}</span>
          <span v-if="explanation.urgent_condition" class="ct-badge danger">{{ t('urgent_condition') }}</span>
        </header>
        <p>{{ explanation.plain_language }}</p>
        <p v-if="explanation.scope_note" class="ct-note">{{ explanation.scope_note }}</p>
        <p class="ct-small"><AppIcon name="arrowRight" :size="14" /> {{ explanation.pathway_label }}</p>
        <div class="ct-tabs" role="tablist" :aria-label="explanation.name">
          <button v-for="name in (['supporting', 'conflicting', 'missing'] as const)" :key="name" type="button" role="tab" :aria-selected="tab(explanation.id) === name" @click="tabs[explanation.id] = name">
            {{ t(name) }} <span class="ct-count">{{ name === 'missing' ? explanation.missing.length : explanation[name].length }}</span>
          </button>
        </div>
        <div role="tabpanel" class="ct-tab-panel">
          <ul v-if="tab(explanation.id) !== 'missing'">
            <li v-for="(item, index) in explanation[tab(explanation.id) as 'supporting' | 'conflicting']" :key="index" :class="tab(explanation.id)">
              {{ item.statement }}
              <small v-if="itemFacts(item)" class="ct-muted"> ({{ itemFacts(item) }})</small>
              <button v-for="id in item.citation_ids" :key="id" type="button" class="ct-cite" :aria-expanded="openCitation === id" @click="toggleCitation(id)">{{ id }}</button>
            </li>
            <li v-if="tab(explanation.id) === 'conflicting' && !explanation.conflicting.length" class="ct-muted">{{ t('none_conflicting') }}</li>
          </ul>
          <ul v-else>
            <li v-for="item in explanation.missing" :key="item.key">{{ item.label }}</li>
            <li v-if="!explanation.missing.length" class="ct-muted">{{ t('none_missing') }}</li>
          </ul>
        </div>
        <div class="ct-chip-row">
          <button v-for="id in explanation.anatomy_ids" :key="id" type="button" class="ct-chip small" @click="emit('focus', id)">{{ nodeLabel(nodes, id, locale) }}</button>
        </div>
      </article>
    </div>

    <div class="ct-facts">
      <h3>{{ t('facts') }}</h3>
      <ul>
        <li v-for="fact in facts" :key="fact.id" :class="fact.status">
          <span class="ct-fact-label">{{ fact.label }}</span>
          <span v-if="fact.status !== 'present'" class="ct-badge neutral">{{ t(fact.status === 'absent' ? 'st_absent' : 'st_uncertain') }}</span>
          <span v-if="fact.temporal === 'past'" class="ct-badge neutral">{{ t('past') }}</span>
          <span class="ct-badge prov">{{ t(`prov_${fact.provenance}` as StringKey) }}</span>
          <q v-if="fact.spans[0]?.quote && fact.provenance === 'patient_statement'" class="ct-quote">{{ fact.spans[0].quote }}</q>
          <button v-if="fact.anatomy_id" type="button" class="ct-link" @click="emit('focus', fact.anatomy_id)">{{ nodeLabel(nodes, fact.anatomy_id, locale) }}</button>
        </li>
      </ul>
      <details v-if="screenFacts.length" class="ct-screen"><summary>{{ t('screen_done') }} ({{ screenFacts.length }})</summary>
        <ul><li v-for="fact in screenFacts" :key="fact.id">{{ fact.label }} — {{ fact.status === 'present' ? '✓' : t('st_absent') }}</li></ul>
      </details>
    </div>

    <div v-if="assessment.observations.length" class="ct-observations">
      <h3>{{ t('observations') }}</h3>
      <ul><li v-for="item in assessment.observations" :key="item.id">{{ item.text }}</li></ul>
    </div>

    <div v-if="openContradictions.length" class="ct-contradictions" role="status">
      <h3>{{ t('contradictions') }}</h3>
      <ul><li v-for="item in openContradictions" :key="item.id">{{ item.description }}</li></ul>
    </div>

    <details v-if="assessment.missing_information.length" class="ct-missing" open>
      <summary>{{ t('missing_info') }} ({{ assessment.missing_information.length }})</summary>
      <ul><li v-for="item in assessment.missing_information" :key="item.key" :class="item.priority"><strong>{{ item.label }}</strong> — <span class="ct-muted">{{ item.reason }}</span></li></ul>
    </details>

    <div v-if="assessment.related_reading.length" class="ct-related">
      <h3>{{ t('related') }}</h3>
      <ul><li v-for="id in assessment.related_reading" :key="id"><button type="button" class="ct-link" @click="toggleCitation(id)">{{ citations.get(id)?.title }} · {{ citations.get(id)?.publisher }}</button></li></ul>
    </div>

    <details class="ct-limitations"><summary>{{ t('limitations') }}</summary><ul><li v-for="item in assessment.limitations" :key="item">{{ item }}</li></ul></details>
    <details class="ct-versions"><summary>{{ t('versions') }}</summary>
      <dl dir="ltr"><div v-for="(value, key) in assessment.versions" :key="key"><dt>{{ key }}</dt><dd>{{ value ?? '—' }}</dd></div>
        <div><dt>engine_ms</dt><dd>{{ assessment.processing.engine_ms }}</dd></div><div><dt>retrieval</dt><dd>{{ assessment.processing.retrieval }}</dd></div>
        <div><dt>external_requests</dt><dd>{{ assessment.processing.external_requests }}</dd></div></dl>
    </details>
    <p class="ct-disclaimer">{{ assessment.disclaimer }}</p>
  </section>
</template>
