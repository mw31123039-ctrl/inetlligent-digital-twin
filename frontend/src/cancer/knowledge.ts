import corpus from '../../../contracts/cancer-knowledge.v1.json'
import type { CancerResult, CancerTrack } from './model'

export const knowledgeVersion = corpus.version
export interface CancerTopic {
  id: string
  name: string
  region: 'head' | 'chest' | 'abdomen' | 'pelvis' | 'systemic' | 'skin'
  modelTrack?: CancerTrack
  overview: string
  symptoms: string[]
  investigations: string[]
  treatment: string[]
  specialist: string
  source: string
  symptomSource?: string
  keywords: string[]
}
export const cancerTopics: CancerTopic[] = corpus.topics as CancerTopic[]
export const cancerFaqs = corpus.faqs


export const clinicalSources = {
  diagnosis: { title: 'NCI: How cancer is diagnosed', url: 'https://www.cancer.gov/about-cancer/diagnosis-staging/diagnosis' },
  treatment: { title: 'NCI: Types of cancer treatment', url: 'https://www.cancer.gov/about-cancer/treatment/types' },
  breathlessness: { title: 'NHS: Shortness of breath', url: 'https://www.nhs.uk/symptoms/shortness-of-breath/' },
  bleeding: { title: 'NHS: Cuts and bleeding', url: 'https://www.nhs.uk/conditions/cuts-and-grazes/' },
  coughingBlood: { title: 'NHS: Coughing up blood', url: 'https://www.nhs.uk/symptoms/coughing-up-blood/' },
}

export interface ReportedConcerns {
  severe_breathing: boolean
  uncontrolled_bleeding: boolean
  coughing_blood: 'not-recorded' | 'small-amount' | 'more-than-streaks'
  persistent_change: boolean
}
export function blankConcerns(): ReportedConcerns {
  return { severe_breathing: false, uncontrolled_bleeding: false, coughing_blood: 'not-recorded', persistent_change: false }
}
export function hasEmergency(value: ReportedConcerns) {
  return value.severe_breathing || value.uncontrolled_bleeding || value.coughing_blood === 'more-than-streaks'
}
export function reviewPlan(topicId: string, concerns: ReportedConcerns, priorEmergency = false) {
  const topic = cancerTopics.find(item => item.id === topicId) ?? cancerTopics[0]!
  const emergency = hasEmergency(concerns) || priorEmergency
  const urgent = concerns.coughing_blood === 'small-amount'
  return {
    topic_id: topic.id, evidence_version: knowledgeVersion,
    basis: 'source-linked-information-and-self-reported-concerns',
    urgency: emergency ? 'emergency' : urgent ? 'urgent-medical-advice' : 'clinical-review',
    title: emergency ? 'Seek emergency care now' : urgent ? 'Seek urgent medical advice' : concerns.persistent_change ? 'Arrange a medical assessment' : 'Prepare for a clinical review',
    action: emergency ? 'Do not wait for an image result. Contact your local emergency service or go to the nearest emergency department.' : urgent ? 'Even small streaks of coughed-up blood need urgent medical advice. If breathing becomes difficult or bleeding increases, seek emergency care.' : 'A new, persistent or unexplained change needs a clinician’s assessment. A low image-model score cannot rule out cancer or other illness.',
    specialist: topic.specialist, investigations: [...topic.investigations], treatment_education: [...topic.treatment],
    sources: [topic.source, clinicalSources.diagnosis.url, ...(emergency ? [clinicalSources.breathlessness.url, clinicalSources.bleeding.url, clinicalSources.coughingBlood.url] : urgent ? [clinicalSources.coughingBlood.url] : [])],
    limitations: 'This is an educational review checklist, not a diagnosis, complete triage service, test order or personalized treatment plan.',
  }
}

const classNames: Record<string, string> = {
  melanocytic_nevi: 'Melanocytic nevus (mole)', benign_keratosis_like_lesions: 'Benign keratosis-like lesion',
  basal_cell_carcinoma: 'Basal cell carcinoma class', actinic_keratoses: 'Actinic keratosis class',
  vascular_lesions: 'Vascular lesion class', melanoma: 'Melanoma class', dermatofibroma: 'Dermatofibroma class',
  benign_lesion: 'Benign-lesion class', malignant_lesion: 'Malignant-lesion class',
  benign: 'Benign class', malignant: 'Malignant class', normal: 'Normal-image class',
  adenocarcinoma: 'Adenocarcinoma class', large_cell_carcinoma: 'Large-cell carcinoma class', squamous_cell_carcinoma: 'Squamous-cell carcinoma class',
}
export function readableClass(label: string) {
  return classNames[label.toLowerCase().replace(/[.\s-]/g, '_')] ?? label.replace(/[_.]/g, ' ')
}
export function resultExplanation(result: CancerResult | null) {
  if (!result) return 'An image result will appear after an installed model has processed the uploaded image.'
  const top = [...result.scores].sort((a, b) => b.value - a.value)[0]!
  return `The model’s highest-scoring category is “${readableClass(top.label)}”. This is a match within its training categories, not a confirmed diagnosis. Examination and appropriate tests are still needed to understand the finding.`
}

export function searchTopics(query: string, region = 'all') {
  const tokens = query.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').split(/\s+/).filter(token => token.length > 1)
  return cancerTopics.filter(topic => region === 'all' || topic.region === region).map(topic => {
    const heading = [topic.name, ...topic.keywords].join(' ').toLowerCase()
    const details = [topic.overview, ...topic.symptoms, ...topic.investigations, ...topic.treatment].join(' ').toLowerCase()
    return { topic, score: tokens.reduce((sum, token) => sum + (heading.includes(token) ? 4 : details.includes(token) ? 1 : 0), 0) }
  }).filter(item => !tokens.length || item.score > 0).sort((a, b) => b.score - a.score).map(item => item.topic)
}
