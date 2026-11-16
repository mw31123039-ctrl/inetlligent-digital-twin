import { computed, reactive } from 'vue'
import { ApiError } from '../services/aiApi'
import { clinicalApi } from './api'
import type { AnatomyNode, ClinicalAssessment, ClinicalCatalog, ClinicalEnvelope, ClinicalLocale, ClinicalSide, ClinicalStatus, SavedAssessmentDetail } from './types'

const LOCALE_KEY = 'humantwin.clinical.locale'

function storedLocale(): ClinicalLocale {
  try { const value = localStorage.getItem(LOCALE_KEY); return value === 'ar' || value === 'ckb' ? value : 'en' } catch { return 'en' }
}

export interface ClinicalState {
  locale: ClinicalLocale
  status: ClinicalStatus | null
  catalog: ClinicalCatalog | null
  catalogError: string
  anatomyId: string
  side: ClinicalSide
  processingAck: boolean
  useMemory: boolean
  envelope: ClinicalEnvelope | null
  previous: ClinicalAssessment | null
  pending: boolean
  stages: string[]
  error: string
  notice: string
  savedId: string
  viewing: SavedAssessmentDetail | null
}

/** Live clinical conversation with generation guards so late replies never overwrite a newer state. */
export function useClinicalSession() {
  const state = reactive<ClinicalState>({
    locale: storedLocale(), status: null, catalog: null, catalogError: '', anatomyId: 'body.eyes', side: 'unknown', processingAck: false, useMemory: false,
    envelope: null, previous: null, pending: false, stages: [], error: '', notice: '', savedId: '', viewing: null,
  })
  let generation = 0
  let controller: AbortController | undefined
  const nodes = computed(() => new Map<string, AnatomyNode>((state.catalog?.anatomy ?? []).map(node => [node.id, node])))
  const assessment = computed(() => state.viewing?.assessment ?? state.envelope?.assessment ?? null)
  const messages = computed(() => state.viewing?.messages ?? state.envelope?.messages ?? [])

  async function init() {
    const version = generation
    try { const status = await clinicalApi.status(); if (version === generation) state.status = status } catch { if (version === generation) state.status = { available: false, language_model_configured: false, clinical_review_required: true } }
    try { const catalog = await clinicalApi.catalog(); if (version === generation) { state.catalog = catalog; state.catalogError = '' } } catch (error) { if (version === generation) state.catalogError = error instanceof Error ? error.message : 'Catalogue unavailable.' }
  }

  function setLocale(locale: ClinicalLocale) {
    state.locale = locale
    try { localStorage.setItem(LOCALE_KEY, locale) } catch { /* per-viewer convenience only */ }
  }

  function selectAnatomy(id: string, side?: ClinicalSide) {
    if (state.envelope && id !== state.anatomyId) reset(false)
    state.anatomyId = id
    const node = nodes.value.get(id)
    if (side) state.side = side
    else if (node?.fixed_side) state.side = node.fixed_side
    else if (node && !node.lateral) state.side = 'midline'
    else if (node?.lateral && (state.side === 'midline')) state.side = 'unknown'
  }

  function reset(clearAck = false) {
    generation++
    controller?.abort()
    const id = state.envelope?.id
    if (id && !state.savedId) void clinicalApi.discard(id).catch(() => undefined)
    state.envelope = null; state.previous = null; state.pending = false; state.stages = []; state.error = ''; state.notice = ''; state.savedId = ''; state.viewing = null
    if (clearAck) state.processingAck = false
  }

  function fail(error: unknown, version: number) {
    if (version !== generation) return
    state.error = error instanceof Error ? error.message : 'The request could not be completed.'
    if (error instanceof ApiError && [409, 410].includes(error.status)) state.notice = 'This conversation changed or expired. Start over to continue safely.'
  }

  async function start() {
    if (state.pending || !state.processingAck) return false
    const version = ++generation
    controller = new AbortController()
    state.pending = true; state.error = ''; state.stages = ['received']; state.viewing = null; state.savedId = ''
    try {
      const envelope = await clinicalApi.start({ anatomy_id: state.anatomyId, side: state.side, locale: state.locale, processing_acknowledged: true, use_memory: state.useMemory }, controller.signal)
      if (version !== generation) return false
      if (envelope?.assessment?.schema_version !== 'humantwin-clinical-assessment-v2') throw new Error('An invalid service response was rejected.')
      state.envelope = envelope; state.previous = null
      return true
    } catch (error) { fail(error, version); return false }
    finally { if (version === generation) { state.pending = false; state.stages = [] } }
  }

  async function answer(text: string, codes: string[] = [], correctMessageId?: string) {
    const current = state.envelope
    const reply = text.trim()
    if (!current || state.pending || !reply) return false
    if (reply.length > 2000) { state.error = 'Answers can be up to 2000 characters.'; return false }
    const version = ++generation
    controller = new AbortController()
    state.pending = true; state.error = ''; state.notice = ''; state.stages = []
    try {
      const envelope = await clinicalApi.turn(current.id, {
        token: current.token, text: reply, answer_codes: codes, correct_message_id: correctMessageId ?? null, locale: state.locale,
      }, stage => { if (version === generation) state.stages = [...state.stages, stage] }, controller.signal)
      if (version !== generation) return false
      if (envelope?.assessment?.schema_version !== 'humantwin-clinical-assessment-v2' || envelope.id !== current.id) throw new Error('An invalid service response was rejected.')
      state.previous = current.assessment
      state.envelope = envelope
      state.savedId = ''
      return true
    } catch (error) { fail(error, version); return false }
    finally { if (version === generation) state.pending = false }
  }

  async function save(previousId?: string | null) {
    const current = state.envelope
    if (!current || state.pending) return null
    const version = generation
    state.pending = true; state.error = ''
    try {
      const result = await clinicalApi.save(current.id, current.token, previousId)
      if (version !== generation) return null
      state.savedId = result.id
      return result.id
    } catch (error) { fail(error, version); return null }
    finally { if (version === generation) state.pending = false }
  }

  function view(detail: SavedAssessmentDetail | null) { state.viewing = detail }
  function dispose() { generation++; controller?.abort() }

  return { state, nodes, assessment, messages, init, setLocale, selectAnatomy, start, answer, save, reset, view, dispose }
}
