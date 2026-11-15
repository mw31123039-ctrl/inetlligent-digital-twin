# HumanTwin private Python service

## Measured model improvement

Reusable upgrade checks now cover binary and multiclass image models: verified cohort identities, known duplicate/patient overlap, per-class confidence intervals, score uncertainty, strict measured-regression rules, artifact binding, exclusive release locking, backup journals and tested rollback. Use `python scripts/review-cancer-upgrade.py --help`; [the operator guide and real rejection evidence](../research/CANCER_UPGRADE_GUARDS.md) describe the input and policy. Missing patient identifiers block automatic activation. The training workflow's `--activate` option now uses this stricter reviewer.

`python scripts/improve-cancer-models.py` trains a bounded, fingerprinted public-data oral-model experiment on the available GPU, compares an EfficientNet-B0 candidate and its ensemble with the installed baseline, and exports the validation-selected candidate. `--activate` only activates a candidate that passes both predeclared development gates; the previous model is preserved for rollback. The historical split is reused as an activation veto and is explicitly development evidence, not independent clinical validation. No user uploads or account records are used. The 13 November run was rejected for worse malignant-label recall on the historical audit; the installed classifier remains active.

`python scripts/evaluate-cancer-knowledge.py --split all` measures synthetic source navigation separately from image performance. Explicit cancer/organ names now reorder only the encoder's already-relevant three matches, preserving real cosine scores. See [the measured run and limitations](../research/CANCER_MODEL_IMPROVEMENT.md) and [its results](../research/cancer-improvement-results-2026-11-13.json). Neither a high synthetic retrieval score nor additional training establishes clinical accuracy.

## Local cancer knowledge AI

Run `uv sync --all-groups`, then `uv run python scripts/install-cancer-knowledge.py` from this directory. The explicit installer downloads a pinned Apache-2.0 MiniLM sentence encoder and verifies the ONNX SHA-256 plus tokenizer Git-blob fingerprint. Inference downloads nothing and uses ONNX Runtime CPU and the core `tokenizers` package. Set `CANCER_KNOWLEDGE_MODEL_DIR` to change the default `models/cancer-knowledge` artifact directory.

`GET /v1/cancer/knowledge-status` and `POST /v1/cancer/knowledge` require the private service key. Laravel exposes sanitized readiness at `/api/cancer/knowledge-status` and an authenticated, rate-limited `/api/cancer/knowledge` question endpoint. Questions require explicit local permission, are bounded to 600 characters, are never stored or used for training, and are not sent to an external provider. Existing health-content logging precautions still apply to infrastructure.

The actual encoder indexes `contracts/cancer-knowledge.v1.json`: 16 cancer overviews plus four evidence/help records, sourced from 29 checked NCI/NHS URLs. It computes attention-masked, mean-pooled normalized vectors and returns up to three approved source IDs with cosine similarity. The UI renders source text from the shared corpus, not unrestricted model-generated advice. The independent JSON Schema, Laravel question hash and frontend record allowlist reject invented IDs, diagnoses, privacy claims or mismatched questions. A general embedding model and a relevance threshold do not establish clinical accuracy or disease risk. Missing models leave browsing available without fabricated AI answers.

Source review, scope and limitations: [Cancer care review](../research/CANCER_CARE_REVIEW.md). Run `python -m pytest tests/test_cancer_knowledge.py -q`, Laravel's `CancerKnowledgeTest`, and `node scripts/smoke-cancer-care.mjs` from `frontend` with all services running for real-model browser checks.

## Cancer research models

Four real research classifiers are installed on this computer. Weights and downloaded data are ignored by Git; another checkout must reproduce their installation/training.

| Input | Learned model and source | Evidence limits |
| --- | --- | --- |
| Dermoscopy | Seven-class quantized ViT, [pinned ONNX export](https://huggingface.co/sazio/skin-mole-vit-onnx/tree/25be9e61a71125de9502648c1f6adceb7a882637) | HAM10000 dermoscopy; not ordinary phone photos. Independent patient validation is unverified. |
| Breast ultrasound | Three-class ViT, [pinned source](https://huggingface.co/hugging-science/breast-cancer-detector-2/tree/257147b35a8d94aca77a556a374bf9260976a453) | Benign/malignant/normal dataset categories. Patient separation and external validity unverified. Not mammography or MRI. |
| Lung CT slice | Four-class EfficientNet-B0, [pinned source](https://huggingface.co/yunussgultekiin/lung-cancer-efficientnet-b0/tree/506c398b6fd10b3e9f046c908c2b59bb33547faf) | Adenocarcinoma/large-cell/normal/squamous-cell dataset categories on slices. No pathology confirmation, staging or full-volume inference is established. Source audit documents duplication and absent patient IDs. |
| Oral photograph | ResNet18 trained locally on [Mendeley Oral Images Dataset v2](https://data.mendeley.com/datasets/mhjyrn35p4/2), CC BY 4.0 | Benign **lesions** vs malignant **lesions**. No normal-mouth class or independent patient validation. |

Reproduce from `ai-service`:

```powershell
uv sync --all-groups
uv run --group cancer-models python scripts/install-cancer-models.py
uv run --group cancer-models python scripts/train-oral-cancer.py --download
```

On this Windows machine the copied virtual-environment executable is blocked by application control. The working alternative is the managed Python returned by `uv python find 3.12`, with `PYTHONPATH` set to this service's `.venv/Lib/site-packages`. No external model API key or paid call is needed. The installer uses pinned HTTPS revisions and SHA-256, preserves source cards/configuration/license notices, executes no repository-provided Python, and checks real ONNX execution before activation. Conversion uses safe tensors or `torch.load(weights_only=True)`, locally defined known architectures, and numeric source/export parity checks.

The oral run used 323 originals (165 benign-lesion, 158 malignant-lesion), ignored supplied augmented copies, and grouped exact/perceptual duplicates before a fixed 226/49/48 train/validation/test split. One near-duplicate pair was kept together. Validation selected epoch 5 of 11. The untouched 48-image test confusion matrix (actual rows, predicted columns; benign then malignant) was `[[21,4],[3,20]]`: accuracy 85.42%, malignant-image recall 20/23, benign-image recall 21/25. These are **image-level results on this small dataset**, not independent-patient accuracy. Patient separation/counts remain `null` in the manifest. Actual split records, training history, attribution, test metrics and ONNX parity remain in ignored `training-data/cancer-oral` and `models/cancer/oral_photo/report.json`. No app/account images were used.

### Result contract v2: input checks, calibrated confidence, "inconclusive" and heatmaps

Results use `humantwin-cancer-result-v2` (`contracts/cancer-result.schema.json`, regenerated by `scripts/export-schema.py`). Every request first runs rule-based input checks (`app/cancer_quality.py`: colour vs grayscale for the selected area, blank, very dark, mostly white, severe blur, small or elongated images, a possible face). A `reject` check returns `outcome: "input-rejected"` without running the model. Otherwise the model runs and the result is `finding` only when no `limiting` check fired, the temperature-scaled top-class probability reaches the model's decision threshold and the image resembles the model's reference images; else it is `inconclusive` with `outcome_reasons`. Temperature, threshold and the familiarity reference come from `calibration/cancer-calibration.json` (written by `scripts/evaluate-cancer-models.py --write-calibration`, keyed by the weights SHA-256; set `CANCER_CALIBRATION_PATH` to move it). Without an entry the default threshold is 0.6 and confidence is labelled uncalibrated.

With `explain: true` the result includes a heatmap grid: Grad-CAM on the last feature map for the ResNet and EfficientNet models, attention rollout for the two ViTs (`app/cancer_explain.py`, computed from extra ONNX outputs added in memory; model files are not modified). Graphs without a supported head fall back to 4 x 4 occlusion sensitivity. Heatmaps show model behaviour, never tumour location. Preprocessing parity with each model's reference pipeline is tested in `tests/test_cancer_preprocessing.py`.

Held-out evaluation, calibration fitting and model cards: `scripts/evaluate-cancer-models.py` (see [research/CANCER_EVALUATION.md](../research/CANCER_EVALUATION.md), results in `research/cancer-evaluation/`, cards in `research/model-cards/`). Saved reports (History) are stored by Laravel, encrypted per user, only for a result the server itself returned to that user within 30 minutes.

Functionality checks use public reference images and do not measure independent clinical accuracy. Source/rights manifests remain beside ignored `models/cancer/verification` images and oral held-out examples. From `frontend`, `node scripts/smoke-cancer-real.mjs` exercises actual uploads through Laravel/Python for all four models, including measured outputs, fingerprints, overlays and mobile layout. All services and the downloaded reference images must be present; these images are intentionally excluded from Git. The default URL is `http://127.0.0.1:5173`, matching the configured first-party auth origin. This check creates a disposable local test login and does not save image assessments.

`GET /v1/cancer/status` and `POST /v1/cancer/analyze` require the existing private `X-Service-Key`. Laravel exposes a public, sanitized readiness endpoint at `/api/cancer/status`; inference at `/api/cancer/analyze` requires an authenticated account, rate limits and three explicit acknowledgements. No identity, subject code or history is forwarded to Python. Inference does not save images or train/update weights, and makes no external-provider calls. Missing, corrupt, incompatible or fingerprint-mismatched models fail closed without scores.

The local machine's model artifacts are under `CANCER_MODEL_DIR` (default `models/cancer`), using one directory per input:

| Pathway | Model directories |
| --- | --- |
| Skin | `skin_photo`, `dermoscopy` |
| Oral | `oral_photo` |
| Lung | `lung_ct_slice` |
| Breast | `mammogram`, `breast_ultrasound`, `breast_mri_slice` |

Each directory needs `model.onnx` and `manifest.json`. Do not install the untrained test fixture as a medical model. Only fingerprinted operator files are loaded; there is no browser model-upload API. The explicit installer downloads pinned source artifacts; inference never downloads models. Model files and datasets are ignored by Git. The environment variable is separate from the general symptom-provider configuration and dental models.

The adapter supports a single NCHW float32 image input, explicit stretch resizing, RGB or grayscale with explicit OpenCV-linear or PIL-bilinear interpolation, and an output vector shaped `[classes]` or `[1, classes]`. Preprocessing is `(pixel * scale - mean) / std`, in manifest channel order. Output must contain mutually exclusive class logits or a finite normalized class-score vector with 2–20 entries. Multi-label, segmentation, detection, multiple inputs/outputs, 3D and other preprocessing require a different adapter. Runtime is explicit (`opencv` or `onnxruntime`); the installed neural networks use ONNX Runtime CPU. Model loading and a dry forward pass must succeed before readiness becomes `configured-unvalidated`. No supplied evaluation report is independently verified by the application; manifest provenance and metrics are operator declarations, not clinical approval. Unknown evaluation fields remain `null`.

Example manifest structure (all placeholder provenance and numbers **must** be replaced with the actual model's evidence; this example is not evidence or a usable model):

```json
{
  "schema_version": "humantwin-cancer-model-v1",
  "track": "skin",
  "modality": "skin_photo",
  "model_version": "your-evaluated-model-v1",
  "target": "The exact research classification target",
  "source_url": "https://example.org/replace-with-model-source",
  "license": "Replace with the actual model license",
  "weights_sha256": "replace-with-the-64-character-sha256-of-model.onnx",
  "input_size": [224, 224],
  "color": "RGB",
  "resize": "stretch",
  "scale": 0.00392156862745098,
  "mean": [0.485, 0.456, 0.406],
  "std": [0.229, 0.224, 0.225],
  "labels": ["replace-first-output-label", "replace-second-output-label"],
  "output": "logits",
  "evaluation": {
    "reference": "Replace with the independent patient evaluation report",
    "patient_disjoint": null,
    "held_out_subjects": null,
    "sensitivity": null,
    "specificity": null
  },
  "research_only": true,
  "runtime": "onnxruntime",
  "interpolation": "pil-bilinear"
}
```

The input is a browser-re-encoded JPEG (32–2048 pixels per side; maximum 1.5 million data-URL characters). Re-encoding strips file metadata but cannot remove identifiers burned into image pixels. Check that the exact export and re-encoding pipeline matches the model's evaluation. CT/MRI entries accept only prepared 8-bit slice exports: no Hounsfield-unit processing, DICOM windowing, full-volume coverage, sequencing, staging or localization is claimed. Mammography support is likewise a single prepared image, not a clinical multi-view workflow. Ordinary skin photos and dermoscopy are separate model inputs. The adapter relies on the operator/user's input-type confirmation; it cannot verify anatomical content or image quality.

The result includes input/model SHA-256, model version, target and raw class scores. Laravel independently validates the shared JSON Schema and image binding. Vue also checks the result against the last inspected model version/hash and refuses mismatches. Scores are never labeled as calibrated cancer probabilities, a negative screen or a diagnosis. Symptoms/history are recorded locally for review, not analyzed by the image classifier. Matching a coded twin subject only adds an explicit relationship to the exported research record; no cancer inference is inserted into physiological measurements.

Software verification: `python -m pytest tests/test_cancer.py -q`, Laravel's `CancerResearchTest`, frontend `cancer.test.ts`, and `node scripts/smoke-cancer.mjs` after building/serving the frontend. The 343-byte ONNX fixture in `tests/fixtures/` is an **untrained color classifier** used to exercise actual OpenCV inference for every modality. Passing tests provides no evidence of cancer detection accuracy.

Source references in the interface: [NCI skin](https://www.cancer.gov/types/skin/patient/skin-screening-pdq), [oral](https://www.cancer.gov/types/head-and-neck/patient/oral-screening-pdq), [lung](https://www.cancer.gov/types/lung/patient/lung-screening-pdq), [breast](https://www.cancer.gov/types/breast/screening), and [diagnosis](https://www.cancer.gov/about-cancer/diagnosis-staging/diagnosis). These describe clinical context; they do not validate this module.

See the root README and CLINICAL_REVIEW.md. FastAPI requires `X-Service-Key` for Laravel requests. General symptom inference remains stateless; explicitly consented dental teaching uses private account-scoped SQLite files. Bind only to loopback/private networking.

```powershell
uv sync --frozen --python 3.12
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --no-access-log
.venv/Scripts/python.exe -m pytest -q
```

The root setup script creates matching internal service keys. The separate general symptom provider optionally uses AI_PROVIDER, OPENAI_API_KEY, OPENAI_MODEL and ALLOW_EXTERNAL_AI. Dental tools never use an external provider. Restart after environment/rule changes. No test provider is used during normal execution.

- `app/schemas.py`: strict decisions, facts, sources and assessment contract.
- `app/engine.py`: verbatim evidence validation, questions and guarded explanations.
- `app/triage.py`, `app/rules/triage.v1.json`: independent draft warning rules.
- `app/evidence.py`: bounded allowlisted NHS retrieval, host-restricted redirects, public-text-only cache.
- `app/provider.py`: official SDK adapter and provider protocol.

POST `/v1/assess` receives region, side, trusted history and prior urgency from Laravel. GET `/health` reports availability/configuration only. Both require the service key. Validation errors do not echo inputs and provider exceptions are not logged.

Regenerate the shared schema after changing Assessment with `.venv/Scripts/python.exe scripts/export-schema.py`; tests detect drift. Laravel independently checks that schema. No credentialed model call has been verified; test doubles do not establish clinical performance.

Dental local tools: /v1/dental/segment fits one user-drawn crown with GrabCut. /v1/dental/detect first uses the account's own trained forest, or the separate operator forest for ownerless internal calls. If none is trained, it uses the experimental public-data ONNX tooth detector at DENTAL_PUBLIC_MODEL_DIR (default models/dental-public), with per-box GrabCut refinement. Both require local-processing consent and the internal service key. Train the public model with `uv sync --group dental-training` and `python scripts/train-dental-public.py --download --epochs 30`; see the root README for source/license/validation limits. The Windows helper `scripts/train-dental-public.ps1` uses the installed managed interpreter and project dependencies. No dental weights are bundled in Git. Status does not claim clinical validation or supervised mask accuracy for the public detector. Ordinary inference saves no photo and updates no model.

In-app teaching uses /v1/dental/learning with authenticated owner headers derived by Laravel, local SQLite under DENTAL_LEARNING_DIR, and a single background worker. It saves examples only on explicit teaching consent and starts training only on a separate request. Run one Uvicorn worker. Models/inference are account-scoped; standalone CLI/operator models remain separate. Teaching status never includes photo bytes. Data changes invalidate saved model versions and discard in-flight results. See root README for the browser workflow.

Orthodontic screening annotations use owner-scoped /v1/dental/screening/cases (GET/POST) and /{case_id} (GET/DELETE), the strict screening-case schema, and separate SQLite case tables. Every patient visit remains in one split across this store and crown teaching. Explicit photo/storage/research rights are required. There is no orthodontic condition classifier; saves never invoke training. Taxonomy review remains pending and recorded review is self-attested.
