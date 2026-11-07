import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.dental_learning import LearningConflict, LocalDentalLearning
from app.dental_screening import ScreeningRecord, TAXONOMY
from app.dental_screening_store import list_screening_cases, read_screening_case, remove_screening_case, save_screening_case
from test_dental_local import example

OWNER, OTHER = 'a' * 64, 'b' * 64


def screening(subject='PATIENT_1', partition='train', pixels=False):
    sample = example(0)
    return ScreeningRecord(schema_version='humantwin-orthodontic-screening-v1', taxonomy_version=TAXONOMY['version'],
        subject_code=subject, visit_code='VISIT_1', partition=partition, age_years=None, dentition_stage='unknown', scope='not_reviewed',
        normal_appearance='not_assessable', existing_braces='not_assessable',
        photos=[{'source_sha256':sample.input_sha256, 'width':180, 'height':100, 'standard_view':'frontal_bite', 'view_confirmed':False,
            'quality':'not_reviewed', 'quality_reasons':[], 'biting_together':'unknown', 'patient_orientation_confirmed':False,
            'data_url':sample.photo.data_url if pixels else None, 'input_sha256':sample.input_sha256 if pixels else None}],
        findings=[{'id':item['id'], 'state':'not_assessable', 'evidence_basis':'not_recorded', 'photo_ids':[], 'record_reference':'', 'note':'', 'locations':[]} for item in TAXONOMY['conditions']],
        classifications={'overall':'not_recorded', 'molar_right':'not_recorded', 'molar_left':'not_recorded', 'canine_right':'not_recorded', 'canine_left':'not_recorded', 'incisor':'not_recorded', 'entered_by_clinician':False, 'note':''},
        review={'reviewer_code':'', 'reviewer_role':'unknown', 'annotations_reviewed':False, 'definitions_reviewed':False},
        data_rights='consented_clinical_data', rights_reference='CONSENT_01', consent_storage=True, consent_training=False,
        is_demonstration=False, clinical_validation=False, classifier_applied=False, model_training_performed=False)


@pytest.fixture
def store(tmp_path):
    service=LocalDentalLearning(tmp_path)
    yield service
    service.executor.shutdown(wait=True)


def test_case_contract_retains_all_explicit_states_and_rejects_missing_labels_or_fake_classifier():
    case=screening()
    assert len(case.findings)==41 and all(item.state=='not_assessable' for item in case.findings)
    for change in [{'findings':case.model_dump()['findings'][:-1]}, {'classifier_applied':True}, {'is_demonstration':True}, {'clinical_validation':True}, {'taxonomy_version':'wrong'}]:
        with pytest.raises(ValidationError):
            ScreeningRecord.model_validate({**case.model_dump(), **change})
    bad=case.model_dump();bad['findings'][0]['photo_ids']=['b'*64]
    with pytest.raises(ValidationError):
        ScreeningRecord.model_validate(bad)


def test_pixels_require_rights_and_a_matching_jpeg_fingerprint_and_review_is_not_invented():
    case=screening(pixels=True)
    assert case.photos[0].data_url
    bad=case.model_dump();bad['photos'][0]['input_sha256']='f'*64
    with pytest.raises(ValidationError):
        ScreeningRecord.model_validate(bad)
    bad=case.model_dump();bad['data_rights']='not_confirmed'
    with pytest.raises(ValidationError):
        ScreeningRecord.model_validate(bad)
    bad=case.model_dump();bad['review']['annotations_reviewed']=True
    with pytest.raises(ValidationError):
        ScreeningRecord.model_validate(bad)


def test_local_saved_visits_are_owner_scoped_deletable_and_do_not_train_a_model(store):
    case=screening(pixels=True)
    response=save_screening_case(store,OWNER,case)
    assert response['classifier_available'] is False and 'data:image' not in json.dumps(response)
    case_id=response['cases'][0]['id']
    assert read_screening_case(store,OWNER,case_id)['photos'][0]['data_url'].startswith('data:image/jpeg;base64,')
    assert list_screening_cases(store,OTHER)['cases']==[]
    with pytest.raises(KeyError):
        read_screening_case(store,OTHER,case_id)
    with pytest.raises(KeyError):
        remove_screening_case(store,OTHER,case_id)
    assert store.futures=={} and store.status(OWNER)['model']['provider_configured'] is False
    assert remove_screening_case(store,OWNER,case_id)['cases']==[]


def test_patient_split_is_consistent_across_every_visit_photo_and_outline_teaching(store):
    save_screening_case(store,OWNER,screening('SUBJECT_0'))
    changed=screening('subject_0','validation');changed.visit_code='VISIT_2'
    with pytest.raises(LearningConflict, match='partition'):
        save_screening_case(store,OWNER,changed)
    with pytest.raises(LearningConflict, match='partition'):
        store.save(OWNER,example(2,'validation').model_copy(update={'subject_code':'SUBJECT_0'}))
    with pytest.raises(LearningConflict, match='photograph'):
        save_screening_case(store,OWNER,screening('OTHER_PATIENT'))
    store.save(OTHER,example(0))
    with pytest.raises(LearningConflict, match='partition'):
        save_screening_case(store,OTHER,screening('SUBJECT_0','test'))


def test_screening_private_api_requires_local_permission_and_never_claims_inference(monkeypatch,store):
    import app.main as main
    monkeypatch.setattr(main,'learning',store)
    monkeypatch.setattr(main.settings,'service_key','screening-private-service-'*2)
    headers={'X-Service-Key':main.settings.service_key,'X-Dental-Owner':OWNER}
    with TestClient(main.app) as client:
        assert client.get('/v1/dental/screening/cases').status_code==401
        case=screening();case.consent_storage=False
        assert client.post('/v1/dental/screening/cases',headers=headers,json=case.model_dump()).status_code==409
        case.consent_storage=True
        response=client.post('/v1/dental/screening/cases',headers=headers,json=case.model_dump())
        assert response.status_code==200 and response.json()['classifier_available'] is False
        case_id=response.json()['cases'][0]['id']
        assert client.get('/v1/dental/screening/cases/'+case_id,headers={**headers,'X-Dental-Owner':OTHER}).status_code==404
        invalid=client.post('/v1/dental/screening/cases',headers=headers,json={**case.model_dump(),'patient_name':'PRIVATE_DATA'})
        assert invalid.status_code==422 and 'PRIVATE_DATA' not in invalid.text


def test_screening_schema_has_not_drifted_and_taxonomy_remains_unvalidated():
    schema=json.loads(Path('../contracts/dental/screening-case.schema.json').read_text())
    schema.pop('$schema')
    assert schema==ScreeningRecord.model_json_schema()
    assert TAXONOMY['clinical_validation'] is False and TAXONOMY['orthodontist_review_status']=='pending'
