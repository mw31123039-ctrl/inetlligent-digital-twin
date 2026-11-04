import assert from 'node:assert/strict'
import { test } from 'node:test'
import fs from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import { createHash } from 'node:crypto'
import { pathToFileURL } from 'node:url'
import { bundleModule, root } from './portable.mjs'

const hash = bytes => createHash('sha256').update(bytes).digest('hex')
function parseGlb(bytes) {
  assert.equal(bytes.subarray(0, 4).toString(), 'glTF')
  assert.equal(bytes.readUInt32LE(4), 2)
  assert.equal(bytes.readUInt32LE(8), bytes.length)
  return JSON.parse(bytes.subarray(20, 20 + bytes.readUInt32LE(12)).toString())
}
const temporary = await fs.mkdtemp(path.join(os.tmpdir(), 'humantwin-realism-test-'))
let model, dispose
try {
  const relative = file => './' + path.relative(temporary, path.join(root, file)).replaceAll('\\', '/')
  const entry = `export * from ${JSON.stringify(relative('src/eye/model.ts'))}; export { disposeScene } from ${JSON.stringify(relative('src/three/disposeScene.ts'))};`
  await fs.writeFile(path.join(temporary, 'entry.ts'), entry)
  await bundleModule(path.join(temporary, 'entry.ts'), path.join(temporary, 'eye.mjs'))
  model = await import(pathToFileURL(path.join(temporary, 'eye.mjs')).href)
  dispose = model.disposeScene
} finally {
  assert.equal(path.dirname(path.resolve(temporary)), path.resolve(os.tmpdir()))
  assert.ok(path.basename(temporary).startsWith('humantwin-realism-test-'))
  await fs.rm(temporary, { recursive: true, force: true })
}

await test('the detailed human retains a real rig, source textures, normal maps and the original asset', async () => {
  const bytes = await fs.readFile(path.join(root, 'public/models/human-detailed.glb'))
  const data = parseGlb(bytes), manifest = JSON.parse(await fs.readFile(path.join(root, 'public/models/human-detailed.manifest.json'), 'utf8'))
  assert.equal(hash(bytes), manifest.output_sha256)
  assert.ok(data.skins[0].joints.length > 30)
  assert.equal(data.materials.filter(material => material.normalTexture).length, 2)
  assert.ok(manifest.sources.every(source => source.width === 2048 && source.height === 2048))
  assert.equal(hash(await fs.readFile(path.join(root, 'public/models/human.glb'))), manifest.source_glb_sha256)
  assert.ok(data.images.every(image => image.bufferView !== undefined && image.uri === undefined))
  assert.match(await fs.readFile(path.join(root, 'public/models/LICENSE-Rocketbox.txt'), 'utf8'), /MIT License/)
})

await test('every regional GLB matches its source manifest and contains detailed indexed geometry', async () => {
  const directory = path.join(root, 'public/models/anatomy')
  const manifest = JSON.parse(await fs.readFile(path.join(directory, 'manifest.json'), 'utf8'))
  assert.equal(Object.keys(manifest.models).length, 7)
  for (const [name, item] of Object.entries(manifest.models)) {
    const bytes = await fs.readFile(path.join(directory, item.file)), gltf = parseGlb(bytes)
    assert.equal(hash(bytes), item.sha256, name)
    assert.ok(item.triangles > 8000, name)
    assert.ok(item.elements.length > 0 && item.elements.every(element => /^FJ\d+M?$/.test(element.id) && /^FMA\d+$/.test(element.fma)))
    assert.ok(gltf.meshes.every(mesh => mesh.primitives.every(primitive => primitive.indices !== undefined)))
    assert.ok(gltf.buffers.every(buffer => buffer.uri === undefined))
  }
  assert.notEqual(manifest.models['arms-left'].sha256, manifest.models['arms-right'].sha256)
  assert.notEqual(manifest.models['legs-left'].sha256, manifest.models['legs-right'].sha256)
  assert.match(await fs.readFile(path.join(directory, 'ATTRIBUTION.txt'), 'utf8'), /Database Center for Life Science/)
})

await test('the licensed iris image is bundled unchanged with its pinned source and CC0 declaration', async () => {
  const directory = path.join(root, 'public/textures/eye')
  const manifest = JSON.parse(await fs.readFile(path.join(directory, 'manifest.json'), 'utf8'))
  assert.match(manifest.revision, /^[0-9a-f]{40}$/)
  for (const file of manifest.files) assert.equal(hash(await fs.readFile(path.join(directory, file.name))), file.sha256)
  assert.match(await fs.readFile(path.join(directory, 'brown.mhmat'), 'utf8'), /explicitly released as CC0/)
})

await test('the chest surface view contains all five lung lobes and four heart chambers with its own source license', async () => {
  const directory = path.join(root, 'public/models/anatomy')
  const bytes = await fs.readFile(path.join(directory, 'chest-surface.glb'))
  const data = parseGlb(bytes), manifest = JSON.parse(await fs.readFile(path.join(directory, 'chest-surface.manifest.json'), 'utf8'))
  assert.equal(hash(bytes), manifest.output_sha256)
  assert.equal(manifest.license, 'CC BY-SA 4.0')
  assert.equal(manifest.included_meshes.filter(name => /lobe_of_.*lung/.test(name)).length, 5)
  for (const name of ['Left_ventricle', 'Right_ventricle', 'Left_atrium', 'Right_atrium']) assert.ok(manifest.included_meshes.includes(name))
  assert.ok(manifest.included_meshes.every(name => !/kidney|j$/.test(name)))
  assert.equal(manifest.sources.length, 2)
  assert.ok(data.buffers.every(buffer => buffer.uri === undefined))
  assert.match(await fs.readFile(path.join(directory, 'LICENSE-Z-Anatomy.txt'), 'utf8'), /Attribution-ShareAlike 4.0/)
})

await test('the surface eye has actual iris and pupil openings, optical material, shaped lids and finite geometry', () => {
  for (const side of ['left', 'right']) {
    const group = model.buildEyeModel(side, 'external')
    const iris = group.getObjectByName('eye.iris'), pupil = group.getObjectByName('eye.pupil'), cornea = group.getObjectByName('eye.cornea')
    assert.equal(iris.userData.natural, true)
    const vertices = iris.children[0].geometry.getAttribute('position')
    for (let i = 0; i < vertices.count; i++) assert.ok(Math.hypot(vertices.getX(i), vertices.getY(i)) >= .1799)
    assert.ok(cornea.children[0].material.transmission > .9)
    assert.ok(cornea.children[0].material.userData.lidMask)
    assert.ok(group.getObjectByName('eye.upper-eyelid').children[0].geometry.getAttribute('position').count > 1000)
    pupil.traverse(child => {
      if (child.geometry?.type === 'CircleGeometry') { assert.equal(child.material.opacity, 0); assert.equal(child.userData.annotationOnly, true) }
    })
    group.traverse(child => {
      const positions = child.geometry?.getAttribute('position')
      if (positions) for (const value of positions.array) assert.ok(Number.isFinite(value))
    })
    dispose(group)
  }
})
