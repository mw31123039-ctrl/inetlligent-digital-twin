# Dental and orthodontic research workspace

Implemented 5 November 2026. Open `http://127.0.0.1:5174/#dental`, `/#orthodontics`, or `/#dental-data` after the portable build. The sidebar's **Dental studio**, and the **Dental pain** / **Braces & bite** area buttons, open this workspace. These two area buttons replace the Arms and Legs launchers. Legacy limb IDs, records, assets and patient-twin observations remain readable.

## What works

- Original 3D atlas of 32 permanent teeth, using FDI notation from the patient's perspective. Select by mesh picking, numbered buttons or arrow-key chart navigation. Upper/lower, front, side and tooth-section views have orbit, pan, zoom and reset controls.
- Different incisor, canine, premolar and molar teaching geometry, enamel/dentin/pulp/root sections, gingiva and source-linked learning topics. Geometry is dimensionless and illustrative; morphology, root counts and eruption vary between people.
- Metal and ceramic bracket visualizations, ligature colors, archwires and a jaw-separation display control. No orthodontic forces, treatment stages, aligner schedule, movement prediction or appliance prescription is calculated.
- Separate pain records for each selected tooth, explicit symptom and appliance fields, a safety-sign screen, source-linked next steps and JSON summary export. No diagnosis or probability is generated.
- Local STL, OBJ and self-contained GLB review, including paired upper/lower surfaces. The pair shares a single centering/scaling transform. Original units are normalized for display; no physical measurements or tooth segmentation are inferred from a surface. External GLB resource URLs are rejected.
- Local PNG/JPEG/WebP image review, a published cephalogram with its 29 expert labels, manual two-point distances and three-point angles, keyboard coordinate fields, calibration entry and manual-point JSON export. Millimetres require a documented mm/pixel scale supplied by the reviewer. There is no trained landmark detector or radiographic interpretation.
- CSV/JSON measurement imports with coded subjects, chronological charts, first-to-last observed change, original-file export and SHA-256 fingerprint. Streams are separated by subject, tooth, metric and unit. Blank numbers, invalid dates, malformed CSV/JSON, duplicate observations and mixed units are rejected. Excel sheets must first be exported as CSV. There is no automatic correction, interpolation of missing observations or forecast.

## Public research data actually fetched

The files are in `frontend/public/data/dental/`. `manifest.json` records each original filename, author/source, release, byte count, modification status and SHA-256 fingerprint. `ATTRIBUTION.md` supplies attribution and license links.

1. **Serial 3D Dental Models**, Abdi and Nouri (2020), [Mendeley Data V1](https://doi.org/10.17632/bpnmf2vhsk.1), **CC BY 4.0**: two unchanged STL casts from the same published visit, one upper and one lower. The full source is longitudinal data from 24 participants with normal occlusion and no previous orthodontic treatment. This is not a treatment-response dataset.
2. **Aariz Cephalometric Dataset**, Khalid et al. (2025), [Figshare V1](https://doi.org/10.6084/m9.figshare.27986417.v1), **CC BY 4.0 dataset license**: one unchanged validation JPEG and its corresponding senior orthodontist annotation JSON. The full release has 1,000 radiographs and 29 expert landmarks. The ~2.1 GB ZIP was not downloaded in full: the reproducible fetcher reads its ZIP directory and selected original entries with bounded HTTP byte ranges. The journal article's separate license is not used to license the dataset.
3. **Orthodont**, [R nlme / CRAN R-universe](https://cran.r-universe.dev/nlme), **package distribution GPL ≥ 2**, original data Potthoff and Roy (1964), UNC Dental School: all 108 unchanged CSV observations from 27 coded subjects at ages 8, 10, 12 and 14. These are pituitary-to-pterygomaxillary-fissure distances in millimetres, not tooth movement, overjet, brace outcomes or population-normal thresholds. The full GPL-2 license text is included.

These are independent references, not three modalities from one matched patient. Public record identifiers are retained for reproducibility. Local research imports should be appropriately de-identified and used under the researcher's permissions.

The source library also links the official **Teeth3DS+** release and **Bite2Text** access page. Their full datasets have not been bundled. Teeth3DS+ website licensing is not assumed to license every OSF file. Bite2Text requires registration and release terms; no account was created and no access controls were bypassed.

Reproduce the reference downloads:

```powershell
cd frontend
npm run data:dental
```

## Measurement import contract

CSV headers or JSON object fields:

```csv
subject_id,recorded_at,tooth_fdi,metric,value,unit
STUDY_01,2026-10-01,11,pain,4,score
STUDY_01,2026-10-15,11,pain,2,score
```

Use coded IDs of 1–48 letters/numbers/underscores/hyphens, `YYYY-MM-DD` or a UTC ISO timestamp, a permanent FDI tooth or blank, a lowercase metric identifier, a finite number and `mm`, `degrees`, `score` or `hours`. The importer accepts up to 10,000 rows / 2 MB. File size and numerical bounds are software resource/input checks, not clinical normal ranges. R's original `distance,age,Subject,Sex` format is recognized separately, without fabricating dates or associating skull distances with a tooth.

## Safety, privacy and validation boundary

Guidance is deterministic, versioned source-based software requiring dental review. Primary sources: [NHS toothache](https://www.nhs.uk/symptoms/toothache/), [NHS abscess](https://www.nhs.uk/conditions/dental-abscess/), [NHS Fife orthodontic emergencies](https://www.nhsfife.org/services/all-services/patient-advice/orthodontic-emergencies/), [AAO emergencies](https://aaoinfo.org/whats-trending/what-is-an-orthodontic-emergency/), [ADA tooth anatomy](https://www.mouthhealthy.org/all-topics-a-z/tooth/) and [NHS braces](https://www.nhs.uk/tests-and-treatments/braces/). Links and draft content were checked on 5 November 2026. References are not endorsements or validation of this implementation.

Emergency signs take precedence before screen completion. A knocked-out or severely displaced permanent tooth receives immediate dental guidance. Emergency advice remains visible after edits, tooth changes and mode switches until an explicit new pain assessment. A score of 7/10 is an **unvalidated conservative software escalation flag**, not a published diagnostic cutoff. An unchecked safety review is incomplete, never interpreted as a negative screen. Medication doses, antibiotics, DIY appliance adjustments and individualized treatment recommendations are not provided.

New pain assessment clears the tooth-specific pain session. Research data has separate clear/close controls. Data stays in component memory and is cleared on reload or account change; image object URLs and GPU resources are released on unmount. There is no dental storage API, automatic browser persistence, file upload, provider request, automatic model training or paid call. The pre-existing eye and general assessment APIs remain independent. Export is an explicit download to the user's device.

Before clinical use: dental/orthodontic review of the numbering, geometry and care pathways; locale/age-specific validation; clinician-defined measurement protocols and calibration; subgroup and failure evaluation; consent and secure record design; and an applicable regulatory assessment. Real tooth movement cannot be inferred from the bundled historical growth table or the appliance display.

## Verification

```powershell
cd frontend
npm run typecheck
npm run test:dental
npm run build:portable
npm run test:dental:browser
```

The unit checks cover FDI laterality, escalation precedence, sticky emergency history, per-stream measurements, input rejection, source-file fingerprints, expert annotation count and finite atlas/hardware geometry. Chrome browser checks cover actual mesh picking, tooth-specific answers, emergency editing and export, appliance controls, local STL/OBJ/GLB inputs, reference images and calibration, reference/custom CSV, invalid import recovery, replacement area launchers and mobile fit. Screenshots are generated under the ignored `frontend/test-results/dental/` directory. These checks establish software behavior, not diagnostic accuracy or treatment efficacy.

For future model research, preserve source patient-level splits and keep repeated scans/visits from one participant in a single partition. Report task-specific segmentation, landmark or longitudinal errors with calibration, missing-data policy and uncertainty; do not report fixture agreement or a rendered brace appearance as clinical accuracy. No trained research model is supplied in this module.
