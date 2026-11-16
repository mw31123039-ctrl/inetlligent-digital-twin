"""Clinical assessment engine v2.

Stateless: every turn rebuilds the case from the full (non-superseded) transcript plus permitted patient
context, so a correction anywhere updates every downstream conclusion. Order of work on each turn:

  1. build structured facts with provenance (structured answers > free-text extraction > patient memory)
  2. detect contradictions and left/right conflicts
  3. evaluate red-flag rules (urgent guidance overrides the interview)
  4. score source-bound conditions (supporting / conflicting / missing evidence; never probabilities)
  5. choose the most informative next question (safety screen first, then expected information gain)
  6. attach verbatim citations and related reading, compose localised text, versions and limitations
"""
import math
import time
from dataclasses import dataclass, field

from . import i18n
from .extract import extract
from .kb import AGAINST, WEIGHTS, Binding, load_kb
from .retrieval import retrieve
from .schemas import (AnatomyRef, AnatomySelection, Assessment, Citation, ClinicianSummary, Contradiction, EvidenceItem, Explanation, Fact, MissingFeature,
                      MissingInfo, Observation, Option, Processing, Question, Span, UrgencyReason, UrgencyResult, Versions)
from .untrusted import clean

ENGINE_VERSION = 'clinical-engine-2026-11-16.1'
LEVELS = {'not_established': 0, 'routine': 1, 'soon': 2, 'same_day': 3, 'emergency': 4}
P_YES = {'typical': .85, 'common': .6, 'possible': .35}
P_AGAINST = {'strong': .08, 'moderate': .2}
BASE_RATE = .15
CORE_ATTRIBUTES = ('onset', 'duration', 'severity')
HISTORY_KEYS = ('medications', 'allergies', 'history')
GENERIC_MATCHES = {'sym:pain', 'sym:swelling', 'sym:redness', 'sym:nausea', 'sym:vomiting', 'sym:fever', 'sym:lump', 'sym:weakness', 'sym:stiffness', 'sym:tender_on_press'}
STRUCTURE_REGIONS = {'body.eyes', 'body.abdomen', 'body.arms', 'body.legs', 'body.head', 'body.back', 'body.mouth'}


class RequestError(ValueError):
    pass


@dataclass
class Assertion:
    message_id: str
    order: int
    status: str
    value: str
    numeric: float | None
    spans: list
    provenance: str
    extractor: str
    temporal: str = 'current'
    anatomy_id: str | None = None
    via_question: str | None = None


@dataclass
class FactState:
    kind: str
    key: str
    assertions: list = field(default_factory=list)
    resolved_by: str | None = None   # 'first' | 'second' after a clarify answer

    def current(self):
        items = [a for a in self.assertions if a.temporal == 'current'] or self.assertions
        if self.resolved_by == 'first':
            return items[0]
        return items[-1]


@dataclass
class Case:
    selected: str
    region: str
    selected_side: str
    facts: dict = field(default_factory=dict)
    asked: list = field(default_factory=list)
    answered: dict = field(default_factory=dict)
    reported_anatomy: dict = field(default_factory=dict)   # anatomy id -> {sides, spans, message_ids}
    side_answers: list = field(default_factory=list)        # (order, side, message_id, via)
    laterality_answer: str | None = None
    unspecific_warning: list = field(default_factory=list)
    screens_done: set = field(default_factory=set)
    clarify_answers: dict = field(default_factory=dict)
    memory_answers: dict = field(default_factory=dict)
    context: list = field(default_factory=list)
    user_turns: int = 0


def _fact_id(kind, key):
    return f'{kind}:{key}'


class Engine:
    def __init__(self, kb=None, language_model=None):
        self._kb = kb
        self.language_model = language_model

    @property
    def kb(self):
        return self._kb or load_kb()

    # =========================================================================================== build
    def build_case(self, request):
        kb = self.kb
        if request.anatomy.id not in kb.anatomy:
            raise RequestError('Unknown anatomy identifier.')
        region = kb.region(request.anatomy.id)
        node = kb.node(request.anatomy.id)
        side = request.anatomy.side
        if node['fixed_side']:
            side = node['fixed_side']  # e.g. FDI 36 is always the patient's left; the anatomy defines the side
        case = Case(selected=request.anatomy.id, region=region, selected_side=side, context=list(request.patient_context))
        last_question = None
        active = [m for m in request.messages if not (m.role == 'user' and m.superseded_by)]
        ids = [m.id for m in request.messages]
        if len(ids) != len(set(ids)):
            raise RequestError('Duplicate message identifiers.')
        for order, message in enumerate(active):
            if message.role == 'assistant':
                last_question = message.question_id
                if message.question_id:
                    case.asked.append(message.question_id)
                continue
            case.user_turns += 1
            question = message.question_id or last_question
            if question:
                case.answered[question] = message.id
            self._apply_message(case, message, question, order)
        self._derive_located_pain(case)
        for item in request.patient_context:
            kind = {'condition': 'history', 'procedure': 'history', 'risk_factor': 'risk_factor', 'medication': 'medication', 'allergy': 'allergy'}[item.kind]
            state = case.facts.setdefault(_fact_id(kind, f'memory:{item.id}'), FactState(kind, f'memory:{item.id}'))
            state.assertions.append(Assertion(item.id, -1, 'present' if item.status == 'active' else 'absent', clean(item.label), None, [], item.provenance if item.provenance != 'patient_memory' else 'patient_memory', 'memory'))
        return case

    LOCATED_PAIN = (('mouth.teeth', 'toothache'), ('body.ears', 'ear_pain'), ('neck.throat', 'sore_throat'), ('chest.chest-wall', 'chest_pain'), ('chest.heart', 'chest_pain'),
                    ('body.chest', 'chest_pain'), ('head.forehead', 'headache'), ('head.temple', 'headache'), ('head.back-of-head', 'headache'), ('body.head', 'headache'))

    def _derive_located_pain(self, case):
        """Pain located at a structure is that structure's specific symptom ("my molar hurts" is toothache).
        Exact-match regions only: jaw-joint pain is not a headache and breast pain is not chest pain."""
        state = case.facts.get(_fact_id('symptom', 'pain'))
        if not state:
            return
        current = state.current()
        anatomy = current.anatomy_id or self.effective_anatomy(case)
        for target, symptom in self.LOCATED_PAIN:
            if self.kb.region(target) != case.region:
                continue  # "pain under my ribs" on an abdomen assessment is not chest pain
            matches = self.kb.within(anatomy, target) if target == 'mouth.teeth' else anatomy == target
            if matches and not case.facts.get(_fact_id('symptom', symptom)):
                derived = FactState('symptom', symptom)
                derived.assertions = [Assertion(a.message_id, a.order, a.status, a.value, a.numeric, a.spans, a.provenance, 'derived', a.temporal, target) for a in state.assertions]
                case.facts[_fact_id('symptom', symptom)] = derived
                return

    def _assert(self, case, kind, key, message, order, status, value='present', numeric=None, spans=(), provenance='patient_statement', extractor='lexicon',
                temporal='current', anatomy_id=None, via=None):
        state = case.facts.setdefault(_fact_id(kind, key), FactState(kind, key))
        state.assertions.append(Assertion(message.id, order, status, value, numeric, list(spans), provenance, extractor, temporal, anatomy_id, via))

    def _apply_message(self, case, message, question, order):
        kb = self.kb
        text = clean(message.text)
        codes = list(message.answer_codes)
        structured = 'structured_answer'

        def span(start=0, end=None):
            end = len(message.text) if end is None else end
            return Span(message_id=message.id, start=start, end=end, quote=message.text[start:end])

        # ---------------------------------------------------------------- structured chips
        for code in codes:
            name, _, value = code.partition(':')
            if name in ('onset', 'pattern', 'course', 'character'):
                self._assert(case, 'attribute', name, message, order, 'present', value, spans=[span()], provenance='patient_answer', extractor=structured, via=question)
            elif name in ('duration', 'severity') and value:
                try:
                    number = float(value)
                except ValueError:
                    continue
                self._assert(case, 'attribute', name, message, order, 'present', value, number, [span()], 'patient_answer', structured, via=question)
            elif name == 'side' and value in ('left', 'right', 'both'):
                case.side_answers.append((order, value, message.id, question))
                if question and question.startswith('laterality'):
                    case.laterality_answer = value
            elif name == 'trigger' and value in kb.symptoms_doc['triggers']:
                self._assert(case, 'trigger', value, message, order, 'present', spans=[span()], provenance='patient_answer', extractor=structured, via=question)
            elif name == 'structure' and value in kb.anatomy:
                entry = case.reported_anatomy.setdefault(value, {'sides': set(), 'spans': [], 'message_ids': set()})
                entry['spans'].append(span()); entry['message_ids'].add(message.id)
            elif name == 'rf' and value in kb.red_flags:
                self._assert(case, 'screen', value, message, order, 'present', spans=[span()], provenance='patient_answer', extractor=structured, via=question)
                for item in kb.knowledge['screen_facts'].get(value, []):
                    self._apply_match_as_fact(case, item, message, order, span(), question)
            elif name in ('yes', 'no', 'unknown') and question and question.startswith('sym:'):
                status = {'yes': 'present', 'no': 'absent', 'unknown': 'uncertain'}[name]
                self._assert(case, 'symptom', question[4:], message, order, status, spans=[span()], provenance='patient_answer', extractor=structured, via=question)
            elif name in ('first', 'second') and question and question.startswith('clarify:'):
                case.clarify_answers[question[8:]] = name
            elif question and question.startswith('memory:') and name in ('yes', 'no'):
                case.memory_answers[question[7:]] = name
            elif name == 'none' and question and question.startswith('safety:'):
                case.screens_done.add(question[7:])
                for flag_id in kb.knowledge['screens'].get(question[7:], []):
                    self._assert(case, 'screen', flag_id, message, order, 'absent', spans=[span()], provenance='patient_answer', extractor=structured, via=question)
            elif name in ('none', 'unknown') and question and question.startswith('history:'):
                key = question.split(':', 1)[1]
                self._assert(case, {'medications': 'medication', 'allergies': 'allergy'}.get(key, 'history'), key, message, order,
                             'absent' if name == 'none' else 'uncertain', 'none' if name == 'none' else 'unknown', spans=[span()], provenance='patient_answer', extractor=structured, via=question)
            elif name == 'unknown' and question and question.startswith('attr:'):
                self._assert(case, 'attribute', question[5:], message, order, 'uncertain', 'unknown', spans=[span()], provenance='patient_answer', extractor=structured, via=question)
            elif name == 'none' and question == 'triggers':
                self._assert(case, 'trigger', 'none', message, order, 'absent', spans=[span()], provenance='patient_answer', extractor=structured, via=question)
        if question and question.startswith('safety:') and any(c.startswith('rf:') for c in codes):
            case.screens_done.add(question[7:])

        # ---------------------------------------------------------------- free text (always parsed; chips also carry text)
        free_text = not codes
        findings = extract(kb, text, question if free_text else None)
        anatomy_mentions = [f for f in findings if f.kind == 'anatomy']
        for finding in findings:
            spans = [Span(message_id=message.id, start=finding.start, end=finding.end, quote=message.text[finding.start:finding.end])]
            if finding.kind == 'symptom':
                anatomy_id = finding.anatomy_id or self._locate(case, finding, anatomy_mentions)
                scope = kb.symptoms.get(finding.key, {}).get('scope') or []
                mentioned = {kb.region(m.key) for m in anatomy_mentions}
                if scope and not any(r in scope for r in {case.region, *mentioned}):
                    continue  # e.g. "burning" in a urinary complaint is not an eye symptom
                self._assert(case, 'symptom', finding.key, message, order, finding.status, spans=spans, temporal=finding.temporal, anatomy_id=anatomy_id,
                             extractor='derived' if finding.extra.get('derived_from') else 'lexicon', via=question)
            elif finding.kind == 'attribute' and free_text:
                self._assert(case, 'attribute', finding.key, message, order, 'present', finding.value, finding.numeric, spans, via=question)
            elif finding.kind == 'trigger' and free_text:
                self._assert(case, 'trigger', finding.key, message, order, 'present', spans=spans, via=question)
            elif finding.kind == 'anatomy':
                entry = case.reported_anatomy.setdefault(finding.key, {'sides': set(), 'spans': [], 'message_ids': set()})
                entry['spans'].extend(spans); entry['message_ids'].add(message.id)
                if finding.side:
                    entry['sides'].add(finding.side)
                    if kb.within(finding.key, case.region) or kb.within(case.selected, finding.key):
                        case.side_answers.append((order, finding.side, message.id, None))
            elif finding.kind == 'side' and free_text:
                case.side_answers.append((order, finding.value, message.id, question))
                if question and question.startswith('laterality'):
                    case.laterality_answer = finding.value
        if not free_text or not question:
            return
        answers = {f.key for f in findings if f.kind == 'answer'}
        whole = [Span(message_id=message.id, start=0, end=len(message.text), quote=message.text)]
        if question.startswith('sym:') and not any(f.kind == 'symptom' and f.key == question[4:] for f in findings):
            if 'yes' in answers:
                self._assert(case, 'symptom', question[4:], message, order, 'present', spans=whole, provenance='patient_answer', via=question)
            elif 'no' in answers:
                self._assert(case, 'symptom', question[4:], message, order, 'absent', spans=whole, provenance='patient_answer', via=question)
            elif 'unsure' in answers:
                self._assert(case, 'symptom', question[4:], message, order, 'uncertain', spans=whole, provenance='patient_answer', via=question)
        elif question.startswith('safety:'):
            region = question[7:]
            positives = [f for f in findings if f.kind == 'symptom' and f.status == 'present']
            if 'no' in answers and not positives:
                case.screens_done.add(region)
                for flag_id in kb.knowledge['screens'].get(region, []):
                    self._assert(case, 'screen', flag_id, message, order, 'absent', spans=whole, provenance='patient_answer', via=question)
            elif 'yes' in answers or positives:
                case.screens_done.add(region)
                if not positives:
                    case.unspecific_warning.append(message.id)
            elif 'unsure' in answers:
                case.unspecific_warning.append(message.id)
                case.screens_done.add(region)
        elif question.startswith('history:'):
            key = question.split(':', 1)[1]
            kind = {'medications': 'medication', 'allergies': 'allergy'}.get(key, 'history')
            if 'no' in answers and len(text) < 40:
                self._assert(case, kind, key, message, order, 'absent', 'none', spans=whole, provenance='patient_answer', via=question)
            elif 'unsure' in answers and len(text) < 40:
                self._assert(case, kind, key, message, order, 'uncertain', 'unknown', spans=whole, provenance='patient_answer', via=question)
            else:
                self._assert(case, kind, key, message, order, 'present', text[:200], spans=whole, provenance='patient_answer', via=question)
        elif question.startswith('clarify:'):
            if 'yes' in answers or 'first' in text.lower():
                case.clarify_answers[question[8:]] = 'first'
            else:
                case.clarify_answers[question[8:]] = 'second'
        elif question.startswith('memory:'):
            if 'yes' in answers:
                case.memory_answers[question[7:]] = 'yes'
            elif 'no' in answers:
                case.memory_answers[question[7:]] = 'no'
        elif question.startswith('attr:') and 'unsure' in answers and not any(f.kind == 'attribute' and f.key == question[5:] for f in findings):
            self._assert(case, 'attribute', question[5:], message, order, 'uncertain', 'unknown', spans=whole, via=question)

    def _apply_match_as_fact(self, case, match, message, order, span, question):
        kind, _, rest = match.partition(':')
        if kind == 'sym':
            self._assert(case, 'symptom', rest, message, order, 'present', spans=[span], provenance='patient_answer', extractor='structured_answer', via=question)
        elif kind == 'attr':
            name, _, value = rest.partition('=')
            if name == 'side':
                if value == 'one' and case.selected_side in ('left', 'right'):
                    case.side_answers.append((order, case.selected_side, message.id, question))
                return
            numeric = float(value) if value.replace('.', '', 1).isdigit() else None
            self._assert(case, 'attribute', name, message, order, 'present', value, numeric, [span], 'patient_answer', 'structured_answer', via=question)

    def _locate(self, case, finding, mentions):
        """Where a symptom is. A symptom's own anatomy ("toothache" -> teeth) beats a nearby word ("back tooth");
        a nearby word only relocates a symptom inside the selected region, unless only a region was selected."""
        kb = self.kb
        implied = kb.symptoms.get(finding.key, {}).get('implies_anatomy')
        nearest = self._nearest_anatomy(finding, mentions)
        if implied and kb.node(implied) and kb.node(implied)['kind'] != 'region':
            return nearest if nearest and kb.within(nearest, implied) else implied
        if nearest:
            selected_is_structure = case.selected != case.region
            if kb.within(nearest, case.region) or not selected_is_structure:
                if implied and not kb.within(nearest, implied):
                    return implied
                return nearest
        return implied

    def _nearest_anatomy(self, finding, mentions):
        best, distance = None, 60
        for mention in mentions:
            gap = min(abs(mention.start - finding.end), abs(finding.start - mention.end))
            if gap < distance:
                best, distance = mention.key, gap
        return best

    # =========================================================================================== resolve
    def effective_anatomy(self, case):
        kb = self.kb
        inside = [a for a in case.reported_anatomy if kb.within(a, case.region) and a != case.region]
        if kb.within(case.selected, case.region) and case.selected != case.region:
            return case.selected
        deepest = sorted(inside, key=lambda a: len(kb.ancestors(a)), reverse=True)
        return deepest[0] if deepest else case.selected

    def resolve_side(self, case):
        reported = [side for _, side, _, via in case.side_answers if via is None]
        answered = [side for _, side, _, via in case.side_answers if via is not None]
        conflict = None
        if case.laterality_answer:
            return case.laterality_answer, None
        if case.selected_side in ('left', 'right'):
            opposite = [s for s in reported + answered if s in ('left', 'right') and s != case.selected_side]
            if opposite:
                conflict = opposite[-1]
        if conflict:
            return case.selected_side, conflict
        if answered:
            return answered[-1], None
        if reported:
            values = set(reported)
            return ('both' if len(values) > 1 or 'both' in values else reported[-1]), None
        return case.selected_side, None

    def present(self, case, key, anatomy=None, kind='symptom'):
        state = case.facts.get(_fact_id(kind, key))
        if not state:
            return None
        current = state.current()
        if current.temporal != 'current':
            return None
        if anatomy:
            fact_anatomy = current.anatomy_id or self.effective_anatomy(case)
            if not (self.kb.within(fact_anatomy, anatomy) or self.kb.within(anatomy, fact_anatomy)):
                return None
        return current

    def attribute(self, case, name):
        state = case.facts.get(_fact_id('attribute', name))
        if not state:
            return None
        current = state.current()
        return None if current.status == 'uncertain' else current

    EXCLUDE = {'eyelid': ('eye.upper-eyelid', 'eye.lower-eyelid', 'eye.eyelid-margin', 'eye.meibomian-glands', 'eye.eyelashes')}

    def holds(self, case, item, side):
        """A red-flag clause item: `!x` holds when x is not positively present."""
        if item.startswith('!'):
            return self.match(case, item[1:], side) is not True
        return self.match(case, item, side) is True

    def match(self, case, expression, side):
        """True / False / None (unknown) for one feature or clause item. `sym:k@a!g` requires anatomy a, excluding group g."""
        kind, _, rest = expression.partition(':')
        if kind == 'sym':
            key, _, anatomy = rest.partition('@')
            anatomy, _, excluded = anatomy.partition('!')
            state = case.facts.get(_fact_id('symptom', key))
            if not state:
                return None
            if excluded:
                fact_anatomy = state.current().anatomy_id or self.effective_anatomy(case)
                if any(self.kb.within(fact_anatomy, a) for a in self.EXCLUDE[excluded]):
                    return None
            current = self.present(case, key, anatomy or None)
            if current is None:
                return False if state.current().status == 'absent' else None
            return {'present': True, 'absent': False}.get(current.status)
        if kind == 'trig':
            state = case.facts.get(_fact_id('trigger', rest))
            if state:
                return True
            return False if case.facts.get(_fact_id('trigger', 'none')) else None
        if kind == 'attr':
            for op in ('>=', '<=', '='):
                if op in rest:
                    name, value = rest.split(op, 1)
                    break
            if name == 'side':
                if side in ('unknown', None):
                    return None
                return (side in ('left', 'right')) if value == 'one' else side == value
            current = self.attribute(case, name)
            if current is None:
                return None
            if op == '=':
                return current.value == value if current.numeric is None or name not in ('severity', 'duration') else current.numeric == float(value)
            if current.numeric is None:
                return None
            return current.numeric >= float(value) if op == '>=' else current.numeric <= float(value)
        return None

    def contradictions(self, case, locale):
        out = []
        for fact_id, state in case.facts.items():
            if state.kind not in ('symptom', 'attribute') or state.resolved_by:
                continue
            items = [a for a in state.assertions if a.temporal == 'current' and a.extractor != 'derived' and a.status != 'uncertain']
            if len(items) < 2:
                continue
            first, last = items[0], items[-1]
            conflict = False
            if state.kind == 'symptom' and first.message_id != last.message_id and first.status != last.status:
                conflict = True
            if state.kind == 'attribute' and first.message_id != last.message_id:
                if state.key in ('onset',) and first.value != last.value:
                    conflict = True
                if state.key == 'duration' and first.numeric and last.numeric and max(first.numeric, last.numeric) / max(.1, min(first.numeric, last.numeric)) > 4:
                    conflict = True
            if conflict:
                answer = case.clarify_answers.get(fact_id)
                if answer:
                    state.resolved_by = answer
                quote_a = first.spans[0].quote if first.spans else first.value
                quote_b = last.spans[0].quote if last.spans else last.value
                out.append({'id': f'contradiction:{fact_id}', 'kind': 'symptom_presence' if state.kind == 'symptom' else 'attribute', 'fact_id': fact_id,
                            'description': i18n.t('contradiction_symptom', locale, a=quote_a[:80], b=quote_b[:80]), 'a': quote_a[:80], 'b': quote_b[:80],
                            'message_ids': [first.message_id, last.message_id], 'resolved': bool(answer)})
        # Saved history disagreeing with a new "none" answer.
        for key, kind in (('allergies', 'allergy'), ('medications', 'medication')):
            answer = case.facts.get(_fact_id(kind, key))
            memory = [s for s in case.facts.values() if s.kind == kind and s.key.startswith('memory:') and s.current().status == 'present']
            if answer and memory and answer.current().value == 'none':
                item_id = memory[0].key[7:]
                resolved = item_id in case.memory_answers
                out.append({'id': f'contradiction:memory:{item_id}', 'kind': 'memory', 'fact_id': _fact_id(kind, memory[0].key),
                            'description': i18n.t('contradiction_memory', locale, a=memory[0].current().value[:80], b='none'), 'a': memory[0].current().value[:80], 'b': 'none',
                            'message_ids': [answer.current().message_id], 'resolved': resolved})
        return out

    # =========================================================================================== safety
    def red_flags(self, case, side):
        kb = self.kb
        regions = self.case_regions(case)
        fired = []
        for rule_id, rule in kb.red_flags.items():
            if rule['scope'] and not any(r in regions for r in rule['scope']):
                screen = self.present(case, rule_id, kind='screen')
                if not (screen and screen.status == 'present'):
                    continue
            screen = case.facts.get(_fact_id('screen', rule_id))
            if screen and screen.current().status == 'present':
                fired.append(rule)
                continue
            if all(any(self.holds(case, item, side) for item in clause.split('|')) for clause in rule['when']):
                fired.append(rule)
        return fired

    def case_regions(self, case):
        kb = self.kb
        regions = {case.region}
        for anatomy_id in case.reported_anatomy:
            regions.add(kb.region(anatomy_id))
        for state in case.facts.values():
            current = state.current()
            if state.kind == 'symptom' and current.anatomy_id and current.status == 'present':
                regions.add(kb.region(current.anatomy_id))
        return {r for r in regions if r}

    # =========================================================================================== reasoning
    def score_conditions(self, case, side):
        kb = self.kb
        regions = self.case_regions(case)
        results = []
        for condition in kb.conditions:
            condition_regions = {kb.region(a) for a in condition['anatomy']}
            if not condition_regions & regions:
                continue
            if condition.get('requires_anatomy'):
                located = {self.effective_anatomy(case), *case.reported_anatomy}
                if not any(kb.within(a, target) for a in located for target in condition['anatomy']):
                    continue
            present, absent_typical, unknown, against = [], [], [], []
            structures = [a for a in condition['anatomy'] if kb.node(a) and kb.node(a)['kind'] != 'region']

            def fact_anatomy_of(feature):
                state = case.facts.get(_fact_id('symptom', feature['match'][4:].split('@')[0]))
                return (state.current().anatomy_id if state else None) or self.effective_anatomy(case)

            def located(feature):
                # A symptom reported at a specific structure only supports conditions of a compatible structure.
                if not feature['match'].startswith('sym:'):
                    return True
                anatomy = fact_anatomy_of(feature)
                return any(kb.within(anatomy, a) or kb.within(a, anatomy) for a in condition['anatomy'])

            def specific(feature):
                """Generic findings (pain, swelling, side...) only count as specific when located at this condition's structure."""
                if not feature['match'].startswith('sym:'):
                    return False  # timing, side and triggers support a match but cannot carry it alone
                if feature['match'] not in GENERIC_MATCHES:
                    return True
                anatomy = fact_anatomy_of(feature)
                return kb.node(anatomy)['kind'] != 'region' and any(kb.within(anatomy, a) for a in structures)

            for feature in condition['features']:
                value = self.match(case, feature['match'], side) if located(feature) else None
                if value is True:
                    present.append(feature)
                elif value is False and feature['weight'] == 'typical' and feature['match'].startswith('sym:'):
                    absent_typical.append(feature)
                elif value is None:
                    unknown.append(feature)
            for feature in condition['against']:
                if self.match(case, feature['match'], side) is True:
                    against.append(feature)
            # A located `pain` derived from a specific word ("toothache") must not count twice.
            if any(f['match'] in ('sym:headache', 'sym:chest_pain', 'sym:toothache', 'sym:ear_pain', 'sym:sore_throat') for f in present):
                present = [f for f in present if f['match'] != 'sym:pain']
            if not any(f['match'].startswith('sym:') for f in present):
                continue
            score = sum(WEIGHTS[f['weight']] for f in present) - sum(AGAINST[f['strength']] for f in against) - .75 * sum(WEIGHTS[f['weight']] for f in absent_typical)
            typical = sum(1 for f in present if f['weight'] == 'typical')
            specific_typical = sum(1 for f in present if f['weight'] == 'typical' and specific(f))
            strong_against = any(f['strength'] == 'strong' for f in against)
            structure_bonus = .5 if any(kb.within(self.effective_anatomy(case), a) or kb.within(a, self.effective_anatomy(case)) for a in condition['anatomy'] if a != kb.region(a)) else 0
            score += structure_bonus
            fit = None
            if score >= 5 and specific_typical >= 1 and not strong_against:
                fit = 'fits'
            elif score >= 2 and (typical >= 1 or len(present) >= 2):
                fit = 'partly_fits'
            results.append({'condition': condition, 'score': score, 'present': present, 'absent_typical': absent_typical, 'unknown': unknown, 'against': against, 'fit': fit,
                            'strong_against': strong_against})
        results.sort(key=lambda r: (-r['score'], r['condition']['id']))
        return results

    def distribution(self, scored):
        pool = [r for r in scored if r['score'] > 0][:8]
        if not pool:
            return [], []
        weights = [math.exp(min(r['score'], 12) / 2.0) for r in pool]
        other = .3 * sum(weights) / max(1, len(weights)) + .2
        total = sum(weights) + other
        return pool, [w / total for w in weights] + [other / total]

    @staticmethod
    def entropy(probabilities):
        return -sum(p * math.log(p) for p in probabilities if p > 0)

    def information_gain(self, pool, probabilities, likelihood):
        """Expected entropy reduction for a yes/no question. likelihood(condition) -> P(yes | condition)."""
        prior = self.entropy(probabilities)
        p_yes_c = [likelihood(r['condition']) for r in pool] + [BASE_RATE]
        p_yes = sum(p * q for p, q in zip(probabilities, p_yes_c))
        if p_yes <= 0 or p_yes >= 1:
            return 0.0
        post_yes = [p * q / p_yes for p, q in zip(probabilities, p_yes_c)]
        post_no = [p * (1 - q) / (1 - p_yes) for p, q in zip(probabilities, p_yes_c)]
        return prior - (p_yes * self.entropy(post_yes) + (1 - p_yes) * self.entropy(post_no))

    @staticmethod
    def likelihood_for(match):
        def inner(condition):
            for feature in condition['features']:
                if feature['match'] == match:
                    return P_YES[feature['weight']]
            for feature in condition['against']:
                if feature['match'] == match:
                    return P_AGAINST[feature['strength']]
            return BASE_RATE
        return inner

    # =========================================================================================== questions
    def choose_question(self, case, side, laterality_conflict, contradictions, scored, locale, max_questions):
        kb = self.kb
        knowledge = kb.knowledge
        asked = set(case.asked)
        if case.user_turns == 0:
            return self.complaint_question(case, locale)
        question_count = sum(1 for q in case.asked if q != 'complaint')
        screen_id = f'safety:{case.region}'
        if case.region in knowledge['screens'] and case.region not in case.screens_done and screen_id not in asked:
            return self.safety_question(case, locale)
        for item in contradictions:
            if not item['resolved'] and item['kind'] != 'memory' and f"clarify:{item['fact_id']}" not in asked:
                q = knowledge['questions']['clarify']
                return Question(id=f"clarify:{item['fact_id']}", kind='clarify', text=q['text'][locale].format(a=item['a'], b=item['b']), purpose=q['purpose'][locale],
                                options=[Option(code=c, label=l[locale]) for c, l in q['options']], multi_select=False, free_text=True, discriminates=[])
        if laterality_conflict and 'laterality' not in asked:
            q = knowledge['questions']['laterality']
            return Question(id='laterality', kind='laterality', text=q['text'][locale].format(selected=i18n.side_word(case.selected_side, locale), said=i18n.side_word(laterality_conflict, locale)),
                            purpose=q['purpose'][locale], options=[Option(code=c, label=l[locale]) for c, l in q['options']], multi_select=False, free_text=True, discriminates=[])
        if question_count >= max_questions:
            return None
        effective = self.effective_anatomy(case)
        profile = knowledge['region_profiles'].get(case.region, {'attributes': list(CORE_ATTRIBUTES), 'triggers': []})
        if kb.is_lateral(effective) and side == 'unknown' and 'attr:side' not in asked and 'side' in profile['attributes']:
            return self.attribute_question('side', locale)
        candidates = []
        pool, probabilities = self.distribution(scored)
        # Attribute questions: information gain plus a safety bonus when an answer could complete a red-flag rule.
        for name in profile['attributes']:
            if name == 'side' or f'attr:{name}' in asked or case.facts.get(_fact_id('attribute', name)):
                continue
            gain = 0.0
            values = kb.symptoms_doc['attributes'].get(name, {}).get('values', {}) if name not in ('duration', 'severity') else {}
            for value in values:
                if pool:
                    gain = max(gain, self.information_gain(pool, probabilities, self.likelihood_for(f'attr:{name}={value}')))
            bonus = .35 if name in CORE_ATTRIBUTES else .1
            if self.completes_red_flag(case, side, f'attr:{name}'):
                bonus += 1.0
            candidates.append((gain + bonus, 'attr', name, []))
        # Discriminating symptom questions from the leading candidates.
        seen = set()
        for result in pool[:5]:
            for feature in result['unknown'] + [f for f in result['condition']['against']]:
                match = feature['match']
                if not match.startswith('sym:') or match in seen:
                    continue
                seen.add(match)
                key = match[4:]
                if f'sym:{key}' in asked or case.facts.get(_fact_id('symptom', key)):
                    continue
                gain = self.information_gain(pool, probabilities, self.likelihood_for(match))
                if self.completes_red_flag(case, side, match):
                    gain += .8
                tops = sorted(pool, key=lambda r: -abs(self.likelihood_for(match)(r['condition']) - BASE_RATE))[:2]
                candidates.append((gain, 'sym', key, [r['condition']['id'] for r in tops]))
        if case.region in STRUCTURE_REGIONS and effective == case.region and 'structure' not in asked and kb.children.get(case.region) and case.region != 'body.mouth':
            candidates.append((.3, 'structure', case.region, []))
        if profile.get('triggers') and 'triggers' not in asked and not any(s.kind == 'trigger' for s in case.facts.values()) and question_count >= 2:
            gain = 0.0
            for trigger in profile['triggers']:
                if pool:
                    gain = max(gain, self.information_gain(pool, probabilities, self.likelihood_for(f'trig:{trigger}')))
            candidates.append((gain + .05, 'triggers', 'triggers', []))
        candidates.sort(key=lambda c: -c[0])
        if candidates and candidates[0][0] >= .12:
            score, kind, key, discriminates = candidates[0]
            if kind == 'attr':
                return self.attribute_question(key, locale)
            if kind == 'sym':
                return self.symptom_question(key, discriminates, locale)
            if kind == 'structure':
                return self.structure_question(case, locale)
            return self.trigger_question(profile['triggers'], locale)
        # History near the end: confirm saved history instead of asking again.
        for key, kind in (('medications', 'medication'), ('allergies', 'allergy')):
            memory = [s for s in case.facts.values() if s.kind == kind and s.key.startswith('memory:') and s.current().status == 'present']
            if memory and f'memory:{memory[0].key[7:]}' not in asked and memory[0].key[7:] not in case.memory_answers:
                q = knowledge['questions']['memory']
                return Question(id=f'memory:{memory[0].key[7:]}', kind='memory', text=q['text'][locale].format(item=memory[0].current().value[:80]), purpose=q['purpose'][locale],
                                options=[Option(code=c, label=l[locale]) for c, l in q['options']], multi_select=False, free_text=False, discriminates=[])
            if not memory and f'history:{key}' not in asked and not case.facts.get(_fact_id(kind, key)) and question_count >= 3:
                return self.history_question(key, locale)
        return None

    def completes_red_flag(self, case, side, expression):
        """Would a positive answer to `expression` complete a red flag whose other clauses already hold?"""
        for rule in self.kb.red_flags.values():
            clauses = rule['when']
            if not any(expression == item.split('@')[0] or (expression.startswith('attr:') and item.startswith(expression)) for clause in clauses for item in clause.split('|')):
                continue
            others = [c for c in clauses if not any(item.split('@')[0] == expression or (expression.startswith('attr:') and item.startswith(expression)) for item in c.split('|'))]
            if others and all(any(self.holds(case, item, side) for item in clause.split('|')) for clause in others):
                return True
        return False

    def complaint_question(self, case, locale):
        label = self.kb.label(case.selected, locale)
        return Question(id='complaint', kind='complaint', text=i18n.t('complaint', locale, anatomy=label), purpose=i18n.t('complaint_purpose', locale), options=[], multi_select=False,
                        free_text=True, discriminates=[])

    def safety_question(self, case, locale):
        knowledge = self.kb.knowledge
        q = knowledge['questions']['safety']
        options = [Option(code=f'rf:{flag_id}', label=self.kb.red_flags[flag_id]['screen_label'][locale]) for flag_id in knowledge['screens'][case.region] if self.kb.red_flags[flag_id].get('screen_label')]
        options.append(Option(code='none', label=i18n.t('none_of_these', locale)))
        return Question(id=f'safety:{case.region}', kind='safety', text=q['text'][locale], purpose=q['purpose'][locale], options=options, multi_select=True, free_text=True, discriminates=[])

    def attribute_question(self, name, locale):
        q = self.kb.knowledge['questions'][name]
        return Question(id=f'attr:{name}', kind='side' if name == 'side' else 'attribute', text=q['text'][locale], purpose=q['purpose'][locale],
                        options=[Option(code=c, label=l[locale]) for c, l in q['options']], multi_select=False, free_text=True, discriminates=[])

    def symptom_question(self, key, discriminates, locale):
        kb = self.kb
        q = kb.knowledge['questions']['symptom']
        label = kb.symptoms[key]['label'][locale]
        names = [next(c['name'][locale] for c in kb.conditions if c['id'] == d) for d in discriminates]
        purpose = q['purpose'][locale].format(a=names[0], b=names[1]) if len(names) >= 2 else q['purpose_single'][locale].format(a=names[0]) if names else i18n.t('missing_feature_reason', locale)
        return Question(id=f'sym:{key}', kind='symptom', text=q['text'][locale].format(label=label), purpose=purpose,
                        options=[Option(code=c, label=l[locale]) for c, l in q['options']], multi_select=False, free_text=True, discriminates=discriminates)

    def structure_question(self, case, locale):
        kb = self.kb
        q = kb.knowledge['questions']['structure']
        children = [c for c in kb.children.get(case.region, []) if kb.node(c)['kind'] != 'tooth'][:8]
        options = [Option(code=f'structure:{c}', label=kb.label(c, locale)) for c in children]
        return Question(id='structure', kind='structure', text=q['text'][locale], purpose=q['purpose'][locale], options=options, multi_select=False, free_text=True, discriminates=[])

    def trigger_question(self, triggers, locale):
        kb = self.kb
        q = kb.knowledge['questions']['triggers']
        options = [Option(code=f'trigger:{t}', label=kb.symptoms_doc['triggers'][t]['label'][locale]) for t in triggers]
        options.append(Option(code='none', label=i18n.t('none_of_these', locale)))
        return Question(id='triggers', kind='triggers', text=q['text'][locale], purpose=q['purpose'][locale], options=options, multi_select=True, free_text=True, discriminates=[])

    def history_question(self, key, locale):
        q = self.kb.knowledge['questions'][key]
        return Question(id=f'history:{key}', kind='history', text=q['text'][locale], purpose=q['purpose'][locale],
                        options=[Option(code=c, label=l[locale]) for c, l in q['options']], multi_select=False, free_text=True, discriminates=[])

    # =========================================================================================== compose
    async def assess(self, request, progress=None):
        started = time.perf_counter()
        stages = []

        async def stage(name):
            stages.append(name)
            if progress:
                await progress(name)

        kb = self.kb
        locale = request.locale
        await stage('extracting')
        case = self.build_case(request)
        language_model_used = False
        if self.language_model and getattr(self.language_model, 'configured', False):
            language_model_used = await self._augment_with_language_model(case, request)
        side, laterality_conflict = self.resolve_side(case)
        contradictions = self.contradictions(case, locale)
        await stage('screening')
        fired = self.red_flags(case, side)
        await stage('reasoning')
        scored = self.score_conditions(case, side)
        citations: dict = {}

        def cite(binding):
            if binding is None:
                return None
            key = (binding.chunk_id, binding.unit_index)
            if key not in citations:
                source = kb.source(binding.source_id)
                citations[key] = Citation(id=f'c{len(citations) + 1}', source_id=binding.source_id, chunk_id=binding.chunk_id, title=source['title'], publisher=source['publisher'],
                                          url=source['url'], quote=binding.text, lead=binding.lead, last_reviewed=source.get('last_reviewed'), next_review_due=source.get('next_review_due'),
                                          review_overdue=kb.review_overdue(binding.source_id), retrieved_at=source['retrieved_at'], licence=source['usage_rights']['licence'])
            return citations[key].id

        facts = self.facts_out(case, side, locale)
        fact_ids = {f.id for f in facts}

        # ---------------------------------------------------------------- urgency
        reasons, level, pathway = [], 'not_established', None
        for rule in sorted(fired, key=lambda r: -LEVELS[r['urgency']]):
            if LEVELS[rule['urgency']] > LEVELS[level]:
                level, pathway = rule['urgency'], rule['pathway']
            related = [f.id for f in facts if any(item.split('@')[0] in (f'sym:{f.key}', f'attr:{f.key}') or item.startswith(f'attr:{f.key}') for clause in rule['when'] for item in clause.split('|'))]
            reasons.append(UrgencyReason(rule_id=rule['id'], text=rule['reason'][locale], citation_ids=[c for c in [cite(rule['binding'])] if c], fact_ids=[i for i in related if i in fact_ids]))
        if case.unspecific_warning and LEVELS[level] < LEVELS['same_day']:
            level, pathway = 'same_day', 'urgent_same_day'
            reasons.append(UrgencyReason(rule_id='unspecific-warning-screen', text=i18n.t('unspecific_warning', locale), citation_ids=[], fact_ids=[]))
        screen_done = case.region in case.screens_done or case.region not in kb.knowledge['screens']
        explanations, explanation_status = [], 'insufficient_information'
        informative = sum(1 for f in facts if f.kind in ('symptom', 'attribute', 'trigger') and f.status == 'present' and f.provenance != 'patient_memory')
        candidates = [r for r in scored if r['fit']][:3]
        for result in candidates:
            condition = result['condition']
            if condition['urgent_condition'] and result['fit'] == 'fits':
                urgency = kb.knowledge['pathways'][condition['pathway']]['urgency']
                if LEVELS[urgency] > LEVELS[level]:
                    level, pathway = urgency, condition['pathway']
                reasons.append(UrgencyReason(rule_id=f"condition:{condition['id']}", text=i18n.t('urgent_condition_reason', locale, condition=condition['name'][locale]),
                                             citation_ids=[c for c in [cite(f['binding']) for f in result['present'][:1]] if c], fact_ids=[]))
        persisted = False
        if request.prior_urgency and LEVELS[request.prior_urgency.level] >= LEVELS['same_day'] and LEVELS[request.prior_urgency.level] > LEVELS[level]:
            level, persisted = request.prior_urgency.level, True
            pathway = 'emergency' if level == 'emergency' else 'urgent_same_day'
            reasons.append(UrgencyReason(rule_id='prior-urgent-guidance', text=i18n.t('prior_urgency', locale), citation_ids=[], fact_ids=[]))
        urgent = LEVELS[level] >= LEVELS['same_day']

        if urgent:
            explanation_status = 'withheld_urgent'
        elif informative >= 2 and screen_done:
            if candidates:
                await stage('retrieving')
                for result in candidates:
                    explanations.append(self.explanation_out(result, case, side, facts, locale, cite))
                explanation_status = 'supported' if any(e.fit == 'fits' for e in explanations) else 'conflicting' if all(r['strong_against'] for r in candidates) else 'supported'
            else:
                explanation_status = 'no_supported_explanation'
        if not urgent and screen_done and not fired and explanations:
            # Only a well-fitting explanation sets the care pathway; partial matches never escalate or reassure.
            top = explanations[0]
            pathway = top.pathway if top.fit == 'fits' else 'gp_routine'
            level = kb.knowledge['pathways'][pathway]['urgency']
            reasons.append(UrgencyReason(rule_id='safety-screen-clear', text=i18n.t('screen_clear', locale), citation_ids=[], fact_ids=[]))

        # ---------------------------------------------------------------- questions and missing information
        next_question = None if urgent else self.choose_question(case, side, laterality_conflict, contradictions, scored, locale, request.max_questions)
        if level == 'same_day' and not screen_done and f'safety:{case.region}' not in case.asked:
            # Same-day guidance must not hide an emergency: the one-tap safety check is still offered (nothing else).
            next_question = self.safety_question(case, locale)
        missing = self.missing_out(case, side, scored, screen_done, locale)

        # ---------------------------------------------------------------- related reading (BM25 x anatomy x tier x freshness)
        concepts = [kb.symptoms[f.key]['label']['en'] for f in facts if f.kind == 'symptom' and f.status == 'present' and f.key in kb.symptoms]
        concepts += [kb.label(self.effective_anatomy(case), 'en')] + [kb.conditions_by_id[e.condition_id]['name']['en'] for e in explanations]
        related_ids = []
        if concepts and case.user_turns:
            used = {key[0] for key in citations}
            for item in retrieve(kb, concepts, self.case_regions(case), used):
                chunk = kb.chunks[item.chunk_id]
                unit = chunk['units'][item.unit_index]
                related_ids.append(cite(Binding(chunk['source_id'], item.chunk_id, item.unit_index, unit['text'], unit.get('lead'))))
        await stage('composing')
        pathway = pathway or None
        pathway_spec = kb.knowledge['pathways'].get(pathway) if pathway else None
        urgency = UrgencyResult(level=level, pathway=pathway or 'not_established', pathway_label=pathway_spec['label'][locale] if pathway_spec else i18n.t('not_established_label', locale),
                                action=pathway_spec['action'][locale] if pathway_spec else i18n.t('not_established_action', locale), reasons=reasons,
                                safety_screen_completed=screen_done, persisted_from_prior=persisted, rules_version=kb.knowledge['version'])
        phase = 'urgent' if urgent else 'complaint' if case.user_turns == 0 else 'safety_screen' if next_question and next_question.kind == 'safety' else \
            'collecting' if next_question else 'summary' if informative else 'insufficient'
        citation_list = sorted(citations.values(), key=lambda c: int(c.id[1:]))
        limitations = self.limitations_out(locale, explanation_status, screen_done, citation_list, case, language_model_used)
        anatomy_refs = self.anatomy_out(case, side, facts, explanations, locale)
        observations = self.observations_out(facts, locale)
        summary = self.summary_out(case, side, facts, urgency, locale)
        clinician = self.clinician_out(case, side, facts, explanations, urgency, missing, contradictions, citation_list)
        versions = Versions(engine=ENGINE_VERSION, anatomy=kb.anatomy_version, symptoms=kb.symptoms_doc['version'], knowledge=kb.knowledge['version'],
                            source_registry=kb.registry['version'], snapshot=kb.snapshot['version'],
                            language_model=getattr(self.language_model, 'model', None) if language_model_used else None,
                            prompt=getattr(self.language_model, 'prompt_version', None) if language_model_used else None)
        return Assessment(locale=locale, direction='rtl' if locale in ('ar', 'ckb') else 'ltr', anatomy=AnatomySelection(id=self.effective_anatomy(case), side=side),
                          phase=phase, summary=summary, patient_facts=facts, anatomical_references=anatomy_refs, observations=observations, possible_explanations=explanations,
                          explanation_status=explanation_status, missing_information=missing,
                          contradictions=[Contradiction(id=c['id'], kind=c['kind'], description=c['description'], fact_ids=[c['fact_id']] if c['fact_id'] in fact_ids else [], message_ids=c['message_ids'], resolved=c['resolved'])
                                          for c in contradictions] + ([Contradiction(id='contradiction:laterality', kind='laterality', description=i18n.t('contradiction_laterality', locale,
                                                                       selected=i18n.side_word(case.selected_side, locale), said=i18n.side_word(laterality_conflict, locale)), fact_ids=[], message_ids=[], resolved=False)] if laterality_conflict else []),
                          urgency=urgency, next_question=next_question, related_reading=[r for r in related_ids if r], citations=citation_list, limitations=limitations,
                          clinician_summary=clinician, versions=versions,
                          processing=Processing(engine_ms=round((time.perf_counter() - started) * 1000, 2), retrieval='bm25-anatomy-tier-freshness', language_model_used=language_model_used,
                                                external_requests=language_model_used, stages=stages),
                          disclaimer=i18n.t('disclaimer', locale))

    async def _augment_with_language_model(self, case, request):
        """Optional: a configured model may add symptom IDs from a closed list, each with a verbatim quote."""
        try:
            users = [m for m in request.messages if m.role == 'user' and not m.superseded_by]
            proposals = await self.language_model.extract(users, sorted(self.kb.symptoms))
        except Exception:
            return False
        by_id = {m.id: m for m in users}
        added = False
        for item in proposals:
            message = by_id.get(item.get('message_id'))
            quote = item.get('quote', '')
            if not message or item.get('symptom_id') not in self.kb.symptoms or not quote or quote not in message.text or item.get('status') not in ('present', 'absent'):
                continue
            if case.facts.get(_fact_id('symptom', item['symptom_id'])):
                continue
            start = message.text.index(quote)
            self._assert(case, 'symptom', item['symptom_id'], message, 0, item['status'], spans=[Span(message_id=message.id, start=start, end=start + len(quote), quote=quote)],
                         extractor='language_model')
            added = True
        return added

    def facts_out(self, case, side, locale):
        kb = self.kb
        out = []
        for fact_id, state in case.facts.items():
            current = state.current()
            if state.kind == 'symptom':
                if state.key not in kb.symptoms:
                    continue
                label = kb.symptoms[state.key]['label'][locale]
            elif state.kind == 'attribute':
                attr = kb.symptoms_doc['attributes'].get(state.key)
                if state.key == 'duration' and current.numeric is not None:
                    label = i18n.t('duration_value', locale, value=i18n.human_duration(current.numeric, locale))
                elif state.key == 'severity' and current.numeric is not None:
                    label = i18n.t('severity_value', locale, value=f'{current.numeric:g}')
                elif attr and current.value in attr['values']:
                    label = f"{attr['label'][locale]}: {attr['values'][current.value]['label'][locale]}"
                else:
                    label = f'{state.key}: {current.value}'
            elif state.kind == 'trigger':
                trigger = kb.symptoms_doc['triggers'].get(state.key)
                label = trigger['label'][locale] if trigger else state.key
            elif state.kind == 'screen':
                flag = kb.red_flags.get(state.key)
                label = (flag.get('screen_label') or flag['reason'])[locale] if flag else state.key
            else:
                label = current.value
            anatomy_id = current.anatomy_id or (self.effective_anatomy(case) if state.kind == 'symptom' else None)
            spans = [s for a in state.assertions for s in a.spans][:6]
            out.append(Fact(id=fact_id, kind=state.kind, key=state.key, value=str(current.value), numeric=current.numeric, label=label[:200], status=current.status,
                            temporal=current.temporal, anatomy_id=anatomy_id, side=side if state.kind == 'symptom' and anatomy_id and kb.is_lateral(anatomy_id) else None,
                            provenance=current.provenance, extractor=current.extractor, spans=spans, source_ref=current.message_id if current.extractor == 'memory' else None))
        order = {'screen': 0, 'symptom': 1, 'attribute': 2, 'trigger': 3, 'risk_factor': 4, 'history': 5, 'medication': 6, 'allergy': 7}
        out.sort(key=lambda f: (order.get(f.kind, 9), f.status != 'present', f.id))
        return out

    def explanation_out(self, result, case, side, facts, locale, cite):
        kb = self.kb
        condition = result['condition']
        name = condition['name'][locale]
        fact_by_key = {(f.kind, f.key): f.id for f in facts}

        def feature_label(match):
            kind, _, rest = match.partition(':')
            if kind == 'sym':
                return kb.symptoms[rest.split('@')[0]]['label'][locale]
            if kind == 'trig':
                return kb.symptoms_doc['triggers'][rest]['label'][locale]
            for op in ('>=', '<=', '='):
                if op in rest:
                    attr, value = rest.split(op, 1)
                    break
            spec = kb.symptoms_doc['attributes'].get(attr)
            if spec and value in spec['values']:
                return f"{spec['label'][locale]}: {spec['values'][value]['label'][locale]}"
            if attr == 'side':
                return i18n.t('one_side' if value == 'one' else 'both_sides', locale) if value in ('one', 'both') else i18n.side_word(value, locale)
            if attr == 'duration':
                return i18n.t('duration_value', locale, value=('≥ ' if op == '>=' else '≤ ') + i18n.human_duration(float(value), locale))
            if attr == 'severity':
                return i18n.t('severity_value', locale, value=f'≥{value}')
            return rest

        def fact_ids_for(match):
            kind, _, rest = match.partition(':')
            if kind == 'sym':
                return [i for i in [fact_by_key.get(('symptom', rest.split('@')[0]))] if i]
            if kind == 'trig':
                return [i for i in [fact_by_key.get(('trigger', rest))] if i]
            attr = rest.split('>')[0].split('<')[0].split('=')[0]
            return [i for i in [fact_by_key.get(('attribute', attr))] if i]

        publisher_of = lambda f: kb.source(f['source'])['publisher'] if kb.source(f['source']) else ''
        supporting = []
        for feature in result['present']:
            template = 'support_symptom' if feature['match'].startswith('sym:') else 'support_attr'
            label = feature_label(feature['match'])
            label = label[:1].lower() + label[1:] if locale == 'en' and template == 'support_symptom' else label
            supporting.append(EvidenceItem(statement=i18n.t(template, locale, feature=label, condition=name, publisher=publisher_of(feature)),
                                           fact_ids=fact_ids_for(feature['match']), citation_ids=[c for c in [cite(feature['binding'])] if c]))
        conflicting = [EvidenceItem(statement=f['why'][locale], fact_ids=fact_ids_for(f['match']), citation_ids=[c for c in [cite(f['binding'])] if c]) for f in result['against']]
        conflicting += [EvidenceItem(statement=i18n.t('absent_typical', locale, feature=feature_label(f['match']), condition=name, publisher=publisher_of(f)),
                                     fact_ids=fact_ids_for(f['match']), citation_ids=[c for c in [cite(f['binding'])] if c]) for f in result['absent_typical']]
        missing = []
        for feature in result['unknown']:
            if feature['weight'] == 'possible':
                continue
            kind, _, rest = feature['match'].partition(':')
            question_id = f'sym:{rest}' if kind == 'sym' else f"attr:{rest.split('>')[0].split('<')[0].split('=')[0]}" if kind == 'attr' else 'triggers'
            missing.append(MissingFeature(key=feature['match'], label=feature_label(feature['match']), question_id=question_id))
        pathway = kb.knowledge['pathways'][condition['pathway']]
        return Explanation(id=f"explanation:{condition['id']}", condition_id=condition['id'], name=name, fit=result['fit'],
                           plain_language=i18n.t(result['fit'], locale, condition=name, publisher=publisher_of(condition['features'][0])),
                           supporting=supporting, conflicting=conflicting, missing=missing[:5], pathway=condition['pathway'], pathway_label=pathway['label'][locale],
                           urgent_condition=condition['urgent_condition'], scope_note=condition['scope_note'][locale] if condition.get('scope_note') else None,
                           anatomy_ids=[a for a in condition['anatomy'] if a in kb.anatomy])

    def missing_out(self, case, side, scored, screen_done, locale):
        kb = self.kb
        out = []
        if not screen_done:
            out.append(MissingInfo(key=f'safety:{case.region}', label=i18n.t('missing_screen', locale), reason=i18n.t('missing_screen_reason', locale), priority='safety'))
        profile = kb.knowledge['region_profiles'].get(case.region, {'attributes': list(CORE_ATTRIBUTES)})
        for name in profile['attributes']:
            if name == 'side':
                if kb.is_lateral(self.effective_anatomy(case)) and side == 'unknown':
                    out.append(MissingInfo(key='attr:side', label=kb.symptoms_doc['attributes']['side']['label'][locale], reason=i18n.t('missing_core_reason', locale), priority='core'))
                continue
            if not case.facts.get(_fact_id('attribute', name)) and name in kb.symptoms_doc['attributes'] or (name in ('duration', 'severity') and not case.facts.get(_fact_id('attribute', name))):
                label = kb.symptoms_doc['attributes'][name]['label'][locale] if name in kb.symptoms_doc['attributes'] else kb.knowledge['questions'][name]['text'][locale]
                out.append(MissingInfo(key=f'attr:{name}', label=label, reason=i18n.t('missing_core_reason', locale), priority='core'))
        seen = set()
        for result in [r for r in scored if r['fit']][:3]:
            for feature in result['unknown']:
                if feature['match'].startswith('sym:') and feature['weight'] != 'possible' and feature['match'] not in seen:
                    seen.add(feature['match'])
                    out.append(MissingInfo(key=feature['match'], label=kb.symptoms[feature['match'][4:]]['label'][locale], reason=i18n.t('missing_feature_reason', locale), priority='discriminating'))
        for key, kind in (('medications', 'medication'), ('allergies', 'allergy')):
            if not any(s.kind == kind for s in case.facts.values()):
                out.append(MissingInfo(key=f'history:{key}', label=kb.knowledge['questions'][key]['text'][locale], reason=i18n.t('missing_history_reason', locale), priority='history'))
        return out[:14]

    def anatomy_out(self, case, side, facts, explanations, locale):
        kb = self.kb
        refs = {}

        def add(identifier, role, relation=None, note=None):
            if identifier not in kb.anatomy:
                return
            node = kb.node(identifier)
            ref_side = node['fixed_side'] or (side if node['lateral'] else 'midline')
            current = refs.get(identifier)
            if current is None or ['selected', 'reported', 'finding', 'related'].index(role) < ['selected', 'reported', 'finding', 'related'].index(current.role):
                refs[identifier] = AnatomyRef(id=identifier, label=kb.label(identifier, locale), side=ref_side, role=role, relation=relation, relation_note=note, marker='illustrative_anatomy',
                                              fact_ids=[f.id for f in facts if f.anatomy_id and (f.anatomy_id == identifier or kb.within(f.anatomy_id, identifier))][:12],
                                              explanation_ids=[e.id for e in explanations if identifier in e.anatomy_ids])
        effective = self.effective_anatomy(case)
        add(effective, 'selected')
        for identifier in case.reported_anatomy:
            add(identifier, 'reported')
        for fact in facts:
            if fact.anatomy_id and fact.status == 'present':
                add(fact.anatomy_id, 'reported')
        for explanation in explanations:
            for identifier in explanation.anatomy_ids:
                if kb.region(identifier) in self.case_regions(case):
                    add(identifier, 'finding')
        node = kb.node(effective)
        for relation in (node['related'] if node else [])[:4]:
            add(relation['target'], 'related', relation['relation'], relation['note'])
        return list(refs.values())[:24]

    def observations_out(self, facts, locale):
        out = []
        for fact in facts:
            if fact.kind not in ('symptom', 'attribute', 'trigger', 'medication', 'allergy', 'history') or fact.extractor == 'derived':
                continue
            if fact.provenance in ('patient_memory', 'clinician_confirmed', 'document_extract'):
                text = i18n.t('observation_memory', locale, provenance=fact.provenance.replace('_', ' '), label=fact.label)
            elif fact.status == 'absent':
                text = i18n.t('observation_absent', locale, label=fact.label)
            else:
                detail = f' — “{fact.spans[0].quote[:60]}”' if fact.spans and fact.spans[0].quote and fact.extractor == 'lexicon' else ''
                text = i18n.t('observation', locale, label=fact.label, detail=detail)
            out.append(Observation(id=f'observation:{fact.id}', text=text, fact_ids=[fact.id], provenance=fact.provenance))
        return out[:30]

    def summary_out(self, case, side, facts, urgency, locale):
        kb = self.kb
        effective = self.effective_anatomy(case)
        side_text = i18n.t('side_suffix', locale, side=i18n.side_word(side, locale)) if kb.is_lateral(effective) and side != 'unknown' else ''
        present = [f.label for f in facts if f.kind == 'symptom' and f.status == 'present' and f.extractor != 'derived']
        attrs = [f.label for f in facts if f.kind == 'attribute' and f.status == 'present' and f.key in ('onset', 'duration', 'severity')]
        absent = [f.label for f in facts if f.kind == 'symptom' and f.status == 'absent' and f.extractor != 'derived']
        joiner = i18n.t('and', locale)
        parts = [i18n.t('summary_reported', locale, anatomy=kb.label(effective, locale), side=side_text, items=joiner.join(present + attrs)) if present or attrs
                 else i18n.t('summary_nothing', locale, anatomy=kb.label(effective, locale), side=side_text)]
        if absent:
            parts.append(i18n.t('summary_denied', locale, items=joiner.join(absent[:6])))
        parts.append(i18n.t('summary_next', locale, pathway=urgency.pathway_label))
        return ' '.join(parts)

    def clinician_out(self, case, side, facts, explanations, urgency, missing, contradictions, citations):
        """Clinician summary is always in English; patient words are quoted verbatim in their original language."""
        kb = self.kb
        effective = self.effective_anatomy(case)
        reported, records = [], []
        for fact in facts:
            if fact.extractor == 'derived':
                continue
            quote = f' — patient words: “{fact.spans[0].quote[:80]}”' if fact.spans else ''
            en_label = kb.symptoms[fact.key]['label']['en'] if fact.kind == 'symptom' and fact.key in kb.symptoms else fact.label
            line = f"{fact.kind}: {en_label} [{fact.status}{', past' if fact.temporal == 'past' else ''}; {fact.provenance}]{quote}"
            (records if fact.provenance in ('patient_memory', 'clinician_confirmed', 'document_extract') else reported).append(line)
        interpretations = [f"{kb.conditions_by_id[e.condition_id]['name']['en']} — {e.fit.replace('_', ' ')}; "
                           f"{len(e.supporting)} supporting, {len(e.conflicting)} conflicting, {len(e.missing)} missing features; sources: "
                           + ', '.join(sorted({c.source_id for c in citations if c.id in {cid for item in e.supporting for cid in item.citation_ids}})) for e in explanations]
        return ClinicianSummary(
            headline=f"{kb.label(effective, 'en')} ({side}) — urgency {urgency.level}; rules {urgency.rules_version}",
            patient_reported=reported[:30], from_records=records[:20],
            observations_note='No examination findings, vital signs or test results are available. Everything above is patient-reported unless labelled otherwise.',
            interpretations=interpretations or ['No AI interpretation offered.'],
            urgency=f"{urgency.level} via {urgency.pathway}: " + '; '.join(f'{r.rule_id}' for r in urgency.reasons),
            missing=[m.key for m in missing][:14], contradictions=[c['description'] for c in contradictions],
            provenance_note='patient_statement = free text; patient_answer = structured answer; patient_memory = consented saved history; document_extract = confirmed report extract; '
                            'interpretations are AI-generated suggestions from source-bound rules, not diagnoses.')

    def limitations_out(self, locale, status, screen_done, citations, case, language_model_used):
        kb = self.kb
        out = [i18n.t('limit_core', locale)]
        if not screen_done:
            out.append(i18n.t('limit_screen', locale))
        status_note = {'insufficient_information': 'limit_insufficient', 'no_supported_explanation': 'limit_none_supported', 'conflicting': 'limit_conflicting', 'withheld_urgent': 'limit_withheld'}.get(status)
        if status_note and case.user_turns:
            out.append(i18n.t(status_note, locale))
        if not language_model_used:
            out.append(i18n.t('limit_lexicon', locale))
        if any(c.review_overdue for c in citations):
            out.append(i18n.t('limit_overdue', locale))
        if case.region in ('body.mouth', 'body.skin'):
            out.append(i18n.t('limit_photo', locale))
        if locale != 'en':
            out.append(i18n.t('limit_translation', locale))
        out.append(i18n.t('limit_coverage', locale, n=len(kb.conditions), s=len(kb.snapshot['sources'])))
        return out
