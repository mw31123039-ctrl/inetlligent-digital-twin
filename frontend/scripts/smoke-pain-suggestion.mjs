import {chromium} from 'playwright'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']})
const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(15000);fs.mkdirSync('test-results',{recursive:true})
try{
 await page.goto((process.env.HUMANTWIN_EYE_URL||'http://127.0.0.1:5173')+'/#eye-chat');const card=page.getByTestId('inline-eye-assistant');await card.locator('.eye-ack input').check()
 await card.locator('.eye-answer-input input').fill('Moderate eye pain distracts me');await card.getByRole('button',{name:'Send answer',exact:false}).click()
 assert.match(await card.getByTestId('pain-suggested-score').innerText(),/5/)
 assert.match(await card.getByTestId('eye-pain-feedback').innerText(),/until you confirm/)
 await card.getByRole('button',{name:'Yes, use this estimate',exact:true}).click();assert.match(await card.getByTestId('eye-pain-feedback').innerText(),/confirmed.*5\/10/)
 await card.locator('.eye-pain-manual-toggle').click();await card.getByRole('button',{name:'Pain 3 out of 10',exact:true}).click();assert.match(await card.getByTestId('eye-pain-feedback').innerText(),/You reported 3\/10/)
 await card.getByRole('button',{name:'Start over',exact:true}).click();await card.locator('.eye-answer-input input').fill('My left eye hurts');await card.getByRole('button',{name:'Send answer',exact:false}).click()
 for(const value of ['No change','No','Gradually'])await card.locator('.eye-question').getByRole('button',{name:value,exact:true}).click()
 await card.locator('.eye-question').getByRole('button',{name:'Moderate pain',exact:true}).click();await card.locator('.eye-question').getByRole('button',{name:'I can do them, but it is distracting',exact:true}).click()
 assert.match(await card.getByTestId('pain-suggested-score').innerText(),/5/);await card.getByRole('button',{name:'Yes, use this estimate',exact:true}).click();assert.match(await card.getByTestId('eye-pain-feedback').innerText(),/confirmed.*5\/10/)
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));await page.screenshot({path:'test-results/pain-suggestion.png',fullPage:true})
 await card.getByRole('button',{name:'Start over',exact:true}).click();await card.locator('.eye-answer-input input').fill('Sudden severe eye pain');await card.getByRole('button',{name:'Send answer',exact:false}).click()
 assert.match(await card.getByTestId('eye-urgency').innerText(),/Emergency assessment now/);assert.equal(await card.getByRole('button',{name:'Yes, use this estimate',exact:true}).isDisabled(),true);assert.equal(await card.locator('form.eye-question').count(),0)
 assert.deepEqual(errors,[]);console.log('PASS: automatic proposal from narrative; guided words/activity flow; confirmation; manual correction; mobile layout; emergency safeguards.')
}finally{await browser.close()}
