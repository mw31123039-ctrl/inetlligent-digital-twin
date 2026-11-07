import { describe, expect, it } from 'vitest'
import { arrangeVisibleCrowns, crownTransform, targetWithinPhoto, validOutline, validateDetection, zeroTarget, type PhotoCrown } from '../../src/dental/photoSimulation'
import care from '../../../contracts/dental/care-options.v1.json'
const points=[{x:.2,y:.2},{x:.3,y:.2},{x:.3,y:.5},{x:.2,y:.5}]
const crown=(id:string,x=0):PhotoCrown=>({id,jaw:'upper',points:points.map(p=>({x:p.x+x,y:p.y})),origin:'manual',reviewed:true,fdi:null,target:zeroTarget()})
describe('photo-derived visible crowns',()=>{
 it('accepts ordered boundaries and rejects invalid, empty or crossing outlines',()=>{
  expect(validOutline(points)).toBe(true)
  expect(validOutline([])).toBe(false)
  expect(validOutline([{x:0,y:0},{x:1,y:0},{x:1,y:1},{x:0,y:1}])).toBe(false)
  expect(validOutline([points[0]!,points[2]!,points[1]!,points[3]!])).toBe(false)
  expect(validOutline([{x:NaN,y:0},...points.slice(1)])).toBe(false)
  expect(validOutline([null,...points.slice(1)] as never)).toBe(false)
 })
 it('keeps original pixel placement unchanged until an outline has been reviewed',()=>{
  const c=crown('one');c.target={dx:.1,dy:-.05,rotation:15};c.reviewed=false
  expect(crownTransform(c,1,1000,500)).toBe('translate(0 0) rotate(0 250 175)')
  c.reviewed=true
  expect(crownTransform(c,1,1000,500)).toBe('translate(100 -25) rotate(15 250 175)')
 })
 it('sketches adjoining reviewed crowns without changing their source outlines or inventing crowns',()=>{
  const row=[crown('one'),crown('two',.2)],before=structuredClone(row)
  const targets=arrangeVisibleCrowns(row)
  expect(Object.keys(targets)).toEqual(['one','two'])
  expect(targets.one!.dx).toBeCloseTo(.05)
  expect(targets.two!.dx).toBeCloseTo(-.05)
  expect(row).toEqual(before)
 })
 it('refuses automated row sketches for uncertain arches or unreviewed drafts',()=>{
  const row=[crown('one'),crown('two',.2)];row[1]!.reviewed=false
  expect(()=>arrangeVisibleCrowns(row)).toThrow(/Review each/)
  row[1]!.reviewed=true;row[1]!.jaw='unknown'
  expect(()=>arrangeVisibleCrowns(row)).toThrow(/assign its arch/)
 })
 it('checks the actual rotated crown against the image boundary',()=>{
  const c=crown('one');expect(targetWithinPhoto(c,1000,500)).toBe(true)
  c.target.dx=-.25;expect(targetWithinPhoto(c,1000,500)).toBe(false)
  c.target.dx=0;c.target.rotation=15;expect(targetWithinPhoto(c,1000,500)).toBe(true)
 })
 it('binds a draft to its exact input fingerprint and refuses unsupported evidence',()=>{
  const hash='a'.repeat(64),result={mode:'photo-outline-draft',clinical_validation:false,input_sha256:hash,image_quality:'usable',crowns:[{jaw:'upper',points}],possible_case_ids:['crowding']}
  expect(validateDetection(result,hash).crowns).toHaveLength(1)
  expect(()=>validateDetection(result,'b'.repeat(64))).toThrow(/photograph/)
  expect(()=>validateDetection({...result,image_quality:'insufficient'},hash)).toThrow(/unusable/)
  expect(()=>validateDetection({...result,crowns:[{jaw:'upper',points:[]}]},hash)).toThrow(/invalid/)
 })
 it('links every discussion option to sources and distinguishes benefits from tradeoffs',()=>{
  expect(care.options).toHaveLength(8)
  for(const option of care.options){expect(option.benefits).toHaveLength(3);expect(option.tradeoffs).toHaveLength(3);expect(option.clinician_checks.length).toBeGreaterThanOrEqual(2);for(const source of option.source_ids)expect(care.sources.some(item=>item.id===source)).toBe(true)}
  expect(care.clinical_validation).toBe(false)
 })
})
