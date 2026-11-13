# Cancer model upgrade checks

The reusable checks run locally for compatible image classifiers, including the installed 7-class skin, 4-class lung, 3-class breast and 2-class oral models. They evaluate development evidence and protect model replacement. They do not certify medical safety or establish that a future model will perform better for unseen patients.

## Data and uncertainty checks

The reviewer requires a labelled cohort with training, validation and historical-audit partitions and the model's exact ordered class names. It checks:

- Raw file hashes, decoded RGB-pixel hashes and known duplicate-group IDs for overlap and conflicting labels across partitions.
- Supplied pseudonymous patient codes for overlap across partitions. Missing codes remain unknown; they are never treated as proof of independent patients. Automatic activation requires codes for every record.
- Actual file contents against the manifest, bounded image sizes and containment inside the explicitly supplied image directory. Local research originals may be up to 12,000 pixels per side and 80 megapixels; browser uploads retain their separate, smaller limits.
- Exact decoded duplicates inside an evaluation partition are counted once. Similar visits, crops or other near-duplicates are not all discoverable from pixels or supplied group IDs.

Both models run on the same verified evaluation pixels, using each model's declared preprocessing. The report includes confusion matrices, each class's recall and specificity, Wilson 95% intervals, balanced accuracy, negative log likelihood, Brier score, mean normalized score entropy and mean top-two score margin. The cohort fingerprint binds reference labels, image/group identities and supplied patient codes without putting raw codes or image pixels in the report.

The image-level intervals assume independent observations. Multiple visits or images from one patient can violate that assumption. Entropy, score margins and score-loss measurements do not create calibrated personal cancer probabilities and cannot establish whether an image is from the intended clinical distribution.

## Model replacement rules

The default policy requires all of the following before the upgrade command can replace the installed model:

1. Complete supplied patient identifiers with no detected cross-partition overlap.
2. At least 20 distinct decoded reference images for every class in both evaluation partitions. This is a conservative development policy, not a medically validated sample-size requirement.
3. Strictly better validation balanced accuracy; no decrease in either partition's balanced accuracy, any class's recall or any class's specificity.
4. No increase in negative log likelihood or Brier score in either partition.
5. Compatible modality/pathway and ordered labels, valid model/preprocessing manifests, actual runtime inference and stable artifact fingerprints throughout the review.

The historical audit participates in activation decisions and is therefore development evidence. Even complete supplied patient codes do not reconstruct an unavailable original training cohort or independently verify patient identities, reference labels, provenance or external clinical validity. The report always leaves clinical validation and independent patient validation unestablished.

Activation checks both weights and preprocessing-manifest hashes again after taking an exclusive local release lock. It verifies that every model operation remains inside the selected models directory, preserves the old model in a new backup directory, verifies the staged model with the same loader used by the app, and records an activation journal. Directory-swap, runtime-load or journal-write failures restore the previous model. If the filesystem also prevents restoration, the previous artifacts remain in their backup and the journal records `recovery-required` when writable. Inspect the journal and active registry before retrying; a process crash or filesystem outage cannot be made impossible by these checks.

The release lock coordinates these upgrade commands. It does not restrict an operator who directly edits files or uses an unrelated installation script. A lock left by a terminated process should be inspected before it is removed. The directory swap is local and brief; an inference request during replacement may need retrying.

## Use

From `ai-service`, using the existing Python environment:

```powershell
python scripts/review-cancer-upgrade.py --modality oral_photo --candidate models/cancer-experiments/EXPERIMENT/candidate --cohort models/cancer-experiments/EXPERIMENT/cohort.json --image-root training-data/cancer-oral/originals
```

Reports are saved under `models/cancer-releases/`. Add `--activate` to request conditional activation; this flag does not bypass a failed check. The existing `improve-cancer-models.py --activate` training workflow now calls the same reviewer for a selected candidate. The current public oral dataset lacks patient codes, so the stricter reviewer will report it for development and refuse automatic activation.

A cohort JSON has `schema_version: "humantwin-cancer-cohort-v1"`, the exact `modality`, the model's ordered `labels` array, and a `records` array. Each record includes `path`, `split` (`train`, `validation`, `test`), integer `label` (index into `labels`), `raw_sha256`, `pixel_sha256`, `group_id`, and optional `patient_id`. Paths must resolve inside `--image-root`. The decoded hash is SHA-256 of `str(oriented_rgb_image.size).encode()` followed by the decoded RGB bytes. Group IDs are 64-character lowercase SHA-256-style tokens supplied by the dataset preparation process. Use pseudonymous patient codes rather than personal identifiers.

## Verification performed on 13 November 2026

The [real-candidate review](cancer-upgrade-guard-check-2026-11-13.json) ran both installed and rejected oral models on the 49 validation and 48 historical-audit reference images, after checking all 323 original file/pixel identities. An activation request was rejected for missing patient codes and worse audit balanced accuracy, benign-label specificity and malignant-label recall. The installed model's actual SHA-256 was checked afterward and matched the pre-review fingerprint.

Software tests exercise multiclass regressions hidden by a better aggregate score, score-loss regressions, insufficient class support, missing/overlapping patient codes, corrupted source images, changed class order, artifact tampering, cache invalidation with preserved file timestamps, concurrent release locking, path containment, successful backup creation, rollback on injected failures and preservation of the backup when automatic restoration is impossible. Synthetic colour classifiers are used for activation tests; they have no medical meaning. The four actual installed models were also exercised through the browser after the shared loader change.

The approach is informed by the [FDA's GMLP overview](https://www.fda.gov/medical-devices/artificial-intelligence-enabled-medical-devices/good-machine-learning-practice-medical-device-development-guiding-principles) and its linked IMDRF principles. Passing these software checks does not establish conformity or clinical readiness.
