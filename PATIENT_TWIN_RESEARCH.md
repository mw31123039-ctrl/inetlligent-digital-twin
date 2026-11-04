# Patient-specific research twin

The person is now a textured, rigged 3D human, with zoom/orbit controls and accessible region navigation. Regional close-ups use reference anatomical mesh assets and the eye has a new surface presentation; see [visual asset provenance](frontend/ASSET_ATTRIBUTIONS.md). Avatar and organ geometry remain reference anatomy, separate from the subject-specific observation model described here.

Implemented on **1 November 2026**, following the selected research focus: **develop a patient-specific digital twin**.

The new **Patient twin** workspace maintains an evolving model for one study subject. Adding or correcting an observation updates its individual reference, time-series chart, eligible statistical projection and retrospective error comparison. It provides the longitudinal data/model layer that was missing from the anatomy explorer.

This is a **synthetic research prototype**, not a validated physiological twin, diagnostic model or clinical service. Anatomy is schematic, devices are not connected, and no patient-outcome or disease-prediction performance is claimed. The distinction follows the [National Academies' digital-twin framework](https://www.nationalacademies.org/read/26894/chapter/4): patient-linked measurements and model updating are components of a twin; validated prediction and a reviewed feedback/decision process require further research.

## Try the workspace

From `frontend/`:

```powershell
npm run build:portable
npm run preview:eye
```

Open **http://127.0.0.1:5174/#twin**, or select **Patient twin** in the sidebar. Standard `npm run dev` also serves the workspace on the normal Vite port when native build tools are available.

1. Start an empty subject using a synthetic study ID, or choose **Load synthetic example**. The example is explicitly labelled synthetic; there are no inferred measurements in an empty twin.
2. Select a measurement stream. **Use selected stream** fills its method, source and anatomical context for a new observation.
3. Record a reading and its observed time. Times in the form and display use Baghdad, UTC+03:00; the exported record uses UTC ISO timestamps.
4. Inspect the personal reference, trajectory, model eligibility and projection provenance. Select a 1-, 6- or 24-hour horizon; ineligible extrapolation is withheld.
5. Use **Correct** in the event ledger to append a correction. The original remains visible as superseded and is excluded from the current model.
6. **Export record** saves an importable JSON ledger. **Export model analysis** saves the ledger plus all streams' reference statistics, horizon, projections, training IDs and retrospective predictions. The analysis file is a report, not an importable record.

Loading another subject or importing a file displays a replacement preview when relevant. It never merges subjects. Navigating into a reported anatomical region and returning to Patient twin preserves the current in-memory record. Changing the authenticated account clears that record. Reloading the page also clears it; **export first to preserve research work**.

## Data model and provenance

`frontend/src/twin/model.ts` owns validation and model computation. `PatientTwinWorkspace.vue` supplies the interface. No PHP/Python changes, database migrations, AI credentials or external service are needed for this workspace.

The importable schema is `humantwin-longitudinal-v1`, with `use: "synthetic-research"`, a single pseudonymous `subject_id`, a creation time and at most 1,000 observation events. Each event contains:

| Field | Meaning |
| --- | --- |
| `id`, `subject_id` | Stable event identity and binding to this subject |
| `metric`, `value`, `unit` | Typed numeric reading and canonical unit |
| `region`, `side` | Reported anatomical context, separate from viewer orientation |
| `method` | Measurement method; incompatible methods are separated |
| `observed_at`, `recorded_at` | Measurement time versus ledger-entry time, both UTC |
| `source.kind`, `source.label` | Explicit, unverified source metadata |
| `supersedes` | Optional reference to the latest active event being corrected |

Supported measurements are resting heart rate (`bpm`, manual pulse or wrist sensor), temperature (`°C`, oral/axillary/tympanic) and regional self-reported pain (`/10`). Heart rate and temperature are systemic; pain requires a body region and side context. The source label distinguishes individual devices or manual protocols. A manual label and an imported-device label do not verify that a device was actually used.

Imports reject mixed subject IDs, unsupported schema/fields, nonfinite values, inconsistent units, invalid dates, future or backward recording times, duplicate active stream timestamps, unknown correction targets and corrections that fork from superseded events. There is a five-minute clock-skew allowance on creation/recording time, while observed time must not exceed recorded time. Corrections preserve measurement time, method, source and anatomical stream. These rules protect data consistency, not medical validity.

Numeric input limits are technical domains, **not reference intervals**. Pain is limited to 0–10; other numeric bounds prevent unsupported/extreme arithmetic and physically invalid temperatures. The interface does not label values normal, abnormal, healthy or dangerous, and it does not convert units silently.

The application keeps this research document in Vue memory. It does not write twin observations to localStorage, sessionStorage, Laravel or an AI provider. Exports are explicit user downloads and include the subject identifier, source labels and original correction history. Existing assessment storage is separate. Real patient processing, shared access, device ingestion, backup/retention and clinical use require an independently designed data-governance and validation workflow.

## Subject-specific model

A measurement stream is identified by **metric + anatomical region + patient side + measurement method + source kind + source label**. Values from different subjects, sources, methods, regions or sides are never pooled into one projection.

For the selected stream, the personal reference is the arithmetic mean of earlier active observations, excluding the latest chronological reading. The displayed change is latest value minus that reference. It describes this record and does not represent a population reference range or clinical baseline.

The experimental model, `linear-research-v1`, fits ordinary least squares to elapsed observation time in hours. For a future time it reports a point extrapolation and a two-sided 95% **model prediction interval**:

```text
b = Σ((x − x̄)(y − ȳ)) / Σ((x − x̄)²)
ŷ(x*) = ȳ + b(x* − x̄)
s² = Σ(y − ŷ(x))² / (n − 2)
interval = ŷ(x*) ± t(0.975, n − 2) × s × √(1 + 1/n + (x* − x̄)² / Σ((x − x̄)²))
```

The interval includes residual variation for an individual future reading, rather than only uncertainty in the mean fitted line. The approach and its assumptions follow standard [simple-linear-regression prediction methods](https://online.stat.psu.edu/stat501/Lesson03); critical values follow the [Student-t distribution convention documented by NIST](https://www.itl.nist.gov/div898/handbook/eda/section3/eda3672.htm). The implementation stores critical values to six decimal places through 30 residual degrees of freedom, then conservatively reuses the df=30 value.

The prototype requires at least four distinct active observation times spanning one hour, with a projection horizon no longer than half the observed span. It withholds out-of-domain projections. It also **withholds pain forecasts**, because ordinal self-reported scores are not treated as a continuous physiological measurement for this model.

These eligibility conditions are explicit engineering choices, not validated medical thresholds. Linear behavior, independent errors, constant residual variance and approximately normal residuals are unverified. Physiological time series can be autocorrelated, irregular and affected by interventions or acquisition conditions. Identical or exactly linear synthetic observations may produce a zero-width interval. A nominal 95% interval is not a demonstrated 95% coverage rate on patients.

## Research evaluation

`rolling-origin-v1` retrospectively predicts each eligible later observation using **only earlier readings**, starting with four training readings. It reports:

- Mean absolute error of the personal linear projection.
- Mean absolute error of a persistence comparator: predict the last observed value.
- Number of targets inside the model interval, number evaluated and number withheld.
- Per-target observed value, prediction, comparator and training IDs in the analysis export.

The backtest does not tune the model on its target. It replays the **currently corrected ledger**, so later-entered corrections to earlier measurement times are included; it is not an as-known-at-the-time clinical replay. Repeated within-subject targets are correlated, and results on a handful of synthetic points are exploratory. This comparison is instrumentation for research, not clinical validation or proof of superiority.

The companion [eye-policy benchmark](research/README.md) adds 90 synthetic multilingual scenarios and records unresolved warning-rule failures. Its scope is different: it measures draft policy agreement, while the twin workspace measures individual observation trajectories. Neither establishes patient outcomes.

## Verification and next research stage

```powershell
# frontend/
npm run test:twin
npm run build:portable
npm run preview:eye
# with the preview running in another terminal:
npm run test:twin:browser
```

Model checks cover subject/unit/time isolation, reactive document handling, correction chains, source separation, a hand-calculated regression interval, model updates, withheld forecasts and rolling-origin target isolation. The browser check exercises adding and correcting readings, separate model/record downloads, invalid cross-subject imports, import restoration, body-region navigation and responsive layout. Existing eye software checks also remain applicable. These are software checks.

For the next research stage, choose a specific disease or physiological process and define the measurement protocol, target outcome and intended decision before adding a more complex model. Freeze model choices, acquire appropriately governed longitudinal observations, evaluate patients independently of tuning, and test prospective error and interval coverage against persistence and disease-appropriate comparators. Real device connectivity, patient-specific anatomy, a physiological simulator and clinician-reviewed action feedback are not implemented here.
