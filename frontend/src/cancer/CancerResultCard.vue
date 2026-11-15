<script setup lang="ts">
import { computed, ref } from 'vue'
import AppIcon from '../components/AppIcon.vue'
import HeatmapImage from './HeatmapImage.vue'
import { classMeaning, confidenceText, guideFor, reasonText, specialists, summarize } from './report'
import { modalities, pathways } from './model'
import type { CancerResult } from './model'

const props = defineProps<{
  result: CancerResult
  imageSrc: string
  createdAt?: string
  mode: 'live' | 'saved'
  signedIn?: boolean
  saving?: boolean
  saved?: boolean
  exporting?: boolean
  uid?: string
}>()
const emit = defineEmits<{ guide: [topicId: string]; save: [note: string]; pdf: []; json: []; remove: [] }>()
const storageConsent = ref(false), note = ref('')
const summary = computed(() => summarize(props.result))
const area = computed(() => pathways.find(item => item.id === props.result.track)!)
const guide = computed(() => guideFor(props.result.track))
const ranked = computed(() => [...props.result.scores].sort((a, b) => b.value - a.value))
const confidence = computed(() => props.result.confidence)
const visibleChecks = computed(() => props.result.image_checks.findings.filter(item => item.severity !== 'info'))
const date = computed(() => props.createdAt ? new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(props.createdAt)) : '')
const percent = (value: number) => Math.round(value * 100) + '%'
const severityLabel: Record<string, string> = { reject: 'Not accepted', limiting: 'Limits the result', warning: 'Check', info: 'Note' }
</script>

<template>
  <article class="cw-result" :class="'tone-' + summary.tone" :aria-labelledby="(uid ?? 'cw') + '-result-title'">
    <p class="cw-disclaimer" role="note"><AppIcon name="shield" :size="18"/><span><strong>Not a medical diagnosis.</strong> An experimental research model looked at one image. It cannot confirm or rule out cancer.</span></p>
    <header class="cw-result-head">
      <div>
        <span class="cw-badge" :class="'tone-' + summary.tone">{{ summary.badge }}</span>
        <h3 :id="(uid ?? 'cw') + '-result-title'" tabindex="-1">{{ summary.headline }}</h3>
        <p class="cw-meta">{{ area.label }} · {{ modalities[result.modality].label }}<template v-if="date"> · {{ date }}</template></p>
      </div>
    </header>

    <div class="cw-result-grid">
      <HeatmapImage :src="imageSrc" :heatmap="result.heatmap" :track="result.track" :alt="'Image analysed by the ' + area.label.toLowerCase() + ' model'"/>
      <div class="cw-result-body">
        <section v-if="confidence" class="cw-result-section" :aria-labelledby="(uid ?? 'cw') + '-confidence-title'">
          <h4 :id="(uid ?? 'cw') + '-confidence-title'">Model confidence</h4>
          <div class="cw-meter" role="meter" :aria-valuenow="Math.round(confidence.probability * 100)" aria-valuemin="0" aria-valuemax="100" :aria-valuetext="confidenceText(result)" :aria-labelledby="(uid ?? 'cw') + '-confidence-title'">
            <i :style="{ width: confidence.probability * 100 + '%' }" :class="'level-' + confidence.level"></i>
            <b :style="{ left: confidence.decision_threshold * 100 + '%' }" :title="'Minimum for a finding: ' + percent(confidence.decision_threshold)"></b>
          </div>
          <p class="cw-meter-label"><strong>{{ percent(confidence.probability) }}</strong> {{ confidenceText(result).replace(/ \(\d+%\)/, '') }}</p>
          <p class="cw-help">The marker shows the minimum ({{ percent(confidence.decision_threshold) }}) needed for a finding. Confidence describes the model, not your personal chance of having cancer.</p>
        </section>
        <section class="cw-result-section">
          <h4>What this means</h4>
          <p>{{ summary.meaning }}</p>
          <ul v-if="result.outcome === 'inconclusive'" class="cw-reasons"><li v-for="reason in result.outcome_reasons" :key="reason">{{ reasonText[reason] }}</li></ul>
        </section>
        <section class="cw-result-section cw-next">
          <h4>Suggested next step</h4>
          <p>{{ summary.nextStep }}</p>
          <div class="cw-next-actions">
            <span v-if="result.outcome !== 'input-rejected'" class="cw-chip"><AppIcon name="user" :size="16"/>{{ specialists[result.track].short }}</span>
            <button type="button" class="cw-link-button" @click="emit('guide', guide.id)">Read the {{ guide.name }} guide<AppIcon name="arrowRight" :size="16"/></button>
          </div>
        </section>
      </div>
    </div>

    <details v-if="ranked.length" class="cw-details">
      <summary>All categories the model considered<AppIcon name="chevronDown" :size="18"/></summary>
      <ul class="cw-scores">
        <li v-for="score in ranked" :key="score.label"><span>{{ classMeaning(score.label, result.track).name }}</span><span class="cw-score-track" aria-hidden="true"><i :style="{ width: score.value * 100 + '%' }"></i></span><strong>{{ (score.value * 100).toFixed(1) }}%</strong></li>
      </ul>
    </details>
    <details class="cw-details" :open="result.outcome !== 'finding' && visibleChecks.length > 0">
      <summary>Image checks and technical details<AppIcon name="chevronDown" :size="18"/></summary>
      <ul v-if="visibleChecks.length" class="cw-checks"><li v-for="item in visibleChecks" :key="item.code" :class="'sev-' + item.severity"><strong>{{ severityLabel[item.severity] }}</strong>{{ item.message }}</li></ul>
      <p v-else class="cw-help">The image passed the automatic checks. Anatomy and image quality are not verified clinically.</p>
      <dl class="cw-tech">
        <div><dt>Model</dt><dd>{{ result.model_version }}</dd></div>
        <div v-if="confidence"><dt>Calibration</dt><dd>{{ confidence.calibration === 'temperature-scaled' ? 'Temperature ' + confidence.temperature?.toFixed(2) + ', fitted on held-out images' : 'Not calibrated' }}</dd></div>
        <div v-if="result.familiarity"><dt>Familiarity</dt><dd>{{ result.familiarity.familiar ? 'Similar to the model’s reference images' : 'Unlike the model’s reference images' }} ({{ result.familiarity.similarity.toFixed(2) }}, minimum {{ result.familiarity.minimum_similarity.toFixed(2) }})</dd></div>
        <div v-if="result.heatmap"><dt>Explanation</dt><dd>{{ result.heatmap.method === 'grad-cam' ? 'Grad-CAM' : result.heatmap.method === 'attention-rollout' ? 'Attention rollout' : 'Occlusion sensitivity' }}, {{ result.heatmap.grid_width }} × {{ result.heatmap.grid_height }} grid</dd></div>
        <div><dt>Image</dt><dd>{{ result.image_checks.width }} × {{ result.image_checks.height }} px</dd></div>
        <div v-if="result.inference_ms"><dt>Processing time</dt><dd>{{ result.inference_ms >= 1000 ? (result.inference_ms / 1000).toFixed(1) + ' s' : Math.round(result.inference_ms) + ' ms' }} on {{ result.runtime === 'onnxruntime-cpu' ? 'ONNX Runtime (CPU)' : 'CPU' }}</dd></div>
        <div v-if="result.model_info"><dt>Evaluation</dt><dd>{{ result.model_info.evaluation_reference }}</dd></div>
        <div v-if="result.model_info"><dt>Source</dt><dd><a :href="result.model_info.source_url" target="_blank" rel="noopener noreferrer">Model source<span class="sr-only"> (opens in a new tab)</span></a> · {{ result.model_info.license }}</dd></div>
        <div><dt>Image fingerprint</dt><dd class="cw-hash">{{ result.input_sha256 }}</dd></div>
      </dl>
    </details>

    <footer class="cw-result-actions">
      <template v-if="mode === 'live' && result.outcome !== 'input-rejected'">
        <div v-if="saved" class="cw-saved" role="status"><AppIcon name="complete" :size="18"/>Saved to History</div>
        <form v-else-if="signedIn" class="cw-save" @submit.prevent="storageConsent && emit('save', note)">
          <label class="cw-check"><input v-model="storageConsent" type="checkbox"/>Save this report to my account history (encrypted). I can delete it at any time.</label>
          <label v-if="storageConsent" class="cw-note">Note for yourself (optional)<input v-model="note" maxlength="500" placeholder="For example: mole on left forearm" autocomplete="off"/></label>
          <button class="cw-button primary" type="submit" :disabled="!storageConsent || saving"><AppIcon name="clipboard" :size="18"/>{{ saving ? 'Saving…' : 'Save to history' }}</button>
        </form>
        <p v-else class="cw-help">Sign in to save reports to your history.</p>
      </template>
      <div class="cw-export">
        <button type="button" class="cw-button" :disabled="exporting" @click="emit('pdf')"><AppIcon name="download" :size="18"/>{{ exporting ? 'Preparing…' : 'Export PDF' }}</button>
        <button v-if="mode === 'live'" type="button" class="cw-button ghost" @click="emit('json')">Research data (JSON)</button>
        <button v-if="mode === 'saved'" type="button" class="cw-button danger" @click="emit('remove')"><AppIcon name="trash" :size="18"/>Delete report</button>
      </div>
    </footer>
  </article>
</template>
