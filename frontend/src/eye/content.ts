import anatomy from '../../../contracts/eye/anatomy.v1.json'
import interview from '../../../contracts/eye/interview.v1.json'
import catalogue from '../../../contracts/eye/conditions.v1.json'
import review from '../../../contracts/eye/review.v1.json'
import type { EyeLocale, EyeQuestion, EyeStructure, Localized } from './types'
export { anatomy, interview, catalogue, review }
export const structures = anatomy.structures as EyeStructure[]
export const questions = interview.questions as EyeQuestion[]
export const structureById = new Map(structures.map(item => [item.id,item]))
export const text = (value: Localized, locale:EyeLocale) => value[locale] || value.en
export const ui = {
 title: {en:'Inside the eye', 'ar-IQ':'داخل العين',ckb:'لە ناو چاو'},
 explore: {en:'Explore anatomy','ar-IQ':'استكشف التشريح',ckb:'گەڕان لە پێکهاتەی چاو'},
 report: {en:'Report symptoms','ar-IQ':'وصف الأعراض',ckb:'باسکردنی نیشانەکان'},
 catalogue:{en:'Condition library','ar-IQ':'مكتبة الحالات',ckb:'کتێبخانەی نەخۆشییەکان'},
 draft:{en:'Draft educational preview · synthetic examples only · live clinical triage disabled','ar-IQ':'معاينة تعليمية مسودة · أمثلة افتراضية فقط · التقييم الطبي الحي معطل',ckb:'پێشبینینی ڕەشنووسی فێرکاری · تەنها نموونەی دەستکرد · هەڵسەنگاندنی پزیشکیی ڕاستەوخۆ ناچالاکە'},
 search:{en:'Search anatomy','ar-IQ':'ابحث بالتشريح',ckb:'گەڕان لە پێکهاتەکان'},
 left:{en:'Patient’s left','ar-IQ':'يسار المريض',ckb:'چەپی نەخۆش'},right:{en:'Patient’s right','ar-IQ':'يمين المريض',ckb:'ڕاستی نەخۆش'},
 unknown:{en:'Unknown','ar-IQ':'غير معروف',ckb:'نادیار'},
 send:{en:'Send answer','ar-IQ':'أرسل الجواب',ckb:'وەڵام بنێرە'},
 reset:{en:'Start over','ar-IQ':'ابدأ من جديد',ckb:'لە سەرەتاوە دەست پێبکە'},
 summary:{en:'Reported summary','ar-IQ':'ملخص المعلومات المبلغ عنها',ckb:'پوختەی زانیارییە ڕاگەیەنراوەکان'},
 original:{en:'Original English · medical translation pending review','ar-IQ':'النص الإنكليزي الأصلي · الترجمة الطبية بانتظار المراجعة',ckb:'دەقی ڕەسەنی ئینگلیزی · وەرگێڕانی پزیشکی چاوەڕێی پێداچوونەوەیە'},
 notDiagnosis:{en:'A selected structure is learning context, not a diagnosis or the origin of a symptom.','ar-IQ':'اختيار تركيب للتعلم مو تشخيص ولا دليل على مصدر العرض.',ckb:'هەڵبژاردنی پێکهاتە بۆ فێربوونە، دەستنیشانکردنی نەخۆشی یان سەرچاوەی نیشانە نییە.'},
 } satisfies Record<string,Localized>
export const viewLabels:Record<string,Localized>={
 external:{en:'External','ar-IQ':'خارجي',ckb:'دەرەکی'},section:{en:'Cross-section','ar-IQ':'مقطع','ckb':'بڕگە'},transparent:{en:'Transparent','ar-IQ':'شفاف',ckb:'شەفاف'},exploded:{en:'Exploded','ar-IQ':'مفكك',ckb:'پارچەکراو'},posterior:{en:'Posterior','ar-IQ':'خلفي',ckb:'پشتەوە'},'corneal-detail':{en:'Cornea × detail','ar-IQ':'تفاصيل القرنية',ckb:'وردەکاریی قەرنیە'},'retinal-detail':{en:'Retina × detail','ar-IQ':'تفاصيل الشبكية',ckb:'وردەکاریی تۆڕینە'}
}
