import { describe, expect, it } from 'vitest'
import { blankConcerns, cancerFaqs, cancerTopics, hasEmergency, readableClass, resultExplanation, reviewPlan, searchTopics } from '../../src/cancer/knowledge'
import { inspectImageDimensions } from '../../src/cancer/model'
import { acceptEvidenceAnswer } from '../../src/cancer/knowledgeAi'

describe('source-linked cancer review', () => {
  it('covers sixteen distinct topics while reserving image models for four pathways', () => {
    expect(cancerTopics).toHaveLength(16)
    expect(new Set(cancerTopics.map(topic => topic.id)).size).toBe(16)
    expect(cancerTopics.filter(topic => topic.modelTrack).map(topic => topic.modelTrack)).toEqual(['skin', 'oral', 'lung', 'breast'])
    for (const topic of cancerTopics) {
      expect(topic.source).toMatch(/^https:\/\/www\.cancer\.gov\//)
      expect(topic.symptoms.length).toBeGreaterThan(0)
      expect(topic.investigations.length).toBeGreaterThan(0)
    }
    expect(cancerFaqs).toHaveLength(4)
  })
  it('retrieves relevant reference topics without assigning a diagnosis or inventing unmatched facts', () => {
    expect(searchTopics('tongue ulcer')[0]!.id).toBe('oral')
    expect(searchTopics('PSA')[0]!.id).toBe('prostate')
    expect(searchTopics('cystoscopy')[0]!.id).toBe('bladder')
    expect(searchTopics('unlistedxyz')).toEqual([])
    expect(searchTopics('', 'systemic').map(topic => topic.id)).toEqual(['leukemia', 'lymphoma'])
    expect(resultExplanation(null)).not.toMatch(/normal|clear|negative screen/i)
    expect(readableClass('melanocytic_Nevi')).toContain('mole')
    expect(readableClass('large.cell.carcinoma')).toContain('Large-cell')
  })
  it('keeps emergency guidance separate from image scores and retains a previous urgent report', () => {
    const empty = blankConcerns()
    expect(hasEmergency(empty)).toBe(false)
    expect(reviewPlan('breast', empty).urgency).toBe('clinical-review')
    for (const concern of [{ severe_breathing: true }, { uncontrolled_bleeding: true }, { coughing_blood: 'more-than-streaks' as const }]) {
      const plan = reviewPlan('lung', { ...empty, ...concern })
      expect(plan.urgency).toBe('emergency')
      expect(plan.action).toContain('Do not wait')
      expect(plan.sources.some(url => url.includes('nhs.uk'))).toBe(true)
    }
    expect(reviewPlan('skin', empty, true).urgency).toBe('emergency')
    expect(reviewPlan('lung', { ...empty, coughing_blood: 'small-amount' }).urgency).toBe('urgent-medical-advice')
    const plan = reviewPlan('brain', empty)
    expect(plan.specialist).toMatch(/neuro/i)
    expect(plan.limitations).toContain('not a diagnosis')
  })
  it('inspects image dimensions before decoding and rejects corrupt headers', () => {
    const png = new Uint8Array(24), data = new DataView(png.buffer)
    png.set([137,80,78,71,13,10,26,10]); data.setUint32(12,0x49484452); data.setUint32(16,4032); data.setUint32(20,3024)
    expect(inspectImageDimensions(png)).toEqual({ width:4032,height:3024 })
    const jpeg = new Uint8Array([255,216,255,192,0,11,8,0,96,0,128,3,1,17,0])
    expect(inspectImageDimensions(jpeg)).toEqual({ width:128,height:96 })
    expect(() => inspectImageDimensions(new Uint8Array([1,2,3]))).toThrow()
    expect(() => inspectImageDimensions(new Uint8Array([255,216,255,192,255,255]))).toThrow()
  })
})

describe('local AI evidence response boundaries', () => {
  const hash = 'a'.repeat(64)
  const fixture = () => ({ schema_version:'humantwin-cancer-retrieval-v1', method:'local-semantic-retrieval', corpus_version:'oncology-reference-2026-11-13', model_version:'minilm-l6-q8-test', weights_sha256:'b'.repeat(64), question_sha256:hash, matches:[{record_id:'oral',similarity:.6}], retrieval_ms:5, safety_notice:'none', question_saved:false, external_requests:false, clinical_validation:false })
  it('accepts only known source IDs bound to the question with explicit research/privacy flags', () => {
    expect(acceptEvidenceAnswer(fixture(), hash).matches[0]!.record_id).toBe('oral')
    for (const change of [{ question_sha256:'c'.repeat(64) }, { clinical_validation:true }, { question_saved:true }, { external_requests:true }, { diagnosis:'cancer' }, { corpus_version:'unknown' }, { matches:[{record_id:'invented',similarity:.8}] }, { matches:[{record_id:'oral',similarity:NaN}] }, { matches:[{record_id:'oral',similarity:.6},{record_id:'oral',similarity:.5}] }]) {
      expect(() => acceptEvidenceAnswer({ ...fixture(), ...change }, hash)).toThrow()
    }
  })
})
