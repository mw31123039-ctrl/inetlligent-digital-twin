<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { aiApi, ApiError } from '../services/aiApi'
import { downloadCase, type CasePhoto } from './caseModel'
import { preparePhoto, type PhotoStudy } from './photoSimulation'
const props=defineProps<{photo?:CasePhoto;study?:PhotoStudy;user:{id:number;email:string}|null;authPending:boolean;authError:string}>()
const emit=defineEmits<{authenticate:[email:string,password:string,register:boolean];modelChanged:[]}>()
interface LearningStatus {runtime:'local';examples:{id:string;subject_code:string;reviewer_code:string;partition:'train'|'validation'|'test';view:string;crowns:number}[];subjects:{train:number;validation:number;test:number};can_train:boolean;job:{state:string;phase:string};model:{provider_configured:boolean;train_images:number;validation_images:number;validation_dice:number|null}}
const subject=ref(''),reviewer=ref(''),partition=ref<'train'|'validation'|'test'>('train'),permission=ref(false),complete=ref(false),busy=ref(false),message=ref(''),error=ref('')
const status=ref<LearningStatus|null>(null),connected=ref(false),refreshing=ref(false),trainingConsent=ref(false),email=ref(''),password=ref(''),register=ref(false)
const code=/^[A-Za-z0-9_-]{1,48}$/
const reviewed=computed(()=>!!props.study?.crowns.length&&props.study.crowns.every(c=>c.reviewed))
const ready=computed(()=>reviewed.value&&code.test(subject.value)&&code.test(reviewer.value)&&permission.value&&complete.value)
const running=computed(()=>status.value?.job.state==='running')
const phases:Record<string,string>={queued:'Waiting for the local trainer',checking:'Checking photos and patient partitions',learning:'Learning crown colours, textures and edges',validating:'Checking separate validation photos',saving:'Saving the new local model',complete:'Local training completed',failed:'Training did not finish. Check the examples and try again.',discarded:'The teaching set changed during training. Train again with the current examples.'}
let generation=0,accountGeneration=0,timer:ReturnType<typeof setTimeout>|undefined
const controllers=new Set<AbortController>()
function clearTimer(){if(timer)clearTimeout(timer);timer=undefined}
function failureMessage(failure:unknown,fallback:string){return failure instanceof ApiError&&failure.status===0?'The local teaching service is unavailable. Your current photo is unchanged. Refresh to check the teaching set again.':failure instanceof Error?failure.message:fallback}
watch(()=>[props.photo?.id,props.photo?.view,JSON.stringify(props.study?.crowns.map(c=>({points:c.points,jaw:c.jaw,reviewed:c.reviewed}))),subject.value,reviewer.value,partition.value],()=>{generation++;permission.value=false;complete.value=false;message.value=''})
watch(()=>props.user?.id,()=>{accountGeneration++;generation++;for(const controller of controllers)controller.abort();controllers.clear();clearTimer();status.value=null;connected.value=false;busy.value=false;refreshing.value=false;permission.value=false;complete.value=false;trainingConsent.value=false;error.value='';message.value='';void refresh()},{immediate:true})
onBeforeUnmount(()=>{accountGeneration++;generation++;clearTimer();for(const controller of controllers)controller.abort()})
function apply(value:LearningStatus){
 if(value?.runtime!=='local'||!Array.isArray(value.examples)||!value.subjects||!value.job||!value.model)throw new Error('The local teaching response was invalid.')
 const previous=status.value
 status.value=value;connected.value=true
 if(previous?.model.provider_configured!==value.model.provider_configured||previous?.job.state!==value.job.state)emit('modelChanged')
 if(value.job.state==='running'){clearTimer();timer=setTimeout(()=>void refresh(),2000)}
}
async function refresh(){
 if(!props.user)return
 const version=accountGeneration,controller=new AbortController();controllers.add(controller);clearTimer();refreshing.value=true
 try{const value=await aiApi.get<LearningStatus>('/dental/learning',controller.signal);if(version===accountGeneration){apply(value);error.value=''}}
 catch(failure){if(version===accountGeneration&&!controller.signal.aborted){connected.value=false;error.value=failureMessage(failure,'The local teaching set could not be loaded.')}}
 finally{controllers.delete(controller);if(version===accountGeneration)refreshing.value=false}
}
async function preparedExample(){
 if(!ready.value||!props.photo||!props.study)throw new Error('Review all visible crown outlines and complete the teaching permissions first.')
 const view=props.photo.view,snapshot={crowns:props.study.crowns.map(c=>({jaw:c.jaw,points:c.points.map(p=>({...p}))})),subject_code:subject.value,reviewer_code:reviewer.value,partition:partition.value}
 const photo=await preparePhoto(props.photo.url)
 return {schema_version:'humantwin-local-crowns-v1',...snapshot,photo:{view,data_url:photo.data_url},input_sha256:photo.input_sha256,permission_training:true,complete_annotation:true}
}
async function saveExample(exportOnly=false){
 if(!ready.value||busy.value||(!exportOnly&&!props.user))return
 const version=generation,account=accountGeneration,controller=new AbortController();controllers.add(controller);busy.value=true;message.value='';error.value=''
 try{
  const example=await preparedExample();if(version!==generation||account!==accountGeneration)return
  if(exportOnly){downloadCase(example,`dental-local-${example.partition}-${example.input_sha256.slice(0,12)}.json`);message.value='Training example exported locally. It has not been saved to the teaching set or used to train a model.'}
  else{await aiApi.csrf();if(version!==generation||account!==accountGeneration)return;const value=await aiApi.post<LearningStatus>('/dental/learning/examples',example,controller.signal);if(account!==accountGeneration)return;apply(value);message.value='Reviewed example saved on this computer. Save more patients or train your local model. Saving does not start training.';trainingConsent.value=false}
  if(version===generation){permission.value=false;complete.value=false}
 }catch(failure){if(account===accountGeneration&&!controller.signal.aborted)error.value=failureMessage(failure,'The teaching example could not be saved.')}
 finally{controllers.delete(controller);if(account===accountGeneration)busy.value=false}
}
async function train(){
 if(!props.user||!connected.value||!status.value?.can_train||!trainingConsent.value||busy.value)return
 const version=accountGeneration,controller=new AbortController();controllers.add(controller);busy.value=true;error.value='';message.value='';trainingConsent.value=false
 try{await aiApi.csrf();if(version!==accountGeneration)return;const value=await aiApi.post<LearningStatus>('/dental/learning/train',{consent_training:true},controller.signal);if(version===accountGeneration)apply(value)}
 catch(failure){if(version===accountGeneration&&!controller.signal.aborted)error.value=failureMessage(failure,'Local training could not start.')}
 finally{controllers.delete(controller);if(version===accountGeneration)busy.value=false}
}
async function remove(id:string){
 if(!props.user||busy.value)return
 const version=accountGeneration;busy.value=true;error.value='';message.value='';trainingConsent.value=false
 try{await aiApi.csrf();if(version!==accountGeneration)return;await aiApi.delete('/dental/learning/examples/'+id);if(version!==accountGeneration)return;await refresh();message.value='Example removed. Saved model versions were invalidated; train again using the remaining examples.'}
 catch(failure){if(version===accountGeneration)error.value=failureMessage(failure,'The example could not be removed.')}
 finally{if(version===accountGeneration)busy.value=false}
}
</script>
<template>
 <details class="photo-local-learning" data-testid="local-dental-learning">
  <summary>Teach your local model <span>Review teeth → save examples → train here</span></summary>
  <p>Start with your own permitted dental photographs. Outline every visible crown, use local refinement if helpful, and have a dentist correct and review each boundary. This local model learns crown outlines; bite diagnoses and treatment plans require separate clinical evidence.</p>
  <form v-if="!user" class="learning-auth" @submit.prevent="emit('authenticate',email,password,register)"><p>Sign in to keep a private teaching set on this computer.</p><label>Email<input v-model="email" type="email" autocomplete="username" required/></label><label>Password<input v-model="password" type="password" :autocomplete="register?'new-password':'current-password'" minlength="12" required/></label><label class="dental-check"><input v-model="register" type="checkbox"/>Create a test account</label><button class="button-secondary" :disabled="authPending">{{authPending?'Please wait…':register?'Create account':'Sign in'}}</button><p v-if="authError" role="alert">{{authError}}</p></form>
  <template v-if="photo&&study">
   <h4>1. Save a reviewed example</h4>
   <div class="local-learning-fields"><label>Coded subject ID<input v-model="subject" maxlength="48" pattern="[A-Za-z0-9_-]+" placeholder="e.g. SUBJECT_017" aria-label="Local training subject code"/></label><label>Reviewer code<input v-model="reviewer" maxlength="48" pattern="[A-Za-z0-9_-]+" placeholder="e.g. DENTIST_02" aria-label="Local training reviewer code"/></label><label>Patient partition<select v-model="partition" aria-label="Local training partition"><option value="train">Training</option><option value="validation">Validation · separate patients</option><option value="test">Test · untouched patients</option></select></label></div>
   <label class="dental-check"><input v-model="complete" type="checkbox" :disabled="!reviewed"/>A dentist checked these outlines, and every visible crown is annotated. Unmarked pixels will count as background.</label>
   <label class="dental-check"><input v-model="permission" type="checkbox"/>I have permission to save this de-identified photo and its labels locally for teaching and to export them.</label>
   <div class="learning-actions"><button class="button-primary" :disabled="!ready||!user||busy" @click="saveExample(false)">{{busy?'Please wait…':'Save reviewed example locally'}}</button><button class="button-secondary" :disabled="!ready||busy" @click="saveExample(true)">Export local training example</button></div>
   <small>Saving includes the photograph and persists after reload, only in this account’s local teaching set. Nothing goes to an external AI provider. Ordinary photo attachment and review do not save or train anything.</small>
  </template>
  <p v-else>Add a photograph above to begin outlining its teeth. Your saved teaching set remains available below.</p>
  <div v-if="user" class="learning-dataset">
   <div class="learning-dataset-heading"><h4>2. Your local teaching set</h4><button class="dental-text-button" :disabled="refreshing||busy" @click="refresh">{{refreshing?'Refreshing…':'Refresh teaching set'}}</button></div>
   <template v-if="status"><div class="learning-counts"><span>{{status.examples.length}} saved photos</span><span>{{status.subjects.train}} training subjects</span><span>{{status.subjects.validation}} validation subjects</span><span>{{status.subjects.test}} test subjects</span></div>
    <p v-if="!status.can_train&&!running">To start training, save photos from at least two training subjects and a different validation subject. Use the same code and partition for all photos and visits of one patient. This minimum checks the software; it cannot establish medical accuracy.</p>
    <details v-if="status.examples.length" class="learning-saved-list"><summary>Review saved examples ({{status.examples.length}})</summary><article v-for="item in status.examples" :key="item.id"><div><strong>{{item.subject_code}}</strong><span>{{item.partition}} · {{item.view}} · {{item.crowns}} crowns</span></div><button class="dental-text-button" :disabled="busy" :aria-label="`Remove teaching example ${item.subject_code} ${item.id.slice(0,6)}`" @click="remove(item.id)">Remove</button></article><small>Removing an example also invalidates saved model versions. Retrain after removing or correcting data.</small></details>
    <h4>3. Train on this computer</h4><label class="dental-check"><input v-model="trainingConsent" type="checkbox" :disabled="!status.can_train||busy||!connected"/>Train a new local model using my saved teaching set.</label><button class="button-primary" :disabled="!status.can_train||!trainingConsent||busy||!connected" @click="train">{{running?'Training locally…':'Train local model'}}</button>
    <p v-if="status.job.state!=='idle'" class="learning-progress" role="status" :aria-busy="running">{{phases[status.job.phase]||'Local training in progress'}}{{running?'…':''}}</p>
    <p v-if="status.model.provider_configured" class="learning-result">Your local model is ready for draft outlines. {{status.model.train_images}} training photos; {{status.model.validation_images}} separate validation photos. Foreground Dice: {{status.model.validation_dice===null?'unavailable':status.model.validation_dice.toFixed(3)}}. This metric measures foreground overlap, not diagnostic or treatment accuracy.</p>
    <small>Training continues if you close this panel. Changing examples during a run discards its result. To teach a correction, edit and review the same source photo, then save it again before retraining.</small>
   </template>
  </div>
  <p v-if="error" class="dental-error" role="alert">{{error}}</p><p v-if="message" class="learning-message" role="status">{{message}}</p>
 </details>
</template>
