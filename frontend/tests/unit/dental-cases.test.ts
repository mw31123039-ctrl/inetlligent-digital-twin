import { describe, expect, it } from 'vitest'
import { caseToothOffset, findStudyCases, jawOffset, orthodonticCases, photoSignature, researchPartition, validCaseId, type DentalSimulation } from '../../src/dental/caseModel'
import { toothById } from '../../src/dental/model'
const simulation = (caseId:string, alignment=0):DentalSimulation => ({caseId,intensity:1,alignment,edits:{}})

describe('dental case learning and research boundaries',()=>{
 it('retrieves a relevant source topic for informal bite names without inventing an image finding',()=>{
  expect(findStudyCases('How do crowded teeth compare?')[0]?.id).toBe('crowding')
  expect(findStudyCases('Explain deep bite')[0]?.id).toBe('deep-bite')
  expect(findStudyCases('zzzznotatopic')).toEqual([])
  expect(findStudyCases('')).toEqual([])
 })
 it('moves crowding, spacing and vertical examples in different visible directions',()=>{
  const tooth=toothById(11)!
  expect(caseToothOffset(tooth,simulation('crowding')).rotation).not.toBe(0)
  expect(caseToothOffset(tooth,simulation('spacing')).x).toBeLessThan(0)
  expect(caseToothOffset(toothById(31)!,simulation('anterior-open-bite')).y).toBeLessThan(0)
  expect(jawOffset('lower',simulation('deep-bite')).y).toBeGreaterThan(0)
  expect(jawOffset('lower',simulation('underbite')).z).toBeGreaterThan(0)
  expect(jawOffset('lower',simulation('increased-overjet')).z).toBeLessThan(0)
 })
 it('resets illustrative alignment without silently clearing a reviewer tooth edit',()=>{
  const aligned=simulation('crowding',1); aligned.edits[11]={x:.1,y:0,z:0,rotation:12}
  expect(caseToothOffset(toothById(11)!,aligned)).toMatchObject({x:.1,z:0,rotation:12})
  expect(jawOffset('lower',simulation('underbite',1)).z).toBe(0)
 })
 it('keeps unilateral crossbite on the documented patient side and a missing tooth absent from alignment previews',()=>{
  const state=simulation('unilateral-posterior-crossbite')
  expect(caseToothOffset(toothById(16)!,state).x).toBeGreaterThan(0)
  expect(caseToothOffset(toothById(26)!,state).x).toBe(0)
  expect(caseToothOffset(toothById(22)!,simulation('missing-tooth',1)).hidden).toBe(true)
 })
 it('requires real image signatures instead of trusting a file extension',()=>{
  expect(photoSignature(new Uint8Array([255,216,255,224]))).toBe('image/jpeg')
  expect(photoSignature(new Uint8Array([137,80,78,71,13,10,26,10]))).toBe('image/png')
  expect(()=>photoSignature(new TextEncoder().encode('<script>alert(1)</script>'))).toThrow(/genuine/)
 })
 it('keeps repeated records from a coded patient in the same proposed research partition',()=>{
  expect(researchPartition('PATIENT_01')).toBe(researchPartition('patient_01'))
  expect(researchPartition(' patient_01 ')).toBe(researchPartition('PATIENT_01'))
  expect(validCaseId('PATIENT_01')).toBe(true)
  expect(validCaseId('Name with spaces')).toBe(false)
  expect(validCaseId('../external')).toBe(false)
 })
 it('provides an answer and clinical limitation for every case shown to a student',()=>{
  expect(orthodonticCases.length).toBeGreaterThanOrEqual(26)
  for(const item of orthodonticCases){expect(item.quiz.options).toHaveLength(4);expect(item.quiz.options[item.quiz.answer_index]).toBeTruthy();expect(item.limits.length).toBeGreaterThan(30);expect(item.source_ids.length).toBeGreaterThan(0)}
 })
})
