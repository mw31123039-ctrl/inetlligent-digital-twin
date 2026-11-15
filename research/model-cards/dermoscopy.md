# Model card: Skin: dermoscopy lesion classifier

*Model version `ham10000-vit-q8-25be9e61` · weights SHA-256 `85c5c07ec67e94d7…` · evaluated 2026-11-16 with `ai-service/scripts/evaluate-cancer-models.py`.*

## Intended use

Education and research demonstration inside the HumanTwin workspace: showing how an image classifier responds to one prepared image, with its confidence, an explanation map and its limits. **Not intended** for diagnosis, screening, triage or treatment decisions, and not a substitute for examination by a clinician.

## Model

- **Architecture:** Vision Transformer (ViT-Base/16), fine-tuned; installed as an 8-bit dynamically quantised ONNX export.
- **Source:** ONNX export sazio/skin-mole-vit-onnx (revision 25be9e61) of Anwarkh1/Skin_Cancer-Image_Classification (Hugging Face).
- **Licence:** MIT for the ONNX repository; HAM10000 images are CC BY-NC 4.0 (non-commercial).
- **Classes (output order):** benign_keratosis-like_lesions, basal_cell_carcinoma, actinic_keratoses, vascular_lesions, melanocytic_Nevi, melanoma, dermatofibroma
- **Classes counted as cancer in the binary view:** melanoma, basal_cell_carcinoma, actinic_keratoses

## Data

- **Training data:** HAM10000 (10,015 dermoscopic images, 7 diagnostic categories, mostly from Austria and Australia). The exact training split was not published.
- **Evaluation data:** ISIC 2018 Task 3 (HAM10000 challenge; CC BY-NC 4.0, attribution: ISIC Archive, Tschandl et al. 2018, Codella et al. 2019): official validation set (193 images) for calibration and official test set (1,512 images) for metrics. The model was fine-tuned on HAM10000, i.e. the challenge training set; the validation and test images were released separately.
- **Test split:** 1512 images (benign_keratosis-like_lesions: 217, basal_cell_carcinoma: 93, actinic_keratoses: 43, vascular_lesions: 35, melanocytic_Nevi: 909, melanoma: 171, dermatofibroma: 44).

## Input and preprocessing

- **Accepted input:** One dermoscopy image of a single skin lesion (not an ordinary phone photograph).
- **Preprocessing:** RGB; exact resize to 224 x 224 with antialiased bilinear interpolation (PIL); scale 1/255; normalise with mean 0.5 and std 0.5 per channel.
- **Parity:** the service tensor matches the model's own reference pipeline within 1e-5 (`ai-service/tests/test_cancer_preprocessing.py`).
- **Explanation:** Attention rollout over the 12 encoder layers (14 x 14 patch grid); not class-specific.

## Measured performance (held-out test split)

| Metric | Value (95% CI) |
|---|---|
| Accuracy | 68.4% (66.0-70.7) |
| Balanced accuracy | 44.6% |
| Macro F1 | 0.447 |
| Sensitivity (cancer vs not) | 81.1% (76.3-85.1) |
| Specificity (cancer vs not) | 80.8% (78.4-82.9) |
| AUC (cancer vs not) | 0.884 |
| F1 (cancer vs not) | 0.632 |

Full tables, the confusion matrix and charts: [`research/cancer-evaluation/dermoscopy/metrics.md`](../cancer-evaluation/dermoscopy/metrics.md).

## Confidence, "inconclusive" and input checks

- Temperature scaling fitted on 193 calibration images: T = 2.1881; expected calibration error on the test split 0.255 before and 0.128 after.
- A finding is shown only when the calibrated top-class probability is at least 0.7; otherwise the result is inconclusive (25.9% of test images; accuracy 80.6% when answered).
- Wrong-area and synthetic images: 164 of 172 were rejected by the input checks or reported as inconclusive; 8 would still receive a finding.

## Known limitations

- Trained on a dataset dominated by moles (about two thirds of images) and by lighter skin types; performance on darker skin is unknown.
- Several images per lesion exist in HAM10000; image-level evaluation can be optimistic.
- The quantised export may differ slightly from the published full-precision model.
- Measured on ISIC 2018 test images it confuses benign keratoses and basal cell carcinoma with melanoma (see the confusion matrix).
- Not trained on phone photographs; such images are often rejected or flagged as unfamiliar.
- Confidence is a property of the model, not a personal probability of cancer. Results are research output and have no clinical validation.
