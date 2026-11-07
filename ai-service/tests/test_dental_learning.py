import json
import threading

import pytest
from fastapi.testclient import TestClient

from app.dental_learning import LearningConflict, LocalDentalLearning
from app.dental_local import detect_local_crowns
from app.dental_local import annotation_mask, decode_photo
from app.dental_photo import PhotoDetectionRequest
from test_dental_local import example

OWNER = 'a' * 64
OTHER = 'b' * 64


@pytest.fixture
def learning(tmp_path):
    service = LocalDentalLearning(tmp_path)
    yield service
    service.executor.shutdown(wait=True)


def fill(service):
    for item in [example(0), example(1), example(2, 'validation')]:
        service.save(OWNER, item)


def test_teaching_is_explicit_persistent_account_scoped_and_redacts_image_bytes_from_status(learning):
    assert learning.status(OWNER)['examples'] == []
    saved = learning.save(OWNER, example(0))
    assert saved['subjects']['train'] == 1 and saved['can_train'] is False
    assert saved['job']['state'] == 'idle'
    assert 'data:image' not in json.dumps(saved)
    assert learning.status(OTHER)['examples'] == []
    with pytest.raises(KeyError):
        learning.remove(OTHER, example(0).input_sha256)
    reopened = LocalDentalLearning(learning.directory)
    try:
        assert len(reopened.status(OWNER)['examples']) == 1
    finally:
        reopened.executor.shutdown(wait=True)
    with pytest.raises(LearningConflict, match='same partition'):
        learning.save(OWNER, example(3, 'validation').model_copy(update={'subject_code':'subject_0'}))
    with pytest.raises(ValueError):
        learning.owner_path('../outside')


def test_button_training_runs_real_learning_activates_own_model_and_deletion_invalidates_it(learning):
    with pytest.raises(LearningConflict, match='two training subjects'):
        learning.start(OWNER)
    fill(learning)
    assert learning.status(OWNER)['can_train'] is True
    learning.start(OWNER)
    learning.futures[OWNER].result(timeout=30)
    status = learning.status(OWNER)
    assert status['job']['state'] == 'complete'
    assert status['model']['provider_configured'] is True
    assert status['model']['validation_dice'] > .8
    assert learning.status(OTHER)['model']['provider_configured'] is False
    request = PhotoDetectionRequest(photo=example(4).photo, consent_local=True)
    assert detect_local_crowns(learning.model_path(OWNER), request).crowns
    remaining = learning.remove(OWNER, example(0).input_sha256)
    assert len(remaining['examples']) == 2
    assert remaining['model']['provider_configured'] is False
    assert not learning.model_path(OWNER).exists()


def test_corrected_example_replaces_prior_label_without_duplicating_the_photo(learning):
    fill(learning)
    corrected = example(0).model_copy(deep=True)
    corrected.crowns[0].points[0].x += .002
    state = learning.save(OWNER, corrected)
    assert len(state['examples']) == 3
    with learning._connection(OWNER) as connection:
        data = json.loads(connection.execute('SELECT data FROM examples WHERE id=?', (corrected.input_sha256,)).fetchone()[0])
    assert data['crowns'][0]['points'][0]['x'] == corrected.crowns[0].points[0].x


def test_adjacent_crowns_can_share_a_boundary_without_overlapping_interiors():
    sample = example(0)
    adjacent = sample.crowns[0].model_copy(deep=True)
    for point in adjacent.points:
        point.x += 23 / 179
    image, _ = decode_photo(sample.photo)
    labels = annotation_mask(image, [sample.crowns[0], adjacent])
    assert labels[30, 43] == 2
    assert labels[30, 30] == 1 and labels[30, 55] == 1


def test_changed_teaching_set_discards_in_flight_training_and_blocks_overlapping_jobs(learning, monkeypatch):
    import app.dental_learning as module
    original = module.train_local_model
    started, release = threading.Event(), threading.Event()
    def paused(*args, **kwargs):
        started.set()
        assert release.wait(timeout=20)
        return original(*args, **kwargs)
    monkeypatch.setattr(module, 'train_local_model', paused)
    fill(learning)
    learning.start(OWNER)
    assert started.wait(timeout=5)
    try:
        with pytest.raises(LearningConflict, match='already running'):
            learning.start(OWNER)
        learning.remove(OWNER, example(0).input_sha256)
    finally:
        release.set()
    learning.futures[OWNER].result(timeout=30)
    assert learning.status(OWNER)['job']['state'] == 'discarded'
    assert not learning.status(OWNER)['model']['provider_configured']
    assert list(learning.owner_path(OWNER).glob('job-*')) == []


def test_private_learning_endpoints_require_owner_and_fresh_training_consent(monkeypatch, learning):
    import app.main as main
    monkeypatch.setattr(main, 'public_status', lambda _: None)
    monkeypatch.setattr(main, 'learning', learning)
    monkeypatch.setattr(main.settings, 'service_key', 'private-learning-service-key-' * 2)
    headers = {'X-Service-Key':main.settings.service_key, 'X-Dental-Owner':OWNER}
    with TestClient(main.app) as client:
        assert client.get('/v1/dental/learning').status_code == 401
        assert client.get('/v1/dental/learning', headers={'X-Service-Key':main.settings.service_key}).status_code == 401
        bad = {**example(0).model_dump(), 'permission_training':False}
        response = client.post('/v1/dental/learning/examples', headers=headers, json=bad)
        assert response.status_code == 422 and 'base64' not in response.text
        for item in [example(0), example(1), example(2, 'validation')]:
            assert client.post('/v1/dental/learning/examples', headers=headers, json=item.model_dump()).status_code == 200
        assert client.post('/v1/dental/learning/train', headers=headers, json={'consent_training':False}).status_code == 422
        assert client.post('/v1/dental/learning/train', headers=headers, json={'consent_training':True}).status_code == 200
        learning.futures[OWNER].result(timeout=30)
        own = client.get('/v1/dental/detection-status', headers=headers).json()
        other = client.get('/v1/dental/detection-status', headers={**headers, 'X-Dental-Owner':OTHER}).json()
        assert own['provider_configured'] is True and other['provider_configured'] is False
        assert client.delete('/v1/dental/learning/examples/'+example(0).input_sha256, headers={**headers, 'X-Dental-Owner':OTHER}).status_code == 404
