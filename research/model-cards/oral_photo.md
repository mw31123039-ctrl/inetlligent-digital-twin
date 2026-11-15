# Model card: Oral: mouth lesion photograph classifier

*Model version `oral-resnet18-mendeley-v1` · weights SHA-256 `f9b99f053b2d73fd…` · evaluated 2026-11-16 with `ai-service/scripts/evaluate-cancer-models.py`.*

## Intended use

Education and research demonstration inside the HumanTwin workspace: showing how an image classifier responds to one prepared image, with its confidence, an explanation map and its limits. **Not intended** for diagnosis, screening, triage or treatment decisions, and not a substitute for examination by a clinician.

## Model

- **Architecture:** ResNet-18 (ImageNet initialisation), trained by this project with scripts/train-oral-cancer.py (seed 42, selected epoch 5 by validation balanced accuracy).
- **Source:** Trained locally; training report in ai-service/models/cancer/oral_photo/report.json.
- **Licence:** Model trained by the project; images from the Mendeley Oral Images Dataset v2 (Chandrashekar et al., CC BY 4.0).
- **Classes (output order):** benign_lesion, malignant_lesion
- **Classes counted as cancer in the binary view:** malignant_lesion

## Data

- **Training data:** 323 original photographs (165 benign, 158 malignant lesions), split by near-duplicate image group into 226 train / 49 validation / 48 test images. Augmented copies in the archive were not used.
- **Evaluation data:** Mendeley Oral Images Dataset v2 (Chandrashekar et al., CC BY 4.0), fixed image-group split from training: validation split for calibration, test split for metrics. The test split was inspected during earlier development (research/CANCER_MODEL_IMPROVEMENT.md), so it is not a new blind test.
- **Test split:** 48 images (benign_lesion: 25, malignant_lesion: 23).

## Input and preprocessing

- **Accepted input:** One close-up colour photograph of a visible lesion inside the mouth.
- **Preprocessing:** RGB; exact resize to 224 x 224 with antialiased bilinear interpolation (torchvision on PIL images); scale 1/255; ImageNet mean and std.
- **Parity:** the service tensor matches the model's own reference pipeline within 1e-5 (`ai-service/tests/test_cancer_preprocessing.py`).
- **Explanation:** Grad-CAM on the last convolutional block (7 x 7 grid); class-specific. For this global-average-pool + linear head it equals the class activation map.

## Measured performance (held-out test split)

| Metric | Value (95% CI) |
|---|---|
| Accuracy | 85.4% (72.8-92.8) |
| Balanced accuracy | 85.5% |
| Macro F1 | 0.854 |
| Sensitivity (cancer vs not) | 87.0% (67.9-95.5) |
| Specificity (cancer vs not) | 84.0% (65.3-93.6) |
| AUC (cancer vs not) | 0.894 |
| F1 (cancer vs not) | 0.851 |

Full tables, the confusion matrix and charts: [`research/cancer-evaluation/oral_photo/metrics.md`](../cancer-evaluation/oral_photo/metrics.md).

## Confidence, "inconclusive" and input checks

- Temperature scaling fitted on 49 calibration images: T = 0.7421; expected calibration error on the test split 0.117 before and 0.083 after.
- A finding is shown only when the calibrated top-class probability is at least 0.65; otherwise the result is inconclusive (8.3% of test images; accuracy 86.4% when answered).
- Wrong-area and synthetic images: 181 of 184 were rejected by the input checks or reported as inconclusive; 3 would still receive a finding.

## Known limitations

- There is no "normal mouth" class: every image is treated as showing a lesion.
- No patient identifiers exist, so splits are by image group, not by patient.
- The 48-image test set gives wide confidence intervals and was inspected during earlier development.
- All photographs come from one published collection; other cameras, lighting and populations are untested.
- Confidence is a property of the model, not a personal probability of cancer. Results are research output and have no clinical validation.
