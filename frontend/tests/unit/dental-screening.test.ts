import { describe, expect, it } from 'vitest'
import { annotationIssues, blankLocation, conditions, locationIssues, newScreeningRecord, parseScreeningRecord, researchReadiness, screeningReport, screeningTaxonomy, type ScreeningRecord } from '../../src/dental/screeningModel'
import { evaluateScreeningCases, type PredictionBundle } from '../../src/dental/screeningEvaluation'
const hash='a'.repeat(64)
function record(subject='PATIENT_1'){
 const value=newScreeningRecord(subject)
 value.scope='in_scope';value.age_years=15;value.dentition_stage='permanent'
 value.photos=[{source_sha256:hash,width:180,height:100,standard_view:'frontal_bite',view_confirmed:true,quality:'usable',quality_reasons:[],biting_together:'yes',patient_orientation_confirmed:true,data_url:null,input_sha256:null}]
 return value
}
function finding(value:ScreeningRecord,id='dental_crowding'){return value.findings.find(item=>item.id===id)!}
function reviewed(value:ScreeningRecord){value.partition='test';value.review={reviewer_code:'ORTHO_1',reviewer_role:'orthodontist',annotations_reviewed:true,definitions_reviewed:true};value.data_rights='consented_clinical_data';value.consent_training=true;return value}
function predictions(records:ScreeningRecord[]):PredictionBundle{return {schema_version:'humantwin-screening-predictions-v1',prediction_origin:'local_model_output',model_id:'TEST_FIXTURE_MODEL',model_version:'test-only',threshold_policy:'Frozen fixture policy',training_subject_codes:['TRAIN_SUBJECT'],validation_subject_codes:['VALIDATION_SUBJECT'],predictions:records.map(item=>({subject_code:item.subject_code,visit_code:item.visit_code,source_sha256s:item.photos.map(photo=>photo.source_sha256),findings:conditions.map(condition=>({id:condition.id,state:'not_assessable',probability:null}))}))}}

describe('orthodontic annotation taxonomy and evidence',()=>{
 it('keeps all 41 distinct snake_case conditions, non-automatic relationships and separate dental classifications',()=>{
  expect(conditions).toHaveLength(41);expect(new Set(conditions.map(item=>item.id)).size).toBe(41)
  expect(conditions.every(item=>/^[a-z][a-z0-9_]*$/.test(item.id))).toBe(true)
  expect(screeningTaxonomy.dental_classifications.map(item=>item.id)).toEqual(['class_i','class_ii_division_1','class_ii_division_2','class_iii'])
  expect(conditions.find(item=>item.id==='traumatic_deep_bite')!.broader_ids).toContain('deep_overbite')
  const value=record();finding(value,'overlapping_teeth').state='present';expect(finding(value).state).toBe('not_assessable')
 })
 it('starts every label unknown, produces no negative screen and never calls an outline model a classifier',()=>{
  const value=newScreeningRecord();expect(value.findings.every(item=>item.state==='not_assessable')).toBe(true)
  expect(value.classifier_applied).toBe(false);expect(screeningReport(value).normal).toBe(false);expect(screeningReport(value).possible).toEqual([])
 })
 it('flags a present subtype with an absent broader concept without changing either annotation',()=>{
  const value=record();Object.assign(finding(value,'traumatic_deep_bite'),{state:'present',evidence_basis:'clinical_record_review',record_reference:'EXAM_1'});Object.assign(finding(value,'deep_overbite'),{state:'absent',evidence_basis:'clinical_record_review',record_reference:'EXAM_1'})
  expect(annotationIssues(value).join(' ')).toContain('absent broader label');expect(finding(value,'deep_overbite').state).toBe('absent');expect(finding(value,'traumatic_deep_bite').state).toBe('present')
 })
 it('requires usable confirmed evidence and closed-bite records for photographic bite findings',()=>{
  const value=record(),bite=finding(value,'deep_overbite');Object.assign(bite,{state:'present',evidence_basis:'photo_observation',photo_ids:[hash]})
  expect(screeningReport(value).possible.map(item=>item.condition.id)).toEqual(['deep_overbite'])
  value.photos[0]!.biting_together='unknown';expect(screeningReport(value).possible).toHaveLength(0)
  value.photos[0]!.biting_together='yes';value.photos[0]!.quality='insufficient';expect(screeningReport(value).possible).toHaveLength(0)
  value.photos[0]!.quality='usable';value.photos[0]!.view_confirmed=false;expect(screeningReport(value).possible).toHaveLength(0)
 })
 it('does not establish impaction, agenesis, skeletal discrepancy or relapse from a photo',()=>{
  for(const id of ['impacted_tooth','hypodontia','oligodontia','skeletal_jaw_discrepancy','orthodontic_relapse']){
   const value=record();Object.assign(finding(value,id),{state:'present',evidence_basis:'photo_observation',photo_ids:[hash]})
   expect(screeningReport(value).possible).toHaveLength(0);expect(screeningReport(value).withheld[0]!.reasons.join(' ')).toMatch(/clinical records/i)
  }
 })
 it('records primary/permanent tooth identifiers manually and rejects inconsistent or unconfirmed locations',()=>{
  const location=blankLocation();location.arch='upper';location.side='patient_left';location.tooth_ids=[61,62];location.tooth_identity_confirmed=true
  expect(locationIssues(location)).toEqual([])
  location.tooth_ids=[11];expect(locationIssues(location).join(' ')).toMatch(/patient-side/)
  location.tooth_ids=[99];expect(locationIssues(location).join(' ')).toMatch(/valid/)
  location.tooth_ids=[61];location.tooth_identity_confirmed=false;expect(locationIssues(location).join(' ')).toMatch(/Confirm/)
 })
 it('keeps normal appearance explicit and incompatible with recorded positive findings',()=>{
  const value=record();value.normal_appearance='present';expect(screeningReport(value).normal).toBe(true)
  finding(value).state='present';expect(screeningReport(value).normal).toBe(false);expect(annotationIssues(value).join(' ')).toMatch(/conflicts/)
 })
 it('requires orthodontist review, rights, permission, and real image bytes for a research bundle',()=>{
  const value=record();expect(researchReadiness(value).length).toBeGreaterThan(0)
  reviewed(value);expect(researchReadiness(value)).toContain('A complete permitted photo bundle is needed for image-classifier research.')
  expect(researchReadiness(value,false)).toEqual([])
  value.review.definitions_reviewed=false;expect(researchReadiness(value,false).join(' ')).toMatch(/definitions/)
 })
 it('rejects changed taxonomies, missing states, clinical claims and remote image URLs on load',()=>{
  const value=record();expect(parseScreeningRecord(value).findings).toHaveLength(41)
  for(const bad of [{...value,taxonomy_version:'other'},{...value,classifier_applied:true},{...value,findings:value.findings.slice(1)},{...value,photos:[{...value.photos[0],data_url:'https://example.invalid/private.jpg'}]}])expect(()=>parseScreeningRecord(bad)).toThrow()
 })
})

describe('actual-output per-condition evaluation',()=>{
 it('computes known confusion counts, coverage and calibration without scoring unknown truth',()=>{
  const cases=[0,1,2,3,4].map(index=>{const value=reviewed(record('TEST_'+index));value.photos[0]!.source_sha256=String(index).repeat(64);Object.assign(finding(value),{state:index<2?'present':'absent',evidence_basis:'photo_observation',photo_ids:[value.photos[0]!.source_sha256]});return value})
  const bundle=predictions(cases),states=['present','absent','present','absent','uncertain'] as const,probabilities=[.8,.2,.7,.1,null]
  bundle.predictions.forEach((item,index)=>Object.assign(item.findings.find(f=>f.id==='dental_crowding')!,{state:states[index],probability:probabilities[index]}))
  const output=evaluateScreeningCases(cases,bundle),row=output.rows.find(item=>item.id==='dental_crowding')!
  expect([row.tp,row.fn,row.fp,row.tn,row.abstained]).toEqual([1,1,1,1,1]);expect(row.sensitivity).toBe(.5);expect(row.specificity).toBe(.5);expect(row.precision).toBe(.5);expect(row.coverage).toBe(.8);expect(row.brier).toBeCloseTo(.295);expect(row.calibration_samples).toBe(4)
  expect(output.rows.find(item=>item.id==='impacted_tooth')!.sensitivity).toBeNull();expect(output.clinical_validation).toBe(false)
 })
 it('blocks leakage, mismatched photographs, unreviewed labels and fabricated score values',()=>{
  const value=reviewed(record('TEST_ONLY'));Object.assign(finding(value),{state:'present',evidence_basis:'photo_observation',photo_ids:[hash]})
  const bundle=predictions([value]);bundle.training_subject_codes.push('test_only');expect(()=>evaluateScreeningCases([value],bundle)).toThrow(/excluded/)
  bundle.training_subject_codes=[];bundle.predictions[0]!.source_sha256s=['b'.repeat(64)];expect(()=>evaluateScreeningCases([value],bundle)).toThrow(/fingerprints/)
  bundle.predictions[0]!.source_sha256s=[hash];bundle.predictions[0]!.findings[0]!.probability=1.5;expect(()=>evaluateScreeningCases([value],bundle)).toThrow(/probabilities/)
  bundle.predictions[0]!.findings[0]!.probability=null;value.review.annotations_reviewed=false;expect(()=>evaluateScreeningCases([value],bundle)).toThrow(/review/)
 })
})
