import * as T from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { disposeScene } from './disposeScene'
import type { RegionId } from '../types'

const parts = ['head', 'chest', 'abdomen', 'arms-left', 'arms-right', 'legs-left', 'legs-right'] as const

/** Undo only regional centering/scale. Preserve the common source's Z-up -> Y-up rotation. */
export function restoreAnatomySourcePose(scene: T.Group, name: typeof parts[number]) {
  const source = scene.getObjectByName('BodyParts3D-' + name)
  if (!source || scene.children.length !== 1) throw new Error('Human model: the reference anatomy source transform could not be verified.')
  source.position.set(0, 0, 0); source.scale.set(1, 1, 1)
  source.updateMatrixWorld(true)
  const region = name.split('-')[0] as RegionId
  scene.traverse(object => {
    if (object instanceof T.Mesh) {
      object.userData.bodyRegion = region
      object.userData.patientSide = name.endsWith('-left') ? 'left' : name.endsWith('-right') ? 'right' : undefined
    }
  })
  return scene
}

export async function loadAnatomyOverview(manager: T.LoadingManager) {
  const results = await Promise.allSettled(parts.map(async name => {
    const gltf = await new GLTFLoader(manager).loadAsync(`${import.meta.env.BASE_URL}models/anatomy/${name}.glb`)
    try { return restoreAnatomySourcePose(gltf.scene, name) } catch (error) { disposeScene(gltf.scene); throw error }
  }))
  const failed = results.find(result => result.status === 'rejected')
  if (failed) {
    for (const result of results) if (result.status === 'fulfilled') disposeScene(result.value)
    throw new Error('Human model: the reference organs and bones could not be loaded. Retry the anatomy view.')
  }
  const root = new T.Group(); root.name = 'BodyParts3D-common-coordinate-overview'
  for (const result of results) if (result.status === 'fulfilled') root.add(result.value)
  return root
}
