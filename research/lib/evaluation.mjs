import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'

export const LEVELS = ['unknown', 'urgent', 'emergency']
export const SYSTEMS = {
  full: 'Production eye engine with conversation state and narrative intake.',
  latest_turn_only: 'Ablation: a fresh session for each turn; only the last turn determines the final result.',
  structured_only: 'Ablation: retain state but omit free text and educational turns; keep supported options and numeric answers.'
}

function keys(value, allowed, context) {
  assert.ok(value && typeof value === 'object' && !Array.isArray(value), `${context}: expected object`)
  for (const key of Object.keys(value)) assert.ok(allowed.includes(key), `${context}: unsupported key ${key}`)
}

export function familySplit(id) {
  // All translations and variants of a family always have the same partition.
  return Number.parseInt(createHash('sha256').update(id).digest('hex').slice(0, 8), 16) % 5 < 3
    ? 'development' : 'evaluation'
}

export function validateDataset(dataset, interview) {
  keys(dataset, ['version', 'synthetic_only', 'label_status', 'translation_status', 'clinical_reviewed_at', 'provenance', 'locales', 'families'], 'dataset')
  assert.equal(dataset.synthetic_only, true, 'Only declared synthetic fixtures are supported')
  assert.equal(dataset.label_status, 'author_draft_not_clinically_adjudicated', 'This runner supports draft author labels only')
  assert.equal(dataset.clinical_reviewed_at, null, 'Clinical review requires a separately designed protocol')
  assert.ok(typeof dataset.version === 'string' && dataset.version.length > 0, 'Dataset version is required')
  assert.ok(typeof dataset.provenance === 'string' && dataset.provenance.length > 0, 'Dataset provenance is required')
  assert.ok(typeof dataset.translation_status === 'string' && dataset.translation_status.length > 0, 'Translation status is required')
  assert.deepEqual([...dataset.locales].sort(), ['ar-IQ', 'ckb', 'en'])
  assert.ok(Array.isArray(dataset.families) && dataset.families.length > 0, 'At least one scenario family is required')
  const ids = new Set()
  const rules = new Map(interview.rules.map(rule => [rule.id, rule]))
  const questions = new Set(interview.questions.map(question => question.id))
  for (const family of dataset.families) {
    keys(family, ['id', 'tags', 'intent', 'source_urls', 'expected', 'cases'], 'family')
    assert.match(family.id, /^[a-z][a-z0-9-]+$/, 'Use stable family identifiers')
    assert.ok(!ids.has(family.id), `Duplicate family: ${family.id}`)
    ids.add(family.id)
    assert.ok(typeof family.intent === 'string' && family.intent.length > 0, `${family.id}: intent is required`)
    assert.ok(Array.isArray(family.tags) && family.tags.length > 0 && family.tags.every(tag => /^[a-z][a-z0-9_]+$/.test(tag)), `${family.id}: invalid tags`)
    assert.ok(Array.isArray(family.source_urls), `${family.id}: sources must be explicit`)
    for (const url of family.source_urls) assert.equal(new URL(url).protocol, 'https:')
    const expected = family.expected
    keys(expected, ['urgency', 'rule_ids', 'reported', 'absent_reported_fields'], `${family.id}.expected`)
    assert.ok(LEVELS.includes(expected.urgency), `${family.id}: invalid expected urgency`)
    assert.ok(Array.isArray(expected.rule_ids), `${family.id}: required rules must be explicit`)
    for (const id of expected.rule_ids) {
      assert.ok(rules.has(id), `${family.id}: unknown rule ${id}`)
      assert.ok(LEVELS.indexOf(rules.get(id).level) <= LEVELS.indexOf(expected.urgency), `${family.id}: required rule exceeds expected urgency`)
    }
    if (expected.reported) {
      assert.ok(typeof expected.reported === 'object' && !Array.isArray(expected.reported))
      for (const value of Object.values(expected.reported)) assert.ok(typeof value === 'string' || typeof value === 'number')
    }
    if (expected.absent_reported_fields) assert.ok(Array.isArray(expected.absent_reported_fields) && expected.absent_reported_fields.every(field => typeof field === 'string'))
    assert.ok(Array.isArray(family.cases), `${family.id}: cases must be an array`)
    assert.deepEqual(family.cases.map(item => item.locale).sort(), [...dataset.locales].sort(), `${family.id}: provide exactly one case per locale`)
    for (const item of family.cases) {
      keys(item, ['locale', 'turns'], `${family.id}.${item.locale}`)
      assert.ok(Array.isArray(item.turns) && item.turns.length > 0 && item.turns.length <= 120)
      for (const turn of item.turns) {
        keys(turn, ['question_id', 'value', 'text', 'expected_urgency'], `${family.id}.turn`)
        assert.ok(questions.has(turn.question_id) || /^learn:[a-z0-9.-]+$/.test(turn.question_id), `${family.id}: unknown question`)
        assert.ok(typeof turn.value === 'string' && turn.value.trim().length > 0 && turn.value.length <= 2000)
        if (turn.text !== undefined) assert.ok(typeof turn.text === 'string' && turn.text.trim().length > 0 && turn.text.length <= 2000)
        if (turn.expected_urgency !== undefined) assert.ok(LEVELS.includes(turn.expected_urgency))
      }
    }
  }
  return dataset
}

export function flattenCases(dataset) {
  return dataset.families.flatMap(family => family.cases.map(item => ({
    id: `${family.id}/${item.locale}`, family: family.id, split: familySplit(family.id),
    locale: item.locale, tags: family.tags, intent: family.intent,
    source_urls: family.source_urls, expected: family.expected, turns: item.turns
  })))
}

function structured(turn, questions) {
  const question = questions.find(item => item.id === turn.question_id)
  if (!question || turn.text) return false
  return question.options.some(option => option.value === turn.value) ||
    ['pain', 'age', 'days'].includes(question.type) && (turn.value === 'unknown' || /^\d+$/.test(turn.value))
}

export function evaluateCase(engine, questions, scenario, system) {
  assert.ok(Object.hasOwn(SYSTEMS, system), `Unknown system: ${system}`)
  let state = engine.newEyeSession('left', scenario.locale)
  let error = null
  const trace = []
  const problems = []
  for (const [index, turn] of scenario.turns.entries()) {
    if (system === 'latest_turn_only') state = engine.newEyeSession('left', scenario.locale)
    const submitted = system !== 'structured_only' || structured(turn, questions)
    try {
      if (submitted) {
        // Expected labels never enter the engine.
        const input = { question_id: turn.question_id, value: turn.value }
        if (turn.text !== undefined) input.text = turn.text
        engine.answerEye(state, input)
      }
      const next = engine.nextEyeQuestion(state)
      if (state.urgency !== 'unknown' && next !== null) problems.push(`turn ${index + 1}: routine question after warning`)
      const checkpoint = turn.expected_urgency ?? (index === scenario.turns.length - 1 ? scenario.expected.urgency : null)
      if (checkpoint !== null && state.urgency !== checkpoint) problems.push(`turn ${index + 1}: expected ${checkpoint}, received ${state.urgency}`)
      trace.push({ turn: index + 1, input: { ...turn }, submitted, urgency: state.urgency,
        rule_ids: [...state.rule_ids], expected_urgency: checkpoint, next_question_id: next?.id ?? null })
    } catch (cause) {
      error = String(cause.message || cause).slice(0, 400)
      problems.push(`turn ${index + 1}: engine error: ${error}`)
      trace.push({ turn: index + 1, input: { ...turn }, submitted, urgency: null, error })
      break
    }
  }
  const urgency = error ? null : state.urgency
  if (!error) {
    for (const rule of scenario.expected.rule_ids) if (!state.rule_ids.includes(rule)) problems.push(`missing required rule: ${rule}`)
    for (const [field, value] of Object.entries(scenario.expected.reported || {})) {
      if (!Object.hasOwn(state.reported, field) || state.reported[field] !== value) problems.push(`reported.${field}: expected ${JSON.stringify(value)}, received ${JSON.stringify(state.reported[field])}`)
    }
    for (const field of scenario.expected.absent_reported_fields || []) {
      if (Object.hasOwn(state.reported, field)) problems.push(`reported.${field}: must remain unreported`)
    }
  }
  return { ...scenario, system, actual: { urgency, rule_ids: [...state.rule_ids],
    reported: { ...state.reported }, care_route: state.care_plan?.route ?? null },
    error, urgency_match: urgency === scenario.expected.urgency, policy_pass: problems.length === 0, problems, trace }
}

export function randomGenerator(seed) {
  let state = seed >>> 0
  return () => {
    state += 0x6D2B79F5
    let value = state
    value = Math.imul(value ^ value >>> 15, value | 1)
    value ^= value + Math.imul(value ^ value >>> 7, value | 61)
    return ((value ^ value >>> 14) >>> 0) / 4294967296
  }
}

function mean(values) { return values.reduce((sum, value) => sum + value, 0) / values.length }
function fraction(numerator, denominator) { return { numerator, denominator, value: denominator ? numerator / denominator : null } }
function group(rows, field) {
  const result = new Map()
  for (const row of rows) {
    const key = row[field]
    if (!result.has(key)) result.set(key, [])
    result.get(key).push(row)
  }
  return result
}

export function bootstrapMean(values, { seed = 20261101, resamples = 2000 } = {}) {
  assert.ok(Number.isSafeInteger(seed) && seed >= 0 && seed <= 0xFFFFFFFF, 'Seed must be an unsigned 32-bit integer')
  assert.ok(Number.isSafeInteger(resamples) && resamples >= 100 && resamples <= 100000, 'Use 100 to 100000 resamples')
  if (!values.length) return { estimate: null, lower: null, upper: null, clusters: 0, resamples, confidence: 0.95 }
  assert.ok(values.every(Number.isFinite), 'Bootstrap input must be finite')
  const estimate = mean(values)
  if (values.length < 2) return { estimate, lower: null, upper: null, clusters: values.length, resamples, confidence: 0.95 }
  const random = randomGenerator(seed)
  const samples = []
  for (let i = 0; i < resamples; i++) {
    let sum = 0
    for (let j = 0; j < values.length; j++) sum += values[Math.floor(random() * values.length)]
    samples.push(sum / values.length)
  }
  samples.sort((a, b) => a - b)
  return { estimate, lower: samples[Math.floor((resamples - 1) * 0.025)],
    upper: samples[Math.floor((resamples - 1) * 0.975)], clusters: values.length, resamples, confidence: 0.95 }
}

export function calculateMetrics(rows, options) {
  const confusion = Object.fromEntries(LEVELS.map(level => [level, Object.fromEntries([...LEVELS, 'error'].map(prediction => [prediction, 0]))]))
  let agreement = 0, policy = 0, errors = 0, emergency = 0, emergencyFound = 0
  let escalation = 0, escalationFound = 0, unknown = 0, unexpectedEscalation = 0, under = 0, over = 0
  const observedRules = new Set()
  for (const row of rows) {
    const expected = row.expected.urgency, actual = row.actual.urgency
    assert.ok(LEVELS.includes(expected), 'Invalid expected urgency in scored row')
    assert.ok(actual === null || LEVELS.includes(actual), 'Invalid predicted urgency in scored row')
    confusion[expected][actual ?? 'error']++
    agreement += Number(row.urgency_match)
    policy += Number(row.policy_pass)
    errors += Number(actual === null)
    if (expected === 'emergency') { emergency++; emergencyFound += Number(actual === 'emergency') }
    if (expected !== 'unknown') { escalation++; escalationFound += Number(actual === 'urgent' || actual === 'emergency') }
    if (expected === 'unknown') { unknown++; unexpectedEscalation += Number(actual === 'urgent' || actual === 'emergency') }
    if (actual !== null) {
      under += Number(LEVELS.indexOf(actual) < LEVELS.indexOf(expected))
      over += Number(LEVELS.indexOf(actual) > LEVELS.indexOf(expected))
    }
    for (const id of row.actual.rule_ids) observedRules.add(id)
  }
  const families = group(rows, 'family')
  return {
    cases: rows.length, families: families.size,
    urgency_agreement: fraction(agreement, rows.length), policy_conformance: fraction(policy, rows.length),
    emergency_level_recall: fraction(emergencyFound, emergency), escalation_recall: fraction(escalationFound, escalation),
    unexpected_escalation: fraction(unexpectedEscalation, unknown),
    underclassified: under, overclassified: over, errors,
    family_macro_agreement: bootstrapMean([...families.values()].map(items => mean(items.map(row => Number(row.urgency_match)))), options),
    observed_rule_ids: [...observedRules].sort(), confusion
  }
}

export function pairedComparison(full, baseline, options) {
  const index = new Map(baseline.map(row => [row.id, row]))
  assert.equal(index.size, baseline.length, 'Duplicate baseline case identifiers')
  assert.equal(new Set(full.map(row => row.id)).size, full.length, 'Duplicate full-system case identifiers')
  assert.equal(full.length, baseline.length, 'Paired systems must contain the same cases')
  const paired = full.map(row => {
    const other = index.get(row.id)
    assert.ok(other && other.family === row.family && other.expected.urgency === row.expected.urgency, 'Paired cases must have matching identifiers, families and targets')
    return { family: row.family, delta: Number(row.urgency_match) - Number(other.urgency_match),
      full_only: row.urgency_match && !other.urgency_match, baseline_only: !row.urgency_match && other.urgency_match }
  })
  return {
    paired_cases: paired.length, full_only_matches: paired.filter(row => row.full_only).length,
    baseline_only_matches: paired.filter(row => row.baseline_only).length,
    family_macro_agreement_difference: bootstrapMean([...group(paired, 'family').values()].map(items => mean(items.map(row => row.delta))), options)
  }
}
