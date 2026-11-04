import assert from 'node:assert/strict'
import { test } from 'node:test'
import fs from 'node:fs'
import { bootstrapMean, calculateMetrics, evaluateCase, familySplit, flattenCases, pairedComparison, validateDataset } from '../lib/evaluation.mjs'
import { csvCell, renderCsv, renderHtml } from '../lib/report.mjs'

const dataset = JSON.parse(fs.readFileSync(new URL('../eye-safety.v1.json', import.meta.url), 'utf8'))
const interview = JSON.parse(fs.readFileSync(new URL('../../contracts/eye/interview.v1.json', import.meta.url), 'utf8'))
const options = { seed: 7, resamples: 500 }

function row(id, family, expected, actual, policy = expected === actual) {
  return { id, family, expected: { urgency: expected }, actual: { urgency: actual, rule_ids: [] },
    urgency_match: expected === actual, policy_pass: policy }
}

test('published fixtures are synthetic, balanced by locale, and cover every draft rule target', () => {
  validateDataset(dataset, interview)
  const rows = flattenCases(dataset)
  assert.equal(rows.length, 90)
  assert.equal(new Set(rows.map(item => item.family)).size, 30)
  for (const locale of dataset.locales) assert.equal(rows.filter(item => item.locale === locale).length, 30)
  assert.deepEqual([...new Set(rows.flatMap(item => item.expected.rule_ids))].sort(), interview.rules.map(rule => rule.id).sort())
  assert.deepEqual([...new Set(rows.map(item => item.split))].sort(), ['development', 'evaluation'])
})

test('family partitions keep all translations together and do not depend on iteration order', () => {
  const rows = flattenCases(dataset)
  for (const family of dataset.families) {
    const translations = rows.filter(item => item.family === family.id)
    assert.equal(new Set(translations.map(item => item.split)).size, 1)
    assert.equal(translations[0].split, familySplit(family.id))
  }
  const shuffled = { ...dataset, families: [...dataset.families].reverse() }
  assert.deepEqual(flattenCases(shuffled).map(item => [item.id, item.split]).sort(), rows.map(item => [item.id, item.split]).sort())
})

test('fixture validation rejects undeclared real-data use, duplicate IDs and missing translations', () => {
  const real = structuredClone(dataset); real.synthetic_only = false
  assert.throws(() => validateDataset(real, interview), /synthetic/)
  const duplicate = structuredClone(dataset); duplicate.families.push(duplicate.families[0])
  assert.throws(() => validateDataset(duplicate, interview), /Duplicate/)
  const missing = structuredClone(dataset); missing.families[0].cases.pop()
  assert.throws(() => validateDataset(missing, interview), /one case per locale/)
})

test('fixture validation rejects misspelled expectations and unknown rules', () => {
  const typo = structuredClone(dataset); typo.families[0].expected.urgncy = 'emergency'
  assert.throws(() => validateDataset(typo, interview), /unsupported key/)
  const rule = structuredClone(dataset); rule.families[0].expected.rule_ids = ['invented.rule']
  assert.throws(() => validateDataset(rule, interview), /unknown rule/)
  const contradictory = structuredClone(dataset); contradictory.families[0].expected.urgency = 'unknown'
  assert.throws(() => validateDataset(contradictory, interview), /exceeds/)
})

test('confusion matrix and denominators distinguish urgency misses, errors and expected-unknown cases', () => {
  const rows = [row('a/en', 'a', 'emergency', 'emergency'), row('a/ar', 'a', 'emergency', 'urgent'),
    row('b/en', 'b', 'urgent', null), row('c/en', 'c', 'unknown', 'emergency'), row('c/ar', 'c', 'unknown', 'unknown')]
  const metrics = calculateMetrics(rows, options)
  assert.deepEqual(metrics.urgency_agreement, { numerator: 2, denominator: 5, value: 0.4 })
  assert.deepEqual(metrics.emergency_level_recall, { numerator: 1, denominator: 2, value: 0.5 })
  assert.deepEqual(metrics.escalation_recall, { numerator: 2, denominator: 3, value: 2 / 3 })
  assert.deepEqual(metrics.unexpected_escalation, { numerator: 1, denominator: 2, value: 0.5 })
  assert.equal(metrics.underclassified, 1)
  assert.equal(metrics.overclassified, 1)
  assert.equal(metrics.errors, 1)
  assert.equal(metrics.confusion.urgent.error, 1)
  assert.equal(metrics.confusion.emergency.urgent, 1)
  assert.equal(metrics.confusion.unknown.emergency, 1)
  assert.equal(metrics.family_macro_agreement.clusters, 3)
  assert.equal(metrics.family_macro_agreement.estimate, 1 / 3)
})

test('undefined denominators remain null and a single family cannot produce an interval', () => {
  const metrics = calculateMetrics([row('a', 'one-family', 'unknown', 'unknown')], options)
  assert.equal(metrics.emergency_level_recall.value, null)
  assert.equal(metrics.escalation_recall.value, null)
  assert.equal(metrics.family_macro_agreement.lower, null)
  assert.equal(metrics.family_macro_agreement.upper, null)
  assert.equal(calculateMetrics([], options).urgency_agreement.value, null)
})

test('policy conformance can fail even when the final urgency matches', () => {
  const metrics = calculateMetrics([row('a', 'a', 'urgent', 'urgent', false)], options)
  assert.equal(metrics.urgency_agreement.value, 1)
  assert.equal(metrics.policy_conformance.value, 0)
})

test('family bootstrap is seeded, respects bounds and does not count translations as independent clusters', () => {
  const values = [0, 1 / 3, 2 / 3, 1]
  const first = bootstrapMean(values, options)
  assert.deepEqual(first, bootstrapMean(values, options))
  assert.ok(first.lower >= 0 && first.upper <= 1)
  assert.equal(first.estimate, 0.5)
  assert.deepEqual(bootstrapMean([1, 1], options), { estimate: 1, lower: 1, upper: 1, clusters: 2, resamples: 500, confidence: 0.95 })
  const translated = [row('a/en', 'a', 'unknown', 'unknown'), row('a/ar', 'a', 'unknown', 'unknown'), row('a/ckb', 'a', 'unknown', 'unknown')]
  assert.equal(calculateMetrics(translated, options).family_macro_agreement.clusters, 1)
})

test('invalid bootstrap configuration is rejected rather than silently falling back', () => {
  for (const seed of [-1, NaN, 1.5, 2 ** 32]) assert.throws(() => bootstrapMean([], { seed, resamples: 100 }))
  for (const resamples of [0, 99, 100001, NaN]) assert.throws(() => bootstrapMean([], { seed: 0, resamples }))
})

test('paired comparisons align IDs, preserve sign, and reject missing or duplicate cases', () => {
  const full = [row('a', 'a', 'emergency', 'emergency'), row('b', 'b', 'unknown', 'urgent')]
  const baseline = [row('b', 'b', 'unknown', 'unknown'), row('a', 'a', 'emergency', 'urgent')]
  const comparison = pairedComparison(full, baseline, options)
  assert.equal(comparison.full_only_matches, 1)
  assert.equal(comparison.baseline_only_matches, 1)
  assert.equal(comparison.family_macro_agreement_difference.estimate, 0)
  const positive = pairedComparison(full.slice(0, 1), baseline.slice(1), options)
  assert.equal(positive.family_macro_agreement_difference.estimate, 1)
  assert.throws(() => pairedComparison(full, baseline.slice(1), options), /same cases/)
  assert.throws(() => pairedComparison(full, [baseline[0], baseline[0]], options), /Duplicate/)
})

const fakeQuestions = [
  { id: 'question.contact', type: 'choice', options: [{ value: 'yes' }] },
  { id: 'question.pain', type: 'pain', options: [] },
  { id: 'question.concern', type: 'text', options: [] }
]
function fakeEngine(seen = []) {
  return {
    newEyeSession: () => ({ urgency: 'unknown', rule_ids: [], reported: {} }),
    answerEye(state, turn) {
      seen.push(turn)
      if (turn.value === 'throw') throw new Error('Test failure')
      if (turn.question_id === 'question.contact') state.reported.contact = turn.value
      if (turn.question_id === 'question.pain') state.reported.pain = Number(turn.value)
      if (state.reported.contact === 'yes' && state.reported.pain > 0) { state.urgency = 'urgent'; state.rule_ids = ['lens-warning'] }
    },
    nextEyeQuestion: state => state.urgency === 'unknown' ? { id: 'question.pain' } : null
  }
}
const multiTurn = { id: 'example/en', family: 'example', locale: 'en',
  expected: { urgency: 'urgent', rule_ids: ['lens-warning'] },
  turns: [{ question_id: 'question.contact', value: 'yes', expected_urgency: 'unknown' }, { question_id: 'question.pain', value: '4' }] }

test('adapter retains conversation history, latest-turn ablation removes it, and labels never enter the engine', () => {
  const seen = [], engine = fakeEngine(seen)
  const full = evaluateCase(engine, fakeQuestions, multiTurn, 'full')
  assert.equal(full.policy_pass, true)
  assert.equal(full.actual.urgency, 'urgent')
  assert.ok(seen.every(turn => !Object.hasOwn(turn, 'expected_urgency')))
  const ablated = evaluateCase(engine, fakeQuestions, multiTurn, 'latest_turn_only')
  assert.equal(ablated.actual.urgency, 'unknown')
  assert.equal(ablated.policy_pass, false)
})

test('structured-only ablation omits narrative input without replacing it with reassuring negatives', () => {
  const scenario = { ...multiTurn, expected: { urgency: 'unknown', rule_ids: [] },
    turns: [{ question_id: 'question.concern', value: 'a symptom' }] }
  const seen = []
  const result = evaluateCase(fakeEngine(seen), fakeQuestions, scenario, 'structured_only')
  assert.equal(seen.length, 0)
  assert.equal(result.trace[0].submitted, false)
  assert.deepEqual(result.actual.reported, {})
  assert.equal(evaluateCase(fakeEngine(), fakeQuestions, multiTurn, 'structured_only').policy_pass, true)
})

test('checkpoint failures remain visible even when a later final answer matches', () => {
  const scenario = structuredClone(multiTurn)
  scenario.turns[0].expected_urgency = 'emergency'
  const result = evaluateCase(fakeEngine(), fakeQuestions, scenario, 'full')
  assert.equal(result.urgency_match, true)
  assert.equal(result.policy_pass, false)
  assert.match(result.problems[0], /turn 1/)
})

test('engine exceptions are error outputs and cannot count as expected-unknown matches', () => {
  const scenario = { ...multiTurn, expected: { urgency: 'unknown', rule_ids: [] },
    turns: [{ question_id: 'question.concern', value: 'throw' }] }
  const result = evaluateCase(fakeEngine(), fakeQuestions, scenario, 'full')
  assert.equal(result.actual.urgency, null)
  assert.equal(result.urgency_match, false)
  assert.equal(result.policy_pass, false)
  assert.match(result.error, /Test failure/)
})

test('a matching severity cannot conceal missing provenance, required rules, or continued routine questions', () => {
  const scenario = structuredClone(multiTurn)
  scenario.expected.rule_ids.push('not-activated')
  scenario.expected.reported = { pain: 7 }
  scenario.expected.absent_reported_fields = ['contact']
  const engine = fakeEngine()
  engine.nextEyeQuestion = () => ({ id: 'question.pain' })
  const result = evaluateCase(engine, fakeQuestions, scenario, 'full')
  assert.equal(result.urgency_match, true)
  assert.equal(result.policy_pass, false)
  assert.ok(result.problems.some(problem => problem.includes('routine question')))
  assert.ok(result.problems.some(problem => problem.includes('missing required rule')))
  assert.ok(result.problems.some(problem => problem.includes('reported.pain')))
  assert.ok(result.problems.some(problem => problem.includes('must remain unreported')))
})

test('offline HTML escapes embedded script endings while preserving the exact JSON data', () => {
  const malicious = { note: '</script><script>alert(1)</script>', text: 'حكة · خوران \u2028' }
  const html = renderHtml(malicious)
  assert.ok(!html.includes(malicious.note))
  const payload = html.match(/<script type="application\/json" id="benchmark-data">([\s\S]*?)<\/script>/)[1]
  assert.deepEqual(JSON.parse(payload), malicious)
})

test('CSV preserves multilingual text, quotes and multiline values and neutralizes spreadsheet formulas', () => {
  assert.equal(csvCell('حكة, "خوران"\nnext'), '"حكة, ""خوران""\nnext"')
  for (const input of ['=SUM(1,2)', ' +1', '-1+2', '@formula', '\ttext']) assert.ok(csvCell(input).startsWith('"\''))
  const report = { systems: { full: { rows: [{ ...multiTurn, split: 'development', tags: ['test'],
    actual: { urgency: 'urgent', rule_ids: [] }, urgency_match: true, policy_pass: true, problems: [] }] } } }
  const csv = renderCsv(report)
  assert.ok(csv.startsWith('\uFEFF'))
  assert.ok(csv.includes('"case_id"'))
  assert.ok(csv.includes('"example/en"'))
})
