import { strict as assert } from 'node:assert'
import { test } from 'node:test'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { bundleModule,root } from './portable.mjs'
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'humantwin-eye-tests-'))
const engineFile=path.join(temp,'engine.mjs'),modelFile=path.join(temp,'model.mjs')
await bundleModule(path.join(root,'src/eye/interview.ts'),engineFile)
await bundleModule(path.join(root,'src/eye/model.ts'),modelFile)
const engine=await import(pathToFileURL(engineFile).href),model=await import(pathToFileURL(modelFile).href)
const painFile=path.join(temp,'pain.mjs'),knowledgeFile=path.join(temp,'knowledge.mjs')
await bundleModule(path.join(root,'src/eye/pain.ts'),painFile);await bundleModule(path.join(root,'src/eye/knowledge.ts'),knowledgeFile)
const pain=await import(pathToFileURL(painFile).href),knowledge=await import(pathToFileURL(knowledgeFile).href)
const careFile=path.join(temp,'care.mjs');await bundleModule(path.join(root,'src/eye/care.ts'),careFile);const care=await import(pathToFileURL(careFile).href)
const suggestionFile=path.join(temp,'suggestion.mjs');await bundleModule(path.join(root,'src/eye/painSuggestion.ts'),suggestionFile);const suggestion=await import(pathToFileURL(suggestionFile).href)
const read=name=>JSON.parse(fs.readFileSync(path.join(root,'../contracts/eye',name+'.v1.json'),'utf8'))
const vectors=read('cases').cases,anatomy=read('anatomy'),catalogue=read('conditions'),review=read('review'),interview=read('interview')
for(const vector of vectors)await test(vector.id,()=>{
 const state=engine.newEyeSession('left','en');engine.answerEye(state,{question_id:'question.concern',value:vector.text})
 assert.equal(state.urgency,vector.level)
 if(vector.rule)assert.ok(state.rule_ids.includes(vector.rule),JSON.stringify(state))
 if(vector.laterality)assert.equal(state.reported.laterality,vector.laterality)
 if(vector.level!=='unknown'){assert.equal(engine.nextEyeQuestion(state),null);assert.throws(()=>engine.answerEye(state,{question_id:'question.pain',value:'0'}))}
})
await test('missing answers are unknown, and skipped pain is not zero',()=>{
 const state=engine.newEyeSession();assert.ok(Object.values(state.red_flags).every(v=>v==='unknown'))
 engine.answerEye(state,{question_id:'question.pain',value:'unknown'});assert.equal(state.reported.pain,'unknown');assert.equal(state.symptoms['symptom.pain'],'unknown');assert.ok(state.missing.includes('pain'))
})
await test('left anatomy does not imply reported laterality; both eyes synchronizes reported state',()=>{
 const state=engine.newEyeSession('left');assert.equal(state.reported.laterality,'unknown')
 engine.answerEye(state,{question_id:'question.side',value:'left'})
 engine.answerEye(state,{question_id:'question.concern',value:'Both eyes are itchy'})
 assert.equal(state.reported.laterality,'both');assert.equal(state.model_side,'left');assert.match(state.acknowledgements.at(-1),/both eyes/i)
})
await test('ambiguous side is clarified and negated side is not inferred',()=>{
 const state=engine.newEyeSession();engine.answerEye(state,{question_id:'question.concern',value:'It is my left eye or right eye, not sure'});assert.equal(state.reported.laterality,'unknown')
 const other=engine.newEyeSession();engine.parseEyeText(other,'Not my left eye. The right eye is itchy.');assert.equal(other.reported.laterality,'right')
})
await test('chemical exposure interrupts an established interview and shows immediate first aid',()=>{
 const state=engine.newEyeSession();engine.answerEye(state,{question_id:'question.concern',value:'Itching in my left eye'});engine.answerEye(state,{question_id:'question.exposure',value:'chemical'})
 assert.equal(state.urgency,'emergency');const rule=interview.rules.find(r=>r.id==='eye.rule.chemical');for(const locale of ['en','ar-IQ','ckb'])assert.ok(rule.first_aid[locale].length>70);assert.match(rule.first_aid.en,/at least 20 minutes/)
})
await test('all warning rules are local and work with no AI or network dependency',()=>{
 const state=engine.newEyeSession();engine.answerEye(state,{question_id:'question.concern',value:'Sudden loss of vision, no pain'});assert.equal(state.urgency,'emergency');assert.deepEqual(state.unconfirmed_explanations,[])
})
await test('additional warning information can escalate an urgent result; no later answer downgrades it',()=>{
 const state=engine.newEyeSession();engine.answerEye(state,{question_id:'question.concern',value:'I wear contact lenses and my eye is red and painful'});assert.equal(state.urgency,'urgent');assert.equal(engine.nextEyeQuestion(state),null)
 engine.answerEye(state,{question_id:'question.concern',value:'My vision is now blurred'});assert.equal(state.urgency,'emergency');assert.ok(state.rule_ids.includes('eye.rule.contact-red-pain'));assert.ok(state.rule_ids.includes('eye.rule.contact-vision'))
})
await test('no structure click establishes a disease or symptom',()=>{
 const state=engine.newEyeSession();state.anatomy_explored=['eye.retina'];engine.evaluateEye(state);assert.equal(state.urgency,'unknown');assert.ok(Object.values(state.symptoms).every(s=>s==='unknown'))
})
await test('age zero is preserved and irrelevant contact-lens questions are skipped',()=>{
 const state=engine.newEyeSession();engine.answerEye(state,{question_id:'question.age',value:'0'});assert.equal(state.reported.age,0)
 engine.answerEye(state,{question_id:'question.contact',value:'no'});assert.equal(engine.questionRelevant(state,interview.questions.find(q=>q.id==='question.overnight')),false)
})
await test('zero years is not automatically a newborn; age in days establishes neonatal context',()=>{
 const state=engine.newEyeSession();engine.answerEye(state,{question_id:'question.age',value:'0'});engine.parseEyeText(state,'My eye is red');engine.evaluateEye(state);assert.equal(state.red_flags['eye.rule.newborn-red-sticky'],'unknown')
 engine.answerEye(state,{question_id:'question.infant-age',value:'14'});assert.equal(state.urgency,'urgent');assert.ok(state.rule_ids.includes('eye.rule.newborn-red-sticky'))
})
await test('anatomical IDs are unique; every condition references real structures and symptoms',()=>{
 const ids=new Set(anatomy.structures.map(s=>s.id)),symptoms=new Set(interview.symptoms.map(s=>s.id));assert.equal(ids.size,63);assert.equal(catalogue.conditions.length,112);assert.equal(catalogue.categories.length,19)
 for(const condition of catalogue.conditions){assert.ok(condition.source_urls.length);assert.equal(condition.clinical_review_status,'draft');for(const id of condition.anatomy_ids)assert.ok(ids.has(id),`${condition.id}: ${id}`);for(const id of condition.symptom_ids)assert.ok(symptoms.has(id),id)}
 for(const structure of anatomy.structures)for(const locale of ['en','ar-IQ','ckb'])assert.ok(structure.label[locale])
})
await test('patient-side reflection keeps the macula temporal to the nasal optic disc',()=>{
 const macula=anatomy.structures.find(s=>s.id==='eye.macula'),disc=anatomy.structures.find(s=>s.id==='eye.optic-disc'),fovea=anatomy.structures.find(s=>s.id==='eye.fovea')
 for(const side of ['left','right']){const m=model.anatomicalPosition(macula,side),d=model.anatomicalPosition(disc,side),f=model.anatomicalPosition(fovea,side);assert.ok(m.x*d.x<0);assert.equal(m.x,f.x);assert.equal(m.y,f.y);assert.ok(m.z<0&&d.z<0)}
})
await test('every anatomical structure is selectable in an appropriate view; micro layers have dedicated views',()=>{
 for(const side of ['left','right'])for(const structure of anatomy.structures){assert.ok(model.viewShows(structure,structure.preferred_view),structure.id);const group=model.buildEyeModel(side,structure.preferred_view);assert.ok(group.getObjectByName(structure.id),structure.id)}
 for(const structure of anatomy.structures.filter(s=>s.shape==='micro')){assert.equal(model.viewShows(structure,'external'),false);assert.ok(structure.preferred_view.endsWith('detail'))}
})
await test('the pupil remains an iris opening, with annotation-only hit geometry',()=>{
 const group=model.buildEyeModel('left','external'),pupil=group.getObjectByName('eye.pupil');let hit=false;pupil.traverse(child=>{if(child.userData.annotationOnly){hit=true;assert.equal(child.material.opacity,0)}});assert.ok(hit)
})
await test('clinical use stays disabled pending review; there are no country-specific emergency numbers',()=>{
 assert.equal(review.approved_for_live_triage,false);assert.equal(review.approval,null);assert.equal(interview.clinical_use_available,false);assert.doesNotMatch(JSON.stringify(interview.actions),/\b(?:999|111|911)\b/)
})
await test('every self-reported score from zero to ten receives the right descriptive band',()=>{
 for(let score=0;score<=10;score++){const state=engine.newEyeSession();engine.answerEye(state,{question_id:'question.pain',value:String(score)});const result=pain.painAssessment(state);assert.equal(result.score,score);assert.equal(result.band,score===0?'none':score<=3?'mild':score<=6?'moderate':'severe');assert.match(state.messages.at(-1).text,new RegExp(`${score}/10`))}
})
await test('qualitative descriptions never become confirmed numeric scores without acceptance',()=>{
 const state=engine.newEyeSession();engine.answerEye(state,{question_id:'question.concern',value:'I have severe eye pain'});assert.equal(state.reported.pain,undefined);assert.equal(pain.painAssessment(state).score,null);assert.equal(pain.painAssessment(state).band,'severe');assert.match(pain.painAssessment(state).summary,/no numeric score/)
 const urgent=engine.newEyeSession();engine.answerEye(urgent,{question_id:'question.concern',value:'Sudden severe eye pain'});assert.equal(urgent.urgency,'emergency');assert.equal(urgent.reported.pain,undefined)
})
await test('knowledge questions leave the clinical interview and symptom facts untouched',()=>{
 const state=engine.newEyeSession();const before=engine.nextEyeQuestion(state).id;engine.answerEye(state,{question_id:'learn:condition.diabetic-retinopathy',value:'What is diabetic retinopathy?'});assert.equal(engine.nextEyeQuestion(state).id,before);assert.equal(state.reported.diabetes,undefined);assert.ok(Object.values(state.symptoms).every(s=>s==='unknown'));assert.equal(state.messages.at(-1).kind,'education');assert.ok(state.messages.at(-1).source_urls.length)
})
await test('the expanded topic library answers explicit questions without classifying patient statements as education',()=>{
 assert.ok(knowledge.library.topics.length>=190);assert.equal(knowledge.knowledgeTopic('Explain the cornea').id,'eye.cornea');assert.equal(knowledge.knowledgeTopic('What is dry eye?').id,'education.dryness');assert.equal(knowledge.knowledgeTopic('Explain the pain scale').id,'education.pain-scale');assert.equal(knowledge.knowledgeTopic('What is a stye?').id,'condition.stye');assert.equal(knowledge.knowledgeTopic('What is glaucoma?').id,'education.glaucoma');assert.equal(knowledge.knowledgeTopic('I have sudden loss of vision'),null)
})
await test('symptom branches are relevant and functional pain impact is collected separately',()=>{
 const state=engine.newEyeSession();engine.answerEye(state,{question_id:'question.concern',value:'Dry gritty eyes'});const screen=interview.questions.find(q=>q.id==='question.screen'),lump=interview.questions.find(q=>q.id==='question.lid-lump-site');assert.equal(engine.questionRelevant(state,screen),true);assert.equal(engine.questionRelevant(state,lump),false)
 engine.answerEye(state,{question_id:'question.pain',value:'6'});engine.answerEye(state,{question_id:'question.pain-function',value:'stopped'});assert.equal(pain.painAssessment(state).impact,'stopped');assert.equal(pain.painAssessment(state).score,6)
})
await test('new free-text follow-ups are retained and invalid pain scores are rejected',()=>{
 const state=engine.newEyeSession();engine.answerEye(state,{question_id:'question.pain-relief',value:'Resting my eyes helps'});assert.equal(state.reported.pain_relief,'Resting my eyes helps');assert.throws(()=>engine.answerEye(state,{question_id:'question.pain',value:'11'}));assert.throws(()=>engine.answerEye(state,{question_id:'learn:condition.invented',value:'invented'}))
})
await test('sudden 9/10 pain recommends emergency ophthalmology and suppresses home comfort measures',()=>{
 const state=engine.newEyeSession();engine.answerEye(state,{question_id:'question.concern',value:'My left eye hurts'});engine.answerEye(state,{question_id:'question.onset',value:'sudden'});engine.answerEye(state,{question_id:'question.pain',value:'9'});const plan=care.eyeCarePlan(state);assert.equal(plan.route,'emergency');assert.match(plan.doctor.description.en,/ophthalmology/);assert.equal(plan.comfort_measures_included,false);assert.ok(plan.steps.some(s=>s.id==='no-pressure'));assert.ok(!plan.steps.some(s=>['screen-breaks','avoid-irritants'].includes(s.id)));assert.match(state.doctor_summary,/9\/10/);assert.match(state.doctor_summary,/laterality: left/)
})
await test('severe pain without known sudden onset still gets same-day eye assessment',()=>{
 const state=engine.newEyeSession();engine.answerEye(state,{question_id:'question.pain',value:'9'});assert.equal(state.urgency,'urgent');assert.ok(state.rule_ids.includes('eye.rule.severe-eye-pain'));assert.equal(care.eyeCarePlan(state).route,'urgent');assert.equal(engine.nextEyeQuestion(state),null)
})
await test('chemical care leads with immediate rinsing and penetrating injury forbids embedded-object removal',()=>{
 const chemical=engine.newEyeSession();engine.answerEye(chemical,{question_id:'question.concern',value:'Bleach splashed in my eye'});assert.equal(care.eyeCarePlan(chemical).steps[0].id,'chemical-rinse');assert.match(care.eyeCarePlan(chemical).steps[0].text.en,/at least 20 minutes/)
 const injury=engine.newEyeSession();engine.answerEye(injury,{question_id:'question.exposure',value:'penetrating'});assert.ok(care.eyeCarePlan(injury).steps.some(s=>s.id==='embedded-object'));assert.equal(care.eyeCarePlan(injury).comfort_measures_included,false)
})
await test('comfort suggestions need explicit safety answers and disappear if visual loss is reported',()=>{
 const state=engine.newEyeSession();engine.answerEye(state,{question_id:'question.concern',value:'My eyes feel dry and gritty'});assert.equal(care.eyeCarePlan(state).comfort_measures_included,false)
 for(const [id,value] of [['vision','unchanged'],['exposure','none'],['onset','gradual'],['pain','2'],['contact','no'],['surgery','no']])engine.answerEye(state,{question_id:`question.${id}`,value})
 assert.equal(care.eyeCarePlan(state).comfort_measures_included,true);assert.ok(care.eyeCarePlan(state).steps.some(s=>s.id==='screen-breaks'))
 engine.answerEye(state,{question_id:'question.vision',value:'loss'});assert.equal(care.eyeCarePlan(state).comfort_measures_included,false);assert.ok(!care.eyeCarePlan(state).steps.some(s=>s.id==='screen-breaks'))
})
await test('paediatric routes require child context and do not label an adult as a child',()=>{
 const child=engine.newEyeSession();engine.answerEye(child,{question_id:'question.concern',value:'My child has a white pupil'});assert.equal(care.eyeCarePlan(child).route,'paediatric')
 const adult=engine.newEyeSession();engine.answerEye(adult,{question_id:'question.age',value:'50'});engine.answerEye(adult,{question_id:'question.concern',value:'A white pupil reflection'});assert.equal(care.eyeCarePlan(adult).route,'urgent')
})
await test('the doctor handoff excludes educational conversations and preserves original patient answers',()=>{
 const state=engine.newEyeSession();engine.answerEye(state,{question_id:'learn:condition.diabetic-retinopathy',value:'What is diabetic retinopathy?'});engine.answerEye(state,{question_id:'question.concern',value:'My eyes are itchy'});const summary=care.eyeDoctorSummary(state);assert.doesNotMatch(summary,/What is diabetic retinopathy/);assert.match(summary,/My eyes are itchy/);assert.match(summary,/Information still unknown/);assert.match(summary,/NOT A DIAGNOSIS/);assert.match(summary,/clinical review: pending/)
})
await test('care templates include all supported languages and never insert foreign emergency numbers',()=>{
 for(const locale of ['en','ar-IQ','ckb']){for(const route of Object.values(care.care.routes))assert.ok(route.title[locale]&&route.description[locale]);for(const step of Object.values(care.care.steps))assert.ok(step.text[locale])}assert.doesNotMatch(JSON.stringify(care.care.routes),/\b(?:999|111|911)\b/);assert.equal(care.care.clinical_use_available,false)
})
await test('the assistant suggests a score from description and activity, and records it only after confirmation',()=>{
 const state=engine.newEyeSession();engine.answerEye(state,{question_id:'question.concern',value:'Moderate eye pain distracts me'});assert.equal(suggestion.suggestPain(state).suggested_score,5);assert.deepEqual(suggestion.suggestPain(state).range,[4,6]);assert.equal(state.reported.pain,undefined);assert.match(state.doctor_summary,/not-reported/)
 engine.answerEye(state,{question_id:'pain-estimate:accept',value:'5'});assert.equal(state.reported.pain,5);assert.equal(state.reported.pain_source,'assisted-confirmed');assert.equal(state.pain_estimate.confirmed,true);assert.match(pain.painAssessment(state).summary,/confirmed the assistant/)
})
await test('the default guided interview asks words and activity rather than requiring a number',()=>{
 const state=engine.newEyeSession();for(const [id,value] of [['concern','My eye hurts'],['vision','unchanged'],['exposure','none'],['onset','gradual']])engine.answerEye(state,{question_id:`question.${id}`,value})
 assert.equal(engine.nextEyeQuestion(state).id,'question.pain-description');engine.answerEye(state,{question_id:'question.pain-description',value:'moderate'});assert.equal(engine.nextEyeQuestion(state).id,'question.pain-function');engine.answerEye(state,{question_id:'question.pain-function',value:'slowed'});assert.equal(engine.nextEyeQuestion(state),null);assert.equal(state.reported.pain,undefined);engine.answerEye(state,{question_id:'pain-estimate:accept',value:'5'});assert.ok(engine.nextEyeQuestion(state));assert.notEqual(engine.nextEyeQuestion(state).field,'pain')
})
await test('unknown and conflicting answers do not produce a default numeric estimate',()=>{
 const state=engine.newEyeSession();assert.equal(suggestion.suggestPain(state).suggested_score,null);engine.answerEye(state,{question_id:'question.pain-description',value:'mild'});assert.equal(suggestion.suggestPain(state).suggested_score,null);engine.answerEye(state,{question_id:'question.pain-function',value:'cannot'});assert.equal(suggestion.suggestPain(state).status,'needs_clarification');assert.equal(state.reported.pain,undefined);assert.throws(()=>engine.answerEye(state,{question_id:'pain-estimate:accept',value:'2'}))
})
await test('confirmation is checked against the current proposal and explicit correction retains its source',()=>{
 const state=engine.newEyeSession();engine.answerEye(state,{question_id:'question.concern',value:'Moderate eye pain distracts me'});assert.throws(()=>engine.answerEye(state,{question_id:'pain-estimate:accept',value:'9'}));assert.equal(state.reported.pain,undefined);engine.answerEye(state,{question_id:'pain-estimate:accept',value:'5'});engine.answerEye(state,{question_id:'question.pain',value:'2'});assert.equal(state.reported.pain,2);assert.equal(state.reported.pain_source,'self-reported');assert.equal(state.pain_estimate.confirmed,false)
})
await test('an estimate never overrides a visual emergency or delays stopping routine questions',()=>{
 const state=engine.newEyeSession();engine.answerEye(state,{question_id:'question.concern',value:'Mild eye pain, I can do my normal activities, but sudden loss of vision'});assert.equal(suggestion.suggestPain(state).suggested_score,2);assert.equal(state.urgency,'emergency');assert.equal(engine.nextEyeQuestion(state),null);assert.throws(()=>engine.answerEye(state,{question_id:'pain-estimate:accept',value:'2'}));assert.equal(state.care_plan.route,'emergency')
})
await test('a person can leave a proposed score unconfirmed and continue with pain unknown',()=>{
 const state=engine.newEyeSession();engine.answerEye(state,{question_id:'question.concern',value:'Moderate eye pain distracts me'});engine.answerEye(state,{question_id:'pain-estimate:skip',value:'skip'});assert.equal(state.reported.pain,undefined);assert.ok(state.missing.includes('pain'));assert.equal(state.reported.pain_entry_mode,'skipped')
})
await test('an explicit self-reported score does not gain an unrelated assistant estimate in the handoff',()=>{
 const state=engine.newEyeSession();engine.answerEye(state,{question_id:'question.concern',value:'Severe eye pain, 9/10'});assert.equal(state.reported.pain,9);assert.equal(state.pain_estimate.status,'not_requested');assert.equal(state.pain_estimate.suggested_score,null);assert.doesNotMatch(state.doctor_summary,/8\/10/)
})
