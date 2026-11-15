# Model card: Lung: single CT slice classifier

*Model version `lung-efficientnet-b0-506c398b-onnx` · weights SHA-256 `5a8f69cb8286e132…` · evaluated 2026-11-16 with `ai-service/scripts/evaluate-cancer-models.py`.*

## Intended use

Education and research demonstration inside the HumanTwin workspace: showing how an image classifier responds to one prepared image, with its confidence, an explanation map and its limits. **Not intended** for diagnosis, screening, triage or treatment decisions, and not a substitute for examination by a clinician.

## Model

- **Architecture:** EfficientNet-B0 (ImageNet initialisation), fine-tuned by the upstream author; exported to ONNX locally with numerical parity checks.
- **Source:** yunussgultekiin/lung-cancer-efficientnet-b0 (revision 506c398b), Hugging Face.
- **Licence:** Repository MIT (model card states Apache-2.0); LungCancer4Types data Apache-2.0.
- **Classes (output order):** adenocarcinoma, large.cell.carcinoma, normal, squamous.cell.carcinoma
- **Classes counted as cancer in the binary view:** adenocarcinoma, large.cell.carcinoma, squamous.cell.carcinoma

## Data

- **Training data:** LungCancer4Types (Kabil007): 824 unique 2D CT slice images after de-duplication; the author trained on a 659-image development pool and held out 165 images.
- **Evaluation data:** LungCancer4Types (Kabil007, Apache-2.0): the model author's own 165-image held-out test split (data/splits/test_dev_split.csv at the pinned model revision; the model was trained on the other 659 de-duplicated images). Split here by near-duplicate cluster: 40% calibration, 60% test.
- **Test split:** 98 images (adenocarcinoma: 40, large.cell.carcinoma: 22, normal: 6, squamous.cell.carcinoma: 30).

## Input and preprocessing

- **Accepted input:** One chest CT slice exported as an 8-bit JPEG or PNG (not DICOM, not a full scan).
- **Preprocessing:** RGB (grayscale replicated); exact resize to 224 x 224 with antialiased bilinear interpolation (torchvision on PIL images); scale 1/255; ImageNet mean and std.
- **Parity:** the service tensor matches the model's own reference pipeline within 1e-5 (`ai-service/tests/test_cancer_preprocessing.py`).
- **Explanation:** Grad-CAM on the final feature map (7 x 7 grid); class-specific, equal to the class activation map for this head.

## Measured performance (held-out test split)

| Metric | Value (95% CI) |
|---|---|
| Accuracy | 96.9% (91.4-99.0) |
| Balanced accuracy | 96.9% |
| Macro F1 | 0.959 |
| Sensitivity (cancer vs not) | 98.9% (94.1-99.8) |
| Specificity (cancer vs not) | 100.0% (61.0-100.0) |
| AUC (cancer vs not) | 0.998 |
| F1 (cancer vs not) | 0.995 |

Full tables, the confusion matrix and charts: [`research/cancer-evaluation/lung_ct_slice/metrics.md`](../cancer-evaluation/lung_ct_slice/metrics.md).

## Confidence, "inconclusive" and input checks

- Temperature scaling fitted on 67 calibration images: T = 0.6219; expected calibration error on the test split 0.103 before and 0.051 after.
- A finding is shown only when the calibrated top-class probability is at least 0.85; otherwise the result is inconclusive (10.2% of test images; accuracy 97.7% when answered).
- Wrong-area and synthetic images: 172 of 172 were rejected by the input checks or reported as inconclusive; 0 would still receive a finding.

## Known limitations

- A single slice cannot represent a CT examination; lung cancer cannot be ruled out from one image.
- The public dataset is small, of unknown scanner and patient provenance, and only 49 "normal" images are unique.
- Class folders carry stage information from one source; the model may learn dataset artefacts rather than anatomy.
- Very high held-out accuracy on 98 test images should be read with its confidence interval and dataset limits in mind.
- Confidence is a property of the model, not a personal probability of cancer. Results are research output and have no clinical validation.
