"""Model-development safeguards; these are not medical-accuracy tests."""
import copy

import numpy as np
import pytest

from app.cancer_training import audit_partitions, binary_metrics, partition_fingerprint, promotion_reasons, wilson_interval


def records():
    values = []
    for split in ('train', 'validation', 'test'):
        for label in (0, 1):
            index = len(values) + 1
            values.append(dict(split=split, label=label, group_id=f'{index:064x}',
                               source_member=f'original_data/source-{index}.jpg',
                               raw_sha256=f'{index + 20:064x}', pixel_sha256=f'{index + 40:064x}'))
    return values


def test_fixed_source_split_fingerprint_is_portable_and_binds_labels_and_partitions():
    original = records()
    reference = partition_fingerprint(original)
    relocated = [item | {'path': '/a/different/machine/file.jpg'} for item in reversed(original)]
    assert partition_fingerprint(relocated) == reference
    for key, value in [('label', 1), ('split', 'test'), ('group_id', 'f' * 64)]:
        changed = copy.deepcopy(original); changed[0][key] = value
        assert partition_fingerprint(changed) != reference


def measured(matrix):
    labels, probabilities = [], []
    for actual, row in enumerate(matrix):
        for predicted, count in enumerate(row):
            labels.extend([actual] * count)
            probabilities.extend([[.8, .2] if predicted == 0 else [.2, .8]] * count)
    return binary_metrics(labels, probabilities)


def test_audit_checks_raw_decoded_and_group_leakage_and_label_conflicts():
    assert audit_partitions(records())['counts'] == {split: [1, 1] for split in ('train', 'validation', 'test')}
    for field in ('group_id', 'raw_sha256', 'pixel_sha256'):
        leaked = records(); leaked[2][field] = leaked[0][field]
        with pytest.raises(ValueError, match='leakage'):
            audit_partitions(leaked)
        conflicting = records(); conflicting[1][field] = conflicting[0][field]
        with pytest.raises(ValueError, match='conflicting'):
            audit_partitions(conflicting)
    with pytest.raises(ValueError):
        audit_partitions(records()[:-1])


def test_metrics_report_class_counts_auc_and_finite_binomial_uncertainty():
    result = measured([[21, 4], [3, 20]])
    assert result['images'] == 48
    assert result['accuracy'] == pytest.approx(41 / 48)
    assert result['malignant_image_sensitivity'] == pytest.approx(20 / 23)
    assert result['benign_image_specificity'] == pytest.approx(21 / 25)
    low, high = result['wilson_95_intervals']['malignant_image_sensitivity']
    assert 0 < low < 20 / 23 < high < 1
    assert result['patient_disjoint'] is None and result['clinical_validation'] is False
    assert binary_metrics([0, 1], [[.5, .5], [.5, .5]])['roc_auc'] == .5
    assert binary_metrics([0, 1], [[.9, .1], [.1, .9]])['roc_auc'] == 1
    assert wilson_interval(0, 10)[0] == pytest.approx(0, abs=1e-15)


@pytest.mark.parametrize('labels,probabilities', [
    ([0, 0], [[.9, .1], [.1, .9]]), ([0, 2], [[.9, .1], [.1, .9]]),
    ([0, 1], [[np.nan, .1], [.1, .9]]), ([0, 1], [[.9, .9], [.1, .9]]),
])
def test_invalid_metric_inputs_cannot_produce_promotable_results(labels, probabilities):
    with pytest.raises(ValueError):
        binary_metrics(labels, probabilities)


def test_promotion_requires_strict_validation_improvement_and_both_class_recalls():
    baseline = measured([[21, 4], [2, 22]])
    better = measured([[23, 2], [1, 23]])
    assert promotion_reasons(baseline, better) == []
    assert promotion_reasons(baseline, baseline)
    # Higher aggregate accuracy cannot hide a worse malignant-class recall.
    tradeoff = measured([[25, 0], [3, 21]])
    assert 'validation: malignant_image_sensitivity regressed' in promotion_reasons(baseline, tradeoff)


def test_reused_historical_audit_can_veto_activation_and_bad_metrics_fail_closed():
    baseline = measured([[21, 4], [2, 22]])
    better = measured([[23, 2], [1, 23]])
    historical = measured([[21, 4], [3, 20]])
    worse = measured([[25, 0], [4, 19]])
    assert 'historical-audit: malignant_image_sensitivity regressed' in promotion_reasons(baseline, better, historical, worse)
    with pytest.raises(ValueError):
        promotion_reasons(baseline, better, historical)
    invalid = copy.deepcopy(better); invalid['balanced_accuracy'] = float('nan')
    with pytest.raises(ValueError):
        promotion_reasons(baseline, invalid)
