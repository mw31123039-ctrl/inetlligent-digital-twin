import base64
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.dental_photo import CrownOutline, PhotoDetectionRequest, PhotoDetectionResult, PhotoOutlineDecision

POINTS = [{'x': .2, 'y': .2}, {'x': .3, 'y': .2}, {'x': .3, 'y': .5}, {'x': .2, 'y': .5}]
RAW = b'\xff\xd8\xff' + b'0' * 100 + b'\xff\xd9'


def payload():
    return {'photo': {'view': 'Frontal bite', 'data_url': 'data:image/jpeg;base64,' + base64.b64encode(RAW).decode()}, 'consent_local': True}


def test_crown_boundaries_reject_crossing_out_of_range_and_degenerate_geometry():
    CrownOutline(jaw='upper', points=POINTS)
    for bad in [[], [POINTS[0], POINTS[2], POINTS[1], POINTS[3]], [{'x': -1, 'y': .2}, *POINTS[1:]], [{'x': .2, 'y': .2}] * 4]:
        with pytest.raises(ValidationError):
            CrownOutline(jaw='upper', points=bad)


def test_unusable_photo_does_not_have_findings_and_hidden_anatomy_is_not_classified():
    for bad in [
        {'image_quality': 'insufficient', 'crowns': [{'jaw': 'upper', 'points': POINTS}], 'possible_case_ids': []},
        {'image_quality': 'usable', 'crowns': [], 'possible_case_ids': []},
        {'image_quality': 'usable', 'crowns': [{'jaw': 'upper', 'points': POINTS}], 'possible_case_ids': ['impacted-canine']},
    ]:
        with pytest.raises(ValidationError):
            PhotoOutlineDecision.model_validate(bad)


def test_private_local_detection_requires_auth_and_local_consent_and_never_uses_external_provider(monkeypatch, tmp_path):
    import app.main as main
    monkeypatch.setattr(main.settings, 'service_key', 'internal-test-key-' * 3)
    monkeypatch.setattr(main, 'Settings', lambda: SimpleNamespace(dental_local_model_dir=str(tmp_path), dental_public_model_dir=str(tmp_path / 'public')))
    def forbidden(*args, **kwargs):
        pytest.fail('Local dental endpoint must never instantiate an external provider.')
    monkeypatch.setattr(main.OpenAIProvider, '__init__', forbidden)
    with TestClient(main.app) as client:
        headers = {'X-Service-Key': main.settings.service_key}
        assert client.post('/v1/dental/detect', json=payload()).status_code == 401
        for change in [{'consent_local':False}, {'consent_external':True}]:
            invalid = client.post('/v1/dental/detect', headers=headers, json={**payload(), **change})
            assert invalid.status_code == 422 and 'base64' not in invalid.text
        assert client.post('/v1/dental/detect', headers=headers, json=payload()).status_code == 503
        status = client.get('/v1/dental/detection-status', headers=headers).json()
        assert status['runtime'] == 'local' and status['external_requests'] is False
        assert status['provider_configured'] is False and status['state'] == 'not-trained'
        assert str(tmp_path) not in json.dumps(status)


def test_shared_detection_schema_has_not_drifted():
    schema = json.loads(Path('../contracts/dental/photo-detection.schema.json').read_text())
    schema.pop('$schema')
    assert schema == PhotoDetectionResult.model_json_schema()
