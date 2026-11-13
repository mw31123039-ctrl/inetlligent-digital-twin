"""Auditable development metrics and conservative promotion rules, not clinical validation."""
import hashlib
import json
import math

import numpy as np


def partition_fingerprint(records):
    """Bind public image identities, source labels and splits independently of install path."""
    fields = ('source_member', 'raw_sha256', 'pixel_sha256', 'label', 'split', 'group_id')
    canonical = sorted([{key: item[key] for key in fields} for item in records],
                       key=lambda item: (item['source_member'], item['raw_sha256']))
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def audit_partitions(records, class_count=2):
    """Reject label conflicts and known image/group leakage before training."""
    if not records or type(class_count) is not int or not 2 <= class_count <= 20:
        raise ValueError('The public split manifest is empty.')
    owners, labels, patients = {}, {}, {}
    counts = {split: [0] * class_count for split in ('train', 'validation', 'test')}
    identified = 0
    for record in records:
        split, label = record['split'], record['label']
        if split not in counts or type(label) is not int or not 0 <= label < class_count:
            raise ValueError('Unsupported partition or label.')
        counts[split][label] += 1
        for field in ('group_id', 'raw_sha256', 'pixel_sha256'):
            value = record[field]
            if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
                raise ValueError('Invalid source fingerprint.')
            key = field, value
            if key in owners and owners[key] != split:
                raise ValueError('Image or duplicate-group leakage between partitions.')
            if key in labels and labels[key] != label:
                raise ValueError('A source image/group has conflicting labels.')
            owners[key], labels[key] = split, label
        patient = record.get('patient_id')
        if patient is not None:
            if not isinstance(patient, str) or not patient.strip() or len(patient) > 128 or any(ord(char) < 32 for char in patient):
                raise ValueError('Patient identifiers must be nonempty pseudonymous codes.')
            patient = patient.strip()
            if patient in patients and patients[patient] != split:
                raise ValueError('A supplied patient identifier crosses partition boundaries.')
            patients[patient] = split
            identified += 1
    if any(min(support) < 1 for support in counts.values()):
        raise ValueError('Both source classes must occur in every partition.')
    return {'counts': counts, 'known_image_group_leakage': False, 'patient_disjoint': None,
            'provided_patient_ids_partition_disjoint': True if identified == len(records) else None,
            'patient_id_coverage': identified / len(records)}


def wilson_interval(correct, total):
    if total < 1 or not 0 <= correct <= total:
        raise ValueError('Invalid binomial counts.')
    z = 1.959963984540054
    p, denominator = correct / total, 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - radius), min(1.0, center + radius)]


def binary_metrics(targets, probabilities):
    targets, probabilities = np.asarray(targets), np.asarray(probabilities, np.float64)
    if targets.ndim != 1 or len(targets) < 2 or probabilities.shape != (len(targets), 2):
        raise ValueError('Binary labels and two-column probabilities are required.')
    if not np.isin(targets, [0, 1]).all() or not np.isfinite(probabilities).all() or (probabilities < 0).any() or (probabilities > 1).any() or not np.allclose(probabilities.sum(1), 1, atol=1e-5):
        raise ValueError('Invalid labels or probabilities.')
    predictions = probabilities.argmax(1)
    confusion = np.zeros((2, 2), dtype=np.int64)
    np.add.at(confusion, (targets.astype(int), predictions), 1)
    negative, positive = confusion.sum(1).tolist()
    if not negative or not positive:
        raise ValueError('Both classes are required for comparison.')
    tn, fp, fn, tp = confusion.reshape(-1).tolist()
    positive_scores, negative_scores = probabilities[targets == 1, 1], probabilities[targets == 0, 1]
    pairs = positive_scores[:, None] - negative_scores[None, :]
    auc = float(((pairs > 0).sum() + .5 * (pairs == 0).sum()) / pairs.size)
    accuracy, sensitivity, specificity = (tn + tp) / len(targets), tp / positive, tn / negative
    return {'unit': 'images', 'images': len(targets),
            'confusion_matrix_rows_actual_columns_predicted': confusion.tolist(),
            'accuracy': accuracy, 'balanced_accuracy': (sensitivity + specificity) / 2,
            'malignant_image_sensitivity': sensitivity, 'benign_image_specificity': specificity,
            'roc_auc': auc, 'negative_log_likelihood': float(-np.log(np.clip(probabilities[np.arange(len(targets)), targets.astype(int)], 1e-12, 1)).mean()),
            'brier_score': float(np.square(probabilities[:, 1] - targets).mean()),
            'wilson_95_intervals': {'accuracy': wilson_interval(tn + tp, len(targets)),
                                    'malignant_image_sensitivity': wilson_interval(tp, positive),
                                    'benign_image_specificity': wilson_interval(tn, negative)},
            'patient_disjoint': None, 'clinical_validation': False}


def classification_metrics(targets, probabilities, labels):
    """Multiclass cohort statistics and score uncertainty, never disease probabilities."""
    targets, values = np.asarray(targets), np.asarray(probabilities, np.float64)
    classes = len(labels)
    if not 2 <= classes <= 20 or len(set(labels)) != classes or any(not isinstance(label, str) or not label.strip() for label in labels):
        raise ValueError('Distinct class labels are required.')
    if targets.ndim != 1 or len(targets) < classes or values.shape != (len(targets), classes) or not np.issubdtype(targets.dtype, np.integer) or not np.isin(targets, range(classes)).all():
        raise ValueError('Class indices and matching score rows are required.')
    if not np.isfinite(values).all() or (values < 0).any() or (values > 1).any() or not np.allclose(values.sum(1), 1, atol=1e-5):
        raise ValueError('Invalid classifier scores.')
    confusion = np.zeros((classes, classes), dtype=np.int64)
    np.add.at(confusion, (targets, values.argmax(1)), 1)
    if (confusion.sum(1) == 0).any():
        raise ValueError('Every declared class needs reference images.')
    per_class = {}
    for index, label in enumerate(labels):
        tp, positive = int(confusion[index, index]), int(confusion[index].sum())
        negative = len(targets) - positive
        tn = negative - int(confusion[:, index].sum()) + tp
        per_class[label] = {'support_images': positive, 'recall': tp / positive,
                            'specificity': tn / negative, 'recall_wilson_95': wilson_interval(tp, positive),
                            'specificity_wilson_95': wilson_interval(tn, negative)}
    entropy = -np.sum(values * np.log(np.clip(values, 1e-15, 1)), axis=1) / np.log(classes)
    ordered = np.sort(values, axis=1)
    margins = ordered[:, -1] - ordered[:, -2]
    correct = int(np.trace(confusion))
    return {'unit': 'images', 'images': len(targets), 'labels': list(labels),
            'confusion_matrix_rows_actual_columns_predicted': confusion.tolist(), 'per_class': per_class,
            'accuracy': correct / len(targets), 'accuracy_wilson_95': wilson_interval(correct, len(targets)),
            'balanced_accuracy': float(np.mean([item['recall'] for item in per_class.values()])),
            'negative_log_likelihood': float(-np.log(np.clip(values[np.arange(len(targets)), targets], 1e-12, 1)).mean()),
            'brier_score': float(np.square(values - np.eye(classes)[targets]).sum(1).mean()),
            'score_uncertainty': {'mean_normalized_entropy': float(entropy.mean()),
                                  'mean_top_two_margin': float(margins.mean()),
                                  'interpretation': 'Descriptive model-score uncertainty; not calibrated personal cancer risk or evidence that an input is in distribution.'},
            'clinical_validation': False, 'patient_disjoint': None}


def promotion_reasons(baseline_validation, candidate_validation, baseline_audit=None, candidate_audit=None):
    """A historical test audit may veto activation; it is therefore development evidence."""
    reasons = []
    comparisons = [('validation', baseline_validation, candidate_validation)]
    if (baseline_audit is None) != (candidate_audit is None):
        raise ValueError('Provide both historical audit results or neither.')
    if baseline_audit is not None:
        comparisons.append(('historical-audit', baseline_audit, candidate_audit))
    for name, baseline, candidate in comparisons:
        if baseline['images'] != candidate['images'] or candidate.get('clinical_validation') is not False:
            raise ValueError('Comparable unvalidated results are required.')
        for metric in ('balanced_accuracy', 'malignant_image_sensitivity', 'benign_image_specificity'):
            if not all(math.isfinite(value[metric]) and 0 <= value[metric] <= 1 for value in (baseline, candidate)):
                raise ValueError('Invalid comparison metric.')
            if candidate[metric] + 1e-12 < baseline[metric]:
                reasons.append(name + ': ' + metric + ' regressed')
    if candidate_validation['balanced_accuracy'] <= baseline_validation['balanced_accuracy'] + 1e-12:
        reasons.append('validation: balanced accuracy did not strictly improve')
    return reasons
