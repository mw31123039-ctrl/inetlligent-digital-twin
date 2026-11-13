<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import AppIcon from '../components/AppIcon.vue'
import TwinHumanPreview from './TwinHumanPreview.vue'
import { getRegion } from '../data/regions'
import type { RegionId } from '../types'
import type { PatientSide } from '../data/bodyParts'
import { activeObservations, analyzeTwin, appendObservation, backtestStream, metrics, newTwin, projectStream, streamKey, streams, summarizeStream, syntheticExample, validateTwin } from './model'
import type { MetricId, Observation, ObservationSide, TwinDocument } from './model'

const document = defineModel<TwinDocument | null>('document', { required: true })
defineProps<{ reducedMotion?: boolean }>()
const emit = defineEmits<{ explore: [region: RegionId, side?: PatientSide]; cancer: [] }>()
const subject = ref('STUDY-001'), error = ref(''), notice = ref('')
const pendingImport = ref<TwinDocument | null>(null)
const activeKey = ref(''), metric = ref<MetricId>('resting_heart_rate'), value = ref<string | number>('')
const method = ref('manual-pulse'), source = ref('Synthetic manual entry')
const region = ref<RegionId>('eyes'), side = ref<ObservationSide>('unspecified')
const observed = ref(new Date(Date.now() + 3 * 3600000).toISOString().slice(0, 16))
const correction = ref<Observation | null>(null), horizon = ref(1)
const allStreams = computed(() => document.value ? streams(document.value) : [])
const selected = computed(() => allStreams.value.find(item => item.key === activeKey.value) ?? allStreams.value[0] ?? null)
const points = computed(() => selected.value?.observations ?? [])
const summary = computed(() => summarizeStream(points.value))
const projection = computed(() => projectStream(points.value, horizon.value))
const retrospective = computed(() => backtestStream(points.value))
const definition = computed(() => metrics[metric.value])
const selectedDefinition = computed(() => summary.value.latest ? metrics[summary.value.latest.metric] : null)
const activeIds = computed(() => new Set(document.value ? activeObservations(document.value).map(item => item.id) : []))
const ledger = computed(() => document.value ? [...document.value.observations].reverse() : [])
const regionIds: RegionId[] = ['eyes', 'head', 'chest', 'abdomen', 'arms', 'legs']
watch(metric, () => { method.value = metrics[metric.value].methods[0] })
watch(() => document.value?.subject_id, () => { correction.value = null; activeKey.value = ''; error.value = '' })
const number = (input: number | null | undefined) => input === null || input === undefined ? '—' : Number(input.toFixed(2)).toLocaleString()
const date = (input: string) => new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Baghdad', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' }).format(new Date(input))
function streamLabel(item: Observation) { return `${metrics[item.metric].label} · ${item.region === 'systemic' ? 'Systemic' : getRegion(item.region).label + ' / ' + item.side} · ${item.method} · ${item.source.label}` }
function fail(cause: unknown) { error.value = cause instanceof Error ? cause.message : 'The research record could not be updated.' }
function start() {
  try {
    const candidate = newTwin(subject.value.trim())
    if (document.value?.observations.length) pendingImport.value = candidate
    else document.value = candidate
    error.value = ''; notice.value = 'An empty research twin is ready. No observations have been inferred.'
  } catch (cause) { fail(cause) }
}
function example() {
  const candidate = syntheticExample()
  if (document.value?.observations.length) pendingImport.value = candidate
  else document.value = candidate
  notice.value = 'The example contains explicitly synthetic readings, not patient measurements.'
}
async function importFile(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]
  if (!file) return
  try {
    if (file.size > 2 * 1024 * 1024) throw new Error('Choose a research JSON file smaller than 2 MB.')
    pendingImport.value = validateTwin(JSON.parse(await file.text()))
    error.value = ''
  } catch (cause) { fail(cause) }
  input.value = ''
}
function acceptImport() {
  if (!pendingImport.value) return
  document.value = pendingImport.value; subject.value = pendingImport.value.subject_id
  pendingImport.value = null; correction.value = null; activeKey.value = ''; error.value = ''
  notice.value = 'Research twin loaded. Source labels are supplied metadata, not verified device connections.'
}
function saveObservation() {
  if (!document.value) return
  try {
    if (!String(value.value).trim()) throw new Error('Enter an observation value; an empty field is not zero.')
    const editing = correction.value
    const candidate = appendObservation(document.value, editing ? {
      metric: editing.metric, value: Number(value.value), region: editing.region, side: editing.side,
      method: editing.method, observed_at: editing.observed_at, source: { ...editing.source }, supersedes: editing.id
    } : {
      metric: metric.value, value: Number(value.value), region: metric.value === 'pain' ? region.value : 'systemic',
      side: metric.value === 'pain' ? side.value : 'unspecified', method: method.value,
      observed_at: new Date(observed.value + ':00+03:00').toISOString(), source: { kind: 'manual', label: source.value.trim() }
    })
    activeKey.value = streamKey(candidate.observations.at(-1)!); document.value = candidate
    correction.value = null; value.value = ''; error.value = ''
    notice.value = editing ? 'Correction appended. The original event remains in the ledger and is excluded from the model.' : 'Observation added. The subject’s reference and experimental model have been recomputed.'
  } catch (cause) { fail(cause) }
}
function edit(item: Observation) {
  correction.value = item; metric.value = item.metric; value.value = String(item.value); error.value = ''
  window.document.getElementById('twin-reading')?.focus()
}
async function useSelectedStream() {
  const item = summary.value.latest
  if (!item) return
  correction.value = null; metric.value = item.metric; value.value = ''
  await nextTick()
  method.value = item.method; source.value = item.source.label
  if (item.region !== 'systemic') region.value = item.region
  side.value = item.side
}
function download(analysis = false) {
  if (!document.value) return
  const content = analysis ? analyzeTwin(document.value, horizon.value) : document.value
  const blob = new Blob([JSON.stringify(content, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob), link = window.document.createElement('a')
  link.href = url; link.download = `humantwin-${analysis ? 'analysis' : 'research'}-${document.value.subject_id}.json`; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  notice.value = analysis ? 'Model analysis exported with its input ledger, horizon, projection provenance and retrospective predictions.' : 'Research JSON exported. It includes the subject ID, readings and original correction history.'
}

const chart = computed(() => {
  if (!points.value.length) return null
  const first = Date.parse(points.value[0]!.observed_at), last = Date.parse(points.value.at(-1)!.observed_at)
  const forecast = projection.value.available ? projection.value : null
  const end = forecast ? Date.parse(forecast.forecast_at!) : Math.max(last, first + 3600000)
  const values = points.value.map(item => item.value)
  if (forecast) values.push(forecast.lower!, forecast.upper!)
  if (summary.value.reference !== null) values.push(summary.value.reference)
  const low = Math.min(...values), high = Math.max(...values), padding = Math.max((high - low) * 0.18, 0.5)
  const min = low - padding, max = high + padding
  const x = (time: number) => 54 + (time - first) / (end - first) * 620
  const y = (reading: number) => 218 - (reading - min) / (max - min) * 184
  return { path: points.value.map((item, index) => `${index ? 'L' : 'M'}${x(Date.parse(item.observed_at))},${y(item.value)}`).join(' '),
    dots: points.value.map(item => ({ id: item.id, x: x(Date.parse(item.observed_at)), y: y(item.value), text: `${date(item.observed_at)}: ${number(item.value)} ${item.unit}` })),
    ticks: [0, 1, 2, 3].map(index => ({ y: 218 - index / 3 * 184, value: number(min + index / 3 * (max - min)) })),
    referenceY: summary.value.reference === null ? null : y(summary.value.reference), first: date(points.value[0]!.observed_at), end: date(new Date(end).toISOString()),
    forecast: forecast ? { x: x(end), y: y(forecast.estimate!), lower: y(forecast.lower!), upper: y(forecast.upper!), startX: x(last), startY: y(points.value.at(-1)!.value) } : null }
})
</script>

<template>
  <section class="patient-twin" aria-label="Patient-specific research twin">
    <div class="twin-notice"><AppIcon name="info" :size="20"/><p><strong>Patient-specific research prototype · synthetic inputs only.</strong> The model updates from one subject’s recorded observations. Projections are experimental; they do not diagnose disease or establish clinical safety. The anatomy remains schematic.</p></div>
    <div v-if="error" class="twin-error" role="alert">{{ error }}</div>
    <p v-if="notice" class="twin-feedback" role="status">{{ notice }}</p>
    <div v-if="pendingImport" class="twin-import-review"><strong>Review incoming research twin</strong><p>Subject <b>{{ pendingImport.subject_id }}</b> · {{ pendingImport.observations.length }} ledger events · {{ activeObservations(pendingImport).length }} active readings.</p><p>This replaces the in-memory workspace. Export the current record first if you need to keep it.</p><button class="button-primary" @click="acceptImport">Use this research twin</button><button class="button-secondary" @click="pendingImport = null">Cancel</button></div>
    <div class="twin-toolbar">
      <form class="twin-subject-form" @submit.prevent="start"><label for="twin-subject">Synthetic study subject ID</label><div><input id="twin-subject" v-model="subject" maxlength="64" required autocomplete="off"/><button class="button-secondary" type="submit">Start empty twin</button></div></form>
      <div class="twin-actions"><button class="button-secondary" @click="emit('cancer')"><AppIcon name="scan" :size="16"/>Cancer research</button><button class="button-secondary" @click="example"><AppIcon name="sparkles" :size="16"/>Load synthetic example</button><label class="button-secondary twin-file">Import research JSON<input type="file" accept="application/json,.json" aria-label="Import research JSON" @change="importFile"/></label><button class="button-secondary" :disabled="!document" @click="download(false)"><AppIcon name="download" :size="16"/>Export record</button><button class="button-secondary" :disabled="!document" @click="download(true)">Export model analysis</button></div>
    </div>
    <div v-if="!document" class="twin-empty"><TwinHumanPreview :reduced-motion="reducedMotion" @explore="(id, patientSide) => emit('explore', id, patientSide)"/><AppIcon name="activity" :size="36"/><h2>A twin that changes with its subject</h2><p>Start a research subject or load the explicit synthetic example. Add observations over time to build an individual reference and inspect a model that updates with new data.</p><span>No measurements are inferred from the body model. Drafts stay in memory; export JSON to keep a record.</span></div>
    <template v-else>
      <div class="twin-identity"><div><span class="twin-eyebrow">ACTIVE SUBJECT</span><h2>{{ document.subject_id }}</h2><p>Revision {{ document.observations.length }} · {{ activeIds.size }} active observations · {{ allStreams.length }} measurement streams</p></div><span class="twin-memory"><i></i>In-memory research record</span></div>
      <div class="twin-layout">
        <aside class="twin-panel twin-capture"><TwinHumanPreview :selected="summary.latest?.region === 'systemic' ? null : summary.latest?.region ?? null" :side="summary.latest?.side === 'right' ? 'right' : 'left'" :reduced-motion="reducedMotion" @explore="(id, patientSide) => emit('explore', id, patientSide)"/><h3>{{ correction ? 'Correct a reading' : 'Record an observation' }}</h3><button v-if="selected && !correction" class="twin-text-button twin-use-stream" @click="useSelectedStream">Use selected stream</button><p v-if="correction" class="twin-caption">Correcting {{ correction.id }}. Time, measurement method and source stay attached to the original reading.</p><form @submit.prevent="saveObservation">
          <label>Measurement<select aria-label="Measurement" v-model="metric" :disabled="!!correction"><option v-for="(item, id) in metrics" :key="id" :value="id">{{ item.label }} ({{ item.unit }})</option></select></label>
          <template v-if="metric === 'pain' && !correction"><label>Reported body region<select aria-label="Reported body region" v-model="region"><option v-for="id in regionIds" :key="id" :value="id">{{ getRegion(id).label }}</option></select></label><label>Patient side<select aria-label="Patient side" v-model="side"><option value="unspecified">Unspecified</option><option value="left">Left</option><option value="right">Right</option><option value="both">Both</option></select></label></template>
          <label for="twin-reading">{{ correction ? metrics[correction.metric].label : definition.label }} value ({{ correction ? correction.unit : definition.unit }})<input id="twin-reading" v-model="value" type="number" step="any" required inputmode="decimal"/></label>
          <template v-if="!correction"><label>Observed time (Baghdad, UTC+03:00)<input v-model="observed" type="datetime-local" required/></label><label>Measurement method<select aria-label="Measurement method" v-model="method"><option v-for="item in definition.methods" :key="item" :value="item">{{ item.replaceAll('-', ' ') }}</option></select></label><label>Source label<input v-model="source" maxlength="120" required placeholder="Study device or manual source"/></label></template>
          <p class="twin-caption">Manual and imported source labels are unverified metadata. Different methods, sources, sides and regions stay in separate streams. Values are never classified as clinically normal.</p>
          <button class="button-primary" type="submit"><AppIcon name="plus" :size="16"/>{{ correction ? 'Append correction' : 'Add observation' }}</button><button v-if="correction" type="button" class="button-secondary" @click="correction = null; value = ''">Cancel correction</button>
        </form></aside>
        <div class="twin-model-column"><section class="twin-panel"><div class="twin-section-heading"><div><span class="twin-eyebrow">PERSONAL OBSERVATION MODEL</span><h3>Trajectory and individual reference</h3></div><label class="twin-horizon">Projection horizon<select aria-label="Projection horizon" v-model.number="horizon"><option :value="1">1 hour</option><option :value="6">6 hours</option><option :value="24">24 hours</option></select></label></div>
          <label class="twin-stream-label">Measurement stream<select aria-label="Measurement stream" :value="selected?.key ?? ''" @change="activeKey = ($event.target as HTMLSelectElement).value"><option v-if="!allStreams.length" value="">Add your first observation</option><option v-for="item in allStreams" :key="item.key" :value="item.key">{{ streamLabel(item.observations[0]!) }}</option></select></label>
          <div class="twin-stats"><div><span>Latest observed</span><strong>{{ number(summary.latest?.value) }} <small>{{ selectedDefinition?.unit }}</small></strong><em>{{ summary.latest ? date(summary.latest.observed_at) : 'No observations' }}</em></div><div><span>Personal reference mean</span><strong>{{ number(summary.reference) }} <small>{{ selectedDefinition?.unit }}</small></strong><em>{{ summary.reference_count }} earlier readings; excludes latest</em></div><div><span>Change from reference</span><strong>{{ summary.delta !== null && summary.delta > 0 ? '+' : '' }}{{ number(summary.delta) }}</strong><em>A descriptive change, not a clinical alert</em></div></div>
          <svg v-if="chart" class="twin-chart" viewBox="0 0 720 265" role="img" :aria-label="`${selectedDefinition?.label} over time for ${document.subject_id}. Exact observations are listed in the ledger.`"><g v-for="tick in chart.ticks" :key="tick.y"><line x1="54" x2="674" :y1="tick.y" :y2="tick.y" stroke="#e5edf1"/><text x="44" :y="tick.y + 4" text-anchor="end">{{ tick.value }}</text></g><line v-if="chart.referenceY !== null" x1="54" x2="674" :y1="chart.referenceY" :y2="chart.referenceY" stroke="#8fa5b5" stroke-dasharray="5 5"/><path :d="chart.path" fill="none" stroke="#119ca6" stroke-width="2.5"/><g v-for="dot in chart.dots" :key="dot.id"><circle :cx="dot.x" :cy="dot.y" r="4" fill="#119ca6"><title>{{ dot.text }}</title></circle></g><g v-if="chart.forecast"><line :x1="chart.forecast.startX" :y1="chart.forecast.startY" :x2="chart.forecast.x" :y2="chart.forecast.y" stroke="#8b67b6" stroke-width="2" stroke-dasharray="5 5"/><line :x1="chart.forecast.x" :x2="chart.forecast.x" :y1="chart.forecast.lower" :y2="chart.forecast.upper" stroke="#8b67b6" stroke-width="12" opacity=".2"/><circle :cx="chart.forecast.x" :cy="chart.forecast.y" r="5" fill="#8b67b6"/></g><text x="54" y="251">{{ chart.first }}</text><text x="674" y="251" text-anchor="end">{{ chart.end }}</text></svg>
          <div v-else class="twin-chart-empty">The chart will appear after an observation is recorded.</div><p class="twin-chart-key"><span>● Observed</span><span>┄ Personal reference</span><span>● Experimental projection and model interval</span></p>
          <div class="twin-projection" data-testid="twin-projection"><span class="twin-eyebrow">{{ projection.model_version }} · {{ projection.n }} ACTIVE READINGS</span><h4 v-if="projection.available">Experimental projection: {{ number(projection.estimate) }} {{ selectedDefinition?.unit }}</h4><h4 v-else>Projection withheld</h4><p v-if="projection.available">At {{ date(projection.forecast_at!) }} · 95% model prediction interval {{ number(projection.lower) }}–{{ number(projection.upper) }} {{ selectedDefinition?.unit }}.</p><p>{{ projection.reason }}</p><details v-if="projection.available"><summary>Model provenance and assumptions</summary><p>Ordinary least squares on observation time in hours. Slope {{ number(projection.slope_per_hour) }} {{ selectedDefinition?.unit }}/hour; residual SD {{ number(projection.residual_sd) }}; residual degrees of freedom {{ projection.degrees_of_freedom }}. No external model or disease prediction is used. Repeated physiological observations may violate the independence assumption.</p><p>Training observation IDs: <code>{{ projection.training_ids?.join(', ') }}</code></p></details></div>
          <div class="twin-retrospective"><h4>Retrospective prediction check</h4><p v-if="retrospective.count">{{ retrospective.count }} past targets · model mean absolute error {{ number(retrospective.model_mae) }} {{ selectedDefinition?.unit }} · last-value baseline error {{ number(retrospective.persistence_mae) }} {{ selectedDefinition?.unit }}. The model interval includes {{ retrospective.interval_hits }}/{{ retrospective.count }} targets.</p><p v-else>More eligible observations are needed for a retrospective comparison with the last-observed-value baseline.</p><p>Each target is predicted using earlier observations only. This small within-subject check is exploratory and does not establish clinical validity. {{ retrospective.skipped }} target(s) withheld by model eligibility checks.</p></div>
        </section></div>
      </div>
      <section class="twin-panel twin-ledger"><div class="twin-section-heading"><div><span class="twin-eyebrow">OBSERVATION AND CORRECTION HISTORY</span><h3>Subject-bound event ledger</h3></div><span>{{ document.observations.length }} events</span></div><p class="twin-caption">Recorded times track entry; observed times track measurement. Corrections retain originals. Superseded readings never enter the current model.</p><div class="twin-table-scroll"><table><thead><tr><th>Observed (Baghdad)</th><th>Measurement / anatomy</th><th>Value</th><th>Source / provenance</th><th>Model state</th><th>Action</th></tr></thead><tbody><tr v-for="item in ledger" :key="item.id" :class="{ 'twin-superseded': !activeIds.has(item.id) }"><td>{{ date(item.observed_at) }}<small>Recorded {{ date(item.recorded_at) }}</small></td><td>{{ metrics[item.metric].label }}<small>{{ item.region }} · {{ item.side }} · {{ item.method }}</small></td><td>{{ number(item.value) }} {{ item.unit }}</td><td>{{ item.source.label }}<small>{{ item.source.kind }} · {{ item.id }}</small><small v-if="item.supersedes">Corrects {{ item.supersedes }}</small></td><td><span class="twin-status">{{ activeIds.has(item.id) ? 'Active' : 'Superseded' }}</span></td><td><button v-if="activeIds.has(item.id)" class="twin-text-button" @click="edit(item)">Correct</button></td></tr><tr v-if="!ledger.length"><td colspan="6">No observation events have been recorded.</td></tr></tbody></table></div></section>
    </template>
  </section>
</template>
