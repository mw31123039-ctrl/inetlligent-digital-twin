"""Patient-facing sentence templates (en / ar / ckb). Arabic and Sorani are drafts pending native medical review."""

T = {
    'complaint': {'en': 'In your own words, what is bothering you about your {anatomy}?', 'ar': 'بكلماتك الخاصة، ما الذي يزعجك في {anatomy}؟', 'ckb': 'بە وشەی خۆت، چی لە {anatomy}دا بێزارت دەکات؟'},
    'complaint_purpose': {'en': 'Your own description guides every later question.', 'ar': 'وصفك بكلماتك يوجّه كل الأسئلة اللاحقة.', 'ckb': 'وەسفی خۆت ڕێنمایی هەموو پرسیارەکانی دواتر دەکات.'},
    'none_of_these': {'en': 'None of these', 'ar': 'لا شيء من هذه', 'ckb': 'هیچ کام لەمانە'},
    'support_symptom': {'en': 'You reported {feature}; {publisher} lists this for {condition}.', 'ar': 'ذكرتَ {feature}؛ ويذكر {publisher} ذلك ضمن {condition}.', 'ckb': 'تۆ باسی {feature}ت کرد؛ {publisher} ئەمە بۆ {condition} ناو دەبات.'},
    'support_attr': {'en': '{feature} matches how {publisher} describes {condition}.', 'ar': '{feature} يتوافق مع وصف {publisher} لـ{condition}.', 'ckb': '{feature} لەگەڵ وەسفی {publisher} بۆ {condition} یەکدەگرێتەوە.'},
    'absent_typical': {'en': 'You said you do not have {feature}, which {publisher} lists as a usual feature of {condition}.', 'ar': 'قلتَ إنه ليس لديك {feature}، وهو من العلامات المعتادة لـ{condition} حسب {publisher}.', 'ckb': 'وتت {feature}ت نیە، کە {publisher} وەک نیشانەیەکی ئاسایی {condition} ناوی دەبات.'},
    'fits': {'en': 'Your answers match several features that {publisher} describes for {condition}. This is a possibility to discuss with a clinician, not a diagnosis.',
             'ar': 'تتوافق إجاباتك مع عدة علامات يصفها {publisher} لـ{condition}. هذا احتمال لمناقشته مع طبيب، وليس تشخيصاً.',
             'ckb': 'وەڵامەکانت لەگەڵ چەند نیشانەیەک یەکدەگرنەوە کە {publisher} بۆ {condition} وەسفی دەکات. ئەمە ئەگەرێکە بۆ گفتوگۆ لەگەڵ پزیشک، نەک دەستنیشانکردن.'},
    'partly_fits': {'en': 'Some of your answers match {condition}, but important features are missing or do not match. It remains one possibility among others.',
                    'ar': 'بعض إجاباتك تتوافق مع {condition}، لكن علامات مهمة غائبة أو لا تتوافق. يبقى احتمالاً واحداً بين احتمالات أخرى.',
                    'ckb': 'هەندێک لە وەڵامەکانت لەگەڵ {condition} یەکدەگرنەوە، بەڵام نیشانەی گرنگ نین یان یەکناگرنەوە. هێشتا تەنها ئەگەرێکە لە نێوان چەند ئەگەرێکدا.'},
    'urgent_condition_reason': {'en': 'Your answers fit {condition}, which needs prompt assessment.', 'ar': 'تتوافق إجاباتك مع {condition} التي تحتاج تقييماً سريعاً.', 'ckb': 'وەڵامەکانت لەگەڵ {condition} یەکدەگرنەوە کە پێویستی بە هەڵسەنگاندنی خێرا هەیە.'},
    'screen_clear': {'en': 'None of the listed warning signs were reported in the safety check.', 'ar': 'لم تُذكر أيٌّ من علامات الخطر المدرجة في فحص السلامة.', 'ckb': 'هیچ کام لە نیشانە مەترسیدارە ڕیزکراوەکان لە پشکنینی سەلامەتیدا باس نەکران.'},
    'unspecific_warning': {'en': 'You reported a possible warning sign without saying which one; it needs to be assessed today.', 'ar': 'ذكرتَ علامة خطر محتملة دون تحديدها؛ يجب تقييمها اليوم.', 'ckb': 'باسی نیشانەیەکی مەترسیدارت کرد بێ ئەوەی دیاری بکەیت کامەیە؛ پێویستە ئەمڕۆ هەڵبسەنگێنرێت.'},
    'prior_urgency': {'en': 'Urgent guidance raised earlier in this conversation stays in place after edits; a clinician should confirm it is safe to stand down.', 'ar': 'تبقى إرشادات الاستعجال السابقة سارية بعد التعديل؛ يجب أن يؤكد طبيب أن التراجع عنها آمن.', 'ckb': 'ڕێنمایی بەپەلەی پێشووتر دوای دەستکاری بەردەوام دەبێت؛ پزیشک دەبێت دڵنیا بکاتەوە کە لابردنی سەلامەتە.'},
    'not_established_action': {'en': 'There is not enough information yet to judge urgency. Answer the next question, or contact a clinician. Get urgent help for severe, sudden or rapidly worsening symptoms.',
                               'ar': 'لا توجد معلومات كافية بعد لتقدير الاستعجال. أجب عن السؤال التالي أو تواصل مع طبيب. اطلب مساعدة عاجلة للأعراض الشديدة أو المفاجئة أو المتفاقمة بسرعة.',
                               'ckb': 'هێشتا زانیاری پێویست نیە بۆ دیاریکردنی پەلە. وەڵامی پرسیاری داهاتوو بدەرەوە یان پەیوەندی بە پزیشکەوە بکە. بۆ نیشانەی توند، لەناکاو یان خێرا خراپبوو داوای یارمەتی بەپەلە بکە.'},
    'not_established_label': {'en': 'Urgency not yet established', 'ar': 'لم يُحدَّد مستوى الاستعجال بعد', 'ckb': 'پلەی پەلە هێشتا دیاری نەکراوە'},
    'summary_reported': {'en': '{anatomy}{side}: you reported {items}.', 'ar': '{anatomy}{side}: ذكرتَ {items}.', 'ckb': '{anatomy}{side}: تۆ باسی {items}ت کرد.'},
    'summary_nothing': {'en': '{anatomy}{side}: no symptoms recorded yet.', 'ar': '{anatomy}{side}: لم تُسجَّل أعراض بعد.', 'ckb': '{anatomy}{side}: هێشتا هیچ نیشانەیەک تۆمار نەکراوە.'},
    'summary_denied': {'en': 'You said you do not have: {items}.', 'ar': 'قلتَ إنه ليس لديك: {items}.', 'ckb': 'وتت ئەمانەت نیە: {items}.'},
    'summary_next': {'en': 'Suggested next step: {pathway}.', 'ar': 'الخطوة التالية المقترحة: {pathway}.', 'ckb': 'هەنگاوی پێشنیارکراوی داهاتوو: {pathway}.'},
    'side_suffix': {'en': ' ({side})', 'ar': ' ({side})', 'ckb': ' ({side})'},
    'and': {'en': ', ', 'ar': '، ', 'ckb': '، '},
    'onset_value': {'en': 'onset {value}', 'ar': 'البدء {value}', 'ckb': 'دەستپێکردن {value}'},
    'duration_value': {'en': 'for {value}', 'ar': 'منذ {value}', 'ckb': 'بۆ ماوەی {value}'},
    'severity_value': {'en': 'severity {value}/10', 'ar': 'الشدة {value}/10', 'ckb': 'توندی {value}/10'},
    'hour': {'en': '1 hour', 'ar': 'ساعة واحدة', 'ckb': '1 کاتژمێر'},
    'day': {'en': '1 day', 'ar': 'يوم واحد', 'ckb': '1 ڕۆژ'},
    'week': {'en': '1 week', 'ar': 'أسبوع واحد', 'ckb': '1 هەفتە'},
    'month': {'en': '1 month', 'ar': 'شهر واحد', 'ckb': '1 مانگ'},
    'one_side': {'en': 'One side only', 'ar': 'جهة واحدة فقط', 'ckb': 'تەنها یەک لا'},
    'both_sides': {'en': 'Both sides', 'ar': 'الجهتان', 'ckb': 'هەردوو لا'},
    'hours': {'en': '{n} hours', 'ar': '{n} ساعة', 'ckb': '{n} کاتژمێر'},
    'days': {'en': '{n} days', 'ar': '{n} أيام', 'ckb': '{n} ڕۆژ'},
    'weeks': {'en': '{n} weeks', 'ar': '{n} أسابيع', 'ckb': '{n} هەفتە'},
    'months': {'en': '{n} months', 'ar': '{n} أشهر', 'ckb': '{n} مانگ'},
    'limit_core': {'en': 'This assessment uses draft rules and source-linked knowledge that no clinician has reviewed yet. It cannot examine you, run tests or confirm a diagnosis.',
                   'ar': 'يستخدم هذا التقييم قواعد أولية ومعرفة مرتبطة بمصادر لم يراجعها أي طبيب بعد. لا يمكنه فحصك أو إجراء تحاليل أو تأكيد تشخيص.',
                   'ckb': 'ئەم هەڵسەنگاندنە یاسای سەرەتایی و زانیاری بەستراو بە سەرچاوە بەکاردەهێنێت کە هێشتا هیچ پزیشکێک پێیدا نەچۆتەوە. ناتوانێت بتپشکنێت، تاقیکردنەوە بکات یان دەستنیشانکردن دووپات بکاتەوە.'},
    'limit_lexicon': {'en': 'Symptoms are recognised with a fixed multilingual vocabulary; unusual wording can be missed. Use the answer buttons where possible and check the recorded facts.',
                      'ar': 'يتم التعرف على الأعراض بمفردات ثابتة متعددة اللغات؛ قد تفوت الصياغات غير المعتادة. استخدم أزرار الإجابة قدر الإمكان وتحقق من الحقائق المسجلة.',
                      'ckb': 'نیشانەکان بە وشەدانێکی جێگیری فرەزمانی دەناسرێنەوە؛ دەربڕینی نائاسایی لەوانەیە لەدەست بچێت. تا دەتوانیت دوگمەکانی وەڵام بەکاربهێنە و ڕاستییە تۆمارکراوەکان بپشکنە.'},
    'limit_screen': {'en': 'The safety check has not been completed, so urgency cannot be judged yet.', 'ar': 'لم يكتمل فحص السلامة بعد، لذا لا يمكن تقدير الاستعجال.', 'ckb': 'پشکنینی سەلامەتی تەواو نەبووە، بۆیە هێشتا ناتوانرێت پەلە دیاری بکرێت.'},
    'limit_overdue': {'en': 'At least one cited page is past its publisher’s planned review date.', 'ar': 'صفحة واحدة على الأقل من المصادر تجاوزت موعد مراجعتها المخطط.', 'ckb': 'لانیکەم یەکێک لە پەڕە ئاماژەپێکراوەکان کاتی پێداچوونەوەی پلانکراوی تێپەڕاندووە.'},
    'limit_translation': {'en': 'Arabic and Kurdish wording is a draft translation pending native medical review.', 'ar': 'الصياغة العربية والكردية ترجمة أولية بانتظار مراجعة طبية من متحدثين أصليين.', 'ckb': 'دەقی عەرەبی و کوردی وەرگێڕانێکی سەرەتاییە و چاوەڕێی پێداچوونەوەی پزیشکی ئاخێوەرانی ڕەسەنە.'},
    'limit_coverage': {'en': 'The knowledge base covers {n} conditions with {s} approved sources; many problems are not covered.', 'ar': 'تغطي قاعدة المعرفة {n} حالة من {s} مصدراً معتمداً؛ كثير من المشاكل غير مغطاة.', 'ckb': 'بنکەی زانیاری {n} حاڵەت لە {s} سەرچاوەی پەسەندکراو دەگرێتەوە؛ زۆر کێشە نەگیراون.'},
    'limit_insufficient': {'en': 'Not enough information has been given to suggest any explanation.', 'ar': 'لم تُقدَّم معلومات كافية لاقتراح أي تفسير.', 'ckb': 'زانیاری پێویست نەدراوە بۆ پێشنیارکردنی هیچ ڕوونکردنەوەیەک.'},
    'limit_none_supported': {'en': 'The approved sources do not support a specific explanation for what you described. Share the recorded facts with a clinician.', 'ar': 'لا تدعم المصادر المعتمدة تفسيراً محدداً لما وصفته. شارك الحقائق المسجلة مع طبيب.', 'ckb': 'سەرچاوە پەسەندکراوەکان پشتگیری ڕوونکردنەوەیەکی دیاریکراو ناکەن بۆ ئەوەی وەسفت کرد. ڕاستییە تۆمارکراوەکان لەگەڵ پزیشک هاوبەش بکە.'},
    'limit_conflicting': {'en': 'Some of your answers conflict with the closest matches, so no explanation fits well.', 'ar': 'بعض إجاباتك تتعارض مع أقرب الاحتمالات، لذا لا يوجد تفسير مناسب تماماً.', 'ckb': 'هەندێک لە وەڵامەکانت لەگەڵ نزیکترین ئەگەرەکان ناکۆکن، بۆیە هیچ ڕوونکردنەوەیەک بە تەواوی ناگونجێت.'},
    'limit_withheld': {'en': 'Possible explanations are withheld so the urgent guidance stays clear. A clinician will assess the cause.', 'ar': 'حُجبت التفسيرات المحتملة لإبقاء الإرشاد العاجل واضحاً. سيقيّم الطبيب السبب.', 'ckb': 'ڕوونکردنەوە ئەگەرییەکان شاردراونەتەوە تا ڕێنمایی بەپەلە ڕوون بمێنێتەوە. پزیشک هۆکارەکە هەڵدەسەنگێنێت.'},
    'limit_photo': {'en': 'A photograph or this chat cannot confirm or exclude cancer or other serious disease.', 'ar': 'لا يمكن للصورة أو لهذه المحادثة تأكيد السرطان أو غيره من الأمراض الخطيرة أو استبعادها.', 'ckb': 'وێنە یان ئەم گفتوگۆیە ناتوانێت شێرپەنجە یان نەخۆشی مەترسیداری تر دووپات یان ڕەت بکاتەوە.'},
    'disclaimer': {'en': 'Educational decision support, not a diagnosis. It does not replace a clinician’s examination.', 'ar': 'دعم تعليمي للقرار، وليس تشخيصاً. لا يغني عن فحص الطبيب.', 'ckb': 'پشتگیری فێرکاری بۆ بڕیاردان، نەک دەستنیشانکردن. جێگەی پشکنینی پزیشک ناگرێتەوە.'},
    'missing_screen': {'en': 'Safety check', 'ar': 'فحص السلامة', 'ckb': 'پشکنینی سەلامەتی'},
    'missing_screen_reason': {'en': 'Warning signs must be ruled out before anything else.', 'ar': 'يجب استبعاد علامات الخطر قبل أي شيء.', 'ckb': 'پێش هەموو شتێک دەبێت نیشانە مەترسیدارەکان دوور بخرێنەوە.'},
    'missing_core_reason': {'en': 'Needed by any clinician to judge this.', 'ar': 'يحتاجها أي طبيب لتقدير الحالة.', 'ckb': 'هەر پزیشکێک پێویستی پێیەتی بۆ هەڵسەنگاندن.'},
    'missing_feature_reason': {'en': 'Would help tell the possible explanations apart.', 'ar': 'سيساعد على التمييز بين التفسيرات المحتملة.', 'ckb': 'یارمەتی جیاکردنەوەی ڕوونکردنەوە ئەگەرییەکان دەدات.'},
    'missing_history_reason': {'en': 'Needed for safe advice and your clinician summary.', 'ar': 'مطلوب لنصيحة آمنة ولملخص الطبيب.', 'ckb': 'بۆ ئامۆژگاری سەلامەت و پوختەی پزیشک پێویستە.'},
    'contradiction_symptom': {'en': 'You first said “{a}” and later “{b}”.', 'ar': 'قلتَ أولاً «{a}» ثم «{b}».', 'ckb': 'سەرەتا وتت «{a}» و دواتر «{b}».'},
    'contradiction_laterality': {'en': 'The selected side ({selected}) differs from the side you described ({said}).', 'ar': 'الجهة المختارة ({selected}) تختلف عن الجهة التي وصفتها ({said}).', 'ckb': 'لای هەڵبژێردراو ({selected}) جیاوازە لە لای وەسفکراو ({said}).'},
    'contradiction_memory': {'en': 'Your saved history lists “{a}”, but you answered “{b}”.', 'ar': 'يذكر سجلك المحفوظ «{a}» لكنك أجبت «{b}».', 'ckb': 'مێژووی پاشەکەوتکراوت «{a}» تێدایە، بەڵام وەڵامت دایەوە «{b}».'},
    'observation': {'en': 'Reported: {label}{detail}', 'ar': 'تم الإبلاغ عن: {label}{detail}', 'ckb': 'ڕاپۆرتکراو: {label}{detail}'},
    'observation_absent': {'en': 'Denied: {label}', 'ar': 'نفى: {label}', 'ckb': 'ڕەتکرایەوە: {label}'},
    'observation_memory': {'en': 'From saved history ({provenance}): {label}', 'ar': 'من السجل المحفوظ ({provenance}): {label}', 'ckb': 'لە مێژووی پاشەکەوتکراو ({provenance}): {label}'},
}
SIDES = {'left': {'en': 'left', 'ar': 'اليسرى', 'ckb': 'چەپ'}, 'right': {'en': 'right', 'ar': 'اليمنى', 'ckb': 'ڕاست'}, 'both': {'en': 'both sides', 'ar': 'الجهتان', 'ckb': 'هەردوو لا'},
         'midline': {'en': 'middle', 'ar': 'الوسط', 'ckb': 'ناوەڕاست'}, 'unknown': {'en': 'side not given', 'ar': 'الجهة غير محددة', 'ckb': 'لا دیاری نەکراوە'}}


def t(key, locale, **values):
    template = T[key].get(locale) or T[key]['en']
    return template.format(**values) if values else template


def side_word(side, locale):
    return SIDES.get(side or 'unknown', SIDES['unknown']).get(locale, side)


def human_duration(hours, locale):
    for limit, size, plural, single in ((24, 1, 'hours', 'hour'), (24 * 14, 24, 'days', 'day'), (24 * 60, 168, 'weeks', 'week'), (float('inf'), 720, 'months', 'month')):
        if hours < limit:
            n = max(1, round(hours / size))
            return t(single, locale) if n == 1 else t(plural, locale, n=n)
