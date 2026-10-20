<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { AiChatState, BodySide } from '../types/ai'
import { getRegion } from '../data/regions'
import AppIcon from './AppIcon.vue'

const props = defineProps<{ state: AiChatState }>()
const emit = defineEmits<{
  send: [text: string, correctionId?: string]; authenticate: [email: string, password: string, register: boolean]
  logout: []; reset: []; remove: []; side: [value: BodySide]; consent: [value: boolean]
}>()
const input = ref(''), email = ref(''), password = ref(''), register = ref(false), correctionId = ref<string>()
const transcript = ref<HTMLDivElement>(), urgent = ref<HTMLDivElement>()
const assessment = computed(() => props.state.envelope?.assessment)
const blocked = computed(() => !props.state.region || !props.state.user || !props.state.status?.available || !props.state.processingConsent || props.state.pending || props.state.readOnly || (assessment.value?.phase === 'urgent' && !correctionId.value))
function submit() { if (blocked.value || !input.value.trim()) return; emit('send', input.value, correctionId.value) }
function correct(id: string, text: string) { correctionId.value = id; input.value = text; nextTick(() => document.getElementById('ai-message')?.focus()) }
function login() { emit('authenticate', email.value, password.value, register.value); password.value = '' }
watch(() => props.state.envelope, (value, previous) => { if (value && value !== previous) { input.value = ''; correctionId.value = undefined } })
watch(() => props.state.region, () => { input.value = ''; correctionId.value = undefined })
watch(() => [props.state.envelope?.messages.length, props.state.pending], async () => { await nextTick(); if (transcript.value) transcript.value.scrollTop = transcript.value.scrollHeight })
watch(() => assessment.value?.phase, async value => { if (value === 'urgent') { await nextTick(); urgent.value?.focus() } })
</script>

<template>
  <section class="panel assistant-panel ai-assistant" :class="{ 'requires-signin': !state.user }" aria-labelledby="ai-assistant-title">
    <div class="assistant-header"><div><span class="assistant-heading-icon"><AppIcon name="chat" :size="23" /></span><h2 id="ai-assistant-title">AI symptom assistant</h2></div><span class="ai-status" :class="{ online: state.status?.provider_configured }">{{ state.status?.provider_configured ? 'AI configured' : 'AI not configured' }}</span></div>
    <p class="ai-disclaimer">This AI symptom assistant does not replace a clinician’s examination or diagnosis. Use mock inputs while this prototype awaits clinical review.</p>
    <div class="assistant-context"><span v-if="state.region" class="region-pill"><AppIcon :name="state.region" :size="18" />{{ getRegion(state.region).label }}</span><label v-if="state.region" class="ai-side">Side <select aria-label="Affected side" :value="state.side" :disabled="state.pending" @change="emit('side', ($event.target as HTMLSelectElement).value as BodySide)"><option value="unknown">Not specified</option><option value="left">Left</option><option value="right">Right</option><option value="both">Both</option><option value="center">Center</option><option value="not_applicable">Not applicable</option></select></label></div>
    <div v-if="!state.status?.available" class="ai-service-notice" role="status">The assessment service is not connected. Your answers will not be submitted until it is available.</div>
    <div v-else-if="!state.status.provider_configured" class="ai-service-notice" role="status">No AI credentials are configured. Only limited rule-based intake and draft warning checks are available. No AI explanations will be generated.</div>
    <div v-if="assessment && ['unavailable', 'invalid_response'].includes(assessment.provider_status)" class="ai-service-notice" role="alert">The AI reply is unavailable or failed verification. Only limited intake guidance is shown; no AI explanation was accepted.</div>
    <form v-if="!state.user" class="ai-auth" @submit.prevent="login"><strong>{{ register ? 'Create an account' : 'Sign in to keep conversations separate' }}</strong><label>Email<input v-model="email" type="email" required autocomplete="username" maxlength="254" /></label><label>Password<input v-model="password" type="password" required :minlength="register ? 12 : 1" maxlength="128" :autocomplete="register ? 'new-password' : 'current-password'" /></label><span v-if="register">Use at least 12 characters. No personal or medical profile is required.</span><div><button type="submit" class="button-primary" :disabled="state.authPending">{{ state.authPending ? 'Please wait…' : register ? 'Create account' : 'Sign in' }}</button><button type="button" class="ai-text-button" @click="register = !register">{{ register ? 'Use existing account' : 'Create an account' }}</button></div></form>
    <template v-else>
      <div class="ai-account"><span>Signed in · conversations are private to your account</span><button class="ai-text-button" :disabled="state.pending" @click="emit('logout')">Sign out</button></div>
      <label class="ai-consent"><input type="checkbox" :checked="state.processingConsent" :disabled="state.pending" @change="emit('consent', ($event.target as HTMLInputElement).checked)" /><span>I understand that my answers are processed by this application and, when enabled, its external AI provider. I will avoid names, addresses and other identifying details. Nothing is saved to history without separate consent.</span></label>
    </template>
    <div v-if="assessment?.phase === 'urgent'" ref="urgent" class="ai-urgency" role="alert" aria-live="assertive" tabindex="-1"><strong>{{ assessment.urgency.level === 'emergency' ? 'Seek emergency help now' : 'Seek urgent assessment today' }}</strong><p>{{ assessment.recommended_next_action }}</p><ul><li v-for="reason in assessment.urgency.reasons" :key="reason">{{ reason }}</li></ul><small>Draft warning rules require clinical review. Do not wait for this chat to establish a diagnosis.</small></div>
    <div ref="transcript" class="conversation ai-conversation" role="log" aria-label="AI symptom conversation" aria-live="polite" :aria-busy="state.pending">
      <div v-if="!state.envelope" class="message-row assistant"><span class="message-avatar"><AppIcon name="bot" :size="20" /></span><div class="message-bubble">{{ state.region ? `You selected your ${getRegion(state.region).label.toLowerCase()}. In your own words, what is bothering you?` : 'Select a body region to start a conversation.' }}</div></div>
      <div v-for="message in state.envelope?.messages" :key="message.id" class="message-row" :class="message.role"><span class="message-avatar"><AppIcon :name="message.role === 'user' ? 'user' : 'bot'" :size="19" /></span><div class="message-bubble">{{ message.text }}<button v-if="message.role === 'user' && !state.readOnly" class="ai-edit-answer" :disabled="state.pending" :aria-label="`Correct answer: ${message.text.slice(0, 50)}`" @click="correct(message.id, message.text)">Correct answer</button></div></div>
      <div v-if="state.pending" class="message-row assistant"><span class="message-avatar"><AppIcon name="bot" :size="20" /></span><div class="message-bubble typing" role="status" aria-label="Assistant is processing your answer"><i></i><i></i><i></i></div></div>
      <div v-if="assessment?.next_question && !blocked" class="answer-options"><button v-for="option in assessment.next_question.options" :key="option" @click="emit('send', option)">{{ option }}</button></div>
    </div>
    <div v-if="state.error" class="conversation-error" role="alert">{{ state.error }} <span v-if="input">Your text is still in the input.</span></div>
    <p v-if="state.notice" class="ai-notice" role="status">{{ state.notice }}</p>
    <p v-if="correctionId" class="ai-correction">Correcting an earlier answer. Later answers will be removed and reassessed.<button @click="correctionId = undefined; input = ''">Cancel</button></p>
    <form class="symptom-form" @submit.prevent="submit"><label for="ai-message" class="sr-only">Describe your symptoms or answer the question</label><input id="ai-message" v-model="input" type="text" maxlength="2000" autocomplete="off" :disabled="blocked" placeholder="Describe what you are experiencing…" /><button class="button-primary" type="submit" :disabled="blocked || !input.trim()"><AppIcon name="send" :size="17" />{{ correctionId ? 'Update' : 'Send' }}</button></form>
    <div class="ai-chat-controls"><button class="button-secondary" :disabled="state.pending" @click="emit('reset')">Start over</button><button class="ai-text-button" :disabled="state.pending" @click="emit('remove')">Delete conversation</button></div>
    <p class="ai-emergency-note">For severe trouble breathing, chest pressure, sudden loss of sight, or new weakness, seek emergency help now. Do not wait for a chat reply.</p>
  </section>
</template>
