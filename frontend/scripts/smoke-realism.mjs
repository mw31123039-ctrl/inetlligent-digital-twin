import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'

const url = process.env.HUMANTWIN_EYE_URL || 'http://127.0.0.1:5174'
const output = path.resolve('test-results/realism')
await fs.mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: process.env.HUMANTWIN_BROWSER_CHANNEL || (process.platform === 'win32' ? 'chrome' : undefined),
  headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] })
const errors = [], shaderErrors = [], failedAssets = [], loadedAssets = new Set()
let page
function inspect(current) {
  current.setDefaultTimeout(30000)
  current.on('pageerror', error => errors.push(error.message))
  current.on('console', message => { if (message.type() === 'error' && /Shader Error|WebGLProgram|GL_INVALID/.test(message.text())) shaderErrors.push(message.text()) })
  current.on('response', response => { if (/\/(models|textures)\//.test(response.url())) { if (!response.ok()) failedAssets.push(response.url()); else loadedAssets.add(new URL(response.url()).pathname) } })
}
async function paint(current) { await current.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))) }
try {
  page = await browser.newPage({ viewport: { width: 1440, height: 1100 } }); inspect(page)
  await page.goto(url + '/#twin')
  const human = page.locator('.twin-human-preview .human-body-viewer')
  await human.locator('canvas').waitFor()
  await page.waitForFunction(() => document.querySelector('.twin-human-preview .human-body-viewer')?.getAttribute('aria-busy') === 'false')
  assert.ok(loadedAssets.has('/models/human-detailed.glb'))
  await page.locator('.twin-human-preview').screenshot({ path: path.join(output, 'human.png'), animations: 'disabled' })
  await page.getByRole('button', { name: 'Load synthetic example', exact: true }).click()
  await page.locator('.twin-capture .human-body-viewer[aria-busy=false]').waitFor()
  assert.match(await page.getByTestId('twin-projection').innerText(), /Experimental projection:/)

  // Fresh document: hash-only navigation must not be mistaken for a component reload.
  const irisResponse = page.waitForResponse(response => response.url().endsWith('/textures/eye/brown_eye.png') && response.ok())
  await page.goto(url + '/?realism=eye#eye')
  await page.locator('.eye-model-stage canvas').waitFor()
  await (await irisResponse).finished(); await paint(page)
  assert.equal(await page.locator('.eye-model-stage').getAttribute('data-view'), 'external')
  await page.locator('.eye-model-stage').screenshot({ path: path.join(output, 'eye-surface.png'), animations: 'disabled' })
  await page.locator('[data-structure-id="eye.iris"]').click()
  await page.getByLabel('Isolate selection', { exact: true }).check()
  assert.equal(await page.locator('[data-structure-id="eye.iris"]').getAttribute('aria-pressed'), 'true')
  assert.equal(await page.getByLabel('Isolate selection', { exact: true }).isChecked(), true)
  await page.getByLabel('Isolate selection', { exact: true }).uncheck()
  await page.locator('[data-structure-id="eye.lens"]').click()
  assert.equal(await page.locator('.eye-model-stage').getAttribute('data-view'), 'section')
  await page.locator('[data-structure-id="eye.photoreceptors"]').click()
  assert.equal(await page.locator('.eye-model-stage').getAttribute('data-view'), 'retinal-detail')
  await page.getByRole('button', { name: 'Back to body explorer', exact: false }).click()
  for (const region of ['Head', 'Chest', 'Abdomen']) {
    await page.locator('.region-selector').getByRole('button', { name: region, exact: true }).click()
    const part = page.locator(`.body-part-viewer[data-part="${region.toLowerCase()}"]`)
    await part.waitFor()
    await page.waitForFunction(region => document.querySelector(`.body-part-viewer[data-part="${region}"]`)?.getAttribute('aria-busy') === 'false', region.toLowerCase())
    const canvas = part.locator('.anatomy-canvas')
    await canvas.locator('canvas').waitFor()
    if (['Arms', 'Legs'].includes(region)) {
      await part.getByRole('button', { name: 'Right', exact: true }).click()
      await page.waitForFunction(region => document.querySelector(`.body-part-viewer[data-part="${region}"]`)?.getAttribute('aria-busy') === 'false', region.toLowerCase())
      assert.equal(await part.getAttribute('data-side'), 'right')
    }
    await part.locator('.part-model-stage').screenshot({ path: path.join(output, region.toLowerCase() + '.png'), animations: 'disabled' })
    if (region === 'Chest') {
      assert.ok(loadedAssets.has('/models/anatomy/chest-surface.glb'))
      await part.getByRole('button', { name: 'Vessels and ribs', exact: true }).click()
      await page.waitForFunction(() => document.querySelector('.body-part-viewer[data-part="chest"]')?.getAttribute('aria-busy') === 'false')
      await part.locator('.anatomy-canvas canvas').waitFor()
      await part.locator('.part-model-stage').screenshot({ path: path.join(output, 'chest-vessels.png'), animations: 'disabled' })
    }
    await page.getByRole('button', { name: 'Back to full body', exact: true }).click()
  }
  const phone = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true }); inspect(phone)
  await phone.goto(url + '/#twin')
  await phone.locator('.twin-human-preview .human-body-viewer[aria-busy=false]').waitFor()
  assert.ok(await phone.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2))
  await phone.screenshot({ path: path.join(output, 'mobile-twin.png'), fullPage: true, animations: 'disabled' })
  const phoneIris = phone.waitForResponse(response => response.url().endsWith('/textures/eye/brown_eye.png') && response.ok())
  await phone.goto(url + '/?realism=phone-eye#eye')
  await phone.locator('.eye-model-stage canvas').waitFor()
  await (await phoneIris).finished(); await paint(phone)
  await phone.locator('.eye-model-stage').screenshot({ path: path.join(output, 'mobile-eye.png'), animations: 'disabled' })
  for (const model of ['head', 'chest', 'abdomen']) assert.ok(loadedAssets.has(`/models/anatomy/${model}.glb`), model)
  assert.deepEqual(errors, []); assert.deepEqual(shaderErrors, []); assert.deepEqual(failedAssets, [])
  console.log('PASS: textured 3D human; source iris and isolation; internal layers; lung/heart surfaces plus vascular chest view; sided reference anatomy; mobile fit; no page, shader or asset-load errors.')
} catch (error) {
  console.error(JSON.stringify({ errors, shaderErrors, failedAssets }))
  if (page) { console.error((await page.locator('body').innerText()).slice(-3000)); await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }) }
  throw error
} finally { await browser.close() }
