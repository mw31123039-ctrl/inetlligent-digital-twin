<script setup lang="ts">
import { translate, type StringKey } from './i18n'
import type { Citation, ClinicalLocale } from './types'

const props = defineProps<{ citation: Citation; locale: ClinicalLocale }>()
defineEmits<{ close: [] }>()
const t = (key: StringKey) => translate(props.locale, key)
</script>

<template>
  <article class="ct-source" :aria-label="citation.title" dir="ltr">
    <header>
      <span class="ct-cite-id">{{ citation.id }}</span>
      <strong>{{ citation.title }}</strong>
      <span class="ct-muted">{{ citation.publisher }}</span>
      <button type="button" class="ct-icon-button" :aria-label="t('close')" @click="$emit('close')">×</button>
    </header>
    <p class="ct-muted ct-small">{{ t('exact_text') }}</p>
    <blockquote><span v-if="citation.lead" class="ct-lead">{{ citation.lead }} </span>{{ citation.quote }}</blockquote>
    <dl class="ct-source-meta">
      <div v-if="citation.last_reviewed"><dt>{{ t('reviewed') }}</dt><dd>{{ citation.last_reviewed }}</dd></div>
      <div v-if="citation.next_review_due"><dt>{{ t('next_review') }}</dt><dd>{{ citation.next_review_due }} <span v-if="citation.review_overdue" class="ct-badge warn">{{ t('overdue') }}</span></dd></div>
      <div><dt>{{ t('licence') }}</dt><dd>{{ citation.licence }}</dd></div>
    </dl>
    <a :href="citation.url" target="_blank" rel="noopener noreferrer">{{ t('open_source') }}</a>
  </article>
</template>
