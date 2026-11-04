import fs from 'node:fs/promises'
import { createHash } from 'node:crypto'
const revision = 'a8bc2d54ff0ac92e78ff71431b1023eda42bf482'
const base = `https://raw.githubusercontent.com/makehumancommunity/makehuman/${revision}/`
const directory = 'public/textures/eye'
await fs.mkdir(directory, { recursive: true })
const files = [{ name: 'brown_eye.png', source: 'makehuman/data/eyes/materials/brown_eye.png' },
  { name: 'brown.mhmat', source: 'makehuman/data/eyes/materials/brown.mhmat' }, { name: 'LICENSE-MakeHuman.md', source: 'LICENSE.md' }]
const manifest = { source: 'MakeHuman core eye asset', revision, license: 'CC0-1.0 for core graphics assets',
  license_url: 'https://www.makehumancommunity.org/about/license.html', modifications: 'Original PNG retained unchanged. Iris sampled through 3D mesh UVs; no image editing.', files: [] }
for (const file of files) {
  const response = await fetch(base + file.source)
  if (!response.ok) throw new Error(`${file.name}: HTTP ${response.status}`)
  const bytes = Buffer.from(await response.arrayBuffer())
  await fs.writeFile(`${directory}/${file.name}`, bytes)
  manifest.files.push({ name: file.name, source_url: base + file.source, sha256: createHash('sha256').update(bytes).digest('hex'), bytes: bytes.length })
}
await fs.writeFile(`${directory}/manifest.json`, JSON.stringify(manifest, null, 2))
await fs.writeFile(`${directory}/ATTRIBUTION.txt`, 'MakeHuman core eye texture, CC0 1.0.\nCore graphics assets were explicitly released under CC0 in September 2020.\nCopyright holders at that release: Data Collection AB, Joel Palmius and Jonas Hauquier.\nOriginal source texture and material retained unchanged. Only UV coordinates in the application select the iris area.\nSee brown.mhmat, LICENSE-MakeHuman.md and manifest.json for the source license declaration, revision and hashes.\n')
console.log('Pinned MakeHuman reference iris texture ready; original asset and license retained.')
