"""Software tests; retrieval relevance is not medical validation."""
import hashlib
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.cancer_knowledge import KnowledgeAnswer, KnowledgeQuestion, knowledge_status, pooled_embedding, rank_source_records, retrieve_knowledge, safety_terms


def test_pooling_uses_attention_mask_and_rejects_invalid_encoder_outputs():
    hidden = np.zeros((1, 3, 384), np.float32)
    hidden[0, 0, 0] = 1; hidden[0, 1, 1] = 1; hidden[0, 2, 2] = 1000
    vector = pooled_embedding(hidden, np.array([[1, 1, 0]]))[0]
    assert np.linalg.norm(vector) == pytest.approx(1)
    assert vector[0] == pytest.approx(vector[1]) and vector[2] == 0
    with pytest.raises(ValueError):
        pooled_embedding(hidden, np.ones((1, 2)))
    with pytest.raises(ValueError):
        pooled_embedding(np.zeros((1, 3, 384)), np.ones((1, 3)))
    hidden[0, 0, 0] = np.nan
    with pytest.raises(ValueError):
        pooled_embedding(hidden, np.ones((1, 3)))


def test_missing_artifacts_never_fabricate_an_answer(tmp_path):
    assert knowledge_status(tmp_path)['configured'] is False
    with pytest.raises(FileNotFoundError):
        retrieve_knowledge(tmp_path, KnowledgeQuestion(question='Which tests investigate oral lesions?', consent_local=True))


def test_question_contract_and_conditional_urgent_term_notice():
    for data in [{'question':'   ','consent_local':True}, {'question':'breast lump','consent_local':False}, {'question':'breast lump','consent_local':True,'patient_name':'private'}]:
        with pytest.raises(ValidationError):
            KnowledgeQuestion(**data)
    assert safety_terms('I cannot breathe properly') == 'emergency-terms'
    assert safety_terms('I am coughing up blood') == 'urgent-terms'
    assert safety_terms('What is a biopsy?') == 'none'


def test_named_topics_rerank_only_relevant_encoder_matches_without_changing_scores():
    records = [('colorectal', ''), ('bladder', ''), ('prostate', ''), ('skin', '')]
    similarities = np.array([.6, .55, .3, .1])
    assert rank_source_records(similarities, records, 'What guide explains bladder cancer and cystoscopy?') == [1, 0, 2]
    assert similarities.tolist() == [.6, .55, .3, .1]
    assert rank_source_records(similarities, records, 'Explain the medical tests') == [0, 1, 2]
    assert rank_source_records(similarities, records, 'Explain skin cancer') == [0, 1, 2]
    assert rank_source_records([.1, .09, .08, .07], records, 'bladder') == []
    # Whole-word matching prevents a partial token from manufacturing a topic hit.
    assert rank_source_records(similarities, records, 'colonial architecture') == [0, 1, 2]
    with pytest.raises(ValueError):
        rank_source_records([np.nan] * 4, records, 'bladder')


@pytest.mark.skipif(not Path('models/cancer-knowledge/model.onnx').exists(), reason='Install the real optional local encoder to run its integration check.')
def test_actual_encoder_retrieves_known_evidence_ids_without_generated_medical_claims():
    root = Path('models/cancer-knowledge')
    for question, expected in [('Which tests investigate a mouth ulcer lasting weeks?','oral'), ('What could a breast lump mean?','breast'), ('How can I upload a cancer image?','upload-image'), ('How is a chemotherapy treatment plan chosen?','choose-treatment')]:
        answer = retrieve_knowledge(root, KnowledgeQuestion(question=question,consent_local=True))
        assert answer.matches[0].record_id == expected
        assert answer.question_sha256 == hashlib.sha256(question.encode()).hexdigest()
        assert answer.question_saved is False and answer.external_requests is False
        assert answer.clinical_validation is False and answer.retrieval_ms > 0
        assert 'diagnosis' not in answer.model_dump()


def test_private_api_auth_consent_and_sanitized_failures(monkeypatch, tmp_path):
    from app import main
    monkeypatch.setattr(main.settings, 'service_key', 'k' * 40)
    monkeypatch.setenv('CANCER_KNOWLEDGE_MODEL_DIR', str(tmp_path))
    headers = {'X-Service-Key':'k' * 40}
    payload = {'question':'Synthetic private concern', 'consent_local':True}
    with TestClient(main.app) as client:
        assert client.post('/v1/cancer/knowledge', json=payload).status_code == 401
        assert client.get('/v1/cancer/knowledge-status').status_code == 401
        assert client.get('/v1/cancer/knowledge-status', headers=headers).json()['configured'] is False
        invalid = client.post('/v1/cancer/knowledge', headers=headers, json=payload | {'consent_local':False})
        assert invalid.status_code == 422 and payload['question'] not in invalid.text
        failed = client.post('/v1/cancer/knowledge', headers=headers, json=payload)
        assert failed.status_code == 503 and 'matches' not in failed.json()
        assert payload['question'] not in failed.text
        assert failed.headers['cache-control'] == 'no-store, private'
