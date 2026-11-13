import { describe, expect, it } from 'vitest'
import { acceptResult, blankHistory, emptyStatus, parseStatus, pathways, preferredModality, researchRecord } from '../../src/cancer/model'
import type { CancerResult, ModelStatus, ResearchImage } from '../../src/cancer/model'

const image: ResearchImage = { dataUrl: 'private-image-bytes', sha256: 'a'.repeat(64), width: 64, height: 48 }
const model: ModelStatus = { modality: 'skin_photo', configured: true, state: 'configured-unvalidated', model_version: 'software-test-v1', target: 'Synthetic software fixture', weights_sha256: 'b'.repeat(64) }
const fixture = (): CancerResult => ({ schema_version: 'humantwin-cancer-result-v1', track: 'skin', modality: 'skin_photo', model_version: model.model_version!, target: model.target!, weights_sha256: model.weights_sha256!, input_sha256: image.sha256,
  scores: [{ label: 'test_a', value: .7 }, { label: 'test_b', value: .3 }], clinical_validation: false, calibrated_cancer_probability: false, scope: 'single-2d-image', external_requests: false })
const status = () => ({ ...emptyStatus(), available: true, clinical_validation: false, external_requests: false, scope: 'single-2d-image', pathways: pathways.map(path => ({ track: path.id, models: path.modalities.map(modality => ({ modality, configured: false, state: 'not-configured' })) })) })

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
  it('requires explicit, consistent model readiness and provenance', () => {
    const valid = status()
    valid.pathways[0]!.models[0] = model
    expect(parseStatus(valid).pathways[0]!.models[0]!.configured).toBe(true)
    expect(() => parseStatus({ ...valid, available: false })).toThrow()
    const missingFingerprint = { ...model, weights_sha256: '' }
    valid.pathways[0]!.models[0] = missingFingerprint
    expect(() => parseStatus(valid)).toThrow(/provenance/)
  })
  it('accepts only scores bound to the exact image, pathway and checked model', () => {
    expect(acceptResult(fixture(), 'skin', 'skin_photo', image.sha256, model).scores[0]!.value).toBe(.7)
    for (const changed of [{ input_sha256: 'c'.repeat(64) }, { track: 'lung' }, { modality: 'dermoscopy' }, { weights_sha256: 'c'.repeat(64) }, { model_version: 'different' }, { target: 'different' }, { diagnosis: 'cancer' }, { clinical_validation: true }, { calibrated_cancer_probability: true }, { scope: 'full-ct-volume' }]) {
      expect(() => acceptResult({ ...fixture(), ...changed }, 'skin', 'skin_photo', image.sha256, model)).toThrow()
    }
  })
  it('selects installed image types without presenting an unavailable input as ready', () => {
    const registry = emptyStatus()
    registry.pathways[0]!.models[1] = { ...model, modality: 'dermoscopy' }
    registry.pathways[3]!.models[1] = { ...model, modality: 'breast_ultrasound' }
    expect(preferredModality(registry, 'skin', 'skin_photo')).toBe('dermoscopy')
    expect(preferredModality(registry, 'breast', 'mammogram')).toBe('breast_ultrasound')
    expect(preferredModality(registry, 'oral')).toBe('oral_photo')
    expect(registry.pathways[0]!.models[0]!.configured).toBe(false)
  })
  it('accepts measured runtime, technical checks and a bounded non-localizing sensitivity map', () => {
    const advanced = { ...fixture(), inference_ms: 1542.2, runtime: 'onnxruntime-cpu',
      uncertainty: { normalized_entropy: .88, margin: .4, interpretation: 'research-only' },
      explanation: { method: 'occlusion-sensitivity', target_label: 'test_a', grid_size: 4, values: Array(16).fill(.25), meaning: 'score-drop-under-occlusion', localization: false, max_score_drop: .06 },
      image_checks: { width: 64, height: 48, brightness: 123, contrast: 47, warnings: [] },
      model_info: { source_url: 'https://example.invalid/model', license: 'Software fixture only', evaluation_reference: 'No clinical evaluation', patient_disjoint: null },
    }
    const result = acceptResult(advanced, 'skin', 'skin_photo', image.sha256, model)
    expect(result.explanation?.values).toHaveLength(16)
    expect(result.explanation?.localization).toBe(false)
    expect(result.explanation?.max_score_drop).toBe(.06)
    expect(result.inference_ms).toBe(1542.2)
    expect(researchRecord('STUDY-1', undefined, 'skin', 'skin_photo', blankHistory(), image, result).result?.model_info?.patient_disjoint).toBeNull()
    for (const changes of [
      { inference_ms: NaN }, { runtime: 'fabricated-gpu' },
      { uncertainty: { ...advanced.uncertainty, normalized_entropy: 1.1 } },
      { explanation: { ...advanced.explanation, localization: true } },
      { explanation: { ...advanced.explanation, max_score_drop: -1 } },
      { explanation: { ...advanced.explanation, values: Array(15).fill(.25) } },
      { explanation: { ...advanced.explanation, values: Array(16).fill(1.1) } },
      { explanation: { ...advanced.explanation, target_label: 'unknown' } },
      { image_checks: { ...advanced.image_checks, brightness: 999 } },
      { model_info: { ...advanced.model_info, source_url: 'javascript:alert(1)' } },
    ]) expect(() => acceptResult({ ...advanced, ...changes }, 'skin', 'skin_photo', image.sha256, model)).toThrow()
  })
  it('retains compatibility with legacy outputs that have no advanced measurements', () => {
    const result = acceptResult({ ...fixture(), inference_ms: null, runtime: null, uncertainty: null, explanation: null, image_checks: null, model_info: null }, 'skin', 'skin_photo', image.sha256, model)
    expect(result.inference_ms).toBeNull()
    expect(result.explanation).toBeNull()
  })
  it('rejects non-finite, duplicate and inconsistent classifier scores', () => {
    for (const scores of [[{ label: 'a', value: NaN }, { label: 'b', value: 0 }], [{ label: 'a', value: .9 }, { label: 'b', value: .9 }], [{ label: 'a', value: .5 }, { label: 'a', value: .5 }]]) {
      expect(() => acceptResult({ ...fixture(), scores }, 'skin', 'skin_photo', image.sha256, model)).toThrow()
    }
  })
  it('exports history-only records without converting missing inference into a negative finding', () => {
    const history = { ...blankHistory(), symptoms: 'Synthetic symptom history' }
    const record = researchRecord('STUDY-1', undefined, 'lung', 'lung_ct_slice', history, null, null)
    expect(record.inference_state).toBe('not-run'); expect(record.cancer_diagnosis).toBeNull()
    expect(record.history.evidence_basis).toBe('user-entered-unverified'); expect(record.twin_link).toBeNull()
    history.symptoms = 'Changed'; expect(record.history.symptoms).toBe('Synthetic symptom history')
  })
  it('links only the same coded subject and excludes image bytes from export', () => {
    const record = researchRecord('STUDY-1', 'STUDY-1', 'skin', 'skin_photo', blankHistory(), image, fixture())
    expect(record.twin_link?.subject_id).toBe('STUDY-1')
    expect(JSON.stringify(record)).not.toContain(image.dataUrl)
    expect(researchRecord('OTHER', 'STUDY-1', 'skin', 'skin_photo', blankHistory(), null, null).twin_link).toBeNull()
    expect(() => researchRecord('full name here', undefined, 'skin', 'skin_photo', blankHistory(), null, null)).toThrow()
    expect(() => researchRecord('STUDY-1', undefined, 'lung', 'skin_photo', blankHistory(), image, fixture())).toThrow()
  })
})
