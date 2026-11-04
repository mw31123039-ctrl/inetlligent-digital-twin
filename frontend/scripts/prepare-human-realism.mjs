/** Preserve the licensed rig and UVs; add original high-resolution head color and normal maps. */
import fs from 'node:fs/promises'
import path from 'node:path'
import { deflateSync } from 'node:zlib'
import { createHash } from 'node:crypto'
import { TGALoader } from 'three/addons/loaders/TGALoader.js'
import { cache, fetchSources } from './fetch-reference-sources.mjs'

await fetchSources()
const original = await fs.readFile('public/models/human.glb')
if (original.subarray(0, 4).toString() !== 'glTF') throw new Error('The source human must be GLB')
const jsonSize = original.readUInt32LE(12)
const document = JSON.parse(original.subarray(20, 20 + jsonSize).toString())
const binaryStart = 20 + jsonSize + 8
const binary = original.subarray(binaryStart, binaryStart + original.readUInt32LE(binaryStart - 8))
const chunks = [binary]; let offset = binary.length
const sha = bytes => createHash('sha256').update(bytes).digest('hex')
const table = Array.from({ length: 256 }, (_, n) => { for (let j = 0; j < 8; j++) n = n & 1 ? 0xEDB88320 ^ n >>> 1 : n >>> 1; return n >>> 0 })
function crc32(bytes) { let value = 0xFFFFFFFF; for (const byte of bytes) value = table[(value ^ byte) & 255] ^ value >>> 8; return (value ^ 0xFFFFFFFF) >>> 0 }
function pngChunk(name, bytes) {
  const type = Buffer.from(name), header = Buffer.alloc(4), crc = Buffer.alloc(4)
  header.writeUInt32BE(bytes.length); crc.writeUInt32BE(crc32(Buffer.concat([type, bytes])))
  return Buffer.concat([header, type, bytes, crc])
}
function png(texture) {
  const { width, height, data } = texture, stride = width * 4
  const rows = Buffer.alloc((stride + 1) * height)
  for (let y = 0; y < height; y++) {
    // Match GLTFExporter's original TGA/CanvasTexture flip, retaining the existing UV mapping.
    const sourceY = texture.flipY ? height - y - 1 : y
    const source = Buffer.from(data.buffer, data.byteOffset + sourceY * stride, stride)
    const target = y * (stride + 1)
    rows[target] = 1 // PNG Sub filter keeps the original pixels while reducing texture size.
    for (let x = 0; x < stride; x++) rows[target + 1 + x] = (source[x] - (x >= 4 ? source[x - 4] : 0)) & 255
  }
  const header = Buffer.alloc(13); header.writeUInt32BE(width); header.writeUInt32BE(height, 4); header[8] = 8; header[9] = 6
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), pngChunk('IHDR', header), pngChunk('IDAT', deflateSync(rows)), pngChunk('IEND', Buffer.alloc(0))])
}
function addImage(bytes, label) {
  const padding = Buffer.alloc((4 - offset % 4) % 4); chunks.push(padding); offset += padding.length
  const view = document.bufferViews.length; document.bufferViews.push({ buffer: 0, byteOffset: offset, byteLength: bytes.length })
  chunks.push(bytes); offset += bytes.length
  const image = document.images.length; document.images.push({ mimeType: 'image/png', bufferView: view, name: label })
  const texture = document.textures.length; document.textures.push({ source: image, sampler: 0, name: label })
  return texture
}
const sources = []
for (const name of ['m002_head_color.tga', 'm002_head_normal.tga', 'm002_body_normal.tga']) {
  const bytes = await fs.readFile(path.join(cache, name))
  const texture = new TGALoader().parse(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength))
  const index = addImage(png(texture), name.replace('.tga', ''))
  const material = document.materials.find(item => item.name === (name.includes('head') ? 'm002_head' : 'm002_body'))
  if (!material) throw new Error('Missing original human material')
  if (name.includes('normal')) material.normalTexture = { index, scale: name.includes('head') ? .55 : .65 }
  else material.pbrMetallicRoughness.baseColorTexture = { index, texCoord: 0 }
  sources.push({ file: name, sha256: sha(bytes), width: texture.width, height: texture.height })
}
for (const material of document.materials) material.pbrMetallicRoughness.roughnessFactor = material.name.includes('head') ? .56 : .77
document.buffers[0].byteLength = offset
document.asset.extras = { ...document.asset.extras, source: 'Microsoft Rocketbox Male_Adult_01', source_revision: '0943055db6ec570bcef9f2c8b41c9e5467c808f9', license: 'MIT', preparation: 'Original head color at 2048px, original skin/clothing normal maps at 2048px, retained rig/UVs, adjusted PBR roughness.' }
let json = Buffer.from(JSON.stringify(document)); json = Buffer.concat([json, Buffer.alloc((4 - json.length % 4) % 4, 32)])
let body = Buffer.concat(chunks); body = Buffer.concat([body, Buffer.alloc((4 - body.length % 4) % 4)])
const header = Buffer.alloc(12), jsonHeader = Buffer.alloc(8), bodyHeader = Buffer.alloc(8)
header.write('glTF'); header.writeUInt32LE(2, 4); header.writeUInt32LE(28 + json.length + body.length, 8)
jsonHeader.writeUInt32LE(json.length); jsonHeader.writeUInt32LE(0x4E4F534A, 4)
bodyHeader.writeUInt32LE(body.length); bodyHeader.writeUInt32LE(0x004E4942, 4)
const result = Buffer.concat([header, jsonHeader, json, bodyHeader, body])
await fs.writeFile('public/models/human-detailed.glb', result)
await fs.writeFile('public/models/human-detailed.manifest.json', JSON.stringify({ source_glb_sha256: sha(original), output_sha256: sha(result), bytes: result.length, sources, license: 'MIT', license_file: 'LICENSE-Rocketbox.txt', preparation: document.asset.extras }, null, 2))
console.log(`Textured 3D human ready: ${result.length} bytes; original rig and source human.glb retained.`)
