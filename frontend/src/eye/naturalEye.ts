/** Original presentation geometry. A lifelike rendering, not a patient scan. */
import * as T from 'three'
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js'

const radius = 1.16
const irisRadius = .56, pupilRadius = .18
const globeZ = (x: number, y: number) => Math.sqrt(Math.max(.015, radius * radius - x * x - y * y))
function noise(x: number, y = 0) { const value = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return value - Math.floor(value) }

function behindLids<M extends T.Material>(material: M): M {
  // The cornea protrudes in front of the globe. Clip its covered surface to the
  // eyelid aperture so a glass circle never draws through the surrounding skin.
  const enabled = { value: 1 }
  material.userData.lidMask = enabled
  material.onBeforeCompile = shader => {
    shader.uniforms.naturalLidMaskEnabled = enabled
    shader.vertexShader = 'varying vec3 vNaturalPosition;\n' + shader.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\nvNaturalPosition = transformed;')
    shader.fragmentShader = 'varying vec3 vNaturalPosition;\nuniform float naturalLidMaskEnabled;\n' + shader.fragmentShader.replace('#include <clipping_planes_fragment>', `#include <clipping_planes_fragment>
      float eyeX = vNaturalPosition.x / 1.10;
      float lidArc = sqrt(max(0.0, 1.0 - eyeX * eyeX));
      float lidTilt = vNaturalPosition.x * 0.045;
      if (naturalLidMaskEnabled > 0.5 && vNaturalPosition.z > 0.0 && (abs(eyeX) > 1.0 || vNaturalPosition.y > 0.48 * lidArc + lidTilt || vNaturalPosition.y < -0.35 * lidArc + lidTilt)) discard;
    `)
  }
  material.customProgramCacheKey = () => 'natural-eye-lid-aperture-v1'
  return material
}

function irisTexture() {
  // The CPU geometry evaluator does not instantiate browser image loaders.
  if (typeof document === 'undefined') { const data = new T.DataTexture(new Uint8Array([98, 63, 37, 255]), 1, 1); data.needsUpdate = true; return data }
  const texture = new T.TextureLoader().load(`${import.meta.env.BASE_URL}textures/eye/brown_eye.png`)
  texture.name = 'MakeHuman-CC0-reference-iris'
  texture.colorSpace = T.SRGBColorSpace; texture.anisotropy = 4
  texture.magFilter = T.LinearFilter; texture.minFilter = T.LinearMipmapLinearFilter; texture.generateMipmaps = true
  return texture
}

function skinNormal() {
  const size = 128, data = new Uint8Array(size * size * 4)
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const index = (y * size + x) * 4
    data[index] = 128 + (noise(x, y) - .5) * 36
    data[index + 1] = 128 + (noise(x + 9, y + 21) - .5) * 36
    data[index + 2] = 253; data[index + 3] = 255
  }
  const texture = new T.DataTexture(data, size, size)
  texture.wrapS = texture.wrapT = T.RepeatWrapping; texture.repeat.set(8, 3); texture.needsUpdate = true
  return texture
}

function aperture(angle: number) {
  const x = Math.cos(angle) * 1.10
  const y = Math.sin(angle) * (Math.sin(angle) >= 0 ? .48 : .35) + x * .045
  return new T.Vector3(x, y, globeZ(x, y) + .035)
}

function skinPatch(upper: boolean) {
  const positions: number[] = [], normals: number[] = [], colors: number[] = [], uv: number[] = [], indices: number[] = []
  const angular = 96, rings = 22
  const skin = new T.Color('#c99b83'), edge = new T.Color('#ad715e')
  for (let ring = 0; ring <= rings; ring++) for (let step = 0; step <= angular; step++) {
    const t = ring / rings, angle = step / angular * Math.PI + (upper ? 0 : Math.PI)
    const inner = aperture(angle), outer = new T.Vector3(Math.cos(angle) * 2.05, Math.sin(angle) * 1.3 + .05, .11)
    const point = inner.clone().lerp(outer, t)
    point.z += Math.sin(t * Math.PI) * (.18 + (upper ? -.02 : .03) * Math.sin(angle) ** 2)
    // Shallow lid fold and orbital volume instead of cylindrical eyelid pieces.
    if (upper) point.z -= Math.exp(-(((t - .19) / .045) ** 2)) * .035 * Math.sin(angle)
    const color = skin.clone().lerp(edge, Math.exp(-t * 13) * .24)
    color.multiplyScalar(.98 + noise(step, ring) * .035)
    positions.push(point.x, point.y, point.z); normals.push(0, 0, 1)
    colors.push(color.r, color.g, color.b, t < .86 ? 1 : (1 - t) / .14)
    uv.push(step / angular, t)
    if (ring < rings && step < angular) {
      const a = ring * (angular + 1) + step, b = a + angular + 1
      indices.push(a, b, a + 1, b, b + 1, a + 1)
    }
  }
  const geometry = new T.BufferGeometry()
  geometry.setAttribute('position', new T.Float32BufferAttribute(positions, 3)); geometry.setAttribute('normal', new T.Float32BufferAttribute(normals, 3))
  geometry.setAttribute('color', new T.Float32BufferAttribute(colors, 4)); geometry.setAttribute('uv', new T.Float32BufferAttribute(uv, 2))
  geometry.setIndex(indices); geometry.computeVertexNormals()
  return geometry
}

function tube(points: T.Vector3[], thickness: number, material: T.Material, taper = false) {
  const curve = new T.CatmullRomCurve3(points)
  const geometry = new T.TubeGeometry(curve, 18, thickness, 5, false)
  if (taper) {
    const positions = geometry.getAttribute('position')
    for (let index = 0; index < positions.count; index++) {
      const t = Math.floor(index / 6) / 18, center = curve.getPointAt(t)
      const point = new T.Vector3().fromBufferAttribute(positions, index).sub(center).multiplyScalar(1 - t * .95).add(center)
      positions.setXYZ(index, point.x, point.y, point.z)
    }
    geometry.computeVertexNormals()
  }
  return new T.Mesh(geometry, material)
}

function irisGeometry() {
  const segments = 192, rings = 22, positions: number[] = [], uv: number[] = [], indices: number[] = []
  for (let ring = 0; ring <= rings; ring++) for (let step = 0; step <= segments; step++) {
    const v = ring / rings, a = step / segments * Math.PI * 2, r = pupilRadius + v * (irisRadius - pupilRadius)
    const x = Math.cos(a) * r, y = Math.sin(a) * r
    positions.push(x, y, 1.042 - v * .015 + Math.sin(a * 79 + v * 8) * .0017)
    // Select the original iris in the unchanged 1024px MakeHuman eye atlas.
    uv.push((724 + x / irisRadius * 112) / 1024, 1 - (301 - y / irisRadius * 112) / 1024)
    if (ring < rings && step < segments) {
      const current = ring * (segments + 1) + step, next = current + segments + 1
      indices.push(current, current + 1, next, next, current + 1, next + 1)
    }
  }
  const geometry = new T.BufferGeometry()
  geometry.setAttribute('position', new T.Float32BufferAttribute(positions, 3)); geometry.setAttribute('uv', new T.Float32BufferAttribute(uv, 2))
  geometry.setIndex(indices); geometry.computeVertexNormals(); return geometry
}

function corneaGeometry() {
  const positions: number[] = [], uv: number[] = [], indices: number[] = []
  const rings = 28, segments = 96
  for (let ring = 0; ring <= rings; ring++) for (let step = 0; step <= segments; step++) {
    const r = ring / rings * .576, a = step / segments * Math.PI * 2
    const z = 1.022 + .155 * Math.sqrt(Math.max(0, 1 - (r / .61) ** 2))
    positions.push(Math.cos(a) * r, Math.sin(a) * r, z); uv.push(step / segments, ring / rings)
    if (ring < rings && step < segments) { const p = ring * (segments + 1) + step, n = p + segments + 1; indices.push(p, n, p + 1, p + 1, n, n + 1) }
  }
  const geometry = new T.BufferGeometry(); geometry.setAttribute('position', new T.Float32BufferAttribute(positions, 3)); geometry.setAttribute('uv', new T.Float32BufferAttribute(uv, 2))
  geometry.setIndex(indices); geometry.computeVertexNormals(); return geometry
}

export function naturalEyeStructures(side: 'left' | 'right'): Map<string, T.Group> {
  const parts = new Map<string, T.Group>()
  const group = (id: string) => { const object = new T.Group(); object.userData.natural = true; parts.set(`eye.${id}`, object); return object }
  const skin = new T.MeshPhysicalMaterial({ color: '#ffffff', vertexColors: true, normalMap: skinNormal(), normalScale: new T.Vector2(.2, .2), roughness: .62, metalness: 0, sheen: .18, sheenColor: new T.Color('#f1c0a4'), transparent: true, alphaTest: .02, side: T.DoubleSide })
  group('upper-eyelid').add(new T.Mesh(skinPatch(true), skin))
  group('lower-eyelid').add(new T.Mesh(skinPatch(false), skin))
  const wet = new T.MeshPhysicalMaterial({ color: '#bc8375', roughness: .27, clearcoat: .8, clearcoatRoughness: .12 })
  const margins = group('eyelid-margin')
  for (const upper of [true, false]) margins.add(tube(Array.from({ length: 49 }, (_, i) => aperture(i / 48 * Math.PI + (upper ? 0 : Math.PI))), .019, wet))
  const lashes = group('eyelashes'), lashGeometries: T.BufferGeometry[] = []
  const lashMaterial = new T.MeshStandardMaterial({ color: '#2d241f', roughness: .7 })
  for (const upper of [true, false]) for (let index = 0; index < (upper ? 54 : 30); index++) {
    const count = upper ? 54 : 30, a = .13 + index / (count - 1) * (Math.PI - .26) + (upper ? 0 : Math.PI)
    const start = aperture(a), direction = upper ? 1 : -1, length = (upper ? .19 : .105) * (.65 + noise(index, upper ? 1 : 2) * .5)
    const hair = tube([start, start.clone().add(new T.Vector3(Math.cos(a) * .035, direction * length * .6, .09)), start.clone().add(new T.Vector3(Math.cos(a) * .075, direction * length, .19))], upper ? .0065 : .004, lashMaterial, true)
    lashGeometries.push(hair.geometry)
  }
  const merged = mergeGeometries(lashGeometries)
  if (merged) lashes.add(new T.Mesh(merged, lashMaterial))
  lashGeometries.forEach(geometry => geometry.dispose())
  // A recessed, light-absorbing chamber behind a genuine annular iris opening.
  const pupil = group('pupil')
  const pupilBorder = new T.TorusGeometry(pupilRadius, .0025, 6, 96); pupilBorder.translate(0, 0, 1.045)
  pupil.add(new T.Mesh(pupilBorder, behindLids(new T.MeshBasicMaterial({ color: '#33271b' }))))
  const hit = new T.Mesh(new T.CircleGeometry(pupilRadius, 64), new T.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false, side: T.DoubleSide }))
  hit.position.z = 1.048; hit.userData.annotationOnly = true; pupil.add(hit)
  const sclera = new T.SphereGeometry(radius, 96, 64, 0, Math.PI * 2, Math.asin((irisRadius + .003) / radius), Math.PI - Math.asin((irisRadius + .003) / radius))
  sclera.rotateX(Math.PI / 2)
  const white = group('sclera')
  white.add(new T.Mesh(sclera, behindLids(new T.MeshPhysicalMaterial({ color: '#eee6d9', roughness: .29, metalness: 0, clearcoat: .5, clearcoatRoughness: .16 }))))
  white.add(new T.Mesh(new T.SphereGeometry(.965, 48, 32), behindLids(new T.MeshBasicMaterial({ color: '#090705' }))))
  group('iris').add(new T.Mesh(irisGeometry(), behindLids(new T.MeshPhysicalMaterial({ color: '#ffffff', map: irisTexture(), roughness: .64, clearcoat: .12, side: T.DoubleSide }))))
  const limbusGeometry = new T.TorusGeometry(irisRadius + .002, .012, 10, 128); limbusGeometry.translate(0, 0, 1.027)
  const limbus = new T.Mesh(limbusGeometry, behindLids(new T.MeshStandardMaterial({ color: '#554c39', roughness: .4 })))
  group('limbus').add(limbus)
  const cornea = new T.Mesh(corneaGeometry(), behindLids(new T.MeshPhysicalMaterial({ color: '#ffffff', transmission: .98, thickness: .035, ior: 1.376, roughness: .055, metalness: 0, clearcoat: .55, clearcoatRoughness: .08, side: T.DoubleSide })))
  cornea.userData.pickThrough = true; group('cornea').add(cornea)
  const film = group('tear-film')
  film.add(tube(Array.from({ length: 41 }, (_, i) => aperture(Math.PI + .25 + i / 40 * (Math.PI - .5)).add(new T.Vector3(0, .014, .014))), .008, new T.MeshPhysicalMaterial({ color: '#f4d7c9', roughness: .04, clearcoat: 1, transparent: true, opacity: .65 })))
  const vessels = group('bulbar-conjunctiva')
  const vesselMaterial = behindLids(new T.MeshStandardMaterial({ color: '#ce9291', roughness: .48, transparent: true, opacity: .42 }))
  for (const direction of [-1, 1]) for (let index = 0; index < 7; index++) {
    const y = -.32 + index / 6 * .68
    const points = Array.from({ length: 11 }, (_, step) => {
      const t = step / 10, x = direction * (1.08 - t * (.34 + noise(index) * .15)), yy = y + Math.sin(t * 5 + index) * .025
      return new T.Vector3(x, yy, globeZ(x, yy) + .007)
    })
    vessels.add(tube(points, .0023 + noise(index) * .0015, vesselMaterial, true))
  }
  const nasal = side === 'left' ? -1 : 1
  for (const [id, x, y, size] of [['medial-canthus', -.99, -.035, .085], ['lateral-canthus', 1.085, .047, .047], ['lacrimal-caruncle', -.94, -.04, .054], ['upper-punctum', -.92, .15, .012], ['lower-punctum', -.93, -.14, .012]] as const) {
    const mesh = new T.Mesh(new T.SphereGeometry(1, 24, 18), new T.MeshPhysicalMaterial({ color: id.includes('punctum') ? '#89574b' : '#c68b7e', roughness: .31, clearcoat: .5 }))
    mesh.position.set(x, y, globeZ(x, y) + .025); mesh.scale.set(size, size * .65, size * .45); group(id).add(mesh)
  }
  // This model's source coordinates put the nasal corner at -X for a patient's left eye.
  for (const object of parts.values()) object.scale.x = -nasal
  return parts
}
