<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { clinicalApi } from './api'
import { translate, type StringKey } from './i18n'
import WhatChanged from './WhatChanged.vue'
import type { ClinicalLocale, SavedAssessmentDetail, SavedAssessmentSummary } from './types'

const props = defineProps<{ locale: ClinicalLocale; refreshKey: number }>()
const emit = defineEmits<{ open: [detail: SavedAssessmentDetail] }>()
const t = (key: StringKey) => translate(props.locale, key)
const items = ref<SavedAssessmentSummary[]>([])
const loading = ref(false), error = ref('')
const picked = ref<string[]>([])
const comparison = ref<{ older: SavedAssessmentDetail; newer: SavedAssessmentDetail } | null>(null)
const sharing = ref<string | null>(null), shareConsent = ref(false)
const sorted = computed(() => [...items.value].sort((a, b) => b.created_at.localeCompare(a.created_at)))
const date = (value: string) => new Date(value).toLocaleString(props.locale === 'en' ? 'en-GB' : props.locale === 'ar' ? 'ar-IQ' : 'ckb-IQ', { dateStyle: 'medium', timeStyle: 'short' })

async function load() {
  loading.value = true; error.value = ''
  try { items.value = (await clinicalApi.list()).assessments } catch (e) { error.value = e instanceof Error ? e.message : t('error_generic') } finally { loading.value = false }
}
function togglePick(id: string) {
  picked.value = picked.value.includes(id) ? picked.value.filter(item => item !== id) : [...picked.value, id].slice(-2)
}
async function compare() {
  if (picked.value.length !== 2) return
  error.value = ''
  try {
    const [a, b] = await Promise.all(picked.value.map(id => clinicalApi.show(id)))
    comparison.value = a!.created_at <= b!.created_at ? { older: a!, newer: b! } : { older: b!, newer: a! }
  } catch (e) { error.value = e instanceof Error ? e.message : t('error_generic') }
}
async function open(id: string) {
  try { emit('open', await clinicalApi.show(id)) } catch (e) { error.value = e instanceof Error ? e.message : t('error_generic') }
}
async function remove(id: string) {
  if (!window.confirm(`${t('delete')}?`)) return
  try { await clinicalApi.remove(id); items.value = items.value.filter(item => item.id !== id); picked.value = picked.value.filter(item => item !== id); comparison.value = null }
  catch (e) { error.value = e instanceof Error ? e.message : t('error_generic') }
}
async function share(item: SavedAssessmentSummary) {
  try {
    if (item.review_shared) await clinicalApi.unshare(item.id)
    else { if (!shareConsent.value) return; await clinicalApi.share(item.id) }
    item.review_shared = !item.review_shared; sharing.value = null; shareConsent.value = false
  } catch (e) { error.value = e instanceof Error ? e.message : t('error_generic') }
}
onMounted(load)
watch(() => props.refreshKey, load)
</script>

<template>
  <section class="ct-panel ct-timeline" :aria-label="t('timeline')">
    <div class="ct-panel-head"><h2>{{ t('timeline') }}</h2><button type="button" class="button-secondary" :disabled="loading" @click="load">{{ t('refresh') }}</button></div>
    <p v-if="error" class="ct-error" role="alert">{{ error }}</p>
    <p v-if="loading" role="status">{{ t('loading') }}</p>
    <p v-else-if="!items.length" class="ct-muted">{{ t('no_saved') }}</p>
    <template v-else>
      <p class="ct-note">{{ t('pick_two') }}</p>
      <ol class="ct-timeline-list">
        <li v-for="item in sorted" :key="item.id" :class="item.urgency">
          <label class="ct-pick"><input type="checkbox" :checked="picked.includes(item.id)" @change="togglePick(item.id)" /><span class="sr-only">{{ t('compare') }}</span></label>
          <div class="ct-timeline-main">
            <strong>{{ item.anatomy_label }}</strong> <span class="ct-level" :class="item.urgency">{{ t(`lvl_${item.urgency}` as StringKey) }}</span>
            <p class="ct-muted ct-small">{{ date(item.created_at) }} · {{ item.pathway_label }}</p>
            <p v-if="item.explanations.length" class="ct-small">{{ item.explanations.map(e => e.name).join(' · ') }}</p>
            <div v-if="sharing === item.id" class="ct-share">
              <label class="ct-consent"><input v-model="shareConsent" type="checkbox" />{{ t('share_consent') }}</label>
              <button type="button" class="button-primary" :disabled="!shareConsent" @click="share(item)">{{ t('share_review') }}</button>
              <button type="button" class="ct-link" @click="sharing = null">{{ t('cancel') }}</button>
            </div>
          </div>
          <div class="ct-actions">
            <button type="button" class="button-secondary" @click="open(item.id)">{{ t('open') }}</button>
            <button v-if="item.review_shared" type="button" class="ct-link" @click="share(item)">{{ t('unshare') }}</button>
            <button v-else type="button" class="ct-link" @click="sharing = item.id">{{ t('share_review') }}</button>
            <span v-if="item.review_shared" class="ct-badge ok">{{ t('shared') }}</span>
            <button type="button" class="ct-link danger" @click="remove(item.id)">{{ t('delete') }}</button>
          </div>
        </li>
      </ol>
      <button type="button" class="button-primary" :disabled="picked.length !== 2" @click="compare">{{ t('compare') }}</button>
      <WhatChanged v-if="comparison" :previous="comparison.older.assessment" :next="comparison.newer.assessment" :locale="locale"
        :heading="`${date(comparison.older.created_at)} → ${date(comparison.newer.created_at)}`" />
    </template>
  </section>
</template>
