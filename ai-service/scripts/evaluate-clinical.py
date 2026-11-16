"""Synthetic regression evaluation: clinical engine v2 versus the existing v1 symptom pipeline.

Usage (from ai-service/):  python scripts/evaluate-clinical.py [--out ../research/clinical-eval]

What this measures: software behaviour on developer-written synthetic cases (internal consistency,
safety-rule coverage of the authored scenarios, extraction robustness, provenance, latency).
What it does NOT measure: clinical accuracy, real-patient performance, or calibration. The "intended
condition" labels were written by the same developer who wrote the knowledge base, so agreement is
partly circular and must never be reported as diagnostic accuracy.
"""
import argparse
import asyncio
import json
import math
import re
import statistics
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ai-service'))
from app.clinical.documents import extract_report  # noqa: E402
from app.clinical.engine import ENGINE_VERSION, LEVELS, Engine  # noqa: E402
from app.clinical.kb import load_kb  # noqa: E402
from app.clinical.schemas import AssessRequest  # noqa: E402
from app.engine import AssessmentEngine  # noqa: E402
from app.provider import DisabledProvider  # noqa: E402
from app.schemas import AssessRequest as V1Request  # noqa: E402

CASES = ROOT / 'research/clinical-eval/cases.v1.json'
V1_REGION = {'body.eyes': 'eyes', 'body.head': 'head', 'body.mouth': 'head', 'body.neck': 'head', 'body.ears': 'head', 'body.chest': 'chest', 'body.abdomen': 'abdomen',
             'body.back': 'chest', 'body.arms': 'arms', 'body.legs': 'legs', 'body.skin': 'arms'}
V1_SIDE = {'left': 'left', 'right': 'right', 'both': 'both', 'unknown': 'unknown', 'midline': 'center'}
PROBABILITY_TEXT = re.compile(r'\d+\s?%|probabilit|likelihood of|chance of having|you have (a|an) [a-z]+ (infection|disease)|diagnos(is|ed) (is|with)', re.I)


def wilson(successes, n, z=1.96):
    if n == 0:
        return None
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0, centre - half), 3), round(min(1, centre + half), 3)]


def rate(successes, n):
    return {'rate': round(successes / n, 3) if n else None, 'successes': successes, 'n': n, 'wilson95': wilson(successes, n)}


class Simulator:
    """Answers each engine question from the case's ground-truth profile (symptoms not listed are 'no')."""

    def __init__(self, truth):
        self.truth = truth

    def answer(self, question):
        t, qid = self.truth, question.id
        codes = {option.code for option in question.options}
        if qid.startswith('safety:'):
            ticked = [f'rf:{flag}' for flag in t.get('red_flags', []) if f'rf:{flag}' in codes]
            return {'codes': ticked or ['none'], 'text': 'selected' if ticked else 'none of these'}
        if qid.startswith('sym:'):
            key = qid[4:]
            return {'codes': ['yes' if key in t.get('present', []) else 'no'], 'text': 'yes' if key in t.get('present', []) else 'no'}
        if qid.startswith('attr:') or qid == 'laterality':
            name = 'side' if qid == 'laterality' else qid[5:]
            value = t.get(name)
            if value is None or (name == 'side' and value == 'unknown'):
                return {'codes': ['unknown'], 'text': 'not sure'}
            return {'codes': [f'{name}:{value}'], 'text': str(value)}
        if qid == 'structure':
            target = t.get('structure')
            return {'codes': [f'structure:{target}'], 'text': target} if target and f'structure:{target}' in codes else {'codes': [], 'text': 'not sure'}
        if qid == 'triggers':
            ticked = [f'trigger:{x}' for x in t.get('triggers', []) if f'trigger:{x}' in codes]
            return {'codes': ticked or ['none'], 'text': 'selected' if ticked else 'none'}
        if qid.startswith('history:'):
            return {'codes': ['none'], 'text': 'none'}
        if qid.startswith('clarify:'):
            return {'codes': ['second'], 'text': 'the later answer'}
        if qid.startswith('memory:'):
            return {'codes': ['yes'], 'text': 'yes'}
        return {'codes': [], 'text': 'not sure'}


async def run_v2(engine, case, locale, max_turns=18):
    messages, history, timings, n = [], [], [], 0
    sim = Simulator(case['truth'])
    extra = list(case.get('after_screen', []))
    request = lambda: AssessRequest(locale=locale, anatomy={'id': case['anatomy'], 'side': case['side']}, messages=messages, patient_context=case.get('context', []),
                                    prior_urgency={'level': history[-1].urgency.level, 'rule_ids': []} if history else None)
    started = time.perf_counter()
    assessment = await engine.assess(request())
    timings.append((time.perf_counter() - started) * 1000)
    history.append(assessment)
    asked = []
    complaint = case['complaint'][locale]
    while assessment.next_question and n < max_turns:
        question = assessment.next_question
        asked.append(question.id)
        messages.append({'id': f'a{n}', 'role': 'assistant', 'text': question.text, 'question_id': question.id})
        if question.id == 'complaint':
            reply = {'codes': [], 'text': complaint}
        elif extra and asked.count(question.id) == 1 and any(q.startswith('safety:') for q in asked[:-1]):
            reply = {'codes': [], 'text': extra.pop(0)}
        else:
            reply = sim.answer(question)
        messages.append({'id': f'u{n}', 'role': 'user', 'text': reply['text'] or '-', 'answer_codes': reply['codes'], 'question_id': question.id})
        n += 1
        started = time.perf_counter()
        assessment = await engine.assess(request())
        timings.append((time.perf_counter() - started) * 1000)
        history.append(assessment)
        if case.get('stop_after') and n >= case['stop_after']:
            break
    return history, asked, timings


async def run_v1(engine, case, max_turns=12):
    """The existing pipeline with no provider configured (the repository's actual default)."""
    region = V1_REGION.get(load_kb().region(case['anatomy']), 'head')
    messages, n = [], 0
    truth = case['truth']
    labels = load_kb().symptoms
    first = await engine.assess(V1Request(region=region, side=V1_SIDE.get(case['side'], 'unknown'), messages=[]))
    assessment = first
    while assessment.next_question and n < max_turns:
        field = assessment.next_question.field
        messages.append({'id': f'a{n}', 'role': 'assistant', 'text': assessment.next_question.text, 'field': field})
        if field == 'symptoms':
            text = case['complaint'].get('en') or next(iter(case['complaint'].values()))
        elif field == 'warning_signs':
            text = 'Yes — I will describe' if truth.get('red_flags') else 'No'
        elif field == 'onset':
            text = {'sudden': 'It started suddenly', 'gradual': 'It came on gradually'}.get(truth.get('onset'), 'Not sure')
        elif field == 'duration':
            text = f"About {round(truth['duration'])} hours" if truth.get('duration') else 'Not sure'
        elif field == 'severity':
            text = f"{truth['severity']}/10" if truth.get('severity') else 'Not sure'
        elif field == 'location':
            text = truth.get('side', 'Not sure')
        elif field == 'related_symptoms':
            text = ', '.join(labels[s]['label']['en'] for s in truth.get('present', [])[1:] if s in labels) or 'None'
        else:
            text = 'None'
        messages.append({'id': f'u{n}', 'role': 'user', 'text': text})
        n += 1
        assessment = await engine.assess(V1Request(region=region, side=V1_SIDE.get(case['side'], 'unknown'), messages=messages, prior_urgency=assessment.urgency))
    return assessment, n


def first_urgent_turn(history):
    for index, item in enumerate(history):
        if LEVELS[item.urgency.level] >= LEVELS['same_day']:
            return index
    return None


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=str(ROOT / 'research/clinical-eval'))
    parser.add_argument('--cases', default=str(CASES))
    parser.add_argument('--label', default='')
    args = parser.parse_args()
    data = json.loads(Path(args.cases).read_text(encoding='utf-8'))
    kb = load_kb()
    engine = Engine()
    v1 = AssessmentEngine(DisabledProvider(), None)
    runs, failures, latencies, v1_rows = [], [], [], []
    for profile in data['profiles']:
        for locale in profile['complaint']:
            history, asked, timings = await run_v2(engine, profile, locale)
            latencies.extend(timings)
            final = history[-1]
            runs.append({'id': profile['id'], 'locale': locale, 'profile': profile, 'final': final, 'history': history, 'asked': asked})
        v1_final, v1_turns = await run_v1(v1, profile)
        v1_rows.append({'id': profile['id'], 'level': v1_final.urgency.level, 'explanations': len(v1_final.possible_explanations), 'turns': v1_turns,
                        'questions': [m for m in [v1_final.next_question] if m]})

    def check(name, ok, run, detail=''):
        if not ok:
            failures.append({'check': name, 'case': run['id'], 'locale': run['locale'], 'detail': detail})
        return ok

    metrics = {}
    # ---------------------------------------------------------------- urgent escalation
    urgent = [r for r in runs if LEVELS[r['profile']['expect'].get('min_urgency', 'not_established')] >= LEVELS['same_day']]
    emergency = [r for r in runs if r['profile']['expect'].get('min_urgency') == 'emergency']
    benign = [r for r in runs if r['profile']['expect'].get('max_urgency') and LEVELS[r['profile']['expect']['max_urgency']] <= LEVELS['soon']]
    metrics['urgent_detected'] = rate(sum(check('urgent_detected', LEVELS[r['final'].urgency.level] >= LEVELS['same_day'], r, r['final'].urgency.level) for r in urgent), len(urgent))
    metrics['emergency_detected'] = rate(sum(check('emergency_level', r['final'].urgency.level == 'emergency', r, r['final'].urgency.level) for r in emergency), len(emergency))
    first_turn = [r for r in urgent if r['profile']['expect'].get('first_turn_urgent')]
    metrics['urgent_from_first_message'] = rate(sum(check('urgent_from_first_message', first_urgent_turn(r['history']) == 1, r, f"turn={first_urgent_turn(r['history'])}") for r in first_turn), len(first_turn))
    metrics['non_safety_questions_after_urgent'] = sum(1 for r in urgent for i, h in enumerate(r['history']) if i >= (first_urgent_turn(r['history']) or 99) and h.next_question and h.next_question.kind != 'safety')
    metrics['over_escalation'] = rate(sum(not check('no_over_escalation', LEVELS[r['final'].urgency.level] <= LEVELS[r['profile']['expect']['max_urgency']], r, r['final'].urgency.level) for r in benign), len(benign))
    # ---------------------------------------------------------------- explanations (internal consistency with authored intent)
    intended = [r for r in runs if r['profile']['expect'].get('intended')]
    top1 = sum(check('intended_top1', bool(r['final'].possible_explanations) and r['final'].possible_explanations[0].condition_id in r['profile']['expect']['intended'], r,
                     ','.join(e.condition_id for e in r['final'].possible_explanations) or r['final'].explanation_status) for r in intended)
    top3 = sum(1 for r in intended if any(e.condition_id in r['profile']['expect']['intended'] for e in r['final'].possible_explanations))
    metrics['intended_condition_top1'] = rate(top1, len(intended))
    metrics['intended_condition_top3'] = rate(top3, len(intended))
    vague = [r for r in runs if r['profile']['expect'].get('no_explanations')]
    metrics['abstains_on_vague_input'] = rate(sum(check('abstain', not r['final'].possible_explanations, r) for r in vague), len(vague))
    # ---------------------------------------------------------------- interview quality
    metrics['repeated_questions'] = sum(len(r['asked']) - len(set(r['asked'])) for r in runs)
    metrics['safety_screen_first'] = rate(sum(check('safety_first', len(r['asked']) < 2 or r['asked'][1].startswith('safety:') or LEVELS[r['history'][1].urgency.level] >= 3, r, ','.join(r['asked'][:3]))
                                              for r in runs), len(runs))
    non_urgent = [r for r in runs if r not in urgent]
    metrics['questions_per_conversation'] = {'mean': round(statistics.mean(len(r['asked']) for r in non_urgent), 2), 'max': max(len(r['asked']) for r in non_urgent), 'n': len(non_urgent)}
    with_purpose = sum(1 for r in runs for h in r['history'] if h.next_question and h.next_question.purpose)
    total_questions = sum(1 for r in runs for h in r['history'] if h.next_question)
    metrics['questions_with_purpose'] = rate(with_purpose, total_questions)
    # ---------------------------------------------------------------- citations and unsupported claims
    citations = [c for r in runs for c in r['final'].citations]
    verified = sum(1 for c in citations if c.quote in [u['text'] for u in kb.chunks[c.chunk_id]['units']])
    metrics['citations_verbatim'] = rate(verified, len(citations))
    items = [i for r in runs for e in r['final'].possible_explanations for i in e.supporting]
    metrics['supporting_statements_with_citation'] = rate(sum(1 for i in items if i.citation_ids), len(items))
    hosts = set(kb.registry['policy']['allowed_hosts'])
    metrics['citations_on_allowlisted_hosts'] = rate(sum(1 for c in citations if re.match(r'https://([^/]+)/', c.url).group(1) in hosts), len(citations))
    patient_text = [(r, t) for r in runs for t in [r['final'].summary, *r['final'].limitations, *(e.plain_language for e in r['final'].possible_explanations)]]
    metrics['probability_or_diagnosis_claims'] = sum(not check('no_probability_text', not PROBABILITY_TEXT.search(t), r, t[:80]) for r, t in patient_text)
    metrics['fits_despite_strong_conflict'] = sum(1 for r in runs for e in r['final'].possible_explanations if e.fit == 'fits' and any('strong' in s.statement for s in e.conflicting))
    # ---------------------------------------------------------------- multilingual consistency
    groups = {}
    for r in runs:
        groups.setdefault(r['id'], {})[r['locale']] = r
    multi = {k: v for k, v in groups.items() if len(v) > 1 and 'en' in v}
    agree_urgency = agree_top = agree_flags = 0
    for key, by_locale in multi.items():
        base = by_locale['en']['final']
        for locale, r in by_locale.items():
            if locale == 'en':
                continue
            f = r['final']
            agree_urgency += check('multilingual_urgency', f.urgency.level == base.urgency.level, r, f'{f.urgency.level} vs en {base.urgency.level}')
            top = lambda a: a.possible_explanations[0].condition_id if a.possible_explanations else None
            agree_top += check('multilingual_top_explanation', top(f) == top(base), r, f'{top(f)} vs en {top(base)}')
            flags = lambda a: {x.rule_id for x in a.urgency.reasons if not x.rule_id.startswith(('safety-', 'prior-', 'condition:'))}
            agree_flags += check('multilingual_red_flags', flags(f) == flags(base), r, f'{sorted(flags(f))} vs en {sorted(flags(base))}')
    pairs = sum(len(v) - 1 for v in multi.values())
    metrics['multilingual_same_urgency'] = rate(agree_urgency, pairs)
    metrics['multilingual_same_top_explanation'] = rate(agree_top, pairs)
    metrics['multilingual_same_red_flags'] = rate(agree_flags, pairs)
    # ---------------------------------------------------------------- special cases
    special_results = []
    for case in data['special']:
        locale = case.get('locale', 'en')
        history, asked, timings = await run_v2(engine, case, locale)
        latencies.extend(timings)
        final = history[-1]
        run = {'id': case['id'], 'locale': locale}
        expect, ok = case['expect'], True
        if 'conflict' in expect:
            detected = any(any(c.kind == 'laterality' for c in h.contradictions) for h in history) or 'laterality' in asked
            ok &= check('laterality_conflict_detected', detected == expect['conflict'], run, f'detected={detected}')
        if 'final_side' in expect:
            ok &= check('laterality_final_side', final.anatomy.side == expect['final_side'], run, final.anatomy.side)
        if expect.get('contradiction'):
            ok &= check('contradiction_detected', any(q.startswith('clarify:') for q in asked), run, ','.join(asked))
        for key in expect.get('final_absent', []):
            fact = next((f for f in final.patient_facts if f.id == f'symptom:{key}'), None)
            ok &= check('contradiction_resolved', bool(fact and fact.status == 'absent'), run, str(fact and fact.status))
        if expect.get('missing_any'):
            keys = {m.key for m in final.missing_information}
            ok &= check('missing_information_listed', all(k in keys for k in expect['missing_any']), run, ','.join(sorted(keys)))
        if expect.get('min_urgency'):
            ok &= check('injection_urgency', LEVELS[final.urgency.level] >= LEVELS[expect['min_urgency']], run, final.urgency.level)
        for qid in expect.get('not_asked', []):
            ok &= check('memory_not_reasked', qid not in asked, run, ','.join(asked))
        if expect.get('asked_any'):
            ok &= check('memory_confirmed', any(q in asked for q in expect['asked_any']), run, ','.join(asked))
        special_results.append({'id': case['id'], 'kind': case['kind'], 'passed': bool(ok), 'questions_asked': asked, 'final_side': final.anatomy.side, 'urgency': final.urgency.level})
    by_kind = {}
    for item in special_results:
        by_kind.setdefault(item['kind'], []).append(item['passed'])
    metrics['special_cases'] = {kind: rate(sum(values), len(values)) for kind, values in by_kind.items()}
    # ---------------------------------------------------------------- documents (prompt injection through reports)
    doc_rows = []
    for doc in data['documents']:
        result = extract_report(doc['text'].encode('utf-8'), 'text/plain')
        kinds = {i.kind for i in result.items}
        ok = set(doc['expect_kinds']) <= kinds and len(result.injection_flags) >= doc['expect_flags'] and not (set(doc.get('expect_absent_kinds', [])) & kinds)
        injected_text = any(re.search(r'ignore|reveal|you are now|تجاهل', i.text, re.I) for i in result.items)
        ok = ok and not injected_text
        if not ok:
            failures.append({'check': 'document_extraction', 'case': doc['id'], 'locale': 'en', 'detail': f'kinds={sorted(kinds)} flags={len(result.injection_flags)}'})
        doc_rows.append({'id': doc['id'], 'passed': ok, 'kinds': sorted(kinds), 'flags': len(result.injection_flags)})
    metrics['documents'] = rate(sum(r['passed'] for r in doc_rows), len(doc_rows))
    # ---------------------------------------------------------------- latency and cost
    latencies.sort()
    metrics['latency_ms_per_turn'] = {'p50': round(statistics.median(latencies), 2), 'p95': round(latencies[int(.95 * (len(latencies) - 1))], 2), 'max': round(latencies[-1], 2), 'turns': len(latencies)}
    metrics['external_requests'] = sum(1 for r in runs for h in r['history'] if h.processing.external_requests)
    metrics['inference_cost_usd'] = 0.0
    # ---------------------------------------------------------------- v1 baseline on the same profiles
    v1_urgent = [row for row, p in zip(v1_rows, data['profiles']) if LEVELS[p['expect'].get('min_urgency', 'not_established')] >= LEVELS['same_day']]
    v1_emergency = [row for row, p in zip(v1_rows, data['profiles']) if p['expect'].get('min_urgency') == 'emergency']
    v1_benign = [(row, p) for row, p in zip(v1_rows, data['profiles']) if p['expect'].get('max_urgency') and LEVELS[p['expect']['max_urgency']] <= LEVELS['soon']]
    baseline = {
        'note': 'v1 = existing /v1/assess with no external provider (the repository default). English complaint text; fixed question order; urgency from English regex rules plus a positive warning-screen answer.',
        'urgent_detected': rate(sum(1 for row in v1_urgent if LEVELS[row['level']] >= LEVELS['same_day']), len(v1_urgent)),
        'emergency_detected': rate(sum(1 for row in v1_emergency if row['level'] == 'emergency'), len(v1_emergency)),
        'over_escalation': rate(sum(1 for row, p in v1_benign if LEVELS[row['level']] > LEVELS[p['expect']['max_urgency']]), len(v1_benign)),
        'explanations_offered': rate(sum(1 for row in v1_rows if row['explanations']), len(v1_rows)),
        'citations': 0, 'multilingual': 'not supported (English-only rules)', 'laterality_checks': 'region-level side only', 'patient_memory': 'not supported',
        'questions_per_conversation': round(statistics.mean(row['turns'] for row in v1_rows), 2) if v1_rows else None,
    }
    report = {
        'generated_on': date.today().isoformat(), 'engine_version': ENGINE_VERSION, 'knowledge_version': kb.knowledge['version'], 'snapshot_version': kb.snapshot['version'],
        'cases_version': data['version'], 'sample_sizes': {'profiles': len(data['profiles']), 'profile_runs_including_translations': len(runs), 'special_cases': len(data['special']),
                                                          'documents': len(data['documents']), 'engine_turns': len(latencies)},
        'interpretation': 'Synthetic developer-authored regression cases. Not clinical accuracy. Intended-condition agreement is partly circular (same author as the knowledge base).',
        'v2': metrics, 'v1_baseline': baseline, 'failures': failures, 'special_results': special_results, 'documents': doc_rows,
        'per_case': [{'id': r['id'], 'locale': r['locale'], 'urgency': r['final'].urgency.level, 'phase': r['final'].phase, 'top': [e.condition_id for e in r['final'].possible_explanations],
                      'status': r['final'].explanation_status, 'questions': r['asked']} for r in runs],
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"results-{date.today().isoformat()}{('-' + args.label) if args.label else ''}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({'v2': {k: v for k, v in metrics.items() if k != 'special_cases'}, 'special': metrics['special_cases'], 'v1': baseline, 'failures': len(failures)}, ensure_ascii=False, indent=1))


asyncio.run(main())
