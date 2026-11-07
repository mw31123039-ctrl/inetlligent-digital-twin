"""Software fixtures only; these tests do not train or validate a dental model."""
import hashlib
import importlib.util
import json
import os
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import dental_public as public
from app.dental_photo import PhotoDetectionRequest
from app.dental_learning import LocalDentalLearning
from app.dental_local import train_local_model
from test_dental_local import example


def test_boxes_are_unpadded_clipped_suppressed_and_invalid_outputs_are_rejected():
    output = np.zeros((1, 5, 8400), np.float32)
    output[0, :, 0] = [320, 320, 64, 128, .9]
    output[0, :, 1] = [320, 320, 64, 128, .8]
    output[0, :, 2] = [100, 100, 10, 10, .1]
    boxes = public.candidate_boxes(output, 512, 256, 1.25, 0, 160)
    assert boxes == [[230, 76, 51, 102]]
    with pytest.raises(ValueError):
        public.candidate_boxes(np.zeros((1, 84, 8400)), 512, 256, 1.25, 0, 160)
    output[0, 0, 0] = np.nan
    with pytest.raises(ValueError):
        public.candidate_boxes(output, 512, 256, 1.25, 0, 160)


def test_public_status_requires_training_report_and_unchanged_onnx(monkeypatch, tmp_path):
    assert public.public_status(tmp_path) is None
    model = tmp_path / 'detector.onnx'
    model.write_bytes(b'x' * 100001)
    report = {'format': 'humantwin-public-tooth-detector-v1', 'clinical_validation': False,
              'training_performed': True, 'condition_classifier_trained': False, 'input_size': 640,
              'train_images': 2541, 'validation_images': 246, 'model_sha256': hashlib.sha256(model.read_bytes()).hexdigest()}
    (tmp_path / 'report.json').write_text(json.dumps(report))
    monkeypatch.setattr(public.cv2.dnn, 'readNetFromONNX', lambda _: SimpleNamespace(setPreferableBackend=lambda _: None, setPreferableTarget=lambda _: None))
    status = public.public_status(tmp_path)
    assert status['model_source'] == 'public-dataset' and status['validation_dice'] is None
    assert status['patient_disjoint_verified'] is False and status['external_requests'] is False
    model.write_bytes(b'y' * 100002)
    assert public.public_status(tmp_path) is None


def test_training_progress_is_unavailable_for_detection_and_stale_runs_are_not_reported_running(tmp_path):
    run = tmp_path / 'runs' / 'visible-teeth'
    run.mkdir(parents=True)
    progress = run / 'results.csv'
    progress.write_text('epoch,time\n4,200\n')
    (tmp_path / 'training-plan.json').write_text(json.dumps({'run': 'visible-teeth', 'epochs': 30, 'train_images': 2541, 'validation_images': 246}))
    status = public.public_status(tmp_path)
    assert status['state'] == 'training' and status['training_epoch'] == 4
    assert status['provider_configured'] is False and status['validation_dice'] is None
    os.utime(progress, (time.time() - 240, time.time() - 240))
    assert public.public_status(tmp_path) is None


def test_public_export_preparation_does_not_mix_source_variants_across_splits_or_include_unexpected_files(tmp_path):
    spec = importlib.util.spec_from_file_location('public_trainer', Path(__file__).parents[1] / 'scripts/train-dental-public.py')
    trainer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(trainer)
    archive = tmp_path / 'software-fixture.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        for partition, name in [('train', 'same.rf.variant'), ('valid', 'same.rf.original'), ('test', 'other.rf.original')]:
            bundle.writestr(f'{partition}/images/{name}.jpg', f'SYNTHETIC SOFTWARE FIXTURE {partition}')
            bundle.writestr(f'{partition}/labels/{name}.txt', '18 0.5 0.5 0.1 0.2\n')
    with pytest.raises(ValueError, match='fingerprint'):
        trainer.prepare(archive, tmp_path / 'invalid')
    # Only this test substitutes an archive fingerprint; no weights are trained.
    trainer.ARCHIVE_SHA256 = hashlib.sha256(archive.read_bytes()).hexdigest()
    destination = tmp_path / 'prepared'
    report = trainer.prepare(archive, destination)
    assert report['images'] == {'test': 1, 'valid': 1, 'train': 0}
    assert report['removed_cross_split_duplicates'] == 1 and report['patient_disjoint_verified'] is False
    assert next((destination / 'valid/labels').glob('*.txt')).read_text().startswith('0 ')
    (destination / 'train/images/unexpected.jpg').write_bytes(b'UNEXPECTED SOFTWARE FIXTURE')
    with pytest.raises(ValueError, match='outside this pinned export'):
        trainer.prepare(archive, destination)


def test_inference_uses_photo_pixels_and_never_emits_diagnoses_fdi_or_targets(monkeypatch, tmp_path):
    sample = example(0)
    output = np.zeros((1, 5, 8400), np.float32)
    output[0, :, 0] = [110, 277, 85, 128, .9]
    net = SimpleNamespace(setInput=lambda _: None, forward=lambda: output)
    monkeypatch.setattr(public, '_load', lambda _: (net, {}))
    result = public.detect_public_crowns(tmp_path, PhotoDetectionRequest(photo=sample.photo, consent_local=True))
    assert result.input_sha256 == sample.input_sha256 and result.possible_case_ids == []
    assert result.crowns and all(c.jaw == 'unknown' for c in result.crowns)
    assert result.clinical_validation is False and 'fdi' not in result.model_dump_json() and 'target' not in result.model_dump_json()
    assert not list(tmp_path.iterdir())


def test_personal_training_overrides_shared_baseline_without_sharing_it_with_another_owner(monkeypatch, tmp_path):
    import app.main as main
    private = LocalDentalLearning(tmp_path / 'private')
    monkeypatch.setattr(main, 'learning', private)
    monkeypatch.setattr(main.settings, 'service_key', 'public-model-test-' * 3)
    monkeypatch.setattr(main, 'Settings', lambda: SimpleNamespace(dental_local_model_dir=str(tmp_path / 'operator'), dental_public_model_dir=str(tmp_path / 'shared')))
    monkeypatch.setattr(main, 'public_status', lambda _: {'provider_configured': True, 'model_source': 'public-dataset'})
    sample = example(0)
    owner = 'a' * 64
    try:
        with TestClient(main.app) as client:
            headers = {'X-Service-Key': main.settings.service_key, 'X-Dental-Owner': owner}
            assert client.get('/v1/dental/detection-status', headers=headers).json()['model_source'] == 'public-dataset'
            train_local_model([example(0), example(1), example(2, 'validation')], private.model_path(owner))
            assert 'model_source' not in client.get('/v1/dental/detection-status', headers=headers).json()
            assert client.get('/v1/dental/detection-status', headers={**headers, 'X-Dental-Owner': 'b' * 64}).json()['model_source'] == 'public-dataset'
            monkeypatch.setattr(main, 'detect_public_crowns', lambda *_: pytest.fail('A personal detector must take precedence.'))
            response = client.post('/v1/dental/detect', headers=headers, json={'photo': sample.photo.model_dump(), 'consent_local': True})
            assert response.status_code == 200 and response.json()['possible_case_ids'] == []
    finally:
        private.executor.shutdown(wait=True)
