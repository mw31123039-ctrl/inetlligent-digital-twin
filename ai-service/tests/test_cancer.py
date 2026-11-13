"""Software checks using an untrained color classifier, never medical validation."""
import base64
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.cancer import MODALITIES, CancerRequest, ModelManifest, cancer_status, decode_image, infer_cancer, output_scores, prepare_input

FIXTURE = Path(__file__).parent / 'fixtures/cancer-software-fixture.onnx'


def manifest(track='skin', modality='skin_photo'):
    return dict(schema_version='humantwin-cancer-model-v1', track=track, modality=modality,
                model_version='synthetic-software-test-v1', target='Untrained color classifier for software tests',
                source_url='https://example.invalid/software-test', license='CC0 untrained software fixture',
                weights_sha256=hashlib.sha256(FIXTURE.read_bytes()).hexdigest(), input_size=[32, 32], color='RGB',
                resize='stretch', scale=1 / 255, mean=[0, 0, 0], std=[1, 1, 1], labels=['test_red', 'test_green'], output='logits',
                evaluation=dict(reference='Synthetic software test only; no clinical subjects', patient_disjoint=True,
                                held_out_subjects=1, sensitivity=.5, specificity=.5), research_only=True)


def install(root, track='skin', modality='skin_photo', changes=None):
    directory = root / modality
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'model.onnx').write_bytes(FIXTURE.read_bytes())
    (directory / 'manifest.json').write_text(json.dumps(manifest(track, modality) | (changes or {})))
    return directory


def payload(track='skin', modality='skin_photo', color=(0, 0, 255)):
    image = np.full((48, 64, 3), color, np.uint8)
    success, raw = cv2.imencode('.jpg', image)
    assert success
    return dict(track=track, modality=modality, image_data_url='data:image/jpeg;base64,' + base64.b64encode(raw).decode(),
                consent_local=True, modality_confirmed=True, research_only_acknowledged=True)


def test_empty_registry_has_all_pathways_without_findings_or_configured_models(tmp_path):
    result = cancer_status(tmp_path)
    assert [path['track'] for path in result['pathways']] == list(MODALITIES)
    assert len([model for path in result['pathways'] for model in path['models']]) == 7
    assert all(not model['configured'] for path in result['pathways'] for model in path['models'])
    assert result['clinical_validation'] is False and result['external_requests'] is False
    with pytest.raises(FileNotFoundError):
        infer_cancer(tmp_path, CancerRequest(**payload()))


@pytest.mark.parametrize('track,modality', [(track, modality) for track, values in MODALITIES.items() for modality in values])
def test_real_opencv_onnx_inference_for_every_input_is_bound_to_image_and_model(tmp_path, track, modality):
    install(tmp_path, track, modality)
    request = CancerRequest(**payload(track, modality))
    result = infer_cancer(tmp_path, request)
    raw = base64.b64decode(request.image_data_url.split(',')[1])
    assert result.input_sha256 == hashlib.sha256(raw).hexdigest()
    assert result.weights_sha256 == manifest()['weights_sha256']
    assert result.track == track and result.modality == modality
    assert result.scores[0].value > result.scores[1].value  # RGB order, not OpenCV's BGR order.
    green = infer_cancer(tmp_path, CancerRequest(**payload(track, modality, (0, 255, 0))))
    assert green.scores[1].value > green.scores[0].value
    assert green.input_sha256 != result.input_sha256
    assert sum(item.value for item in result.scores) == pytest.approx(1)
    assert result.clinical_validation is False and result.calibrated_cancer_probability is False
    assert result.scope == 'single-2d-image'


def test_corrupt_changed_wrong_modality_or_incompatible_models_remain_disabled(tmp_path):
    directory = install(tmp_path)
    assert cancer_status(tmp_path)['pathways'][0]['models'][0]['configured'] is True
    (directory / 'model.onnx').write_bytes(b'corrupt model')
    assert cancer_status(tmp_path)['pathways'][0]['models'][0]['state'] == 'invalid-artifacts'
    install(tmp_path, changes={'modality': 'dermoscopy'})
    assert cancer_status(tmp_path)['pathways'][0]['models'][0]['configured'] is False
    install(tmp_path, changes={'labels': ['one', 'two', 'three']})
    assert cancer_status(tmp_path)['pathways'][0]['models'][0]['configured'] is False


@pytest.mark.parametrize('changes', [
    {'consent_local': False}, {'modality_confirmed': False}, {'research_only_acknowledged': False},
    {'track': 'lung'}, {'modality': '../skin_photo'}, {'image_data_url': 'https://example.invalid/patient.jpg'},
    {'image_data_url': 'data:image/png;base64,AAAA'}, {'subject_id': 'not-forwarded'},
])
def test_request_rejects_missing_permissions_cross_pathway_input_and_extra_health_fields(changes):
    with pytest.raises(ValidationError):
        CancerRequest(**(payload() | changes))


def test_preprocessing_matches_explicit_contract_and_invalid_outputs_fail_closed():
    config = ModelManifest(**manifest())
    pixels = np.full((48, 64, 3), (0, 64, 255), np.uint8)
    blob = prepare_input(pixels, config)
    assert blob.shape == (1, 3, 32, 32)
    assert blob[0, 0, 0, 0] == pytest.approx(1)
    assert blob[0, 1, 0, 0] == pytest.approx(64 / 255)
    for invalid in [np.array([[np.nan, 0]]), np.array([[np.inf, 0]]), np.zeros((1, 2, 1, 1)), np.zeros((1, 3))]:
        with pytest.raises(ValueError):
            output_scores(invalid, config)
    probabilities = config.model_copy(update={'output': 'probabilities'})
    for invalid in [np.array([.8, .8]), np.array([-1, 2])]:
        with pytest.raises(ValueError):
            output_scores(invalid, probabilities)
    with pytest.raises(ValidationError):
        ModelManifest(**(manifest() | {'std': [1, 0, 1]}))


def test_invalid_or_oversized_jpeg_is_rejected_before_opencv_decode(monkeypatch):
    raw = bytearray(base64.b64decode(payload()['image_data_url'].split(',')[1]))
    index = raw.index(b'\xff\xc0')
    raw[index + 5:index + 7] = (30000).to_bytes(2, 'big')
    monkeypatch.setattr(cv2, 'imdecode', lambda *_: pytest.fail('Oversized JPEG must not be decoded'))
    with pytest.raises(ValueError):
        decode_image('data:image/jpeg;base64,' + base64.b64encode(raw).decode())
    with pytest.raises(ValueError):
        decode_image('data:image/jpeg;base64,AAAA')


def test_real_onnxruntime_inference_and_occlusion_return_measured_evidence(tmp_path):
    install(tmp_path, changes={'runtime': 'onnxruntime', 'interpolation': 'pil-bilinear',
                              'evaluation': {'reference': 'Software fixture only; patient evidence unknown',
                                             'patient_disjoint': None, 'held_out_subjects': None,
                                             'sensitivity': None, 'specificity': None}})
    request = CancerRequest(**(payload() | {'explain': True}))
    result = infer_cancer(tmp_path, request)
    assert result.runtime == 'onnxruntime-cpu' and result.inference_ms > 0
    assert result.model_info.patient_disjoint is None
    assert result.explanation.target_label == 'test_red'
    assert result.explanation.grid_size == 4 and len(result.explanation.values) == 16
    assert result.explanation.max_score_drop > 0
    assert result.explanation.localization is False
    assert result.explanation.method == 'occlusion-sensitivity'
    assert all(0 <= item <= 1 for item in result.explanation.values)
    assert 0 < result.uncertainty.normalized_entropy < 1 and result.uncertainty.margin > 0
    assert result.uncertainty.interpretation == 'research-only'
    assert (result.image_checks.width, result.image_checks.height) == (64, 48)
    assert any('Low image contrast' in item for item in result.image_checks.warnings)
    assert infer_cancer(tmp_path, CancerRequest(**payload())).explanation is None


def test_unknown_evaluation_is_retained_without_inventing_independent_patient_claims():
    value = manifest()
    value['evaluation'] = {'reference': 'Public research model; no patient separation reported'}
    parsed = ModelManifest(**value)
    assert parsed.evaluation.patient_disjoint is None
    assert parsed.evaluation.held_out_subjects is None
    assert parsed.evaluation.sensitivity is None and parsed.evaluation.specificity is None


def test_private_routes_require_service_secret_and_never_return_results_without_a_model(monkeypatch, tmp_path):
    from app import main
    monkeypatch.setattr(main.settings, 'service_key', 's' * 40)
    monkeypatch.setenv('CANCER_MODEL_DIR', str(tmp_path))
    with TestClient(main.app) as client:
        assert client.get('/v1/cancer/status').status_code == 401
        assert client.post('/v1/cancer/analyze', json=payload()).status_code == 401
        headers = {'X-Service-Key': 's' * 40}
        response = client.get('/v1/cancer/status', headers=headers)
        assert response.status_code == 200 and response.headers['cache-control'] == 'no-store, private'
        failed = client.post('/v1/cancer/analyze', headers=headers, json=payload())
        assert failed.status_code == 503 and 'scores' not in failed.json()
        rejected = client.post('/v1/cancer/analyze', headers=headers, json=payload() | {'consent_local': False})
        assert rejected.status_code == 422 and 'image_data_url' not in rejected.text
        install(tmp_path)
        accepted = client.post('/v1/cancer/analyze', headers=headers, json=payload())
        assert accepted.status_code == 200 and accepted.json()['clinical_validation'] is False
