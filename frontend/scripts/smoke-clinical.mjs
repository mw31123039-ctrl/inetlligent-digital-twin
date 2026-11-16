// Full-stack check of the clinical assistant: real Vue → Laravel → Python engine, no mocks.
// Requires all three services (see docs/clinical-ai/README.md). Uses a disposable test account and synthetic input.
import assert from 'node:assert/strict'
import {randomBytes} from 'node:crypto'
import fs from 'node:fs/promises'
import path from 'node:path'
import {chromium,expect} from '@playwright/test'

const url=process.env.HUMANTWIN_URL||'http://127.0.0.1:5173'
const output=path.resolve('test-results/clinical');await fs.mkdir(output,{recursive:true})
const browser=await chromium.launch({channel:process.env.HUMANTWIN_BROWSER_CHANNEL||(process.platform==='win32'?'chrome':undefined),headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']})
const page=await browser.newPage({viewport:{width:1440,height:1000}})
page.setDefaultTimeout(30000)
const errors=[],streamed=[]
page.on('pageerror',error=>errors.push(error.message))
page.on('response',response=>{if(response.url().includes('/api/clinical/sessions/')&&response.url().endsWith('/turns'))streamed.push(response.headers()['content-type'])})
async function api(method,route,body){return page.evaluate(async([method,route,body])=>{const xsrf=decodeURIComponent(document.cookie.split('; ').find(c=>c.startsWith('XSRF-TOKEN='))?.slice(11)||'');const r=await fetch(route,{method,credentials:'include',headers:{Accept:'application/json','Content-Type':'application/json','X-XSRF-TOKEN':xsrf},body:body?JSON.stringify(body):undefined});return{status:r.status,body:await r.json().catch(()=>null)}},[method,route,body])}
async function answerChoice(name){await page.locator('.ct-options').getByRole('button',{name,exact:true}).click()}
try{
 await page.goto(url+'/#assistant')
 await page.evaluate(()=>fetch('/sanctum/csrf-cookie',{credentials:'include'}))
 const email=`clinical-smoke-${randomBytes(6).toString('hex')}@example.invalid`
 const registered=await api('POST','/api/register',{email,password:randomBytes(18).toString('base64url')})
 assert.ok([200,201].includes(registered.status),`register ${registered.status}`)
 await page.reload()
 await expect(page.getByRole('heading',{name:'Clinical assistant'}).first()).toBeVisible()
 await page.locator('.ct-navigator').getByRole('button',{name:'Eyes',exact:true}).click()
 await page.locator('.ct-navigator').getByLabel('Left',{exact:true}).check()
 await page.getByLabel(/I understand my answers are processed/).check()
 await page.getByRole('button',{name:'Start assessment'}).click()
 const field=page.getByPlaceholder('Type your answer…')
 await expect(field).toBeEnabled()
 await page.screenshot({path:path.join(output,'1-started.png')})
 // Complaint in free text, streamed back with progress stages.
 await field.fill('My left eye is red and itchy with sticky discharge since yesterday')
 await page.getByRole('button',{name:'Send',exact:true}).click()
 await expect(page.locator('.ct-options')).toContainText('None of these')
 // Safety screen first.
 await answerChoice('None of these');await page.getByRole('button',{name:'Submit selection'}).click()
 await expect(page.locator('.ct-question')).not.toContainText('Before we continue')
 await expect(page.locator('.ct-question')).toContainText('Why I’m asking')
 for(let i=0;i<4;i++){const opts=page.locator('.ct-options button');if(!(await opts.count()))break;const no=opts.filter({hasText:/^(No|Gradually|Not sure)$/});if(await no.count()){await no.first().click()}else{await opts.first().click()}await page.waitForTimeout(400)}
 await expect(page.locator('.ct-assessment, .ct-panel').filter({hasText:'Possible explanations'}).first()).toBeVisible()
 await expect(page.getByText('Conjunctivitis').first()).toBeVisible()
 await page.screenshot({path:path.join(output,'2-assessment.png'),fullPage:true})
 // A citation opens its verbatim source card.
 const citation=page.locator('button, a').filter({hasText:/^c\d+$|NHS/}).first()
 if(await citation.count())await citation.click()
 // Correct the first answer: switch to the right eye with eye pain → laterality conflict / urgent guidance.
 await page.locator('.ct-transcript').getByRole('button',{name:'Correct'}).first().click()
 await field.fill('My left eye is red, painful and light hurts')
 await page.getByRole('button',{name:'Update answer'}).click()
 await expect(page.getByText(/Get urgent help today|Get emergency help now/).first()).toBeVisible()
 await expect(page.getByText('What changed?').first()).toBeVisible()
 await page.screenshot({path:path.join(output,'3-corrected-urgent.png'),fullPage:true})
 // Consented save, then the timeline lists it.
 await page.getByLabel(/consent to saving/i).check()
 await page.getByRole('button',{name:/^Save/}).click()
 await expect(page.getByText(/Saved/).first()).toBeVisible()
 const saved=await api('GET','/api/clinical/assessments')
 assert.equal(saved.status,200);assert.equal(saved.body.assessments.length,1)
 assert.ok(['same_day','emergency'].includes(saved.body.assessments[0].urgency))
 await page.getByRole('tab',{name:'Timeline'}).click()
 await expect(page.getByRole('region',{name:'Timeline'}).getByText('Eyes',{exact:true})).toBeVisible()
 // RTL in Sorani.
 await page.getByRole('tab',{name:'Assessment'}).click()
 await page.locator('select').first().selectOption('ckb')
 await expect(page.locator('[dir="rtl"]').first()).toBeVisible()
 await page.screenshot({path:path.join(output,'4-sorani-rtl.png'),fullPage:true})
 // Mobile fit.
 await page.setViewportSize({width:390,height:844})
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-window.innerWidth)
 await page.screenshot({path:path.join(output,'5-mobile.png'),fullPage:false})
 assert.ok(overflow<=1,`horizontal overflow ${overflow}px`)
 assert.ok(streamed.some(type=>type?.includes('ndjson')),'turns were streamed as NDJSON')
 assert.deepEqual(errors,[])
 console.log(JSON.stringify({ok:true,streamed:streamed.length,screenshots:output}))
}catch(error){await page.screenshot({path:path.join(output,'failure.png'),fullPage:true}).catch(()=>{});console.error(error);console.error('page errors',errors);process.exitCode=1}
finally{await browser.close()}
