import fs from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import { createHash } from 'node:crypto'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { SYSTEMS, validateDataset, flattenCases, evaluateCase, calculateMetrics, pairedComparison, bootstrapMean } from './lib/evaluation.mjs'
import { renderCsv, renderHtml, renderMarkdown } from './lib/report.mjs'

const researchRoot = path.dirname(fileURLToPath(import.meta.url))
const projectRoot = path.dirname(researchRoot)
const hash = bytes => createHash('sha256').update(bytes).digest('hex')

function argumentsFor(argv) {
  const options = { dataset: path.join(researchRoot, 'eye-safety.v1.json'),
    out: path.join(researchRoot, 'results/latest'), seed: 20261101, resamples: 2000, check: false }
  for (let index = 0; index < argv.length; index++) {
    const arg = argv[index]
    if (arg === '--check') options.check = true
    else if (arg === '--help') options.help = true
    else if (['--dataset', '--out', '--seed', '--resamples'].includes(arg)) {
      const value = argv[++index]
      if (!value || value.startsWith('--')) throw new Error(`${arg} requires a value`)
      const key = arg.slice(2)
      options[key] = ['seed', 'resamples'].includes(key) ? Number(value) : path.resolve(value)
    } else throw new Error(`Unknown argument: ${arg}`)
  }
  bootstrapMean([], options) // Validate numeric options before running anything.
  return options
}

async function sourceHashes() {
  const files = []
  async function collect(relative) {
    for (const entry of await fs.readdir(path.join(projectRoot, relative), { withFileTypes: true })) {
      const child = path.join(relative, entry.name)
      if (entry.isDirectory()) await collect(child)
      else if (/\.(ts|json|mjs)$/.test(entry.name)) files.push(child)
    }
  }
  await collect('frontend/src/eye')
  await collect('contracts/eye')
  files.push('frontend/scripts/portable.mjs', 'frontend/package.json', 'frontend/package-lock.json',
    'research/run-eye-benchmark.mjs', 'research/lib/evaluation.mjs', 'research/lib/report.mjs')
  return Object.fromEntries(await Promise.all(files.sort().map(async file => [file.replaceAll('\\', '/'), hash(await fs.readFile(path.join(projectRoot, file)))])))
}

function subsets(rows, locales) {
  return Object.fromEntries(['all', ...locales].flatMap(locale => ['all', 'development', 'evaluation'].map(split => [
    `${locale}/${split}`, rows.filter(row => (locale === 'all' || row.locale === locale) && (split === 'all' || row.split === split))
  ])))
}

async function main() {
  const options = argumentsFor(process.argv.slice(2))
  if (options.help) {
    console.log('Usage: node research/run-eye-benchmark.mjs [--out DIRECTORY] [--dataset FILE] [--seed UINT32] [--resamples 100..100000] [--check]\nOffline synthetic evaluation. --check exits 1 on production-policy disagreements; reports are still written.')
    return
  }
  const datasetBytes = await fs.readFile(options.dataset)
  const dataset = JSON.parse(datasetBytes.toString('utf8'))
  const interview = JSON.parse(await fs.readFile(path.join(projectRoot, 'contracts/eye/interview.v1.json'), 'utf8'))
  validateDataset(dataset, interview)
  const cases = flattenCases(dataset)
  const inputs = await sourceHashes()
  const temporary = await fs.mkdtemp(path.join(os.tmpdir(), 'humantwin-research-'))
  let engine, engineHash
  try {
    const { bundleModule } = await import('../frontend/scripts/portable.mjs')
    const bundle = path.join(temporary, 'eye-engine.mjs')
    await bundleModule(path.join(projectRoot, 'frontend/src/eye/interview.ts'), bundle)
    engineHash = hash(await fs.readFile(bundle))
    engine = await import(pathToFileURL(bundle).href)
    const systems = {}
    for (const [name, description] of Object.entries(SYSTEMS)) {
      const rows = cases.map(scenario => evaluateCase(engine, interview.questions, scenario, name))
      systems[name] = { description, rows,
        summaries: Object.fromEntries(Object.entries(subsets(rows, dataset.locales)).map(([key, selected]) => [key, calculateMetrics(selected, options)])),
        by_tag: Object.fromEntries([...new Set(rows.flatMap(row => row.tags))].sort().map(tag => [tag, calculateMetrics(rows.filter(row => row.tags.includes(tag)), options)])) }
    }
    const fullGroups = subsets(systems.full.rows, dataset.locales)
    const comparisons = {}
    for (const name of Object.keys(SYSTEMS).filter(name => name !== 'full')) {
      comparisons[name] = Object.fromEntries(Object.entries(subsets(systems[name].rows, dataset.locales)).map(([key, selected]) => [key, pairedComparison(fullGroups[key], selected, options)]))
    }
    const observed = systems.full.summaries['all/all'].observed_rule_ids
    const required = [...new Set(cases.flatMap(item => item.expected.rule_ids))].sort()
    const report = {
      format_version: 'humantwin-eye-benchmark-v1',
      interpretation: 'Synthetic development fixtures with draft author labels and translations. No clinical accuracy, external validation, translation equivalence, or patient safety claim. Unknown is not a clinical negative. Ablations are not independent systems.',
      manifest: {
        generated_at: new Date().toISOString(), dataset_version: dataset.version, dataset_sha256: hash(datasetBytes),
        dataset_file: path.relative(projectRoot, options.dataset).replaceAll('\\', '/'),
        protocol_relative_path: path.relative(options.out, path.join(researchRoot, 'README.md')).replaceAll('\\', '/'),
        label_status: dataset.label_status, translation_status: dataset.translation_status, provenance: dataset.provenance,
        rules_version: interview.version, engine_bundle_sha256: engineHash, input_sha256: inputs,
        seed: options.seed, resamples: options.resamples, locales: dataset.locales,
        partition_method: 'SHA-256 family ID, first 32 bits modulo 5: 0..2 development; 3..4 evaluation. Both public and exploratory; not blinded holdout.',
        interval_method: 'Seeded percentile bootstrap of scenario-family mean urgency agreement; translations cluster together. Descriptive fixture variability only; interval undefined with fewer than two families.',
        runtime: { node: process.version, platform: process.platform, arch: process.arch },
        external_model_calls: 0, network_requests: 0, backend_replay_evaluated: false,
        git_revision: null, revision_note: 'Source fingerprints identify this workspace snapshot; no Git revision is inferred.'
      },
      coverage: { all_rule_ids: interview.rules.map(rule => rule.id).sort(), expected_rule_ids: required,
        observed_production_rule_ids: observed, unactivated_rule_ids: interview.rules.map(rule => rule.id).filter(id => !observed.includes(id)).sort() },
      systems, comparisons
    }
    // Read inputs first; never allow generated artifacts to overwrite a dataset or source.
    const artifacts = ['report.json', 'report.html', 'report.md', 'cases.csv'].map(file => path.join(options.out, file))
    for (const target of artifacts) {
      if (path.resolve(target) === path.resolve(options.dataset)) throw new Error('Output would overwrite the dataset')
      try { if ((await fs.lstat(target)).isSymbolicLink()) throw new Error(`Refusing symbolic-link output: ${target}`) }
      catch (error) { if (error.code !== 'ENOENT') throw error }
    }
    await fs.mkdir(options.out, { recursive: true })
    const outputs = [JSON.stringify(report, null, 2) + '\n', renderHtml(report), renderMarkdown(report), renderCsv(report)]
    // Writes remain sequential so a failed artifact write cannot be silently discarded.
    for (const [index, target] of artifacts.entries()) await fs.writeFile(target, outputs[index], 'utf8')
    const full = systems.full.summaries['all/all']
    console.log(`Synthetic eye benchmark: ${full.cases} cases / ${full.families} families / ${dataset.locales.length} locales`)
    for (const [name, result] of Object.entries(systems)) {
      const m = result.summaries['all/all']
      console.log(`${name}: urgency agreement ${m.urgency_agreement.numerator}/${m.cases}; policy conformance ${m.policy_conformance.numerator}/${m.cases}; engine errors ${m.errors}`)
    }
    console.log(`Report: ${path.join(options.out, 'report.html')}`)
    console.log('Draft synthetic expectations only. Disagreements are preserved; these numbers are not clinical accuracy.')
    if (options.check && full.policy_conformance.numerator !== full.cases) process.exitCode = 1
  } finally {
    // mkdtemp creates a private directory under the OS temp root; never remove a user-provided path.
    if (path.dirname(path.resolve(temporary)) !== path.resolve(os.tmpdir()) || !path.basename(temporary).startsWith('humantwin-research-')) {
      throw new Error('Temporary cleanup target is outside the expected directory')
    }
    await fs.rm(temporary, { recursive: true, force: true })
  }
}

main().catch(error => { console.error(`Research benchmark failed: ${error.message}`); process.exitCode = 2 })
