import { reactive,ref,type InjectionKey } from 'vue'
import { newEyeSession,answerEye } from './interview'
import { knowledgeTopic } from './knowledge'
import type { EyeTurn } from './types'
import { questions } from './content'
export function createEyeContext(side:'left'|'right'='left'){
 const session=reactive(newEyeSession(side)),acknowledged=ref(false),selected=ref('eye.cornea'),error=ref('')
 function answer(turn:EyeTurn){
  if(!acknowledged.value){error.value='Acknowledge the synthetic educational preview before entering an example.';return false}
  try{answerEye(session,turn);error.value='';return true}catch(e){error.value=e instanceof Error?e.message:'The answer could not be recorded.';return false}
 }
 function send(text:string,questionId:string){const topic=knowledgeTopic(text),question=questions.find(q=>q.id===questionId);return answer({question_id:topic?`learn:${topic.id}`:questionId,value:text,...(!topic&&question?.options.length?{text}:{})})}
 function explore(id:string){selected.value=id;if(!session.anatomy_explored.includes(id))session.anatomy_explored.push(id)}
 function reset(){const explored=[...session.anatomy_explored];Object.assign(session,newEyeSession(session.model_side,session.locale));session.anatomy_explored=explored;error.value=''}
 return {session,acknowledged,selected,error,answer,send,explore,reset}
}
export type EyeContext=ReturnType<typeof createEyeContext>
export const eyeContextKey:InjectionKey<EyeContext>=Symbol('HumanTwinEyeAssessment')
