import { aiApi, ApiError } from '../services/aiApi'
import type { ClinicalCatalog, ClinicalEnvelope, ClinicalStatus, ExtractionResult, MemoryFact, MemoryState, SavedAssessmentDetail, SavedAssessmentSummary, StreamEvent } from './types'

function csrfHeader(): Record<string, string> {
  const token = document.cookie.split('; ').find(item => item.startsWith('XSRF-TOKEN='))?.slice(11)
  return token ? { 'X-XSRF-TOKEN': decodeURIComponent(token) } : {}
}

/**
 * Incremental NDJSON parser. Network chunks can split a line anywhere (even inside a multi-byte
 * character, which TextDecoder's stream mode handles); only complete lines are parsed.
 */
export function createNdjsonParser(onEvent: (event: StreamEvent) => void) {
  let buffer = ''
  function flushLine(line: string) {
    const trimmed = line.trim()
    if (!trimmed) return
    let value: unknown
    try { value = JSON.parse(trimmed) } catch { throw new ApiError('The service sent an unreadable progress update.') }
    if (!value || typeof value !== 'object' || !('type' in value)) throw new ApiError('The service sent an unreadable progress update.')
    onEvent(value as StreamEvent)
  }
  return {
    push(chunk: string) {
      buffer += chunk
      let index = buffer.indexOf('\n')
      while (index !== -1) {
        const line = buffer.slice(0, index)
        buffer = buffer.slice(index + 1)
        flushLine(line)
        index = buffer.indexOf('\n')
      }
    },
    end() { const rest = buffer; buffer = ''; flushLine(rest) },
  }
}

/** POST a turn and stream progress. Falls back to a single JSON envelope when the server does not stream. */
export async function streamTurn(sessionId: string, body: Record<string, unknown>, onStage: (stage: string) => void, signal?: AbortSignal): Promise<ClinicalEnvelope> {
  const timeout = new AbortController()
  const timer = window.setTimeout(() => timeout.abort(), 45_000)
  try {
    const response = await fetch(`/api/clinical/sessions/${sessionId}/turns`, {
      method: 'POST', credentials: 'include', cache: 'no-store', body: JSON.stringify(body),
      signal: signal ? AbortSignal.any([signal, timeout.signal]) : timeout.signal,
      headers: { Accept: 'application/x-ndjson, application/json', 'Content-Type': 'application/json', ...csrfHeader() },
    })
    const type = response.headers.get('content-type') || ''
    if (!response.ok || !type.includes('ndjson') || !response.body) {
      const json = await response.json().catch(() => null)
      if (!response.ok) throw new ApiError(response.status === 401 ? 'Sign in to continue.' : response.status === 419 ? 'Your session expired. Sign in again.' : typeof json?.message === 'string' ? json.message : 'The request could not be completed.', response.status)
      if (!json) throw new ApiError('The service returned an invalid response.')
      return json as ClinicalEnvelope
    }
    let envelope: ClinicalEnvelope | null = null
    let failure: ApiError | null = null
    const parser = createNdjsonParser(event => {
      if (event.type === 'stage') onStage(event.stage)
      else if (event.type === 'final') envelope = event.envelope
      else if (event.type === 'error') failure = new ApiError(event.message || 'The assessment could not be completed.', event.status)
    })
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      parser.push(decoder.decode(value, { stream: true }))
    }
    parser.push(decoder.decode())
    parser.end()
    if (failure) throw failure
    if (!envelope) throw new ApiError('The assessment stream ended without a result. Your answer was not lost; retry.')
    return envelope
  } catch (error) {
    if (error instanceof ApiError || signal?.aborted) throw error
    throw new ApiError('The service is unavailable or timed out. For severe or sudden symptoms, seek urgent medical help.')
  } finally { window.clearTimeout(timer) }
}

async function upload(file: File): Promise<ExtractionResult> {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch('/api/clinical/documents', { method: 'POST', credentials: 'include', cache: 'no-store', body: form, headers: { Accept: 'application/json', ...csrfHeader() } })
  const json = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(typeof json?.message === 'string' ? json.message : 'The report could not be processed.', response.status)
  return json as ExtractionResult
}

export const clinicalApi = {
  status: () => aiApi.get<ClinicalStatus>('/clinical/status'),
  catalog: () => aiApi.get<ClinicalCatalog>('/clinical/catalog'),
  start: (body: { anatomy_id: string; side: string; locale: string; processing_acknowledged: true; use_memory: boolean }, signal?: AbortSignal) => aiApi.post<ClinicalEnvelope>('/clinical/sessions', body, signal, 45_000),
  turn: streamTurn,
  save: (id: string, token: string, previousId?: string | null) => aiApi.post<{ id: string; saved: true; created_at: string }>(`/clinical/sessions/${id}/save`, { token, consent: true, consent_version: 'clinical-storage-v1', previous_id: previousId ?? null }, undefined, 45_000),
  discard: (id: string) => aiApi.delete(`/clinical/sessions/${id}`),
  list: () => aiApi.get<{ assessments: SavedAssessmentSummary[] }>('/clinical/assessments'),
  show: (id: string) => aiApi.get<SavedAssessmentDetail>(`/clinical/assessments/${id}`),
  remove: (id: string) => aiApi.delete(`/clinical/assessments/${id}`),
  share: (id: string) => aiApi.post<{ review_shared: boolean }>(`/clinical/assessments/${id}/review-share`, { consent: true, consent_version: 'clinical-review-share-v1' }),
  unshare: (id: string) => aiApi.delete(`/clinical/assessments/${id}/review-share`),
  memory: () => aiApi.get<MemoryState>('/clinical/memory'),
  grantMemory: (retentionDays: number) => aiApi.post('/clinical/memory/consent', { consent: true, consent_version: 'patient-memory-v1', retention_days: retentionDays }),
  revokeMemory: () => aiApi.delete('/clinical/memory/consent'),
  addFact: (body: { kind: string; label: string; details?: string | null }) => aiApi.post<MemoryFact>('/clinical/memory/facts', body),
  correctFact: (id: string, body: { label: string; details?: string | null }) => request<MemoryFact>(`/clinical/memory/facts/${id}`, 'PATCH', body),
  confirmFact: (id: string, decision: 'confirm' | 'reject', label?: string) => aiApi.post<MemoryFact | undefined>(`/clinical/memory/facts/${id}/confirm`, { decision, ...(label ? { label } : {}) }),
  deleteFact: (id: string) => aiApi.delete(`/clinical/memory/facts/${id}`),
  exportMemory: () => aiApi.get<unknown>('/clinical/memory/export'),
  rememberFromAssessment: (assessmentId: string, factIds: string[]) => aiApi.post<{ facts: MemoryFact[] }>('/clinical/memory/facts/from-assessment', { assessment_id: assessmentId, fact_ids: factIds }),
  upload,
}

async function request<T>(path: string, method: string, body: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, { method, credentials: 'include', cache: 'no-store', body: JSON.stringify(body), headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...csrfHeader() } })
  const json = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(typeof json?.message === 'string' ? json.message : 'The request could not be completed.', response.status)
  return json as T
}
