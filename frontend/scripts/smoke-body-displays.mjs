// Software/graphics integration with licensed references and a local, explicitly labelled test model.
import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import fs from 'node:fs/promises'
import path from 'node:path'
import { chromium, expect as browserExpect } from '@playwright/test'
const expect = browserExpect.configure({ timeout: 30000 })

const base = process.env.HUMANTWIN_EYE_URL || 'http://127.0.0.1:5173'
const output = path.resolve('test-results/body-displays')
await fs.mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: process.env.HUMANTWIN_BROWSER_CHANNEL || (process.platform === 'win32' ? 'chrome' : undefined), headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] })
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } })
page.setDefaultTimeout(60000)
const errors = [], remoteRequests = [], filePosts = []
page.on('pageerror', error => errors.push(error.message))
page.on('request', request => {
  if (/^https?:/.test(request.url()) && !request.url().startsWith(base + '/')) remoteRequests.push(request.url())
  if (request.method() === 'POST' && /model|avatar|body/i.test(request.url())) filePosts.push(request.url())
})
async function snapshot() { return page.locator('.human-body-viewer').first().evaluate(node => node.humanTwinSnapshot()) }
async function ready(kind) {
  await expect(page.locator(`.human-body-viewer[data-body-kind="${kind}"]`).first()).toHaveAttribute('aria-busy', 'false', { timeout: 60000 })
  assert.equal((await snapshot()).displayKind, kind)
}
async function register() {
  await page.locator('.header-sign-in').click()
  await page.getByRole('dialog').getByRole('button', { name: 'Create an account', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Create your account' })
  await dialog.getByLabel('Email', { exact: true }).fill(`body-display-check-${randomBytes(8).toString('hex')}@example.invalid`)
  await dialog.getByLabel('Password', { exact: true }).fill(randomBytes(20).toString('base64url'))
  await dialog.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.locator('.profile-button')).toContainText('Member')
}
async function screenshot(name) { await page.locator('.viewer-panel').screenshot({ path: path.join(output, name), animations: 'disabled' }) }
try {
  await page.goto(base + '/#body')
  await ready('reference')
  const tools = await page.locator('.viewer-panel>.viewer-topbar').boundingBox()
  const heading = await page.locator('.viewer-panel .body-display-heading').boundingBox()
  assert.ok(heading.y >= tools.y + tools.height, 'Body display choices must remain below the viewer toolbar.')
  await page.getByRole('button', { name: 'Organs & bones', exact: true }).click()
  await ready('anatomy')
  const anatomy = await snapshot()
  assert.equal(anatomy.animated, false)
  assert.ok(anatomy.referenceMeshCount > 100)
  assert.ok(anatomy.regions.head.y < anatomy.regions.chest.y)
  assert.ok(anatomy.regions.chest.y < anatomy.regions.abdomen.y)
  assert.ok(anatomy.regions.abdomen.y < anatomy.regions.legs.y)
  const idleFrames = await page.locator('.human-body-viewer').evaluate(async node => {
    await new Promise(resolve => setTimeout(resolve, 250))
    const before = node.humanTwinSnapshot().renderedFrames
    await new Promise(resolve => setTimeout(resolve, 400))
    return node.humanTwinSnapshot().renderedFrames - before
  })
  assert.ok(idleFrames <= 2, 'Static anatomy should not render continuously while idle.')
  await screenshot('anatomy-overview.png')
  const bounds = await page.locator('.human-body-viewer').boundingBox()
  await page.mouse.click(bounds.x + anatomy.regions.chest.x, bounds.y + anatomy.regions.chest.y)
  await expect(page.locator('.body-stage')).toHaveAttribute('data-phase', 'detail')
  await expect(page.locator('.body-part-viewer')).toHaveAttribute('data-part', 'chest')
  await page.getByRole('button', { name: 'Back to full body', exact: true }).click()
  await ready('anatomy')
  await page.reload()
  await ready('anatomy')

  await register()
  await expect(page.getByRole('button', { name: 'Reference person', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await ready('reference')
  await page.getByRole('button', { name: 'My 3D model', exact: true }).click()
  await expect(page.locator('.personal-body-empty')).toBeVisible()
  await expect(page.getByLabel('Attach personal 3D model')).toBeDisabled()
  await page.getByRole('checkbox', { name: 'I own this model or have permission to use it.' }).check()
  await page.getByLabel('Attach personal 3D model').setInputFiles(path.resolve('public/models/human.glb'))
  await ready('personal')
  assert.equal((await snapshot()).animated, false)
  await expect(page.locator('.personal-body-attached')).toContainText('human.glb')
  assert.deepEqual(await page.evaluate(() => Object.keys(localStorage).filter(key => key.includes('bodyDisplay')).map(key => localStorage.getItem(key)).sort()), ['anatomy', 'personal'])
  await screenshot('personal-model-example.png')
  await page.getByRole('button', { name: 'Turn model 90°', exact: true }).click()
  await ready('personal')

  await page.getByRole('button', { name: 'Patient twin', exact: true }).click()
  await ready('personal')
  await expect(page.locator('.twin-human-heading')).toContainText('Personal 3D model')
  await page.getByRole('button', { name: 'Account menu', exact: true }).click()
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Organs & bones', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await ready('anatomy')
  assert.equal(await page.locator('.personal-body-attached').count(), 0)
  await page.getByRole('button', { name: 'My 3D model', exact: true }).click()
  await expect(page.locator('.personal-body-empty')).toBeVisible()
  await expect(page.getByRole('checkbox', { name: 'I own this model or have permission to use it.' })).not.toBeChecked()
  await page.getByRole('checkbox', { name: 'I own this model or have permission to use it.' }).check()
  await page.getByLabel('Attach personal 3D model').setInputFiles({ name: 'invalid.glb', mimeType: 'model/gltf-binary', buffer: Buffer.from('Not a GLB model') })
  await expect(page.locator('.personal-body-error')).toBeVisible()
  await page.reload()
  await expect(page.locator('.personal-body-empty')).toBeVisible()
  assert.equal(await page.locator('.personal-body-attached').count(), 0)

  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: 'Organs & bones', exact: true }).click()
  await ready('anatomy')
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false)
  await page.locator('.twin-human-preview').screenshot({ path: path.join(output, 'mobile-anatomy.png'), animations: 'disabled' })
  await page.goto(base + '/#body')
  await ready('anatomy')
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false)
  assert.deepEqual(errors, []); assert.deepEqual(remoteRequests, []); assert.deepEqual(filePosts, [])
  console.log('PASS: three body displays; common-coordinate anatomy and chest picking; local GLB validation, rotation and privacy; shared twin view; account isolation; saved display preferences; reload clears personal model; mobile fit; no external model requests or uploads.')
} finally { await browser.close() }
