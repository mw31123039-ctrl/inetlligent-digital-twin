/** Mirrors contracts/clinical/assessment.v2.schema.json (source: ai-service/app/clinical/schemas.py). */
export type ClinicalLocale = 'en' | 'ar' | 'ckb'
export type ClinicalSide = 'left' | 'right' | 'both' | 'midline' | 'unknown'
export type UrgencyLevel = 'not_established' | 'routine' | 'soon' | 'same_day' | 'emergency'
export type Provenance = 'patient_statement' | 'patient_answer' | 'patient_memory' | 'document_extract' | 'clinician_confirmed' | 'ai_suggestion'
export type Localized = Record<ClinicalLocale, string>

export interface Span { message_id: string; start: number; end: number; quote: string }
export interface Fact {
  id: string; kind: 'symptom' | 'attribute' | 'trigger' | 'risk_factor' | 'history' | 'medication' | 'allergy' | 'screen'; key: string; value: string
  numeric: number | null; label: string; status: 'present' | 'absent' | 'uncertain'; temporal: 'current' | 'past'; anatomy_id: string | null
  side: ClinicalSide | null; provenance: Provenance; extractor: string; spans: Span[]; source_ref: string | null
}
export interface AnatomyRef { id: string; label: string; side: ClinicalSide; role: 'selected' | 'reported' | 'related' | 'finding'; relation: string | null; relation_note: string | null; marker: 'illustrative_anatomy'; fact_ids: string[]; explanation_ids: string[] }
export interface Observation { id: string; text: string; fact_ids: string[]; provenance: Provenance }
export interface Citation { id: string; source_id: string; chunk_id: string; title: string; publisher: string; url: string; quote: string; lead: string | null; last_reviewed: string | null; next_review_due: string | null; review_overdue: boolean; retrieved_at: string; licence: string }
export interface EvidenceItem { statement: string; fact_ids: string[]; citation_ids: string[] }
export interface MissingFeature { key: string; label: string; question_id: string | null }
export interface Explanation {
  id: string; condition_id: string; name: string; fit: 'fits' | 'partly_fits'; plain_language: string; supporting: EvidenceItem[]; conflicting: EvidenceItem[]
  missing: MissingFeature[]; pathway: string; pathway_label: string; urgent_condition: boolean; scope_note: string | null; anatomy_ids: string[]
}
export interface MissingInfo { key: string; label: string; reason: string; priority: 'safety' | 'core' | 'discriminating' | 'history' }
export interface Contradiction { id: string; kind: 'symptom_presence' | 'attribute' | 'laterality' | 'memory'; description: string; fact_ids: string[]; message_ids: string[]; resolved: boolean }
export interface UrgencyReason { rule_id: string; text: string; citation_ids: string[]; fact_ids: string[] }
export interface Urgency { level: UrgencyLevel; pathway: string; pathway_label: string; action: string; reasons: UrgencyReason[]; safety_screen_completed: boolean; persisted_from_prior: boolean; rules_version: string }
export interface Option { code: string; label: string }
export interface Question {
  id: string; kind: 'complaint' | 'safety' | 'attribute' | 'symptom' | 'structure' | 'side' | 'clarify' | 'history' | 'memory' | 'laterality' | 'triggers'
  text: string; purpose: string; options: Option[]; multi_select: boolean; free_text: boolean; discriminates: string[]
}
export interface ClinicianSummary { headline: string; patient_reported: string[]; from_records: string[]; observations_note: string; interpretations: string[]; urgency: string; missing: string[]; contradictions: string[]; provenance_note: string }
export interface Versions { engine: string; anatomy: string; symptoms: string; knowledge: string; source_registry: string; snapshot: string; language_model: string | null; prompt: string | null }
export interface ClinicalAssessment {
  schema_version: 'humantwin-clinical-assessment-v2'; locale: ClinicalLocale; direction: 'ltr' | 'rtl'; anatomy: { id: string; side: ClinicalSide }
  phase: 'complaint' | 'safety_screen' | 'collecting' | 'summary' | 'urgent' | 'insufficient'; summary: string; patient_facts: Fact[]; anatomical_references: AnatomyRef[]
  observations: Observation[]; possible_explanations: Explanation[]
  explanation_status: 'supported' | 'insufficient_information' | 'no_supported_explanation' | 'withheld_urgent' | 'conflicting'
  missing_information: MissingInfo[]; contradictions: Contradiction[]; urgency: Urgency; next_question: Question | null; related_reading: string[]; citations: Citation[]
  limitations: string[]; clinician_summary: ClinicianSummary; versions: Versions
  processing: { engine_ms: number; retrieval: string; language_model_used: boolean; external_requests: boolean; stages: string[] }
  clinical_review_required: true; disclaimer: string
}
export interface ClinicalMessage { id: string; role: 'user' | 'assistant'; text: string; question_id: string | null; answer_codes: string[]; superseded_by: string | null }
export interface ClinicalEnvelope { id: string; revision: number; token: string; locale: ClinicalLocale; memory_shared: boolean; messages: ClinicalMessage[]; assessment: ClinicalAssessment }

export interface AnatomyAnchor { bone: string; offset: [number, number, number]; to?: string; t?: number }
export interface AnatomyNode {
  id: string; parent: string | null; kind: 'region' | 'structure' | 'group' | 'tooth'; label: Localized; lateral: boolean; fixed_side: 'left' | 'right' | null
  anchor: AnatomyAnchor | null; legacy_region: string | null; internal: boolean; specialty: string | null; photo_visible: boolean | null
  related: { target: string; relation: string; note: string }[]; status: string
}
export interface ClinicalCatalog {
  versions: Record<string, string>; anatomy: AnatomyNode[]; symptoms: { id: string; label: Localized; group: string }[]
  coverage: { conditions: number; red_flags: number; sources: number; chunks: number; known_gaps: string[]; sources_review_overdue: string[]; snapshot_version: string; built_at: string; clinical_review_status: string; by_region: Record<string, { id: string; name: Localized; urgent_condition: boolean }[]> }
  imaging_scope: Record<string, { photo_can_show: Localized; needs_examination: Localized }>
}
export interface ClinicalStatus { available: boolean; language_model_configured: boolean; clinical_review_required: boolean }
export interface SavedAssessmentSummary {
  id: string; created_at: string; locale: ClinicalLocale; anatomy: { id: string; side: ClinicalSide }; anatomy_label: string; urgency: UrgencyLevel; pathway_label: string
  explanations: { condition_id: string; name: string; fit: 'fits' | 'partly_fits' }[]; versions: Versions; previous_id: string | null; review_shared: boolean
}
export interface SavedAssessmentDetail extends SavedAssessmentSummary { messages: ClinicalMessage[]; assessment: ClinicalAssessment }
export type MemoryKind = 'condition' | 'medication' | 'allergy' | 'procedure' | 'risk_factor'
export interface MemoryFact {
  id: string; kind: MemoryKind; status: 'active' | 'resolved' | 'pending_confirmation' | 'corrected' | 'rejected'; provenance: string; source_type: string; source_ref: string | null
  supersedes_id: string | null; label: string; details: string | null; anatomy_id: string | null; location: { page: number; line: number; start: number; end: number; text: string } | null
  confirmed_at: string | null; expires_at: string | null; created_at: string; updated_at: string
}
export interface MemoryState { consent: { version: string; consented_at: string; retention_days: number } | null; facts: MemoryFact[] }
export interface ExtractionResult {
  document_sha256: string; pages: number; characters: number; method: string; unsupported_reason: string | null; raw_file_retained: false; stored_for_confirmation: boolean; pending_fact_ids: string[]
  items: { id: string; kind: string; label: string; value: string | null; text: string; location: { page: number; line: number; start: number; end: number }; certainty: string; status: string }[]
  injection_flags: { page: number; line: number; type: string; text: string }[]
}
export type StreamEvent = { type: 'stage'; stage: string } | { type: 'final'; envelope: ClinicalEnvelope } | { type: 'error'; status: number; message: string }
