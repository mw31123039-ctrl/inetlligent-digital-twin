/** Optional native-free build for machines where native build tools are unavailable. */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { rollup } from '@rollup/wasm-node'
import { nodeResolve } from '@rollup/plugin-node-resolve'
import ts from 'typescript'
import { parse,compileScript,compileStyle } from '@vue/compiler-sfc'
const here=path.dirname(fileURLToPath(import.meta.url))
export const root=path.resolve(here,'..')
export function portablePlugins(styles=[]){return [
 {name:'human-twin-source',
  resolveId(source,importer){if(source.startsWith('.')&&importer){const target=path.resolve(path.dirname(importer),source);for(const extension of ['','.ts','.vue','.js','.json'])if(fs.existsSync(target+extension)&&fs.statSync(target+extension).isFile())return target+extension}},
  load(id){
   if(id.endsWith('.json'))return `export default ${fs.readFileSync(id,'utf8')}`
   if(id.endsWith('.css')){let css=fs.readFileSync(id,'utf8').replace('@import "tailwindcss";','').replace('@theme {',':root {');styles.push(css);return 'export default undefined'}
   if(id.endsWith('.vue')){
    const source=fs.readFileSync(id,'utf8'),{descriptor,errors}=parse(source,{filename:id});if(errors.length)throw new Error(`${id}: ${errors[0]}`)
    const scope='data-v-'+Buffer.from(path.relative(root,id)).toString('hex').slice(-16)
    const script=compileScript(descriptor,{id:scope,inlineTemplate:true,templateOptions:{compilerOptions:{whitespace:'condense',scopeId:descriptor.styles.some(s=>s.scoped)?scope:undefined}}})
    for(const style of descriptor.styles){const result=compileStyle({source:style.content,filename:id,id:scope,scoped:style.scoped});if(result.errors.length)throw new Error(String(result.errors[0]));styles.push(result.code)}
    let compiled=ts.transpileModule(script.content,{fileName:id+'.ts',compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText
    if(descriptor.styles.some(s=>s.scoped)){compiled=compiled.replace('export default','const __portable_component =');compiled+=`\n__portable_component.__scopeId=${JSON.stringify(scope)};export default __portable_component;`}
    return compiled
   }
  },
  transform(code,id){
   code=code.replaceAll('process.env.NODE_ENV',JSON.stringify('production')).replaceAll('__VUE_OPTIONS_API__','true').replaceAll('__VUE_PROD_DEVTOOLS__','false').replaceAll('__VUE_PROD_HYDRATION_MISMATCH_DETAILS__','false')
   if(id.endsWith('.ts')&&!id.includes('node_modules'))code=ts.transpileModule(code,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText
   if(id.startsWith(path.join(root,'src')))code=code.replaceAll('import.meta.env.BASE_URL',JSON.stringify('/')).replaceAll('import.meta.env.DEV','false').replaceAll('import.meta.env.PROD','true')
   return {code,map:null}
  }
 },nodeResolve({extensions:['.mjs','.js','.json','.ts','.vue'],browser:true,exportConditions:['browser','import','default']})
]}
export async function bundleModule(input,output){const bundle=await rollup({input,plugins:portablePlugins(),onwarn(warning,defaultHandler){if(warning.code!=='THIS_IS_UNDEFINED')defaultHandler(warning)}});await bundle.write({file:output,format:'esm',inlineDynamicImports:true});await bundle.close()}
export async function build(){
 const styles=['*,::before,::after{box-sizing:border-box}button,input,select,textarea{font:inherit}button{color:inherit}img,canvas,svg{vertical-align:middle}']
 const bundle=await rollup({input:path.join(root,'src/main.ts'),plugins:portablePlugins(styles),onwarn(warning,defaultHandler){if(warning.code!=='THIS_IS_UNDEFINED')defaultHandler(warning)}})
 // Isolated output avoids replacing an existing reviewed/deployed build.
 const out=path.join(root,'dist-eye-preview');fs.mkdirSync(out,{recursive:true});fs.cpSync(path.join(root,'public'),out,{recursive:true})
 await bundle.write({dir:path.join(out,'assets'),format:'esm',generatedCode:{symbols:true},entryFileNames:'app.js',chunkFileNames:'[name]-[hash].js',manualChunks(id){if(id.includes('node_modules/three/'))return 'three'}})
 await bundle.close();fs.writeFileSync(path.join(out,'assets/app.css'),styles.join('\n'))
 let html=fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/<script type="module"[^>]+src="\/src\/main.ts"><\/script>/,'<script type="module" src="/assets/app.js"></script><link rel="stylesheet" href="/assets/app.css">')
 fs.writeFileSync(path.join(out,'index.html'),html);console.log(`Native-free frontend build: ${out}`)
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))await build()
