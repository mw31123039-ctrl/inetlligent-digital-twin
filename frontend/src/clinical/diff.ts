import type { ClinicalAssessment, Fact, UrgencyLevel } from './types'

export interface FactChange { id: string; label: string; from: string; to: string }
export interface AssessmentDiff {
  facts: { added: Fact[]; removed: Fact[]; changed: FactChange[] }
  urgency: { from: UrgencyLevel; to: UrgencyLevel } | null
  explanations: { added: { id: string; name: string; fit: string }[]; removed: { id: string; name: string }[]; fitChanged: { id: string; name: string; from: string; to: string }[] }
  missing: { resolved: string[]; added: string[] }
  contradictions: { added: string[]; resolved: string[] }
  hasChanges: boolean
}

/** A fact's comparable state: status, value and time context (spans/provenance changes alone are not reported). */
function state(fact: Fact) {
  return `${fact.status}${fact.temporal === 'past' ? ' (past)' : ''}${['attribute', 'history', 'medication', 'allergy'].includes(fact.kind) ? `: ${fact.label}` : ''}`
}

/** What changed between two assessments (consecutive turns or two saved records). Pure and order-sensitive. */
export function diffAssessments(previous: ClinicalAssessment | null, next: ClinicalAssessment): AssessmentDiff {
  const before = new Map((previous?.patient_facts ?? []).filter(f => f.extractor !== 'derived').map(f => [f.id, f]))
  const after = new Map(next.patient_facts.filter(f => f.extractor !== 'derived').map(f => [f.id, f]))
  const added = [...after.values()].filter(f => !before.has(f.id))
  const removed = [...before.values()].filter(f => !after.has(f.id))
  const changed: FactChange[] = []
  for (const [id, fact] of after) {
    const prior = before.get(id)
    if (prior && state(prior) !== state(fact)) changed.push({ id, label: fact.label, from: state(prior), to: state(fact) })
  }
  const urgency = previous && previous.urgency.level !== next.urgency.level ? { from: previous.urgency.level, to: next.urgency.level } : null
  const oldExplanations = new Map((previous?.possible_explanations ?? []).map(e => [e.condition_id, e]))
  const newExplanations = new Map(next.possible_explanations.map(e => [e.condition_id, e]))
  const explanations = {
    added: [...newExplanations.values()].filter(e => !oldExplanations.has(e.condition_id)).map(e => ({ id: e.condition_id, name: e.name, fit: e.fit })),
    removed: [...oldExplanations.values()].filter(e => !newExplanations.has(e.condition_id)).map(e => ({ id: e.condition_id, name: e.name })),
    fitChanged: [...newExplanations.values()].filter(e => oldExplanations.has(e.condition_id) && oldExplanations.get(e.condition_id)!.fit !== e.fit)
      .map(e => ({ id: e.condition_id, name: e.name, from: oldExplanations.get(e.condition_id)!.fit, to: e.fit })),
  }
  const oldMissing = new Map((previous?.missing_information ?? []).map(m => [m.key, m.label]))
  const newMissing = new Map(next.missing_information.map(m => [m.key, m.label]))
  const missing = {
    resolved: previous ? [...oldMissing].filter(([key]) => !newMissing.has(key)).map(([, label]) => label) : [],
    added: previous ? [...newMissing].filter(([key]) => !oldMissing.has(key)).map(([, label]) => label) : [],
  }
  const openBefore = new Map((previous?.contradictions ?? []).filter(c => !c.resolved).map(c => [c.id, c.description]))
  const openAfter = new Map(next.contradictions.filter(c => !c.resolved).map(c => [c.id, c.description]))
  const contradictions = {
    added: [...openAfter].filter(([id]) => !openBefore.has(id)).map(([, text]) => text),
    resolved: [...openBefore].filter(([id]) => !openAfter.has(id)).map(([, text]) => text),
  }
  const hasChanges = !!(added.length || removed.length || changed.length || urgency || explanations.added.length || explanations.removed.length
    || explanations.fitChanged.length || missing.resolved.length || missing.added.length || contradictions.added.length || contradictions.resolved.length)
  return { facts: { added, removed, changed }, urgency, explanations, missing, contradictions, hasChanges }
}
