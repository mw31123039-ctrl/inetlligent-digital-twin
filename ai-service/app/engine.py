import asyncio
import re
from .schemas import Assessment, Fact, ModelDecision, Source, Explanation
from .questions import CORE, UNKNOWN, relevant_fields, question
from .triage import screen, action, RULESET, LEVELS
from .evidence import normalized

class InvalidDecision(Exception):
    pass

def seeded_facts(messages):
    facts = []
    field = 'symptoms'
    for message in messages:
        if message.role == 'assistant':
            field = message.field or 'symptoms'
        elif message.role == 'user':
            facts.append(Fact(field=field, value=message.text, quote=message.text, message_id=message.id))
    return facts

def validate_decision(decision, messages, documents):
    decision = ModelDecision.model_validate(decision)
    users = {m.id: m for m in messages if m.role == 'user'}
    evidence = {document.id: document for document in documents}
    def symptom_terms(text):
        groups = [r'dry', r'itch', r'pain|hurt|sore|ach[ei]', r'red', r'blur|vision', r'swell|swollen', r'tingl|numb', r'cramp', r'bloat', r'constipat', r'heartburn|reflux', r'nause|sick', r'headache', r'weak']
        return {i for i, pattern in enumerate(groups) if re.search(pattern, text, re.I)}
    for fact in decision.facts:
        message = users.get(fact.message_id)
        if not message or fact.value != fact.quote or fact.quote not in message.text:
            raise InvalidDecision()
    for candidate in decision.explanations:
        document = evidence.get(candidate.condition_id)
        if not document or normalized(candidate.supporting_quote) not in document.text:
            raise InvalidDecision()
        if re.search(r'\b(take|apply|dosage|dose|prescription|prescribed|tablets?|milligrams?|mg|ml)\b', candidate.supporting_quote, re.I):
            # Reference excerpts are for symptoms, not an outlet for medication advice.
            raise InvalidDecision()
        if not candidate.fact_message_ids or any(id not in users for id in candidate.fact_message_ids):
            raise InvalidDecision()
        reported = ' '.join(users[id].text for id in candidate.fact_message_ids)
        if not symptom_terms(reported).intersection(symptom_terms(candidate.supporting_quote)):
            raise InvalidDecision()
    if decision.suggested_urgency != 'not_established' and (not decision.urgency_fact_message_ids or any(id not in users for id in decision.urgency_fact_message_ids)):
        raise InvalidDecision()
    return decision

class AssessmentEngine:
    def __init__(self, provider, retriever, timeout=18):
        self.provider, self.retriever, self.timeout = provider, retriever, timeout

    async def assess(self, request):
        facts = seeded_facts(request.messages)
        urgency = screen(request.messages, request.prior_urgency)
        documents, explanations, sources, limitations = [], [], [], []
        provider_status = 'ready' if self.provider.configured else 'disabled'
        evidence_status = 'not_requested'
        fields = relevant_fields(request.region, facts)
        known = {f.field for f in facts if f.value.lower().strip() not in UNKNOWN}
        answered = {f.field for f in facts}
        missing = [field for field in fields if field not in known]
        eligible = [field for field in fields if field not in answered]
        next_field = eligible[0] if eligible else None
        phase = 'collecting'
        decision = None
        if LEVELS[urgency.level] >= LEVELS['same_day']:
            # No retrieval/provider call may delay this response.
            phase, evidence_status, next_field = 'urgent', 'urgent_bypass', None
        elif request.messages and self.provider.configured:
            try:
                documents = await asyncio.wait_for(self.retriever.retrieve(request.region), timeout=6)
            except Exception:
                documents = []
            evidence_status = 'retrieved' if documents else 'unavailable'
            if not documents:
                limitations.append('Authoritative source retrieval is unavailable. No medical explanations or citations will be invented.')
            try:
                raw = await asyncio.wait_for(self.provider.decide({
                    'region': request.region, 'side': request.side,
                    'messages': [m.model_dump() for m in request.messages],
                    'eligible_fields': eligible, 'known_facts': [f.model_dump() for f in facts],
                    'evidence': [document.__dict__ for document in documents],
                    'minimum_urgency': urgency.model_dump(),
                }), timeout=self.timeout)
                decision = validate_decision(raw, request.messages, documents)
                # Model extraction augments verbatim intake; it never overwrites the user's words.
                merged = {(f.field, f.message_id): f for f in facts}
                for fact in decision.facts:
                    merged[(fact.field, fact.message_id)] = fact
                facts = list(merged.values())
                fields = relevant_fields(request.region, facts)
                known = {f.field for f in facts if f.value.lower().strip() not in UNKNOWN}
                answered = {f.field for f in facts}
                missing = [field for field in fields if field not in known]
                eligible = [field for field in fields if field not in answered]
                if decision.next_question_field is not None and decision.next_question_field not in eligible:
                    raise InvalidDecision()
                next_field = decision.next_question_field or (eligible[0] if eligible else None)
                if LEVELS[decision.suggested_urgency] > LEVELS[urgency.level]:
                    urgency.level = decision.suggested_urgency
                    urgency.reasons.append('The AI identified a concern from your report; a clinician needs to assess it.')
                if LEVELS[urgency.level] >= LEVELS['same_day']:
                    phase, next_field = 'urgent', None
                elif not any(field in missing for field in CORE):
                    phase = 'summary' if not next_field else 'collecting'
                    by_id = {document.id: document for document in documents}
                    for candidate in decision.explanations:
                        doc = by_id[candidate.condition_id]
                        explanations.append(Explanation(
                            condition=doc.title,
                            interpretation='One possible explanation with overlapping symptoms. This conversation cannot confirm it; other causes remain possible.',
                            source_ids=[doc.id], reported_fact_ids=candidate.fact_message_ids,
                        ))
                        if doc.id not in {source.id for source in sources}:
                            sources.append(Source(id=doc.id, title=doc.title, url=doc.url, retrieved_at=doc.retrieved_at, excerpt=candidate.supporting_quote))
                elif not next_field:
                    phase = 'insufficient'
            except (InvalidDecision, ValueError):
                provider_status = 'invalid_response'
                explanations, sources = [], []
                limitations.append('The AI response failed verification. No AI explanation is shown; the next question is limited intake guidance.')
            except Exception:
                provider_status = 'unavailable'
                limitations.append('The AI provider is unavailable or timed out. No AI explanation is shown; limited intake can continue.')
        elif not self.provider.configured:
            limitations.append('AI is not configured. This is limited rule-based intake, not a working medical AI assessment. No AI explanations have been generated.')
        if provider_status != 'ready' and phase != 'urgent':
            phase = 'unavailable'
            explanations, sources = [], []
        if phase != 'urgent' and missing:
            limitations.append('Information is still missing. An examination or further tests may be needed; no diagnosis has been established.')
        if phase == 'summary' and not explanations:
            limitations.append('The available evidence does not support a possible explanation here. Share the reported facts with a clinician.')
        symptoms = [f.value for f in facts if f.field == 'symptoms']
        summary = '\n'.join([
            'USER-REPORTED INFORMATION — not verified examination findings',
            f'Body region: {request.region}; side: {request.side}.',
            *[f'{fact.field.replace("_", " ")}: {fact.value}' for fact in facts],
            'Missing: ' + (', '.join(missing) or 'No further intake fields requested; examination findings remain unavailable.'),
            f'ADVISORY URGENCY: {urgency.level}. ' + ' '.join(urgency.reasons),
            'NEXT ACTION: ' + action(urgency.level),
            'No confirmed diagnosis. Draft, unvalidated triage rules: ' + RULESET['version'],
        ])
        return Assessment(
            selected_region=request.region, side=request.side, reported_symptoms=symptoms, facts=facts,
            unanswered_questions=[question(field, request.region).text for field in missing], urgency=urgency,
            possible_explanations=explanations, recommended_next_action=action(urgency.level), supporting_sources=sources,
            next_question=question(next_field, request.region) if next_field else None,
            clinician_summary=summary, phase=phase, provider_status=provider_status, evidence_status=evidence_status,
            limitations=limitations, triage_rules_version=RULESET['version'],
        )
