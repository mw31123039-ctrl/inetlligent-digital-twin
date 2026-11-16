"""Validated request/response contract for the clinical assessment v2 endpoint.

The JSON Schema in contracts/clinical/assessment.v2.schema.json is exported from these models
(scripts/export-clinical-schema.py) and independently enforced by Laravel before anything reaches a browser.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Locale = Literal['en', 'ar', 'ckb']
Side = Literal['left', 'right', 'both', 'midline', 'unknown']
Urgency = Literal['not_established', 'routine', 'soon', 'same_day', 'emergency']
Provenance = Literal['patient_statement', 'patient_answer', 'patient_memory', 'document_extract', 'clinician_confirmed', 'ai_suggestion']
Extractor = Literal['lexicon', 'structured_answer', 'language_model', 'memory', 'document', 'derived']
Identifier = Field(min_length=1, max_length=96, pattern=r'^[A-Za-z0-9_.:@#~\-]+$')


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


# ------------------------------------------------------------------------------------------- request
class Message(Strict):
    id: str = Field(min_length=1, max_length=80)
    role: Literal['user', 'assistant']
    text: str = Field(min_length=1, max_length=2000)
    question_id: str | None = Field(default=None, max_length=120)
    answer_codes: list[str] = Field(default_factory=list, max_length=20)
    superseded_by: str | None = Field(default=None, max_length=80)


class AnatomySelection(Strict):
    id: str = Field(min_length=3, max_length=64, pattern=r'^[a-z0-9.\-]+$')
    side: Side = 'unknown'


class PatientContextItem(Strict):
    id: str = Field(min_length=1, max_length=80)
    kind: Literal['condition', 'medication', 'allergy', 'procedure', 'risk_factor']
    label: str = Field(min_length=1, max_length=200)
    status: Literal['active', 'resolved', 'unknown'] = 'active'
    provenance: Literal['patient_memory', 'document_extract', 'clinician_confirmed']
    recorded_at: str | None = Field(default=None, max_length=40)


class UrgencyReason(Strict):
    rule_id: str
    text: str
    citation_ids: list[str]
    fact_ids: list[str]


class PriorUrgency(Strict):
    level: Urgency
    rule_ids: list[str] = Field(default_factory=list, max_length=40)


class AssessRequest(Strict):
    locale: Locale = 'en'
    anatomy: AnatomySelection
    messages: list[Message] = Field(default_factory=list, max_length=90)
    patient_context: list[PatientContextItem] = Field(default_factory=list, max_length=60)
    prior_urgency: PriorUrgency | None = None
    max_questions: int = Field(default=12, ge=3, le=25)


# ------------------------------------------------------------------------------------------- response
class Span(Strict):
    message_id: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    quote: str = Field(max_length=2000)


class Fact(Strict):
    id: str
    kind: Literal['symptom', 'attribute', 'trigger', 'risk_factor', 'history', 'medication', 'allergy', 'screen']
    key: str
    value: str
    numeric: float | None = None
    label: str
    status: Literal['present', 'absent', 'uncertain']
    temporal: Literal['current', 'past']
    anatomy_id: str | None = None
    side: Side | None = None
    provenance: Provenance
    extractor: Extractor
    spans: list[Span]
    source_ref: str | None = None


class AnatomyRef(Strict):
    id: str
    label: str
    side: Side
    role: Literal['selected', 'reported', 'related', 'finding']
    relation: str | None = None
    relation_note: str | None = None
    marker: Literal['illustrative_anatomy']
    fact_ids: list[str]
    explanation_ids: list[str]


class Observation(Strict):
    id: str
    text: str
    fact_ids: list[str]
    provenance: Provenance


class Citation(Strict):
    id: str
    source_id: str
    chunk_id: str
    title: str
    publisher: str
    url: str
    quote: str
    lead: str | None
    last_reviewed: str | None
    next_review_due: str | None
    review_overdue: bool
    retrieved_at: str
    licence: str


class EvidenceItem(Strict):
    statement: str
    fact_ids: list[str]
    citation_ids: list[str]


class MissingFeature(Strict):
    key: str
    label: str
    question_id: str | None


class Explanation(Strict):
    id: str
    condition_id: str
    name: str
    fit: Literal['fits', 'partly_fits']
    plain_language: str
    supporting: list[EvidenceItem]
    conflicting: list[EvidenceItem]
    missing: list[MissingFeature]
    pathway: str
    pathway_label: str
    urgent_condition: bool
    scope_note: str | None
    anatomy_ids: list[str]


class MissingInfo(Strict):
    key: str
    label: str
    reason: str
    priority: Literal['safety', 'core', 'discriminating', 'history']


class Contradiction(Strict):
    id: str
    kind: Literal['symptom_presence', 'attribute', 'laterality', 'memory']
    description: str
    fact_ids: list[str]
    message_ids: list[str]
    resolved: bool


class UrgencyResult(Strict):
    level: Urgency
    pathway: str
    pathway_label: str
    action: str
    reasons: list[UrgencyReason]
    safety_screen_completed: bool
    persisted_from_prior: bool
    rules_version: str


class Option(Strict):
    code: str
    label: str


class Question(Strict):
    id: str
    kind: Literal['complaint', 'safety', 'attribute', 'symptom', 'structure', 'side', 'clarify', 'history', 'memory', 'laterality', 'triggers']
    text: str
    purpose: str
    options: list[Option]
    multi_select: bool
    free_text: bool
    discriminates: list[str]


class ClinicianSummary(Strict):
    headline: str
    patient_reported: list[str]
    from_records: list[str]
    observations_note: str
    interpretations: list[str]
    urgency: str
    missing: list[str]
    contradictions: list[str]
    provenance_note: str


class Versions(Strict):
    engine: str
    anatomy: str
    symptoms: str
    knowledge: str
    source_registry: str
    snapshot: str
    language_model: str | None
    prompt: str | None


class Processing(Strict):
    engine_ms: float = Field(ge=0)
    retrieval: Literal['bm25-anatomy-tier-freshness', 'bm25+semantic-rerank']
    language_model_used: bool
    external_requests: bool
    stages: list[str]


class Assessment(Strict):
    schema_version: Literal['humantwin-clinical-assessment-v2'] = 'humantwin-clinical-assessment-v2'
    locale: Locale
    direction: Literal['ltr', 'rtl']
    anatomy: AnatomySelection
    phase: Literal['complaint', 'safety_screen', 'collecting', 'summary', 'urgent', 'insufficient']
    summary: str
    patient_facts: list[Fact]
    anatomical_references: list[AnatomyRef]
    observations: list[Observation]
    possible_explanations: list[Explanation] = Field(max_length=3)
    explanation_status: Literal['supported', 'insufficient_information', 'no_supported_explanation', 'withheld_urgent', 'conflicting']
    missing_information: list[MissingInfo]
    contradictions: list[Contradiction]
    urgency: UrgencyResult
    next_question: Question | None
    related_reading: list[str]
    citations: list[Citation]
    limitations: list[str]
    clinician_summary: ClinicianSummary
    versions: Versions
    processing: Processing
    clinical_review_required: Literal[True] = True
    disclaimer: str
