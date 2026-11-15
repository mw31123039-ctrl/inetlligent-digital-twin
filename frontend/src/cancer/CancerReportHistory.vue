<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import AppIcon from '../components/AppIcon.vue'
import CancerResultCard from './CancerResultCard.vue'
import { classMeaning, compositeImage, guideFor, printReport, reportHtml } from './report'
import { reportsApi } from './reportsApi'
import type { ReportSummaryRow, SavedReport } from './reportsApi'
import { modalities, pathways } from './model'
import './cancer-care.css'

const props = defineProps<{ signedIn: boolean; refreshKey?: number }>()
const emit = defineEmits<{ analyze: []; signIn: []; guide: [topicId: string] }>()
const reports = ref<ReportSummaryRow[]>([]), loading = ref(false), error = ref(''), opened = ref<SavedReport | null>(null), exporting = ref(false)
const dialog = ref<HTMLDialogElement | null>(null)
let controller: AbortController | null = null

async function load() {
  if (!props.signedIn) { reports.value = []; return }
  controller?.abort(); controller = new AbortController()
  const active = controller
  loading.value = true; error.value = ''
  try { const rows = await reportsApi.list(active.signal); if (!active.signal.aborted) reports.value = rows }
  catch (cause) { if (!active.signal.aborted) error.value = cause instanceof Error ? cause.message : 'Saved reports could not be loaded.' }
  finally { if (controller === active) loading.value = false }
}
onMounted(load)
watch(() => [props.signedIn, props.refreshKey], load)

const date = (value: string) => new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
const area = (track: string) => pathways.find(item => item.id === track)?.label ?? track
function title(item: ReportSummaryRow) {
  if (item.outcome === 'input-rejected') return 'Image not accepted'
  if (item.outcome === 'inconclusive') return 'Inconclusive result'
  return classMeaning(item.finding_label ?? '', item.track).name
}
async function open(item: ReportSummaryRow) {
  error.value = ''
  try { opened.value = await reportsApi.show(item.id); await nextTick(); dialog.value?.showModal() }
  catch (cause) { error.value = cause instanceof Error ? cause.message : 'The report could not be opened.' }
}
function close() { dialog.value?.close(); opened.value = null }
async function remove(id: string) {
  if (!window.confirm('Delete this saved report? This cannot be undone.')) return
  try { await reportsApi.remove(id); reports.value = reports.value.filter(item => item.id !== id); if (opened.value?.id === id) close() }
  catch (cause) { error.value = cause instanceof Error ? cause.message : 'The report could not be deleted.' }
}
async function exportPdf() {
  if (!opened.value || exporting.value) return
  exporting.value = true
  try {
    const report = opened.value
    const [plain, overlay] = await Promise.all([compositeImage(report.thumbnail_data_url, null), report.result.heatmap ? compositeImage(report.thumbnail_data_url, report.result.heatmap) : Promise.resolve(null)])
    printReport(reportHtml({ result: report.result, imageDataUrl: plain, heatmapDataUrl: overlay, createdAt: report.created_at, note: report.note }))
  } finally { exporting.value = false }
}
function guide(topicId: string) { close(); emit('guide', topicId) }
</script>

<template>
  <section class="cancer-workspace cw-history" aria-labelledby="cw-history-title">
    <header class="cw-history-head">
      <div><h2 id="cw-history-title">Cancer research reports</h2><p class="cw-help">Reports you saved from the Cancer research page. Stored encrypted in your account; only you can see them.</p></div>
      <button v-if="signedIn && reports.length" type="button" class="cw-link-button" :disabled="loading" @click="load"><AppIcon name="reset" :size="16"/>Refresh</button>
    </header>
    <p v-if="error" class="cancer-error" role="alert"><span>{{ error }}</span></p>
    <div v-if="!signedIn" class="cw-empty"><span class="cw-empty-icon" aria-hidden="true"><AppIcon name="user" :size="26"/></span><div><p><strong>Sign in to see your saved reports.</strong></p><p class="cw-help">Saving a report needs an account so it can be encrypted and kept private.</p><button type="button" class="cw-button" @click="emit('signIn')">Sign in</button></div></div>
    <p v-else-if="loading && !reports.length" class="cw-help" role="status">Loading saved reports…</p>
    <div v-else-if="!reports.length" class="cw-empty"><span class="cw-empty-icon" aria-hidden="true"><AppIcon name="clipboard" :size="26"/></span><div><p><strong>No saved reports yet.</strong></p><p class="cw-help">After you analyse an image, choose “Save to history” on the result to keep the report here.</p><button type="button" class="cw-button primary" @click="emit('analyze')"><AppIcon name="scan" :size="18"/>Analyse an image</button></div></div>
    <ul v-else class="cw-history-list">
      <li v-for="item in reports" :key="item.id" class="cw-history-item">
        <span class="cw-badge" :class="item.outcome === 'finding' ? 'tone-reassuring' : item.outcome === 'input-rejected' ? 'tone-blocked' : ''">{{ item.outcome === 'finding' ? 'Finding' : item.outcome === 'inconclusive' ? 'Inconclusive' : 'Not accepted' }}</span>
        <div class="cw-history-main"><strong>{{ title(item) }}</strong><span>{{ area(item.track) }} · {{ modalities[item.modality]?.label }} · {{ date(item.created_at) }}</span></div>
        <div class="cw-history-actions"><button type="button" class="cw-button" @click="open(item)">Open report</button><button type="button" class="cw-link-button" :aria-label="'Delete report from ' + date(item.created_at)" @click="remove(item.id)"><AppIcon name="trash" :size="16"/>Delete</button></div>
      </li>
    </ul>
    <dialog ref="dialog" class="cw-report-dialog" aria-labelledby="cw-saved-result-title" @cancel.prevent="close" @close="opened = null">
      <div v-if="opened" class="cw-report-dialog-body">
        <div class="cw-report-dialog-top"><span class="cw-help">Saved report · {{ guideFor(opened.result.track).name }}</span><button type="button" class="cw-button ghost" aria-label="Close report" autofocus @click="close"><AppIcon name="x" :size="20"/></button></div>
        <p v-if="opened.note" class="cw-help"><strong>Your note:</strong> {{ opened.note }}</p>
        <CancerResultCard :result="opened.result" :image-src="opened.thumbnail_data_url" :created-at="opened.created_at" uid="cw-saved" mode="saved" :exporting="exporting" @pdf="exportPdf" @remove="remove(opened.id)" @guide="guide"/>
      </div>
    </dialog>
  </section>
</template>
