import taxonomyData from '../../../contracts/dental/screening-taxonomy.v1.json'
import type { CasePhoto } from './caseModel'

export const assessmentStates = ['present','absent','uncertain','not_assessable'] as const
export type AssessmentState = typeof assessmentStates[number]
export const stateNames:Record<AssessmentState,string>={present:'Present',absent:'Absent',uncertain:'Uncertain',not_assessable:'Not assessable'}
export const standardViews = ['frontal_bite','right_bite','left_bite','upper_occlusal','lower_occlusal','other','unknown'] as const
export const viewNames:Record<string,string>={frontal_bite:'Frontal bite',right_bite:'Right bite',left_bite:'Left bite',upper_occlusal:'Upper occlusal',lower_occlusal:'Lower occlusal',other:'Other / out of scope',unknown:'Unconfirmed view'}
export interface ScreeningCondition {id:string;user_id:number;name:string;user_definition:string;simple_explanation:string;category:string;broader_ids:string[];related_ids:string[];evidence_scope:string;useful_standard_views:string[];limitations:string[];source_ids:string[]}
export const screeningTaxonomy=taxonomyData as unknown as {version:string;conditions:ScreeningCondition[];categories:{id:string;name:string;description:string}[];sources:{id:string;title:string;url:string;publisher:string}[];dental_classifications:{id:string;name:string;definition:string;simple_explanation:string}[]}
export const conditions=screeningTaxonomy.conditions
export const conditionIds=new Set(conditions.map(item=>item.id))
export const allFdi=Array.from({length:8},(_,q)=>Array.from({length:q<4?8:5},(_,t)=>(q+1)*10+t+1)).flat()
export type Location={arch:'upper'|'lower'|'both'|'unknown';region:'anterior'|'posterior'|'whole_arch'|'tooth_specific'|'unknown';side:'patient_left'|'patient_right'|'bilateral'|'midline'|'unknown';tooth_ids:number[];tooth_identity_confirmed:boolean}
export type Finding={id:string;state:AssessmentState;evidence_basis:'not_recorded'|'photo_observation'|'clinical_record_review'|'history_report';photo_ids:string[];record_reference:string;note:string;locations:Location[]}
export type ScreeningPhoto={source_sha256:string;width:number;height:number;standard_view:typeof standardViews[number];view_confirmed:boolean;quality:'not_reviewed'|'usable'|'limited'|'insufficient'|'out_of_scope';quality_reasons:string[];biting_together:'yes'|'no'|'unknown';patient_orientation_confirmed:boolean;data_url:string|null;input_sha256:string|null}
export const relationshipKeys=['molar_right','molar_left','canine_right','canine_left','incisor'] as const
export type ScreeningRecord={schema_version:'humantwin-orthodontic-screening-v1';taxonomy_version:string;subject_code:string;visit_code:string;partition:'train'|'validation'|'test';age_years:number|null;dentition_stage:'primary'|'mixed'|'permanent'|'unknown';scope:'not_reviewed'|'in_scope'|'insufficient_images'|'out_of_scope';normal_appearance:AssessmentState;existing_braces:AssessmentState;photos:ScreeningPhoto[];findings:Finding[];classifications:{overall:string;molar_right:string;molar_left:string;canine_right:string;canine_left:string;incisor:string;entered_by_clinician:boolean;note:string};review:{reviewer_code:string;reviewer_role:'orthodontist'|'dentist'|'student'|'patient'|'unknown';annotations_reviewed:boolean;definitions_reviewed:boolean};data_rights:'not_confirmed'|'consented_clinical_data'|'appropriately_licensed';rights_reference:string;consent_storage:boolean;consent_training:boolean;is_demonstration:boolean;clinical_validation:false;classifier_applied:false;model_training_performed:false}
export const blankLocation=():Location=>({arch:'unknown',region:'unknown',side:'unknown',tooth_ids:[],tooth_identity_confirmed:false})
export const blankFinding=(id:string):Finding=>({id,state:'not_assessable',evidence_basis:'not_recorded',photo_ids:[],record_reference:'',note:'',locations:[]})
export function newScreeningRecord(subject=''):ScreeningRecord{return {schema_version:'humantwin-orthodontic-screening-v1',taxonomy_version:screeningTaxonomy.version,subject_code:subject,visit_code:'VISIT_001',partition:'train',age_years:null,dentition_stage:'unknown',scope:'not_reviewed',normal_appearance:'not_assessable',existing_braces:'not_assessable',photos:[],findings:conditions.map(item=>blankFinding(item.id)),classifications:{overall:'not_recorded',molar_right:'not_recorded',molar_left:'not_recorded',canine_right:'not_recorded',canine_left:'not_recorded',incisor:'not_recorded',entered_by_clinician:false,note:''},review:{reviewer_code:'',reviewer_role:'unknown',annotations_reviewed:false,definitions_reviewed:false},data_rights:'not_confirmed',rights_reference:'',consent_storage:false,consent_training:false,is_demonstration:false,clinical_validation:false,classifier_applied:false,model_training_performed:false}}
export function newScreeningPhoto(photo:CasePhoto):ScreeningPhoto{const names:Record<string,ScreeningPhoto['standard_view']>={'Frontal bite':'frontal_bite','Right bite':'right_bite','Left bite':'left_bite','Upper arch':'upper_occlusal','Lower arch':'lower_occlusal','Smile / profile':'other'};return {source_sha256:photo.sha256,width:photo.width,height:photo.height,standard_view:names[photo.view]||'unknown',view_confirmed:false,quality:'not_reviewed',quality_reasons:[],biting_together:'unknown',patient_orientation_confirmed:false,data_url:null,input_sha256:null}}
export function photoEvidenceIssues(record:ScreeningRecord,condition:ScreeningCondition,finding:Finding):string[]{
 if(finding.evidence_basis!=='photo_observation')return []
 const issues:string[]=[]
 if(record.scope!=='in_scope')issues.push('The image set is not marked in scope.')
 const linked=record.photos.filter(photo=>finding.photo_ids.includes(photo.source_sha256))
 if(!linked.length)issues.push('No supporting photo was selected.')
 if(linked.some(photo=>!photo.view_confirmed||photo.quality!=='usable'))issues.push('Supporting views must be confirmed and usable.')
 if(!linked.some(photo=>condition.useful_standard_views.includes(photo.standard_view)))issues.push('The supplied view does not support this observation.')
 if(condition.evidence_scope==='clinical_records_required')issues.push('Photographs cannot establish this condition; review clinical records.')
 if(condition.category==='bite_abnormalities'&&linked.some(photo=>photo.biting_together!=='yes'))issues.push('Bite observations need a confirmed biting-together record; contact still needs clinical review.')
 if(finding.locations.some(location=>['patient_left','patient_right'].includes(location.side))&&linked.some(photo=>!photo.patient_orientation_confirmed))issues.push('Confirm patient-side orientation before reporting a left/right photographic location.')
 return issues
}
export function locationIssues(location:Location):string[]{
 const issues:string[]=[]
 if(location.tooth_ids.some(id=>!allFdi.includes(id))||new Set(location.tooth_ids).size!==location.tooth_ids.length)issues.push('Use distinct valid permanent or primary FDI identifiers.')
 if(location.tooth_ids.length&&!location.tooth_identity_confirmed)issues.push('Confirm every manually entered tooth identity.')
 const upper=(id:number)=>[1,2,5,6].includes(Math.floor(id/10)),left=(id:number)=>[2,3,6,7].includes(Math.floor(id/10))
 if(location.tooth_ids.some(id=>location.arch==='upper'&&!upper(id)||location.arch==='lower'&&upper(id)))issues.push('The tooth identifiers do not match the selected arch.')
 if(location.tooth_ids.some(id=>location.side==='patient_left'&&!left(id)||location.side==='patient_right'&&left(id)))issues.push('The tooth identifiers do not match the patient-side selection.')
 if(location.tooth_ids.some(id=>location.region==='anterior'&&id%10>3||location.region==='posterior'&&id%10<=3))issues.push('The tooth identifiers do not match the selected region.')
 return issues
}
export function describeLocation(location:Location):string{
 if(locationIssues(location).length)return 'Location needs review; tooth identifiers are not established'
 return [location.arch,location.region,location.side.replaceAll('_',' '),location.tooth_ids.length&&location.tooth_identity_confirmed?'FDI '+location.tooth_ids.join(', '):'tooth identity not established'].join(' · ')
}
export function annotationIssues(record:ScreeningRecord):string[]{
 const issues:string[]=[]
 for(const finding of record.findings){
  const condition=conditions.find(item=>item.id===finding.id);if(!condition)continue
  if(finding.state==='present')for(const parent of condition.broader_ids)if(record.findings.find(item=>item.id===parent)?.state==='absent')issues.push(`${condition.name}: review the absent broader label ${conditions.find(item=>item.id===parent)?.name}. Labels are never changed automatically.`)
  if(finding.state==='present'||finding.state==='absent'){
   if(finding.evidence_basis==='not_recorded')issues.push(`${condition.name}: record the evidence basis.`)
   if(['clinical_record_review','history_report'].includes(finding.evidence_basis)&&!finding.record_reference.trim())issues.push(`${condition.name}: add a coded record/history reference.`)
   for(const issue of photoEvidenceIssues(record,condition,finding))issues.push(`${condition.name}: ${issue}`)
   if(condition.evidence_scope!=='visible_photographic_finding'&&finding.evidence_basis!=='clinical_record_review')issues.push(`${condition.name}: clinical records are required for an established research label.`)
   if(condition.category==='tooth_eruption_and_development'&&(record.age_years===null||record.dentition_stage==='unknown'))issues.push(`${condition.name}: record age and dentition stage.`)
  }
  for(const location of finding.locations)for(const issue of locationIssues(location))issues.push(`${condition.name}: ${issue}`)
 }
 if(record.normal_appearance==='present'&&record.findings.some(f=>f.state==='present'))issues.push('Normal appearance conflicts with a present finding. Review both entries.')
 if(Object.entries(record.classifications).some(([key,value])=>!['entered_by_clinician','note'].includes(key)&&!['not_recorded','uncertain','not_assessable'].includes(String(value)))&&!record.classifications.entered_by_clinician)issues.push('Dental classifications must be entered by a clinician.')
 return [...new Set(issues)]
}
export function researchReadiness(record:ScreeningRecord,requirePixels=true):string[]{
 const issues=annotationIssues(record)
 if(record.is_demonstration)issues.push('Demonstrations cannot become clinical training annotations.')
 if(record.review.reviewer_role!=='orthodontist'||!record.review.reviewer_code||!record.review.annotations_reviewed)issues.push('An orthodontist must review these annotations; review is self-attested here.')
 if(!record.review.definitions_reviewed)issues.push('The taxonomy definitions need recorded orthodontist review.')
 if(record.data_rights==='not_confirmed'||record.data_rights==='appropriately_licensed'&&!record.rights_reference.trim())issues.push('Record patient consent or an appropriate data licence.')
 if(!record.consent_training)issues.push('Permission to use this case for local model research is missing.')
 if(!record.photos.length||requirePixels&&record.photos.some(p=>!p.data_url||!p.input_sha256))issues.push('A complete permitted photo bundle is needed for image-classifier research.')
 if(record.scope==='not_reviewed'||record.photos.some(p=>p.quality==='not_reviewed'))issues.push('Complete the image-quality and scope review.')
 return [...new Set(issues)]
}
export function screeningReport(record:ScreeningRecord){
 const possible: {condition:ScreeningCondition;finding:Finding;basis:string}[]=[],uncertain:typeof possible=[],withheld:{condition:ScreeningCondition;reasons:string[]}[]=[]
 for(const finding of record.findings){const condition=conditions.find(item=>item.id===finding.id)!;if(!condition)continue
  if(finding.state==='present'||finding.state==='uncertain'){
   const reasons=photoEvidenceIssues(record,condition,finding)
   if(finding.evidence_basis==='not_recorded')reasons.push('Evidence has not been recorded.')
   if(condition.evidence_scope==='clinical_records_required'&&finding.evidence_basis!=='clinical_record_review')reasons.push('Clinical records are needed; this is not established by the supplied information.')
   if(['clinical_record_review','history_report'].includes(finding.evidence_basis)&&!finding.record_reference.trim())reasons.push('The record/history reference is missing.')
   if(reasons.length){withheld.push({condition,reasons:[...new Set(reasons)]});continue}
   const result={condition,finding,basis:finding.evidence_basis==='photo_observation'?'Reviewer-entered photographic observation':finding.evidence_basis==='clinical_record_review'?'Reviewer-entered clinical-record label':'Reported history; not confirmed by photographs'}
   if(finding.state==='uncertain')uncertain.push(result);else possible.push(result)
  }
 }
 const usable=record.photos.filter(p=>p.quality==='usable'&&p.view_confirmed),missing=standardViews.slice(0,5).filter(view=>!usable.some(p=>p.standard_view===view))
 const normal=record.normal_appearance==='present'&&record.scope==='in_scope'&&usable.length>0&&!record.findings.some(f=>f.state==='present'||f.state==='uncertain')
 return {possible,uncertain,withheld,usable,missing,normal,notAssessable:record.findings.filter(f=>f.state==='not_assessable').length,reviewRecommended:possible.length>0||uncertain.length>0||withheld.length>0||record.scope!=='in_scope'||missing.length>0}
}
export function parseScreeningRecord(value:unknown):ScreeningRecord{
 if(!value||typeof value!=='object')throw new Error('No screening record was supplied.')
 const r=value as ScreeningRecord
 if(r.schema_version!=='humantwin-orthodontic-screening-v1'||r.taxonomy_version!==screeningTaxonomy.version||r.clinical_validation!==false||r.classifier_applied!==false||r.model_training_performed!==false||!Array.isArray(r.findings)||r.findings.length!==conditions.length||new Set(r.findings.map(f=>f.id)).size!==conditions.length||r.findings.some(f=>!conditionIds.has(f.id)||!assessmentStates.includes(f.state)||!Array.isArray(f.locations))||!Array.isArray(r.photos)||r.photos.length>6||r.photos.some(p=>p.data_url!==null&&(typeof p.data_url!=='string'||p.data_url.length>350000||!/^data:image\/jpeg;base64,[A-Za-z0-9+/=]+$/.test(p.data_url)))||!r.review||!r.classifications)throw new Error('The screening record did not match the taxonomy and annotation contract.')
 return JSON.parse(JSON.stringify(r)) as ScreeningRecord
}
