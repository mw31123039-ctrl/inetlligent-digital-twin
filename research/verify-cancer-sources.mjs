// Verify primary-source URLs and retain metadata only, never copied clinical pages.
import fs from 'node:fs/promises'
import path from 'node:path'
import { createHash } from 'node:crypto'
import { fileURLToPath } from 'node:url'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const corpus = JSON.parse(await fs.readFile(path.join(root, 'contracts/cancer-knowledge.v1.json'), 'utf8'))
const urls = [...new Set([...corpus.topics.flatMap(topic => [topic.source, topic.symptomSource]), ...corpus.faqs.flatMap(faq => faq.sources)].filter(Boolean))]
const checked = []
for (let start = 0; start < urls.length; start += 5) {
  checked.push(...await Promise.all(urls.slice(start, start + 5).map(async url => {
    try {
      const response = await fetch(url, { headers: { 'User-Agent': 'HumanTwin-Research/1.0' }, signal: AbortSignal.timeout(35000) })
      const text = await response.text()
      const title = text.match(/<h1[^>]*>([\s\S]*?)<\/h1>/i)?.[1].replace(/<[^>]*>/g, '').replace(/&[^;]+;/g, ' ').trim()
      return { url, resolved_url: response.url, status: response.status, title: title || null, content_sha256: createHash('sha256').update(text).digest('hex') }
    } catch (error) { return { url, status: null, error: error.name } }
  })))
}
const report = { corpus_version: corpus.version, checked_at: new Date().toISOString(), method: 'URL/title verification and page fingerprint; not clinical peer review or treatment-guideline approval', primary_sources: checked }
await fs.writeFile(path.join(root, 'research/cancer-source-review.json'), JSON.stringify(report, null, 2) + '\n')
console.log(JSON.stringify({ sources_checked: checked.length, accessible: checked.filter(item => item.status === 200 && item.title).length, failures: checked.filter(item => item.status !== 200 || !item.title) }))
