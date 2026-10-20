import * as THREE from 'three'

/** Shared resources are disposed once, including GLB image bitmaps and bone textures. */
export function disposeScene(root: THREE.Object3D) {
  const geometries = new Set<THREE.BufferGeometry>()
  const materials = new Set<THREE.Material>()
  const textures = new Set<THREE.Texture>()
  const skeletons = new Set<THREE.Skeleton>()
  root.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return
    geometries.add(object.geometry)
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
      materials.add(material)
      for (const value of Object.values(material)) if (value instanceof THREE.Texture) textures.add(value)
    }
    if (object instanceof THREE.SkinnedMesh) skeletons.add(object.skeleton)
  })
  geometries.forEach(geometry => geometry.dispose())
  materials.forEach(material => material.dispose())
  const images = new Set<ImageBitmap>()
  textures.forEach(texture => {
    if (typeof ImageBitmap !== 'undefined' && texture.image instanceof ImageBitmap) images.add(texture.image)
    texture.dispose()
  })
  images.forEach(bitmap => bitmap.close())
  skeletons.forEach(skeleton => skeleton.dispose())
}
