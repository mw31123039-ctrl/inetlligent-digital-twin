import { cancerFaqs, cancerTopics, knowledgeVersion } from './knowledge'

export interface EvidenceAnswer {
  schema_version: 'humantwin-cancer-retrieval-v1'
  method: 'local-semantic-retrieval'
  corpus_version: string
  model_version: string
  weights_sha256: string
  question_sha256: string
  matches: { record_id: string; similarity: number }[]
  retrieval_ms: number
  safety_notice: 'none' | 'urgent-terms' | 'emergency-terms'
  question_saved: false
  external_requests: false
  clinical_validation: false
}
export async function questionFingerprint(question: string) {
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(question.trim())))].map(byte => byte.toString(16).padStart(2, '0')).join('')
}
export function acceptEvidenceAnswer(value: unknown, expectedQuestionHash: string): EvidenceAnswer {
  const fail = () => { throw new Error('The local evidence response could not be verified. You can still browse the source library.') }
  if (!value || typeof value !== 'object' || Array.isArray(value)) return fail()
  const item = value as Record<string, unknown>
  const allowed = ['schema_version', 'method', 'corpus_version', 'model_version', 'weights_sha256', 'question_sha256', 'matches', 'retrieval_ms', 'safety_notice', 'question_saved', 'external_requests', 'clinical_validation']
  if (Object.keys(item).some(key => !allowed.includes(key)) || item.schema_version !== 'humantwin-cancer-retrieval-v1' || item.method !== 'local-semantic-retrieval' || item.corpus_version !== knowledgeVersion || item.question_sha256 !== expectedQuestionHash || !/^[a-f0-9]{64}$/.test(expectedQuestionHash) || typeof item.weights_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(item.weights_sha256) || typeof item.model_version !== 'string' || !/^[A-Za-z0-9._-]{1,80}$/.test(item.model_version) || item.clinical_validation !== false || item.question_saved !== false || item.external_requests !== false || typeof item.retrieval_ms !== 'number' || !Number.isFinite(item.retrieval_ms) || item.retrieval_ms < 0 || !['none', 'urgent-terms', 'emergency-terms'].includes(String(item.safety_notice)) || !Array.isArray(item.matches) || item.matches.length > 3) return fail()
  const known = new Set([...cancerTopics, ...cancerFaqs].map(record => record.id))
  const ids = new Set<string>()
  for (const match of item.matches) {
    if (!match || typeof match !== 'object' || Array.isArray(match) || Object.keys(match).length !== 2 || typeof match.record_id !== 'string' || !known.has(match.record_id) || ids.has(match.record_id) || typeof match.similarity !== 'number' || !Number.isFinite(match.similarity) || match.similarity < -1 || match.similarity > 1) return fail()
    ids.add(match.record_id)
  }
  return item as unknown as EvidenceAnswer
}
