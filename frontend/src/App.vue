<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, provide, reactive, ref, watch } from 'vue'
import AppIcon from './components/AppIcon.vue'
import AppSidebar from './components/AppSidebar.vue'
import BodyViewer from './components/BodyViewer.vue'
import SymptomAssistant from './components/SymptomAssistant.vue'
import AiSymptomAssistant from './components/AiSymptomAssistant.vue'
import AiAssessmentSummary from './components/AiAssessmentSummary.vue'
import AiHistoryView from './components/AiHistoryView.vue'
import { useAiAssessment } from './composables/useAiAssessment'
import type { BodySide } from './types/ai'
import type { PatientSide } from './data/bodyParts'
import AssessmentSummary from './components/AssessmentSummary.vue'
import OverviewView from './components/OverviewView.vue'
import HistoryView from './components/HistoryView.vue'
import SettingsView from './components/SettingsView.vue'
import AppDialog from './components/AppDialog.vue'
import { useAssessment } from './composables/useAssessment'
import { assessmentRepository } from './services/localAssessmentRepository'
import { getRegion } from './data/regions'
import type { Assessment, DemoSettings, Navigation, RegionId } from './types'
import { createEyeContext,eyeContextKey } from './eye/context'
import EyeSummary from './eye/EyeSummary.vue'
import type { DentalMode } from './dental/model'
import type { TwinDocument } from './twin/model'

const dentalHashes = ['#dental', '#orthodontics', '#dental-data']
const page = ref<Navigation>(dentalHashes.includes(window.location.hash) ? 'Dental studio' : window.location.hash === '#twin' ? 'Patient twin' : 'Body explorer')
const DentalWorkspace = defineAsyncComponent(() => import('./dental/DentalWorkspace.vue'))
const dentalMode = ref<DentalMode>(window.location.hash === '#orthodontics' ? 'braces' : window.location.hash === '#dental-data' ? 'research' : 'pain')
const dentalOpened = ref(page.value === 'Dental studio'), dentalSessionKey = ref(0)
watch(page, value => { if (value === 'Dental studio') dentalOpened.value = true })
function openDental(mode: 'pain' | 'braces' = 'pain') { dentalMode.value = mode; navigate('Dental studio') }
function dentalModeChanged(mode: DentalMode) { dentalMode.value = mode; if (page.value === 'Dental studio') window.history.replaceState(null, '', dentalHash()) }
function dentalHash() { return dentalMode.value === 'braces' ? '#orthodontics' : dentalMode.value === 'research' ? '#dental-data' : '#dental' }
function syncDentalHash() { const hash = window.location.hash; if (dentalHashes.includes(hash)) { dentalMode.value = hash === '#orthodontics' ? 'braces' : hash === '#dental-data' ? 'research' : 'pain'; page.value = 'Dental studio' } }
onMounted(() => window.addEventListener('hashchange', syncDentalHash))
onBeforeUnmount(() => window.removeEventListener('hashchange', syncDentalHash))
const EyeWorkspace = defineAsyncComponent(() => import('./eye/EyeWorkspace.vue'))
const PatientTwinWorkspace = defineAsyncComponent(() => import('./twin/PatientTwinWorkspace.vue'))
const patientTwin = ref<TwinDocument | null>(null)
const twinInitialPart = ref<RegionId | null>(null)
const eyeOpen = ref(window.location.hash === '#eye')
const mobileNav = ref(false)
const profileOpen = ref(false)
const settings = reactive(assessmentRepository.loadSettings())
const flow = useAssessment(settings)
const eye = createEyeContext()
provide(eyeContextKey,eye)
const ai = useAiAssessment()
watch(() => ai.state.user?.id, (value, previous) => { if (value !== previous) { patientTwin.value = null; dentalSessionKey.value++ } })
const demoConsent = ref(false)
const chatMode = ref<'ai' | 'demo'>('demo')
try { if (sessionStorage.getItem('humantwin.chatMode') === 'ai') chatMode.value = 'ai' } catch {}
function setMode(value: 'ai' | 'demo') { if (value === chatMode.value) return; ai.reset(region.value); chatMode.value = value; try { sessionStorage.setItem('humantwin.chatMode', value) } catch {} }
onMounted(ai.init)
onBeforeUnmount(ai.dispose)
const patientSide = ref<PatientSide>('left')
watch(patientSide,value=>{eye.session.model_side=value})
watch(()=>ai.state.user?.id,(value,previous)=>{if(previous!==undefined&&value!==previous){eye.reset();eye.acknowledged.value=false}})
function changeSide(value: BodySide) { if (value === 'left' || value === 'right') patientSide.value = value; ai.reset(region.value, value); ai.state.notice = 'Changing the side starts a fresh assessment.' }
function selectSide(value: PatientSide) { patientSide.value = value; flow.setSide(value); if (chatMode.value === 'ai') changeSide(value) }
async function openAiRecord(id: string) { if (await ai.openSaved(id)) { flow.selectRegion(ai.state.region); navigate('Body explorer') } }
const { region, messages, answers, pain, step, pending, error, options, complete, saved, canRetry } = flow
const assessments = ref<Assessment[]>([])
const storageError = ref('')
try { assessments.value = assessmentRepository.list() } catch (e) { storageError.value = e instanceof Error ? e.message : 'Local storage is unavailable. You can still use the demo and export your summary.' }
const dialog = ref<'help' | 'clear' | 'assessment' | null>(null)
const inspected = ref<Assessment | null>(null)
const toast = ref('')
let toastTimer: ReturnType<typeof setTimeout>
function notify(message: string) { toast.value = message; clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.value = '', 4500) }
onBeforeUnmount(() => clearTimeout(toastTimer))
const title = computed(() => ({ Overview: 'Your body. Better understood.', 'Body explorer': 'Where does it hurt?', 'Dental studio': 'Your smile. In detail.', 'Patient twin': 'One subject. An evolving model.', Assessments: 'Your assessments', History: 'Assessment history', Settings: 'Make yourself comfortable' }[page.value]))
const subtitle = computed(() => ({ Overview: 'A simple way to explore your digital twin.', 'Body explorer': 'Select an area to explore anatomy or start a focused assessment.', 'Dental studio': 'Interactive dental anatomy, tooth-specific pain intake, and an orthodontic research workspace.', 'Patient twin': 'Time-stamped observations, a personal reference, and transparent research projections.', Assessments: chatMode.value === 'ai' ? 'Conversations saved to your account with your consent.' : 'Your saved demonstration summaries.', History: chatMode.value === 'ai' ? 'Your consented account records.' : 'History saved in this browser.', Settings: 'Preferences, storage controls, and scripted demo tools.' }[page.value]))
function navigate(value: Navigation) { if (value !== 'Body explorer') twinInitialPart.value = null; page.value = value; window.scrollTo(0, 0); mobileNav.value = false; profileOpen.value = false; window.history.replaceState(null, '', window.location.pathname + window.location.search + (value === 'Patient twin' ? '#twin' : value === 'Dental studio' ? dentalHash() : '')) }
function start(id?: RegionId) { eye.reset(); eyeOpen.value = false; flow.selectRegion(id ?? null); ai.reset(id ?? null); demoConsent.value = false; navigate('Body explorer') }
function select(id: RegionId, side?: PatientSide) {
  eyeOpen.value = false
  if (side) patientSide.value = side
  if (region.value !== id) { flow.selectRegion(id, side); ai.reset(id, side ?? 'unknown'); demoConsent.value = false }
  else if (side) { flow.setSide(side); if (chatMode.value === 'ai' && ai.state.side !== side) ai.reset(id, side) }
}
function exploreTwin(id: RegionId, side?: PatientSide) { twinInitialPart.value = id; select(id, side); navigate('Body explorer') }
function saveAssessment() {
  const item = flow.snapshot()
  if (!item || pending.value || !demoConsent.value) return
  try {
    if (settings.rememberHistory) {
      assessmentRepository.save(item)
      assessments.value = [item, ...assessments.value.filter(a => a.id !== item.id)].slice(0, 50)
    } else assessments.value = [item, ...assessments.value.filter(a => a.id !== item.id)].slice(0, 50)
    saved.value = true
    notify(settings.rememberHistory ? 'Assessment saved in this browser.' : 'Assessment saved for this session.')
  } catch { storageError.value = 'Your assessment could not be saved. Browser storage may be full or unavailable. You can export the summary as JSON.' }
}
function exportAssessment(item = flow.snapshot()) {
  if (!item || pending.value) return
  const blob = new Blob([JSON.stringify({ demonstration: true, disclaimer: 'Scripted demonstration. Not a medical diagnosis.', ...item }, null, 2)], { type: 'application/json' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `humantwin-${item.region}-${item.createdAt.slice(0, 10)}.json`
  link.click()
  setTimeout(() => URL.revokeObjectURL(link.href), 1000)
  notify('Demo summary exported.')
}
function removeAssessment(id: string) {
  try { assessmentRepository.remove(id); assessments.value = assessments.value.filter(a => a.id !== id); notify('Assessment deleted.'); if (flow.snapshot()?.id === id) saved.value = false }
  catch { storageError.value = 'The assessment could not be removed from browser storage. Try clearing local history in Settings.' }
}
function clearHistory() {
  try { assessmentRepository.clear(); assessments.value = []; storageError.value = ''; saved.value = false; dialog.value = null; notify('Local assessment history cleared.') }
  catch { storageError.value = 'Browser storage is unavailable. Enable local storage to clear persisted history.'; dialog.value = null }
}
function updateSettings(key: keyof DemoSettings, value: boolean) {
  settings[key] = value
  try { assessmentRepository.saveSettings(settings) } catch { notify('Preferences apply to this session. Browser storage is unavailable.') }
}
function inspect(item: Assessment) { inspected.value = item; dialog.value = 'assessment' }
watch(pain, () => saved.value = false)
</script>
<template>
  <div class="app-shell" :class="{ 'reduced-motion': settings.reducedMotion }" @keydown.esc="profileOpen = false; mobileNav = false">
    <a class="skip-link" href="#main-content">Skip to main content</a>
    <header class="topbar"><div class="brand-section"><button class="mobile-menu icon-button" aria-label="Open navigation" :aria-expanded="mobileNav" @click="mobileNav = !mobileNav"><AppIcon name="menu"/></button><a href="#" class="brand" aria-label="HumanTwin overview" @click.prevent="navigate('Overview')"><svg class="brand-mark" viewBox="0 0 40 44" aria-hidden="true"><circle cx="20" cy="7" r="5.5" fill="#3bc0c6"/><path d="M7 16Q20 32 33 16M12 39V33Q20 23 28 33V39" fill="none" stroke="#3bc0c6" stroke-width="6" stroke-linecap="round"/><circle cx="5" cy="31" r="2.5" fill="#3bc0c6"/></svg><span>Human<span class="brand-twin">Twin</span></span></a></div><span class="header-divider"></span><div class="product-title">Symptom explorer</div><span class="demo-badge"><i></i>{{ page === 'Dental studio' ? 'Oral research' : page === 'Patient twin' ? 'Twin research' : chatMode === 'ai' ? 'AI prototype' : region === 'eyes' && page === 'Body explorer' ? 'Eye prototype' : 'Scripted demo' }}</span><div class="header-actions"><button class="help-button" aria-label="Help and demo information" @click="dialog = 'help'"><AppIcon name="help" :size="21"/></button><div class="profile-menu"><button class="profile-button" :aria-expanded="profileOpen" aria-controls="profile-dropdown" @click="profileOpen = !profileOpen"><span class="profile-avatar"><AppIcon name="user" :size="19"/></span><span>{{ chatMode === 'ai' && ai.state.user ? 'Member' : 'Guest' }}</span><AppIcon name="chevronDown" :size="15"/></button><div v-if="profileOpen" id="profile-dropdown" class="profile-dropdown"><strong>Guest workspace</strong><p>Local demonstration session</p><button @click="navigate('Settings')"><AppIcon name="settings" :size="16"/>Preferences</button><button @click="dialog = 'help'; profileOpen = false"><AppIcon name="info" :size="16"/>About this demo</button></div></div></div></header>
    <AppSidebar :active="page" :open="mobileNav" :demo="chatMode === 'demo'" @navigate="navigate" @close="mobileNav = false"/>
    <main id="main-content" class="main-content" tabindex="-1">
      <div class="page-heading"><div><div class="breadcrumb">WORKSPACE <AppIcon name="chevronRight" :size="11"/><span>{{ page }}</span></div><h1>{{ title }}</h1><p>{{ subtitle }}</p></div><button v-if="page !== 'Settings' && page !== 'Patient twin' && page !== 'Dental studio'" class="new-assessment button-secondary" @click="start()"><AppIcon name="plus" :size="16"/>New assessment</button></div>
      <div v-if="page !== 'Patient twin' && page !== 'Dental studio'" class="ai-mode-bar"><div class="segmented" aria-label="Chat mode"><button :class="{ chosen: chatMode === 'ai' }" :aria-pressed="chatMode === 'ai'" @click="setMode('ai')">AI assistant</button><button :class="{ chosen: chatMode === 'demo' }" :aria-pressed="chatMode === 'demo'" @click="setMode('demo')">Scripted demo</button></div><span>{{ chatMode === 'ai' ? 'Clinical review required before patient use' : region === 'eyes' ? 'Adaptive eye interview and learning library; clinical review pending' : 'Mock questionnaire; no AI or medical triage' }}</span></div>
      <div v-if="storageError" class="storage-error" role="alert"><AppIcon name="error" :size="19"/><p>{{ storageError }}</p><button @click="navigate('Settings')">Settings</button></div>
      <DentalWorkspace v-if="dentalOpened" v-show="page === 'Dental studio'" :key="dentalSessionKey" :initial-mode="dentalMode" :reduced-motion="settings.reducedMotion" @mode="dentalModeChanged" @close="navigate('Body explorer')"/><template v-if="page === 'Body explorer'"><EyeWorkspace v-if="eyeOpen" :side="patientSide" :reduced-motion="settings.reducedMotion" :user="ai.state.user" :auth-pending="ai.state.authPending" :auth-error="ai.state.error" @close="eyeOpen = false" @side="patientSide = $event" @authenticate="ai.authenticate"/><template v-else><button v-if="region === 'eyes'" class="eye-launch" @click="eyeOpen = true">Open detailed eye explorer · 63 structures →</button><div class="explorer-grid"><BodyViewer :initial-part="twinInitialPart" :selected="region" :side="patientSide" :reduced-motion="settings.reducedMotion" @select="select" @side="selectSide" @dental="openDental"/><AiSymptomAssistant v-if="chatMode === 'ai'" :state="ai.state" @send="ai.send" @authenticate="ai.authenticate" @logout="ai.logout" @reset="ai.reset(region)" @remove="ai.remove()" @side="changeSide" @consent="ai.state.processingConsent = $event"/><SymptomAssistant v-else @eye-details="eyeOpen = true" :region="region" :side="flow.side.value" :messages="messages" :options="options" :pain="pain" :step="step" :pending="pending" :error="error" :complete="complete" :can-retry="canRetry" @send="flow.send" @retry="flow.retry" @clear="flow.selectRegion(null)" @update:pain="pain = $event"/></div><AiAssessmentSummary v-if="chatMode === 'ai'" :state="ai.state" @save="ai.save" @consent="ai.state.storageConsent = $event"/><EyeSummary v-else-if="region === 'eyes'" :session="eye.session"/><template v-else><label v-if="complete" class="ai-consent demo-save-consent"><input v-model="demoConsent" type="checkbox"/>I consent to saving this scripted demo conversation in this browser until I delete it.</label><AssessmentSummary :consent="demoConsent" :region="region" :answers="answers" :pain="pain" :complete="complete" :saved="saved" :pending="pending" @save="saveAssessment" @export="exportAssessment()"/></template></template></template>
      <PatientTwinWorkspace :reduced-motion="settings.reducedMotion" v-else-if="page === 'Patient twin'" v-model:document="patientTwin" @explore="exploreTwin"/><OverviewView v-else-if="page === 'Overview'" :demo="chatMode === 'demo'" :saved-count="chatMode === 'ai' ? ai.state.savedChats.length : assessments.length" @start="start" @history="navigate('Assessments')" @dental="openDental"/>
      <AiHistoryView v-else-if="chatMode === 'ai' && (page === 'Assessments' || page === 'History')" :state="ai.state" @open="openAiRecord" @remove="ai.remove" @explore="navigate('Body explorer')" @refresh="ai.listSaved"/><HistoryView v-else-if="page === 'Assessments' || page === 'History'" :assessments="assessments" :timeline="page === 'History'" @start="start()" @inspect="inspect" @remove="removeAssessment"/>
      <SettingsView v-else-if="page === 'Settings'" :demo="chatMode === 'demo'" :settings="settings" :saved-count="assessments.length" @update="updateSettings" @clear="dialog = 'clear'" @explore="navigate('Body explorer')"/>
      <footer class="page-footer"><span><span class="footer-dot"></span>Intelligent Digital Twin of the Human Body</span><span>{{ page === 'Patient twin' ? 'Patient-specific research prototype' : chatMode === 'ai' ? 'AI prototype · Clinical review required' : 'Scripted demonstration' }}<i>·</i>Not a medical diagnosis</span></footer>
    </main>
    <Transition name="toast"><div v-if="toast" class="toast-message" role="status"><AppIcon name="complete" :size="19"/>{{ toast }}<button aria-label="Dismiss notification" @click="toast = ''"><AppIcon name="x" :size="15"/></button></div></Transition>
    <AppDialog :open="dialog !== null" :title="dialog === 'help' ? 'A little guidance' : dialog === 'clear' ? 'Clear local history?' : 'Your demo assessment'" @close="dialog = null">
      <template v-if="dialog === 'help'"><span class="dialog-demo-label"><AppIcon name="sparkles" :size="16"/>HUMANTWIN DEMONSTRATION</span><p v-if="chatMode === 'ai'">The AI assistant uses the Laravel API and Python service. Answers are processed by the configured AI provider only when enabled. Saving requires separate consent. Warning rules are drafts and require clinical review before patient use.</p><p v-else>Explore the body and record a simulated symptom conversation. This frontend uses local mock data and scripted responses. It does not provide medical advice or a real diagnosis.</p><ol class="help-steps"><li><strong>Choose a body area.</strong> Click the body or use the area buttons beneath it. Dental pain and Braces & bite open the dental studio.</li><li><strong>Find your view.</strong> Switch between 2D and 3D. Drag the 3D body to rotate; scroll or use + / − to zoom. Arrow keys rotate a focused 3D viewer.</li><li><strong>Describe how you feel.</strong> Choose an answer or type your own. Adjust pain from 1 to 10.</li><li><strong>Keep your summary.</strong> Finish the conversation to save it locally or export JSON. New assessment starts over.</li></ol><p class="dialog-muted">The scripted demo does not call the AI provider. The textured human avatar is supplied by Microsoft Rocketbox under the MIT license. It is not a clinical anatomical model.</p><button class="button-primary" @click="dialog = null">Got it<AppIcon name="check" :size="16"/></button></template>
      <template v-else-if="dialog === 'clear'"><p>This removes all saved assessments from this browser and this session. Your current conversation will stay open.</p><div class="dialog-actions"><button class="button-secondary" @click="dialog = null">Keep history</button><button class="button-danger" @click="clearHistory">Clear history</button></div></template>
      <template v-else-if="inspected"><span class="dialog-demo-label">SCRIPTED DEMONSTRATION · NOT A DIAGNOSIS</span><h3 class="assessment-dialog-area"><AppIcon :name="inspected.region" :size="24"/>{{ getRegion(inspected.region).label }}</h3><dl class="assessment-details"><div><dt>Symptoms</dt><dd>{{ inspected.answers.symptom }}</dd></div><div><dt>Location</dt><dd>{{ inspected.answers.location }}</dd></div><div><dt>First noticed</dt><dd>{{ inspected.answers.onset }}</dd></div><div><dt>Pattern</dt><dd>{{ inspected.answers.character }}</dd></div><div><dt>Pain level</dt><dd>{{ inspected.pain }} out of 10</dd></div></dl><button class="button-primary" @click="exportAssessment(inspected)"><AppIcon name="download" :size="16"/>Export JSON</button></template>
    </AppDialog>
  </div>
</template>
