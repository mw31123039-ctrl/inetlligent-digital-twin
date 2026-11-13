"""Offline 2D cancer research classifiers; no weights or clinical validation bundled.

Operators install independently evaluated ONNX classifiers with an explicit input
contract. CT/MRI exports are single 8-bit slices, never whole-volume screening.
"""
import base64
import hashlib
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

Track = Literal['skin', 'oral', 'lung', 'breast']
Modality = Literal['skin_photo', 'dermoscopy', 'oral_photo', 'lung_ct_slice', 'mammogram', 'breast_ultrasound', 'breast_mri_slice']
MODALITIES = {
    'skin': ['skin_photo', 'dermoscopy'],
    'oral': ['oral_photo'],
    'lung': ['lung_ct_slice'],
    'breast': ['mammogram', 'breast_ultrasound', 'breast_mri_slice'],
}
_lock = threading.Lock()
_cache: dict = {}


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Evaluation(ClosedModel):
    """Operator-supplied provenance, not independently verified by this software."""
    reference: str = Field(min_length=1, max_length=200)
    patient_disjoint: bool | None = None
    held_out_subjects: int | None = Field(default=None, strict=True, ge=1)
    sensitivity: float | None = Field(default=None, ge=0, le=1)
    specificity: float | None = Field(default=None, ge=0, le=1)


class ModelManifest(ClosedModel):
    schema_version: Literal['humantwin-cancer-model-v1']
    track: Track
    modality: Modality
    model_version: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$')
    target: str = Field(min_length=1, max_length=160)
    source_url: str = Field(pattern=r'^https://[^\s]+$', max_length=500)
    license: str = Field(min_length=1, max_length=120)
    weights_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    input_size: tuple[int, int]
    color: Literal['RGB', 'GRAY']
    resize: Literal['stretch']
    scale: float = Field(gt=0, le=1)
    mean: list[float]
    std: list[float]
    labels: list[str] = Field(min_length=2, max_length=20)
    output: Literal['logits', 'probabilities']
    evaluation: Evaluation
    research_only: Literal[True]
    runtime: Literal['opencv', 'onnxruntime'] = 'opencv'
    interpolation: Literal['opencv-linear', 'pil-bilinear'] = 'opencv-linear'

    @model_validator(mode='after')
    def input_contract(self):
        if self.modality not in MODALITIES[self.track]:
            raise ValueError('The model modality does not belong to this pathway.')
        if any(size < 32 or size > 1024 for size in self.input_size):
            raise ValueError('Use input sizes between 32 and 1024.')
        channels = 3 if self.color == 'RGB' else 1
        if len(self.mean) != channels or len(self.std) != channels or any(value <= 0 for value in self.std):
            raise ValueError('Normalization must match the input channels with positive standard deviations.')
        if len(set(self.labels)) != len(self.labels) or any(not label.strip() or len(label) > 80 for label in self.labels):
            raise ValueError('Provide distinct nonempty output labels.')
        return self


class CancerRequest(ClosedModel):
    track: Track
    modality: Modality
    image_data_url: str = Field(pattern=r'^data:image/jpeg;base64,[A-Za-z0-9+/=]+$', max_length=1500000)
    consent_local: Literal[True]
    modality_confirmed: Literal[True]
    research_only_acknowledged: Literal[True]
    explain: bool = False

    @model_validator(mode='after')
    def compatible(self):
        if self.modality not in MODALITIES[self.track]:
            raise ValueError('The input modality does not belong to this pathway.')
        return self


class Score(ClosedModel):
    label: str = Field(min_length=1, max_length=80)
    value: float = Field(ge=0, le=1)


class Uncertainty(ClosedModel):
    normalized_entropy: float = Field(ge=0, le=1)
    margin: float = Field(ge=0, le=1)
    interpretation: Literal['research-only']


class Explanation(ClosedModel):
    method: Literal['occlusion-sensitivity']
    target_label: str = Field(min_length=1, max_length=80)
    grid_size: Literal[4, 6]
    values: list[Annotated[float, Field(ge=0, le=1)]] = Field(min_length=16, max_length=36)
    meaning: Literal['score-drop-under-occlusion']
    localization: Literal[False]
    max_score_drop: float = Field(ge=0, le=1)

    @model_validator(mode='after')
    def grid_contract(self):
        if len(self.values) != self.grid_size ** 2 or any(value < 0 or value > 1 for value in self.values):
            raise ValueError('Invalid sensitivity grid.')
        return self


class ImageChecks(ClosedModel):
    width: int = Field(ge=32, le=2048)
    height: int = Field(ge=32, le=2048)
    brightness: float = Field(ge=0, le=255)
    contrast: float = Field(ge=0, le=128)
    warnings: list[str] = Field(max_length=8)


class ModelInfo(ClosedModel):
    source_url: str = Field(pattern=r'^https://[^\s]+$', max_length=500)
    license: str = Field(min_length=1, max_length=120)
    evaluation_reference: str = Field(min_length=1, max_length=200)
    patient_disjoint: bool | None


class CancerResult(ClosedModel):
    schema_version: Literal['humantwin-cancer-result-v1']
    track: Track
    modality: Modality
    model_version: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$')
    target: str = Field(min_length=1, max_length=160)
    weights_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    input_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    scores: list[Score] = Field(min_length=2, max_length=20)
    clinical_validation: Literal[False]
    calibrated_cancer_probability: Literal[False]
    scope: Literal['single-2d-image']
    external_requests: Literal[False]
    inference_ms: float | None = Field(default=None, ge=0)
    runtime: Literal['onnxruntime-cpu', 'opencv-cpu'] | None = None
    uncertainty: Uncertainty | None = None
    explanation: Explanation | None = None
    image_checks: ImageChecks | None = None
    model_info: ModelInfo | None = None


def decode_image(data_url: str) -> tuple[np.ndarray, bytes]:
    raw = base64.b64decode(data_url.split(',', 1)[1], validate=True)
    if not raw.startswith(b'\xff\xd8\xff') or not raw.endswith(b'\xff\xd9'):
        raise ValueError('Use a re-encoded JPEG image.')
    # Read dimensions before allocating the decoded array (decompression bounds).
    index, dimensions = 2, None
    while index + 4 <= len(raw):
        if raw[index] != 0xff:
            raise ValueError('Invalid JPEG marker.')
        marker = raw[index + 1]
        if marker in (0xda, 0xd9):
            break
        length = int.from_bytes(raw[index + 2:index + 4], 'big')
        if length < 2 or index + 2 + length > len(raw):
            raise ValueError('Invalid JPEG segment.')
        if marker in (0xc0, 0xc1, 0xc2):
            if length < 8:
                raise ValueError('Invalid JPEG frame.')
            dimensions = (int.from_bytes(raw[index + 7:index + 9], 'big'), int.from_bytes(raw[index + 5:index + 7], 'big'))
            break
        index += 2 + length
    if dimensions is None or min(dimensions) < 32 or max(dimensions) > 2048:
        raise ValueError('Use a JPEG between 32 and 2048 pixels on each side.')
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    if image is None or (image.shape[1], image.shape[0]) != dimensions:
        raise ValueError('The JPEG could not be decoded.')
    return image, raw


def prepare_input(image: np.ndarray, manifest: ModelManifest) -> np.ndarray:
    pixels = cv2.cvtColor(image, cv2.COLOR_BGR2RGB if manifest.color == 'RGB' else cv2.COLOR_BGR2GRAY)
    width, height = manifest.input_size
    if manifest.interpolation == 'pil-bilinear':
        from PIL import Image
        pixels = np.asarray(Image.fromarray(pixels).resize((width, height), Image.Resampling.BILINEAR)).astype(np.float32)
    else:
        pixels = cv2.resize(pixels, (width, height), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    if pixels.ndim == 2:
        pixels = pixels[:, :, None]
    pixels = (pixels * manifest.scale - np.asarray(manifest.mean, np.float32)) / np.asarray(manifest.std, np.float32)
    return np.ascontiguousarray(pixels.transpose(2, 0, 1)[None])


def output_scores(output: np.ndarray, manifest: ModelManifest) -> list[Score]:
    values = np.asarray(output, np.float64)
    if values.shape not in ((len(manifest.labels),), (1, len(manifest.labels))) or not np.isfinite(values).all():
        raise ValueError('The classifier returned an unsupported or non-finite output.')
    values = values.reshape(-1)
    if manifest.output == 'logits':
        values = np.exp(values - values.max())
        values /= values.sum()
    elif (values < 0).any() or (values > 1).any() or abs(float(values.sum()) - 1) > .001:
        raise ValueError('The classifier returned invalid class scores.')
    return [Score(label=label, value=float(value)) for label, value in zip(manifest.labels, values)]


@dataclass
class ModelRunner:
    network: object
    runtime: str
    input_name: str = ''

    def predict(self, blob: np.ndarray) -> np.ndarray:
        if self.runtime == 'onnxruntime-cpu':
            return self.network.run(None, {self.input_name: blob})[0]
        self.network.setInput(blob)
        return self.network.forward()


def load_model(root: Path, modality: str):
    return load_bundle(root / modality, modality)


def load_bundle(directory: Path, modality: str):
    """Use the same verified runtime for installed and staged research models."""
    if modality not in {item for items in MODALITIES.values() for item in items}:
        raise ValueError('Unsupported modality.')
    manifest_path, weights = directory / 'manifest.json', directory / 'model.onnx'
    if manifest_path.stat().st_size > 20000 or not 1 <= weights.stat().st_size <= 512 * 1024 * 1024:
        raise ValueError('Model artifact size is unsupported.')
    manifest_raw = manifest_path.read_bytes()
    fingerprint = (str(directory.resolve()), hashlib.sha256(manifest_raw).hexdigest(), manifest_path.stat().st_mtime_ns, manifest_path.stat().st_size,
                   weights.stat().st_mtime_ns, weights.stat().st_size)
    if fingerprint in _cache:
        return _cache[fingerprint]
    manifest = ModelManifest.model_validate_json(manifest_raw)
    if manifest.modality != modality:
        raise ValueError('The installed model is for a different input modality.')
    # Read and hash the exact bytes loaded into OpenCV; no pickle/PyTorch code execution.
    raw = weights.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest.weights_sha256:
        raise ValueError('Model fingerprint mismatch.')
    if manifest.runtime == 'onnxruntime':
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.intra_op_num_threads = min(4, os.cpu_count() or 1)
        options.inter_op_num_threads = 1
        options.log_severity_level = 4
        session = ort.InferenceSession(raw, sess_options=options, providers=['CPUExecutionProvider'])
        if len(session.get_inputs()) != 1 or len(session.get_outputs()) != 1:
            raise ValueError('A single image input and classifier output are required.')
        input_spec = session.get_inputs()[0]
        expected = [1, 3 if manifest.color == 'RGB' else 1, manifest.input_size[1], manifest.input_size[0]]
        if input_spec.type != 'tensor(float)' or len(input_spec.shape) != 4 or any(isinstance(size, int) and size > 0 and size != target for size, target in zip(input_spec.shape, expected)):
            raise ValueError('The ONNX input does not match the preprocessing contract.')
        runner = ModelRunner(session, 'onnxruntime-cpu', input_spec.name)
    else:
        network = cv2.dnn.readNetFromONNX(np.frombuffer(raw, np.uint8))
        network.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        network.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        if len(network.getUnconnectedOutLayersNames()) != 1:
            raise ValueError('A single classifier output is required.')
        runner = ModelRunner(network, 'opencv-cpu')
    output_scores(runner.predict(prepare_input(np.zeros((32, 32, 3), np.uint8), manifest)), manifest)
    # Retain at most one network for each input modality.
    for key in list(_cache):
        if key[0] == fingerprint[0]:
            del _cache[key]
    _cache[fingerprint] = (manifest, runner)
    return manifest, runner


def cancer_status(root: Path) -> dict:
    pathways = []
    with _lock:
        for track, modalities in MODALITIES.items():
            models = []
            for modality in modalities:
                item = {'modality': modality, 'configured': False, 'state': 'not-configured'}
                try:
                    manifest, _ = load_model(root, modality)
                    item.update(configured=True, state='configured-unvalidated', model_version=manifest.model_version,
                                target=manifest.target, weights_sha256=manifest.weights_sha256)
                except FileNotFoundError:
                    # A partial installation is invalid, rather than a new model.
                    if (root / modality).exists():
                        item['state'] = 'invalid-artifacts'
                except Exception:
                    item['state'] = 'invalid-artifacts'
                models.append(item)
            pathways.append({'track': track, 'models': models})
    return {'available': True, 'clinical_validation': False, 'external_requests': False,
            'scope': 'single-2d-image', 'pathways': pathways}


def infer_cancer(root: Path, request: CancerRequest) -> CancerResult:
    image, raw = decode_image(request.image_data_url)
    started = time.perf_counter()
    with _lock:
        manifest, runner = load_model(root, request.modality)
        if manifest.track != request.track:
            raise ValueError('The model does not match this pathway.')
        blob = prepare_input(image, manifest)
        scores = output_scores(runner.predict(blob), manifest)
        explanation = explain_input(runner, blob, manifest, scores) if request.explain else None
    probabilities = np.array([item.value for item in scores], np.float64)
    ordered = np.sort(probabilities)
    entropy = float(-np.sum(probabilities * np.log(np.maximum(probabilities, 1e-15))) / np.log(len(scores)))
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    brightness, contrast = float(gray.mean()), float(gray.std())
    warnings = []
    if brightness < 25:
        warnings.append('Very dark image; check the intended acquisition and preprocessing.')
    if brightness > 230:
        warnings.append('Very bright image; check for overexposure or a blank export.')
    if contrast < 12:
        warnings.append('Low image contrast; model scores may be unreliable.')
    if min(image.shape[:2]) < min(manifest.input_size):
        warnings.append('This image is smaller than the model input and is upsampled.')
    warnings.append('Anatomy, modality and clinical image quality are not verified automatically.')
    return CancerResult(schema_version='humantwin-cancer-result-v1', track=request.track, modality=request.modality, model_version=manifest.model_version,
                        target=manifest.target, weights_sha256=manifest.weights_sha256,
                        input_sha256=hashlib.sha256(raw).hexdigest(), scores=scores, clinical_validation=False,
                        calibrated_cancer_probability=False, scope='single-2d-image', external_requests=False,
                        inference_ms=round((time.perf_counter() - started) * 1000, 2), runtime=runner.runtime,
                        uncertainty=Uncertainty(normalized_entropy=min(1, max(0, entropy)), margin=float(ordered[-1] - ordered[-2]), interpretation='research-only'),
                        explanation=explanation,
                        image_checks=ImageChecks(width=image.shape[1], height=image.shape[0], brightness=brightness, contrast=contrast, warnings=warnings),
                        model_info=ModelInfo(source_url=manifest.source_url, license=manifest.license,
                                             evaluation_reference=manifest.evaluation.reference,
                                             patient_disjoint=manifest.evaluation.patient_disjoint))


def explain_input(runner: ModelRunner, blob: np.ndarray, manifest: ModelManifest, scores: list[Score]) -> Explanation:
    """Measure class-score changes under patch occlusion, never lesion localization."""
    grid = 4
    target_index = int(np.argmax([score.value for score in scores]))
    baseline = scores[target_index].value
    height, width = blob.shape[-2:]
    drops = []
    for row in range(grid):
        for column in range(grid):
            occluded = blob.copy()
            # Zero in normalized space corresponds to the model's mean color.
            occluded[:, :, row * height // grid:(row + 1) * height // grid,
                     column * width // grid:(column + 1) * width // grid] = 0
            masked_scores = output_scores(runner.predict(occluded), manifest)
            drops.append(max(0.0, baseline - masked_scores[target_index].value))
    peak = max(drops)
    values = [value / peak if peak > .00001 else 0.0 for value in drops]
    return Explanation(method='occlusion-sensitivity', target_label=scores[target_index].label, grid_size=grid,
                       values=values, max_score_drop=peak, meaning='score-drop-under-occlusion', localization=False)
