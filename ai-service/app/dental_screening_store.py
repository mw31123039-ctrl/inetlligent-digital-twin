"""Explicit local persistence for annotations, separate from crown-model training."""
import json
from contextlib import closing

from .dental_learning import LearningConflict, LocalDentalLearning
from .dental_screening import ScreeningRecord, screening_case_key


def list_screening_cases(store: LocalDentalLearning, owner: str) -> dict:
    with store.lock, closing(store._connection(owner)) as connection:
        rows = connection.execute('SELECT id, subject_code, visit_code, partition FROM screening_cases ORDER BY subject_code, visit_code').fetchall()
    return {'cases': [dict(row) for row in rows], 'classifier_available': False, 'clinical_validation': False}


def save_screening_case(store: LocalDentalLearning, owner: str, record: ScreeningRecord) -> dict:
    if not record.consent_storage:
        raise LearningConflict('Explicit permission is required to store this screening annotation locally.')
    case_id = screening_case_key(record)
    with store.lock, closing(store._connection(owner)) as connection:
        count = connection.execute('SELECT COUNT(*) FROM screening_cases').fetchone()[0]
        if count >= 200 and not connection.execute('SELECT 1 FROM screening_cases WHERE id=?', (case_id,)).fetchone():
            raise LearningConflict('The local screening set supports up to 200 visits.')
        groups = connection.execute('SELECT subject_code, partition FROM examples UNION SELECT subject_code, partition FROM screening_cases').fetchall()
        if any(row['subject_code'].casefold() == record.subject_code.casefold() and row['partition'] != record.partition for row in groups):
            raise LearningConflict('Every image and visit of one patient must stay in the same partition.')
        rows = connection.execute('SELECT source_sha256, subject_code, partition FROM screening_photos WHERE case_id<>?', (case_id,)).fetchall()
        hashes = {photo.source_sha256 for photo in record.photos}
        if any(row['source_sha256'] in hashes and (row['subject_code'].casefold() != record.subject_code.casefold() or row['partition'] != record.partition) for row in rows):
            raise LearningConflict('A photograph is already assigned to another patient or partition.')
        with connection:
            connection.execute('INSERT OR REPLACE INTO screening_cases VALUES (?, ?, ?, ?, ?)', (case_id, record.subject_code, record.visit_code, record.partition, record.model_dump_json()))
            connection.execute('DELETE FROM screening_photos WHERE case_id=?', (case_id,))
            connection.executemany('INSERT INTO screening_photos VALUES (?, ?, ?, ?)', [(case_id, photo.source_sha256, record.subject_code, record.partition) for photo in record.photos])
    return list_screening_cases(store, owner)


def read_screening_case(store: LocalDentalLearning, owner: str, case_id: str) -> dict:
    with store.lock, closing(store._connection(owner)) as connection:
        row = connection.execute('SELECT data FROM screening_cases WHERE id=?', (case_id,)).fetchone()
    if not row:
        raise KeyError('Screening case not found.')
    return ScreeningRecord.model_validate_json(row['data']).model_dump()


def remove_screening_case(store: LocalDentalLearning, owner: str, case_id: str) -> dict:
    with store.lock, closing(store._connection(owner)) as connection:
        if not connection.execute('SELECT 1 FROM screening_cases WHERE id=?', (case_id,)).fetchone():
            raise KeyError('Screening case not found.')
        with connection:
            connection.execute('DELETE FROM screening_photos WHERE case_id=?', (case_id,))
            connection.execute('DELETE FROM screening_cases WHERE id=?', (case_id,))
        connection.execute('VACUUM')
    return list_screening_cases(store, owner)
