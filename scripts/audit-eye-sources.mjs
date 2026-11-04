import { readFileSync,writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
const dir=fileURLToPath(new URL('../contracts/eye/',import.meta.url))
const catalogue=JSON.parse(readFileSync(dir+'conditions.v1.json','utf8'))
const anatomy=JSON.parse(readFileSync(dir+'sources.v1.json','utf8'))
const urls=[...new Set([...catalogue.conditions.flatMap(c=>c.source_urls),...anatomy.anatomy.map(s=>s.url)])]
const results=[];let cursor=0
async function worker(){while(cursor<urls.length){const url=urls[cursor++];let entry;try{const response=await fetch(url,{signal:AbortSignal.timeout(18000),headers:{'User-Agent':'HumanTwin educational-source-link-check/1.0'}});const html=await response.text();entry={url,status:response.status,final_url:response.url,title:(html.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1]||'').replace(/<[^>]*>/g,'').trim(),link_check:response.ok?'reachable':'requires-verification',clinical_review:'not-performed'};}catch(error){entry={url,status:null,link_check:'requires-verification',error:error.name,clinical_review:'not-performed'}}results.push(entry)}}
await Promise.all(Array.from({length:6},worker))
results.sort((a,b)=>a.url.localeCompare(b.url))
writeFileSync(dir+'source-audit.v1.json',JSON.stringify({checked_at:new Date().toISOString(),purpose:'Public link and title verification only. This is not a clinical content review.',sources:results},null,2)+'\n')
console.log(JSON.stringify({total:results.length,reachable:results.filter(x=>x.status===200).length,pending:results.filter(x=>x.status!==200)},null,2))
