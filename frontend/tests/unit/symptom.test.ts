import { describe, expect, it } from 'vitest'
import { reactive } from 'vue'
import { createMockSymptomService } from '../../src/services/mockSymptomService'
import { useAssessment } from '../../src/composables/useAssessment'
import { defaultSettings } from '../../src/services/localAssessmentRepository'
import { regions } from '../../src/data/regions'

describe('scripted symptom service', () => {
  it.each(regions)('supports the full $label conversation and additional notes', async region => {
    const service = createMockSymptomService({ delay: 0 })
    expect((await service.respond(region.id, 0, 'My symptoms')).message).toBe(region.locationQuestion)
    expect((await service.respond(region.id, 1, region.locations[0]!)).options).toContain('Just today')
    expect((await service.respond(region.id, 2, 'Just today')).options).toContain('Constant')
    expect((await service.respond(region.id, 3, 'Constant')).complete).toBe(true)
    expect((await service.respond(region.id, 4, 'A note')).message).toContain('note')
  })
  it('validates input and exposes retryable service failures', async () => {
    const service = createMockSymptomService({ delay: 0, shouldFail: () => true })
    await expect(service.respond('eyes', 0, '   ')).rejects.toThrow('Please describe')
    await expect(service.respond('eyes', 0, 'a'.repeat(501))).rejects.toThrow('500')
    await expect(service.respond('eyes', 0, 'My eyes hurt')).rejects.toThrow('try again')
  })
})

describe('assessment state', () => {
  it('ignores a stale response after switching regions', async () => {
    const flow = useAssessment(reactive({ ...defaultSettings }))
    const response = flow.send('My eyes hurt')
    flow.selectRegion('legs')
    await response
    expect(flow.region.value).toBe('legs')
    expect(flow.messages.value).toHaveLength(1)
    expect(flow.answers.value.symptom).toBe('')
    expect(flow.pending.value).toBe(false)
  })
  it('retries without duplicating the user message or losing the answer', async () => {
    const settings = reactive({ ...defaultSettings, failNextResponse: true })
    const flow = useAssessment(settings)
    expect(flow.canRetry.value).toBe(false)
    await flow.send('My eyes hurt')
    expect(flow.canRetry.value).toBe(true)
    expect(flow.step.value).toBe(0)
    await flow.retry()
    expect(flow.answers.value.symptom).toBe('My eyes hurt')
    expect(flow.step.value).toBe(1)
    expect(flow.messages.value.filter(m => m.role === 'user')).toHaveLength(1)
    expect(flow.error.value).toBe('')
    expect(flow.canRetry.value).toBe(false)
  })
})
