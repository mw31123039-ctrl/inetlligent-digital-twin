"""Build contracts/clinical/anatomy.v1.json, the stable anatomy ontology shared by Python, Laravel and Vue.

Conventions
- IDs are stable, lowercase, dot-separated. Never rename an ID; retire it with "status": "retired".
- Side is always the PATIENT's side. A lateral structure has no side in its ID; the side travels separately.
- Teeth use FDI two-digit notation (11-48). Quadrants 1 and 4 are on the patient's right.
- 3D anchors are illustrative marker positions on the bundled reference body (1.8 m, faces +z,
  +x is the patient's LEFT). Lateral anchors are written for the left side and mirrored for the right.
  They are not measured patient anatomy.

Run from the repository root:  python ai-service/scripts/build-clinical-anatomy.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EYE = json.loads((ROOT / 'contracts/eye/anatomy.v1.json').read_text(encoding='utf-8'))
EYE_LABELS = {item['id']: item['label'] for item in EYE['structures']}


def eye_label(identifier):
    label = EYE_LABELS[identifier]
    return {'en': label['en'], 'ar': label['ar-IQ'], 'ckb': label['ckb']}


def L(en, ar, ckb):
    return {'en': en, 'ar': ar, 'ckb': ckb}


def anchor(bone, offset=(0, 0, 0), to=None, t=None):
    value = {'bone': bone, 'offset': [round(v, 4) for v in offset]}
    if to:
        value.update({'to': to, 't': t})
    return value


nodes = []


def node(identifier, parent, kind, label, *, lateral=False, fixed_side=None, anchor_value=None, legacy=None,
         related=(), terms=None, internal=False, specialty=None, photo_visible=None):
    nodes.append({
        'id': identifier, 'parent': parent, 'kind': kind, 'label': label, 'lateral': lateral,
        'fixed_side': fixed_side, 'anchor': anchor_value, 'legacy_region': legacy, 'internal': internal,
        'specialty': specialty, 'photo_visible': photo_visible,
        'related': [{'target': target, 'relation': relation, 'note': note} for target, relation, note in related],
        'terms': terms or {'en': [], 'ar': [], 'ckb': []}, 'status': 'active',
    })


T = lambda en=(), ar=(), ckb=(): {'en': list(en), 'ar': list(ar), 'ckb': list(ckb)}

# ---------------------------------------------------------------- regions
node('body.head', None, 'region', L('Head', 'الرأس', 'سەر'), anchor_value=anchor('head', (0, .16, .09)), legacy='head',
     terms=T(['head'], ['رأس', 'راس', 'راسي'], ['سەر', 'سەرم']))
node('body.eyes', None, 'region', L('Eyes', 'العينان', 'چاوەکان'), lateral=True, anchor_value=anchor('head', (.033, .099, .11)), legacy='eyes',
     terms=T(['eye', 'eyes'], ['عين', 'عيني', 'عيون', 'العين'], ['چاو', 'چاوم']), specialty='ophthalmology')
node('body.ears', None, 'region', L('Ears', 'الأذنان', 'گوێیەکان'), lateral=True, anchor_value=anchor('head', (.077, .085, 0)), legacy='head',
     terms=T(['ear', 'ears'], ['أذن', 'اذن', 'اذني', 'أذني'], ['گوێ', 'گوێم']))
node('body.mouth', None, 'region', L('Mouth & teeth', 'الفم والأسنان', 'دەم و ددان'), anchor_value=anchor('head', (0, .035, .105)), legacy='head',
     terms=T(['mouth'], ['فم', 'الفم', 'حلك'], ['دەمم', 'ناو دەم', 'دەممدا', 'دەمەوە']), specialty='dentistry')
node('body.neck', None, 'region', L('Neck & throat', 'الرقبة والحلق', 'مل و گەروو'), anchor_value=anchor('neck', (0, .03, .06)), legacy='head',
     terms=T(['neck'], ['رقبة', 'رقبتي', 'الرقبة'], ['مل', 'ملم']))
node('body.chest', None, 'region', L('Chest', 'الصدر', 'سنگ'), anchor_value=anchor('chest', (0, .075, .125)), legacy='chest',
     terms=T(['chest'], ['صدر', 'صدري', 'الصدر'], ['سنگ', 'سنگم']))
node('body.abdomen', None, 'region', L('Abdomen', 'البطن', 'سک'), anchor_value=anchor('spine', (0, .105, .125)), legacy='abdomen',
     terms=T(['abdomen', 'stomach', 'belly', 'tummy'], ['بطن', 'بطني', 'معدة', 'معدتي', 'البطن'], ['سک', 'سکم', 'گەدە']))
node('body.back', None, 'region', L('Back', 'الظهر', 'پشت'), anchor_value=anchor('spine', (0, .1, -.12)), legacy='chest',
     terms=T(['back'], ['ظهر', 'ظهري', 'الظهر'], ['پشت', 'پشتم']))
node('body.arms', None, 'region', L('Arms & hands', 'الذراعان واليدان', 'باڵ و دەست'), lateral=True,
     anchor_value=anchor('upperArm', (0, 0, .02), to='forearm', t=.5), legacy='arms',
     terms=T(['arm', 'arms'], ['ذراع', 'ذراعي', 'يد', 'إيد', 'ايدي'], ['باڵ', 'قۆڵ', 'دەست']))
node('body.legs', None, 'region', L('Legs & feet', 'الساقان والقدمان', 'لاق و پێ'), lateral=True,
     anchor_value=anchor('thigh', (0, 0, .03), to='shin', t=.5), legacy='legs',
     terms=T(['leg', 'legs'], ['رجل', 'رجلي', 'ساق', 'ساقي'], ['لاق', 'قاچ', 'لاقم', 'قاچم']))
node('body.skin', None, 'region', L('Skin', 'الجلد', 'پێست'), anchor_value=None, legacy=None,
     terms=T(['skin'], ['جلد', 'جلدي', 'بشرة'], ['پێست']), specialty='dermatology', photo_visible=True)

# ---------------------------------------------------------------- head
node('head.forehead', 'body.head', 'structure', L('Forehead', 'الجبهة', 'ناوچەوان'), anchor_value=anchor('head', (0, .165, .095)),
     terms=T(['forehead'], ['جبهة', 'جبين', 'الجبهة'], ['ناوچەوان']))
node('head.temple', 'body.head', 'structure', L('Temple', 'الصدغ', 'لاجانگ'), lateral=True, anchor_value=anchor('head', (.068, .13, .05)),
     terms=T(['temple', 'temples'], ['صدغ', 'الصدغ'], ['لاجانگ']), related=[('head.jaw-joint', 'adjacent', 'Jaw-joint and chewing-muscle pain can be felt at the temple.')])
node('head.back-of-head', 'body.head', 'structure', L('Back of the head', 'مؤخرة الرأس', 'پشتی سەر'), anchor_value=anchor('head', (0, .12, -.09)),
     terms=T(['back of my head', 'back of the head'], ['مؤخرة الرأس', 'ورا راسي', 'خلف الرأس'], ['پشتی سەر', 'پشتەوەی سەر']),
     related=[('body.neck', 'adjacent', 'Neck muscle tension can be felt at the back of the head.')])
node('head.sinuses', 'body.head', 'structure', L('Sinuses & cheeks', 'الجيوب الأنفية والخدان', 'سینوس و ڕوومەت'), anchor_value=anchor('head', (0, .085, .112)),
     terms=T(['sinus', 'sinuses', 'cheek', 'cheeks', 'nose'], ['جيوب', 'الجيوب الأنفية', 'خد', 'خدي', 'أنف', 'انف'], ['سینوس', 'ڕوومەت', 'لووت']),
     related=[('mouth.teeth', 'referred_pain', 'Upper-sinus pressure can feel like upper back-tooth pain.')])
node('head.jaw-joint', 'body.head', 'structure', L('Jaw joint (TMJ)', 'مفصل الفك', 'جومگەی شەویلگە'), lateral=True, anchor_value=anchor('head', (.062, .06, .03)),
     terms=T(['jaw', 'jaw joint', 'tmj'], ['فك', 'فكي', 'مفصل الفك', 'حنك'], ['شەویلگە', 'چەناگە']),
     related=[('mouth.bite', 'adjacent', 'Bite and chewing load the jaw joint.'), ('body.ears', 'referred_pain', 'Jaw-joint pain is often felt in front of the ear.')])
node('head.brain', 'body.head', 'structure', L('Brain (internal)', 'الدماغ (داخلي)', 'مێشک (ناوەکی)'), anchor_value=anchor('head', (0, .14, 0)), internal=True,
     related=[('eye.optic-nerve', 'clinical_link', 'Vision depends on the optic nerve and brain pathways.')])

# ---------------------------------------------------------------- eyes (IDs shared with contracts/eye/anatomy.v1.json)
EYE_PARTS = [
    ('eye.upper-eyelid', (.033, .112, .108), True, [('eye.lower-eyelid', 'adjacent', 'Both lids protect the eye surface.')]),
    ('eye.lower-eyelid', (.033, .088, .108), True, []),
    ('eye.eyelid-margin', (.033, .106, .111), True, [('eye.meibomian-glands', 'adjacent', 'Oil glands open on the lid margin.')]),
    ('eye.meibomian-glands', (.033, .104, .109), True, [('eye.tear-film', 'clinical_link', 'Gland oil stabilises the tear film.')]),
    ('eye.bulbar-conjunctiva', (.04, .099, .112), True, [('eye.cornea', 'adjacent', 'The conjunctiva surrounds the cornea at the limbus.')]),
    ('eye.tear-film', (.033, .099, .115), True, [('eye.cornea', 'adjacent', 'Tears cover and protect the cornea.')]),
    ('eye.lacrimal-gland', (.052, .112, .095), True, [('eye.tear-film', 'clinical_link', 'Produces the watery part of tears.')]),
    ('eye.cornea', (.033, .099, .116), True, [('eye.iris', 'adjacent', 'The iris sits behind the cornea.')]),
    ('eye.sclera', (.045, .099, .108), False, []),
    ('eye.iris', (.033, .099, .113), False, [('eye.pupil', 'adjacent', 'The iris sets the pupil size.')]),
    ('eye.pupil', (.033, .099, .114), False, []),
    ('eye.lens', (.033, .099, .108), False, [('eye.vitreous-body', 'adjacent', 'The vitreous lies behind the lens.')]),
    ('eye.vitreous-body', (.033, .099, .1), False, [('eye.retina', 'adjacent', 'Vitreous traction can tear the retina.')]),
    ('eye.retina', (.033, .099, .092), False, [('eye.macula', 'adjacent', 'The macula is the central retina.'), ('eye.optic-nerve', 'adjacent', 'Retinal signals leave through the optic nerve.')]),
    ('eye.macula', (.031, .099, .09), False, []),
    ('eye.optic-nerve', (.028, .099, .084), False, [('head.brain', 'clinical_link', 'Carries visual signals to the brain.')]),
]
for identifier, offset, visible, related in EYE_PARTS:
    label = eye_label(identifier)
    if identifier == 'eye.bulbar-conjunctiva':
        label = L('Conjunctiva (white of the eye)', 'الملتحمة (بياض العين)', 'پەردەی سپێی چاو')
    node(identifier, 'body.eyes', 'structure', label, lateral=True, anchor_value=anchor('head', offset), related=related,
         internal=not visible, photo_visible=visible, specialty='ophthalmology',
         terms=T(*{
             'eye.upper-eyelid': (['eyelid', 'eyelids', 'upper lid', 'eye lid', 'lids'], ['جفن', 'الجفن', 'جفوني'], ['پێڵوو', 'پلک']),
             'eye.cornea': (['cornea'], ['قرنية', 'القرنية'], ['قەرنیە']),
             'eye.bulbar-conjunctiva': (['white of the eye', 'conjunctiva'], ['بياض العين', 'الملتحمة'], ['سپێنەی چاو']),
             'eye.retina': (['retina'], ['شبكية', 'الشبكية'], ['تۆڕینە']),
             'eye.lens': (['lens'], ['عدسة العين'], ['هاوێنەی چاو']),
         }.get(identifier, ((), (), ()))))

# ---------------------------------------------------------------- ears
node('ear.outer', 'body.ears', 'structure', L('Outer ear & canal', 'الأذن الخارجية والقناة', 'گوێی دەرەوە و جۆگە'), lateral=True,
     anchor_value=anchor('head', (.08, .085, .005)), photo_visible=True)
node('ear.middle', 'body.ears', 'structure', L('Middle ear (internal)', 'الأذن الوسطى (داخلية)', 'گوێی ناوەڕاست (ناوەکی)'), lateral=True,
     anchor_value=anchor('head', (.068, .085, .005)), internal=True,
     related=[('neck.throat', 'referred_pain', 'Throat infection can cause ear pain.')])

# ---------------------------------------------------------------- mouth and teeth
node('mouth.lips', 'body.mouth', 'structure', L('Lips', 'الشفتان', 'لێوەکان'), anchor_value=anchor('head', (0, .028, .118)), photo_visible=True,
     terms=T(['lip', 'lips'], ['شفة', 'شفايف', 'شفاه'], ['لێو']))
node('mouth.gums', 'body.mouth', 'structure', L('Gums', 'اللثة', 'پووک'), anchor_value=anchor('head', (0, .05, .108)), photo_visible=True, specialty='dentistry',
     terms=T(['gum', 'gums'], ['لثة', 'اللثة', 'لثتي'], ['پووک', 'پووکم']), related=[('mouth.teeth', 'adjacent', 'Gums support the teeth.')])
node('mouth.tongue', 'body.mouth', 'structure', L('Tongue', 'اللسان', 'زمان'), anchor_value=anchor('head', (0, .035, .095)), photo_visible=True,
     terms=T(['tongue'], ['لسان', 'لساني'], ['زمان', 'زمانم']))
node('mouth.oral-lining', 'body.mouth', 'structure', L('Inside of the mouth', 'بطانة الفم', 'ناوەوەی دەم'), anchor_value=anchor('head', (.025, .04, .095)), photo_visible=True,
     terms=T(['inside my mouth', 'inner cheek', 'inside my cheek', 'inside of my cheek'], ['داخل الفم', 'باطن الخد', 'داخل خدي'], ['ناو دەمم', 'ناوەوەی ڕوومەتم']))
node('mouth.teeth', 'body.mouth', 'group', L('Teeth', 'الأسنان', 'ددانەکان'), anchor_value=anchor('head', (0, .04, .11)), photo_visible=True, specialty='dentistry',
     terms=T(['tooth', 'teeth', 'molar', 'molars'], ['سن', 'سني', 'أسنان', 'اسنان', 'ضرس', 'ضرسي', 'أضراس'], ['ددان', 'ددانم', 'کاکیلە']),
     related=[('head.sinuses', 'referred_pain', 'Upper back-tooth pain can come from the sinuses.')])
node('mouth.bite', 'body.mouth', 'structure', L('Bite (how teeth meet)', 'العضة (تطابق الأسنان)', 'گەستن (یەکگرتنی ددان)'), anchor_value=anchor('head', (0, .04, .112)),
     specialty='orthodontics', terms=T(['bite', 'overbite', 'underbite', 'crossbite', 'open bite'], ['العضة', 'عضة'], ['گەستن']),
     related=[('head.jaw-joint', 'adjacent', 'Bite relationships load the jaw joints.')])

TOOTH = [('Central incisor', 'قاطع مركزي', 'ددانی پێشەوەی ناوەڕاست'), ('Lateral incisor', 'قاطع جانبي', 'ددانی پێشەوەی لاتەنیشت'),
         ('Canine', 'ناب', 'ددانی کەڵبە'), ('First premolar', 'ضاحك أول', 'یەکەم پێش-کاکیلە'), ('Second premolar', 'ضاحك ثانٍ', 'دووەم پێش-کاکیلە'),
         ('First molar', 'رحى أولى', 'یەکەم کاکیلە'), ('Second molar', 'رحى ثانية', 'دووەم کاکیلە'), ('Third molar (wisdom)', 'رحى ثالثة (ضرس العقل)', 'سێیەم کاکیلە (ددانی عەقڵ)')]
JAW = {'upper': ('upper', 'العلوي', 'سەرەوە'), 'lower': ('lower', 'السفلي', 'خوارەوە')}
SIDE = {'right': ('right', 'الأيمن', 'ڕاست'), 'left': ('left', 'الأيسر', 'چەپ')}
for quadrant in (1, 2, 3, 4):
    jaw = 'upper' if quadrant < 3 else 'lower'
    side = 'right' if quadrant in (1, 4) else 'left'
    for position in range(1, 9):
        fdi = quadrant * 10 + position
        en, ar, ckb = TOOTH[position - 1]
        sign = 1 if side == 'left' else -1
        offset = (sign * (.0045 + .0068 * (position - 1)), .047 if jaw == 'upper' else .031, .112 - .0032 * (position - 1) ** 1.3)
        node(f'tooth.fdi.{fdi}', 'mouth.teeth', 'tooth', L(f'{en}, {JAW[jaw][0]} {SIDE[side][0]} (FDI {fdi})',
                                                          f'{ar} {JAW[jaw][1]} {SIDE[side][1]} (FDI {fdi})',
                                                          f'{ckb}ی {JAW[jaw][2]}ی {SIDE[side][2]} (FDI {fdi})'),
             fixed_side=side, anchor_value=anchor('head', offset), photo_visible=position <= 6, specialty='dentistry',
             related=[('mouth.gums', 'adjacent', 'Supported by the surrounding gum.')])

# ---------------------------------------------------------------- neck
node('neck.throat', 'body.neck', 'structure', L('Throat', 'الحلق', 'گەروو'), anchor_value=anchor('neck', (0, .045, .055)),
     terms=T(['throat'], ['حلق', 'حلقي', 'بلعوم', 'زردوم'], ['گەروو', 'قوڕگ']), related=[('ear.middle', 'referred_pain', 'Throat pain can be felt in the ear.')])
node('neck.thyroid', 'body.neck', 'structure', L('Thyroid (front of neck)', 'الغدة الدرقية', 'گلاندی دەرەقی'), anchor_value=anchor('neck', (0, .0, .065)), internal=True)
node('neck.lymph-nodes', 'body.neck', 'structure', L('Neck glands (lymph nodes)', 'الغدد اللمفاوية في الرقبة', 'گرێ لیمفاوییەکانی مل'), lateral=True,
     anchor_value=anchor('neck', (.045, .04, .03)), terms=T(['glands', 'lymph node'], ['غدد', 'الغدد'], ['گرێ']))

# ---------------------------------------------------------------- chest
node('chest.chest-wall', 'body.chest', 'structure', L('Chest wall & ribs', 'جدار الصدر والأضلاع', 'دیواری سنگ و پەراسوو'), anchor_value=anchor('chest', (0, .075, .135)),
     terms=T(['rib', 'ribs', 'breastbone', 'sternum'], ['ضلع', 'أضلاع', 'اضلاع', 'عظم القص'], ['پەراسوو', 'ئێسکی سنگ']))
node('chest.heart', 'body.chest', 'structure', L('Heart (internal)', 'القلب (داخلي)', 'دڵ (ناوەکی)'), fixed_side=None, anchor_value=anchor('chest', (.035, .06, .1)), internal=True,
     terms=T(['heart'], ['قلب', 'قلبي'], ['دڵ', 'دڵم']),
     related=[('body.arms', 'referred_pain', 'Heart pain can spread to the arms, especially the left.'), ('head.jaw-joint', 'referred_pain', 'Heart pain can spread to the jaw.'),
              ('back.upper', 'referred_pain', 'Heart pain can spread to the back.')])
node('chest.lungs', 'body.chest', 'structure', L('Lungs (internal)', 'الرئتان (داخلي)', 'سییەکان (ناوەکی)'), lateral=True, anchor_value=anchor('chest', (.075, .09, .08)), internal=True,
     terms=T(['lung', 'lungs'], ['رئة', 'رئتي', 'الرئة'], ['سی', 'سییەکان']), related=[('leg.calf', 'clinical_link', 'A clot in a leg vein can travel to the lungs.')])
node('chest.breast', 'body.chest', 'structure', L('Breast', 'الثدي', 'مەمک'), lateral=True, anchor_value=anchor('chest', (.085, .02, .135)),
     terms=T(['breast'], ['ثدي', 'الثدي'], ['مەمک']), photo_visible=False)
node('chest.oesophagus', 'body.chest', 'structure', L('Food pipe (oesophagus)', 'المريء', 'سورێنچک'), anchor_value=anchor('chest', (0, .11, .06)), internal=True,
     related=[('abdomen.upper-central', 'adjacent', 'Acid from the stomach can irritate the food pipe.')])

# ---------------------------------------------------------------- abdomen (fixed sides follow patient anatomy)
node('abdomen.upper-central', 'body.abdomen', 'structure', L('Upper abdomen (below the breastbone)', 'أعلى البطن (تحت القص)', 'سەرەوەی سک (ژێر ئێسکی سنگ)'),
     anchor_value=anchor('spine', (0, .2, .125)), terms=T(['upper stomach', 'upper abdomen', 'epigastric'], ['فم المعدة', 'أعلى البطن', 'اعلى البطن'], ['سەرەوەی سک', 'دەمی گەدە']))
node('abdomen.right-upper', 'body.abdomen', 'structure', L('Upper right abdomen (liver, gallbladder)', 'أعلى يمين البطن (الكبد والمرارة)', 'سەرەوەی لای ڕاستی سک (جگەر و زراو)'),
     fixed_side='right', anchor_value=anchor('spine', (-.075, .17, .115)), internal=True,
     related=[('back.upper', 'referred_pain', 'Gallbladder pain can spread to the right shoulder blade.')])
node('abdomen.left-upper', 'body.abdomen', 'structure', L('Upper left abdomen', 'أعلى يسار البطن', 'سەرەوەی لای چەپی سک'), fixed_side='left',
     anchor_value=anchor('spine', (.075, .17, .115)), internal=True)
node('abdomen.central', 'body.abdomen', 'structure', L('Around the belly button', 'حول السرة', 'دەوری ناوک'), anchor_value=anchor('spine', (0, .1, .13)),
     terms=T(['belly button', 'navel'], ['السرة', 'سرة'], ['ناوک']), related=[('abdomen.right-lower', 'clinical_link', 'Appendix pain can start centrally and move to the lower right.')])
node('abdomen.right-lower', 'body.abdomen', 'structure', L('Lower right abdomen', 'أسفل يمين البطن', 'خوارەوەی لای ڕاستی سک'), fixed_side='right',
     anchor_value=anchor('spine', (-.075, .02, .12)), terms=T(['lower right'], ['أسفل اليمين', 'جهة اليمين تحت'], ['خوارەوەی ڕاست']))
node('abdomen.left-lower', 'body.abdomen', 'structure', L('Lower left abdomen', 'أسفل يسار البطن', 'خوارەوەی لای چەپی سک'), fixed_side='left',
     anchor_value=anchor('spine', (.075, .02, .12)))
node('abdomen.lower-central', 'body.abdomen', 'structure', L('Lower abdomen (bladder area)', 'أسفل البطن (منطقة المثانة)', 'خوارەوەی سک (ناوچەی میزڵدان)'),
     anchor_value=anchor('hips', (0, .06, .11)), terms=T(['bladder', 'lower abdomen'], ['المثانة', 'أسفل البطن', 'اسفل البطن'], ['میزڵدان', 'خوارەوەی سک']))
node('abdomen.flank', 'body.abdomen', 'structure', L('Side/flank (kidney area)', 'الخاصرة (منطقة الكلية)', 'تەنیشت (ناوچەی گورچیلە)'), lateral=True,
     anchor_value=anchor('spine', (.1, .12, -.03)), terms=T(['flank', 'kidney'], ['خاصرة', 'الخاصرة', 'كلية', 'الكلية'], ['گورچیلە', 'تەنیشتم']),
     related=[('abdomen.lower-central', 'clinical_link', 'Kidneys drain to the bladder.')])

# ---------------------------------------------------------------- back
node('back.upper', 'body.back', 'structure', L('Upper back', 'أعلى الظهر', 'سەرەوەی پشت'), anchor_value=anchor('chest', (0, .08, -.11)),
     terms=T(['upper back', 'shoulder blade'], ['أعلى الظهر', 'لوح الكتف'], ['سەرەوەی پشت']))
node('back.lower', 'body.back', 'structure', L('Lower back', 'أسفل الظهر', 'خوارەوەی پشت'), anchor_value=anchor('spine', (0, .04, -.11)),
     terms=T(['lower back'], ['أسفل الظهر', 'اسفل الظهر', 'الظهر السفلي'], ['ناوقەد', 'خوارەوەی پشت']),
     related=[('leg.thigh', 'referred_pain', 'A trapped nerve in the lower back can cause pain down the leg (sciatica).')])

# ---------------------------------------------------------------- arms (lateral)
for identifier, label, value, terms in [
    ('arm.shoulder', L('Shoulder', 'الكتف', 'شان'), anchor('upperArm', (0, .02, .0)), T(['shoulder'], ['كتف', 'كتفي'], ['شان', 'شانم'])),
    ('arm.upper-arm', L('Upper arm', 'العضد', 'بازوو'), anchor('upperArm', (0, 0, .02), to='forearm', t=.5), T(['upper arm', 'bicep'], ['العضد', 'زند'], ['بازوو'])),
    ('arm.elbow', L('Elbow', 'المرفق', 'ئانیشک'), anchor('forearm', (0, 0, .0)), T(['elbow'], ['كوع', 'مرفق', 'الكوع'], ['ئانیشک'])),
    ('arm.forearm', L('Forearm', 'الساعد', 'باسک'), anchor('forearm', (0, 0, .015), to='hand', t=.5), T(['forearm'], ['ساعد', 'الساعد'], [])),
    ('arm.wrist', L('Wrist', 'الرسغ', 'مەچەک'), anchor('hand', (0, .01, .01)), T(['wrist'], ['رسغ', 'معصم', 'الرسغ'], ['مەچەک'])),
    ('arm.hand', L('Hand & fingers', 'اليد والأصابع', 'دەست و پەنجە'), anchor('hand', (0, -.07, .015)), T(['hand', 'finger', 'fingers', 'thumb'], ['كف', 'أصابع', 'اصابع', 'إبهام'], ['پەنجە', 'لەپ'])),
]:
    related = []
    if identifier == 'arm.wrist':
        related = [('arm.hand', 'clinical_link', 'A compressed nerve at the wrist causes hand tingling (carpal tunnel).')]
    if identifier == 'arm.shoulder':
        related = [('body.neck', 'referred_pain', 'Neck problems can cause shoulder and arm pain.')]
    node(identifier, 'body.arms', 'structure', label, lateral=True, anchor_value=value, terms=terms, related=related)

# ---------------------------------------------------------------- legs (lateral)
for identifier, label, value, terms in [
    ('leg.hip', L('Hip', 'الورك', 'سمت'), anchor('thigh', (0, .02, .02)), T(['hip'], ['ورك', 'وركي', 'حوض'], ['سمت', 'کەفەڵ'])),
    ('leg.thigh', L('Thigh', 'الفخذ', 'ران'), anchor('thigh', (0, 0, .04), to='shin', t=.5), T(['thigh'], ['فخذ', 'فخذي'], ['ران'])),
    ('leg.knee', L('Knee', 'الركبة', 'ئەژنۆ'), anchor('shin', (0, .01, .05)), T(['knee'], ['ركبة', 'ركبتي', 'الركبة'], ['ئەژنۆ', 'ئەژنۆم'])),
    ('leg.calf', L('Calf & shin', 'ربلة الساق', 'پشتی لاق'), anchor('shin', (0, 0, -.02), to='foot', t=.45), T(['calf', 'shin'], ['ربلة', 'سمانة', 'بطة الرجل', 'قصبة الساق'], ['پشتی لاق'])),
    ('leg.ankle', L('Ankle', 'الكاحل', 'گوێزینگ'), anchor('foot', (0, .0, .02)), T(['ankle'], ['كاحل', 'الكاحل', 'كعب الرجل'], ['گوێزینگ', 'قوڵەپێ'])),
    ('leg.foot', L('Foot & heel', 'القدم والكعب', 'پێ و پاژنە'), anchor('foot', (0, -.04, .07)), T(['foot', 'heel', 'toe', 'toes'], ['قدم', 'كعب', 'أصابع القدم'], ['پاژنە', 'پەنجەی پێ'])),
]:
    related = [('chest.lungs', 'clinical_link', 'A clot in a leg vein can travel to the lungs.')] if identifier == 'leg.calf' else []
    node(identifier, 'body.legs', 'structure', label, lateral=True, anchor_value=value, terms=terms, related=related)

node('skin.general', 'body.skin', 'structure', L('Skin surface', 'سطح الجلد', 'ڕووی پێست'), anchor_value=None, photo_visible=True,
     terms=T(['rash', 'mole'], ['شامة', 'خال'], ['خاڵ']))

ids = [item['id'] for item in nodes]
assert len(ids) == len(set(ids)), 'duplicate anatomy id'
for item in nodes:
    assert item['parent'] is None or item['parent'] in ids, item['id']
    for relation in item['related']:
        assert relation['target'] in ids, (item['id'], relation['target'])

contract = {
    'schema_version': 'humantwin-anatomy-v1',
    'version': 'anatomy-2026-11-16.1',
    'conventions': {
        'side': 'Always the patient\'s side. Lateral structures carry side separately from the ID.',
        'teeth': 'FDI two-digit notation; quadrants 1 and 4 are the patient\'s right.',
        'anchors': 'Illustrative marker positions on the bundled reference body (+x = patient left, faces +z). Not measured patient anatomy.',
        'bones': ['hips', 'spine', 'chest', 'neck', 'head', 'upperArm', 'forearm', 'hand', 'thigh', 'shin', 'foot'],
    },
    'clinical_review_status': 'draft',
    'translation_review_status': {'en': 'draft', 'ar': 'draft — native medical review pending', 'ckb': 'draft — native medical review pending'},
    'nodes': nodes,
}
out = ROOT / 'contracts/clinical/anatomy.v1.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(contract, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print(f'{len(nodes)} anatomy nodes -> {out.relative_to(ROOT)}')
