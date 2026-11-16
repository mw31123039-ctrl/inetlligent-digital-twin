<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import AppIcon from '../components/AppIcon.vue'
import { translate, type StringKey } from './i18n'
import type { ClinicalAssessment, ClinicalLocale, ClinicalMessage } from './types'

const props = defineProps<{ messages: ClinicalMessage[]; assessment: ClinicalAssessment | null; pending: boolean; stages: string[]; locale: ClinicalLocale; readOnly: boolean }>()
const emit = defineEmits<{ answer: [text: string, codes: string[], correctionId?: string] }>()
const t = (key: StringKey) => translate(props.locale, key)
const STAGES = ['received', 'extracting', 'screening', 'reasoning', 'retrieving', 'composing', 'validated'] as const
const input = ref(''), picked = ref<string[]>([]), correctionId = ref<string>()
const transcript = ref<HTMLElement>(), urgentBox = ref<HTMLElement>(), field = ref<HTMLInputElement>()
const question = computed(() => props.readOnly ? null : props.assessment?.next_question ?? null)
const urgent = computed(() => props.assessment?.phase === 'urgent')
const visibleStages = computed(() => STAGES.filter(stage => props.stages.includes(stage)))
const blocked = computed(() => props.pending || props.readOnly || (urgent.value && !correctionId.value))
const correcting = computed(() => props.messages.find(message => message.id === correctionId.value))

function toggle(code: string) {
  if (code === 'none') { picked.value = picked.value.includes('none') ? [] : ['none']; return }
  picked.value = picked.value.includes(code) ? picked.value.filter(item => item !== code) : [...picked.value.filter(item => item !== 'none'), code]
}
function choose(code: string, label: string) { if (!blocked.value) emit('answer', label, [code]) }
function submitPicked() {
  if (!question.value || !picked.value.length || blocked.value) return
  const labels = question.value.options.filter(option => picked.value.includes(option.code)).map(option => option.label)
  emit('answer', labels.join(', '), [...picked.value])
}
function submitText() {
  const text = input.value.trim()
  if (!text || (blocked.value && !correctionId.value) || props.pending) return
  emit('answer', text, [], correctionId.value)
}
function startCorrection(message: ClinicalMessage) { correctionId.value = message.id; input.value = message.text; nextTick(() => field.value?.focus()) }
function cancelCorrection() { correctionId.value = undefined; input.value = '' }
watch(() => props.messages.length, async () => {
  input.value = ''; picked.value = []; correctionId.value = undefined
  await nextTick()
  if (transcript.value) transcript.value.scrollTop = transcript.value.scrollHeight
})
watch(() => props.assessment?.phase, async phase => { if (phase === 'urgent') { await nextTick(); urgentBox.value?.focus() } })
</script>

<template>
  <section class="ct-panel ct-interview" :aria-label="t('interview')">
    <div class="ct-panel-head"><h2><AppIcon name="chat" :size="20" />{{ t('interview') }}</h2></div>
    <div v-if="urgent && assessment" ref="urgentBox" class="ct-urgent" :class="assessment.urgency.level" role="alert" aria-live="assertive" tabindex="-1">
      <strong>{{ assessment.urgency.level === 'emergency' ? t('urgent_emergency') : t('urgent_same_day') }}</strong>
      <p>{{ assessment.urgency.action }}</p>
      <ul><li v-for="reason in assessment.urgency.reasons" :key="reason.rule_id">{{ reason.text }}</li></ul>
      <small>{{ t('urgent_stop') }}</small>
    </div>
    <ol ref="transcript" class="ct-transcript" role="log" aria-live="polite" :aria-busy="pending" :aria-label="t('interview')">
      <li v-for="message in messages" :key="message.id" :class="['ct-message', message.role, { superseded: !!message.superseded_by }]">
        <span class="ct-avatar" aria-hidden="true"><AppIcon :name="message.role === 'user' ? 'user' : 'bot'" :size="16" /></span>
        <div class="ct-bubble">
          <span v-if="message.superseded_by" class="ct-tag">{{ t('corrected') }}</span>
          <component :is="message.superseded_by ? 's' : 'span'">{{ message.text }}</component>
          <button v-if="message.role === 'user' && !message.superseded_by && !readOnly" type="button" class="ct-link" :disabled="pending" @click="startCorrection(message)">{{ t('correct') }}</button>
        </div>
      </li>
    </ol>
    <div v-if="pending" class="ct-stages" role="status" aria-live="polite">
      <span v-for="stage in visibleStages" :key="stage" class="done"><AppIcon name="check" :size="14" />{{ t(`stage_${stage}` as StringKey) }}</span>
      <span class="active"><i class="ct-spinner" aria-hidden="true"></i>{{ t('loading') }}</span>
    </div>
    <div v-if="question && !urgent" class="ct-question">
      <p class="ct-question-text">{{ question.text }}</p>
      <details class="ct-why" open><summary>{{ t('why') }}</summary><p>{{ question.purpose }}</p></details>
      <div v-if="question.options.length" class="ct-options" role="group" :aria-label="question.text">
        <template v-if="question.multi_select">
          <button v-for="option in question.options" :key="option.code" type="button" class="ct-option" :aria-pressed="picked.includes(option.code)" :disabled="blocked" @click="toggle(option.code)">
            <AppIcon v-if="picked.includes(option.code)" name="check" :size="15" />{{ option.label }}
          </button>
          <button type="button" class="button-primary ct-submit" :disabled="blocked || !picked.length" @click="submitPicked">{{ t('submit_choices') }}</button>
        </template>
        <button v-for="option in question.options" v-else :key="option.code" type="button" class="ct-option" :disabled="blocked" @click="choose(option.code, option.label)">{{ option.label }}</button>
      </div>
    </div>
    <p v-else-if="assessment && !urgent && !readOnly && !pending && assessment.phase !== 'complaint'" class="ct-note">{{ t('interview_done') }}</p>
    <p v-if="correcting" class="ct-correction">{{ t('correcting') }} <button type="button" class="ct-link" @click="cancelCorrection">{{ t('cancel') }}</button></p>
    <form v-if="!readOnly && ((question && question.free_text && !urgent) || correctionId)" class="ct-input" @submit.prevent="submitText">
      <label class="sr-only" for="clinical-answer">{{ t('type_answer') }}</label>
      <input id="clinical-answer" ref="field" v-model="input" type="text" maxlength="2000" autocomplete="off" :placeholder="t('type_answer')" :disabled="pending || (blocked && !correctionId)" />
      <button type="submit" class="button-primary" :disabled="pending || !input.trim() || (blocked && !correctionId)"><AppIcon name="send" :size="16" />{{ correctionId ? t('update') : t('send') }}</button>
    </form>
  </section>
</template>
