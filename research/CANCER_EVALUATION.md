# Cancer image models: evaluation, calibration and explainability

This note documents how the four image models in the Cancer research module were evaluated and how
their confidence, "inconclusive" decision, input checks and heatmaps work. Results tables and
charts are generated, not hand-written: see `research/cancer-evaluation/` and the model cards in
`research/model-cards/`.

## 1. Pipeline (upload to report)

1. **Browser** (`frontend/src/cancer/model.ts`, `readResearchImage`): checks type (JPEG/PNG) and size,
   reads the header dimensions before decoding, draws the image on a white background, downsizes
   to at most 2,048 px with high-quality smoothing, re-encodes as JPEG (quality 0.95, which also
   strips metadata) and hashes it (SHA-256).
2. **Laravel** (`backend/app/Http/Controllers/CancerResearchController.php`): authentication,
   consent flags, JPEG marker check, forwards only the whitelisted fields to the AI service, then
   validates the answer against `contracts/cancer-result.schema.json` and re-checks the outcome
   rules (`backend/app/Services/CancerResultContract.php`). The result is kept for 30 minutes,
   encrypted, so the user can save exactly that output to History.
3. **AI service** (`ai-service/app/cancer.py`, `infer_cancer`):
   decode JPEG → input checks (`cancer_quality.py`) → if rejected, stop → preprocessing from the
   manifest → ONNX Runtime (CPU) → temperature scaling and familiarity check
   (`cancer_calibration.py`) → heatmap (`cancer_explain.py`) → outcome.
4. **Frontend report** (`CancerResultCard.vue`, `report.ts`): finding, calibrated confidence with the
   decision threshold, heatmap overlay, plain-language meaning, suggested next step, link to the
   knowledge guide, image checks, save to History and PDF export (browser print dialog).

## 2. Outcomes

| Outcome | When | What the user sees |
|---|---|---|
| `input-rejected` | An input check with severity `reject` fired (for example a colour photograph sent to the CT model, a grayscale image sent to the dermoscopy model, a blank image). The model is not run. | "Image not accepted", the reason, and what to upload instead. |
| `inconclusive` | Any of: a `limiting` input check (severe blur, very dark, mostly white, colour overlay on a scan); calibrated top-class probability below the model's decision threshold; image unlike the model's reference images (familiarity check). | "Inconclusive", the reasons, the closest category marked as *not* a finding. |
| `finding` | None of the above. | The category in plain language, confidence, heatmap and next step. |

## 3. Preprocessing parity

Each model's test-time preprocessing was re-derived from its own sources (Hugging Face
`preprocessor_config.json` for the two ViTs, the training code for the EfficientNet and ResNet)
and compared numerically with the service tensor. `ai-service/tests/test_cancer_preprocessing.py`
asserts agreement within 1e-5 against `transformers.ViTImageProcessor` (dermoscopy, breast) and the
torchvision training transform (lung, oral). All four already matched: exact 224 x 224 resize
with antialiased bilinear interpolation (no centre crop), scale 1/255, per-model mean and std,
RGB with grayscale replicated. The only browser-side change is high-quality smoothing when a large
upload is downscaled, so it behaves like the antialiased resize used in training.

## 4. Evaluation protocol

Script: `ai-service/scripts/evaluate-cancer-models.py`. Every image passes through the same path
as the app (browser-style JPEG preparation, `decode_image`, input checks, `prepare_input`, the
installed ONNX file). Model files are only read.

| Model | Calibration split (fitting only) | Test split (reported) | Why this data |
|---|---|---|---|
| Skin (dermoscopy ViT) | ISIC 2018 Task 3 validation, 193 images | ISIC 2018 Task 3 test, 1,512 images | The model was fine-tuned on HAM10000 (the challenge training set); validation and test were released separately. |
| Oral (ResNet-18) | Project validation split, 49 images | Project test split, 48 images | Fixed image-group split from training. The test split was inspected during earlier development. |
| Lung (EfficientNet-B0) | 40% of the author's 165-image held-out split, by near-duplicate cluster | Remaining 60% (98 images) | The author's own held-out images; the public dataset's original "test" folder overlaps the training pool. |
| Breast (ViT) | 30% of BUS-BRA, by patient | 70% of BUS-BRA (1,310 images, 752 patients) | External data (Brazil) rather than BUSI, which the model was trained on. BUS-BRA has no "normal" images. |

Metrics on the test split (argmax decision): accuracy, balanced accuracy, macro F1, per-class
sensitivity/specificity/precision/F1/one-vs-rest AUC, confusion matrix, and a binary "cancer vs not"
view (sensitivity, specificity, F1, AUC). Intervals: Wilson score (95%) for proportions; bootstrap
with 2,000 resamples for AUC. Calibration: expected calibration error (15 bins), negative
log-likelihood and multiclass Brier score, before and after temperature scaling.

**Fitted on the calibration split only:**
- *Temperature* minimising negative log-likelihood (golden-section search on log T).
- *Decision threshold*: the value in 0.50-0.95 (step 0.05) with the highest accuracy among answered
  images while answering at least 75% of the calibration images.
- *Familiarity reference*: per-class centroids of L2-normalised image embeddings (global-average-pooled
  feature map for the CNNs, CLS token for the ViTs); the minimum similarity is the 2nd percentile of
  the calibration images. Images below it are reported as "unfamiliar" (inconclusive).

The fitted values are stored in `ai-service/calibration/cancer-calibration.json`, keyed by the
SHA-256 of the model weights; an entry is ignored if the weights, version or labels change.

**Wrong-input analysis:** 60 test images from each of the other three datasets plus synthetic images
(noise, gradient, a coloured scene, gray noise) are passed to each model; the report counts how many
are rejected, flagged unfamiliar, or would still receive a finding.

## 5. Explainability

| Model family | Method | Notes |
|---|---|---|
| ResNet-18, EfficientNet-B0 (global average pooling + linear head) | Grad-CAM | For this head Grad-CAM's channel weights equal the classifier weights divided by the number of positions, so the map is `ReLU(W[c] · F)` on the last feature map (7 x 7). Computed without gradients from an extra ONNX output added in memory. At load time the head is replayed in NumPy and must reproduce the graph's logits, otherwise the method is disabled. |
| ViT-Base (CLS token) | Attention rollout | Head-averaged attention of all 12 layers with the residual identity, multiplied through; CLS-to-patch row on the 14 x 14 grid. Not class-specific. |
| Any other graph | Occlusion sensitivity | 4 x 4 patch occlusion, the original method, kept as a fallback. |

Heatmaps show model behaviour, not tumour boundaries; the result card and PDF say so.

## 6. Input checks

Rule-based measurements in `ai-service/app/cancer_quality.py` (no model): contrast, brightness,
share of saturated colour pixels, share of pure-white pixels, sharpness (variance of the Laplacian at
512 px) and a conservative frontal-face detector (privacy warning). Thresholds were set so that none
of the 323 local oral photographs and none of the installed verification images is rejected or
limited (`ai-service/tests/test_cancer_quality.py`), and so that colour/grayscale mismatches between
areas are rejected. On the held-out test splits above, no in-area image was rejected by these
checks (see "Input checks and familiarity" in each `metrics.md`).

## 7. Limitations to state in the thesis

- These are research evaluations on public datasets, not clinical validation.
- Oral and lung test sets are small (48 and 98 images); intervals are wide.
- The breast model's malignant sensitivity drops to about 44% on external data (domain shift).
- Skin results are for dermoscopy images from the ISIC archive; phone photographs and darker skin
  types are not represented.
- Splits are by image group, cluster or patient as available; the oral data has no patient IDs.
- Confidence is calibrated on one dataset per model and may not transfer to other devices.

## 8. Reproduce

```powershell
cd ai-service
# The venv's python.exe is blocked by Application Control on this machine; use the managed interpreter:
$env:PYTHONPATH = "$PWD\.venv\Lib\site-packages"
$py = "$env:APPDATA\uv\python\cpython-3.12-windows-x86_64-none\python.exe"
& $py scripts/evaluate-cancer-models.py --download            # once: ISIC 2018, LungCancer4Types + author split, BUS-BRA (~730 MB)
& $py scripts/evaluate-cancer-models.py --write-calibration   # about 15 minutes on CPU
& $py scripts/evaluate-cancer-models.py --cards-only          # regenerate model cards from metrics.json
```

Dataset licences: ISIC 2018 (CC BY-NC 4.0), LungCancer4Types (Apache-2.0), BUS-BRA (CC BY 4.0),
Mendeley Oral Images v2 (CC BY 4.0). Downloads are stored in the git-ignored
`ai-service/training-data/cancer-eval/`.
