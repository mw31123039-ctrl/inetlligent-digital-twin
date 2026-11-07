// Optional integration check: requires running services, actual trained weights,
// and the attributed public validation image. No model or API response is mocked.
import assert from 'node:assert/strict'
import {createHash,randomBytes} from 'node:crypto'
import fs from 'node:fs/promises'
import path from 'node:path'
import {chromium,expect} from '@playwright/test'

const url=process.env.HUMANTWIN_EYE_URL||'http://127.0.0.1:5173'
const photo=process.env.HUMANTWIN_DENTAL_INFERENCE_PHOTO||'../ai-service/training-data/public/visible-teeth-v1/valid/images/OHI_datasetIMG_1746_JPG.rf.4391a3d85087ac2405cb21d2dec9db92.jpg'
await fs.access(photo)
const output=path.resolve('test-results/dental-public');await fs.mkdir(output,{recursive:true})
const browser=await chromium.launch({channel:process.env.HUMANTWIN_BROWSER_CHANNEL||(process.platform==='win32'?'chrome':undefined),headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']})
const page=await browser.newPage({viewport:{width:1440,height:1080}})
page.setDefaultTimeout(30000)
const errors=[],detections=[]
page.on('pageerror',error=>errors.push(error.message))
page.on('request',request=>{if(request.url().endsWith('/api/dental/detect')&&request.method()==='POST')detections.push(request.postDataJSON())})
try{
 await page.goto(url+'/#dental-cases')
 await page.addStyleTag({content:'.ortho-twin-card{display:none!important}'})
 await page.getByLabel('Add patient dental photos').setInputFiles(path.resolve(photo))
 const sim=page.getByTestId('photo-simulator')
 await expect(sim).toBeVisible()
 await expect(sim.locator('.photo-detection-bar')).toContainText('Local model trained')
 const button=sim.getByRole('button',{name:'Detect teeth with local model',exact:true})
 await expect(button).toBeDisabled()
 assert.equal(detections.length,0)
 await sim.getByRole('button',{name:'Sign in for local tools',exact:true}).click()
 const auth=sim.locator('.photo-auth')
 const identity=randomBytes(8).toString('hex')
 await auth.getByLabel('Email',{exact:true}).fill(`tooth-inference-${identity}@example.invalid`)
 await auth.getByLabel('Password',{exact:true}).fill(randomBytes(18).toString('base64url'))
 await auth.getByLabel('Create a test account',{exact:true}).check()
 await auth.getByRole('button',{name:'Create account',exact:true}).click()
 await expect(sim.locator('.photo-auth')).toHaveCount(0)
 await expect(button).toBeDisabled()
 await sim.getByLabel('I have permission to process this de-identified photograph',{exact:false}).check()
 await expect(button).toBeEnabled()
 const responsePromise=page.waitForResponse(response=>response.url().endsWith('/api/dental/detect')&&response.request().method()==='POST')
 await button.click()
 const response=await responsePromise
 assert.equal(response.status(),200)
 const result=await response.json()
 await expect.poll(()=>sim.locator('.photo-crown-list>button').count()).toBeGreaterThan(0)
 assert.equal(detections.length,1)
 const raw=Buffer.from(detections[0].photo.data_url.split(',')[1],'base64')
 assert.equal(result.input_sha256,createHash('sha256').update(raw).digest('hex'))
 assert.equal(result.clinical_validation,false)
 assert.deepEqual(result.possible_case_ids,[])
 assert.ok(result.crowns.every(c=>c.jaw==='unknown'&&c.points.length>=4&&c.points.length<=12))
 await expect(sim.getByLabel('Manual FDI identity')).toHaveValue('')
 await expect(sim.getByLabel('Photo mock-up blend')).toBeDisabled()
 await expect(sim.getByLabel('I have permission to process this de-identified photograph',{exact:false})).not.toBeChecked()
 await sim.locator('.photo-compare-grid').screenshot({path:path.join(output,'actual-local-detection.png')})
 assert.deepEqual(errors,[])
 const report={source:'DentalMate6v CC BY 4.0 public validation photo',actual_local_model:true,api_status:response.status(),crowns:result.crowns.length,clinical_validation:false,automatic_diagnoses:0,review_required:true}
 await fs.writeFile(path.join(output,'integration-result.json'),JSON.stringify(report,null,2))
 console.log(JSON.stringify(report))
}finally{
 await browser.close()
}
