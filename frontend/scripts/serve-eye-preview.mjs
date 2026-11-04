import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
const root=fileURLToPath(new URL('../dist-eye-preview/',import.meta.url))
const port=Number(process.env.HUMANTWIN_PREVIEW_PORT||5174)
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml','.glb':'model/gltf-binary','.json':'application/json','.png':'image/png','.jpg':'image/jpeg','.webp':'image/webp'}
http.createServer((req,res)=>{
 let pathname;try{pathname=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname)}catch{res.writeHead(400);return res.end()}
 if(/^\/(api|sanctum)(\/|$)/.test(pathname)){
  const upstream=http.request({host:'127.0.0.1',port:8000,path:req.url,method:req.method,headers:req.headers},reply=>{res.writeHead(reply.statusCode,reply.headers);reply.pipe(res)})
  upstream.on('error',()=>{if(!res.headersSent)res.writeHead(503,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify({message:'The Laravel API is offline. The educational eye explorer works locally; account storage is unavailable.'}))});req.pipe(upstream);return
 }
 let file=path.resolve(root,'.'+pathname)
 if(!file.startsWith(path.resolve(root)+path.sep)&&file!==path.resolve(root)){res.writeHead(403);return res.end()}
 if(pathname.endsWith('/'))file=path.join(file,'index.html')
 if(!fs.existsSync(file)&&!path.extname(pathname))file=path.join(root,'index.html')
 fs.stat(file,(error,stat)=>{if(error||!stat.isFile()){res.writeHead(404);return res.end()}res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream','Content-Length':stat.size,'Cache-Control':'no-cache'});if(req.method==='HEAD')return res.end();const stream=fs.createReadStream(file);stream.on('error',()=>res.destroy());stream.pipe(res)})
}).listen(port,'127.0.0.1',()=>console.log(`HumanTwin eye upgrade: http://127.0.0.1:${port}`))
