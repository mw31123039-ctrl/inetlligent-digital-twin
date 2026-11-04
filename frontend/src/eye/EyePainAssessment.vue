<script setup lang="ts">
import { computed } from 'vue'
import { painAssessment } from './pain'
import {assistance,suggestPain} from './painSuggestion'
import type { EyeSession,EyeTurn } from './types'
const props=defineProps<{session:EyeSession;enabled:boolean}>()
const emit=defineEmits<{answer:[turn:EyeTurn]}>()
const assessment=computed(()=>painAssessment(props.session))
const locale=computed(()=>props.session.locale)
const proposal=computed(()=>suggestPain(props.session))
const assistantMode=computed(()=>props.session.reported.pain_entry_mode==='assistant')
function action(name:string,value=name){emit('answer',{question_id:`pain-estimate:${name}`,value})}
</script>
<template><section class="eye-pain-assessment" aria-label="Assistant pain assessment" :data-band="assessment.band">
 <div class="eye-pain-heading"><div><span class="eye-kicker">{{locale==='en'?'PAIN CHECK-IN':locale==='ar-IQ'?'تقييم الألم':'پشکنینی ئازار'}}</span><h4>{{locale==='en'?'Let’s understand your pain':locale==='ar-IQ'?'خل نفهم ألمك':'با لە ئازارەکەت تێبگەین'}}</h4></div><output data-testid="eye-pain-score">{{assessment.score===null?'—':assessment.score}}<small>/ 10</small></output></div>
 <p data-testid="eye-pain-feedback">{{assessment.summary}}</p>
 <button class="eye-estimate-start" :aria-pressed="assistantMode" :disabled="!enabled||session.urgency!=='unknown'" @click="action('start')">{{assistance.labels.button[locale]}}</button>
 <div v-if="assistantMode" class="eye-pain-suggestion" :data-estimate-status="proposal.status" data-testid="eye-pain-suggestion"><span class="eye-kicker">{{assistance.labels.title[locale]}}</span><template v-if="proposal.status==='suggested'"><strong class="eye-pain-suggested-number" data-testid="pain-suggested-score">≈ {{proposal.suggested_score}}<small>/10</small></strong><p>{{locale==='en'?'Suggested range':locale==='ar-IQ'?'المدى المقترح':'مەودای پێشنیارکراو'}}: {{proposal.range?.join('–')}} / 10</p><p class="eye-pain-disclaimer">{{assistance.labels.limit[locale]}}</p><button class="eye-estimate-accept" :disabled="!enabled||session.urgency==='emergency'" @click="action('accept',String(proposal.suggested_score))">{{assistance.labels.accept[locale]}}</button></template><p v-else>{{(proposal.status==='needs_clarification'?assistance.labels.conflict:assistance.labels.waiting)[locale]}}</p><button class="eye-estimate-skip" :disabled="!enabled||session.urgency!=='unknown'" @click="action('skip')">{{assistance.labels.skip[locale]}}</button></div>
 <p v-if="session.urgency!=='unknown'" class="eye-pain-conflict">{{assistance.labels.urgent[locale]}}</p>
 <button class="eye-pain-manual-toggle" :disabled="!enabled||session.urgency!=='unknown'" @click="action('manual')">{{assistance.labels.change[locale]}}</button>
 <div v-if="session.reported.pain_entry_mode==='manual'" class="eye-pain-numbers" role="group" aria-label="Your pain score"><button v-for="n in 11" :key="n" :aria-label="`Pain ${n-1} out of 10`" :aria-pressed="assessment.score===n-1" :disabled="!enabled||session.urgency!=='unknown'" @click="emit('answer',{question_id:'question.pain',value:String(n-1)})">{{n-1}}</button></div>
 <div class="eye-pain-anchors"><span>{{locale==='en'?'0 · No pain':locale==='ar-IQ'?'0 · بدون ألم':'٠ · بێ ئازار'}}</span><span>{{locale==='en'?'10 · Worst imaginable':locale==='ar-IQ'?'10 · أشد ألم تتخيله':'١٠ · توندترین ئازاری بیرهاتوو'}}</span></div>
 <p v-if="assessment.conflict" class="eye-pain-conflict" role="status">{{locale==='en'?'You also described severe pain. Please confirm the score; warning guidance stays active.':locale==='ar-IQ'?'هم وصفت ألم شديد. أكد الرقم؛ إرشادات الخطر تبقى فعالة.':'هەروەها ئازاری توندت وەسف کرد. نمرەکە پشتڕاست بکەرەوە؛ ڕێنمایی مەترسی چالاک دەمێنێتەوە.'}}</p>
 <p class="eye-pain-disclaimer">{{locale==='en'?'Suggested, confirmed and self-reported scores stay separate. Pain severity never cancels a warning about vision loss or injury.':locale==='ar-IQ'?'الدرجات المقترحة والمؤكدة والمبلغ عنها تبقى منفصلة. الألم ما يلغي تحذير فقدان النظر أو الإصابة.':'نمرەی پێشنیارکراو، پشتڕاستکراو و ڕاگەیەنراو جیا دەمێننەوە. ئاستی ئازار هەرگیز ئاگاداریی لەدەستدانی بینین یان برینداری هەڵناوەشێنێتەوە.'}}</p>
</section></template>
