<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppIcon from '../components/AppIcon.vue'
import { aiApi } from '../services/aiApi'
import { ACCEPTED_TYPES, MAX_FILE_BYTES, acceptResult, blankHistory, emptyStatus, makeThumbnail, modalities, parseStatus, pathways, preferredModality, readResearchImage, researchRecord } from './model'
import type { CancerModality, CancerResult, CancerTrack, ResearchImage } from './model'
import CancerBodyMap from './CancerBodyMap.vue'
import CancerKnowledge from './CancerKnowledge.vue'
import CancerCarePlan from './CancerCarePlan.vue'
import CancerResultCard from './CancerResultCard.vue'
import { blankConcerns, cancerTopics, hasEmergency, knowledgeVersion, reviewPlan } from './knowledge'
import { compositeImage, printReport, reportHtml } from './report'
import { reportsApi } from './reportsApi'
import './cancer-care.css'

const props = defineProps<{ user: { id: number } | null; twinSubject?: string }>()
const emit = defineEmits<{ signIn: []; openTwin: []; saved: [] }>()
const selected = ref<CancerTrack>('skin'), modality = ref<CancerModality>('dermoscopy')
const subject = ref(props.twinSubject || 'CASE-' + crypto.randomUUID().slice(0, 8).toUpperCase()), history = ref(blankHistory())
const activeTab = ref<'analysis' | 'knowledge' | 'plan'>('analysis'), planTopic = ref('skin'), knowledgeTopic = ref<string | undefined>()
const concerns = ref(blankConcerns()), emergencySeen = ref(false), exampleSource = ref('')
const currentPlan = computed(() => reviewPlan(planTopic.value, concerns.value, emergencySeen.value))
const registry = ref(emptyStatus()), checking = ref(false), preparing = ref(false), pending = ref(false)
const image = ref<ResearchImage | null>(null), result = ref<CancerResult | null>(null)
const error = ref(''), notice = ref(''), consent = ref(false), confirmed = ref(false), acknowledged = ref(false)
const dragActive = ref(false), elapsed = ref(0), saving = ref(false), savedId = ref(''), exporting = ref(false)
const path = computed(() => pathways.find(item => item.id === selected.value)!)
const selectedModels = computed(() => registry.value.pathways.find(item => item.track === selected.value)!.models)
const model = computed(() => selectedModels.value.find(item => item.modality === modality.value)!)
const installedCount = computed(() => registry.value.pathways.flatMap(item => item.models).filter(item => item.configured).length)
const readyByTrack = computed(() => Object.fromEntries(registry.value.pathways.map(item => [item.track, item.models.some(entry => entry.configured)])) as Record<CancerTrack, boolean>)
const linked = computed(() => !!props.twinSubject && subject.value === props.twinSubject)
const subjectValid = computed(() => /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(subject.value))
const permissions = computed(() => consent.value && confirmed.value && acknowledged.value)
const canRun = computed(() => !!props.user && subjectValid.value && !!image.value && registry.value.available && model.value.configured && permissions.value && !emergencySeen.value && !pending.value && !preparing.value && !checking.value)
const step = computed(() => result.value ? 3 : image.value ? 2 : 1)
const stageText = computed(() => elapsed.value < 2 ? 'Checking the image…' : elapsed.value < 5 ? 'Running the ' + path.value.label.toLowerCase() + ' model…' : 'Building the heatmap and report…')
const runHint = computed(() => emergencySeen.value ? 'Image analysis is paused because an urgent symptom was reported.'
  : !model.value.configured ? (checking.value ? 'Checking the local models…' : 'No model is installed for this input type.')
  : !props.user ? 'Sign in to run the model. Your image is only processed after you confirm below.'
  : !image.value ? 'Add an image to continue.'
  : !permissions.value ? 'Tick the three confirmations to continue.' : 'Ready. The image is analysed locally and is not stored.')
let generation = 0, request: AbortController | null = null, statusRequest: AbortController | null = null, timer: ReturnType<typeof setInterval> | undefined

function invalidate() {
  generation++; request?.abort(); request = null; clearInterval(timer)
  result.value = null; pending.value = false; preparing.value = false; error.value = ''; savedId.value = ''
}
function clearImage() { invalidate(); image.value = null; consent.value = false; confirmed.value = false; acknowledged.value = false; exampleSource.value = '' }
function clearCase() { clearImage(); history.value = blankHistory(); concerns.value = blankConcerns(); emergencySeen.value = false; notice.value = '' }
watch(selected, () => { clearImage(); modality.value = preferredModality(registry.value, selected.value); planTopic.value = selected.value })
watch(modality, clearImage)
watch(subject, () => { invalidate() })
watch(() => props.twinSubject, (value, previous) => { if (!subject.value || subject.value === previous) subject.value = value || '' })
watch([consent, confirmed, acknowledged], values => { if (pending.value && values.some(value => !value)) invalidate() })
watch(concerns, value => { if (hasEmergency(value)) { emergencySeen.value = true; if (pending.value) invalidate() } }, { deep: true, flush: 'sync' })

function selectTrack(track: CancerTrack) { selected.value = track; planTopic.value = track; activeTab.value = 'analysis' }
function openPlan(topic = selected.value as string) { planTopic.value = topic; activeTab.value = 'plan' }
async function openGuide(topicId: string) { knowledgeTopic.value = undefined; activeTab.value = 'knowledge'; await nextTick(); knowledgeTopic.value = topicId }
async function editCase() { activeTab.value = 'analysis'; await nextTick(); const details = document.getElementById('cw-case-details') as HTMLDetailsElement | null; if (details) { details.open = true; details.scrollIntoView({ behavior: 'smooth', block: 'center' }) } }
async function moveSection(direction: number) {
  const tabs = ['analysis', 'knowledge', 'plan'] as const
  activeTab.value = tabs[(tabs.indexOf(activeTab.value) + direction + tabs.length) % tabs.length]!
  await nextTick(); document.getElementById('care-' + activeTab.value + '-tab')?.focus()
}
function chooseFile() { document.getElementById('cw-file-input')?.click() }

async function loadExample(kind: 'benign' | 'malignant') {
  selected.value = 'oral'; activeTab.value = 'analysis'; await nextTick()
  const revision = generation
  try {
    const response = await fetch('/cancer-examples/oral-' + kind + '-reference.png', { cache: 'no-store' })
    if (!response.ok) throw new Error('The public example image could not be loaded.')
    const blob = await response.blob()
    if (revision !== generation) return
    await prepareFile(new File([blob], 'public-oral-' + kind + '.png', { type: 'image/png' }))
    if (image.value && selected.value === 'oral') exampleSource.value = 'Public oral reference image (source-labelled ' + kind + ' lesion): Chandrashekar et al., Mendeley Oral Images Dataset v2, CC BY 4.0.'
  } catch (cause) { if (revision === generation) error.value = cause instanceof Error ? cause.message : 'The example image could not be loaded.' }
}

async function checkModels() {
  statusRequest?.abort(); statusRequest = new AbortController()
  const active = statusRequest
  checking.value = true
  try {
    const value = await aiApi.get<unknown>('/cancer/status', active.signal)
    if (!active.signal.aborted) {
      registry.value = parseStatus(value)
      if (!image.value) modality.value = preferredModality(registry.value, selected.value, modality.value)
    }
  } catch {
    if (!active.signal.aborted) { registry.value = emptyStatus(); notice.value = 'The local model service could not be reached. Start the AI service, then use “Check again”.' }
  } finally { if (statusRequest === active) checking.value = false }
}
onMounted(checkModels)
onBeforeUnmount(() => { invalidate(); statusRequest?.abort() })

async function prepareFile(file: File) {
  clearImage(); preparing.value = true; dragActive.value = false
  const revision = generation
  try { const prepared = await readResearchImage(file); if (revision === generation) image.value = prepared }
  catch (cause) { if (revision === generation) error.value = cause instanceof Error ? cause.message : 'The image could not be prepared.' }
  finally { if (revision === generation) preparing.value = false }
}
function attach(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]
  input.value = ''; if (file) void prepareFile(file)
}
function dropFile(event: DragEvent) { dragActive.value = false; const file = event.dataTransfer?.files[0]; if (file && !preparing.value) void prepareFile(file) }
function pasteFile(event: ClipboardEvent) { const file = event.clipboardData?.files[0]; if (file) { event.preventDefault(); void prepareFile(file) } }

async function analyze() {
  if (!props.user) { emit('signIn'); return }
  if (!canRun.value || !image.value) return
  invalidate(); pending.value = true; request = new AbortController(); elapsed.value = 0
  timer = setInterval(() => { elapsed.value++ }, 1000)
  const active = request, revision = generation, currentImage = image.value
  const track = selected.value, inputModality = modality.value, expectedModel = { ...model.value }
  try {
    const value = await aiApi.post<unknown>('/cancer/analyze', {
      track, modality: inputModality, image_data_url: currentImage.dataUrl,
      consent_local: true, modality_confirmed: true, research_only_acknowledged: true, explain: true,
    }, active.signal, 120_000)
    if (revision === generation && !active.signal.aborted) {
      result.value = acceptResult(value, track, inputModality, currentImage.sha256, expectedModel)
      await nextTick(); document.getElementById('cw-step-result')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      document.getElementById('cw-result-title')?.focus({ preventScroll: true })
    }
  } catch (cause) {
    if (revision === generation && !active.signal.aborted) error.value = cause instanceof Error ? cause.message : 'No result was generated. Please try again.'
  } finally { if (revision === generation) { pending.value = false; request = null; clearInterval(timer) } }
}
function cancelAnalysis() { invalidate(); notice.value = 'Analysis cancelled. Nothing was saved.' }

async function saveReport(note: string) {
  if (!result.value || !image.value || saving.value) return
  saving.value = true; error.value = ''
  try {
    const saved = await reportsApi.save(result.value.input_sha256, await makeThumbnail(image.value), note)
    savedId.value = saved.id; emit('saved')
  } catch (cause) { error.value = cause instanceof Error ? cause.message : 'The report could not be saved.' }
  finally { saving.value = false }
}
async function exportPdf() {
  if (!result.value || !image.value || exporting.value) return
  exporting.value = true
  try {
    const [plain, overlay] = await Promise.all([compositeImage(image.value.dataUrl, null), result.value.heatmap ? compositeImage(image.value.dataUrl, result.value.heatmap) : Promise.resolve(null)])
    printReport(reportHtml({ result: result.value, imageDataUrl: plain, heatmapDataUrl: overlay, createdAt: new Date().toISOString() }))
  } catch { error.value = 'The PDF report could not be prepared in this browser.' }
  finally { exporting.value = false }
}
function downloadJson() {
  try {
    const record = { ...researchRecord(subject.value, props.twinSubject, selected.value, modality.value, history.value, image.value, result.value),
      knowledge_version: knowledgeVersion, review_guide: currentPlan.value,
      reported_concerns: { ...concerns.value, absence_not_established_for_unchecked_items: true, emergency_report_retained: emergencySeen.value },
      public_example_attribution: exampleSource.value || null }
    const url = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2)], { type: 'application/json' }))
    const link = document.createElement('a'); link.href = url; link.download = 'humantwin-cancer-' + selected.value + '-' + subject.value + '.json'; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    notice.value = 'Research data downloaded (notes, fingerprints and model output; no image pixels).'
  } catch (cause) { error.value = cause instanceof Error ? cause.message : 'The record could not be exported.' }
}
function statusLabel(track: CancerTrack) { return checking.value ? 'Checking…' : readyByTrack.value[track] ? 'Model ready' : registry.value.available ? 'No model installed' : 'Service offline' }
function acceptedFor(track: CancerTrack) {
  const models = registry.value.pathways.find(item => item.track === track)?.models ?? []
  const ready = models.find(item => item.configured)
  return modalities[ready?.modality ?? pathways.find(item => item.id === track)!.modalities[0]!].accepts
}
</script>

<template>
  <section class="cancer-workspace" aria-label="Cancer research workspace">
    <div class="cw-intro">
      <p class="cw-lead">A clearer picture, <em>a better next step.</em></p>
      <ul class="cw-facts" aria-label="About this workspace">
        <li><AppIcon name="scan" :size="16"/>{{ installedCount }} local image models</li>
        <li><AppIcon name="book" :size="16"/>{{ cancerTopics.length }} cancer guides</li>
        <li><AppIcon name="shield" :size="16"/>Permission before processing</li>
      </ul>
    </div>

    <div class="care-section-nav" role="tablist" aria-label="Cancer workspace sections" @keydown.right.prevent="moveSection(1)" @keydown.left.prevent="moveSection(-1)">
      <button id="care-analysis-tab" role="tab" :aria-selected="activeTab === 'analysis'" :tabindex="activeTab === 'analysis' ? 0 : -1" aria-controls="care-analysis" :class="{ active: activeTab === 'analysis' }" @click="activeTab = 'analysis'"><AppIcon name="scan" :size="20"/>Analyze an image</button>
      <button id="care-knowledge-tab" role="tab" :aria-selected="activeTab === 'knowledge'" :tabindex="activeTab === 'knowledge' ? 0 : -1" aria-controls="care-knowledge" :class="{ active: activeTab === 'knowledge' }" @click="activeTab = 'knowledge'"><AppIcon name="book" :size="20"/>Cancer knowledge</button>
      <button id="care-plan-tab" role="tab" :aria-selected="activeTab === 'plan'" :tabindex="activeTab === 'plan' ? 0 : -1" aria-controls="care-plan" :class="{ active: activeTab === 'plan' }" @click="openPlan()"><AppIcon name="clipboard" :size="20"/>Care &amp; next steps</button>
    </div>

    <div v-if="emergencySeen" class="care-emergency" role="alert"><AppIcon name="error" :size="24"/><div><h3>Seek emergency care now</h3><p>You reported an urgent warning sign. Do not wait for an image result. Contact your local emergency service or go to the nearest emergency department.</p><small>This guidance stays visible until you clear this case.</small><button class="cw-link-button" @click="openPlan()">View the review guidance<AppIcon name="arrowRight" :size="16"/></button></div></div>
    <div v-if="error" class="cancer-error" role="alert"><AppIcon name="error" :size="20"/><span>{{ error }}</span><button class="cw-link-button" @click="error = ''">Dismiss</button></div>
    <p v-if="notice" class="cancer-notice" role="status"><span>{{ notice }}</span><button v-if="!registry.available" class="cw-link-button" :disabled="checking" @click="notice = ''; checkModels()">Check again</button></p>

    <section id="care-analysis" v-show="activeTab === 'analysis'" role="tabpanel" aria-labelledby="care-analysis-tab">
      <ol class="cw-stepper" aria-label="Progress">
        <li :class="{ current: step === 1, done: step > 1 }" :aria-current="step === 1 ? 'step' : undefined"><span>1</span>Choose area</li>
        <li :class="{ current: step === 2, done: step > 2 }" :aria-current="step === 2 ? 'step' : undefined"><span>2</span>Upload image</li>
        <li :class="{ current: step === 3 }" :aria-current="step === 3 ? 'step' : undefined"><span>3</span>Review result</li>
      </ol>

      <div class="cw-flow">
        <section class="cw-card cw-step-area" aria-labelledby="cw-area-title">
          <header class="cw-card-head"><span class="cw-step-number" aria-hidden="true">1</span><h2 id="cw-area-title">Choose the body area</h2></header>
          <div class="cw-area-layout">
            <CancerBodyMap :selected="selected" :ready="readyByTrack" @select="selectTrack"/>
            <div class="cw-area-cards" role="radiogroup" aria-labelledby="cw-area-title">
              <button v-for="item in pathways" :key="item.id" type="button" role="radio" :aria-checked="selected === item.id" :tabindex="selected === item.id ? 0 : -1" class="cancer-pathway cw-area-card" :class="{ selected: selected === item.id }" @click="selectTrack(item.id)"
                      @keydown.down.prevent="selectTrack(pathways[(pathways.indexOf(item) + 1) % 4]!.id)" @keydown.up.prevent="selectTrack(pathways[(pathways.indexOf(item) + 3) % 4]!.id)">
                <span class="cw-area-icon" aria-hidden="true"><AppIcon :name="item.icon" :size="22"/></span>
                <span class="cw-area-text"><span class="cw-area-title"><strong>{{ item.label }}</strong><span class="cw-status" :class="{ ready: readyByTrack[item.id] }"><i aria-hidden="true"></i>{{ statusLabel(item.id) }}</span></span><span>{{ acceptedFor(item.id) }}</span><small>{{ item.modelName }}</small></span>
              </button>
            </div>
          </div>
        </section>

        <section class="cw-card cw-step-upload" aria-labelledby="cw-upload-title" @paste="pasteFile">
          <header class="cw-card-head"><span class="cw-step-number" aria-hidden="true">2</span><h2 id="cw-upload-title">Upload {{ path.id === 'oral' ? 'an' : 'a' }} {{ path.label.toLowerCase() }} image</h2></header>
          <label v-if="selectedModels.filter(item => item.configured).length > 1" class="cw-field">Image type
            <select v-model="modality"><option v-for="id in path.modalities" :key="id" :value="id" :disabled="!selectedModels.find(m => m.modality === id)?.configured">{{ modalities[id].label }}{{ selectedModels.find(m => m.modality === id)?.configured ? '' : ' (no model installed)' }}</option></select>
          </label>
          <div v-if="!image" class="cw-dropzone" :class="{ dragging: dragActive, busy: preparing }" @dragover.prevent="dragActive = true" @dragleave.prevent="dragActive = false" @drop.prevent="dropFile">
            <span class="cw-drop-icon" aria-hidden="true"><AppIcon name="arrowDown" :size="28"/></span>
            <p class="cw-drop-title">{{ preparing ? 'Preparing your image…' : 'Drag and drop an image here' }}</p>
            <p class="cw-drop-accepts">Accepted: <strong>{{ modalities[modality].accepts }}</strong></p>
            <button type="button" class="cw-button primary" :disabled="preparing" @click="chooseFile"><AppIcon name="plus" :size="18"/>Choose a file</button>
            <input id="cw-file-input" class="sr-only" type="file" :accept="ACCEPTED_TYPES.join(',')" aria-label="Choose an image file" tabindex="-1" @change="attach"/>
            <p class="cw-help">JPEG or PNG, up to {{ MAX_FILE_BYTES / 1024 / 1024 }} MB. You can also paste an image. Remove names and other identifying details first.</p>
          </div>
          <div v-else class="cw-preview">
            <img :src="image.dataUrl" :alt="'Preview of the image to analyse for the ' + path.label.toLowerCase() + ' model'"/>
            <div class="cw-preview-info">
              <strong>{{ image.name || 'Prepared image' }}</strong>
              <span>{{ image.width }} × {{ image.height }} px{{ image.resized ? ' (resized from ' + image.originalWidth + ' × ' + image.originalHeight + ')' : '' }}</span>
              <div class="cw-preview-actions"><button type="button" class="cw-link-button" :disabled="pending" @click="chooseFile">Replace</button><button type="button" class="cw-link-button" :disabled="pending" @click="clearImage">Remove</button></div>
              <input id="cw-file-input" class="sr-only" type="file" :accept="ACCEPTED_TYPES.join(',')" aria-label="Choose an image file" tabindex="-1" @change="attach"/>
            </div>
          </div>
          <p v-if="exampleSource" class="cw-attribution">{{ exampleSource }} <a href="https://data.mendeley.com/datasets/mhjyrn35p4/2" target="_blank" rel="noopener noreferrer">Source<span class="sr-only"> (opens in a new tab)</span></a></p>

          <fieldset class="cw-confirm" :disabled="pending">
            <legend>Before analysing</legend>
            <label class="cw-check"><input v-model="confirmed" type="checkbox"/>This is a {{ modalities[modality].label.toLowerCase() }}, the type this model expects.</label>
            <label class="cw-check"><input v-model="acknowledged" type="checkbox"/>I understand this is a research tool and cannot diagnose cancer.</label>
            <label class="cw-check"><input v-model="consent" type="checkbox"/>I allow the local research model to process this image (it is not stored).</label>
          </fieldset>

          <div v-if="pending" class="cw-progress" role="status" aria-live="polite">
            <div class="cw-progress-bar" aria-hidden="true"><i></i></div>
            <p><strong>{{ stageText }}</strong> {{ elapsed }} s</p>
            <button type="button" class="cw-link-button" @click="cancelAnalysis">Cancel</button>
          </div>
          <div v-else class="cw-run">
            <button type="button" class="cw-button primary large" :disabled="!!props.user && !canRun" @click="analyze"><AppIcon name="scan" :size="20"/>{{ !props.user ? 'Sign in to analyse' : result ? 'Analyse again' : 'Analyse image' }}</button>
            <p class="cw-help" aria-live="polite">{{ runHint }}</p>
          </div>
          <p class="cw-example">No image at hand? <button type="button" class="cw-link-button" :disabled="preparing || pending" @click="loadExample('benign')">Try a public oral example</button> or <button type="button" class="cw-link-button" :disabled="preparing || pending" @click="loadExample('malignant')">a second one</button>.</p>
        </section>
      </div>

      <section id="cw-step-result" class="cw-step-result" aria-labelledby="cw-step-result-title" aria-live="polite">
        <header class="cw-card-head"><span class="cw-step-number" aria-hidden="true">3</span><h2 id="cw-step-result-title">Review the result</h2></header>
        <CancerResultCard v-if="result && image" :result="result" :image-src="image.dataUrl" mode="live" :signed-in="!!props.user" :saving="saving" :saved="!!savedId" :exporting="exporting"
                          @guide="openGuide" @save="saveReport" @pdf="exportPdf" @json="downloadJson"/>
        <div v-else class="cw-empty">
          <span class="cw-empty-icon" aria-hidden="true"><AppIcon :name="pending ? 'activity' : 'clipboard'" :size="28"/></span>
          <div><p><strong>{{ pending ? 'Your result is being prepared.' : 'Your report will appear here.' }}</strong></p>
          <p class="cw-help">You will see the finding, the model’s confidence, a heatmap, what it means in plain language and a suggested next step. A model result alone cannot diagnose or rule out cancer.</p></div>
        </div>
      </section>

      <details id="cw-case-details" class="cw-card cw-case">
        <summary><span><strong>Research case details (optional)</strong><small>Case code, symptoms for a reviewer and urgent warning signs</small></span><AppIcon name="chevronDown" :size="20"/></summary>
        <div class="cw-case-grid">
          <label class="cw-field">Coded study subject ID<input v-model="subject" maxlength="64" autocomplete="off" spellcheck="false"/><small>A generated case code; no name is needed.</small></label>
          <div class="cancer-twin-link"><span><AppIcon name="activity" :size="18"/>{{ linked ? 'Linked by code to the open twin: ' + props.twinSubject : props.twinSubject ? 'Open twin: ' + props.twinSubject + '. Use the same code to link this case.' : 'You can link this case to a patient twin with the same code.' }}</span><button type="button" class="cw-link-button" @click="emit('openTwin')">Patient twin<AppIcon name="arrowRight" :size="16"/></button></div>
          <label class="cw-field">Symptoms or changes<textarea v-model="history.symptoms" rows="3" maxlength="2000" placeholder="What changed, and where? Leave out names and contact details."></textarea></label>
          <label class="cw-field">When first noticed<input v-model="history.duration" maxlength="120" placeholder="For example: three weeks ago"/></label>
          <label class="cw-field">Family history of cancer<select v-model="history.family_history"><option value="unknown">Not recorded</option><option value="yes">Yes, reported</option><option value="no">No, reported</option></select></label>
          <label class="cw-field">Tobacco use<select v-model="history.tobacco_exposure"><option value="unknown">Not recorded</option><option value="yes">Yes, reported</option><option value="no">No, reported</option></select></label>
        </div>
        <fieldset class="cw-urgent">
          <legend>Any urgent symptoms right now?</legend>
          <label class="cw-check"><input v-model="concerns.severe_breathing" type="checkbox"/>Severe difficulty breathing</label>
          <label class="cw-check"><input v-model="concerns.uncontrolled_bleeding" type="checkbox"/>Heavy bleeding that is not stopping</label>
          <label class="cw-check"><input v-model="concerns.persistent_change" type="checkbox"/>A new, persistent or unexplained change</label>
          <label class="cw-field">Coughing up blood<select v-model="concerns.coughing_blood"><option value="not-recorded">Not recorded</option><option value="small-amount">A few spots or streaks</option><option value="more-than-streaks">More than a few spots or streaks</option></select></label>
          <p class="cw-help">The image model does not read these notes. If someone seems seriously ill, get medical help instead of waiting for AI.</p>
        </fieldset>
        <div class="cw-case-actions"><button type="button" class="cw-button ghost" :disabled="!subjectValid" @click="downloadJson"><AppIcon name="download" :size="18"/>Download research data (JSON)</button><button type="button" class="cw-link-button" @click="clearCase"><AppIcon name="reset" :size="16"/>Clear case</button></div>
      </details>
    </section>

    <section id="care-knowledge" v-if="activeTab === 'knowledge'" role="tabpanel" aria-labelledby="care-knowledge-tab"><CancerKnowledge :signed-in="!!props.user" :topic="knowledgeTopic" @analyze="selectTrack" @plan="openPlan" @sign-in="emit('signIn')"/></section>
    <section id="care-plan" v-if="activeTab === 'plan'" role="tabpanel" aria-labelledby="care-plan-tab"><CancerCarePlan :topic-id="planTopic" :concerns="concerns" :prior-emergency="emergencySeen" :history="history" :result="result" :subject="subject" @edit="editCase"/></section>

    <p class="care-footnote"><AppIcon name="info" :size="18"/><span>HumanTwin combines experimental image models with a curated reference library. It does not replace an examination, pathology, a confirmed diagnosis or a treatment decision. <a href="https://www.cancer.gov/about-cancer/diagnosis-staging/diagnosis" target="_blank" rel="noopener noreferrer">How cancer is diagnosed (NCI)<span class="sr-only"> (opens in a new tab)</span></a></span></p>
  </section>
</template>
