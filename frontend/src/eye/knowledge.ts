import library from '../../../contracts/eye/knowledge.v1.json'
import type { EyeLocale,EyeSession } from './types'
export { library }
const normalize=(s:string)=>s.normalize('NFKC').toLocaleLowerCase().replace(/[’'“”?!.,:;؟]/g,'').replace(/\s+/g,' ').trim()
export function knowledgeTopic(input:string){
 const query=normalize(input)
 const explicit=/^(?:what (?:is|are|does|causes)|why |how (?:does|do|can|is)|explain |tell me about |teach me|learn about |can you explain |ما هو|ما هي|شنو |ليش |وضح |اشرح |چییە|بۆچی |ڕوونی بکەوە)/iu.test(query)
 if(!explicit)return null
 const stem=query.replace(/^(?:what (?:is|are)|explain|tell me about|شنو|اشرح|چییە|ڕوونی بکەوە)\s*/iu,'').replace(/^(?:the|a|an)\s+/,'')
 const matches=library.topics.flatMap(topic=>topic.aliases.map(a=>{const alias=normalize(a);return {topic,alias,score:alias===stem?1000+alias.length:query.includes(alias)?100+alias.length:0}})).filter(x=>x.alias.length>=3&&x.score>0)
 return matches.sort((a,b)=>b.score-a.score)[0]?.topic||null
}
export function educationalExchange(state:EyeSession,topicId:string,input:string){
 const topic=library.topics.find(t=>t.id===topicId)
 if(!topic)throw new Error('This educational topic is unavailable.')
 state.turns.push({question_id:`learn:${topic.id}`,value:input})
 state.messages.push({role:'user',text:input},{role:'assistant',text:topic.answer[state.locale],kind:'education',source_urls:topic.source_urls,topic_id:topic.id})
 return topic
}
export const learningPrompts:Record<EyeLocale,string[]>={en:['Explain the cornea','What is dry eye?','Explain the pain scale','What is a stye?','What is glaucoma?','Tell me about the retina'],'ar-IQ':['اشرح القرنية','شنو جفاف العين؟','اشرح pain scale','شنو شحاذ العين؟'],ckb:['ڕوونی بکەوە قەرنیە','چییە وشکی چاو','ڕوونی بکەوە pain scale','چییە گلاوکۆمای گۆشەکراوە']}
