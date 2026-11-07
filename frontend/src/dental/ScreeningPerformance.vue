<script setup lang="ts">
import { ref } from 'vue'
import { downloadCase } from './caseModel'
import { conditions } from './screeningModel'
import { evaluateScreeningCases } from './screeningEvaluation'
const truth=ref<unknown>(),predictions=ref<unknown>(),report=ref<ReturnType<typeof evaluateScreeningCases>|null>(null),error=ref('')
async function read(event:Event,kind:'truth'|'predictions'){
 const input=event.target as HTMLInputElement,file=input.files?.[0];input.value='';if(!file)return;error.value='';report.value=null
 try{if(file.size>10000000)throw new Error('Use a JSON file no larger than 10 MB. Evaluation needs annotations and hashes, not photo pixels.');const value=JSON.parse(await file.text());if(kind==='truth')truth.value=value;else predictions.value=value}
 catch{error.value='The evaluation file could not be read as bounded JSON.'}
}
function evaluate(){error.value='';try{report.value=evaluateScreeningCases(truth.value,predictions.value)}catch(failure){report.value=null;error.value=failure instanceof Error?failure.message:'The evaluation inputs were invalid.'}}
const number=(value:number|null|undefined)=>value===null||value===undefined?'Not evaluated':value.toFixed(3)
</script>
<template>
 <section class="screening-performance panel" aria-label="Per-condition screening performance"><span class="dental-eyebrow">RESEARCH EVALUATION · NO CLINICAL ACCURACY CLAIM</span><h3>Measure each condition separately.</h3><p>No trained orthodontic condition classifier or reviewed test dataset is bundled. All performance values therefore start as not evaluated. A list of conditions or a text prompt does not train an image classifier.</p><details><summary>Evaluate actual local-model outputs</summary><p>Provide a screening annotation JSON record (or array of records) from the test split and a separate model prediction bundle. Only present/absent reviewed truth is scored; uncertain and not-assessable truth is excluded. Prediction abstentions are shown with coverage. Sensitivity/recall, specificity and precision use covered predictions only.</p><p>Calibration uses actual supplied model probabilities: Brier score and expected calibration error with ten fixed bins. No score is synthesized for a model that provides none. Brier measures probability error rather than calibration alone; ECE depends on the cohort and bins. Select thresholds before examining the test set.</p><div class="screening-fields"><label>Reviewed held-out annotations<input type="file" accept="application/json,.json" aria-label="Screening evaluation truth file" @change="read($event,'truth')"/></label><label>Local model predictions<input type="file" accept="application/json,.json" aria-label="Screening evaluation prediction file" @change="read($event,'predictions')"/></label></div><button class="button-secondary" :disabled="!truth||!predictions" @click="evaluate">Calculate per-condition metrics</button><details><summary>Prediction file format</summary><pre>{
  "schema_version": "humantwin-screening-predictions-v1",
  "prediction_origin": "local_model_output",
  "model_id": "YOUR_ACTUAL_LOCAL_MODEL",
  "model_version": "YOUR_MODEL_VERSION",
  "threshold_policy": "Document thresholds fixed before test evaluation",
  "training_subject_codes": [],
  "validation_subject_codes": [],
  "predictions": [{
    "subject_code": "TEST_PATIENT_CODE",
    "visit_code": "TEST_VISIT_CODE",
    "source_sha256s": ["Exact source photo fingerprints"],
    "findings": [{"id": "dental_crowding", "state": "not_assessable", "probability": null}]
  }]
}</pre><p>Supply all 41 unique label IDs per visit; the abbreviated format above shows one. Unknown scores stay null. Every test visit needs an explicit output record, including abstentions. These files declare provenance; the evaluator does not certify that the model generated them.</p></details></details><p v-if="error" class="dental-error" role="alert">{{error}}</p><div v-if="report" class="screening-message"><strong>{{report.model_id}} · {{report.model_version}}</strong><p>{{report.test_visits}} test visits from {{report.test_patients}} patients. {{report.denominator_policy}}</p><p>{{report.review_policy}}</p><button class="button-secondary" @click="downloadCase(report,'orthodontic-condition-evaluation.json')">Export calculated metrics</button></div><div class="screening-metrics-table"><table><caption>41 conditions · sensitivity and recall are the same rate</caption><thead><tr><th scope="col">Condition</th><th scope="col">Eligible / covered / abstained</th><th scope="col">Sensitivity / recall</th><th scope="col">Specificity</th><th scope="col">Precision</th><th scope="col">Coverage</th><th scope="col">Brier / ECE</th></tr></thead><tbody><tr v-for="condition in conditions" :key="condition.id"><th scope="row">{{condition.name}}</th><td>{{report?`${report.rows.find(row=>row.id===condition.id)!.eligible} / ${report.rows.find(row=>row.id===condition.id)!.covered} / ${report.rows.find(row=>row.id===condition.id)!.abstained}`:'No model outputs'}}</td><td>{{number(report?.rows.find(row=>row.id===condition.id)?.sensitivity)}}</td><td>{{number(report?.rows.find(row=>row.id===condition.id)?.specificity)}}</td><td>{{number(report?.rows.find(row=>row.id===condition.id)?.precision)}}</td><td>{{number(report?.rows.find(row=>row.id===condition.id)?.coverage)}}</td><td>{{number(report?.rows.find(row=>row.id===condition.id)?.brier)}} / {{number(report?.rows.find(row=>row.id===condition.id)?.ece)}}</td></tr></tbody></table></div></section>
</template>
