# HumanTwin research review and reproducible evaluation

Review date: **1 November 2026**. This review concerns the local workspace, not a deployed service. The clinical rules, geometry, labels and translations remain unvalidated.

## Recommended research direction

The selected research focus is **developing a patient-specific digital twin**. The resulting [patient-specific research workspace](../PATIENT_TWIN_RESEARCH.md) now supplies subject-bound longitudinal observations, immutable corrections, individual references, experimental projections and rolling-origin evaluation. This document describes the supporting eye-policy benchmark and its limits.

The strongest part of this project is its connection between anatomy exploration, structured symptom context, explicit uncertainty and independently versioned warning rules. The eye module offers a focused starting point with more depth than the other body regions. Its software tests, shared contracts and server replay provide useful engineering foundations.

For the selected patient-specific-twin direction, prioritize the [individual observation model, target outcome and longitudinal validation plan](../PATIENT_TWIN_RESEARCH.md). The multilingual anatomy-guided intake remains a useful supporting component. A defensible question for this supporting benchmark is:

> On a fixed set of draft synthetic scenarios, how does retaining conversation context affect warning-policy conformance, and which language and input variations produce disagreements?

This is a proposed research question, not a claim of scientific novelty. Establish novelty through a systematic literature review and independent evaluation. A suitable working title is *A multilingual anatomy-guided symptom intake prototype: reproducible evaluation of context retention and safety-policy failures*.

The anatomy and symptom-intake implementation remains educational. Its procedural body/eye model is not patient specific, and saved assessments do not provide a validated predictive model. The new Patient twin workspace adds a separate individual observation model with experimental statistical extrapolation; it does not add patient-specific geometry or a validated physiological simulator. A digital twin, under the [National Academies' definition](https://www.nationalacademies.org/read/26894/chapter/4), should update from a physical counterpart, support prediction and inform decisions through feedback. Validated physiological prediction and reviewed action feedback therefore remain further research work.

## What was implemented

- An offline benchmark that runs the **actual TypeScript eye engine**, using the project's existing portable bundler. It does not copy the policy into a second evaluator.
- **90 synthetic scenarios across 30 families**, with English, Iraqi Arabic and Sorani versions. Together their expected targets cover all 18 draft warning rules. Eight additional families were added after the initial coverage audit showed unexercised rules; no failing expectations were changed to improve agreement.
- Per-turn urgency checkpoints, final required-rule checks, reported-fact/provenance checks and checks that warnings stop routine questions.
- Two explicit software ablations: discard previous turns, or omit narrative input while retaining structured answers and state.
- A filterable standalone HTML report, Markdown summary, UTF-8 CSV and JSON with exact inputs, traces, confusion matrices, denominators and source fingerprints.
- Seeded family-level bootstrap intervals and paired comparisons that keep translations of a scenario together.
- Evaluator tests for error accounting, missing denominators, paired identities, history ablation, label isolation, report escaping and spreadsheet-safe exports; a real-browser report check is also included.

No credentials, application server, external AI model or network request is needed to execute the benchmark. The browser report loads its data and scripts from the generated file. No application records, health data, rules or clinical-use gates are changed by the benchmark.

## Run it

Use the project's existing Node environment and install frontend dependencies first if necessary (`npm ci` from `frontend/`). From the project root:

```powershell
node research/run-eye-benchmark.mjs
node --test research/tests/evaluation.test.mjs
node research/tests/report-browser.mjs
```

Open **`research/results/latest/report.html`** directly in a browser. JSON, CSV and Markdown exports are beside it. Generated results and screenshots are ignored by Git; archive them deliberately with the dataset and source snapshot when recording an experiment.

The same commands are available from `frontend/` as `npm run research:eye`, `npm run research:test` and `npm run research:test:browser`.

```powershell
# Reproducible resampling and an explicit output folder
node research/run-eye-benchmark.mjs --seed 20261101 --resamples 2000 --out research/results/experiment-01

# Strict policy-conformance gate; writes all reports before exiting
node research/run-eye-benchmark.mjs --check
```

Normal execution exits **0** when reports are generated, including when disagreements are discovered. `--check` exits **1** if the production engine disagrees with any supplied expectation; execution/configuration failures exit **2**. The current fixtures intentionally include unresolved challenges, so `--check` currently exits 1. An ablation's failure does not affect this gate. No minimum clinical-performance threshold is invented.

The browser check uses installed Google Chrome on Windows, matching the existing project's workaround for application-control restrictions. On another platform it uses Playwright Chromium. Set `HUMANTWIN_BROWSER_CHANNEL` to select a different installed channel. It checks the offline report and does not start the application.

## Initial findings

For fixture version `eye-research-fixtures-2026-11-01.1` and policy `eye-draft-2026-10-30.4`, the measured results were:

| System | Urgency matches | Full policy matches | Engine errors |
| --- | --- | --- | --- |
| Production engine with context | 76/90 | 76/90 | 0 |
| Latest-turn-only ablation | 48/90 | 39/90 | 0 |
| Structured-input-only ablation | 48/90 | 45/90 | 0 |

These are **draft fixture agreement counts**, not diagnostic accuracy. In particular, repeatedly presenting identical structured option IDs in three UI languages does not establish multilingual natural-language understanding. The report also provides narrative-only, structured, mixed-input and challenge subgroups so those inputs can be distinguished.

The production engine activates all 18 rules somewhere in this suite. That is rule-activation coverage, not complete predicate, branch or clinical coverage. It disagrees on 14 cases:

- **Eight missed draft emergency expectations:** chemical-exposure paraphrases, misspellings, Arabic diacritics and Kurdish/Arabic character variants.
- **Two missed draft urgent expectations:** natural Arabic and Sorani descriptions of neonatal redness that do not match the current lexical patterns.
- **Four unexpected escalations relative to draft unknown labels:** three explicitly historical visual-loss reports and a Sorani denial expressed after the symptom.

All 15 challenge cases stay in the main report, including failures. Their subgroup has 3/15 urgency matches; the other 75 cases have 73/75. The suite was deliberately constructed to contain these kinds of inputs and is not sampled from a target population. Its overall proportion is sensitive to the author-selected mixture of routine and challenge scenarios.

Conversation state improves agreement on these authored examples relative to discarding it. This is a useful software finding and a hypothesis for independent study, not evidence that the current system improves patient outcomes. Required-rule or reported-fact checks may fail even when the final urgency matches, which explains the different policy and urgency counts in the ablations.

## Evaluation protocol and definitions

**Reference labels.** Family expectations are manually authored before each run and never derived from the engine's output. They reflect intended draft behavior and targeted robustness probes. They are not clinician-adjudicated reference standards. Source links indicate the existing policy's provenance and do not validate a scenario label. Some concerns deliberately overlap with existing software tests; this is not an independent external dataset. No patient data, clinical reviewers, native medical translators or patient/public participants were involved in fixture authoring.

**Systems.** `full` replays the supplied turns with the production engine's session state. `latest_turn_only` creates a new session before each answer and scores the final turn's resulting state; it deliberately removes context and warning retention. `structured_only` retains state and accepts known choice values and numeric pain/age/day answers, including explicit unknowns. It omits narrative and educational turns without converting them into negative answers. These are capability-removal experiments on the same engine. They are not comparisons against another medical system or clinicians. Supplied turns test replay, not whether the adaptive UI would elicit the same answers in practice.

**Urgency agreement.** Exact final match among `unknown`, `urgent` and `emergency`. **Policy conformance** additionally requires every labelled checkpoint, every required rule, expected reported-field values, absence of specified unreported fields and stopped routine questioning after a warning. An expected empty rule list does not prohibit all rules independently; final urgency and other constraints are still checked.

**Emergency-level recall.** Observed `emergency` / expected `emergency`. Returning `urgent` on an expected-emergency case is a miss for this metric. **Escalation recall** counts either warning level on any expected-warning case. **Unexpected escalation** counts warnings on cases labelled `unknown`; this is not clinical false-positive rate or specificity because unknown does not mean disease absent or safe.

**Errors and denominators.** Engine exceptions become an explicit error column, never unknown or a successful abstention. They count as misses in applicable agreement/recall denominators. Underclassification/overclassification compare the ordinal levels for successful engine outputs; errors are reported separately. A metric with no eligible cases is `null`, displayed as `n/a`. No AUROC, calibrated probability, diagnostic sensitivity/specificity or patient-level confidence is reported.

**Families and partitions.** Translations share a stable family ID. SHA-256 of that ID, first 32 bits modulo five, assigns development (0–2) or evaluation (3–4). Labels and all inputs remain public; this evaluation partition is exploratory and is **not a blinded holdout**. Partition assignment is unaffected by family iteration order and does not separate translations. Subgroups overlap, so subgroup counts must not be summed.

**Uncertainty.** The main descriptive interval resamples families with replacement, keeping all language variants together, and computes the mean of per-family urgency-agreement proportions. Paired differences first align identical cases, compute within-family differences, and resample those family differences. The default is 2,000 resamples and seed 20261101. Fewer than two families produces no interval. Bootstrap intervals describe variation over these authored families; they do not measure uncertainty about patient populations, and homogenous fixtures can produce degenerate intervals. A positive paired result on this suite is not a superiority claim.

**Reproducibility.** JSON records the dataset bytes' SHA-256, bundled engine SHA-256, rule version, individual input-file hashes, Node/platform, seed and resample count. Timestamp and runtime metadata may differ between runs; numerical results, traces and source hashes should match for unchanged source, dependencies and configuration. Random session IDs, timestamps and generated prose are excluded from scored outputs. The source lockfile is fingerprinted. No Git commit is inferred because this workspace is not a Git checkout.

## Highest-priority next work

1. **Review the measured language failures.** Have an ophthalmologist and native medical translators adjudicate both the challenge labels and the intended emergency wording. Then implement shared text normalization, explicit temporal context and pre-/post-symptom negation in both frontend and PHP replay. Add new, separately authored cases before claiming generalization. Do not fix these solely by adding the exact benchmark strings to a keyword list.
2. **Design an independent study.** Freeze the intended use, local referral policy, eligibility criteria, primary outcome and analysis before obtaining an independent cohort. Use independently authored cases or appropriately governed clinical data, multiple clinician raters with disagreement adjudication, and bilingual medical review. Size the study for the chosen endpoint and population; do not derive a clinical sample size from these synthetic fixtures. Keep patients and source scenario families separate across all tuning/evaluation splits and evaluate relevant subgroups.
3. **Evaluate the complete system.** This benchmark covers browser-engine replay, not PHP replay equivalence, account authorization, provider retrieval, configured LLM behavior, anatomy correctness, user understanding, accessibility or prospective outcomes. Existing backend tests need a supported PHP runtime. The local review records application-control restrictions on PHP/Python/native tooling; this work does not bypass those restrictions. Future LLM experiments should record the actual provider/model configuration and all failures without silently substituting this deterministic engine.
4. **Extend the new longitudinal research layer.** The Patient twin workspace now provides typed time-stamped observations, source metadata, subject binding, immutable corrections and explicitly experimental projections on synthetic data. Before real measurements or clinical predictive claims, choose a disease-specific model, reference outcomes, consent workflow and validation design. Wearables, imaging and laboratory integration need a defined research protocol and verified provenance. A synthetic example must remain visibly labelled as such.

This supporting deliverable is a repeatable measurement instrument and a prioritized failure inventory. The Patient twin workspace supplies the initial individual observation model; broader clinical validation, disease-specific physiological modeling and a publishable novelty claim remain further work.

## Reporting references

- National Academies of Sciences, Engineering, and Medicine. *Foundational Research Gaps and Future Directions for Digital Twins* (2024), [chapter 2: definition, verification, validation and uncertainty](https://www.nationalacademies.org/read/26894/chapter/4), DOI: 10.17226/26894. This informs the scope distinction and the emphasis on evaluation.
- Gallifant et al. *The TRIPOD-LLM reporting guideline for studies using large language models*. Nature Medicine 31, 60–69 (2025). [Primary article](https://www.nature.com/articles/s41591-024-03425-5), DOI: 10.1038/s41591-024-03425-5. This informs transparent dataset, configuration, reproducibility and failure reporting for future LLM research. The current deterministic benchmark is not an LLM evaluation and does not claim checklist compliance.
