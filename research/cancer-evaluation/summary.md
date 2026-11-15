# Cancer image models: held-out evaluation summary

| Model | Test images | Accuracy | Balanced acc. | Macro F1 | Cancer sensitivity | Cancer specificity | Cancer AUC | Temperature | Inconclusive |
|---|---|---|---|---|---|---|---|---|---|
| oral-resnet18-mendeley-v1 | 48 | 85.4% | 85.5% | 0.854 | 87.0% | 84.0% | 0.894 | 0.7421 | 8.3% |
| lung-efficientnet-b0-506c398b-onnx | 98 | 96.9% | 96.9% | 0.959 | 98.9% | 100.0% | 0.998 | 0.6219 | 10.2% |
| busi-vit-257147b3-onnx | 1310 | 76.2% | 67.6% | 0.694 | 43.5% | 92.8% | 0.817 | 1.3082 | 24.9% |
| ham10000-vit-q8-25be9e61 | 1512 | 68.4% | 44.6% | 0.447 | 81.1% | 80.8% | 0.884 | 2.1881 | 25.9% |

Per-model details, confusion matrices and charts are in each model folder. See research/CANCER_EVALUATION.md for the method.
