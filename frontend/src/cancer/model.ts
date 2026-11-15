export type CancerTrack = 'skin' | 'oral' | 'lung' | 'breast'
export type CancerModality = 'skin_photo' | 'dermoscopy' | 'oral_photo' | 'lung_ct_slice' | 'mammogram' | 'breast_ultrasound' | 'breast_mri_slice'
export type HeatmapMethod = 'grad-cam' | 'attention-rollout' | 'occlusion-sensitivity'
export interface ModelStatus {
  modality: CancerModality
  configured: boolean
  state: 'not-configured' | 'configured-unvalidated' | 'invalid-artifacts' | 'service-unavailable'
  model_version?: string
  target?: string
  weights_sha256?: string
  labels?: string[]
  heatmap_method?: HeatmapMethod
  calibration?: 'temperature-scaled' | 'none'
}
export interface CancerStatus { available: boolean; pathways: { track: CancerTrack; models: ModelStatus[] }[] }
export type CheckSeverity = 'info' | 'warning' | 'limiting' | 'reject'
export interface InputCheck { code: string; severity: CheckSeverity; message: string }
export interface ImageChecks {
  width: number; height: number; brightness: number; contrast: number; sharpness: number
  colored_fraction: number; overexposed_fraction: number
  decision: 'accepted' | 'accepted-with-warnings' | 'rejected'
  findings: InputCheck[]
}
export interface Confidence {
  top_label: string; probability: number; level: 'high' | 'moderate' | 'low'
  calibration: 'temperature-scaled' | 'none'; temperature: number | null; decision_threshold: number
  normalized_entropy: number; margin: number; interpretation: 'model-confidence-not-personal-risk'
}
export interface Heatmap {
  method: HeatmapMethod; target_label: string; class_specific: boolean
  grid_width: number; grid_height: number; values: number[]
  meaning: 'regions-that-raised-the-score' | 'patches-the-model-attended-to' | 'score-drop-under-occlusion'
  localization: false
}
export interface Familiarity { method: 'class-centroid-cosine'; similarity: number; minimum_similarity: number; familiar: boolean }
export type Outcome = 'finding' | 'inconclusive' | 'input-rejected'
export type OutcomeReason = 'input-rejected' | 'input-quality' | 'low-confidence' | 'unfamiliar-image'
export interface CancerResult {
  schema_version: 'humantwin-cancer-result-v2'
  track: CancerTrack
  modality: CancerModality
  model_version: string
  target: string
  weights_sha256: string
  input_sha256: string
  outcome: Outcome
  outcome_reasons: OutcomeReason[]
  finding_label: string | null
  scores: { label: string; value: number }[]
  confidence: Confidence | null
  familiarity: Familiarity | null
  heatmap: Heatmap | null
  image_checks: ImageChecks
  clinical_validation: false
  calibrated_cancer_probability: false
  scope: 'single-2d-image'
  external_requests: false
  inference_ms?: number | null
  runtime?: 'onnxruntime-cpu' | 'opencv-cpu' | null
  model_info?: { source_url: string; license: string; evaluation_reference: string; patient_disjoint: boolean | null } | null
}
export interface ResearchImage { dataUrl: string; sha256: string; width: number; height: number; originalWidth?: number; originalHeight?: number; resized?: boolean; name?: string }
export interface CancerHistory { symptoms: string; duration: string; family_history: 'unknown' | 'yes' | 'no'; tobacco_exposure: 'unknown' | 'yes' | 'no'; prior_findings: string }

export const modalities: Record<CancerModality, { label: string; accepts: string; scope: string }> = {
  skin_photo: { label: 'Skin photograph', accepts: 'Close-up skin photo', scope: 'Visible lesion photographs require a model evaluated on ordinary skin photos.' },
  dermoscopy: { label: 'Dermoscopic image', accepts: 'Dermoscopy photo of one skin lesion', scope: 'A dermoscope image requires a model evaluated on dermoscopy. A phone photograph is a different input.' },
  oral_photo: { label: 'Mouth photograph', accepts: 'Close-up photo inside the mouth', scope: 'Visible oral tissue only. A tooth-outline model cannot assess oral cancer.' },
  lung_ct_slice: { label: 'Lung CT slice export', accepts: 'One chest CT slice, exported as JPEG or PNG', scope: 'One prepared 8-bit CT slice for research. This cannot screen a CT volume, reconstruct a tumor or rule out lung cancer.' },
  mammogram: { label: 'Mammogram export', accepts: 'Mammogram export', scope: 'One prepared 8-bit mammogram image for research. Full-resolution DICOM, multiple views and clinical mammography workflows are not supported.' },
  breast_ultrasound: { label: 'Breast ultrasound export', accepts: 'One breast ultrasound image', scope: 'One prepared ultrasound image requires its own ultrasound model. It cannot be assessed by a mammography model.' },
  breast_mri_slice: { label: 'Breast MRI slice export', accepts: 'Breast MRI slice export', scope: 'One prepared 8-bit MRI slice for research. Volumes, sequences and contrast timing are not supported.' },
}
export const pathways: { id: CancerTrack; label: string; icon: string; summary: string; modalities: CancerModality[]; modelName: string }[] = [
  { id: 'skin', label: 'Skin', icon: 'scan', summary: 'Skin lesions seen through a dermatoscope', modalities: ['skin_photo', 'dermoscopy'], modelName: 'Dermoscopy ViT (HAM10000, 7 classes)' },
  { id: 'oral', label: 'Oral', icon: 'tooth', summary: 'Visible lesions inside the mouth', modalities: ['oral_photo'], modelName: 'Oral lesion ResNet-18 (2 classes)' },
  { id: 'lung', label: 'Lung', icon: 'chest', summary: 'A single chest CT slice', modalities: ['lung_ct_slice'], modelName: 'Lung CT EfficientNet-B0 (4 classes)' },
  { id: 'breast', label: 'Breast', icon: 'layers', summary: 'A single breast ultrasound image', modalities: ['mammogram', 'breast_ultrasound', 'breast_mri_slice'], modelName: 'Breast ultrasound ViT (3 classes)' },
]
export const blankHistory = (): CancerHistory => ({ symptoms: '', duration: '', family_history: 'unknown', tobacco_exposure: 'unknown', prior_findings: '' })
export function emptyStatus(): CancerStatus {
  return { available: false, pathways: pathways.map(path => ({ track: path.id, models: path.modalities.map(modality => ({ modality, configured: false, state: 'service-unavailable' })) })) }
}
export function preferredModality(status: CancerStatus, track: CancerTrack, current?: CancerModality): CancerModality {
  const path = pathways.find(item => item.id === track)!
  const models = status.pathways.find(item => item.track === track)?.models ?? []
  if (current && models.some(item => item.modality === current && item.configured)) return current
  return models.find(item => item.configured)?.modality ?? (current && path.modalities.includes(current) ? current : path.modalities[0]!)
}
const hash = /^[a-f0-9]{64}$/
const version = /^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/
function check(condition: unknown, message: string): asserts condition { if (!condition) throw new Error(message) }
function object(value: unknown): Record<string, unknown> {
  check(value && typeof value === 'object' && !Array.isArray(value), 'The research service returned an invalid object.')
  return value as Record<string, unknown>
}
const finite = (value: unknown, minimum: number, maximum = Number.MAX_VALUE): value is number => typeof value === 'number' && Number.isFinite(value) && value >= minimum && value <= maximum
const label = (value: unknown): value is string => typeof value === 'string' && value.trim().length > 0 && value.length <= 80
const onlyKeys = (value: Record<string, unknown>, keys: string[]) => Object.keys(value).every(key => keys.includes(key))

export function parseStatus(value: unknown): CancerStatus {
  const status = object(value)
  check(typeof status.available === 'boolean' && status.clinical_validation === false && status.external_requests === false && status.scope === 'single-2d-image', 'The model status contract is unsupported.')
  check(Array.isArray(status.pathways) && status.pathways.length === pathways.length, 'The model registry is incomplete.')
  const entries = status.pathways.map(object)
  check(new Set(entries.map(item => item.track)).size === pathways.length, 'The model registry contains duplicate pathways.')
  return { available: status.available, pathways: pathways.map(path => {
    const entry = entries.find(item => item.track === path.id)
    check(entry && Array.isArray(entry.models) && entry.models.length === path.modalities.length, 'The input registry is incomplete.')
    const models = entry.models.map(object)
    check(new Set(models.map(item => item.modality)).size === path.modalities.length, 'The input registry contains duplicates.')
    return { track: path.id, models: path.modalities.map(modality => {
      const model = models.find(item => item.modality === modality)
      check(model && typeof model.configured === 'boolean' && ['not-configured', 'configured-unvalidated', 'invalid-artifacts', 'service-unavailable'].includes(String(model.state)), 'The model state is unsupported.')
      check(model.configured === (model.state === 'configured-unvalidated'), 'The model readiness flags disagree.')
      if (!model.configured) return { modality, configured: false, state: model.state as ModelStatus['state'] }
      check(status.available === true && typeof model.model_version === 'string' && version.test(model.model_version) && typeof model.weights_sha256 === 'string' && hash.test(model.weights_sha256) && typeof model.target === 'string' && model.target.length > 0 && model.target.length <= 160, 'The configured model is missing provenance.')
      const parsed: ModelStatus = { modality, configured: true, state: 'configured-unvalidated', model_version: model.model_version, weights_sha256: model.weights_sha256, target: model.target }
      if (Array.isArray(model.labels) && model.labels.length >= 2 && model.labels.length <= 20 && model.labels.every(label)) parsed.labels = model.labels as string[]
      if (['grad-cam', 'attention-rollout', 'occlusion-sensitivity'].includes(String(model.heatmap_method))) parsed.heatmap_method = model.heatmap_method as HeatmapMethod
      parsed.calibration = model.calibration === 'temperature-scaled' ? 'temperature-scaled' : 'none'
      return parsed
    }) }
  }) }
}

const RESULT_KEYS = ['schema_version', 'track', 'modality', 'model_version', 'target', 'weights_sha256', 'input_sha256', 'outcome', 'outcome_reasons', 'finding_label', 'scores', 'confidence', 'familiarity', 'heatmap', 'image_checks', 'clinical_validation', 'calibrated_cancer_probability', 'scope', 'external_requests', 'inference_ms', 'runtime', 'model_info']
const REASONS = ['input-rejected', 'input-quality', 'low-confidence', 'unfamiliar-image']

function parseChecks(value: unknown): ImageChecks {
  const checks = object(value)
  check(onlyKeys(checks, ['width', 'height', 'brightness', 'contrast', 'sharpness', 'colored_fraction', 'overexposed_fraction', 'decision', 'findings'])
    && Number.isInteger(checks.width) && finite(checks.width, 32, 2048) && Number.isInteger(checks.height) && finite(checks.height, 32, 2048)
    && finite(checks.brightness, 0, 255) && finite(checks.contrast, 0, 128) && finite(checks.sharpness, 0) && finite(checks.colored_fraction, 0, 1) && finite(checks.overexposed_fraction, 0, 1)
    && ['accepted', 'accepted-with-warnings', 'rejected'].includes(String(checks.decision)), 'The image measurements are invalid.')
  check(Array.isArray(checks.findings) && checks.findings.length <= 12, 'The image checks are invalid.')
  const findings = checks.findings.map(item => {
    const finding = object(item)
    check(onlyKeys(finding, ['code', 'severity', 'message']) && typeof finding.code === 'string' && /^[a-z-]{2,40}$/.test(finding.code)
      && ['info', 'warning', 'limiting', 'reject'].includes(String(finding.severity)) && typeof finding.message === 'string' && finding.message.length > 0 && finding.message.length <= 240, 'The image checks are invalid.')
    return { code: finding.code, severity: finding.severity as CheckSeverity, message: finding.message }
  })
  check((checks.decision === 'rejected') === findings.some(item => item.severity === 'reject'), 'The image check decision is inconsistent.')
  return { ...(checks as unknown as ImageChecks), findings }
}

/** Accept a result only when it is bound to this image, pathway and checked model, and internally consistent. */
export function acceptResult(value: unknown, track: CancerTrack, modality: CancerModality, inputHash: string, expected: ModelStatus): CancerResult {
  const result = object(value)
  check(onlyKeys(result, RESULT_KEYS), 'The classifier returned unsupported fields.')
  check(expected.configured && result.schema_version === 'humantwin-cancer-result-v2' && result.track === track && result.modality === modality && pathways.find(path => path.id === track)?.modalities.includes(modality), 'The result belongs to a different pathway.')
  check(hash.test(inputHash) && result.input_sha256 === inputHash && result.model_version === expected.model_version && result.weights_sha256 === expected.weights_sha256 && result.target === expected.target, 'The image or model changed. Check model status and run again.')
  return validateResult(result)
}

/** Structural and cross-field validation shared by live and saved results. */
export function validateResult(value: unknown): CancerResult {
  const result = object(value)
  check(onlyKeys(result, RESULT_KEYS) && result.schema_version === 'humantwin-cancer-result-v2', 'The classifier returned unsupported fields.')
  check(result.clinical_validation === false && result.calibrated_cancer_probability === false && result.scope === 'single-2d-image' && result.external_requests === false, 'The model returned unsupported clinical claims.')
  check(['finding', 'inconclusive', 'input-rejected'].includes(String(result.outcome)), 'The result outcome is unsupported.')
  check(Array.isArray(result.outcome_reasons) && result.outcome_reasons.every(item => REASONS.includes(String(item))) && new Set(result.outcome_reasons).size === result.outcome_reasons.length, 'The result reasons are unsupported.')
  check(Array.isArray(result.scores) && result.scores.length <= 20, 'The classifier returned an invalid score vector.')
  const scores = result.scores.map(item => {
    const score = object(item)
    check(Object.keys(score).length === 2 && label(score.label) && finite(score.value, 0, 1), 'The classifier returned invalid scores.')
    return { label: score.label as string, value: score.value as number }
  })
  const checks = parseChecks(result.image_checks)
  const reasons = result.outcome_reasons as OutcomeReason[]
  if (result.outcome === 'input-rejected') {
    check(scores.length === 0 && result.confidence == null && result.heatmap == null && result.familiarity == null && result.finding_label == null && reasons.length === 1 && reasons[0] === 'input-rejected' && checks.decision === 'rejected', 'A rejected image cannot carry model output.')
  } else {
    check(scores.length >= 2 && new Set(scores.map(item => item.label)).size === scores.length && Math.abs(scores.reduce((sum, item) => sum + item.value, 0) - 1) <= .001, 'The classifier returned inconsistent class scores.')
    check(checks.decision !== 'rejected' && !reasons.includes('input-rejected'), 'A rejected image cannot carry model output.')
    const confidence = object(result.confidence)
    const top = scores.reduce((best, item) => item.value > best.value ? item : best)
    check(onlyKeys(confidence, ['top_label', 'probability', 'level', 'calibration', 'temperature', 'decision_threshold', 'normalized_entropy', 'margin', 'interpretation'])
      && confidence.top_label === top.label && finite(confidence.probability, 0, 1) && Math.abs((confidence.probability as number) - top.value) <= 1e-6
      && ['high', 'moderate', 'low'].includes(String(confidence.level)) && ['temperature-scaled', 'none'].includes(String(confidence.calibration))
      && (confidence.temperature === null || confidence.temperature === undefined || finite(confidence.temperature, .05, 20)) && finite(confidence.decision_threshold, 0, 1)
      && finite(confidence.normalized_entropy, 0, 1) && finite(confidence.margin, 0, 1) && confidence.interpretation === 'model-confidence-not-personal-risk', 'The model confidence summary is invalid.')
    if (result.outcome === 'finding') check(reasons.length === 0 && result.finding_label === top.label, 'A finding must name the top category.')
    else check(reasons.length > 0 && result.finding_label == null, 'An inconclusive result must state why.')
    if (result.heatmap != null) {
      const heatmap = object(result.heatmap)
      const meanings: Record<string, string> = { 'grad-cam': 'regions-that-raised-the-score', 'attention-rollout': 'patches-the-model-attended-to', 'occlusion-sensitivity': 'score-drop-under-occlusion' }
      check(onlyKeys(heatmap, ['method', 'target_label', 'class_specific', 'grid_width', 'grid_height', 'values', 'meaning', 'localization'])
        && typeof heatmap.method === 'string' && meanings[heatmap.method] === heatmap.meaning && heatmap.localization === false && typeof heatmap.class_specific === 'boolean'
        && scores.some(score => score.label === heatmap.target_label) && Number.isInteger(heatmap.grid_width) && Number.isInteger(heatmap.grid_height)
        && finite(heatmap.grid_width, 2, 32) && finite(heatmap.grid_height, 2, 32), 'The heatmap is unsupported.')
      check(Array.isArray(heatmap.values) && heatmap.values.length === (heatmap.grid_width as number) * (heatmap.grid_height as number) && heatmap.values.every(item => finite(item, 0, 1)), 'The heatmap grid is invalid.')
    }
    if (result.familiarity != null) {
      const familiarity = object(result.familiarity)
      check(onlyKeys(familiarity, ['method', 'similarity', 'minimum_similarity', 'familiar']) && familiarity.method === 'class-centroid-cosine' && finite(familiarity.similarity, -1, 1) && finite(familiarity.minimum_similarity, -1, 1) && typeof familiarity.familiar === 'boolean', 'The familiarity check is invalid.')
      check(familiarity.familiar || reasons.includes('unfamiliar-image'), 'An unfamiliar image must be reported as inconclusive.')
    }
    if (checks.findings.some(item => item.severity === 'limiting')) check(reasons.includes('input-quality'), 'A limited image must be reported as inconclusive.')
  }
  if (result.inference_ms != null) check(finite(result.inference_ms, 0), 'The measured inference time is invalid.')
  if (result.runtime != null) check(['onnxruntime-cpu', 'opencv-cpu'].includes(String(result.runtime)), 'The model runtime is unsupported.')
  if (result.model_info != null) {
    const info = object(result.model_info)
    check(Object.keys(info).length === 4 && typeof info.source_url === 'string' && /^https:\/\/[^\s]+$/.test(info.source_url) && info.source_url.length <= 500 && typeof info.license === 'string' && info.license.trim().length > 0 && info.license.length <= 120 && typeof info.evaluation_reference === 'string' && info.evaluation_reference.length <= 1000 && (info.patient_disjoint === null || typeof info.patient_disjoint === 'boolean'), 'The model evidence response is invalid.')
  }
  return { ...(result as unknown as CancerResult), scores, image_checks: checks }
}

export function researchRecord(subject: string, twinSubject: string | undefined, track: CancerTrack, modality: CancerModality, history: CancerHistory, image: ResearchImage | null, result: CancerResult | null) {
  check(/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(subject), 'Use a coded study subject ID: 1–64 letters, digits, underscores or hyphens.')
  check(pathways.find(path => path.id === track)?.modalities.includes(modality), 'The input does not match this pathway.')
  check(history.symptoms.length <= 2000 && history.duration.length <= 120 && history.prior_findings.length <= 2000, 'Shorten the history before exporting.')
  if (result) {
    check(image && result.input_sha256 === image.sha256 && result.track === track && result.modality === modality, 'The result does not match this research case.')
  }
  return {
    schema_version: 'humantwin-cancer-case-v2', use: 'research-only', created_at: new Date().toISOString(),
    subject_id: subject, twin_link: subject === twinSubject ? { subject_id: twinSubject, relationship: 'same-coded-subject' } : null,
    track, modality, history: { ...history, evidence_basis: 'user-entered-unverified' },
    image: image ? { sha256: image.sha256, width: image.width, height: image.height, format: 'image/jpeg',
      ...(image.originalWidth ? { original_width: image.originalWidth, original_height: image.originalHeight, resized: image.resized === true } : {}) } : null,
    inference_state: result ? 'experimental-model-output' : 'not-run', result,
    clinical_validation: false, cancer_diagnosis: null,
    limitations: ['Does not confirm or exclude cancer.', 'Model confidence is not a personal probability of cancer, even after calibration.', 'Only a single prepared 2D image is supported; no full-volume or multi-view screening.', 'History is recorded for review and is not analyzed by this classifier.'],
  }
}

export const ACCEPTED_TYPES = ['image/jpeg', 'image/png']
export const MAX_FILE_BYTES = 16 * 1024 * 1024

export async function readResearchImage(file: File): Promise<ResearchImage> {
  check(ACCEPTED_TYPES.includes(file.type) && file.size > 0 && file.size <= MAX_FILE_BYTES, 'Choose a JPEG or PNG image smaller than 16 MB. DICOM, NIfTI, PDF and scan volumes are not supported.')
  const dimensions = inspectImageDimensions(new Uint8Array(await file.arrayBuffer()))
  check(Math.min(dimensions.width, dimensions.height) >= 32 && Math.max(dimensions.width, dimensions.height) <= 8192 && dimensions.width * dimensions.height <= 40_000_000, 'Use an image of at least 32 pixels per side, at most 8192 pixels per side and at most 40 megapixels.')
  const bitmap = await createImageBitmap(file)
  try {
    check(Math.min(bitmap.width, bitmap.height) >= 32 && Math.max(bitmap.width, bitmap.height) <= 8192 && bitmap.width * bitmap.height <= 40_000_000, 'The decoded image is outside the supported size limits.')
    const factor = Math.min(1, 2048 / Math.max(bitmap.width, bitmap.height))
    check(Math.min(bitmap.width, bitmap.height) * factor >= 31.5, 'This image is too narrow to resize without distorting it. Prepare a less extreme crop.')
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(32, Math.round(bitmap.width * factor)); canvas.height = Math.max(32, Math.round(bitmap.height * factor))
    const context = canvas.getContext('2d')
    check(context, 'The browser could not prepare the image.')
    // Smooth downscaling matches the antialiased resize used when the models were trained.
    context.imageSmoothingEnabled = true; context.imageSmoothingQuality = 'high'
    context.fillStyle = '#fff'; context.fillRect(0, 0, canvas.width, canvas.height); context.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    let dataUrl = canvas.toDataURL('image/jpeg', .95)
    if (dataUrl.length > 1500000) dataUrl = canvas.toDataURL('image/jpeg', .85)
    check(dataUrl.length <= 1500000, 'The prepared image is too large. Use a smaller research export.')
    const bytes = Uint8Array.from(atob(dataUrl.split(',')[1]!), character => character.charCodeAt(0))
    const sha256 = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(byte => byte.toString(16).padStart(2, '0')).join('')
    return { dataUrl, sha256, width: canvas.width, height: canvas.height, originalWidth: bitmap.width, originalHeight: bitmap.height, resized: factor < 1, name: file.name }
  } finally { bitmap.close() }
}

/** A small JPEG preview for saved reports (longest side 384 px). */
export async function makeThumbnail(image: ResearchImage, longest = 384): Promise<string> {
  const element = new Image()
  element.src = image.dataUrl
  await element.decode()
  const factor = Math.min(1, longest / Math.max(element.naturalWidth, element.naturalHeight))
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(element.naturalWidth * factor)); canvas.height = Math.max(1, Math.round(element.naturalHeight * factor))
  const context = canvas.getContext('2d')
  check(context, 'The browser could not prepare a preview.')
  context.imageSmoothingQuality = 'high'
  context.drawImage(element, 0, 0, canvas.width, canvas.height)
  return canvas.toDataURL('image/jpeg', .82)
}

export function inspectImageDimensions(bytes: Uint8Array) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  if (bytes.length >= 24 && bytes[0] === 137 && bytes[1] === 80 && bytes[2] === 78 && bytes[3] === 71 && view.getUint32(12) === 0x49484452) {
    return { width: view.getUint32(16), height: view.getUint32(20) }
  }
  check(bytes.length >= 4 && bytes[0] === 255 && bytes[1] === 216, 'This file is not a supported JPEG or PNG image.')
  let index = 2
  while (index + 4 <= bytes.length) {
    check(bytes[index] === 255, 'The JPEG header is invalid.')
    const marker = bytes[index + 1]!, size = view.getUint16(index + 2)
    check(size >= 2 && index + size + 2 <= bytes.length, 'The JPEG contains an invalid segment.')
    if ([192, 193, 194].includes(marker)) {
      check(size >= 8 && index + 9 <= bytes.length, 'The JPEG frame is incomplete.')
      return { width: view.getUint16(index + 7), height: view.getUint16(index + 5) }
    }
    if (marker === 218 || marker === 217) break
    index += size + 2
  }
  throw new Error('Image dimensions could not be verified before decoding.')
}
