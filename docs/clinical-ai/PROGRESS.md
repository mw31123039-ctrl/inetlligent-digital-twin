# Clinical AI v2 — progress tracker

This file is the hand-off point between sessions. Update it whenever an increment lands.
Status keys: `done` · `partial` · `boundary` (integration point built, dependency missing) · `todo`.

## Findings from the 2026-11-16 inspection (before v2)

| Area | State before v2 |
| --- | --- |
| Stack | Laravel 13 (PHP 8.5, SQLite, Sanctum cookie auth), Vue 3 + TypeScript + Tailwind 4 + plain Three.js (no TresJS), FastAPI private service (Python 3.12, uv). |
| General symptom AI (`/v1/assess`) | Six coarse regions + side. Fixed question order. English-only regex triage. NHS pages fetched live only when an external LLM key is configured; none is, so every turn ended `phase: unavailable` with no evidence. No patient memory, structured attributes, streaming or i18n. Kept unchanged. |
| Eye / dental / cancer | Rich, separately built modules (63-structure eye atlas, FDI dental tooling and local detector, four local cancer classifiers with release gate). Not connected to a shared anatomy model. Kept unchanged. |

## v2 increments

| # | Increment | Status | Where |
| --- | --- | --- | --- |
| 1 | Anatomy ontology (104 nodes, stable IDs, laterality, related structures, 3D anchors, en/ar/ckb) | done | `contracts/clinical/anatomy.v1.json` ← `ai-service/scripts/build-clinical-anatomy.py` |
| 2 | Symptom/attribute lexicon (95 concepts, negation, durations, severity, triggers) | done | `contracts/clinical/symptoms.v1.json` ← `build-clinical-knowledge.py` |
| 3 | Knowledge base: 47 conditions, 63 red flags, care pathways, screens, imaging scope, coverage gaps | done | `contracts/clinical/knowledge.v1.json` |
| 4 | Source registry + ingestion (fetch, chunk, hash, dedupe, version, retire) — 64 sources, 644 sections | done | `contracts/clinical/sources.v1.json`, `scripts/ingest-clinical-knowledge.py`, `ai-service/knowledge/` |
| 5 | Reasoning engine (provenance, contradictions, red-flag priority, information-gain questions, evidence for/against/missing, abstention) | done | `ai-service/app/clinical/engine.py` |
| 6 | Retrieval (BM25 × anatomy × tier × freshness) and verbatim citations | done | `app/clinical/retrieval.py` |
| 7 | Validated response schema v2, enforced by Laravel | done | `contracts/clinical/assessment.v2.schema.json` |
| 8 | Laravel API: encrypted sessions, in-place corrections, NDJSON streaming, consented server-recomputed save | done | `ClinicalSessionController` |
| 9 | Patient memory + audit log + retention pruning | done | `PatientMemoryController`, `AuditLog`, `clinical:prune` |
| 10 | Expert review queue (two reviewers, provenance, patient-shared de-identified cases) | done | `ClinicalReviewController`, `humantwin:reviewer` |
| 11 | Report extraction with location, injection screening, confirmation gate | partial | text done; PDF needs optional `pypdf`; no OCR |
| 12 | Vue workspace (navigator, 3D markers, streamed interview, evidence cards, what-changed, timeline, memory, clinician summary, RTL) | done | `frontend/src/clinical/` |
| 13 | Synthetic evaluation vs v1 (dev + held-out), report | done | `research/clinical-eval/` |
| 14 | Image router (quality → suitability → supported model or explicit "unsupported") and follow-up photo comparability (lighting/angle/scale) | todo | reuse `cancer_quality.py`; show `imaging_scope` from knowledge |
| 15 | Generic training registry (dataset cards, patient-level splits, model/prompt versions, review-before-promote, rollback) | todo | generalise `cancer_release.py` |
| 16 | Optional LLM extraction adapter | boundary | `app/clinical/language_model.py`; needs credentials + evaluation |
| 17 | Close held-out vocabulary gaps (see report) and grow held-out set; native-speaker review of ar/ckb | todo | `build-clinical-knowledge.py` |

## Gates to keep green

`python -m pytest -q` (169) · `php artisan test --compact` (105) · `npm test` (69) + `npm run build` · `npm run test:clinical:browser` (live) · `python scripts/evaluate-clinical.py` (dev + `--cases …heldout.v1.json --label heldout`).

Do not tune on `heldout.v1.json`; write a new held-out set after each tuning round and keep the first-run results file.
