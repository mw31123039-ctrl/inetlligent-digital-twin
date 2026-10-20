import { test, expect, type Page } from '@playwright/test'

interface Snapshot {
  loaded: boolean; animated: boolean; animationTime: number; skinnedMeshes: number; skinTextures: number; bones: number
  camera: number[]; deformedVertex: number[]; chestTransform: number[]; eyeAnchor: number[]
  regions: Record<string, { x: number; y: number }>
}
async function snapshot(page: Page): Promise<Snapshot> {
  return page.locator('.human-body-viewer').evaluate(node => (node as unknown as { __vueParentComponent: { exposed: { getSnapshot(): Snapshot } } }).__vueParentComponent.exposed.getSnapshot())
}
async function ready(page: Page) {
  const demo = page.getByRole('button', { name: 'Scripted demo', exact: true }); if (await demo.getAttribute('aria-pressed') === 'false') await demo.click()
  await expect(page.locator('.human-body-viewer')).toHaveAttribute('aria-busy', 'false')
  await expect(page.getByText('Preparing your digital twin')).not.toBeVisible()
}
async function selectOnModel(page: Page, region: string, touch = false) {
  const state = await snapshot(page)
  const point = state.regions[region]!
  const box = (await page.locator('.human-body-viewer').boundingBox())!
  if (touch) await page.touchscreen.tap(box.x + point.x, box.y + point.y)
  else await page.mouse.click(box.x + point.x, box.y + point.y)
}

test('real textured GLB, skeletal breathing, following zones, pause and resume', async ({ page, request }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  const response = await request.get('/models/human.glb')
  expect(response.ok()).toBe(true)
  const glb = await response.body()
  expect(glb.subarray(0, 4).toString()).toBe('glTF')
  expect((await request.get('/models/LICENSE-Rocketbox.txt')).ok()).toBe(true)
  await page.goto('/')
  await ready(page)
  const before = await snapshot(page)
  expect(before.skinnedMeshes).toBeGreaterThan(0)
  expect(before.skinTextures).toBeGreaterThanOrEqual(2)
  expect(before.bones).toBeGreaterThan(30)
  expect(before.animated).toBe(true)
  await expect.poll(async () => (await snapshot(page)).deformedVertex).not.toEqual(before.deformedVertex)
  await expect.poll(async () => (await snapshot(page)).eyeAnchor).not.toEqual(before.eyeAnchor)
  await page.getByRole('button', { name: 'Pause motion', exact: true }).click()
  const paused = await snapshot(page)
  await page.waitForTimeout(350)
  expect((await snapshot(page)).animationTime).toBe(paused.animationTime)
  await page.getByRole('button', { name: 'Resume motion', exact: true }).click()
  await expect.poll(async () => (await snapshot(page)).animationTime).toBeGreaterThan(paused.animationTime)
  expect(errors).toEqual([])
})

test('raycast all six animated areas and complete the eyes questionnaire', async ({ page }) => {
  await page.goto('/')
  await ready(page)
  const symptoms: Record<string, string> = { chest: 'Chest discomfort', abdomen: 'My stomach hurts', arms: 'My arm hurts', legs: 'My leg hurts', head: 'I have a headache', eyes: 'My eyes hurt' }
  for (const [region, symptom] of Object.entries(symptoms)) {
    await selectOnModel(page, region)
    await expect(page.locator('.region-selector button.selected')).toHaveText(new RegExp(region, 'i'))
    await expect(page.locator('.human-region-label')).toHaveText(new RegExp(region, 'i'))
    await expect(page.getByRole('button', { name: symptom, exact: true })).toBeVisible()
  }
  await page.getByRole('button', { name: 'My eyes hurt', exact: true }).click()
  await page.getByRole('button', { name: 'Both eyes', exact: true }).click()
  await page.getByRole('button', { name: 'A few days', exact: true }).click()
  await page.getByRole('button', { name: 'Comes and goes', exact: true }).click()
  await expect(page.getByText('Your demo assessment is complete', { exact: true })).toBeVisible()
})

test('smooth side/front/back transitions, drag rotation, zoom and reset', async ({ page }) => {
  await page.goto('/')
  await ready(page)
  for (const side of ['Left side', 'Right side']) {
    await page.getByRole('button', { name: side, exact: true }).click()
    await expect.poll(async () => Math.abs((await snapshot(page)).camera[2]!)).toBeLessThan(.1)
    expect(Math.abs((await snapshot(page)).camera[0]!)).toBeGreaterThan(2)
  }
  await page.getByRole('button', { name: 'Back', exact: true }).click()
  await expect.poll(async () => (await snapshot(page)).camera[2]).toBeLessThan(-3)
  // The invisible eye zones must not be selectable through the back of the head.
  await selectOnModel(page, 'head')
  await expect(page.locator('.region-selector button.selected')).toHaveText('Head')
  await page.getByRole('button', { name: 'Front', exact: true }).click()
  await expect.poll(async () => (await snapshot(page)).camera[2]).toBeGreaterThan(3)
  await page.locator('.human-body-viewer').focus()
  await page.keyboard.press('ArrowRight')
  await expect.poll(async () => Math.abs((await snapshot(page)).camera[0]!)).toBeGreaterThan(.1)
  // Re-selecting an already active preset must restore its exact direction.
  await page.getByRole('button', { name: 'Front', exact: true }).click()
  await expect.poll(async () => Math.abs((await snapshot(page)).camera[0]!)).toBeLessThan(.02)
  const box = (await page.locator('.human-body-viewer').boundingBox())!
  const beforeDrag = (await snapshot(page)).camera
  await page.mouse.move(box.x + box.width / 2, box.y + box.height * .6)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width / 2 + 110, box.y + box.height * .6, { steps: 12 })
  await page.mouse.up()
  await expect.poll(async () => (await snapshot(page)).camera).not.toEqual(beforeDrag)
  const distance = (state: Snapshot) => Math.hypot(state.camera[0]!, state.camera[1]! - .92, state.camera[2]!)
  const beforeZoom = distance(await snapshot(page))
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click()
  await expect.poll(async () => distance(await snapshot(page))).toBeLessThan(beforeZoom - .1)
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  const beforeWheel = distance(await snapshot(page))
  await page.mouse.wheel(0, -120)
  await expect.poll(async () => distance(await snapshot(page))).toBeLessThan(beforeWheel - .05)
  await page.getByRole('button', { name: 'Reset', exact: true }).click()
  await expect.poll(async () => Math.abs((await snapshot(page)).camera[0]!)).toBeLessThan(.02)
  await expect.poll(async () => distance(await snapshot(page))).toBeCloseTo(3.844, 1)
})

test('loading progress, missing-model error, retry and repeated 2D/3D mounts', async ({ page }) => {
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  const brokenModel = async (route: import('@playwright/test').Route) => {
    await gate
    await route.fulfill({ status: 404, body: 'Model missing' })
  }
  await page.route('**/models/human.glb', brokenModel)
  await page.goto('/')
  await expect(page.getByRole('progressbar', { name: 'Human model loading progress' })).toBeVisible()
  release()
  await expect(page.getByRole('alert')).toContainText('human model could not load')
  await expect(page.getByRole('button', { name: 'Use 2D instead' })).toBeVisible()
  await page.unroute('**/models/human.glb', brokenModel)
  await page.getByRole('button', { name: 'Retry 3D', exact: true }).click()
  await ready(page)
  for (let i = 0; i < 2; i++) {
    await page.getByRole('button', { name: '2D', exact: true }).click()
    await expect(page.locator('.body-canvas canvas')).toHaveCount(0)
    await expect(page.locator('.body-svg')).toBeVisible()
    await page.getByRole('button', { name: '3D', exact: true }).click()
    await ready(page)
    await expect(page.locator('.body-canvas canvas')).toHaveCount(1)
  }
})

test('mobile touch selection and rotation, responsive layout, reduced motion', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, reducedMotion: 'reduce' })
  const page = await context.newPage()
  try {
    await page.goto('/')
    await ready(page)
    expect((await snapshot(page)).animated).toBe(false)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await selectOnModel(page, 'chest', true)
    await expect(page.getByRole('button', { name: 'Chest discomfort', exact: true })).toBeVisible()
    await selectOnModel(page, 'eyes', true)
    await expect(page.getByRole('button', { name: 'My eyes hurt', exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Left side', exact: true }).tap()
    expect(Math.abs((await snapshot(page)).camera[0]!)).toBeGreaterThan(2)
    await page.getByRole('button', { name: 'Reset', exact: true }).tap()
    const box = (await page.locator('.human-body-viewer').boundingBox())!
    const cdp = await context.newCDPSession(page)
    const x = box.x + box.width / 2, y = box.y + box.height * .6
    const before = (await snapshot(page)).camera
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] })
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: x + 60, y }] })
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
    await expect.poll(async () => (await snapshot(page)).camera).not.toEqual(before)
    const radius = (state: Snapshot) => Math.hypot(state.camera[0]!, state.camera[1]! - .92, state.camera[2]!)
    const beforePinch = radius(await snapshot(page))
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: x - 30, y }, { x: x + 30, y }] })
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: x - 60, y }, { x: x + 60, y }] })
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
    await expect.poll(async () => radius(await snapshot(page))).toBeLessThan(beforePinch - .1)
    await expect(page.locator('.region-selector button.selected')).toHaveText('Eyes')
  } finally { await context.close() }
})
