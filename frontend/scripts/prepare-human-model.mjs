// Rebuild the bundled GLB from pinned, MIT-licensed Microsoft Rocketbox assets.
// Requires the development server at http://127.0.0.1:5173 and Playwright Chromium.
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { chromium } from '@playwright/test'

const revision = '0943055db6ec570bcef9f2c8b41c9e5467c808f9'
const root = `https://raw.githubusercontent.com/microsoft/Microsoft-Rocketbox/${revision}`
const source = 'Assets/Avatars/Adults/Male_Adult_01'
const cache = path.join(os.tmpdir(), `humantwin-rocketbox-${revision}`)
await fs.mkdir(cache, { recursive: true })
const files = ['Export/Male_Adult_01.fbx', 'Textures/m002_body_color.tga', 'Textures/m002_head_color.tga', 'Textures/m002_opacity_color.tga']
for (const file of files) {
  const destination = path.join(cache, path.basename(file))
  try { await fs.access(destination) } catch {
    console.log(`Downloading ${file}`)
    const response = await fetch(`${root}/${source}/${file}`)
    if (!response.ok) throw new Error(`${response.status}: ${file}`)
    await fs.writeFile(destination, Buffer.from(await response.arrayBuffer()))
  }
}
const browser = await chromium.launch()
try {
  const page = await browser.newPage()
  await page.route('http://127.0.0.1:5173/', route => route.fulfill({ contentType: 'text/html', body: '<!doctype html><title>Human model preparation</title>' }))
  page.on('console', message => { if (message.type() === 'error') console.log(message.text()) })
  await page.route('**/rocketbox-source/**', async route => {
    const filename = decodeURIComponent(new URL(route.request().url()).pathname.split('/').pop())
    try { await route.fulfill({ body: await fs.readFile(path.join(cache, filename)) }) }
    catch { await route.fulfill({ status: 404, body: '' }) }
  })
  await page.goto('http://127.0.0.1:5173')
  const result = await page.evaluate(async () => {
    const THREE = await import('/node_modules/three/build/three.module.js')
    const { FBXLoader } = await import('/node_modules/three/examples/jsm/loaders/FBXLoader.js')
    const { TGALoader } = await import('/node_modules/three/examples/jsm/loaders/TGALoader.js')
    const { GLTFExporter } = await import('/node_modules/three/examples/jsm/exporters/GLTFExporter.js')
    const manager = new THREE.LoadingManager()
    manager.setURLModifier(url => `/rocketbox-source/${url.replaceAll('\\', '/').split('/').pop()}`)
    // The web model deliberately uses diffuse textures only. Do not request the
    // source specular/normal maps, which are replaced by the PBR material below.
    const tgaLoader = new TGALoader(manager)
    const loadTga = tgaLoader.load.bind(tgaLoader)
    // FBXLoader asks for a handler by extension, then passes the actual filename.
    tgaLoader.load = (url, ...callbacks) => /_(normal|specular)\.tga$/i.test(url) ? new THREE.Texture() : loadTga(url, ...callbacks)
    manager.addHandler(/\.tga$/i, tgaLoader)
    const loaded = new Promise(resolve => { manager.onLoad = resolve })
    const model = await new FBXLoader(manager).loadAsync('/rocketbox-source/Male_Adult_01.fbx')
    await loaded
    const metadata = []
    const convertedTextures = new Map()
    function exportTexture(texture) {
      if (!texture?.image?.data) return texture
      if (convertedTextures.has(texture)) return convertedTextures.get(texture)
      // putImageData ignores canvas transforms and cropping in GLTFExporter's
      // DataTexture branch. A CanvasTexture preserves TGA orientation and scales correctly.
      const canvas = document.createElement('canvas')
      canvas.width = texture.image.width
      canvas.height = texture.image.height
      canvas.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(texture.image.data), canvas.width, canvas.height), 0, 0)
      const result = new THREE.CanvasTexture(canvas)
      result.colorSpace = texture.colorSpace
      result.flipY = texture.flipY
      convertedTextures.set(texture, result)
      return result
    }
    model.traverse(node => {
      if (node.isMesh) metadata.push({ name: node.name, vertices: node.geometry.attributes.position.count, groups: node.geometry.groups, materials: (Array.isArray(node.material) ? node.material : [node.material]).map(m => ({ name: m.name, map: m.map?.name, flipY: m.map?.flipY, repeat: m.map?.repeat.toArray(), offset: m.map?.offset.toArray(), transparent: m.transparent })) })
      if (node.isBone && !/finger|toe|twist/i.test(node.name)) metadata.push({ bone: node.name, position: node.getWorldPosition(new THREE.Vector3()).toArray() })
    })
    console.log(JSON.stringify(metadata))
    // Keep the highest-detail body only, removing duplicate lower LOD geometry.
    const remove = []
    model.traverse(node => { if (node.isMesh && /(?:midpoly|lowpoly|ultralowpoly)/i.test(node.name)) remove.push(node) })
    remove.forEach(node => node.removeFromParent())
    model.traverse(node => {
      if (!node.isMesh) return
      const old = Array.isArray(node.material) ? node.material : [node.material]
      const materials = old.map(material => {
        const map = exportTexture(material.map)
        if (map && !/opacity|hair|lash/i.test(material.name)) map.userData.mimeType = 'image/jpeg'
        return new THREE.MeshStandardMaterial({
        name: material.name, color: 0xffffff, map,
        roughness: .82, metalness: 0, side: THREE.DoubleSide,
        alphaTest: /opacity|hair|lash/i.test(material.name) ? .45 : 0,
        })
      })
      node.material = Array.isArray(node.material) ? materials : materials[0]
    })
    const box = new THREE.Box3().setFromObject(model)
    const exporter = new GLTFExporter()
    const glb = await exporter.parseAsync(model, { binary: true, maxTextureSize: 1024 })
    const bytes = new Uint8Array(glb)
    let binary = ''
    for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192))
    return { base64: btoa(binary), metadata, bounds: { min: box.min.toArray(), max: box.max.toArray() } }
  })
  await fs.mkdir('public/models', { recursive: true })
  await fs.writeFile('public/models/human.glb', Buffer.from(result.base64, 'base64'))
  await fs.writeFile(path.join(cache, 'metadata.json'), JSON.stringify({ metadata: result.metadata, bounds: result.bounds }, null, 2))
  const license = await fetch(`${root}/LICENSE.md`)
  if (!license.ok) throw new Error('Could not retrieve the required license')
  await fs.writeFile('public/models/LICENSE-Rocketbox.txt', await license.text())
  console.log(JSON.stringify({ bytes: Buffer.from(result.base64, 'base64').length, bounds: result.bounds, metadata: path.join(cache, 'metadata.json') }))
} finally { await browser.close() }
