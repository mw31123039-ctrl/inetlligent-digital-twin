"""Small, offline supervised baseline. No bundled dental weights or network calls.

Learns background, crown interiors and crown edges from reviewed RGB polygons.
This is a colour/texture random forest, not a diagnostic or treatment model.
"""
import base64
import hashlib
import json
import os
import threading
import uuid
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from .dental import DentalPhoto
from .dental_photo import CrownOutline, PhotoDetectionRequest, PhotoDetectionResult

FEATURE_VERSION = 'colour-texture-v1'
MAX_SIDE = 512
_lock = threading.Lock()


class TrainingExample(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['humantwin-local-crowns-v1']
    subject_code: str = Field(pattern=r'^[A-Za-z0-9_-]{1,48}$')
    reviewer_code: str = Field(pattern=r'^[A-Za-z0-9_-]{1,48}$')
    partition: Literal['train', 'validation', 'test']
    permission_training: Literal[True]
    complete_annotation: Literal[True]
    photo: DentalPhoto
    input_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    crowns: list[CrownOutline] = Field(min_length=1, max_length=32)


class LocalSegmentRequest(PhotoDetectionRequest):
    prompt: CrownOutline


def decode_photo(photo: DentalPhoto) -> tuple[np.ndarray, bytes]:
    raw = base64.b64decode(photo.data_url.split(',', 1)[1], validate=True)
    # Inspect SOF dimensions before OpenCV allocates a decoded image.
    index, dimensions = 2, None
    while index + 4 <= len(raw):
        if raw[index] != 255:
            raise ValueError('Invalid JPEG structure.')
        while index < len(raw) and raw[index] == 255:
            index += 1
        marker = raw[index]
        index += 1
        if marker in (0xD9, 0xDA):
            break
        length = int.from_bytes(raw[index:index + 2], 'big')
        if length < 2 or index + length > len(raw):
            raise ValueError('Invalid JPEG segment.')
        if marker in (0xC0, 0xC1, 0xC2):
            if length < 8:
                raise ValueError('Invalid JPEG dimensions.')
            dimensions = (int.from_bytes(raw[index + 5:index + 7], 'big'), int.from_bytes(raw[index + 3:index + 5], 'big'))
            break
        index += length
    if dimensions is None or min(dimensions) < 16 or max(dimensions) > 1024:
        raise ValueError('Use a re-encoded photograph, 16–1024 pixels on each side.')
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    if image is None or (image.shape[1], image.shape[0]) != dimensions:
        raise ValueError('The photograph could not be decoded.')
    scale = min(1, MAX_SIDE / max(dimensions))
    if scale < 1:
        image = cv2.resize(image, (round(dimensions[0] * scale), round(dimensions[1] * scale)), interpolation=cv2.INTER_AREA)
    return image, raw


def features(image: np.ndarray) -> np.ndarray:
    colour = image.astype(np.float32) / 255
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32) / 255
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32) / 255
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    layers = [colour, lab, hsv, grey[..., None]]
    for size in (3, 9):
        mean = cv2.blur(grey, (size, size))
        std = np.sqrt(np.maximum(0, cv2.blur(grey * grey, (size, size)) - mean * mean))
        layers.extend([mean[..., None], std[..., None]])
    layers.extend([cv2.Sobel(grey, cv2.CV_32F, 1, 0)[..., None], cv2.Sobel(grey, cv2.CV_32F, 0, 1)[..., None]])
    return np.ascontiguousarray(np.concatenate(layers, axis=2).reshape(-1, 16), dtype=np.float32)


def annotation_mask(image: np.ndarray, crowns: list[CrownOutline]) -> np.ndarray:
    height, width = image.shape[:2]
    labels = np.zeros((height, width), np.uint8)
    occupied = np.zeros_like(labels)
    interiors = np.zeros_like(labels)
    for crown in crowns:
        polygon = np.array([[round(p.x * (width - 1)), round(p.y * (height - 1))] for p in crown.points], np.int32)
        mask = np.zeros_like(labels)
        cv2.fillPoly(mask, [polygon], 1)
        interior = cv2.erode(mask, np.ones((3, 3), np.uint8))
        # A shared raster boundary is expected where adjacent crowns touch;
        # overlapping interiors would give contradictory instance supervision.
        if np.count_nonzero(mask) < 16 or np.any(interior & occupied) or np.any(mask & interiors):
            raise ValueError('Training crowns must be distinct, non-overlapping and at least 16 pixels.')
        occupied |= mask
        interiors |= interior
        labels[mask == 1] = 2
        labels[interior == 1] = 1
    if np.count_nonzero(labels == 0) < 50 or np.count_nonzero(labels == 1) < 20:
        raise ValueError('Training needs both crown interiors and non-tooth background.')
    return labels


def predict_mask(forest, image: np.ndarray) -> np.ndarray:
    matrix = features(image)
    predictions = [forest.predict(matrix[start:start + 32768])[1].ravel() for start in range(0, len(matrix), 32768)]
    return np.concatenate(predictions).reshape(image.shape[:2]).astype(np.uint8)


def outlines_from_mask(mask: np.ndarray) -> list[CrownOutline]:
    # Learned edge class separates interiors. Touching crowns may still merge;
    # never divide a blob into a fabricated fixed number of teeth.
    binary = (mask == 1).astype(np.uint8) * 255
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    height, width = mask.shape
    result = []
    for contour in sorted(contours, key=cv2.contourArea, reverse=True):
        area = cv2.contourArea(contour) / (height * width)
        _, _, w, h = cv2.boundingRect(contour)
        if not .0002 <= area <= .15 or not .15 <= w / max(1, h) <= 5:
            continue
        perimeter = cv2.arcLength(contour, True)
        polygon = None
        for epsilon in (.006, .01, .015, .02, .03, .04, .05):
            candidate = cv2.approxPolyDP(contour, epsilon * perimeter, True).reshape(-1, 2)
            if 4 <= len(candidate) <= 12:
                polygon = candidate
                break
        if polygon is None:
            continue
        try:
            result.append(CrownOutline(jaw='unknown', points=[{'x': float(x / (width - 1)), 'y': float(y / (height - 1))} for x, y in polygon]))
        except ValueError:
            continue
        if len(result) == 32:
            break
    return sorted(result, key=lambda crown: (min(p.y for p in crown.points), min(p.x for p in crown.points)))


def _load_model(directory: Path):
    pointer = directory / 'current.json'
    if not pointer.is_file() or pointer.stat().st_size > 256:
        raise ValueError('No trained local model.')
    generation = json.loads(pointer.read_text())['generation']
    if not isinstance(generation, str) or len(generation) != 32 or any(c not in '0123456789abcdef' for c in generation):
        raise ValueError('Invalid local model version.')
    location = directory / generation
    report_path, model_path = location / 'report.json', location / 'forest.xml'
    if report_path.stat().st_size > 100000 or model_path.stat().st_size > 50000000:
        raise ValueError('Invalid model size.')
    report = json.loads(report_path.read_text())
    if report.get('feature_version') != FEATURE_VERSION or report.get('clinical_validation') is not False or report.get('train_subjects', 0) < 2 or report.get('validation_subjects', 0) < 1:
        raise ValueError('The local model has no valid training report.')
    if hashlib.sha256(model_path.read_bytes()).hexdigest() != report.get('model_sha256'):
        raise ValueError('The model fingerprint changed.')
    forest = cv2.ml.RTrees_load(str(model_path))
    if not forest.isTrained() or not forest.isClassifier() or forest.getVarCount() != 16:
        raise ValueError('Invalid local classifier.')
    return forest, report


def local_status(directory: Path) -> dict:
    status = {'available': True, 'provider_configured': False, 'model_capability_verified': False,
              'draft_only': True, 'runtime': 'local', 'external_requests': False, 'state': 'not-trained',
              'train_images': 0, 'validation_images': 0, 'validation_dice': None}
    try:
        _, report = _load_model(directory)
        status.update(provider_configured=True, state='trained-unvalidated', train_images=report['train_images'],
                      validation_images=report['validation_images'], validation_dice=report['validation']['foreground_dice'])
    except (ValueError, OSError, KeyError, TypeError, cv2.error):
        pass
    return status


def detect_local_crowns(directory: Path, request: PhotoDetectionRequest) -> PhotoDetectionResult:
    with _lock:
        forest, _ = _load_model(directory)
        image, raw = decode_photo(request.photo)
        crowns = outlines_from_mask(predict_mask(forest, image))
    # No disease/occlusion classifier has been trained. Never derive diagnosis
    # or jaw identity from pixel colours or the number/position of contours.
    return PhotoDetectionResult(mode='photo-outline-draft', input_sha256=hashlib.sha256(raw).hexdigest(),
        clinical_validation=False, geometry_dimensions='2d-visible-crowns', image_quality='usable' if crowns else 'insufficient',
        crowns=crowns, possible_case_ids=[])


def refine_local_outline(request: LocalSegmentRequest) -> PhotoDetectionResult:
    """Fit per-image foreground/background GMMs around a human's rough polygon.

    GrabCut is assisted segmentation, never a pretrained dental detector. It does
    not persist or update the supervised random forest.
    """
    image, raw = decode_photo(request.photo)
    height, width = image.shape[:2]
    polygon = np.array([[round(p.x * (width - 1)), round(p.y * (height - 1))] for p in request.prompt.points], np.int32)
    original = np.zeros((height, width), np.uint8)
    cv2.fillPoly(original, [polygon], 1)
    if np.count_nonzero(original) < 36 or np.count_nonzero(original == 0) < 50:
        raise ValueError('The rough outline is too small or fills the photograph.')
    _, _, w, h = cv2.boundingRect(polygon)
    radius = max(2, round(min(w, h) * .12))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
    core = cv2.erode(original, kernel)
    if not core.any():
        raise ValueError('The outline has no clear interior.')
    surround = cv2.dilate(original, kernel)
    mask = np.full((height, width), cv2.GC_BGD, np.uint8)
    mask[surround == 1] = cv2.GC_PR_BGD
    mask[original == 1] = cv2.GC_PR_FGD
    mask[core == 1] = cv2.GC_FGD
    with _lock:
        cv2.grabCut(image, mask, None, np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64), 4, cv2.GC_INIT_WITH_MASK)
    foreground = np.isin(mask, [cv2.GC_FGD, cv2.GC_PR_FGD]).astype(np.uint8)
    crowns = outlines_from_mask(foreground)
    if crowns:
        # Return the component that best overlaps the user's selected crown.
        def overlap(crown):
            candidate = np.zeros_like(original)
            cv2.fillPoly(candidate, [np.array([[round(p.x * (width - 1)), round(p.y * (height - 1))] for p in crown.points], np.int32)], 1)
            return np.count_nonzero(candidate & original)
        crowns = [max(crowns, key=overlap)]
        crowns[0].jaw = request.prompt.jaw
    return PhotoDetectionResult(mode='photo-outline-draft', input_sha256=hashlib.sha256(raw).hexdigest(),
        clinical_validation=False, geometry_dimensions='2d-visible-crowns', image_quality='usable' if crowns else 'insufficient',
        crowns=crowns, possible_case_ids=[])


def _perceptual_hash(image: np.ndarray) -> int:
    grey = cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (9, 8))
    bits = (grey[:, 1:] > grey[:, :-1]).ravel()
    return sum(int(value) << index for index, value in enumerate(bits))


def train_local_model(examples: list[TrainingExample], directory: Path, progress=None) -> dict:
    if progress:
        progress('checking')
    if not 3 <= len(examples) <= 200:
        raise ValueError('Use 3–200 labelled photos; at least two training subjects and one separate validation subject. This minimum only checks the pipeline, not clinical adequacy.')
    groups, hashes, loaded = {}, {}, []
    for example in examples:
        group = example.subject_code.casefold()
        if group in groups and groups[group] != example.partition:
            raise ValueError('Every photo of one subject must stay in the same partition.')
        groups[group] = example.partition
        image, raw = decode_photo(example.photo)
        digest = hashlib.sha256(raw).hexdigest()
        if digest != example.input_sha256 or digest in hashes:
            raise ValueError('Photo fingerprint mismatch or duplicate image.')
        hashes[digest] = example.partition
        perceptual = _perceptual_hash(image)
        if any(partition != example.partition and (perceptual ^ other).bit_count() <= 4 for _, _, partition, other in loaded):
            raise ValueError('Near-duplicate photos cross dataset partitions. Keep related photos together.')
        loaded.append((image, annotation_mask(image, example.crowns), example.partition, perceptual))
    train_subjects = sum(partition == 'train' for partition in groups.values())
    validation_subjects = sum(partition == 'validation' for partition in groups.values())
    if train_subjects < 2 or validation_subjects < 1:
        raise ValueError('Use at least two training subjects and one separate validation subject.')
    rng = np.random.default_rng(42)
    inputs, outputs = [], []
    for image, labels, partition, _ in loaded:
        if partition != 'train':
            continue
        matrix, flattened = features(image), labels.ravel()
        for label in (0, 1, 2):
            indices = np.flatnonzero(flattened == label)
            if len(indices) == 0:
                raise ValueError('Missing background, crown interior or edge pixels.')
            indices = rng.choice(indices, min(len(indices), max(100, 40000 // len(loaded))), replace=False)
            inputs.append(matrix[indices]); outputs.append(flattened[indices])
    forest = cv2.ml.RTrees_create()
    forest.setMaxDepth(12)
    forest.setMinSampleCount(8)
    forest.setMaxCategories(3)
    forest.setTermCriteria((cv2.TERM_CRITERIA_MAX_ITER, 48, 0))
    cv2.setRNGSeed(42)
    if progress:
        progress('learning')
    if not forest.train(np.concatenate(inputs), cv2.ml.ROW_SAMPLE, np.concatenate(outputs).astype(np.int32)):
        raise ValueError('Local model training failed.')
    report = {'feature_version': FEATURE_VERSION, 'model_type': 'opencv-random-forest-pixel-baseline',
              'clinical_validation': False, 'condition_classification': False, 'training_performed': True,
              'train_subjects': train_subjects, 'validation_subjects': validation_subjects,
              'train_images': sum(item.partition == 'train' for item in examples),
              'validation_images': sum(item.partition == 'validation' for item in examples),
              'note': 'Small-data engineering metrics only. Colour/texture errors, merged teeth and false positives require human correction. No diagnosis, bite classification or treatment prediction.'}
    if progress:
        progress('validating')
    for partition in ('validation', 'test'):
        metrics = []
        for image, labels, selected, _ in loaded:
            if selected != partition:
                continue
            predicted = predict_mask(forest, image) > 0
            truth = labels > 0
            intersection = int(np.count_nonzero(predicted & truth))
            metrics.append(2 * intersection / max(1, np.count_nonzero(predicted) + np.count_nonzero(truth)))
        if metrics:
            report[partition] = {'images': len(metrics), 'foreground_dice': round(float(np.mean(metrics)), 6)}
    # New immutable version first, then atomic pointer: failed training leaves
    # the previous model intact. Reports contain counts, never photos or codes.
    if progress:
        progress('saving')
    generation = uuid.uuid4().hex
    destination = directory / generation
    destination.mkdir(parents=True, exist_ok=False)
    forest.save(str(destination / 'forest.xml'))
    report['model_sha256'] = hashlib.sha256((destination / 'forest.xml').read_bytes()).hexdigest()
    (destination / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    pointer = directory / f'current-{generation}.tmp'
    pointer.write_text(json.dumps({'generation': generation}), encoding='utf-8')
    os.replace(pointer, directory / 'current.json')
    return report
