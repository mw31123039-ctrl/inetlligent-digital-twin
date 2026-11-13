// Actual installed models and public reference images, not mocked inference.
// Creates a disposable local test login; inference does not save the image.
import assert from 'node:assert/strict'
import { createHash, randomBytes } from 'node:crypto'
import fs from 'node:fs/promises'
import path from 'node:path'
import { chromium, expect as baseExpect } from '@playwright/test'

const expect = baseExpect.configure({ timeout: 30000 })
const show = process.argv.includes('--show')

const base = process.env.HUMANTWIN_CANCER_URL || 'http://127.0.0.1:5173'
const output = path.resolve(show ? 'test-results/cancer-demo' : 'test-results/cancer-real')
await fs.mkdir(output, { recursive: true })
const cases = [
  { track: 'Skin', modality: 'dermoscopy', file: '../ai-service/models/cancer/verification/dermoscopy.jpg' },
  { track: 'Breast', modality: 'breast_ultrasound', file: '../ai-service/models/cancer/verification/breast_ultrasound.jpg' },
  { track: 'Lung', modality: 'lung_ct_slice', file: '../ai-service/models/cancer/verification/lung_ct_slice.jpg' },
  { track: 'Oral', modality: 'oral_photo', file: process.env.HUMANTWIN_ORAL_EXAMPLE || '../ai-service/models/cancer/oral_photo/examples/benign_lesion.png' },
].filter((_, index) => !show || index === 0)
for (const item of cases) await fs.access(path.resolve(item.file))
if (show) console.log('Starting visible public-image demo; helper process ' + process.pid)
const browser = await chromium.launch({ channel: process.env.HUMANTWIN_BROWSER_CHANNEL || (process.platform === 'win32' ? 'chrome' : undefined), headless: !show,
  args: show ? ['--disable-gpu', '--disable-gpu-compositing', '--start-maximized'] : ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] })
const page = await browser.newPage({ viewport: show ? null : { width: 1500, height: 1080 } })
page.setDefaultTimeout(30000)
const errors = [], summary = []
page.on('pageerror', error => errors.push(error.message))
try {
  await page.goto(base + '/#cancer')
  await expect(page.getByLabel('Input type')).toHaveValue('dermoscopy')
  await page.locator('.header-sign-in').click()
  await page.getByRole('dialog').getByRole('button', { name: 'Create an account', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Create your account' })
  await dialog.getByLabel('Email', { exact: true }).fill(`cancer-real-${randomBytes(8).toString('hex')}@example.invalid`)
  await dialog.getByLabel('Password', { exact: true }).fill(randomBytes(20).toString('base64url'))
  await dialog.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.locator('.profile-button')).toContainText('Member')

  for (const item of cases) {
    await page.locator('.cancer-pathway').filter({ has: page.getByText(item.track, { exact: true }) }).click()
    await expect(page.getByLabel('Input type')).toHaveValue(item.modality)
    await page.getByLabel('Coded study subject ID').fill('PUBLIC-SOFTWARE-CHECK')
    await page.getByLabel('Attach research image', { exact: true }).setInputFiles(path.resolve(item.file))
    await expect(page.getByAltText('Attached research image preview')).toBeVisible()
    await page.getByRole('checkbox', { name: /^I confirm this image/ }).check()
    await page.getByRole('checkbox', { name: /^I understand this is experimental/ }).check()
    await page.getByRole('checkbox', { name: /^I permit sending/ }).check()
    const responseEvent = page.waitForResponse(response => new URL(response.url()).pathname === '/api/cancer/analyze' && response.request().method() === 'POST', { timeout: 60000 })
    await page.getByRole('button', { name: 'Run research model', exact: true }).click()
    const response = await responseEvent, result = await response.json()
    assert.equal(response.status(), 200, `${item.modality}: ${result.message || 'inference failed'}`)
    const sent = response.request().postDataJSON()
    const hash = createHash('sha256').update(Buffer.from(sent.image_data_url.split(',')[1], 'base64')).digest('hex')
    assert.equal(result.input_sha256, hash)
    assert.equal(result.modality, item.modality)
    assert.equal(result.runtime, 'onnxruntime-cpu')
    assert.equal(result.clinical_validation, false)
    assert.equal(result.calibrated_cancer_probability, false)
    assert.equal(result.explanation.localization, false)
    assert.equal(result.explanation.values.length, 16)
    assert.ok(result.inference_ms > 0)
    assert.equal(result.model_info.patient_disjoint, null)
    await expect(page.getByRole('heading', { name: 'Model findings' })).toBeVisible()
    await expect(page.locator('.cancer-score-row')).toHaveCount(result.scores.length)
    await page.getByRole('button', { name: 'Sensitivity', exact: true }).click()
    await expect(page.locator('svg.cancer-heatmap rect')).toHaveCount(16)
    await expect(page.locator('.cancer-runtime-strip')).toContainText('16 perturbations')
    await expect(page.locator('.cancer-quality-panel')).toBeVisible()
    const top = [...result.scores].sort((a, b) => b.value - a.value)[0]
    summary.push({ modality: item.modality, model: result.model_version, input_sha256: hash, top_model_class: top.label, top_model_score: top.value, inference_ms: result.inference_ms, explanation_cells: 16, clinical_validation: false, purpose: 'Functionality check; reference images may overlap model development data. No medical accuracy evaluation.' })
    await fs.writeFile(path.join(output, item.modality + '.json'), JSON.stringify(result, null, 2))
    await page.evaluate(() => { window.scrollTo(0, 0); if (document.activeElement instanceof HTMLElement) document.activeElement.blur() })
    if (!show) await page.screenshot({ path: path.join(output, item.modality + '.png'), fullPage: true })
  }
  if (!show) {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.waitForFunction(() => document.querySelector('.sidebar').getBoundingClientRect().right <= 1)
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false)
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: path.join(output, 'mobile-real-output.png'), fullPage: true })
  }
  assert.deepEqual(errors, [])
  await fs.writeFile(path.join(output, 'summary.json'), JSON.stringify(summary, null, 2))
  console.log(JSON.stringify({ actual_models_verified: summary.length, runtime: 'onnxruntime-cpu', results: summary.map(item => ({ modality: item.modality, model: item.model, inference_ms: item.inference_ms, explanation_cells: 16 })) }))
  if (show) {
    await page.evaluate(() => window.scrollTo(0, Math.max(0, document.querySelector('.care-workflow-grid')?.getBoundingClientRect().top + window.scrollY - 90 || 440)))
    await page.bringToFront()
    console.log('Live public-image demo ready. Close the browser window to end the demo session.')
    await new Promise(resolve => browser.once('disconnected', resolve))
  } else {
  await page.getByRole('button', { name: 'Account menu', exact: true }).click()
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  }
} finally { await browser.close() }
