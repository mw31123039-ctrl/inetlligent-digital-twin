# Clinical assistant (v2) — architecture, setup and operations

Open **Clinical assistant** in the sidebar, or `http://127.0.0.1:5173/#assistant`. The complete path is:
select anatomy → adaptive, streamed interview → red-flag screening → evidence from approved sources → structured assessment → 3D markers update → consented save → timeline, comparison and clinician summary.

Draft decision support for development with synthetic inputs. Not clinically validated, not a diagnosis. See [CAPABILITY_REPORT.md](CAPABILITY_REPORT.md) before using it with anyone.

## Architecture

```text
Vue  src/clinical/*        anatomy navigator + 3D twin markers · interview (NDJSON stream) · evidence cards · what-changed · timeline · memory
  │  /api (Sanctum session, CSRF)
Laravel  Clinical*Controller, PatientMemoryController
  │  encrypted owner-bound session token (drafts never stored) · consent gates · JSON-Schema validation · source-host allowlist · audit log
  │  X-Service-Key, private network
FastAPI  app/clinical/
     extract.py    en / ar / ckb lexicon → facts with verbatim spans, negation, past-tense, durations, severity, laterality
     engine.py     provenance-aware case → contradictions → red flags (priority) → source-bound condition scoring
                   → information-gain question selection → composed, versioned assessment (schemas.py)
     retrieval.py  BM25 × anatomical relevance × source tier × freshness over the approved snapshot
     documents.py  report text → items with page/line/character location, injection screening, pending confirmation
     language_model.py  optional closed-vocabulary extractor (disabled; never sets urgency or explanations)
contracts/clinical/  anatomy.v1 · symptoms.v1 · knowledge.v1 · sources.v1 · assessment.v2.schema · report-extraction.v1.schema
ai-service/knowledge/clinical-snapshot.json   versioned, hashed text of the approved sources
```

Design rules that the tests enforce:

- **Every claim is bound to a verbatim sentence.** Each condition feature, "argues against" feature and red-flag rule names a source and a pattern that must match a stored sentence (`tests/test_clinical.py::test_every_feature_and_red_flag_is_bound...`). A changed source page breaks the binding and forces review instead of drifting silently.
- **Urgent guidance has priority.** Emergency rules stop the interview; same-day guidance still offers the one-tap safety screen (so an emergency sign cannot be hidden), then stops. Corrections cannot silently downgrade earlier urgent guidance.
- **Provenance is explicit.** Facts are `patient_statement` (free text), `patient_answer` (button), `patient_memory`, `document_extract` (confirmed only) or `clinician_confirmed`; interpretations are separate and never stored as facts.
- **No probabilities.** Condition weights only order questions and explanations. "Fits / partly fits" plus supporting, conflicting and missing evidence is shown instead.
- **Untrusted text stays data.** Patient text, documents and source pages are never instructions; instruction-like lines are flagged and excluded from extraction.
- **Stable anatomy IDs.** `contracts/clinical/anatomy.v1.json` (104 nodes: regions, structures, the 63-structure eye module's IDs, FDI teeth `tooth.fdi.11`–`48`). Side is always the patient's side; 3D anchors are illustrative markers on the reference body, labelled as such.

## Setup

Existing setup applies (`powershell -File scripts/setup.ps1`, then the three services). Additional steps:

```powershell
cd backend
php artisan migrate                      # adds clinical_* , patient_*, audit_events, review_items, users.role
```

Run the services (three terminals, from the project root):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-ai-service.ps1     # Python, 127.0.0.1:8001
cd backend;  php artisan serve --host=127.0.0.1 --port=8000 --no-reload
cd frontend; npm run dev                                                    # http://127.0.0.1:5173/#assistant
```

Configuration (all server-side; nothing goes in `VITE_*`):

| Where | Variable | Default | Purpose |
| --- | --- | --- | --- |
| backend `.env` | `CLINICAL_MAX_QUESTIONS` | 12 | Interview length cap |
| ai-service `.env` | `CLINICAL_LM_PROVIDER`, `CLINICAL_LM_MODEL` | disabled | Optional closed-vocabulary symptom extraction; also needs `OPENAI_API_KEY` and `ALLOW_EXTERNAL_AI=true`. Model choice is configuration only. Verify current provider documentation and data-processing terms before enabling; this path has **not** been run with real credentials. |

Run the scheduler (`php artisan schedule:run` every minute, or `schedule:work`) so `clinical:prune` removes expired drafts and memory items past their retention period.

## Operations

**Assign a clinical reviewer** (server-side only; the role is not mass-assignable):

```powershell
php artisan humantwin:reviewer reviewer@example.org            # --revoke to remove
```

Verify the person's professional registration separately. Reviewers propose corrections (findings, citations, anatomy mappings, question selection, red flags, translations) in a queue with provenance; a *different* reviewer accepts or rejects. Accepted items are applied by a maintainer to the generator scripts below — nothing changes model weights automatically. Reviewers only see assessments a patient explicitly shared, in de-identified form (no free text, quotes, account details).

**Update knowledge (no model weights involved):**

```powershell
cd ai-service
python scripts/ingest-clinical-knowledge.py                # fetch approved pages, chunk, hash, dedupe, version, retire changed sections
python scripts/ingest-clinical-knowledge.py --check        # integrity check only
python scripts/build-clinical-knowledge.py                 # regenerate symptoms.v1.json + knowledge.v1.json from the editable source
python scripts/build-clinical-anatomy.py                   # regenerate anatomy.v1.json
python scripts/export-schema.py                            # re-export JSON Schemas
python -m pytest tests/test_clinical.py                    # fails if any evidence binding broke
```

To add a source: add it to `contracts/clinical/sources.v1.json` (allowlisted host, publisher with usage rights), ingest, then bind features to its sentences in `build-clinical-knowledge.py`. Sources past their publisher's review date stay retrievable, are ranked lower and are marked "review overdue".

## API (Laravel, `/api`)

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/clinical/status`, `/clinical/catalog`, `/clinical/coverage` | Public metadata, no patient data |
| POST | `/clinical/sessions` | `{anatomy_id, side, locale, processing_acknowledged, use_memory?}` |
| POST | `/clinical/sessions/{id}/turns` | `{token, text, answer_codes?, correct_message_id?, locale?}`; send `Accept: application/x-ndjson` for streamed stages |
| POST | `/clinical/sessions/{id}/save` | consent `clinical-storage-v1`; assessment recomputed server-side |
| GET/DELETE | `/clinical/assessments[/{id}]` | owner-only; `POST/DELETE …/review-share` (consent `clinical-review-share-v1`) |
| GET/POST/PATCH/DELETE | `/clinical/memory…` | consent (`patient-memory-v1`, retention 30/90/365/730 days), facts, corrections (supersede), confirm extracts, export, revoke-and-delete |
| POST | `/clinical/documents` | `.txt` (UTF-8) or `.pdf` ≤ 5 MB; file not retained |
| GET/POST | `/clinical/review/items`, `/clinical/review/cases`, `…/items/{id}/decision` | reviewer role only |

## Tests

```powershell
cd ai-service; python -m pytest -q                      # 169 tests (33 clinical)
cd backend;    php artisan test --compact               # 105 tests (15 clinical)
cd frontend;   npm test; npm run build                  # 69 unit tests (8 clinical)
cd frontend;   npm run test:clinical:browser            # live end-to-end; needs all three services
cd ai-service; python scripts/evaluate-clinical.py      # synthetic evaluation → research/clinical-eval/
```

On this workstation the copied venv `python.exe` is blocked by Application Control; use the uv-managed interpreter with `PYTHONPATH=.venv/Lib/site-packages;.` (as `scripts/start-ai-service.ps1` does).
