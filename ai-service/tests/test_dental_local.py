import base64
import hashlib
import json
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.dental_local import TrainingExample, LocalSegmentRequest, decode_photo, detect_local_crowns, local_status, refine_local_outline, train_local_model
from app.dental_photo import PhotoDetectionRequest


def example(index, partition='train'):
    # Synthetic software fixture, never installed as a patient/dental model.
    rng = np.random.default_rng(index + 7)
    image = rng.integers(25, 110, (100, 180, 3), dtype=np.uint8)
    x, y = 20 + index * 16, 20 + (index % 3) * 7
    image[y:y + 36, x:x + 24] = [215, 225, 230]
    ok, encoded = cv2.imencode('.jpg', image)
    assert ok
    raw = encoded.tobytes()
    points = [{'x': x / 179, 'y': y / 99}, {'x': (x + 23) / 179, 'y': y / 99},
              {'x': (x + 23) / 179, 'y': (y + 35) / 99}, {'x': x / 179, 'y': (y + 35) / 99}]
    return TrainingExample(schema_version='humantwin-local-crowns-v1', subject_code=f'SUBJECT_{index}', reviewer_code='REVIEWER_TEST',
        partition=partition, permission_training=True, complete_annotation=True,
        photo={'view': 'Frontal bite', 'data_url': 'data:image/jpeg;base64,' + base64.b64encode(raw).decode()},
        input_sha256=hashlib.sha256(raw).hexdigest(), crowns=[{'jaw':'upper', 'points':points}])


def test_actual_supervised_learning_serialization_and_inference_stay_local(tmp_path):
    samples = [example(0), example(1), example(2, 'validation'), example(3, 'test')]
    assert local_status(tmp_path)['provider_configured'] is False
    report = train_local_model(samples, tmp_path)
    assert report['training_performed'] is True and report['clinical_validation'] is False
    assert report['train_subjects'] == 2 and report['validation_subjects'] == 1
    assert report['validation']['foreground_dice'] > .8
    assert report['test']['images'] == 1
    assert 'SUBJECT_' not in json.dumps(report) and 'data:image' not in json.dumps(report)
    assert local_status(tmp_path)['state'] == 'trained-unvalidated'
    result = detect_local_crowns(tmp_path, PhotoDetectionRequest(photo=example(4).photo, consent_local=True))
    assert result.crowns and result.input_sha256 == example(4).input_sha256
    assert result.possible_case_ids == [] and result.crowns[0].jaw == 'unknown'
    assert not hasattr(result.crowns[0], 'target') and result.clinical_validation is False
    assert not list(tmp_path.rglob('*.jpg'))
    pointer = (tmp_path / 'current.json').read_bytes()
    with pytest.raises(ValueError):
        train_local_model([example(0)], tmp_path)
    assert (tmp_path / 'current.json').read_bytes() == pointer
    model = next(tmp_path.rglob('forest.xml'))
    model.write_text('corrupted')
    assert local_status(tmp_path)['provider_configured'] is False


def test_training_blocks_subject_leakage_duplicate_images_unreviewed_and_mismatched_exports(tmp_path):
    samples = [example(0), example(1), example(2, 'validation')]
    for field in ('permission_training', 'complete_annotation'):
        with pytest.raises(ValidationError):
            TrainingExample.model_validate({**samples[0].model_dump(), field:False})
    leaked = samples[2].model_copy(update={'subject_code': samples[0].subject_code.lower()})
    with pytest.raises(ValueError, match='same partition'):
        train_local_model([*samples[:2], leaked], tmp_path)
    duplicate = samples[0].model_copy(update={'subject_code':'OTHER', 'partition':'validation'})
    with pytest.raises(ValueError, match='duplicate image'):
        train_local_model([*samples[:2], duplicate], tmp_path)
    mismatch = samples[2].model_copy(update={'input_sha256':'a' * 64})
    with pytest.raises(ValueError, match='fingerprint mismatch'):
        train_local_model([*samples[:2], mismatch], tmp_path)
    overlap = samples[0].model_copy(update={'crowns': samples[0].crowns * 2})
    with pytest.raises(ValueError, match='non-overlapping'):
        train_local_model([overlap, *samples[1:]], tmp_path)
    assert not (tmp_path / 'current.json').exists()


def test_assisted_segmentation_fits_photo_pixels_without_saved_weights_or_training():
    sample = example(0)
    result = refine_local_outline(LocalSegmentRequest(photo=sample.photo, consent_local=True, prompt=sample.crowns[0]))
    assert len(result.crowns) == 1
    assert result.input_sha256 == sample.input_sha256 and result.possible_case_ids == []
    assert result.crowns[0].jaw == 'upper'
    assert max(p.x for p in result.crowns[0].points) < .3


def test_local_service_reloads_new_model_without_restart_and_refines_without_any_external_call(monkeypatch, tmp_path):
    import app.main as main
    monkeypatch.setattr(main.settings, 'service_key', 'private-test-service-' * 2)
    monkeypatch.setattr(main, 'Settings', lambda: SimpleNamespace(dental_local_model_dir=str(tmp_path), dental_public_model_dir=str(tmp_path / 'public')))
    sample = example(0)
    with TestClient(main.app) as client:
        headers = {'X-Service-Key': main.settings.service_key}
        body = {'photo':sample.photo.model_dump(), 'consent_local':True, 'prompt':sample.crowns[0].model_dump()}
        assert client.post('/v1/dental/segment', json=body).status_code == 401
        response = client.post('/v1/dental/segment', headers=headers, json=body)
        assert response.status_code == 200 and response.json()['input_sha256'] == sample.input_sha256
        assert response.headers['cache-control'] == 'no-store, private'
        assert client.get('/v1/dental/detection-status', headers=headers).json()['provider_configured'] is False
        train_local_model([example(0), example(1), example(2, 'validation')], tmp_path)
        assert client.get('/v1/dental/detection-status', headers=headers).json()['provider_configured'] is True
        response = client.post('/v1/dental/detect', headers=headers, json={'photo':sample.photo.model_dump(), 'consent_local':True})
        assert response.status_code == 200 and response.json()['possible_case_ids'] == []


def test_invalid_jpeg_and_oversized_dimensions_are_rejected_before_inference():
    sample = example(0)
    raw = base64.b64decode(sample.photo.data_url.split(',')[1])
    # Corrupt SOF width to exceed the decode bound.
    marker = raw.index(b'\xff\xc0')
    oversized = raw[:marker + 7] + b'\xff\xff' + raw[marker + 9:]
    bad = sample.photo.model_copy(update={'data_url':'data:image/jpeg;base64,' + base64.b64encode(oversized).decode()})
    with pytest.raises(ValueError, match='1024'):
        decode_photo(bad)
