/** Editable, versioned educational content. No clinical or translation approval is asserted. */
import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { anatomyTranslations } from './eye-anatomy-translations.mjs'
const root = fileURLToPath(new URL('../contracts/eye/', import.meta.url))
mkdirSync(root, { recursive: true })
const version = 'eye-draft-2026-10-30.2'
const localized = (en, ar, ckb) => ({ en, 'ar-IQ': ar, ckb })
const meta = { version, clinical_review_status: 'draft', clinical_reviewed_at: null, translation_review_status: { en: 'draft', 'ar-IQ': 'draft', ckb: 'draft' }, source_checked_at: '2026-10-30', clinical_use_available: false }
const save = (name, data) => writeFileSync(`${root}${name}.v1.json`, JSON.stringify({ ...meta, ...data }, null, 2) + '\n')
const groups = [
 ['surface','Lids & surface','الجفون والسطح','پلک و ڕووکار'], ['tears','Tear system','جهاز الدمع','سیستەمی فرمێسک'],
 ['cornea','Cornea','القرنية','قەرنیە'], ['coats','Eye wall','جدار العين','دیواری چاو'], ['focus','Iris & lens','القزحية والعدسة','قازحیە و عەدەسە'],
 ['fluid','Fluid & drainage','السائل وتصريفه','شلە و دەرچوونی'], ['vitreous','Vitreous','الجسم الزجاجي','جەستەی شووشەیی'],
 ['retina','Retina','الشبكية','تۆڕینە'], ['nerve','Optic nerve','العصب البصري','دەمارە بیناییەکە'], ['orbit','Orbit & movement','الحجاج والحركة','کاسەی چاو و جووڵە']
].map(([id,en,ar,ckb])=>({id,label:localized(en,ar,ckb)}))
// id | English | Iraqi Arabic draft | Sorani draft | function (original English) | shape | x,y,z | scale x,y,z
const anatomyRows = {
 surface: `upper-eyelid|Upper eyelid|الجفن العلوي|پلکی سەرەوە|Protects the eye and spreads tears when blinking.|lid|0,.63,.79|1.05,.25,.12
lower-eyelid|Lower eyelid|الجفن السفلي|پلکی خوارەوە|Protects the lower surface and supports the tear meniscus.|lid|0,-.59,.79|1.05,.18,.12
eyelid-margin|Eyelid margins|حواف الجفون|لێواری پلکەکان|The lid edges contain lash roots and meibomian gland openings.|ring|0,0,.91|1,.65,.04
eyelashes|Eyelashes|الرموش|برژانگ|Help protect the ocular surface from particles.|lashes|0,.72,.96|1,.2,.1
medial-canthus|Medial canthus|زاوية العين الداخلية|گۆشەی ناوەوەی چاو|The eyelids meet on the nasal side near the tear drainage openings.|dot|1,.02,.84|.13,.13,.12
lateral-canthus|Lateral canthus|زاوية العين الخارجية|گۆشەی دەرەوەی چاو|The eyelids meet on the temporal side.|dot|-1,.02,.84|.1,.09,.08
lacrimal-caruncle|Lacrimal caruncle|اللحيمة الدمعية|گۆشتۆکەی فرمێسکی|Small pink tissue at the inner corner of the eye.|dot|.91,-.04,.94|.1,.07,.06
meibomian-glands|Meibomian glands|غدد ميبوميان|ڕژێنەکانی میبۆمیان|Glands inside the lids supply oil that limits tear evaporation.|glands|0,.78,.78|.8,.13,.06
bulbar-conjunctiva|Bulbar conjunctiva|ملتحمة مقلة العين|پەردەی ڕووپۆشی گۆی چاو|A thin membrane covers the front sclera, stopping at the corneal edge.|shell|0,0,0|1.014,1.014,1.014
palpebral-conjunctiva|Palpebral conjunctiva|ملتحمة الجفن|پەردەی ناوەوەی پلک|Lines the inner eyelids.|lid|0,.57,.72|.95,.2,.04
conjunctival-fornices|Conjunctival fornices|جيوب الملتحمة|قووڵاییەکانی پەردەی چاو|Folds join the lid lining to the globe covering and permit movement.|ring|0,0,.62|1.05,.82,.04`,
 tears: `tear-film|Tear film|طبقة الدمع|چینی فرمێسک|A thin surface film lubricates, protects and smooths the optical surface.|cap|0,0,1.031|.62,.62,.12
lacrimal-gland|Lacrimal gland|الغدة الدمعية|ڕژێنی فرمێسک|Produces aqueous tears in the upper temporal orbit.|gland|-.95,.86,.32|.31,.18,.16
upper-punctum|Upper lacrimal punctum|فتحة الدمع العلوية|کونەی سەرەوەی فرمێسک|An opening near the nasal upper lid drains tears.|dot|.85,.2,.96|.045,.045,.04
lower-punctum|Lower lacrimal punctum|فتحة الدمع السفلية|کونەی خوارەوەی فرمێسک|An opening near the nasal lower lid drains tears.|dot|.85,-.2,.96|.045,.045,.04
canaliculi|Lacrimal canaliculi|القنيّات الدمعية|بۆرییە بچووکەکانی فرمێسک|Small channels connect the puncta to the lacrimal sac.|tube|1.02,0,.85|.04,.24,.04
lacrimal-sac|Lacrimal sac|كيس الدمع|کیسی فرمێسک|Collects tears on the nasal side before drainage to the nose.|gland|1.17,-.12,.67|.11,.23,.1
nasolacrimal-duct|Nasolacrimal duct|القناة الأنفية الدمعية|بۆری لووت و فرمێسک|Carries tears from the sac toward the inferior nasal passage.|tube|1.17,-.64,.58|.07,.4,.07`,
 cornea: `cornea|Cornea|القرنية|قەرنیە|The transparent front surface bends incoming light.|cap|0,0,.91|.63,.63,.28
limbus|Limbus|حافة القرنية|لێواری قەرنیە|Junction of the cornea and sclera.|ring|0,0,.87|.64,.64,.035
corneal-epithelium|Corneal epithelium|ظهارة القرنية|ئەپیثیلیۆمی قەرنیە|The outer epithelial barrier protects the cornea.|micro|0,0,0|1,1,1
bowmans-layer|Bowman’s layer|طبقة بومان|چینی بۆمان|A collagenous layer beneath the corneal epithelium.|micro|0,0,0|1,1,1
corneal-stroma|Corneal stroma|سدى القرنية|سترۆمای قەرنیە|Organized collagen provides most corneal thickness and clarity.|micro|0,0,0|1,1,1
descemets-membrane|Descemet’s membrane|غشاء ديسميت|پەردەی دێسمێت|The basement membrane supporting the corneal endothelium.|micro|0,0,0|1,1,1
corneal-endothelium|Corneal endothelium|بطانة القرنية|ئەندۆثیلیۆمی قەرنیە|Cells regulate corneal hydration to preserve transparency.|micro|0,0,0|1,1,1`,
 coats: `episclera|Episclera|فوق الصلبة|ڕووپۆشی سکلێرا|A vascular connective tissue layer lies over the sclera.|shell|0,0,0|1.005,1.005,1.005
sclera|Sclera|الصلبة|سکلێرا|The tough outer coat supports and protects the globe.|shell|0,0,0|1,1,1
choroid|Choroid|المشيمية|کۆرۆید|The vascular coat between sclera and retina nourishes the outer retina.|shell|0,0,0|.958,.958,.958`,
 focus: `iris|Iris|القزحية|قازحیە|A muscular diaphragm controls the size of its central opening, the pupil.|iris|0,0,.77|.58,.58,.035
pupil|Pupil opening|فتحة البؤبؤ|کونی بیلبیلە|An opening in the iris, not a solid anatomical disc; light passes through it.|opening|0,0,.78|.225,.225,.02
ciliary-body|Ciliary body|الجسم الهدبي|جەستەی مژۆڵکەیی|Includes aqueous-producing processes and the focusing muscle.|ring|0,0,.48|.78,.78,.12
ciliary-muscle|Ciliary muscle|العضلة الهدبية|ماسولکەی مژۆڵکەیی|Changes zonular tension to alter lens shape for focusing.|ring|0,0,.48|.8,.8,.07
ciliary-processes|Ciliary processes|النواتئ الهدبية|پڕۆسەکانی مژۆڵکەیی|Folded tissue produces aqueous humour.|processes|0,0,.5|.67,.67,.08
zonular-fibres|Zonular fibres|ألياف الزونول|ڕیشاڵەکانی زۆنول|Suspend the lens between its capsule and the ciliary body.|spokes|0,0,.47|.64,.64,.02
lens|Lens|العدسة|عەدەسە|A transparent biconvex structure behind the iris focuses light onto the retina.|lens|0,0,.41|.4,.4,.19
lens-capsule|Lens capsule|محفظة العدسة|کەپسوولی عەدەسە|An elastic envelope surrounds the lens.|lens|0,0,.41|.414,.414,.201`,
 fluid: `anterior-chamber|Anterior chamber|الحجرة الأمامية|ژووری پێشەوە|The aqueous-filled space between cornea and iris.|cap|0,0,.91|.54,.54,.11
posterior-chamber|Posterior chamber|الحجرة الخلفية|ژووری دواوە|A narrow aqueous-filled space behind the iris, in front of the lens and ciliary body; not the vitreous chamber.|ring|0,0,.64|.5,.5,.035
aqueous-humour|Aqueous humour|الخلط المائي|شلەی ئاوی|Fluid produced by the ciliary processes flows through the pupil to the anterior chamber.|cap|0,0,.87|.52,.52,.075
drainage-angle|Drainage angle|زاوية التصريف|گۆشەی دەرچوونی شلە|The angle where the peripheral cornea meets the iris contains drainage tissues.|ring|0,0,.77|.61,.61,.025
trabecular-meshwork|Trabecular meshwork|الشبكة التربيقية|تۆڕی ترابێکولار|Aqueous passes through this tissue at the drainage angle.|ring|0,0,.78|.63,.63,.02
schlemms-canal|Schlemm’s canal|قناة شليم|کەناڵی شلێم|Collects aqueous draining through the trabecular meshwork.|ring|0,0,.79|.66,.66,.018`,
 vitreous: `vitreous-chamber|Vitreous chamber|الحجرة الزجاجية|ژووری شووشەیی|The large cavity behind the lens and in front of the retina.|volume|0,0,-.14|.86,.86,.71
vitreous-body|Vitreous body|الجسم الزجاجي|جەستەی شووشەیی|A transparent gel fills most of the globe behind the lens.|volume|0,0,-.14|.84,.84,.7
posterior-vitreous-interface|Posterior vitreous interface|السطح الزجاجي الخلفي|ڕووپۆشی پشتی شووشەیی|The posterior vitreous cortex contacts the inner retina.|shell|0,0,-.08|.89,.89,.81`,
 retina: `retina|Retina|الشبكية|تۆڕینە|Light-sensitive neural tissue lines the inner posterior globe.|shell|0,0,0|.93,.93,.93
retinal-pigment-epithelium|Retinal pigment epithelium|الظهارة الصباغية للشبكية|ئەپیثیلیۆمی ڕەنگداری تۆڕینە|A cell layer outside photoreceptors supports their function.|micro|0,0,0|1,1,1
photoreceptors|Photoreceptor detail|المستقبلات الضوئية|وەرگرەکانی ڕووناکی|Rods and cones convert light into signals; shown in a magnified educational view.|micro|0,0,0|1,1,1
peripheral-retina|Peripheral retina|الشبكية المحيطية|دەوروبەری تۆڕینە|Retina outside the central macula supports peripheral vision.|ring|0,0,-.53|.72,.72,.035
macula|Macula|البقعة الصفراء|ماکولا|Central posterior retina, temporal to the optic disc, supports detailed vision.|patch|-.32,0,-.878|.19,.19,.022
fovea|Fovea|النقرة المركزية|فۆڤیا|A small central depression within the macula provides sharp central vision.|patch|-.32,0,-.905|.055,.055,.018
retinal-vessels|Retinal blood vessels|الأوعية الدموية للشبكية|ڕەگە خوێنییەکانی تۆڕینە|Branch from the optic disc across the inner retina.|vessels|.3,0,-.88|.65,.65,.03`,
 nerve: `optic-disc|Optic disc|القرص البصري|دیسکی بینایی|Retinal nerve fibres leave the eye here, nasal to the macula; there are no photoreceptors at the disc.|patch|.3,0,-.88|.105,.13,.025
optic-nerve|Optic nerve|العصب البصري|دەمارە بیناییەکە|Carries retinal signals toward the brain, exiting posteriorly at the optic disc.|nerve|.38,0,-1.32|.14,.14,.43`,
 orbit: `bony-orbit|Bony orbit|الحجاج العظمي|کاسەی ئێسکی چاو|The bony socket surrounds and protects orbital contents.|orbit|0,0,-.2|1.4,1.3,1.2
orbital-fat|Orbital fat|دهون الحجاج|چەوری کاسەی چاو|Cushions the globe and occupies spaces around muscles and nerves.|fat|0,0,-.3|1.18,1.1,.95
superior-rectus|Superior rectus|المستقيمة العلوية|ماسولکەی ڕاستی سەرەوە|Mainly elevates the eye; its action also depends on eye position.|muscle|0,1,-.35|.16,.1,.65
inferior-rectus|Inferior rectus|المستقيمة السفلية|ماسولکەی ڕاستی خوارەوە|Mainly depresses the eye.|muscle|0,-1,-.35|.16,.1,.65
medial-rectus|Medial rectus|المستقيمة الإنسية|ماسولکەی ڕاستی ناوەوە|Turns the eye toward the nose.|muscle|1,0,-.35|.1,.16,.65
lateral-rectus|Lateral rectus|المستقيمة الوحشية|ماسولکەی ڕاستی دەرەوە|Turns the eye toward the temple.|muscle|-1,0,-.35|.1,.16,.65
superior-oblique|Superior oblique|المائلة العلوية|ماسولکەی لارەکی سەرەوە|Passes through the superonasal trochlea and helps rotate and depress the eye.|oblique|.55,.92,-.24|.5,.08,.4
inferior-oblique|Inferior oblique|المائلة السفلية|ماسولکەی لارەکی خوارەوە|Runs from the anterior medial orbital floor beneath the globe toward its temporal posterior surface.|oblique|-.22,-.92,-.1|.7,.09,.2
levator-palpebrae|Levator palpebrae superioris|رافعة الجفن العلوي|بەرزکەرەوەی پلکی سەرەوە|Raises the upper eyelid above the superior rectus.|muscle|0,1.15,-.25|.24,.07,.7`
}
const structures = Object.entries(anatomyRows).flatMap(([group, rows]) => rows.split('\n').map(row => {
 const [id,en,ar,ckb,explanation,shape,position,scale] = row.split('|')
 return { id:`eye.${id}`, group, label:localized(en,ar,ckb), function:localized(explanation,`مسودة تعليمية عن ${ar}. النص الإنكليزي الأصلي معروض أدناه ويحتاج مراجعة طبية وترجمة.`,`ڕەشنووسی فێرکاری دەربارەی ${ckb}. دەقی ئینگلیزی لە خوارەوەیە و پێویستی بە پێداچوونەوەی پزیشکی و وەرگێڕان هەیە.`), shape, position:position.split(',').map(Number), scale:scale.split(',').map(Number), preferred_view:shape==='micro'?(group==='cornea'?'corneal-detail':'retinal-detail'):['retina','nerve'].includes(group)?'posterior':['focus','fluid','vitreous','coats'].includes(group)?'section':group==='orbit'?'transparent':'external', source_ids:['anatomy-msd','anatomy-aao'], clinical_review_status:'draft' }
}))
for(const structure of structures){
 const translation=anatomyTranslations[structure.id]
 if(!translation)throw new Error(`Missing draft anatomy translation: ${structure.id}`)
 Object.assign(structure.function,translation)
 structure.translation_review_status={'ar-IQ':'draft-awaiting-medical-review',ckb:'draft-awaiting-medical-review'}
}
save('anatomy', { groups, structures, anatomical_convention: 'Positive model x is nasal before patient-side reflection. Anterior is +z; superior is +y. Macula is temporal to the optic disc. Camera movement never changes patient laterality.', model_limitations:['Procedural schematic; not a patient-specific reconstruction or surgical reference.','Fine layers are magnified and thicknesses are deliberately exaggerated.','Muscles show principal paths, not validated insertion geometry.'] })
save('review', { intended_use:'Synthetic educational exploration only', approved_for_live_triage:false, required_reviews:['Ophthalmologist: every anatomical relationship, condition, question and urgency pathway','Native Kurdish Sorani and Iraqi Arabic medical translators','Iraq clinical operations: local access pathways and emergency directions','Independent usability, clinical performance, privacy and deployment evaluation'], approval:null })
console.log(`Wrote ${structures.length} draft anatomical structures.`)
