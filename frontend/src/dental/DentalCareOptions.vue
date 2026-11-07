<script setup lang="ts">
import { computed, ref } from 'vue'
import content from '../../../contracts/dental/care-options.v1.json'
const props=defineProps<{caseIds:string[]}>()
const showAll=ref(false),selected=ref('fixed-braces')
const options=computed(()=>showAll.value||!props.caseIds.length?content.options:content.options.filter(option=>option.case_ids.some(id=>props.caseIds.includes(id))))
const current=computed(()=>options.value.find(option=>option.id===selected.value)||options.value[0]!)
const sources=computed(()=>content.sources.filter(source=>current.value.source_ids.includes(source.id)))
const riskSources=content.sources.filter(source=>content.shared_risk_source_ids.includes(source.id))
</script>
<template>
 <section class="dental-care-options" aria-label="Dental treatment options, benefits and drawbacks">
  <div class="care-options-heading"><span class="dental-eyebrow">HOW A DENTAL TEAM MAY ADDRESS THE PROBLEM</span><h3>Compare the options. Understand the tradeoffs.</h3><p>{{content.pathway_note}}</p></div>
  <div class="care-pathway"><span>Examination & records</span><i>→</i><span>Discuss options</span><i>→</i><span>Clinician’s plan</span><i>→</i><span>Supervised care & retention</span></div>
  <div class="care-option-tabs" role="group" aria-label="Treatment discussion options"><button v-for="option in options" :key="option.id" :aria-pressed="current.id===option.id" @click="selected=option.id">{{option.name}}</button></div><label v-if="caseIds.length" class="dental-check care-show-all"><input v-model="showAll" type="checkbox"/>Show all discussion options</label>
  <article class="care-option-detail"><span class="care-discussion-tag">Educational discussion · suitability not assessed</span><h4>{{current.name}}</h4><p>{{current.overview}}</p><div class="care-pros-cons"><div><h5><span>+</span>Potential advantages</h5><ul><li v-for="benefit in current.benefits" :key="benefit">{{benefit}}</li></ul></div><div><h5><span>−</span>Disadvantages & limitations</h5><ul><li v-for="tradeoff in current.tradeoffs" :key="tradeoff">{{tradeoff}}</li></ul></div></div><h5>What the clinician needs to check</h5><ul class="care-clinician-checks"><li v-for="check in current.clinician_checks" :key="check">{{check}}</li></ul><div class="care-option-sources"><a v-for="source in sources" :key="source.id" :href="source.url" target="_blank" rel="noopener noreferrer">{{source.publisher}} · {{source.title}} ↗</a></div></article>
  <details class="care-shared-risks"><summary>Shared orthodontic risks to discuss</summary><ul><li v-for="risk in content.shared_risks" :key="risk">{{risk}}</li></ul><a v-for="source in riskSources" :key="source.id" :href="source.url" target="_blank" rel="noopener noreferrer">{{source.publisher}} · risk guidance ↗</a></details><p class="care-option-note">Choosing a discussion tab does not prescribe that option or calculate its outcome. The photo mock-up uses reviewer-set positions; a dentist must decide what is appropriate and achievable.</p>
 </section>
</template>
