<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppIcon from '../components/AppIcon.vue'
import { cancerFaqs, cancerTopics, clinicalSources, searchTopics } from './knowledge'
import type { CancerTrack } from './model'
import { aiApi } from '../services/aiApi'
import { acceptEvidenceAnswer, questionFingerprint } from './knowledgeAi'
import type { EvidenceAnswer } from './knowledgeAi'
const props = defineProps<{ signedIn: boolean; topic?: string }>()
const emit = defineEmits<{ analyze: [track: CancerTrack]; plan: [topic: string]; signIn: [] }>()
const query = ref(''), region = ref('all'), topicId = ref(cancerTopics.some(item => item.id === props.topic) ? props.topic! : 'skin')
const matches = computed(() => searchTopics(query.value, region.value))
const active = computed(() => cancerTopics.find(item => item.id === topicId.value)!)
watch(() => props.topic, async value => {
  if (!value || !cancerTopics.some(item => item.id === value)) return
  query.value = ''; region.value = 'all'; topicId.value = value
  await nextTick(); (document.getElementById('care-topic-heading') as HTMLElement | null)?.focus()
})
watch(matches, values => { if (values.length && !values.some(item => item.id === topicId.value)) topicId.value = values[0]!.id })
const question = ref(''), aiConsent = ref(false), aiReady = ref(false), aiChecking = ref(true), aiPending = ref(false), aiError = ref('')
const answer = ref<EvidenceAnswer | null>(null), selectedEvidenceId = ref('')
const faq = computed(() => cancerFaqs.find(item => item.id === selectedEvidenceId.value))
let controller: AbortController | null = null, statusController: AbortController | null = null, revision = 0
function cancel() { revision++; controller?.abort(); controller = null; aiPending.value = false; answer.value = null; selectedEvidenceId.value = ''; aiError.value = '' }
watch(question, cancel)
watch(aiConsent, value => { if (!value) cancel() })
onMounted(async () => {
  const active = new AbortController(); statusController = active
  try {
    const value = await aiApi.get<{ configured: boolean; method: string; clinical_validation: boolean; external_requests: boolean }>('/cancer/knowledge-status', active.signal)
    if (!active.signal.aborted) aiReady.value = value.configured === true && value.method === 'local-semantic-retrieval' && value.clinical_validation === false && value.external_requests === false
  } catch { aiReady.value = false }
  finally { aiChecking.value = false; if (statusController === active) statusController = null }
})
onBeforeUnmount(() => { cancel(); statusController?.abort() })
async function ask() {
  if (!props.signedIn) { emit('signIn'); return }
  if (!aiReady.value || !aiConsent.value || question.value.trim().length < 3 || aiPending.value) return
  cancel(); const version = revision, text = question.value.trim(); aiPending.value = true
  const active = new AbortController(); controller = active
  try {
    const hash = await questionFingerprint(text)
    const value = await aiApi.post<unknown>('/cancer/knowledge', { question: text, consent_local: true }, active.signal)
    if (version !== revision || active.signal.aborted) return
    answer.value = acceptEvidenceAnswer(value, hash)
    selectedEvidenceId.value = answer.value.matches[0]?.record_id ?? ''
    const topic = cancerTopics.find(item => item.id === answer.value?.matches[0]?.record_id)
    if (topic) { query.value = ''; region.value = 'all'; topicId.value = topic.id }
  } catch (cause) { if (version === revision && !active.signal.aborted) aiError.value = cause instanceof Error ? cause.message : 'Local evidence search is unavailable.' }
  finally { if (version === revision) { aiPending.value = false; controller = null } }
}
function recordTitle(id: string) { return cancerTopics.find(item => item.id === id)?.name ?? cancerFaqs.find(item => item.id === id)?.title ?? id }
function followRecord(id: string) { selectedEvidenceId.value = id; const topic = cancerTopics.find(item => item.id === id); if (topic) { query.value = ''; region.value = 'all'; topicId.value = id } }
function select(id: string) { topicId.value = id }
</script>
<template>
  <section class="care-knowledge" aria-label="Cancer knowledge library">
    <div class="care-section-heading"><div><span class="care-eyebrow">KNOWLEDGE, WITH SOURCES</span><h2>Understand the questions behind a diagnosis.</h2><p>Explore {{ cancerTopics.length }} cancer topics, common investigations and treatment approaches. Symptoms can have many causes; these pages do not diagnose an individual.</p></div><span class="care-source-stamp">NCI + NHS references<br/>Sources consulted 13 Nov 2026</span></div>
    <section class="care-ai-search" aria-label="Local AI evidence assistant"><div class="care-panel-title"><div><span class="care-eyebrow">ASK THE SOURCE LIBRARY</span><h3>Ask a question in your own words.</h3></div><span class="care-ready-chip"><i v-if="aiReady"></i>{{ aiChecking ? 'Checking AI search…' : aiReady ? 'Local AI search ready' : 'AI search unavailable' }}</span></div><p>A local sentence-embedding model finds relevant records in this curated library. It retrieves information, not possible diagnoses or personal treatment prescriptions.</p><label>Your cancer information question<textarea v-model="question" rows="2" maxlength="600" placeholder="For example: Which tests investigate a mouth ulcer lasting several weeks?"></textarea></label><label class="care-checkbox"><input v-model="aiConsent" type="checkbox"/>I permit processing this question in the local evidence-search service. It is not saved or sent to an external AI provider.</label><div class="care-topic-actions"><button class="care-primary" :disabled="aiPending || (!props.signedIn ? false : !aiReady || !aiConsent || question.trim().length < 3)" @click="ask"><AppIcon name="sparkles" :size="19"/>{{ !props.signedIn ? 'Sign in to ask local AI' : aiPending ? 'Searching the source records…' : 'Ask local AI' }}</button><span class="care-help">English reference questions · up to 600 characters</span></div><p v-if="aiError" class="cancer-error" role="alert">{{ aiError }}</p><div v-if="answer" class="care-ai-answer" aria-live="polite"><div v-if="answer.safety_notice !== 'none'" class="care-emergency"><AppIcon name="info" :size="23"/><div><h4>{{ answer.safety_notice === 'emergency-terms' ? 'If this describes a current emergency, seek help now.' : 'Coughing up blood needs urgent medical advice.' }}</h4><p>{{ answer.safety_notice === 'emergency-terms' ? 'Do not wait for AI if there is severe breathing difficulty, uncontrolled bleeding or more than a few streaks of coughed-up blood. Contact the local emergency service.' : 'Even a few blood streaks need urgent medical advice. Seek emergency care if bleeding increases or breathing becomes difficult.' }}</p><a :href="clinicalSources.coughingBlood.url" target="_blank" rel="noopener noreferrer">NHS guidance</a></div></div><template v-if="answer.matches.length"><span class="care-eyebrow">SOURCE-LINKED INFORMATION FOUND</span><h4>{{ recordTitle(selectedEvidenceId) }}</h4><p v-if="faq">{{ faq.text }}</p><p v-else>The most relevant guide is selected below. It explains reported changes, possible investigations and broad treatment approaches. Relevance is not the likelihood that you have that cancer.</p><div class="care-ai-matches"><button v-for="item in answer.matches" :key="item.record_id" class="care-secondary" @click="followRecord(item.record_id)">{{ recordTitle(item.record_id) }}<AppIcon name="arrowRight" :size="16"/></button></div><div v-if="faq?.sources.length" class="care-topic-sources"><a v-for="source in faq.sources" :key="source" :href="source" target="_blank" rel="noopener noreferrer">{{ source.includes('nhs.uk') ? 'NHS source guidance' : 'National Cancer Institute source' }}<AppIcon name="arrowRight" :size="15"/></a></div><small>Computed in {{ answer.retrieval_ms.toFixed(0) }} ms with {{ answer.model_version }}. Retrieved text comes from the shared source library; no free-form medical answer is generated.</small></template><p v-else>No sufficiently close reference was found in this limited collection. Try a specific cancer type or browse the guides below.</p></div></section>
    <label class="care-search"><AppIcon name="book" :size="22"/><input v-model="query" aria-label="Search cancer knowledge" placeholder="Or filter the library by a cancer type, symptom or test…" type="search"/></label>
    <div class="care-filter-row" aria-label="Filter knowledge by body area"><button v-for="item in [{id:'all',label:'All areas'},{id:'head',label:'Head & neck'},{id:'chest',label:'Chest'},{id:'abdomen',label:'Abdomen'},{id:'pelvis',label:'Pelvis'},{id:'systemic',label:'Blood & lymph'},{id:'skin',label:'Skin'}]" :key="item.id" :aria-pressed="region === item.id" :class="{ active: region === item.id }" @click="region = item.id">{{ item.label }}</button></div>
    <div class="care-knowledge-layout">
      <nav class="care-topic-list" aria-label="Cancer topics"><button v-for="topic in matches" :key="topic.id" :class="{ active: topicId === topic.id }" :aria-pressed="topicId === topic.id" @click="select(topic.id)"><span>{{ topic.name }}</span><small>{{ topic.modelTrack ? 'Image model + knowledge' : 'Knowledge guide' }}</small><AppIcon name="chevronRight" :size="18"/></button><p v-if="!matches.length" class="care-no-matches">No matching topic in this library. This is a selected reference collection, not a complete medical database.</p></nav>
      <article v-if="matches.length" class="care-topic-detail">
        <span class="care-eyebrow">{{ active.modelTrack ? 'IMAGE REVIEW & CLINICAL KNOWLEDGE' : 'CLINICAL KNOWLEDGE · NO IMAGE MODEL INSTALLED' }}</span><h3 id="care-topic-heading" tabindex="-1">{{ active.name }}</h3><p class="care-topic-intro">{{ active.overview }}</p>
        <div class="care-topic-columns"><section><span class="care-topic-icon"><AppIcon name="activity" :size="22"/></span><h4>Changes to discuss</h4><ul><li v-for="item in active.symptoms" :key="item">{{ item }}</li></ul><p>These changes can also be caused by other conditions. Their absence does not rule out disease.</p></section><section><span class="care-topic-icon"><AppIcon name="clipboard" :size="22"/></span><h4>How clinicians investigate</h4><ul><li v-for="item in active.investigations" :key="item">{{ item }}</li></ul><p>Tests are chosen after a clinical assessment, not ordered by this app.</p></section></div>
        <section class="care-treatment-box"><div><span class="care-eyebrow">AFTER A CONFIRMED DIAGNOSIS</span><h4>Treatment approaches to discuss</h4></div><ul><li v-for="item in active.treatment" :key="item">{{ item }}</li></ul><p>The exact type, stage, biomarkers, overall health and personal preferences guide treatment. This overview does not choose a treatment or medicine for you.</p></section>
        <div class="care-topic-actions"><button v-if="active.modelTrack" class="care-primary" @click="emit('analyze', active.modelTrack)">Open image review<AppIcon name="arrowRight" :size="18"/></button><button class="care-secondary" @click="emit('plan', active.id)">Prepare a review plan<AppIcon name="clipboard" :size="18"/></button></div>
        <footer class="care-topic-sources"><strong>Read the original information</strong><a :href="active.source" target="_blank" rel="noopener noreferrer">National Cancer Institute · {{ active.name }}<AppIcon name="arrowRight" :size="16"/></a><a v-if="active.symptomSource" :href="active.symptomSource" target="_blank" rel="noopener noreferrer">Symptoms and clinical assessment<AppIcon name="arrowRight" :size="16"/></a><a :href="clinicalSources.diagnosis.url" target="_blank" rel="noopener noreferrer">How cancer is diagnosed<AppIcon name="arrowRight" :size="16"/></a></footer>
      </article>
    </div>
  </section>
</template>
