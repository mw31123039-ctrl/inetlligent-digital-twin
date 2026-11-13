<script setup lang="ts">
import { computed } from 'vue'
import AppIcon from '../components/AppIcon.vue'
import { cancerTopics, clinicalSources, reviewPlan } from './knowledge'
import type { ReportedConcerns } from './knowledge'
import type { CancerHistory, CancerResult } from './model'
const props = defineProps<{ topicId: string; concerns: ReportedConcerns; priorEmergency: boolean; history: CancerHistory; result: CancerResult | null; subject: string }>()
defineEmits<{ edit: [] }>()
const topic = computed(() => cancerTopics.find(item => item.id === props.topicId) ?? cancerTopics[0]!)
const plan = computed(() => reviewPlan(topic.value.id, props.concerns, props.priorEmergency))
</script>
<template>
  <section class="care-plan-view" aria-label="Clinical review preparation">
    <div class="care-section-heading"><div><span class="care-eyebrow">FROM A FINDING TO THE NEXT STEP</span><h2>A review plan you can discuss.</h2><p>Bring your symptoms, source reports and questions together. A qualified clinician decides which tests and treatments are appropriate.</p></div><span class="care-source-stamp">Case {{ subject }}<br/>{{ topic.name }}</span></div>
    <div class="care-plan-priority" :class="{ emergency: plan.urgency === 'emergency', urgent: plan.urgency === 'urgent-medical-advice' }" role="status"><AppIcon name="info" :size="26"/><div><h3>{{ plan.title }}</h3><p>{{ plan.action }}</p><small>Based on reported concerns and source guidance. This is not a complete triage assessment.</small></div></div>
    <div class="care-plan-grid"><article class="care-paper"><span class="care-step-number">01</span><h3>Take the right information</h3><p>Suggested service: <strong>{{ plan.specialist }}</strong></p><dl><div><dt>Reported symptoms</dt><dd>{{ history.symptoms || 'Not recorded' }}</dd></div><div><dt>Duration</dt><dd>{{ history.duration || 'Not recorded' }}</dd></div><div><dt>Previous findings</dt><dd>{{ history.prior_findings || 'Not recorded' }}</dd></div><div><dt>Image-model result</dt><dd>{{ result && result.track === topic.modelTrack ? 'Experimental output available; include the original report for review.' : 'No matching image-model result in this case.' }}</dd></div></dl><button class="care-text-button" @click="$emit('edit')">Edit case information<AppIcon name="arrowRight" :size="17"/></button></article>
    <article class="care-paper"><span class="care-step-number">02</span><h3>Understand possible investigations</h3><p>A clinician may consider:</p><ul><li v-for="item in plan.investigations" :key="item">{{ item }}</li></ul><p>Biopsy and pathology often establish the diagnosis. The model does not determine cancer stage or replace review of the full imaging study.</p><a :href="clinicalSources.diagnosis.url" target="_blank" rel="noopener noreferrer">NCI: Diagnosis and tests<AppIcon name="arrowRight" :size="16"/></a></article>
    <article class="care-paper"><span class="care-step-number">03</span><h3>Discuss treatment after confirmation</h3><ul><li v-for="item in plan.treatment_education" :key="item">{{ item }}</li></ul><p>Choices depend on confirmed pathology, extent, biomarkers, health and preferences. This app does not prescribe cancer therapy, doses or a personal cure.</p><a :href="topic.source" target="_blank" rel="noopener noreferrer">NCI: {{ topic.name }} treatment<AppIcon name="arrowRight" :size="16"/></a></article>
    <article class="care-paper care-questions"><span class="care-step-number">04</span><h3>Questions for your appointment</h3><ul><li>What else could explain this finding?</li><li>Which test would clarify it, and why?</li><li>If cancer is confirmed, what type and stage is it?</li><li>Which treatment options fit my situation, and what are their benefits and harms?</li><li>What changes should prompt earlier medical help?</li></ul><p>The case export includes this educational checklist and its sources, with your permission.</p></article></div>
    <div class="care-review-sources"><strong>Guidance sources</strong><a v-for="source in plan.sources" :key="source" :href="source" target="_blank" rel="noopener noreferrer">{{ source.includes('nhs.uk') ? 'NHS clinical guidance' : 'National Cancer Institute' }}<AppIcon name="arrowRight" :size="15"/></a></div>
  </section>
</template>
