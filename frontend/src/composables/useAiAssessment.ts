import { reactive } from 'vue'
import { aiApi, ApiError } from '../services/aiApi'
import type { AiAssessment, AiChatState, BodySide, ChatEnvelope } from '../types/ai'
import type { RegionId } from '../types'

function validEnvelope(value: ChatEnvelope): boolean {
  return !!value && typeof value.id === 'string' && typeof value.token === 'string' && Array.isArray(value.messages)
    && value.messages.every(message => typeof message.text === 'string' && ['user', 'assistant'].includes(message.role))
    && value.assessment?.schema_version === '1.0' && Array.isArray(value.assessment.facts) && Array.isArray(value.assessment.limitations)
    && Array.isArray(value.assessment.supporting_sources) && value.assessment.supporting_sources.every(source => /^https:\/\/www\.nhs\.uk\//.test(source.url))
    && ['not_established', 'routine', 'soon', 'same_day', 'emergency'].includes(value.assessment.urgency?.level)
}

export function useAiAssessment() {
  const state = reactive<AiChatState>({ user: null, status: null, region: 'eyes', side: 'unknown', envelope: null, pending: false, authPending: false, error: '', notice: '', processingConsent: false, storageConsent: false, saved: false, readOnly: false, savedChats: [] })
  let generation = 0
  let controller: AbortController | undefined
  const authChannel = typeof BroadcastChannel === 'undefined' ? null : new BroadcastChannel('humantwin-auth')
  if (authChannel) authChannel.onmessage = () => { reset(); state.user = null; state.savedChats = []; state.processingConsent = false; void init() }
  function reset(region = state.region, side: BodySide = 'unknown') {
    generation++
    controller?.abort()
    state.envelope = null
    state.region = region
    state.side = side
    state.pending = false
    state.error = ''
    state.notice = ''
    state.saved = false
    state.storageConsent = false
    state.readOnly = false
  }
  async function init() {
    const version = generation
    try { state.status = await aiApi.get('/status') } catch { state.status = { available: false, provider_configured: false } }
    if (version !== generation) return
    try { const response = await aiApi.get<{ user: AiChatState['user'] }>('/me'); if (version !== generation) return; state.user = response.user; await listSaved() } catch { if (version === generation) state.user = null }
  }
  async function authenticate(email: string, password: string, register = false) {
    state.authPending = true; state.error = ''
    try {
      await aiApi.csrf()
      const result = await aiApi.post<{ user: AiChatState['user'] }>(register ? '/register' : '/login', { email, password })
      reset(); state.user = result.user; state.processingConsent = false
      authChannel?.postMessage('changed')
      await listSaved()
    } catch (error) { state.error = error instanceof Error ? error.message : 'Sign in failed.' }
    finally { state.authPending = false }
  }
  async function logout() {
    try { await aiApi.post('/logout', {}) }
    catch { state.error = 'Sign out could not be confirmed. Retry before using a shared device.'; return }
    reset(); state.user = null; state.savedChats = []; state.processingConsent = false
    authChannel?.postMessage('changed')
  }
  async function send(text: string, correctMessageId?: string) {
    if (state.pending || !state.region || !state.user || !state.processingConsent || state.readOnly) return false
    const answer = text.trim()
    if (!answer || answer.length > 2000) { state.error = 'Enter an answer between 1 and 2000 characters.'; return false }
    const version = generation
    controller = new AbortController()
    const signal = controller.signal
    state.pending = true; state.error = ''; state.notice = ''
    try {
      let current = state.envelope
      if (!current) {
        current = await aiApi.post<ChatEnvelope>('/conversations', { region: state.region, side: state.side, processing_acknowledged: true }, signal)
        if (version !== generation) return false
        if (!validEnvelope(current)) throw new Error('An invalid service response was rejected.')
        state.envelope = current
      }
      const result = await aiApi.post<ChatEnvelope>(`/conversations/${current.id}/turns`, { token: current.token, text: answer, correct_message_id: correctMessageId ?? null }, signal)
      if (version !== generation) return false
      if (!validEnvelope(result) || result.assessment.selected_region !== state.region) throw new Error('An invalid service response was rejected.')
      state.envelope = result; state.side = result.assessment.side; state.saved = false; state.storageConsent = false
      return true
    } catch (error) {
      if (version === generation) {
        state.error = error instanceof Error ? error.message : 'The response could not be loaded.'
        if (error instanceof ApiError && [401, 419].includes(error.status)) { reset(); state.user = null; state.savedChats = []; state.processingConsent = false; state.error = 'Your session expired. Sign in again.' }
      }
      return false
    } finally { if (version === generation) state.pending = false }
  }
  async function save() {
    const current = state.envelope
    if (!current || !state.storageConsent || state.pending || state.readOnly) return
    const version = generation
    state.pending = true; state.error = ''
    try {
      await aiApi.post(`/conversations/${current.id}/save`, { token: current.token, consent: true, consent_version: 'health-storage-v1' })
      if (version !== generation) return
      state.saved = true; state.notice = 'Saved with your consent. You can delete it at any time.'
      await listSaved()
    } catch (error) { if (version === generation) state.error = error instanceof Error ? error.message : 'Saving failed.' }
    finally { if (version === generation) state.pending = false }
  }
  async function listSaved() {
    if (!state.user) return
    const userId = state.user.id
    try { const records = await aiApi.get<AiChatState['savedChats']>('/assessments'); if (state.user?.id === userId) state.savedChats = records }
    catch { state.notice = 'Saved conversations could not be loaded.' }
  }
  async function openSaved(id: string) {
    const userId = state.user?.id, version = generation
    try {
      const record = await aiApi.get<{ id: string; messages: ChatEnvelope['messages']; assessment: AiAssessment }>(`/assessments/${id}`)
      if (version !== generation || userId !== state.user?.id) return false
      reset(record.assessment.selected_region, record.assessment.side)
      state.envelope = { ...record, revision: 0, token: '' }; state.readOnly = true; state.saved = true
      state.notice = 'Viewing a saved record. Start over to begin a new conversation.'
      return true
    } catch (error) { state.error = error instanceof Error ? error.message : 'This record could not be opened.'; return false }
  }
  async function remove(id = state.envelope?.id) {
    if (!id) { reset(); return }
    const version = generation
    try {
      await aiApi.delete(`/conversations/${id}`)
      state.savedChats = state.savedChats.filter(item => item.id !== id)
      if (version === generation && state.envelope?.id === id) { reset(); state.notice = 'Conversation deleted from this screen and the application database.' }
    } catch (error) { state.error = error instanceof Error ? error.message : 'Deletion failed. Retry to confirm deletion.' }
  }
  function dispose() { generation++; controller?.abort(); authChannel?.close() }
  return { state, init, authenticate, logout, send, save, listSaved, openSaved, remove, reset, dispose }
}
