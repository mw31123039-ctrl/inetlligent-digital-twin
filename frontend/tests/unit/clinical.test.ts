import { describe, expect, it } from 'vitest'
import fixture from '../fixtures/clinical-collecting.json'
import { anchorPositions } from '../../src/clinical/anatomy'
import { createNdjsonParser } from '../../src/clinical/api'
import { diffAssessments } from '../../src/clinical/diff'
import { strings, translate } from '../../src/clinical/i18n'
import type { AnatomyNode, ClinicalAssessment, StreamEvent } from '../../src/clinical/types'

const base = fixture as unknown as ClinicalAssessment
const clone = (): ClinicalAssessment => JSON.parse(JSON.stringify(base))

describe('clinical i18n', () => {
  it('has every UI string in English, Arabic and Sorani Kurdish', () => {
    for (const [key, value] of Object.entries(strings)) {
      for (const locale of ['en', 'ar', 'ckb'] as const) expect((value as Record<string, string>)[locale]?.trim(), `${key}.${locale}`).toBeTruthy()
      const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map(match => match[1]).sort()
      expect(placeholders(value.ar), key).toEqual(placeholders(value.en))
      expect(placeholders(value.ckb), key).toEqual(placeholders(value.en))
    }
    expect(translate('ckb', 'days', { n: 30 })).toContain('30')
  })
})

describe('NDJSON stream parser', () => {
  it('parses events split anywhere across network chunks', () => {
    const events: StreamEvent[] = []
    const parser = createNdjsonParser(event => events.push(event))
    const payload = '{"type":"stage","stage":"received"}\n{"type":"stage","stage":"screening"}\n{"type":"final","envelope":{"id":"x"}}\n'
    for (let index = 0; index < payload.length; index += 7) parser.push(payload.slice(index, index + 7))
    parser.end()
    expect(events.map(event => event.type)).toEqual(['stage', 'stage', 'final'])
    expect(events[1]).toEqual({ type: 'stage', stage: 'screening' })
  })

  it('accepts a final line without a trailing newline and rejects garbage', () => {
    const events: StreamEvent[] = []
    const parser = createNdjsonParser(event => events.push(event))
    parser.push('{"type":"error","status":502,"message":"No result was accepted."}')
    parser.end()
    expect(events[0]).toMatchObject({ type: 'error', status: 502 })
    expect(() => createNdjsonParser(() => undefined).push('not json\n')).toThrow()
  })
})

describe('what changed', () => {
  it('reports nothing for identical assessments', () => {
    expect(diffAssessments(base, clone()).hasChanges).toBe(false)
  })

  it('reports fact, urgency, explanation, missing-information and contradiction changes', () => {
    const next = clone()
    next.urgency.level = 'same_day'
    const itch = next.patient_facts.find(fact => fact.id === 'symptom:itch')!
    itch.status = 'absent'
    next.patient_facts.push({ ...itch, id: 'symptom:pain', key: 'pain', label: 'Pain or soreness', status: 'present' })
    next.patient_facts = next.patient_facts.filter(fact => fact.id !== 'symptom:discharge')
    next.possible_explanations[0]!.fit = 'partly_fits'
    next.possible_explanations = next.possible_explanations.slice(0, 2)
    const resolved = next.missing_information.shift()!
    next.contradictions.push({ id: 'contradiction:x', kind: 'symptom_presence', description: 'You first said “a” and later “b”.', fact_ids: [], message_ids: [], resolved: false })
    const diff = diffAssessments(base, next)
    expect(diff.urgency).toEqual({ from: base.urgency.level, to: 'same_day' })
    expect(diff.facts.added.map(fact => fact.id)).toEqual(['symptom:pain'])
    expect(diff.facts.removed.map(fact => fact.id)).toEqual(['symptom:discharge'])
    expect(diff.facts.changed).toEqual([expect.objectContaining({ id: 'symptom:itch', from: 'present', to: 'absent' })])
    expect(diff.explanations.fitChanged[0]).toMatchObject({ from: 'fits', to: 'partly_fits' })
    expect(diff.explanations.removed).toHaveLength(base.possible_explanations.length - 2)
    expect(diff.missing.resolved).toEqual([resolved.label])
    expect(diff.contradictions.added).toHaveLength(1)
    expect(diff.hasChanges).toBe(true)
  })

  it('treats the first assessment as all-new facts without inventing resolved items', () => {
    const diff = diffAssessments(null, base)
    expect(diff.urgency).toBeNull()
    expect(diff.missing.resolved).toEqual([])
    expect(diff.facts.added.length).toBeGreaterThan(0)
  })
})

describe('anatomy marker anchors', () => {
  const bones = (key: string): [number, number, number] => key.startsWith('left') ? [.2, 1, 0] : key.startsWith('right') ? [-.2, 1, 0] : [0, 1.5, 0]
  const node = (patch: Partial<AnatomyNode>): AnatomyNode => ({ id: 'x', parent: null, kind: 'structure', label: { en: 'x', ar: 'x', ckb: 'x' }, lateral: false, fixed_side: null,
    anchor: { bone: 'head', offset: [.03, .1, .1] }, legacy_region: null, internal: false, specialty: null, photo_visible: null, related: [], status: 'active', ...patch })

  it('mirrors lateral structures to the patient’s right (+x is the patient’s left)', () => {
    const eye = node({ lateral: true })
    expect(anchorPositions(eye, 'left', bones)[0]![0]).toBeCloseTo(.03)
    expect(anchorPositions(eye, 'right', bones)[0]![0]).toBeCloseTo(-.03)
    expect(anchorPositions(eye, 'unknown', bones)).toHaveLength(2)
  })

  it('uses the side-specific limb bone and keeps fixed-side offsets unmirrored', () => {
    const knee = node({ lateral: true, anchor: { bone: 'shin', offset: [0, 0, .05] } })
    expect(anchorPositions(knee, 'right', bones)[0]![0]).toBeCloseTo(-.2)
    const tooth = node({ fixed_side: 'right', anchor: { bone: 'head', offset: [-.01, .04, .1] } })
    expect(anchorPositions(tooth, 'right', bones)[0]![0]).toBeCloseTo(-.01)
  })
})
