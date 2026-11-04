/** Prepare only the selected CC BY-SA reference chest organs from Z-Anatomy. */
import fs from 'node:fs/promises'
import path from 'node:path'
import { createHash } from 'node:crypto'
import * as T from 'three'
import { FBXLoader } from 'three/addons/loaders/FBXLoader.js'
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js'
import { mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js'
import { cache } from './fetch-reference-sources.mjs'
const revision = '6c7f9016bd5899ac8edafd31b9900c151df42ed6'
const base = `https://raw.githubusercontent.com/LluisV/Z-Anatomy/${revision}/`
const inspectHeart = process.argv.includes('--inspect-heart')
const sourcePath = inspectHeart ? 'Resources/Models/FBX/CardioVascular41.fbx' : 'Resources/Models/FBX/VisceralSystem100.fbx'
const filename = path.join(cache, `Z-Anatomy-${revision}-${inspectHeart ? 'cardio' : 'visceral'}.fbx`)
const hash = bytes => createHash('sha256').update(bytes).digest('hex')
await fs.mkdir(cache, { recursive: true })
let bytes
try { bytes = await fs.readFile(filename) } catch {
  const response = await fetch(base + sourcePath, { signal: AbortSignal.timeout(180000) })
  if (!response.ok) throw new Error(`Z-Anatomy source: HTTP ${response.status}`)
  bytes = Buffer.from(await response.arrayBuffer()); await fs.writeFile(filename, bytes)
}
const license = await (await fetch(base + 'LICENSE')).text()
if (!/Attribution-ShareAlike 4.0/i.test(license)) throw new Error('The pinned source license needs review')
// The source FBX carries unrelated textures. Geometry selection uses original
// transforms and our illustrative materials; no source texture is needed.
const manager = new T.LoadingManager()
class GeometryOnlyTextureLoader extends T.TextureLoader { load() { return new T.Texture() } }
manager.addHandler(/.*/, new GeometryOnlyTextureLoader(manager))
globalThis.window = { URL }
const original = new FBXLoader(manager).parse(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '')
original.updateMatrixWorld(true)
const meshes = []
original.traverse(child => { if (child instanceof T.Mesh) meshes.push(child) })
if (process.argv.includes('--inspect') || inspectHeart) {
  console.log(meshes.map(mesh => mesh.name).filter(name => inspectHeart ? /heart|ventric|atri[au]|myoc|aort|epicard/i.test(name) : /lung|pulm|heart|trach|cor_|bronch/i.test(name)).join('\n'))
  console.log(`Total source meshes: ${meshes.length}`)
  process.exit(0)
}
const lungNames = new Set(['Superior_lobe_of_right_lung', 'Middle_lobe_of_right_lung', 'Inferior_lobe_of_right_lung',
  'Superior_lobe_of_left_lung', 'Inferior_lobe_of_left_lung', 'Trachea', 'Right_main_bronchus', 'Left_main_bronchus'])
const selected = meshes.filter(mesh => lungNames.has(mesh.name))
if (selected.filter(mesh => /lobe_of_.*lung/.test(mesh.name)).length !== 5) throw new Error('All five named lung lobes are required')
const cardiacPath = 'Resources/Models/FBX/CardioVascular41.fbx'
const cardiacFile = path.join(cache, `Z-Anatomy-${revision}-cardio.fbx`)
let cardiacBytes
try { cardiacBytes = await fs.readFile(cardiacFile) } catch {
  const response = await fetch(base + cardiacPath, { signal: AbortSignal.timeout(180000) })
  if (!response.ok) throw new Error(`Cardiac source: HTTP ${response.status}`)
  cardiacBytes = Buffer.from(await response.arrayBuffer()); await fs.writeFile(cardiacFile, cardiacBytes)
}
const cardiac = new FBXLoader(manager).parse(cardiacBytes.buffer.slice(cardiacBytes.byteOffset, cardiacBytes.byteOffset + cardiacBytes.byteLength), '')
cardiac.updateMatrixWorld(true)
const heartNames = new Set(['Left_ventricle', 'Right_ventricle', 'Left_atrium', 'Right_atrium', 'Ascending_aorta', 'Aortic_arch',
  'Pulmonary_trunk', 'Superior_vena_cava', 'Anterior_interventricular_artery', 'Circumflex_artery_of_heart'])
cardiac.traverse(mesh => { if (mesh instanceof T.Mesh && heartNames.has(mesh.name)) selected.push(mesh) })
for (const name of ['Left_ventricle', 'Right_ventricle', 'Left_atrium', 'Right_atrium']) if (!selected.some(mesh => mesh.name === name)) throw new Error(`Missing cardiac surface: ${name}`)
const group = new T.Group(); group.name = 'Z-Anatomy-chest-surfaces'
const included = []; let triangles = 0
for (const source of selected) {
  const geometry = source.geometry.clone(); geometry.applyMatrix4(source.matrixWorld)
  geometry.deleteAttribute('normal'); geometry.deleteAttribute('uv'); geometry.deleteAttribute('color')
  const welded = mergeVertices(geometry, .00001); geometry.dispose(); welded.computeVertexNormals()
  const color = /lung/i.test(source.name) ? '#c98b8e' : /trach|bronch/i.test(source.name) ? '#d7c1a5' : /vena_cava/i.test(source.name) ? '#6b849d' : '#a65053'
  const mesh = new T.Mesh(welded, new T.MeshPhysicalMaterial({ color, roughness: .52, metalness: 0, clearcoat: .12, clearcoatRoughness: .4, side: T.DoubleSide }))
  mesh.name = source.name; group.add(mesh)
  triangles += (welded.index?.count ?? welded.getAttribute('position').count) / 3
  included.push(source.name)
}
const bounds = new T.Box3().setFromObject(group), size = bounds.getSize(new T.Vector3())
group.scale.setScalar(2.8 / Math.max(size.x, size.y, size.z)); group.updateMatrixWorld(true)
group.position.sub(new T.Box3().setFromObject(group).getCenter(new T.Vector3())); group.updateMatrixWorld(true)
globalThis.FileReader = class { readAsArrayBuffer(blob) { blob.arrayBuffer().then(result => { this.result = result; this.onloadend?.() }, error => this.onerror?.(error)) } }
const result = Buffer.from(await new GLTFExporter().parseAsync(group, { binary: true }))
const out = path.resolve('public/models/anatomy')
await fs.mkdir(out, { recursive: true })
await fs.writeFile(path.join(out, 'chest-surface.glb'), result)
await fs.writeFile(path.join(out, 'LICENSE-Z-Anatomy.txt'), license)
await fs.writeFile(path.join(out, 'chest-surface.manifest.json'), JSON.stringify({ source: 'Z-Anatomy / Lluís Vinent Juanico and contributors, based on Z-Anatomy by Gauthier Kervyn and BodyParts3D / DBCLS',
  source_url: base + sourcePath, revision, source_sha256: hash(bytes),
  sources: [{ url: base + sourcePath, sha256: hash(bytes) }, { url: base + cardiacPath, sha256: hash(cardiacBytes) }],
  output_sha256: hash(result), bytes: result.length, triangles, included_meshes: included,
  license: 'CC BY-SA 4.0', license_url: 'https://creativecommons.org/licenses/by-sa/4.0/',
  modifications: 'Selected chest-organ meshes only; retained FBX world transforms; welded duplicates and recomputed smooth normals; illustrative materials; uniform centering/scaling; GLB conversion. No patient-specific reconstruction. The included list is the scope of this derivative.' }, null, 2))
await fs.writeFile(path.join(out, 'ATTRIBUTION-Z-Anatomy.txt'), `Z-Anatomy reference chest-organ surfaces.\nLluís Vinent Juanico and contributors; based on Z-Anatomy by Gauthier Kervyn and BodyParts3D / DBCLS.\nSource revision: ${revision}\nSource: ${base + sourcePath}\nAdapted model asset: CC BY-SA 4.0, https://creativecommons.org/licenses/by-sa/4.0/\nOnly meshes listed in chest-surface.manifest.json are included. Source FBX is not redistributed by this application.\nChanges: selected organ geometry, preserved transforms, vertex welding/smooth normals, illustrative materials, centering/scaling and GLB conversion.\nKeep this attribution and LICENSE-Z-Anatomy.txt when redistributing this derivative model under CC BY-SA 4.0.\n`)
console.log(`Reference chest surfaces: ${selected.length} meshes, ${triangles} triangles, ${result.length} bytes. Names: ${included.join(', ')}`)
