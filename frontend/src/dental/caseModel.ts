import library from '../../../contracts/dental/orthodontics.v1.json'
import type { Tooth } from './model'
import type { PhotoStudy } from './photoSimulation'

export interface OrthodonticCase {
  id: string; name: string; category: string; summary: string; recognition: string[]; review: string[]; limits: string; source_ids: string[]
  quiz: { question: string; options: string[]; answer_index: number; explanation: string }
}
export const orthodonticCases = library.cases as OrthodonticCase[]
export const orthodonticSources = library.sources
export const caseVersion = library.version
export const categories = ['all', 'alignment', 'vertical', 'sagittal', 'transverse', 'eruption', 'combined']
export const modelledCases = new Set(['crowding', 'spacing', 'diastema', 'deep-bite', 'anterior-open-bite', 'posterior-open-bite', 'underbite', 'increased-overjet', 'anterior-crossbite', 'unilateral-posterior-crossbite', 'bilateral-posterior-crossbite', 'scissor-bite', 'class-ii-division-1', 'class-ii-division-2', 'class-iii', 'midline-discrepancy', 'rotated-teeth', 'missing-tooth', 'ectopic-eruption', 'relapse', 'asymmetry'])
export interface ToothEdit { x: number; y: number; z: number; rotation: number }
export interface DentalSimulation { caseId: string; intensity: number; alignment: number; edits: Record<number, ToothEdit> }
export const blankEdit = (): ToothEdit => ({ x: 0, y: 0, z: 0, rotation: 0 })
export function jawOffset(jaw: 'upper' | 'lower', simulation?: DentalSimulation) {
  const offset = { x: 0, y: 0, z: 0 }
  if (!simulation || jaw !== 'lower') return offset
  const k = Math.max(0, Math.min(1, simulation.intensity)) * (1 - Math.max(0, Math.min(1, simulation.alignment)))
  const id = simulation.caseId
  if (id === 'deep-bite' || id === 'class-ii-division-2') offset.y = .24 * k
  if (id === 'underbite' || id === 'class-iii') offset.z = .43 * k
  if (id === 'increased-overjet' || id === 'class-ii-division-1' || id === 'class-ii-division-2') offset.z = -.38 * k
  if (id === 'midline-discrepancy' || id === 'asymmetry') offset.x = .23 * k
  return offset
}

/** Dimensionless, deliberately exaggerated teaching poses; never patient measurements or biomechanical predictions. */
export function caseToothOffset(tooth: Tooth, simulation?: DentalSimulation) {
  const delta = { ...blankEdit(), hidden: false }
  if (!simulation) return delta
  const k = Math.max(0, Math.min(1, simulation.intensity)) * (1 - Math.max(0, Math.min(1, simulation.alignment)))
  const id = simulation.caseId, side = tooth.side === 'right' ? -1 : 1, anterior = tooth.position <= 3
  if ((id === 'crowding' || id === 'relapse') && tooth.position <= 4) {
    delta.x = -side * .07 * k; delta.z = (tooth.position % 2 ? -.19 : .12) * k; delta.rotation = side * (tooth.position % 2 ? 27 : -22) * k
  }
  if (id === 'spacing') delta.x = side * (.09 + (8 - tooth.position) * .022) * k
  if (id === 'diastema' && tooth.position === 1 && tooth.jaw === 'upper') delta.x = side * .17 * k
  if (id === 'anterior-open-bite' && anterior && tooth.jaw === 'lower') delta.y = -.3 * (1 - (tooth.position - 1) * .19) * k
  if (id === 'posterior-open-bite' && tooth.position >= 4 && tooth.jaw === 'lower') delta.y = -.22 * k
  if (id === 'anterior-crossbite' && tooth.fdi === 21) delta.z = -.43 * k
  if (['unilateral-posterior-crossbite', 'bilateral-posterior-crossbite'].includes(id) && tooth.jaw === 'upper' && tooth.position >= 4 && (id.startsWith('bilateral') || tooth.side === 'right')) delta.x = -side * .34 * k
  if (id === 'scissor-bite' && tooth.jaw === 'upper' && tooth.position >= 4 && tooth.side === 'left') delta.x = side * .36 * k
  if (id === 'rotated-teeth' && [12, 22, 33, 43].includes(tooth.fdi)) delta.rotation = side * 52 * k
  if (id === 'ectopic-eruption' && tooth.fdi === 13) { delta.y = .16 * k; delta.z = .3 * k; delta.rotation = 22 * k }
  if (id === 'missing-tooth' && tooth.fdi === 22) delta.hidden = true
  if (id === 'class-ii-division-2' && tooth.jaw === 'upper' && tooth.position === 1) delta.z = -.13 * k
  const edit = simulation.edits[tooth.fdi]
  if (edit) { delta.x += edit.x; delta.y += edit.y; delta.z += edit.z; delta.rotation += edit.rotation }
  return delta
}

const aliases: Record<string, string> = { crowded: 'crowding', spaced: 'spacing', 'open bite': 'anterior-open-bite', overbite: 'deep-bite', 'deep bite': 'deep-bite', 'under bite': 'underbite', crossbite: 'anterior-crossbite', 'gap teeth': 'diastema', 'class 2': 'class-ii-division-1', 'class 3': 'class-iii' }
export function findStudyCases(query: string): OrthodonticCase[] {
  const normalized = query.toLowerCase().trim()
  if (!normalized) return []
  const tokens = normalized.split(/[^a-z0-9]+/).filter(t => t.length > 2 && !['what', 'how', 'the', 'and', 'with', 'teeth', 'about', 'does', 'that', 'this', 'treat', 'fix', 'explain', 'can'].includes(t))
  return orthodonticCases.map(item => {
    const text = [item.name, item.summary, ...item.recognition].join(' ').toLowerCase()
    const alias = Object.entries(aliases).some(([term, id]) => normalized.includes(term) && item.id === id)
    return { item, score: (alias ? 10 : 0) + tokens.reduce((n, token) => n + (text.includes(token) ? 1 : 0), 0) }
  }).filter(row => row.score > 0).sort((a, b) => b.score - a.score).slice(0, 3).map(row => row.item)
}

export const photoViews = ['Frontal bite', 'Right bite', 'Left bite', 'Upper arch', 'Lower arch', 'Smile / profile'] as const
export interface PhotoMarker { x: number; y: number; tooth: number; note: string }
export interface CasePhoto { id: string; url: string; view: string; width: number; height: number; sha256: string; markers: PhotoMarker[]; study?: PhotoStudy }
export const validCaseId = (value: string) => /^[A-Za-z0-9_-]{1,48}$/.test(value)
export function photoSignature(bytes: Uint8Array) {
  if (bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) return 'image/jpeg'
  if ([137, 80, 78, 71, 13, 10, 26, 10].every((b, i) => bytes[i] === b)) return 'image/png'
  if (new TextDecoder().decode(bytes.slice(0, 4)) === 'RIFF' && new TextDecoder().decode(bytes.slice(8, 12)) === 'WEBP') return 'image/webp'
  throw new Error('Choose a genuine JPEG, PNG or WebP photo.')
}
export function researchPartition(subject: string): 'train' | 'validation' | 'test' {
  let hash = 2166136261
  for (const char of subject.trim().toLowerCase()) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619)
  const bucket = (hash >>> 0) % 10
  return bucket === 0 ? 'test' : bucket === 1 ? 'validation' : 'train'
}
export function downloadCase(value: unknown, filename: string, jsonl = false) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, jsonl ? undefined : 2) + '\n'], { type: jsonl ? 'application/x-ndjson' : 'application/json' }))
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename; anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
