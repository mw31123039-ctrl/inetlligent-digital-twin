import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath, pathToFileURL } from 'node:url'

const require = createRequire(new URL('../../frontend/package.json', import.meta.url))
const { chromium } = require('@playwright/test')
const results = fileURLToPath(new URL('../results/latest/', import.meta.url))
await fs.access(path.join(results, 'report.html'))
const data = JSON.parse(await fs.readFile(path.join(results, 'report.json'), 'utf8'))
const channel = process.env.HUMANTWIN_BROWSER_CHANNEL || (process.platform === 'win32' ? 'chrome' : undefined)
const browser = await chromium.launch({ channel, headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
  const errors = [], network = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('request', request => { if (/^https?:/i.test(request.url())) network.push(request.url()) })
  await page.goto(pathToFileURL(path.join(results, 'report.html')).href)
  assert.equal(await page.locator('#rows > tr').count(), data.systems.full.rows.length)
  const agreement = data.systems.full.summaries['all/all'].urgency_agreement.value
  assert.ok((await page.locator('#cards').innerText()).includes((agreement * 100).toFixed(1) + '%'))
  await page.selectOption('#outcome', 'fail')
  assert.equal(await page.locator('#rows > tr').count(), data.systems.full.rows.filter(row => !row.policy_pass).length)
  await page.selectOption('#locale', 'ckb')
  assert.equal(await page.locator('#rows > tr').count(), data.systems.full.rows.filter(row => row.locale === 'ckb' && !row.policy_pass).length)
  await page.fill('#search', 'historical')
  assert.equal(await page.locator('#rows > tr').count(), 1)
  await page.locator('#rows summary').click()
  assert.match(await page.locator('#rows').innerText(), /چەند ساڵ/)
  await page.fill('#search', '')
  await page.selectOption('#locale', 'all')
  await page.selectOption('#outcome', 'all')
  await page.selectOption('#system', 'latest_turn_only')
  assert.match(await page.locator('#description').innerText(), /fresh session/)
  await page.selectOption('#split', 'evaluation')
  assert.equal(await page.locator('#rows > tr').count(), data.systems.latest_turn_only.rows.filter(row => row.split === 'evaluation').length)
  await page.selectOption('#system', 'full')
  await page.selectOption('#split', 'all')
  await page.screenshot({ path: path.join(results, 'report-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2), 'Report overflows on mobile')
  await page.screenshot({ path: path.join(results, 'report-mobile.png'), fullPage: true })
  assert.equal(await page.getByRole('link', { name: 'JSON and traces' }).getAttribute('href'), 'report.json')
  assert.deepEqual(network, [], 'Offline report must not make network requests')
  assert.deepEqual(errors, [], 'Report must have no browser script errors')
  console.log('PASS: offline report renders; filters match JSON; Sorani trace survives; ablation and partition controls work; desktop/mobile fit; no network requests or browser errors.')
} finally {
  await browser.close()
}
