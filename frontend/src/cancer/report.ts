import { cancerTopics } from './knowledge'
import { modalities, pathways } from './model'
import type { CancerResult, CancerTrack, Heatmap, OutcomeReason } from './model'

/** Plain-language meaning of every class the installed models can return. Educational, not diagnostic. */
export interface ClassMeaning { name: string; kind: 'cancer' | 'precancer' | 'benign' | 'no-finding'; meaning: string }
export const classMeanings: Record<string, ClassMeaning> = {
  melanocytic_nevi: { name: 'Common mole (melanocytic nevus)', kind: 'benign', meaning: 'Most moles are harmless. A mole that is new, changing in size, shape or colour, bleeding or itching should still be checked by a clinician.' },
  melanoma: { name: 'Melanoma pattern', kind: 'cancer', meaning: 'Melanoma is a skin cancer that starts in pigment cells. This image shares features with melanomas the model learned from. Only an examination, and a biopsy if needed, can confirm or rule it out.' },
  basal_cell_carcinoma: { name: 'Basal cell carcinoma pattern', kind: 'cancer', meaning: 'Basal cell carcinoma is the most common skin cancer. It usually grows slowly and rarely spreads, but it should be examined and treated.' },
  actinic_keratoses: { name: 'Actinic keratosis / early squamous cell pattern', kind: 'precancer', meaning: 'Rough, sun-damaged patches that can occasionally turn into squamous cell skin cancer. This category also includes early (in situ) squamous cell carcinoma.' },
  benign_keratosis_like_lesions: { name: 'Benign keratosis-like lesion', kind: 'benign', meaning: 'Includes seborrhoeic keratoses (“stuck-on” spots), sun spots (solar lentigines) and similar harmless growths. Some melanomas can look similar, so changes still need checking.' },
  dermatofibroma: { name: 'Dermatofibroma pattern', kind: 'benign', meaning: 'A common, harmless firm bump in the skin, often on the legs.' },
  vascular_lesions: { name: 'Vascular lesion pattern', kind: 'benign', meaning: 'A spot made of small blood vessels, such as a cherry angioma. These are usually harmless.' },
  benign_lesion: { name: 'Benign-appearing mouth lesion', kind: 'benign', meaning: 'In the photographs the model learned from, this category held mouth lesions that were not cancer. An ulcer, lump, or red or white patch lasting more than three weeks still needs to be examined.' },
  malignant_lesion: { name: 'Possible malignant mouth lesion', kind: 'cancer', meaning: 'In the photographs the model learned from, this category held lesions diagnosed as oral cancer. A dentist or doctor needs to examine the mouth; a biopsy is the only way to confirm it.' },
  normal: { name: 'No tumour pattern recognised', kind: 'no-finding', meaning: 'The model did not recognise a tumour pattern in this single image. One image cannot rule out cancer; symptoms or changes still need a clinician.' },
  adenocarcinoma: { name: 'Adenocarcinoma pattern', kind: 'cancer', meaning: 'Adenocarcinoma is the most common type of non-small cell lung cancer. A single CT slice cannot establish it; full imaging and usually a biopsy are needed.' },
  large_cell_carcinoma: { name: 'Large cell carcinoma pattern', kind: 'cancer', meaning: 'Large cell carcinoma is a less common type of non-small cell lung cancer. A single CT slice cannot establish it; full imaging and usually a biopsy are needed.' },
  squamous_cell_carcinoma: { name: 'Squamous cell carcinoma pattern', kind: 'cancer', meaning: 'Squamous cell carcinoma is a type of non-small cell lung cancer that often starts in the central airways. A single CT slice cannot establish it; full imaging and usually a biopsy are needed.' },
  benign: { name: 'Benign-appearing breast finding', kind: 'benign', meaning: 'In the ultrasound images the model learned from, this category held non-cancerous findings such as cysts or fibroadenomas. A breast change still needs a clinical assessment.' },
  malignant: { name: 'Possible malignant breast finding', kind: 'cancer', meaning: 'In the ultrasound images the model learned from, this category held cancers. A breast clinic decides on further imaging and a needle biopsy.' },
}
export const labelKey = (label: string) => label.toLowerCase().replace(/[.\s-]/g, '_')
export function classMeaning(label: string, track?: CancerTrack): ClassMeaning {
  const key = labelKey(label)
  if (key === 'normal' && track === 'breast') return { name: 'No mass pattern recognised', kind: 'no-finding', meaning: 'The model did not recognise a mass in this single ultrasound image. One image cannot rule out a breast problem; a new lump or change still needs a clinician.' }
  return classMeanings[key] ?? { name: label.replace(/[_.]/g, ' '), kind: 'benign', meaning: 'This is one of the categories the model was trained on.' }
}

export const specialists: Record<CancerTrack, { who: string; short: string }> = {
  skin: { who: 'your GP or a dermatologist (skin specialist)', short: 'Discuss with a dermatologist' },
  oral: { who: 'your dentist or doctor, who can refer you to an oral and maxillofacial specialist', short: 'Discuss with a dentist or doctor' },
  lung: { who: 'your GP or a respiratory (lung) specialist, together with the radiology report of the full scan', short: 'Discuss with a lung specialist' },
  breast: { who: 'your GP or a breast clinic', short: 'Discuss with a breast clinic' },
}

export function guideFor(track: CancerTrack) {
  return cancerTopics.find(topic => topic.modelTrack === track) ?? cancerTopics.find(topic => topic.id === track)!
}

export const reasonText: Record<OutcomeReason, string> = {
  'input-rejected': 'The image does not match the selected area, so the model was not run.',
  'input-quality': 'The image quality limits what the model can see (see the image checks).',
  'low-confidence': 'The model did not reach its minimum confidence for a clear answer.',
  'unfamiliar-image': 'The image looks unlike the images this model was evaluated on.',
}

export interface ReportSummary {
  tone: 'attention' | 'reassuring' | 'neutral' | 'blocked'
  badge: string
  headline: string
  meaning: string
  nextStep: string
}

/** The plain-language reading of a result: what was found, what it means and what to do next. */
export function summarize(result: CancerResult): ReportSummary {
  const area = pathways.find(item => item.id === result.track)!
  const specialist = specialists[result.track]
  if (result.outcome === 'input-rejected') {
    const accepts = modalities[result.modality].accepts
    return { tone: 'blocked', badge: 'Image not accepted', headline: 'This image does not fit the ' + area.label.toLowerCase() + ' model',
      meaning: (result.image_checks.findings.find(item => item.severity === 'reject')?.message ?? 'The image did not pass the input checks.') + ' No model result was produced.',
      nextStep: `Choose a matching image — ${accepts.charAt(0).toLowerCase() + accepts.slice(1)} — or select the body area that fits your image, then analyse again.` }
  }
  const top = result.confidence!.top_label
  const meaning = classMeaning(top, result.track)
  if (result.outcome === 'inconclusive') {
    return { tone: 'neutral', badge: 'Inconclusive', headline: 'No reliable answer from this image',
      meaning: `The model could not give a reliable answer for this image. Its closest category was “${meaning.name}”, but that should not be read as a finding.`,
      nextStep: `Try a sharper, well-lit image that shows only the area of concern. If you are worried about a change, ${specialist.short.toLowerCase().replace('discuss with', 'see')} rather than relying on this tool.` }
  }
  const attention = meaning.kind === 'cancer' || meaning.kind === 'precancer'
  return {
    tone: attention ? 'attention' : 'reassuring', badge: attention ? 'Needs a clinician’s review' : 'Model finding', headline: meaning.name, meaning: meaning.meaning,
    nextStep: attention
      ? `Book an appointment with ${specialist.who} soon and bring this report. The model cannot confirm cancer; an examination and possibly a biopsy can.`
      : `No cancer pattern was the top match, but this cannot rule cancer out. If the area is new, changing, bleeding or painful, see ${specialist.who}.`,
  }
}

export const confidenceText = (result: CancerResult) => {
  const confidence = result.confidence
  if (!confidence) return ''
  const level = { high: 'High', moderate: 'Moderate', low: 'Low' }[confidence.level]
  return `${level} model confidence (${Math.round(confidence.probability * 100)}%)` + (confidence.calibration === 'temperature-scaled' ? ', calibrated on held-out images.' : ', not calibrated.')
}

export function heatmapCaption(heatmap: Heatmap, track: CancerTrack) {
  const name = classMeaning(heatmap.target_label, track).name
  if (heatmap.method === 'grad-cam') return `Grad-CAM: warmer areas raised the model’s score for “${name}”.`
  if (heatmap.method === 'attention-rollout') return 'Attention rollout: warmer areas are where the model looked most. It is not specific to one category.'
  return `Occlusion: warmer areas lowered the score for “${name}” most when hidden.`
}

// ------------------------------------------------------------------- heatmap rendering

/** Bilinear sample of a row-major grid at fractional coordinates (cell centres at integer + .5). */
export function sampleGrid(values: number[], width: number, height: number, x: number, y: number) {
  const gx = Math.min(Math.max(x * width - .5, 0), width - 1), gy = Math.min(Math.max(y * height - .5, 0), height - 1)
  const x0 = Math.floor(gx), y0 = Math.floor(gy), x1 = Math.min(x0 + 1, width - 1), y1 = Math.min(y0 + 1, height - 1)
  const fx = gx - x0, fy = gy - y0
  const at = (column: number, row: number) => values[row * width + column]!
  return (at(x0, y0) * (1 - fx) + at(x1, y0) * fx) * (1 - fy) + (at(x0, y1) * (1 - fx) + at(x1, y1) * fx) * fy
}

/** Warm colour ramp with transparency for low values, so the image stays visible underneath. */
export function heatColor(value: number): [number, number, number, number] {
  const v = Math.min(Math.max(value, 0), 1)
  const stops: [number, [number, number, number]][] = [[0, [255, 241, 168]], [.5, [247, 147, 30]], [1, [196, 30, 58]]]
  const upper = stops.findIndex(([position]) => position >= v)
  const [p0, c0] = stops[Math.max(upper - 1, 0)]!, [p1, c1] = stops[Math.max(upper, 0)]!
  const t = p1 === p0 ? 0 : (v - p0) / (p1 - p0)
  const alpha = v < .12 ? 0 : Math.pow((v - .12) / .88, .75)
  return [Math.round(c0[0] + (c1[0] - c0[0]) * t), Math.round(c0[1] + (c1[1] - c0[1]) * t), Math.round(c0[2] + (c1[2] - c0[2]) * t), alpha]
}

export function paintHeatmap(canvas: HTMLCanvasElement, heatmap: Heatmap, opacity = .7) {
  const context = canvas.getContext('2d')
  if (!context) return
  const { width, height } = canvas
  const pixels = context.createImageData(width, height)
  for (let row = 0; row < height; row++) {
    for (let column = 0; column < width; column++) {
      const [r, g, b, a] = heatColor(sampleGrid(heatmap.values, heatmap.grid_width, heatmap.grid_height, (column + .5) / width, (row + .5) / height))
      const index = (row * width + column) * 4
      pixels.data[index] = r; pixels.data[index + 1] = g; pixels.data[index + 2] = b; pixels.data[index + 3] = Math.round(a * opacity * 255)
    }
  }
  context.putImageData(pixels, 0, 0)
}

/** Image with the heatmap composited on top, as a JPEG data URL (used by the PDF report). */
export async function compositeImage(dataUrl: string, heatmap: Heatmap | null, longest = 640): Promise<string> {
  const image = new Image()
  image.src = dataUrl
  await image.decode()
  const factor = Math.min(1, longest / Math.max(image.naturalWidth, image.naturalHeight))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(image.naturalWidth * factor); canvas.height = Math.round(image.naturalHeight * factor)
  const context = canvas.getContext('2d')!
  context.drawImage(image, 0, 0, canvas.width, canvas.height)
  if (heatmap) {
    const overlay = document.createElement('canvas')
    overlay.width = Math.max(1, Math.round(canvas.width / 4)); overlay.height = Math.max(1, Math.round(canvas.height / 4))
    paintHeatmap(overlay, heatmap)
    context.imageSmoothingQuality = 'high'
    context.drawImage(overlay, 0, 0, canvas.width, canvas.height)
  }
  return canvas.toDataURL('image/jpeg', .9)
}

// ------------------------------------------------------------------- printable report (PDF)

const escapeHtml = (value: unknown) => String(value ?? '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]!)

export interface PrintableReport { result: CancerResult; imageDataUrl: string | null; heatmapDataUrl: string | null; createdAt: string; note?: string | null }

export function reportHtml({ result, imageDataUrl, heatmapDataUrl, createdAt, note }: PrintableReport): string {
  const summary = summarize(result)
  const area = pathways.find(item => item.id === result.track)!
  const guide = guideFor(result.track)
  const ranked = [...result.scores].sort((a, b) => b.value - a.value)
  const confidence = result.confidence
  const date = new Intl.DateTimeFormat('en', { dateStyle: 'long', timeStyle: 'short' }).format(new Date(createdAt))
  const checks = result.image_checks.findings.filter(item => item.severity !== 'info')
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>HumanTwin research report – ${escapeHtml(area.label)}</title><style>
  @page{size:A4;margin:16mm}*{box-sizing:border-box}body{font-family:"Segoe UI",Arial,sans-serif;color:#17312f;font-size:11pt;line-height:1.5;margin:0}
  h1{font-size:20pt;margin:0 0 4pt}h2{font-size:12.5pt;margin:16pt 0 6pt;color:#1f5f4c}p{margin:0 0 6pt}.muted{color:#4a5f58}
  .notice{border:1.5pt solid #b4572f;background:#fff4ec;color:#7a3416;padding:8pt 10pt;border-radius:8pt;font-weight:600;margin:10pt 0}
  .header{display:flex;justify-content:space-between;gap:12pt;border-bottom:1pt solid #cfdcd5;padding-bottom:8pt}.badge{display:inline-block;padding:2pt 8pt;border-radius:8pt;background:#e3efe7;font-weight:600}
  .grid{display:flex;gap:14pt;margin-top:10pt}.grid figure{margin:0;flex:1}.grid img{width:100%;border-radius:8pt;border:1pt solid #cfdcd5}figcaption{font-size:9pt;color:#4a5f58;margin-top:3pt}
  .bar{height:9pt;background:#e5ece8;border-radius:8pt;position:relative;margin:4pt 0}.bar i{position:absolute;left:0;top:0;bottom:0;background:#287b62;border-radius:8pt}
  table{border-collapse:collapse;width:100%;font-size:10pt}td,th{border-bottom:.6pt solid #d8e2dc;padding:3pt 4pt;text-align:left}footer{margin-top:16pt;font-size:8.5pt;color:#4a5f58;border-top:1pt solid #cfdcd5;padding-top:6pt}
  </style></head><body>
  <div class="header"><div><p class="muted">HumanTwin · Cancer research module</p><h1>${escapeHtml(summary.headline)}</h1><span class="badge">${escapeHtml(summary.badge)}</span></div>
  <div class="muted" style="text-align:right">${escapeHtml(date)}<br>Area: ${escapeHtml(area.label)}<br>Input: ${escapeHtml(modalities[result.modality].label)}</div></div>
  <p class="notice">Not a medical diagnosis. This is an experimental research model applied to one image. It cannot confirm or rule out cancer.</p>
  <div class="grid">${imageDataUrl ? `<figure><img src="${imageDataUrl}" alt="Analysed image"><figcaption>Analysed image (prepared copy).</figcaption></figure>` : ''}
  ${heatmapDataUrl && result.heatmap ? `<figure><img src="${heatmapDataUrl}" alt="Heatmap overlay"><figcaption>${escapeHtml(heatmapCaption(result.heatmap, result.track))} Not a tumour boundary.</figcaption></figure>` : ''}</div>
  <h2>What this means</h2><p>${escapeHtml(summary.meaning)}</p>
  ${confidence ? `<h2>Model confidence</h2><p>${escapeHtml(confidenceText(result))} Minimum for a finding: ${Math.round(confidence.decision_threshold * 100)}%.</p><div class="bar"><i style="width:${(confidence.probability * 100).toFixed(1)}%"></i></div><p class="muted">Confidence describes how strongly the model prefers its top category. It is not your personal probability of having cancer.</p>` : ''}
  <h2>Suggested next step</h2><p>${escapeHtml(summary.nextStep)}</p><p class="muted">Learn more: ${escapeHtml(guide.name)} guide (${escapeHtml(guide.source)}).</p>
  ${ranked.length ? `<h2>All categories</h2><table><tr><th>Category</th><th>Score</th></tr>${ranked.map(score => `<tr><td>${escapeHtml(classMeaning(score.label, result.track).name)}</td><td>${(score.value * 100).toFixed(1)}%</td></tr>`).join('')}</table>` : ''}
  ${checks.length ? `<h2>Image checks</h2><ul>${checks.map(item => `<li>${escapeHtml(item.message)}</li>`).join('')}</ul>` : ''}
  ${note ? `<h2>Your note</h2><p>${escapeHtml(note)}</p>` : ''}
  <h2>About the model</h2><p class="muted">${escapeHtml(result.model_version)} · ${escapeHtml(result.target)}. Runtime ${escapeHtml(result.runtime ?? 'not reported')}. ${result.model_info ? 'Licence: ' + escapeHtml(result.model_info.license) + '. Evaluation: ' + escapeHtml(result.model_info.evaluation_reference) : ''}</p>
  <footer>Image fingerprint (SHA-256): ${escapeHtml(result.input_sha256)}<br>Generated by HumanTwin, a university research and education project. Bring this report to a qualified clinician; do not use it to make treatment decisions.</footer>
  </body></html>`
}

/** Open the browser's print dialog for the report (choose “Save as PDF”). Uses a hidden frame, no pop-up. */
export function printReport(html: string) {
  const frame = document.createElement('iframe')
  frame.setAttribute('aria-hidden', 'true')
  frame.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden'
  document.body.appendChild(frame)
  const finish = () => setTimeout(() => frame.remove(), 1000)
  frame.onload = () => {
    const view = frame.contentWindow
    if (!view) { finish(); return }
    view.addEventListener('afterprint', finish)
    view.focus(); view.print()
    setTimeout(finish, 60_000)
  }
  frame.srcdoc = html
}
