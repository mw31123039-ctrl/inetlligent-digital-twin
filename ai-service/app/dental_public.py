"""Offline inference from a locally trained public-data ONNX tooth detector.

Boxes locate candidate teeth. GrabCut fits draft pixel boundaries independently;
neither the boxes nor the refined masks establish a diagnosis or FDI identity.
"""
import hashlib
import csv
import json
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from .dental_local import decode_photo
from .dental_photo import CrownOutline, PhotoDetectionRequest, PhotoDetectionResult

_lock = threading.Lock()
_cache = {}


def _training_status(directory: Path) -> dict | None:
    """Show recently recorded progress; stale/interrupted runs stay unavailable."""
    plan_path = directory / 'training-plan.json'
    try:
        if plan_path.stat().st_size > 2000:
            return None
        plan = json.loads(plan_path.read_text())
        run = plan['run']
        if not isinstance(run, str) or not run.startswith('visible-teeth') or not run.replace('-', '').isalnum():
            return None
        progress = directory / 'runs' / run / 'results.csv'
        if progress.stat().st_size > 1000000 or not 0 <= time.time() - progress.stat().st_mtime < 180:
            return None
        rows = list(csv.DictReader(progress.read_text().splitlines()))
        epoch = int(rows[-1]['epoch'])
        epochs = int(plan['epochs'])
        if not 0 < epoch <= epochs <= 500:
            return None
        return {'available': True, 'provider_configured': False, 'model_capability_verified': False,
                'draft_only': True, 'runtime': 'local', 'external_requests': False, 'state': 'training',
                'model_source': 'public-dataset', 'train_images': int(plan['train_images']),
                'validation_images': int(plan['validation_images']), 'validation_dice': None,
                'training_epoch': epoch, 'training_epochs': epochs}
    except (ValueError, OSError, KeyError, TypeError, IndexError):
        return None


def _load(directory: Path):
    model, metadata = directory / 'detector.onnx', directory / 'report.json'
    if metadata.stat().st_size > 50000 or not 100000 < model.stat().st_size < 50000000:
        raise ValueError('Invalid public detector artifact size.')
    key = (str(directory.resolve()), model.stat().st_mtime_ns, model.stat().st_size, metadata.stat().st_mtime_ns)
    if key in _cache:
        return _cache[key]
    report = json.loads(metadata.read_text())
    if (not isinstance(report, dict) or report.get('format') != 'humantwin-public-tooth-detector-v1'
        or report.get('clinical_validation') is not False or report.get('training_performed') is not True
        or report.get('condition_classifier_trained') is not False or report.get('input_size') != 640
        or report.get('train_images', 0) < 1 or report.get('validation_images', 0) < 1
        or hashlib.sha256(model.read_bytes()).hexdigest() != report.get('model_sha256')):
        raise ValueError('Invalid public detector training report or fingerprint.')
    net = cv2.dnn.readNetFromONNX(str(model))
    net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
    net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    _cache.clear()
    _cache[key] = net, report
    return net, report


def public_status(directory: Path) -> dict | None:
    with _lock:
        try:
            _, report = _load(directory)
        except (ValueError, OSError, KeyError, TypeError, cv2.error):
            return _training_status(directory)
    return {'available': True, 'provider_configured': True, 'model_capability_verified': False,
            'draft_only': True, 'runtime': 'local', 'external_requests': False, 'state': 'trained-unvalidated',
            'model_source': 'public-dataset', 'train_images': report['train_images'],
            'validation_images': report['validation_images'], 'validation_dice': None,
            'patient_disjoint_verified': False, 'mask_validation_available': False}


def candidate_boxes(output: np.ndarray, width: int, height: int, scale: float, pad_x: int, pad_y: int) -> list:
    if output.shape != (1, 5, 8400) or not np.isfinite(output).all():
        raise ValueError('Unexpected single-class detector output.')
    rows = output[0].T
    boxes, scores = [], []
    for x, y, w, h, score in rows:
        if score < .35 or score > 1 or w <= 0 or h <= 0:
            continue
        left, top = max(0, (x - w / 2 - pad_x) / scale), max(0, (y - h / 2 - pad_y) / scale)
        right, bottom = min(width - 1, (x + w / 2 - pad_x) / scale), min(height - 1, (y + h / 2 - pad_y) / scale)
        bw, bh = right - left, bottom - top
        if bw < 5 or bh < 5 or not .0002 < bw * bh / (width * height) < .15:
            continue
        boxes.append([int(left), int(top), int(bw), int(bh)])
        scores.append(float(score))
    keep = cv2.dnn.NMSBoxes(boxes, scores, .35, .4)
    return [boxes[int(i)] for i in np.asarray(keep).reshape(-1)[:32]]


def outline_in_box(image: np.ndarray, box: list) -> CrownOutline | None:
    height, width = image.shape[:2]
    x, y, w, h = box
    margin = max(3, round(min(w, h) * .15))
    left, top = max(0, x - margin), max(0, y - margin)
    right, bottom = min(width, x + w + margin), min(height, y + h + margin)
    crop = image[top:bottom, left:right].copy()
    mask = np.full(crop.shape[:2], cv2.GC_BGD, np.uint8)
    bx, by = x - left, y - top
    mask[by:by + h, bx:bx + w] = cv2.GC_PR_FGD
    # A small central seed starts per-image fitting, never learned crown masks.
    mask[by + h // 3:by + 2 * h // 3, bx + w // 3:bx + 2 * w // 3] = cv2.GC_FGD
    try:
        cv2.grabCut(crop, mask, None, np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64), 4, cv2.GC_INIT_WITH_MASK)
    except cv2.error:
        return None
    foreground = np.isin(mask, [cv2.GC_FGD, cv2.GC_PR_FGD]).astype(np.uint8)
    contours, _ = cv2.findContours(foreground, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < w * h * .15:
        return None
    perimeter = cv2.arcLength(contour, True)
    for epsilon in (.005, .01, .015, .02, .03, .04):
        polygon = cv2.approxPolyDP(contour, epsilon * perimeter, True).reshape(-1, 2)
        if 4 <= len(polygon) <= 12:
            try:
                return CrownOutline(jaw='unknown', points=[{'x': float((px + left) / (width - 1)),
                                                          'y': float((py + top) / (height - 1))} for px, py in polygon])
            except ValueError:
                return None
    return None


def detect_public_crowns(directory: Path, request: PhotoDetectionRequest) -> PhotoDetectionResult:
    image, raw = decode_photo(request.photo)
    height, width = image.shape[:2]
    scale = 640 / max(width, height)
    resized = cv2.resize(image, (round(width * scale), round(height * scale)))
    pad_x, pad_y = (640 - resized.shape[1]) // 2, (640 - resized.shape[0]) // 2
    canvas = np.full((640, 640, 3), 114, np.uint8)
    canvas[pad_y:pad_y + resized.shape[0], pad_x:pad_x + resized.shape[1]] = resized
    with _lock:
        net, _ = _load(directory)
        net.setInput(cv2.dnn.blobFromImage(canvas, 1 / 255, (640, 640), swapRB=True, crop=False))
        output = net.forward()
    boxes = candidate_boxes(output, width, height, scale, pad_x, pad_y)
    crowns = [crown for box in boxes if (crown := outline_in_box(image, box)) is not None]
    crowns.sort(key=lambda c: (min(p.y for p in c.points), min(p.x for p in c.points)))
    return PhotoDetectionResult(mode='photo-outline-draft', input_sha256=hashlib.sha256(raw).hexdigest(),
        clinical_validation=False, geometry_dimensions='2d-visible-crowns',
        image_quality='usable' if crowns else 'insufficient', crowns=crowns, possible_case_ids=[])
