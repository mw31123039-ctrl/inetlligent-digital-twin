import type { Assessment, DemoSettings } from '../types'
import { regions } from '../data/regions'

const key = 'humantwin.assessments.v1'
const settingsKey = 'humantwin.settings.v1'
export const defaultSettings: DemoSettings = { rememberHistory: true, reducedMotion: false, failNextResponse: false }
function validAssessment(value: unknown): value is Assessment {
  if (!value || typeof value !== 'object') return false
  const a = value as Assessment
  return typeof a.id === 'string' && regions.some(r => r.id === a.region) && Number.isFinite(Date.parse(a.createdAt)) && Number.isFinite(a.pain) && a.pain >= 1 && a.pain <= 10 && !!a.answers && ['symptom', 'location', 'onset', 'character'].every(k => typeof a.answers[k as keyof typeof a.answers] === 'string') && Array.isArray(a.messages) && a.messages.every(m => m && typeof m.id === 'string' && ['user', 'assistant'].includes(m.role) && typeof m.text === 'string')
}
export const assessmentRepository = {
  list(): Assessment[] {
    const raw = localStorage.getItem(key)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed) || !parsed.every(validAssessment)) throw new Error('Saved demo data could not be read. Clear local history in Settings to reset it.')
    return parsed
  },
  save(assessment: Assessment): Assessment[] {
    const items = [assessment, ...this.list().filter(a => a.id !== assessment.id)].slice(0, 50)
    localStorage.setItem(key, JSON.stringify(items))
    return items
  },
  remove(id: string): Assessment[] {
    const items = this.list().filter(a => a.id !== id)
    localStorage.setItem(key, JSON.stringify(items))
    return items
  },
  clear() { localStorage.removeItem(key) },
  loadSettings(): DemoSettings {
    try {
      const value = JSON.parse(localStorage.getItem(settingsKey) ?? '{}')
      return { rememberHistory: typeof value.rememberHistory === 'boolean' ? value.rememberHistory : true, reducedMotion: value.reducedMotion === true, failNextResponse: false }
    } catch { return { ...defaultSettings } }
  },
  saveSettings(settings: DemoSettings) { localStorage.setItem(settingsKey, JSON.stringify({ ...settings, failNextResponse: false })) },
}
