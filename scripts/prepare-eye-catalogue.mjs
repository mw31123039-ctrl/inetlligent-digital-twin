/** Curated short paraphrases, not diagnostic rules. Run source audit separately. */
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { conditionTranslations } from './eye-condition-translations.mjs'
const dir=fileURLToPath(new URL('../contracts/eye/',import.meta.url))
const loc=(en,ar,ckb)=>({en,'ar-IQ':ar,ckb})
const categoryRows=[
 ['lids','Eyelids & eyelashes','الجفون والرموش','پلک و برژانگ','surface','Lid examination and slit-lamp assessment.','Skin inflammation, lid gland problems, age-related changes or prior surgery.'],
 ['tears','Tears & drainage','الدموع والتصريف','فرمێسک و دەرچوونی','tears','Tear film, ocular surface and drainage assessment.','Ageing, medicines, inflammation, contact lenses or blocked drainage.'],
 ['conjunctiva','Conjunctiva','الملتحمة','پەردەی چاو','surface','Visual acuity and slit-lamp assessment; samples only when indicated.','Allergen or infection exposure, irritation or sunlight.'],
 ['cornea','Cornea','القرنية','قەرنیە','cornea','Visual acuity, slit lamp and fluorescein; corneal imaging or cultures when indicated.','Contact lenses, trauma, exposure, family history or surface disease.'],
 ['corneal-infection','Infectious corneal disease','أمراض القرنية المعدية','تووشبوونی قەرنیە بە میکرۆب','cornea','Urgent slit-lamp examination; scraping, culture or PCR as clinically indicated.','Contact lenses, water exposure, trauma or reduced immunity.'],
 ['sclera','Sclera','الصلبة','سکلێرا','coats','Slit-lamp assessment; systemic evaluation when indicated.','Inflammatory or autoimmune disease; some cases have no identified cause.'],
 ['uvea','Uvea','العنبية','یوڤیا','focus','Slit lamp, dilated examination and targeted systemic or infection testing.','Infection, immune inflammation, systemic disease or no identified cause.'],
 ['lens','Lens','العدسة','عەدەسە','focus','Visual acuity, refraction and slit-lamp assessment.','Age, family history, trauma, diabetes or certain medicines.'],
 ['pressure','Pressure & drainage','الضغط والتصريف','فشار و دەرچوونی شلە','fluid','Eye pressure, gonioscopy, optic nerve assessment, OCT and visual fields.','Age, family history, eye anatomy, medicines or other eye disease.'],
 ['vitreous','Vitreous','الجسم الزجاجي','جەستەی شووشەیی','vitreous','Dilated retinal examination; ultrasound if the view is obscured.','Ageing, myopia, diabetes, injury or retinal disease.'],
 ['retina','Retina & macula','الشبكية والبقعة','تۆڕینە و ماکولا','retina','Dilated fundus examination and OCT; vascular imaging when indicated.','Age, myopia, diabetes, high blood pressure or vascular disease.'],
 ['inherited','Inherited retinal conditions','أمراض الشبكية الوراثية','نەخۆشییە بۆماوەییەکانی تۆڕینە','retina','Retinal imaging, visual function tests, family history and genetic counselling/testing.','Inherited genetic changes; age of onset varies by condition.'],
 ['nerve','Optic nerve & disc findings','العصب والقرص البصري','دەمار و دیسکی بینایی','nerve','Pupils, colour vision, fields, optic nerve examination and targeted imaging/laboratory tests.','Vascular, inflammatory, compressive, inherited or toxic causes.'],
 ['refraction','Refraction & visual development','الانكسار وتطور النظر','شکاندنەوەی ڕووناکی و گەشەی بینین','focus','Age-appropriate visual acuity, refraction and examination.','Eye shape, ageing, family history or unequal visual development.'],
 ['movement','Alignment & movement','المحاذاة والحركة','ڕیزبوون و جووڵە','orbit','Eye alignment, motility, binocular function and neurological assessment when indicated.','Childhood visual development, nerve disease or muscle imbalance.'],
 ['orbit','Orbit','الحجاج','کاسەی چاو','orbit','Vision, pupils and eye movement; orbital imaging and blood tests when indicated.','Sinus disease, infection, thyroid or other inflammation, or a mass.'],
 ['injury','Injury & procedures','الإصابات والإجراءات','برینداری و کردارەکان','cornea','Urgent eye examination; imaging when appropriate. Avoid pressure if penetration is suspected.','Chemical exposure, trauma, ultraviolet exposure or a recent procedure.'],
 ['childhood','Childhood & congenital conditions','أمراض الطفولة والخلقية','نەخۆشییەکانی منداڵی و لەدایکبوون','retina','Paediatric eye examination, red reflex assessment and targeted imaging/genetic evaluation.','Prematurity, inherited changes or altered development before birth.'],
 ['systemic','Tumours & systemic causes','الأورام والأسباب العامة','گرێ و هۆکارە گشتییەکان','nerve','Specialist eye examination and targeted systemic, imaging or tissue investigations.','Age, systemic inflammation, vascular risks, inherited changes or medicine exposure.']
]
const categories=categoryRows.map(([id,en,ar,ckb,group,examination,risks])=>({id,label:loc(en,ar,ckb),anatomy_group:group,examination,risks}))
// id | name en | name ar | name ckb | explanation | structures | symptoms | condition-specific source hint | synonyms
const rows={
 lids:`blepharitis|Blepharitis|التهاب حواف الجفن|هەوکردنی لێواری پلک|Inflammation of the lid edges may cause irritation and crusting.|eyelid-margin,eyelashes|crusting,itching,burning|msd:blepharitis|lid inflammation
meibomian-dysfunction|Meibomian gland dysfunction|خلل غدد ميبوميان|تێکچوونی ڕژێنەکانی میبۆمیان|Reduced or altered lid oil can destabilize the tear film.|meibomian-glands,tear-film|dryness,burning|wiki:Meibomian_Gland_Dysfunction|MGD
stye|Stye / hordeolum|شحاذ العين|گولەی پلک|A localized acute lid gland infection can form a tender lump.|eyelid-margin,eyelashes|lid-lump,pain|msd:chalazion-and-hordeolum-stye|hordeolum
chalazion|Chalazion|بردة الجفن|کیسی پلک|A blocked meibomian gland may cause a persistent lid nodule.|meibomian-glands,upper-eyelid|lid-lump,swelling|msd:chalazion-and-hordeolum-stye|meibomian cyst
ptosis|Ptosis|تدلي الجفن|داکەوتنی پلک|The upper lid sits lower than expected; the cause needs assessment.|upper-eyelid,levator-palpebrae|drooping|aapos:ptosis|drooping lid
entropion|Entropion|انقلاب الجفن للداخل|وەرگەڕانی پلک بۆ ناوەوە|The lid turns inward so lashes may rub the eye.|lower-eyelid,cornea|watering,foreign-body|msd:entropion-and-ectropion|inward lid
ectropion|Ectropion|انقلاب الجفن للخارج|وەرگەڕانی پلک بۆ دەرەوە|An outward-turning lid may expose the surface and impair tear drainage.|lower-eyelid,lower-punctum|watering,dryness|msd:entropion-and-ectropion|outward lid
trichiasis|Trichiasis|انحراف الرموش|لاربوونی برژانگ|Misdirected lashes rub against the eye surface.|eyelashes,cornea|foreign-body,pain|msd:trichiasis|misdirected lashes
lagophthalmos|Lagophthalmos|عدم انغلاق الجفن|داخراونەبوونی تەواوی پلک|Incomplete eyelid closure can expose and damage the cornea.|upper-eyelid,cornea|dryness,burning|wiki:Lagophthalmos|incomplete lid closure
lid-dermatitis|Eyelid dermatitis|التهاب جلد الجفن|هەوکردنی پێستی پلک|Inflamed lid skin may be itchy, scaly or swollen.|upper-eyelid,lower-eyelid|itching,swelling|wiki:Eyelid_Contact_Dermatitis|contact dermatitis
lid-lesion|Eyelid lesions|آفات الجفن|گۆڕانکارییەکانی پلک|Lid growths have several causes and sometimes need tissue examination.|upper-eyelid,eyelid-margin|lid-lump|msd:eyelid-growths|eyelid growth`,
 tears:`aqueous-dry-eye|Aqueous-deficient dry eye|جفاف نقص الدمع|وشکی چاو بەهۆی کەمی فرمێسک|Insufficient aqueous tears can disturb the ocular surface.|lacrimal-gland,tear-film|dryness,grittiness|msd:keratoconjunctivitis-sicca|aqueous deficiency
evaporative-dry-eye|Evaporative dry eye|الجفاف التبخري|وشکی چاو بەهۆی هەڵمبوون|Excess tear evaporation may cause burning and fluctuating blur.|tear-film,meibomian-glands|burning,blurred-vision|msd:keratoconjunctivitis-sicca|evaporative tear deficiency
tear-obstruction|Tear drainage obstruction|انسداد مجرى الدمع|گیرانی ڕێڕەوی فرمێسک|Tears drain poorly when part of the drainage pathway is narrowed or blocked.|canaliculi,lacrimal-sac,nasolacrimal-duct|watering|msd:dacryostenosis|nasolacrimal obstruction
dacryocystitis|Dacryocystitis|التهاب كيس الدمع|هەوکردنی کیسی فرمێسک|Infection of the tear sac can cause painful swelling near the nose.|lacrimal-sac|swelling,pain,discharge|msd:dacryocystitis|
dacryoadenitis|Dacryoadenitis|التهاب الغدة الدمعية|هەوکردنی ڕژێنی فرمێسک|Inflammation of the lacrimal gland may cause upper outer lid swelling.|lacrimal-gland|swelling,pain|wiki:Dacryoadenitis|`,
 conjunctiva:`allergic-conjunctivitis|Allergic conjunctivitis|التهاب الملتحمة التحسسي|هەوکردنی هەستیاریی پەردەی چاو|Allergen-triggered surface inflammation commonly causes itching and watering.|bulbar-conjunctiva,palpebral-conjunctiva|itching,watering|msd:allergic-conjunctivitis|
viral-conjunctivitis|Viral conjunctivitis|التهاب الملتحمة الفيروسي|هەوکردنی ڤایرۆسی پەردەی چاو|Viral surface infection may cause redness and watery discharge.|bulbar-conjunctiva|redness,watering|msd:viral-conjunctivitis|pink eye
bacterial-conjunctivitis|Bacterial conjunctivitis|التهاب الملتحمة البكتيري|هەوکردنی بەکتریایی پەردەی چاو|Bacterial surface infection can cause discharge and redness; symptoms alone cannot confirm the organism.|bulbar-conjunctiva|redness,discharge|msd:acute-bacterial-conjunctivitis|
subconjunctival-haemorrhage|Subconjunctival haemorrhage|نزف تحت الملتحمة|خوێنبەربوون لە ژێر پەردەی چاو|Blood under the conjunctiva forms a red patch; associated pain, injury or vision change needs assessment.|bulbar-conjunctiva|redness|msd:subconjunctival-hemorrhages|subconjunctival hemorrhage
pinguecula|Pinguecula|شحيمة الملتحمة|پینگۆکولا|A raised conjunctival change occurs beside the cornea.|bulbar-conjunctiva,limbus|foreign-body|msd:pinguecula-and-pterygium|
pterygium|Pterygium|ظفرة|پتەریجیۆم|Conjunctival tissue extends onto the cornea and can affect vision.|bulbar-conjunctiva,cornea|redness,blurred-vision|msd:pinguecula-and-pterygium|`,
 cornea:`corneal-abrasion|Corneal abrasion|خدش القرنية|خەوشی قەرنیە|An epithelial scratch may cause pain, watering and light sensitivity.|corneal-epithelium|pain,watering,light-sensitivity|wiki:Corneal_Abrasion|
corneal-foreign-body|Corneal foreign body|جسم غريب بالقرنية|تەنێکی نامۆ لە قەرنیە|A surface particle can damage the cornea; high-speed injuries may penetrate deeper.|cornea|foreign-body,pain|wiki:Removal_of_Corneal_Foreign_Bodies|
recurrent-erosion|Recurrent corneal erosion|تآكل القرنية المتكرر|خەوشی دووبارەی قەرنیە|Poor epithelial attachment can lead to repeated painful surface breakdown.|corneal-epithelium,bowmans-layer|pain,watering|wiki:Recurrent_Corneal_Erosion|
infectious-keratitis|Infectious keratitis|التهاب القرنية المعدي|هەوکردنی میکرۆبی قەرنیە|Corneal infection may threaten sight and needs urgent examination.|cornea,corneal-stroma|pain,redness,blurred-vision|msd:corneal-ulcer|microbial keratitis
corneal-ulcer|Corneal ulcer|قرحة القرنية|برینی قەرنیە|Loss of corneal epithelium with stromal inflammation requires urgent assessment.|corneal-epithelium,corneal-stroma|pain,light-sensitivity,blurred-vision|msd:corneal-ulcer|
exposure-keratopathy|Exposure keratopathy|اعتلال القرنية بالتعرض|زیانی قەرنیە بەهۆی بەرکەوتن|Incomplete protection of the surface can damage the corneal epithelium.|cornea,upper-eyelid|dryness,pain|wiki:Exposure_Keratopathy|
keratoconus|Keratoconus|القرنية المخروطية|قەرنیەی کۆنی|Progressive corneal thinning and shape change can distort vision.|cornea,corneal-stroma|blurred-vision,glare|msd:keratoconus|
corneal-dystrophy|Corneal dystrophies|حثل القرنية|دیسترۆفی قەرنیە|Inherited corneal disorders can alter clarity or cause recurrent erosions.|cornea,corneal-stroma|blurred-vision,pain|nei:corneal-conditions|
fuchs-dystrophy|Fuchs’ endothelial dystrophy|حثل فوكس|دیسترۆفی فوکس|Loss of endothelial function may cause corneal swelling and blurred vision.|corneal-endothelium,descemets-membrane|blurred-vision,glare|msd:bullous-keratopathy|Fuchs dystrophy
corneal-scarring|Corneal scarring|تندب القرنية|برینی کۆنی قەرنیە|Scar tissue from injury or inflammation may reduce corneal clarity.|corneal-stroma|blurred-vision,glare|nei:corneal-conditions|`,
 'corneal-infection':`bacterial-keratitis|Bacterial keratitis|التهاب القرنية البكتيري|هەوکردنی بەکتریایی قەرنیە|Bacterial infection can rapidly damage corneal tissue.|cornea,corneal-stroma|pain,redness,blurred-vision|msd:corneal-ulcer|
fungal-keratitis|Fungal keratitis|التهاب القرنية الفطري|هەوکردنی کەڕوویی قەرنیە|Fungal corneal infection can follow plant injury or other exposures.|cornea|pain,redness|wiki:Fungal_Keratitis|
herpes-simplex-keratitis|Herpes simplex keratitis|التهاب القرنية بالهربس البسيط|هەوکردنی قەرنیە بە هێرپێسی سادە|Herpes simplex virus may cause recurrent corneal disease.|corneal-epithelium,corneal-stroma|pain,light-sensitivity|msd:herpes-simplex-keratitis|HSV keratitis
herpes-zoster-eye|Herpes zoster ophthalmicus|الحزام الناري العيني|هێرپێس زۆستەری چاو|Shingles affecting the forehead or nose may involve the eye.|cornea,upper-eyelid|pain,redness|msd:herpes-zoster-ophthalmicus|HZO
acanthamoeba-keratitis|Acanthamoeba keratitis|التهاب القرنية بالأكانثاميبا|هەوکردنی قەرنیە بە ئەکانتامێبا|Acanthamoeba infection can follow contaminated water exposure, particularly with contact lenses.|cornea|pain,blurred-vision|wiki:Acanthamoeba_Keratitis|`,
 sclera:`episcleritis|Episcleritis|التهاب فوق الصلبة|هەوکردنی ڕووپۆشی سکلێرا|Inflammation of the superficial tissue over the sclera causes redness.|episclera|redness,pain|msd:episcleritis|
scleritis|Scleritis|التهاب الصلبة|هەوکردنی سکلێرا|Deep scleral inflammation can cause severe pain and may accompany systemic disease.|sclera|pain,redness|msd:scleritis|`,
 uvea:`anterior-uveitis|Anterior uveitis / iritis|التهاب العنبية الأمامي|هەوکردنی یوڤیای پێشەوە|Inflammation mainly affects the anterior chamber and often the iris.|iris,anterior-chamber|pain,light-sensitivity|msd:overview-of-uveitis|iritis
intermediate-uveitis|Intermediate uveitis|التهاب العنبية المتوسط|هەوکردنی یوڤیای ناوەڕاست|Inflammation mainly involves the vitreous and peripheral retinal region.|vitreous-body,peripheral-retina|floaters,blurred-vision|msd:overview-of-uveitis|
posterior-uveitis|Posterior uveitis|التهاب العنبية الخلفي|هەوکردنی یوڤیای دواوە|Inflammation mainly involves the retina or choroid.|retina,choroid|floaters,blurred-vision|msd:overview-of-uveitis|
panuveitis|Panuveitis|التهاب العنبية الشامل|هەوکردنی هەموو یوڤیا|Inflammation affects anterior, intermediate and posterior eye regions.|iris,vitreous-body,choroid|blurred-vision,pain|msd:overview-of-uveitis|
choroiditis|Choroiditis|التهاب المشيمية|هەوکردنی کۆرۆید|Inflammation involves the choroid and may affect the adjacent retina.|choroid,retina|blurred-vision,blind-spots|msd:infectious-uveitis|`,
 lens:`age-cataract|Age-related cataract|الساد المرتبط بالعمر|کاتاراکتی پەیوەندیدار بە تەمەن|Age-related lens clouding can gradually reduce clarity and increase glare.|lens|blurred-vision,glare|msd:cataract/cataract|age-related lens opacity
congenital-cataract|Congenital cataract|الساد الخلقي|کاتاراکتی لەدایکبوون|Lens opacity present early in life can interfere with visual development.|lens|white-pupil,blurred-vision|aapos:cataract|childhood cataract
traumatic-cataract|Traumatic cataract|الساد الرضي|کاتاراکتی برینداری|Injury may cloud the lens, sometimes with other damage.|lens,lens-capsule|blurred-vision|msd:cataract/cataract|
medication-cataract|Medication-associated cataract|الساد المرتبط بالأدوية|کاتاراکتی پەیوەندیدار بە دەرمان|Some medicines are associated with lens clouding; do not stop treatment without medical advice.|lens|blurred-vision,glare|msd:cataract/cataract|
lens-displacement|Lens displacement|انزياح العدسة|جووڵانی عەدەسە لە شوێنی خۆی|Weak or disrupted zonules can let the lens move from its usual position.|lens,zonular-fibres|blurred-vision,double-vision|wiki:Ectopia_Lentis|ectopia lentis`,
 pressure:`open-angle-glaucoma|Open-angle glaucoma|الزرق مفتوح الزاوية|گلاوکۆمای گۆشەکراوە|Progressive optic nerve damage may occur without early symptoms.|optic-disc,trabecular-meshwork|blind-spots|msd:primary-open-angle-glaucoma|POAG
angle-closure-glaucoma|Angle-closure glaucoma|الزرق مغلق الزاوية|گلاوکۆمای گۆشەداخراو|Blocked drainage angle can raise pressure; an acute painful episode is an emergency.|drainage-angle,iris|pain,halos,blurred-vision|msd:angle-closure-glaucoma|acute angle closure
secondary-glaucoma|Secondary glaucoma|الزرق الثانوي|گلاوکۆمای لاوەکی|Other eye disease, injury or medicines can lead to glaucomatous nerve damage.|optic-disc,drainage-angle|blind-spots|msd:overview-of-glaucoma|
congenital-glaucoma|Congenital glaucoma|الزرق الخلقي|گلاوکۆمای لەدایکبوون|Abnormal early drainage development can damage vision in infants and children.|drainage-angle,cornea|watering,light-sensitivity|aapos:glaucoma-in-children|infantile glaucoma
ocular-hypertension|Ocular hypertension|ارتفاع ضغط العين|بەرزبوونی فشاری چاو|Raised eye pressure without demonstrated glaucoma still needs risk assessment and monitoring.|aqueous-humour,trabecular-meshwork||msd:overview-of-glaucoma|`,
 vitreous:`posterior-vitreous-detachment|Posterior vitreous detachment|انفصال الجسم الزجاجي الخلفي|جیابوونەوەی پشتی شووشەیی|The vitreous separates from the retina; new symptoms need a retinal tear check.|vitreous-body,posterior-vitreous-interface|flashes,floaters|nei:vitreous-detachment|PVD
vitreous-haemorrhage|Vitreous haemorrhage|نزف الجسم الزجاجي|خوێنبەربوونی شووشەیی|Blood in the vitreous may obscure vision and requires assessment of its cause.|vitreous-body,retinal-vessels|floaters,vision-loss|wiki:Vitreous_Hemorrhage|vitreous hemorrhage`,
 retina:`retinal-tear|Retinal tear|تمزق الشبكية|دڕانی تۆڕینە|A retinal break can allow detachment; new flashes or floaters require urgent examination.|peripheral-retina|flashes,floaters|nei:retinal-detachment|
retinal-detachment|Retinal detachment|انفصال الشبكية|جیابوونەوەی تۆڕینە|The sensory retina separates from underlying tissue and can cause permanent sight loss.|retina|curtain,flashes,vision-loss|nei:retinal-detachment|
diabetic-retinopathy|Diabetic retinopathy|اعتلال الشبكية السكري|زیانی تۆڕینەی شەکرە|Diabetes can damage retinal vessels before noticeable visual symptoms occur.|retina,retinal-vessels|blurred-vision,floaters|nei:diabetic-retinopathy|
hypertensive-retinopathy|Hypertensive retinopathy|اعتلال الشبكية بارتفاع الضغط|زیانی تۆڕینەی فشاری خوێن|High blood pressure can damage retinal blood vessels.|retinal-vessels|blurred-vision|msd:hypertensive-retinopathy|
retinal-artery-occlusion|Retinal artery occlusion|انسداد شريان الشبكية|گیرانی شەریانی تۆڕینە|Interrupted retinal arterial blood flow can cause sudden painless sight loss and needs emergency assessment.|retinal-vessels,retina|vision-loss|msd:central-retinal-artery-occlusion-and-branch-retinal-artery-occlusion|RAO
retinal-vein-occlusion|Retinal vein occlusion|انسداد وريد الشبكية|گیرانی وریدی تۆڕینە|Blocked retinal venous drainage can cause bleeding and macular swelling.|retinal-vessels,macula|blurred-vision,vision-loss|msd:central-retinal-vein-occlusion-and-branch-retinal-vein-occlusion|RVO
amd|Age-related macular degeneration|تنكس البقعة المرتبط بالعمر|تێکچوونی ماکولای پەیوەندیدار بە تەمەن|Degenerative macular changes can impair central vision.|macula,retinal-pigment-epithelium|distorted-lines,blind-spots|nei:age-related-macular-degeneration|AMD
macular-oedema|Macular oedema|وذمة البقعة|ئاوسانی ماکولا|Fluid accumulation thickens the macula; several diseases can cause it.|macula,retinal-vessels|blurred-vision,distorted-lines|nei:macular-edema|macular edema
macular-hole|Macular hole|ثقب البقعة|کونی ماکولا|A defect through the central retina can distort central vision.|fovea,macula|distorted-lines,blind-spots|nei:macular-hole|
epiretinal-membrane|Epiretinal membrane|غشاء فوق الشبكية|پەردەی سەر تۆڕینە|A membrane on the retinal surface may wrinkle the macula.|macula|distorted-lines,blurred-vision|nei:macular-pucker|macular pucker
central-serous|Central serous chorioretinopathy|اعتلال المشيمية والشبكية المصلي المركزي|نەخۆشی سیرۆزی ناوەندی کۆرۆید و تۆڕینە|Fluid beneath central retina can distort or blur vision.|macula,choroid|distorted-lines,blurred-vision|wiki:Central_Serous_Chorioretinopathy|CSCR`,
 inherited:`retinitis-pigmentosa|Retinitis pigmentosa|التهاب الشبكية الصباغي|ڕەتینایتیسی ڕەنگدار|Inherited retinal degeneration can impair night and peripheral vision.|photoreceptors,peripheral-retina|night-vision,blind-spots|nei:retinitis-pigmentosa|RP
stargardt|Stargardt disease|مرض ستارغارت|نەخۆشی ستارگارت|An inherited macular disorder often reduces central vision beginning in youth.|macula,retinal-pigment-epithelium|blurred-vision,blind-spots|nei:stargardt-disease|
usher|Usher syndrome|متلازمة أشر|سندرۆمی ئەشەر|An inherited condition combines hearing loss with progressive retinal degeneration.|photoreceptors,retina|night-vision|nei:usher-syndrome|
inherited-retinal-disorders|Other inherited retinal disorders|أمراض الشبكية الوراثية الأخرى|نەخۆشییە بۆماوەییەکانی تری تۆڕینە|Genetically diverse retinal diseases require specialist phenotyping and sometimes genetic testing.|photoreceptors,retina|night-vision,blurred-vision|nei:rare-diseases|inherited retinal dystrophy`,
 nerve:`optic-neuritis|Optic neuritis|التهاب العصب البصري|هەوکردنی دەمارە بیناییەکە|Optic nerve inflammation can reduce vision and colour perception, sometimes with movement pain.|optic-nerve|vision-loss,colour-change,movement-pain|msd:optic-neuritis|
ischaemic-optic-neuropathy|Ischaemic optic neuropathy|اعتلال العصب البصري الإقفاري|زیانی دەمارە بیناییەکە بەهۆی کەمی خوێن|Reduced optic nerve blood supply can cause sudden sight loss; urgent assessment identifies dangerous causes.|optic-disc,optic-nerve|vision-loss|msd:ischemic-optic-neuropathy|ischemic optic neuropathy
optic-atrophy|Optic atrophy|ضمور العصب البصري|پووکانی دەمارە بیناییەکە|Optic nerve tissue loss is an outcome with several possible underlying causes.|optic-nerve,optic-disc|vision-loss,colour-change|wiki:Optic_Atrophy|
disc-swelling|Optic-disc swelling / papilloedema|تورم القرص البصري|ئاوسانی دیسکی بینایی|Disc swelling is a finding; papilloedema specifically relates to raised intracranial pressure and needs urgent assessment.|optic-disc|blurred-vision|msd:papilledema|papilledema`,
 refraction:`myopia|Myopia|قصر النظر|کورتبینی|Light focuses in front of the retina, often blurring distance vision.|cornea,lens,retina|blurred-vision|nei:nearsightedness-myopia|nearsightedness
hyperopia|Hyperopia|طول النظر|دووربینی|Focusing demand is increased when the eye’s optical power is insufficient for its length.|cornea,lens|blurred-vision|nei:farsightedness-hyperopia|farsightedness
astigmatism|Astigmatism|اللابؤرية|ئاستیگماتیزم|Unequal optical curvature can blur or distort vision.|cornea,lens|blurred-vision|nei:astigmatism|
presbyopia|Presbyopia|قصو البصر الشيخي|لاوازی بینینی نزیک بە تەمەن|Age-related loss of lens accommodation makes near focusing harder.|lens,ciliary-muscle|blurred-vision|nei:presbyopia|
amblyopia|Amblyopia|كسل العين|تەمبەڵی چاو|Abnormal early visual development reduces vision despite appropriate optical correction.|retina,optic-nerve|blurred-vision|nei:amblyopia-lazy-eye|lazy eye
colour-deficiency|Colour-vision deficiency|ضعف تمييز الألوان|کەموکوڕی بینینی ڕەنگ|Inherited or acquired changes reduce the ability to distinguish some colours.|photoreceptors,optic-nerve|colour-change|nei:color-blindness|color blindness`,
 movement:`strabismus|Strabismus|الحول|خێڵی چاو|The eyes do not align on the same target; causes and visual effects vary.|medial-rectus,lateral-rectus|double-vision|aapos:strabismus|squint
convergence-insufficiency|Convergence insufficiency|قصور التقارب|کەموکوڕی نزیکبوونەوەی چاوەکان|The eyes have difficulty maintaining coordinated inward alignment for near tasks.|medial-rectus|double-vision,blurred-vision|nei:convergence-insufficiency|
nystagmus|Nystagmus|الرأرأة|لەرزینی چاو|Involuntary rhythmic eye movements can have developmental, eye or neurological causes.|superior-rectus,lateral-rectus|blurred-vision|aapos:nystagmus|
ocular-motor-nerve-disorders|Ocular motor nerve disorders|اضطرابات أعصاب حركة العين|تێکچوونی دەمارە جووڵێنەرەکانی چاو|Cranial nerve dysfunction may impair alignment or movement and sometimes alter the pupil or lid.|medial-rectus,superior-oblique,levator-palpebrae|double-vision,drooping|msd:diplopia|third fourth sixth nerve palsy`,
 orbit:`preseptal-cellulitis|Preseptal cellulitis|التهاب ما قبل الحاجز|هەوکردنی پێش پەردەی کاسەی چاو|Infection affects lid tissues in front of the orbital septum; examination must exclude orbital involvement.|upper-eyelid,lower-eyelid|swelling,redness|msd:preseptal-and-orbital-cellulitis|
orbital-cellulitis|Orbital cellulitis|التهاب الحجاج|هەوکردنی کاسەی چاو|Infection behind the orbital septum can threaten vision and life.|orbital-fat,optic-nerve|swelling,movement-pain,protrusion|msd:preseptal-and-orbital-cellulitis|
thyroid-eye-disease|Thyroid eye disease|مرض العين الدرقي|نەخۆشی چاوی تیڕۆید|Immune inflammation may enlarge orbital muscles and fat and alter eyelid position.|orbital-fat,medial-rectus,upper-eyelid|protrusion,double-vision,dryness|nei:graves-eye-disease|Graves orbitopathy
orbital-inflammation|Orbital inflammation|التهاب الحجاج غير المعدي|هەوکردنی نامیکرۆبی کاسەی چاو|Non-infectious orbital inflammation can cause pain, swelling or restricted movement.|orbital-fat,superior-rectus|swelling,movement-pain|msd:inflammatory-orbital-disease|
orbital-mass|Orbital masses|كتل الحجاج|گرێکانی کاسەی چاو|A space-occupying orbital lesion can displace the globe or affect vision.|bony-orbit,orbital-fat|protrusion,double-vision|msd:tumors-of-the-orbit|`,
 injury:`chemical-injury|Chemical eye injury|إصابة العين الكيميائية|برینداریی کیمیایی چاو|Chemical exposure needs immediate rinsing and emergency assessment.|cornea,bulbar-conjunctiva|burning,pain,vision-loss|nhs:eye-injuries|
thermal-injury|Thermal eye injury|إصابة العين الحرارية|برینداریی گەرمی چاو|Heat can damage lids and the ocular surface.|upper-eyelid,cornea|pain,burning|wiki:Ocular_Burns|
uv-keratitis|UV keratitis|التهاب القرنية بالأشعة فوق البنفسجية|هەوکردنی قەرنیەی تیشکی سەروو بنەوشەیی|Ultraviolet exposure can injure the corneal epithelium, often affecting both eyes.|corneal-epithelium|pain,light-sensitivity|msd:superficial-punctate-keratitis|photokeratitis
blunt-injury|Blunt eye injury|رض العين|زەبری چاو|A blunt impact can damage external and internal structures despite an intact surface.|cornea,lens,retina|pain,vision-loss|nhs:eye-injuries|
penetrating-injury|Penetrating eye injury|جرح العين النافذ|برینداریی چوونەناوی چاو|An open-globe injury needs emergency care; do not press the eye or remove an embedded object.|sclera,cornea|pain,vision-loss|nhs:eye-injuries|open globe
hyphema|Hyphema|تحدمية|خوێن لە ژووری پێشەوە|Blood collects in the anterior chamber, commonly after injury.|anterior-chamber,iris|blurred-vision,pain|wiki:Hyphema|
orbital-fracture|Orbital fracture|كسر الحجاج|شکانی کاسەی چاو|An orbital bone fracture can trap tissue or affect eye position and movement.|bony-orbit,inferior-rectus|double-vision,swelling|wiki:Orbital_Floor_Fractures|
intraocular-foreign-body|Intraocular foreign body|جسم غريب داخل العين|تەنێکی نامۆ لە ناو چاو|A penetrating fragment inside the eye is an emergency even if pain is limited.|cornea,vitreous-body|foreign-body,vision-loss|nhs:eye-injuries|IOFB
endophthalmitis|Endophthalmitis|التهاب باطن العين|هەوکردنی ناو چاو|Severe internal infection may follow surgery, injection, injury or bloodstream infection.|vitreous-body,anterior-chamber|pain,vision-loss|msd:endophthalmitis|`,
 childhood:`retinopathy-prematurity|Retinopathy of prematurity|اعتلال شبكية الخدج|زیانی تۆڕینەی منداڵی پێشوەخت|Abnormal retinal blood vessel development in premature infants requires scheduled screening.|retinal-vessels,peripheral-retina||nei:retinopathy-prematurity|ROP
coloboma|Coloboma|ثلامة العين|کۆلۆبۆما|A developmental gap may affect the iris, retina or optic nerve.|iris,retina,optic-nerve|vision-loss|nei:coloboma|
aniridia|Aniridia|انعدام القزحية|نەبوونی قازحیە|Reduced iris development can coexist with other eye and sometimes systemic abnormalities.|iris,fovea|light-sensitivity,blurred-vision|wiki:Aniridia|
microphthalmia|Microphthalmia|صغر العين الخلقي|بچووکیی چاوی لەدایکبوون|One or both eyes are unusually small from altered development before birth.|sclera,retina|vision-loss|nei:anophthalmia-and-microphthalmia|
retinoblastoma|Retinoblastoma|الورم الأرومي الشبكي|ڕەتینۆبلاستۆما|A childhood retinal cancer may first cause a white pupil reflection and needs prompt specialist assessment.|retina|white-pupil|nei:retinoblastoma|`,
 systemic:`uveal-melanoma|Uveal melanoma|ميلانوما العنبية|مێلانۆمای یوڤیا|A malignant tumour can arise in the choroid, ciliary body or iris.|choroid,ciliary-body,iris|blurred-vision,blind-spots|wiki:Choroidal_and_Ciliary_Body_Melanoma|
ocular-surface-tumours|Ocular surface tumours|أورام سطح العين|گرێکانی ڕووکاری چاو|Surface growths include benign, precancerous and malignant lesions requiring examination.|bulbar-conjunctiva,cornea|redness,foreign-body|wiki:Ocular_Surface_Squamous_Neoplasia|
eyelid-tumours|Eyelid tumours|أورام الجفن|گرێکانی پلک|Persistent or changing lid lesions sometimes need biopsy to identify their nature.|upper-eyelid,eyelid-margin|lid-lump|msd:eyelid-growths|
autoimmune-eye-disease|Autoimmune eye involvement|تأثر العين بأمراض المناعة الذاتية|کاریگەری نەخۆشیی خۆبەرگری لە چاو|Systemic inflammatory disease can affect the ocular surface, sclera, uvea or retinal vessels.|sclera,iris,retinal-vessels|pain,redness,vision-loss|msd:uveitis-caused-by-systemic-rheumatic-disease|
giant-cell-arteritis|Giant cell arteritis|التهاب الشريان ذي الخلايا العملاقة|هەوکردنی شەریانی خانە گەورەکان|Arterial inflammation, usually after age 50, can threaten sight and needs urgent assessment.|optic-nerve,retinal-vessels|vision-loss,double-vision|nhs:temporal-arteritis|temporal arteritis
medication-toxicity|Medication-related ocular toxicity|سمية الأدوية على العين|ژەهراویبوونی چاو بە دەرمان|Some medicines can damage retinal or optic nerve function; monitoring depends on the medicine.|retina,optic-nerve|blurred-vision,colour-change|msd:toxic-and-nutritional-optic-neuropathies|drug toxicity
neurological-visual-causes|Neurological causes of visual symptoms|أسباب عصبية لأعراض النظر|هۆکارە دەمارەییەکانی نیشانەکانی بینین|Disorders beyond the eye can affect visual pathways or eye movement.|optic-nerve,superior-rectus|double-vision,vision-loss|msd:the-optic-pathway|
vascular-visual-causes|Vascular causes of visual symptoms|أسباب وعائية لأعراض النظر|هۆکارە ڕەگییەکانی نیشانەکانی بینین|Reduced blood flow in the eye or brain can cause sudden visual symptoms and needs emergency assessment.|retinal-vessels,optic-nerve|vision-loss|msd:acute-vision-loss|`
}
// Resolve to actual links found on authoritative indexes; never invent an NEI/MSD slug.
const indexUrls={msd:'https://www.msdmanuals.com/professional/eye-disorders',nei:'https://www.nei.nih.gov/eye-health-information/eye-conditions-and-diseases'}
const indexes={}
for(const [key,url] of Object.entries(indexUrls)){
 const response=await fetch(url); if(!response.ok)throw new Error(`Index unavailable: ${key}`)
 const html=await response.text()
 indexes[key]=[...new Set([...html.matchAll(/href=["']([^"']+)["']/g)].map(m=>new URL(m[1],url).href.split('#')[0]))]
}
const overrides={'nei:retinopathy-prematurity':'https://www.nei.nih.gov/eye-health-information/eye-conditions-and-diseases/retinopathy-prematurity','nei:rare-diseases':'https://www.nei.nih.gov/eye-health-information/eye-conditions-and-diseases/rare-diseases'}
const unresolved=[]
function source(hint){
 const replacements={
  'wiki:Meibomian_Gland_Dysfunction':'https://www.msdmanuals.com/professional/eye-disorders/eyelid-and-lacrimal-disorders/blepharitis',
  'wiki:Lagophthalmos':'https://www.ncbi.nlm.nih.gov/books/NBK560661/',
  'wiki:Eyelid_Contact_Dermatitis':'https://dermnetnz.org/topics/eyelid-contact-dermatitis',
  'wiki:Corneal_Abrasion':'https://www.msdmanuals.com/professional/injuries-poisoning/eye-trauma/corneal-abrasions-and-corneal-foreign-bodies',
  'wiki:Ocular_Burns':'https://www.msdmanuals.com/professional/injuries-poisoning/eye-trauma/ocular-burns'
 }
 if(replacements[hint])return replacements[hint]
 const [provider,key]=hint.split(':')
 if(provider==='wiki')return `https://eyewiki.aao.org/${key}`
 if(provider==='aapos')return `https://aapos.org/glossary/${key}`
 if(provider==='nhs')return `https://www.nhs.uk/conditions/${key}/`
 const found=indexes[provider]?.find(url=>url.endsWith('/'+key)) || overrides[hint]
 if(!found){unresolved.push(hint);return indexUrls[provider]}
 return found
}
const conditions=Object.entries(rows).flatMap(([category,text])=>text.split('\n').map(row=>{
 const [id,en,ar,ckb,explanation,structures,symptoms,hint,synonyms]=row.split('|')
 const profile=categories.find(c=>c.id===category)
 const kind=id==='disc-swelling'?'finding':id==='optic-atrophy'?'outcome':id.endsWith('-causes')?'cause-category':id==='lid-lesion'?'finding':'condition'
 return {id:`condition.${id}`,category,kind,label:loc(en,ar,ckb),synonyms:synonyms?synonyms.split(','):[],anatomy_ids:structures.split(',').map(x=>`eye.${x}`),symptom_ids:symptoms?symptoms.split(',').map(x=>`symptom.${x}`):[],explanation:loc(explanation,`معلومات تعليمية عن ${ar}. التشخيص يحتاج فحص مختص. الترجمة الطبية التفصيلية بانتظار المراجعة؛ النص الإنكليزي الأصلي أدناه.`,`زانیاریی فێرکاری دەربارەی ${ckb}. دەستنیشانکردن پێویستی بە پشکنینی پسپۆڕ هەیە. وەرگێڕانی پزیشکیی ورد چاوەڕێی پێداچوونەوەیە؛ دەقی ئینگلیزی لە خوارەوەیە.`),risk_factors:profile.risks,age_considerations:['childhood','inherited'].includes(category)||id.startsWith('congenital')?'Infants and children need age-appropriate specialist assessment; visual development is time-sensitive.':id==='giant-cell-arteritis'?'Usually affects adults over 50; age alone must not dismiss visual warning signs.':'May occur at different ages. Age and history change the examination needed.',red_flags:['sudden vision loss','severe or new eye pain','chemical or penetrating injury','new flashes, floaters or curtain','new neurological symptoms'],urgency_guidance:'Urgency depends on the reported symptoms and examination, not this catalogue entry or a clicked structure. New visual loss or injury requires urgent assessment.',confirmation:profile.examination,source_urls:[source(hint)],source_hint:hint,source_checked_at:'2026-10-30',clinical_reviewed_at:null,clinical_review_status:'draft',translation_review_status:{en:'draft','ar-IQ':'pending-medical-translation',ckb:'pending-medical-translation'},content_version:'eye-draft-2026-10-30.2'}
}))
for(const condition of conditions){
 const translation=conditionTranslations[condition.id]
 if(!translation)throw new Error(`Missing draft condition translation: ${condition.id}`)
 Object.assign(condition.explanation,translation)
 condition.translation_review_status={'en':'draft','ar-IQ':'draft-awaiting-medical-review',ckb:'draft-awaiting-medical-review'}
 condition.category_ids=[condition.category,...(['congenital-cataract','congenital-glaucoma'].includes(condition.id.replace('condition.',''))?['childhood']:[])]
}
writeFileSync(`${dir}conditions.v1.json`,JSON.stringify({version:'eye-draft-2026-10-30.2',clinical_review_status:'draft',clinical_use_available:false,categories,conditions},null,2)+'\n')
writeFileSync(`${dir}sources.v1.json`,JSON.stringify({version:'eye-draft-2026-10-30.2',anatomy:[{id:'anatomy-msd',url:'https://www.msdmanuals.com/professional/eye-disorders/approach-to-the-ophthalmologic-patient/ophthalmic-anatomy'},{id:'anatomy-aao',url:'https://www.aao.org/eye-health/anatomy/human-eye'}],index_urls:indexUrls,unresolved_hints:unresolved},null,2)+'\n')
console.log(JSON.stringify({conditions:conditions.length,categories:categories.length,source_urls:new Set(conditions.flatMap(x=>x.source_urls)).size,unresolved}))
