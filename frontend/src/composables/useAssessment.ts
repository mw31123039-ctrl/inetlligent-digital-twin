import { computed, ref } from 'vue'
import { getRegion } from '../data/regions'
import { createMockSymptomService } from '../services/mockSymptomService'
import type { Answers, Assessment, DemoSettings, Message, RegionId } from '../types'

const emptyAnswers = (): Answers => ({ symptom: '', location: '', onset: '', character: '' })
export function useAssessment(settings: DemoSettings) {
  const region = ref<RegionId | null>('eyes')
  const messages = ref<Message[]>([])
  const answers = ref(emptyAnswers())
  const pain = ref(4)
  const step = ref(0)
  const pending = ref(false)
  const error = ref('')
  const options = ref<string[]>([])
  const saved = ref(false)
  const complete = computed(() => step.value >= 4)
  let generation = 0
  let assessmentId = crypto.randomUUID()
  const failedAnswer = ref('')
  const service = createMockSymptomService({ shouldFail: () => {
    if (!settings.failNextResponse) return false
    settings.failNextResponse = false
    return true
  } })
  function selectRegion(id: RegionId | null) {
    generation++
    assessmentId = crypto.randomUUID()
    region.value = id
    answers.value = emptyAnswers()
    pain.value = 4
    step.value = 0
    error.value = ''
    pending.value = false
    saved.value = false
    failedAnswer.value = ''
    messages.value = id ? [{ id: crypto.randomUUID(), role: 'assistant', text: `You selected your ${getRegion(id).label.toLowerCase()}. What is bothering you?` }] : []
    options.value = id ? getRegion(id).symptomOptions : []
  }
  async function send(text: string, retry = false) {
    if (!region.value || pending.value) return
    const answer = text.trim()
    if (!answer || answer.length > 500) { error.value = 'Enter an answer between 1 and 500 characters.'; return }
    const version = generation
    error.value = ''
    pending.value = true
    if (!retry) messages.value.push({ id: crypto.randomUUID(), role: 'user', text: answer })
    try {
      const result = await service.respond(region.value, step.value, answer)
      if (version !== generation) return
      const keys: (keyof Answers)[] = ['symptom', 'location', 'onset', 'character']
      if (step.value < 4) answers.value[keys[step.value]!] = answer
      else answers.value.symptom += ` · ${answer}`
      step.value = Math.min(4, step.value + 1)
      messages.value.push({ id: crypto.randomUUID(), role: 'assistant', text: result.message })
      options.value = result.options
      failedAnswer.value = ''
      saved.value = false
    } catch (e) {
      if (version !== generation) return
      error.value = e instanceof Error ? e.message : 'Something went wrong. Please try again.'
      failedAnswer.value = answer
    } finally { if (version === generation) pending.value = false }
  }
  function retry() { if (failedAnswer.value) return send(failedAnswer.value, true) }
  function snapshot(): Assessment | null {
    if (!region.value || !complete.value) return null
    return { id: assessmentId, region: region.value, answers: { ...answers.value }, pain: pain.value, messages: messages.value.map(m => ({ ...m })), createdAt: new Date().toISOString() }
  }
  selectRegion('eyes')
  return { region, messages, answers, pain, step, pending, error, options, saved, complete, selectRegion, send, retry, snapshot, canRetry: computed(() => !!failedAnswer.value) }
}
