# Model card: Breast: ultrasound image classifier

*Model version `busi-vit-257147b3-onnx` · weights SHA-256 `71cc8f91d8329332…` · evaluated 2026-11-16 with `ai-service/scripts/evaluate-cancer-models.py`.*

## Intended use

Education and research demonstration inside the HumanTwin workspace: showing how an image classifier responds to one prepared image, with its confidence, an explanation map and its limits. **Not intended** for diagnosis, screening, triage or treatment decisions, and not a substitute for examination by a clinician.

## Model

- **Architecture:** Vision Transformer (ViT-Base/16), fine-tuned by the upstream author; exported to ONNX locally with numerical parity checks.
- **Source:** hugging-science/breast-cancer-detector-2 (revision 257147b3), Hugging Face.
- **Licence:** Apache-2.0 (model card); BUSI dataset CC BY 4.0 (Al-Dhabyani et al. 2020).
- **Classes (output order):** benign, malignant, normal
- **Classes counted as cancer in the binary view:** malignant

## Data

- **Training data:** BUSI breast ultrasound images (Egypt; benign, malignant and normal), with 20% label noise deliberately added by the author.
- **Evaluation data:** BUS-BRA (Gomez-Flores et al. 2024, Zenodo 10.5281/zenodo.8231412, CC BY 4.0): 1,875 biopsy-proven breast ultrasound images from 1,064 patients in Brazil, external to the model's training data (BUSI). Split by patient: 30% calibration, 70% test. BUS-BRA has no "normal" images, so the model's normal class is never correct here.
- **Test split:** 1310 images (benign: 887, malignant: 423, normal: 0).

## Input and preprocessing

- **Accepted input:** One breast ultrasound image (not a mammogram or MRI).
- **Preprocessing:** RGB (grayscale replicated); exact resize to 224 x 224 with antialiased bilinear interpolation (PIL); scale 1/255; normalise with mean 0.5 and std 0.5.
- **Parity:** the service tensor matches the model's own reference pipeline within 1e-5 (`ai-service/tests/test_cancer_preprocessing.py`).
- **Explanation:** Attention rollout over the 12 encoder layers (14 x 14 patch grid); not class-specific.

## Measured performance (held-out test split)

| Metric | Value (95% CI) |
|---|---|
| Accuracy | 76.2% (73.8-78.4) |
| Balanced accuracy | 67.6% |
| Macro F1 | 0.694 |
| Sensitivity (cancer vs not) | 43.5% (38.9-48.3) |
| Specificity (cancer vs not) | 92.8% (90.9-94.3) |
| AUC (cancer vs not) | 0.817 |
| F1 (cancer vs not) | 0.548 |

Full tables, the confusion matrix and charts: [`research/cancer-evaluation/breast_ultrasound/metrics.md`](../cancer-evaluation/breast_ultrasound/metrics.md).

## Confidence, "inconclusive" and input checks

- Temperature scaling fitted on 565 calibration images: T = 1.3082; expected calibration error on the test split 0.111 before and 0.057 after.
- A finding is shown only when the calibrated top-class probability is at least 0.75; otherwise the result is inconclusive (24.9% of test images; accuracy 82.8% when answered).
- Wrong-area and synthetic images: 162 of 172 were rejected by the input checks or reported as inconclusive; 10 would still receive a finding.

## Known limitations

- On the external BUS-BRA dataset (Brazil, different devices) it misses more than half of the cancers: this is a domain shift that the in-domain benchmark hides.
- The "normal" class could not be evaluated externally because BUS-BRA contains only biopsied lesions.
- Grayscale CT slices are not always recognised as the wrong image type.
- Not suitable for screening or for deciding whether a lump needs a biopsy.
- Confidence is a property of the model, not a personal probability of cancer. Results are research output and have no clinical validation.
