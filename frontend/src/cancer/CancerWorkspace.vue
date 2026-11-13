<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppIcon from '../components/AppIcon.vue'
import { aiApi } from '../services/aiApi'
import { acceptResult, blankHistory, emptyStatus, modalities, parseStatus, pathways, preferredModality, readResearchImage, researchRecord } from './model'
import type { CancerModality, CancerResult, CancerTrack, ResearchImage } from './model'
import CancerBodyMap from './CancerBodyMap.vue'
import CancerKnowledge from './CancerKnowledge.vue'
import CancerCarePlan from './CancerCarePlan.vue'
import { blankConcerns, cancerTopics, hasEmergency, knowledgeVersion, readableClass, resultExplanation, reviewPlan } from './knowledge'
import './cancer-care.css'

const props = defineProps<{ user: { id: number } | null; twinSubject?: string }>()
const emit = defineEmits<{ signIn: []; openTwin: [] }>()
const selected = ref<CancerTrack>('skin'), modality = ref<CancerModality>('skin_photo')
const subject = ref(props.twinSubject || 'CASE-' + crypto.randomUUID().slice(0, 8).toUpperCase()), history = ref(blankHistory())
const activeTab = ref<'analysis' | 'knowledge' | 'plan'>('analysis'), planTopic = ref('skin')
const concerns = ref(blankConcerns()), emergencySeen = ref(false), exampleSource = ref('')
const currentPlan = computed(() => reviewPlan(planTopic.value, concerns.value, emergencySeen.value))
const registry = ref(emptyStatus()), checking = ref(false), preparing = ref(false), pending = ref(false)
const image = ref<ResearchImage | null>(null), result = ref<CancerResult | null>(null)
const error = ref(''), notice = ref(''), consent = ref(false), confirmed = ref(false), acknowledged = ref(false), exportConsent = ref(false)
const explain = ref(true), showOverlay = ref(true), overlayOpacity = ref(.65), dragActive = ref(false)
const path = computed(() => pathways.find(item => item.id === selected.value)!)
const selectedModels = computed(() => registry.value.pathways.find(item => item.track === selected.value)!.models)
const model = computed(() => selectedModels.value.find(item => item.modality === modality.value)!)
const installedCount = computed(() => registry.value.pathways.flatMap(item => item.models).filter(item => item.configured).length)
const linked = computed(() => !!props.twinSubject && subject.value === props.twinSubject)
const subjectValid = computed(() => /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(subject.value))
const canRun = computed(() => !!props.user && subjectValid.value && !!image.value && registry.value.available && model.value.configured && consent.value && confirmed.value && acknowledged.value && !emergencySeen.value && !pending.value && !preparing.value && !checking.value)
const rankedScores = computed(() => [...(result.value?.scores ?? [])].sort((a, b) => b.value - a.value))
const explanation = computed(() => result.value?.explanation ?? null)
const overlayCells = computed(() => explanation.value?.values.map((value, index) => ({ value,
  x: index % explanation.value!.grid_size * 100 / explanation.value!.grid_size,
  y: Math.floor(index / explanation.value!.grid_size) * 100 / explanation.value!.grid_size,
  size: 100 / explanation.value!.grid_size,
})) ?? [])
const imageStageStyle = computed(() => image.value ? { aspectRatio: image.value.width + ' / ' + image.value.height, maxWidth: image.value.width / image.value.height * 440 + 'px' } : {})
const runRequirement = computed(() => !model.value.configured ? 'A compatible model is not installed for this input.' : !props.user ? 'Sign in to run the installed model.' : !subjectValid.value ? 'Enter a coded study subject ID.' : !image.value ? 'Attach a matching research image.' : !consent.value || !confirmed.value || !acknowledged.value ? 'Confirm the input, research scope and processing permission below.' : 'Ready for local inference. Images are not saved or used for training.')
let generation = 0, request: AbortController | null = null, statusRequest: AbortController | null = null

function invalidate() {
  generation++; request?.abort(); request = null
  result.value = null; pending.value = false; preparing.value = false; error.value = ''; notice.value = ''; exportConsent.value = false
}
function clearImage() { invalidate(); image.value = null; consent.value = false; confirmed.value = false; acknowledged.value = false; exampleSource.value = '' }
function clearCase() { clearImage(); history.value = blankHistory(); concerns.value = blankConcerns(); emergencySeen.value = false; notice.value = 'Research draft cleared.' }
watch(selected, () => { clearCase(); modality.value = preferredModality(registry.value, selected.value); planTopic.value = selected.value; notice.value = '' })
watch(modality, clearImage)
watch(subject, () => { clearCase(); notice.value = '' })
watch(() => props.twinSubject, (value, previous) => { if (!subject.value || subject.value === previous) subject.value = value || '' })
watch(history, () => { exportConsent.value = false }, { deep: true })
watch([consent, confirmed, acknowledged], values => { if (pending.value && values.some(value => !value)) invalidate() })
watch(explain, () => { if (pending.value) invalidate() })
watch(concerns, value => { exportConsent.value = false; if (hasEmergency(value)) { emergencySeen.value = true; if (pending.value) invalidate() } }, { deep: true, flush: 'sync' })
function selectTrack(track: CancerTrack) { selected.value = track; planTopic.value = track; activeTab.value = 'analysis' }
function openPlan(topic = selected.value as string) { planTopic.value = topic; activeTab.value = 'plan' }
async function editCase() { activeTab.value = 'analysis'; await nextTick(); document.getElementById('care-case-context')?.scrollIntoView({ behavior: 'smooth', block: 'center' }) }
async function chooseImage() { activeTab.value = 'analysis'; await nextTick(); document.getElementById('care-file-input')?.click() }
async function dockAction() {
  if (emergencySeen.value) { openPlan(); return }
  if (!props.user) { emit('signIn'); return }
  if (canRun.value) { await analyze(); return }
  document.querySelector('.care-run-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
async function moveSection(direction: number) {
  const tabs = ['analysis', 'knowledge', 'plan'] as const
  activeTab.value = tabs[(tabs.indexOf(activeTab.value) + direction + tabs.length) % tabs.length]!
  await nextTick(); document.getElementById('care-' + activeTab.value + '-tab')?.focus()
}
async function loadExample(kind: 'benign' | 'malignant') {
  selected.value = 'oral'; activeTab.value = 'analysis'; await nextTick()
  const revision = generation
  try {
    const response = await fetch('/cancer-examples/oral-' + kind + '-reference.png', { cache: 'no-store' })
    if (!response.ok) throw new Error('The public reference image could not be loaded.')
    const blob = await response.blob()
    if (revision !== generation) return
    await prepareFile(new File([blob], 'public-oral-' + kind + '.png', { type: 'image/png' }))
    if (image.value && selected.value === 'oral') {
      exampleSource.value = 'Public oral reference: source-labeled ' + kind + ' lesion. Chandrashekar et al., Mendeley Oral Images Dataset v2, CC BY 4.0. Resized from an original photograph; not a personal diagnosis.'
      notice.value = 'Public example loaded. Confirm the input and processing permissions before running the model.'
    }
  } catch (cause) { if (revision === generation) error.value = cause instanceof Error ? cause.message : 'The reference image could not be loaded.' }
}

async function checkModels() {
  statusRequest?.abort(); statusRequest = new AbortController()
  const active = statusRequest
  checking.value = true; result.value = null
  try {
    const value = await aiApi.get<unknown>('/cancer/status', active.signal)
    if (!active.signal.aborted) {
      registry.value = parseStatus(value)
      if (!image.value) modality.value = preferredModality(registry.value, selected.value, modality.value)
    }
  } catch {
    if (!active.signal.aborted) { registry.value = emptyStatus(); notice.value = 'The model service could not be reached. No result has been generated.' }
  } finally { if (statusRequest === active) checking.value = false }
}
onMounted(checkModels)
onBeforeUnmount(() => { invalidate(); statusRequest?.abort() })
async function prepareFile(file: File) {
  clearImage(); preparing.value = true; dragActive.value = false
  const revision = generation
  try { const prepared = await readResearchImage(file); if (revision === generation) { image.value = prepared; await nextTick(); if (activeTab.value === 'analysis') document.querySelector('.care-image-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' }) } }
  catch (cause) { if (revision === generation) error.value = cause instanceof Error ? cause.message : 'The image could not be prepared.' }
  finally { if (revision === generation) preparing.value = false }
}
function attach(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]
  input.value = ''; if (file) void prepareFile(file)
}
function dropFile(event: DragEvent) { dragActive.value = false; const file = event.dataTransfer?.files[0]; if (file && !preparing.value) void prepareFile(file) }
async function analyze() {
  if (!canRun.value || !image.value) return
  invalidate(); pending.value = true; request = new AbortController()
  const active = request, revision = generation, currentImage = image.value
  const track = selected.value, inputModality = modality.value, expectedModel = { ...model.value }
  try {
    const value = await aiApi.post<unknown>('/cancer/analyze', {
      track, modality: inputModality, image_data_url: currentImage.dataUrl,
      consent_local: true, modality_confirmed: true, research_only_acknowledged: true, explain: explain.value,
    }, active.signal, 120_000)
    if (revision === generation && !active.signal.aborted) { result.value = acceptResult(value, track, inputModality, currentImage.sha256, expectedModel); showOverlay.value = true; await nextTick(); if (activeTab.value === 'analysis') document.querySelector('.cancer-result-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }
  } catch (cause) { if (revision === generation && !active.signal.aborted) error.value = cause instanceof Error ? cause.message : 'No result was generated.' }
  finally { if (revision === generation) { pending.value = false; request = null } }
}
function download() {
  if (!exportConsent.value || preparing.value || pending.value) return
  try {
    const record = { ...researchRecord(subject.value, props.twinSubject, selected.value, modality.value, history.value, image.value, result.value),
      knowledge_version: knowledgeVersion, review_guide: currentPlan.value,
      reported_concerns: { ...concerns.value, absence_not_established_for_unchecked_items: true, emergency_report_retained: emergencySeen.value },
      public_example_attribution: exampleSource.value || null }
    const url = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2)], { type: 'application/json' }))
    const link = document.createElement('a'); link.href = url; link.download = 'humantwin-cancer-' + selected.value + '-' + subject.value + '.json'; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    notice.value = 'Research record exported with notes and measured model outputs. Image pixels are excluded.'
  } catch (cause) { error.value = cause instanceof Error ? cause.message : 'The record could not be exported.' }
}
function readiness(state: string) { return state === 'configured-unvalidated' ? 'Research model configured' : state === 'invalid-artifacts' ? 'Model installation invalid' : state === 'service-unavailable' ? 'Service unavailable' : 'No model installed' }
function runtimeLabel(value: string) { return value === 'onnxruntime-cpu' ? 'ONNX Runtime · CPU' : 'OpenCV · CPU' }
function milliseconds(value: number) { return value >= 1000 ? (value / 1000).toFixed(2) + ' s' : value.toFixed(0) + ' ms' }
</script>

<template>
  <section class="cancer-workspace" :class="{ 'care-has-image': !!image && activeTab === 'analysis' }" aria-label="Cancer research workspace">
    <header class="care-hero">
      <div class="care-hero-copy"><span class="care-eyebrow"><i></i>HUMANTWIN / CANCER CARE</span><h2>A clearer picture.<br/><em>A better next step.</em></h2><p>Bring image analysis, symptoms and trusted cancer information into one place. Understand what a finding means and prepare for the right clinical review.</p><div class="care-hero-actions"><button class="care-primary" @click="chooseImage"><AppIcon name="plus" :size="21"/>Upload an image</button><button class="care-text-button" @click="activeTab = 'knowledge'">Explore cancer knowledge<AppIcon name="arrowRight" :size="18"/></button></div><div class="care-hero-facts"><span><AppIcon name="scan" :size="19"/>{{ installedCount }} local image models</span><span><AppIcon name="book" :size="19"/>{{ cancerTopics.length }} cancer knowledge guides</span><span><AppIcon name="shield" :size="19"/>Permission before processing</span></div></div>
      <div class="care-hero-map"><CancerBodyMap :selected="selected" @select="selectTrack"/><div class="care-hero-map-label"><strong>Your body, connected.</strong><span>A reference map for choosing a review area.</span></div></div>
    </header>

    <div class="care-section-nav" role="tablist" aria-label="Cancer workspace sections" @keydown.right.prevent="moveSection(1)" @keydown.left.prevent="moveSection(-1)"><button id="care-analysis-tab" role="tab" :aria-selected="activeTab === 'analysis'" aria-controls="care-analysis" :class="{ active: activeTab === 'analysis' }" @click="activeTab = 'analysis'"><AppIcon name="scan" :size="21"/>Analyze an image<span>01</span></button><button id="care-knowledge-tab" role="tab" :aria-selected="activeTab === 'knowledge'" aria-controls="care-knowledge" :class="{ active: activeTab === 'knowledge' }" @click="activeTab = 'knowledge'"><AppIcon name="book" :size="21"/>Cancer knowledge<span>02</span></button><button id="care-plan-tab" role="tab" :aria-selected="activeTab === 'plan'" aria-controls="care-plan" :class="{ active: activeTab === 'plan' }" @click="openPlan()"><AppIcon name="clipboard" :size="21"/>Care &amp; next steps<span>03</span></button></div>

    <div v-if="emergencySeen" class="care-emergency" role="alert"><AppIcon name="error" :size="28"/><div><h3>Seek emergency care now</h3><p>You reported an urgent warning sign. Do not wait for an image result. Contact your local emergency service or go to the nearest emergency department.</p><small>This guidance remains visible until you clear this case. Unchecking a box does not undo the earlier report.</small><button class="care-text-button" @click="openPlan()">View the review guidance<AppIcon name="arrowRight" :size="18"/></button></div></div>
    <div v-if="error" class="cancer-error" role="alert"><AppIcon name="error" :size="21"/>{{ error }}</div><p v-if="notice" class="cancer-notice" role="status">{{ notice }}</p>

    <section id="care-analysis" v-show="activeTab === 'analysis'" role="tabpanel" aria-labelledby="care-analysis-tab">
      <div class="care-analysis-intro"><div><span class="care-eyebrow">START HERE</span><h2>Upload the right image for the right model.</h2><p>Choose the area, attach a matching image, then review the computed finding. A model result alone cannot diagnose or exclude cancer.</p></div><span class="care-engine-status"><i :class="{ ready: installedCount > 0 }"></i>{{ checking ? 'Checking local engines…' : installedCount + ' models ready' }}</span></div>

      <div class="cancer-pathways" aria-label="Cancer pathways"><button v-for="item in pathways" :key="item.id" class="cancer-pathway" :class="{ selected: selected === item.id }" :aria-pressed="selected === item.id" @click="selectTrack(item.id)"><span class="care-path-icon"><AppIcon :name="item.icon" :size="25"/></span><div><strong>{{ item.label }}</strong><span>{{ item.id === 'skin' ? 'Dermoscopic skin images' : item.id === 'oral' ? 'Oral lesion photographs' : item.id === 'lung' ? 'Prepared CT slice images' : 'Breast ultrasound images' }}</span><small>{{ registry.pathways.find(p => p.track === item.id)?.models.some(m => m.configured) ? 'Local model available' : 'No compatible model ready' }}</small></div><AppIcon v-if="selected === item.id" name="check" :size="20"/></button></div>

      <div class="care-workflow-grid">
        <div class="care-upload-column">
          <section class="care-paper care-input-panel">
            <div class="care-panel-title"><div><span class="care-eyebrow">STEP 1 / SELECT THE INPUT</span><h3>{{ path.label }} research input</h3></div><button class="care-text-button" @click="clearCase"><AppIcon name="reset" :size="17"/>Clear case</button></div>
            <div class="care-input-pair"><label>Input type<select v-model="modality"><option v-for="id in path.modalities" :key="id" :value="id">{{ modalities[id].label }}{{ selectedModels.find(m => m.modality === id)?.configured ? ' · installed' : ' · no model installed' }}</option></select></label><label>Coded study subject ID<input v-model="subject" maxlength="64" autocomplete="off" spellcheck="false"/><small>A generated case code; no name is needed.</small></label></div>
            <p class="care-input-scope"><AppIcon name="info" :size="20"/>{{ modalities[modality].scope }}</p>
            <div class="cancer-twin-link"><span><AppIcon name="activity" :size="18"/>{{ linked ? 'Linked by code to the open twin: ' + props.twinSubject : props.twinSubject ? 'Open twin: ' + props.twinSubject + '. Match its code to link this review.' : 'You can link this case to a matching patient twin code.' }}</span><button class="care-text-button" @click="emit('openTwin')">Patient twin<AppIcon name="arrowRight" :size="17"/></button></div>
          </section>

          <section class="care-paper care-image-panel" @paste="event => { const file = event.clipboardData?.files[0]; if (file) { event.preventDefault(); void prepareFile(file) } }">
            <div class="care-panel-title"><div><span class="care-eyebrow">STEP 2 / ADD YOUR IMAGE</span><h3>{{ image ? 'Review the attached image' : 'Choose an image to analyze' }}</h3></div><span v-if="image" class="care-ready-chip"><i></i>Attached</span></div>
            <div v-if="!image" class="care-drop-zone" :class="{ dragging: dragActive }" @dragover.prevent="dragActive = true" @dragleave.prevent="dragActive = false" @drop.prevent="dropFile"><span class="care-upload-symbol"><AppIcon name="arrowDown" :size="31"/></span><h4>Drop your image here</h4><p>or choose a file from your computer</p><label class="care-primary care-file-button"><AppIcon name="plus" :size="21"/>{{ preparing ? 'Preparing your image…' : 'Upload an image' }}<input id="care-file-input" type="file" accept="image/jpeg,image/png" aria-label="Attach research image" :disabled="preparing" @change="attach"/></label><small>JPG or PNG · up to 16 MB<br/>Larger images are resized safely for this research workflow.</small></div>
            <div v-else class="care-image-viewer"><div class="care-viewer-top"><span>{{ image.width }} × {{ image.height }} · prepared JPEG</span><div aria-label="Image display"><button :class="{ active: !showOverlay || !explanation }" :aria-pressed="!showOverlay || !explanation" @click="showOverlay = false">Original</button><button :disabled="!explanation" :class="{ active: showOverlay && explanation }" :aria-pressed="!!(showOverlay && explanation)" @click="showOverlay = true">Sensitivity</button></div></div><div class="care-image-canvas"><div class="care-image-frame" :style="imageStageStyle"><img :src="image.dataUrl" alt="Attached research image preview"/><svg v-if="showOverlay && explanation" viewBox="0 0 100 100" preserveAspectRatio="none" class="cancer-heatmap" role="img" :aria-label="'Model sensitivity for ' + explanation.target_label + '; not tumor localization'"><title>Changes in model score under occlusion; not a tumor boundary</title><rect v-for="(cell,index) in overlayCells" :key="index" :x="cell.x" :y="cell.y" :width="cell.size" :height="cell.size" fill="#edb85c" :fill-opacity="cell.value * overlayOpacity"/></svg></div><span v-if="showOverlay && explanation" class="care-overlay-caption">MODEL SENSITIVITY · NOT TUMOR LOCATION</span></div><div class="care-image-actions"><label class="care-text-button care-replace">Replace image<input id="care-file-input" type="file" accept="image/jpeg,image/png" aria-label="Replace research image" @change="attach"/></label><button class="care-text-button" @click="clearImage">Remove image</button></div></div>
            <div v-if="pending" class="care-inference-state" role="status"><span></span><div><strong>Analyzing with the local model…</strong><p>{{ explain ? 'Computing class scores and 16 sensitivity comparisons.' : 'Computing class scores from the prepared image.' }}</p></div></div>
            <p v-if="image?.resized" class="care-help">Resized from {{ image.originalWidth }} × {{ image.originalHeight }} to {{ image.width }} × {{ image.height }}. The original file is not uploaded.</p>
            <div v-if="explanation && image" class="care-opacity"><label>Overlay opacity<input v-model.number="overlayOpacity" type="range" min="0" max="1" step="0.05"/></label><p>The map shows relative effects on the score. Largest raw score decrease: {{ explanation.max_score_drop?.toFixed(3) ?? 'not reported' }}.</p></div>
            <p v-if="exampleSource" class="care-reference-attribution">{{ exampleSource }} <a href="https://data.mendeley.com/datasets/mhjyrn35p4/2" target="_blank" rel="noopener noreferrer">View original source</a></p>
            <div class="care-example-row"><span>Want to try the workflow?</span><button class="care-text-button" :disabled="preparing || pending" @click="loadExample('benign')">Load a public oral example<AppIcon name="arrowRight" :size="17"/></button><details><summary>Another source-labeled example</summary><button class="care-text-button" :disabled="preparing || pending" @click="loadExample('malignant')">Load the malignant-lesion reference</button></details></div>
            <p class="care-help">Use de-identified research images. Visible names must be removed as well as file metadata. DICOM, scan volumes and PDFs are not accepted by these image models.</p>
          </section>

          <section id="care-case-context" class="care-paper cancer-history-panel">
            <details><summary><div><span class="care-eyebrow">CLINICAL CONTEXT</span><h3>Symptoms &amp; history for a reviewer</h3></div><AppIcon name="chevronDown" :size="20"/></summary><p class="care-help">These are user-reported notes for a reviewer. The image classifier does not analyze this text or turn it into a cancer risk estimate.</p><label>Symptoms or changes<textarea v-model="history.symptoms" rows="3" maxlength="2000" placeholder="What changed, and where? Please omit names and contact details."></textarea></label><label>When first noticed / duration<input v-model="history.duration" maxlength="120" placeholder="For example: reported for three weeks"/></label><div class="care-input-pair"><label>Reported family history of cancer<select v-model="history.family_history"><option value="unknown">Not recorded</option><option value="yes">Yes, reported</option><option value="no">No, reported</option></select></label><label>Reported tobacco exposure<select v-model="history.tobacco_exposure"><option value="unknown">Not recorded</option><option value="yes">Yes, reported</option><option value="no">No, reported</option></select></label></div><label>Previous examination or report reference<textarea v-model="history.prior_findings" rows="2" maxlength="2000" placeholder="A coded reference or reported finding; no diagnosis is verified here."></textarea></label></details>
            <details class="care-symptom-checks"><summary><div><span class="care-eyebrow">BEFORE WAITING FOR AI</span><h3>Any urgent symptoms?</h3></div><AppIcon name="chevronDown" :size="20"/></summary><p>Check any reported concern that applies. Unchecked items are not a clinical assessment of absence.</p><label class="care-checkbox"><input v-model="concerns.severe_breathing" type="checkbox"/>Severe difficulty breathing, such as gasping or being unable to get words out.</label><label class="care-checkbox"><input v-model="concerns.uncontrolled_bleeding" type="checkbox"/>Heavy bleeding that is not stopping.</label><label>Coughing up blood<select v-model="concerns.coughing_blood"><option value="not-recorded">Not recorded</option><option value="small-amount">A few spots or streaks</option><option value="more-than-streaks">More than a few spots or streaks</option></select></label><label class="care-checkbox"><input v-model="concerns.persistent_change" type="checkbox"/>A new, persistent or unexplained change needs assessment.</label><p class="care-help">This is not complete emergency triage. If someone seems seriously ill, seek medical help rather than waiting for AI.</p></details>
          </section>

          <section class="care-paper care-run-panel"><span class="care-eyebrow">STEP 3 / PROCESS WITH PERMISSION</span><h3>Ready to analyze?</h3><fieldset class="care-confirmations"><legend>Confirm the input and processing</legend><label class="care-checkbox"><input v-model="confirmed" type="checkbox"/>I confirm this image is {{ modalities[modality].label.toLowerCase() }} and matches the model’s intended input.</label><label class="care-checkbox"><input v-model="acknowledged" type="checkbox"/>I understand this is experimental single-image research and cannot establish a cancer diagnosis.</label><label class="care-checkbox"><input v-model="consent" type="checkbox"/>I permit sending this prepared image to the project’s research model service for local inference.</label></fieldset><label class="care-checkbox care-explain-toggle"><input v-model="explain" type="checkbox"/>Compute model sensitivity map<span>Runs additional comparisons; does not segment a tumor.</span></label><div class="care-run-actions"><button class="care-primary" :disabled="!canRun" @click="analyze"><AppIcon name="scan" :size="21"/>{{ pending ? 'Analyzing image…' : 'Run research model' }}<AppIcon v-if="!pending" name="arrowRight" :size="19"/></button><button v-if="!props.user" class="care-secondary" @click="emit('signIn')">Sign in to analyze</button></div><p class="care-help">{{ emergencySeen ? 'Image analysis is paused because an urgent concern was reported.' : runRequirement }}</p></section>
        </div>

        <aside class="care-results-column">
          <section class="care-paper cancer-result-panel" aria-live="polite"><div class="care-panel-title"><div><span class="care-eyebrow">YOUR IMAGE FINDINGS</span><h3>{{ result ? 'Model findings' : 'Your review starts here' }}</h3></div><span v-if="result" class="care-ready-chip"><i></i>Computed</span></div>
            <template v-if="result"><div class="care-top-finding"><span>Highest-scoring model category</span><strong>{{ readableClass(rankedScores[0]!.label) }}</strong><p>{{ resultExplanation(result) }}</p></div><div class="cancer-runtime-strip"><span v-if="result.inference_ms"><AppIcon name="clock" :size="18"/>{{ milliseconds(result.inference_ms) }} total{{ explanation ? ' · ' + explanation.grid_size * explanation.grid_size + ' perturbations' : '' }}</span><span v-if="result.runtime">{{ runtimeLabel(result.runtime) }}</span></div><div class="care-meaning-box"><h4>What happens next?</h4><p>A clinical examination and appropriate tests are needed to understand this finding. The model cannot confirm cancer, rule it out, or select treatment.</p><button class="care-text-button" @click="openPlan()">Build a review plan<AppIcon name="arrowRight" :size="18"/></button></div>
              <details class="care-technical" open><summary>Model scores and uncertainty<AppIcon name="chevronDown" :size="18"/></summary><div class="cancer-class-scores" aria-label="Uncalibrated class scores"><div v-for="score in rankedScores" :key="score.label" class="cancer-score-row"><div><span>{{ readableClass(score.label) }}</span><strong>{{ score.value.toFixed(3) }}</strong></div><div class="care-score-track"><i :style="{ width: score.value * 100 + '%' }"></i></div></div></div><p class="care-help">Scores use a 0–1 scale. They are not your probability of cancer.</p><div v-if="result.uncertainty" class="care-uncertainty"><div><span>Output entropy</span><strong>{{ result.uncertainty.normalized_entropy.toFixed(3) }}</strong><small>How spread out the model scores are.</small></div><div><span>Top-two margin</span><strong>{{ result.uncertainty.margin.toFixed(3) }}</strong><small>Separation between the leading categories.</small></div></div><p class="care-help">These measures describe the model output, not whether its prediction is correct.</p></details>
            </template><div v-else class="care-results-empty"><span><AppIcon :name="pending ? 'activity' : 'clipboard'" :size="36"/></span><h4>{{ pending ? 'The local model is processing your image' : 'A finding, with context' }}</h4><p>{{ pending ? 'Computed scores appear when processing finishes. No intermediate result is invented.' : 'After you upload and analyze an image, this panel explains the model category, its limitations and the next questions to discuss.' }}</p><ol><li>Choose the matching input type.</li><li>Upload a de-identified image.</li><li>Confirm permission and run the model.</li></ol><small>No diagnosis or risk level has been assigned.</small></div>
          </section>
          <section v-if="result?.image_checks" class="care-paper cancer-quality-panel"><span class="care-eyebrow">INPUT CHECKS</span><h3>About this image</h3><div class="care-image-metrics"><div><span>Brightness</span><strong>{{ result.image_checks.brightness.toFixed(1) }} / 255</strong></div><div><span>Contrast</span><strong>{{ result.image_checks.contrast.toFixed(1) }}</strong></div><div><span>Dimensions</span><strong>{{ result.image_checks.width }} × {{ result.image_checks.height }}</strong></div></div><ul class="care-image-warnings"><li v-for="warning in result.image_checks.warnings" :key="warning">{{ warning }}</li></ul></section>
          <section class="care-paper care-model-panel"><div class="care-panel-title"><div><span class="care-eyebrow">AVAILABLE MODELS</span><h3>{{ path.label }} inputs</h3></div><button class="care-text-button" :disabled="checking || pending" @click="checkModels"><AppIcon name="reset" :size="18"/>Refresh</button></div><button v-for="item in selectedModels" :key="item.modality" class="cancer-model-row" :class="{ current: item.modality === modality }" :aria-pressed="item.modality === modality" @click="modality = item.modality"><strong>{{ modalities[item.modality].label }}</strong><span :class="{ ready: item.configured }"><i></i>{{ readiness(item.state) }}</span><small v-if="item.model_version">{{ item.model_version }}</small></button><p class="care-help">Only compatible, installed models can analyze an image. Other cancer types are available in the knowledge library.</p><button class="care-text-button" @click="activeTab = 'knowledge'">Explore all {{ cancerTopics.length }} topics<AppIcon name="book" :size="18"/></button></section>
        </aside>
      </div>
    </section>

    <section id="care-knowledge" v-if="activeTab === 'knowledge'" role="tabpanel" aria-labelledby="care-knowledge-tab"><CancerKnowledge :signed-in="!!props.user" @analyze="selectTrack" @plan="openPlan" @sign-in="emit('signIn')"/></section>
    <section id="care-plan" v-if="activeTab === 'plan'" role="tabpanel" aria-labelledby="care-plan-tab"><CancerCarePlan :topic-id="planTopic" :concerns="concerns" :prior-emergency="emergencySeen" :history="history" :result="result" :subject="subject" @edit="editCase"/></section>

    <section v-if="result?.model_info && activeTab === 'analysis'" class="care-paper cancer-evidence-panel"><details><summary><div><span class="care-eyebrow">SOURCE &amp; PROVENANCE</span><h3>Where this result comes from</h3></div><AppIcon name="chevronDown" :size="21"/></summary><div class="care-evidence-grid"><div><span>Model version</span><strong>{{ result.model_version }}</strong></div><div><span>Original source</span><a :href="result.model_info.source_url" target="_blank" rel="noopener noreferrer">View the model or training source<AppIcon name="arrowRight" :size="17"/></a></div><div><span>License</span><p>{{ result.model_info.license }}</p></div><div><span>Evaluation reference</span><p>{{ result.model_info.evaluation_reference }}</p></div><div><span>Independent patient evaluation</span><p>{{ result.model_info.patient_disjoint === null ? 'Not established from the source.' : result.model_info.patient_disjoint ? 'Reported by the operator; not independently verified here.' : 'Patient separation not established.' }}</p></div></div><details class="care-fingerprints"><summary>Exact image and model fingerprints</summary><dl><dt>Prepared image SHA-256</dt><dd>{{ result.input_sha256 }}</dd><dt>Model weights SHA-256</dt><dd>{{ result.weights_sha256 }}</dd></dl></details></details></section>

    <section class="care-paper care-export-panel"><div><span class="care-eyebrow">TAKE THE INFORMATION WITH YOU</span><h3>Keep the evidence with your case.</h3><p>Export your case code, notes, image fingerprint, computed output and source-linked review checklist. Image pixels are excluded. Drafts clear on reload or account change.</p></div><div><label class="care-checkbox"><input v-model="exportConsent" type="checkbox"/>I permit downloading this research record, including my entered notes, to this device.</label><button class="care-secondary" :disabled="!subjectValid || !exportConsent || pending || preparing" @click="download"><AppIcon name="download" :size="19"/>Export research JSON</button><small>{{ linked ? 'The same coded twin subject is linked in the export.' : 'Exported without a twin link unless the subject codes match.' }}</small></div></section>
    <p class="care-footnote"><AppIcon name="info" :size="19"/>HumanTwin combines experimental image models with a curated reference library. It does not replace examination, pathology, a confirmed diagnosis or an individualized treatment decision. <a href="https://www.cancer.gov/about-cancer/diagnosis-staging/diagnosis" target="_blank" rel="noopener noreferrer">NCI: How cancer is diagnosed</a></p>
    <div v-if="image && activeTab === 'analysis'" class="care-action-dock" aria-label="Image review actions"><div><strong>{{ emergencySeen ? 'Do not wait for an AI result' : pending ? 'Running the local model' : path.label + ' image ready' }}</strong><span>{{ emergencySeen ? 'An urgent concern was reported.' : result ? 'Computed findings are available in this case.' : !props.user ? 'Sign in before sending an image for processing.' : !confirmed || !acknowledged || !consent ? 'Review the input and processing permissions.' : 'Prepared for the installed local model.' }}</span></div><button class="care-primary" :disabled="pending || preparing || checking" @click="dockAction">{{ emergencySeen ? 'See urgent guidance' : !props.user ? 'Sign in to continue' : !confirmed || !acknowledged || !consent ? 'Review permissions' : result ? 'Re-run this image' : 'Analyze this image' }}<AppIcon name="arrowRight" :size="19"/></button></div>
  </section>
</template>
