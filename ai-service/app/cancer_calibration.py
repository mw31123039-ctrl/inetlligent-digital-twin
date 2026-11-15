"""Per-model calibration, decision threshold and familiarity reference.

Values are fitted by scripts/evaluate-cancer-models.py on a calibration split that is separate
from the reported test split, and stored in a tracked JSON file outside ai-service/models so the
installed model files never change. An entry applies only to the exact weights it was fitted for.
"""
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA = 'humantwin-cancer-calibration-v1'
DEFAULT_DECISION_THRESHOLD = .6
_cache: dict = {}


class _Closed(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class FamiliarityReference(_Closed):
    """Class centroids of L2-normalised image embeddings from in-distribution calibration images."""
    method: Literal['class-centroid-cosine']
    centroids: list[list[float]] = Field(min_length=2, max_length=20)
    minimum_similarity: float = Field(ge=-1, le=1)
    reference: str = Field(min_length=1, max_length=300)

    @model_validator(mode='after')
    def same_dimension(self):
        sizes = {len(row) for row in self.centroids}
        if len(sizes) != 1 or not 8 <= sizes.pop() <= 4096:
            raise ValueError('Centroids must share one embedding dimension.')
        return self


class CalibrationEntry(_Closed):
    model_version: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$')
    labels: list[str] = Field(min_length=2, max_length=20)
    temperature: float = Field(ge=.05, le=20)
    decision_threshold: float = Field(ge=0, le=1)
    fitted_on: str = Field(min_length=1, max_length=300)
    familiarity: FamiliarityReference | None = None

    @model_validator(mode='after')
    def centroid_per_label(self):
        if self.familiarity is not None and len(self.familiarity.centroids) != len(self.labels):
            raise ValueError('Provide one centroid per label.')
        return self


class CalibrationFile(_Closed):
    schema_version: Literal['humantwin-cancer-calibration-v1']
    models: dict[str, CalibrationEntry] = Field(max_length=50)

    @model_validator(mode='after')
    def keyed_by_weights(self):
        if any(len(key) != 64 or any(char not in '0123456789abcdef' for char in key) for key in self.models):
            raise ValueError('Entries are keyed by the SHA-256 of the model weights.')
        return self


def read_calibration(path: Path | None) -> CalibrationFile | None:
    if path is None or not path.is_file() or path.stat().st_size > 2_000_000:
        return None
    stamp = (str(path.resolve()), path.stat().st_mtime_ns, path.stat().st_size)
    if stamp not in _cache:
        _cache.clear()
        _cache[stamp] = CalibrationFile.model_validate_json(path.read_bytes())
    return _cache[stamp]


def calibration_for(path: Path | None, weights_sha256: str, model_version: str, labels: list[str]) -> CalibrationEntry | None:
    """Return the entry fitted for these exact weights and labels, or None (never a stale entry)."""
    try:
        document = read_calibration(path)
    except (OSError, ValueError):
        return None
    entry = document.models.get(weights_sha256) if document else None
    if entry is None or entry.model_version != model_version or entry.labels != labels:
        return None
    return entry


def write_entry(path: Path, weights_sha256: str, entry: CalibrationEntry) -> None:
    document = read_calibration(path) if path.is_file() else None
    models = dict(document.models) if document else {}
    models[weights_sha256] = entry
    payload = CalibrationFile(schema_version=SCHEMA, models=dict(sorted(models.items())))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload.model_dump(), indent=1) + '\n', encoding='utf-8')
    _cache.clear()
