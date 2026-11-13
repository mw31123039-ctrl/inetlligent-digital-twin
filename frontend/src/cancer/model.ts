export type CancerTrack = 'skin' | 'oral' | 'lung' | 'breast'
export type CancerModality = 'skin_photo' | 'dermoscopy' | 'oral_photo' | 'lung_ct_slice' | 'mammogram' | 'breast_ultrasound' | 'breast_mri_slice'
export interface ModelStatus {
  modality: CancerModality
  configured: boolean
  state: 'not-configured' | 'configured-unvalidated' | 'invalid-artifacts' | 'service-unavailable'
  model_version?: string
  target?: string
  weights_sha256?: string
}
export interface CancerStatus { available: boolean; pathways: { track: CancerTrack; models: ModelStatus[] }[] }
export interface OcclusionExplanation {
  method: 'occlusion-sensitivity'
  target_label: string
  grid_size: 4 | 6
  values: number[]
  meaning: 'score-drop-under-occlusion'
  localization: false
  max_score_drop?: number
}
export interface CancerResult {
  schema_version: 'humantwin-cancer-result-v1'
  track: CancerTrack
  modality: CancerModality
  model_version: string
  target: string
  weights_sha256: string
  input_sha256: string
  scores: { label: string; value: number }[]
  clinical_validation: false
  calibrated_cancer_probability: false
  scope: 'single-2d-image'
  external_requests: false
  inference_ms?: number | null
  runtime?: 'onnxruntime-cpu' | 'opencv-cpu' | null
  uncertainty?: { normalized_entropy: number; margin: number; interpretation: 'research-only' } | null
  explanation?: OcclusionExplanation | null
  image_checks?: { width: number; height: number; brightness: number; contrast: number; warnings: string[] } | null
  model_info?: { source_url: string; license: string; evaluation_reference: string; patient_disjoint: boolean | null } | null
}
export interface ResearchImage { dataUrl: string; sha256: string; width: number; height: number; originalWidth?: number; originalHeight?: number; resized?: boolean }
export interface CancerHistory { symptoms: string; duration: string; family_history: 'unknown' | 'yes' | 'no'; tobacco_exposure: 'unknown' | 'yes' | 'no'; prior_findings: string }

export const modalities: Record<CancerModality, { label: string; scope: string }> = {
  skin_photo: { label: 'Skin photograph', scope: 'Visible lesion photographs require a model evaluated on ordinary skin photos.' },
  dermoscopy: { label: 'Dermoscopic image', scope: 'A dermoscope image requires a model evaluated on dermoscopy. A phone photograph is a different input.' },
  oral_photo: { label: 'Mouth photograph', scope: 'Visible oral tissue only. A tooth-outline model cannot assess oral cancer.' },
  lung_ct_slice: { label: 'Lung CT slice export', scope: 'One prepared 8-bit CT slice for research. This cannot screen a CT volume, reconstruct a tumor or rule out lung cancer.' },
  mammogram: { label: 'Mammogram export', scope: 'One prepared 8-bit mammogram image for research. Full-resolution DICOM, multiple views and clinical mammography workflows are not supported.' },
  breast_ultrasound: { label: 'Breast ultrasound export', scope: 'One prepared ultrasound image requires its own ultrasound model. It cannot be assessed by a mammography model.' },
  breast_mri_slice: { label: 'Breast MRI slice export', scope: 'One prepared 8-bit MRI slice for research. Volumes, sequences and contrast timing are not supported.' },
}
export const pathways: { id: CancerTrack; label: string; icon: string; summary: string; modalities: CancerModality[]; source: string; sourceTitle: string; needs: string }[] = [
  { id: 'skin', label: 'Skin', icon: 'scan', summary: 'Skin lesions and dermoscopic images', modalities: ['skin_photo', 'dermoscopy'], source: 'https://www.cancer.gov/types/skin/patient/skin-screening-pdq', sourceTitle: 'NCI: Skin cancer screening', needs: 'Expert-labeled images, diagnosis references and evaluation across skin tones, devices and independent patients.' },
  { id: 'oral', label: 'Oral', icon: 'tooth', summary: 'Visible mouth and oral tissue', modalities: ['oral_photo'], source: 'https://www.cancer.gov/types/head-and-neck/patient/oral-screening-pdq', sourceTitle: 'NCI: Oral cancer screening', needs: 'Reviewed oral lesion photos with diagnostic references and independent patient testing. Dental crown detection is a separate task.' },
  { id: 'lung', label: 'Lung', icon: 'chest', summary: 'Prepared CT slices for research', modalities: ['lung_ct_slice'], source: 'https://www.cancer.gov/types/lung/patient/lung-screening-pdq', sourceTitle: 'NCI: Lung cancer screening', needs: 'Radiologist-reviewed CT data and independent patient testing. Clinical use needs a volume-aware model and validated DICOM preprocessing.' },
  { id: 'breast', label: 'Breast', icon: 'layers', summary: 'Mammography, ultrasound and MRI exports', modalities: ['mammogram', 'breast_ultrasound', 'breast_mri_slice'], source: 'https://www.cancer.gov/types/breast/screening', sourceTitle: 'NCI: Breast cancer screening', needs: 'A separate model for each imaging modality, reviewed diagnostic references and independent patient testing.' },
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
      return { modality, configured: true, state: 'configured-unvalidated', model_version: model.model_version, weights_sha256: model.weights_sha256, target: model.target }
    }) }
  }) }
}

export function acceptResult(value: unknown, track: CancerTrack, modality: CancerModality, inputHash: string, expected: ModelStatus): CancerResult {
  const result = object(value)
  const allowed = ['schema_version', 'track', 'modality', 'model_version', 'target', 'weights_sha256', 'input_sha256', 'scores', 'clinical_validation', 'calibrated_cancer_probability', 'scope', 'external_requests', 'inference_ms', 'runtime', 'uncertainty', 'explanation', 'image_checks', 'model_info']
  check(Object.keys(result).every(key => allowed.includes(key)), 'The classifier returned unsupported fields.')
  check(expected.configured && result.schema_version === 'humantwin-cancer-result-v1' && result.track === track && result.modality === modality && pathways.find(path => path.id === track)?.modalities.includes(modality), 'The result belongs to a different pathway.')
  check(hash.test(inputHash) && result.input_sha256 === inputHash && result.model_version === expected.model_version && result.weights_sha256 === expected.weights_sha256 && result.target === expected.target, 'The image or model changed. Check model status and run again.')
  check(result.clinical_validation === false && result.calibrated_cancer_probability === false && result.scope === 'single-2d-image' && result.external_requests === false, 'The model returned unsupported clinical claims.')
  check(Array.isArray(result.scores) && result.scores.length >= 2 && result.scores.length <= 20, 'The classifier returned an invalid score vector.')
  const scores = result.scores.map(item => {
    const score = object(item)
    check(Object.keys(score).length === 2 && typeof score.label === 'string' && score.label.trim().length > 0 && score.label.length <= 80 && typeof score.value === 'number' && Number.isFinite(score.value) && score.value >= 0 && score.value <= 1, 'The classifier returned invalid scores.')
    return { label: score.label, value: score.value }
  })
  check(new Set(scores.map(item => item.label)).size === scores.length && Math.abs(scores.reduce((sum, item) => sum + item.value, 0) - 1) <= .001, 'The classifier returned inconsistent class scores.')
  const finite = (value: unknown, minimum: number, maximum = Number.MAX_VALUE): value is number => typeof value === 'number' && Number.isFinite(value) && value >= minimum && value <= maximum
  if (result.inference_ms != null) check(finite(result.inference_ms, 0), 'The measured inference time is invalid.')
  if (result.runtime != null) check(['onnxruntime-cpu', 'opencv-cpu'].includes(String(result.runtime)), 'The model runtime is unsupported.')
  if (result.uncertainty != null) {
    const uncertainty = object(result.uncertainty)
    check(Object.keys(uncertainty).length === 3 && finite(uncertainty.normalized_entropy, 0, 1) && finite(uncertainty.margin, 0, 1) && uncertainty.interpretation === 'research-only', 'The model uncertainty response is invalid.')
  }
  if (result.explanation !== undefined && result.explanation !== null) {
    const explanation = object(result.explanation)
    check(Object.keys(explanation).every(key => ['method', 'target_label', 'grid_size', 'values', 'meaning', 'localization', 'max_score_drop'].includes(key)) && explanation.method === 'occlusion-sensitivity' && explanation.meaning === 'score-drop-under-occlusion' && explanation.localization === false && [4, 6].includes(Number(explanation.grid_size)) && typeof explanation.grid_size === 'number' && typeof explanation.target_label === 'string' && scores.some(score => score.label === explanation.target_label), 'The sensitivity explanation is unsupported.')
    check(Array.isArray(explanation.values) && explanation.values.length === explanation.grid_size * explanation.grid_size && explanation.values.every(value => finite(value, 0, 1)), 'The sensitivity grid is invalid.')
    if (explanation.max_score_drop !== undefined) check(finite(explanation.max_score_drop, 0, 1), 'The measured sensitivity magnitude is invalid.')
  }
  if (result.image_checks != null) {
    const checks = object(result.image_checks)
    check(Object.keys(checks).length === 5 && Number.isInteger(checks.width) && finite(checks.width, 32, 2048) && Number.isInteger(checks.height) && finite(checks.height, 32, 2048) && finite(checks.brightness, 0, 255) && finite(checks.contrast, 0), 'The image measurements are invalid.')
    check(Array.isArray(checks.warnings) && checks.warnings.length <= 20 && checks.warnings.every(warning => typeof warning === 'string' && warning.length > 0 && warning.length <= 300), 'The image warnings are invalid.')
  }
  if (result.model_info != null) {
    const info = object(result.model_info)
    check(Object.keys(info).length === 4 && typeof info.source_url === 'string' && /^https:\/\/[^\s]+$/.test(info.source_url) && info.source_url.length <= 500 && typeof info.license === 'string' && info.license.trim().length > 0 && info.license.length <= 120 && typeof info.evaluation_reference === 'string' && info.evaluation_reference.length <= 1000 && (info.patient_disjoint === null || typeof info.patient_disjoint === 'boolean'), 'The model evidence response is invalid.')
  }
  return { ...result, scores } as CancerResult
}

export function researchRecord(subject: string, twinSubject: string | undefined, track: CancerTrack, modality: CancerModality, history: CancerHistory, image: ResearchImage | null, result: CancerResult | null) {
  check(/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(subject), 'Use a coded study subject ID: 1–64 letters, digits, underscores or hyphens.')
  check(pathways.find(path => path.id === track)?.modalities.includes(modality), 'The input does not match this pathway.')
  check(history.symptoms.length <= 2000 && history.duration.length <= 120 && history.prior_findings.length <= 2000, 'Shorten the history before exporting.')
  if (result) {
    check(image && result.input_sha256 === image.sha256 && result.track === track && result.modality === modality, 'The result does not match this research case.')
  }
  return {
    schema_version: 'humantwin-cancer-case-v1', use: 'research-only', created_at: new Date().toISOString(),
    subject_id: subject, twin_link: subject === twinSubject ? { subject_id: twinSubject, relationship: 'same-coded-subject' } : null,
    track, modality, history: { ...history, evidence_basis: 'user-entered-unverified' },
    image: image ? { sha256: image.sha256, width: image.width, height: image.height, format: 'image/jpeg',
      ...(image.originalWidth ? { original_width: image.originalWidth, original_height: image.originalHeight, resized: image.resized === true } : {}) } : null,
    inference_state: result ? 'experimental-model-output' : 'not-run', result,
    clinical_validation: false, cancer_diagnosis: null,
    limitations: ['Does not confirm or exclude cancer.', 'Class scores are not calibrated personal cancer probabilities.', 'Only a single prepared 2D image is supported; no full-volume or multi-view screening.', 'History is recorded for review and is not analyzed by this classifier.'],
  }
}

export async function readResearchImage(file: File): Promise<ResearchImage> {
  check(['image/jpeg', 'image/png'].includes(file.type) && file.size > 0 && file.size <= 16 * 1024 * 1024, 'Choose a de-identified JPEG or PNG smaller than 16 MB. DICOM, NIfTI, PDFs and scan volumes are not supported.')
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
    context.fillStyle = '#fff'; context.fillRect(0, 0, canvas.width, canvas.height); context.drawImage(bitmap, 0, 0)
    let dataUrl = canvas.toDataURL('image/jpeg', .95)
    if (dataUrl.length > 1500000) dataUrl = canvas.toDataURL('image/jpeg', .85)
    check(dataUrl.length <= 1500000, 'The prepared image is too large. Use a smaller research export.')
    const bytes = Uint8Array.from(atob(dataUrl.split(',')[1]!), character => character.charCodeAt(0))
    const sha256 = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(byte => byte.toString(16).padStart(2, '0')).join('')
    return { dataUrl, sha256, width: canvas.width, height: canvas.height, originalWidth: bitmap.width, originalHeight: bitmap.height, resized: factor < 1 }
  } finally { bitmap.close() }
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
