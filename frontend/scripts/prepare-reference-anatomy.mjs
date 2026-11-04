/** Fetch only selected ZIP entries from the official DBCLS archive, then export local GLBs. */
import fs from 'node:fs/promises'
import path from 'node:path'
import { inflateRawSync } from 'node:zlib'
import { createHash } from 'node:crypto'
import * as T from 'three'
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js'
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js'
import { mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js'
import { cache, fetchSources } from './fetch-reference-sources.mjs'

await fetchSources()
const archive = 'https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/isa_BP3D_4.0_obj_99.zip'
const output = path.resolve('public/models/anatomy')
await fs.mkdir(output, { recursive: true })
await fs.mkdir(path.join(cache, 'objects'), { recursive: true })
const sha = data => createHash('sha256').update(data).digest('hex')

async function range(start, end) {
  let last
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      const response = await fetch(archive, { headers: { Range: `bytes=${start}-${end}` }, signal: AbortSignal.timeout(60000) })
      if (response.status !== 206) throw new Error(`ZIP range request: HTTP ${response.status}`)
      return { bytes: Buffer.from(await response.arrayBuffer()), etag: response.headers.get('etag') }
    } catch (error) { last = error }
  }
  throw last
}

let index
try { index = JSON.parse(await fs.readFile(path.join(cache, 'zip-index.json'), 'utf8')) }
catch {
  const response = await fetch(archive, { headers: { Range: 'bytes=-65557' }, signal: AbortSignal.timeout(60000) })
  if (response.status !== 206) throw new Error('The archive server must support range requests')
  const tail = Buffer.from(await response.arrayBuffer())
  let end = tail.length - 22
  while (end >= 0 && tail.readUInt32LE(end) !== 0x06054b50) end--
  if (end < 0) throw new Error('ZIP end directory not found')
  const size = tail.readUInt32LE(end + 12), offset = tail.readUInt32LE(end + 16)
  const { bytes: directory } = await range(offset, offset + size - 1)
  const entries = []
  for (let position = 0; position + 46 <= directory.length && directory.readUInt32LE(position) === 0x02014b50;) {
    const n = directory.readUInt16LE(position + 28), extra = directory.readUInt16LE(position + 30), comment = directory.readUInt16LE(position + 32)
    entries.push({ name: directory.subarray(position + 46, position + 46 + n).toString(), method: directory.readUInt16LE(position + 10),
      compressed: directory.readUInt32LE(position + 20), uncompressed: directory.readUInt32LE(position + 24),
      offset: directory.readUInt32LE(position + 42), crc: directory.readUInt32LE(position + 16) })
    position += 46 + n + extra + comment
  }
  index = { url: archive, etag: response.headers.get('etag'), entries }
  await fs.writeFile(path.join(cache, 'zip-index.json'), JSON.stringify(index))
}
if (index.url !== archive) throw new Error('Archive index source mismatch')
const entries = new Map(index.entries.map(entry => [path.basename(entry.name, '.obj'), entry]))
const definitions = new Map()
for (const filename of ['isa_element_parts.txt', 'partof_element_parts.txt']) {
  const lines = (await fs.readFile(path.join(cache, filename), 'utf8')).split(/\r?\n/).slice(1)
  for (const line of lines) {
    const [fma, name, fj] = line.split('\t')
    if (!fj) continue
    if (!definitions.has(name)) definitions.set(name, { fma, name, elements: new Set() })
    definitions.get(name).elements.add(fj)
  }
}
const structure = (name, color) => {
  const definition = definitions.get(name)
  if (!definition) throw new Error(`Missing source concept: ${name}`)
  return { ...definition, elements: [...definition.elements].filter(id => entries.has(id)), color }
}
const models = {
  head: [['cerebellum', '#c18d86'], ['brainstem', '#dcc2a4'], ['brain', '#d5a6a0']],
  chest: [['heart', '#a54f52'], ['right lung', '#cf9596'], ['left lung', '#cb8e91'], ['trachea', '#d9c2a7'], ['sternum', '#ded0b8']],
  abdomen: [['liver', '#925b4a'], ['stomach', '#d4a093'], ['small intestine', '#cba092'], ['large intestine', '#b68d80'], ['right kidney', '#975551'], ['left kidney', '#975551']]
}
for (const side of ['right', 'left']) for (const ordinal of ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth', 'eleventh', 'twelfth']) {
  models.chest.push([`${side} ${ordinal} rib`, '#ddd0b8'])
}
for (const side of ['right', 'left']) {
  models[`arms-${side}`] = [[`${side} humerus`, '#dfd4bc'], [`${side} radius`, '#e4d7bc'], [`${side} ulna`, '#ddd0b5'],
    [`short head of ${side} biceps brachii`, '#b8786e'], [`long head of ${side} biceps brachii`, '#b8786e']]
  models[`legs-${side}`] = [[`${side} femur`, '#dfd4bc'], [`${side} tibia`, '#e4d7bc'], [`${side} fibula`, '#ddd0b5'], [`${side} patella`, '#e4d7bc'],
    [`medial head of ${side} gastrocnemius`, '#b8786e'], [`lateral head of ${side} gastrocnemius`, '#b37569']]
}
const prepared = Object.fromEntries(Object.entries(models).map(([name, items]) => [name, items.map(([label, color]) => structure(label, color))]))
const wanted = [...new Set(Object.values(prepared).flatMap(items => items.flatMap(item => item.elements)))]
console.log(`Preparing ${wanted.length} source elements for ${Object.keys(models).length} regional models; downloading ZIP subsets only.`)
const crcTable = Array.from({ length: 256 }, (_, n) => { for (let j = 0; j < 8; j++) n = n & 1 ? 0xEDB88320 ^ n >>> 1 : n >>> 1; return n >>> 0 })
function crc32(bytes) { let crc = 0xFFFFFFFF; for (const byte of bytes) crc = crcTable[(crc ^ byte) & 255] ^ crc >>> 8; return (crc ^ 0xFFFFFFFF) >>> 0 }
const fingerprints = new Map()
let cursor = 0, complete = 0
await Promise.all(Array.from({ length: 6 }, async () => {
  while (cursor < wanted.length) {
    const id = wanted[cursor++], entry = entries.get(id), filename = path.join(cache, 'objects', `${id}.obj`)
    let object
    try { object = await fs.readFile(filename); if (object.length !== entry.uncompressed || crc32(object) !== entry.crc) throw new Error('Stale object') }
    catch {
      const result = await range(entry.offset, entry.offset + entry.compressed + Buffer.byteLength(entry.name) + 2048)
      if (index.etag && result.etag !== index.etag) throw new Error('The upstream archive changed; refresh the recorded source snapshot')
      const bytes = result.bytes
      if (bytes.readUInt32LE(0) !== 0x04034b50) throw new Error(`${id}: invalid local ZIP header`)
      const start = 30 + bytes.readUInt16LE(26) + bytes.readUInt16LE(28)
      const compressed = bytes.subarray(start, start + entry.compressed)
      object = entry.method === 8 ? inflateRawSync(compressed) : compressed
      if (object.length !== entry.uncompressed || crc32(object) !== entry.crc) throw new Error(`${id}: ZIP integrity mismatch`)
      await fs.writeFile(filename, object)
    }
    fingerprints.set(id, sha(object)); complete++
    if (complete % 50 === 0 || complete === wanted.length) console.log(`Verified ${complete}/${wanted.length} elements`)
  }
}))

// GLTFExporter's binary writer uses FileReader; Node supplies Blob but no FileReader.
globalThis.FileReader = class {
  readAsArrayBuffer(blob) { blob.arrayBuffer().then(result => { this.result = result; this.onloadend?.() }, error => this.onerror?.(error)) }
}
const manifest = { dataset: 'BodyParts3D 4.0 / IS-A 99% polygon-reduced meshes', archive, archive_etag: index.etag,
  attribution: 'BodyParts3D, © The Database Center for Life Science licensed under CC Attribution 4.0 International',
  license_url: 'https://creativecommons.org/licenses/by/4.0/', official_license: 'https://dbarchive.biosciencedbc.jp/en/bodyparts3d/lic.html',
  modifications: 'Selected original meshes; welded duplicate position vertices and recomputed smooth normals; source Z-up to Y-up with anterior -Y mapped to +Z; uniform regional centering/scaling; illustrative PBR colors and subtle vertex variation; exported GLB. No polygon decimation or patient-specific reconstruction.',
  models: {} }
for (const [name, items] of Object.entries(prepared)) {
  const root = new T.Group(); root.name = `BodyParts3D-${name}`
  const used = new Set(); let triangles = 0
  const included = []
  for (const item of items) for (const id of item.elements) {
    if (used.has(id)) continue
    used.add(id)
    const object = new OBJLoader().parse(await fs.readFile(path.join(cache, 'objects', `${id}.obj`), 'utf8'))
    object.name = `${item.name} / ${id}`; object.userData = { fma: item.fma, source_element: id, source_sha256: fingerprints.get(id) }
    object.traverse(child => {
      if (!(child instanceof T.Mesh)) return
      child.geometry.deleteAttribute('normal'); child.geometry.deleteAttribute('uv')
      const welded = mergeVertices(child.geometry, .00001); child.geometry.dispose(); child.geometry = welded
      child.geometry.computeVertexNormals()
      const position = child.geometry.getAttribute('position'), colors = []
      const color = new T.Color(item.color)
      for (let i = 0; i < position.count; i++) {
        const variation = 1 + Math.sin(position.getX(i) * .037 + position.getY(i) * .051 + position.getZ(i) * .019) * .035
        colors.push(color.r * variation, color.g * variation, color.b * variation)
      }
      child.geometry.setAttribute('color', new T.Uint8BufferAttribute(colors.map(value => Math.round(Math.min(1, value) * 255)), 3, true))
      const rib = name === 'chest' && (/\brib\b/.test(item.name) || item.name === 'sternum')
      child.material = new T.MeshPhysicalMaterial({ color: '#ffffff', vertexColors: true, roughness: .49, metalness: 0, clearcoat: .15, clearcoatRoughness: .4,
        transparent: rib, opacity: rib ? .28 : 1, depthWrite: !rib })
      triangles += (child.geometry.index?.count ?? position.count) / 3
    })
    root.add(object); included.push({ id, fma: item.fma, name: item.name, sha256: fingerprints.get(id) })
  }
  if (!used.size) throw new Error(`${name}: no source geometry`)
  root.rotation.x = -Math.PI / 2; root.updateMatrixWorld(true)
  const original = new T.Box3().setFromObject(root), dimensions = original.getSize(new T.Vector3())
  root.scale.setScalar(2.8 / Math.max(dimensions.x, dimensions.y, dimensions.z)); root.updateMatrixWorld(true)
  root.position.sub(new T.Box3().setFromObject(root).getCenter(new T.Vector3())); root.updateMatrixWorld(true)
  const bytes = Buffer.from(await new GLTFExporter().parseAsync(root, { binary: true }))
  await fs.writeFile(path.join(output, `${name}.glb`), bytes)
  manifest.models[name] = { file: `${name}.glb`, bytes: bytes.length, sha256: sha(bytes), triangles, source_bounds: { min: original.min.toArray(), max: original.max.toArray() }, elements: included }
  console.log(`${name}: ${used.size} source meshes, ${triangles} triangles, ${bytes.length} bytes`)
}
await fs.writeFile(path.join(output, 'manifest.json'), JSON.stringify(manifest, null, 2))
await fs.writeFile(path.join(output, 'ATTRIBUTION.txt'), `${manifest.attribution}\n\nSource: ${archive}\nOfficial current license: ${manifest.official_license}\nLicense: ${manifest.license_url}\n\n${manifest.modifications}\nDetailed source identifiers, hashes and transformations are recorded in manifest.json.\nThese reference anatomical assets are educational and are not patient scans or clinically validated by this application.\n`)
console.log(`Anatomical reference models ready: ${output}`)
