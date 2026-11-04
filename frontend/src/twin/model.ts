import type { RegionId } from '../types'

export type MetricId = 'resting_heart_rate' | 'body_temperature' | 'pain'
export type ObservationRegion = RegionId | 'systemic'
export type ObservationSide = 'left' | 'right' | 'both' | 'unspecified'
export interface Observation {
  id: string
  subject_id: string
  metric: MetricId
  value: number
  unit: string
  region: ObservationRegion
  side: ObservationSide
  method: string
  observed_at: string
  recorded_at: string
  source: { kind: 'manual' | 'device-import'; label: string }
  supersedes?: string
}
export interface TwinDocument {
  schema_version: 'humantwin-longitudinal-v1'
  use: 'synthetic-research'
  subject_id: string
  created_at: string
  observations: Observation[]
}
export interface ObservationInput {
  metric: MetricId; value: number; region: ObservationRegion; side: ObservationSide
  method: string; observed_at: string; source: Observation['source']; supersedes?: string
}
export const metrics = {
  resting_heart_rate: { label: 'Resting heart rate', unit: 'bpm', methods: ['manual-pulse', 'wrist-sensor'], min: 0, max: 1000000 },
  body_temperature: { label: 'Body temperature', unit: '°C', methods: ['oral', 'axillary', 'tympanic'], min: -273.15, max: 1000000 },
  pain: { label: 'Self-reported pain', unit: '/10', methods: ['self-report'], min: 0, max: 10 }
} as const
const regions = ['systemic', 'eyes', 'head', 'chest', 'abdomen', 'arms', 'legs']
const sides = ['left', 'right', 'both', 'unspecified']
const HOUR = 3600000

function requireValue(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message)
}
function exactKeys(value: unknown, allowed: string[], label: string): asserts value is Record<string, unknown> {
  requireValue(value && typeof value === 'object' && !Array.isArray(value), `${label} must be an object.`)
  for (const key of Object.keys(value)) requireValue(allowed.includes(key), `${label} has an unsupported field: ${key}.`)
}
function timestamp(value: unknown, label: string) {
  requireValue(typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value), `${label} must be a UTC ISO timestamp.`)
  const time = Date.parse(value)
  requireValue(Number.isFinite(time) && new Date(time).toISOString() === value.replace(/Z$/, value.includes('.') ? 'Z' : '.000Z'), `${label} is invalid.`)
  return time
}
function identifier(value: unknown, label: string) {
  requireValue(typeof value === 'string' && /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$/.test(value), `${label}: use 1–64 letters, digits, underscores or hyphens.`)
}

export function newTwin(subject: string, now = new Date().toISOString()): TwinDocument {
  identifier(subject, 'Study subject ID')
  timestamp(now, 'Creation time')
  return { schema_version: 'humantwin-longitudinal-v1', use: 'synthetic-research', subject_id: subject, created_at: now, observations: [] }
}

export function streamKey(observation: Pick<Observation, 'metric' | 'region' | 'side' | 'method' | 'source'>) {
  return JSON.stringify([observation.metric, observation.region, observation.side, observation.method, observation.source.kind, observation.source.label])
}

export function validateTwin(value: unknown, now = Date.now()): TwinDocument {
  exactKeys(value, ['schema_version', 'use', 'subject_id', 'created_at', 'observations'], 'Research twin')
  requireValue(value.schema_version === 'humantwin-longitudinal-v1', 'Unsupported research-twin version.')
  requireValue(value.use === 'synthetic-research', 'This prototype accepts synthetic research records only.')
  identifier(value.subject_id, 'Study subject ID')
  const created = timestamp(value.created_at, 'Creation time')
  requireValue(created <= now + 5 * 60000, 'Creation time is in the future.')
  requireValue(Array.isArray(value.observations) && value.observations.length <= 1000, 'Use at most 1,000 observation events per research twin.')
  const ids = new Map<string, Observation>(), superseded = new Set<string>(), activeTimes = new Map<string, string>()
  let previousRecorded = created
  for (const item of value.observations) {
    exactKeys(item, ['id', 'subject_id', 'metric', 'value', 'unit', 'region', 'side', 'method', 'observed_at', 'recorded_at', 'source', 'supersedes'], 'Observation')
    identifier(item.id, 'Observation ID')
    requireValue(!ids.has(item.id as string), 'Observation IDs must be unique.')
    requireValue(item.subject_id === value.subject_id, 'An observation belongs to a different subject.')
    requireValue(typeof item.metric === 'string' && Object.hasOwn(metrics, item.metric), 'Unsupported measurement.')
    const definition = metrics[item.metric as MetricId]
    requireValue(typeof item.value === 'number' && Number.isFinite(item.value) && item.value >= definition.min && item.value <= definition.max, 'The value is outside the supported numeric input domain. These are data checks, not clinical ranges.')
    requireValue(item.unit === definition.unit, `Use ${definition.unit}; silent unit conversion is not supported.`)
    requireValue(typeof item.method === 'string' && (definition.methods as readonly string[]).includes(item.method), 'Choose a supported measurement method.')
    requireValue(typeof item.region === 'string' && regions.includes(item.region), 'Unsupported anatomical region.')
    requireValue(typeof item.side === 'string' && sides.includes(item.side), 'Unsupported patient side.')
    if (item.metric !== 'pain') requireValue(item.region === 'systemic' && item.side === 'unspecified', 'Systemic measurements cannot be attached to a single eye or limb.')
    else requireValue(item.region !== 'systemic', 'Attach a pain observation to a reported body region.')
    const observed = timestamp(item.observed_at, 'Observed time'), recorded = timestamp(item.recorded_at, 'Recorded time')
    requireValue(observed <= recorded && recorded <= now + 5 * 60000 && recorded >= previousRecorded, 'Observation/recording times are inconsistent or in the future.')
    previousRecorded = recorded
    exactKeys(item.source, ['kind', 'label'], 'Observation source')
    requireValue(item.source.kind === 'manual' || item.source.kind === 'device-import', 'Unsupported observation source.')
    requireValue(typeof item.source.label === 'string' && item.source.label.trim().length > 0 && item.source.label.length <= 120, 'Provide a source label of 1–120 characters.')
    const observation = item as unknown as Observation
    if (item.supersedes !== undefined) {
      requireValue(typeof item.supersedes === 'string', 'A correction must identify an earlier observation.')
      const original = ids.get(item.supersedes)
      requireValue(original && !superseded.has(original.id), 'Correct the latest active observation, not an unknown or already superseded record.')
      requireValue(streamKey(original) === streamKey(observation) && original.observed_at === observation.observed_at, 'A correction must retain the original stream and observed time.')
      superseded.add(original.id)
    }
    const timeKey = `${streamKey(observation)}|${new Date(observed).toISOString()}`
    const collision = activeTimes.get(timeKey)
    requireValue(!collision || superseded.has(collision), 'A reading already exists for this stream and time. Use Correct to preserve its history.')
    activeTimes.set(timeKey, observation.id)
    ids.set(observation.id, observation)
  }
  // Build plain objects explicitly: Vue's reactive proxies cannot be structured-cloned.
  // No imported source object is retained by reference.
  return { schema_version: 'humantwin-longitudinal-v1', use: 'synthetic-research',
    subject_id: value.subject_id as string, created_at: value.created_at as string,
    observations: value.observations.map(item => {
      const observation = item as Observation
      return { ...observation, source: { ...observation.source } }
    }) }
}

export function activeObservations(document: TwinDocument): Observation[] {
  const superseded = new Set(document.observations.flatMap(item => item.supersedes ? [item.supersedes] : []))
  return document.observations.filter(item => !superseded.has(item.id)).sort((a, b) => Date.parse(a.observed_at) - Date.parse(b.observed_at) || a.id.localeCompare(b.id))
}

export function appendObservation(document: TwinDocument, input: ObservationInput, now = new Date().toISOString()): TwinDocument {
  requireValue(Object.hasOwn(metrics, input.metric), 'Unsupported measurement.')
  const observation: Observation = { ...input, id: crypto.randomUUID(), subject_id: document.subject_id,
    unit: metrics[input.metric].unit, recorded_at: now, source: { ...input.source } }
  return validateTwin({ ...document, observations: [...document.observations, observation] }, Date.parse(now))
}

export function streams(document: TwinDocument) {
  const result = new Map<string, Observation[]>()
  for (const observation of activeObservations(document)) {
    const key = streamKey(observation)
    const items = result.get(key) || []
    items.push(observation)
    result.set(key, items)
  }
  return [...result.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([key, observations]) => ({ key, observations }))
}

// Two-sided 95% Student-t critical values for 1..30 residual degrees of freedom.
// For >30, use df=30 as a conservative approximation, explicitly reported below.
const criticalT = [0, 12.706205, 4.302653, 3.182446, 2.776445, 2.570582, 2.446912, 2.364624, 2.306004, 2.262157, 2.228139, 2.200985, 2.178813, 2.160369, 2.144787, 2.131450, 2.119905, 2.109816, 2.100922, 2.093024, 2.085963, 2.079614, 2.073873, 2.068658, 2.063899, 2.059539, 2.055529, 2.051831, 2.048407, 2.045230, 2.042272]

export interface TwinProjection {
  available: boolean; reason: string; model_version: string; n: number
  forecast_at?: string; estimate?: number; lower?: number; upper?: number; slope_per_hour?: number
  residual_sd?: number; degrees_of_freedom?: number; t_critical?: number; training_ids?: string[]
}
export function projectStream(observations: Observation[], horizonHours: number): TwinProjection {
  const base = { available: false, reason: '', model_version: 'linear-research-v1', n: observations.length }
  if (!Number.isFinite(horizonHours) || horizonHours <= 0) return { ...base, reason: 'Choose a positive projection horizon.' }
  if (observations.length < 4) return { ...base, reason: 'At least four active observations in one measurement stream are needed.' }
  const ordered = [...observations].sort((a, b) => Date.parse(a.observed_at) - Date.parse(b.observed_at))
  if (ordered.some(item => item.subject_id !== ordered[0]!.subject_id || streamKey(item) !== streamKey(ordered[0]!))) return { ...base, reason: 'Measurements from different subjects, methods or anatomical streams cannot be pooled.' }
  if (ordered[0]!.metric === 'pain') return { ...base, reason: 'Pain scores are ordinal self-reports. This model does not forecast them.' }
  const times = ordered.map(item => Date.parse(item.observed_at))
  if (new Set(times).size !== times.length) return { ...base, reason: 'Projection requires distinct observation times.' }
  const first = times[0]!, last = times.at(-1)!, span = (last - first) / HOUR
  if (span < 1 || horizonHours > span / 2) return { ...base, reason: 'Use at least one hour of observations and a horizon no longer than half their observed span.' }
  const x = times.map(time => (time - first) / HOUR), y = ordered.map(item => item.value), n = x.length
  const meanX = x.reduce((a, b) => a + b, 0) / n, meanY = y.reduce((a, b) => a + b, 0) / n
  const sxx = x.reduce((sum, value) => sum + (value - meanX) ** 2, 0)
  const slope = x.reduce((sum, value, index) => sum + (value - meanX) * (y[index]! - meanY), 0) / sxx
  const intercept = meanY - slope * meanX
  const residual = y.reduce((sum, value, index) => sum + (value - intercept - slope * x[index]!) ** 2, 0)
  const residualSD = Math.sqrt(residual / (n - 2)), futureX = span + horizonHours
  const t = criticalT[Math.min(n - 2, 30)]!, estimate = intercept + slope * futureX
  const half = t * residualSD * Math.sqrt(1 + 1 / n + (futureX - meanX) ** 2 / sxx)
  const lower = estimate - half, upper = estimate + half, domain = metrics[ordered[0]!.metric]
  if (![estimate, lower, upper, slope, residualSD].every(Number.isFinite) || lower < domain.min || upper > domain.max) return { ...base, reason: 'The experimental projection extends beyond the supported numeric domain and is withheld.' }
  return { ...base, available: true, reason: 'An unvalidated linear extrapolation of this subject’s observations. The 95% model prediction interval assumes independent, normally distributed, constant-variance residuals; it is not a physiological or clinical guarantee. For more than 30 residual degrees of freedom, the df=30 critical value is used conservatively.',
    forecast_at: new Date(last + horizonHours * HOUR).toISOString(), estimate, lower, upper,
    slope_per_hour: slope, residual_sd: residualSD, degrees_of_freedom: n - 2, t_critical: t, training_ids: ordered.map(item => item.id) }
}

export function summarizeStream(observations: Observation[]) {
  const ordered = [...observations].sort((a, b) => Date.parse(a.observed_at) - Date.parse(b.observed_at))
  const latest = ordered.at(-1) ?? null
  const previous = ordered.slice(0, -1)
  const reference = previous.length ? previous.reduce((sum, item) => sum + item.value, 0) / previous.length : null
  return { latest, count: ordered.length, reference, reference_count: previous.length,
    delta: latest && reference !== null ? latest.value - reference : null }
}

export function backtestStream(observations: Observation[]) {
  const ordered = [...observations].sort((a, b) => Date.parse(a.observed_at) - Date.parse(b.observed_at))
  const predictions: { target_id: string; training_ids: string[]; actual: number; estimate: number; persistence: number; lower: number; upper: number }[] = []
  // Rolling origin: a target and every later observation are excluded from fitting.
  for (let index = 4; index < ordered.length; index++) {
    const target = ordered[index]!, previous = ordered[index - 1]!
    const horizon = (Date.parse(target.observed_at) - Date.parse(previous.observed_at)) / HOUR
    const projection = projectStream(ordered.slice(0, index), horizon)
    if (!projection.available) continue
    predictions.push({ target_id: target.id, training_ids: projection.training_ids!, actual: target.value,
      estimate: projection.estimate!, lower: projection.lower!, upper: projection.upper!, persistence: previous.value })
  }
  const count = predictions.length
  return { method: 'rolling-origin-v1', count, skipped: Math.max(0, ordered.length - 4) - count,
    model_mae: count ? predictions.reduce((sum, item) => sum + Math.abs(item.actual - item.estimate), 0) / count : null,
    persistence_mae: count ? predictions.reduce((sum, item) => sum + Math.abs(item.actual - item.persistence), 0) / count : null,
    interval_hits: predictions.filter(item => item.actual >= item.lower && item.actual <= item.upper).length,
    predictions }
}

export function analyzeTwin(document: TwinDocument, horizonHours: number, now = new Date().toISOString()) {
  const validated = validateTwin(document, Date.parse(now))
  return { schema_version: 'humantwin-analysis-v1', use: 'synthetic-research', generated_at: now,
    interpretation: 'Unvalidated individual observation model. No diagnosis, treatment recommendation, physiological simulation or clinical prediction claim.',
    horizon_hours: horizonHours, record: validated,
    streams: streams(validated).map(item => ({ stream_key: item.key, summary: summarizeStream(item.observations),
      projection: projectStream(item.observations, horizonHours), retrospective: backtestStream(item.observations) })) }
}

export function syntheticExample(now = new Date().toISOString()): TwinDocument {
  const current = Date.parse(now)
  const document = newTwin('SYNTHETIC-001', new Date(current - 26 * HOUR).toISOString())
  const values = [76, 74, 75, 72, 73, 71, 72]
  document.observations = values.map((value, index) => ({ id: `example-${index + 1}`, subject_id: document.subject_id,
    metric: 'resting_heart_rate', value, unit: 'bpm', region: 'systemic', side: 'unspecified', method: 'manual-pulse',
    observed_at: new Date(current - (25 - index * 4) * HOUR).toISOString(),
    recorded_at: new Date(current - (25 - index * 4) * HOUR).toISOString(), source: { kind: 'manual', label: 'Explicit synthetic research example' } }))
  return validateTwin(document, current)
}
