"""Account-scoped, explicitly consented local teaching sets and training jobs."""
import hashlib
import json
import os
import re
import shutil
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .dental_local import TrainingExample, _perceptual_hash, annotation_mask, decode_photo, local_status, train_local_model


class LearningConflict(ValueError):
    pass


class TrainRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    consent_training: Literal[True]


class LocalDentalLearning:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='local-dental-training')
        self.jobs = {}
        self.futures = {}

    def owner_path(self, owner: str) -> Path:
        if not re.fullmatch('[a-f0-9]{64}', owner):
            raise ValueError('Invalid teaching-set owner.')
        path = (self.directory / owner).resolve()
        if not path.is_relative_to(self.directory) or path == self.directory:
            raise ValueError('Invalid teaching-set location.')
        return path

    def model_path(self, owner: str) -> Path:
        return self.owner_path(owner) / 'models'

    def _connection(self, owner: str):
        location = self.owner_path(owner)
        location.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(location / 'teaching.sqlite3', timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA secure_delete=ON')
        connection.execute('CREATE TABLE IF NOT EXISTS examples (id TEXT PRIMARY KEY, subject_code TEXT NOT NULL, partition TEXT NOT NULL, view TEXT NOT NULL, crowns INTEGER NOT NULL, reviewer_code TEXT NOT NULL, dhash TEXT NOT NULL, data TEXT NOT NULL)')
        connection.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), revision TEXT NOT NULL)')
        connection.execute('CREATE TABLE IF NOT EXISTS screening_cases (id TEXT PRIMARY KEY, subject_code TEXT NOT NULL, visit_code TEXT NOT NULL, partition TEXT NOT NULL, data TEXT NOT NULL)')
        connection.execute('CREATE TABLE IF NOT EXISTS screening_photos (case_id TEXT NOT NULL, source_sha256 TEXT NOT NULL, subject_code TEXT NOT NULL, partition TEXT NOT NULL)')
        connection.execute('INSERT OR IGNORE INTO state VALUES (1, ?)', (uuid.uuid4().hex,))
        connection.commit()
        return connection

    def _remove_tree(self, owner: str, path: Path):
        # Validate resolved absolute targets before recursive Windows operations.
        root = self.owner_path(owner)
        target = path.resolve()
        if target == root or not target.is_relative_to(root):
            raise ValueError('Invalid local artifact location.')
        if target.exists():
            shutil.rmtree(target)

    def _invalidate_model(self, owner: str):
        self._remove_tree(owner, self.model_path(owner))

    def status(self, owner: str) -> dict:
        with self.lock, closing(self._connection(owner)) as connection:
            rows = connection.execute('SELECT id, subject_code, partition, view, crowns, reviewer_code FROM examples ORDER BY subject_code, id').fetchall()
            subjects = {partition: len({row['subject_code'].casefold() for row in rows if row['partition'] == partition}) for partition in ('train', 'validation', 'test')}
            job = dict(self.jobs.get(owner, {'state': 'idle', 'phase': 'idle'}))
            model = local_status(self.model_path(owner))
            return {'runtime': 'local', 'external_requests': False, 'clinical_validation': False,
                    'examples': [dict(row) for row in rows], 'subjects': subjects,
                    'can_train': subjects['train'] >= 2 and subjects['validation'] >= 1 and job['state'] != 'running',
                    'job': job, 'model': model}

    def save(self, owner: str, example: TrainingExample) -> dict:
        image, raw = decode_photo(example.photo)
        digest = hashlib.sha256(raw).hexdigest()
        if digest != example.input_sha256:
            raise LearningConflict('The photo fingerprint does not match the teaching example.')
        annotation_mask(image, example.crowns)
        perceptual = _perceptual_hash(image)
        with self.lock, closing(self._connection(owner)) as connection:
            rows = connection.execute('SELECT id, subject_code, partition, dhash FROM examples').fetchall()
            screening = connection.execute('SELECT partition FROM screening_cases WHERE lower(subject_code)=?', (example.subject_code.casefold(),)).fetchall()
            if any(row['partition'] != example.partition for row in screening):
                raise LearningConflict('Every photograph and screening visit of one subject must stay in the same partition.')
            if len(rows) >= 200 and not any(row['id'] == digest for row in rows):
                raise LearningConflict('This local teaching set supports up to 200 photographs.')
            for row in rows:
                if row['id'] == digest and (row['subject_code'].casefold() != example.subject_code.casefold() or row['partition'] != example.partition):
                    raise LearningConflict('This photo already belongs to a subject and partition. Keep its existing assignment.')
                if row['subject_code'].casefold() == example.subject_code.casefold() and row['partition'] != example.partition:
                    raise LearningConflict('Every photograph of one subject must stay in the same partition.')
                if row['partition'] != example.partition and (perceptual ^ int(row['dhash'], 16)).bit_count() <= 4:
                    raise LearningConflict('A similar photo is already in another partition. Keep related photos together.')
            self._invalidate_model(owner)
            with connection:
                connection.execute('INSERT OR REPLACE INTO examples VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    (digest, example.subject_code, example.partition, example.photo.view, len(example.crowns), example.reviewer_code,
                     format(perceptual, '016x'), example.model_dump_json()))
                connection.execute('UPDATE state SET revision=? WHERE id=1', (uuid.uuid4().hex,))
            if self.jobs.get(owner, {}).get('state') != 'running':
                self.jobs.pop(owner, None)
        return self.status(owner)

    def remove(self, owner: str, example_id: str) -> dict:
        if not re.fullmatch('[a-f0-9]{64}', example_id):
            raise LearningConflict('Invalid local example.')
        with self.lock, closing(self._connection(owner)) as connection:
            if not connection.execute('SELECT 1 FROM examples WHERE id=?', (example_id,)).fetchone():
                raise KeyError('Example not found.')
            self._invalidate_model(owner)
            with connection:
                connection.execute('DELETE FROM examples WHERE id=?', (example_id,))
                connection.execute('UPDATE state SET revision=? WHERE id=1', (uuid.uuid4().hex,))
            # Deleted image bytes should not remain in unused SQLite pages.
            connection.execute('VACUUM')
            if self.jobs.get(owner, {}).get('state') != 'running':
                self.jobs.pop(owner, None)
        return self.status(owner)

    def start(self, owner: str) -> dict:
        with self.lock:
            if any(job.get('state') == 'running' for job in self.jobs.values()):
                raise LearningConflict('A local training job is already running. Wait for it to finish.')
            status = self.status(owner)
            if not status['can_train']:
                raise LearningConflict('Save examples from at least two training subjects and one different validation subject before training.')
            with closing(self._connection(owner)) as connection:
                revision = connection.execute('SELECT revision FROM state WHERE id=1').fetchone()[0]
                examples = [TrainingExample.model_validate_json(row[0]) for row in connection.execute('SELECT data FROM examples ORDER BY id')]
            job_id = uuid.uuid4().hex
            self.jobs[owner] = {'state': 'running', 'phase': 'queued'}
            self.futures[owner] = self.executor.submit(self._train, owner, job_id, revision, examples)
        return self.status(owner)

    def _train(self, owner: str, job_id: str, revision: str, examples: list[TrainingExample]):
        staging = self.owner_path(owner) / ('job-' + job_id)
        def progress(phase):
            with self.lock:
                self.jobs[owner] = {'state': 'running', 'phase': phase}
        try:
            train_local_model(examples, staging, progress=progress)
            with self.lock, closing(self._connection(owner)) as connection:
                current = connection.execute('SELECT revision FROM state WHERE id=1').fetchone()[0]
                if current != revision:
                    self.jobs[owner] = {'state': 'discarded', 'phase': 'discarded', 'message': 'The teaching set changed during training. Train again using the current examples.'}
                    return
                generation = json.loads((staging / 'current.json').read_text())['generation']
                if not re.fullmatch('[a-f0-9]{32}', generation):
                    raise ValueError('Invalid training artifact.')
                model_dir = self.model_path(owner)
                model_dir.mkdir(parents=True, exist_ok=True)
                source, destination = (staging / generation).resolve(), (model_dir / generation).resolve()
                root = self.owner_path(owner)
                if not source.is_relative_to(root) or not destination.is_relative_to(root):
                    raise ValueError('Invalid model activation location.')
                os.replace(source, destination)
                pointer = model_dir / ('pointer-' + job_id + '.tmp')
                pointer.write_text(json.dumps({'generation': generation}), encoding='utf-8')
                os.replace(pointer, model_dir / 'current.json')
                self.jobs[owner] = {'state': 'complete', 'phase': 'complete'}
        except Exception:
            # Never expose validation errors that may contain patient bytes.
            with self.lock:
                self.jobs[owner] = {'state': 'failed', 'phase': 'failed', 'message': 'Training could not finish. Check distinct patient partitions, complete crown annotations and clear photos. The previous model was preserved.'}
        finally:
            self._remove_tree(owner, staging)
