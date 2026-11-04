/** Reproducible, public, licensed research samples. No private patient endpoints. */
import fs from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { inflateRawSync } from 'node:zlib'
import { fileURLToPath } from 'node:url'
const destination = fileURLToPath(new URL('../public/data/dental/', import.meta.url))
await fs.mkdir(destination, { recursive: true })
const hash = b => createHash('sha256').update(b).digest('hex')
const manifest = { version: 1, retrieved: '2026-11-05', purpose: 'Public research reference samples; not the current user or a treatment prediction.', files: [] }
async function request(url, options = {}) {
  const r = await fetch(url, { signal: AbortSignal.timeout(90000), ...options })
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${url}`)
  return r
}
async function save(name, bytes, metadata) {
  await fs.writeFile(new URL(name, 'file:///' + destination.replaceAll('\\', '/') + '/'), bytes)
  manifest.files.push({ name, bytes: bytes.length, sha256: hash(bytes), ...metadata })
  console.log(`${name}: ${bytes.length} bytes`)
}
const mendeley = 'https://data.mendeley.com/public-api/datasets/bpnmf2vhsk'
const snapshot = await (await request(`${mendeley}/snapshot/1`)).json()
if (!/by-4|by\/4|CC BY 4/i.test(JSON.stringify(snapshot.licence ?? snapshot.license))) throw new Error('Review the dental-cast license before redistribution')
const casts = await (await request(`${mendeley}/files?folder_id=2007ed63-f906-43f5-beef-870bf75389b5&version=1`, { headers: { Accept: 'application/vnd.mendeley-public-dataset.1+json' } })).json()
for (const [original, name] of [['Upper jaw.stl', 'reference-upper.stl'], ['Lower jaw.stl', 'reference-lower.stl']]) {
  const entry = casts.find(f => f.filename === original)
  if (!entry || entry.content_details.size > 15000000) throw new Error('Unexpected cast file')
  const bytes = Buffer.from(await (await request(entry.content_details.download_url)).arrayBuffer())
  if (hash(bytes) !== entry.content_details.sha256_hash) throw new Error('Cast checksum mismatch')
  await save(name, bytes, { source: 'https://data.mendeley.com/datasets/bpnmf2vhsk/1', original, originalFolder: 'Patient01-1992', fileId: entry.id, license: 'CC BY 4.0', authors: 'Amir Abdi; Mahtab Nouri', modified: false, note: 'Published serial dental-cast reference, normal occlusion; not a treated case or tooth-segmented scan.' })
}
// Select one original JPEG and its expert annotations from the 2 GB ZIP using
// standard byte ranges. No bulk archive download, conversion or image cropping.
const article = await (await request('https://api.figshare.com/v2/articles/27986417/versions/1')).json()
if (article.license?.name !== 'CC BY 4.0') throw new Error('Review Aariz license')
const archive = article.files.find(f => f.name === 'Aariz.zip')
if (!archive || archive.size !== 2098209792) throw new Error('Unexpected versioned Aariz archive')
async function range(start, end) {
  const r = await request(archive.download_url, { headers: { Range: `bytes=${start}-${end}` } })
  if (r.status !== 206 || !r.headers.get('content-range')?.startsWith(`bytes ${start}-`)) { await r.body.cancel(); throw new Error('Server did not honor the bounded byte range') }
  return Buffer.from(await r.arrayBuffer())
}
const tail = await range(archive.size - 66000, archive.size - 1)
const eocd = tail.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]))
if (eocd < 0) throw new Error('Missing ZIP directory')
const cdSize = tail.readUInt32LE(eocd + 12), cdOffset = tail.readUInt32LE(eocd + 16)
if (cdSize > 2000000) throw new Error('Unexpected directory size')
const cd = await range(cdOffset, cdOffset + cdSize - 1), entries = []
for (let i = 0; i < cd.length - 46;) {
  if (cd.readUInt32LE(i) !== 0x02014b50) throw new Error('Invalid ZIP central record')
  const n = cd.readUInt16LE(i + 28), x = cd.readUInt16LE(i + 30), c = cd.readUInt16LE(i + 32)
  entries.push({ name: cd.subarray(i + 46, i + 46 + n).toString(), size: cd.readUInt32LE(i + 24), compressed: cd.readUInt32LE(i + 20), method: cd.readUInt16LE(i + 10), offset: cd.readUInt32LE(i + 42) })
  i += 46 + n + x + c
}
const image = entries.find(e => e.name === 'Aariz/valid/Cephalograms/cl8ka1gfc2y3b072wawosdu4b.jpg')
if (!image) throw new Error('Reference image missing')
const id = image.name.split('/').at(-1).replace('.jpg', '')
const annotation = entries.find(e => e.name.includes('Senior Orthodontists') && e.name.endsWith(`/${id}.json`))
for (const [entry, name] of [[image, 'reference-cephalogram.jpg'], [annotation, 'reference-landmarks.json']]) {
  if (!entry || entry.compressed > 5000000 || entry.size > 10000000) throw new Error('Unexpected sample entry')
  const header = await range(entry.offset, entry.offset + 29)
  if (header.readUInt32LE(0) !== 0x04034b50) throw new Error('Invalid ZIP local header')
  const start = entry.offset + 30 + header.readUInt16LE(26) + header.readUInt16LE(28)
  const compressed = await range(start, start + entry.compressed - 1)
  const bytes = entry.method === 8 ? inflateRawSync(compressed) : compressed
  if (bytes.length !== entry.size) throw new Error('ZIP sample size mismatch')
  await save(name, bytes, { source: 'https://doi.org/10.6084/m9.figshare.27986417.v1', original: entry.name, license: article.license.name, authors: article.authors.map(a => a.full_name).join('; '), modified: false, note: 'One published validation-set reference. Annotated by dataset experts; no image-analysis model is bundled.' })
}
const growthUrl = 'https://cran.r-universe.dev/nlme/data/Orthodont/csv'
const nlme = await (await request('https://cran.r-universe.dev/nlme/json')).json()
if (nlme.Version !== '3.1-172' || !/GPL/.test(nlme.License ?? '')) throw new Error('The nlme mirror changed; review the package version and license before refreshing this pinned reference')
const growth = Buffer.from(await (await request(growthUrl)).arrayBuffer())
if (growth.toString().trim().split(/\r?\n/).length !== 109) throw new Error('Unexpected Orthodont row count')
await save('orthodont-growth.csv', growth, { source: growthUrl, package: 'nlme 3.1-172', license: 'GPL (>= 2), package distribution', authors: 'R Core nlme contributors; original data: Potthoff and Roy (1964), University of North Carolina Dental School', modified: false, note: '108 historical craniofacial distance measurements from 27 children at ages 8, 10, 12 and 14. Not tooth movement, brace outcomes or normative thresholds.' })
const gpl = Buffer.from(await (await request('https://www.r-project.org/Licenses/GPL-2')).arrayBuffer())
if (!gpl.toString().includes('GNU GENERAL PUBLIC LICENSE') || gpl.toString().includes('<!DOCTYPE')) throw new Error('Expected the plain-text GPL-2 license')
await fs.writeFile(destination + 'LICENSE-Orthodont-GPL-2.txt', gpl)
await fs.writeFile(destination + 'manifest.json', JSON.stringify(manifest, null, 2) + '\n')
await fs.writeFile(destination + 'ATTRIBUTION.md', '# Dental research references\n\nTwo unchanged STL casts: Abdi, Amir; Nouri, Mahtab (2020), Serial 3D Dental Models, Mendeley Data V1, https://doi.org/10.17632/bpnmf2vhsk.1. CC BY 4.0: https://creativecommons.org/licenses/by/4.0/.\n\nOne unchanged JPEG and senior annotation JSON from Aariz Cephalometric Dataset V1, Khalid et al. (2025), https://doi.org/10.6084/m9.figshare.27986417.v1. CC BY 4.0. Dataset license is distinct from the journal article license.\n\nOrthodont CSV: R nlme package 3.1-172, package license GPL >= 2; GPL-2 text is included. Original source: Potthoff and Roy (1964), Biometrika 51, 313–326. Accessed via the CRAN R-universe mirror. Export format is the mirror’s CSV, values unchanged.\n\nThe tooth atlas and hardware geometry in src/dental/anatomy.ts are original educational artwork. Public scans, X-rays, statistical measurements and the atlas are independent references; they do not describe the same participant. See manifest.json for original filenames, sizes and SHA-256 fingerprints.\n')
console.log('Dental reference provenance written')
