import { annotationIssues, assessmentStates, conditions, parseScreeningRecord, type AssessmentState } from './screeningModel'

export type PredictionBundle={schema_version:'humantwin-screening-predictions-v1';prediction_origin:'local_model_output';model_id:string;model_version:string;threshold_policy:string;training_subject_codes:string[];validation_subject_codes:string[];predictions:{subject_code:string;visit_code:string;source_sha256s:string[];findings:{id:string;state:AssessmentState;probability:number|null}[]}[]}
export type ConditionMetrics={id:string;eligible:number;covered:number;abstained:number;tp:number;tn:number;fp:number;fn:number;sensitivity:number|null;specificity:number|null;precision:number|null;recall:number|null;coverage:number|null;brier:number|null;ece:number|null;calibration_samples:number}
const rate=(numerator:number,denominator:number)=>denominator?numerator/denominator:null
const code=/^[A-Za-z0-9_-]{1,48}$/
const key=(subject:string,visit:string)=>subject.toLowerCase()+':'+visit.toLowerCase()
export function evaluateScreeningCases(truthInput:unknown,predictionInput:unknown){
 const input=Array.isArray(truthInput)?truthInput:[truthInput],bundle=predictionInput as PredictionBundle
 if(input.length<1||input.length>1000||bundle?.schema_version!=='humantwin-screening-predictions-v1'||bundle.prediction_origin!=='local_model_output'||![bundle.model_id,bundle.model_version,bundle.threshold_policy].every(v=>typeof v==='string'&&v.trim().length>0&&v.length<=300)||!Array.isArray(bundle.training_subject_codes)||!Array.isArray(bundle.validation_subject_codes)||!Array.isArray(bundle.predictions))throw new Error('Supply reviewed test records and a declared local-model prediction bundle, with model/version and threshold policy.')
 if([...bundle.training_subject_codes,...bundle.validation_subject_codes].some(v=>typeof v!=='string'||!code.test(v)))throw new Error('Model training and validation subject codes must be explicitly listed.')
 const training=new Set(bundle.training_subject_codes.map(v=>v.toLowerCase())),validation=new Set(bundle.validation_subject_codes.map(v=>v.toLowerCase()))
 if([...training].some(v=>validation.has(v)))throw new Error('The declared model training and validation subjects overlap.')
 const truth=input.map(parseScreeningRecord),truthKeys=new Set<string>(),photos=new Map<string,string>()
 for(const item of truth){
  const subject=item.subject_code.toLowerCase(),id=key(item.subject_code,item.visit_code)
  if(!code.test(item.subject_code)||!code.test(item.visit_code)||item.partition!=='test'||training.has(subject)||validation.has(subject)||truthKeys.has(id))throw new Error('Use distinct test visits from patients excluded from the model’s training and validation sets.')
  if(item.is_demonstration||item.review.reviewer_role!=='orthodontist'||!item.review.reviewer_code||!item.review.annotations_reviewed||!item.review.definitions_reviewed||!item.consent_training||item.data_rights==='not_confirmed'||annotationIssues(item).length)throw new Error('Evaluation requires permitted test annotations with recorded orthodontist review and resolved annotation issues. Review remains self-attested.')
  truthKeys.add(id)
  for(const photo of item.photos){const previous=photos.get(photo.source_sha256);if(previous&&previous!==subject)throw new Error('A source photograph is assigned to different patients.');photos.set(photo.source_sha256,subject)}
 }
 const predictions=new Map<string,PredictionBundle['predictions'][number]>()
 for(const prediction of bundle.predictions){
  if(!prediction||!code.test(prediction.subject_code)||!code.test(prediction.visit_code)||!Array.isArray(prediction.source_sha256s)||!Array.isArray(prediction.findings)||prediction.findings.length!==conditions.length||new Set(prediction.findings.map(f=>f.id)).size!==conditions.length||prediction.findings.some(f=>!conditions.some(c=>c.id===f.id)||!assessmentStates.includes(f.state)||f.probability!==null&&(typeof f.probability!=='number'||!Number.isFinite(f.probability)||f.probability<0||f.probability>1)))throw new Error('Predictions must explicitly provide the 41 known labels; model probabilities must be null or finite values from 0 to 1.')
  const id=key(prediction.subject_code,prediction.visit_code);if(predictions.has(id)||!truthKeys.has(id))throw new Error('Prediction visits are duplicated or do not match the supplied test cohort.');predictions.set(id,prediction)
 }
 if(predictions.size!==truth.length)throw new Error('Every test visit must have an explicit prediction record, including abstentions.')
 const rows:ConditionMetrics[]=conditions.map(condition=>({id:condition.id,eligible:0,covered:0,abstained:0,tp:0,tn:0,fp:0,fn:0,sensitivity:null,specificity:null,precision:null,recall:null,coverage:null,brier:null,ece:null,calibration_samples:0}))
 const scores=new Map<string,{p:number;y:number}[]>()
 for(const item of truth){
  const prediction=predictions.get(key(item.subject_code,item.visit_code))!,expected=item.photos.map(photo=>photo.source_sha256).sort()
  if(JSON.stringify([...prediction.source_sha256s].sort())!==JSON.stringify(expected))throw new Error('Prediction photo fingerprints do not match the test visit.')
  for(const row of rows){const annotation=item.findings.find(f=>f.id===row.id)!,predicted=prediction.findings.find(f=>f.id===row.id)!
   if(annotation.state!=='present'&&annotation.state!=='absent')continue
   row.eligible++;const y=annotation.state==='present'?1:0
   if(predicted.state==='present'||predicted.state==='absent'){row.covered++;if(predicted.state==='present'){if(y)row.tp++;else row.fp++}else{if(y)row.fn++;else row.tn++}}else row.abstained++
   if(predicted.probability!==null){const entries=scores.get(row.id)||[];entries.push({p:predicted.probability,y});scores.set(row.id,entries)}
  }
 }
 for(const row of rows){row.sensitivity=rate(row.tp,row.tp+row.fn);row.recall=row.sensitivity;row.specificity=rate(row.tn,row.tn+row.fp);row.precision=rate(row.tp,row.tp+row.fp);row.coverage=rate(row.covered,row.eligible)
  const entries=scores.get(row.id)||[];row.calibration_samples=entries.length
  if(entries.length){row.brier=entries.reduce((sum,item)=>sum+(item.p-item.y)**2,0)/entries.length;row.ece=0;for(let bin=0;bin<10;bin++){const values=entries.filter(item=>Math.min(9,Math.floor(item.p*10))===bin);if(values.length)row.ece+=values.length/entries.length*Math.abs(values.reduce((s,item)=>s+item.p,0)/values.length-values.reduce((s,item)=>s+item.y,0)/values.length)}}
 }
 return {clinical_validation:false,model_id:bundle.model_id,model_version:bundle.model_version,threshold_policy:bundle.threshold_policy,test_visits:truth.length,test_patients:new Set(truth.map(item=>item.subject_code.toLowerCase())).size,unit:'patient_visit',denominator_policy:'Sensitivity, specificity, precision and recall use covered binary predictions only. Abstentions and coverage are reported separately. Uncertain/not-assessable truth is excluded. Calibration uses only actual supplied model probabilities on binary truth.',review_policy:'Orthodontist review and model provenance are declared by the supplied files, not independently verified. Multiple visits from one patient are correlated; these calculations do not establish clinical validity.',rows}
}
