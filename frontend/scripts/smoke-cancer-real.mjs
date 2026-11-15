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
  await expect(page.locator('.cw-area-card.selected')).toContainText('Skin')
  await page.locator('.header-sign-in').click()
  await page.getByRole('dialog').getByRole('button', { name: 'Create an account', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Create your account' })
  await dialog.getByLabel('Email', { exact: true }).fill(`cancer-real-${randomBytes(8).toString('hex')}@example.invalid`)
  await dialog.getByLabel('Password', { exact: true }).fill(randomBytes(20).toString('base64url'))
  await dialog.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.locator('.profile-button')).toContainText('Member')

  for (const item of cases) {
    await page.locator('.cw-area-card').filter({ hasText: item.track }).click()
    await expect(page.locator('.cw-area-card.selected')).toContainText(item.track)
    await page.getByLabel('Choose an image file').first().setInputFiles(path.resolve(item.file))
    await expect(page.locator('.cw-preview img')).toBeVisible()
    await page.getByRole('checkbox', { name: /^This is a/ }).check()
    await page.getByRole('checkbox', { name: /^I understand this is a research tool/ }).check()
    await page.getByRole('checkbox', { name: /^I allow the local research model/ }).check()
    const responseEvent = page.waitForResponse(response => new URL(response.url()).pathname === '/api/cancer/analyze' && response.request().method() === 'POST', { timeout: 60000 })
    await page.getByRole('button', { name: /^Analyse/ }).click()
    const response = await responseEvent, result = await response.json()
    assert.equal(response.status(), 200, `${item.modality}: ${result.message || 'inference failed'}`)
    const sent = response.request().postDataJSON()
    const hash = createHash('sha256').update(Buffer.from(sent.image_data_url.split(',')[1], 'base64')).digest('hex')
    assert.equal(result.input_sha256, hash)
    assert.equal(result.modality, item.modality)
    assert.equal(result.runtime, 'onnxruntime-cpu')
    assert.equal(result.clinical_validation, false)
    assert.equal(result.calibrated_cancer_probability, false)
    assert.equal(result.schema_version, 'humantwin-cancer-result-v2')
    assert.notEqual(result.outcome, 'input-rejected', `${item.modality}: the reference image was rejected by the input checks`)
    assert.equal(result.heatmap.localization, false)
    assert.equal(result.heatmap.values.length, result.heatmap.grid_width * result.heatmap.grid_height)
    assert.ok(['grad-cam', 'attention-rollout'].includes(result.heatmap.method))
    assert.ok(result.inference_ms > 0)
    assert.equal(result.model_info.patient_disjoint, null)
    await expect(page.locator('.cw-result')).toContainText('Not a medical diagnosis')
    await expect(page.locator('.cw-result').getByRole('meter')).toBeVisible()
    await expect(page.locator('.cw-heatmap canvas')).toBeVisible()
    summary.push({ modality: item.modality, model: result.model_version, input_sha256: hash, outcome: result.outcome, top_model_class: result.confidence.top_label, top_model_probability: result.confidence.probability, calibration: result.confidence.calibration, heatmap: result.heatmap.method, inference_ms: result.inference_ms, clinical_validation: false, purpose: 'Functionality check; reference images may overlap model development data. No medical accuracy evaluation.' })
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
  console.log(JSON.stringify({ actual_models_verified: summary.length, runtime: 'onnxruntime-cpu', results: summary.map(item => ({ modality: item.modality, model: item.model, outcome: item.outcome, heatmap: item.heatmap, inference_ms: item.inference_ms })) }))
  if (show) {
    await page.evaluate(() => window.scrollTo(0, Math.max(0, document.querySelector('.cw-flow')?.getBoundingClientRect().top + window.scrollY - 90 || 440)))
    await page.bringToFront()
    console.log('Live public-image demo ready. Close the browser window to end the demo session.')
    await new Promise(resolve => browser.once('disconnected', resolve))
  } else {
  await page.getByRole('button', { name: 'Account menu', exact: true }).click()
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  }
} finally { await browser.close() }
