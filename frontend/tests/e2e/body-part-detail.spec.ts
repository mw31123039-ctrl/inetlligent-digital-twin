import { test, expect, type Page } from '@playwright/test'

interface AnatomySnapshot { meshes: number; triangles: number; textures: number; camera: number[]; target: number[]; structures: string[] }
async function anatomy(page: Page): Promise<AnatomySnapshot> {
  return page.locator('.anatomy-canvas').evaluate(node => (node as unknown as { __vueParentComponent: { exposed: { getSnapshot(): AnatomySnapshot } } }).__vueParentComponent.exposed.getSnapshot())
}
async function ready(page: Page) {
  await page.goto('/')
  await expect(page.locator('.human-body-viewer')).toHaveAttribute('aria-busy', 'false', { timeout: 30_000 })
}
async function detailReady(page: Page, part = 'eyes') {
  await expect(page.locator('.body-stage')).toHaveAttribute('data-phase', 'detail')
  await expect(page.locator('.body-part-viewer')).toHaveAttribute('data-part', part)
  await expect(page.locator('.body-part-viewer')).toHaveAttribute('aria-busy', 'false')
}
const radius = (state: AnatomySnapshot) => Math.hypot(...state.camera.map((value, i) => value - state.target[i]!))

test('complete eye flow: camera opening, real geometry, orbit, zoom, 2D atlas and return; symptoms survive', async ({ page }) => {
  test.setTimeout(90_000)
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message))
  await ready(page)
  await expect(page.locator('.body-part-viewer')).toHaveCount(0)
  const initial = await page.locator('.human-body-viewer').evaluate(node => (node as any).__vueParentComponent.exposed.getSnapshot().camera as number[])
  await page.getByRole('button', { name: 'Eyes', exact: true }).click()
  await expect(page.locator('.body-stage')).toHaveAttribute('data-phase', 'focusing')
  await expect.poll(async () => page.locator('.human-body-viewer').evaluate(node => (node as any).__vueParentComponent.exposed.getSnapshot().camera[2] as number)).toBeLessThan(initial[2]! - .15)
  await detailReady(page)
  await expect(page.getByRole('heading', { name: 'Left eye', exact: true })).toBeVisible()
  await page.screenshot({ path: 'test-results/eye-detail-3d.png', fullPage: true })
  const original = await anatomy(page)
  expect(original.meshes).toBeGreaterThan(20); expect(original.triangles).toBeGreaterThan(10_000); expect(original.textures).toBe(1)
  expect(original.structures).toEqual(expect.arrayContaining(['Sclera', 'Iris', 'Pupil', 'Cornea', 'Optic nerve']))
  const box = (await page.locator('.anatomy-canvas').boundingBox())!
  await page.mouse.move(box.x + box.width * .48, box.y + box.height * .5); await page.mouse.down()
  await page.mouse.move(box.x + box.width * .75, box.y + box.height * .6, { steps: 10 }); await page.mouse.up()
  await expect.poll(async () => (await anatomy(page)).camera).not.toEqual(original.camera)
  await page.getByRole('button', { name: 'Reset View', exact: true }).click()
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  await page.mouse.wheel(0, -240)
  await expect.poll(async () => radius(await anatomy(page))).toBeLessThan(radius(original) - .2)
  await page.locator('.anatomy-canvas').focus(); await page.keyboard.press('Shift+ArrowRight')
  await expect.poll(async () => (await anatomy(page)).target[0]).not.toBe(0)
  // Rotating beyond a complete revolution is unrestricted in 3D.
  for (let i = 0; i < 38; i++) await page.keyboard.press('ArrowRight')
  await page.getByRole('checkbox', { name: 'Auto Rotate', exact: true }).check()
  const autoBefore = (await anatomy(page)).camera
  await expect.poll(async () => (await anatomy(page)).camera).not.toEqual(autoBefore)
  await page.getByRole('checkbox', { name: 'Auto Rotate', exact: true }).uncheck()
  await page.getByRole('button', { name: 'Right', exact: true }).click(); await detailReady(page)
  await expect(page.locator('.region-pill')).toContainText('Right eye')
  await page.getByRole('button', { name: 'My eyes hurt', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Both eyes', exact: true })).toBeVisible()
  const input = page.getByRole('textbox', { name: 'Describe your symptoms', exact: true })
  await input.fill('Keep this unsent note')
  const transcript = await page.locator('.conversation').innerText()
  await page.getByRole('button', { name: '2D', exact: true }).click(); await detailReady(page)
  await expect(page.locator('.body-part-viewer')).toHaveAttribute('data-side', 'right')
  await expect(page.locator('.anatomy-canvas')).toHaveCount(0)
  await expect(page.locator('.anatomy-illustration img')).toBeVisible()
  await page.getByRole('button', { name: 'Cross-section', exact: true }).click(); await detailReady(page)
  await expect(page.locator('.anatomy-illustration img')).toHaveAttribute('src', /eyes-section\.svg$/)
  await page.screenshot({ path: 'test-results/eye-detail-2d.png', fullPage: true })
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click()
  await page.locator('.anatomy-illustration').focus(); await page.keyboard.press('ArrowRight')
  await expect(page.locator('.anatomy-illustration img')).toHaveAttribute('style', /translate\(20px, 0px\) scale\(1\.18\)/)
  await expect(input).toHaveValue('Keep this unsent note'); expect(await page.locator('.conversation').innerText()).toBe(transcript)
  await page.getByRole('button', { name: '3D', exact: true }).click(); await detailReady(page)
  await expect(input).toHaveValue('Keep this unsent note'); expect(await page.locator('.conversation').innerText()).toBe(transcript)
  await page.getByRole('button', { name: '2D', exact: true }).click(); await detailReady(page)
  await page.getByRole('button', { name: 'Back to full body', exact: true }).click()
  await expect(page.locator('.body-stage')).toHaveAttribute('data-phase', 'full')
  await expect(page.locator('.body-svg')).toBeVisible()
  await page.getByRole('button', { name: '3D', exact: true }).click()
  await expect(page.locator('.human-body-viewer')).toHaveAttribute('aria-busy', 'false', { timeout: 30_000 })
  await expect(page.locator('.human-body-viewer')).toBeVisible(); await expect(page.locator('.body-part-viewer')).toHaveCount(0)
  expect(errors).toEqual([])
  await page.screenshot({ path: 'test-results/detail-flow-full-body.png', fullPage: true })
})

test('all six body areas open from the actual full-body model and buttons; patient side matches anterior coordinates', async ({ page }) => {
  test.setTimeout(150_000)
  await page.emulateMedia({ reducedMotion: 'reduce' }); await ready(page)
  for (const part of ['eyes', 'head', 'chest', 'abdomen', 'arms', 'legs']) {
    const point = await page.locator('.human-body-viewer').evaluate((node, id) => (node as any).__vueParentComponent.exposed.getSnapshot().regions[id] as { x: number; y: number }, part)
    const box = (await page.locator('.human-body-viewer').boundingBox())!
    await page.mouse.click(box.x + point.x, box.y + point.y); await detailReady(page, part)
    expect((await anatomy(page)).meshes).toBeGreaterThan(3)
    if (part === 'eyes') await expect(page.getByRole('heading', { name: 'Right eye', exact: true })).toBeVisible()
    await page.getByRole('button', { name: '2D', exact: true }).click(); await detailReady(page, part)
    for (const view of ['Side', 'Cross-section', 'Front']) { await page.getByRole('button', { name: view, exact: true }).click(); await detailReady(page, part); expect(await page.locator('.anatomy-illustration img').evaluate(node => (node as HTMLImageElement).naturalWidth)).toBeGreaterThan(0) }
    await page.getByRole('button', { name: '3D', exact: true }).click(); await detailReady(page, part)
    await page.getByRole('button', { name: 'Back to full body', exact: true }).click()
  }
  for (const part of ['Eyes', 'Head', 'Chest', 'Abdomen', 'Arms', 'Legs']) { await page.getByRole('button', { name: part, exact: true }).click(); await detailReady(page, part.toLowerCase()); await page.getByRole('button', { name: 'Back to full body', exact: true }).click() }
})

test('detail loading and error recovery; rapid selections and a canceled opening do not leave a stale view', async ({ page }) => {
  let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/src/three/anatomyModels.ts*', async route => { await gate; await route.abort() })
  await ready(page); await page.getByRole('button', { name: 'Eyes', exact: true }).click()
  await expect(page.getByText('Loading left eye', { exact: true })).toBeVisible()
  release(); await expect(page.getByRole('alert')).toContainText('detailed model could not load')
  await page.getByRole('button', { name: 'Use 2D instead', exact: true }).click(); await detailReady(page)
  await page.route('**/illustrations/head-front.svg', route => route.fulfill({ status: 404, body: 'Missing' }))
  await page.getByRole('button', { name: 'Head', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('illustration could not load')
  await page.unroute('**/illustrations/head-front.svg'); await page.getByRole('button', { name: 'Retry illustration' }).click(); await detailReady(page, 'head')
  await page.getByRole('button', { name: 'Back to full body', exact: true }).click()
  await page.getByRole('button', { name: 'Eyes', exact: true }).click(); await page.getByRole('button', { name: 'Legs', exact: true }).click(); await page.getByRole('button', { name: 'Chest', exact: true }).click(); await detailReady(page, 'chest')
  await page.getByRole('button', { name: 'Back to full body', exact: true }).click()
  await page.getByRole('button', { name: 'Eyes', exact: true }).click(); await page.locator('.region-selector button.selected').press('Escape')
  await expect(page.locator('.body-stage')).toHaveAttribute('data-phase', 'full'); await page.waitForTimeout(1100)
  await expect(page.locator('.body-part-viewer')).toHaveCount(0)
})

test('mobile touch rotation, pinch, 2D pan, keyboard return and reduced motion', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, reducedMotion: 'reduce' })
  const page = await context.newPage()
  try {
    await ready(page); await page.getByRole('button', { name: 'Eyes', exact: true }).tap(); await detailReady(page)
    await expect(page.getByRole('checkbox', { name: 'Auto Rotate', exact: true })).toBeDisabled()
    await page.screenshot({ path: 'test-results/eye-detail-mobile.png', fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.locator('.anatomy-canvas').scrollIntoViewIfNeeded()
    const box = (await page.locator('.anatomy-canvas').boundingBox())!, x = box.x + box.width / 2, y = box.y + box.height / 2
    const cdp = await context.newCDPSession(page), original = await anatomy(page)
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] })
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: x + 70, y }] })
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
    await expect.poll(async () => (await anatomy(page)).camera).not.toEqual(original.camera)
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: x - 30, y }, { x: x + 30, y }] })
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: x - 60, y }, { x: x + 60, y }] })
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
    await expect.poll(async () => radius(await anatomy(page))).toBeLessThan(radius(original) - .1)
    await page.getByRole('button', { name: '2D', exact: true }).tap(); await detailReady(page)
    const image = page.locator('.anatomy-illustration'); await image.scrollIntoViewIfNeeded(); const ib = (await image.boundingBox())!
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: ib.x + 150, y: ib.y + 100 }] })
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: ib.x + 195, y: ib.y + 140 }] })
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
    await expect(image.locator('img')).toHaveAttribute('style', /translate\(45px, 40px\)/)
    await image.focus(); await page.keyboard.press('Escape')
    await expect(page.locator('.body-stage')).toHaveAttribute('data-phase', 'full')
  } finally { await context.close() }
})
