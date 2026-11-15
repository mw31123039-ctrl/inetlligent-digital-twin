# Intelligent Digital Twin of the Human Body

**Expanded cancer care workspace:** open `/#cancer`. A prominent upload button, drag and drop, safe resizing for larger JPEG/PNG images, licensed oral examples and a fixed action bar make image review easier. The new logo and larger default text are shared across the workspace; A+ offers a larger type setting. Alongside the four working image models, a real local MiniLM encoder searches a shared library of 16 cancer topics and four source/help records. The care view turns reported context into a source-linked review checklist, not a diagnosis or prescription. Read [the clinical-source and implementation review](research/CANCER_CARE_REVIEW.md).

**Real local cancer AI:** open `/#cancer` or **Cancer research**. This computer now has four working learned classifiers: a seven-class dermoscopy ViT, a benign/malignant/normal breast-ultrasound ViT, a four-class lung-CT-slice EfficientNet-B0, and an oral-lesion ResNet18 actually trained locally from licensed public original photographs. The workflow is: choose an area on the body map, upload a matching image, review a report. Input checks reject images that do not fit the selected area (for example a colour photo sent to the CT model) and mark blurred, blank or unfamiliar images as inconclusive. The report shows the finding in plain language, temperature-calibrated confidence against a per-model threshold, a Grad-CAM (CNNs) or attention-rollout (ViTs) heatmap, a suggested next step and the matching knowledge guide; it can be saved to History (encrypted, per account) or exported as a PDF. Heatmaps show model behaviour, not tumour boundaries. Held-out evaluation, calibration and model cards: [research/CANCER_EVALUATION.md](research/CANCER_EVALUATION.md). Symptoms/history are optional unverified reviewer notes and are not analyzed by the image classifier. Exports can link the matching coded twin subject and exclude image pixels.

**Research models, not clinically validated cancer diagnosis.** Local trained artifacts and public training data are ignored by Git; the reproducible installer/training scripts and source fingerprints are included in the source. Patient separation is unknown for these models and is represented as unknown, without invented validation claims. Ordinary phone skin photos, mammograms and MRI still need their own models; they remain unavailable. CT support is a single prepared 8-bit slice, not full-volume screening or staging. Inference requires sign-in plus explicit input/processing acknowledgements, does not save images or train on account data, and calls no external AI provider. See [model sources, measured oral evaluation and reproduction instructions](ai-service/README.md#cancer-research-models).

**Orthodontic screening annotations:** open `/#dental-cases` → **Orthodontic screening**. This new local research workflow covers all 41 supplied conditions with stable snake_case labels, four assessment states, standardized view/quality/bite records, manually established locations and separate clinician-entered dental classifications. It provides a reviewer-entered summary, a clearly separate synthetic demonstration, and a per-condition evaluation tool for actual imported held-out model outputs. No orthodontic condition classifier is bundled or trained; taxonomy definitions remain pending independent orthodontist review. Explicit local saves and optional reviewed photo bundles are separate from crown-outline training. See [the dental module review](DENTAL_MODULE_REVIEW.md).
**Local dental simulator:** open `/#dental-cases` and attach a photo. The before/mock-up panels use that photograph. Draw a rough crown outline and use **Refine selected outline locally**, then review it before moving the actual crown pixels. This runs OpenCV assisted segmentation on this computer with no external AI provider or API key. Full-photo **Detect teeth with local model** uses your separately trained local random forest. It remains disabled until reviewed training data and a model exist. Eight sourced care pathways explain methods, potential advantages, disadvantages and clinician checks. The visual result is a 2D educational mock-up, not a treatment prediction.

**Dental case room:** open `/#dental-cases`, or **Dental studio → Cases & practice**. Attach up to six local patient photos, label views and teeth, record findings, explore 26 source-linked orthodontic topics and take randomized student tests. The study coach searches the local reference library. External dental AI review is disabled. Ordinary case exports exclude images; a separate explicitly consented **Teach your local model** export includes the re-encoded photo and dentist-reviewed crown polygons. No upload or automatic training occurs. See [the dental module review](DENTAL_MODULE_REVIEW.md).

**Dental and orthodontic workspace:** open `/#dental` for a selectable 32-tooth atlas and tooth-specific pain intake, `/#orthodontics` for bracket and archwire visualization, or `/#dental-data` for research scans, X-rays and measurement charts. Dental pain and Braces & bite replace the Arms/Legs area launchers. Includes licensed public STL casts, a cephalogram with expert landmarks and historical growth measurements, plus local research-file imports. See [DENTAL_MODULE_REVIEW.md](DENTAL_MODULE_REVIEW.md) for sources, limits and verification.

**3D visual update:** Patient twin now displays the textured, rigged human with higher-resolution face and normal maps. The eye starts with a lifelike surface view using a licensed reference iris, shaped lids and clear cornea. Regional close-ups use bundled anatomical mesh geometry: BodyParts3D plus a Z-Anatomy chest organ-surface view, with a separate vessels-and-ribs view. Read [asset provenance and licenses](frontend/ASSET_ATTRIBUTIONS.md). These are reference representations, not a reconstruction of the study subject.

**Patient-specific research twin:** select **Patient twin** in the sidebar, or open `/#twin`. The new workspace updates an individual model from time-stamped observations, keeps corrections and source provenance, plots a personal reference, and provides an experimental statistical projection with retrospective comparison and JSON exports. Read [PATIENT_TWIN_RESEARCH.md](PATIENT_TWIN_RESEARCH.md) for the model, assumptions and local running instructions. Synthetic research inputs only; this is not a validated physiological or clinical twin.

Research review and reproducible evaluation: [research/README.md](research/README.md). Run `node research/run-eye-benchmark.mjs` from the project root to produce an offline interactive report, JSON traces and CSV for 90 synthetic eye scenarios in English, Iraqi Arabic and Sorani. The benchmark compares retained conversation context with explicit software ablations, preserves disagreements and records source fingerprints. Draft fixture agreement is not clinical accuracy; patient-specific updating and prediction remain future research work.

The detailed eye explorer is documented in [EYE_MODULE_REVIEW.md](EYE_MODULE_REVIEW.md). It includes an educational anatomy atlas, adaptive synthetic symptom interview, source-linked condition library and protected eye-record API. Clinical use remains disabled pending review. An optional native-free frontend build/preview is available through `npm run build:portable` and `npm run preview:eye` in `frontend/`.

Vue/Three.js human explorer with an authenticated Laravel API and private Python symptom-assistant service.

**Development prototype; not clinically validated. Use synthetic symptom inputs. The dental data viewer also supports licensed public and de-identified research references.** No external AI key or model is configured. The interface reports **AI not configured** and offers limited, explicitly labeled rule-based intake, without AI explanations. The original questionnaire remains under **Scripted demo**. Test doubles are used only in tests.

## Local setup

Requirements: Node.js 22.12+, PHP 8.4+ with SQLite/OpenSSL/mbstring/DOM/curl/ZIP, Composer, and [uv](https://docs.astral.sh/uv/) for Python 3.12. The Composer lock uses Symfony 8 and requires PHP 8.4+.

```powershell
powershell -File scripts/setup.ps1
```

The setup script installs dependencies, preserves existing environments, generates matching internal service secrets without printing them, and migrates SQLite. It does not configure or enable a paid AI provider. Use `-SkipInstall` for existing dependencies. Run these commands in three separate terminals, starting from the project root:

```powershell
# Terminal 1
cd ai-service
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --no-access-log
# Terminal 2
cd backend
php artisan serve --host=127.0.0.1 --port=8000 --no-reload
# Terminal 3
cd frontend
npm run dev
```

Open http://127.0.0.1:5173. Create an account using a test email and a password of at least 12 characters. Acknowledge processing, select a body area and describe a synthetic symptom. Correct answer edits an earlier answer and removes derived later answers. Changing region or side starts fresh intake. Start over clears the on-screen draft. Save with consent is optional. Assessments/History show only the authenticated owner's saved records; deletion removes the saved record and invalidates the draft token.

## Teach and train a local dental outline model inside the app

Open `/#dental-cases` and **Teach your local model** to train an account-specific outline model. A separate public-data tooth detector can provide initial drafts before you create a personal teaching set. Your personal model takes precedence; it is never shared with other accounts.

The public detector is trained locally with YOLO11n on the [DentalMate6v RGB tooth-box dataset](https://universe.roboflow.com/dentalmate6v/intraoral-tooth-numbering-fdi/dataset/1), attributed under CC BY 4.0, using a fingerprinted [public mirror](https://huggingface.co/datasets/Frallex/FDI_Intraoral). Its 34 numbering labels are collapsed to one visible-tooth class. The pinned export has 2,541 training images (including supplied augmentations), 246 validation images and 120 test images. Patient identities, patient separation and independent annotation quality are unverified. This is experimental tooth localization, not a trained orthodontic-condition classifier. YOLO software/base weights use AGPL-3.0; preserve the applicable notices when distributing them.

To reproduce this training from `ai-service`, run `uv sync --group dental-training`, then `uv run --group dental-training python scripts/train-dental-public.py --download --epochs 30`. The optional group uses CUDA 12.8 PyTorch on Windows; ordinary inference needs only the existing OpenCV runtime. The script checks the dataset and official base-checkpoint SHA-256, checks exact/source-image overlap across the published splits, trains, evaluates boxes on the test split, and exports a single-class ONNX model. It does not use any app account photos. The completed model and actual run report are local ignored files at `ai-service/models/dental-public/detector.onnx` and `report.json`; trained weights/data are not bundled in Git. Set `DENTAL_PUBLIC_MODEL_DIR` to change this model directory. Missing or corrupted artifacts keep detection unavailable.

Inference runs offline in OpenCV: candidate tooth boxes seed per-image GrabCut boundaries. Those boundaries have **no supervised crown-mask validation** and need manual correction. The app does not present box scores as mask Dice or medical accuracy. Uploaded inference photos are not saved or used to update the detector. The shared baseline is separate from all account teaching data and models.

On Windows with the training dependencies already installed, `powershell -File scripts/train-dental-public.ps1 -Epochs 30 -Download` uses the managed Python interpreter with the project packages. This also supports machines whose application-control policy prevents starting the copied virtual-environment interpreter. Recent epoch progress appears through **Check local model**; detection remains disabled until the completed ONNX model and report are available. For a real-model browser integration check after training, run `node scripts/smoke-dental-public.mjs` from `frontend` while all services are running. It uses the downloaded public validation photo and creates a disposable test login, without saving the image to a teaching set.

1. Attach a permitted RGB dental photograph, outline every visible crown and have a dentist correct/review each boundary. Local refinement can help fit a rough boundary.
2. Sign in, enter coded subject/reviewer IDs and choose Training, Validation or Test. Keep all photographs and visits of one patient in the same partition.
3. Confirm complete annotation and explicit local photo-storage permission, then click **Save reviewed example locally**. A correction saved for the same re-encoded photo replaces its prior annotation.
4. Save examples from at least two training subjects and a different validation subject. This minimum exercises the software; it cannot establish medical accuracy. Reserve additional independent patients for testing.
5. Confirm training and click **Train local model**. The app shows checking, learning, validation and saving stages, then activates the account's model for draft detection. No terminal or API key is needed.

The teaching set remains available after reload, even with no photo attached. Its list supports removal. Removing or changing an example invalidates the account's saved model versions; retrain using the remaining/current examples. Changes during training discard that run's result. Training continues when the browser panel closes, but a service restart does not resume an interrupted run. Run one Python service process for this local background-job implementation.

Explicitly saved photos and labels persist in an account-scoped SQLite file under the ignored `ai-service/training-data/app` directory. They are local private files, not encrypted cloud storage. Set `DENTAL_LEARNING_DIR` on the private Python service to change this root. Laravel derives a scoped owner token from the authenticated account; browser-supplied owner IDs/paths are ignored. Account emails and raw user IDs are not forwarded to Python. Job/status responses contain only metadata and aggregate metrics, never image bytes. Inference does not save photos or update weights. Dataset examples and models are excluded from Git.

The CPU OpenCV random forest learns background, crown interiors and edges from colour/texture features. It checks subject separation, exact/near duplicates, photo fingerprints and polygon overlap; fits only training examples; and reports foreground Dice on separate validation/optional test images. This does not establish per-crown mask quality, diagnostic accuracy or treatment feasibility. It can miss or merge teeth, include non-tooth areas and cannot verify image type. Use ordinary dental RGB photos, correct every outline and assign its arch manually.

**Optional offline export:** the separate JSON export still includes an explicitly consented photo and reviewed polygons. For standalone research, `scripts/train-dental-local.ps1` and `ai-service/scripts/train-dental-local.py` remain available. Their operator model directory (`DENTAL_LOCAL_MODEL_DIR`, default `models/dental-local`) is separate from app accounts' teaching sets/models; the in-app button manages the account-specific model automatically.

The following optional provider belongs to the separate general symptom assistant; it is not used by local dental tools.

## Optional general symptom provider

Set these **only in `ai-service/.env`**, then restart Python:

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=your-server-key
OPENAI_MODEL=your-account-model-supporting-structured-outputs
ALLOW_EXTERNAL_AI=true
```

Keep Python SERVICE_KEY equal to Laravel AI_SERVICE_KEY; these are internal credentials distinct from the external AI key. No key belongs in Vue or a `VITE_` variable. No paid model call was made during implementation, so the credentialed provider path still requires integration evaluation. Unsupported/incomplete configuration remains disabled. `DecisionProvider` is the adapter boundary for additional providers using their official SDKs. The general symptom assistant has no training pipeline. Dental outline training is separate and local.

The OpenAI adapter uses its official Python SDK: `responses.parse(..., text_format=ModelDecision, store=False)`. [Official structured output documentation](https://developers.openai.com/api/docs/guides/structured-outputs).

## Architecture and privacy

```text
Vue chatbot -> Laravel /api -> private Python /v1/assess -> validated structured assessment
frontend/     dashboard, real rigged human, AI chat, explicit scripted demo
backend/      Laravel 13, Sanctum cookie auth/CSRF, owner-scoped encrypted records
ai-service/   FastAPI, Pydantic, independent triage rules, NHS retrieval, official SDK adapter
contracts/    shared assessment JSON Schema independently checked by Laravel
```

The full-stack repository is [mw31123039-ctrl/inetlligent-digital-twin](https://github.com/mw31123039-ctrl/inetlligent-digital-twin), including `frontend/`, `backend/`, `ai-service/`, `contracts/` and setup/review files. The root `.gitignore` excludes local credentials, databases, dependencies and generated archives.

The general symptom pipeline keeps drafts out of the Python database; explicitly saved dental teaching examples use the separate local SQLite store described above. Laravel passes no account email/name to Python or the provider. Draft health content stays in browser memory and an authenticated encrypted client-held token. Before save consent, Laravel stores only random session ID, owner ID, revision and expiry in `conversation_sessions`, without symptoms/body region. Tokens are owner-bound, expire after one hour, reject stale revisions, and are revoked by deletion. A lost network reply can leave a stale token; the UI asks for a new assessment rather than replaying an answer.

Saving requires consent and policy version `health-storage-v1`. Only then is a Laravel encrypted-array payload stored in `health_assessments`. Account email/password hashes, auth sessions and rate-limit metadata are separate. No active transcript/result is written to browser storage. Only the chat-mode preference is in sessionStorage; explicitly consented scripted-demo saves remain browser-local. Saved snapshots are read-only; start a new conversation for further answers.

Application deletion removes primary records and clears the current screen; it does not promise deletion from external-provider retention, backups or user exports. `store=False` is not a zero-retention guarantee. Review provider processing terms before external AI is enabled. Laravel reports API exception class only, without request/SQL/upstream content; Python HTTP/provider debug and access logs are suppressed. Infrastructure logging/APM still needs review.

The Vite development proxy forwards `/api` and `/sanctum` to Laravel. Production needs HTTPS, secure cookies, the correct Sanctum first-party domains, an equivalent reverse proxy, and private access to Python. Run Laravel's scheduler (`schedule:run`) to prune expired non-health session metadata hourly.

## Safety and evidence

- `ai-service/app/rules/triage.v1.json` contains **draft, unvalidated English rules**, separately versioned and linked to NHS references. Screening runs throughout the conversation before retrieval/model calls. Urgent matches stop normal questions and return immediate guidance. Corrections cannot silently downgrade previously raised urgent guidance.
- Facts require exact user-message quotes. AI explanations are constrained to current-region allowlisted NHS pages actually retrieved, with verified excerpts and a reported-symptom overlap check. These checks establish provenance, **not clinical entailment or validation**. Retrieval failure is explicit; no sources are invented. Urgent guidance bypasses retrieval so it is not delayed.
- The model selects relevant question fields and uncertain explanation candidates. It cannot inject unrestricted diagnostic prose, personal probability percentages, prescriptions or dosages. The app formats conservative uncertainty and next actions. Reported diagnoses remain user-reported facts.
- Pydantic validates decisions and results; Laravel validates the final result against the shared schema. Provider refusal, timeout, malformed data, source failure and missing credentials lead to honest limited-intake/unavailable states.

Read [CLINICAL_REVIEW.md](CLINICAL_REVIEW.md) before considering real patient use.

## Tests

```powershell
cd ai-service
.venv/Scripts/python.exe -m pytest -q
cd ../backend
php artisan test --compact
cd ../frontend
npm run build
npm test
npm run test:e2e
```

Install Chromium with `npx playwright install chromium` if needed. Full-stack browser tests require all three services and run only with AI disabled; no paid calls occur. Unit tests use test-only provider/source doubles. Tests cover context, follow-ups, corrections, urgency, insufficient information, unsupported explanations, malformed outputs, failures, consent, encryption, deletion, isolation and the existing body viewer. Passing software tests does not establish clinical performance.

Human model/license: [asset attribution](frontend/ASSET_ATTRIBUTIONS.md). All required reference models and textures are bundled. Existing zip/tar deployment archives remain older frontend snapshots, not updated releases.
