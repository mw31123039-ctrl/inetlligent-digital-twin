import { chromium } from 'playwright'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']})
const context=await browser.newContext({viewport:{width:1440,height:1100},permissions:['clipboard-read','clipboard-write']})
const page=await context.newPage();page.setDefaultTimeout(15000);const errors=[];page.on('pageerror',e=>errors.push(e.message));fs.mkdirSync('test-results',{recursive:true})
try{
 await page.goto((process.env.HUMANTWIN_EYE_URL||'http://127.0.0.1:5173')+'/#eye-chat')
 const card=page.getByTestId('inline-eye-assistant');await card.locator('.eye-ack input').check()
 await card.locator('.eye-answer-input input').fill('Sudden severe pain in my left eye, 9/10')
 await card.getByRole('button',{name:'Send answer',exact:false}).click()
 const advice=card.getByTestId('eye-care-advice');await advice.waitFor()
 assert.match(await advice.getByTestId('eye-doctor-route').innerText(),/Emergency department/)
 assert.match(await advice.innerText(),/Do not wait for a routine appointment/)
 assert.equal(await advice.locator('[data-care-step="screen-breaks"]').count(),0)
 await advice.locator('.eye-doctor-summary>summary').click()
 await advice.getByRole('button',{name:'Copy doctor summary',exact:true}).click()
 assert.match(await page.evaluate(()=>navigator.clipboard.readText()),/9\/10/)
 const downloaded=page.waitForEvent('download');await advice.getByRole('button',{name:'Download doctor summary',exact:true}).click();assert.match((await downloaded).suggestedFilename(),/^humantwin-eye-doctor-/)
 assert.equal(await card.locator('form.eye-question').count(),0)
 await page.evaluate(()=>window.scrollTo(0,document.querySelector('.eye-care-advice').getBoundingClientRect().top+scrollY-120));await page.screenshot({path:'test-results/eye-care-desktop.png',fullPage:true})
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2))
 await page.getByRole('button',{name:/3D anatomy & saved summary/}).click();await page.getByLabel('Eye explorer language').selectOption('ar-IQ');await page.locator('.eye-main-tabs button').nth(1).click()
 assert.match(await page.locator('.eye-interview-panel').getByTestId('eye-doctor-route').innerText(),/طوارئ/)
 assert.equal(await page.locator('.eye-workspace').getAttribute('dir'),'rtl')
 assert.deepEqual(errors,[]);console.log('PASS: emergency care advice, ophthalmology recommendation, no home-care delay, clipboard and downloadable doctor handoff, stopped questioning, mobile and Arabic RTL.')
}finally{await browser.close()}
