import type { Group } from 'three'
import type { RegionId } from '../types'
import eyeAnatomy from '../../../contracts/eye/anatomy.v1.json'

export type PatientSide = 'left' | 'right'
export type AnatomyView = 'front' | 'side' | 'section'
export interface BodyPartConfig {
  label: string
  singular: string
  paired: boolean
  description: string
  structures: string[]
  camera: [number, number, number]
  focusDistance: number
  model: { kind: 'procedural'; load: () => Promise<(side: PatientSide) => Group> } | { kind: 'gltf'; url: string; sideUrls?: Record<PatientSide, string>; alternateUrl?: string }
  illustrations: Partial<Record<AnatomyView, string>>
}
const illustrations = (id: RegionId) => Object.fromEntries(['front', 'side', 'section'].map(view => [view, `${import.meta.env.BASE_URL}illustrations/${id}-${view}.svg`]))
const model = (id: RegionId): BodyPartConfig['model'] => ({ kind: 'procedural', load: async () => {
  const { buildAnatomy } = await import('../three/anatomyModels')
  return side => buildAnatomy(id, side)
} })
const reference = (id: RegionId, paired = false): BodyPartConfig['model'] => ({ kind: 'gltf',
  url: `${import.meta.env.BASE_URL}models/anatomy/${id}${paired ? '-left' : ''}.glb`,
  ...(paired ? { sideUrls: { left: `${import.meta.env.BASE_URL}models/anatomy/${id}-left.glb`, right: `${import.meta.env.BASE_URL}models/anatomy/${id}-right.glb` } } : {}) })

/** Asset/camera boundary: an API can supply GLB URLs without changing either viewer. */
export const bodyParts: Record<RegionId, BodyPartConfig> = {
  eyes: { label: 'Eyes', singular: 'eye', paired: true, description: 'Explore 63 selectable eye structures, with internal and magnified layers', structures: eyeAnatomy.structures.map(s=>s.label.en), camera: [0, .12, 4.4], focusDistance: .42, model: model('eyes'), illustrations: illustrations('eyes') },
  head: { label: 'Head', singular: 'head', paired: false, description: 'Reference brain geometry, cerebellum and brainstem', structures: ['Cerebrum', 'Cerebellum', 'Brainstem'], camera: [.3, .2, 4.9], focusDistance: .62, model: reference('head'), illustrations: illustrations('head') },
  chest: { label: 'Chest', singular: 'chest', paired: false, description: 'Reference organs, with a separate vascular and rib view', structures: ['Lungs', 'Heart', 'Trachea', 'Ribs'], camera: [.2, .1, 5.7], focusDistance: .95,
    model: { kind: 'gltf', url: `${import.meta.env.BASE_URL}models/anatomy/chest-surface.glb`, alternateUrl: `${import.meta.env.BASE_URL}models/anatomy/chest.glb` }, illustrations: illustrations('chest') },
  abdomen: { label: 'Abdomen', singular: 'abdomen', paired: false, description: 'Reference digestive organs and kidneys', structures: ['Liver', 'Stomach', 'Intestines', 'Kidneys'], camera: [0, .1, 5.5], focusDistance: .85, model: reference('abdomen'), illustrations: illustrations('abdomen') },
  arms: { label: 'Arms', singular: 'arm', paired: true, description: 'Reference bones and biceps, with source left and right models', structures: ['Humerus', 'Radius', 'Ulna', 'Biceps'], camera: [0, 0, 6.7], focusDistance: .85, model: reference('arms', true), illustrations: illustrations('arms') },
  legs: { label: 'Legs', singular: 'leg', paired: true, description: 'Reference bones, knee and calf muscles', structures: ['Femur', 'Tibia', 'Fibula', 'Patella'], camera: [0, 0, 6.9], focusDistance: 1.05, model: reference('legs', true), illustrations: illustrations('legs') },
}
export function partLabel(id: RegionId, side: PatientSide) {
  return bodyParts[id].paired ? `${side === 'left' ? 'Left' : 'Right'} ${bodyParts[id].singular}` : bodyParts[id].label
}
