import fs from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import { createHash } from 'node:crypto'
import { fileURLToPath } from 'node:url'

export const cache = path.join(os.tmpdir(), 'humantwin-realism-v1')
const revision = '0943055db6ec570bcef9f2c8b41c9e5467c808f9'
const archiveRoot = 'https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/'
const rocketRoot = `https://raw.githubusercontent.com/microsoft/Microsoft-Rocketbox/${revision}/Assets/Avatars/Adults/Male_Adult_01/Textures/`
export const sources = [
  ...['isa_parts_list_e.txt', 'isa_element_parts.txt', 'partof_parts_list_e.txt', 'partof_element_parts.txt'].map(name => ({ name, url: archiveRoot + name })),
  ...['m002_head_color.tga', 'm002_head_normal.tga', 'm002_body_normal.tga'].map(name => ({ name, url: rocketRoot + name }))
]

export async function fetchSources() {
  await fs.mkdir(cache, { recursive: true })
  const manifest = []
  await Promise.all(sources.map(async ({ name, url }) => {
    const target = path.join(cache, name)
    if (path.dirname(path.resolve(target)) !== path.resolve(cache)) throw new Error('Invalid cache target')
    try { await fs.access(target) } catch {
      console.log(`Fetching ${name}`)
      const response = await fetch(url, { signal: AbortSignal.timeout(600000) })
      if (!response.ok) throw new Error(`${name}: HTTP ${response.status}`)
      const temporary = target + '.partial'
      const handle = await fs.open(temporary, 'w')
      try {
        for await (const chunk of response.body) await handle.write(chunk)
      } finally { await handle.close() }
      await fs.rename(temporary, target)
    }
    const bytes = await fs.readFile(target)
    manifest.push({ name, url, bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') })
    console.log(`Ready ${name}: ${bytes.length} bytes`)
  }))
  await fs.writeFile(path.join(cache, 'sources.json'), JSON.stringify(manifest.sort((a, b) => a.name.localeCompare(b.name)), null, 2))
  return cache
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await fetchSources()
