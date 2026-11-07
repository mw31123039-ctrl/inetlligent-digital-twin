export type DentalMode = 'pain' | 'braces' | 'research' | 'cases'
export type DentalView = 'front' | 'upper' | 'lower' | 'side' | 'section'
export type Appliance = 'none' | 'metal' | 'ceramic'
export interface DentalScan { id: string; name: string; parts: { name: string; format: 'stl' | 'obj' | 'glb'; bytes: ArrayBuffer }[]; source: string; license: string }
export interface Tooth { fdi: number; jaw: 'upper' | 'lower'; side: 'right' | 'left'; position: number; kind: 'incisor' | 'canine' | 'premolar' | 'molar'; name: string; roots: number; purpose: string }
const names = ['Central incisor', 'Lateral incisor', 'Canine', 'First premolar', 'Second premolar', 'First molar', 'Second molar', 'Third molar']
export const teeth: Tooth[] = [1, 2, 3, 4].flatMap(q => names.map((name, i) => ({
  fdi: q * 10 + i + 1, jaw: q < 3 ? 'upper' : 'lower', side: q === 1 || q === 4 ? 'right' : 'left', position: i + 1,
  kind: i < 2 ? 'incisor' : i === 2 ? 'canine' : i < 5 ? 'premolar' : 'molar', name,
  roots: i < 3 ? 1 : i < 5 ? (q < 3 && i === 3 ? 2 : 1) : q < 3 ? 3 : 2,
  purpose: i < 2 ? 'Cuts food with a broad biting edge.' : i === 2 ? 'A pointed crown helps tear food.' : i < 5 ? 'Two principal cusps help crush food.' : 'A broad chewing surface grinds food.',
} as Tooth)))
export const toothById = (id: number) => teeth.find(t => t.fdi === id)
export const chartRows = [[18,17,16,15,14,13,12,11,21,22,23,24,25,26,27,28], [48,47,46,45,44,43,42,41,31,32,33,34,35,36,37,38]]
export function toothLabel(id: number) { const t = toothById(id); return t ? `FDI ${id} · ${t.jaw} ${t.side} ${t.name.toLowerCase()}` : 'Choose a permanent tooth' }
export const safetySigns = [
  { id: 'airway', label: 'Difficulty breathing, swallowing or speaking', emergency: true, source: 'nhs-abscess' },
  { id: 'eye-neck', label: 'Swelling near the eye or neck, or new vision problems', emergency: true, source: 'nhs-toothache' },
  { id: 'mouth-opening', label: 'A lot of mouth swelling or difficulty opening the mouth', emergency: true, source: 'nhs-abscess' },
  { id: 'bleeding', label: 'Heavy bleeding that will not stop', emergency: true, source: 'aao-emergency' },
  { id: 'trauma', label: 'Major facial injury or a suspected broken jaw', emergency: true, source: 'aao-emergency' },
  { id: 'knocked-out', label: 'A permanent tooth knocked out or severely displaced', emergency: false, source: 'aao-emergency' },
]
export interface PainRecord { tooth: number; severity: number; duration: 'today' | 'days' | 'weeks'; trigger: string; applianceIssue: string; infectionSigns: boolean; signs: string[]; reviewed: boolean }
export const newPainRecord = (tooth = 11): PainRecord => ({ tooth, severity: 0, duration: 'today', trigger: 'unsure', applianceIssue: 'none', infectionSigns: false, signs: [], reviewed: false })
export interface DentalAdvice { level: 'emergency' | 'urgent' | 'appointment' | 'incomplete'; title: string; detail: string; actions: string[]; sources: string[] }
export function dentalAdvice(record: PainRecord, priorEmergency = false): DentalAdvice {
  if (priorEmergency || safetySigns.some(s => s.emergency && record.signs.includes(s.id))) return { level: 'emergency', title: 'Get emergency care now', detail: priorEmergency ? 'An emergency sign was reported earlier in this assessment. This guidance stays visible after edits.' : 'The sign you selected needs immediate professional assessment.', actions: ['Contact local emergency services or go to an emergency department now.'], sources: ['nhs-toothache', 'nhs-abscess', 'aao-emergency'] }
  if (record.signs.includes('knocked-out')) return { level: 'urgent', title: 'Contact an emergency dentist immediately', detail: 'A knocked-out or severely displaced permanent tooth is time-sensitive.', actions: ['Arrange immediate dental care; do not wait for a routine braces visit.'], sources: ['aao-emergency'] }
  if (!record.reviewed) return { level: 'incomplete', title: 'First, check the safety signs', detail: 'Review the signs below. A tooth selection or pain score cannot rule out an urgent problem.', actions: [], sources: ['nhs-toothache'] }
  if (record.infectionSigns || record.severity >= 7) return { level: 'urgent', title: 'Arrange urgent dental assessment', detail: 'Severe pain, fever, swelling or a bad taste needs a dentist’s assessment. This form cannot identify the cause.', actions: ['Contact a dentist today and describe the symptoms.', 'Choose soft foods and gently clean with a soft toothbrush while arranging care.'], sources: ['nhs-abscess', 'nhs-toothache'] }
  if (record.applianceIssue !== 'none') return { level: 'appointment', title: 'Contact your orthodontic team', detail: 'Tell your orthodontist about the appliance problem and any pain so they can advise when to attend.', actions: ['Orthodontic wax can cover a rubbing bracket or wire while you arrange advice.', 'Keep your prescribed appliance schedule; ask your team before changing it.'], sources: ['nhs-fife', 'aao-emergency'] }
  return { level: 'appointment', title: record.duration === 'today' ? 'Record the symptoms and arrange dental advice' : 'Book a dental appointment', detail: record.duration === 'today' ? 'Watch for changes. A dentist can examine pain or sensitivity; this tool does not diagnose it.' : 'Pain lasting more than two days should be assessed by a dentist.', actions: ['Avoid chewing on the painful tooth and avoid temperature triggers.', 'Ask a pharmacist about pain relief suitable for you.'], sources: ['nhs-toothache'] }
}

export interface Measurement { subject: string; x: number; xLabel: string; metric: string; value: number; unit: string; tooth: number | null; sourceRow: number }
export interface ImportedMeasurements { rows: Measurement[]; subjects: string[]; metrics: string[]; format: 'orthodont-growth' | 'measurements'; }
function csvRows(text: string) {
  if (text.length > 2000000) throw new Error('Measurement files must be smaller than 2 MB.')
  const rows: string[][] = []; let row: string[] = [], value = '', quote = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]!
    if (c === '"') { if (quote && text[i+1] === '"') { value += '"'; i++ } else if (quote || !value.trim()) quote = !quote; else throw new Error('Unexpected quote in CSV.') }
    else if (c === ',' && !quote) { row.push(value.trim()); value = '' }
    else if ((c === '\n' || c === '\r') && !quote) { if (c === '\r' && text[i+1] === '\n') i++; row.push(value.trim()); if (row.some(Boolean)) rows.push(row); row = []; value = '' }
    else value += c
  }
  if (quote) throw new Error('CSV contains an unclosed quoted field.')
  row.push(value.trim()); if (row.some(Boolean)) rows.push(row)
  if (rows.length > 10001) throw new Error('Import up to 10,000 measurements at a time.')
  return rows
}
export function parseMeasurements(text: string, format: 'csv' | 'json'): ImportedMeasurements {
  if (text.length > 2000000) throw new Error('Measurement files must be smaller than 2 MB.')
  let records: Record<string, unknown>[]
  if (format === 'json') {
    const parsed: unknown = JSON.parse(text)
    if (!Array.isArray(parsed) || !parsed.length || parsed.length > 10000 || parsed.some(r => !r || typeof r !== 'object' || Array.isArray(r))) throw new Error('JSON must be an array of 1–10,000 measurement objects.')
    records = parsed
  } else {
    const [header, ...rows] = csvRows(text.replace(/^\uFEFF/, ''))
    if (!header || new Set(header).size !== header.length) throw new Error('CSV needs a header with unique column names.')
    if (rows.some(r => r.length !== header.length)) throw new Error('Each CSV row must have the same number of fields as its header.')
    records = rows.map(r => Object.fromEntries(header.map((h, i) => [h, r[i]])))
  }
  if (!records.length) throw new Error('The file has no measurement rows.')
  const growth = ['distance', 'age', 'Subject'].every(k => k in records[0]!)
  const numeric = (v: unknown, field: string, row: number) => { if (v === '' || v === null || v === undefined || typeof v === 'boolean' || !['string','number'].includes(typeof v) || !Number.isFinite(Number(v))) throw new Error(`Row ${row}: ${field} must be a number.`); return Number(v) }
  const seen = new Set<string>()
  const rows = records.map((r, i): Measurement => {
    const n = i + 2
    const subject = String(growth ? r.Subject ?? '' : r.subject_id ?? '').trim()
    if (!/^[A-Za-z0-9_-]{1,48}$/.test(subject)) throw new Error(`Row ${n}: use a coded subject_id with letters, numbers, _ or - (up to 48 characters).`)
    const metric = growth ? 'craniofacial_distance' : String(r.metric ?? '').trim()
    if (!/^[a-z][a-z0-9_]{0,63}$/.test(metric)) throw new Error(`Row ${n}: metric must be a lowercase identifier.`)
    const value = numeric(growth ? r.distance : r.value, 'value', n)
    if (Math.abs(value) > 10000) throw new Error(`Row ${n}: value is outside the import range.`)
    const unit = growth ? 'mm' : String(r.unit ?? '').trim()
    if (!['mm', 'degrees', 'score', 'hours'].includes(unit)) throw new Error(`Row ${n}: unit must be mm, degrees, score or hours.`)
    let x: number, xLabel: string
    if (growth) { x = numeric(r.age, 'age', n); if (x < 0 || x > 120) throw new Error(`Row ${n}: invalid age.`); xLabel = `Age ${x}` }
    else { const date = String(r.recorded_at ?? ''); if (!/^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?Z)?$/.test(date)) throw new Error(`Row ${n}: recorded_at needs YYYY-MM-DD or a UTC ISO timestamp.`); x = Date.parse(date); if (!Number.isFinite(x) || new Date(x).toISOString().slice(0, 10) !== date.slice(0, 10)) throw new Error(`Row ${n}: invalid date.`); xLabel = date.slice(0, 10) }
    const tooth = !growth && r.tooth_fdi !== '' && r.tooth_fdi != null ? numeric(r.tooth_fdi, 'tooth_fdi', n) : null
    if (tooth !== null && !toothById(tooth)) throw new Error(`Row ${n}: tooth_fdi must identify one of the 32 permanent teeth.`)
    const key = JSON.stringify([subject, x, metric, tooth])
    if (seen.has(key)) throw new Error(`Row ${n}: duplicate subject, time, metric and tooth. Keep corrections explicit.`)
    seen.add(key)
    return { subject, x, xLabel, metric, value, unit, tooth, sourceRow: n }
  })
  for (const m of new Set(rows.map(r => r.metric))) if (new Set(rows.filter(r => r.metric === m).map(r => r.unit)).size !== 1) throw new Error(`Metric ${m} mixes units; convert them before importing.`)
  return { rows, subjects: [...new Set(rows.map(r => r.subject))].sort(), metrics: [...new Set(rows.map(r => r.metric))].sort(), format: growth ? 'orthodont-growth' : 'measurements' }
}
export function measurementSeries(data: ImportedMeasurements | null, subject: string, metric: string, tooth: number | null) {
  return (data?.rows ?? []).filter(r => r.subject === subject && r.metric === metric && r.tooth === tooth).sort((a, b) => a.x - b.x)
}
export function angleDegrees(a: [number,number], b: [number,number], c: [number,number]) {
  const u = [a[0]-b[0],a[1]-b[1]], v = [c[0]-b[0],c[1]-b[1]], length = Math.hypot(...u)*Math.hypot(...v)
  return length < 1e-8 ? null : Math.acos(Math.max(-1,Math.min(1,(u[0]!*v[0]!+u[1]!*v[1]!)/length)))*180/Math.PI
}
export function distanceMm(a: [number,number], b: [number,number], mmPerPixel: number) { return Number.isFinite(mmPerPixel) && mmPerPixel > 0 ? Math.hypot(a[0]-b[0], a[1]-b[1])*mmPerPixel : null }
export const measurementTemplate = 'subject_id,recorded_at,tooth_fdi,metric,value,unit\nDEMO_01,2026-10-01,11,pain,4,score\nDEMO_01,2026-10-15,11,pain,2,score\n'
