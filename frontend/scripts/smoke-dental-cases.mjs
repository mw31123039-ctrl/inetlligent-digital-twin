import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { chromium, expect } from '@playwright/test'

const url=process.env.HUMANTWIN_EYE_URL||'http://127.0.0.1:5173'
const library=JSON.parse(await fs.readFile(new URL('../../contracts/dental/orthodontics.v1.json',import.meta.url),'utf8'))
const output=path.resolve('test-results/dental-cases');await fs.mkdir(output,{recursive:true})
const browser=await chromium.launch({channel:process.env.HUMANTWIN_BROWSER_CHANNEL||(process.platform==='win32'?'chrome':undefined),headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']})
const errors=[],posts=[];let page
async function fixturePhoto(current){return Buffer.from(await current.evaluate(()=>{
 const canvas=document.createElement('canvas');canvas.width=640;canvas.height=360;const c=canvas.getContext('2d');c.fillStyle='#eee7db';c.fillRect(0,0,640,360);c.fillStyle='#cb8a90';c.beginPath();c.ellipse(320,165,230,92,0,0,Math.PI*2);c.fill();c.fillStyle='#fff9e5';for(let i=0;i<12;i++)c.fillRect(106+i*35,130+Math.abs(i-5.5)*4,29,75);c.fillStyle='#394f42';c.font='16px sans-serif';c.fillText('SYNTHETIC SOFTWARE TEST IMAGE',165,310);return canvas.toDataURL('image/png').split(',')[1]
}),'base64')}
try{
 page=await browser.newPage({viewport:{width:1440,height:1080}});page.setDefaultTimeout(20000);page.on('pageerror',error=>errors.push(error.message));page.on('request',request=>{if(request.method()==='POST')posts.push(request.url())})
 await page.goto(url+'/#dental-cases');await page.getByRole('heading',{name:'Every smile has something to teach.'}).waitFor()
 await expect(page.locator('.ortho-model-stage .dental-canvas')).toHaveAttribute('aria-busy','false')
 await page.locator('.ortho-studio').screenshot({path:path.join(output,'desktop-empty.png')})
 await page.getByRole('button',{name:/Condition library/}).click();assert.equal(await page.locator('.ortho-library-grid>article').count(),26)
 await page.getByLabel('Search orthodontic conditions').fill('open bite');assert.ok(await page.locator('.ortho-library-grid>article').count()>=2)
 await page.getByLabel('Search orthodontic conditions').fill('notatopicxyz');await expect(page.getByText('No matching topics.',{exact:false})).toBeVisible()
 await page.getByLabel('Search orthodontic conditions').fill('');await page.locator('[data-case="underbite"]').getByRole('button',{name:/Explore case/}).click()
 await expect(page.getByLabel('Orthodontic teaching example')).toHaveValue('underbite')
 await page.getByRole('button',{name:'Side',exact:true}).click();await expect(page.locator('.ortho-model-stage .dental-canvas')).toHaveAttribute('aria-busy','false')
 const blend=page.getByLabel('Illustrative alignment preview');await blend.fill('0.8');await expect(page.locator('.ortho-model-controls output')).toHaveText('80%');await page.getByRole('button',{name:'Reset model',exact:true}).click();await expect(blend).toHaveValue('0')
 await page.getByRole('button',{name:'Front',exact:true}).click()
 const photo=await fixturePhoto(page)
 await page.getByLabel('Add patient dental photos').setInputFiles({name:'synthetic.png',mimeType:'image/png',buffer:photo})
 await expect(page.locator('.ortho-photo-strip>button')).toHaveCount(1)
 assert.equal(posts.length,0,'Local photo upload must not post to a server')
 await page.getByLabel('Add patient dental photos').setInputFiles({name:'fake.png',mimeType:'image/png',buffer:Buffer.from('<script>bad file</script>')})
 await expect(page.getByRole('alert').filter({hasText:'genuine JPEG'})).toBeVisible();await expect(page.locator('.ortho-photo-strip>button')).toHaveCount(1)
 await page.getByLabel('Add patient dental photos').setInputFiles({name:'duplicate.png',mimeType:'image/png',buffer:photo})
 await expect(page.getByRole('alert').filter({hasText:'already attached'})).toBeVisible()
 await page.getByRole('button',{name:'Mark a tooth',exact:true}).click();await page.getByRole('button',{name:/Edit FDI 21 ·/}).click()
 await page.getByLabel('Photo marker X percent').fill('39');await page.getByLabel('Photo marker Y percent').fill('46');await page.getByLabel('Photo marker note').fill('<img src=x onerror=alert(1)> visible overlap')
 await page.getByRole('button',{name:'Add marker',exact:true}).click();await expect(page.locator('.ortho-photo-stage svg circle')).toHaveCount(1)
 assert.equal(await page.locator('.ortho-marker-tools img').count(),0,'Marker text must be escaped')
 await page.getByText('Explore individual tooth position',{exact:false}).click();await page.getByLabel('Selected tooth rotation').fill('18')
 await page.getByLabel('Coded dental case ID').fill('SYNTHETIC_CASE_01');await page.getByLabel('Dental case notes').fill('Synthetic review: inspect the visible overlap and obtain complete bite records.')
 await page.getByText('Record discussion topics',{exact:false}).click();await page.locator('.ortho-findings').getByLabel('Crowded teeth',{exact:true}).check()
 await page.getByLabel('Dental reviewer code').fill('REVIEWER_TEST');await page.getByLabel('I have reviewed the photo labels',{exact:false}).check()
 const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'Export reviewed research label',exact:true}).click()]);const exported=path.join(output,'reviewed-label.jsonl');await download.saveAs(exported);const record=JSON.parse(await fs.readFile(exported,'utf8'))
 assert.equal(record.subject_id,'SYNTHETIC_CASE_01');assert.equal(record.photos.length,1);assert.equal(record.photos[0].markers[0].tooth,21);assert.equal(record.photos[0].sha256.length,64);assert.equal(record.image_bytes_included,false);assert.equal(record.model_training_performed,false);assert.equal(record.review.status,'self-attested-review');assert.deepEqual(record.reported_findings,['crowding']);assert.equal('url' in record.photos[0],false)
 assert.equal(posts.length,0,'Exporting a local label must not upload it')
 await page.getByRole('button',{name:'Practise with this reviewed photo',exact:true}).click();await expect(page.locator('.ortho-patient-exercise')).toBeVisible();await expect(page.getByRole('button',{name:'Compare with reviewer',exact:true})).toBeDisabled();await page.locator('.ortho-photo-answers').getByLabel('Crowded teeth',{exact:true}).check();await page.getByRole('button',{name:'Compare with reviewer',exact:true}).click();await expect(page.locator('.ortho-patient-exercise .ortho-explanation')).toContainText('Your choices match the reviewer labels.');await page.getByRole('button',{name:'Back to this case',exact:true}).click()
 await page.getByLabel('Dental case notes').fill('Changed after review');await expect(page.getByLabel('I have reviewed the photo labels',{exact:false})).not.toBeChecked()
 await page.getByLabel('What would you like to understand?').fill('Explain deep bite');await page.getByRole('button',{name:'Find references',exact:true}).click();await expect(page.locator('.ortho-coach-references')).toContainText('Deep bite')
 await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(output,'desktop-case.png'),fullPage:true})
 await page.getByRole('button',{name:/Student practice/}).click();await page.getByRole('button',{name:'Start 10-question test',exact:true}).click()
 for(let i=0;i<10;i++){
  const question=await page.locator('.ortho-exam-question>h3').innerText(),item=library.cases.find(c=>c.quiz.question===question);assert.ok(item)
  const choice=i===0?(item.quiz.answer_index+1)%4:item.quiz.answer_index
  await page.locator('.ortho-exam-question input[type=radio]').nth(choice).check();await page.getByRole('button',{name:'Check answer',exact:true}).click();await expect(page.locator('.ortho-explanation')).toContainText(item.quiz.explanation)
  if(i===0)await page.locator('.ortho-practice').screenshot({path:path.join(output,'student-explanation.png')})
  await page.getByRole('button',{name:i===9?/See results/:/Next question/}).click()
 }
 await expect(page.locator('.ortho-exam-results>h3')).toHaveText('9 / 10');await expect(page.locator('.ortho-exam-results article')).toHaveCount(10)
 await page.getByRole('button',{name:/Case workspace/}).click();await expect(page.locator('.ortho-photo-strip>button')).toHaveCount(1)
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>window.scrollTo(0,0));await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true)
 await page.locator('.ortho-model-stage').scrollIntoViewIfNeeded();await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));await page.locator('.ortho-model-stage').screenshot({path:path.join(output,'mobile-model.png')});await page.evaluate(()=>window.scrollTo(0,0))
 await page.screenshot({path:path.join(output,'mobile-case.png'),fullPage:true});await page.getByRole('button',{name:/Condition library/}).click();await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true)
 await page.screenshot({path:path.join(output,'mobile-library.png'),fullPage:true})
 await page.reload();await page.getByTestId('ortho-studio').waitFor();await expect(page.locator('.ortho-photo-strip>button')).toHaveCount(0);assert.equal(await page.getByLabel('Dental case notes').inputValue(),'')
 assert.deepEqual(await page.evaluate(()=>Object.keys(localStorage).filter(key=>/dental.case|dental.photo|ortho.case/i.test(key))),[])
 await page.goto(url+'/#orthodontics');await page.getByRole('button',{name:/Open cases & practice/}).click();await expect(page.getByTestId('ortho-studio')).toBeVisible()
 console.log('PASS: 26-topic library; bite presets; reference alignment; local photos; signature/duplicate checks; tooth annotations; escaped notes; reviewed label export; review invalidation; reference search; 10-question grading; tab state; mobile fit; reload privacy; braces entry.')

 // Reference assistance stays local even if the unrelated general provider is configured.
 const local=await browser.newPage({viewport:{width:1280,height:1000}});local.on('pageerror',error=>errors.push(error.message));const outgoing=[]
 local.on('request',request=>{if(request.method()==='POST')outgoing.push(request.url())})
 await local.route('**/api/status',route=>route.fulfill({json:{available:true,provider_configured:true}}))
 await local.goto(url+'/#dental-cases');await expect(local.getByText('Local reference library',{exact:true})).toBeVisible()
 await local.getByLabel('What would you like to understand?').fill('deep bite');await local.getByRole('button',{name:'Find references',exact:true}).click();await expect(local.locator('.ortho-coach-references')).toContainText('Deep bite')
 await expect(local.getByRole('button',{name:'Request AI draft',exact:true})).toHaveCount(0);assert.deepEqual(outgoing,[])
 assert.deepEqual(errors,[]);console.log('PASS: local reference coach; configured general AI does not expose external dental controls or send context.')
}catch(error){if(page){console.error((await page.locator('body').innerText()).slice(-3500));await page.screenshot({path:path.join(output,'failure.png'),fullPage:true})}throw error}finally{await browser.close()}
