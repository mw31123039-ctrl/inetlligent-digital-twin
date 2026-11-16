# Clinical AI v2 — capability report (2026-11-17)

Status labels: **Working** (implemented and tested in software) · **Boundary** (integration point built; a named dependency is missing) · **Not built** (next increments).
"Working" never means clinically validated. No clinician, ophthalmologist, dentist, orthodontist or native-speaker medical reviewer has reviewed any rule, translation or output.

## What the assistant does

| Capability | Status | Evidence |
| --- | --- | --- |
| Anatomy-aware interview: region → structure → patient side, FDI tooth selection, 63 shared eye-structure IDs | Working | `contracts/clinical/anatomy.v1.json`; laterality cases 4/4 |
| Structured symptom capture: presence/absence, onset, duration, severity, pattern, course, character, triggers, laterality, past vs current | Working | Extraction tests in en/ar/ckb |
| Adaptive questioning: safety screen first, then expected-information-gain questions, each with a stated purpose; no repeats; capped length | Working | 0 repeated questions in 102 conversations; 100% of questions carry a purpose |
| Contradiction and laterality conflict detection with clarification questions; in-place corrections that recompute everything | Working | Special cases 2/2 and 4/4; Laravel correction test |
| Red-flag escalation with priority over the interview; corrections cannot silently downgrade | Working (draft rules) | 63 rules bound to NHS care-advice sentences; see evaluation |
| Possible explanations with supporting / conflicting / missing evidence, verbatim citations, abstention | Working | 47 conditions, 64 approved sources (644 stored sections), every feature bound to a stored sentence |
| Retrieval (BM25 × anatomy × source tier × freshness), language-independent queries | Working | Related reading on allowlisted hosts only |
| Validated response schema with versions (engine, anatomy, symptoms, knowledge, sources, snapshot, model, prompt) | Working | Pydantic + JSON Schema enforced again by Laravel |
| Streaming progress (real stages), validated envelope only | Working | Laravel NDJSON test; live browser run |
| English, Arabic, Sorani with RTL | Working (draft translations) | Multilingual agreement 30/30 on dev set |
| 3D markers from stable IDs, selectable, labelled as illustrative | Working | Live screenshots; anchor convention unit test |
| What-changed comparison (within session and between saved assessments) | Working | `diff.ts` unit tests |
| Clinician summary separating patient reports, records, interpretations, urgency rule IDs, missing data | Working | English by design; patient words quoted verbatim |
| Consented save, timeline, owner-only access, encryption at rest, audit log, deletion | Working | `ClinicalSessionsTest` |
| Patient memory: consent with retention, inspect, add, correct (supersede, history kept), delete, export, revoke-and-delete-all; used in an assessment only when opted in | Working | `PatientMemoryTest` |
| Report extraction with page/line/character location; injection lines flagged and excluded; nothing enters the record without confirmation | Working for UTF-8 text | 5/5 report cases |
| PDF reports | Boundary | Needs optional `pypdf` on the AI service (text-layer only); scanned PDFs need OCR, not installed |
| Expert review queue: provenance, versions, two-reviewer rule, patient-controlled de-identified sharing | Working | `ClinicalReviewTest` |
| Optional language-model extraction (closed vocabulary, verbatim-quote checked) | Boundary | No credentials; not evaluated |
| Image router for the clinical assistant, follow-up photo comparability checks | Not built | Existing cancer/dental pipelines remain separate |
| Generic training registry (dataset cards, patient-level splits, promotion review, rollback) for new tasks | Not built | Existing cancer release gate (`app/cancer_release.py`) and dental patient-partition checks remain the only training governance |

## Measured results (synthetic, see `research/clinical-eval/REPORT.md`)

Held-out set (24 profiles written after tuning, run once): urgent cases reached ≥ same-day 11/11; emergency 2/3 before a safety fix and 3/3 after it; no over-escalation 0/13; the authored intended condition ranked first 8/12 (the four misses abstained); 125/125 citations verbatim. The existing v1 pipeline on the same profiles: urgent 5/11, emergency 0/3, explanations 0/24.

Development set (48 profiles, 78 conversations including translations; used for tuning, so optimistic): all urgency, citation, multilingual, laterality, contradiction, injection and memory checks pass after fixes; the first run had 30 failures, documented in the report with root causes.

Engine latency 19 ms median / 37 ms p95 per turn on this workstation; no external requests; inference cost $0.

These are software-behaviour results on developer-written cases, not accuracy or safety in patients.

## Known limitations

- **Vocabulary.** Recognition uses a fixed en/ar/ckb lexicon. Paraphrases, dialect forms, typing errors and suffix forms are missed (four held-out examples in the report). Missed symptoms lead to abstention, not invention, but they can also delay an urgent rule until the safety screen.
- **Knowledge.** 47 conditions from 64 NHS/NEI/NIDCR pages (UK-oriented wording, including UK service names in quotes). Children, pregnancy, mental health and many common problems are not covered (listed in `knowledge.v1.json → coverage_gaps` and the Coverage tab). Weights are author judgement, not calibrated likelihoods.
- **Rules.** Red flags are drafts derived from public care-advice pages; they over- and under-call in ways not yet measured on real data. Emergency numbers are generic ("your local emergency number").
- **Translations.** Arabic (MSA/Iraqi mix) and Sorani strings are the developer's drafts; medical terminology needs native clinical review.
- **Images and documents.** No new image model. Document extraction is pattern-based and English-label oriented.
- **Infrastructure.** Production still needs HTTPS, secure cookies, private networking for the AI service, secret rotation, encrypted backups, log/APM redaction review, MFA and a reviewed retention policy (see `CLINICAL_REVIEW.md`).

## Inspection findings that shaped v2 (2026-11-16)

The existing general symptom path was region-level only, asked a fixed question sequence, used English-only regex triage, and fetched evidence only when an external model key was configured — none is, so every v1 turn ended in "unavailable" with no evidence. Eye, dental and cancer modules were rich but disconnected from a shared anatomy model. v2 keeps v1 and all modules working and adds the shared contracts, local reasoning engine, memory, review and evaluation described above.
