<script setup lang="ts">
import { computed, ref } from 'vue'
import { findStudyCases, orthodonticSources, type CasePhoto } from './caseModel'
defineProps<{caseId:string;findings:string[];notes:string;photo?:CasePhoto;user:{id:number;email:string}|null;authPending:boolean;authError:string}>()
const emit=defineEmits<{authenticate:[email:string,password:string,register:boolean];open:[id:string]}>()
const query=ref(''),searched=ref('')
const matches=computed(()=>findStudyCases(searched.value))
</script>
<template>
 <section class="ortho-coach panel" aria-label="Dental study coach">
  <div class="ortho-card-top"><div><span class="dental-eyebrow">A REFERENCE AT YOUR SIDE</span><h3>Study coach</h3></div><span class="ortho-ai-state">Local reference library</span></div>
  <p>Search dental conditions, recognition cues and records to discuss with a dentist. Treatment options above explain how each approach works, its potential advantages and its disadvantages. This search uses the sourced library on your computer.</p>
  <form class="ortho-coach-search" @submit.prevent="searched=query"><label for="ortho-question">What would you like to understand?</label><div><input id="ortho-question" v-model="query" maxlength="1000" placeholder="e.g. Crowding or a deep bite?"/><button class="button-secondary" type="submit">Find references</button></div></form>
  <div v-if="searched" class="ortho-coach-references" aria-live="polite"><span class="ortho-tiny-label">LOCAL LIBRARY SEARCH</span><p v-if="!matches.length">No matching topic. Try crowding, spacing, crossbite or open bite.</p><article v-for="item in matches" :key="item.id"><button class="dental-text-button" @click="emit('open',item.id)">{{item.name}} ↗</button><p>{{item.summary}}</p><a v-for="source in orthodonticSources.filter(s=>item.source_ids.includes(s.id)).slice(0,1)" :key="source.id" :href="source.url" target="_blank" rel="noopener noreferrer">{{source.publisher}} ↗</a></article></div>
 </section>
</template>
