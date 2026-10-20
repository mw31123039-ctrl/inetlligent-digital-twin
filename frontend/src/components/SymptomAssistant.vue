<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { Message, RegionId } from '../types'
import { getRegion } from '../data/regions'
import AppIcon from './AppIcon.vue'
const props = defineProps<{ region: RegionId | null; messages: Message[]; options: string[]; pain: number; step: number; pending: boolean; error: string; canRetry: boolean; complete: boolean }>()
const emit = defineEmits<{ send: [answer: string]; retry: []; clear: []; 'update:pain': [pain: number] }>()
const input = ref('')
const transcript = ref<HTMLDivElement>()
const painPercent = computed(() => (props.pain - 1) / 9 * 100)
async function scrollToEnd() { await nextTick(); if (transcript.value) transcript.value.scrollTop = transcript.value.scrollHeight }
watch(() => [props.messages.length, props.pending, props.error, props.options], scrollToEnd, { deep: true })
watch(() => props.region, () => { input.value = '' })
function submit() { if (!input.value.trim() || props.pending || props.canRetry) return; emit('send', input.value); input.value = '' }
</script>
<template>
  <section class="panel assistant-panel" aria-labelledby="assistant-title">
    <div class="assistant-header"><div><span class="assistant-heading-icon"><AppIcon name="chat" :size="23"/></span><h2 id="assistant-title">Symptom assistant</h2></div><span class="step-count">{{ region ? Math.min(step + 1, 5) : 0 }} of 5</span><div class="step-dots" aria-hidden="true"><i v-for="n in 5" :key="n" :class="{ filled: region && n <= step + 1 }"></i></div></div>
    <div class="assistant-context"><span v-if="region" class="region-pill"><AppIcon :name="region" :size="19"/>{{ getRegion(region).label }}<button aria-label="Clear selected area and conversation" @click="$emit('clear')"><AppIcon name="x" :size="14"/></button></span><span class="scripted-label"><span></span> SCRIPTED DEMO</span></div>
    <div ref="transcript" class="conversation" role="log" aria-live="polite" aria-relevant="additions text" aria-label="Symptom conversation" :aria-busy="pending">
      <div v-if="!region" class="conversation-empty"><span><AppIcon name="body" :size="36"/></span><h3>Let’s start with an area</h3><p>Select a body region on the model or use the area buttons. Your guided conversation will appear here.</p></div>
      <div v-for="message in messages" :key="message.id" class="message-row" :class="message.role"><span class="message-avatar"><AppIcon :name="message.role === 'assistant' ? 'bot' : 'user'" :size="20"/></span><div class="message-bubble">{{ message.text }}</div></div>
      <div v-if="pending" class="message-row assistant"><span class="message-avatar"><AppIcon name="bot" :size="20"/></span><div class="message-bubble typing" role="status" aria-label="Assistant is preparing a simulated response"><i></i><i></i><i></i></div></div>
      <div v-if="error" class="conversation-error" role="alert"><AppIcon name="error" :size="18"/><div><p>{{ error }}</p><button v-if="canRetry" @click="$emit('retry')" :disabled="pending">{{ pending ? 'Retrying…' : 'Retry response' }}</button></div></div>
      <div v-if="options.length && !pending && !canRetry" class="answer-options"><button v-for="option in options" :key="option" @click="$emit('send', option)">{{ option }}</button></div>
      <div v-if="complete && !pending" class="completion-note"><AppIcon name="complete" :size="17"/>Your demo assessment is complete</div>
    </div>
    <div class="pain-section"><div class="pain-heading"><label for="pain-level">Pain level <span class="info-tip" title="Your self-reported pain, from 1 (minimal) to 10 (severe)."><AppIcon name="info" :size="15"/></span></label><span>{{ pain <= 3 ? 'Mild' : pain <= 6 ? 'Moderate' : 'Severe' }} discomfort</span></div><div class="pain-slider-row"><span>1</span><div class="slider-container"><output for="pain-level" :style="{ left: `calc(10px + (100% - 20px) * ${painPercent / 100})` }">{{ pain }}</output><input id="pain-level" type="range" min="1" max="10" step="1" :value="pain" :disabled="!region" :style="{ '--pain-percent': `${painPercent}%` }" :aria-valuetext="`${pain} out of 10`" @input="emit('update:pain', Number(($event.target as HTMLInputElement).value))"/></div><span>10</span></div><div class="pain-labels"><span>Minimal</span><span>Severe</span></div></div>
    <form class="symptom-form" @submit.prevent="submit"><label for="symptoms" class="sr-only">Describe your symptoms</label><input id="symptoms" v-model="input" type="text" autocomplete="off" maxlength="500" :disabled="!region || pending || canRetry" :placeholder="complete ? 'Add a note to your summary…' : 'Describe your symptoms…'"/><button type="submit" class="button-primary" :disabled="!region || pending || canRetry || !input.trim()"><AppIcon name="send" :size="17"/><span>Send</span></button></form>
    <div class="assistant-footnote"><AppIcon name="shield" :size="12"/>For exploration only. Not a medical diagnosis.</div>
  </section>
</template>
