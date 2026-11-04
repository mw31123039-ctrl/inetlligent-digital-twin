<script setup lang="ts">
import { computed,ref } from 'vue'
import { care,eyeCarePlan,eyeDoctorSummary } from './care'
import type { EyeSession } from './types'
const props=defineProps<{session:EyeSession;compact?:boolean}>()
const plan=computed(()=>eyeCarePlan(props.session)),summary=computed(()=>eyeDoctorSummary(props.session)),copyState=ref('')
const locale=computed(()=>props.session.locale)
async function copy(){try{await navigator.clipboard.writeText(summary.value);copyState.value=({en:'Copied. Share this with the clinician.','ar-IQ':'تم النسخ. شاركه ويا الطبيب.',ckb:'کۆپیکرا. لەگەڵ پزیشک هاوبەشی بکە.'})[locale.value]}catch{copyState.value=({en:'Copy is unavailable here. Download the summary instead.','ar-IQ':'النسخ مو متاح. نزل الملخص بدل ذلك.',ckb:'کۆپیکردن بەردەست نییە. لە جیاتی ئەوە پوختەکە دابگرە.'})[locale.value]}}
function download(){const url=URL.createObjectURL(new Blob([summary.value],{type:'text/plain;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download=`humantwin-eye-doctor-${props.session.id}.txt`;a.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000)}
</script>
<template><section class="eye-care-advice" :class="[plan.level,{'care-compact':compact}]" aria-label="Eye care advice and doctor recommendation" data-testid="eye-care-advice">
 <span class="eye-kicker">{{locale==='en'?'DRAFT CARE GUIDANCE':locale==='ar-IQ'?'إرشادات رعاية مسودة':'ڕێنمایی چاودێریی ڕەشنووس'}}</span>
 <h3>{{care.headings.title[locale]}}</h3><div class="eye-doctor-route" data-testid="eye-doctor-route"><span>{{care.headings.doctor[locale]}}</span><strong>{{plan.doctor.title[locale]}}</strong><p>{{plan.doctor.description[locale]}}</p></div>
 <ol v-if="!compact" class="eye-care-steps"><li v-for="step in plan.steps" :key="step.id" :data-care-step="step.id">{{step.text[locale]}}</li></ol>
 <p class="eye-care-limit">{{care.headings.limitation[locale]}}</p>
 <details class="eye-doctor-summary"><summary>{{care.headings.handoff[locale]}}</summary><pre dir="auto">{{summary}}</pre><div class="eye-care-buttons"><button type="button" @click="copy">{{care.headings.copy[locale]}}</button><button type="button" @click="download">{{care.headings.download[locale]}}</button></div><p v-if="copyState" role="status">{{copyState}}</p><h4>{{care.headings.questions[locale]}}</h4><ul><li v-for="q in care.doctor_questions" :key="q.en">{{q[locale]}}</li></ul></details>
 <div v-if="!compact" class="eye-care-sources"><a v-for="url in plan.source_urls" :key="url" :href="url" target="_blank" rel="noopener noreferrer">{{url.replace('https://','').split('/')[0]}} ↗</a></div>
</section></template>
