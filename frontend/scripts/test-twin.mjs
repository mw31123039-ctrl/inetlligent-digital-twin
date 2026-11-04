import assert from 'node:assert/strict'
import { test } from 'node:test'
import { reactive } from 'vue'
import fs from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import { pathToFileURL } from 'node:url'
import { bundleModule, root } from './portable.mjs'

const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'humantwin-twin-tests-'))
let model
try {
  const filename = path.join(directory, 'twin-model.mjs')
  await bundleModule(path.join(root, 'src/twin/model.ts'), filename)
  model = await import(pathToFileURL(filename).href)
} finally {
  assert.equal(path.dirname(path.resolve(directory)), path.resolve(os.tmpdir()))
  assert.ok(path.basename(directory).startsWith('humantwin-twin-tests-'))
  await fs.rm(directory, { recursive: true, force: true })
}
const { newTwin, validateTwin, appendObservation, activeObservations, streams, streamKey, projectStream, summarizeStream, backtestStream, analyzeTwin, syntheticExample } = model
const at = hours => new Date(Date.parse('2026-10-01T00:00:00.000Z') + hours * 3600000).toISOString()
function fixture() {
  const document = newTwin('SUBJECT-A', at(0))
  document.observations = [71, 72, 71, 72].map((value, index) => ({
    id: `record-${index}`, subject_id: 'SUBJECT-A', metric: 'resting_heart_rate', value, unit: 'bpm',
    region: 'systemic', side: 'unspecified', method: 'manual-pulse', observed_at: at(index), recorded_at: at(index),
    source: { kind: 'manual', label: 'Synthetic test source' }
  }))
  return validateTwin(document, Date.parse(at(4)))
}
function input(observation, value = observation.value) {
  return { metric: observation.metric, value, region: observation.region, side: observation.side,
    method: observation.method, observed_at: observation.observed_at, source: { ...observation.source } }
}

await test('empty subjects contain no fabricated readings and JSON round-trips retain the complete ledger', () => {
  assert.equal(newTwin('SUBJECT-A', at(0)).observations.length, 0)
  const document = fixture()
  assert.deepEqual(validateTwin(JSON.parse(JSON.stringify(document)), Date.parse(at(4))), document)
  const copy = validateTwin(document, Date.parse(at(4)))
  copy.observations[0].source.label = 'changed'
  assert.equal(document.observations[0].source.label, 'Synthetic test source')
})

await test('reactive document proxies produce plain validated records and self-contained model exports', () => {
  const document = reactive(fixture())
  const original = document.observations[0]
  const corrected = appendObservation(document, { ...input(original, 74), supersedes: original.id }, at(4))
  const analysis = analyzeTwin(reactive(corrected), 1, at(5))
  assert.equal(analysis.record.observations.length, 5)
  assert.equal(analysis.streams[0].projection.n, 4)
  assert.doesNotThrow(() => structuredClone(analysis))
  assert.ok(!analysis.streams[0].projection.training_ids.includes(original.id))
})

await test('subject binding, declared research use and canonical units cannot be bypassed on import', () => {
  const document = fixture()
  for (const [field, value] of [['subject_id', 'SUBJECT-B'], ['unit', 'beats per second']]) {
    const changed = structuredClone(document); changed.observations[0][field] = value
    assert.throws(() => validateTwin(changed, Date.parse(at(4))))
  }
  const real = structuredClone(document); real.use = 'clinical'
  assert.throws(() => validateTwin(real, Date.parse(at(4))), /synthetic/)
})

await test('invalid dates, future data, backward recorded times and nonfinite values are rejected', () => {
  for (const [field, value] of [['observed_at', '2026-02-30T00:00:00.000Z'], ['observed_at', at(6)], ['value', NaN], ['value', Infinity]]) {
    const changed = fixture(); changed.observations[0][field] = value
    assert.throws(() => validateTwin(changed, Date.parse(at(4))))
  }
  const backward = fixture(); backward.observations[3].recorded_at = at(1)
  assert.throws(() => validateTwin(backward, Date.parse(at(4))), /times/)
})

await test('duplicate observations need an explicit correction instead of silently replacing the source event', () => {
  const document = fixture(), original = document.observations[0]
  assert.throws(() => appendObservation(document, input(original, 74), at(4)), /already exists/)
  const corrected = appendObservation(document, { ...input(original, 74), supersedes: original.id }, at(4))
  assert.equal(document.observations.length, 4)
  assert.equal(corrected.observations.length, 5)
  assert.equal(corrected.observations[0].value, 71)
  assert.equal(activeObservations(corrected).length, 4)
  assert.equal(activeObservations(corrected)[0].value, 74)
  assert.equal(corrected.observations[4].supersedes, original.id)
})

await test('correction chains preserve identity and time and cannot fork from an already superseded reading', () => {
  const document = fixture(), original = document.observations[0]
  const corrected = appendObservation(document, { ...input(original, 74), supersedes: original.id }, at(4))
  assert.throws(() => appendObservation(corrected, { ...input(original, 75), supersedes: original.id }, at(5)), /latest active/)
  assert.throws(() => appendObservation(document, { ...input(original), observed_at: at(1), supersedes: original.id }, at(4)), /retain/)
  assert.throws(() => appendObservation(document, { ...input(original), method: 'wrist-sensor', supersedes: original.id }, at(4)), /retain/)
  const second = appendObservation(corrected, { ...input(corrected.observations[4], 73), supersedes: corrected.observations[4].id }, at(5))
  assert.equal(second.observations.length, 6)
  assert.equal(activeObservations(second)[0].value, 73)
})

await test('personal reference excludes the latest chronological reading and superseded measurements', () => {
  const document = fixture(), result = summarizeStream(activeObservations(document).reverse())
  assert.equal(result.latest.value, 72)
  assert.equal(result.reference, 214 / 3)
  assert.equal(result.reference_count, 3)
  const corrected = appendObservation(document, { ...input(document.observations[0], 74), supersedes: document.observations[0].id }, at(4))
  assert.equal(summarizeStream(activeObservations(corrected)).reference, 217 / 3)
})

await test('streams separate measurement sources, methods, sides and anatomical locations', () => {
  const first = fixture().observations[0]
  const variants = [first, { ...first, method: 'wrist-sensor' }, { ...first, source: { kind: 'manual', label: 'Another source' } }]
  assert.equal(new Set(variants.map(streamKey)).size, 3)
  const document = fixture()
  document.observations.push({ ...first, id: 'other-source', source: { kind: 'manual', label: 'Another source' }, recorded_at: at(4) })
  assert.equal(streams(validateTwin(document, Date.parse(at(4)))).length, 2)
  const pain = { ...first, metric: 'pain', unit: '/10', value: 4, region: 'eyes', side: 'left', method: 'self-report' }
  assert.notEqual(streamKey(pain), streamKey({ ...pain, side: 'right' }))
  assert.notEqual(streamKey(pain), streamKey({ ...pain, region: 'arms' }))
})

await test('OLS prediction and Student-t model interval agree with an independently calculated four-point example', () => {
  const result = projectStream(fixture().observations, 1)
  assert.equal(result.available, true)
  assert.ok(Math.abs(result.slope_per_hour - 0.2) < 1e-10)
  assert.ok(Math.abs(result.estimate - 72) < 1e-10)
  assert.ok(Math.abs(result.residual_sd - Math.sqrt(0.4)) < 1e-10)
  assert.ok(Math.abs(result.lower - (72 - 4.302653)) < 1e-6)
  assert.ok(Math.abs(result.upper - (72 + 4.302653)) < 1e-6)
  assert.equal(result.forecast_at, at(4))
  assert.equal(result.degrees_of_freedom, 2)
  assert.equal(result.training_ids.length, 4)
})

await test('new observations and corrections update the fitted model, and superseded IDs leave model provenance', () => {
  const document = fixture(), old = projectStream(activeObservations(document), 1)
  const corrected = appendObservation(document, { ...input(document.observations[3], 76), supersedes: document.observations[3].id }, at(4))
  const updated = projectStream(activeObservations(corrected), 1)
  assert.notEqual(updated.estimate, old.estimate)
  assert.ok(!updated.training_ids.includes(document.observations[3].id))
  const reading = { ...input(document.observations[3], 77), observed_at: at(5) }
  const appended = appendObservation(corrected, reading, at(5))
  assert.equal(projectStream(activeObservations(appended), 1).n, 5)
})

await test('projection is withheld for missing data, mixed subjects/sources, duplicate times, ordinal pain and excessive horizons', () => {
  const document = fixture(), observations = document.observations
  assert.equal(projectStream(observations.slice(0, 3), 1).available, false)
  assert.equal(projectStream(observations, 6).available, false)
  assert.equal(projectStream(observations, 0).available, false)
  assert.equal(projectStream(observations.map(item => ({ ...item, metric: 'pain', value: 4 })), 1).available, false)
  assert.equal(projectStream(observations.map((item, index) => ({ ...item, subject_id: index ? item.subject_id : 'OTHER' })), 1).available, false)
  assert.equal(projectStream(observations.map((item, index) => ({ ...item, observed_at: index ? item.observed_at : observations[1].observed_at })), 1).available, false)
})

await test('synthetic example validates and produces a subject-specific model without clinical flags', () => {
  const document = syntheticExample(at(30))
  assert.equal(document.use, 'synthetic-research')
  assert.equal(activeObservations(document).length, 7)
  assert.equal(projectStream(activeObservations(document), 1).available, true)
  assert.equal(Object.hasOwn(document, 'diagnosis'), false)
})

await test('rolling-origin evaluation excludes every target and future reading from training and reports a persistence comparator', () => {
  const prototype = fixture().observations[0]
  const observations = Array.from({ length: 8 }, (_, index) => ({ ...prototype, id: `rolling-${index}`, value: 71 + index, observed_at: at(index), recorded_at: at(index) }))
  const result = backtestStream(observations)
  assert.equal(result.count, 4)
  assert.equal(result.model_mae, 0)
  assert.equal(result.persistence_mae, 1)
  assert.equal(result.interval_hits, 4)
  for (const [index, prediction] of result.predictions.entries()) {
    assert.equal(prediction.target_id, `rolling-${index + 4}`)
    assert.deepEqual(prediction.training_ids, observations.slice(0, index + 4).map(item => item.id))
  }
  observations[7].value = 100
  assert.deepEqual(backtestStream(observations).predictions.slice(0, 3), result.predictions.slice(0, 3))
  assert.equal(backtestStream(observations.slice(0, 4)).model_mae, null)
})
