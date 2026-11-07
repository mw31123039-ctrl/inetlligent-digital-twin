import base64

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.dental import DentalPhoto


def test_photo_input_rejects_remote_urls_invalid_encodings_and_non_jpeg():
    for value in ['https://example.invalid/private.jpg', 'data:image/jpeg;base64,INVALID', 'data:image/png;base64,' + base64.b64encode(b'not-jpeg').decode()]:
        with pytest.raises(ValidationError):
            DentalPhoto(view='Frontal bite', data_url=value)


def test_external_dental_review_is_disabled_even_when_general_provider_is_configured(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main.settings, 'service_key', 'test-internal-key-' * 3)
    monkeypatch.setattr(main, 'configured', True)
    with TestClient(main.app) as client:
        assert client.post('/v1/dental/review', json={}).status_code == 401
        response = client.post('/v1/dental/review', headers={'X-Service-Key': main.settings.service_key}, json={'question':'PRIVATE input'})
        assert response.status_code == 503
        assert 'disabled' in response.json()['detail']
        assert 'PRIVATE' not in response.text
