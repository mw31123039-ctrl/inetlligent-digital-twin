# Clinical AI v2 — synthetic evaluation report (2026-11-17)

**Read this first.** Every case here is synthetic and was written by the developer who also wrote the knowledge base. These numbers describe **software behaviour on authored scenarios**: safety-rule coverage, extraction robustness, provenance and consistency. They are **not** diagnostic accuracy, sensitivity in real patients, or calibration. No clinician has reviewed the cases, the rules or the outputs. Clinical performance claims require an independent, representative, clinician-labelled evaluation.

Reproduce from `ai-service/`:

```powershell
python scripts/evaluate-clinical.py                                   # development set
python scripts/evaluate-clinical.py --cases ../research/clinical-eval/heldout.v1.json --label heldout
```

Raw outputs (per-case questions, urgency, explanations and every failure) are in the JSON files listed below.

## Method

- **Simulated patient.** Each profile has a free-text complaint (natural wording, not copied from the lexicon) and a ground-truth profile. A scripted patient answers every engine question from that profile; symptoms not listed are answered "no".
- **Development set** (`cases.v1.json`): 48 profiles, 15 of them also in Arabic and Sorani (78 conversations), 10 special cases (laterality, contradictions, incomplete history, prompt injection, patient memory) and 5 reports for document-injection tests.
- **Held-out set** (`heldout.v1.json`): 24 new profiles (16 English, 8 Arabic/Sorani, 1 mixed-language) written *after* the development fixes and run once before any further change.
- **Baseline.** The existing `/v1/assess` pipeline with no external provider — the repository's actual default — given the English complaint and scripted answers to its fixed questions.
- Proportions show successes/n with a descriptive Wilson 95% interval. Small n means wide intervals.

## Results

| Metric | Dev — first run | Dev — after fixes | Held-out — first run | Held-out — after safety fix |
| --- | --- | --- | --- | --- |
| Urgent cases reaching ≥ same-day | 30/30 [0.89–1] | 30/30 [0.89–1] | 11/11 [0.74–1] | 11/11 [0.74–1] |
| Emergency cases reaching emergency | 18/18 [0.82–1] | 18/18 [0.82–1] | **2/3** [0.21–0.94] | 3/3 [0.44–1] |
| Urgency raised from the first message | 23/27 [0.68–0.94] | 27/27 [0.88–1] | — | — |
| Over-escalation of non-urgent cases | 2/42 | 0/42 [0–0.08] | 0/13 [0–0.23] | 0/13 [0–0.23] |
| Authored "intended" condition ranked first | 34/45 | 45/45 | **8/12** [0.39–0.86] | 8/12 |
| Abstains on vague input | 2/2 | 2/2 | — | — |
| Safety screen asked before other questions | 78/78 | 78/78 | 24/24 | 24/24 |
| Questions that state their purpose | 407/407 | 446/446 | 121/121 | 126/126 |
| Repeated questions | 0 | 0 | 0 | 0 |
| Citations whose quote is verbatim in the stored source | 415/415 | 450/450 | 123/123 | 125/125 |
| Supporting statements carrying a citation | 140/140 | 186/186 | 38/38 | 38/38 |
| Citations on allowlisted publisher hosts | 415/415 | 450/450 | 123/123 | 125/125 |
| Patient text containing probabilities/diagnosis claims | 0 | 0 | 0 | 0 |
| "Fits" shown despite strong conflicting evidence | 0 | 0 | 0 | 0 |
| Same urgency across en/ar/ckb | 26/30 | 30/30 | — | — |
| Same top explanation across en/ar/ckb | 25/30 | 30/30 | — | — |
| Same red-flag rules across en/ar/ckb | 26/30 | 30/30 | — | — |
| Report extraction incl. injection lines (5 reports) | 5/5 | 5/5 | — | — |
| Laterality / contradiction / incomplete / injection / memory special cases | — | 4/4, 2/2, 1/1, 2/2, 1/1 | — | — |
| Engine latency per turn (p50 / p95) | 13 / 19 ms | 23 / 35 ms | 16 / 35 ms | 19 / 37 ms |
| External requests / inference cost | 0 / $0 | 0 / $0 | 0 / $0 | 0 / $0 |

Mean interview length (non-urgent): 7.7 → 8.4 questions on the development set (maximum 13 including the opening complaint; the configured cap is 12 follow-ups). Latency is CPU time inside the engine on this workstation; it excludes Laravel and network time.

### Against the v1 baseline (same profiles, English only)

| | v1 (current default) | v2 |
| --- | --- | --- |
| Urgent cases reaching ≥ same-day — dev | 13/16 [0.57–0.93] | 16/16 |
| Emergency cases reaching emergency — dev | 4/10 [0.17–0.69] | 10/10 |
| Urgent — held-out | 5/11 [0.21–0.72] | 11/11 |
| Emergency — held-out | 0/3 | 3/3 (after fix; 2/3 before) |
| Over-escalation — dev / held-out | 0/26, 0/13 | 0/26, 0/13 |
| Cases offering any explanation | 0/48 (no provider configured) | 45/48 dev (3 correctly abstained or withheld) |
| Citations, multilingual input, laterality checks, patient memory | none / English only / region-level / none | verified / en·ar·ckb / structure-level / consented |

v1's misses are mostly paraphrases its English regex does not cover and positive warning answers that it can only escalate to same-day, never emergency.

## What changed between runs (and why the development numbers are optimistic)

The first development run found 30 failures. Each was traced to a root cause and fixed in the engine or lexicon — the development set was therefore used for tuning and its final numbers overstate generalisation. Fixes included: a Sorani negation word matching *inside* another word ("بەیانییەوە" contains the letters of "نییە"), "back tooth" read as the back, "pressure in my chest" not recognised, a deep-vein-thrombosis rule firing on an ankle sprain, eyelid pain treated as eye pain, "burning" in a urinary complaint matched to an eye symptom, Sorani "hand" matched inside "toilet", generic findings (pain, swelling, side) being enough for an urgent condition to "fit", and partial matches setting the care pathway.

The held-out first run exposed a **safety design gap**: once a case reached *same-day* urgency, the interview stopped, so the safety screen that would have revealed an emergency sign (breathlessness with a swollen calf) was never shown. The engine now still offers the one-tap safety screen when urgency is same-day and the screen has not been completed (covered by `test_same_day_guidance_still_offers_the_emergency_screen`). The held-out emergency figure after this fix (3/3) is no longer a clean held-out number for that rule.

## Remaining failures (held-out, unchanged)

All four held-out misses abstained ("no supported explanation") rather than suggesting something wrong — the intended failure mode — but each is a real vocabulary gap:

| Case | Cause |
| --- | --- |
| Forehead "dull pressure" (tension headache) | No headache word; "pressure" alone is not recognised as head pain |
| Arabic "حساسية بالأسنان من البارد" | Lexicon has "حساسية الأسنان" / "حساسية للبارد" but not this preposition form |
| "Blood in the sink every time I floss" | Paraphrase of bleeding gums not covered |
| Sorani "سووتانەوەیەک لە سنگمدا" | Indefinite suffix form of "burning in my chest" not covered |

These are the limits of a fixed multilingual vocabulary. The optional closed-vocabulary language-model extractor (`app/clinical/language_model.py`) is the intended mitigation, but it has **not** been evaluated because no credentials are configured.

## Not evaluated here

- **Images.** v2 does not add image models. Quality gating and modality checks for the four existing cancer classifiers are covered by `ai-service/tests/test_cancer_quality.py`; there is no new image evaluation in this report.
- **Privacy and cross-patient access** are tested as software behaviour in Laravel feature tests (`ClinicalSessionsTest`, `PatientMemoryTest`, `ClinicalReviewTest`: owner scoping, 404 for other accounts, encryption at rest, consent gates, reviewer de-identification) — see the test output in `docs/clinical-ai/CAPABILITY_REPORT.md`.
- Real conversations, children, pregnancy, older adults, typing errors at scale, dialect variation beyond the authored phrases, and anything about clinical outcomes.

## Proposed targets (not achieved results)

Before any patient-facing use: an independent clinician-labelled set of ≥ 300 conversations per language, with sensitivity for emergency presentations reported with confidence intervals and a pre-registered threshold; native-speaker review of every Arabic and Sorani term; and a prospective silent-mode study comparing triage against clinician decisions.
