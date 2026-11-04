<script setup lang="ts">
import { computed,defineAsyncComponent,ref,watch } from 'vue'
import { anatomy,structures,structureById,text,ui,viewLabels } from './content'
import { eyeColors,nasalDirection,viewShows } from './model'
import type { EyeLocale,EyeView,EyeStructure } from './types'
const EyeCanvas=defineAsyncComponent(()=>import('./EyeCanvas.vue'))
const props=defineProps<{side:'left'|'right';locale:EyeLocale;reducedMotion:boolean;selected:string;compact?:boolean;display?:'2d'|'3d'}>()
const emit=defineEmits<{select:[id:string];report:[]}>()
const view=ref<EyeView>('external'),query=ref(''),hidden=ref<string[]>([]),isolated=ref(false),hovered=ref(''),fallback=ref(props.display==='2d')
watch(()=>props.display,value=>{if(value)fallback.value=value==='2d'})
watch(()=>props.selected,id=>{const structure=structureById.get(id);if(structure&&!viewShows(structure,view.value))view.value=structure.preferred_view;if(structure)hidden.value=hidden.value.filter(g=>g!==structure.group)},{immediate:true})
const canvas=ref<{reset():void;zoom(n:number):void;rotate(n:number):void;getSnapshot():unknown}>()
const current=computed(()=>structureById.get(props.selected)!)
const filtered=computed(()=>structures.filter(s=>(s.label.en+' '+s.label[props.locale]+' '+s.id).toLocaleLowerCase().includes(query.value.toLocaleLowerCase())))
const visible=computed(()=>structures.filter(s=>viewShows(s,view.value)&&!hidden.value.includes(s.group)&&(!isolated.value||s.id===props.selected)))
const scale=ref(1),angle=ref(0)
function select(id:string){const item=structureById.get(id);if(!item)return;emit('select',id);if(!viewShows(item,view.value))view.value=item.preferred_view;hidden.value=hidden.value.filter(g=>g!==item.group)}
function toggleGroup(group:string){hidden.value=hidden.value.includes(group)?hidden.value.filter(x=>x!==group):[...hidden.value,group]}
function changeView(value:EyeView){view.value=value;if(current.value&&!viewShows(current.value,value)){const candidate=structures.find(s=>s.id===({external:'eye.cornea',section:'eye.lens',transparent:'eye.sclera',exploded:'eye.lens',posterior:'eye.retina','corneal-detail':'eye.corneal-epithelium','retinal-detail':'eye.photoreceptors'}[value]));if(candidate)emit('select',candidate.id)}}
function zoom(n:number){if(fallback.value)scale.value=Math.max(.65,Math.min(2,scale.value+(n>0?.15:-.15)));else canvas.value?.zoom(n)}
function reset(){hidden.value=[];isolated.value=false;scale.value=1;angle.value=0;canvas.value?.reset()}
function svgPosition(s:EyeStructure){
 if(s.shape==='micro'){const list=visible.value.filter(x=>x.shape==='micro');return {x:200,y:95+list.indexOf(s)*52,rx:112,ry:s.id==='eye.corneal-stroma'?22:12}}
 const section=['section','exploded'].includes(view.value)
 let x=section?210+s.position[2]!*100:210+s.position[0]!*nasalDirection(props.side)*95
 let y=200-s.position[1]!*95
 if(view.value==='exploded')x+=['surface','tears','cornea','fluid','focus','vitreous','coats','retina','nerve','orbit'].indexOf(s.group)*12-55
 return {x,y,rx:Math.max(4,s.scale[section?2:0]!*87),ry:Math.max(4,s.scale[1]!*87)}
}
defineExpose({select,reset,zoom,getSnapshot:()=>canvas.value?.getSnapshot()||{side:props.side,view:view.value,structures:visible.value.map(s=>s.id),fallback:true}})
</script>
<template>
 <div class="eye-atlas" :class="{'eye-atlas-compact':compact}">
  <div class="eye-model-panel">
   <div class="eye-view-tabs" role="group" aria-label="Anatomy view"><button v-for="(label,id) in viewLabels" :key="id" :aria-pressed="view===id" @click="changeView(id as EyeView)">{{text(label,locale)}}</button></div>
   <div class="eye-model-stage" :data-view="view" :data-patient-side="side">
    <div class="eye-model-watermark">{{view.includes('detail')?'MAGNIFIED · NOT TO SCALE':view==='external'?'REFERENCE EYE · SURFACE VIEW':'SCHEMATIC ANATOMY'}}</div>
    <EyeCanvas v-if="!fallback" ref="canvas" :side="side" :view="view" :selected="selected" :hidden="hidden" :isolated="isolated" :reduced-motion="reducedMotion" @select="select" @hover="hovered=$event" @error="fallback=true"/>
    <svg v-else viewBox="0 0 420 400" class="eye-svg" role="group" :aria-label="`${side} eye accessible schematic; ${view}`">
     <g :transform="`translate(210 200) scale(${scale}) rotate(${angle}) translate(-210 -200)`">
      <ellipse v-if="!view.includes('detail')" cx="210" cy="200" rx="92" ry="92" fill="#efe6d5" fill-opacity=".12" stroke="#aac4c5"/>
      <g v-for="s in visible" :key="s.id" role="button" tabindex="0" :aria-label="text(s.label,locale)" :aria-pressed="selected===s.id" :data-anatomy-id="s.id" class="eye-svg-structure" :class="{selected:selected===s.id}" @click="select(s.id)" @keydown.enter.prevent="select(s.id)" @keydown.space.prevent="select(s.id)" @pointerenter="hovered=s.id" @pointerleave="hovered=''">
       <title>{{text(s.label,locale)}}</title>
       <rect v-if="s.shape==='micro'" :x="svgPosition(s).x-svgPosition(s).rx" :y="svgPosition(s).y-svgPosition(s).ry" :width="svgPosition(s).rx*2" :height="svgPosition(s).ry*2" rx="5" :fill="eyeColors[s.group]"/>
       <path v-else-if="s.shape==='iris' && !['section','exploded'].includes(view)" d="M 263 200 A 53 53 0 1 0 157 200 A 53 53 0 1 0 263 200 M 230 200 A 20 20 0 1 1 190 200 A 20 20 0 1 1 230 200" fill="#54a4a0" fill-rule="evenodd"/>
       <ellipse v-else :cx="svgPosition(s).x" :cy="svgPosition(s).y" :rx="svgPosition(s).rx" :ry="svgPosition(s).ry" :fill="['ring','shell','opening','orbit'].includes(s.shape)?'transparent':eyeColors[s.group]" :fill-opacity="s.shape==='volume'?.15:.6" :stroke="eyeColors[s.group]" :stroke-width="s.shape==='opening'?1:2"/>
      </g>
     </g>
    </svg>
    <span class="eye-patient-mark">{{text(side==='left'?ui.left:ui.right,locale)}} · {{locale==='en'?'fixed anatomical side':'L / R = patient'}}</span>
    <span v-if="hovered" class="eye-hover-label" role="status">{{structureById.get(hovered)?.label[locale]}}</span>
   </div>
   <div class="eye-model-tools"><button @click="canvas?.rotate(-.3);angle-=10" aria-label="Rotate left">↶</button><button @click="canvas?.rotate(.3);angle+=10" aria-label="Rotate right">↷</button><button @click="zoom(1)" aria-label="Zoom in">＋</button><button @click="zoom(-1)" aria-label="Zoom out">−</button><button @click="reset">{{locale==='en'?'Reset view':locale==='ar-IQ'?'إعادة العرض':'نوێکردنەوەی دیمەن'}}</button><button :aria-pressed="fallback" @click="fallback=!fallback">{{fallback?'Try 3D':'2D atlas'}}</button><label><input v-model="isolated" type="checkbox"/>{{locale==='en'?'Isolate selection':locale==='ar-IQ'?'اعزل الاختيار':'تەنها هەڵبژاردە'}}</label></div>
   <p class="eye-model-note">{{locale==='en'?'Drag to rotate · pinch or scroll to zoom · use the list for precise and keyboard selection. Layers and distances are schematic.':locale==='ar-IQ'?'اسحب للتدوير وكبّر بإصبعين. استخدم القائمة للاختيار الدقيق. الطبقات والمسافات تخطيطية.':'بۆ سووڕاندن ڕایبکێشە و بە دوو پەنجە گەورەی بکە. لیستەکە بۆ هەڵبژاردنی ورد بەکاربهێنە. پێکهاتەکان هێڵکاریین.'}}</p>
   <details class="eye-layers"><summary>{{locale==='en'?'Layer visibility':locale==='ar-IQ'?'إظهار الطبقات':'پیشاندانی چینەکان'}}</summary><div><label v-for="group in anatomy.groups" :key="group.id"><input type="checkbox" :checked="!hidden.includes(group.id)" @change="toggleGroup(group.id)"/><i :style="{background:eyeColors[group.id]}"/>{{text(group.label,locale)}}</label></div></details>
  </div>
  <aside class="eye-structure-panel">
   <div class="eye-structure-info"><span class="eye-kicker">{{current?.id}}</span><h3>{{current?.label[locale]}}</h3><p>{{current?.function[locale]}}</p><details v-if="locale!=='en'"><summary>{{text(ui.original,locale)}}</summary><p lang="en" dir="ltr">{{current?.function.en}}</p></details><p class="eye-subtle">{{text(ui.notDiagnosis,locale)}}</p><button class="eye-link-button" @click="emit('report')">{{text(ui.report,locale)}} →</button></div>
   <label class="eye-search">{{text(ui.search,locale)}}<input v-model="query" type="search" :placeholder="locale==='en'?'e.g. retina, lens, tear…':locale==='ar-IQ'?'مثلاً القرنية أو الدمع':'بۆ نموونە قەرنیە یان فرمێسک'"/></label>
   <div class="eye-anatomy-list" role="group" aria-label="Selectable eye anatomy"><button v-for="s in filtered" :key="s.id" :aria-pressed="selected===s.id" :data-structure-id="s.id" @click="select(s.id)"><i :style="{background:eyeColors[s.group]}"/><span>{{s.label[locale]}}<small v-if="locale!=='en'" lang="en" dir="ltr">{{s.label.en}}</small></span><small v-if="s.shape==='micro'">×</small></button><p v-if="!filtered.length">{{locale==='en'?'No matching structures.':locale==='ar-IQ'?'ماكو نتائج.':'ئەنجام نییە.'}}</p></div>
   <div class="eye-reference-links"><a href="https://www.msdmanuals.com/professional/eye-disorders/approach-to-the-ophthalmologic-patient/ophthalmic-anatomy" target="_blank" rel="noopener noreferrer">MSD · anatomy ↗</a><a href="https://www.aao.org/eye-health/anatomy/human-eye" target="_blank" rel="noopener noreferrer">AAO · eye anatomy ↗</a></div>
  </aside>
 </div>
</template>
