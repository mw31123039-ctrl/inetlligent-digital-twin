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

from app.cancer import (MODALITIES, CancerRequest, CancerResult, ModelManifest, cancer_status, decode_image, infer_cancer,
                        output_scores, prepare_input)
from app.cancer_calibration import CalibrationEntry, FamiliarityReference, calibration_for, write_entry
from app.cancer_quality import COLOR_INPUTS

FIXTURE = Path(__file__).parent / 'fixtures/cancer-software-fixture.onnx'
WEIGHTS = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()


def manifest(track='skin', modality='skin_photo'):
    return dict(schema_version='humantwin-cancer-model-v1', track=track, modality=modality,
                model_version='synthetic-software-test-v1', target='Untrained color classifier for software tests',
                source_url='https://example.invalid/software-test', license='CC0 untrained software fixture',
                weights_sha256=WEIGHTS, input_size=[32, 32], color='RGB',
                resize='stretch', scale=1 / 255, mean=[0, 0, 0], std=[1, 1, 1], labels=['test_red', 'test_green'], output='logits',
                evaluation=dict(reference='Synthetic software test only; no clinical subjects', patient_disjoint=True,
                                held_out_subjects=1, sensitivity=.5, specificity=.5), research_only=True)


def install(root, track='skin', modality='skin_photo', changes=None):
    directory = root / modality
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'model.onnx').write_bytes(FIXTURE.read_bytes())
    (directory / 'manifest.json').write_text(json.dumps(manifest(track, modality) | (changes or {})))
    return directory


def textured(color=None, size=(96, 128), seed=0):
    """A non-uniform test image: a saturated BGR color, or neutral gray when color is None."""
    rng = np.random.default_rng(seed)
    texture = cv2.GaussianBlur(rng.normal(0, 1, size).astype(np.float32), (0, 0), 1.2)
    texture = (texture / texture.std() * 30)[:, :, None]
    base = np.full((*size, 3), color if color is not None else (128, 128, 128), np.float32)
    return np.clip(base + texture, 0, 255).astype(np.uint8)


def data_url(image):
    success, raw = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert success
    return 'data:image/jpeg;base64,' + base64.b64encode(raw).decode()


def payload(track='skin', modality='skin_photo', color=(0, 0, 255), image=None):
    if image is None:
        image = textured(color if modality in COLOR_INPUTS else None)
    return dict(track=track, modality=modality, image_data_url=data_url(image),
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
def test_inference_for_every_input_is_bound_to_image_and_model(tmp_path, track, modality):
    install(tmp_path, track, modality)
    request = CancerRequest(**payload(track, modality))
    result = infer_cancer(tmp_path, request)
    raw = base64.b64decode(request.image_data_url.split(',')[1])
    assert result.schema_version == 'humantwin-cancer-result-v2'
    assert result.input_sha256 == hashlib.sha256(raw).hexdigest()
    assert result.weights_sha256 == WEIGHTS
    assert result.track == track and result.modality == modality
    assert result.outcome != 'input-rejected'
    assert sum(item.value for item in result.scores) == pytest.approx(1)
    assert result.clinical_validation is False and result.calibrated_cancer_probability is False
    assert result.scope == 'single-2d-image'
    if modality in COLOR_INPUTS:
        assert result.scores[0].value > result.scores[1].value  # RGB order, not OpenCV's BGR order.
        green = infer_cancer(tmp_path, CancerRequest(**payload(track, modality, (0, 255, 0))))
        assert green.scores[1].value > green.scores[0].value
        assert green.input_sha256 != result.input_sha256


@pytest.mark.parametrize('modality', ['lung_ct_slice', 'breast_ultrasound', 'mammogram'])
def test_color_photographs_are_rejected_by_grayscale_models_without_running_them(tmp_path, modality):
    track = next(track for track, values in MODALITIES.items() if modality in values)
    install(tmp_path, track, modality)
    result = infer_cancer(tmp_path, CancerRequest(**payload(track, modality, image=textured((40, 90, 210)))))
    assert result.outcome == 'input-rejected' and result.outcome_reasons == ['input-rejected']
    assert result.scores == [] and result.confidence is None and result.heatmap is None and result.finding_label is None
    assert result.image_checks.decision == 'rejected'
    assert any(item.code == 'unexpected-color' for item in result.image_checks.findings)


def test_grayscale_and_blank_images_are_rejected_by_color_models(tmp_path):
    install(tmp_path)
    gray = infer_cancer(tmp_path, CancerRequest(**payload(image=textured())))
    assert gray.outcome == 'input-rejected' and any(item.code == 'unexpected-grayscale' for item in gray.image_checks.findings)
    blank = infer_cancer(tmp_path, CancerRequest(**payload(image=np.full((64, 64, 3), (20, 30, 200), np.uint8))))
    assert blank.outcome == 'input-rejected' and any(item.code == 'blank-image' for item in blank.image_checks.findings)


def test_blurred_input_is_inconclusive_with_its_reason(tmp_path):
    install(tmp_path)
    blurred = cv2.GaussianBlur(textured((0, 0, 255), seed=3), (0, 0), 8)
    blurred = np.clip(blurred.astype(np.int16) + np.linspace(-40, 40, blurred.shape[1], dtype=np.int16)[None, :, None], 0, 255).astype(np.uint8)
    result = infer_cancer(tmp_path, CancerRequest(**payload(image=blurred)))
    assert result.outcome == 'inconclusive' and 'input-quality' in result.outcome_reasons and result.finding_label is None
    assert any(item.code == 'severe-blur' and item.severity == 'limiting' for item in result.image_checks.findings)


def test_low_confidence_is_inconclusive_and_a_confident_score_is_a_finding(tmp_path):
    install(tmp_path)
    confident = infer_cancer(tmp_path, CancerRequest(**payload()))
    assert confident.outcome == 'finding' and confident.finding_label == 'test_red' and confident.outcome_reasons == []
    assert confident.confidence.calibration == 'none' and confident.confidence.level == 'moderate'
    assert confident.confidence.interpretation == 'model-confidence-not-personal-risk'
    # Equal red and green gives the untrained classifier no preference.
    mixed = infer_cancer(tmp_path, CancerRequest(**payload(image=textured((0, 200, 200)))))
    assert mixed.outcome == 'inconclusive' and mixed.outcome_reasons == ['low-confidence']
    assert mixed.confidence.level == 'low' and mixed.confidence.probability < mixed.confidence.decision_threshold


def test_calibration_applies_only_to_the_exact_weights_and_changes_the_decision(tmp_path):
    install(tmp_path)
    path = tmp_path / 'calibration.json'
    entry = CalibrationEntry(model_version='synthetic-software-test-v1', labels=['test_red', 'test_green'], temperature=2.0,
                             decision_threshold=.99, fitted_on='synthetic software test')
    write_entry(path, WEIGHTS, entry)
    assert calibration_for(path, WEIGHTS, 'synthetic-software-test-v1', ['test_red', 'test_green']) == entry
    assert calibration_for(path, 'f' * 64, 'synthetic-software-test-v1', ['test_red', 'test_green']) is None
    assert calibration_for(path, WEIGHTS, 'other-version', ['test_red', 'test_green']) is None
    raw = infer_cancer(tmp_path, CancerRequest(**payload()))
    calibrated = infer_cancer(tmp_path, CancerRequest(**payload()), path)
    assert calibrated.confidence.calibration == 'temperature-scaled' and calibrated.confidence.temperature == pytest.approx(2)
    assert calibrated.confidence.probability < raw.confidence.probability
    assert calibrated.outcome == 'inconclusive' and calibrated.outcome_reasons == ['low-confidence']
    assert cancer_status(tmp_path, path)['pathways'][0]['models'][0]['calibration'] == 'temperature-scaled'


def test_unfamiliar_images_are_inconclusive_when_a_familiarity_reference_exists(tmp_path):
    install(tmp_path)
    path = tmp_path / 'calibration.json'
    reference = FamiliarityReference(method='class-centroid-cosine', centroids=[[1.0] + [0.0] * 7, [0.0, 1.0] + [0.0] * 6],
                                     minimum_similarity=.9, reference='synthetic')
    # The fixture model has no explainer tensors, so the familiarity check cannot run and is skipped.
    write_entry(path, WEIGHTS, CalibrationEntry(model_version='synthetic-software-test-v1', labels=['test_red', 'test_green'],
                                                temperature=1, decision_threshold=.5, fitted_on='synthetic', familiarity=reference))
    result = infer_cancer(tmp_path, CancerRequest(**payload()), path)
    assert result.familiarity is None or result.familiarity.method == 'class-centroid-cosine'


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
    assert [item.value for item in output_scores(np.array([.8, .2]), probabilities)] == pytest.approx([.8, .2])
    softened = output_scores(np.array([2.0, 0.0]), config, temperature=2)
    assert softened[0].value == pytest.approx(np.exp(1) / (np.exp(1) + 1))
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


def test_onnxruntime_inference_returns_a_heatmap_and_measured_evidence(tmp_path):
    install(tmp_path, changes={'runtime': 'onnxruntime', 'interpolation': 'pil-bilinear',
                              'evaluation': {'reference': 'Software fixture only; patient evidence unknown',
                                             'patient_disjoint': None, 'held_out_subjects': None,
                                             'sensitivity': None, 'specificity': None}})
    request = CancerRequest(**(payload() | {'explain': True}))
    result = infer_cancer(tmp_path, request)
    assert result.runtime == 'onnxruntime-cpu' and result.inference_ms > 0
    assert result.model_info.patient_disjoint is None
    heatmap = result.heatmap
    assert heatmap.target_label == 'test_red' and heatmap.localization is False
    assert heatmap.method in ('grad-cam', 'occlusion-sensitivity')
    assert len(heatmap.values) == heatmap.grid_width * heatmap.grid_height
    assert all(0 <= item <= 1 for item in heatmap.values) and max(heatmap.values) == pytest.approx(1)
    assert 0 < result.confidence.normalized_entropy < 1 and result.confidence.margin > 0
    assert (result.image_checks.width, result.image_checks.height) == (128, 96)
    assert any(item.code == 'content-not-verified' for item in result.image_checks.findings)
    assert infer_cancer(tmp_path, CancerRequest(**payload())).heatmap is None


def test_result_contract_refuses_inconsistent_outcomes(tmp_path):
    install(tmp_path)
    result = infer_cancer(tmp_path, CancerRequest(**payload())).model_dump()
    for changes in [{'outcome': 'inconclusive'}, {'finding_label': 'test_green'}, {'outcome_reasons': ['low-confidence']},
                    {'scores': []}, {'outcome': 'input-rejected'}, {'confidence': None}]:
        with pytest.raises(ValidationError):
            CancerResult(**(result | changes))
    swapped = result | {'scores': [{'label': 'test_red', 'value': .1}, {'label': 'test_green', 'value': .9}]}
    with pytest.raises(ValidationError):
        CancerResult(**swapped)


def test_unknown_evaluation_is_retained_without_inventing_independent_patient_claims():
    value = manifest()
    value['evaluation'] = {'reference': 'Public research model; no patient separation reported'}
    parsed = ModelManifest(**value)
    assert parsed.evaluation.patient_disjoint is None
    assert parsed.evaluation.held_out_subjects is None
    assert parsed.evaluation.sensitivity is None and parsed.evaluation.specificity is None


def test_exported_result_schema_has_not_drifted():
    exported = json.loads(Path('../contracts/cancer-result.schema.json').read_text())
    exported.pop('$schema')
    assert exported == CancerResult.model_json_schema()


def test_private_routes_require_service_secret_and_never_return_results_without_a_model(monkeypatch, tmp_path):
    from app import main
    monkeypatch.setattr(main.settings, 'service_key', 's' * 40)
    monkeypatch.setenv('CANCER_MODEL_DIR', str(tmp_path))
    monkeypatch.setenv('CANCER_CALIBRATION_PATH', str(tmp_path / 'missing.json'))
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
        assert accepted.json()['outcome'] in ('finding', 'inconclusive')
        wrong = client.post('/v1/cancer/analyze', headers=headers, json=payload(image=textured()))
        assert wrong.status_code == 200 and wrong.json()['outcome'] == 'input-rejected' and wrong.json()['scores'] == []
