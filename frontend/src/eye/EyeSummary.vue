<script setup lang="ts">
import { interview,structureById,text,ui } from './content'
import { computed } from 'vue'
import { painAssessment } from './pain'
import EyeCareAdvice from './EyeCareAdvice.vue'
import type { EyeSession } from './types'
const props=defineProps<{session:EyeSession}>()
const explored=computed(()=>props.session.anatomy_explored.map(id=>structureById.get(id)?.label[props.session.locale]).join(', '))
const assessedPain=computed(()=>painAssessment(props.session))
</script>
<template><section class="eye-summary" :dir="session.locale==='en'?'ltr':'rtl'" :lang="session.locale" aria-label="Eye assessment summary">
 <h3>{{text(ui.summary,session.locale)}}</h3><p class="eye-subtle">{{text(ui.draft,session.locale)}}</p><p class="eye-summary-pain">{{assessedPain.summary}}</p>
 <dl class="eye-summary-grid"><div><dt>{{session.locale==='en'?'Reported side':session.locale==='ar-IQ'?'الجهة المبلغ عنها':'لای ڕاگەیەنراو'}}</dt><dd data-testid="eye-reported-side">{{session.reported.laterality==='unknown'?text(ui.unknown,session.locale):session.reported.laterality}}</dd></div><div><dt>{{session.locale==='en'?'Reported location':session.locale==='ar-IQ'?'المكان المبلغ عنه':'شوێنی ڕاگەیەنراو'}}</dt><dd>{{interview.locations.find(x=>x.id===session.reported.location)?.label[session.locale]||text(ui.unknown,session.locale)}}</dd></div><div><dt>{{session.locale==='en'?'Model side (learning only)':session.locale==='ar-IQ'?'جهة النموذج (للتعلم فقط)':'لای مۆدێل (تەنها بۆ فێربوون)'}}</dt><dd>{{text(session.model_side==='left'?ui.left:ui.right,session.locale)}}</dd></div><div><dt>{{session.locale==='en'?'Pain / 10':session.locale==='ar-IQ'?'الألم من 10':'ئازار لە ١٠'}}</dt><dd>{{session.reported.pain??text(ui.unknown,session.locale)}}</dd></div></dl>
 <EyeCareAdvice v-if="session.turns.some(t=>!t.question_id.startsWith('learn:'))" :session="session" compact/>
 <details open><summary>{{session.locale==='en'?'Reported symptoms & answers':session.locale==='ar-IQ'?'الأعراض والأجوبة المبلغ عنها':'نیشانە و وەڵامە ڕاگەیەنراوەکان'}}</summary><div class="eye-anatomy-chips"><span v-for="symptom in interview.symptoms.filter(s=>session.symptoms[s.id]==='present')" :key="symptom.id">{{symptom.label[session.locale]}}</span></div><dl class="eye-answer-list"><div v-for="(value,key) in session.reported" :key="key"><dt>{{String(key).replaceAll('_',' ')}}</dt><dd dir="auto">{{value}}</dd></div></dl></details>
 <details><summary>{{session.locale==='en'?'Anatomy explored · separate from symptom location':session.locale==='ar-IQ'?'التشريح المستكشف · منفصل عن مكان العرض':'پێکهاتەی گەڕاو · جیا لە شوێنی نیشانە'}}</summary><p>{{explored||text(ui.unknown,session.locale)}}</p></details>
 <details><summary>{{session.locale==='en'?'Warning sign states: present / absent / unknown':session.locale==='ar-IQ'?'حالات علامات الخطر: موجود / غير موجود / غير معروف':'دۆخی نیشانەکانی مەترسی: هەیە / نییە / نادیار'}}</summary><dl class="eye-answer-list"><div v-for="(value,id) in session.red_flags" :key="id"><dt>{{id}}</dt><dd>{{value}}</dd></div></dl></details>
 <details><summary>{{session.locale==='en'?'Information still missing':session.locale==='ar-IQ'?'المعلومات الناقصة':'زانیارییە ماوەکان'}}</summary><p>{{session.missing.join(', ')}}</p><p>{{session.locale==='en'?'Examination and testing have not been performed. No diagnosis or confidence percentage is provided.':session.locale==='ar-IQ'?'لم يتم إجراء فحص أو اختبارات. ماكو تشخيص أو نسبة ثقة.':'پشکنین و تاقیکردنەوە نەکراون. هیچ دەستنیشانکردن یان ڕێژەی دڵنیاییەک نادرێت.'}}</p></details>
 <p>{{text(interview.actions[session.urgency],session.locale)}}</p><div class="eye-reference-links"><a v-for="url in session.source_urls" :key="url" :href="url" target="_blank" rel="noopener noreferrer">{{url.replace('https://','').split('/')[0]}} ↗</a></div><p class="eye-subtle">{{session.rule_version}} · DRAFT · {{session.rule_ids.join(', ')||'Urgency not established'}} · {{session.created_at}}</p>
</section></template>
