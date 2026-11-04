import care from '../../../contracts/eye/care.v1.json'
import { interview } from './content'
import { painAssessment } from './pain'
import type { EyeSession,Localized } from './types'
export { care }
export function eyeCarePlan(session:EyeSession){
 const level=session.urgency
 const child=session.reported.child==='yes'||session.reported.newborn==='yes'||typeof session.reported.age==='number'&&session.reported.age<16
 const childRule=session.rule_ids.includes('eye.rule.newborn-red-sticky')||child&&session.rule_ids.includes('eye.rule.white-pupil')
 const route=level==='emergency'?'emergency':level==='urgent'?(childRule?'paediatric':'urgent'):'assessment'
 const steps:{id:string;text:Localized}[]=[]
 const chemical=interview.rules.find(rule=>rule.id==='eye.rule.chemical'&&session.rule_ids.includes(rule.id))
 if(chemical?.first_aid)steps.push({id:'chemical-rinse',text:chemical.first_aid})
 if(level==='emergency')steps.push(care.steps.travel,care.steps.protect)
 if(['penetrating','high-speed'].includes(String(session.reported.exposure)))steps.push(care.steps.embedded)
 if(session.reported.contact_lenses==='yes'&&session.reported.exposure!=='penetrating')steps.push(care.steps.lenses)
 // Comfort measures never accompany urgent/emergency results, unknown safety answers or recent procedures.
 const comfort=level==='unknown'&&session.reported.vision==='unchanged'&&session.reported.exposure==='none'&&session.reported.contact_lenses==='no'&&session.reported.recent_procedure==='no'&&session.reported.onset==='gradual'&&typeof session.reported.pain==='number'&&session.reported.pain<=3&&['dryness','grittiness','burning'].some(id=>session.symptoms[`symptom.${id}`]==='present')
 if(comfort)steps.push(care.steps.screen,care.steps.environment)
 if(level!=='unknown')steps.push(care.steps.prepare)
 steps.push(care.steps.medicine)
 if(level==='unknown')steps.push(care.steps.worsening)
 return {version:care.version,clinical_review_status:'draft' as const,level,route,doctor:care.routes[route],steps,comfort_measures_included:comfort,source_urls:[...new Set([care.sources.pain,...session.source_urls,...(comfort?[care.sources.dry]:[]),...(level==='emergency'?[care.sources.injury]:[]),...(session.reported.contact_lenses==='yes'?[care.sources.red]:[])])]}
}
/** Factual handoff, not a diagnosis, referral order or treatment instruction to a doctor. */
export function eyeDoctorSummary(session:EyeSession){
 const plan=eyeCarePlan(session),locale=session.locale
 const facts=Object.entries(session.reported).map(([key,value])=>`${key.replaceAll('_',' ')}: ${value}`)
 const present=interview.symptoms.filter(s=>session.symptoms[s.id]==='present').map(s=>s.label[locale])
 const originals=session.turns.filter(t=>!t.question_id.startsWith('learn:')).map(t=>`${t.question_id}: ${t.text||t.value}`)
 return [
  'HumanTwin — synthetic educational eye summary / NOT A DIAGNOSIS',
  `Created: ${session.created_at}`,`Draft warning result: ${session.urgency}`,`Care service: ${plan.doctor.title[locale]}`,
  'Reported symptoms: '+(present.join(', ')||'Not established'),painAssessment(session).summary,
  ...facts,'','Reason for urgency:',...interview.rules.filter(r=>session.rule_ids.includes(r.id)).map(r=>`${r.id}: ${r.reason[locale]}`),
  '',`Pain-score origin: ${painAssessment(session).numeric_source}. Assistant suggestion (${session.pain_estimate?.confirmed?'patient-confirmed':'unconfirmed'}): ${session.pain_estimate?.suggested_score??'none'}/10. This is not a measured score.`,
  '', 'Information still unknown: '+session.missing.join(', '),
  'No examination, eye-pressure measurement, imaging or clinical diagnosis has been performed in this chat.',
  '', 'Original answers (kept in the language entered):',...originals,
  '', 'Questions for the examining clinician:',...care.doctor_questions.map(q=>q[locale]),
  '',`Rules: ${session.rule_version}; care: ${plan.version}; clinical review: pending`,
  'Sources:',...plan.source_urls
 ].join('\n')
}
