# Measured cancer AI improvement run

Run date: 13 November 2026. [Machine-readable results](cancer-improvement-results-2026-11-13.json). This is development work, not a clinical evaluation or a comparison with competing clinical products.

## Training actually performed

A new EfficientNet-B0 oral-lesion classifier trained on the laptop's NVIDIA RTX 5060 GPU for 22 epochs with early stopping. Two predeclared candidates were evaluated: the new classifier alone and an equal-probability ensemble with the installed ResNet18. The 323 original public photographs retained the original partition: 226 training, 49 validation and 48 historical-audit images. No user uploads or account records were training sources.

The split audit checked raw-image, decoded-pixel and duplicate-group fingerprints for overlap and conflicting labels. Only original public files with verified hashes were loaded. Training used a warm-up classification head followed by fine-tuning the latter EfficientNet blocks. Augmentation and class weights used the training partition only; BatchNorm running statistics were frozen. The bounded experiment, selection rules and baseline fingerprint were saved before reading historical-audit pixels.

Images come from the [Mendeley Oral Images Dataset V2](https://data.mendeley.com/datasets/mhjyrn35p4/2), licensed CC BY 4.0. Labels are benign lesions versus malignant lesions; there are no patient IDs and no normal-mouth screening class. The official [torchvision EfficientNet-B0 architecture](https://docs.pytorch.org/vision/0.22/models/generated/torchvision.models.efficientnet_b0.html) initializes from ImageNet weights. This experiment intentionally uses the existing full-image bilinear resize consistently in training and inference, instead of the pretrained default center crop. Source checkpoints have full recorded SHA-256 fingerprints and are loaded as tensors with `weights_only=True`.

## The image candidate was rejected

The validation-selected candidate was the ensemble at epoch 15. Predictions use the fixed maximum-score class rule.

| Development comparison | Installed ResNet18 | Selected ensemble |
| --- | ---: | ---: |
| Validation images | 49 | 49 |
| Validation balanced accuracy | 87.83% | 89.83% |
| Validation malignant-label recall | 22/24 | 22/24 |
| Validation benign-label recall | 21/25 | 22/25 |
| Historical-audit images | 48 | 48 |
| Historical-audit balanced accuracy | 85.48% | 85.13% |
| Historical-audit malignant-label recall | 20/23 | 18/23 |
| Historical-audit benign-label recall | 21/25 | 23/25 |

The candidate missed two more malignant-labelled images in the historical audit. Activation was rejected; the installed classifier and fingerprint remain unchanged. Rejected weights, the training trace and report remain in the ignored `ai-service/models/cancer-experiments/20261113T195434Z/` folder. The ONNX export was compared against PyTorch on all 49 validation images and exercised with dynamic batches. The running app does not use the rejected weights.

This historical split had already been inspected during initial development. It now vetoes activation, so it is explicitly development evidence. It must not be described as a new blind test or used to claim independent accuracy. Wilson 95% intervals, ROC AUC, Brier score and negative log likelihood accompany the confusion matrices. For example, installed-model historical malignant-label recall is 20/23, with a wide Wilson interval of approximately 67.9%-95.5%. Patient-level generalization remains unknown.

## Active source-search improvement

A synthetic source-navigation benchmark covers all 16 cancer guides, four workflow records and eight unrelated questions. Each split has 20 relevant questions and four unrelated questions. These are developer-written checks, not clinician-authored cases or independent medical answer evaluation.

On the development split, the original encoder ranked the intended source first on 19/20 questions. A question explicitly about bladder cancer and cystoscopy incorrectly ranked the colorectal guide first. The fix uses whole-word cancer/organ aliases to reorder only the encoder's three already-relevant matches. It preserves their actual cosine similarities and the relevance threshold. It cannot introduce a new source record or infer a diagnosis from symptoms.

The revised search ranked the accepted source first on 20/20 development questions and 20/20 reserved check questions. All eight unrelated questions returned no match. These small synthetic results verify a navigation fix; they do not mean 100% medical accuracy, general retrieval accuracy or cancer-detection accuracy. Adding aliases does not train new knowledge into either the image classifier's or sentence encoder's weights.

The revised search is loaded in the running private service. Image classifiers remain unchanged. Stored health records and the frontend API contract were not expanded.

## Reproduce and review

From `ai-service`, using the existing environment with the optional cancer-model dependencies:

```powershell
python scripts/improve-cancer-models.py
python scripts/evaluate-cancer-knowledge.py --split development
python scripts/evaluate-cancer-knowledge.py --split holdout
python -m pytest -q
```

`--activate` requests conditional activation after both predeclared gates pass. It cannot bypass regressions, fingerprints or export parity. Accepted activation preserves the previous model directory and rolls back a failed directory swap. Without the flag, candidates remain outside the served model registry. The current experiment targets the original installed ResNet18 baseline and rejects an incompatible contract. Reproduction is subject to GPU/software nondeterminism despite fixed seeds and deterministic cuDNN settings; reports document the recorded run, not guaranteed bitwise identical retraining.

The fixture and aliases are now visible to developers. Future changes must treat these as regression checks and add new unseen evaluation material instead of repeatedly calling them independent tests.

## Remaining requirements for clinical performance claims

A larger licensed dataset needs clinician-verified reference labels, reliable patient/cohort identifiers and representative acquisition conditions. Independent cohorts should be reserved before further tuning. Each modality needs appropriate data and evaluation; oral-model training does not improve lung, breast or skin models. The installed pretrained models' incomplete provenance cannot be repaired by software checks.

The [2025 IMDRF GMLP guidance](https://www.imdrf.org/sites/default/files/2025-02/IMDRF_AIML%20WG_GMLP_N88%20Final.pdf), linked by the [FDA](https://www.fda.gov/medical-devices/artificial-intelligence-enabled-medical-devices/good-machine-learning-practice-medical-device-development-guiding-principles), calls for representative evaluation data and independence that considers patients, sites and acquisition. This project's checks support reproducible research; they establish neither conformity nor clinical safety. External clinical data and expert evaluation remain necessary before ranking it against clinical systems or using it for care decisions.
