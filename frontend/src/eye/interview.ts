import { interview, questions, structures } from './content'
import type { EyeLocale, EyeQuestion, EyeSession, EyeTurn, Finding } from './types'
import { educationalExchange } from './knowledge'
import { painAssessment } from './pain'
import { eyeCarePlan,eyeDoctorSummary } from './care'
import {assistance,suggestPain} from './painSuggestion'

const version=interview.version
const unknown='unknown'
const visualSymptoms=['vision-loss','blurred-vision','double-vision','curtain','blind-spots','distorted-lines','colour-change']
export function newEyeSession(side:'left'|'right'='left',locale:EyeLocale='en'):EyeSession {
 const state:EyeSession={id:crypto.randomUUID(),locale,use:'education',anatomy_explored:[],model_side:side,reported:{laterality:unknown,location:unknown,pain_entry_mode:'assistant'},symptoms:Object.fromEntries(interview.symptoms.map(s=>[s.id,'unknown' as Finding])),turns:[],messages:[],acknowledgements:[],urgency:'unknown',rule_ids:[],red_flags:{},missing:[],unconfirmed_explanations:[],source_urls:[],rule_version:version,source_version:version,clinical_review_status:'draft',created_at:new Date().toISOString()}
 return evaluateEye(state)
}
function positive(state:EyeSession,id:string){return state.symptoms[`symptom.${id}`]==='present'}
function isVisual(state:EyeSession){return ['loss','blurred','double'].includes(String(state.reported.vision))||visualSymptoms.some(id=>positive(state,id))}
function negative(prefix:string){return new RegExp(interview.negation_pattern,'iu').test(prefix)||/(?:not|never|no|without|denies|لا|بدون)\s*$/iu.test(prefix)}

/** Bounded lexical intake. Never treats silence as a negative or translates free text. */
export function parseEyeText(state:EyeSession,input:string){
 const text=input.normalize('NFKC')
 const clauses=text.split(/[;.!?\n]|\bbut\b/iu)
 for(const clause of clauses){
  for(const item of interview.lexical){
   const matches=[...clause.matchAll(new RegExp(item.pattern,'giu'))]
   for(const m of matches){if(!negative(clause.slice(0,m.index)))state.reported[item.field]=item.value}
  }
  for(const [id,pattern] of Object.entries(interview.symptom_patterns)){
   for(const m of clause.matchAll(new RegExp(pattern,'giu'))){state.symptoms[`symptom.${id}`]=negative(clause.slice(0,m.index))?'absent':'present'}
  }
 }
 if(/\b(?:no pain|painless|without pain)\b|بدون ألم|بێ ئازار/iu.test(text)){state.reported.pain=0;state.reported.pain_source='self-reported';state.reported.pain_entry_mode='manual';state.symptoms['symptom.pain']='absent'}
 if(/(?:severe|terrible|excruciating) (?:eye )?pain|ألم شديد|ئازاری توند/iu.test(text)&&!/(?:no|not) severe/iu.test(text)){state.reported.pain_descriptor='severe';state.symptoms['symptom.pain']='present'}
 else if(/\bmild (?:eye )?pain\b|ألم خفيف|ئازاری سووک/iu.test(text)){state.reported.pain_descriptor='mild';state.symptoms['symptom.pain']='present'}
 else if(/\bmoderate (?:eye )?pain\b|ألم متوسط|ئازاری مامناوەند/iu.test(text)){state.reported.pain_descriptor='moderate';state.symptoms['symptom.pain']='present'}
 const pain=text.match(/\b(10|[0-9])\s*(?:\/\s*10|out of 10)\b/i);if(pain){state.reported.pain=Number(pain[1]);state.reported.pain_source='self-reported';state.reported.pain_entry_mode='manual';state.symptoms['symptom.pain']=Number(pain[1])>0?'present':'absent'}
 for(const item of assistance.activity_patterns){const match=new RegExp(item.pattern,'iu').exec(text);if(match&&!negative(text.slice(0,match.index))){state.reported.pain_function=item.value;break}}
 if(/\b(?:newborn|neonate)\b|مولود جديد|تازەلەدایکبوو/iu.test(text)){state.reported.age=0;state.reported.newborn='yes'}
 else if(/\b(?:my child|my baby|my son|my daughter|toddler)\b|طفلي|طفلتي|منداڵەکەم/iu.test(text))state.reported.child='yes'
 const age=text.match(/\b(\d{1,3})\s*(?:years? old|year.old|y\/o)\b/i);if(age&&Number(age[1])<=120)state.reported.age=Number(age[1])
 const sides=[...text.matchAll(/\b(both eyes|left eye|right eye|bilateral)\b|العينين|العين اليسرى|العين اليمنى|هەردوو چاو|چاوی چەپ|چاوی ڕاست/giu)].filter(m=>!negative(text.slice(0,m.index)))
 const values=new Set(sides.map(m=>/both|bilateral|العينين|هەردوو/iu.test(m[0])?'both':/left|اليسرى|چەپ/iu.test(m[0])?'left':'right'))
 if(values.size===1){
  const side=[...values][0]!
  if(state.reported.laterality!==side){state.reported.laterality=side;state.acknowledgements.push(({left:{en:'Reported side updated to the patient’s left eye.','ar-IQ':'تم تحديث الجهة المبلغ عنها إلى العين اليسرى.','ckb':'لای ڕاگەیەنراو بۆ چاوی چەپی نەخۆش نوێکرایەوە.'},right:{en:'Reported side updated to the patient’s right eye.','ar-IQ':'تم تحديث الجهة المبلغ عنها إلى العين اليمنى.','ckb':'لای ڕاگەیەنراو بۆ چاوی ڕاستی نەخۆش نوێکرایەوە.'},both:{en:'You reported both eyes. The symptom summary now says both; the model still shows one eye for learning.','ar-IQ':'وصفت العينين. الملخص هسه يذكر العينين؛ النموذج يعرض عين وحدة للتعلم.','ckb':'هەردوو چاوت باسکرد. پوختەکە ئێستا هەردوو چاو دەڵێت؛ مۆدێلەکە بۆ فێربوون یەک چاو پیشان دەدات.'}})[side][state.locale])}
 }else if(values.size>1){state.reported.laterality='unknown';state.acknowledgements.push('Laterality is ambiguous. Please choose left, right, both or not sure. / الجهة غير واضحة / لا نادیارە.')}
}
function fact(state:EyeSession,key:string,value:unknown):Finding{
 if(key==='symptom')return state.symptoms[`symptom.${value}`]||'unknown'
 if(key==='symptoms')return combine((value as string[]).map(id=>fact(state,'symptom',id)),false)
 if(key==='visual'){
  if(isVisual(state))return 'present'
  return state.reported.vision==='unchanged'?'absent':'unknown'
 }
 if(key==='pain_gte'){if(state.reported.pain_descriptor==='severe'&&Number(value)<=7)return 'present';return typeof state.reported.pain==='number'?(state.reported.pain>=Number(value)?'present':'absent'):'unknown'}
 if(key==='newborn'){if(state.reported.newborn==='yes')return 'present';if(typeof state.reported.age_days==='number')return state.reported.age_days<28?'present':'absent';return typeof state.reported.age==='number'&&state.reported.age>0?'absent':'unknown'}
 const actual=state.reported[key]
 if(actual===undefined||actual===unknown||actual==='')return unknown
 return (Array.isArray(value)?value.includes(actual):actual===value)?'present':'absent'
}
function combine(values:Finding[],all:boolean):Finding{
 if(all){if(values.includes('absent'))return 'absent';return values.every(v=>v==='present')?'present':'unknown'}
 if(values.includes('present'))return 'present';return values.every(v=>v==='absent')?'absent':'unknown'
}
function clause(state:EyeSession,condition:unknown,all:boolean):Finding{
 if(!condition)return 'present'
 return combine(Object.entries(condition as Record<string,unknown>).map(([key,value])=>fact(state,key,value)),all)
}
export function evaluateEye(state:EyeSession):EyeSession{
 // Escalation is sticky within a session. Start over to discard an erroneous report.
 const ids=new Set(state.rule_ids)
 for(const rule of interview.rules){
  const result=combine([clause(state,rule.all,true),clause(state,rule.any,false)],true)
  state.red_flags[rule.id]=ids.has(rule.id)?'present':result
  if(result==='present')ids.add(rule.id)
 }
 state.rule_ids=[...ids]
 const matches=interview.rules.filter(rule=>ids.has(rule.id))
 state.urgency=matches.some(r=>r.level==='emergency')?'emergency':matches.length?'urgent':'unknown'
 state.source_urls=[...new Set(matches.flatMap(r=>r.source_urls))]
 state.missing=questions.filter(q=>!(q.field in state.reported)||state.reported[q.field]===unknown).map(q=>q.field)
 state.care_plan=eyeCarePlan(state)
 state.pain_estimate=suggestPain(state)
 state.doctor_summary=eyeDoctorSummary(state)
 return state
}
export function questionRelevant(state:EyeSession,question:EyeQuestion):boolean{
 if(!question.when)return true
 if(question.when.pain_present)return positive(state,'pain')||typeof state.reported.pain==='number'&&state.reported.pain>0
 if(question.when.any_symptoms)return (question.when.any_symptoms as string[]).some(id=>positive(state,id))
 if(question.when.visual)return isVisual(state)
 if(question.when.child)return state.reported.child==='yes'||(typeof state.reported.age==='number'&&state.reported.age<16)
 return Object.entries(question.when).every(([key,value])=>state.reported[key]===value)
}
export function nextEyeQuestion(state:EyeSession):EyeQuestion|null{
 if(state.urgency!=='unknown')return null
 const answered=new Set(state.turns.map(t=>t.question_id))
 // Reported explicit facts skip redundant questions; a declined answer remains unknown.
 for(const q of questions){
  if(q.id==='question.pain-description')continue
  if(answered.has(q.id)||!questionRelevant(state,q)||q.field in state.reported&&state.reported[q.field]!==unknown)continue
  if(q.field==='pain'){
   if(state.reported.pain_entry_mode==='skipped')continue
   if(state.reported.pain_entry_mode==='assistant'){
    if(!state.reported.pain_descriptor||state.reported.pain_descriptor===unknown)return answered.has('question.pain-description')?null:questions.find(item=>item.id==='question.pain-description')||null
    const estimate=suggestPain(state)
    if(estimate.status==='suggested'||estimate.status==='needs_clarification')return null
    return answered.has('question.pain-function')?null:questions.find(item=>item.id==='question.pain-function')||null
   }
  }
  return q
 }
 return null
}
export function answerEye(state:EyeSession,turn:EyeTurn):EyeSession{
 const previousPain=painAssessment(state)
 if(turn.value.length>2000||!turn.value.trim())throw new Error('Enter an answer between 1 and 2000 characters.')
 if(state.turns.length>=120)throw new Error('This educational session reached its limit.')
 if(turn.question_id.startsWith('pain-estimate:')){
  if(state.urgency==='emergency')throw new Error('Emergency guidance takes priority. Do not delay care to confirm a score.')
  const action=turn.question_id.slice('pain-estimate:'.length)
  if(!['start','accept','manual','skip'].includes(action))throw new Error('Unknown pain helper action.')
  if(action==='accept'){
   const proposal=suggestPain(state)
   if(proposal.status!=='suggested'||proposal.suggested_score===null||turn.value!==String(proposal.suggested_score))throw new Error('The proposed score changed. Confirm the current suggestion.')
   state.reported.pain=proposal.suggested_score;state.reported.pain_source='assisted-confirmed';state.reported.pain_entry_mode='confirmed'
   state.symptoms['symptom.pain']=proposal.suggested_score>0?'present':'absent'
  }else state.reported.pain_entry_mode=action==='start'?'assistant':action==='skip'?'skipped':'manual'
  state.turns.push({...turn});evaluateEye(state)
  if(action==='accept')state.messages.push({role:'user',text:({en:'Yes, use the suggested pain score.','ar-IQ':'نعم، استخدم درجة الألم المقترحة.',ckb:'بەڵێ، نمرەی پێشنیارکراوی ئازار بەکاربهێنە.'})[state.locale]},{role:'assistant',text:painAssessment(state).summary,source_urls:suggestPain(state).source_urls})
  return state
 }
 if(turn.question_id.startsWith('learn:')){
  if(state.urgency!=='unknown')throw new Error('Please follow the urgency guidance before continuing educational chat.')
  educationalExchange(state,turn.question_id.slice(6),turn.value);return state
 }
 if(state.urgency==='emergency'||state.urgency==='urgent'&&turn.question_id!=='question.concern')throw new Error('Routine questions stop after an urgency warning. Start over for another synthetic example.')
 const q=questions.find(item=>item.id===turn.question_id)
 if(!q)throw new Error('Unknown question.')
 if(q.options.length&&!q.options.some(o=>o.value===turn.value)&&!turn.text)throw new Error('Choose a supported answer or provide free text.')
 if(['pain','age','days'].includes(q.type)&&turn.value!==unknown&&!turn.text){const n=Number(turn.value);if(!Number.isInteger(n)||n<0||n>(q.type==='pain'?10:q.type==='days'?365:120))throw new Error('Enter a valid number.')}
 state.turns.push({...turn})
 const isOption=q.options.some(o=>o.value===turn.value)
 if(isOption||['pain','age','days'].includes(q.type)&&turn.value!==unknown&&!turn.text)state.reported[q.field]=['pain','age','days'].includes(q.type)&&turn.value!==unknown?Number(turn.value):turn.value
 else state.reported[q.field]=q.type==='text'?turn.value:unknown
 if(q.field==='pain'&&typeof state.reported.pain==='number')state.symptoms['symptom.pain']=state.reported.pain>0?'present':'absent'
 if(q.field==='pain'&&typeof state.reported.pain==='number'){state.reported.pain_source='self-reported';state.reported.pain_entry_mode='manual'}
 if(q.field==='pain_descriptor'&&['mild','moderate','severe','none'].includes(String(state.reported.pain_descriptor)))state.symptoms['symptom.pain']=state.reported.pain_descriptor==='none'?'absent':'present'
 if(q.field==='vision'){
  for(const [value,id] of [['loss','vision-loss'],['blurred','blurred-vision'],['double','double-vision']]){
   if(state.reported.vision===value)state.symptoms[`symptom.${id}`]='present'
   else if(state.reported.vision==='unchanged')state.symptoms[`symptom.${id}`]='absent'
  }
 }
 const message=isOption?q.options.find(o=>o.value===turn.value)!.label[state.locale]:turn.text||turn.value
 state.messages.push({role:'assistant',text:q.text[state.locale]},{role:'user',text:message})
 // Structured negatives are authoritative; never parse the translated option label.
 if(!isOption&&!['pain','age','days'].includes(q.type))parseEyeText(state,turn.text||turn.value)
 evaluateEye(state)
 const assessedPain=painAssessment(state)
 if(q.field==='pain'||assessedPain.score!==previousPain.score||assessedPain.band!==previousPain.band)state.messages.push({role:'assistant',text:assessedPain.summary,source_urls:assessedPain.source_urls})
 return state
}
export function replayEye(turns:EyeTurn[],side:'left'|'right',locale:EyeLocale,explored:string[]=[]){
 const state=newEyeSession(side,locale)
 state.anatomy_explored=explored.filter(id=>structures.some(s=>s.id===id))
 for(const turn of turns)answerEye(state,turn)
 return state
}
