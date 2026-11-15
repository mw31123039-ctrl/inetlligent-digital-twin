/** Local, self-contained GLB admission checks before any loader or texture request. */
export const personalModelLimits = { bytes: 40 * 1024 * 1024, triangles: 750000, imagePixels: 32 * 1024 * 1024 }

function imageSize(bytes: Uint8Array, mime: string): [number, number] {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  if (mime === 'image/png' && bytes.length >= 24 && view.getUint32(0) === 0x89504e47 && view.getUint32(4) === 0x0d0a1a0a) return [view.getUint32(16), view.getUint32(20)]
  if (mime === 'image/jpeg' && bytes[0] === 255 && bytes[1] === 216) {
    let offset = 2
    while (offset + 4 <= bytes.length) {
      if (bytes[offset] !== 255) break
      const marker = bytes[offset + 1]!, length = view.getUint16(offset + 2)
      if (length < 2 || offset + 2 + length > bytes.length || marker === 0xda || marker === 0xd9) break
      if ([0xc0, 0xc1, 0xc2].includes(marker) && length >= 8) return [view.getUint16(offset + 7), view.getUint16(offset + 5)]
      offset += 2 + length
    }
  }
  throw new Error('Embed valid PNG or JPEG textures in the GLB before attaching it.')
}

export function inspectPersonalGlb(buffer: ArrayBuffer) {
  const fail = (message = 'Use a valid, self-contained GLB 2.0 model.') => { throw new Error(message) }
  if (buffer.byteLength < 28 || buffer.byteLength > personalModelLimits.bytes) return fail('Choose a GLB model up to 40 MB.')
  const view = new DataView(buffer)
  if (view.getUint32(0, true) !== 0x46546c67 || view.getUint32(4, true) !== 2 || view.getUint32(8, true) !== buffer.byteLength || view.getUint32(16, true) !== 0x4e4f534a) return fail()
  const jsonLength = view.getUint32(12, true), binaryHeader = 20 + jsonLength
  if (!jsonLength || jsonLength > 2 * 1024 * 1024 || jsonLength % 4 || binaryHeader + 8 > buffer.byteLength || view.getUint32(binaryHeader + 4, true) !== 0x004e4942) return fail()
  const binaryLength = view.getUint32(binaryHeader, true), binaryStart = binaryHeader + 8
  if (binaryStart + binaryLength !== buffer.byteLength) return fail()
  let document: Record<string, any>
  try { document = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(new Uint8Array(buffer, 20, jsonLength))) } catch { return fail() }
  if (document?.asset?.version !== '2.0' || !Array.isArray(document.buffers) || document.buffers.length !== 1 || document.buffers.some((item: any) => item.uri !== undefined) || !Number.isInteger(document.buffers[0].byteLength) || document.buffers[0].byteLength < 1 || document.buffers[0].byteLength > binaryLength) return fail()
  const extensions = new Set(['KHR_materials_unlit', 'KHR_materials_clearcoat', 'KHR_materials_ior', 'KHR_materials_specular', 'KHR_materials_transmission', 'KHR_materials_volume', 'KHR_materials_sheen', 'KHR_materials_emissive_strength', 'KHR_texture_transform', 'KHR_mesh_quantization', 'KHR_lights_punctual'])
  if (document.extensionsRequired !== undefined && (!Array.isArray(document.extensionsRequired) || document.extensionsRequired.some((name: string) => !extensions.has(name)))) return fail('Export an uncompressed GLB with embedded PNG/JPEG textures. Draco, Meshopt, KTX2 and instanced assets are not supported here.')
  if (document.extensionsUsed !== undefined && !Array.isArray(document.extensionsUsed)) return fail()
  for (const name of document.extensionsUsed ?? []) if (/compression|meshopt|basisu|instancing/i.test(name)) return fail('Export an uncompressed GLB with embedded PNG/JPEG textures.')
  if (!Array.isArray(document.nodes) || !document.nodes.length || document.nodes.length > 2048 || !Array.isArray(document.meshes) || !document.meshes.length || document.meshes.length > 128 || !Array.isArray(document.accessors) || document.accessors.length > 4096 || !Array.isArray(document.bufferViews)) return fail('This model is too complex for the personal body viewer.')
  const parents = new Set<number>(), visiting = new Set<number>(), visited = new Set<number>()
  for (const node of document.nodes) {
    if (!node || typeof node !== 'object' || (node.children !== undefined && !Array.isArray(node.children))) return fail()
    for (const [key, count] of [['matrix',16],['translation',3],['scale',3],['rotation',4]] as const) if (node[key] !== undefined && (!Array.isArray(node[key]) || node[key].length !== count || !node[key].every(Number.isFinite))) return fail()
    for (const child of node.children ?? []) {
      if (!Number.isInteger(child) || child < 0 || child >= document.nodes.length || parents.has(child)) return fail('The model contains an invalid scene hierarchy.')
      parents.add(child)
    }
  }
  function visit(index: number, depth: number) {
    if (visiting.has(index) || depth > 128) return fail('The model contains a cyclic or excessively deep scene hierarchy.')
    if (visited.has(index)) return
    visiting.add(index)
    for (const child of document.nodes[index].children ?? []) visit(child, depth + 1)
    visiting.delete(index); visited.add(index)
  }
  for (let index = 0; index < document.nodes.length; index++) visit(index, 0)
  if (!Array.isArray(document.scenes) || !document.scenes.length || document.scenes.length > 16 || !Number.isInteger(document.scene ?? 0) || !document.scenes[document.scene ?? 0]) return fail()
  for (const scene of document.scenes) if (!Array.isArray(scene.nodes) || scene.nodes.some((index: number) => !Number.isInteger(index) || !document.nodes[index] || parents.has(index))) return fail()
  let accessorBytes = 0
  for (const accessor of document.accessors) {
    const components = ({ SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT2: 4, MAT3: 9, MAT4: 16 } as Record<string, number>)[accessor.type]
    if (!Number.isInteger(accessor.count) || accessor.count < 0 || accessor.count > 1000000 || !components) return fail('The model geometry exceeds the viewer limits.')
    accessorBytes += accessor.count * components * 4
  }
  if (accessorBytes > 128 * 1024 * 1024) return fail('The model geometry exceeds the viewer limits.')
  for (const item of document.bufferViews) if (item.buffer !== 0 || !Number.isInteger(item.byteLength) || item.byteLength < 0 || !Number.isInteger(item.byteOffset ?? 0) || (item.byteOffset ?? 0) < 0 || (item.byteOffset ?? 0) + item.byteLength > document.buffers[0].byteLength) return fail()
  let imagePixels = 0
  if (document.images !== undefined && (!Array.isArray(document.images) || document.images.length > 32)) return fail()
  for (const image of document.images ?? []) {
    if (image.uri !== undefined || !Number.isInteger(image.bufferView) || !document.bufferViews[image.bufferView]) return fail('Embed all textures in the GLB. External files and remote texture URLs are not loaded.')
    const item = document.bufferViews[image.bufferView]
    const [width, height] = imageSize(new Uint8Array(buffer, binaryStart + (item.byteOffset ?? 0), item.byteLength), image.mimeType)
    imagePixels += width * height
    if (!width || !height || width > 4096 || height > 4096 || imagePixels > personalModelLimits.imagePixels) return fail('Use textures up to 4096 pixels per side and reduce the total texture size.')
  }
  const meshTriangles = document.meshes.map((mesh: any) => {
    if (!Array.isArray(mesh.primitives) || mesh.primitives.length > 64) return fail()
    return mesh.primitives.reduce((count: number, primitive: any) => {
      if ((primitive.mode ?? 4) !== 4 || (primitive.targets?.length ?? 0) > 8) return fail('Use a triangle-mesh human model with at most eight morph targets per mesh.')
      const accessor = document.accessors[primitive.indices ?? primitive.attributes?.POSITION]
      if (!accessor || !document.accessors[primitive.attributes?.POSITION] || accessor.count % 3) return fail()
      return count + accessor.count / 3
    }, 0)
  })
  let triangles = 0
  for (const node of document.nodes) {
    if (node.mesh === undefined) continue
    if (!Number.isInteger(node.mesh) || meshTriangles[node.mesh] === undefined) return fail()
    triangles += meshTriangles[node.mesh]
  }
  if (!triangles || triangles > personalModelLimits.triangles) return fail('Use a human model with fewer than 750,000 rendered triangles.')
  return { triangles: Math.ceil(triangles), imageCount: document.images?.length ?? 0, bytes: buffer.byteLength }
}
