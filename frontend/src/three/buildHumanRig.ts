import * as THREE from 'three'
import type { RegionId } from '../types'
import type { HumanModelConfig } from './humanViewerConfig'

/** Fit bone-bound interaction zones to a real skinned GLTF, never a substitute body. */
export function buildHumanRig(root: THREE.Group, clips: THREE.AnimationClip[], config: HumanModelConfig) {
  const bones = {} as Record<keyof HumanModelConfig['bones'], THREE.Bone>
  const skinned: THREE.SkinnedMesh[] = []
  const textures = new Set<THREE.Texture>()
  root.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return
    object.castShadow = true
    object.receiveShadow = true
    if (object instanceof THREE.SkinnedMesh) {
      object.frustumCulled = false
      skinned.push(object)
    }
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
      if (material instanceof THREE.MeshStandardMaterial && material.map) textures.add(material.map)
    }
  })
  if (!skinned.length || !textures.size) throw new Error('Human model: a skinned human mesh with skin textures is required.')
  for (const [key, name] of Object.entries(config.bones)) {
    const bone = root.getObjectByName(name)
    if (!(bone instanceof THREE.Bone)) throw new Error(`Human model: required rig bone "${name}" is missing. Update the model bone mapping.`)
    bones[key as keyof typeof bones] = bone
  }
  root.rotation.y += config.facingRotation ?? 0
  root.updateMatrixWorld(true)
  let box = new THREE.Box3().setFromObject(root)
  const height = box.max.y - box.min.y
  if (!Number.isFinite(height) || height <= 0) throw new Error('Human model: the mesh has invalid dimensions.')
  root.scale.multiplyScalar(1.8 / height)
  root.updateMatrixWorld(true)
  box = new THREE.Box3().setFromObject(root)
  root.position.sub(new THREE.Vector3((box.min.x + box.max.x) / 2, box.min.y, (box.min.z + box.max.z) / 2))
  root.updateMatrixWorld(true)

  // Lower the supplied A-pose to a relaxed standing posture through the actual rig.
  for (const bone of [bones.leftUpperArm, bones.rightUpperArm]) {
    const sign = Math.sign(bone.getWorldPosition(new THREE.Vector3()).x)
    const world = bone.getWorldQuaternion(new THREE.Quaternion())
    world.premultiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), -sign * (config.armRelaxation ?? 0)))
    const parent = bone.parent!.getWorldQuaternion(new THREE.Quaternion()).invert()
    bone.quaternion.copy(parent.multiply(world))
    root.updateMatrixWorld(true)
  }

  const zones: THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial>[] = []
  const geometry = new THREE.SphereGeometry(1, 24, 18)
  function zone(region: RegionId, bone: THREE.Bone, position: THREE.Vector3, scale: THREE.Vector3, rotation = new THREE.Quaternion()) {
    const material = new THREE.MeshBasicMaterial({ color: 0x14bac5, transparent: true, opacity: 0, depthWrite: false, colorWrite: false })
    const mesh = new THREE.Mesh(geometry, material)
    mesh.name = `selection_${region}_${zones.length}`
    mesh.userData.region = region
    mesh.position.copy(position)
    mesh.scale.copy(scale)
    mesh.quaternion.copy(rotation)
    mesh.updateMatrixWorld(true)
    bone.attach(mesh) // Preserves the fitted world transform; follows every subsequent bone animation.
    zones.push(mesh)
    return mesh
  }
  const worldPosition = (bone: THREE.Bone) => bone.getWorldPosition(new THREE.Vector3())
  function segment(region: RegionId, start: THREE.Bone, end: THREE.Bone, radius: number) {
    const a = worldPosition(start), b = worldPosition(end)
    return zone(region, start, a.clone().lerp(b, .5), new THREE.Vector3(radius, a.distanceTo(b) / 2 + radius * .35, radius), new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), a.sub(b).normalize()))
  }
  zone('head', bones.head, worldPosition(bones.head).add(new THREE.Vector3(0, .105, .012)), new THREE.Vector3(.087, .121, .097))
  const head = worldPosition(bones.head)
  for (const x of [-.033, .033]) zone('eyes', bones.head, head.clone().add(new THREE.Vector3(x, .099, .108)), new THREE.Vector3(.032, .021, .025))
  zone('chest', bones.chest, worldPosition(bones.chest).add(new THREE.Vector3(0, .075, .018)), new THREE.Vector3(.207, .142, .133))
  zone('abdomen', bones.spine, worldPosition(bones.spine).add(new THREE.Vector3(0, .105, .008)), new THREE.Vector3(.175, .164, .124))
  for (const side of ['left', 'right'] as const) {
    segment('arms', bones[`${side}UpperArm`], bones[`${side}Forearm`], .066)
    segment('arms', bones[`${side}Forearm`], bones[`${side}Hand`], .05)
    zone('arms', bones[`${side}Hand`], worldPosition(bones[`${side}Hand`]).add(new THREE.Vector3(side === 'left' ? .015 : -.015, -.06, .012)), new THREE.Vector3(.046, .092, .035))
    segment('legs', bones[`${side}Thigh`], bones[`${side}Shin`], .104)
    segment('legs', bones[`${side}Shin`], bones[`${side}Foot`], .072)
    zone('legs', bones[`${side}Foot`], worldPosition(bones[`${side}Foot`]).add(new THREE.Vector3(0, -.035, .065)), new THREE.Vector3(.06, .06, .14))
  }
  root.updateMatrixWorld(true)

  // Prefer only an explicitly configured, in-place clip. Other embedded clips may walk/dance.
  let idle = config.idleClip ? clips.find(clip => clip.name === config.idleClip) : undefined
  if (config.idleClip && !idle) throw new Error(`Human model: animation "${config.idleClip}" is missing.`)
  if (!idle) {
    const times = [0, 1.5, 3, 4.5, 6]
    const tracks: THREE.KeyframeTrack[] = []
    function rotation(bone: THREE.Bone, axis: THREE.Vector3, angles: number[]) {
      const rest = bone.quaternion.clone()
      const values = angles.flatMap(angle => rest.clone().multiply(new THREE.Quaternion().setFromAxisAngle(axis, angle)).toArray())
      tracks.push(new THREE.QuaternionKeyframeTrack(`${bone.name}.quaternion`, times, values))
    }
    rotation(bones.chest, new THREE.Vector3(0, 0, 1), [0, .006, 0, -.004, 0])
    rotation(bones.head, new THREE.Vector3(0, 1, 0), [0, .009, 0, -.007, 0])
    rotation(bones.leftUpperArm, new THREE.Vector3(0, 0, 1), [0, .006, 0, -.004, 0])
    rotation(bones.rightUpperArm, new THREE.Vector3(0, 0, 1), [0, -.005, 0, .004, 0])
    const scale = bones.chest.scale.clone()
    tracks.push(new THREE.VectorKeyframeTrack(`${bones.chest.name}.scale`, times, [1, 1.012, 1, .997, 1].flatMap(s => [scale.x, scale.y * s, scale.z * s])))
    idle = new THREE.AnimationClip('HumanTwin_BreathingIdle', 6, tracks)
  }

  let selected: RegionId | null = null
  function highlight(id: RegionId | null) {
    selected = id
    for (const mesh of zones) {
      const active = mesh.userData.region === id
      mesh.material.colorWrite = active
      mesh.material.opacity = active ? (id === 'eyes' ? .38 : .13) : 0
    }
  }
  function anchor(id: RegionId) {
    const matching = zones.filter(mesh => mesh.userData.region === id)
    // Use one side for limbs, and the right eye for a readable small-area callout.
    const point = matching[0]!.getWorldPosition(new THREE.Vector3())
    if (id === 'head') point.y += .07 // Forehead, separate from the small eye targets.
    return point
  }
  function pick(raycaster: THREE.Raycaster, cameraPosition: THREE.Vector3): RegionId | null {
    const hits = raycaster.intersectObjects(zones, false)
    for (const hit of hits) {
      const region = hit.object.userData.region as RegionId
      if (region === 'eyes') {
        // Do not select eyes through the back of the head.
        const forward = new THREE.Vector3(0, 0, 1).transformDirection(bones.head.matrixWorld)
        // Bone axes vary by source; use the actual fitted eye center relative to head instead.
        forward.copy(anchor('eyes')).sub(worldPosition(bones.head)).setY(0).normalize()
        if (cameraPosition.clone().sub(worldPosition(bones.head)).normalize().dot(forward) < .25) continue
      }
      return region
    }
    // A click on a visible surface outside a fitted zone still resolves by nearest zone,
    // but empty canvas clicks never select a region.
    const surface = raycaster.intersectObjects(skinned, false)[0]
    if (!surface) return null
    let nearest: RegionId | null = null, best = Infinity
    for (const mesh of zones) {
      if (mesh.userData.region === 'eyes') continue
      const distance = surface.point.distanceTo(mesh.getWorldPosition(new THREE.Vector3()))
      if (distance < best) { best = distance; nearest = mesh.userData.region as RegionId }
    }
    return nearest
  }
  function diagnostics() {
    const { mesh, index } = animatedSample
    mesh.skeleton.update()
    const vertex = mesh.getVertexPosition(index, new THREE.Vector3()).applyMatrix4(mesh.matrixWorld)
    return {
      skinnedMeshes: skinned.length, skinTextures: textures.size, bones: mesh.skeleton.bones.length,
      clip: idle!.name, selected, deformedVertex: vertex.toArray(),
      chestTransform: bones.chest.matrixWorld.elements.slice(),
      eyeAnchor: anchor('eyes').toArray(),
    }
  }
  // Choose a real chest vertex for diagnostics of skeletal deformation.
  const chestSurface = worldPosition(bones.chest).add(new THREE.Vector3(0, .08, .1))
  let animatedSample = { mesh: skinned[0]!, index: 0 }, nearestSample = Infinity
  for (const mesh of skinned) {
    mesh.skeleton.update()
    const indices = mesh.geometry.index
    const count = indices?.count ?? mesh.geometry.attributes.position!.count
    for (let i = 0; i < count; i += 3) {
      const index = indices ? indices.getX(i) : i
      const point = mesh.getVertexPosition(index, new THREE.Vector3()).applyMatrix4(mesh.matrixWorld)
      const distance = point.distanceToSquared(chestSurface)
      if (distance < nearestSample) { nearestSample = distance; animatedSample = { mesh, index } }
    }
  }
  return { root, idle, highlight, anchor, pick, diagnostics }
}
