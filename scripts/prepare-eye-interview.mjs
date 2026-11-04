import { writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expandEyeQuestions } from './eye-expanded-questions.mjs'
import { readFileSync } from 'node:fs'
const loc=(en,ar,ckb)=>({en,'ar-IQ':ar,ckb})
const version='eye-draft-2026-10-30.4'
const rows=`pain|Pain|ألم|ئازار
burning|Burning|حرقة|سووتان
itching|Itching|حكة|خوران
grittiness|Grittiness|إحساس بالرمل|هەستی لم
foreign-body|Foreign-body sensation|إحساس بجسم غريب|هەستی شتێکی نامۆ
redness|Redness|احمرار|سووربوونەوە
watering|Watering|دموع زائدة|فرمێسکی زۆر
dryness|Dryness|جفاف|وشکی
discharge|Discharge|إفرازات|دەردانی شلە
crusting|Crusting|قشور|توێکڵ
swelling|Swelling|تورم|ئاوسان
lid-lump|Eyelid lump|كتلة بالجفن|گرێ لە پلک
drooping|Drooping eyelid|تدلي الجفن|داکەوتنی پلک
twitching|Eyelid twitching|رفة الجفن|لەرزینی پلک
blurred-vision|Blurred vision|غشاوة بالنظر|تەماوی بینین
double-vision|Double vision|ازدواج النظر|دووانبینین
vision-loss|Loss of vision|فقدان النظر|لەدەستدانی بینین
flashes|Flashes|ومضات ضوئية|بروسکەی ڕووناکی
floaters|Floaters|عوائم بالنظر|خاڵی جووڵاو
curtain|Curtain or shadow|ستار أو ظل بالنظر|پەردە یان سێبەر لە بینین
halos|Halos|هالات حول الضوء|بازنە دەوری ڕووناکی
glare|Glare|انبهار بالضوء|بریقەی ڕووناکی
light-sensitivity|Light sensitivity|حساسية للضوء|هەستیاری بە ڕووناکی
distorted-lines|Distorted lines|خطوط متعرجة|خەتی خواروخێچ
blind-spots|Blind spots|بقع عمياء|خاڵی نابینا
colour-change|Colour changes|تغير بالألوان|گۆڕانی ڕەنگ
night-vision|Poor night vision|ضعف النظر بالليل|لاوازی بینینی شەو
protrusion|Protrusion|جحوظ العين|هاتنەدەرەوەی چاو
movement-pain|Pain on eye movement|ألم عند تحريك العين|ئازار لە جووڵاندنی چاو
white-pupil|White pupil or reflection|بؤبؤ أو انعكاس أبيض|بیلبیلە یان ڕەنگدانەوەی سپی
unequal-pupils|New unequal pupils|اختلاف جديد بحجم البؤبؤ|جیاوازی نوێی قەبارەی بیلبیلە`
const symptoms=rows.split('\n').map(row=>{const [id,en,ar,ckb]=row.split('|');return {id:`symptom.${id}`,label:loc(en,ar,ckb),kind:'symptom_or_observed_sign'}})
const locations=[['whole-eye','Whole eye','كل العين','هەموو چاو'],['surface','Surface','سطح العين','ڕووکاری چاو'],['eyelid','Eyelid','الجفن','پلک'],['behind','Behind the eye','خلف العين','پشت چاو'],['around','Around the eye','حول العين','دەوروبەری چاو'],['unknown','Not sure','مو متأكد','دڵنیا نیم']].map(([id,...labels])=>({id,label:loc(...labels)}))
const option=(value,en,ar,ckb)=>({value,label:loc(en,ar,ckb)})
const yesno=[option('yes','Yes','نعم','بەڵێ'),option('no','No','لا','نەخێر'),option('unknown','Not sure','مو متأكد','دڵنیا نیم')]
const questions=[]
function q(id,field,en,ar,ckb,options=[],when=null,type='choice'){questions.push({id:`question.${id}`,field,text:loc(en,ar,ckb),options,when,type})}
q('concern','concern','What is the main eye concern in this synthetic example?','شنو المشكلة الرئيسية بالعين بهذا المثال التعليمي؟','لە ئەم نموونە فێرکارییەدا کێشەی سەرەکی چاو چییە؟',[],null,'text')
q('vision','vision','Has the vision changed?','هل تغير النظر؟','ئایا بینین گۆڕاوە؟',[option('unchanged','No change','ماكو تغير','گۆڕان نییە'),option('blurred','Blurred','غشاوة','تەماوی'),option('loss','Some or all vision lost','فقدان جزء أو كل النظر','لەدەستدانی هەندێک یان هەموو بینین'),option('double','Double vision','ازدواج النظر','دووانبینین'),option('unknown','Not sure','مو متأكد','دڵنیا نیم')])
q('exposure','exposure','Was there an injury or chemical splash?','صار جرح أو تعرض لمادة كيميائية؟','برینداری یان پڕژانی ماددەی کیمیایی ڕوویداوە؟',[option('none','No','لا','نەخێر'),option('chemical','Chemical splash','مادة كيميائية','ماددەی کیمیایی'),option('penetrating','Sharp or embedded object','جسم حاد أو مغروس','شتێکی تیژ یان چەسپاو'),option('high-speed','High-speed impact','ضربة بسرعة عالية','پێکدادان بە خێرایی زۆر'),option('other','Other injury','إصابة أخرى','برینداری تر'),option('unknown','Not sure','مو متأكد','دڵنیا نیم')])
q('onset','onset','Did the problem start suddenly or gradually?','المشكلة بدت فجأة لو بالتدريج؟','کێشەکە لەناکاو دەستی پێکرد یان وردەوردە؟',[option('sudden','Suddenly','فجأة','لەناکاو'),option('gradual','Gradually','بالتدريج','وردەوردە'),option('unknown','Not sure','مو متأكد','دڵنیا نیم')])
q('pain','pain','How much eye pain is there, from 0 (none) to 10?','شكد ألم العين من صفر (بدون ألم) إلى عشرة؟','ئازاری چاو لە سفر (بێ ئازار) تا دە چەندە؟',[],null,'pain')
q('side','laterality','Which eye is affected, from the patient’s perspective?','أي عين متأثرة من جهة المريض؟','لە ڕوانگەی نەخۆشەوە کام چاو تووش بووە؟',[option('left','Left','اليسرى','چەپ'),option('right','Right','اليمنى','ڕاست'),option('both','Both eyes','العينين','هەردوو چاو'),option('unknown','Not sure','مو متأكد','دڵنیا نیم')])
q('location','location','Where does the problem seem to be?','وين تحس المشكلة؟','هەست دەکەیت کێشەکە لە کوێیە؟',locations.map(x=>({value:x.id,label:x.label})))
q('duration','duration','How long has the problem been present?','صارلها شكد المشكلة؟','کێشەکە ماوەی چەندە هەیە؟',[],null,'text')
q('progression','progression','Is it getting worse, improving or staying the same?','دا تسوء لو تتحسن لو مثل ما هي؟','خراپتر دەبێت، باشتر دەبێت یان وەک خۆیەتی؟',[option('worsening','Getting worse','دا تسوء','خراپتر دەبێت'),option('improving','Improving','دا تتحسن','باشتر دەبێت'),option('same','Unchanged','مثل ما هي','وەک خۆیەتی'),option('unknown','Not sure','مو متأكد','دڵنیا نیم')])
q('age','age','What is the patient’s age in years? For a newborn, enter 0.','شكد عمر المريض بالسنين؟ للمولود الجديد اكتب صفر.','تەمەنی نەخۆش بە ساڵ چەندە؟ بۆ تازەلەدایکبوو سفر بنووسە.',[],null,'age')
q('infant-age','age_days','For a baby under one year, how many days old are they?','للطفل الأقل من سنة، شكد عمره بالأيام؟','بۆ منداڵی خوار یەک ساڵ، تەمەنی بە ڕۆژ چەندە؟',[],{age:0},'days')
q('contact','contact_lenses','Are contact lenses worn?','يستخدم عدسات لاصقة؟','لێنزی چەسپاو بەکاردەهێنێت؟',yesno)
q('overnight','overnight','Were contact lenses worn during sleep?','نام بالعدسات اللاصقة؟','بە لێنزی چەسپاوەوە نووستووە؟',yesno,{contact_lenses:'yes'})
q('water','water_exposure','Did the lenses contact tap water, a pool or shower water?','العدسات لامست مي الحنفية أو المسبح أو الدوش؟','لێنزەکان پەیوەندییان بە ئاوی بۆری، مەلەوانگە یان دووشەوە هەبووە؟',yesno,{contact_lenses:'yes'})
q('surgery','recent_procedure','Was there recent eye surgery, injection or another eye procedure?','صار مؤخراً عملية أو حقنة أو إجراء للعين؟','لە ماوەی ڕابردوودا نەشتەرگەری، دەرزی یان کرداری چاو کراوە؟',yesno)
q('movement','movement_pain','Does moving the eye hurt or feel restricted?','تحريك العين يوجع أو حركتها محدودة؟','جووڵاندنی چاو ئازاری هەیە یان سنووردارە؟',yesno,{any_symptoms:['swelling','protrusion','pain','double-vision']})
q('fever','fever','Is there a fever?','أكو حرارة؟','تا هەیە؟',yesno,{any_symptoms:['swelling','protrusion','movement-pain']})
q('headache','severe_headache','Is there a severe or new headache?','أكو صداع شديد أو جديد؟','سەرئێشەی توند یان نوێ هەیە؟',yesno,{any_symptoms:['redness','pain','vision-loss','double-vision','unequal-pupils']})
q('nausea','nausea','Is there nausea or vomiting?','أكو غثيان أو تقيؤ؟','دڵتێکچوون یان ڕشانەوە هەیە؟',yesno,{severe_headache:'yes'})
q('vascular','jaw_scalp','Is there new jaw pain when chewing or scalp tenderness?','أكو ألم جديد بالفك عند المضغ أو ألم بفروة الرأس؟','ئازاری نوێی چەناگە لە کاتی جوین یان ناسکیی سەری پێست هەیە؟',yesno,{visual:true})
q('neurological','neurological','Is there new weakness, facial droop, confusion or trouble speaking?','أكو ضعف جديد، تدلي بالوجه، تشوش أو صعوبة بالكلام؟','لاوازیی نوێ، داکەوتنی ڕوو، شێوان یان کێشەی قسەکردن هەیە؟',yesno,{any_symptoms:['double-vision','vision-loss','unequal-pupils']})
q('caregiver','caregiver','What has the caregiver noticed about the child’s eyes or behaviour?','شنو لاحظ مقدم الرعاية على عيون الطفل أو تصرفاته؟','چاودێر چی لە چاوەکان یان ڕەفتاری منداڵەکە تێبینی کردووە؟',[],{child:true},'text')
q('diabetes','diabetes','Does the patient have diabetes?','المريض عنده سكري؟','نەخۆشەکە شەکرەی هەیە؟',yesno)
q('immunity','immunosuppressed','Is the immune system weakened by illness or treatment?','المناعة ضعيفة بسبب مرض أو علاج؟','بەرگریی لەش بەهۆی نەخۆشی یان چارەسەرەوە لاوازە؟',yesno)
q('history','history','What relevant eye problems or treatments happened before?','شنو مشاكل أو علاجات العين السابقة؟','پێشتر چ کێشە یان چارەسەرێکی پەیوەندیدار بە چاو هەبووە؟',[],null,'text')
q('medicines','medicines','What medicines are used, including eye drops?','شنو الأدوية المستخدمة، ومنها قطرات العين؟','چ دەرمانێک بەکاردەهێنرێت، لەوانەش دڵۆپی چاو؟',[],null,'text')
const sources={
 injuries:'https://www.nhs.uk/conditions/eye-injuries/',vision:'https://www.nhs.uk/conditions/vision-loss/',red:'https://www.nhs.uk/symptoms/red-eye/',flashes:'https://www.nhs.uk/symptoms/floaters-and-flashes-in-the-eyes/',
 orbit:'https://www.msdmanuals.com/professional/eye-disorders/orbital-diseases/preseptal-and-orbital-cellulitis',postop:'https://www.msdmanuals.com/professional/eye-disorders/uveitis-and-related-disorders/endophthalmitis',vascular:'https://www.nhs.uk/conditions/temporal-arteritis/',child:'https://www.nhs.uk/conditions/retinoblastoma/symptoms/'
}
// Establish safety context before duration, progression and routine history.
const priority=['concern','vision','exposure','onset','pain','contact','surgery','movement','fever','headache','nausea','vascular','neurological','age','infant-age','side','location','duration','progression','overnight','water','caregiver','diabetes','immunity','history','medicines']
questions.sort((a,b)=>priority.indexOf(a.id.replace('question.',''))-priority.indexOf(b.id.replace('question.','')))
expandEyeQuestions(questions)
questions.push(JSON.parse(readFileSync(fileURLToPath(new URL('../contracts/eye/pain-assistance.v1.json',import.meta.url)),'utf8')).description_question)
const rules=[]
sources.pain='https://www.nhs.uk/symptoms/eye-pain/'
function rule(id,level,all,any,reason,source,firstAid=null){rules.push({id:`eye.rule.${id}`,level,all,any,reason:loc(reason,`تحذير تعليمي: ${id}. راجع النص الإنكليزي الأصلي أدناه.`,`ئاگاداریی فێرکاری: ${id}. دەقی ئینگلیزی لە خوارەوە بخوێنەوە.`),source_urls:[sources[source]],first_aid:firstAid,clinical_review_status:'draft',version})}
rule('chemical','emergency',{exposure:'chemical'},null,'A chemical splash can damage the eye and needs immediate first aid and emergency assessment.','injuries',loc('Start rinsing now with plenty of clean, lukewarm water for at least 20 minutes. Hold the eyelids open and use a gentle flow. Keep rinsing while help is arranged. Do not add other chemicals.','ابدأ غسل العين هسه بمي نظيف فاتر وبكمية كبيرة لمدة لا تقل عن 20 دقيقة. افتح الجفون وخلي تدفق المي لطيف. استمر بالغسل لحد ترتيب المساعدة. لا تضيف مواد كيميائية ثانية.','ئێستا دەست بە شۆردن بکە بە ئاوی پاکی نیمگەرم بۆ لانیکەم ٢٠ خولەک. پلکەکان بکەرەوە و ئاوی هێواش بەکاربهێنە. تا ڕێکخستنی یارمەتی بەردەوام بە. ماددەی کیمیایی تر زیاد مەکە.'))
rule('penetrating','emergency',null,{exposure:['penetrating','high-speed']},'A penetrating object or high-speed impact needs emergency assessment. Do not remove an embedded object or press on the eye.','injuries')
rule('sudden-vision-loss','emergency',{onset:'sudden',vision:'loss'},null,'Sudden loss of vision is an emergency even when there is no pain.','vision')
rule('sudden-severe-pain','emergency',{onset:'sudden',pain_gte:7},null,'Sudden severe eye pain needs emergency assessment.','vision')
rule('curtain','emergency',{symptom:'curtain'},null,'A new curtain or shadow may reflect a sight-threatening retinal problem and needs immediate eye assessment.','flashes')
rule('new-flashes-floaters','urgent',null,{symptoms:['flashes','floaters']},'New or increasing flashes or floaters need urgent eye assessment without waiting for this interview. Chronic unchanged symptoms still need clinical context.','flashes')
rule('contact-vision','emergency',{contact_lenses:'yes',visual:true}, {symptoms:['pain','redness']},'A painful or red eye with contact lens use and changed vision needs emergency eye assessment.','red')
rule('contact-red-pain','urgent',{contact_lenses:'yes'},{symptoms:['pain','redness']},'Contact lens use with a painful or red eye needs urgent assessment; stop wearing the lenses.','red')
rule('red-headache-nausea','emergency',{symptom:'redness',severe_headache:'yes',nausea:'yes'},null,'A red eye with severe headache and nausea needs emergency assessment.','red')
rule('pupil-neurology','emergency',{symptom:'unequal-pupils'},{visual:true,neurological:'yes'},'A new pupil abnormality with visual or neurological changes needs emergency assessment.','red')
rule('neurological','emergency',{neurological:'yes'},null,'New neurological symptoms accompanying an eye concern need emergency assessment.','vision')
rule('orbital','emergency',{symptom:'swelling'},{movement_pain:'yes',symptoms:['protrusion'],visual:true},'Swelling with painful or restricted movement, protrusion or changed vision needs emergency assessment. Fever is not required.','orbit')
rule('postoperative','emergency',{recent_procedure:'yes'},{pain_gte:7,visual:true},'Severe eye pain or changed vision after a recent eye procedure needs emergency assessment.','postop')
rule('vascular','urgent',{visual:true},{jaw_scalp:'yes',severe_headache:'yes'},'Visual symptoms with a new headache, jaw pain or scalp tenderness need urgent same-day assessment for a potentially serious vascular cause, especially after age 50.','vascular')
rule('white-pupil','urgent',{symptom:'white-pupil'},null,'A white pupil or reflection, particularly in a child, needs prompt urgent clinical assessment. It is a finding, not a diagnosis.','child')
rule('newborn-red-sticky','urgent',{newborn:true},{symptoms:['redness','discharge']},'A newborn with a red or sticky eye needs urgent clinical assessment.','red')
rule('unexplained-vision-loss','urgent',{vision:'loss'},null,'Loss of vision requires clinical assessment; missing onset information does not make it safe.','vision')
rule('severe-eye-pain','urgent',{pain_gte:7},null,'Severe eye pain needs urgent same-day assessment even when the onset is unknown or gradual. Sudden severe pain remains an emergency.','pain')
const reasonTranslations={
 'severe-eye-pain':['ألم العين الشديد يحتاج فحص عاجل بنفس اليوم حتى إذا البداية مو معروفة أو تدريجية. الألم الشديد المفاجئ يبقى طارئ.','ئازاری توندی چاو پشکنینی پەلەیی هەمان ڕۆژ دەوێت تەنانەت ئەگەر دەستپێک نادیار یان وردەوردە بێت. ئازاری توندی لەناکاو هێشتا فریاکەوتنە.'],
 chemical:['التعرض الكيميائي ممكن يضر العين ويحتاج إسعاف أولي فوري وفحص طارئ.','بەرکەوتنی کیمیایی دەکرێت چاو زیانمەند بکات و یارمەتیی سەرەتایی دەستبەجێ و فریاکەوتن دەوێت.'],
 penetrating:['جسم نافذ أو ضربة سريعة يحتاج فحص طارئ. لا تزيل جسم مغروس ولا تضغط على العين.','تەنێکی چووەناو یان زەبری خێرا پشکنینی فریاکەوتن دەوێت. تەنێکی چەسپاو دەر مەهێنە و فشار لە چاو مەکە.'],
 'sudden-vision-loss':['فقدان النظر المفاجئ طارئ حتى إذا ماكو ألم.','لەدەستدانی لەناکاوی بینین فریاکەوتنە تەنانەت ئەگەر ئازار نەبێت.'],
 'sudden-severe-pain':['ألم العين الشديد والمفاجئ يحتاج فحص طارئ.','ئازاری توند و لەناکاوی چاو پشکنینی فریاکەوتن دەوێت.'],
 curtain:['ستار أو ظل جديد ممكن يدل على مشكلة خطرة بالشبكية ويحتاج فحص فوري.','پەردە یان سێبەری نوێ دەکرێت نیشانەی کێشەی مەترسیداری تۆڕینە بێت و پشکنینی دەستبەجێ دەوێت.'],
 'new-flashes-floaters':['ومضات أو عوائم جديدة أو متزايدة تحتاج فحص عاجل بدون انتظار المحادثة. الأعراض القديمة الثابتة هم تحتاج سياق طبي.','بروسکە یان خاڵی جووڵاوی نوێ یان زیادبوو پشکنینی پەلەیی دەوێت بەبێ چاوەڕێی گفتوگۆ. نیشانەی کۆن و نەگۆڕاویش پێویستی بە زانیاریی پزیشکی هەیە.'],
 'contact-vision':['ألم أو احمرار مع عدسات لاصقة وتغير نظر يحتاج فحص عين طارئ.','ئازار یان سووربوون لەگەڵ لێنزی چەسپاو و گۆڕانی بینین پشکنینی فریاکەوتنی چاو دەوێت.'],
 'contact-red-pain':['عدسات لاصقة مع ألم أو احمرار تحتاج فحص عاجل؛ أوقف لبس العدسات.','لێنزی چەسپاو لەگەڵ ئازار یان سووربوون پشکنینی پەلەیی دەوێت؛ لێنزەکان مەپۆشە.'],
 'red-headache-nausea':['احمرار العين مع صداع شديد وغثيان يحتاج فحص طارئ.','سووربوونی چاو لەگەڵ سەرئێشەی توند و دڵتێکچوون پشکنینی فریاکەوتن دەوێت.'],
 'pupil-neurology':['تغير جديد بالبؤبؤ مع تغير نظر أو أعراض عصبية يحتاج فحص طارئ.','گۆڕانی نوێی بیلبیلە لەگەڵ گۆڕانی بینین یان نیشانەی دەمارەیی پشکنینی فریاکەوتن دەوێت.'],
 neurological:['أعراض عصبية جديدة مع مشكلة العين تحتاج فحص طارئ.','نیشانەی دەمارەیی نوێ لەگەڵ کێشەی چاو پشکنینی فریاکەوتن دەوێت.'],
 orbital:['تورم مع ألم أو تقييد حركة العين أو جحوظ أو تغير نظر يحتاج طوارئ؛ مو شرط تكون أكو حرارة.','ئاوسان لەگەڵ ئازار یان سنوورداربوونی جووڵە، هاتنەدەرەوەی چاو یان گۆڕانی بینین فریاکەوتن دەوێت؛ تا بوونی مەرج نییە.'],
 postoperative:['ألم شديد أو تغير نظر بعد إجراء عين حديث يحتاج فحص طارئ.','ئازاری توند یان گۆڕانی بینین دوای کرداری نوێی چاو پشکنینی فریاکەوتن دەوێت.'],
 vascular:['تغير نظر مع صداع جديد أو ألم فك أو فروة الرأس يحتاج فحص عاجل اليوم، خصوصاً بعد عمر 50.','گۆڕانی بینین لەگەڵ سەرئێشەی نوێ یان ئازاری چەناگە یان پێستی سەر پشکنینی پەلەیی ئەمڕۆ دەوێت، بەتایبەتی دوای تەمەنی ٥٠.'],
 'white-pupil':['بؤبؤ أو انعكاس أبيض، خصوصاً بالطفل، يحتاج فحص عاجل. هو علامة مو تشخيص.','بیلبیلە یان ڕەنگدانەوەی سپی، بەتایبەتی لە منداڵ، پشکنینی پەلەیی دەوێت. ئەمە نیشانەیە نەک دەستنیشانکردن.'],
 'newborn-red-sticky':['احمرار أو إفراز لزج بعين مولود جديد يحتاج فحص طبي عاجل.','سووربوون یان شلەی لەزجی چاوی تازەلەدایکبوو پشکنینی پەلەیی پزیشکی دەوێت.'],
 'unexplained-vision-loss':['فقدان النظر يحتاج فحص؛ عدم معرفة وقت البداية ما يعني الأمان.','لەدەستدانی بینین پشکنین دەوێت؛ نەزانینی کاتی دەستپێک واتای سەلامەتی نییە.']
}
for(const rule of rules){const [ar,ckb]=reasonTranslations[rule.id.replace('eye.rule.','')];rule.reason=loc(rule.reason.en,ar,ckb)}
const lexical=[
 ['vision','loss','(?:cannot see|can.t see|lost (?:my |all |the )?(?:sight|vision)|(?:vision|sight) (?:loss|gone)|loss of (?:vision|sight)|فقدان (?:النظر|البصر)|ما اشوف|لەدەستدانی بینین)'],
 ['vision','blurred','(?:blurred? (?:vision|sight)|blurry|reduced (?:vision|sight)|غشاوة|تشوش النظر|تەماوی)'],['vision','double','(?:double vision|seeing double|ازدواج|دووانبینین)'],
 ['onset','sudden','(?:sudden(?:ly)?|all of a sudden|just (?:lost|started)|فجأة|فجائي|لەناکاو)'],['onset','gradual','(?:gradual(?:ly)?|بالتدريج|وردەوردە)'],
 ['exposure','chemical','(?:chemical|bleach|acid|alkali|oven cleaner|مادة كيميائية|كلور|حامض|ماددەی کیمیایی)'],['exposure','penetrating','(?:penetrat|embedded|pierced|stuck (?:in|into) (?:my |the )?eye|جسم مغروس|اخترق|چەسپاو)'],['exposure','high-speed','(?:high.speed|grind(?:er|ing)|hammering|metal fragment|سرعة عالية|بە خێرایی زۆر)'],
 ['contact_lenses','yes','(?:contact lens(?:es)?|contacts|عدسات لاصقة|لێنزی چەسپاو)'],['recent_procedure','yes','(?:(?:recent|yesterday|last week|after|following).{0,32}(?:eye surgery|eye operation|eye injection|cataract surgery)|(?:eye surgery|eye injection).{0,22}(?:yesterday|recent|last week)|عملية عين|حقنة بالعين|نەشتەرگەری چاو)'],
 ['movement_pain','yes','(?:pain(?:ful)? (?:on |with |when )?(?:eye )?mov(?:ement|ing)|hurts? (?:to|when I) mov|restricted (?:eye )?movement|ألم عند تحريك|جووڵاندنی چاو ئازار)'],
 ['fever','yes','(?:fever|temperature|حمى|حرارة|تا هەیە)'],['severe_headache','yes','(?:(?:severe|new|bad|terrible) headache|صداع شديد|صداع جديد|سەرئێشەی توند)'],['nausea','yes','(?:nausea|vomit|feeling sick|غثيان|تقيؤ|ڕشانەوە)'],['jaw_scalp','yes','(?:jaw pain|scalp tender|ألم الفك|فروة الرأس|ئازاری چەناگە)'],['neurological','yes','(?:facial droop|slurred speech|new weakness|cannot speak|تدلي الوجه|صعوبة بالكلام|لاوازیی نوێ)']
].map(([field,value,pattern])=>({field,value,pattern}))
const symptomPatterns={pain:'\\b(?:pain|ache|hurts?)\\b|ألم|يوجع|ئازار',burning:'burn|حرقة|سووتان',itching:'itch|حكة|خوران',grittiness:'grit|sand|رمل|هەستی لم','foreign-body':'foreign.body|something in|جسم غريب|شتێکی نامۆ',redness:'\\bred(?:ness)?\\b|احمرار|سووربوون',watering:'water(?:ing|y)|tearing|دموع|فرمێسکی زۆر',dryness:'dry|جفاف|وشکی',discharge:'discharge|sticky|إفرازات|لەزج',crusting:'crust|قشور|توێکڵ',swelling:'swell|swollen|تورم|ئاوسان','lid-lump':'(?:lid|eyelid) lump|كتلة بالجفن|گرێ لە پلک',drooping:'droop|تدلي|داکەوتنی پلک',twitching:'twitch|رفة|لەرزینی پلک','blurred-vision':'blurr|غشاوة|تەماوی','double-vision':'double vision|seeing double|ازدواج|دووانبینین','vision-loss':'vision loss|sight loss|cannot see|lost.{0,15}(?:vision|sight)|فقدان النظر|ما اشوف|لەدەستدانی بینین',flashes:'flash|ومضات|بروسکە',floaters:'floater|عوائم|خاڵی جووڵاو',curtain:'curtain|shadow.{0,16}(?:vision|eye|sight)|ستار|ظل بالنظر|پەردە لە بینین',halos:'halo|هالات|بازنە دەوری',glare:'glare|انبهار|بریقە','light-sensitivity':'photophobia|light sensitiv|sensitive to light|حساسية للضوء|هەستیاری بە ڕووناکی','distorted-lines':'wavy|distort|متعرج|خواروخێچ','blind-spots':'blind spot|بقع عمياء|خاڵی نابینا','colour-change':'colou?r chang|تغير بالألوان|گۆڕانی ڕەنگ','night-vision':'night vision|النظر بالليل|بینینی شەو',protrusion:'protrud|bulg|جحوظ|هاتنەدەرەوەی چاو','movement-pain':'pain.{0,12}mov|ألم عند تحريك|جووڵاندنی چاو ئازار','white-pupil':'white (?:pupil|reflex|reflection|glow)|بؤبؤ أبيض|انعكاس أبيض|بیلبیلەی سپی','unequal-pupils':'unequal pupils|different.{0,12}pupil|اختلاف.{0,16}البؤبؤ|جیاوازی.{0,16}بیلبیلە'}
symptomPatterns.pain='\\b(?:pain(?:ful)?|ache|hurts?)\\b|ألم|يوجع|ئازار'
writeFileSync(fileURLToPath(new URL('../contracts/eye/interview.v1.json',import.meta.url)),JSON.stringify({version,clinical_review_status:'draft',clinical_use_available:false,symptoms,locations,questions,rules,lexical,symptom_patterns:symptomPatterns,negation_pattern:'(?:no|not|without|never|denies|don.t|do not|لا|ما عندي|بدون|نییە|نەخێر)\\s+(?:\\w+\\s+){0,3}$',actions:{emergency:loc('Seek emergency assessment now at the nearest emergency department or emergency eye service. Ask someone to take you; do not drive with affected vision. Use your local emergency service if you cannot travel safely.','راجع هسه أقرب طوارئ أو طوارئ عيون. خلي شخص يوصلك ولا تسوق إذا نظرك متأثر. اتصل بخدمة الطوارئ المحلية إذا ما تكدر توصل بأمان.','ئێستا سەردانی نزیکترین فریاکەوتن یان فریاکەوتنی چاو بکە. داوا لە کەسێک بکە بتبات؛ ئەگەر بینینت تێکچووە شۆفێری مەکە. ئەگەر بە سەلامەتی ناگەیت پەیوەندی بە فریاکەوتنی ناوخۆ بکە.'),urgent:loc('Arrange urgent eye assessment today. Do not wait to finish this interview. If urgent eye care is unavailable, attend an emergency department.','ڕتب فحص عيون عاجل اليوم. لا تنتظر تكمل المحادثة. إذا ما متوفر فحص عاجل، راجع الطوارئ.','ئەمڕۆ پشکنینی پەلەیی چاو ڕێکبخە. چاوەڕێی تەواوبوونی گفتوگۆ مەکە. ئەگەر خزمەتگوزاری پەلەیی چاو نییە، بڕۆ بۆ فریاکەوتن.'),unknown:loc('Urgency is not established. An eye professional needs to assess the cause; incomplete answers or no pain do not rule out a serious problem.','درجة الاستعجال مو محددة. لازم مختص يفحص السبب؛ نقص المعلومات أو عدم وجود ألم ما ينفي مشكلة خطيرة.','پلەی پەلە دیاری نەکراوە. پێویستە پسپۆڕی چاو هۆکارەکە بپشکنێت؛ وەڵامی ناتەواو یان نەبوونی ئازار کێشەی جدی ڕەت ناکاتەوە.')}},null,2)+'\n')
console.log(`Wrote ${symptoms.length} symptoms, ${questions.length} questions and ${rules.length} DRAFT rules.`)
