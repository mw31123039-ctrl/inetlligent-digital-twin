import type { RegionId } from '../types'

export type BodySide = 'unknown' | 'left' | 'right' | 'both' | 'center' | 'not_applicable'
export interface ChatMessage { id: string; role: 'assistant' | 'user'; text: string; field: string | null }
export interface AiAssessment {
  schema_version: '1.0'
  selected_region: RegionId
  side: BodySide
  reported_symptoms: string[]
  facts: { field: string; value: string; quote: string; message_id: string }[]
  unanswered_questions: string[]
  urgency: { level: 'not_established' | 'routine' | 'soon' | 'same_day' | 'emergency'; reasons: string[]; rule_ids: string[] }
  possible_explanations: { condition: string; interpretation: string; source_ids: string[]; reported_fact_ids: string[] }[]
  recommended_next_action: string
  supporting_sources: { id: string; title: string; url: string; retrieved_at: string; excerpt: string }[]
  next_question: { field: string; text: string; options: string[] } | null
  clinician_summary: string
  phase: 'collecting' | 'summary' | 'urgent' | 'insufficient' | 'unavailable'
  provider_status: 'ready' | 'disabled' | 'unavailable' | 'invalid_response'
  evidence_status: 'retrieved' | 'unavailable' | 'not_requested' | 'urgent_bypass'
  limitations: string[]
  triage_rules_version: string
  clinical_review_required: true
  disclaimer: string
}
export interface ChatEnvelope { id: string; revision: number; token: string; messages: ChatMessage[]; assessment: AiAssessment }
export interface SavedChat { id: string; region: RegionId; created_at: string }
export interface AiChatState {
  user: { id: number; email: string } | null
  status: { available: boolean; provider_configured: boolean } | null
  region: RegionId | null
  side: BodySide
  envelope: ChatEnvelope | null
  pending: boolean
  authPending: boolean
  error: string
  notice: string
  processingConsent: boolean
  storageConsent: boolean
  saved: boolean
  readOnly: boolean
  savedChats: SavedChat[]
}
