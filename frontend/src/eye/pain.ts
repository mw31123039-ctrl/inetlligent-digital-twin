import scale from '../../../contracts/eye/pain-scale.v1.json'
import type { EyeSession } from './types'
import {suggestPain} from './painSuggestion'
export function painAssessment(state:Pick<EyeSession,'reported'|'locale'>){
 const score=typeof state.reported.pain==='number'&&Number.isInteger(state.reported.pain)&&state.reported.pain>=0&&state.reported.pain<=10?state.reported.pain:null
 const descriptor=String(state.reported.pain_descriptor||'unknown')
 const band=score!==null?scale.bands.find(b=>score>=b.min&&score<=b.max):scale.bands.find(b=>b.id===descriptor)
 const conflict=score!==null&&score<=3&&descriptor==='severe'
 const proposal=suggestPain(state)
 const summary=score!==null?({en:`You reported ${score}/10: ${band?.label.en.toLowerCase()}.`,'ar-IQ':`بلغت عن ${score}/10: ${band?.label['ar-IQ']}.`,ckb:`تۆ ${score}/10 ڕاگەیاند: ${band?.label.ckb}.`})[state.locale]:band?({en:`You described ${band.label.en.toLowerCase()}; no numeric score has been assigned.`,'ar-IQ':`وصفت ${band.label['ar-IQ']}؛ ما تم تعيين رقم من عند المساعد.`,ckb:`تۆ ${band.label.ckb} وەسف کرد؛ هیچ نمرەیەکی ژمارەیی دیاری نەکراوە.`})[state.locale]:({en:'Pain has not been rated yet. Choose 0–10, including 0 for no pain.','ar-IQ':'الألم بعده مو مقيم. اختار من صفر إلى عشرة، وصفر يعني بدون ألم.',ckb:'ئازار هێشتا نمرەی بۆ دانەنراوە. سفر تا دە هەڵبژێرە؛ سفر واتە بێ ئازار.'})[state.locale]
 const assisted=state.reported.pain_source==='assisted-confirmed'
 const displaySummary=score!==null&&assisted?({en:`You confirmed the assistant’s suggestion of ${score}/10: ${band?.label.en.toLowerCase()}.`,'ar-IQ':`أكدت اقتراح المساعد ${score}/10: ${band?.label['ar-IQ']}.`,ckb:`تۆ پێشنیاری یاریدەدەرت پشتڕاست کردەوە ${score}/10: ${band?.label.ckb}.`})[state.locale]:score===null&&proposal.status==='suggested'&&state.reported.pain_entry_mode==='assistant'?({en:`Assistant suggestion: about ${proposal.suggested_score}/10 (${band?.label.en.toLowerCase()}); no numeric score is recorded until you confirm.`,'ar-IQ':`اقتراح المساعد: تقريباً ${proposal.suggested_score}/10 (${band?.label['ar-IQ']})؛ ما يتسجل رقم لحد ما تأكد.`,ckb:`پێشنیاری یاریدەدەر: نزیکەی ${proposal.suggested_score}/10 (${band?.label.ckb})؛ تا پشتڕاستی نەکەیتەوە نمرە تۆمار ناکرێت.`})[state.locale]:summary
 return {score,band:band?.id||'unknown',label:band?.label[state.locale]||({en:'Not rated','ar-IQ':'غير مقيم',ckb:'نمرە نەدراو'})[state.locale],summary:displaySummary,conflict,impact:state.reported.pain_function||'unknown',numeric_source:score===null?'not-reported':assisted?'assisted-confirmed':'self-reported',source_urls:scale.source_urls}
}
