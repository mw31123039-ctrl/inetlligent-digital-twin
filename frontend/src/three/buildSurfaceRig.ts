import * as T from 'three'
import type { RegionId } from '../types'
import type { PatientSide } from '../data/bodyParts'

/** Static scan interaction. Region locations are illustrative, not measured anatomy. */
export function buildSurfaceRig(root: T.Group, anatomy: boolean, facingRotation = 0) {
  const surfaces: T.Mesh[] = [], textures = new Set<T.Texture>()
  let bones = 0, skinned = 0
  root.traverse(object => {
    if (object instanceof T.Light) object.visible = false
    if (!(object instanceof T.Mesh)) return
    surfaces.push(object); object.castShadow = true; object.receiveShadow = true
    if (object instanceof T.SkinnedMesh) { object.frustumCulled = false; bones += object.skeleton.bones.length; skinned++ }
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
      if (material instanceof T.MeshStandardMaterial && material.map) textures.add(material.map)
    }
  })
  if (!surfaces.length) throw new Error('Human model: this file does not contain a visible human mesh.')
  root.rotation.y += facingRotation; root.updateMatrixWorld(true)
  let box = new T.Box3().setFromObject(root)
  const size = box.getSize(new T.Vector3())
  if (![...box.min.toArray(), ...box.max.toArray()].every(Number.isFinite) || size.y <= 0 || size.x <= 0 || size.z <= 0) throw new Error('Human model: the mesh has invalid dimensions.')
  root.scale.multiplyScalar(1.8 / size.y); root.updateMatrixWorld(true)
  box = new T.Box3().setFromObject(root)
  root.position.sub(new T.Vector3((box.min.x + box.max.x) / 2, box.min.y, (box.min.z + box.max.z) / 2)); root.updateMatrixWorld(true)
  box = new T.Box3().setFromObject(root)
  const anchors: Record<RegionId, T.Vector3> = {
    eyes: new T.Vector3(.033, 1.68, box.max.z), head: new T.Vector3(0, 1.7, 0),
    chest: new T.Vector3(0, 1.34, 0), abdomen: new T.Vector3(0, 1.06, 0),
    arms: new T.Vector3(box.max.x * .8, 1.15, 0), legs: new T.Vector3(.13, .5, 0),
  }
  const regionBounds = new Map<string, T.Box3>()
  if (anatomy) for (const mesh of surfaces) {
    const id = mesh.userData.bodyRegion as RegionId, side = mesh.userData.patientSide
    if (!id) continue
    const key = id + (side ? '-' + side : '')
    if (!regionBounds.has(key)) regionBounds.set(key, new T.Box3())
    regionBounds.get(key)!.expandByObject(mesh)
  }
  for (const [key, bounds] of regionBounds) {
    const id = key.split('-')[0] as RegionId
    if (!key.endsWith('-right')) anchors[id] = bounds.getCenter(new T.Vector3())
  }
  function anchor(id: RegionId, side?: PatientSide) {
    const bounds = regionBounds.get(id + (side ? '-' + side : ''))
    const point = bounds ? bounds.getCenter(new T.Vector3()) : anchors[id].clone()
    if (!anatomy && side && ['eyes', 'arms', 'legs'].includes(id)) point.x = Math.abs(point.x) * (side === 'left' ? 1 : -1)
    return point
  }
  const marker = new T.Mesh(new T.SphereGeometry(.055, 20, 14), new T.MeshBasicMaterial({ color: '#32b9a4', transparent: true, opacity: .2, depthWrite: false }))
  marker.visible = false; marker.name = 'Approximate selected body area'
  if (anatomy) { marker.geometry.dispose(); marker.material.dispose() }
  else { marker.position.copy(anchors.chest); root.attach(marker) }
  let selected: RegionId | null = null, lastSide: PatientSide | undefined
  function highlight(id: RegionId | null, side?: PatientSide) {
    selected = id; lastSide = side
    marker.visible = !!id && !anatomy
    if (id && !anatomy) { marker.position.copy(root.worldToLocal(anchor(id, side))); marker.scale.setScalar(1 / Math.abs(root.getWorldScale(new T.Vector3()).x)) }
    if (anatomy) for (const mesh of surfaces) for (const material of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
      if (material instanceof T.MeshStandardMaterial) {
        const active = mesh.userData.bodyRegion === id && (!side || !mesh.userData.patientSide || mesh.userData.patientSide === side)
        material.emissive.set(active ? '#185c50' : '#000000'); material.emissiveIntensity = active ? .65 : 0
      }
    }
  }
  function intersection(ray: T.Raycaster) { return ray.intersectObjects(surfaces, false)[0] }
  function pick(ray: T.Raycaster, _camera: T.Vector3): RegionId | null {
    const hit = intersection(ray)
    if (!hit) return null
    if (anatomy) return hit.object.userData.bodyRegion ?? null
    const { x, y } = hit.point
    if (y > 1.51) return 'head'
    if (y < .88) return 'legs'
    if (Math.abs(x) > Math.max(.23, box.max.x * .55)) return 'arms'
    return y > 1.2 ? 'chest' : 'abdomen'
  }
  function pickSide(ray: T.Raycaster, id: RegionId): PatientSide | undefined {
    if (!['eyes', 'arms', 'legs'].includes(id)) return undefined
    const hit = intersection(ray)
    if (!hit) return undefined
    return hit.object.userData.patientSide ?? (hit.point.x >= 0 ? 'left' : 'right')
  }
  function diagnostics() {
    return { skinnedMeshes: skinned, skinTextures: textures.size, skinNormalMaps: 0, headTextureWidth: 0, bones,
      clip: null, selected, selectedSide: lastSide, regionAnchors: Object.keys(anchors).length,
      bodyKind: anatomy ? 'anatomy' : 'personal', referenceMeshCount: surfaces.length,
      framingHalfWidth: box.getSize(new T.Vector3()).x / 2 + .1 }
  }
  return { root, idle: undefined as T.AnimationClip | undefined, highlight, anchor, pick, pickSide, diagnostics }
}
