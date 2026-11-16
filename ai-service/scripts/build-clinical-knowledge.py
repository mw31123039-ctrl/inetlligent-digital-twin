"""Build contracts/clinical/symptoms.v1.json and contracts/clinical/knowledge.v1.json.

This file is the editable source of the clinical knowledge base. The JSON contracts are generated artifacts.

Rules for contributors
- Every condition feature, "argues against" feature and red flag cites a source in contracts/clinical/sources.v1.json
  and an `ev` pattern that must match exactly one or more sentences of that source in the ingested snapshot
  (ai-service/knowledge/clinical-snapshot.json). `tests/test_clinical_knowledge.py` fails if a binding breaks,
  so a changed source page forces review instead of silently drifting.
- Weights are qualitative (typical/common/possible). They order questions and explanations; they are NOT
  calibrated probabilities and must never be shown as percentages.
- Arabic (`ar`) and Sorani Kurdish (`ckb`) text is a draft pending native medical-language review.

Run from the repository root:  python ai-service/scripts/build-clinical-knowledge.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def L(en, ar, ckb):
    return {'en': en, 'ar': ar, 'ckb': ckb}


# =====================================================================================================
# Symptom concepts. terms: regex per language (matched on normalised text; Arabic-script patterns are
# substring matches because prefixes/suffixes attach to words). evidence is not needed here: bindings live
# on the conditions and red flags that use a symptom.
# =====================================================================================================
SYMPTOMS = []


def symptom(identifier, label, en, ar, ckb, *, scope=None, implies=None, kind='symptom', group='general'):
    SYMPTOMS.append({'id': identifier, 'label': label, 'kind': kind, 'group': group, 'scope': scope or [], 'implies_anatomy': implies,
                     'terms': {'en': en, 'ar': ar, 'ckb': ckb}})


symptom('pain', L('Pain or soreness', 'ألم', 'ئازار'),
        [r'\b(pain|painful|hurts?|hurting|ache|aches|aching|achy|sore|soreness|tender)\b'],
        ['ألم', 'الم ', 'آلام', 'وجع', 'يوجع', 'توجع', 'يؤلم', 'تؤلم', 'موجوع'], ['ئازار', 'ئێش', 'ژان', 'دێشێ', 'دەیەشێ', 'دەئێشێ'])
symptom('headache', L('Headache', 'صداع', 'سەرئێشە'),
        [r'\bhead ?aches?\b', r'\bmy head (hurts|is pounding|aches|is killing me)\b'],
        ['صداع', 'وجع راس', 'وجع رأس', 'ألم في الرأس', 'الم في الراس', 'راسي يوجع', 'رأسي يؤلم'], ['سەرئێشە', 'سەر ئێشە', 'ژانەسەر', 'سەرم دێشێ', 'سەرم دەیەشێ'],
        implies='body.head', group='head')
symptom('fever', L('High temperature (fever)', 'حرارة مرتفعة (حمى)', 'پلەی گەرمی بەرز (تا)'),
        [r'\b(fever|feverish|high temperature|temperature of 3[89]|hot and cold|shivery|shivering|chills)\b'],
        ['حمى', 'حمّى', 'حرارة', 'سخونة', 'سخونيه', 'رجفة'], ['تام هەیە', 'تای هەیە', 'تاو لەرز', 'گەرمی لەش', 'پلەی گەرمی', 'لەرز'])
symptom('nausea', L('Feeling sick (nausea)', 'غثيان', 'هێڵنج'),
        [r'\b(nause\w*|feel(ing)? sick|queasy)\b'], ['غثيان', 'لعيان', 'نفسي تلعب', 'دوار المعدة'], ['هێڵنج', 'دڵتێکچوون', 'دڵم تێکدەچێ'])
symptom('vomiting', L('Vomiting', 'تقيؤ', 'ڕشانەوە'),
        [r'\b(vomit\w*|being sick|throwing up|threw up|thrown up)\b'], ['استفراغ', 'تقيؤ', 'تقيّؤ', 'ترجيع', 'قيء', 'أستفرغ', 'استفرغ', 'يزوع', 'زواع'],
        ['ڕشانەوە', 'دەڕشێمەوە', 'ڕشامەوە'])
symptom('shortness_of_breath', L('Shortness of breath', 'ضيق في التنفس', 'هەناسەتەنگی'),
        [r'\b(short(ness)? of breath|breathless\w*|out of breath|difficulty breathing|hard to breathe|trouble breathing|wheez\w*)\b'],
        ['ضيق تنفس', 'ضيق النفس', 'ضيق في التنفس', 'ضيق بالتنفس', 'صعوبة في التنفس', 'صعوبة التنفس', 'نهجان', 'لهاث', 'صفير'],
        ['هەناسەتەنگی', 'هەناسە تەنگی', 'هەناسەدان قورس', 'هەناسەم سوار'], group='chest')
symptom('breathing_severe', L('Severe difficulty breathing', 'صعوبة شديدة في التنفس', 'هەناسەدانی زۆر قورس'),
        [r"\b(can'?t breathe|cannot breathe|unable to breathe|struggling to breathe|gasping|choking)\b"],
        ['ما اكدر اتنفس', 'ما أكدر أتنفس', 'لا أستطيع التنفس', 'لا استطيع التنفس', 'اختناق', 'أختنق', 'اختنق'],
        ['ناتوانم هەناسە بدەم', 'خنکان', 'دەخنکێم'], group='chest')
symptom('chest_pain', L('Chest pain or pressure', 'ألم أو ضغط في الصدر', 'ئازار یان گوشاری سنگ'),
        [r'\bchest (pain|pressure|tightness|discomfort|hurts?|is tight|feels (tight|heavy))\b', r'\b(pain|pressure|tightness|heaviness|discomfort|ache)\b.{0,12}\bin (my |the )?chest\b', r'\bmy chest (hurts|is tight|feels tight|feels heavy)\b'],
        ['(ألم|الم|وجع|ضغط|ثقل|ضيق).{0,15}(الصدر|صدري|بالصدر)', 'ألم في الصدر', 'الم في الصدر', 'ألم بالصدر', 'وجع صدر', 'وجع بالصدر', 'وجع في الصدر', 'صدري يوجع', 'ضيق في الصدر', 'ثقل في الصدر', 'ضغط على الصدر'],
        ['(ئازار|ژان|گوشار|قورسی|تەنگی).{0,18}سنگ', 'سنگم.{0,12}(دێشێ|دەیەشێ|قورسە|تەنگە|گوشار)', 'ئازاری سنگ', 'ژانی سنگ'], implies='body.chest', group='chest')
symptom('radiating_pain', L('Pain spreading to the arm, jaw, neck or back', 'ألم ينتشر إلى الذراع أو الفك أو الرقبة أو الظهر', 'ئازار بڵاو دەبێتەوە بۆ باڵ، شەویلگە، مل یان پشت'),
        [r'\b(spread\w*|radiat\w*|goes|going|moves|moving|shoot\w*|travel\w*)\b.{0,15}\b(to|into|towards?|up)\b.{0,12}\b(arm|arms|jaw|neck|back|shoulder)\b(?!\s+of\s+(my|the)\s+(left |right )?(leg|thigh|knee|foot|calf))'],
        ['ينتشر.{0,20}(الذراع|ذراعي|الفك|فكي|الرقبة|رقبتي|الكتف|كتفي|ايدي|إيدي|الظهر)', 'يمتد.{0,20}(الذراع|الفك|الرقبة|الكتف|الظهر)', 'ينزل.{0,15}(ايدي|إيدي|ذراعي)'],
        ['بڵاو دەبێتەوە.{0,20}(باڵ|شەویلگە|مل|شان|دەست|پشت)', 'دەچێتە.{0,10}(باڵ|شەویلگە|مل|شان|دەست)'], group='chest')
symptom('sweating', L('Sweating or clammy skin', 'تعرّق', 'ئارەقکردنەوە'),
        [r'\b(sweat\w*|clammy)\b'], ['تعرق', 'تعرّق', 'عرق بارد', 'يعرق', 'أعرق', 'اعرق'], ['ئارەق'])
symptom('palpitations', L('Racing, pounding or fluttering heartbeat', 'خفقان', 'دڵەکوتێ'),
        [r'\b(palpitations?|racing heart|fluttering)\b', r'\bheart (is )?(racing|pounding|fluttering|thumping|beating (very |really )?fast|flutters|races|pounds|skips)\b'],
        ['خفقان', 'قلبي يدق', 'دقات القلب', 'دقات قلب سريعة', 'نبض سريع', 'ضربات القلب'], ['دڵەکوتێ', 'دڵەکوتە', 'لێدانی خێرای دڵ', 'دڵم خێرا لێدەدات', 'دڵم توند لێدەدات'], group='chest')
symptom('cough', L('Cough', 'سعال', 'کۆکە'), [r'\bcough\w*\b'], ['سعال', 'كحة', 'كحه', 'گحة', 'قحة', 'أكح', 'اكح', 'يكح'], ['کۆکە', 'دەکۆکم'], group='chest')
symptom('coughing_blood', L('Coughing up blood', 'سعال مع دم', 'کۆکەی خوێناوی'),
        [r'\bcough\w* (up )?blood\b', r'\bblood(y)? (in )?(my )?(phlegm|sputum|mucus)\b'], ['سعال دموي', 'دم مع السعال', 'اكح دم', 'أكح دم', 'بلغم فيه دم', 'بلغم بيه دم'],
        ['کۆکەی خوێناوی', 'خوێن لەگەڵ کۆکە', 'بە کۆکە خوێن'], group='chest')
symptom('faint', L('Fainting or passing out', 'إغماء', 'بووران'),
        [r'\b(faint\w*|passed out|pass out|blacked out|black out|collaps\w*|lost consciousness)\b'], ['إغماء', 'اغماء', 'أغمي', 'اغمى', 'غشي', 'غشيان', 'فقدان الوعي', 'فقدت الوعي'],
        ['بووران', 'بوورامەوە', 'لە هۆش چووم', 'بێهۆش'])
symptom('confusion', L('New confusion or drowsiness', 'تشوش ذهني أو نعاس جديد', 'سەرلێشێواوی یان خەواڵوویی نوێ'),
        [r'\b(confus\w*|disorient\w*|drowsy)\b'], ['ارتباك', 'تشوش ذهني', 'مشوش', 'نعاس شديد', 'مو صاحي'], ['سەرلێشێواو', 'خەواڵوو', 'تێکچوونی هۆش'])
symptom('face_droop', L('Face drooping on one side', 'تدلّي جانب من الوجه', 'لاربوونی لایەکی دەموچاو'),
        [r'\b(face|mouth|smile) (is )?(droop\w*|fall\w*|drop\w*|lopsided)\b', r'\bdroop\w* (face|mouth)\b'], ['ميلان الوجه', 'ارتخاء الوجه', 'تدلي الوجه', 'فمي مايل', 'وجهي مايل', 'وجهي معوج'],
        ['لاربوونی دەموچاو', 'دەموچاوم لار', 'دەمم لار'], group='neuro')
symptom('speech_problem', L('Slurred or difficult speech', 'كلام متلعثم أو صعب', 'قسەکردنی تێکچوو یان قورس'),
        [r"\b(slurr\w*|trouble speaking|difficulty speaking|hard to speak|can'?t speak|cannot speak|can'?t get (my )?words out)\b", r'\bspeech (is )?(slurred|strange|difficult)\b'],
        ['تلعثم', 'ثقل في اللسان', 'ثقل باللسان', 'صعوبة في الكلام', 'صعوبة الكلام', 'ما اكدر احچي', 'ما أكدر أحچي', 'لا أستطيع الكلام', 'كلامي ثقيل'],
        ['قسەکردنم قورس', 'زمانم گیرا', 'زمانم قورس', 'ناتوانم قسە بکەم'], group='neuro')
symptom('weakness', L('Weakness', 'ضعف', 'لاوازی'),
        [r'\b(weak|weakness)\b', r"\b(can'?t|cannot) (lift|move|grip|raise)\b"], ['ضعف', 'ضعيف', 'ما اكدر ارفع', 'ما أكدر أحرك', 'لا أستطيع تحريك', 'ثقل في يدي', 'ثقل في رجلي'],
        ['لاوازی', 'بێهێزی', 'بێهێز', 'ناتوانم بەرزی بکەمەوە', 'ناتوانم بیجوڵێنم'], group='neuro')
symptom('numbness_tingling', L('Numbness or tingling', 'خدر أو تنميل', 'سڕبوون یان مێروولە'),
        [r'\b(numb\w*|tingl\w*|pins and needles|loss of feeling|no feeling)\b'], ['تنميل', 'خدر', 'خدران', 'نمنمة', 'تخدير', 'فقدان الإحساس', 'فقدان الاحساس'],
        ['سڕبوون', 'سڕ بووە', 'سڕە', 'مێروولە', 'هەستی نەماوە'], group='neuro')
symptom('swelling', L('Swelling', 'تورّم', 'ئاوسان'),
        [r'\b(swell\w*|swollen|puffy|puffiness)\b'], ['تورم', 'تورّم', 'متورم', 'منتفخ', 'ورم', 'وارم'], ['ئاوسان', 'ئاوساو', 'هەڵئاوساو', 'پەنەمان'])
symptom('redness', L('Redness', 'احمرار', 'سووربوونەوە'),
        [r'\b(red|redness|reddish|bloodshot|pink eye|inflamed)\b'], ['احمرار', 'حمرة', 'أحمر', 'احمر', 'محمر', 'محمرة', 'حمراء'], ['سوور', 'سووربوونەوە', 'سووربۆتەوە'])
symptom('itch', L('Itching', 'حكّة', 'خوران'), [r'\bitch\w*\b'], ['حكة', 'حكه', 'يحك', 'يحكني', 'تحكني', 'تحك'], ['خوران', 'دەخورێ', 'خورشت'])
symptom('discharge', L('Discharge or pus', 'إفرازات أو قيح', 'دەردراو یان کێم'),
        [r'\b(discharge|pus|sticky|gunk|oozing|mucus)\b'], ['إفرازات', 'افرازات', 'إفراز', 'قيح', 'صديد', 'رمص', 'عماص', 'لزج', 'مخاط'], ['کێم', 'چڵک', 'دەردراو', 'لینج'])
symptom('watery_eyes', L('Watery eyes', 'دموع زائدة', 'فرمێسکڕشتن'),
        [r'\b(watery|watering|teary|tearing up)\b'], ['دموع', 'تدمع', 'تدميع', 'دمعان'], ['فرمێسک', 'ئاو دەڕێژێ', 'ئاوی لێدێت'], scope=['body.eyes'], implies='body.eyes', group='eye')
symptom('eye_dryness_grit', L('Dry, gritty or burning eyes', 'جفاف أو حرقة أو إحساس بالرمل في العين', 'وشکی، سووتان یان هەستی لم لە چاو'),
        [r'\b(dry|dryness|gritty|sandy|scratchy|burning|stinging)\b', r'\bsomething in my eye\b'], ['جفاف', 'ناشفة', 'جافة', 'رمل', 'حرقان', 'حرقة', 'كأن شي بعيني', 'لسع'],
        ['وشکی', 'وشکە', 'سووتان', 'دەسووتێ', 'هەستی لم'], scope=['body.eyes'], implies='body.eyes', group='eye')
symptom('blurred_vision', L('Blurred or changed vision', 'رؤية ضبابية أو متغيرة', 'بینینی لێڵ یان گۆڕاو'),
        [r'\b(blur\w*|blurry|cloudy vision|hazy vision|fuzzy vision|wavy lines|distorted)\b', r"\b(can'?t|cannot) see (clearly|properly|well)\b", r'\bvision (is )?(worse|changed|different|cloudy|getting worse)\b'],
        ['رؤية ضبابية', 'ضبابية', 'تشوش الرؤية', 'تشوش في الرؤية', 'زغللة', 'غباش', 'غشاوة', 'نظري ضعف', 'ما أشوف زين', 'ما اشوف زين'],
        ['لێڵ', 'تەماوی', 'بینینم کز', 'باش نابینم', 'چاوم لێڵ'], implies='body.eyes', group='eye')
symptom('vision_loss', L('Loss of vision', 'فقدان البصر', 'لەدەستدانی بینین'),
        [r"\b(lost (my |the )?(vision|sight)|loss of (vision|sight)|went blind|gone blind|blindness|no vision)\b", r"\b(can'?t|cannot) see\b(?! (clearly|properly|well))"],
        ['فقدان البصر', 'فقدت النظر', 'فقدت البصر', 'ما اشوف(?! زين)', 'ما أشوف(?! زين)', 'لا أرى', 'عمى', 'انطفى نظري'],
        ['بینینم نەما', 'ناتوانم ببینم', 'کوێر بووم', 'هیچ نابینم'], implies='body.eyes', group='eye')
symptom('curtain_shadow', L('A dark curtain or shadow over vision', 'ستارة أو ظل داكن على الرؤية', 'پەردە یان سێبەرێکی تاریک بەسەر بینیندا'),
        [r'\b(curtain|shadow|veil)\b'], ['ستارة', 'ظل', 'غشاء أسود'], ['پەردە', 'سێبەر'], scope=['body.eyes'], implies='body.eyes', group='eye')
symptom('flashes_floaters', L('Flashes or floaters', 'ومضات أو أجسام عائمة', 'بریسکە یان پەڵەی سەرچاو'),
        [r'\b(flash\w*|floater\w*|cobweb\w*|squiggl\w*)\b', r'\b(dots|spots|specks)\b.{0,25}\b(in|across|through) (my )?(vision|sight)\b', r'\bfloating (dots|spots|specks)\b'], ['ومضات', 'ومضة', 'برق', 'ذباب طائر', 'أجسام عائمة', 'نقاط سوداء', 'خيوط سوداء'],
        ['بریسکە', 'پەڵەی ڕەش', 'مێشی فڕیو', 'تیشکی ڕووناکی'], scope=['body.eyes'], implies='body.eyes', group='eye')
symptom('light_sensitivity', L('Light sensitivity', 'حساسية للضوء', 'هەستیاری بە ڕووناکی'),
        [r'\b(light sensitiv\w*|sensitiv\w* to (the )?(bright )?light|photophobia)\b', r'\b(light|bright lights?) (hurts?|bothers?)\b', r'\bhurts to look at (the )?light\b'],
        ['حساسية للضوء', 'حساسية من الضوء', 'الضوء يزعج', 'الضوء يؤلم', 'ما أتحمل الضوء', 'ما اتحمل الضوء'], ['هەستیاری بە ڕووناکی', 'ڕووناکی ئازارم دەدات', 'ڕووناکی بێزارم دەکات'], group='eye')
symptom('double_vision', L('Double vision', 'ازدواج الرؤية', 'دووانەبینی'),
        [r'\b(double vision|seeing double|see double)\b'], ['ازدواج الرؤية', 'رؤية مزدوجة', 'أشوف شيئين', 'اشوف شيئين', 'أشوف دبل', 'اشوف دبل'], ['دووانەبینی', 'دووانە دەبینم', 'دوو دەبینم'],
        implies='body.eyes', group='eye')
symptom('halos', L('Rainbow rings around lights', 'هالات ملوّنة حول الأضواء', 'بازنەی ڕەنگاوڕەنگ لە دەوری ڕووناکی'),
        [r'\b(halos?|rainbow\w*)\b'], ['هالات', 'هالة', 'ألوان حول الضوء'], ['بازنەی ڕەنگاوڕەنگ', 'ئەڵقەی ڕەنگاوڕەنگ'], scope=['body.eyes'], group='eye')
symptom('eyelid_lump', L('Lump on the eyelid', 'كتلة على الجفن', 'گرێ لەسەر پێڵوو'),
        [r'\b(lump|bump|spot|swelling)\b.{0,22}\b(eye)?lids?\b', r'\beyelid (lump|bump)\b', r'\bstye\b'], ['شحاذ', 'شحاذة', 'جليجل', 'كتلة في الجفن', 'حبة بالجفن', 'حبة على الجفن', 'دملة بالجفن'],
        ['گرێی پێڵوو', 'گرێ لە پێڵوو', 'دەنکە لە پلک', 'دانەوێڵە'], scope=['body.eyes'], implies='eye.upper-eyelid', group='eye')
symptom('eyelid_crusting', L('Crusts or flakes on the eyelids', 'قشور على الجفون', 'توێکڵ لەسەر پێڵوو'),
        [r'\b(crust\w*|flak\w*)\b', r'\b(eye)?lids? (are )?stick\w*\b'], ['قشور', 'قشرة', 'الجفون ملتصقة', 'جفوني تلتصق'], ['توێکڵ', 'پێڵووەکانم دەنووسێن'], scope=['body.eyes'], group='eye')
symptom('uneven_pupils', L('One pupil larger than the other', 'بؤبؤ أكبر من الآخر', 'بیلبیلەیەک گەورەترە'),
        [r'\bpupils? (are |is )?(different|uneven|unequal)\b', r'\bone pupil (is )?(bigger|larger)\b'], ['بؤبؤ أكبر', 'حدقة غير متساوية', 'البؤبؤ مو متساوي'], ['بیلبیلەی چاو جیاوازە', 'بیلبیلەیەک گەورەترە'],
        scope=['body.eyes'], group='eye')
symptom('contact_lens', L('Wears contact lenses', 'يستخدم عدسات لاصقة', 'لێنزی چاو بەکاردەهێنێت'),
        [r'\bcontact lens\w*\b', r'\b(wear|use) contacts\b'], ['عدسات لاصقة', 'عدسة لاصقة', 'لينزات', 'لنزات'], ['لێنز', 'عەدەسەی لکاو'], kind='risk_factor', group='eye')
symptom('screen_use', L('Long periods of screen use', 'استخدام الشاشات لفترات طويلة', 'بەکارهێنانی شاشە بۆ ماوەی درێژ'),
        [r'\b(screens?|computer|phone|laptop|reading)\b'], ['شاشة', 'الشاشة', 'الكمبيوتر', 'الموبايل', 'الحاسوب', 'القراءة'], ['شاشە', 'کۆمپیوتەر', 'مۆبایل', 'خوێندنەوە'], kind='risk_factor', group='eye')
symptom('injury', L('Injury, fall or blow', 'إصابة أو سقوط أو ضربة', 'برین، کەوتن یان زەبر'),
        [r'\b(injur\w*|fell|fall|fallen|accident|twist\w*|sprain\w*|blow to|crash|got hit|was hit|hit my)\b'], ['إصابة', 'اصابة', 'سقطت', 'وقعت', 'طحت', 'حادث', 'التواء', 'التوى', 'ضربة', 'انضربت'],
        ['کەوتم', 'کەوتمە', 'زەبر', 'ڕووداو', 'بادان', 'بادرا', 'بریندار'])
symptom('chemical_exposure', L('Chemical splash or exposure', 'تعرّض لمادة كيميائية', 'بەرکەوتنی ماددەی کیمیایی'),
        [r'\b(chemical|bleach|acid|alkali|cleaning product|splash\w*)\b'], ['مادة كيميائية', 'مواد كيميائية', 'كلور', 'قاصر', 'حامض', 'أسيد', 'تيزاب'], ['ماددەی کیمیایی', 'کلۆر', 'ترشەڵۆک'])
symptom('toothache', L('Toothache', 'ألم الأسنان', 'ددانئێشە'),
        [r'\btooth ?ache\b', r'\b(tooth|teeth|molar) (pain|hurts?|aches?)\b', r'\bpain in (my |a |the )?(tooth|teeth|molar|gum)\b'],
        ['ألم الأسنان', 'ألم في السن', 'ألم في الضرس', 'الم في الضرس', 'وجع سن', 'وجع ضرس', 'وجع أسنان', 'وجع اسنان', 'سني يوجع', 'ضرسي يوجع', 'ضرس يوجع'],
        ['ددانئێشە', 'ددان ئێشە', 'ئازاری ددان', 'ددانم دێشێ', 'ددانم دەیەشێ', 'کاکیلەم دێشێ'], implies='mouth.teeth', group='dental')
symptom('tooth_sensitivity', L('Sensitivity to hot, cold or sweet', 'حساسية للحار أو البارد أو الحلو', 'هەستیاری بە گەرم، سارد یان شیرین'),
        [r'\bsensitiv\w* (to )?(hot|cold|sweet)\b', r'\b(hot|cold|sweet) (food|drinks?|things?) (hurts?|causes? pain|makes? it hurt)\b', r'\bsensitive (teeth|tooth)\b'],
        ['حساسية الأسنان', 'حساسية للبارد', 'حساسية للحار', 'يوجع مع البارد', 'البارد يوجع', 'الحار يوجع'], ['هەستیاری ددان', 'هەستیارە بە سارد', 'سارد دەیئێشێنێ'], group='dental')
symptom('pain_on_biting', L('Pain when biting or chewing', 'ألم عند العض أو المضغ', 'ئازار لە کاتی گەستن یان جووین'),
        [r'\b(pain|hurts?) (when|while|on) (biting|chewing|i bite|i chew|eating)\b', r'\bbite down\b'], ['ألم عند العض', 'ألم عند المضغ', 'يوجع لما أعض', 'يوجع لما اعض', 'يوجع وكت المضغ'],
        ['ئازار لە کاتی جووین', 'کە دەیجووم دێشێ', 'کە دەگەزم دێشێ'], group='dental')
symptom('gum_bleeding', L('Bleeding gums', 'نزيف اللثة', 'خوێنبەربوونی پووک'),
        [r'\bgums? (bleed\w*|are bleeding)\b', r'\bbleeding gums?\b', r'\bblood when (i )?(brush|floss)\w*\b'], ['نزيف اللثة', 'اللثة تنزف', 'لثتي تنزف', 'دم من اللثة', 'دم وكت التفريش', 'دم عند التفريش', 'دم عند تنظيف الأسنان'],
        ['خوێنبەربوونی پووک', 'پووکم خوێن', 'خوێن لە پووک'], implies='mouth.gums', group='dental')
symptom('bad_taste_breath', L('Bad taste or bad breath', 'طعم سيئ أو رائحة فم كريهة', 'تامی ناخۆش یان بۆنی ناخۆشی دەم'),
        [r'\b(bad|foul|sour|unpleasant) (taste|breath)\b', r'\bhalitosis\b'], ['رائحة كريهة', 'طعم سيء', 'طعم سيئ', 'طعم مر', 'ريحة الفم', 'نفس كريه', 'طعم حامض'], ['بۆنی ناخۆشی دەم', 'تامی ناخۆش', 'تامی ترش'], group='dental')
symptom('loose_tooth', L('Loose tooth', 'سن متحرك', 'ددانی لەق'),
        [r'\b(loose|wobbly|moving) (tooth|teeth)\b', r'\b(tooth|teeth) (is |are |feels? )?(loose|wobbly)\b'], ['سن متحرك', 'ضرس متحرك', 'أسنان متحركة', 'سني يتحرك', 'سن مخلخل'], ['ددانی لەق', 'ددانم لەقە', 'ددانەکانم دەلەقن'],
        implies='mouth.teeth', group='dental')
symptom('broken_tooth', L('Chipped, cracked or broken tooth', 'سن مكسور أو متشقق', 'ددانی شکاو یان درزبردوو'),
        [r'\b(broken|chipped|cracked|fractured) (my )?(tooth|teeth|molar)\b', r'\b(tooth|teeth) (is |got )?(broke|broken|chipped|cracked)\b'], ['سن مكسور', 'انكسر سني', 'انكسر ضرسي', 'سن مشقوق', 'ضرس مكسور'],
        ['ددانم شکا', 'ددانی شکاو', 'ددانم درزی بردووە'], implies='mouth.teeth', group='dental')
symptom('knocked_out_tooth', L('Knocked-out tooth', 'سقوط سن بسبب ضربة', 'ددانی دەرهاتوو بە زەبر'),
        [r'\bknocked (out )?(a |my |the )?(\w+ )?(tooth|teeth)( out)?\b', r'\b(tooth|teeth) (was |got )?knocked out\b'], ['سقط سني', 'طاح سني', 'طلع سني من الضربة', 'انقلع سني'], ['ددانم کەوت', 'ددانم دەرهات'],
        implies='mouth.teeth', group='dental')
symptom('mouth_ulcer', L('Mouth ulcer or sore', 'قرحة في الفم', 'برینی دەم'),
        [r'\b(ulcers?|canker)\b', r'\b(mouth|tongue|lip) sores?\b', r'\bsores? (in|inside|on) (my |the )?(mouth|tongue|lip)\b'], ['قرحة', 'تقرح', 'تقرحات', 'حبة بالفم', 'حبة في الفم', 'قلاع', 'جرح في الفم'],
        ['برینی دەم', 'برین لە دەم', 'زامی دەم', 'برینی زمان'], implies='mouth.oral-lining', group='dental')
symptom('mouth_patch', L('Red or white patch in the mouth', 'بقعة حمراء أو بيضاء في الفم', 'پەڵەی سوور یان سپی لە دەم'),
        [r'\b(white|red) (patch\w*|spots?|areas?)\b'], ['بقعة بيضاء', 'بقعة حمراء', 'بقع بيضاء', 'بقع حمراء'], ['پەڵەی سپی', 'پەڵەی سوور'], scope=['body.mouth'], group='dental')
symptom('lump', L('Lump', 'كتلة', 'گرێ'), [r'\b(lump|lumps|mass|growth|bump)\b'], ['كتلة', 'درنة', 'عقدة', 'نتوء'], ['گرێ', 'لووە', 'بەرزایی'])
symptom('swallowing_difficulty', L('Difficulty or pain swallowing', 'صعوبة أو ألم في البلع', 'قووتدانی قورس یان بە ئازار'),
        [r"\b(difficult\w* swallow\w*|hard to swallow|can'?t swallow|cannot swallow|trouble swallowing|struggling to swallow|dysphagia)\b", r'\b(pain(ful)?|hurts?) (when |on |to )?swallow\w*\b'],
        ['صعوبة البلع', 'صعوبة في البلع', 'ما اكدر ابلع', 'ما أكدر أبلع', 'لا أستطيع البلع', 'ألم عند البلع', 'يوجع لما ابلع', 'يوجع لما أبلع'],
        ['قووتدان قورس', 'ناتوانم قووت بدەم', 'ئازار لە کاتی قووتدان'])
symptom('sore_throat', L('Sore throat', 'ألم الحلق', 'گەروو ئێشە'),
        [r'\bsore throat\b', r'\bthroat (pain|hurts?|is sore|is scratchy)\b', r'\bscratchy throat\b'], ['التهاب الحلق', 'ألم الحلق', 'ألم في الحلق', 'وجع حلق', 'وجع بالحلق', 'حلقي يوجع', 'بلعومي يوجع'],
        ['گەروو ئێشە', 'قوڕگ ئێشە', 'گەرووم دێشێ', 'قوڕگم دێشێ'], implies='neck.throat', group='ent')
symptom('ear_pain', L('Earache', 'ألم الأذن', 'گوێ ئێشە'),
        [r'\bear ?aches?\b', r'\bear (pain|hurts?)\b', r'\bpain in (my |the )?ear\b'], ['ألم الأذن', 'ألم في الأذن', 'وجع اذن', 'وجع أذن', 'أذني توجع', 'اذني توجع'], ['گوێ ئێشە', 'گوێم دێشێ', 'ئازاری گوێ'],
        implies='body.ears', group='ent')
symptom('hearing_change', L('Change in hearing', 'تغير في السمع', 'گۆڕانی بیستن'),
        [r"\b(hearing (loss|change|problem)|can'?t hear|muffled|deaf\w*|ringing in)\b"], ['ضعف السمع', 'ما أسمع', 'ما اسمع', 'طنين', 'صمم'], ['کەمبوونی بیستن', 'نابیستم', 'زرینگانەوە'], group='ent')
symptom('nasal_congestion', L('Blocked or runny nose', 'انسداد أو سيلان الأنف', 'لووتگیران یان لووتی ئاوی'),
        [r'\b(blocked|stuffy|runny|congested) nose\b', r'\bnasal congestion\b'], ['انسداد الأنف', 'انسداد الانف', 'خشمي مسدود', 'رشح', 'سيلان الأنف', 'زكام'], ['لووتم گیراوە', 'لووت گیران', 'هەڵامەت', 'لووتم ئاو دەکات'],
        group='ent')
symptom('reduced_smell', L('Reduced sense of smell', 'ضعف حاسة الشم', 'کەمبوونی هەستی بۆنکردن'),
        [r"\b(loss of smell|can'?t smell|reduced (sense of )?smell)\b"], ['فقدان الشم', 'ما أشم', 'ما اشم', 'ضعف الشم'], ['بۆن ناکەم', 'هەستی بۆنکردنم نەماوە'], group='ent')
symptom('jaw_clicking', L('Jaw clicking, popping or locking', 'طقطقة أو قفل في الفك', 'تەقەتەق یان گیرانی شەویلگە'),
        [r'\b(click\w*|pop\w*|grind\w*|lock\w*)\b.{0,20}\bjaw\b', r'\bjaw\b.{0,20}\b(click\w*|pop\w*|lock\w*)\b'], ['طقطقة الفك', 'صوت في الفك', 'الفك يطق', 'قفل الفك', 'فكي يطقطق'],
        ['شەویلگەم دەتەقێ', 'دەنگی شەویلگە', 'شەویلگەم گیر دەخوات'], implies='head.jaw-joint', group='dental')
symptom('difficulty_opening_mouth', L('Difficulty opening the mouth', 'صعوبة فتح الفم', 'قورسی کردنەوەی دەم'),
        [r"\b(can'?t|cannot|difficult\w* to|hard to|trouble|struggling to) open\w* (my )?mouth\b"], ['صعوبة فتح الفم', 'ما اكدر افتح حلكي', 'ما أكدر أفتح حلكي', 'لا أستطيع فتح فمي'],
        ['ناتوانم دەمم بکەمەوە', 'دەمم ناکرێتەوە'], group='dental')
symptom('crowding', L('Crowded or crooked teeth', 'ازدحام أو اعوجاج الأسنان', 'ددانی قەرەباڵغ یان خوار'),
        [r'\b(crowd\w*|crooked|overlapping|twisted|rotated) (teeth|tooth)\b', r'\b(teeth|tooth) (are |is )?(crowded|crooked|overlapping)\b', r'\bteeth (are )?too close\b'],
        ['ازدحام الأسنان', 'أسنان متزاحمة', 'أسنان معوجة', 'اسنان عوجة', 'تراكب الأسنان', 'اسناني عوجة'], ['ددانی خوار', 'قەرەباڵغی ددان', 'ددانەکانم خوارن'], implies='mouth.bite', group='ortho')
symptom('spacing', L('Gaps between teeth', 'فراغات بين الأسنان', 'بۆشایی نێوان ددانەکان'),
        [r'\b(gaps?|spaces?|spacing|diastema)\b.{0,20}\b(teeth|tooth)\b', r'\bgap.?toothed\b'], ['فراغات بين الأسنان', 'فراغ بين الأسنان', 'تباعد الأسنان', 'فلجة'], ['بۆشایی نێوان ددان', 'ددانی لێک دوور'],
        implies='mouth.bite', group='ortho')
symptom('bite_problem', L('Bite that does not meet properly', 'عضة غير متطابقة', 'گەستنی ناڕێک'),
        [r"\b(overbite|underbite|crossbite|open bite|deep bite|buck teeth)\b", r"\bbite (is |feels )?(off|wrong|uneven)\b", r"\bteeth (don'?t|do not) meet\b", r'\b(teeth|tooth) (stick|sticks|sticking) out\b', r'\bprotruding (front )?teeth\b'],
        ['مشكلة في العضة', 'عضة غير متساوية', 'بروز الأسنان', 'أسنان بارزة', 'الأسنان ما تتطابق', 'اسنان بارزة'], ['گەستنی ناڕێک', 'ددانی پێشەوە دەرچووە', 'ددانەکان یەک ناگرنەوە'],
        implies='mouth.bite', group='ortho')
symptom('missing_tooth', L('Missing tooth', 'سن مفقود', 'ددانی ونبوو'),
        [r'\b(missing|lost) (a |one |two |some )?(tooth|teeth)\b', r'\b(tooth|teeth) (is |are )?missing\b'], ['سن مفقود', 'أسنان مفقودة', 'ناقص سن', 'سن مقلوع', 'ضرس مقلوع'], ['ددانی کەم', 'ددانێکم نیە', 'ددانی هەڵکێشراو'],
        implies='mouth.teeth', group='ortho')
symptom('braces_problem', L('Problem with braces', 'مشكلة في تقويم الأسنان', 'کێشەی ئامرازی ڕاستکردنەوەی ددان'),
        [r'\b(braces?|bracket|wire|aligner)\b.{0,30}\b(broken|loose|poking|hurt\w*|pain\w*|digging)\b'], ['التقويم مكسور', 'سلك التقويم', 'تقويم يوجع', 'التقويم يجرح'], ['تەلی ددان شکاوە', 'ئامرازی ددان ئازار دەدات'],
        group='ortho')
symptom('heartburn', L('Heartburn or acid reflux', 'حرقة أو ارتجاع حمضي', 'سووتانەوەی گەدە یان ترشێتی'),
        [r'\b(heartburn|acid reflux|reflux|indigestion|sour taste)\b', r'\bburning (in|behind) (my )?(chest|throat)\b'], ['حرقة(?! (البول|بالبول|في البول|عند التبول))', 'حموضة', 'حرقان المعدة', 'ارتجاع', 'عسر هضم', 'عسر الهضم'],
        ['ترشێتی', 'سووتانەوەی گەدە', 'سووتانەوەی سنگ', 'هەرسنەکردن'], implies='chest.oesophagus', group='gi')
symptom('bloating', L('Bloating', 'انتفاخ', 'پڕبوونی سک'), [r'\b(bloat\w*|gassy|distended)\b'], ['انتفاخ', 'نفخة', 'غازات', 'امتلاء'], ['پڕبوونی سک', 'بای سک', 'گاز'], scope=['body.abdomen'], group='gi')
symptom('constipation', L('Constipation', 'إمساك', 'قەبزی'), [r'\b(constipat\w*|hard (stools?|poo)|straining)\b', r"\b(can'?t|haven'?t|not) (had a )?poo\w*\b"], ['إمساك', 'امساك', 'قبض'], ['قەبزی', 'قەبز'], group='gi')
symptom('diarrhoea', L('Diarrhoea', 'إسهال', 'سکچوون'), [r'\b(diarrh\w*|loose (stools?|poo)|runny poo|watery (stools?|poo))\b'], ['إسهال', 'اسهال', 'إسهالات'], ['سکچوون', 'ڕیخۆڵەچوون'], group='gi')
symptom('gi_bleeding', L('Vomiting blood, black stools or blood in poo', 'تقيؤ دم أو براز أسود أو دم في البراز', 'ڕشانەوەی خوێن، پیسایی ڕەش یان خوێن لە پیسایی'),
        [r'\b(vomit\w* blood|throwing up blood|blood in (my )?(vomit|poo|stool)|black (tarry )?(stools?|poo)|bloody (diarrh\w*|stools?|poo)|rectal bleeding|bleeding from (my )?bottom)\b'],
        ['دم في البراز', 'دم بالبراز', 'براز أسود', 'خروج أسود', 'استفراغ دم', 'تقيؤ دم', 'قيء دموي'], ['خوێن لە پیسایی', 'پیسایی ڕەش', 'ڕشانەوەی خوێن'], group='gi')
symptom('pain_moves_right_lower', L('Pain moving to the lower right abdomen', 'ألم انتقل إلى أسفل يمين البطن', 'ئازار گواسترایەوە بۆ خوارەوەی لای ڕاستی سک'),
        [r'\b(mov\w*|shift\w*|went|moved)\b.{0,25}\b(lower right|right side|bottom right)\b'], ['انتقل.{0,40}(اليمين|الجهة اليمنى)', 'نزل.{0,40}(اليمين|الجهة اليمنى)'], ['گواسترایەوە.{0,40}ڕاست', 'چووە.{0,40}لای ڕاست'],
        scope=['body.abdomen'], implies='abdomen.right-lower', group='gi')
symptom('yellow_skin_eyes', L('Yellow skin or whites of the eyes', 'اصفرار الجلد أو بياض العين', 'زەردبوونی پێست یان سپێنەی چاو'),
        [r'\b(yellow (skin|eyes|whites)|jaundice\w*|skin (is |looks |turned )?yellow|eyes (are |look |turned )?yellow)\b'], ['اصفرار', 'يرقان', 'صفار', 'أبو صفار'], ['زەردوویی', 'زەردبوونی چاو', 'پێستم زەرد'], group='gi')
symptom('urinary_burning', L('Pain or burning when peeing', 'حرقة أو ألم عند التبول', 'سووتانەوە یان ئازار لە کاتی میزکردن'),
        [r'\b(burn\w*|sting\w*|pain(ful)?|hurts?) (when|while|on) (i )?(pee|urinat\w*)\b', r'\bdysuria\b'], ['حرقة البول', 'حرقة بالبول', 'حرقة عند التبول', 'ألم عند التبول', 'ألم أثناء التبول', 'يحرقني البول'],
        ['سووتانەوەی میز', 'ئازار لە کاتی میزکردن', 'میزەکەم دەسووتێنێ'], implies='abdomen.lower-central', group='urinary')
symptom('urinary_frequency', L('Needing to pee more often', 'كثرة التبول', 'زۆر میزکردن'),
        [r'\b(peeing|urinating|pee|urinate) (more|a lot|often|frequently)\b', r'\bfrequent urination\b', r'\bneed(ing)? to pee (often|all the time|urgently)\b'], ['كثرة التبول', 'تبول متكرر', 'أبول كثير', 'ابول هواية'],
        ['زۆر میز دەکەم', 'زۆر میزکردن'], group='urinary')
symptom('blood_in_urine', L('Blood in pee', 'دم في البول', 'خوێن لە میز'), [r'\b(blood in (my )?(pee|urine)|haematuria|hematuria|red urine)\b'], ['دم في البول', 'دم بالبول'], ['خوێن لە میز'], group='urinary')
symptom('stiffness', L('Stiffness', 'تيبّس', 'ڕەقی'), [r'\bstiff\w*\b'], ['تيبس', 'تيبّس', 'تصلب', 'متيبس', 'يابس'], ['ڕەقی', 'ڕەق بووە', 'ڕەقە'], group='msk')
symptom('stiff_neck', L('Stiff neck', 'تيبّس الرقبة', 'ڕەقبوونی مل'), [r'\bstiff neck\b', r'\bneck (is |feels )?stiff\b'], ['تيبس الرقبة', 'تصلب الرقبة', 'رقبتي متيبسة', 'رقبتي يابسة'],
        ['ڕەقبوونی مل', 'ملم ڕەق'], group='neuro')
symptom('rash', L('Rash', 'طفح جلدي', 'پەڵەی پێست'), [r'\b(rash\w*|hives|welts?|blotch\w*)\b'], ['طفح', 'حبوب', 'بثور', 'شرى', 'حساسية جلد'], ['پەڵەی پێست', 'زیپکە', 'خورشتی پێست', 'پەڵە'], group='skin')
symptom('non_blanching_rash', L('Rash that does not fade when pressed', 'طفح لا يختفي عند الضغط', 'پەڵەیەک کە بە گوشار ون نابێت'),
        [r"\brash (that )?(does not|doesn'?t|won'?t) fade\b", r'\bnon.?blanching\b', r'\bglass test\b'], ['طفح لا يختفي', 'طفح ما يروح بالضغط'], ['پەڵە بە گوشار ون نابێت'], group='skin')
symptom('face_lip_tongue_swelling', L('Swelling of the lips, tongue, face or throat', 'تورم الشفاه أو اللسان أو الوجه أو الحلق', 'ئاوسانی لێو، زمان، دەموچاو یان گەروو'),
        [r'\b(lips?|tongue|throat|face) (is |are |feels? |looks? )?(swell\w*|swollen|puff\w*)\b', r'\bswell\w* (of |in )?(my )?(lips?|tongue|throat|face)\b'],
        ['تورم الشفايف', 'تورم الشفاه', 'تورم اللسان', 'تورم الحلق', 'تورم الوجه', 'لساني متورم', 'شفايفي متورمة', 'وجهي متورم'],
        ['ئاوسانی لێو', 'ئاوسانی زمان', 'زمانم ئاوساوە', 'لێوم ئاوساوە', 'دەموچاوم ئاوساوە'], group='allergy')
symptom('throat_tight', L('Tight throat or struggling to swallow', 'ضيق في الحلق', 'تەنگبوونی گەروو'),
        [r'\bthroat (feels? |is )?(tight|closing)\b', r'\btight throat\b'], ['ضيق في الحلق', 'حلقي ضايق', 'الحلق يتسكر'], ['تەنگبوونی گەروو', 'گەرووم تەنگ'], group='allergy')
symptom('cramp', L('Cramp or spasm', 'شد عضلي', 'گرژبوون'), [r'\b(cramp\w*|spasm\w*)\b'], ['شد عضلي', 'تشنج عضلي', 'شدة عضلية', 'شد في'], ['گرژبوون', 'گرژی', 'ماسولکەم گرژ'], group='msk')
symptom('joint_locking', L('Joint locking or giving way', 'انقفال المفصل أو خذلانه', 'گیرانی جومگە یان چەمانەوەی لەناکاو'),
        [r'\b(locks?|locking|gives? way|giving way|buckl\w*|unstable)\b'], ['ينقفل', 'تنقفل', 'يخون', 'يرتخي فجأة'], ['گیر دەخوات', 'دەچەمێتەوە'], group='msk')
symptom('cannot_bear_weight', L('Cannot put weight on it or walk', 'لا يستطيع الوقوف أو المشي عليها', 'ناتوانێت بڕوات یان قورسایی بخاتە سەری'),
        [r"\b(can'?t|cannot|unable to) (put (any )?weight|walk|stand)\b"], ['ما اكدر امشي', 'ما أكدر أمشي', 'لا أستطيع المشي', 'ما أكدر أوكف', 'لا أستطيع الوقوف'],
        ['ناتوانم بڕۆم', 'ناتوانم پێی لێ بنێم', 'ناتوانم بوەستم'], group='msk')
symptom('deformity', L('Looks deformed or out of place', 'تشوّه أو خروج من المكان', 'شێوە گۆڕاو یان لە جێی خۆی دەرچوو'),
        [r'\b(deform\w*|out of place|changed shape|pointing the wrong way|bone (is )?(sticking|poking) out)\b'], ['تشوه', 'معوج بعد', 'العظم طالع', 'تغير شكله'], ['شێوەی گۆڕاوە', 'ئێسکەکە دەرچووە'],
        group='msk')
symptom('crack_sound', L('Heard a crack at the time of injury', 'سماع صوت طقة عند الإصابة', 'بیستنی دەنگی شکان لە کاتی برین'),
        [r'\b(heard|felt) a (crack|snap)\b'], ['سمعت صوت طقة', 'سمعت طقة', 'صوت كسر'], ['دەنگی شکان', 'دەنگی تەقە بیست'], group='msk')
symptom('saddle_bladder', L('Numbness around the genitals or new bladder/bowel control problems', 'خدر حول الأعضاء التناسلية أو مشاكل جديدة في التحكم بالبول أو البراز', 'سڕبوون لە دەوری ئەندامی زاوزێ یان کێشەی نوێی کۆنترۆڵی میز/پیسایی'),
        [r'\bnumb\w* (around|between) (my )?(genitals|bottom|anus|buttocks|groin|private)\b', r'\bsaddle (numbness|anaesthesia)\b', r"\b(can'?t|cannot) (control|hold|start) (my )?(pee|peeing|urine|bladder|bowels?|poo)\b", r'\bincontinen\w*\b'],
        ['خدر حول الأعضاء التناسلية', 'ما أسيطر على البول', 'سلس', 'ما اكدر امسك البول', 'ما أكدر أمسك البول'], ['سڕبوونی دەوری ئەندامی زاوزێ', 'ناتوانم میزەکەم بگرم'], group='neuro')
symptom('dizziness', L('Dizziness', 'دوخة', 'سەرسووڕان'), [r'\b(dizz\w*|lightheaded|light.headed|vertigo|room (is )?spinning|unsteady)\b'], ['دوخة', 'دوار', 'دايخ', 'الدنيا تدور'],
        ['سەرسووڕان', 'گێژبوون', 'گێژ', 'سەرم دەسووڕێ'], group='neuro')
symptom('seizure', L('Seizure (fit)', 'نوبة تشنج', 'فێ'), [r'\b(seizures?|convuls\w*|had a fit|having a fit)\b'], ['نوبة تشنج', 'تشنجات', 'صرع', 'اختلاج'], ['فێ', 'گرژبوونی لەش'], group='neuro')
symptom('jaw_pain_eating', L('Jaw pain when eating', 'ألم الفك عند الأكل', 'ئازاری شەویلگە لە کاتی خواردن'),
        [r'\bjaw (pain|ache|aches|hurts?) (when|while) (eating|chewing)\b'], ['ألم الفك عند الأكل', 'فكي يوجع لما آكل', 'فكي يوجع وكت الأكل'], ['ئازاری شەویلگە لە کاتی خواردن', 'کە دەخۆم شەویلگەم دێشێ'], group='neuro')
symptom('tender_on_press', L('Tender when pressed', 'مؤلم عند الضغط', 'بە گوشار دەئێشێت'),
        [r'\btender\w*\b', r'\b(hurts?|sore|painful) (when|if) (i )?(press|touch|push)\w*\b', r'\bsore to (the )?touch\b'], ['يؤلم عند الضغط', 'يوجع لما أضغط', 'يوجع لما اضغط', 'يوجع باللمس'],
        ['بە گوشار دەئێشێت', 'کە دەستی لێ دەدەم دێشێ'])
symptom('weight_loss', L('Weight loss without trying', 'فقدان الوزن دون سبب', 'دابەزینی کێش بەبێ هۆ'),
        [r'\b(lost (a lot of )?weight|weight loss|losing weight)\b'], ['نقص الوزن', 'نزل وزني', 'خسرت وزن', 'نقص وزني'], ['کێشم دابەزیوە', 'کێشم کەم بۆتەوە'])
symptom('pale_blue_skin', L('Blue, grey or very pale lips or skin', 'زرقة أو شحوب شديد في الشفاه أو الجلد', 'لێو یان پێستی شین، خۆڵەمێشی یان زۆر زەرد'),
        [r'\b(blue|grey|gray|very pale) (lips|skin|face|tongue)\b', r'\b(lips|skin|face|tongue) (turn\w*|are|is|look\w*) (blue|grey|gray|very pale)\b'], ['شفايف زرقاء', 'شفايفي زرق', 'زرقة', 'شحوب شديد'],
        ['لێوی شین', 'لێوم شین', 'پێستی شین'])
symptom('hoarse_voice', L('Hoarse voice', 'بحّة في الصوت', 'گیرانی دەنگ'), [r'\bhoarse\w*\b'], ['بحة', 'بحّة', 'صوتي مبحوح'], ['دەنگم گیراوە', 'گیرانی دەنگ'], group='ent')
symptom('drooling', L('Drooling / unable to swallow saliva', 'سيلان اللعاب', 'لیکڕشتن'), [r'\bdrool\w*\b'], ['سيلان اللعاب', 'لعاب يسيل', 'ريالة'], ['لیک دەڕژێت', 'لیکڕشتن'], group='ent')
symptom('night_vision_difficulty', L('Difficulty seeing at night', 'صعوبة الرؤية ليلاً', 'قورسی بینین بە شەو'),
        [r"\b(night vision|difficulty seeing at night|(can'?t|cannot) see (well )?at night|trouble seeing at night)\b"], ['ضعف الرؤية الليلية', 'ما أشوف بالليل', 'ما اشوف بالليل'], ['شەوان باش نابینم'], group='eye')
symptom('bleeding', L('Heavy bleeding that will not stop', 'نزيف شديد لا يتوقف', 'خوێنبەربوونی زۆر کە ناوەستێت'),
        [r"\b(won'?t stop bleeding|bleeding (that )?(won'?t|will not|does not|doesn'?t) stop|heavy bleeding|uncontrolled bleeding)\b"], ['نزيف شديد', 'نزيف ما يوقف', 'الدم ما يوقف'], ['خوێنبەربوون ناوەستێت', 'خوێنی زۆر'])

# =====================================================================================================
# Structured attributes
# =====================================================================================================
ATTRIBUTES = {
    'onset': {'label': L('Onset', 'طريقة البدء', 'شێوەی دەستپێکردن'), 'values': {
        'sudden': {'label': L('Sudden', 'مفاجئ', 'لەناکاو'), 'terms': {'en': [r'\b(sudden\w*|all of a sudden|abrupt\w*|out of nowhere|came on (quickly|fast)|instantly|in seconds)\b'], 'ar': ['فجأة', 'فجاة', 'فجأه', 'مفاجئ', 'بلحظة', 'فد مرة'], 'ckb': ['لەناکاو', 'کتوپڕ', 'بەیەکجار', 'لە پڕ']}},
        'gradual': {'label': L('Gradual', 'تدريجي', 'وردە وردە'), 'terms': {'en': [r'\b(gradual\w*|slowly|over (time|weeks|months|days)|bit by bit|crept up|creeping)\b'], 'ar': ['تدريجي', 'تدريجيا', 'تدريجياً', 'شوي شوي', 'شيئا فشيئا', 'بالتدريج'], 'ckb': ['وردە وردە', 'هێدی هێدی', 'بەرەبەرە', 'بە هێواشی']}},
    }},
    'course': {'label': L('Change over time', 'التغير مع الوقت', 'گۆڕان بە تێپەڕبوونی کات'), 'values': {
        'worsening': {'label': L('Getting worse', 'يزداد سوءاً', 'خراپتر دەبێت'), 'terms': {'en': [r'\b(worse|worsening|getting worse|increasing|spreading)\b'], 'ar': ['يزداد', 'أسوأ', 'اسوأ', 'صار أسوأ', 'يسوء', 'زاد', 'ينتشر', 'دا يزيد'], 'ckb': ['خراپتر', 'زیاد دەکات', 'زیاتر دەبێت', 'بڵاو دەبێتەوە']}},
        'improving': {'label': L('Getting better', 'يتحسن', 'باشتر دەبێت'), 'terms': {'en': [r'\b(better|improv\w*|easing|settling|going away)\b'], 'ar': ['أحسن', 'احسن', 'يتحسن', 'خف', 'دا يخف', 'قل'], 'ckb': ['باشتر', 'کەم دەبێتەوە', 'سووکتر']}},
        'stable': {'label': L('About the same', 'كما هو تقريباً', 'نزیکەی وەک خۆی'), 'terms': {'en': [r'\b(the same|unchanged|no change|stable|not changing)\b'], 'ar': ['نفس الشي', 'نفس الشيء', 'ما تغير', 'ثابت', 'نفسه'], 'ckb': ['وەک خۆیەتی', 'نەگۆڕاوە', 'هەمان شت']}},
    }},
    'pattern': {'label': L('Pattern', 'النمط', 'شێواز'), 'values': {
        'constant': {'label': L('Constant', 'مستمر', 'بەردەوام'), 'terms': {'en': [r'\b(constant\w*|all the time|continuous\w*|non.?stop|persistent|always there)\b'], 'ar': ['مستمر', 'طول الوقت', 'دائم', 'دايم', 'على طول', 'بدون توقف'], 'ckb': ['بەردەوام', 'هەمیشە', 'هەموو کات']}},
        'intermittent': {'label': L('Comes and goes', 'يأتي ويذهب', 'دێت و دەڕوات'), 'terms': {'en': [r'\b(comes and goes|come and go|on and off|off and on|intermittent\w*|sometimes|episodes?|attacks?|now and then)\b'], 'ar': ['يروح ويجي', 'يجي ويروح', 'أحيانا', 'احيانا', 'أحياناً', 'متقطع', 'نوبات', 'بعض الأوقات'], 'ckb': ['جار جار', 'هەندێک جار', 'دێت و دەڕوات', 'ناوە ناوە']}},
    }},
    'character': {'label': L('What it feels like', 'كيف يبدو', 'هەستەکەی چۆنە'), 'values': {
        'pressure': {'label': L('Pressing, tight or heavy', 'ضاغط أو ثقيل', 'گوشار، تەنگ یان قورس'), 'terms': {'en': [r'\b(tight|tightness|heavy|heaviness|pressure|pressing|crushing|squeez\w*|band around)\b'], 'ar': ['ضغط', 'ثقل', 'عصر', 'ضاغط', 'كأن شي ثقيل'], 'ckb': ['گوشار', 'قورسی', 'تەنگی', 'گوشین']}},
        'throbbing': {'label': L('Throbbing or pulsing', 'نابض', 'ترپەدار'), 'terms': {'en': [r'\b(throb\w*|pounding|pulsing|pulsating)\b'], 'ar': ['نابض', 'ينبض', 'يدق', 'نبض'], 'ckb': ['ترپە', 'ترپەدار', 'لێدان']}},
        'sharp': {'label': L('Sharp or stabbing', 'حاد أو طاعن', 'تیژ یان وەک چەقۆ'), 'terms': {'en': [r'\b(sharp|stabbing|shooting|knife.?like)\b'], 'ar': ['حاد', 'طعن', 'كالسكين', 'نغزة', 'نغز'], 'ckb': ['تیژ', 'وەک چەقۆ', 'چەقۆیی']}},
        'burning': {'label': L('Burning', 'حارق', 'سووتێنەر'), 'terms': {'en': [r'\bburn\w*\b'], 'ar': ['حارق', 'يحرق', 'حرقان'], 'ckb': ['سووتان', 'دەسووتێ', 'سووتێنەر']}},
    }},
    'side': {'label': L('Side', 'الجهة', 'لا'), 'values': {
        'left': {'label': L('Left', 'اليسار', 'چەپ'), 'terms': {'en': [r'\bleft\b(?! (alone|over|behind|out|it))'], 'ar': ['يسار', 'اليسار', 'اليسرى', 'الأيسر', 'الايسر', 'يسرى', 'اليسره'], 'ckb': ['ی چەپ', 'لای چەپ', 'چەپم', 'چەپ']}},
        'right': {'label': L('Right', 'اليمين', 'ڕاست'), 'terms': {'en': [r'(?<!all )\bright\b(?! (now|away|after|before|there|here|back|then|thing))'], 'ar': ['يمين', 'اليمين', 'اليمنى', 'الأيمن', 'الايمن', 'يمنى'], 'ckb': ['ی ڕاست', 'لای ڕاست', 'ڕاستم']}},
        'both': {'label': L('Both sides', 'كلا الجهتين', 'هەردوو لا'), 'terms': {'en': [r'\b(both|either side|each side)\b'], 'ar': ['كلتا', 'كلا ', 'الاثنين', 'الثنتين', 'الجهتين', 'الطرفين', 'الثنين'], 'ckb': ['هەردوو', 'هەردووک', 'هەر دوو']}},
    }},
}
TRIGGERS = {
    'exertion': (L('Exercise or exertion', 'الجهد أو الرياضة', 'هەوڵ یان وەرزش'), [r'\b(exercis\w*|exertion|walking|running|stairs|climbing|effort)\b'], ['الجهد', 'المشي', 'الركض', 'الرياضة', 'الدرج'], ['وەرزش', 'ڕۆیشتن', 'ڕاکردن', 'پلیکانە']),
    'eating': (L('Eating or drinking', 'الأكل أو الشرب', 'خواردن یان خواردنەوە'), [r'\b(eat\w*|meals?|food|drink\w*)\b'], ['الأكل', 'الاكل', 'الطعام', 'الشرب', 'بعد الأكل'], ['خواردن', 'دوای خواردن', 'خواردنەوە']),
    'temperature': (L('Hot or cold food and drinks', 'الأطعمة والمشروبات الحارة أو الباردة', 'خواردنی گەرم یان سارد'), [r'\b(cold|hot|ice|sweet)\b'], ['البارد', 'بارد', 'الحار', 'حار', 'الحلو', 'الثلج'], ['سارد', 'گەرم', 'شیرین', 'سەهۆڵ']),
    'chewing': (L('Chewing or biting', 'المضغ أو العض', 'جووین یان گەستن'), [r'\b(chew\w*|bit(e|ing))\b'], ['المضغ', 'مضغ', 'العض', 'أعض', 'اعض'], ['جووین', 'گەستن', 'دەیجووم']),
    'screen': (L('Screens or reading', 'الشاشات أو القراءة', 'شاشە یان خوێندنەوە'), [r'\b(screens?|computer|phone|reading|laptop)\b'], ['الشاشة', 'الموبايل', 'الكمبيوتر', 'القراءة'], ['شاشە', 'مۆبایل', 'کۆمپیوتەر', 'خوێندنەوە']),
    'lying_down': (L('Lying down or bending', 'الاستلقاء أو الانحناء', 'ڕاکشان یان چەمانەوە'), [r'\b(lying down|lie down|bending|bend over|at bed ?time)\b'], ['الاستلقاء', 'لما أنام', 'لما انام', 'الانحناء'], ['ڕاکشان', 'کە پاڵ دەکەوم', 'چەمانەوە']),
    'movement': (L('Moving or using it', 'الحركة أو الاستخدام', 'جووڵە یان بەکارهێنان'), [r'\b(mov\w*|lifting|bending|twisting|gripping|using it)\b'], ['الحركة', 'أتحرك', 'اتحرك', 'الرفع', 'الإمساك'], ['جووڵە', 'دەجووڵێم', 'هەڵگرتن', 'گرتن']),
    'breathing': (L('Breathing in deeply or coughing', 'التنفس العميق أو السعال', 'هەناسەی قووڵ یان کۆکە'), [r'\b(deep breath\w*|breath\w* in|when i breathe|cough\w*)\b'], ['التنفس العميق', 'أتنفس', 'اتنفس', 'السعال', 'الكحة'], ['هەناسەی قووڵ', 'هەناسەدان', 'کۆکە']),
    'light': (L('Bright light', 'الضوء الساطع', 'ڕووناکی بەهێز'), [r'\b(bright )?lights?\b'], ['الضوء', 'الضو'], ['ڕووناکی']),
    'stress': (L('Stress or tiredness', 'التوتر أو التعب', 'فشار یان ماندوویی'), [r'\b(stress\w*|tired\w*|anxi\w*|lack of sleep)\b'], ['التوتر', 'الضغط النفسي', 'التعب', 'قلة النوم'], ['فشار', 'ماندوویی', 'نیگەرانی', 'کەمخەوی']),
    'night': (L('At night', 'في الليل', 'بە شەو'), [r'\b(at night|night ?time|wakes? me( up)?)\b'], ['بالليل', 'في الليل', 'يصحيني'], ['بە شەو', 'شەوان', 'لە خەو هەڵمدەستێنێ']),
    'morning': (L('First thing in the morning', 'أول الصباح', 'سەرەتای بەیانی'), [r'\b(in the morning|first steps?|when i get up|after rest\w*)\b'], ['الصبح', 'الصباح', 'لما أكعد من النوم', 'أول خطوات'], ['بەیانیان', 'بەیانی', 'کە هەڵدەستم']),
    'pressing': (L('Pressing on it', 'الضغط عليه', 'گوشار لەسەری'), [r'\b(press\w*|touch\w*)\b'], ['الضغط', 'اللمس'], ['گوشار', 'دەستلێدان']),
    'swallowing': (L('Swallowing', 'البلع', 'قووتدان'), [r'\bswallow\w*\b'], ['البلع', 'أبلع', 'ابلع'], ['قووتدان']),
}
TRIGGER_CUES = {'en': r'\b(when|while|after|with|during|if|on|by|from|whenever|worse)\b', 'ar': r'(لما|عند|بعد|وقت|وكت|مع|أثناء|اثناء|من)', 'ckb': r'(کاتێک|کە|دوای|لەگەڵ|لە کاتی|بە)'}
SEVERITY_WORDS = {
    'en': [(r'\bworst\b.{0,25}\b(ever|of my life|i have (ever )?had)\b|\bthe worst (pain|headache)\b', 10), (r'\b(unbearable|excruciating|agoni\w*|extreme\w*)\b', 9),
           (r'\b(severe\w*|intense\w*|terrible|very bad|really bad|horrible)\b', 8), (r'\b(moderate\w*|medium|quite bad|fairly bad)\b', 5), (r'\b(mild\w*|slight\w*|a little|minor|not bad)\b', 2)],
    'ar': [('أسوأ (ألم|صداع)|أشد ألم|اسوأ (الم|صداع)', 10), ('ما يتحمل|لا يطاق|فظيع', 9), ('شديد|قوي|كلش|هواية', 8), ('متوسط', 5), ('خفيف|بسيط|شوية', 2)],
    'ckb': [('خراپترین', 10), ('بەرگەناگیرێ|تاقەتپڕووکێن', 9), ('زۆر توند|(?<![\u0600-\u06FF])توند|بەهێز|زۆر خراپ', 8), ('مامناوەند', 5), ('(?<![\u0600-\u06FF])(سووک|کەمێک|کەم)(?![\u0600-\u06FF])', 2)],
}
NEGATION = {
    'en': {'before': r"\b(no|not|without|denies|deny|never|don'?t have|do not have|haven'?t (had|noticed|got)|have not (had|noticed)|nor|none|neither|free of)\b[^.,;:!?]{0,30}$", 'after': r"^[^.,;:!?]{0,12}\b(is|are|has|have)? ?(gone|absent|resolved)\b"},
    'ar': {'before': r'(^|\s)(لا|ما|ماكو|مو|مش|بدون|ليس|ليست|غير|لم|ولا|ما عندي|ماعندي|ما كو|ما بي|ما بيه)\s[^.,;:!?،؟]{0,25}$', 'after': r'^[^.,;:!?،؟]{0,10}(?<![\u0600-\u06FF])(ماكو|لا يوجد|ما موجود|غير موجود|ما عندي|اختفى|راح)(?![\u0600-\u06FF])'},
    'ckb': {'before': r'(^|\s)(نەخێر|هیچ|بێ|بەبێ)\s[^.,;:!?،؟]{0,25}$', 'after': r'^[^.,;:!?،؟]{0,14}(?<![\u0600-\u06FF])(نیە|نییە|نەبووە|نیم|نیمە|نەبوو|نەماوە|نیه)(?![\u0600-\u06FF])'},
}
UNCERTAIN = {'en': r"\b(not sure|unsure|don'?t know|do not know|maybe|i think|possibly|might be)\b", 'ar': r'(مو متأكد|مش متأكد|غير متأكد|ما أدري|ما ادري|ما اعرف|ما أعرف|يمكن|ربما)', 'ckb': r'(دڵنیا نیم|نازانم|لەوانەیە|ڕەنگە)'}
HISTORICAL = {'en': r'\b(years? ago|last year|used to|in the past|as a child|previously had|months ago)\b', 'ar': r'(قبل سنين|قبل سنة|سابقا|سابقاً|من زمان|كان عندي|بالماضي)', 'ckb': r'(ساڵانێک لەمەوبەر|پار|جاران|پێشتر هەبوو|لە ڕابردوودا)'}
YES = {'en': r"^\s*(yes|yeah|yep|yup|correct|true|sure|i do(?! not)(?!n'?t)|i have(?! not| no)(?!n'?t))\b", 'ar': r'^\s*(نعم|اي|إي|ايه|أيوه|بلى|صح|عندي)', 'ckb': r'^\s*(بەڵێ|ئا|ئەری|هەیە|هەمە|ڕاستە)'}
NO = {'en': r"^\s*(no|nope|nah|none|i don'?t|not really|never)\b", 'ar': r'^\s*(لا|كلا|ماكو|ما عندي|أبد|ابد)', 'ckb': r'^\s*(نەخێر|نا|نیە|نییە|هیچ)'}
NUMBER_WORDS = {
    'en': {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'few': 3, 'couple of': 2, 'several': 4},
    'ar': {'واحد': 1, 'اثنين': 2, 'ثنين': 2, 'ثلاث': 3, 'ثلاثة': 3, 'تلاث': 3, 'اربع': 4, 'أربع': 4, 'اربعة': 4, 'خمس': 5, 'خمسة': 5, 'ست': 6, 'ستة': 6, 'سبع': 7, 'سبعة': 7, 'ثمان': 8, 'ثمانية': 8, 'تسع': 9, 'تسعة': 9, 'عشر': 10, 'عشرة': 10, 'كم': 3, 'عدة': 4},
    'ckb': {'یەک': 1, 'دوو': 2, 'سێ': 3, 'چوار': 4, 'پێنج': 5, 'شەش': 6, 'حەوت': 7, 'هەشت': 8, 'نۆ': 9, 'دە': 10, 'چەند': 3},
}
DURATION_UNITS = {  # hours per unit
    'en': [(r'min(ute)?s?', 1 / 60), (r'h(ou)?rs?', 1), (r'days?', 24), (r'w(ee)?ks?', 168), (r'months?', 720), (r'y(ea)?rs?', 8760)],
    'ar': [('دقيقة|دقائق|دقايق', 1 / 60), ('ساعة|ساعات|ساعه', 1), ('يوم|أيام|ايام', 24), ('أسبوع|اسبوع|أسابيع|اسابيع|اسبوعين|أسبوعين', 168), ('شهر|أشهر|اشهر|شهور', 720), ('سنة|سنوات|سنين|سنه', 8760)],
    'ckb': [('خولەک|دەقیقە', 1 / 60), ('کاتژمێر|سەعات', 1), ('ڕۆژ', 24), ('هەفتە|حەفتە', 168), ('مانگ', 720), ('ساڵ', 8760)],
}
DURATION_SPECIAL = {
    'en': [(r'\bsince (yesterday|last night)\b', 24), (r'\b(this morning|since this morning|today|earlier today)\b', 6), (r'\b(just now|a few minutes ago)\b', 0.2), (r'\bsince last week\b', 168), (r'\bsince last month\b', 720)],
    'ar': [('من البارحة|من امس|من أمس|من البارحه', 24), ('من الصبح|اليوم|هذا الصباح', 6), ('يومين', 48), ('ساعتين', 2), ('اسبوعين|أسبوعين', 336), ('شهرين', 1440), ('سنتين', 17520)],
    'ckb': [('لە دوێنێوە|دوێنێ', 24), ('لە بەیانییەوە|ئەمڕۆ', 6), ('هەفتەی پێشوو', 168), ('مانگی پێشوو', 720)],
}

# =====================================================================================================
# Questions (multilingual) and the purpose shown with each question
# =====================================================================================================
QUESTIONS = {
    'onset': {'text': L('Did it start suddenly (within seconds to minutes) or gradually?', 'هل بدأ فجأة (خلال ثوانٍ أو دقائق) أم تدريجياً؟', 'لەناکاو دەستی پێکرد (لە چەند چرکە یان خولەکێکدا) یان وردە وردە؟'),
              'purpose': L('Sudden versus gradual onset changes how urgent this may be.', 'البدء المفاجئ أو التدريجي يغيّر مدى الاستعجال.', 'دەستپێکردنی لەناکاو یان وردە وردە پلەی پەلەکردن دەگۆڕێت.'),
              'options': [('onset:sudden', L('Suddenly', 'فجأة', 'لەناکاو')), ('onset:gradual', L('Gradually', 'تدريجياً', 'وردە وردە')), ('unknown', L('Not sure', 'لست متأكداً', 'دڵنیا نیم'))]},
    'duration': {'text': L('How long have you had it?', 'منذ متى لديك هذا؟', 'چەندە ئەم کێشەیەت هەیە؟'),
                 'purpose': L('How long it has lasted affects which explanations fit and when to get checked.', 'المدة تؤثر على التفسيرات المناسبة وموعد الفحص.', 'ماوەکەی کاریگەری لەسەر ڕوونکردنەوەکان و کاتی پشکنین هەیە.'),
                 'options': [('duration:12', L('Less than a day', 'أقل من يوم', 'کەمتر لە ڕۆژێک')), ('duration:96', L('1–7 days', '١–٧ أيام', '١–٧ ڕۆژ')), ('duration:336', L('1–3 weeks', '١–٣ أسابيع', '١–٣ هەفتە')), ('duration:1080', L('More than 3 weeks', 'أكثر من ٣ أسابيع', 'زیاتر لە ٣ هەفتە')), ('unknown', L('Not sure', 'لست متأكداً', 'دڵنیا نیم'))]},
    'severity': {'text': L('How bad is it from 0 (none) to 10 (worst imaginable)?', 'ما شدّته من 0 (لا شيء) إلى 10 (أسوأ ما يمكن تخيله)؟', 'توندییەکەی لە 0 (هیچ) تا 10 (خراپترین شێوە) چەندە؟'),
                 'purpose': L('Severity helps set urgency and is recorded for your clinician.', 'الشدة تساعد في تحديد الاستعجال وتُسجّل لطبيبك.', 'توندی یارمەتی دیاریکردنی پەلە دەدات و بۆ پزیشکەکەت تۆمار دەکرێت.'),
                 'options': [('severity:2', L('Mild (0–3)', 'خفيف (0–3)', 'سووک (0–3)')), ('severity:5', L('Moderate (4–6)', 'متوسط (4–6)', 'مامناوەند (4–6)')), ('severity:8', L('Severe (7–10)', 'شديد (7–10)', 'توند (7–10)'))]},
    'pattern': {'text': L('Is it there all the time, or does it come and go?', 'هل هو موجود طوال الوقت أم يأتي ويذهب؟', 'هەمیشە هەیە یان دێت و دەڕوات؟'),
                'purpose': L('Constant versus coming-and-going symptoms point to different causes.', 'الأعراض المستمرة أو المتقطعة تشير إلى أسباب مختلفة.', 'نیشانەی بەردەوام یان ناوە ناوە ئاماژە بە هۆکاری جیاواز دەکەن.'),
                'options': [('pattern:constant', L('All the time', 'طوال الوقت', 'هەموو کات')), ('pattern:intermittent', L('Comes and goes', 'يأتي ويذهب', 'دێت و دەڕوات')), ('unknown', L('Not sure', 'لست متأكداً', 'دڵنیا نیم'))]},
    'course': {'text': L('Since it started, is it getting better, worse, or staying the same?', 'منذ أن بدأ، هل يتحسن أم يسوء أم يبقى كما هو؟', 'لەو کاتەوەی دەستی پێکردووە، باشتر دەبێت، خراپتر دەبێت یان وەک خۆیەتی؟'),
               'purpose': L('A worsening course can change the recommended care.', 'تفاقم الحالة قد يغيّر الرعاية الموصى بها.', 'خراپتربوون دەتوانێت چاودێری پێشنیارکراو بگۆڕێت.'),
               'options': [('course:worsening', L('Worse', 'يسوء', 'خراپتر')), ('course:improving', L('Better', 'يتحسن', 'باشتر')), ('course:stable', L('About the same', 'كما هو', 'وەک خۆی'))]},
    'character': {'text': L('What does it feel like?', 'كيف تشعر به؟', 'هەستەکەی چۆنە؟'),
                  'purpose': L('The quality of the pain helps separate possible causes.', 'طبيعة الألم تساعد في التفريق بين الأسباب المحتملة.', 'جۆری ئازارەکە یارمەتی جیاکردنەوەی هۆکارەکان دەدات.'),
                  'options': [('character:pressure', L('Pressing, tight or heavy', 'ضاغط أو ثقيل', 'گوشار یان قورس')), ('character:throbbing', L('Throbbing', 'نابض', 'ترپەدار')), ('character:sharp', L('Sharp or stabbing', 'حاد', 'تیژ')), ('character:burning', L('Burning', 'حارق', 'سووتێنەر')), ('unknown', L('Hard to describe', 'يصعب وصفه', 'قورسە وەسفی بکەم'))]},
    'side': {'text': L('Which side is affected?', 'أي جهة متأثرة؟', 'کام لا تووش بووە؟'),
             'purpose': L('Knowing the exact side keeps your record and the 3D view accurate.', 'معرفة الجهة بدقة تحافظ على دقة سجلك والعرض ثلاثي الأبعاد.', 'زانینی لای دروست تۆمار و پیشاندانی سێ ڕەهەندی ورد دەهێڵێتەوە.'),
             'options': [('side:left', L('Left', 'اليسار', 'چەپ')), ('side:right', L('Right', 'اليمين', 'ڕاست')), ('side:both', L('Both', 'كلاهما', 'هەردووک'))]},
    'structure': {'text': L('Which part exactly?', 'أي جزء بالتحديد؟', 'بە وردی کام بەش؟'),
                  'purpose': L('Pinpointing the structure narrows down what applies.', 'تحديد الجزء بدقة يضيّق الاحتمالات.', 'دیاریکردنی بەشەکە ئەگەرەکان کەم دەکاتەوە.'), 'options': []},
    'triggers': {'text': L('Does anything bring it on or make it worse?', 'هل هناك شيء يسببه أو يزيده سوءاً؟', 'هیچ شتێک هەیە بیهێنێت یان خراپتری بکات؟'),
                 'purpose': L('What brings it on helps distinguish between causes.', 'معرفة ما يسببه تساعد على التمييز بين الأسباب.', 'زانینی هۆکاری هێنانی یارمەتی جیاکردنەوەی هۆکارەکان دەدات.'), 'options': []},
    'medications': {'text': L('Are you taking any medicines, including anything new or recently changed?', 'هل تتناول أي أدوية، بما فيها دواء جديد أو تغيّر مؤخراً؟', 'هیچ دەرمانێک بەکاردەهێنیت، لەوانە دەرمانی نوێ یان گۆڕاو؟'),
                    'purpose': L('Medicines can cause or change symptoms and matter for safe advice.', 'الأدوية قد تسبب الأعراض أو تغيّرها وهي مهمة لنصيحة آمنة.', 'دەرمان دەتوانێت نیشانە دروست بکات یان بیگۆڕێت و بۆ ئامۆژگاری سەلامەت گرنگە.'),
                    'options': [('none', L('None', 'لا شيء', 'هیچ')), ('unknown', L('Not sure', 'لست متأكداً', 'دڵنیا نیم'))]},
    'allergies': {'text': L('Do you have any allergies to medicines or other things?', 'هل لديك حساسية من أدوية أو أشياء أخرى؟', 'هەستیاریت هەیە بەرامبەر دەرمان یان شتی تر؟'),
                  'purpose': L('Allergies matter for safe treatment and can explain some symptoms.', 'الحساسية مهمة لعلاج آمن وقد تفسر بعض الأعراض.', 'هەستیاری بۆ چارەسەری سەلامەت گرنگە و دەتوانێت هەندێک نیشانە ڕوون بکاتەوە.'),
                  'options': [('none', L('No known allergies', 'لا توجد حساسية معروفة', 'هیچ هەستیارییەکی ناسراو نیە')), ('unknown', L('Not sure', 'لست متأكداً', 'دڵنیا نیم'))]},
    'history': {'text': L('Do you have any long-term conditions or past problems that might be related?', 'هل لديك أمراض مزمنة أو مشاكل سابقة قد تكون ذات صلة؟', 'هیچ نەخۆشییەکی درێژخایەن یان کێشەیەکی پێشووت هەیە کە پەیوەندیدار بێت؟'),
                'purpose': L('Relevant history changes which explanations and warning signs apply.', 'التاريخ المرضي يغيّر التفسيرات وعلامات الخطر المنطبقة.', 'مێژووی نەخۆشی ڕوونکردنەوە و نیشانەی مەترسیدار دەگۆڕێت.'),
                'options': [('none', L('None', 'لا شيء', 'هیچ')), ('unknown', L('Not sure', 'لست متأكداً', 'دڵنیا نیم'))]},
    'safety': {'text': L('Before we continue — do you have any of these right now?', 'قبل أن نكمل — هل لديك أيٌّ من هذه الآن؟', 'پێش ئەوەی بەردەوام بین — ئێستا هیچ کام لەمانەت هەیە؟'),
               'purpose': L('Safety first: these signs need urgent care, so they are checked before anything else.', 'السلامة أولاً: هذه العلامات تحتاج رعاية عاجلة لذا تُفحص قبل أي شيء.', 'سەلامەتی یەکەم: ئەم نیشانانە پێویستیان بە چاودێری خێرا هەیە، بۆیە پێش هەموو شتێک دەپشکنرێن.'), 'options': []},
    'symptom': {'text': L('Have you also noticed this: {label}?', 'هل لاحظت هذا أيضاً: {label}؟', 'ئایا ئەمەشت هەستپێکردووە: {label}؟'),
                'purpose': L('This helps tell apart {a} and {b}.', 'يساعد هذا على التمييز بين {a} و{b}.', 'ئەمە یارمەتی جیاکردنەوەی {a} و {b} دەدات.'),
                'purpose_single': L('This checks a typical feature of {a}.', 'يتحقق هذا من علامة نموذجية لـ{a}.', 'ئەمە نیشانەیەکی ئاسایی {a} دەپشکنێت.'),
                'options': [('yes', L('Yes', 'نعم', 'بەڵێ')), ('no', L('No', 'لا', 'نەخێر')), ('unknown', L('Not sure', 'لست متأكداً', 'دڵنیا نیم'))]},
    'clarify': {'text': L('Earlier you said “{a}”, and later “{b}”. Which is correct now?', 'ذكرتَ سابقاً «{a}» ثم «{b}». أيهما صحيح الآن؟', 'پێشتر وتت «{a}» و دواتر «{b}». ئێستا کامیان ڕاستە؟'),
                'purpose': L('Your answers disagree; I need to know which is correct before relying on them.', 'إجاباتك متعارضة؛ أحتاج معرفة الصحيح قبل الاعتماد عليها.', 'وەڵامەکانت پێچەوانەی یەکن؛ پێویستە بزانم کامیان ڕاستە.'),
                'options': [('first', L('The first answer', 'الإجابة الأولى', 'وەڵامی یەکەم')), ('second', L('The later answer', 'الإجابة اللاحقة', 'وەڵامی دواتر'))]},
    'laterality': {'text': L('You selected the {selected} side but mentioned the {said} side. Which side is affected?', 'اخترت الجهة {selected} لكنك ذكرت الجهة {said}. أي جهة متأثرة؟', 'لای {selected}ت هەڵبژارد بەڵام باسی لای {said}ت کرد. کام لا تووش بووە؟'),
                   'purpose': L('Left/right must be consistent before the record and 3D view are updated.', 'يجب أن تتطابق الجهة قبل تحديث السجل والعرض ثلاثي الأبعاد.', 'چەپ/ڕاست دەبێت یەکبگرنەوە پێش نوێکردنەوەی تۆمار و پیشاندانی سێ ڕەهەندی.'),
                   'options': [('side:left', L('Left', 'اليسار', 'چەپ')), ('side:right', L('Right', 'اليمين', 'ڕاست')), ('side:both', L('Both', 'كلاهما', 'هەردووک'))]},
    'memory': {'text': L('Your saved history lists “{item}”. Is that still current?', 'يذكر سجلك المحفوظ «{item}». هل ما زال ذلك صحيحاً؟', 'مێژووە پاشەکەوتکراوەکەت «{item}» تێدایە. هێشتا ڕاستە؟'),
               'purpose': L('Saved history can be out of date; confirming avoids relying on old information.', 'قد يكون السجل المحفوظ قديماً؛ التأكيد يمنع الاعتماد على معلومات قديمة.', 'مێژووی پاشەکەوتکراو لەوانەیە کۆن بێت؛ دڵنیاکردنەوە ڕێگری لە پشتبەستن بە زانیاری کۆن دەکات.'),
               'options': [('yes', L('Yes, still current', 'نعم، ما زال صحيحاً', 'بەڵێ، هێشتا ڕاستە')), ('no', L('No longer', 'لم يعد كذلك', 'نەخێر، چیتر نا'))]},
}

# =====================================================================================================
# Care pathways
# =====================================================================================================
PATHWAYS = {
    'emergency': {'urgency': 'emergency', 'label': L('Emergency care now', 'رعاية طارئة الآن', 'فریاکەوتنی خێرا ئێستا'),
                  'action': L('Call your local emergency number or go to the nearest emergency department now. Do not drive yourself. Do not wait for this chat.', 'اتصل برقم الطوارئ المحلي أو اذهب إلى أقرب قسم طوارئ الآن. لا تقد السيارة بنفسك. لا تنتظر هذه المحادثة.', 'ئێستا پەیوەندی بە ژمارەی فریاکەوتنی ناوخۆوە بکە یان بچۆ بۆ نزیکترین بەشی فریاکەوتن. خۆت ئۆتۆمبێل لێمەخوڕە. چاوەڕێی ئەم گفتوگۆیە مەکە.')},
    'eye_emergency': {'urgency': 'emergency', 'label': L('Emergency eye care now', 'رعاية طارئة للعين الآن', 'فریاکەوتنی خێرای چاو ئێستا'),
                      'action': L('Go to an emergency department or emergency eye service now. Do not drive yourself.', 'اذهب إلى قسم الطوارئ أو خدمة طوارئ العيون الآن. لا تقد السيارة بنفسك.', 'ئێستا بچۆ بۆ بەشی فریاکەوتن یان خزمەتگوزاری فریاکەوتنی چاو. خۆت ئۆتۆمبێل لێمەخوڕە.')},
    'urgent_same_day': {'urgency': 'same_day', 'label': L('Urgent medical assessment today', 'تقييم طبي عاجل اليوم', 'هەڵسەنگاندنی پزیشکی بەپەلە ئەمڕۆ'),
                        'action': L('Get an urgent appointment with a doctor or urgent-care service today. Use emergency services if it gets worse quickly.', 'احصل على موعد عاجل مع طبيب أو خدمة رعاية عاجلة اليوم. استخدم الطوارئ إذا ساءت الحالة بسرعة.', 'ئەمڕۆ کاتێکی بەپەلە لەگەڵ پزیشک یان خزمەتگوزاری بەپەلە وەربگرە. ئەگەر بە خێرایی خراپتر بوو فریاکەوتن بەکاربهێنە.')},
    'eye_urgent': {'urgency': 'same_day', 'label': L('Urgent eye assessment today', 'فحص عاجل للعين اليوم', 'پشکنینی بەپەلەی چاو ئەمڕۆ'),
                   'action': L('Get your eye checked today by an eye casualty service, urgent optometrist or doctor.', 'افحص عينك اليوم في طوارئ العيون أو لدى أخصائي بصريات أو طبيب بشكل عاجل.', 'ئەمڕۆ چاوت لە فریاکەوتنی چاو یان لای چاوساز یان پزیشک بە پەلە بپشکنە.')},
    'dentist_urgent': {'urgency': 'same_day', 'label': L('Urgent dental appointment', 'موعد عاجل لدى طبيب الأسنان', 'کاتی بەپەلەی ددانساز'),
                       'action': L('Contact a dentist for an urgent appointment today. Go to emergency care if swelling affects breathing, swallowing, speaking or your eye.', 'تواصل مع طبيب أسنان لموعد عاجل اليوم. اذهب للطوارئ إذا أثّر التورم على التنفس أو البلع أو الكلام أو العين.', 'ئەمڕۆ پەیوەندی بە ددانسازێکەوە بکە بۆ کاتی بەپەلە. ئەگەر ئاوسان کاریگەری لەسەر هەناسەدان، قووتدان، قسەکردن یان چاو هەبوو بچۆ بۆ فریاکەوتن.')},
    'gp_soon': {'urgency': 'soon', 'label': L('See a doctor within a few days', 'راجع طبيباً خلال أيام قليلة', 'لە ماوەی چەند ڕۆژێکدا سەردانی پزیشک بکە'),
                'action': L('Book an appointment with a doctor within a few days. Seek urgent help if it gets worse or warning signs appear.', 'احجز موعداً مع طبيب خلال أيام قليلة. اطلب مساعدة عاجلة إذا ساءت الحالة أو ظهرت علامات خطر.', 'لە ماوەی چەند ڕۆژێکدا کاتێک لەگەڵ پزیشک دابنێ. ئەگەر خراپتر بوو یان نیشانەی مەترسی دەرکەوت داوای یارمەتی بەپەلە بکە.')},
    'dentist_soon': {'urgency': 'soon', 'label': L('See a dentist soon', 'راجع طبيب الأسنان قريباً', 'بەم زووانە سەردانی ددانساز بکە'),
                     'action': L('Book a dental appointment soon. A dentist can examine the mouth and take X-rays if needed.', 'احجز موعداً لدى طبيب الأسنان قريباً. يمكنه فحص الفم وأخذ أشعة عند الحاجة.', 'بەم زووانە کاتێک لای ددانساز دابنێ. دەتوانێت دەم بپشکنێت و ئەگەر پێویست بوو تیشک بگرێت.')},
    'optometrist': {'urgency': 'routine', 'label': L('Eye examination by an optometrist', 'فحص العين لدى أخصائي البصريات', 'پشکنینی چاو لای چاوساز'),
                    'action': L('Arrange an eye examination with an optometrist (optician) or eye doctor.', 'رتّب فحصاً للعين لدى أخصائي بصريات أو طبيب عيون.', 'پشکنینێکی چاو لای چاوساز یان پزیشکی چاو ڕێک بخە.')},
    'gp_routine': {'urgency': 'routine', 'label': L('Routine doctor appointment if it persists', 'موعد اعتيادي مع الطبيب إذا استمر', 'سەردانی ئاسایی پزیشک ئەگەر بەردەوام بوو'),
                   'action': L('If it does not improve, book a routine appointment with a doctor. Seek help sooner if it worsens.', 'إذا لم يتحسن، احجز موعداً اعتيادياً مع طبيب. اطلب المساعدة أبكر إذا ساء.', 'ئەگەر باشتر نەبوو، کاتێکی ئاسایی لەگەڵ پزیشک دابنێ. ئەگەر خراپتر بوو زووتر داوای یارمەتی بکە.')},
    'pharmacist': {'urgency': 'routine', 'label': L('Pharmacist advice', 'استشارة الصيدلي', 'ئامۆژگاری دەرمانساز'),
                   'action': L('A pharmacist can advise on self-care for this kind of problem. See a doctor if it does not improve or gets worse.', 'يمكن للصيدلي تقديم النصح حول الرعاية الذاتية لهذا النوع من المشاكل. راجع طبيباً إذا لم يتحسن أو ساء.', 'دەرمانساز دەتوانێت ئامۆژگاری چاودێری خۆیی بدات. ئەگەر باشتر نەبوو یان خراپتر بوو سەردانی پزیشک بکە.')},
    'dentist_routine': {'urgency': 'routine', 'label': L('Routine dental appointment', 'موعد أسنان اعتيادي', 'کاتی ئاسایی ددانساز'),
                        'action': L('Book a routine dental check-up.', 'احجز فحصاً اعتيادياً للأسنان.', 'پشکنینێکی ئاسایی ددان دابنێ.')},
    'orthodontist': {'urgency': 'routine', 'label': L('Orthodontic assessment', 'تقييم تقويم الأسنان', 'هەڵسەنگاندنی ڕاستکردنەوەی ددان'),
                     'action': L('Ask a dentist about an orthodontic assessment. Any treatment plan, tooth movement or extraction decision needs an orthodontist’s examination and clinical records (X-rays, photographs, scans).', 'اسأل طبيب الأسنان عن تقييم لتقويم الأسنان. أي خطة علاج أو تحريك للأسنان أو قرار خلع يحتاج فحص أخصائي تقويم وسجلات سريرية (أشعة وصور ومسح).', 'لە ددانساز بپرسە دەربارەی هەڵسەنگاندنی ڕاستکردنەوەی ددان. هەر پلانێکی چارەسەر، جووڵاندنی ددان یان بڕیاری هەڵکێشان پێویستی بە پشکنینی پسپۆڕی ڕاستکردنەوە و تۆماری کلینیکی هەیە (تیشک، وێنە، سکان).')},
}

# =====================================================================================================
# Conditions. F(match, weight, source, evidence) / A(match, strength, source, evidence)
# match syntax: sym:<id> | attr:<name>=<value> | attr:side=one | attr:duration>=<hours> | attr:duration<=<hours> | attr:severity>=<n> | trig:<id>
# =====================================================================================================
def F(match, weight, src, ev):
    return {'match': match, 'weight': weight, 'source': src, 'ev': ev}


def A(match, strength, src, ev, why):
    return {'match': match, 'strength': strength, 'source': src, 'ev': ev, 'why': why}


CONDITIONS = []


def condition(identifier, name, anatomy, pathway, sources, features, against=(), *, urgent=False, scope_note=None, requires_anatomy=False):
    CONDITIONS.append({'id': identifier, 'name': name, 'anatomy': anatomy, 'pathway': pathway, 'sources': sources, 'features': features,
                       'against': list(against), 'urgent_condition': urgent, 'scope_note': scope_note, 'requires_anatomy': requires_anatomy,
                       'review_status': 'draft — clinician review pending'})


WHY_VISION = L('Changes in vision are listed as a sign of a more serious eye problem.', 'تغيّر الرؤية مذكور كعلامة على مشكلة أخطر في العين.', 'گۆڕانی بینین وەک نیشانەی کێشەیەکی جددیتری چاو ناوبراوە.')
WHY_PAIN_EYE = L('Eye pain is listed as a sign of a more serious eye problem.', 'ألم العين مذكور كعلامة على مشكلة أخطر.', 'ئازاری چاو وەک نیشانەی کێشەیەکی جددیتر ناوبراوە.')

# ---- eyes
condition('conjunctivitis', L('Conjunctivitis', 'التهاب الملتحمة', 'هەوکردنی پەردەی چاو'), ['body.eyes', 'eye.bulbar-conjunctiva'], 'pharmacist', ['nhs-conjunctivitis'], [
    F('sym:redness', 'typical', 'nhs-conjunctivitis', r'^red$'), F('sym:discharge', 'typical', 'nhs-conjunctivitis', r'produce pus that sticks'),
    F('sym:eye_dryness_grit', 'common', 'nhs-conjunctivitis', r'burn or feel gritty'), F('sym:itch', 'common', 'nhs-conjunctivitis', r'^itch$'),
    F('sym:watery_eyes', 'common', 'nhs-conjunctivitis', r'^water$'), F('attr:side=both', 'common', 'nhs-conjunctivitis', r'usually affects both eyes')],
    [A('sym:blurred_vision', 'strong', 'nhs-conjunctivitis', r'changes in your vision', WHY_VISION), A('sym:vision_loss', 'strong', 'nhs-conjunctivitis', r'changes in your vision', WHY_VISION),
     A('sym:pain', 'moderate', 'nhs-conjunctivitis', r'^pain in your eyes$', WHY_PAIN_EYE),
     A('sym:light_sensitivity', 'moderate', 'nhs-conjunctivitis', r'^sensitivity to light$', L('Light sensitivity is listed as a sign of a more serious eye problem.', 'الحساسية للضوء مذكورة كعلامة على مشكلة أخطر.', 'هەستیاری بە ڕووناکی وەک نیشانەی کێشەیەکی جددیتر ناوبراوە.'))])
condition('dry_eye', L('Dry eyes', 'جفاف العين', 'وشکی چاو'), ['body.eyes', 'eye.tear-film', 'eye.cornea'], 'pharmacist', ['nhs-dry-eyes', 'nei-dry-eye'], [
    F('sym:eye_dryness_grit', 'typical', 'nhs-dry-eyes', r'^gritty$'), F('sym:itch', 'common', 'nhs-dry-eyes', r'^itchy$'), F('sym:redness', 'common', 'nhs-dry-eyes', r'^red$'),
    F('sym:pain', 'possible', 'nhs-dry-eyes', r'^sore$'), F('sym:blurred_vision', 'possible', 'nhs-dry-eyes', r'^blurry$'), F('sym:watery_eyes', 'possible', 'nhs-dry-eyes', r'more watery than normal'),
    F('sym:light_sensitivity', 'possible', 'nhs-dry-eyes', r'^sensitive to light$'), F('sym:contact_lens', 'common', 'nhs-dry-eyes', r'^you wear contact lenses$'),
    F('sym:screen_use', 'common', 'nhs-dry-eyes', r'computer screens'), F('trig:screen', 'common', 'nhs-dry-eyes', r'computer screens')],
    [A('sym:vision_loss', 'strong', 'nhs-dry-eyes', r'changes to your sight', WHY_VISION), A('sym:curtain_shadow', 'strong', 'nhs-dry-eyes', r'changes to your sight', WHY_VISION)])
condition('blepharitis', L('Blepharitis (inflamed eyelids)', 'التهاب الجفن', 'هەوکردنی پێڵوو'), ['eye.eyelid-margin', 'eye.upper-eyelid', 'eye.lower-eyelid', 'body.eyes'], 'pharmacist', ['nhs-blepharitis'], [
    F('sym:eyelid_crusting', 'typical', 'nhs-blepharitis', r'flakes or crusts'), F('sym:pain', 'common', 'nhs-blepharitis', r'^sore eyelids$'),
    F('sym:itch', 'common', 'nhs-blepharitis', r'^itchy eyes$'), F('sym:eye_dryness_grit', 'common', 'nhs-blepharitis', r'gritty feeling'),
    F('attr:pattern=intermittent', 'common', 'nhs-blepharitis', r'often come and go')],
    [A('sym:blurred_vision', 'strong', 'nhs-blepharitis', r'changes to your vision', WHY_VISION), A('sym:vision_loss', 'strong', 'nhs-blepharitis', r'changes to your vision', WHY_VISION)])
condition('stye', L('Stye', 'شحاذ العين', 'دانەوێڵەی چاو'), ['eye.upper-eyelid', 'eye.lower-eyelid', 'eye.eyelid-margin'], 'pharmacist', ['nhs-stye'], [
    F('sym:eyelid_lump', 'typical', 'nhs-stye', r'small, painful lump on the eyelid'), F('sym:pain', 'common', 'nhs-stye', r'small, painful lump'),
    F('attr:side=one', 'common', 'nhs-stye', r'usually only affects 1 eye')],
    [A('sym:blurred_vision', 'strong', 'nhs-stye', r'it affects your vision', L('A stye affecting vision needs urgent review.', 'الشحاذ الذي يؤثر على الرؤية يحتاج مراجعة عاجلة.', 'دانەوێڵەیەک کە کاریگەری لەسەر بینین هەبێت پێویستی بە پشکنینی بەپەلە هەیە.'))])
condition('floaters', L('Floaters and flashes (often harmless)', 'الأجسام العائمة والومضات (غالباً غير ضارة)', 'پەڵەی سەرچاو و بریسکە (زۆرجار بێزیانن)'), ['eye.vitreous-body', 'body.eyes'], 'optometrist', ['nhs-floaters'], [
    F('sym:flashes_floaters', 'typical', 'nhs-floaters', r'^small dark dots$'), F('attr:duration>=720', 'common', 'nhs-floaters', r'had them for a long time')],
    [A('sym:curtain_shadow', 'strong', 'nhs-floaters', r'dark "curtain" or shadow moving', L('A shadow or curtain can mean the retina is detaching.', 'الظل أو الستارة قد يعني انفصال الشبكية.', 'سێبەر یان پەردە لەوانەیە مانای جیابوونەوەی تۆڕینە بێت.')),
     A('attr:onset=sudden', 'moderate', 'nhs-floaters', r'suddenly get floaters or flashes', L('New or sudden floaters need an urgent check.', 'الأجسام العائمة الجديدة أو المفاجئة تحتاج فحصاً عاجلاً.', 'پەڵەی نوێ یان لەناکاو پێویستی بە پشکنینی بەپەلە هەیە.')),
     A('sym:blurred_vision', 'moderate', 'nhs-floaters', r'you also have blurred vision', WHY_VISION), A('sym:pain', 'moderate', 'nhs-floaters', r'you also have eye pain', WHY_PAIN_EYE)])
condition('retinal_detachment', L('Detached retina (needs urgent care)', 'انفصال الشبكية (يحتاج رعاية عاجلة)', 'جیابوونەوەی تۆڕینە (پێویستی بە چاودێری بەپەلە هەیە)'), ['eye.retina', 'eye.vitreous-body'], 'eye_urgent',
          ['nhs-detached-retina', 'nei-retinal-detachment'], [
    F('sym:flashes_floaters', 'typical', 'nhs-detached-retina', r'floaters \(dots and lines\) or flashes of light in your eye'), F('sym:curtain_shadow', 'typical', 'nhs-detached-retina', r'^a dark "curtain" or shadow in your vision$'),
    F('sym:blurred_vision', 'common', 'nhs-detached-retina', r'such as blurred vision'), F('attr:onset=sudden', 'common', 'nei-retinal-detachment', r'often come on quickly')], urgent=True)
condition('acute_glaucoma', L('Sudden (acute) glaucoma — an emergency', 'الزرق الحاد المفاجئ — حالة طارئة', 'گلۆکۆمای لەناکاو — حاڵەتی فریاکەوتن'), ['body.eyes', 'eye.iris', 'eye.optic-nerve'], 'eye_emergency', ['nhs-glaucoma'], [
    F('sym:pain', 'typical', 'nhs-glaucoma', r'^intense eye pain$'), F('sym:halos', 'typical', 'nhs-glaucoma', r'rainbow-coloured circles'), F('sym:redness', 'common', 'nhs-glaucoma', r'^a red eye$'),
    F('sym:blurred_vision', 'common', 'nhs-glaucoma', r'^blurred vision$'), F('sym:headache', 'possible', 'nhs-glaucoma', r'^a headache$'), F('sym:nausea', 'possible', 'nhs-glaucoma', r'feeling sick \(nausea\)'),
    F('attr:onset=sudden', 'typical', 'nhs-glaucoma', r'can develop suddenly')], urgent=True)
condition('cataract', L('Cataracts', 'إعتام عدسة العين (الماء الأبيض)', 'ئاوی سپی چاو (کاتاراکت)'), ['eye.lens'], 'optometrist', ['nhs-cataracts'], [
    F('sym:blurred_vision', 'typical', 'nhs-cataracts', r'^blurred vision$'), F('sym:night_vision_difficulty', 'common', 'nhs-cataracts', r'difficulty seeing at night'),
    F('sym:light_sensitivity', 'possible', 'nhs-cataracts', r'sensitive to, light'), F('sym:double_vision', 'possible', 'nhs-cataracts', r'double vision'),
    F('attr:onset=gradual', 'typical', 'nhs-cataracts', r'usually develop slowly')],
    [A('attr:onset=sudden', 'moderate', 'nhs-cataracts', r'usually develop slowly', L('Cataract symptoms usually develop slowly, not suddenly.', 'أعراض الماء الأبيض تتطور عادة ببطء وليس فجأة.', 'نیشانەکانی ئاوی سپی زۆرجار هێواش پەرە دەسێنن نەک لەناکاو.'))])
condition('uveitis', L('Uveitis (inflammation inside the eye)', 'التهاب العنبية', 'هەوکردنی ناوەوەی چاو (یووڤیایتس)'), ['eye.iris', 'body.eyes'], 'eye_urgent', ['nhs-uveitis'], [
    F('sym:pain', 'typical', 'nhs-uveitis', r'eye pain, which may feel worse'), F('sym:redness', 'common', 'nhs-uveitis', r'red or watery eyes'), F('sym:blurred_vision', 'common', 'nhs-uveitis', r'reduced or blurred vision'),
    F('sym:light_sensitivity', 'common', 'nhs-uveitis', r'^sensitivity to light$'), F('attr:side=one', 'common', 'nhs-uveitis', r'usually only affects one eye'),
    F('sym:flashes_floaters', 'possible', 'nhs-uveitis', r'dark spots')], urgent=True)

# ---- head, ears, throat
condition('tension_headache', L('Tension-type headache', 'صداع التوتر', 'سەرئێشەی فشار'), ['body.head', 'head.forehead', 'head.temple', 'head.back-of-head'], 'pharmacist', ['nhs-tension-headache'], [
    F('sym:headache', 'typical', 'nhs-tension-headache', r'pain on both sides of your head'), F('attr:side=both', 'common', 'nhs-tension-headache', r'pain on both sides of your head'),
    F('attr:character=pressure', 'typical', 'nhs-tension-headache', r'pressing on your head'), F('sym:tender_on_press', 'possible', 'nhs-tension-headache', r'may feel tender'),
    F('trig:stress', 'common', 'nhs-tension-headache', r'^stress$')],
    [A('attr:character=throbbing', 'moderate', 'nhs-tension-headache', r'throbbing pain at the front, or on 1 side', L('A throbbing, one-sided headache suggests a different type, such as migraine.', 'الصداع النابض في جهة واحدة يشير إلى نوع آخر مثل الشقيقة.', 'سەرئێشەی ترپەداری یەک لایەنە ئاماژە بە جۆرێکی تر دەکات وەک شەقیقە.')),
     A('sym:vomiting', 'moderate', 'nhs-tension-headache', r'feel sick, vomit and find light or noise painful', L('Sickness and light sensitivity suggest a different type of headache.', 'الغثيان والحساسية للضوء يشيران لنوع آخر من الصداع.', 'هێڵنج و هەستیاری بە ڕووناکی ئاماژە بە جۆرێکی تری سەرئێشە دەکەن.')),
     A('sym:light_sensitivity', 'moderate', 'nhs-tension-headache', r'feel sick, vomit and find light or noise painful', L('Light sensitivity suggests a different type of headache.', 'الحساسية للضوء تشير إلى نوع آخر من الصداع.', 'هەستیاری بە ڕووناکی ئاماژە بە جۆرێکی تری سەرئێشە دەکات.'))])
condition('migraine', L('Migraine', 'الشقيقة (الصداع النصفي)', 'شەقیقە'), ['body.head', 'head.temple', 'head.forehead'], 'gp_routine', ['nhs-migraine'], [
    F('sym:headache', 'typical', 'nhs-migraine', r'a throbbing headache'), F('attr:character=throbbing', 'typical', 'nhs-migraine', r'a throbbing headache'),
    F('attr:side=one', 'common', 'nhs-migraine', r'often on 1 side'), F('sym:nausea', 'common', 'nhs-migraine', r'feeling or being sick'), F('sym:vomiting', 'common', 'nhs-migraine', r'feeling or being sick'),
    F('sym:light_sensitivity', 'common', 'nhs-migraine', r'sensitive to light and sounds'), F('attr:pattern=intermittent', 'common', 'nhs-migraine', r'migraine attacks more than once a week'),
    F('trig:stress', 'possible', 'nhs-migraine', r'stress and tiredness')])
condition('sinusitis', L('Sinusitis', 'التهاب الجيوب الأنفية', 'هەوکردنی سینوس'), ['head.sinuses', 'head.forehead'], 'pharmacist', ['nhs-sinusitis'], [
    F('sym:pain', 'typical', 'nhs-sinusitis', r'pain, swelling and tenderness around your cheeks'), F('sym:nasal_congestion', 'typical', 'nhs-sinusitis', r'blocked or runny nose'),
    F('sym:reduced_smell', 'common', 'nhs-sinusitis', r'reduced sense of smell'), F('sym:discharge', 'common', 'nhs-sinusitis', r'green or yellow mucus'), F('sym:fever', 'possible', 'nhs-sinusitis', r'^a high temperature$')])
condition('tmd', L('Jaw joint disorder (TMD)', 'اضطراب مفصل الفك', 'تێکچوونی جومگەی شەویلگە'), ['head.jaw-joint', 'head.temple', 'mouth.bite'], 'dentist_routine', ['nhs-tmd'], [
    F('sym:pain', 'typical', 'nhs-tmd', r'pain around your jaw, ear and temple'), F('sym:jaw_clicking', 'typical', 'nhs-tmd', r'clicking, popping or grinding noises'),
    F('sym:headache', 'common', 'nhs-tmd', r'headache around your temples'), F('sym:difficulty_opening_mouth', 'common', 'nhs-tmd', r'difficulty opening your mouth fully'),
    F('trig:chewing', 'common', 'nhs-tmd', r'worse when chewing'), F('trig:stress', 'possible', 'nhs-tmd', r'worse when chewing and when you feel stressed')])
condition('ear_infection', L('Ear infection', 'التهاب الأذن', 'هەوکردنی گوێ'), ['ear.outer', 'ear.middle', 'body.ears'], 'pharmacist', ['nhs-ear-infections'], [
    F('sym:ear_pain', 'typical', 'nhs-ear-infections', r'pain inside the ear'), F('sym:fever', 'common', 'nhs-ear-infections', r'^a high temperature$'),
    F('sym:hearing_change', 'common', 'nhs-ear-infections', r'difficulty hearing'), F('sym:discharge', 'common', 'nhs-ear-infections', r'discharge running out of the ear'),
    F('sym:itch', 'possible', 'nhs-ear-infections', r'itching and irritation'), F('attr:onset=sudden', 'common', 'nhs-ear-infections', r'usually start quickly')])
condition('sore_throat', L('Sore throat (usually viral)', 'التهاب الحلق (غالباً فيروسي)', 'گەروو ئێشە (زۆرجار ڤایرۆسی)'), ['neck.throat'], 'pharmacist', ['nhs-sore-throat'], [
    F('sym:sore_throat', 'typical', 'nhs-sore-throat', r'painful throat, especially when swallowing'), F('sym:swallowing_difficulty', 'common', 'nhs-sore-throat', r'painful throat, especially when swallowing'),
    F('sym:cough', 'possible', 'nhs-sore-throat', r'^a mild cough$'), F('sym:swelling', 'possible', 'nhs-sore-throat', r'swollen neck glands'), F('sym:bad_taste_breath', 'possible', 'nhs-sore-throat', r'^bad breath$')],
    [A('sym:drooling', 'strong', 'nhs-sore-throat', r'drooling', L('Drooling can mean you cannot swallow — an emergency sign.', 'سيلان اللعاب قد يعني عدم القدرة على البلع — علامة طارئة.', 'لیکڕشتن لەوانەیە مانای نەتوانینی قووتدان بێت — نیشانەی فریاکەوتن.'))])
condition('tonsillitis', L('Tonsillitis', 'التهاب اللوزتين', 'هەوکردنی لەوزە'), ['neck.throat'], 'pharmacist', ['nhs-tonsillitis'], [
    F('sym:sore_throat', 'typical', 'nhs-tonsillitis', r'^a sore throat$'), F('sym:swallowing_difficulty', 'common', 'nhs-tonsillitis', r'^problems swallowing$'),
    F('sym:fever', 'common', 'nhs-tonsillitis', r'^a high temperature$'), F('sym:cough', 'possible', 'nhs-tonsillitis', r'^coughing$'), F('sym:headache', 'possible', 'nhs-tonsillitis', r'^a headache$')])

# ---- mouth and teeth
condition('tooth_problem', L('Toothache from a tooth problem (e.g. decay, crack or filling)', 'ألم أسنان بسبب مشكلة في السن (تسوس أو كسر أو حشوة)', 'ددانئێشە بەهۆی کێشەی ددان (کرمخواردن، درز یان پڕکردنەوە)'), ['mouth.teeth'], 'dentist_soon', ['nhs-toothache'], [
    F('sym:toothache', 'typical', 'nhs-toothache', r'^tooth decay$'), F('sym:tooth_sensitivity', 'common', 'nhs-toothache', r'having sensitive teeth'), F('sym:broken_tooth', 'common', 'nhs-toothache', r'cracked or damaged tooth'),
    F('sym:pain_on_biting', 'common', 'nhs-toothache', r'pain when you bite'), F('attr:duration>=48', 'possible', 'nhs-toothache', r'^that lasts more than 2 days$'),
    F('trig:temperature', 'common', 'nhs-toothache', r'very hot or very cold')])
condition('dental_abscess', L('Dental abscess (needs an urgent dentist)', 'خراج سني (يحتاج طبيب أسنان عاجلاً)', 'کێمی ددان (پێویستی بە ددانسازی بەپەلە هەیە)'), ['mouth.teeth', 'mouth.gums'], 'dentist_urgent', ['nhs-dental-abscess'], [
    F('sym:toothache', 'typical', 'nhs-dental-abscess', r'intense toothache or pain in your gums'), F('sym:swelling', 'typical', 'nhs-dental-abscess', r'a swollen face or jaw'),
    F('sym:tooth_sensitivity', 'common', 'nhs-dental-abscess', r'sensitivity to hot or cold food'), F('sym:bad_taste_breath', 'common', 'nhs-dental-abscess', r'a bad taste in your mouth'),
    F('sym:difficulty_opening_mouth', 'common', 'nhs-dental-abscess', r'difficulty opening your mouth and chewing'), F('sym:redness', 'possible', 'nhs-dental-abscess', r'redness inside the mouth'),
    F('trig:temperature', 'possible', 'nhs-dental-abscess', r'sensitivity to hot or cold food')], urgent=True)
condition('gum_disease', L('Gum disease', 'أمراض اللثة', 'نەخۆشی پووک'), ['mouth.gums'], 'dentist_routine', ['nhs-gum-disease', 'nidcr-gum-disease'], [
    F('sym:gum_bleeding', 'typical', 'nhs-gum-disease', r'your gums bleeding when you brush'), F('sym:swelling', 'common', 'nhs-gum-disease', r'gums becoming swollen, red and sore'),
    F('sym:redness', 'common', 'nhs-gum-disease', r'gums becoming swollen, red and sore'), F('sym:bad_taste_breath', 'common', 'nhs-gum-disease', r'bad breath and a bad taste'),
    F('sym:loose_tooth', 'possible', 'nhs-gum-disease', r'teeth becoming loose or falling out')])
condition('mouth_ulcer', L('Mouth ulcer', 'قرحة الفم', 'برینی دەم'), ['mouth.oral-lining', 'mouth.tongue', 'mouth.lips'], 'pharmacist', ['nhs-mouth-ulcers'], [
    F('sym:mouth_ulcer', 'typical', 'nhs-mouth-ulcers', r'more than 1 ulcer at a time'),
    F('trig:chewing', 'possible', 'nhs-mouth-ulcers', r'biting the inside of your cheek')],
    [A('attr:duration>=504', 'strong', 'nhs-mouth-ulcers', r'^lasts longer than 3 weeks$', L('An ulcer lasting more than 3 weeks needs to be checked by a dentist or doctor.', 'القرحة التي تستمر أكثر من 3 أسابيع تحتاج فحصاً من طبيب أسنان أو طبيب.', 'برینێک کە زیاتر لە ٣ هەفتە بمێنێتەوە پێویستی بە پشکنینی ددانساز یان پزیشک هەیە.'))])
condition('broken_tooth', L('Chipped or cracked tooth', 'سن مكسور أو متشقق', 'ددانی شکاو یان درزبردوو'), ['mouth.teeth'], 'dentist_soon', ['nhs-broken-tooth'], [
    F('sym:broken_tooth', 'typical', 'nhs-broken-tooth', r'chipped, cracked or broken a tooth')])
condition('wisdom_tooth', L('Wisdom tooth problem', 'مشكلة في ضرس العقل', 'کێشەی ددانی عەقڵ'), ['tooth.fdi.18', 'tooth.fdi.28', 'tooth.fdi.38', 'tooth.fdi.48', 'mouth.gums'], 'dentist_soon', ['nhs-wisdom-teeth'], [
    F('sym:pain', 'typical', 'nhs-wisdom-teeth', r'^pain and swelling$'), F('sym:swelling', 'common', 'nhs-wisdom-teeth', r'^pain and swelling$'), F('sym:toothache', 'common', 'nhs-wisdom-teeth', r'^pain and swelling$')],
    requires_anatomy=True)
condition('orthodontic', L('Tooth alignment or bite concern (orthodontic)', 'مشكلة في اصطفاف الأسنان أو العضة (تقويم)', 'کێشەی ڕیزبوونی ددان یان گەستن (ڕاستکردنەوە)'), ['mouth.bite', 'mouth.teeth'], 'orthodontist', ['nhs-orthodontics'], [
    F('sym:crowding', 'typical', 'nhs-orthodontics', r'growing too close together or they stick out'), F('sym:bite_problem', 'typical', 'nhs-orthodontics', r'do not meet properly'),
    F('sym:spacing', 'typical', 'nhs-orthodontics', r'large gaps between your teeth'), F('sym:braces_problem', 'common', 'nhs-orthodontics', r'your braces are broken')],
    scope_note=L('Educational only. Tooth movement, forces, extractions and treatment plans need an orthodontist and clinical records.', 'تعليمي فقط. تحريك الأسنان والقوى والخلع وخطط العلاج تحتاج أخصائي تقويم وسجلات سريرية.', 'تەنها فێرکاری. جووڵاندنی ددان، هێز، هەڵکێشان و پلانی چارەسەر پێویستیان بە پسپۆڕی ڕاستکردنەوە و تۆماری کلینیکی هەیە.'))

# ---- chest
condition('costochondritis', L('Costochondritis (chest-wall inflammation)', 'التهاب الغضروف الضلعي', 'هەوکردنی کڕکڕاگەی پەراسوو'), ['chest.chest-wall'], 'gp_soon', ['nhs-costochondritis'], [
    F('sym:chest_pain', 'typical', 'nhs-costochondritis', r'sharp pain in the front or side'), F('attr:character=sharp', 'common', 'nhs-costochondritis', r'sharp pain in the front'),
    F('sym:tender_on_press', 'typical', 'nhs-costochondritis', r'press the middle of your chest'), F('trig:movement', 'common', 'nhs-costochondritis', r'moving your upper body'),
    F('trig:breathing', 'common', 'nhs-costochondritis', r'^breathing deeply$'), F('trig:lying_down', 'possible', 'nhs-costochondritis', r'^lying down$')],
    scope_note=L('Chest pain always needs a clinician to rule out heart and lung causes.', 'ألم الصدر يحتاج دائماً إلى طبيب لاستبعاد أسباب القلب والرئة.', 'ئازاری سنگ هەمیشە پێویستی بە پزیشک هەیە بۆ دوورخستنەوەی هۆکاری دڵ و سی.'))
condition('acid_reflux', L('Heartburn / acid reflux', 'الحرقة / الارتجاع الحمضي', 'ترشێتی / گەڕانەوەی ترشی گەدە'), ['chest.oesophagus', 'abdomen.upper-central'], 'pharmacist', ['nhs-heartburn'], [
    F('sym:heartburn', 'typical', 'nhs-heartburn', r'heartburn – a burning sensation'), F('attr:character=burning', 'typical', 'nhs-heartburn', r'heartburn – a burning sensation'),
    F('sym:bad_taste_breath', 'common', 'nhs-heartburn', r'unpleasant sour taste'), F('sym:cough', 'possible', 'nhs-heartburn', r'cough or hiccups'), F('sym:hoarse_voice', 'possible', 'nhs-heartburn', r'^a hoarse voice$'),
    F('sym:bloating', 'possible', 'nhs-heartburn', r'bloating and feeling sick'), F('trig:eating', 'common', 'nhs-heartburn', r'worse after eating'), F('trig:lying_down', 'common', 'nhs-heartburn', r'when lying down')])
condition('chest_infection', L('Chest infection', 'التهاب الصدر', 'هەوکردنی سنگ'), ['chest.lungs'], 'gp_soon', ['nhs-chest-infection'], [
    F('sym:cough', 'typical', 'nhs-chest-infection', r'a chesty cough'), F('sym:shortness_of_breath', 'common', 'nhs-chest-infection', r'wheezing and shortness of breath'),
    F('sym:chest_pain', 'common', 'nhs-chest-infection', r'chest pain or discomfort'), F('sym:fever', 'common', 'nhs-chest-infection', r'^a high temperature$'), F('sym:headache', 'possible', 'nhs-chest-infection', r'^a headache$')])
condition('palpitations', L('Heart palpitations (often harmless)', 'خفقان القلب (غالباً غير ضار)', 'دڵەکوتێ (زۆرجار بێزیان)'), ['chest.heart'], 'gp_routine', ['nhs-palpitations'], [
    F('sym:palpitations', 'typical', 'nhs-palpitations', r'^racing or beating very fast$'), F('attr:pattern=intermittent', 'common', 'nhs-palpitations', r'can last seconds, minutes or longer'),
    F('trig:stress', 'common', 'nhs-palpitations', r'^stress and anxiety$'), F('trig:exertion', 'common', 'nhs-palpitations', r'^strenuous exercise$')],
    [A('sym:chest_pain', 'strong', 'nhs-palpitations', r'^chest pain$', L('Palpitations with chest pain need emergency care.', 'الخفقان مع ألم الصدر يحتاج رعاية طارئة.', 'دڵەکوتێ لەگەڵ ئازاری سنگ پێویستی بە فریاکەوتن هەیە.')),
     A('sym:shortness_of_breath', 'strong', 'nhs-palpitations', r'^shortness of breath$', L('Palpitations with breathlessness need emergency care.', 'الخفقان مع ضيق التنفس يحتاج رعاية طارئة.', 'دڵەکوتێ لەگەڵ هەناسەتەنگی پێویستی بە فریاکەوتن هەیە.')),
     A('sym:faint', 'strong', 'nhs-palpitations', r'feeling faint or fainting', L('Palpitations with fainting need emergency care.', 'الخفقان مع الإغماء يحتاج رعاية طارئة.', 'دڵەکوتێ لەگەڵ بووران پێویستی بە فریاکەوتن هەیە.'))])

# ---- abdomen
condition('indigestion', L('Indigestion', 'عسر الهضم', 'هەرسنەکردن'), ['abdomen.upper-central', 'chest.oesophagus'], 'pharmacist', ['nhs-indigestion'], [
    F('sym:heartburn', 'typical', 'nhs-indigestion', r'heartburn – a painful burning'), F('sym:bloating', 'common', 'nhs-indigestion', r'feeling full and bloated'), F('sym:nausea', 'common', 'nhs-indigestion', r'^feeling sick$'),
    F('trig:eating', 'typical', 'nhs-indigestion', r'after eating or drinking')],
    [A('sym:gi_bleeding', 'strong', 'nhs-indigestion', r'bloody vomit or poo', L('Blood in vomit or poo needs urgent assessment.', 'الدم في القيء أو البراز يحتاج تقييماً عاجلاً.', 'خوێن لە ڕشانەوە یان پیسایی پێویستی بە هەڵسەنگاندنی بەپەلە هەیە.')),
     A('sym:weight_loss', 'moderate', 'nhs-indigestion', r'lost a lot of weight', L('Unexplained weight loss needs a doctor’s assessment.', 'فقدان الوزن غير المبرر يحتاج تقييم طبيب.', 'دابەزینی کێشی بێهۆ پێویستی بە هەڵسەنگاندنی پزیشک هەیە.')),
     A('sym:swallowing_difficulty', 'moderate', 'nhs-indigestion', r'difficulty swallowing', L('Difficulty swallowing needs a doctor’s assessment.', 'صعوبة البلع تحتاج تقييم طبيب.', 'قورسی قووتدان پێویستی بە هەڵسەنگاندنی پزیشک هەیە.'))])
condition('constipation', L('Constipation', 'الإمساك', 'قەبزی'), ['abdomen.lower-central', 'abdomen.left-lower', 'abdomen.central', 'body.abdomen'], 'pharmacist', ['nhs-constipation'], [
    F('sym:constipation', 'typical', 'nhs-constipation', r'not had a poo at least 3 times'), F('sym:bloating', 'common', 'nhs-constipation', r'stomach ache and feel bloated'), F('sym:pain', 'possible', 'nhs-constipation', r'stomach ache and feel bloated')],
    [A('sym:gi_bleeding', 'strong', 'nhs-constipation', r'have blood in your poo', L('Blood in poo needs a doctor’s assessment.', 'الدم في البراز يحتاج تقييم طبيب.', 'خوێن لە پیسایی پێویستی بە هەڵسەنگاندنی پزیشک هەیە.')),
     A('sym:weight_loss', 'moderate', 'nhs-constipation', r'lost weight without trying', L('Unexplained weight loss needs a doctor’s assessment.', 'فقدان الوزن غير المبرر يحتاج تقييم طبيب.', 'دابەزینی کێشی بێهۆ پێویستی بە هەڵسەنگاندنی پزیشک هەیە.'))])
condition('gastroenteritis', L('Stomach bug (diarrhoea and vomiting)', 'التهاب المعدة والأمعاء (إسهال وتقيؤ)', 'هەوکردنی گەدە و ڕیخۆڵە (سکچوون و ڕشانەوە)'), ['body.abdomen', 'abdomen.central'], 'pharmacist', ['nhs-diarrhoea-vomiting'], [
    F('sym:diarrhoea', 'typical', 'nhs-diarrhoea-vomiting', r'^a stomach bug$'), F('sym:vomiting', 'typical', 'nhs-diarrhoea-vomiting', r'^a stomach bug$'), F('sym:nausea', 'common', 'nhs-diarrhoea-vomiting', r'^food poisoning$')],
    [A('sym:gi_bleeding', 'strong', 'nhs-diarrhoea-vomiting', r'bloody diarrhoea', L('Bloody diarrhoea needs urgent advice.', 'الإسهال الدموي يحتاج نصيحة عاجلة.', 'سکچوونی خوێناوی پێویستی بە ئامۆژگاری بەپەلە هەیە.')),
     A('attr:duration>=168', 'moderate', 'nhs-diarrhoea-vomiting', r'diarrhoea for more than 7 days', L('Diarrhoea lasting more than 7 days needs medical advice.', 'الإسهال لأكثر من 7 أيام يحتاج نصيحة طبية.', 'سکچوونی زیاتر لە ٧ ڕۆژ پێویستی بە ئامۆژگاری پزیشکی هەیە.'))])
condition('appendicitis', L('Appendicitis (needs urgent assessment)', 'التهاب الزائدة الدودية (يحتاج تقييماً عاجلاً)', 'هەوکردنی ڕیخۆڵەکوێرە (پێویستی بە هەڵسەنگاندنی بەپەلە هەیە)'), ['abdomen.right-lower', 'abdomen.central'], 'urgent_same_day', ['nhs-appendicitis'], [
    F('sym:pain', 'typical', 'nhs-appendicitis', r'start with pain in the middle'), F('sym:pain_moves_right_lower', 'typical', 'nhs-appendicitis', r'moves to the lower right side'),
    F('trig:movement', 'common', 'nhs-appendicitis', r'worse when you move, cough'), F('sym:nausea', 'common', 'nhs-appendicitis', r'feeling or being sick, or loss of appetite'),
    F('sym:fever', 'common', 'nhs-appendicitis', r'^a high temperature$'), F('attr:course=worsening', 'common', 'nhs-appendicitis', r'gradually getting worse')], urgent=True)
condition('gallstones', L('Gallstone pain (biliary colic)', 'ألم حصى المرارة', 'ئازاری بەردی زراو'), ['abdomen.right-upper', 'abdomen.upper-central'], 'gp_soon', ['nhs-gallstones'], [
    F('sym:pain', 'typical', 'nhs-gallstones', r'just under your ribs on the right'), F('attr:severity>=7', 'common', 'nhs-gallstones', r'^feel severe$'), F('attr:pattern=constant', 'common', 'nhs-gallstones', r'^be constant$'),
    F('attr:duration>=0.5', 'common', 'nhs-gallstones', r'longer than 30 minutes, and up to several hours'), F('sym:nausea', 'common', 'nhs-gallstones', r'make you feel sick or vomit')])
condition('ibs', L('Irritable bowel syndrome (IBS)', 'متلازمة القولون العصبي', 'سیندرۆمی ڕیخۆڵەی هەستیار'), ['body.abdomen', 'abdomen.central', 'abdomen.left-lower'], 'gp_routine', ['nhs-ibs'], [
    F('sym:pain', 'typical', 'nhs-ibs', r'stomach pain or cramps'), F('sym:bloating', 'typical', 'nhs-ibs', r'^bloating –'), F('sym:diarrhoea', 'common', 'nhs-ibs', r'^diarrhoea –'), F('sym:constipation', 'common', 'nhs-ibs', r'^constipation –'),
    F('attr:pattern=intermittent', 'common', 'nhs-ibs', r'days when your symptoms are better'), F('trig:eating', 'common', 'nhs-ibs', r'usually worse after eating')],
    [A('sym:gi_bleeding', 'strong', 'nhs-ibs', r'bloody diarrhoea', L('Bleeding is not explained by IBS and needs urgent review.', 'النزيف لا يفسّره القولون العصبي ويحتاج مراجعة عاجلة.', 'خوێنبەربوون بە IBS ڕوون ناکرێتەوە و پێویستی بە پشکنینی بەپەلە هەیە.')),
     A('sym:weight_loss', 'strong', 'nhs-ibs', r'lost a lot of weight for no reason', L('Unexplained weight loss needs urgent review.', 'فقدان الوزن غير المبرر يحتاج مراجعة عاجلة.', 'دابەزینی کێشی بێهۆ پێویستی بە پشکنینی بەپەلە هەیە.'))])
condition('uti', L('Urinary tract infection (UTI)', 'التهاب المسالك البولية', 'هەوکردنی ڕێڕەوی میز'), ['abdomen.lower-central'], 'pharmacist', ['nhs-uti'], [
    F('sym:urinary_burning', 'typical', 'nhs-uti', r'burning sensation when peeing'), F('sym:urinary_frequency', 'common', 'nhs-uti', r'^needing to pee more often than usual$'),
    F('sym:pain', 'common', 'nhs-uti', r'lower tummy pain'), F('sym:blood_in_urine', 'possible', 'nhs-uti', r'^blood in your pee$')],
    [A('sym:fever', 'moderate', 'nhs-uti', r'very high or low temperature', L('A high temperature with urinary symptoms needs an urgent doctor’s review.', 'الحرارة المرتفعة مع أعراض بولية تحتاج مراجعة طبية عاجلة.', 'پلەی گەرمی بەرز لەگەڵ نیشانەی میز پێویستی بە پشکنینی بەپەلەی پزیشک هەیە.'))])
condition('kidney_stones', L('Kidney stones', 'حصى الكلى', 'بەردی گورچیلە'), ['abdomen.flank', 'back.lower'], 'gp_soon', ['nhs-kidney-stones'], [
    F('sym:pain', 'typical', 'nhs-kidney-stones', r'starts in the side of your tummy'), F('attr:severity>=7', 'common', 'nhs-kidney-stones', r'can cause severe pain'),
    F('attr:pattern=intermittent', 'common', 'nhs-kidney-stones', r'may come and go'), F('sym:nausea', 'possible', 'nhs-kidney-stones', r'feeling sick \(nausea\)'),
    F('sym:urinary_frequency', 'possible', 'nhs-kidney-stones', r'^needing to pee often$')])

# ---- back, limbs, skin
condition('back_pain', L('Back pain (often a strain)', 'ألم الظهر (غالباً شدّ عضلي)', 'پشت ئێشە (زۆرجار ماسولکە)'), ['back.lower', 'back.upper'], 'pharmacist', ['nhs-back-pain'], [
    F('sym:pain', 'typical', 'nhs-back-pain', r'injury like a pulled muscle'), F('sym:injury', 'common', 'nhs-back-pain', r'injury like a pulled muscle')],
    [A('sym:weight_loss', 'strong', 'nhs-back-pain', r"you've lost weight without trying", L('Weight loss with back pain needs a doctor’s review.', 'فقدان الوزن مع ألم الظهر يحتاج مراجعة طبيب.', 'دابەزینی کێش لەگەڵ پشت ئێشە پێویستی بە پشکنینی پزیشک هەیە.')),
     A('sym:fever', 'moderate', 'nhs-back-pain', r'hot, cold, shivery or generally unwell', L('Feeling feverish with back pain needs urgent advice.', 'الحمى مع ألم الظهر تحتاج نصيحة عاجلة.', 'تا لەگەڵ پشت ئێشە پێویستی بە ئامۆژگاری بەپەلە هەیە.'))])
condition('sciatica', L('Sciatica', 'عرق النسا', 'دەماری ساتیک (عێرق النسا)'), ['back.lower', 'leg.thigh', 'leg.calf'], 'pharmacist', ['nhs-sciatica'], [
    F('sym:pain', 'typical', 'nhs-sciatica', r'sharp, burning pain down the back of the leg'), F('sym:numbness_tingling', 'common', 'nhs-sciatica', r'tingling – like pins and needles'),
    F('sym:weakness', 'possible', 'nhs-sciatica', r'^weakness$'), F('attr:character=sharp', 'common', 'nhs-sciatica', r'sharp, burning pain')])
condition('sprain', L('Sprain or strain', 'التواء أو شدّ عضلي', 'بادان یان کشانی ماسولکە'), ['arm.wrist', 'arm.hand', 'leg.ankle', 'leg.knee', 'arm.elbow', 'arm.shoulder', 'leg.foot'], 'pharmacist', ['nhs-sprains'], [
    F('sym:pain', 'typical', 'nhs-sprains', r'pain, tenderness or weakness'), F('sym:swelling', 'common', 'nhs-sprains', r'swollen or bruised'), F('sym:injury', 'typical', 'nhs-sprains', r'Torn or twisted ligament'),
    F('sym:cannot_bear_weight', 'possible', 'nhs-sprains', r'cannot put weight on the injury'), F('sym:cramp', 'possible', 'nhs-sprains', r'muscle spasms or cramping')],
    [A('sym:deformity', 'strong', 'nhs-sprains', r'changed shape or is pointing', L('A changed shape can mean a broken bone that needs an X-ray.', 'تغيّر الشكل قد يعني كسراً يحتاج أشعة.', 'گۆڕانی شێوە لەوانەیە مانای شکانی ئێسک بێت کە پێویستی بە تیشک هەیە.')),
     A('sym:crack_sound', 'strong', 'nhs-sprains', r'heard a crack', L('Hearing a crack can mean a broken bone.', 'سماع طقة قد يعني كسراً في العظم.', 'بیستنی دەنگی شکان لەوانەیە مانای شکانی ئێسک بێت.'))])
condition('carpal_tunnel', L('Carpal tunnel syndrome', 'متلازمة النفق الرسغي', 'سیندرۆمی تونێلی مەچەک'), ['arm.wrist', 'arm.hand'], 'gp_routine', ['nhs-carpal-tunnel'], [
    F('sym:numbness_tingling', 'typical', 'nhs-carpal-tunnel', r'tingling or pins and needles'), F('sym:pain', 'common', 'nhs-carpal-tunnel', r'ache or pain in your fingers, hand or arm'),
    F('sym:weakness', 'common', 'nhs-carpal-tunnel', r'weak thumb or difficulty gripping'), F('attr:pattern=intermittent', 'common', 'nhs-carpal-tunnel', r'start slowly and come and go'),
    F('attr:onset=gradual', 'common', 'nhs-carpal-tunnel', r'start slowly and come and go'), F('trig:night', 'common', 'nhs-carpal-tunnel', r'usually worse at night')])
condition('tennis_elbow', L('Tennis elbow', 'مرفق التنس', 'ئانیشکی تێنس'), ['arm.elbow', 'arm.forearm'], 'pharmacist', ['nhs-tennis-elbow'], [
    F('sym:pain', 'typical', 'nhs-tennis-elbow', r'pain on the outside of'), F('trig:movement', 'common', 'nhs-tennis-elbow', r'^gripping objects$'), F('sym:swelling', 'possible', 'nhs-tennis-elbow', r'tenderness or swelling')])
condition('frozen_shoulder', L('Frozen shoulder', 'الكتف المتجمد', 'شانی بەستوو'), ['arm.shoulder'], 'gp_routine', ['nhs-frozen-shoulder'], [
    F('sym:pain', 'typical', 'nhs-frozen-shoulder', r'pain in your shoulder which can be worse at night'), F('sym:stiffness', 'typical', 'nhs-frozen-shoulder', r'stiffness in your shoulder'),
    F('trig:night', 'common', 'nhs-frozen-shoulder', r'worse at night'), F('attr:onset=gradual', 'possible', 'nhs-frozen-shoulder', r'months or years to get better')])
condition('leg_cramps', L('Leg cramps', 'تشنجات الساق', 'گرژبوونی لاق'), ['leg.calf', 'leg.foot', 'leg.thigh'], 'pharmacist', ['nhs-leg-cramps'], [
    F('sym:cramp', 'typical', 'nhs-leg-cramps', r'muscle in the leg tightens'), F('sym:pain', 'common', 'nhs-leg-cramps', r'muscle in the leg tightens'),
    F('attr:duration<=0.17', 'common', 'nhs-leg-cramps', r'few seconds to 10 minutes'), F('trig:night', 'possible', 'nhs-leg-cramps', r'disturbing your sleep')],
    [A('sym:swelling', 'moderate', 'nhs-leg-cramps', r'numbness or swelling in your legs', L('Swelling is not typical of simple cramps and needs a doctor’s review.', 'التورم غير معتاد في التشنج البسيط ويحتاج مراجعة طبيب.', 'ئاوسان لە گرژبوونی سادەدا ئاسایی نیە و پێویستی بە پشکنینی پزیشک هەیە.'))])
condition('knee_injury', L('Knee strain or ligament injury', 'إصابة أربطة أو شدّ في الركبة', 'برینی بەستەر یان کشانی ئەژنۆ'), ['leg.knee'], 'gp_routine', ['nhs-knee-pain'], [
    F('sym:pain', 'typical', 'nhs-knee-pain', r'Pain after overstretching, overusing or twisting'), F('sym:injury', 'common', 'nhs-knee-pain', r'Pain after overstretching, overusing or twisting'),
    F('sym:joint_locking', 'common', 'nhs-knee-pain', r'Unstable, gives way'), F('sym:swelling', 'possible', 'nhs-knee-pain', r'badly swollen')])
condition('plantar_fasciitis', L('Plantar fasciitis (heel pain)', 'التهاب اللفافة الأخمصية (ألم الكعب)', 'هەوکردنی پەردەی بنی پێ (ئازاری پاژنە)'), ['leg.foot'], 'pharmacist', ['nhs-plantar-fasciitis'], [
    F('sym:pain', 'typical', 'nhs-plantar-fasciitis', r'pain on the bottom of your foot'), F('trig:morning', 'typical', 'nhs-plantar-fasciitis', r'first start walking after'),
    F('attr:course=improving', 'possible', 'nhs-plantar-fasciitis', r'gradually gets better when you start moving')])
condition('dvt', L('Deep vein thrombosis (DVT) — needs urgent assessment', 'تجلط الأوردة العميقة — يحتاج تقييماً عاجلاً', 'خوێنمەیینی دەماری قووڵ — پێویستی بە هەڵسەنگاندنی بەپەلە هەیە'), ['leg.calf', 'leg.thigh'], 'urgent_same_day', ['nhs-dvt'], [
    F('sym:pain', 'typical', 'nhs-dvt', r'throbbing pain in 1 leg'), F('sym:swelling', 'typical', 'nhs-dvt', r'^swelling in 1 leg'), F('sym:redness', 'common', 'nhs-dvt', r'red, blue or darkened skin'),
    F('attr:side=one', 'typical', 'nhs-dvt', r'rarely both legs')], urgent=True)
condition('hives', L('Hives (urticaria)', 'الشرى (الأرتيكاريا)', 'خورشتی پێست (هایڤز)'), ['skin.general', 'body.skin'], 'pharmacist', ['nhs-hives'], [
    F('sym:rash', 'typical', 'nhs-hives', r'main symptom of hives is an itchy rash'), F('sym:itch', 'typical', 'nhs-hives', r'main symptom of hives is an itchy rash')],
    [A('sym:face_lip_tongue_swelling', 'strong', 'nhs-hives', r'lips, mouth, throat or tongue suddenly become swollen', L('Swelling of the lips, tongue or throat can be anaphylaxis — an emergency.', 'تورم الشفاه أو اللسان أو الحلق قد يكون صدمة تحسسية — حالة طارئة.', 'ئاوسانی لێو، زمان یان گەروو لەوانەیە شۆکی هەستیاری بێت — فریاکەوتن.'))])
condition('contact_dermatitis', L('Contact dermatitis', 'التهاب الجلد التماسي', 'هەوکردنی پێستی بەرکەوتن'), ['skin.general', 'arm.hand', 'body.skin'], 'pharmacist', ['nhs-contact-dermatitis'], [
    F('sym:rash', 'typical', 'nhs-contact-dermatitis', r'skin to become itchy, bliste'), F('sym:itch', 'typical', 'nhs-contact-dermatitis', r'skin to become itchy, bliste'),
    F('sym:redness', 'common', 'nhs-contact-dermatitis', r'Lighter skin can become red')])

# =====================================================================================================
# Red flags. when: list of clauses, all must hold; a clause is "a|b|c" (any). Clause items use the same
# match syntax as conditions, plus "@<anatomy-id>" to require the anatomy (or a descendant) on the fact/case.
# =====================================================================================================
RED_FLAGS = []


def flag(identifier, urgency, pathway, when, src, ev, reason, *, scope=None, screen=None):
    RED_FLAGS.append({'id': identifier, 'urgency': urgency, 'pathway': pathway, 'when': when, 'scope': scope or [], 'source': src, 'ev': ev, 'reason': reason,
                      'screen_label': screen, 'review_status': 'draft — clinician review pending'})


flag('chest-pain-spreading', 'emergency', 'emergency', ['sym:chest_pain', 'sym:radiating_pain'], 'nhs-chest-pain', r'pain that spreads to your left or right arm',
     L('Chest pain spreading to the arm, jaw, neck or back can be a heart attack.', 'ألم الصدر الذي ينتشر إلى الذراع أو الفك أو الرقبة أو الظهر قد يكون نوبة قلبية.', 'ئازاری سنگ کە بڵاو دەبێتەوە بۆ باڵ، شەویلگە، مل یان پشت لەوانەیە جەڵتەی دڵ بێت.'),
     screen=L('Chest pain spreading to the arm, jaw, neck or back', 'ألم صدر ينتشر إلى الذراع أو الفك أو الرقبة', 'ئازاری سنگ بڵاو دەبێتەوە بۆ باڵ یان شەویلگە یان مل'))
flag('chest-pain-with-symptoms', 'emergency', 'emergency', ['sym:chest_pain', 'sym:sweating|sym:nausea|sym:vomiting|sym:shortness_of_breath|sym:dizziness'], 'nhs-chest-pain', r'feel sweaty, sick, light',
     L('Chest pain with sweating, sickness, light-headedness or breathlessness needs emergency care.', 'ألم الصدر مع التعرق أو الغثيان أو الدوخة أو ضيق التنفس يحتاج رعاية طارئة.', 'ئازاری سنگ لەگەڵ ئارەقکردنەوە، هێڵنج، سەرسووڕان یان هەناسەتەنگی پێویستی بە فریاکەوتن هەیە.'),
     screen=L('Chest pain with sweating, feeling sick or breathless', 'ألم صدر مع تعرق أو غثيان أو ضيق تنفس', 'ئازاری سنگ لەگەڵ ئارەق، هێڵنج یان هەناسەتەنگی'))
flag('chest-pain-sudden', 'emergency', 'emergency', ['sym:chest_pain', 'attr:onset=sudden'], 'nhs-chest-pain', r'sudden pain or discomfort in your chest',
     L('Sudden chest pain needs emergency assessment.', 'ألم الصدر المفاجئ يحتاج تقييماً طارئاً.', 'ئازاری لەناکاوی سنگ پێویستی بە هەڵسەنگاندنی فریاکەوتن هەیە.'))
flag('chest-pressure', 'emergency', 'emergency', ['sym:chest_pain', 'attr:character=pressure'], 'nhs-heart-attack', r'chest pain that feels tight or like squeezing',
     L('Tight, heavy or squeezing chest pain can be a heart attack.', 'ألم الصدر الضاغط أو الثقيل قد يكون نوبة قلبية.', 'ئازاری گوشاری یان قورسی سنگ لەوانەیە جەڵتەی دڵ بێت.'))
flag('severe-breathing', 'emergency', 'emergency', ['sym:breathing_severe'], 'nhs-shortness-of-breath', r'severe difficulty breathing',
     L('Severe difficulty breathing is an emergency.', 'صعوبة التنفس الشديدة حالة طارئة.', 'هەناسەدانی زۆر قورس فریاکەوتنە.'),
     screen=L('Severe difficulty breathing', 'صعوبة شديدة في التنفس', 'هەناسەدانی زۆر قورس'))
flag('sudden-breathlessness', 'emergency', 'emergency', ['sym:shortness_of_breath', 'attr:onset=sudden'], 'nhs-pulmonary-embolism', r'difficulty breathing which comes on suddenly',
     L('Breathlessness that comes on suddenly can be a blood clot in the lungs.', 'ضيق التنفس المفاجئ قد يكون جلطة في الرئة.', 'هەناسەتەنگی لەناکاو لەوانەیە خوێنمەیین لە سی بێت.'))
flag('blue-lips', 'emergency', 'emergency', ['sym:pale_blue_skin'], 'nhs-shortness-of-breath', r'lips or skin are turning very pale',
     L('Blue, grey or very pale lips or skin is an emergency sign.', 'زرقة أو شحوب شديد في الشفاه أو الجلد علامة طارئة.', 'لێو یان پێستی شین یان زۆر زەرد نیشانەی فریاکەوتنە.'))
flag('stroke-face-speech', 'emergency', 'emergency', ['sym:face_droop|sym:speech_problem'], 'nhs-stroke-symptoms', r'face weakness',
     L('Face drooping or speech problems can be a stroke. Call emergency services now (FAST).', 'تدلّي الوجه أو مشاكل الكلام قد تكون جلطة دماغية. اتصل بالطوارئ الآن.', 'لاربوونی دەموچاو یان کێشەی قسەکردن لەوانەیە جەڵتەی مێشک بێت. ئێستا پەیوەندی بە فریاکەوتنەوە بکە.'),
     screen=L('Face drooping, slurred speech or new arm weakness', 'تدلّي الوجه أو تلعثم أو ضعف جديد في الذراع', 'لاربوونی دەموچاو، تێکچوونی قسە یان لاوازی نوێی باڵ'))
flag('stroke-sudden-weakness', 'emergency', 'emergency', ['sym:weakness|sym:numbness_tingling', 'attr:onset=sudden'], 'nhs-stroke-symptoms', r'weakness or numbness down 1 side',
     L('Sudden weakness or numbness can be a stroke.', 'الضعف أو الخدر المفاجئ قد يكون جلطة دماغية.', 'لاوازی یان سڕبوونی لەناکاو لەوانەیە جەڵتەی مێشک بێت.'))
flag('thunderclap-headache', 'emergency', 'emergency', ['sym:headache', 'attr:onset=sudden', 'attr:severity>=8'], 'nhs-headaches', r'started suddenly and is extremely painful',
     L('A sudden, extremely painful headache needs emergency care.', 'الصداع المفاجئ الشديد جداً يحتاج رعاية طارئة.', 'سەرئێشەی لەناکاوی زۆر توند پێویستی بە فریاکەوتن هەیە.'),
     screen=L('Sudden, extremely severe headache', 'صداع مفاجئ وشديد جداً', 'سەرئێشەی لەناکاو و زۆر توند'))
flag('worst-headache', 'emergency', 'emergency', ['sym:headache', 'attr:severity>=10'], 'nhs-headaches', r'started suddenly and is extremely painful',
     L('A worst-ever headache needs emergency care.', 'أسوأ صداع في حياتك يحتاج رعاية طارئة.', 'خراپترین سەرئێشەی ژیانت پێویستی بە فریاکەوتن هەیە.'))
flag('headache-neuro', 'emergency', 'emergency', ['sym:headache', 'sym:weakness|sym:numbness_tingling|sym:confusion|sym:seizure|sym:vision_loss|sym:speech_problem'], 'nhs-headaches', r'numbness or weakness in the body or face',
     L('A headache with weakness, numbness, confusion, seizure, speech or vision loss needs emergency care.', 'الصداع مع ضعف أو خدر أو تشوش أو نوبة أو فقدان كلام أو بصر يحتاج رعاية طارئة.', 'سەرئێشە لەگەڵ لاوازی، سڕبوون، سەرلێشێواوی، فێ یان لەدەستدانی قسە یان بینین پێویستی بە فریاکەوتن هەیە.'))
flag('headache-head-injury', 'emergency', 'emergency', ['sym:headache', 'sym:injury'], 'nhs-headaches', r'head injury within the last 3 months',
     L('A headache after a head injury needs emergency assessment.', 'الصداع بعد إصابة في الرأس يحتاج تقييماً طارئاً.', 'سەرئێشە دوای برینی سەر پێویستی بە هەڵسەنگاندنی فریاکەوتن هەیە.'), screen=L('A recent head injury', 'إصابة حديثة في الرأس', 'برینێکی نوێی سەر'))
flag('meningitis-signs', 'emergency', 'emergency', ['sym:stiff_neck', 'sym:headache|sym:fever|sym:light_sensitivity'], 'nhs-meningitis', r'stiff neck and cannot look at bright lights',
     L('A stiff neck with headache, fever or light sensitivity can be meningitis.', 'تيبّس الرقبة مع صداع أو حمى أو حساسية للضوء قد يكون التهاب السحايا.', 'ڕەقبوونی مل لەگەڵ سەرئێشە، تا یان هەستیاری بە ڕووناکی لەوانەیە مەنەنجایتس بێت.'),
     screen=L('Stiff neck with fever or a rash that does not fade', 'تيبّس الرقبة مع حمى أو طفح لا يختفي', 'ڕەقبوونی مل لەگەڵ تا یان پەڵەیەک کە ون نابێت'))
flag('non-blanching-rash', 'emergency', 'emergency', ['sym:non_blanching_rash'], 'nhs-meningitis', r'rash that does not fade when you press',
     L('A rash that does not fade when pressed can be a sign of serious infection.', 'الطفح الذي لا يختفي عند الضغط قد يكون علامة عدوى خطيرة.', 'پەڵەیەک کە بە گوشار ون نابێت لەوانەیە نیشانەی هەوکردنێکی مەترسیدار بێت.'))
flag('seizure', 'emergency', 'emergency', ['sym:seizure'], 'nhs-meningitis', r'seizure \(fit\) for the first time',
     L('A first seizure needs emergency care.', 'النوبة التشنجية الأولى تحتاج رعاية طارئة.', 'یەکەم فێ پێویستی بە فریاکەوتن هەیە.'))
flag('confusion', 'emergency', 'emergency', ['sym:confusion'], 'nhs-uti', r'confused, drowsy',
     L('New confusion or drowsiness needs emergency care.', 'التشوش أو النعاس الجديد يحتاج رعاية طارئة.', 'سەرلێشێواوی یان خەواڵوویی نوێ پێویستی بە فریاکەوتن هەیە.'))
flag('sepsis-signs', 'emergency', 'emergency', ['sym:fever', 'sym:confusion|sym:breathing_severe|sym:pale_blue_skin|sym:non_blanching_rash'], 'nhs-sepsis', r'confusion or slurred speech',
     L('Fever with confusion, breathing difficulty, discoloured skin or a non-fading rash can be sepsis.', 'الحمى مع تشوش أو صعوبة تنفس أو تغير لون الجلد أو طفح لا يختفي قد تكون إنتاناً.', 'تا لەگەڵ سەرلێشێواوی، هەناسەتەنگی، گۆڕانی ڕەنگی پێست یان پەڵەی ون نەبوو لەوانەیە سێپسیس بێت.'))
flag('vision-loss', 'emergency', 'eye_emergency', ['sym:vision_loss'], 'nhs-vision-loss', r'suddenly cannot see from 1 or both eyes',
     L('Loss of vision needs emergency eye care.', 'فقدان البصر يحتاج رعاية طارئة للعين.', 'لەدەستدانی بینین پێویستی بە فریاکەوتنی چاو هەیە.'),
     screen=L('Sudden loss of vision', 'فقدان مفاجئ للبصر', 'لەدەستدانی لەناکاوی بینین'))
flag('sudden-severe-eye-pain', 'emergency', 'eye_emergency', ['sym:pain@body.eyes', 'attr:severity>=7'], 'nhs-vision-loss', r'suddenly have severe eye pain',
     L('Severe eye pain needs emergency eye care.', 'ألم العين الشديد يحتاج رعاية طارئة للعين.', 'ئازاری توندی چاو پێویستی بە فریاکەوتنی چاو هەیە.'), screen=L('Severe eye pain', 'ألم شديد في العين', 'ئازاری توندی چاو'))
flag('red-eye-danger', 'emergency', 'eye_emergency', ['sym:redness@body.eyes', 'sym:light_sensitivity|sym:blurred_vision|sym:halos|sym:uneven_pupils'], 'nhs-red-eye', r'hurts to look at light',
     L('A red eye with vision changes, light sensitivity, haloes or unequal pupils needs emergency care.', 'احمرار العين مع تغير الرؤية أو الحساسية للضوء أو الهالات أو اختلاف البؤبؤ يحتاج رعاية طارئة.', 'سووربوونەوەی چاو لەگەڵ گۆڕانی بینین، هەستیاری بە ڕووناکی، بازنەی ڕەنگاوڕەنگ یان جیاوازی بیلبیلە پێویستی بە فریاکەوتن هەیە.'))
flag('red-eye-headache-sick', 'emergency', 'eye_emergency', ['sym:redness@body.eyes', 'sym:headache', 'sym:nausea|sym:vomiting'], 'nhs-red-eye', r'severe headache and feel sick',
     L('A red eye with a severe headache and sickness can be sudden glaucoma.', 'احمرار العين مع صداع شديد وغثيان قد يكون زرقاً حاداً.', 'سووربوونەوەی چاو لەگەڵ سەرئێشەی توند و هێڵنج لەوانەیە گلۆکۆمای لەناکاو بێت.'))
flag('eye-injury', 'emergency', 'eye_emergency', ['sym:injury@body.eyes|sym:chemical_exposure@body.eyes'], 'nhs-red-eye', r'injured your eye, or something is stuck',
     L('An eye injury or chemical in the eye needs emergency care. Rinse chemicals with clean water while getting help.', 'إصابة العين أو دخول مادة كيميائية فيها يحتاج رعاية طارئة. اغسل المادة بماء نظيف أثناء طلب المساعدة.', 'برینی چاو یان چوونی ماددەی کیمیایی بۆ ناو چاو پێویستی بە فریاکەوتن هەیە. لە کاتی داوای یارمەتیدا بە ئاوی پاک بیشۆ.'),
     screen=L('Eye injury or chemical in the eye', 'إصابة في العين أو مادة كيميائية فيها', 'برینی چاو یان ماددەی کیمیایی لە چاو'))
flag('curtain-shadow', 'same_day', 'eye_urgent', ['sym:curtain_shadow'], 'nhs-floaters', r'dark "curtain" or shadow moving',
     L('A dark curtain or shadow across vision can mean the retina is detaching. Get checked today.', 'الستارة أو الظل الداكن على الرؤية قد يعني انفصال الشبكية. افحص اليوم.', 'پەردە یان سێبەری تاریک لەسەر بینین لەوانەیە جیابوونەوەی تۆڕینە بێت. ئەمڕۆ بپشکنە.'),
     screen=L('A dark curtain or shadow over your vision', 'ستارة أو ظل داكن على الرؤية', 'پەردە یان سێبەرێکی تاریک بەسەر بینینتدا'))
flag('new-floaters', 'same_day', 'eye_urgent', ['sym:flashes_floaters', 'attr:onset=sudden'], 'nhs-floaters', r'suddenly get floaters or flashes',
     L('New or sudden floaters or flashes need an urgent eye check today.', 'الأجسام العائمة أو الومضات الجديدة أو المفاجئة تحتاج فحصاً عاجلاً اليوم.', 'پەڵە یان بریسکەی نوێ یان لەناکاو پێویستی بە پشکنینی بەپەلەی چاو هەیە ئەمڕۆ.'),
     screen=L('New flashes of light or a sudden shower of floaters', 'ومضات جديدة أو أجسام عائمة مفاجئة', 'بریسکەی نوێ یان پەڵەی لەناکاو'))
flag('eye-pain', 'same_day', 'eye_urgent', ['sym:pain@body.eyes!eyelid'], 'nhs-conjunctivitis', r'^pain in your eyes$',
     L('Eye pain can be a sign of a more serious eye problem and needs an urgent check.', 'ألم العين قد يكون علامة على مشكلة أخطر ويحتاج فحصاً عاجلاً.', 'ئازاری چاو لەوانەیە نیشانەی کێشەیەکی جددیتر بێت و پێویستی بە پشکنینی بەپەلە هەیە.'))
flag('eyelid-very-painful', 'same_day', 'urgent_same_day', ['sym:pain@body.eyes', 'attr:severity>=7'], 'nhs-stye', r'a stye is very painful or swollen',
     L('A very painful or swollen eyelid needs an urgent doctor’s review today.', 'الجفن شديد الألم أو التورم يحتاج مراجعة طبية عاجلة اليوم.', 'پێڵووی زۆر بە ئازار یان ئاوساو پێویستی بە پشکنینی بەپەلەی پزیشک هەیە ئەمڕۆ.'))
flag('eye-light-sensitivity', 'same_day', 'eye_urgent', ['sym:light_sensitivity'], 'nhs-conjunctivitis', r'^sensitivity to light$',
     L('Sensitivity to light can be a sign of a more serious eye problem.', 'الحساسية للضوء قد تكون علامة على مشكلة أخطر في العين.', 'هەستیاری بە ڕووناکی لەوانەیە نیشانەی کێشەیەکی جددیتری چاو بێت.'), scope=['body.eyes'], screen=L('Light hurts your eyes', 'الضوء يؤلم عينيك', 'ڕووناکی ئازاری چاوت دەدات'))
flag('eye-vision-change', 'same_day', 'eye_urgent', ['sym:blurred_vision|sym:double_vision'], 'nhs-conjunctivitis', r'changes in your vision',
     L('A change in vision needs an urgent eye check.', 'تغيّر الرؤية يحتاج فحصاً عاجلاً للعين.', 'گۆڕانی بینین پێویستی بە پشکنینی بەپەلەی چاو هەیە.'))
flag('red-eye-contact-lens', 'same_day', 'eye_urgent', ['sym:redness@body.eyes', 'sym:contact_lens'], 'nhs-red-eye', r'wear contact lenses',
     L('A red eye in a contact-lens wearer can be a corneal infection and needs an urgent check.', 'احمرار العين لدى مستخدم العدسات اللاصقة قد يكون عدوى في القرنية ويحتاج فحصاً عاجلاً.', 'سووربوونەوەی چاو لای بەکارهێنەری لێنز لەوانەیە هەوکردنی قەرنیە بێت و پێویستی بە پشکنینی بەپەلە هەیە.'))
flag('dental-airway', 'emergency', 'emergency', ['sym:swelling|sym:toothache|sym:pain@body.mouth', 'sym:breathing_severe|sym:shortness_of_breath|sym:swallowing_difficulty|sym:speech_problem'], 'nhs-dental-abscess', r'hard to breathe, speak or swallow',
     L('Mouth or face swelling affecting breathing, swallowing or speaking is an emergency.', 'تورم الفم أو الوجه الذي يؤثر على التنفس أو البلع أو الكلام حالة طارئة.', 'ئاوسانی دەم یان دەموچاو کە کاریگەری لەسەر هەناسەدان، قووتدان یان قسەکردن هەبێت فریاکەوتنە.'),
     scope=['body.mouth'], screen=L('Difficulty breathing, swallowing or speaking', 'صعوبة في التنفس أو البلع أو الكلام', 'قورسی هەناسەدان، قووتدان یان قسەکردن'))
flag('dental-mouth-opening', 'emergency', 'emergency', ['sym:difficulty_opening_mouth', 'sym:swelling|sym:toothache|sym:pain'], 'nhs-dental-abscess', r'finding it hard to open your mouth',
     L('Difficulty opening the mouth with swelling or tooth pain needs emergency care.', 'صعوبة فتح الفم مع تورم أو ألم أسنان تحتاج رعاية طارئة.', 'قورسی کردنەوەی دەم لەگەڵ ئاوسان یان ددانئێشە پێویستی بە فریاکەوتن هەیە.'),
     scope=['body.mouth'], screen=L('A lot of swelling or difficulty opening your mouth', 'تورم كبير أو صعوبة فتح الفم', 'ئاوسانی زۆر یان قورسی کردنەوەی دەم'))
flag('dental-swelling', 'same_day', 'dentist_urgent', ['sym:swelling', 'sym:toothache|sym:pain|sym:fever|sym:bad_taste_breath'], 'nhs-dental-abscess', r'think you have a dental abscess',
     L('Tooth or gum pain with swelling can be a dental abscess and needs an urgent dentist.', 'ألم السن أو اللثة مع تورم قد يكون خراجاً ويحتاج طبيب أسنان عاجلاً.', 'ددانئێشە یان ئازاری پووک لەگەڵ ئاوسان لەوانەیە کێم بێت و پێویستی بە ددانسازی بەپەلە هەیە.'), scope=['body.mouth'])
flag('knocked-out-tooth', 'same_day', 'dentist_urgent', ['sym:knocked_out_tooth'], 'nhs-knocked-out-tooth', r'knocked out a tooth, even if you cannot find it',
     L('A knocked-out adult tooth needs an emergency dental appointment — time matters.', 'السن البالغ الذي سقط بسبب ضربة يحتاج موعد أسنان طارئ — الوقت مهم.', 'ددانی گەورەی دەرهاتوو بە زەبر پێویستی بە کاتی فریاکەوتنی ددان هەیە — کات گرنگە.'),
     screen=L('A knocked-out tooth', 'سن سقط بسبب ضربة', 'ددانێکی دەرهاتوو بە زەبر'))
flag('mouth-ulcer-3-weeks', 'soon', 'dentist_soon', ['sym:mouth_ulcer', 'attr:duration>=504'], 'nhs-mouth-cancer', r'mouth ulcer that has lasted more than 3 weeks',
     L('A mouth ulcer lasting more than 3 weeks should be examined by a dentist or doctor. Most have harmless causes; a chat or photo cannot confirm or rule out cancer.', 'قرحة الفم التي تستمر أكثر من 3 أسابيع يجب أن يفحصها طبيب أسنان أو طبيب. معظمها لأسباب غير ضارة؛ المحادثة أو الصورة لا تؤكد السرطان ولا تنفيه.', 'برینی دەم کە زیاتر لە ٣ هەفتە بمێنێتەوە دەبێت ددانساز یان پزیشک بیپشکنێت. زۆربەیان هۆکاری بێزیانیان هەیە؛ گفتوگۆ یان وێنە ناتوانێت شێرپەنجە دووپات یان ڕەت بکاتەوە.'))
flag('mouth-patch-lump', 'soon', 'dentist_soon', ['sym:mouth_patch|sym:lump'], 'nhs-mouth-cancer', r'lump in your mouth, on your lip',
     L('A red or white patch or a lump in the mouth should be examined by a dentist or doctor. A chat or photo cannot confirm or rule out cancer.', 'البقعة الحمراء أو البيضاء أو الكتلة في الفم يجب أن يفحصها طبيب أسنان أو طبيب. المحادثة أو الصورة لا تؤكد السرطان ولا تنفيه.', 'پەڵەی سوور یان سپی یان گرێ لە دەم دەبێت ددانساز یان پزیشک بیپشکنێت. گفتوگۆ یان وێنە ناتوانێت شێرپەنجە دووپات یان ڕەت بکاتەوە.'), scope=['body.mouth'])
flag('abdominal-sudden-severe', 'emergency', 'emergency', ['sym:pain@body.abdomen', 'attr:onset=sudden', 'attr:severity>=7'], 'nhs-stomach-ache', r'started suddenly and is severe',
     L('Sudden, severe abdominal pain needs emergency care.', 'ألم البطن المفاجئ الشديد يحتاج رعاية طارئة.', 'ئازاری لەناکاو و توندی سک پێویستی بە فریاکەوتن هەیە.'),
     screen=L('Sudden, severe tummy pain', 'ألم بطن مفاجئ وشديد', 'ئازاری لەناکاو و توندی سک'))
flag('gi-bleeding', 'emergency', 'emergency', ['sym:gi_bleeding'], 'nhs-stomach-ache', r"vomiting blood or your vomit looks green",
     L('Vomiting blood or passing black or bloody stools needs emergency care.', 'تقيؤ الدم أو البراز الأسود أو الدموي يحتاج رعاية طارئة.', 'ڕشانەوەی خوێن یان پیسایی ڕەش یان خوێناوی پێویستی بە فریاکەوتن هەیە.'),
     screen=L('Vomiting blood, or black or bloody poo', 'تقيؤ دم أو براز أسود أو دموي', 'ڕشانەوەی خوێن یان پیسایی ڕەش یان خوێناوی'))
flag('jaundice-pain', 'emergency', 'emergency', ['sym:yellow_skin_eyes', 'sym:pain'], 'nhs-gallstones', r'white part of your eyes looks yellow',
     L('Yellow skin or eyes with tummy pain needs emergency care.', 'اصفرار الجلد أو العينين مع ألم البطن يحتاج رعاية طارئة.', 'زەردبوونی پێست یان چاو لەگەڵ ئازاری سک پێویستی بە فریاکەوتن هەیە.'), screen=L('Yellow skin or eyes', 'اصفرار الجلد أو العينين', 'زەردبوونی پێست یان چاو'))
flag('jaundice', 'same_day', 'urgent_same_day', ['sym:yellow_skin_eyes'], 'nhs-gallstones', r'white part of your eyes looks yellow',
     L('Yellow skin or eyes needs to be checked by a doctor today.', 'اصفرار الجلد أو العينين يحتاج فحصاً طبياً اليوم.', 'زەردبوونی پێست یان چاو پێویستی بە پشکنینی پزیشک هەیە ئەمڕۆ.'))
flag('appendicitis-pattern', 'same_day', 'urgent_same_day', ['sym:pain_moves_right_lower'], 'nhs-appendicitis', r'moves to the lower right side',
     L('Pain moving to the lower right of the tummy can be appendicitis.', 'الألم الذي ينتقل إلى أسفل يمين البطن قد يكون التهاب الزائدة.', 'ئازارێک کە دەگوازرێتەوە بۆ خوارەوەی ڕاستی سک لەوانەیە ڕیخۆڵەکوێرە بێت.'))
flag('abdominal-pain-fever', 'same_day', 'urgent_same_day', ['sym:pain@body.abdomen', 'sym:fever'], 'nhs-appendicitis', r'^a high temperature$',
     L('Tummy pain with a high temperature needs an urgent assessment.', 'ألم البطن مع حرارة مرتفعة يحتاج تقييماً عاجلاً.', 'ئازاری سک لەگەڵ پلەی گەرمی بەرز پێویستی بە هەڵسەنگاندنی بەپەلە هەیە.'), screen=L('High temperature with tummy pain', 'حرارة مرتفعة مع ألم البطن', 'پلەی گەرمی بەرز لەگەڵ ئازاری سک'))
flag('cauda-equina', 'emergency', 'emergency', ['sym:saddle_bladder'], 'nhs-back-pain', r'loss of feeling around your genitals',
     L('Numbness around the genitals or new bladder or bowel problems with back pain is an emergency.', 'الخدر حول الأعضاء التناسلية أو مشاكل جديدة في البول أو البراز مع ألم الظهر حالة طارئة.', 'سڕبوون لە دەوری ئەندامی زاوزێ یان کێشەی نوێی میز یان پیسایی لەگەڵ پشت ئێشە فریاکەوتنە.'),
     screen=L('Numbness around the genitals or new bladder/bowel problems', 'خدر حول الأعضاء التناسلية أو مشاكل جديدة في البول أو البراز', 'سڕبوونی دەوری ئەندامی زاوزێ یان کێشەی نوێی میز/پیسایی'))
flag('back-both-legs', 'emergency', 'emergency', ['sym:numbness_tingling|sym:weakness', 'attr:side=both'], 'nhs-back-pain', r'tingling, weakness or numbness in both legs',
     L('Back pain with numbness or weakness in both legs is an emergency.', 'ألم الظهر مع خدر أو ضعف في الساقين كلتيهما حالة طارئة.', 'پشت ئێشە لەگەڵ سڕبوون یان لاوازی لە هەردوو لاق فریاکەوتنە.'), scope=['body.back', 'body.legs'])
flag('dvt-breathing', 'emergency', 'emergency', ['sym:pain|sym:swelling', 'sym:shortness_of_breath|sym:chest_pain'], 'nhs-dvt', r'feel short of breath',
     L('Leg pain or swelling with breathlessness or chest pain can be a clot that has reached the lungs.', 'ألم أو تورم الساق مع ضيق تنفس أو ألم صدر قد يكون جلطة وصلت إلى الرئة.', 'ئازار یان ئاوسانی لاق لەگەڵ هەناسەتەنگی یان ئازاری سنگ لەوانەیە خوێنمەیینێک بێت کە گەیشتۆتە سی.'),
     scope=['body.legs'], screen=L('Breathlessness or chest pain', 'ضيق تنفس أو ألم في الصدر', 'هەناسەتەنگی یان ئازاری سنگ'))
flag('dvt-one-leg', 'same_day', 'urgent_same_day', ['sym:swelling', 'sym:pain', 'attr:side=one', '!sym:injury'], 'nhs-dvt', r'you think you have DVT',
     L('Pain and swelling in one leg can be a blood clot (DVT) and needs urgent assessment today.', 'الألم والتورم في ساق واحدة قد يكون جلطة ويحتاج تقييماً عاجلاً اليوم.', 'ئازار و ئاوسان لە یەک لاق لەوانەیە خوێنمەیین بێت و پێویستی بە هەڵسەنگاندنی بەپەلە هەیە ئەمڕۆ.'),
     scope=['body.legs'], screen=L('One leg swollen and painful', 'ساق واحدة متورمة ومؤلمة', 'یەک لاق ئاوساو و بە ئازار'))
flag('anaphylaxis', 'emergency', 'emergency', ['sym:face_lip_tongue_swelling|sym:throat_tight'], 'nhs-anaphylaxis', r'lips, mouth, throat or tongue suddenly become swollen',
     L('Swelling of the lips, tongue or throat, or a tight throat, can be anaphylaxis. Use an adrenaline auto-injector if you have one and call emergency services.', 'تورم الشفاه أو اللسان أو الحلق أو ضيق الحلق قد يكون صدمة تحسسية. استخدم حقنة الأدرينالين إن وجدت واتصل بالطوارئ.', 'ئاوسانی لێو، زمان یان گەروو، یان تەنگبوونی گەروو لەوانەیە شۆکی هەستیاری بێت. ئەگەر دەرزی ئەدرینالینت هەیە بەکاری بهێنە و پەیوەندی بە فریاکەوتنەوە بکە.'),
     screen=L('Swelling of the lips, tongue or throat', 'تورم الشفاه أو اللسان أو الحلق', 'ئاوسانی لێو، زمان یان گەروو'))
flag('fracture-signs', 'emergency', 'emergency', ['sym:deformity|sym:crack_sound'], 'nhs-sprains', r'heard a crack when you had your injury',
     L('A crack at the time of injury or a changed shape can mean a broken bone that needs an X-ray.', 'سماع طقة عند الإصابة أو تغيّر الشكل قد يعني كسراً يحتاج أشعة.', 'دەنگی شکان لە کاتی برین یان گۆڕانی شێوە لەوانەیە مانای شکانی ئێسک بێت کە پێویستی بە تیشک هەیە.'),
     screen=L('Heard a crack, or it looks deformed', 'سماع طقة أو تشوّه ظاهر', 'دەنگی شکان بیسترا یان شێوەی گۆڕاوە'))
flag('injury-numb', 'emergency', 'emergency', ['sym:injury', 'sym:numbness_tingling'], 'nhs-sprains', r'numb, tingling or has pins and needles',
     L('An injured area that is numb or tingling needs emergency assessment.', 'المنطقة المصابة التي فيها خدر أو تنميل تحتاج تقييماً طارئاً.', 'شوێنی بریندار کە سڕ بووە یان مێروولەی تێدایە پێویستی بە هەڵسەنگاندنی فریاکەوتن هەیە.'), scope=['body.arms', 'body.legs'])
flag('cannot-bear-weight', 'same_day', 'urgent_same_day', ['sym:cannot_bear_weight'], 'nhs-sprains', r'cannot put any weight on it',
     L('Not being able to put weight on an injury needs an urgent assessment.', 'عدم القدرة على تحميل الوزن على الإصابة يحتاج تقييماً عاجلاً.', 'نەتوانینی خستنە سەری قورسایی لەسەر برین پێویستی بە هەڵسەنگاندنی بەپەلە هەیە.'),
     scope=['body.legs'], screen=L('Cannot put any weight on it', 'لا تستطيع تحميل الوزن عليها', 'ناتوانیت قورسایی بخەیتە سەری'))
flag('palpitations-red', 'emergency', 'emergency', ['sym:palpitations', 'sym:chest_pain|sym:shortness_of_breath|sym:faint|sym:dizziness'], 'nhs-palpitations', r'feeling faint or fainting',
     L('Palpitations with chest pain, breathlessness or fainting need emergency care.', 'الخفقان مع ألم الصدر أو ضيق التنفس أو الإغماء يحتاج رعاية طارئة.', 'دڵەکوتێ لەگەڵ ئازاری سنگ، هەناسەتەنگی یان بووران پێویستی بە فریاکەوتن هەیە.'))
flag('fainting', 'same_day', 'urgent_same_day', ['sym:faint'], 'nhs-palpitations', r'feeling faint or fainting',
     L('Fainting needs to be assessed by a doctor today; call emergency services if it happens with chest pain, palpitations or breathlessness.', 'الإغماء يحتاج تقييم طبيب اليوم؛ اتصل بالطوارئ إذا حدث مع ألم صدر أو خفقان أو ضيق تنفس.', 'بووران پێویستی بە هەڵسەنگاندنی پزیشک هەیە ئەمڕۆ؛ ئەگەر لەگەڵ ئازاری سنگ، دڵەکوتێ یان هەناسەتەنگی بوو پەیوەندی بە فریاکەوتنەوە بکە.'),
     screen=L('Fainting or passing out', 'إغماء أو فقدان الوعي', 'بووران یان لە هۆش چوون'))
flag('coughing-blood', 'same_day', 'urgent_same_day', ['sym:coughing_blood'], 'nhs-pulmonary-embolism', r"you're coughing up blood",
     L('Coughing up blood needs an urgent assessment today.', 'السعال المصحوب بالدم يحتاج تقييماً عاجلاً اليوم.', 'کۆکەی خوێناوی پێویستی بە هەڵسەنگاندنی بەپەلە هەیە ئەمڕۆ.'), screen=L('Coughing up blood', 'سعال مع دم', 'کۆکەی خوێناوی'))
flag('cough-3-weeks', 'soon', 'gp_soon', ['sym:cough', 'attr:duration>=504'], 'nhs-chest-infection', r'cough for more than 3 weeks',
     L('A cough lasting more than 3 weeks should be checked by a doctor.', 'السعال الذي يستمر أكثر من 3 أسابيع يجب أن يفحصه طبيب.', 'کۆکەیەک کە زیاتر لە ٣ هەفتە بمێنێتەوە دەبێت پزیشک بیپشکنێت.'))
flag('weight-loss', 'soon', 'gp_soon', ['sym:weight_loss'], 'nhs-back-pain', r"you've lost weight without trying",
     L('Unexplained weight loss should be checked by a doctor.', 'فقدان الوزن غير المبرر يجب أن يفحصه طبيب.', 'دابەزینی کێشی بێهۆ دەبێت پزیشک بیپشکنێت.'))
flag('throat-airway', 'emergency', 'emergency', ['sym:drooling|sym:breathing_severe'], 'nhs-sore-throat', r'have difficulty breathing or are unable to swallow',
     L('Difficulty breathing, drooling or being unable to swallow with a sore throat is an emergency.', 'صعوبة التنفس أو سيلان اللعاب أو عدم القدرة على البلع مع التهاب الحلق حالة طارئة.', 'قورسی هەناسەدان، لیکڕشتن یان نەتوانینی قووتدان لەگەڵ گەروو ئێشە فریاکەوتنە.'),
     scope=['body.neck'], screen=L('Difficulty breathing, drooling or cannot swallow', 'صعوبة تنفس أو سيلان لعاب أو عدم القدرة على البلع', 'قورسی هەناسە، لیکڕشتن یان نەتوانینی قووتدان'))
flag('uti-upper', 'same_day', 'urgent_same_day', ['sym:urinary_burning|sym:urinary_frequency', 'sym:fever'], 'nhs-uti', r'very high or low temperature',
     L('Urinary symptoms with a high temperature need an urgent doctor’s review today.', 'الأعراض البولية مع حرارة مرتفعة تحتاج مراجعة طبية عاجلة اليوم.', 'نیشانەی میز لەگەڵ پلەی گەرمی بەرز پێویستی بە پشکنینی بەپەلەی پزیشک هەیە ئەمڕۆ.'))
flag('kidney-stone-fever', 'same_day', 'urgent_same_day', ['sym:pain@abdomen.flank|sym:pain@back.lower', 'sym:fever'], 'nhs-kidney-stones', r'you have a high temperature, or you feel hot, cold or shiv',
     L('Flank or back pain with a high temperature needs an urgent doctor’s review today.', 'ألم الخاصرة أو الظهر مع حرارة مرتفعة يحتاج مراجعة طبية عاجلة اليوم.', 'ئازاری تەنیشت یان پشت لەگەڵ پلەی گەرمی بەرز پێویستی بە پشکنینی بەپەلەی پزیشک هەیە ئەمڕۆ.'))
flag('knee-locked', 'same_day', 'urgent_same_day', ['sym:joint_locking@leg.knee|sym:deformity@leg.knee'], 'nhs-knee-pain', r'your knee locks, gives way or painfully clicks',
     L('A knee that locks, gives way or has changed shape needs an urgent assessment.', 'الركبة التي تنقفل أو تخون أو تغيّر شكلها تحتاج تقييماً عاجلاً.', 'ئەژنۆیەک کە گیر دەخوات، دەچەمێتەوە یان شێوەی گۆڕاوە پێویستی بە هەڵسەنگاندنی بەپەلە هەیە.'))
flag('headache-jaw-eating', 'same_day', 'urgent_same_day', ['sym:headache', 'sym:jaw_pain_eating'], 'nhs-headaches', r'jaw pain when eating',
     L('A headache with jaw pain when eating needs an urgent doctor’s review today.', 'الصداع مع ألم الفك عند الأكل يحتاج مراجعة طبية عاجلة اليوم.', 'سەرئێشە لەگەڵ ئازاری شەویلگە لە کاتی خواردن پێویستی بە پشکنینی بەپەلەی پزیشک هەیە ئەمڕۆ.'))
flag('headache-vomiting', 'same_day', 'urgent_same_day', ['sym:headache', 'sym:vomiting'], 'nhs-headaches', r'is being sick \(vomiting\)',
     L('A headache with vomiting needs an urgent doctor’s review today.', 'الصداع مع التقيؤ يحتاج مراجعة طبية عاجلة اليوم.', 'سەرئێشە لەگەڵ ڕشانەوە پێویستی بە پشکنینی بەپەلەی پزیشک هەیە ئەمڕۆ.'))
flag('headache-vision', 'same_day', 'urgent_same_day', ['sym:headache', 'sym:blurred_vision|sym:double_vision'], 'nhs-headaches', r'headache and vision or eye problems',
     L('A headache with vision problems needs an urgent doctor’s review today.', 'الصداع مع مشاكل في الرؤية يحتاج مراجعة طبية عاجلة اليوم.', 'سەرئێشە لەگەڵ کێشەی بینین پێویستی بە پشکنینی بەپەلەی پزیشک هەیە ئەمڕۆ.'))
flag('severe-bleeding', 'emergency', 'emergency', ['sym:bleeding'], 'nhs-wisdom-teeth', r'bleeding that does not stop',
     L('Heavy bleeding that will not stop needs urgent help now.', 'النزيف الشديد الذي لا يتوقف يحتاج مساعدة عاجلة الآن.', 'خوێنبەربوونی زۆر کە ناوەستێت پێویستی بە یارمەتی بەپەلە هەیە ئێستا.'), screen=L('Bleeding that will not stop', 'نزيف لا يتوقف', 'خوێنبەربوون کە ناوەستێت'))

# Region safety screens: the red flags offered as one multi-select question before the interview.
SCREENS = {
    'body.eyes': ['vision-loss', 'sudden-severe-eye-pain', 'curtain-shadow', 'new-floaters', 'eye-injury', 'eye-light-sensitivity'],
    'body.head': ['thunderclap-headache', 'stroke-face-speech', 'meningitis-signs', 'headache-head-injury', 'fainting'],
    'body.mouth': ['dental-airway', 'dental-mouth-opening', 'knocked-out-tooth', 'severe-bleeding'],
    'body.neck': ['throat-airway', 'anaphylaxis', 'severe-breathing'],
    'body.ears': ['stroke-face-speech', 'meningitis-signs', 'fainting'],
    'body.chest': ['chest-pain-spreading', 'chest-pain-with-symptoms', 'severe-breathing', 'coughing-blood', 'fainting'],
    'body.abdomen': ['abdominal-sudden-severe', 'gi-bleeding', 'jaundice-pain', 'abdominal-pain-fever'],
    'body.back': ['cauda-equina', 'chest-pain-spreading', 'fracture-signs'],
    'body.arms': ['stroke-face-speech', 'chest-pain-spreading', 'fracture-signs'],
    'body.legs': ['dvt-one-leg', 'dvt-breathing', 'fracture-signs', 'cannot-bear-weight'],
    'body.skin': ['anaphylaxis', 'meningitis-signs', 'severe-breathing'],
}
# What each screen chip asserts when ticked (facts), keyed by red flag id.
SCREEN_FACTS = {
    'vision-loss': ['sym:vision_loss', 'attr:onset=sudden'], 'sudden-severe-eye-pain': ['sym:pain', 'attr:severity=8'], 'curtain-shadow': ['sym:curtain_shadow'],
    'new-floaters': ['sym:flashes_floaters', 'attr:onset=sudden'], 'eye-injury': ['sym:injury'], 'eye-light-sensitivity': ['sym:light_sensitivity'],
    'thunderclap-headache': ['sym:headache', 'attr:onset=sudden', 'attr:severity=10'], 'stroke-face-speech': ['sym:face_droop'], 'meningitis-signs': ['sym:stiff_neck', 'sym:fever'],
    'headache-head-injury': ['sym:injury'], 'fainting': ['sym:faint'], 'dental-airway': ['sym:swallowing_difficulty'], 'dental-mouth-opening': ['sym:difficulty_opening_mouth', 'sym:swelling'],
    'knocked-out-tooth': ['sym:knocked_out_tooth'], 'severe-bleeding': ['sym:bleeding'], 'throat-airway': ['sym:drooling'], 'anaphylaxis': ['sym:face_lip_tongue_swelling'],
    'severe-breathing': ['sym:breathing_severe'], 'chest-pain-spreading': ['sym:chest_pain', 'sym:radiating_pain'], 'chest-pain-with-symptoms': ['sym:chest_pain', 'sym:sweating'],
    'coughing-blood': ['sym:coughing_blood'], 'abdominal-sudden-severe': ['sym:pain', 'attr:onset=sudden', 'attr:severity=8'], 'gi-bleeding': ['sym:gi_bleeding'],
    'jaundice-pain': ['sym:yellow_skin_eyes', 'sym:pain'], 'abdominal-pain-fever': ['sym:pain', 'sym:fever'], 'cauda-equina': ['sym:saddle_bladder'], 'fracture-signs': ['sym:deformity'],
    'dvt-one-leg': ['sym:swelling', 'sym:pain', 'attr:side=one'], 'dvt-breathing': ['sym:shortness_of_breath'], 'cannot-bear-weight': ['sym:cannot_bear_weight'],
}

# Region-specific trigger options and interview attributes (in addition to onset/duration/severity).
REGION_PROFILE = {
    'body.eyes': {'attributes': ['side', 'onset', 'duration', 'course'], 'triggers': ['screen', 'light'], 'history': ['contact_lens']},
    'body.head': {'attributes': ['onset', 'severity', 'character', 'side', 'pattern', 'duration'], 'triggers': ['stress', 'light', 'chewing'], 'history': []},
    'body.ears': {'attributes': ['side', 'onset', 'duration', 'severity'], 'triggers': [], 'history': []},
    'body.mouth': {'attributes': ['severity', 'duration', 'pattern'], 'triggers': ['temperature', 'chewing'], 'history': []},
    'body.neck': {'attributes': ['onset', 'duration', 'severity'], 'triggers': ['swallowing'], 'history': []},
    'body.chest': {'attributes': ['onset', 'character', 'severity', 'pattern', 'duration'], 'triggers': ['exertion', 'breathing', 'movement', 'eating', 'lying_down'], 'history': []},
    'body.abdomen': {'attributes': ['onset', 'severity', 'pattern', 'duration', 'course'], 'triggers': ['eating', 'movement'], 'history': []},
    'body.back': {'attributes': ['onset', 'severity', 'duration', 'course'], 'triggers': ['movement', 'night'], 'history': []},
    'body.arms': {'attributes': ['side', 'onset', 'severity', 'duration'], 'triggers': ['movement', 'night'], 'history': []},
    'body.legs': {'attributes': ['side', 'onset', 'severity', 'duration'], 'triggers': ['movement', 'morning', 'night'], 'history': []},
    'body.skin': {'attributes': ['onset', 'duration', 'course'], 'triggers': [], 'history': []},
}

IMAGING_SCOPE = {
    'body.eyes': {'photo_can_show': L('Eyelids, lashes, visible redness of the white of the eye, discharge, obvious lumps and large differences in pupil size.',
                                       'الجفون والرموش واحمرار بياض العين الظاهر والإفرازات والكتل الواضحة والاختلافات الكبيرة في حجم البؤبؤ.',
                                       'پێڵوو، برژانگ، سووربوونەوەی دیاری سپێنەی چاو، دەردراو، گرێی ڕوون و جیاوازیی گەورەی قەبارەی بیلبیلە.'),
                  'needs_examination': L('Vision, eye pressure, the cornea in detail, the lens, retina, macula and optic nerve need an eye examination with specialised equipment (for example a slit lamp, ophthalmoscope, tonometry or OCT).',
                                         'الرؤية وضغط العين وتفاصيل القرنية والعدسة والشبكية والبقعة والعصب البصري تحتاج فحصاً بأجهزة متخصصة (مثل المصباح الشقي ومنظار العين وقياس الضغط وOCT).',
                                         'بینین، فشاری چاو، وردەکاری قەرنیە، هاوێنە، تۆڕینە، ماکولا و دەماری بینین پێویستیان بە پشکنین بە ئامێری تایبەت هەیە (وەک لامپی درزی، ئۆفتالمۆسکۆپ، پێوانی فشار یان OCT).')},
    'body.mouth': {'photo_can_show': L('Visible tooth surfaces, gum colour and swelling, obvious crowding, gaps, missing teeth and — when biting together — some bite relationships.',
                                        'أسطح الأسنان الظاهرة ولون اللثة وتورمها والازدحام الواضح والفراغات والأسنان المفقودة وبعض علاقات العضة عند الإطباق.',
                                        'ڕووی دیاری ددان، ڕەنگ و ئاوسانی پووک، قەرەباڵغی ڕوون، بۆشایی، ددانی ونبوو و هەندێک پەیوەندیی گەستن کاتێک ددانەکان یەکدەگرنەوە.'),
                   'needs_examination': L('Decay between teeth, roots, bone levels, infection spread, jaw growth and whether teeth can be moved need a dental examination and X-rays; orthodontic planning also needs study models or scans and cephalometric records.',
                                          'التسوس بين الأسنان والجذور ومستوى العظم وانتشار العدوى ونمو الفك وإمكانية تحريك الأسنان تحتاج فحص أسنان وأشعة؛ وتخطيط التقويم يحتاج أيضاً نماذج أو مسحاً وسجلات سيفالومترية.',
                                          'کرمخواردنی نێوان ددان، ڕەگ، ئاستی ئێسک، بڵاوبوونەوەی هەوکردن، گەشەی شەویلگە و توانای جووڵاندنی ددان پێویستیان بە پشکنینی ددان و تیشک هەیە؛ پلاندانانی ڕاستکردنەوەش پێویستی بە مۆدێل یان سکان و تۆماری سێفالۆمێتری هەیە.')},
    'body.skin': {'photo_can_show': L('Colour, shape, size relative to a reference and visible surface changes over time when photographed the same way.',
                                       'اللون والشكل والحجم مقارنة بمرجع والتغيرات السطحية الظاهرة مع الوقت عند التصوير بالطريقة نفسها.',
                                       'ڕەنگ، شێوە، قەبارە بەراورد بە پێوەرێک و گۆڕانی دیاری ڕووکار بە تێپەڕبوونی کات کاتێک بە هەمان شێوە وێنە دەگیرێت.'),
                  'needs_examination': L('Whether a skin lesion is cancer cannot be confirmed or excluded from a photograph; dermoscopy, examination and sometimes biopsy are needed.',
                                         'لا يمكن تأكيد أو استبعاد كون الآفة الجلدية سرطاناً من صورة؛ يلزم فحص بالمنظار الجلدي وفحص سريري وأحياناً خزعة.',
                                         'ناتوانرێت لە وێنەیەکەوە دووپات یان ڕەت بکرێتەوە کە ئایا برینێکی پێست شێرپەنجەیە؛ پێویستی بە دێرمۆسکۆپی، پشکنین و هەندێک جار نموونەوەرگرتن هەیە.')},
}

COVERAGE_GAPS = [
    'Children and babies (age-specific warning signs and thresholds are not modelled).',
    'Pregnancy and postpartum presentations.',
    'Mental health, self-harm and crisis pathways (no screening content yet).',
    'Ear wax, nosebleeds, eye strain, tooth erosion, cold sores and many other common problems.',
    'Long-term condition management (diabetes, heart failure, asthma control).',
    'Medication interactions, dosing and prescribing (deliberately out of scope).',
    'Region-specific emergency numbers and services outside the UK-derived source wording.',
]

symptom_ids = {item['id'] for item in SYMPTOMS}
for item in CONDITIONS:
    for feature in item['features'] + item['against']:
        kind, _, rest = feature['match'].partition(':')
        assert kind in ('sym', 'attr', 'trig'), feature
        if kind == 'sym':
            assert rest in symptom_ids, (item['id'], rest)
        if kind == 'trig':
            assert rest in TRIGGERS, (item['id'], rest)
for item in RED_FLAGS:
    for clause in item['when']:
        for part in clause.split('|'):
            kind, _, rest = part.lstrip('!').partition(':')
            if kind == 'sym':
                assert rest.split('@')[0] in symptom_ids, (item['id'], rest)
flag_ids = {item['id'] for item in RED_FLAGS}
for region, ids in SCREENS.items():
    for identifier in ids:
        assert identifier in flag_ids and identifier in SCREEN_FACTS, (region, identifier)

out = ROOT / 'contracts/clinical'
out.mkdir(parents=True, exist_ok=True)
header = {'generated_by': 'ai-service/scripts/build-clinical-knowledge.py — edit the generator, not this file',
          'clinical_review_status': 'draft — no clinician has reviewed this content', 'translation_review_status': {'en': 'draft', 'ar': 'draft — native medical review pending', 'ckb': 'draft — native medical review pending'}}
symptoms_doc = {'schema_version': 'humantwin-symptoms-v1', 'version': 'symptoms-2026-11-16.1', **header, 'symptoms': SYMPTOMS, 'attributes': ATTRIBUTES,
                'triggers': {key: {'label': value[0], 'terms': {'en': value[1], 'ar': value[2], 'ckb': value[3]}} for key, value in TRIGGERS.items()},
                'trigger_cues': TRIGGER_CUES, 'severity_words': SEVERITY_WORDS, 'negation': NEGATION, 'uncertain': UNCERTAIN, 'historical': HISTORICAL, 'yes': YES, 'no': NO,
                'number_words': NUMBER_WORDS, 'duration_units': DURATION_UNITS, 'duration_special': DURATION_SPECIAL}
knowledge_doc = {'schema_version': 'humantwin-clinical-knowledge-v1', 'version': 'knowledge-2026-11-16.1', **header,
                 'weights': {'typical': 3, 'common': 2, 'possible': 1, 'strong': -4, 'moderate': -2, 'note': 'Ordering weights, not probabilities.'},
                 'questions': QUESTIONS, 'pathways': PATHWAYS, 'conditions': CONDITIONS, 'red_flags': RED_FLAGS, 'screens': SCREENS, 'screen_facts': SCREEN_FACTS,
                 'region_profiles': REGION_PROFILE, 'imaging_scope': IMAGING_SCOPE, 'coverage_gaps': COVERAGE_GAPS}
(out / 'symptoms.v1.json').write_text(json.dumps(symptoms_doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
(out / 'knowledge.v1.json').write_text(json.dumps(knowledge_doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print(f'{len(SYMPTOMS)} symptoms, {len(CONDITIONS)} conditions, {len(RED_FLAGS)} red flags')
