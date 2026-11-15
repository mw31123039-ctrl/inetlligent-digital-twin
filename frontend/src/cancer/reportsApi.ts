import { aiApi } from '../services/aiApi'
import { validateResult } from './model'
import type { CancerModality, CancerResult, CancerTrack, Outcome } from './model'

export const REPORT_CONSENT_VERSION = 'cancer-report-storage-v1'
export interface ReportSummaryRow { id: string; created_at: string; track: CancerTrack; modality: CancerModality; outcome: Outcome; finding_label: string | null; top_label: string | null; probability: number | null; model_version: string }
export interface SavedReport extends ReportSummaryRow { result: CancerResult; thumbnail_data_url: string; note: string | null }

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
function row(value: unknown): ReportSummaryRow {
  const item = value as Record<string, unknown>
  if (!item || typeof item !== 'object' || typeof item.id !== 'string' || !uuid.test(item.id) || typeof item.created_at !== 'string' || !Number.isFinite(Date.parse(item.created_at))
    || !['skin', 'oral', 'lung', 'breast'].includes(String(item.track)) || !['finding', 'inconclusive', 'input-rejected'].includes(String(item.outcome))) {
    throw new Error('A saved report could not be read.')
  }
  return item as unknown as ReportSummaryRow
}

export const reportsApi = {
  async list(signal?: AbortSignal): Promise<ReportSummaryRow[]> {
    const body = await aiApi.get<{ reports: unknown[] }>('/cancer/reports', signal)
    if (!Array.isArray(body?.reports)) throw new Error('Saved reports could not be read.')
    return body.reports.map(row)
  },
  async show(id: string): Promise<SavedReport> {
    if (!uuid.test(id)) throw new Error('Unknown report.')
    const body = await aiApi.get<Record<string, unknown>>('/cancer/reports/' + id)
    const summary = row(body)
    if (typeof body.thumbnail_data_url !== 'string' || !body.thumbnail_data_url.startsWith('data:image/jpeg;base64,')) throw new Error('The saved preview could not be read.')
    return { ...summary, result: validateResult(body.result), thumbnail_data_url: body.thumbnail_data_url, note: typeof body.note === 'string' ? body.note : null }
  },
  save(inputSha256: string, thumbnailDataUrl: string, note: string) {
    return aiApi.post<{ id: string; saved: boolean; created_at: string }>('/cancer/reports', {
      input_sha256: inputSha256, thumbnail_data_url: thumbnailDataUrl, note: note.trim() || null, consent: true, consent_version: REPORT_CONSENT_VERSION,
    })
  },
  remove(id: string) { return aiApi.delete('/cancer/reports/' + id) },
}
