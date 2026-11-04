import assistance from '../../../contracts/eye/pain-assistance.v1.json'
import type {EyeSession} from './types'
export {assistance}
export function suggestPain(state:Pick<EyeSession,'reported'|'locale'>){
 const descriptor=String(state.reported.pain_descriptor||'unknown'),impact=String(state.reported.pain_function||'unknown')
 const supported=Object.hasOwn(assistance.proposals,descriptor)
 const table=supported?assistance.proposals[descriptor as keyof typeof assistance.proposals]:null
 const score=table&&Object.hasOwn(table,impact)?table[impact as keyof typeof table]:null
 const range=supported?assistance.ranges[descriptor as keyof typeof assistance.ranges]:null
 const status=!supported?'insufficient':score===null?(impact==='unknown'?'insufficient':'needs_clarification'):'suggested'
 const active=['assistant','confirmed'].includes(String(state.reported.pain_entry_mode))||state.reported.pain_source==='assisted-confirmed'
 return {version:assistance.version,clinical_review_status:'draft' as const,status:active?status:'not_requested',suggested_score:active?score??null:null,range:active?range:null,band:active&&supported?descriptor:'unknown',based_on:{description:descriptor,activity_impact:impact},numeric_source:'assistant-estimate' as const,confirmed:state.reported.pain_source==='assisted-confirmed',source_urls:assistance.source_urls}
}
