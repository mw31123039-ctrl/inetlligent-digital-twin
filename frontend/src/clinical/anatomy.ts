import type { AnatomyNode, ClinicalLocale, ClinicalSide } from './types'

export type Vec3 = [number, number, number]
export type BoneKey = 'hips' | 'spine' | 'chest' | 'neck' | 'head' | 'leftUpperArm' | 'leftForearm' | 'leftHand' | 'rightUpperArm' | 'rightForearm' | 'rightHand'
  | 'leftThigh' | 'leftShin' | 'leftFoot' | 'rightThigh' | 'rightShin' | 'rightFoot'
const LIMB: Record<string, [BoneKey, BoneKey]> = {
  upperArm: ['leftUpperArm', 'rightUpperArm'], forearm: ['leftForearm', 'rightForearm'], hand: ['leftHand', 'rightHand'],
  thigh: ['leftThigh', 'rightThigh'], shin: ['leftShin', 'rightShin'], foot: ['leftFoot', 'rightFoot'],
}

function boneFor(name: string, side: 'left' | 'right'): BoneKey {
  const limb = LIMB[name]
  return limb ? limb[side === 'left' ? 0 : 1] : (name as BoneKey)
}

/**
 * World positions for an ontology node's illustrative marker(s) on the reference body.
 * Convention (contracts/clinical/anatomy.v1.json): +x is the patient's LEFT and lateral offsets are written for
 * the left side, so the patient's right mirrors x and uses the right-hand bones. Fixed-side nodes (teeth,
 * liver area) use their offset exactly as given. A lateral node with no known side gets both markers.
 */
export function anchorPositions(node: AnatomyNode, side: ClinicalSide, bone: (key: BoneKey) => Vec3): Vec3[] {
  const anchor = node.anchor
  if (!anchor) return []
  const sides: ('left' | 'right')[] = node.lateral ? (side === 'left' || side === 'right' ? [side] : ['left', 'right']) : ['left']
  return sides.map(current => {
    const mirror = node.lateral && current === 'right' ? -1 : 1
    const start = bone(boneFor(anchor.bone, current))
    const end = anchor.to ? bone(boneFor(anchor.to, current)) : start
    const t = anchor.to ? anchor.t ?? .5 : 0
    const base: Vec3 = [start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t, start[2] + (end[2] - start[2]) * t]
    return [base[0] + anchor.offset[0] * mirror, base[1] + anchor.offset[1], base[2] + anchor.offset[2]]
  })
}

export function nodeLabel(nodes: Map<string, AnatomyNode>, id: string, locale: ClinicalLocale) {
  const node = nodes.get(id)
  return node ? node.label[locale] || node.label.en : id
}

export function regionOf(nodes: Map<string, AnatomyNode>, id: string): string {
  let current = nodes.get(id)
  while (current?.parent) current = nodes.get(current.parent)
  return current?.id ?? id
}

export function isWithin(nodes: Map<string, AnatomyNode>, id: string, ancestor: string) {
  let current = nodes.get(id)
  while (current) {
    if (current.id === ancestor) return true
    current = current.parent ? nodes.get(current.parent) : undefined
  }
  return false
}

/** Sides that make sense for a node: lateral → left/right/both, fixed side → that side only, otherwise midline. */
export function sideChoices(node: AnatomyNode | undefined): ClinicalSide[] {
  if (!node) return ['unknown']
  if (node.fixed_side) return [node.fixed_side]
  return node.lateral ? ['left', 'right', 'both', 'unknown'] : ['midline']
}
