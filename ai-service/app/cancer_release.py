"""Local research-model review and guarded activation. Never clinical certification."""
import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from .cancer import load_bundle, output_scores, prepare_input
from .cancer_training import audit_partitions, classification_metrics

POLICY = 'humantwin-cancer-release-v1'


def file_sha(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def artifact_identity(directory):
    if any((directory / name).is_symlink() or (directory / name).resolve().parent != directory.resolve()
           for name in ('model.onnx', 'manifest.json')):
        raise ValueError('Model artifacts must be files inside their declared bundle directory.')
    return {'weights_sha256': file_sha(directory / 'model.onnx'),
            'manifest_sha256': file_sha(directory / 'manifest.json')}


def release_reasons(baseline, candidate, audit, minimum_per_class=20):
    """Block measured regressions and unknown supplied-patient separation."""
    if type(minimum_per_class) is not int or minimum_per_class < 1:
        raise ValueError('A positive minimum class support is required.')
    reasons = []
    if audit['provided_patient_ids_partition_disjoint'] is not True:
        reasons.append('Patient identifiers are incomplete; separation cannot be checked for every record.')
    for split in ('validation', 'test'):
        old, new = baseline[split], candidate[split]
        if old['labels'] != new['labels'] or old['images'] != new['images'] or old.get('clinical_validation') is not False or new.get('clinical_validation') is not False:
            raise ValueError('Comparable development metrics are required.')
        for item in (old, new):
            if any(not np.isfinite(item[key]) for key in ('balanced_accuracy', 'negative_log_likelihood', 'brier_score')):
                raise ValueError('Non-finite release metrics.')
        if new['balanced_accuracy'] + 1e-12 < old['balanced_accuracy']:
            reasons.append(split + ': balanced accuracy regressed')
        for key in ('negative_log_likelihood', 'brier_score'):
            if new[key] > old[key] + 1e-12:
                reasons.append(split + ': ' + key + ' regressed')
        for label in old['labels']:
            first, second = old['per_class'][label], new['per_class'][label]
            if first['support_images'] != second['support_images']:
                raise ValueError('Class supports differ between the compared models.')
            if first['support_images'] < minimum_per_class:
                reasons.append(split + ': insufficient reference images for ' + label)
            for key in ('recall', 'specificity'):
                if not all(np.isfinite(item[key]) and 0 <= item[key] <= 1 for item in (first, second)):
                    raise ValueError('Invalid per-class release metrics.')
                if second[key] + 1e-12 < first[key]:
                    reasons.append(split + ': ' + label + ' ' + key + ' regressed')
    if candidate['validation']['balanced_accuracy'] <= baseline['validation']['balanced_accuracy'] + 1e-12:
        reasons.append('validation: balanced accuracy did not strictly improve')
    return reasons


def inside_root(path, root):
    resolved = path.resolve()
    if resolved == root or not resolved.is_relative_to(root) or path.is_symlink():
        raise ValueError('Model operations must remain inside the explicitly selected models directory.')
    return resolved


@contextmanager
def release_lock(root):
    lock = root / '.cancer-release.lock'
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, 'w') as handle:
            handle.write(str(os.getpid()))
        yield
    finally:
        lock.unlink()


def activate_reviewed_candidate(models_root, active, candidate, backup, review):
    """Use only a just-computed review; restore the active directory on swap/load failure."""
    root = models_root.resolve(strict=True)
    active, candidate, backup = (inside_root(path, root) for path in (active, candidate, backup))
    if active != (root / 'cancer' / review.get('modality', '')).resolve():
        raise ValueError('Only the selected registry entry may be replaced.')
    if active == candidate or backup.exists() or any(left.is_relative_to(right) for left, right in
                                                  ((candidate, active), (active, candidate), (backup, active), (backup, candidate), (active, backup), (candidate, backup))):
        raise ValueError('Distinct, nonoverlapping model directories and a new backup path are required.')
    if review.get('policy_version') != POLICY or review.get('eligible') is not True or review.get('reasons') != []:
        raise ValueError('The candidate did not pass the release review.')
    with release_lock(root):
        # Bind weights AND preprocessing/labels to the exact evaluated artifacts.
        if artifact_identity(active) != review['baseline_artifacts'] or artifact_identity(candidate) != review['candidate_artifacts']:
            raise ValueError('Model artifacts changed after evaluation; activation refused.')
        installed, _ = load_bundle(active, review['modality'])
        staged, _ = load_bundle(candidate, review['modality'])
        if installed.labels != staged.labels or installed.track != staged.track:
            raise ValueError('The staged model changed the class or pathway contract.')
        backup.parent.mkdir(parents=True, exist_ok=True)
        journal = backup.parent / 'activation.json'
        entry = {'policy_version': POLICY, 'stage': 'prepared', 'modality': review['modality'],
                 'baseline_artifacts': review['baseline_artifacts'], 'candidate_artifacts': review['candidate_artifacts'],
                 'cohort_sha256': review['cohort_sha256'], 'active_directory': str(active),
                 'candidate_directory': str(candidate), 'backup_directory': str(backup)}
        with journal.open('x', encoding='utf-8') as handle:
            json.dump(entry, handle, allow_nan=False)
        try:
            active.rename(backup)
            candidate.rename(active)
            load_bundle(active, review['modality'])
            if artifact_identity(active) != review['candidate_artifacts']:
                raise ValueError('Activated artifact verification failed.')
            entry['stage'] = 'activated'
            journal.write_text(json.dumps(entry, allow_nan=False) + '\n', encoding='utf-8')
        except BaseException:
            try:
                if backup.exists():
                    if active.exists():
                        active.rename(candidate)
                    backup.rename(active)
            except BaseException as restoration_error:
                try:
                    entry['stage'] = 'recovery-required'
                    journal.write_text(json.dumps(entry, allow_nan=False) + '\n', encoding='utf-8')
                except OSError:
                    pass
                raise RuntimeError('Automatic restoration failed; inspect the saved model backup at ' + str(backup)) from restoration_error
            try:
                entry['stage'] = 'rolled-back'
                journal.write_text(json.dumps(entry, allow_nan=False) + '\n', encoding='utf-8')
            except OSError:
                pass  # Preserve the original failure after restoring the previous model.
            raise
    return {'activated': True, 'backup_directory': str(backup), 'journal': str(journal), 'active_weights_sha256': staged.weights_sha256}


def review_upgrade(models_root, modality, candidate, cohort, image_root, *, activate=False, minimum_per_class=20):
    root = models_root.resolve(strict=True)
    active = inside_root(root / 'cancer' / modality, root)
    candidate = inside_root(candidate, root)
    image_root = image_root.resolve(strict=True)
    before, staged_before = artifact_identity(active), artifact_identity(candidate)
    installed, baseline_runner = load_bundle(active, modality)
    staged, candidate_runner = load_bundle(candidate, modality)
    if cohort.get('schema_version') != 'humantwin-cancer-cohort-v1' or cohort.get('modality') != modality or cohort.get('labels') != installed.labels or staged.labels != installed.labels or installed.track != staged.track:
        raise ValueError('The cohort and both models must declare the same modality and ordered classes.')
    records = cohort['records']
    if not isinstance(records, list) or not 1 <= len(records) <= 20000:
        raise ValueError('Use a bounded cohort manifest.')
    audit = audit_partitions(records, len(installed.labels))
    targets = {split: [] for split in ('validation', 'test')}
    scores = {name: {split: [] for split in targets} for name in ('baseline', 'candidate')}
    observed, normalized, seen = [], [], {split: set() for split in targets}
    duplicate_evaluation_images_removed = 0
    for record in records:
        path = Path(record['path'])
        path = (path if path.is_absolute() else image_root / path).resolve(strict=True)
        if not path.is_relative_to(image_root) or path.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.bmp'):
            raise ValueError('Cohort images must remain inside the explicitly selected image directory.')
        if not 0 < path.stat().st_size <= 32 * 1024 * 1024 or file_sha(path) != record['raw_sha256']:
            raise ValueError('A source image is missing or its file fingerprint changed.')
        with Image.open(path) as original:
            # Public research originals include a 64 MP photograph. These local
            # bounds are separate from the smaller browser-upload contract.
            if min(original.size) < 32 or max(original.size) > 12000 or original.width * original.height > 80000000:
                raise ValueError('Unsupported source-image dimensions.')
            rgb = ImageOps.exif_transpose(original).convert('RGB')
            pixels = np.asarray(rgb)
            pixel_sha = hashlib.sha256(str(rgb.size).encode() + pixels.tobytes()).hexdigest()
        if pixel_sha != record['pixel_sha256']:
            raise ValueError('A decoded source-image fingerprint changed.')
        current_sha = file_sha(path)
        if current_sha != record['raw_sha256']:
            raise ValueError('A source image changed during evaluation.')
        observed.append({**record, 'raw_sha256': current_sha, 'pixel_sha256': pixel_sha})
        patient = record.get('patient_id')
        normalized.append({key: record[key] for key in ('split', 'label', 'group_id', 'raw_sha256', 'pixel_sha256')} |
                          {'patient_id_sha256': hashlib.sha256(patient.strip().encode()).hexdigest() if patient is not None else None})
        split = record['split']
        if split == 'train':
            continue
        if pixel_sha in seen[split]:
            duplicate_evaluation_images_removed += 1
            continue
        seen[split].add(pixel_sha)
        image = np.ascontiguousarray(pixels[:, :, ::-1])
        targets[split].append(record['label'])
        for name, manifest, runner in [('baseline', installed, baseline_runner), ('candidate', staged, candidate_runner)]:
            scores[name][split].append([item.value for item in output_scores(runner.predict(prepare_input(image, manifest)), manifest)])
    audit_partitions(observed, len(installed.labels))
    measurements = {name: {split: classification_metrics(targets[split], scores[name][split], installed.labels)
                           for split in targets} for name in scores}
    if artifact_identity(active) != before or artifact_identity(candidate) != staged_before:
        raise ValueError('Model artifacts changed during the review.')
    cohort_sha = hashlib.sha256(json.dumps(sorted(normalized, key=lambda item: (item['split'], item['raw_sha256'])),
                                          sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    reasons = release_reasons(measurements['baseline'], measurements['candidate'], audit, minimum_per_class)
    review = {'schema_version': 'humantwin-cancer-release-review-v1', 'policy_version': POLICY,
              'created_at': datetime.now(timezone.utc).isoformat(), 'modality': modality,
              'baseline_artifacts': before, 'candidate_artifacts': staged_before, 'cohort_sha256': cohort_sha,
              'data_audit': audit, 'minimum_reference_images_per_class': minimum_per_class,
              'duplicate_evaluation_images_removed': duplicate_evaluation_images_removed,
              'baseline': measurements['baseline'], 'candidate': measurements['candidate'],
              'eligible': not reasons, 'reasons': reasons, 'activation_requested': activate, 'activated': False,
              'clinical_validation': False, 'independent_patient_validation_established': False,
              'limitations': ['Release thresholds are development policy, not validated medical cutoffs.',
                              'Supplied patient codes and duplicate groups cannot establish true identities or discover every near-duplicate.',
                              'Reference labels and provenance still need independent expert review.',
                              'The audit split participates in activation decisions and is therefore development evidence.',
                              'Wilson intervals treat images as independent and do not adjust for correlated visits or multiple images of one patient.',
                              'Score uncertainty and cohort statistics do not establish individual cancer risk or exclude out-of-distribution inputs.']}
    if activate and review['eligible']:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        review['activation'] = activate_reviewed_candidate(root, active, candidate,
                                                         root / 'cancer-releases' / stamp / 'previous-model', review)
        review['activated'] = True
    return review
