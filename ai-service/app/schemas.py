from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Region = Literal['eyes', 'head', 'chest', 'abdomen', 'arms', 'legs']
Side = Literal['unknown', 'left', 'right', 'both', 'center', 'not_applicable']
FieldName = Literal['symptoms', 'warning_signs', 'location', 'onset', 'duration', 'severity', 'related_symptoms', 'medical_history', 'medications', 'allergies']
Urgency = Literal['not_established', 'routine', 'soon', 'same_day', 'emergency']

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Message(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    role: Literal['user', 'assistant']
    text: str = Field(min_length=1, max_length=2000)
    field: FieldName | None = None

class Fact(StrictModel):
    field: FieldName
    value: str = Field(min_length=1, max_length=2000)
    message_id: str = Field(min_length=1, max_length=80)
    quote: str = Field(min_length=1, max_length=2000)

class Question(StrictModel):
    field: FieldName
    text: str
    options: list[str]

class Source(StrictModel):
    id: str
    title: str
    url: str
    retrieved_at: str
    excerpt: str = Field(max_length=160)

class Explanation(StrictModel):
    condition: str
    interpretation: str
    source_ids: list[str]
    reported_fact_ids: list[str]

class Escalation(StrictModel):
    level: Urgency
    reasons: list[str]
    rule_ids: list[str]

class Assessment(StrictModel):
    schema_version: Literal['1.0'] = '1.0'
    selected_region: Region
    side: Side
    reported_symptoms: list[str]
    facts: list[Fact]
    unanswered_questions: list[str]
    urgency: Escalation
    possible_explanations: list[Explanation]
    recommended_next_action: str
    supporting_sources: list[Source]
    next_question: Question | None
    clinician_summary: str
    phase: Literal['collecting', 'summary', 'urgent', 'insufficient', 'unavailable']
    provider_status: Literal['ready', 'disabled', 'unavailable', 'invalid_response']
    evidence_status: Literal['retrieved', 'unavailable', 'not_requested', 'urgent_bypass']
    limitations: list[str]
    triage_rules_version: str
    clinical_review_required: Literal[True] = True
    disclaimer: str = 'AI symptom assistant. This does not replace a clinician’s examination or diagnosis.'

class AssessRequest(StrictModel):
    region: Region
    side: Side = 'unknown'
    messages: list[Message] = Field(max_length=60)
    prior_urgency: Escalation | None = None

# No unrestricted diagnosis, medication advice, probabilities or clinical prose
# can enter the user response through a model-generated string.
class CandidateExplanation(StrictModel):
    condition_id: str
    supporting_quote: str = Field(min_length=20, max_length=160)
    fact_message_ids: list[str] = Field(min_length=1, max_length=10)

class ModelDecision(StrictModel):
    facts: list[Fact] = Field(max_length=30)
    next_question_field: FieldName | None
    explanations: list[CandidateExplanation] = Field(max_length=3)
    suggested_urgency: Literal['not_established', 'soon', 'same_day', 'emergency']
    urgency_fact_message_ids: list[str] = Field(max_length=10)
