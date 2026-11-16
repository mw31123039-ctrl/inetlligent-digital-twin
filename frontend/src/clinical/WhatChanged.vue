<script setup lang="ts">
import { computed } from 'vue'
import { diffAssessments } from './diff'
import { translate, type StringKey } from './i18n'
import type { ClinicalAssessment, ClinicalLocale } from './types'

const props = defineProps<{ previous: ClinicalAssessment | null; next: ClinicalAssessment; locale: ClinicalLocale; heading?: string }>()
const t = (key: StringKey) => translate(props.locale, key)
const diff = computed(() => diffAssessments(props.previous, props.next))
const level = (value: string) => t(`lvl_${value}` as StringKey)
const fit = (value: string) => t(value as StringKey)
</script>

<template>
  <section v-if="previous" class="ct-panel ct-changes" :aria-label="t('what_changed')">
    <div class="ct-panel-head"><h3>{{ t('what_changed') }}</h3><span class="ct-muted ct-small">{{ heading ?? t('changed_since') }}</span></div>
    <p v-if="!diff.hasChanges" class="ct-muted">{{ t('no_changes') }}</p>
    <ul v-else class="ct-change-list">
      <li v-if="diff.urgency" class="urgency"><strong>{{ t('urgency_changed') }}:</strong> {{ level(diff.urgency.from) }} → {{ level(diff.urgency.to) }}</li>
      <li v-for="fact in diff.facts.added" :key="`a-${fact.id}`" class="added"><strong>{{ t('added') }}:</strong> {{ fact.label }}<span v-if="fact.status !== 'present'"> ({{ t(fact.status === 'absent' ? 'st_absent' : 'st_uncertain') }})</span></li>
      <li v-for="change in diff.facts.changed" :key="`c-${change.id}`" class="changed"><strong>{{ t('changed') }}:</strong> {{ change.label }} — {{ change.from }} → {{ change.to }}</li>
      <li v-for="fact in diff.facts.removed" :key="`r-${fact.id}`" class="removed"><strong>{{ t('removed') }}:</strong> {{ fact.label }}</li>
      <li v-for="item in diff.explanations.added" :key="`ea-${item.id}`" class="added"><strong>{{ t('explanation_added') }}:</strong> {{ item.name }} ({{ fit(item.fit) }})</li>
      <li v-for="item in diff.explanations.fitChanged" :key="`ef-${item.id}`" class="changed"><strong>{{ t('fit_changed') }}:</strong> {{ item.name }} — {{ fit(item.from) }} → {{ fit(item.to) }}</li>
      <li v-for="item in diff.explanations.removed" :key="`er-${item.id}`" class="removed"><strong>{{ t('explanation_removed') }}:</strong> {{ item.name }}</li>
      <li v-for="label in diff.missing.resolved" :key="`mr-${label}`" class="added"><strong>{{ t('missing_resolved') }}:</strong> {{ label }}</li>
      <li v-for="label in diff.missing.added" :key="`ma-${label}`" class="changed"><strong>{{ t('missing_new') }}:</strong> {{ label }}</li>
      <li v-for="text in diff.contradictions.added" :key="`ca-${text}`" class="removed"><strong>{{ t('contradiction_new') }}:</strong> {{ text }}</li>
      <li v-for="text in diff.contradictions.resolved" :key="`cr-${text}`" class="added"><strong>{{ t('contradiction_resolved') }}:</strong> {{ text }}</li>
    </ul>
  </section>
</template>
