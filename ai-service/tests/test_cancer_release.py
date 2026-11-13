"""Synthetic classifier/cohort checks; no patient data or medical validation."""
import copy
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app import cancer_release
from app.cancer import load_bundle
from app.cancer_release import activate_reviewed_candidate, artifact_identity, release_reasons, review_upgrade
from app.cancer_training import audit_partitions, classification_metrics


def metrics(matrix):
    targets, values = [], []
    classes = len(matrix)
    for actual, row in enumerate(matrix):
        for predicted, count in enumerate(row):
            for _ in range(count):
                targets.append(actual)
                scores = [.1 / (classes - 1)] * classes; scores[predicted] = .9
                values.append(scores)
    return classification_metrics(targets, values, [f'class-{i}' for i in range(classes)])


def test_multiclass_metrics_include_each_class_and_uncertainty_without_claiming_risk():
    measured = metrics([[2, 1, 0], [0, 3, 0], [0, 1, 2]])
    assert measured['accuracy'] == pytest.approx(7 / 9)
    assert measured['balanced_accuracy'] == pytest.approx(7 / 9)
    assert measured['per_class']['class-1']['recall'] == 1
    assert measured['per_class']['class-1']['specificity'] == pytest.approx(4 / 6)
    assert 0 < measured['score_uncertainty']['mean_normalized_entropy'] < 1
    assert measured['score_uncertainty']['mean_top_two_margin'] == pytest.approx(.85)
    assert measured['clinical_validation'] is False and measured['patient_disjoint'] is None
    for targets, scores in [([0, 0], [[.9, .1]] * 2), ([0, 1], [[float('nan'), .1], [.1, .9]]),
                            ([0.5, 1.], [[.9, .1], [.1, .9]])]:
        with pytest.raises(ValueError):
            classification_metrics(targets, scores, ['a', 'b'])


def test_a_better_aggregate_cannot_hide_a_worse_multiclass_recall():
    old, new = metrics([[2, 1, 0], [0, 3, 0], [0, 1, 2]]), metrics([[3, 0, 0], [0, 2, 1], [0, 0, 3]])
    assert new['balanced_accuracy'] > old['balanced_accuracy']
    reasons = release_reasons({'validation': old, 'test': old}, {'validation': new, 'test': new},
                              {'provided_patient_ids_partition_disjoint': True}, 1)
    assert 'validation: class-1 recall regressed' in reasons
    invalid = copy.deepcopy(new); invalid['negative_log_likelihood'] = float('nan')
    with pytest.raises(ValueError):
        release_reasons({'validation': old, 'test': old}, {'validation': invalid, 'test': new},
                        {'provided_patient_ids_partition_disjoint': True})


def test_score_losses_and_insufficient_class_support_can_block_an_upgrade():
    targets = [0, 0, 1, 1]
    old = classification_metrics(targets, [[.99, .01], [.99, .01], [.9, .1], [.01, .99]], ['a', 'b'])
    new = classification_metrics(targets, [[.51, .49], [.51, .49], [.49, .51], [.49, .51]], ['a', 'b'])
    reasons = release_reasons({'validation': old, 'test': old}, {'validation': new, 'test': new},
                              {'provided_patient_ids_partition_disjoint': True})
    assert 'validation: negative_log_likelihood regressed' in reasons
    assert 'validation: brier_score regressed' in reasons
    assert 'validation: insufficient reference images for a' in reasons


def bundle(directory, red_weight):
    onnx = pytest.importorskip('onnx')
    from onnx import TensorProto, helper, numpy_helper
    directory.mkdir(parents=True)
    graph = helper.make_graph([
        helper.make_node('ReduceMean', ['pixels'], ['mean'], axes=[2, 3], keepdims=0),
        helper.make_node('MatMul', ['mean', 'weights'], ['logits']),
    ], 'synthetic-colour-model', [helper.make_tensor_value_info('pixels', TensorProto.FLOAT, [1, 3, 32, 32])],
        [helper.make_tensor_value_info('logits', TensorProto.FLOAT, [1, 2])],
        [numpy_helper.from_array(np.array([[red_weight, 0], [0, 1], [0, 0]], np.float32), 'weights')])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid('', 17)], ir_version=10)
    onnx.save(model, directory / 'model.onnx')
    manifest = dict(schema_version='humantwin-cancer-model-v1', track='oral', modality='oral_photo',
                    model_version='synthetic-release-v1', target='Untrained software colour fixture',
                    source_url='https://example.invalid/software-check', license='CC0 synthetic fixture',
                    weights_sha256=hashlib.sha256((directory / 'model.onnx').read_bytes()).hexdigest(),
                    input_size=[32, 32], color='RGB', resize='stretch', scale=1 / 255,
                    mean=[0, 0, 0], std=[1, 1, 1], labels=['red', 'green'], output='logits', runtime='onnxruntime',
                    evaluation={'reference': 'Synthetic software-only checks', 'patient_disjoint': None}, research_only=True)
    (directory / 'manifest.json').write_text(json.dumps(manifest))


@pytest.fixture
def fixture(tmp_path):
    root, image_root = tmp_path / 'models', tmp_path / 'synthetic-images'
    image_root.mkdir()
    active, staged = root / 'cancer/oral_photo', root / 'experiments/candidate'
    bundle(active, 1.); bundle(staged, 2.)
    records = []
    for split in ('train', 'validation', 'test'):
        for position, (label, red, green) in enumerate([(0, 153, 178), (0, 229, 25), (1, 25, 229), (1, 25, 204)]):
            index = len(records) + 1
            image = Image.new('RGB', (32, 32), (red, green, index))
            path = image_root / f'{index}.png'; image.save(path)
            records.append({'path': str(path), 'source_member': path.name, 'split': split, 'label': label,
                            'raw_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                            'pixel_sha256': hashlib.sha256(str(image.size).encode() + np.asarray(image).tobytes()).hexdigest(),
                            'group_id': f'{index:064x}', 'patient_id': 'synthetic-code-' + str(index)})
    cohort = {'schema_version': 'humantwin-cancer-cohort-v1', 'modality': 'oral_photo',
              'labels': ['red', 'green'], 'records': records}
    review = review_upgrade(root, 'oral_photo', staged, cohort, image_root, minimum_per_class=1)
    assert review['eligible'] and not review['activated']
    return root, active, staged, image_root, cohort, review


def test_patient_overlap_is_rejected_and_missing_ids_never_claim_patient_validation(fixture):
    _, _, _, _, cohort, _ = fixture
    records = copy.deepcopy(cohort['records'])
    records[4]['patient_id'] = records[0]['patient_id']
    with pytest.raises(ValueError, match='crosses partition') as failure:
        audit_partitions(records)
    assert records[0]['patient_id'] not in str(failure.value)
    records = copy.deepcopy(cohort['records']); records[0].pop('patient_id')
    audit = audit_partitions(records)
    assert audit['provided_patient_ids_partition_disjoint'] is None
    assert audit['patient_disjoint'] is None and audit['patient_id_coverage'] < 1


def test_eligible_activation_keeps_a_recoverable_backup_and_journal(fixture):
    root, active, staged, _, _, review = fixture
    previous, candidate = artifact_identity(active), artifact_identity(staged)
    backup = root / 'releases/run/previous-model'
    result = activate_reviewed_candidate(root, active, staged, backup, review)
    assert result['activated']
    assert artifact_identity(active) == candidate and artifact_identity(backup) == previous
    assert not staged.exists() and not (root / '.cancer-release.lock').exists()
    assert json.loads(Path(result['journal']).read_text())['stage'] == 'activated'


def test_rejected_or_tampered_candidates_leave_the_active_model_unchanged(fixture):
    root, active, staged, _, _, review = fixture
    previous = artifact_identity(active)
    rejected = dict(review, eligible=False, reasons=['a measured regression'])
    with pytest.raises(ValueError, match='did not pass'):
        activate_reviewed_candidate(root, active, staged, root / 'releases/rejected/previous', rejected)
    path = staged / 'manifest.json'; path.write_text(path.read_text().replace('synthetic-release-v1', 'synthetic-release-v2'))
    with pytest.raises(ValueError, match='changed after evaluation'):
        activate_reviewed_candidate(root, active, staged, root / 'releases/tampered/previous', review)
    assert artifact_identity(active) == previous


@pytest.mark.parametrize('failure_stage', ['directory-swap', 'runtime-load', 'journal-write'])
def test_swap_load_or_journal_failure_restores_the_previous_model(fixture, monkeypatch, failure_stage):
    root, active, staged, _, _, review = fixture
    backup = root / 'releases/failed/previous'
    previous, candidate = artifact_identity(active), artifact_identity(staged)
    rename, load, write = Path.rename, cancer_release.load_bundle, Path.write_text

    def failing_rename(path, target):
        if failure_stage == 'directory-swap' and path == staged:
            raise OSError('Synthetic locked directory')
        return rename(path, target)

    def failing_load(path, modality):
        if failure_stage == 'runtime-load' and path == active and backup.exists():
            raise ValueError('Synthetic runtime-load failure')
        return load(path, modality)

    def failing_write(path, data, *args, **kwargs):
        if failure_stage == 'journal-write' and path.name == 'activation.json' and '"activated"' in data:
            raise OSError('Synthetic journal-write failure')
        return write(path, data, *args, **kwargs)

    monkeypatch.setattr(Path, 'rename', failing_rename)
    monkeypatch.setattr(cancer_release, 'load_bundle', failing_load)
    monkeypatch.setattr(Path, 'write_text', failing_write)
    with pytest.raises((OSError, ValueError)):
        activate_reviewed_candidate(root, active, staged, backup, review)
    assert artifact_identity(active) == previous and artifact_identity(staged) == candidate
    assert not backup.exists() and not (root / '.cancer-release.lock').exists()
    assert json.loads((backup.parent / 'activation.json').read_text())['stage'] == 'rolled-back'


def test_release_lock_and_workspace_boundaries_prevent_conflicting_or_outside_moves(fixture, tmp_path):
    root, active, staged, _, _, review = fixture
    previous = artifact_identity(active)
    with pytest.raises(ValueError, match='inside'):
        activate_reviewed_candidate(root, active, staged, tmp_path / 'outside/previous', review)
    lock = root / '.cancer-release.lock'; lock.write_text('synthetic-existing-owner')
    with pytest.raises(FileExistsError):
        activate_reviewed_candidate(root, active, staged, root / 'releases/locked/previous', review)
    assert artifact_identity(active) == previous and lock.read_text() == 'synthetic-existing-owner'


def test_unrecoverable_filesystem_failure_keeps_the_backup_and_records_recovery_state(fixture, monkeypatch):
    root, active, staged, _, _, review = fixture
    backup = root / 'releases/recovery/previous'
    previous = artifact_identity(active)
    rename = Path.rename

    def failing_rename(path, target):
        if path in (staged, backup):
            raise OSError('Synthetic unavailable filesystem')
        return rename(path, target)

    monkeypatch.setattr(Path, 'rename', failing_rename)
    with pytest.raises(RuntimeError, match='restoration failed'):
        activate_reviewed_candidate(root, active, staged, backup, review)
    assert artifact_identity(backup) == previous and staged.exists()
    assert json.loads((backup.parent / 'activation.json').read_text())['stage'] == 'recovery-required'


def test_actual_review_refuses_missing_patient_ids_corrupt_sources_and_class_changes(fixture):
    root, active, staged, image_root, cohort, _ = fixture
    missing = copy.deepcopy(cohort)
    for record in missing['records']:
        record.pop('patient_id')
    refused = review_upgrade(root, 'oral_photo', staged, missing, image_root, activate=True, minimum_per_class=1)
    assert not refused['eligible'] and not refused['activated']
    assert any('Patient identifiers' in reason for reason in refused['reasons'])
    wrong = dict(cohort, labels=['green', 'red'])
    with pytest.raises(ValueError, match='same modality'):
        review_upgrade(root, 'oral_photo', staged, wrong, image_root)
    path = Path(cohort['records'][0]['path']); path.write_bytes(b'corrupt synthetic file')
    with pytest.raises(ValueError, match='fingerprint changed'):
        review_upgrade(root, 'oral_photo', staged, cohort, image_root)


def test_manifest_cache_detects_contract_changes_with_preserved_timestamps(fixture):
    _, active, _, _, _, _ = fixture
    original, _ = load_bundle(active, 'oral_photo')
    path = active / 'manifest.json'; timestamps = path.stat()
    path.write_text(path.read_text().replace('synthetic-release-v1', 'synthetic-release-v2'))
    os.utime(path, ns=(timestamps.st_atime_ns, timestamps.st_mtime_ns))
    updated, _ = load_bundle(active, 'oral_photo')
    assert original.model_version != updated.model_version
