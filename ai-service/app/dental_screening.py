"""Orthodontic annotation contract. No condition classifier is supplied or run."""
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .dental import DentalPhoto
from .dental_local import decode_photo

TAXONOMY = json.loads((Path(__file__).resolve().parents[2] / 'contracts/dental/screening-taxonomy.v1.json').read_text(encoding='utf-8'))
CONDITION_IDS = {item['id'] for item in TAXONOMY['conditions']}
State = Literal['present', 'absent', 'uncertain', 'not_assessable']
FDI = {q * 10 + t for q in range(1, 9) for t in range(1, 9 if q < 5 else 6)}


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class ScreeningLocation(Strict):
    arch: Literal['upper', 'lower', 'both', 'unknown']
    region: Literal['anterior', 'posterior', 'whole_arch', 'tooth_specific', 'unknown']
    side: Literal['patient_left', 'patient_right', 'bilateral', 'midline', 'unknown']
    tooth_ids: list[int] = Field(max_length=52)
    tooth_identity_confirmed: bool

    @model_validator(mode='after')
    def known_identifiers(self):
        if any(tooth not in FDI for tooth in self.tooth_ids) or len(set(self.tooth_ids)) != len(self.tooth_ids):
            raise ValueError('Invalid or duplicate FDI identifiers.')
        return self


class ScreeningFinding(Strict):
    id: str = Field(max_length=80)
    state: State
    evidence_basis: Literal['not_recorded', 'photo_observation', 'clinical_record_review', 'history_report']
    photo_ids: list[str] = Field(max_length=6)
    record_reference: str = Field(max_length=300)
    note: str = Field(max_length=1000)
    locations: list[ScreeningLocation] = Field(max_length=8)


class ScreeningPhoto(Strict):
    source_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    width: int = Field(ge=1, le=24000000)
    height: int = Field(ge=1, le=24000000)
    standard_view: Literal['frontal_bite', 'right_bite', 'left_bite', 'upper_occlusal', 'lower_occlusal', 'other', 'unknown']
    view_confirmed: bool
    quality: Literal['not_reviewed', 'usable', 'limited', 'insufficient', 'out_of_scope']
    quality_reasons: list[Literal['blur', 'lighting', 'occlusion', 'cropped_teeth', 'unconfirmed_view', 'not_biting_together', 'non_dental_image', 'radiograph_or_scan', 'other']] = Field(max_length=9)
    biting_together: Literal['yes', 'no', 'unknown']
    patient_orientation_confirmed: bool
    data_url: str | None = Field(max_length=350000)
    input_sha256: str | None = Field(pattern='^[a-f0-9]{64}$')

    @model_validator(mode='after')
    def bound_pixels(self):
        if self.width * self.height > 24000000 or len(set(self.quality_reasons)) != len(self.quality_reasons):
            raise ValueError('Invalid photo dimensions or repeated quality reasons.')
        if (self.data_url is None) != (self.input_sha256 is None):
            raise ValueError('Image bytes and their prepared fingerprint must be supplied together.')
        if self.data_url:
            _, raw = decode_photo(DentalPhoto(view='Frontal bite', data_url=self.data_url))
            if hashlib.sha256(raw).hexdigest() != self.input_sha256:
                raise ValueError('The prepared photo fingerprint changed.')
        return self


BasicClass = Literal['not_recorded', 'uncertain', 'not_assessable', 'class_i', 'class_ii', 'class_iii']
IncisorClass = Literal['not_recorded', 'uncertain', 'not_assessable', 'class_i', 'class_ii_division_1', 'class_ii_division_2', 'class_iii']


class DentalClassifications(Strict):
    overall: IncisorClass
    molar_right: BasicClass
    molar_left: BasicClass
    canine_right: BasicClass
    canine_left: BasicClass
    incisor: IncisorClass
    entered_by_clinician: bool
    note: str = Field(max_length=1000)


class ScreeningReview(Strict):
    reviewer_code: str = Field(pattern='^([A-Za-z0-9_-]{1,48})?$')
    reviewer_role: Literal['orthodontist', 'dentist', 'student', 'patient', 'unknown']
    annotations_reviewed: bool
    definitions_reviewed: bool

    @model_validator(mode='after')
    def attested_review(self):
        if (self.annotations_reviewed or self.definitions_reviewed) and (self.reviewer_role != 'orthodontist' or not self.reviewer_code):
            raise ValueError('Recorded specialist review requires an orthodontist role and coded reviewer.')
        return self


class ScreeningRecord(Strict):
    schema_version: Literal['humantwin-orthodontic-screening-v1']
    taxonomy_version: str = Field(max_length=80)
    subject_code: str = Field(pattern='^[A-Za-z0-9_-]{1,48}$')
    visit_code: str = Field(pattern='^[A-Za-z0-9_-]{1,48}$')
    partition: Literal['train', 'validation', 'test']
    age_years: float | None = Field(ge=0, le=120)
    dentition_stage: Literal['primary', 'mixed', 'permanent', 'unknown']
    scope: Literal['not_reviewed', 'in_scope', 'insufficient_images', 'out_of_scope']
    normal_appearance: State
    existing_braces: State
    photos: list[ScreeningPhoto] = Field(max_length=6)
    findings: list[ScreeningFinding] = Field(min_length=41, max_length=41)
    classifications: DentalClassifications
    review: ScreeningReview
    data_rights: Literal['not_confirmed', 'consented_clinical_data', 'appropriately_licensed']
    rights_reference: str = Field(max_length=300)
    consent_storage: bool
    consent_training: bool
    is_demonstration: Literal[False]
    clinical_validation: Literal[False]
    classifier_applied: Literal[False]
    model_training_performed: Literal[False]

    @model_validator(mode='after')
    def explicit_labels_and_evidence(self):
        if self.taxonomy_version != TAXONOMY['version'] or {finding.id for finding in self.findings} != CONDITION_IDS or len({f.id for f in self.findings}) != 41:
            raise ValueError('The annotation must contain exactly the current 41 distinct condition identifiers.')
        hashes = {photo.source_sha256 for photo in self.photos}
        if len(hashes) != len(self.photos) or any(len(set(finding.photo_ids)) != len(finding.photo_ids) or set(finding.photo_ids) - hashes for finding in self.findings):
            raise ValueError('Photographic evidence must reference distinct supplied photos.')
        if (self.consent_storage or self.consent_training or any(photo.data_url for photo in self.photos)) and self.data_rights == 'not_confirmed':
            raise ValueError('Record consent or appropriate data rights before storage or research use.')
        if self.data_rights == 'appropriately_licensed' and not self.rights_reference.strip():
            raise ValueError('An appropriate licence reference is required.')
        return self


def screening_case_key(record: ScreeningRecord) -> str:
    return hashlib.sha256((record.subject_code.casefold() + ':' + record.visit_code.casefold()).encode()).hexdigest()
