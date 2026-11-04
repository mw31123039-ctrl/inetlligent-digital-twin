import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { createHash } from 'node:crypto'
import ts from 'typescript'
import { bundleModule } from './portable.mjs'
const code=ts.transpileModule(await fs.readFile('src/dental/model.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText
const m=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))
let passed=0
function test(name,fn){fn();passed++;console.log('PASS '+name)}
test('32 unique permanent FDI teeth; anatomical sides match chart',()=>{assert.equal(m.teeth.length,32);assert.equal(new Set(m.teeth.map(t=>t.fdi)).size,32);assert.equal(m.toothById(11).side,'right');assert.equal(m.toothById(21).side,'left');assert.equal(m.toothById(41).jaw,'lower');assert.equal(m.toothById(31).side,'left');assert.deepEqual(m.chartRows.flat().toSorted(),m.teeth.map(t=>t.fdi).toSorted());assert.equal(m.toothById(51),undefined)})
for(const sign of m.safetySigns.filter(s=>s.emergency))test('Emergency priority before screen completion: '+sign.id,()=>{const r=m.newPainRecord();r.signs=[sign.id];assert.equal(m.dentalAdvice(r).level,'emergency')})
test('Reported emergencies survive corrections and changing teeth',()=>assert.equal(m.dentalAdvice(m.newPainRecord(36),true).level,'emergency'))
test('A knocked-out permanent tooth receives immediate urgent dental guidance',()=>{const r=m.newPainRecord();r.signs=['knocked-out'];assert.match(m.dentalAdvice(r).title,/immediately/)})
test('Unchecked safety screen is not interpreted as negative',()=>assert.equal(m.dentalAdvice(m.newPainRecord()).level,'incomplete'))
test('Fever/swelling flag and severe pain need urgent dental assessment',()=>{for(const change of [{infectionSigns:true},{severity:8}])assert.equal(m.dentalAdvice({...m.newPainRecord(),reviewed:true,...change}).level,'urgent')})
test('Appliance problem routes to the orthodontic team after screening',()=>assert.match(m.dentalAdvice({...m.newPainRecord(),reviewed:true,applianceIssue:'wire'}).title,/orthodontic/))
test('Persistent symptoms do not produce a diagnosis',()=>{const result=m.dentalAdvice({...m.newPainRecord(),reviewed:true,duration:'days'});assert.equal(result.level,'appointment');assert.match(result.detail,/two days/);assert.equal('diagnosis' in result,false)})
test('CSV template imports with tooth-specific chronological series',()=>{const d=m.parseMeasurements(m.measurementTemplate,'csv');const s=m.measurementSeries(d,'DEMO_01','pain',11);assert.deepEqual(s.map(r=>r.value),[4,2]);assert.equal(s[0].tooth,11)})
const header='subject_id,recorded_at,tooth_fdi,metric,value,unit\n'
test('Quoted fields, BOM and CRLF are supported',()=>{const d=m.parseMeasurements('\uFEFF'+header.replaceAll('\n','\r\n')+'"STUDY_1",2026-10-01,21,overjet,3.2,mm\r\n','csv');assert.equal(d.rows[0].value,3.2)})
test('Subject, tooth and metric streams never mix',()=>{const d=m.parseMeasurements(header+'A,2026-10-01,11,pain,4,score\nA,2026-10-01,21,pain,8,score\nB,2026-10-01,11,pain,9,score','csv');assert.deepEqual(m.measurementSeries(d,'A','pain',11).map(r=>r.value),[4])})
test('Same subject/time/tooth/metric duplicates are rejected',()=>assert.throws(()=>m.parseMeasurements(header+'A,2026-10-01,11,pain,4,score\nA,2026-10-01,11,pain,5,score','csv'),/duplicate/))
test('Mixed measurement units cannot silently share a chart',()=>assert.throws(()=>m.parseMeasurements(header+'A,2026-10-01,11,bite,4,mm\nA,2026-10-02,11,bite,5,degrees','csv'),/mixes units/))
for(const [value,pattern]of [['A,2026-02-31,11,pain,4,score',/invalid date/],['A,2026-10-01,51,pain,4,score',/32 permanent/],['=CMD,2026-10-01,11,pain,4,score',/coded subject/],['A,2026-10-01,11,pain,,score',/must be a number/],['A,2026-10-01,11,pain,Infinity,score',/must be a number/]])test('Reject malformed record: '+value,()=>assert.throws(()=>m.parseMeasurements(header+value,'csv'),pattern))
test('Malformed CSV and unsupported JSON shapes are rejected',()=>{assert.throws(()=>m.parseMeasurements(header+'"A,2026-10-01,11,pain,4,score','csv'),/unclosed/);for(const s of ['{}','[]','[1]','[null]'])assert.throws(()=>m.parseMeasurements(s,'json'));assert.throws(()=>m.parseMeasurements('x'.repeat(2000001),'csv'),/2 MB/)})
const growth=m.parseMeasurements(await fs.readFile('public/data/dental/orthodont-growth.csv','utf8'),'csv')
test('Historical sample is 108 observed rows / 27 distinct coded subjects',()=>{assert.equal(growth.rows.length,108);assert.equal(growth.subjects.length,27);assert.equal(growth.format,'orthodont-growth');assert.deepEqual(m.measurementSeries(growth,'M01','craniofacial_distance',null).map(r=>r.value),[26,25,29,31]);assert.ok(growth.rows.every(r=>r.tooth===null))})
test('Geometric image measurements require valid calibration; angles handle coincident points',()=>{assert.equal(m.distanceMm([0,0],[3,4],.2),1);assert.equal(m.distanceMm([0,0],[3,4],0),null);assert.equal(m.angleDegrees([1,0],[0,0],[0,1]),90);assert.equal(m.angleDegrees([0,0],[0,0],[1,1]),null)})
const manifest=JSON.parse(await fs.readFile('public/data/dental/manifest.json','utf8'))
for(const file of manifest.files){const bytes=await fs.readFile('public/data/dental/'+file.name);test('Published sample integrity and provenance: '+file.name,()=>{assert.equal(createHash('sha256').update(bytes).digest('hex'),file.sha256);assert.equal(bytes.length,file.bytes);assert.equal(file.modified,false);assert.ok(file.source.startsWith('https://'))})}
const annotation=JSON.parse(await fs.readFile('public/data/dental/reference-landmarks.json','utf8'))
test('Expert annotation has 29 labeled landmarks from the published image',()=>{assert.equal(annotation.landmarks.length,29);assert.equal(new Set(annotation.landmarks.map(p=>p.symbol)).size,29)})
const temporary=await fs.mkdtemp(path.join(os.tmpdir(),'humantwin-dental-tests-')),output=path.join(temporary,'anatomy.mjs')
await bundleModule(path.resolve('src/dental/anatomy.ts'),output)
const {buildDentalAtlas}=await import((await import('node:url')).pathToFileURL(output).href)
for(const [view,count]of [['front',32],['upper',16],['lower',16],['side',32],['section',1]]){
 const atlas=buildDentalAtlas({view,selected:16,appliance:'metal',elastic:'#399d91',opening:.14})
 test('Selectable finite geometry for view '+view,()=>{assert.equal(atlas.children.filter(o=>o.userData.toothFdi).length,count);let vertices=0;atlas.traverse(o=>{if(!o.isMesh)return;const pos=o.geometry.getAttribute('position');vertices+=pos.count;assert.ok(Array.from(pos.array).every(Number.isFinite))});assert.ok(vertices>1000)})
 atlas.traverse(o=>{o.geometry?.dispose();for(const mat of Array.isArray(o.material)?o.material:o.material?[o.material]:[])mat.dispose()})
}
for(const [appliance,count]of [['none',0],['metal',24],['ceramic',24]]){
 const atlas=buildDentalAtlas({view:'front',selected:11,appliance,elastic:'#399d91',opening:0})
 test('Hardware is attached to the atlas; '+appliance,()=>{let brackets=0;atlas.traverse(o=>{if(o.name==='bracket')brackets++});assert.equal(brackets,count)})
 atlas.traverse(o=>{o.geometry?.dispose();for(const mat of Array.isArray(o.material)?o.material:o.material?[o.material]:[])mat.dispose()})
}
await fs.unlink(output);await fs.rmdir(temporary)
console.log(`PASS ${passed} dental checks`)
