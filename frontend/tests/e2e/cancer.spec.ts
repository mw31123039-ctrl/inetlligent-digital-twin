import { createHash } from 'node:crypto'
import path from 'node:path'
import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

// The API is mocked with synthetic results in the v2 contract; no model or backend is needed.
const weights = 'b'.repeat(64)
const models: Record<string, { track: string; version: string; target: string; labels: string[] }> = {
  dermoscopy: { track: 'skin', version: 'synthetic-skin-v1', target: 'Synthetic dermoscopy fixture', labels: ['melanocytic_Nevi', 'melanoma'] },
  oral_photo: { track: 'oral', version: 'synthetic-oral-v1', target: 'Synthetic oral fixture', labels: ['benign_lesion', 'malignant_lesion'] },
  lung_ct_slice: { track: 'lung', version: 'synthetic-lung-v1', target: 'Synthetic lung fixture', labels: ['adenocarcinoma', 'normal'] },
  breast_ultrasound: { track: 'breast', version: 'synthetic-breast-v1', target: 'Synthetic breast fixture', labels: ['benign', 'malignant'] },
}
const inputs: Record<string, string[]> = { skin: ['skin_photo', 'dermoscopy'], oral: ['oral_photo'], lung: ['lung_ct_slice'], breast: ['mammogram', 'breast_ultrasound', 'breast_mri_slice'] }
const status = { available: true, clinical_validation: false, external_requests: false, scope: 'single-2d-image', pathways: Object.entries(inputs).map(([track, list]) => ({ track, models: list.map(modality => models[modality]
  ? { modality, configured: true, state: 'configured-unvalidated', model_version: models[modality]!.version, target: models[modality]!.target, weights_sha256: weights, labels: models[modality]!.labels, heatmap_method: 'grad-cam', calibration: 'temperature-scaled' }
  : { modality, configured: false, state: 'not-configured' }) })) }
const checks = (rejected: boolean) => ({ width: 224, height: 224, brightness: 120, contrast: 40, sharpness: 60, colored_fraction: rejected ? 0 : .8, overexposed_fraction: 0, decision: rejected ? 'rejected' : 'accepted',
  findings: rejected ? [{ code: 'unexpected-color', severity: 'reject', message: 'This looks like a color photograph, but this model expects a grayscale CT slice of the chest.' }] : [{ code: 'content-not-verified', severity: 'info', message: 'Anatomy is not verified automatically.' }] })

function result(modality: string, inputHash: string) {
  const model = models[modality]!
  const base = { schema_version: 'humantwin-cancer-result-v2', track: model.track, modality, model_version: model.version, target: model.target, weights_sha256: weights, input_sha256: inputHash,
    clinical_validation: false, calibrated_cancer_probability: false, scope: 'single-2d-image', external_requests: false, inference_ms: 42, runtime: 'onnxruntime-cpu', familiarity: null }
  if (modality === 'lung_ct_slice') return { ...base, outcome: 'input-rejected', outcome_reasons: ['input-rejected'], finding_label: null, scores: [], confidence: null, heatmap: null, image_checks: checks(true) }
  const [first, second] = model.labels
  return { ...base, outcome: 'finding', outcome_reasons: [], finding_label: second, scores: [{ label: first, value: .1 }, { label: second, value: .9 }],
    confidence: { top_label: second, probability: .9, level: 'high', calibration: 'temperature-scaled', temperature: 1.2, decision_threshold: .65, normalized_entropy: .4, margin: .8, interpretation: 'model-confidence-not-personal-risk' },
    heatmap: { method: 'grad-cam', target_label: second, class_specific: true, grid_width: 7, grid_height: 7, values: Array.from({ length: 49 }, (_, index) => index === 24 ? 1 : .1), meaning: 'regions-that-raised-the-score', localization: false },
    image_checks: checks(false) }
}

async function mockApi(page: Page) {
  const saved: Record<string, unknown>[] = []
  let last: ReturnType<typeof result> | null = null
  await page.route('**/sanctum/**', route => route.fulfill({ status: 204 }))
  await page.route('**/api/**', async route => {
    const request = route.request(), pathname = new URL(request.url()).pathname
    if (pathname === '/api/cancer/status') return route.fulfill({ json: status })
    if (pathname === '/api/me') return route.fulfill({ json: { user: { id: 1, email: 'synthetic@example.invalid' } } })
    if (pathname === '/api/cancer/knowledge-status') return route.fulfill({ json: { configured: false, method: 'local-semantic-retrieval', clinical_validation: false, external_requests: false } })
    if (pathname === '/api/cancer/analyze') {
      const body = request.postDataJSON()
      expect(body.explain).toBe(true)
      last = result(body.modality, createHash('sha256').update(Buffer.from(body.image_data_url.split(',')[1], 'base64')).digest('hex'))
      return route.fulfill({ json: last })
    }
    if (pathname === '/api/cancer/reports' && request.method() === 'POST') {
      const body = request.postDataJSON()
      expect(body.consent).toBe(true); expect(body.thumbnail_data_url).toMatch(/^data:image\/jpeg;base64,/)
      saved.push({ id: '0d3b6c1e-4a1f-4c3a-9b2e-2f1a5d7c8e90', created_at: '2026-11-16T10:00:00Z', track: last!.track, modality: last!.modality, outcome: last!.outcome, finding_label: last!.finding_label, top_label: last!.confidence?.top_label ?? null, probability: .9, model_version: last!.model_version, thumbnail_data_url: body.thumbnail_data_url, note: body.note, result: last })
      return route.fulfill({ status: 201, json: { id: saved.at(-1)!.id, saved: true, created_at: '2026-11-16T10:00:00Z' } })
    }
    if (pathname === '/api/cancer/reports') return route.fulfill({ json: { reports: saved.map(({ result: _r, thumbnail_data_url: _t, note: _n, ...row }) => row) } })
    if (pathname.startsWith('/api/cancer/reports/')) return route.fulfill({ json: saved[0] })
    return route.fulfill({ json: [] })
  })
}

async function analyse(page: Page, area: string, file: string) {
  await page.locator('.cw-area-card').filter({ hasText: area }).click()
  const chooser = page.waitForEvent('filechooser')
  await page.getByRole('button', { name: 'Choose a file' }).click()
  await (await chooser).setFiles(path.resolve('public/cancer-examples', file))
  await expect(page.locator('.cw-preview img')).toBeVisible()
  for (const name of [/^This is a/, /^I understand/, /^I allow/]) await page.getByRole('checkbox', { name }).check()
  await page.getByRole('button', { name: /^Analyse/ }).click()
  await expect(page.locator('.cw-result')).toBeVisible()
}

test('one headline, upload above the fold, interactive body map, result report, guide link and history', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.setViewportSize({ width: 1366, height: 768 })
  await mockApi(page)
  await page.goto('/#cancer')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Cancer care intelligence')
  await expect(page.locator('main h2').filter({ hasText: /clearer picture|right image for the right model/ })).toHaveCount(0)
  await expect(page.locator('.demo-badge')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Increase text size' })).toContainText('Text size')
  expect((await page.locator('.cw-dropzone').boundingBox())!.y).toBeLessThan(768)
  await page.locator('[data-map-area="breast"] .cw-map-dot').click()
  await expect(page.getByRole('radio', { name: 'Breast' }).first()).toHaveAttribute('aria-checked', 'true')
  await expect(page.locator('.cw-area-card.selected')).toContainText('Breast')
  await analyse(page, 'Oral', 'oral-malignant-reference.png')
  const card = page.locator('.cw-result')
  await expect(card).toContainText('Not a medical diagnosis')
  await expect(card.getByRole('heading', { name: 'Possible malignant mouth lesion' })).toBeVisible()
  await expect(card.getByRole('meter')).toHaveAttribute('aria-valuenow', '90')
  await expect(card).toContainText('dentist or doctor')
  await expect(card.locator('canvas')).toBeVisible()
  await card.getByRole('button', { name: 'Image', exact: true }).click()
  await expect(card.locator('canvas')).toBeHidden()
  await card.getByRole('checkbox', { name: /^Save this report/ }).check()
  await card.getByRole('button', { name: 'Save to history' }).click()
  await expect(card.getByText('Saved to History')).toBeVisible()
  await card.getByRole('button', { name: /Read the Mouth & oral cavity guide/ }).click()
  await expect(page.locator('#care-topic-heading')).toHaveText('Mouth & oral cavity')
  await page.locator('.sidebar').getByRole('button', { name: 'History' }).click()
  await expect(page.getByRole('heading', { name: 'Cancer research reports' })).toBeVisible()
  await page.getByRole('button', { name: 'Open report' }).click()
  await expect(page.locator('.cw-report-dialog')).toContainText('Possible malignant mouth lesion')
  expect(errors).toEqual([])
})

test('a wrong image type is rejected with a reason and nothing to save', async ({ page }) => {
  await mockApi(page)
  await page.goto('/#cancer')
  await analyse(page, 'Lung', 'oral-benign-reference.png')
  await expect(page.locator('.cw-badge').first()).toHaveText(/Image not accepted/i)
  await expect(page.locator('.cw-result')).toContainText('grayscale CT slice')
  await expect(page.getByRole('button', { name: 'Save to history' })).toHaveCount(0)
})

test('mobile layout has no horizontal scrolling and a bottom navigation bar; dark mode persists', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockApi(page)
  await page.goto('/#cancer')
  await expect(page.getByRole('navigation', { name: 'Quick navigation' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)).toBe(false)
  await page.getByRole('button', { name: 'Use dark theme' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.getByRole('button', { name: 'Open the full menu' }).click()
  await expect(page.locator('.sidebar .nav-link').first()).toHaveText('Overview')
})
