# Eye explorer implementation and review record

**Visual update, 1 November 2026:** compact and full eye workspaces now start with the new surface rendering: shaped lids/skin/lashes, a MakeHuman CC0 reference iris texture, recessed pupil opening and clear cornea with studio reflections. All 63 IDs and internal/magnified views remain available. See [asset provenance](frontend/ASSET_ATTRIBUTIONS.md) for the body and regional-model changes. This presentation update does not add clinical review, patient-specific anatomy or validated optics, and does not alter triage rules.

Rules version: `eye-draft-2026-10-30.4`; care content: `eye-care-draft-2026-10-30.1`; assisted pain guide: `pain-assistance-draft-2026-10-30.1`. Educational evaluation with synthetic examples only. **Live clinical triage is disabled in both the content manifest and Laravel API.** No clinical validation or medical translation approval is claimed.

The main **Symptom assistant** card now uses the adaptive eye interview when Eyes is selected. Selecting **Eyes** opens the complete eye atlas beside the chat, including all 63 structures across the available views. **Open detailed eye explorer** opens the larger workspace. The two views share an in-memory session, explored structures, acknowledgement and reported pain. The running main preview is `http://127.0.0.1:5173/#eye-chat`; the optional portable preview also runs on port 5174. Other body regions, saved legacy records and the separate AI assistant remain available. Eye records have a separate encrypted table and history; the migration does not modify existing assessment tables.

## Implemented coverage

- 63 stable anatomical IDs across 10 groups: surface/lids, tears, cornea, coats, focusing, fluid/drainage, vitreous, retina, nerve and orbit/movement. Includes all structures listed in the requested scope. Corneal microscopic layers and retinal pigment epithelium/photoreceptors have magnified views.
- External, cross-section, transparent, exploded and posterior views; magnified corneal/retinal views; layer controls, isolation, searchable selection, hover/tap information, rotation, zoom, reset, keyboard selection and a selectable SVG fallback.
- Patient-side coordinates remain fixed through camera rotation. The macula is temporal to the optic disc, with the fovea within the macula. The pupil uses annular iris geometry and an invisible annotation hit target, rather than an opaque pupil disc. Posterior aqueous and vitreous chambers are separate entities.
- 112 condition/finding/outcome records in 19 categories. Congenital cataract and glaucoma also belong to the childhood category. Synonyms, anatomy/symptom relationships, risks, age considerations, examination needs, warning signs, source links and review metadata are structured data. Symptoms and findings are not automatically made into diagnoses.
- 31 symptom/sign IDs, 65 adaptive questions and 18 deterministic warning pathways. Added symptom-directed branches for pain character/impact/pattern, dryness and screens, itching/allergen context, discharge, lid lumps, watering, double vision, visual distortion, night/colour vision, lens hygiene and history. Safety context precedes routine history. Warning evaluation runs after every answer, with no AI/network dependency. Emergency and urgent results stop routine questions. No condition ranking, diagnosis, prescription or confidence percentage is produced.
- 195 source-linked educational chat topics, including every anatomy and condition record plus common questions. Explicit learning requests are answered without extracting patient symptoms or advancing the pending interview question. Server replay validates topic IDs against the same library.
- The default pain flow asks for a description and activity impact, then proposes an explicitly labelled approximate number and range. A person can confirm it, correct it, enter a manual score, or continue unrated. Unconfirmed estimates remain outside `reported.pain`; accepted proposals are marked `assisted-confirmed`, and manual corrections are marked `self-reported`. The server independently derives the proposal and rejects mismatched confirmations. Describing pain as “severe” can trigger safety rules immediately and produce a separate draft suggestion, but never silently becomes a confirmed numeric score. An estimate never lowers urgency, and emergency guidance stops further estimation questions. Explicit self-reported scores do not acquire unrelated proposals in the doctor handoff.
- Assisted estimates use an **original, unvalidated heuristic**, not an objective measurement or a validated pain instrument. Linked clinical resources inform question topics and broad bands; they do not validate the proposed individual numbers. Ophthalmology, pain-assessment and native medical translation review remain required. The helper must remain unavailable for live clinical use until those reviews and performance evaluation are completed.
- Care guidance provides safe immediate steps, an appropriate service type, and a factual clinician handoff with copy/download. Emergency presentations route to emergency care/ophthalmology now; urgent presentations to same-day eye assessment, with paediatric routes requiring child context. Severe pain with unknown/gradual onset also triggers an explicit urgent rule; sudden severe pain remains an emergency. Environmental comfort measures for reported dryness/grittiness are offered only after explicit low-risk safety answers and are removed after escalation. No cure, diagnosis, prescription drops or medication dosing is suggested. Care content remains draft and needs ophthalmology and translation review.
- Explicit patient locations do not require anatomy knowledge. Laterality from narrative is separate from the model side; clear “both eyes” reports update the summary, while ambiguous conflicting side reports remain unknown.
- English, Iraqi Arabic and Kurdish Sorani interface, labels, question/answer choices, short anatomy functions, short condition explanations and urgency/first-aid wording. Non-English content is a **draft**, with original English retained and accessible. Detailed condition risk/examination/reference notes remain in original English with an explicit translation-review notice.
- In-memory educational sessions; optional export; authenticated, consented Laravel saving; server-side validation and independent replay; encrypted payloads; owner-scoped list/read/delete. No eye draft is written to browser storage or sent to an external AI provider.

## Files and architecture

- `frontend/src/eye/`: workspace, Three.js schematic, SVG fallback, catalogue, interview, summary, shared assessment context, educational retrieval, pain interpretation, inline assistant and styles.
- `frontend/src/App.vue`, `frontend/src/main.ts`: integration and stylesheet import.
- `contracts/eye/`: versioned anatomy, conditions, interview/rules, educational knowledge, pain scale, care/referral templates, review gate, sources, link-audit report and safety case vectors. Vue and PHP consume the same declarative content and rules. Care plans and clinician summaries are independently recomputed on the server before encrypted persistence.
- `scripts/prepare-eye-*.mjs`, `scripts/eye-*-translations.mjs`: editable content generators. Run content and interview generators before the catalogue generator. `scripts/audit-eye-sources.mjs` checks public links and titles, not medical validity.
- `backend/app/Services/EyeAssessmentService.php`: independent deterministic server replay; does not trust client urgency or diagnoses.
- `backend/app/Http/Controllers/EyeAssessmentController.php`, `backend/app/Models/EyeAssessment.php`, the new `create_eye_assessments_table` migration and API routes: protected persistence. Existing health records are unchanged.
- `frontend/scripts/test-eye.mjs`, `frontend/scripts/smoke-eye.mjs`, `contracts/eye/cases.v1.json`, `backend/tests/Feature/EyeAssessmentsTest.php`: software verification.
- `frontend/scripts/portable.mjs` and `serve-eye-preview.mjs`: optional WebAssembly bundling and local preview when native build tools cannot run. Standard Vite commands remain available. The isolated output is `dist-eye-preview/`.

## Running and checking

```powershell
cd frontend
npm run build:portable
npm run test:eye
npm run preview:eye
# http://127.0.0.1:5174 — /api and /sanctum proxy to Laravel on port 8000
node scripts/smoke-eye.mjs
npm run test:eye:chat
npm run test:eye:care
npm run test:eye:pain

cd ../backend
php artisan migrate
php artisan test --compact --filter=EyeAssessmentsTest
```

The portable builder does not rebuild Tailwind utilities; this application's existing authored CSS and theme variables are preserved. Normal production deployment should use the standard Vite build on a supported machine. Do not publish a local preview as a clinical service.

## Review still required

1. An ophthalmologist must review geometry, relationships, educational statements, category-specific guidance, every rule predicate/threshold, first-aid wording and question order. No clinician has signed an approval. The source-check date is **not** a clinical review date; `clinical_reviewed_at` remains null.
2. Native medical translators must review all Arabic/Sorani content, dialect/register, anatomy terminology and urgent-action meaning. Detailed catalogue risk/examination notes still need full medical translation.
3. Rules use bounded lexical recognition. They can miss paraphrases, unusual wording, spelling errors, historical statements and mixed-language context, and can over-escalate. A rule non-match never establishes safety. New/unknown-context flashes or floaters are escalated conservatively; the prototype cannot establish benign chronicity.
4. Geometry is procedural, non-patient-specific and not anatomically validated. Microscopic thickness and exploded spacing are exaggerated. Muscle trajectories and insertions, vessel branching, eyelid/conjunctival surfaces and chamber boundaries are schematic. This is not a surgical atlas or imaging reconstruction.
5. Condition coverage is a starting catalogue, not exhaustive. Sources are linked at the condition level and short explanations are paraphrases. Link/title checks do not verify clinical entailment, completeness, currency or safe individual advice.
6. Iraq referral/access pathways require local clinical operations review. The prototype uses nearest emergency department/urgent eye service wording and does not insert UK emergency numbers.
7. The existing privacy/deployment review in `CLINICAL_REVIEW.md` still applies. Review health-data processing, retention, backup deletion, infrastructure logs, accessibility and clinical performance before any patient deployment.

## Verification limits on this machine

Recorded software checks: 52 portable Node assertions/scenarios, TypeScript/Vue type checking, a complete portable production bundle, PHP syntax parsing, and real Chrome browser smoke checks covering internal and magnified selection, keyboard/touch controls, patient-side orientation, both-eye updates, chemical interruption, educational chat, pain feedback, guided pain proposals/confirmation/correction, shared-session switching, care/referral guidance, clinician handoff copying/download, library search, mobile layout and Sorani/Arabic RTL. Existing non-eye navigation and the head detail viewer were also exercised. These are software checks, not clinical validation.

Windows application control blocks PHP and Python and the native Rollup binary, even outside the sandbox. Laravel Boost setup and PHP runtime tests/migration could not run. The added PHP files can be syntax-parsed, but this is not a substitute for Laravel feature tests. Browser checks use the installed Google Chrome because the downloaded Playwright headless binary is also blocked. No security policy was changed.
The existing Vitest suite also fails to start because its native Rollup dependency is blocked. Use the portable eye checks here, and run the full existing frontend/Laravel suites on a supported machine before release. The public-source audit reached 93 of 94 unique source URLs; the NCBI lagophthalmos reference could be verified through web retrieval but its direct Node fetch failed on this machine. This remains an explicit link-check limitation.
