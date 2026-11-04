<script setup lang="ts">
import { computed,inject,onBeforeUnmount,ref,watch } from 'vue'
import { catalogue,review,structures,text,ui } from './content'
import { aiApi } from '../services/aiApi'
import EyeAtlas from './EyeAtlas.vue'
import EyeCatalogue from './EyeCatalogue.vue'
import EyeInterview from './EyeInterview.vue'
import EyeSummary from './EyeSummary.vue'
import type { EyeLocale,EyeSession,EyeTurn } from './types'
import { createEyeContext,eyeContextKey } from './context'
const props=defineProps<{side:'left'|'right';reducedMotion:boolean;user:{id:number;email:string}|null;authPending:boolean;authError:string}>()
const emit=defineEmits<{close:[];side:[value:'left'|'right'];authenticate:[email:string,password:string,register:boolean]}>()
const shared=inject(eyeContextKey)||createEyeContext(props.side)
const session=shared.session,selected=shared.selected,ack=shared.acknowledged
const locale=computed<EyeLocale>({get:()=>session.locale,set:value=>{session.locale=value}})
const tab=ref<'explore'|'report'|'catalogue'|'records'>('explore')
const error=ref(''),storageConsent=ref(false),pending=ref(false),saved=ref(false)
const email=ref(''),password=ref(''),register=ref(false)
const records=ref<{id:string;created_at:string}[]>([]),inspected=ref<EyeSession|null>(null)
let generation=0
onBeforeUnmount(()=>{generation++})
const direction=computed(()=>locale.value==='en'?'ltr':'rtl')
function reset(){generation++;shared.reset();storageConsent.value=false;saved.value=false;error.value='';pending.value=false;inspected.value=null}
function explore(id:string){shared.explore(id);saved.value=false}
function answer(turn:EyeTurn){shared.answer(turn);error.value=shared.error.value;saved.value=false}
function changeSide(side:'left'|'right'){session.model_side=side;emit('side',side)}
watch(locale,value=>{session.locale=value})
watch(()=>props.user?.id,(value,old)=>{if(old!==undefined&&old!==value){reset();records.value=[];inspected.value=null}})
async function save(){if(!props.user||!storageConsent.value||!ack.value||!session.turns.length)return;const g=++generation,userId=props.user.id;const payload=JSON.parse(JSON.stringify({id:session.id,use:'education',locale:session.locale,model_side:session.model_side,anatomy_explored:session.anatomy_explored,turns:session.turns,consent:true,consent_version:'health-storage-v1'}));pending.value=true;error.value='';try{
 await aiApi.csrf()
 if(g!==generation||props.user?.id!==userId)return
 await aiApi.post('/eye/assessments',payload)
 if(g===generation)saved.value=true
 }catch(e){if(g===generation)error.value=e instanceof Error?e.message:'Saving failed.'}finally{if(g===generation)pending.value=false}}
async function list(){tab.value='records';if(!props.user)return;const g=++generation;pending.value=true;error.value='';try{const result=await aiApi.get<{id:string;created_at:string}[]>('/eye/assessments');if(g===generation)records.value=result}catch(e){if(g===generation)error.value=e instanceof Error?e.message:'History unavailable.'}finally{if(g===generation)pending.value=false}}
async function open(id:string){const g=++generation;error.value='';try{const result=await aiApi.get<{session:EyeSession}>(`/eye/assessments/${id}`);if(g===generation)inspected.value=result.session}catch(e){if(g===generation)error.value=e instanceof Error?e.message:'Record unavailable.'}}
async function remove(id:string){const g=++generation;error.value='';try{await aiApi.csrf();await aiApi.delete(`/eye/assessments/${id}`);if(g===generation){records.value=records.value.filter(r=>r.id!==id);if(inspected.value?.id===id)inspected.value=null;if(session.id===id)reset()}}catch(e){if(g===generation)error.value=e instanceof Error?e.message:'Deletion failed.'}}
function download(){const blob=new Blob([JSON.stringify({demonstration:true,clinical_use_available:false,content_version:review.version,session},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`humantwin-eye-${session.id}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
explore(selected.value)
</script>
<template><section class="eye-workspace" :dir="direction" :lang="locale" aria-label="Detailed eye explorer" data-testid="eye-workspace">
 <div class="eye-workspace-top"><button class="eye-back" @click="emit('close')">← {{locale==='en'?'Back to body explorer':locale==='ar-IQ'?'رجوع لاستكشاف الجسم':'گەڕانەوە بۆ گەڕانی لەش'}}</button><label class="eye-language">{{locale==='en'?'Language':locale==='ar-IQ'?'اللغة':'زمان'}}<select v-model="locale" aria-label="Eye explorer language"><option value="en">English</option><option value="ckb">کوردی سۆرانی</option><option value="ar-IQ">عربي عراقي</option></select></label></div>
 <div class="eye-hero"><div><span class="eye-kicker">HUMANTWIN / ANATOMY ATLAS / 01</span><h2>{{text(ui.title,locale)}}<span class="eye-hero-dot">.</span></h2><p>{{locale==='en'?'An intricate world. A clearer understanding.':locale==='ar-IQ'?'عالم دقيق. فهم أوضح.':'جیهانێکی ورد. تێگەیشتنێکی ڕوونتر.'}}</p></div><div class="eye-hero-stat"><strong>{{structures.length}}</strong><span>{{locale==='en'?'anatomical structures':locale==='ar-IQ'?'تركيب تشريحي':'پێکهاتەی چاو'}}</span><small>{{catalogue.conditions.length}} {{locale==='en'?'educational records':locale==='ar-IQ'?'سجل تعليمي':'تۆماری فێرکاری'}}</small></div></div>
 <div class="eye-review-banner" role="note"><span aria-hidden="true">◇</span><p>{{text(ui.draft,locale)}}<small v-if="locale!=='en'">{{text(ui.original,locale)}}</small></p></div>
 <div class="eye-workspace-toolbar"><div class="eye-main-tabs" role="group" aria-label="Eye explorer mode"><button :aria-pressed="tab==='explore'" @click="tab='explore'">01 <span>{{text(ui.explore,locale)}}</span></button><button :aria-pressed="tab==='report'" @click="tab='report'">02 <span>{{text(ui.report,locale)}}</span></button><button :aria-pressed="tab==='catalogue'" @click="tab='catalogue'">03 <span>{{text(ui.catalogue,locale)}}</span></button><button :aria-pressed="tab==='records'" @click="list">{{locale==='en'?'Saved eye records':locale==='ar-IQ'?'سجلات العين المحفوظة':'تۆمارە پاشەکەوتکراوەکان'}}</button></div><div class="eye-side-selector" role="group" aria-label="Anatomical patient side"><button v-for="sideValue in (['left','right'] as const)" :key="sideValue" :aria-pressed="session.model_side===sideValue" @click="changeSide(sideValue)">{{text(ui[sideValue],locale)}}</button></div></div>
 <p v-if="error" class="eye-error" role="alert">{{error}}</p>
 <EyeAtlas v-show="tab==='explore'" :side="session.model_side" :locale="locale" :reduced-motion="reducedMotion" :selected="selected" @select="explore" @report="tab='report'"/>
 <template v-if="tab==='report'"><EyeInterview :session="session" :acknowledged="ack" @answer="answer" @acknowledge="ack=$event" @reset="reset"/><div v-if="session.turns.length" class="eye-save-bar"><button class="button-secondary" @click="download">{{locale==='en'?'Export draft summary':locale==='ar-IQ'?'تصدير ملخص المسودة':'هەناردەکردنی پوختەی ڕەشنووس'}}</button><label><input v-model="storageConsent" type="checkbox" :disabled="saved||pending"/>{{locale==='en'?'I consent to encrypted storage in my account until I delete this record.':locale==='ar-IQ'?'أوافق على الحفظ المشفر بحسابي لحد ما أحذف السجل.':'ڕازیم بە پاشەکەوتکردنی کۆدکراو لە هەژمارەکەم تا کاتی سڕینەوەی تۆمارەکە.'}}</label><button class="button-primary" :disabled="!user||!storageConsent||pending||saved||!ack" @click="save">{{saved?(locale==='en'?'Saved':locale==='ar-IQ'?'تم الحفظ':'پاشەکەوتکرا'):(locale==='en'?'Save with consent':locale==='ar-IQ'?'حفظ بالموافقة':'پاشەکەوت بە ڕەزامەندی')}}</button></div></template>
 <EyeCatalogue v-if="tab==='catalogue'" :locale="locale" :selected="selected" @explore="explore($event);tab='explore'"/>
 <section v-if="tab==='records'" class="eye-records"><h3>{{locale==='en'?'Your saved eye records':locale==='ar-IQ'?'سجلات عينك المحفوظة':'تۆمارەکانی چاوی تۆ'}}</h3><p v-if="!user">{{locale==='en'?'Sign in below to access your encrypted, consented records.':locale==='ar-IQ'?'سجل دخولك أدناه لعرض سجلاتك المشفرة المحفوظة بموافقتك.':'لە خوارەوە بچۆ ژوورەوە بۆ تۆمارە کۆدکراو و ڕەزامەندکراوەکانت.'}}</p><p v-if="user&&!records.length&&!pending">{{locale==='en'?'No saved eye records. Existing body assessments remain in Assessments / History.':locale==='ar-IQ'?'ماكو سجلات عين محفوظة. تقييمات الجسم السابقة موجودة بالتقييمات والتاريخ.':'تۆماری پاشەکەوتکراوی چاو نییە. هەڵسەنگاندنەکانی پێشووی لەش لە مێژوودان.'}}</p><article v-for="r in records" :key="r.id"><time>{{r.created_at}}</time><button @click="open(r.id)">{{locale==='en'?'View summary':locale==='ar-IQ'?'عرض الملخص':'بینینی پوختە'}}</button><button @click="remove(r.id)">{{locale==='en'?'Delete record':locale==='ar-IQ'?'حذف السجل':'سڕینەوەی تۆمار'}}</button></article><EyeSummary v-if="inspected" :session="{...inspected,locale}"/></section>
 <form v-if="!user&&(tab==='records'||tab==='report')" class="eye-auth" @submit.prevent="emit('authenticate',email,password,register);password='' "><h4>{{locale==='en'?'Sign in to save or read records':locale==='ar-IQ'?'سجل دخولك لحفظ أو قراءة السجلات':'بۆ پاشەکەوت یان خوێندنەوەی تۆمارەکان بچۆ ژوورەوە'}}</h4><label>Email<input v-model="email" type="email" required autocomplete="email"/></label><label>{{locale==='en'?'Password':locale==='ar-IQ'?'كلمة المرور':'وشەی نهێنی'}}<input v-model="password" type="password" :minlength="register?12:1" required :autocomplete="register?'new-password':'current-password'"/></label><label><input v-model="register" type="checkbox"/>{{locale==='en'?'Create a test account (12+ character password)':locale==='ar-IQ'?'إنشاء حساب تجريبي (كلمة مرور 12 حرف أو أكثر)':'دروستکردنی هەژماری تاقیکردنەوە (وشەی نهێنی ١٢ پیت یان زیاتر)'}}</label><button class="button-primary" :disabled="authPending">{{locale==='en'?'Continue':locale==='ar-IQ'?'استمر':'بەردەوام بە'}}</button><p v-if="authError" role="alert">{{authError}}</p></form>
 <footer class="eye-workspace-footer"><span>{{review.version}} · {{locale==='en'?'Anatomical schematic, not a patient scan.':locale==='ar-IQ'?'رسم تشريحي تخطيطي، مو تصوير للمريض.':'هێڵکاریی پێکهاتەی چاوە، سکانێکی نەخۆش نییە.'}}</span><span>{{locale==='en'?'Medical & translation review pending':locale==='ar-IQ'?'بانتظار مراجعة الطب والترجمة':'چاوەڕێی پێداچوونەوەی پزیشکی و وەرگێڕان'}}</span></footer>
</section></template>
