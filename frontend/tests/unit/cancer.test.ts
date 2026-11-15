import { describe, expect, it } from 'vitest'
import { acceptResult, blankHistory, emptyStatus, parseStatus, pathways, preferredModality, researchRecord, validateResult } from '../../src/cancer/model'
import type { CancerResult, ModelStatus, ResearchImage } from '../../src/cancer/model'
import { classMeaning, guideFor, heatColor, reportHtml, sampleGrid, summarize } from '../../src/cancer/report'

const image: ResearchImage = { dataUrl: 'private-image-bytes', sha256: 'a'.repeat(64), width: 64, height: 48 }
const model: ModelStatus = { modality: 'skin_photo', configured: true, state: 'configured-unvalidated', model_version: 'software-test-v1', target: 'Synthetic software fixture', weights_sha256: 'b'.repeat(64) }
const checks = (decision: 'accepted' | 'accepted-with-warnings' | 'rejected' = 'accepted') => ({ width: 64, height: 48, brightness: 123, contrast: 47, sharpness: 80, colored_fraction: .9, overexposed_fraction: 0, decision,
  findings: decision === 'rejected' ? [{ code: 'unexpected-grayscale', severity: 'reject' as const, message: 'This image is grayscale.' }] : [{ code: 'content-not-verified', severity: 'info' as const, message: 'Anatomy is not verified automatically.' }] })
const confidence = (label = 'melanoma', probability = .7, level: 'high' | 'moderate' | 'low' = 'moderate') => ({ top_label: label, probability, level, calibration: 'temperature-scaled' as const, temperature: 1.5, decision_threshold: .6, normalized_entropy: .88, margin: .4, interpretation: 'model-confidence-not-personal-risk' as const })
const fixture = (): CancerResult => ({ schema_version: 'humantwin-cancer-result-v2', track: 'skin', modality: 'skin_photo', model_version: model.model_version!, target: model.target!, weights_sha256: model.weights_sha256!, input_sha256: image.sha256,
  outcome: 'finding', outcome_reasons: [], finding_label: 'melanoma', scores: [{ label: 'melanoma', value: .7 }, { label: 'melanocytic_Nevi', value: .3 }], confidence: confidence(), familiarity: null, heatmap: null,
  image_checks: checks(), clinical_validation: false, calibrated_cancer_probability: false, scope: 'single-2d-image', external_requests: false })
const rejected = (): CancerResult => ({ ...fixture(), outcome: 'input-rejected', outcome_reasons: ['input-rejected'], finding_label: null, scores: [], confidence: null, image_checks: checks('rejected') })
const status = () => ({ ...emptyStatus(), available: true, clinical_validation: false, external_requests: false, scope: 'single-2d-image', pathways: pathways.map(path => ({ track: path.id, models: path.modalities.map(modality => ({ modality, configured: false, state: 'not-configured' })) })) })
const heatmap = { method: 'grad-cam' as const, target_label: 'melanoma', class_specific: true, grid_width: 2, grid_height: 2, values: [0, .5, .5, 1], meaning: 'regions-that-raised-the-score' as const, localization: false as const }

describe('cancer research boundaries', () => {
  it('covers all four pathways and keeps seven unconfigured input models unavailable', () => {
    const registry = parseStatus(status())
    expect(registry.pathways.map(path => path.track)).toEqual(['skin', 'oral', 'lung', 'breast'])
    expect(registry.pathways.flatMap(path => path.models)).toHaveLength(7)
    expect(registry.pathways.every(path => path.models.every(item => !item.configured))).toBe(true)
    expect(() => parseStatus({ ...status(), clinical_validation: true })).toThrow()
    const invalid = status(); invalid.pathways[1] = invalid.pathways[0]!
    expect(() => parseStatus(invalid)).toThrow(/duplicate/)
  })
  it('requires explicit, consistent model readiness and provenance, and keeps only known extra metadata', () => {
    const valid = status()
    valid.pathways[0]!.models[0] = { ...model, labels: ['a', 'b'], heatmap_method: 'grad-cam', calibration: 'temperature-scaled' } as never
    const parsed = parseStatus(valid).pathways[0]!.models[0]!
    expect(parsed.configured).toBe(true)
    expect(parsed.heatmap_method).toBe('grad-cam'); expect(parsed.calibration).toBe('temperature-scaled'); expect(parsed.labels).toEqual(['a', 'b'])
    valid.pathways[0]!.models[0] = { ...model, heatmap_method: 'invented' } as never
    expect(parseStatus(valid).pathways[0]!.models[0]!.heatmap_method).toBeUndefined()
    expect(() => parseStatus({ ...valid, available: false })).toThrow()
    valid.pathways[0]!.models[0] = { ...model, weights_sha256: '' } as never
    expect(() => parseStatus(valid)).toThrow(/provenance/)
  })
  it('accepts only results bound to the exact image, pathway and checked model', () => {
    expect(acceptResult(fixture(), 'skin', 'skin_photo', image.sha256, model).scores[0]!.value).toBe(.7)
    for (const changed of [{ input_sha256: 'c'.repeat(64) }, { track: 'lung' }, { modality: 'dermoscopy' }, { weights_sha256: 'c'.repeat(64) }, { model_version: 'different' }, { target: 'different' }, { diagnosis: 'cancer' }, { clinical_validation: true }, { calibrated_cancer_probability: true }, { scope: 'full-ct-volume' }, { schema_version: 'humantwin-cancer-result-v1' }]) {
      expect(() => acceptResult({ ...fixture(), ...changed }, 'skin', 'skin_photo', image.sha256, model)).toThrow()
    }
  })
  it('enforces the outcome contract: findings, inconclusive results and rejected images', () => {
    expect(acceptResult(rejected(), 'skin', 'skin_photo', image.sha256, model).outcome).toBe('input-rejected')
    const inconclusive = { ...fixture(), outcome: 'inconclusive', outcome_reasons: ['low-confidence'], finding_label: null, confidence: confidence('melanoma', .55, 'low'), scores: [{ label: 'melanoma', value: .55 }, { label: 'melanocytic_Nevi', value: .45 }] }
    expect(validateResult(inconclusive).outcome).toBe('inconclusive')
    for (const broken of [
      { ...rejected(), scores: [{ label: 'a', value: 1 }, { label: 'b', value: 0 }] },
      { ...rejected(), image_checks: checks() },
      { ...fixture(), finding_label: 'melanocytic_Nevi' },
      { ...fixture(), outcome_reasons: ['low-confidence'] },
      { ...inconclusive, outcome_reasons: [] },
      { ...fixture(), confidence: confidence('melanocytic_Nevi', .3) },
      { ...fixture(), confidence: null },
      { ...fixture(), image_checks: checks('rejected') },
      { ...fixture(), familiarity: { method: 'class-centroid-cosine', similarity: .1, minimum_similarity: .5, familiar: false } },
      { ...fixture(), image_checks: { ...checks(), findings: [{ code: 'severe-blur', severity: 'limiting', message: 'Blurred.' }] } },
    ]) expect(() => validateResult(broken)).toThrow()
  })
  it('accepts a bounded, non-localising heatmap that refers to a returned class', () => {
    expect(validateResult({ ...fixture(), heatmap }).heatmap?.values).toHaveLength(4)
    for (const changes of [{ localization: true }, { values: [0, .5, .5] }, { values: [0, .5, .5, 1.2] }, { target_label: 'unknown' }, { method: 'grad-cam', meaning: 'patches-the-model-attended-to' }, { grid_width: 64 }]) {
      expect(() => validateResult({ ...fixture(), heatmap: { ...heatmap, ...changes } })).toThrow()
    }
  })
  it('selects installed image types without presenting an unavailable input as ready', () => {
    const registry = emptyStatus()
    registry.pathways[0]!.models[1] = { ...model, modality: 'dermoscopy' }
    registry.pathways[3]!.models[1] = { ...model, modality: 'breast_ultrasound' }
    expect(preferredModality(registry, 'skin', 'skin_photo')).toBe('dermoscopy')
    expect(preferredModality(registry, 'breast', 'mammogram')).toBe('breast_ultrasound')
    expect(preferredModality(registry, 'oral')).toBe('oral_photo')
  })
  it('rejects non-finite, duplicate and inconsistent classifier scores', () => {
    for (const scores of [[{ label: 'melanoma', value: NaN }, { label: 'b', value: 0 }], [{ label: 'melanoma', value: .9 }, { label: 'b', value: .9 }], [{ label: 'melanoma', value: .5 }, { label: 'melanoma', value: .5 }]]) {
      expect(() => acceptResult({ ...fixture(), scores }, 'skin', 'skin_photo', image.sha256, model)).toThrow()
    }
  })
  it('exports research records without image pixels or a negative finding for missing inference', () => {
    const history = { ...blankHistory(), symptoms: 'Synthetic symptom history' }
    const record = researchRecord('STUDY-1', undefined, 'lung', 'lung_ct_slice', history, null, null)
    expect(record.inference_state).toBe('not-run'); expect(record.cancer_diagnosis).toBeNull()
    const linked = researchRecord('STUDY-1', 'STUDY-1', 'skin', 'skin_photo', blankHistory(), image, fixture())
    expect(linked.twin_link?.subject_id).toBe('STUDY-1')
    expect(JSON.stringify(linked)).not.toContain(image.dataUrl)
    expect(() => researchRecord('full name here', undefined, 'skin', 'skin_photo', blankHistory(), null, null)).toThrow()
  })
})

describe('result report', () => {
  it('reads a cancer-class finding as needing review and never as a diagnosis', () => {
    const summary = summarize(fixture())
    expect(summary.tone).toBe('attention'); expect(summary.headline).toBe('Melanoma pattern')
    expect(summary.nextStep).toMatch(/dermatologist/); expect(summary.nextStep).toMatch(/cannot confirm/)
    expect(summarize({ ...fixture(), finding_label: 'melanocytic_Nevi', scores: [{ label: 'melanocytic_Nevi', value: .9 }, { label: 'melanoma', value: .1 }], confidence: confidence('melanocytic_Nevi', .9, 'high') }).nextStep).toMatch(/cannot rule cancer out/)
  })
  it('explains inconclusive and rejected outcomes without naming a finding', () => {
    const inconclusive = summarize({ ...fixture(), outcome: 'inconclusive', outcome_reasons: ['unfamiliar-image'], finding_label: null })
    expect(inconclusive.badge).toBe('Inconclusive'); expect(inconclusive.meaning).toMatch(/not be read as a finding/)
    const blocked = summarize(rejected())
    expect(blocked.tone).toBe('blocked'); expect(blocked.meaning).toMatch(/grayscale/); expect(blocked.meaning).toMatch(/No model result/)
  })
  it('maps every installed model label to plain language and every area to its guide', () => {
    for (const label of ['benign_keratosis-like_lesions', 'basal_cell_carcinoma', 'actinic_keratoses', 'vascular_lesions', 'melanocytic_Nevi', 'melanoma', 'dermatofibroma', 'benign_lesion', 'malignant_lesion', 'adenocarcinoma', 'large.cell.carcinoma', 'normal', 'squamous.cell.carcinoma', 'benign', 'malignant']) {
      expect(classMeaning(label).meaning.length).toBeGreaterThan(30)
    }
    expect(classMeaning('normal', 'breast').name).toMatch(/mass/)
    expect(pathways.map(path => guideFor(path.id).id)).toEqual(['skin', 'oral', 'lung', 'breast'])
  })
  it('interpolates heatmap grids and keeps weak values transparent', () => {
    expect(sampleGrid([0, 1, 0, 1], 2, 2, .25, .5)).toBeCloseTo(0)
    expect(sampleGrid([0, 1, 0, 1], 2, 2, .5, .5)).toBeCloseTo(.5)
    expect(heatColor(0)[3]).toBe(0); expect(heatColor(1)[3]).toBeCloseTo(1)
  })
  it('renders an escaped printable report with the disclaimer', () => {
    const html = reportHtml({ result: { ...fixture(), heatmap }, imageDataUrl: 'data:image/jpeg;base64,AAAA', heatmapDataUrl: 'data:image/jpeg;base64,BBBB', createdAt: '2026-11-16T10:00:00Z', note: '<script>alert(1)</script>' })
    expect(html).toContain('Not a medical diagnosis')
    expect(html).not.toContain('<script>alert(1)</script>'); expect(html).toContain('&lt;script&gt;')
    expect(html).toContain('Grad-CAM')
  })
})
