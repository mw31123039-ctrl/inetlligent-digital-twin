// Browser integration with software-only API fixtures; no medical model or patient data.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import fs from 'node:fs/promises'
import path from 'node:path'
import { chromium, expect } from '@playwright/test'

const base = process.env.HUMANTWIN_CANCER_URL || 'http://127.0.0.1:5174'
const output = path.resolve('test-results/cancer')
await fs.mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: process.env.HUMANTWIN_BROWSER_CHANNEL || (process.platform === 'win32' ? 'chrome' : undefined), headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] })
const page = await browser.newPage({ viewport: { width: 1440, height: 1080 }, acceptDownloads: true })
page.setDefaultTimeout(20000)
const errors = [], requests = []
let signedIn = false, configured = false, delayNext = false, release
const inputs = { skin: ['skin_photo', 'dermoscopy'], oral: ['oral_photo'], lung: ['lung_ct_slice'], breast: ['mammogram', 'breast_ultrasound', 'breast_mri_slice'] }
const model = { model_version: 'browser-software-fixture-v1', target: 'Synthetic browser fixture; no medical meaning', weights_sha256: 'b'.repeat(64) }
page.on('pageerror', error => errors.push(error.message))
await page.route('**/api/**', async route => {
  const request = route.request(), pathname = new URL(request.url()).pathname
  let json = {}
  if (pathname === '/api/cancer/status') json = { available: true, clinical_validation: false, external_requests: false, scope: 'single-2d-image', pathways: Object.entries(inputs).map(([track, values]) => ({ track, models: values.map(modality => ({ modality, configured: configured && modality === 'skin_photo', state: configured && modality === 'skin_photo' ? 'configured-unvalidated' : 'not-configured', ...(configured && modality === 'skin_photo' ? model : {}) })) })) }
  else if (pathname === '/api/me') {
    if (!signedIn) return route.fulfill({ status: 401, json: { message: 'Sign in to continue.' } })
    json = { user: { id: 987, email: 'synthetic-browser@example.invalid' } }
  } else if (pathname === '/api/status') json = { available: true, provider_configured: false }
  else if (pathname === '/api/assessments') json = { assessments: [] }
  else if (pathname === '/api/logout') { signedIn = false; return route.fulfill({ status: 204 }) }
  else if (pathname === '/api/cancer/analyze') {
    const body = request.postDataJSON(); requests.push(body)
    if (delayNext) { delayNext = false; await new Promise(resolve => { release = resolve }) }
    const inputHash = createHash('sha256').update(Buffer.from(body.image_data_url.split(',')[1], 'base64')).digest('hex')
    json = { schema_version: 'humantwin-cancer-result-v1', track: body.track, modality: body.modality, ...model, input_sha256: inputHash, scores: [{ label: 'synthetic_a', value: .6 }, { label: 'synthetic_b', value: .4 }], clinical_validation: false, calibrated_cancer_probability: false, external_requests: false, scope: 'single-2d-image' }
  }
  try { await route.fulfill({ json }) } catch (error) { if (!request.failure()) throw error }
})

async function attach() {
  const bytes = Buffer.from(await page.evaluate(() => {
    const canvas = document.createElement('canvas'); canvas.width = 128; canvas.height = 96
    const context = canvas.getContext('2d'); context.fillStyle = '#bb6666'; context.fillRect(0, 0, 128, 96)
    context.fillStyle = '#fff'; context.fillText('SYNTHETIC TEST', 9, 50)
    return canvas.toDataURL('image/png').split(',')[1]
  }), 'base64')
  await page.getByLabel('Attach research image').setInputFiles({ name: 'synthetic.png', mimeType: 'image/png', buffer: bytes })
  await expect(page.getByAltText('Attached research image preview')).toBeVisible()
}
async function permissions() {
  await page.getByRole('checkbox', { name: /^I confirm this image/ }).check()
  await page.getByRole('checkbox', { name: /^I understand this is experimental/ }).check()
  await page.getByRole('checkbox', { name: /^I permit sending/ }).check()
}
async function exportRecord() {
  await page.getByRole('checkbox', { name: /^I permit downloading/ }).check()
  const event = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export research JSON' }).click()
  const download = await event
  return JSON.parse(await fs.readFile(await download.path(), 'utf8'))
}
async function screenshot(name) {
  await page.evaluate(() => { window.scrollTo(0, 0); if (document.activeElement instanceof HTMLElement) document.activeElement.blur() })
  await page.screenshot({ path: path.join(output, name), fullPage: true })
}

try {
  await page.goto(base + '/#cancer')
  await expect(page.getByRole('heading', { name: 'Cancer care intelligence' })).toBeVisible()
  await expect(page.locator('.cancer-pathway')).toHaveCount(4)
  for (const label of ['Skin', 'Oral', 'Lung', 'Breast']) {
    await page.locator('.cancer-pathway').filter({ has: page.getByText(label, { exact: true }) }).click()
    await expect(page.getByRole('heading', { name: label + ' research input' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Run research model' })).toBeDisabled()
  }
  await expect(page.getByLabel('Input type').locator('option')).toHaveCount(3)
  await page.getByLabel('Coded study subject ID').fill('BROWSER-CASE')
  await page.locator('.cancer-history-panel > details').first().locator('summary').first().click()
  await page.getByLabel('Symptoms or changes').fill('Synthetic reviewer note')
  const historyOnly = await exportRecord()
  assert.equal(historyOnly.inference_state, 'not-run'); assert.equal(historyOnly.cancer_diagnosis, null)
  assert.equal(historyOnly.history.symptoms, 'Synthetic reviewer note'); assert.equal(historyOnly.image, null)
  await attach(); await permissions()
  await expect(page.getByRole('button', { name: 'Run research model' })).toBeDisabled()
  const withImage = await exportRecord()
  assert.ok(withImage.image.sha256); assert.ok(!JSON.stringify(withImage).includes('data:image/'))
  assert.equal(requests.length, 0, 'Attaching and exporting must not send an inference request')
  await screenshot('desktop-unconfigured.png')

  await page.locator('.cancer-twin-link').getByRole('button', { name: 'Patient twin' }).click()
  await page.getByLabel('Synthetic study subject ID').fill('LINKED-SUBJECT')
  await page.getByRole('button', { name: 'Start empty twin' }).click()
  await page.locator('.twin-actions').getByRole('button', { name: 'Cancer research', exact: true }).click()
  await expect(page.getByLabel('Coded study subject ID')).toHaveValue('BROWSER-CASE')
  await expect(page.locator('.cancer-twin-link')).toContainText('Open twin: LINKED-SUBJECT')
  await page.getByLabel('Coded study subject ID').fill('LINKED-SUBJECT')
  await expect(page.locator('.cancer-twin-link')).toContainText('Linked by code to the open twin')
  assert.equal((await exportRecord()).twin_link.subject_id, 'LINKED-SUBJECT')
  await page.getByLabel('Attach research image').setInputFiles({ name: 'scan.dcm', mimeType: 'application/dicom', buffer: Buffer.from('unsupported software fixture') })
  await expect(page.getByRole('alert')).toContainText('DICOM')
  await expect(page.getByAltText('Attached research image preview')).toHaveCount(0)

  signedIn = true; configured = true
  await page.reload()
  await expect(page.locator('.profile-button')).toContainText('Member')
  await expect(page.locator('.cancer-model-row').first()).toContainText('Research model configured')
  await page.getByLabel('Coded study subject ID').fill('SYNTHETIC-RESULT')
  await attach(); await permissions()
  await page.getByRole('button', { name: 'Run research model' }).click()
  await expect(page.getByRole('heading', { name: 'Model findings' })).toBeVisible()
  assert.equal(requests.length, 1)
  assert.deepEqual(Object.keys(requests[0]).sort(), ['track', 'modality', 'image_data_url', 'consent_local', 'modality_confirmed', 'research_only_acknowledged', 'explain'].sort())
  const scored = await exportRecord()
  assert.equal(scored.result.input_sha256, scored.image.sha256)
  assert.equal(scored.result.calibrated_cancer_probability, false)
  await screenshot('desktop-software-fixture.png')

  delayNext = true
  await page.getByRole('button', { name: 'Run research model' }).click()
  await expect.poll(() => requests.length).toBe(2)
  await page.locator('.cancer-pathway').filter({ has: page.getByText('Oral', { exact: true }) }).click()
  release?.()
  await expect(page.getByRole('heading', { name: 'Your review starts here' })).toBeVisible()
  await expect(page.getByAltText('Attached research image preview')).toHaveCount(0)
  await expect(page.getByRole('checkbox', { name: /^I permit sending/ })).not.toBeChecked()

  await page.locator('.cancer-history-panel > details').first().locator('summary').first().click()
  await page.getByLabel('Symptoms or changes').fill('Must clear on account change')
  await page.getByRole('button', { name: 'Account menu', exact: true }).click()
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page.getByLabel('Symptoms or changes')).toHaveValue('')
  await expect(page.getByLabel('Coded study subject ID')).toHaveValue(/^CASE-/)
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole('heading', { name: 'Skin research input' })).toBeVisible()
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1), false, 'Mobile workspace must not overflow horizontally')
  await screenshot('mobile.png')
  assert.deepEqual(errors, [])
  console.log('Cancer browser checks passed: four pathways, unavailable models, consent, previews, exports, twin link, fixture inference, stale-response cancellation, account isolation and mobile layout.')
} finally { release?.(); await browser.close() }
