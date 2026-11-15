"""Offline 2D cancer research classifiers; no weights or clinical validation bundled.

Operators install independently evaluated ONNX classifiers with an explicit input
contract. CT/MRI exports are single 8-bit slices, never whole-volume screening.

Pipeline for one request: decode the browser-prepared JPEG -> input checks (cancer_quality) ->
preprocessing exactly as declared in the manifest -> ONNX inference -> optional temperature
scaling and familiarity check (cancer_calibration) -> heatmap (cancer_explain) -> outcome.
A finding is reported only when the input passed its checks and the calibrated top-class
probability reaches the model's decision threshold; otherwise the outcome is inconclusive.
"""
import base64
import hashlib
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .cancer_calibration import DEFAULT_DECISION_THRESHOLD, CalibrationEntry, calibration_for
from .cancer_explain import Explainer, augment, normalized, replay_head
from .cancer_quality import ImageChecks, check_image

Track = Literal['skin', 'oral', 'lung', 'breast']
Modality = Literal['skin_photo', 'dermoscopy', 'oral_photo', 'lung_ct_slice', 'mammogram', 'breast_ultrasound', 'breast_mri_slice']
MODALITIES = {
    'skin': ['skin_photo', 'dermoscopy'],
    'oral': ['oral_photo'],
    'lung': ['lung_ct_slice'],
    'breast': ['mammogram', 'breast_ultrasound', 'breast_mri_slice'],
}
RESULT_SCHEMA = 'humantwin-cancer-result-v2'
HIGH_CONFIDENCE = .85
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


class Confidence(ClosedModel):
    """How strongly the model prefers its top category. Not a personal probability of cancer."""
    top_label: str = Field(min_length=1, max_length=80)
    probability: float = Field(ge=0, le=1)
    level: Literal['high', 'moderate', 'low']
    calibration: Literal['temperature-scaled', 'none']
    temperature: float | None = Field(default=None, ge=.05, le=20)
    decision_threshold: float = Field(ge=0, le=1)
    normalized_entropy: float = Field(ge=0, le=1)
    margin: float = Field(ge=0, le=1)
    interpretation: Literal['model-confidence-not-personal-risk']


class Familiarity(ClosedModel):
    """Similarity of the image embedding to embeddings of the model's own reference images."""
    method: Literal['class-centroid-cosine']
    similarity: float = Field(ge=-1, le=1)
    minimum_similarity: float = Field(ge=-1, le=1)
    familiar: bool


class Heatmap(ClosedModel):
    method: Literal['grad-cam', 'attention-rollout', 'occlusion-sensitivity']
    target_label: str = Field(min_length=1, max_length=80)
    class_specific: bool
    grid_width: int = Field(ge=2, le=32)
    grid_height: int = Field(ge=2, le=32)
    values: list[Annotated[float, Field(ge=0, le=1)]] = Field(min_length=4, max_length=1024)
    meaning: Literal['regions-that-raised-the-score', 'patches-the-model-attended-to', 'score-drop-under-occlusion']
    localization: Literal[False]

    @model_validator(mode='after')
    def grid_contract(self):
        meanings = {'grad-cam': 'regions-that-raised-the-score', 'attention-rollout': 'patches-the-model-attended-to',
                    'occlusion-sensitivity': 'score-drop-under-occlusion'}
        if len(self.values) != self.grid_width * self.grid_height or self.meaning != meanings[self.method]:
            raise ValueError('Invalid heatmap grid.')
        if self.class_specific == (self.method == 'attention-rollout'):
            raise ValueError('Only attention rollout is class-agnostic.')
        return self


class ModelInfo(ClosedModel):
    source_url: str = Field(pattern=r'^https://[^\s]+$', max_length=500)
    license: str = Field(min_length=1, max_length=120)
    evaluation_reference: str = Field(min_length=1, max_length=200)
    patient_disjoint: bool | None


Outcome = Literal['finding', 'inconclusive', 'input-rejected']
OutcomeReason = Literal['input-rejected', 'input-quality', 'low-confidence', 'unfamiliar-image']


class CancerResult(ClosedModel):
    schema_version: Literal['humantwin-cancer-result-v2']
    track: Track
    modality: Modality
    model_version: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$')
    target: str = Field(min_length=1, max_length=160)
    weights_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    input_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    outcome: Outcome
    outcome_reasons: list[OutcomeReason] = Field(max_length=4)
    finding_label: str | None = Field(default=None, min_length=1, max_length=80)
    scores: list[Score] = Field(max_length=20)
    confidence: Confidence | None = None
    familiarity: Familiarity | None = None
    heatmap: Heatmap | None = None
    image_checks: ImageChecks
    clinical_validation: Literal[False]
    calibrated_cancer_probability: Literal[False]
    scope: Literal['single-2d-image']
    external_requests: Literal[False]
    inference_ms: float | None = Field(default=None, ge=0)
    runtime: Literal['onnxruntime-cpu', 'opencv-cpu'] | None = None
    model_info: ModelInfo | None = None

    @model_validator(mode='after')
    def outcome_contract(self):
        labels = [item.label for item in self.scores]
        if len(set(self.outcome_reasons)) != len(self.outcome_reasons):
            raise ValueError('Duplicate outcome reasons.')
        if self.outcome == 'input-rejected':
            if labels or self.confidence or self.heatmap or self.familiarity or self.finding_label or self.outcome_reasons != ['input-rejected'] \
                    or self.image_checks.decision != 'rejected':
                raise ValueError('A rejected input carries no model output.')
            return self
        if len(labels) < 2 or len(set(labels)) != len(labels) or abs(sum(item.value for item in self.scores) - 1) > .001 or self.confidence is None:
            raise ValueError('A model result needs a normalized score vector and a confidence summary.')
        if self.image_checks.decision == 'rejected' or 'input-rejected' in self.outcome_reasons:
            raise ValueError('A rejected input cannot produce a model result.')
        top = max(self.scores, key=lambda item: item.value)
        if self.confidence.top_label != top.label or abs(self.confidence.probability - top.value) > 1e-6:
            raise ValueError('The confidence summary does not match the scores.')
        if self.outcome == 'finding' and (self.outcome_reasons or self.finding_label != top.label):
            raise ValueError('A finding names the top category and has no inconclusive reasons.')
        if self.outcome == 'inconclusive' and (not self.outcome_reasons or self.finding_label is not None):
            raise ValueError('An inconclusive result states its reasons and names no finding.')
        if self.heatmap and self.heatmap.target_label not in labels:
            raise ValueError('The heatmap must refer to a returned category.')
        return self


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
    """Test-time preprocessing as declared by the manifest.

    'pil-bilinear' reproduces Hugging Face ViTImageProcessor (resample=2) and torchvision
    Resize((h, w), BILINEAR) on PIL images: an exact-size, antialiased PIL bilinear resize, then
    rescale and per-channel normalization, NCHW float32. tests/test_cancer_preprocessing.py checks
    this against each installed model's own reference pipeline.
    """
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


def output_scores(output: np.ndarray, manifest: ModelManifest, temperature: float | None = None) -> list[Score]:
    values = np.asarray(output, np.float64)
    if values.shape not in ((len(manifest.labels),), (1, len(manifest.labels))) or not np.isfinite(values).all():
        raise ValueError('The classifier returned an unsupported or non-finite output.')
    values = values.reshape(-1)
    if manifest.output == 'probabilities':
        if (values < 0).any() or (values > 1).any() or abs(float(values.sum()) - 1) > .001:
            raise ValueError('The classifier returned invalid class scores.')
        values = np.log(np.maximum(values, 1e-12))
    if temperature is not None:
        values = values / temperature
    values = np.exp(values - values.max())
    values /= values.sum()
    return [Score(label=label, value=float(value)) for label, value in zip(manifest.labels, values)]


@dataclass
class ModelRunner:
    network: object
    runtime: str
    input_name: str = ''
    output_name: str = ''
    explainer: Explainer | None = field(default=None)

    def predict(self, blob: np.ndarray) -> np.ndarray:
        if self.runtime == 'onnxruntime-cpu':
            return self.network.run([self.output_name] if self.output_name else None, {self.input_name: blob})[0]
        self.network.setInput(blob)
        return self.network.forward()

    def predict_with_tensors(self, blob: np.ndarray) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        """Logits plus the intermediate tensors the explainer reads, in one forward pass."""
        if self.explainer is None:
            return self.predict(blob), {}
        names = list(dict.fromkeys((self.output_name, *self.explainer.outputs, self.explainer.embedding_output)))
        values = self.network.run(names, {self.input_name: blob})
        return values[0], dict(zip(names, values))


def load_model(root: Path, modality: str):
    return load_bundle(root / modality, modality)


def _verified_explainer(runner: ModelRunner, blob: np.ndarray, manifest: ModelManifest) -> Explainer | None:
    """Keep an explainer only when it reproduces the graph's own computation on a dry run."""
    try:
        logits, values = runner.predict_with_tensors(blob)
        explainer = runner.explainer
        if explainer.method == 'grad-cam':
            if explainer.weight.shape[0] != len(manifest.labels):
                return None
            replayed = replay_head(values[explainer.outputs[0]], explainer.weight, explainer.bias)
            if not np.allclose(replayed, np.asarray(logits, np.float64).reshape(-1), rtol=1e-3, atol=1e-3):
                return None
        explainer.heatmap(values, 0)
        explainer.embedding(values)
        return explainer
    except Exception:
        return None


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
    # Read and hash the exact bytes loaded into the runtime; no pickle/PyTorch code execution.
    raw = weights.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest.weights_sha256:
        raise ValueError('Model fingerprint mismatch.')
    dry_run = prepare_input(np.zeros((32, 32, 3), np.uint8), manifest)
    if manifest.runtime == 'onnxruntime':
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.intra_op_num_threads = min(4, os.cpu_count() or 1)
        options.inter_op_num_threads = 1
        options.log_severity_level = 4
        augmented = augment(raw)
        session = ort.InferenceSession(augmented[0] if augmented else raw, sess_options=options, providers=['CPUExecutionProvider'])
        outputs = session.get_outputs()
        if len(session.get_inputs()) != 1 or not outputs or (augmented is None and len(outputs) != 1) \
                or (augmented is not None and outputs[0].name != augmented[1].logits_output):
            raise ValueError('A single image input and classifier output are required.')
        input_spec = session.get_inputs()[0]
        expected = [1, 3 if manifest.color == 'RGB' else 1, manifest.input_size[1], manifest.input_size[0]]
        if input_spec.type != 'tensor(float)' or len(input_spec.shape) != 4 or any(isinstance(size, int) and size > 0 and size != target for size, target in zip(input_spec.shape, expected)):
            raise ValueError('The ONNX input does not match the preprocessing contract.')
        runner = ModelRunner(session, 'onnxruntime-cpu', input_spec.name, outputs[0].name, augmented[1] if augmented else None)
        if runner.explainer is not None:
            runner.explainer = _verified_explainer(runner, dry_run, manifest)
    else:
        network = cv2.dnn.readNetFromONNX(np.frombuffer(raw, np.uint8))
        network.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        network.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        if len(network.getUnconnectedOutLayersNames()) != 1:
            raise ValueError('A single classifier output is required.')
        runner = ModelRunner(network, 'opencv-cpu')
    output_scores(runner.predict(dry_run), manifest)
    # Retain at most one network for each input modality.
    for key in list(_cache):
        if key[0] == fingerprint[0]:
            del _cache[key]
    _cache[fingerprint] = (manifest, runner)
    return manifest, runner


def heatmap_method(runner: ModelRunner) -> str:
    return runner.explainer.method if runner.explainer else 'occlusion-sensitivity'


def cancer_status(root: Path, calibration_path: Path | None = None) -> dict:
    pathways = []
    with _lock:
        for track, modalities in MODALITIES.items():
            models = []
            for modality in modalities:
                item = {'modality': modality, 'configured': False, 'state': 'not-configured'}
                try:
                    manifest, runner = load_model(root, modality)
                    calibration = calibration_for(calibration_path, manifest.weights_sha256, manifest.model_version, manifest.labels)
                    item.update(configured=True, state='configured-unvalidated', model_version=manifest.model_version,
                                target=manifest.target, weights_sha256=manifest.weights_sha256, labels=list(manifest.labels),
                                heatmap_method=heatmap_method(runner), calibration='temperature-scaled' if calibration else 'none')
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


def confidence_summary(scores: list[Score], calibration: CalibrationEntry | None) -> Confidence:
    probabilities = np.array([item.value for item in scores], np.float64)
    # Stable order: on an exact tie the first label wins, matching max() in the result contract.
    order = np.argsort(-probabilities, kind='stable')
    top = float(probabilities[order[0]])
    entropy = float(-np.sum(probabilities * np.log(np.maximum(probabilities, 1e-15))) / np.log(len(scores)))
    threshold = calibration.decision_threshold if calibration else DEFAULT_DECISION_THRESHOLD
    # Without calibration a raw softmax score is often overconfident, so it is never called "high".
    level = 'low' if top < threshold else 'high' if calibration and top >= max(HIGH_CONFIDENCE, threshold) else 'moderate'
    return Confidence(top_label=scores[int(order[0])].label, probability=top, level=level,
                      calibration='temperature-scaled' if calibration else 'none', temperature=calibration.temperature if calibration else None,
                      decision_threshold=threshold, normalized_entropy=min(1.0, max(0.0, entropy)),
                      margin=float(probabilities[order[0]] - probabilities[order[1]]), interpretation='model-confidence-not-personal-risk')


def familiarity_check(embedding: np.ndarray, calibration: CalibrationEntry | None) -> Familiarity | None:
    reference = calibration.familiarity if calibration else None
    if reference is None:
        return None
    centroids = np.asarray(reference.centroids, np.float64)
    if centroids.shape[1] != embedding.shape[0]:
        return None
    centroids /= np.linalg.norm(centroids, axis=1, keepdims=True)
    similarity = float(np.clip((centroids @ embedding).max(), -1, 1))
    return Familiarity(method='class-centroid-cosine', similarity=similarity, minimum_similarity=reference.minimum_similarity,
                       familiar=similarity >= reference.minimum_similarity)


def infer_cancer(root: Path, request: CancerRequest, calibration_path: Path | None = None) -> CancerResult:
    image, raw = decode_image(request.image_data_url)
    started = time.perf_counter()
    with _lock:
        manifest, runner = load_model(root, request.modality)
        if manifest.track != request.track:
            raise ValueError('The model does not match this pathway.')
        checks = check_image(image, request.modality, manifest.input_size)
        common = dict(schema_version=RESULT_SCHEMA, track=request.track, modality=request.modality, model_version=manifest.model_version,
                      target=manifest.target, weights_sha256=manifest.weights_sha256, input_sha256=hashlib.sha256(raw).hexdigest(),
                      image_checks=checks, clinical_validation=False, calibrated_cancer_probability=False, scope='single-2d-image',
                      external_requests=False, runtime=runner.runtime,
                      model_info=ModelInfo(source_url=manifest.source_url, license=manifest.license,
                                           evaluation_reference=manifest.evaluation.reference,
                                           patient_disjoint=manifest.evaluation.patient_disjoint))
        if checks.decision == 'rejected':
            return CancerResult(**common, outcome='input-rejected', outcome_reasons=['input-rejected'], scores=[],
                                inference_ms=round((time.perf_counter() - started) * 1000, 2))
        calibration = calibration_for(calibration_path, manifest.weights_sha256, manifest.model_version, manifest.labels)
        blob = prepare_input(image, manifest)
        logits, tensors = runner.predict_with_tensors(blob)
        scores = output_scores(logits, manifest, calibration.temperature if calibration else None)
        confidence = confidence_summary(scores, calibration)
        target = [item.label for item in scores].index(confidence.top_label)
        familiarity = familiarity_check(runner.explainer.embedding(tensors), calibration) if tensors else None
        heatmap = None
        if request.explain:
            if tensors:
                grid = np.asarray(runner.explainer.heatmap(tensors, target))
                heatmap = Heatmap(method=runner.explainer.method, target_label=confidence.top_label,
                                  class_specific=runner.explainer.method == 'grad-cam', grid_width=grid.shape[1], grid_height=grid.shape[0],
                                  values=normalized(grid), localization=False,
                                  meaning='regions-that-raised-the-score' if runner.explainer.method == 'grad-cam' else 'patches-the-model-attended-to')
            else:
                heatmap = occlusion_heatmap(runner, blob, manifest, scores, target, calibration)
    reasons = []
    if any(item.severity == 'limiting' for item in checks.findings):
        reasons.append('input-quality')
    if confidence.level == 'low':
        reasons.append('low-confidence')
    if familiarity is not None and not familiarity.familiar:
        reasons.append('unfamiliar-image')
    return CancerResult(**common, outcome='inconclusive' if reasons else 'finding', outcome_reasons=reasons,
                        finding_label=None if reasons else confidence.top_label, scores=scores, confidence=confidence,
                        familiarity=familiarity, heatmap=heatmap, inference_ms=round((time.perf_counter() - started) * 1000, 2))


def occlusion_heatmap(runner: ModelRunner, blob: np.ndarray, manifest: ModelManifest, scores: list[Score], target: int,
                      calibration: CalibrationEntry | None, grid: int = 4) -> Heatmap:
    """Measure top-class score changes under patch occlusion (fallback when no gradient-free map exists)."""
    temperature = calibration.temperature if calibration else None
    baseline = scores[target].value
    height, width = blob.shape[-2:]
    drops = []
    for row in range(grid):
        for column in range(grid):
            occluded = blob.copy()
            # Zero in normalized space corresponds to the model's mean color.
            occluded[:, :, row * height // grid:(row + 1) * height // grid, column * width // grid:(column + 1) * width // grid] = 0
            drops.append(max(0.0, baseline - output_scores(runner.predict(occluded), manifest, temperature)[target].value))
    return Heatmap(method='occlusion-sensitivity', target_label=scores[target].label, class_specific=True, grid_width=grid, grid_height=grid,
                   values=normalized(np.asarray(drops)), meaning='score-drop-under-occlusion', localization=False)
