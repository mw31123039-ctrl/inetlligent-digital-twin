import type { RegionId } from '../types'

export type HumanView = 'front' | 'back' | 'left' | 'right'

export interface HumanModelConfig {
  url: string
  /** Rotation around Y applied before framing. The model should face +Z. */
  facingRotation?: number
  /** Optional source A-pose adjustment in radians; zero for an already relaxed rig. */
  armRelaxation?: number
  /** Bone names are asset-specific; this mapping is the replacement boundary. */
  bones: Record<'hips' | 'spine' | 'chest' | 'neck' | 'head' | 'leftUpperArm' | 'leftForearm' | 'leftHand' | 'rightUpperArm' | 'rightForearm' | 'rightHand' | 'leftThigh' | 'leftShin' | 'leftFoot' | 'rightThigh' | 'rightShin' | 'rightFoot', string>
  idleClip?: string
}

export const humanModelConfig: HumanModelConfig = {
  url: `${import.meta.env.BASE_URL}models/human.glb`,
  armRelaxation: .46,
  bones: {
    hips: 'Bip01_Pelvis', spine: 'Bip01_Spine', chest: 'Bip01_Spine2', neck: 'Bip01_Neck', head: 'Bip01_Head',
    leftUpperArm: 'Bip01_L_UpperArm', leftForearm: 'Bip01_L_Forearm', leftHand: 'Bip01_L_Hand',
    rightUpperArm: 'Bip01_R_UpperArm', rightForearm: 'Bip01_R_Forearm', rightHand: 'Bip01_R_Hand',
    leftThigh: 'Bip01_L_Thigh', leftShin: 'Bip01_L_Calf', leftFoot: 'Bip01_L_Foot',
    rightThigh: 'Bip01_R_Thigh', rightShin: 'Bip01_R_Calf', rightFoot: 'Bip01_R_Foot',
  },
}

export const regionLabels: Record<RegionId, string> = { eyes: 'Eyes', head: 'Head', chest: 'Chest', abdomen: 'Abdomen', arms: 'Arms', legs: 'Legs' }
export const viewAngles: Record<HumanView, number> = { front: 0, back: Math.PI, left: Math.PI / 2, right: -Math.PI / 2 }

export function viewFromAngle(angle: number): HumanView {
  const wrapped = Math.atan2(Math.sin(angle), Math.cos(angle))
  if (Math.abs(wrapped) < Math.PI / 4) return 'front'
  if (Math.abs(wrapped) > Math.PI * .75) return 'back'
  return wrapped > 0 ? 'left' : 'right'
}
