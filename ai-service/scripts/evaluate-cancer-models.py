"""Evaluate the installed cancer image models on held-out data and fit their calibration.

For each model the script builds a cohort with two disjoint parts:

  calibration  used only to fit the temperature, the decision threshold and the familiarity
               reference (never reported as performance);
  test         used only for the reported metrics.

Every image goes through the same path as the app: browser-style preparation (white background,
longest side <= 2048 px, JPEG quality 0.95), JPEG decoding, input checks, the manifest's
preprocessing and the installed ONNX model. Model files are only read, never changed.

Outputs (default ../research/cancer-evaluation/<modality>/): metrics.json, metrics.md,
per_class.csv, predictions.csv and PNG charts (confusion matrix, ROC, reliability), plus
summary.md and model cards in ../research/model-cards/. With --write-calibration the fitted values
are stored in calibration/cancer-calibration.json for the running service.

Data (git-ignored, see research/CANCER_EVALUATION.md for sources and licences):
  training-data/cancer-oral/                local oral split (validation -> calibration, test -> test)
  training-data/cancer-eval/downloads/      ISIC 2018 Task 3, LungCancer4Types + author split, BUS-BRA
Run --download first to fetch the public sets.

Example (from ai-service):
  python scripts/evaluate-cancer-models.py --download
  python scripts/evaluate-cancer-models.py --write-calibration
"""
import argparse
import base64
import csv
import hashlib
import io
import json
import math
import random
import sys
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.cancer import MODALITIES, decode_image, load_bundle, prepare_input  # noqa: E402
from app.cancer_calibration import CalibrationEntry, FamiliarityReference, write_entry  # noqa: E402
from app.cancer_quality import check_image  # noqa: E402

SEED = 2026
DOWNLOADS = ROOT / 'training-data/cancer-eval/downloads'
SOURCES = {
    'ISIC2018_Task3_Validation_Input.zip': 'https://isic-archive.s3.amazonaws.com/challenges/2018/ISIC2018_Task3_Validation_Input.zip',
    'ISIC2018_Task3_Validation_GroundTruth.zip': 'https://isic-archive.s3.amazonaws.com/challenges/2018/ISIC2018_Task3_Validation_GroundTruth.zip',
    'ISIC2018_Task3_Test_Input.zip': 'https://isic-archive.s3.amazonaws.com/challenges/2018/ISIC2018_Task3_Test_Input.zip',
    'ISIC2018_Task3_Test_GroundTruth.zip': 'https://isic-archive.s3.amazonaws.com/challenges/2018/ISIC2018_Task3_Test_GroundTruth.zip',
    'LungCancer4Types.zip': 'https://huggingface.co/datasets/Kabil007/LungCancer4Types/resolve/main/Data-20240107T052410Z-001.zip',
    'lung_test_dev_split.csv': 'https://huggingface.co/yunussgultekiin/lung-cancer-efficientnet-b0/resolve/506c398b6fd10b3e9f046c908c2b59bb33547faf/data/splits/test_dev_split.csv',
    'BUSBRA.zip': 'https://zenodo.org/records/8231412/files/BUSBRA.zip?download=1',
}
# Classes counted as cancer (or, for actinic keratoses / AKIEC, intraepithelial carcinoma) in the binary view.
POSITIVE = {
    'dermoscopy': ['melanoma', 'basal_cell_carcinoma', 'actinic_keratoses'],
    'oral_photo': ['malignant_lesion'],
    'lung_ct_slice': ['adenocarcinoma', 'large.cell.carcinoma', 'squamous.cell.carcinoma'],
    'breast_ultrasound': ['malignant'],
}
ISIC_LABELS = {'MEL': 'melanoma', 'NV': 'melanocytic_Nevi', 'BCC': 'basal_cell_carcinoma', 'AKIEC': 'actinic_keratoses',
               'BKL': 'benign_keratosis-like_lesions', 'DF': 'dermatofibroma', 'VASC': 'vascular_lesions'}
TRACK = {modality: track for track, items in MODALITIES.items() for modality in items}


@dataclass
class Item:
    key: str            # public identifier or relative path, never a local absolute path
    label: str
    split: str          # 'calibration' or 'test'
    group: str          # patient, lesion cluster or image group used to keep splits disjoint
    load: object        # callable returning image bytes


# ----------------------------------------------------------------------------- data

def download():
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        target = DOWNLOADS / name
        if target.exists() and target.stat().st_size > 0:
            print('present', name, target.stat().st_size, 'bytes')
            continue
        print('downloading', name, flush=True)
        partial = target.with_suffix(target.suffix + '.part')
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'humantwin-research-evaluation'}), timeout=120) as response, open(partial, 'wb') as handle:
            while chunk := response.read(1 << 20):
                handle.write(chunk)
        partial.replace(target)
    for name in SOURCES:
        print(name, hashlib.sha256((DOWNLOADS / name).read_bytes()).hexdigest())


def zip_reader(path):
    archive = zipfile.ZipFile(path)
    return archive, (lambda member: (lambda: archive.read(member)))


def grouped_split(items, fraction, seed):
    """Assign whole groups to calibration with roughly `fraction` of each label; the rest is test."""
    rng = random.Random(seed)
    by_label = {}
    for item in items:
        by_label.setdefault(item.label, {}).setdefault(item.group, []).append(item)
    calibration_groups = set()
    for label, groups in sorted(by_label.items()):
        keys = sorted(groups)
        rng.shuffle(keys)
        target, taken = fraction * sum(len(groups[key]) for key in keys), 0
        for key in keys:
            if taken >= target:
                break
            calibration_groups.add(key)
            taken += len(groups[key])
    for item in items:
        item.split = 'calibration' if item.group in calibration_groups else 'test'
    return items


def cohort(modality):
    """Return (items, description) or raise FileNotFoundError when the data is not present."""
    if modality == 'oral_photo':
        manifest = json.loads((ROOT / 'training-data/cancer-oral/split-manifest.json').read_text())
        records = manifest['records'] if isinstance(manifest, dict) else manifest
        items = []
        for record in records:
            if record['split'] not in ('validation', 'test'):
                continue
            label = record['label'] if isinstance(record['label'], str) else ['benign_lesion', 'malignant_lesion'][record['label']]
            path = ROOT / 'training-data/cancer-oral/originals' / label / Path(record['path']).name
            items.append(Item(f'{label}/{path.name}', label, 'calibration' if record['split'] == 'validation' else 'test',
                              record.get('group_id', path.name), (lambda p=path: p.read_bytes())))
        return items, ('Mendeley Oral Images Dataset v2 (Chandrashekar et al., CC BY 4.0), fixed image-group split from training: '
                       'validation split for calibration, test split for metrics. The test split was inspected during earlier '
                       'development (research/CANCER_MODEL_IMPROVEMENT.md), so it is not a new blind test.')
    if modality == 'lung_ct_slice':
        archive, member = zip_reader(DOWNLOADS / 'LungCancer4Types.zip')
        names = set(archive.namelist())
        items = []
        with open(DOWNLOADS / 'lung_test_dev_split.csv', newline='', encoding='utf-8') as handle:
            for row in csv.DictReader(handle):
                if row['split'] != 'test':
                    continue
                name = 'Data/' + row['relative_path']
                if name not in names:
                    raise FileNotFoundError(name)
                items.append(Item(row['relative_path'], row['class_name'], '', 'cluster-' + row['cluster_id'], member(name)))
        return grouped_split(items, .4, SEED), ('LungCancer4Types (Kabil007, Apache-2.0): the model author\'s own 165-image held-out test split '
                                                '(data/splits/test_dev_split.csv at the pinned model revision; the model was trained on the '
                                                'other 659 de-duplicated images). Split here by near-duplicate cluster: 40% calibration, 60% test.')
    if modality == 'dermoscopy':
        items = []
        for part, split in (('Validation', 'calibration'), ('Test', 'test')):
            truth_zip = zipfile.ZipFile(DOWNLOADS / f'ISIC2018_Task3_{part}_GroundTruth.zip')
            truth_name = next(name for name in truth_zip.namelist() if name.endswith('.csv'))
            archive, member = zip_reader(DOWNLOADS / f'ISIC2018_Task3_{part}_Input.zip')
            members = {Path(name).stem: name for name in archive.namelist() if name.lower().endswith('.jpg')}
            for row in csv.DictReader(io.StringIO(truth_zip.read(truth_name).decode('utf-8'))):
                code = max(ISIC_LABELS, key=lambda key: float(row[key]))
                items.append(Item(row['image'], ISIC_LABELS[code], split, row['image'], member(members[row['image']])))
        return items, ('ISIC 2018 Task 3 (HAM10000 challenge; CC BY-NC 4.0, attribution: ISIC Archive, Tschandl et al. 2018, Codella et al. 2019): '
                       'official validation set (193 images) for calibration and official test set (1,512 images) for metrics. The model was '
                       'fine-tuned on HAM10000, i.e. the challenge training set; the validation and test images were released separately.')
    if modality == 'breast_ultrasound':
        archive, member = zip_reader(DOWNLOADS / 'BUSBRA.zip')
        names = {Path(name).stem: name for name in archive.namelist() if name.startswith('BUSBRA/Images/')}
        rows = list(csv.DictReader(io.StringIO(archive.read('BUSBRA/bus_data.csv').decode('utf-8'))))
        items = [Item(row['ID'], row['Pathology'].strip().lower(), '', 'case-' + row['Case'], member(names[row['ID']])) for row in rows]
        return grouped_split(items, .3, SEED), ('BUS-BRA (Gomez-Flores et al. 2024, Zenodo 10.5281/zenodo.8231412, CC BY 4.0): 1,875 biopsy-proven '
                                                'breast ultrasound images from 1,064 patients in Brazil, external to the model\'s training data (BUSI). '
                                                'Split by patient: 30% calibration, 70% test. BUS-BRA has no "normal" images, so the model\'s normal '
                                                'class is never correct here.')
    raise ValueError(modality)


# ----------------------------------------------------------------------------- inference

def browser_jpeg(raw):
    """Emulate frontend/src/cancer/model.ts readResearchImage: white background, <= 2048 px, JPEG q=0.95."""
    image = Image.open(io.BytesIO(raw))
    image.load()
    if image.mode in ('RGBA', 'LA', 'P'):
        image = image.convert('RGBA')
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.getchannel('A'))
        image = background
    image = image.convert('RGB')
    factor = min(1, 2048 / max(image.size))
    if factor < 1:
        image = image.resize((max(32, round(image.width * factor)), max(32, round(image.height * factor))), Image.Resampling.BILINEAR, reducing_gap=2)
    buffer = io.BytesIO()
    image.save(buffer, 'JPEG', quality=95)
    return 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode()


def run_model(manifest, runner, raw, modality):
    image, _ = decode_image(browser_jpeg(raw))
    checks = check_image(image, modality, manifest.input_size)
    blob = prepare_input(image, manifest)
    names = [runner.output_name] + ([runner.explainer.embedding_output] if runner.explainer else [])
    values = runner.network.run(names, {runner.input_name: blob})
    logits = np.asarray(values[0], np.float64).reshape(-1)
    embedding = runner.explainer.embedding(dict(zip(names, values))) if runner.explainer else None
    return logits, embedding, checks


def infer_all(manifest, runner, items, modality, label):
    rows, started = [], time.perf_counter()
    for index, item in enumerate(items, 1):
        try:
            logits, embedding, checks = run_model(manifest, runner, item.load(), modality)
            rows.append({'item': item, 'logits': logits, 'embedding': embedding, 'decision': checks.decision,
                         'limiting': [check.code for check in checks.findings if check.severity == 'limiting'],
                         'rejected': [check.code for check in checks.findings if check.severity == 'reject']})
        except Exception as error:  # an unreadable file is reported, not silently dropped
            rows.append({'item': item, 'error': type(error).__name__})
        if index % 100 == 0 or index == len(items):
            print(f'  {label}: {index}/{len(items)} images, {time.perf_counter() - started:.0f}s', flush=True)
    return rows


# ----------------------------------------------------------------------------- statistics

def softmax(logits, temperature=1.0):
    values = np.asarray(logits, np.float64) / temperature
    values = np.exp(values - values.max(axis=-1, keepdims=True))
    return values / values.sum(axis=-1, keepdims=True)


def fit_temperature(logits, targets):
    """Temperature minimising the negative log-likelihood (golden-section search on log T)."""
    def nll(log_t):
        probabilities = softmax(logits, math.exp(log_t))
        return -np.mean(np.log(np.maximum(probabilities[np.arange(len(targets)), targets], 1e-12)))
    low, high = math.log(.05), math.log(20)
    ratio = (math.sqrt(5) - 1) / 2
    a, b = high - ratio * (high - low), low + ratio * (high - low)
    for _ in range(80):
        if nll(a) < nll(b):
            high, b = b, a
            a = high - ratio * (high - low)
        else:
            low, a = a, b
            b = low + ratio * (high - low)
    return float(math.exp((low + high) / 2))


def wilson(successes, total):
    if total == 0:
        return None
    z, p = 1.959963984540054, successes / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return [round(max(0, centre - half), 4), round(min(1, centre + half), 4)]


def auc(scores, positives):
    """ROC AUC by the Mann-Whitney statistic (ties count one half)."""
    scores, positives = np.asarray(scores, np.float64), np.asarray(positives, bool)
    positive, negative = scores[positives], scores[~positives]
    if len(positive) == 0 or len(negative) == 0:
        return None
    ranks = np.empty(len(scores))
    order = np.argsort(scores, kind='mergesort')
    sorted_scores = scores[order]
    position = 0
    while position < len(scores):
        end = position
        while end + 1 < len(scores) and sorted_scores[end + 1] == sorted_scores[position]:
            end += 1
        ranks[order[position:end + 1]] = (position + end) / 2 + 1
        position = end + 1
    return float((ranks[positives].sum() - len(positive) * (len(positive) + 1) / 2) / (len(positive) * len(negative)))


def roc_points(scores, positives):
    scores, positives = np.asarray(scores), np.asarray(positives, bool)
    thresholds = np.unique(scores)[::-1]
    points = [(0.0, 0.0)]
    for threshold in thresholds:
        predicted = scores >= threshold
        points.append((float((predicted & ~positives).sum() / max(1, (~positives).sum())), float((predicted & positives).sum() / max(1, positives.sum()))))
    return points


def bootstrap(statistic, size, rounds=2000, seed=SEED):
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(rounds):
        value = statistic(rng.integers(0, size, size))
        if value is not None and np.isfinite(value):
            values.append(value)
    return [round(float(np.percentile(values, 2.5)), 4), round(float(np.percentile(values, 97.5)), 4)] if len(values) > rounds * .9 else None


def expected_calibration_error(probabilities, targets, bins=15):
    confidence = probabilities.max(axis=1)
    correct = probabilities.argmax(axis=1) == targets
    edges = np.linspace(0, 1, bins + 1)
    error, table = 0.0, []
    for low, high in zip(edges[:-1], edges[1:]):
        inside = (confidence > low) & (confidence <= high)
        if inside.any():
            error += inside.mean() * abs(correct[inside].mean() - confidence[inside].mean())
            table.append({'bin': [round(float(low), 3), round(float(high), 3)], 'count': int(inside.sum()),
                          'accuracy': round(float(correct[inside].mean()), 4), 'confidence': round(float(confidence[inside].mean()), 4)})
    return float(error), table


def rounded(value, digits=4):
    return None if value is None else round(float(value), digits)


def classification_report(probabilities, targets, labels, positive_labels):
    count = len(labels)
    predicted = probabilities.argmax(axis=1)
    confusion = np.zeros((count, count), int)
    for actual, guess in zip(targets, predicted):
        confusion[actual, guess] += 1
    per_class, recalls, f1s = {}, [], []
    for index, label in enumerate(labels):
        tp = int(confusion[index, index]); fn = int(confusion[index].sum() - tp); fp = int(confusion[:, index].sum() - tp)
        tn = int(confusion.sum() - tp - fn - fp)
        support = tp + fn
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / support if support else None
        specificity = tn / (tn + fp) if tn + fp else None
        f1 = 2 * precision * recall / (precision + recall) if precision and recall else (0.0 if support else None)
        class_auc = auc(probabilities[:, index], targets == index)
        per_class[label] = {'support': support, 'precision': rounded(precision), 'sensitivity_recall': rounded(recall),
                            'sensitivity_95ci': wilson(tp, support), 'specificity': rounded(specificity), 'specificity_95ci': wilson(tn, tn + fp),
                            'f1': rounded(f1), 'auc_one_vs_rest': rounded(class_auc)}
        if support:
            recalls.append(recall); f1s.append(f1)
    aucs = [value['auc_one_vs_rest'] for value in per_class.values() if value['auc_one_vs_rest'] is not None]
    correct = int((predicted == targets).sum())
    positive_index = [labels.index(label) for label in positive_labels]
    is_positive = np.isin(targets, positive_index)
    predicted_positive = np.isin(predicted, positive_index)
    score = probabilities[:, positive_index].sum(axis=1)
    tp = int((is_positive & predicted_positive).sum()); fn = int((is_positive & ~predicted_positive).sum())
    tn = int((~is_positive & ~predicted_positive).sum()); fp = int((~is_positive & predicted_positive).sum())
    binary_f1 = 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else None
    binary_auc = auc(score, is_positive)
    nll = -np.mean(np.log(np.maximum(probabilities[np.arange(len(targets)), targets], 1e-12)))
    one_hot = np.eye(count)[targets]
    return {
        'images': int(len(targets)), 'accuracy': rounded(correct / len(targets)), 'accuracy_95ci': wilson(correct, len(targets)),
        'balanced_accuracy': rounded(np.mean(recalls)), 'macro_f1': rounded(np.mean(f1s)),
        'macro_auc_one_vs_rest': rounded(np.mean(aucs)) if aucs else None,
        'confusion_matrix': {'labels': labels, 'rows_actual_columns_predicted': confusion.tolist()},
        'per_class': per_class,
        'cancer_vs_not': {
            'positive_classes': positive_labels, 'positives': int(is_positive.sum()), 'negatives': int((~is_positive).sum()),
            'sensitivity': rounded(tp / (tp + fn)) if tp + fn else None, 'sensitivity_95ci': wilson(tp, tp + fn),
            'specificity': rounded(tn / (tn + fp)) if tn + fp else None, 'specificity_95ci': wilson(tn, tn + fp),
            'precision': rounded(tp / (tp + fp)) if tp + fp else None, 'f1': rounded(binary_f1),
            'auc': rounded(binary_auc), 'auc_95ci_bootstrap': bootstrap(lambda sample: auc(score[sample], is_positive[sample]), len(targets)) if binary_auc is not None else None,
            'confusion': {'true_positive': tp, 'false_negative': fn, 'true_negative': tn, 'false_positive': fp},
            'decision_rule': 'Predicted positive when the highest-scoring class is a cancer class.',
        },
        'negative_log_likelihood': rounded(nll), 'brier_score_multiclass': rounded(np.mean(((probabilities - one_hot) ** 2).sum(axis=1))),
        'expected_calibration_error_15_bins': rounded(expected_calibration_error(probabilities, targets)[0]),
    }


def choose_threshold(probabilities, targets, minimum_coverage=.75):
    """Highest selective accuracy on the calibration split with at least 75% of images answered."""
    confidence, correct = probabilities.max(axis=1), probabilities.argmax(axis=1) == targets
    best = (.5, -1.0)
    for threshold in np.round(np.arange(.5, .951, .05), 2):
        kept = confidence >= threshold
        if kept.mean() >= minimum_coverage and kept.any():
            accuracy = correct[kept].mean()
            if accuracy > best[1] + 1e-9:
                best = (float(threshold), float(accuracy))
    return best[0]


def selective(probabilities, targets, threshold):
    confidence, correct = probabilities.max(axis=1), probabilities.argmax(axis=1) == targets
    kept = confidence >= threshold
    return {'decision_threshold': threshold, 'answered_fraction': rounded(kept.mean()), 'inconclusive_fraction': rounded(1 - kept.mean()),
            'accuracy_when_answered': rounded(correct[kept].mean()) if kept.any() else None,
            'accuracy_when_inconclusive': rounded(correct[~kept].mean()) if (~kept).any() else None}


# ----------------------------------------------------------------------------- familiarity

def familiarity_reference(embeddings, targets, labels, quantile=2.0):
    matrix = np.asarray(embeddings, np.float64)
    overall = matrix.mean(axis=0)
    centroids = []
    for index in range(len(labels)):
        members = matrix[targets == index]
        centroid = members.mean(axis=0) if len(members) else overall
        centroids.append(centroid / np.linalg.norm(centroid))
    centroids = np.asarray(centroids)
    similarities = (matrix @ centroids.T).max(axis=1)
    minimum = float(np.percentile(similarities, quantile))
    return centroids, round(minimum, 4)


def similarity(embedding, centroids):
    return float((centroids @ embedding).max())


def synthetic_images():
    rng = np.random.default_rng(SEED)
    images = {}
    noise = rng.integers(0, 256, (384, 384, 3), np.uint8)
    images['synthetic-color-noise'] = noise
    gradient = np.dstack([*np.meshgrid(np.linspace(0, 255, 384), np.linspace(255, 0, 384)), np.full((384, 384), 128.0)]).astype(np.uint8)
    images['synthetic-gradient'] = gradient
    scene = np.full((384, 512, 3), (90, 150, 210), np.uint8)
    scene[200:] = (60, 140, 70)
    for _ in range(12):
        x, y, r = rng.integers(30, 480), rng.integers(30, 350), rng.integers(10, 50)
        yy, xx = np.ogrid[:384, :512]
        scene[(yy - y) ** 2 + (xx - x) ** 2 < r * r] = rng.integers(0, 256, 3)
    images['synthetic-photo-scene'] = scene
    gray = np.clip(rng.normal(110, 40, (384, 384)), 0, 255).astype(np.uint8)
    images['synthetic-gray-noise'] = np.dstack([gray] * 3)
    encoded = {}
    for name, array in images.items():
        buffer = io.BytesIO(); Image.fromarray(array).save(buffer, 'PNG'); encoded[name] = buffer.getvalue()
    return encoded


def other_area_images(modality, per_source=60):
    """Images from the other three areas plus synthetic images, for the wrong-input analysis."""
    collected = []
    for other in ('dermoscopy', 'oral_photo', 'lung_ct_slice', 'breast_ultrasound'):
        if other == modality:
            continue
        try:
            items, _ = cohort(other)
        except (FileNotFoundError, KeyError, OSError):
            continue
        test = [item for item in items if item.split == 'test']
        random.Random(SEED).shuffle(test)
        collected += [(other, item.key, item.load) for item in test[:per_source]]
    collected += [('synthetic', name, (lambda raw=raw: raw)) for name, raw in synthetic_images().items()]
    return collected


# ----------------------------------------------------------------------------- reporting

def charts(directory, labels, report_raw, test_probabilities, test_targets, calibrated, positive_labels):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print('  matplotlib is not installed; charts skipped')
        return []
    written = []
    readable = [label.replace('_', ' ').replace('.', ' ') for label in labels]
    matrix = np.asarray(report_raw['confusion_matrix']['rows_actual_columns_predicted'])
    figure, axis = plt.subplots(figsize=(1.1 * len(labels) + 3, 1.0 * len(labels) + 2.5))
    shares = matrix / np.maximum(matrix.sum(axis=1, keepdims=True), 1)
    axis.imshow(shares, cmap='Greens', vmin=0, vmax=1)
    for row in range(len(labels)):
        for column in range(len(labels)):
            axis.text(column, row, f'{matrix[row, column]}\n{shares[row, column]:.0%}', ha='center', va='center', fontsize=9,
                      color='white' if shares[row, column] > .55 else '#1c3c3d')
    axis.set_xticks(range(len(labels)), readable, rotation=35, ha='right'); axis.set_yticks(range(len(labels)), readable)
    axis.set_xlabel('Predicted class'); axis.set_ylabel('Reference class'); axis.set_title('Confusion matrix (test split)')
    figure.tight_layout(); figure.savefig(directory / 'confusion_matrix.png', dpi=160); plt.close(figure)
    written.append('confusion_matrix.png')

    positive_index = [labels.index(label) for label in positive_labels]
    figure, axis = plt.subplots(figsize=(5.4, 5))
    is_positive = np.isin(test_targets, positive_index)
    points = roc_points(test_probabilities[:, positive_index].sum(axis=1), is_positive)
    axis.plot([p[0] for p in points], [p[1] for p in points], color='#287b62', linewidth=2.4,
              label='Cancer vs not' + (f" (AUC {report_raw['cancer_vs_not']['auc']:.3f})" if report_raw['cancer_vs_not']['auc'] is not None else ''))
    if len(labels) > 2:
        for index, label in enumerate(labels):
            if (test_targets == index).any() and (test_targets != index).any():
                class_points = roc_points(test_probabilities[:, index], test_targets == index)
                axis.plot([p[0] for p in class_points], [p[1] for p in class_points], linewidth=1, alpha=.65, label=f'{readable[index]} (one vs rest)')
    axis.plot([0, 1], [0, 1], color='#999', linestyle='--', linewidth=1)
    axis.set_xlabel('False positive rate (1 - specificity)'); axis.set_ylabel('True positive rate (sensitivity)')
    axis.set_title('ROC curves (test split)'); axis.legend(fontsize=7, loc='lower right'); figure.tight_layout()
    figure.savefig(directory / 'roc.png', dpi=160); plt.close(figure)
    written.append('roc.png')

    figure, axis = plt.subplots(figsize=(5.4, 5))
    for name, probabilities, color in (('Uncalibrated', test_probabilities, '#b0832f'), ('Temperature-scaled', calibrated, '#287b62')):
        _, table = expected_calibration_error(probabilities, test_targets, bins=10)
        axis.plot([row['confidence'] for row in table], [row['accuracy'] for row in table], marker='o', color=color, label=name)
    axis.plot([0, 1], [0, 1], color='#999', linestyle='--', linewidth=1)
    axis.set_xlabel('Mean confidence of the top class'); axis.set_ylabel('Observed accuracy'); axis.set_title('Reliability diagram (test split)')
    axis.legend(); figure.tight_layout(); figure.savefig(directory / 'reliability.png', dpi=160); plt.close(figure)
    written.append('reliability.png')
    return written


def table(rows, header):
    lines = ['| ' + ' | '.join(header) + ' |', '|' + '|'.join('---' for _ in header) + '|']
    lines += ['| ' + ' | '.join('' if cell is None else str(cell) for cell in row) + ' |' for row in rows]
    return '\n'.join(lines)


def percent(value):
    return 'n/a' if value is None else f'{value * 100:.1f}%'


def interval(pair):
    return '' if not pair else f' ({pair[0] * 100:.1f}-{pair[1] * 100:.1f})'


def markdown(metrics):
    raw, binary = metrics['test_metrics_uncalibrated'], metrics['test_metrics_uncalibrated']['cancer_vs_not']
    lines = [f"# Evaluation: {metrics['model_version']}", '', f"*Generated by `ai-service/scripts/evaluate-cancer-models.py` on {metrics['generated']}.*", '',
             f"**Data:** {metrics['data']}", '',
             f"Calibration split: {metrics['splits']['calibration_images']} images. Test split: {metrics['splits']['test_images']} images "
             f"({metrics['splits']['test_groups']} groups).", '', '## Headline metrics (test split, argmax decision)', '',
             table([['Accuracy', percent(raw['accuracy']) + interval(raw['accuracy_95ci'])],
                    ['Balanced accuracy', percent(raw['balanced_accuracy'])],
                    ['Macro F1', rounded(raw['macro_f1'], 3)],
                    ['Macro AUC (one vs rest)', rounded(raw['macro_auc_one_vs_rest'], 3)],
                    ['Cancer vs not: sensitivity', percent(binary['sensitivity']) + interval(binary['sensitivity_95ci'])],
                    ['Cancer vs not: specificity', percent(binary['specificity']) + interval(binary['specificity_95ci'])],
                    ['Cancer vs not: F1', rounded(binary['f1'], 3)],
                    ['Cancer vs not: AUC', f"{rounded(binary['auc'], 3)}" + (f" ({binary['auc_95ci_bootstrap'][0]:.3f}-{binary['auc_95ci_bootstrap'][1]:.3f})" if binary['auc_95ci_bootstrap'] else '')]],
                   ['Metric', 'Value (95% CI)']), '',
             f"Cancer classes in the binary view: {', '.join(binary['positive_classes'])}. Intervals: Wilson score for proportions, "
             'stratified-free bootstrap (2,000 resamples) for AUC.', '', '## Per class (test split)', '',
             table([[label, values['support'], percent(values['sensitivity_recall']) + interval(values['sensitivity_95ci']),
                     percent(values['specificity']), rounded(values['precision'], 3), rounded(values['f1'], 3), rounded(values['auc_one_vs_rest'], 3)]
                    for label, values in raw['per_class'].items()], ['Class', 'n', 'Sensitivity (95% CI)', 'Specificity', 'Precision', 'F1', 'AUC']), '',
             '## Confusion matrix (rows: reference, columns: predicted)', '',
             table([[label] + row for label, row in zip(raw['confusion_matrix']['labels'], raw['confusion_matrix']['rows_actual_columns_predicted'])],
                   ['Reference \\ predicted'] + raw['confusion_matrix']['labels']), '',
             '## Calibration and the "inconclusive" decision', '',
             table([['Temperature (fitted on calibration split)', metrics['calibration']['temperature']],
                    ['ECE before / after (test, 15 bins)', f"{rounded(raw['expected_calibration_error_15_bins'], 3)} / {rounded(metrics['test_metrics_calibrated']['expected_calibration_error_15_bins'], 3)}"],
                    ['NLL before / after (test)', f"{rounded(raw['negative_log_likelihood'], 3)} / {rounded(metrics['test_metrics_calibrated']['negative_log_likelihood'], 3)}"],
                    ['Decision threshold (calibrated top-class probability)', metrics['selective']['decision_threshold']],
                    ['Test images answered / inconclusive', f"{percent(metrics['selective']['answered_fraction'])} / {percent(metrics['selective']['inconclusive_fraction'])}"],
                    ['Accuracy when answered / when inconclusive', f"{percent(metrics['selective']['accuracy_when_answered'])} / {percent(metrics['selective']['accuracy_when_inconclusive'])}"]],
                   ['Item', 'Value']), '',
             '## Input checks and familiarity', '',
             table([['In-area test images rejected by input checks', f"{metrics['input_checks']['test_rejected']} of {metrics['splits']['test_images']}"],
                    ['In-area test images limited by input checks', f"{metrics['input_checks']['test_limited']} of {metrics['splits']['test_images']}"],
                    ['In-area test images flagged unfamiliar', percent(metrics['familiarity']['test_flagged_unfamiliar'])],
                    ['Other-area images rejected or flagged', f"{metrics['wrong_input']['caught']} of {metrics['wrong_input']['images']} ({percent(metrics['wrong_input']['caught_fraction'])})"],
                    ['Other-area images that would get a finding', f"{metrics['wrong_input']['would_report_finding']} of {metrics['wrong_input']['images']}"]],
                   ['Check', 'Result']), '']
    if metrics['wrong_input']['by_source']:
        lines += [table([[source, values['images'], values['rejected_by_checks'], values['flagged_unfamiliar'], values['would_report_finding']]
                         for source, values in metrics['wrong_input']['by_source'].items()],
                        ['Other-area source', 'Images', 'Rejected by checks', 'Flagged unfamiliar', 'Would get a finding']), '']
    lines += ['Charts: ' + ', '.join(f'[{name}]({name})' for name in metrics['charts']) if metrics['charts'] else 'Charts: not generated.', '',
              '> Research evaluation of a single-image classifier. It is not clinical validation and does not establish safety for diagnosis.', '']
    return '\n'.join(lines)


def evaluate(modality, models_root, output_root, write_calibration, calibration_path, limit):
    manifest, runner = load_bundle(models_root / modality, modality)
    labels = list(manifest.labels)
    items, description = cohort(modality)
    unknown = {item.label for item in items} - set(labels)
    if unknown:
        raise ValueError(f'Dataset labels {sorted(unknown)} are not model labels.')
    if limit:
        rng = random.Random(SEED)
        items = rng.sample([item for item in items if item.split == 'calibration'], min(limit, sum(item.split == 'calibration' for item in items))) + \
            rng.sample([item for item in items if item.split == 'test'], min(limit, sum(item.split == 'test' for item in items)))
    print(f'\n== {modality}: {manifest.model_version} | {len(items)} images', flush=True)
    rows = infer_all(manifest, runner, items, modality, 'cohort')
    failed = [row for row in rows if 'error' in row]
    rows = [row for row in rows if 'error' not in row]
    parts = {split: [row for row in rows if row['item'].split == split] for split in ('calibration', 'test')}
    logits = {split: np.array([row['logits'] for row in part]) for split, part in parts.items()}
    targets = {split: np.array([labels.index(row['item'].label) for row in part]) for split, part in parts.items()}

    temperature = fit_temperature(logits['calibration'], targets['calibration'])
    calibrated = {split: softmax(values, temperature) for split, values in logits.items()}
    threshold = choose_threshold(calibrated['calibration'], targets['calibration'])
    raw_test = softmax(logits['test'])
    report_raw = classification_report(raw_test, targets['test'], labels, POSITIVE[modality])
    report_calibrated = classification_report(calibrated['test'], targets['test'], labels, POSITIVE[modality])

    familiarity, reference_entry, wrong = {'available': False, 'test_flagged_unfamiliar': None}, None, {'images': 0, 'caught': 0, 'caught_fraction': None, 'would_report_finding': 0, 'by_source': {}}
    if runner.explainer is not None:
        centroids, minimum = familiarity_reference([row['embedding'] for row in parts['calibration']], targets['calibration'], labels)
        test_similarity = np.array([similarity(row['embedding'], centroids) for row in parts['test']])
        familiarity = {'available': True, 'method': 'class-centroid-cosine', 'minimum_similarity': minimum,
                       'test_flagged_unfamiliar': rounded((test_similarity < minimum).mean())}
        reference_entry = FamiliarityReference(method='class-centroid-cosine', centroids=[[round(float(v), 6) for v in row] for row in centroids],
                                               minimum_similarity=minimum, reference=f'{modality} calibration split; 2nd percentile of in-area similarity')
        others = other_area_images(modality)
        for source, key, load in others:
            stats = wrong['by_source'].setdefault(source, {'images': 0, 'rejected_by_checks': 0, 'flagged_unfamiliar': 0, 'would_report_finding': 0})
            stats['images'] += 1; wrong['images'] += 1
            try:
                logits_other, embedding, checks = run_model(manifest, runner, load(), modality)
            except Exception:
                continue
            limiting = any(check.severity == 'limiting' for check in checks.findings)
            unfamiliar = similarity(embedding, centroids) < minimum
            confident = softmax(logits_other, temperature).max() >= threshold
            if checks.decision == 'rejected':
                stats['rejected_by_checks'] += 1
            elif unfamiliar:
                stats['flagged_unfamiliar'] += 1
            if checks.decision == 'rejected' or unfamiliar or limiting or not confident:
                wrong['caught'] += 1
            else:
                stats['would_report_finding'] += 1; wrong['would_report_finding'] += 1
        wrong['caught_fraction'] = rounded(wrong['caught'] / wrong['images']) if wrong['images'] else None

    metrics = {
        'schema_version': 'humantwin-cancer-evaluation-v1', 'generated': time.strftime('%Y-%m-%d'), 'modality': modality, 'track': TRACK[modality],
        'model_version': manifest.model_version, 'weights_sha256': manifest.weights_sha256, 'labels': labels, 'data': description,
        'splits': {'calibration_images': len(parts['calibration']), 'test_images': len(parts['test']),
                   'test_groups': len({row['item'].group for row in parts['test']}), 'unreadable_images': len(failed),
                   'test_label_counts': {label: int((targets['test'] == index).sum()) for index, label in enumerate(labels)}},
        'pipeline': 'browser-style JPEG preparation -> app.cancer.decode_image -> app.cancer_quality.check_image -> app.cancer.prepare_input -> installed ONNX model',
        'test_metrics_uncalibrated': report_raw, 'test_metrics_calibrated': report_calibrated,
        'calibration': {'method': 'temperature scaling (NLL on calibration split)', 'temperature': round(temperature, 4)},
        'selective': selective(calibrated['test'], targets['test'], threshold),
        'input_checks': {'test_rejected': sum(row['decision'] == 'rejected' for row in parts['test']),
                         'test_limited': sum(bool(row['limiting']) for row in parts['test'])},
        'familiarity': familiarity, 'wrong_input': wrong,
    }
    directory = output_root / modality
    directory.mkdir(parents=True, exist_ok=True)
    metrics['charts'] = charts(directory, labels, report_raw, raw_test, targets['test'], calibrated['test'], POSITIVE[modality])
    (directory / 'metrics.json').write_text(json.dumps(metrics, indent=1) + '\n', encoding='utf-8')
    (directory / 'metrics.md').write_text(markdown(metrics), encoding='utf-8')
    with open(directory / 'per_class.csv', 'w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['class', 'support', 'sensitivity', 'specificity', 'precision', 'f1', 'auc_one_vs_rest'])
        for label, values in report_raw['per_class'].items():
            writer.writerow([label, values['support'], values['sensitivity_recall'], values['specificity'], values['precision'], values['f1'], values['auc_one_vs_rest']])
    with open(directory / 'predictions.csv', 'w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['image', 'split', 'reference', 'predicted', *[f'p_{label}' for label in labels], 'input_check'])
        for split in ('calibration', 'test'):
            for row, probabilities in zip(parts[split], calibrated[split]):
                writer.writerow([row['item'].key, split, row['item'].label, labels[int(probabilities.argmax())],
                                 *[f'{value:.5f}' for value in probabilities], row['decision']])
    if write_calibration:
        write_entry(calibration_path, manifest.weights_sha256, CalibrationEntry(
            model_version=manifest.model_version, labels=labels, temperature=round(temperature, 4), decision_threshold=threshold,
            fitted_on=f"{description.split(':')[0]}; calibration split, {len(parts['calibration'])} images", familiarity=reference_entry))
        print('  calibration written to', calibration_path)
    print(f"  accuracy {report_raw['accuracy']} | cancer sensitivity {report_raw['cancer_vs_not']['sensitivity']} | specificity {report_raw['cancer_vs_not']['specificity']} "
          f"| AUC {report_raw['cancer_vs_not']['auc']} | T={temperature:.3f} | threshold {threshold} | wrong-input caught {wrong['caught']}/{wrong['images']}")
    return metrics


# ----------------------------------------------------------------------------- model cards

CARD_FACTS = {
    'dermoscopy': {
        'title': 'Skin: dermoscopy lesion classifier',
        'architecture': 'Vision Transformer (ViT-Base/16), fine-tuned; installed as an 8-bit dynamically quantised ONNX export.',
        'source': 'ONNX export sazio/skin-mole-vit-onnx (revision 25be9e61) of Anwarkh1/Skin_Cancer-Image_Classification (Hugging Face).',
        'licence': 'MIT for the ONNX repository; HAM10000 images are CC BY-NC 4.0 (non-commercial).',
        'training': 'HAM10000 (10,015 dermoscopic images, 7 diagnostic categories, mostly from Austria and Australia). The exact training split was not published.',
        'input': 'One dermoscopy image of a single skin lesion (not an ordinary phone photograph).',
        'preprocessing': 'RGB; exact resize to 224 x 224 with antialiased bilinear interpolation (PIL); scale 1/255; normalise with mean 0.5 and std 0.5 per channel.',
        'explanation': 'Attention rollout over the 12 encoder layers (14 x 14 patch grid); not class-specific.',
        'limitations': ['Trained on a dataset dominated by moles (about two thirds of images) and by lighter skin types; performance on darker skin is unknown.',
                        'Several images per lesion exist in HAM10000; image-level evaluation can be optimistic.',
                        'The quantised export may differ slightly from the published full-precision model.',
                        'Measured on ISIC 2018 test images it confuses benign keratoses and basal cell carcinoma with melanoma (see the confusion matrix).',
                        'Not trained on phone photographs; such images are often rejected or flagged as unfamiliar.'],
    },
    'oral_photo': {
        'title': 'Oral: mouth lesion photograph classifier',
        'architecture': 'ResNet-18 (ImageNet initialisation), trained by this project with scripts/train-oral-cancer.py (seed 42, selected epoch 5 by validation balanced accuracy).',
        'source': 'Trained locally; training report in ai-service/models/cancer/oral_photo/report.json.',
        'licence': 'Model trained by the project; images from the Mendeley Oral Images Dataset v2 (Chandrashekar et al., CC BY 4.0).',
        'training': '323 original photographs (165 benign, 158 malignant lesions), split by near-duplicate image group into 226 train / 49 validation / 48 test images. Augmented copies in the archive were not used.',
        'input': 'One close-up colour photograph of a visible lesion inside the mouth.',
        'preprocessing': 'RGB; exact resize to 224 x 224 with antialiased bilinear interpolation (torchvision on PIL images); scale 1/255; ImageNet mean and std.',
        'explanation': 'Grad-CAM on the last convolutional block (7 x 7 grid); class-specific. For this global-average-pool + linear head it equals the class activation map.',
        'limitations': ['There is no "normal mouth" class: every image is treated as showing a lesion.',
                        'No patient identifiers exist, so splits are by image group, not by patient.',
                        'The 48-image test set gives wide confidence intervals and was inspected during earlier development.',
                        'All photographs come from one published collection; other cameras, lighting and populations are untested.'],
    },
    'lung_ct_slice': {
        'title': 'Lung: single CT slice classifier',
        'architecture': 'EfficientNet-B0 (ImageNet initialisation), fine-tuned by the upstream author; exported to ONNX locally with numerical parity checks.',
        'source': 'yunussgultekiin/lung-cancer-efficientnet-b0 (revision 506c398b), Hugging Face.',
        'licence': 'Repository MIT (model card states Apache-2.0); LungCancer4Types data Apache-2.0.',
        'training': 'LungCancer4Types (Kabil007): 824 unique 2D CT slice images after de-duplication; the author trained on a 659-image development pool and held out 165 images.',
        'input': 'One chest CT slice exported as an 8-bit JPEG or PNG (not DICOM, not a full scan).',
        'preprocessing': 'RGB (grayscale replicated); exact resize to 224 x 224 with antialiased bilinear interpolation (torchvision on PIL images); scale 1/255; ImageNet mean and std.',
        'explanation': 'Grad-CAM on the final feature map (7 x 7 grid); class-specific, equal to the class activation map for this head.',
        'limitations': ['A single slice cannot represent a CT examination; lung cancer cannot be ruled out from one image.',
                        'The public dataset is small, of unknown scanner and patient provenance, and only 49 "normal" images are unique.',
                        'Class folders carry stage information from one source; the model may learn dataset artefacts rather than anatomy.',
                        'Very high held-out accuracy on 98 test images should be read with its confidence interval and dataset limits in mind.'],
    },
    'breast_ultrasound': {
        'title': 'Breast: ultrasound image classifier',
        'architecture': 'Vision Transformer (ViT-Base/16), fine-tuned by the upstream author; exported to ONNX locally with numerical parity checks.',
        'source': 'hugging-science/breast-cancer-detector-2 (revision 257147b3), Hugging Face.',
        'licence': 'Apache-2.0 (model card); BUSI dataset CC BY 4.0 (Al-Dhabyani et al. 2020).',
        'training': 'BUSI breast ultrasound images (Egypt; benign, malignant and normal), with 20% label noise deliberately added by the author.',
        'input': 'One breast ultrasound image (not a mammogram or MRI).',
        'preprocessing': 'RGB (grayscale replicated); exact resize to 224 x 224 with antialiased bilinear interpolation (PIL); scale 1/255; normalise with mean 0.5 and std 0.5.',
        'explanation': 'Attention rollout over the 12 encoder layers (14 x 14 patch grid); not class-specific.',
        'limitations': ['On the external BUS-BRA dataset (Brazil, different devices) it misses more than half of the cancers: this is a domain shift that the in-domain benchmark hides.',
                        'The "normal" class could not be evaluated externally because BUS-BRA contains only biopsied lesions.',
                        'Grayscale CT slices are not always recognised as the wrong image type.',
                        'Not suitable for screening or for deciding whether a lump needs a biopsy.'],
    },
}


def model_card(metrics):
    facts = CARD_FACTS[metrics['modality']]
    raw, binary = metrics['test_metrics_uncalibrated'], metrics['test_metrics_uncalibrated']['cancer_vs_not']
    lines = [f"# Model card: {facts['title']}", '', f"*Model version `{metrics['model_version']}` · weights SHA-256 `{metrics['weights_sha256'][:16]}…` · "
             f"evaluated {metrics['generated']} with `ai-service/scripts/evaluate-cancer-models.py`.*", '',
             '## Intended use', '',
             'Education and research demonstration inside the HumanTwin workspace: showing how an image classifier responds to one prepared image, '
             'with its confidence, an explanation map and its limits. **Not intended** for diagnosis, screening, triage or treatment decisions, '
             'and not a substitute for examination by a clinician.', '',
             '## Model', '', f"- **Architecture:** {facts['architecture']}", f"- **Source:** {facts['source']}", f"- **Licence:** {facts['licence']}",
             f"- **Classes (output order):** {', '.join(metrics['labels'])}", f"- **Classes counted as cancer in the binary view:** {', '.join(binary['positive_classes'])}", '',
             '## Data', '', f"- **Training data:** {facts['training']}", f"- **Evaluation data:** {metrics['data']}",
             f"- **Test split:** {metrics['splits']['test_images']} images ({', '.join(f'{label}: {count}' for label, count in metrics['splits']['test_label_counts'].items())}).", '',
             '## Input and preprocessing', '', f"- **Accepted input:** {facts['input']}", f"- **Preprocessing:** {facts['preprocessing']}",
             '- **Parity:** the service tensor matches the model\'s own reference pipeline within 1e-5 (`ai-service/tests/test_cancer_preprocessing.py`).',
             f"- **Explanation:** {facts['explanation']}", '',
             '## Measured performance (held-out test split)', '',
             table([['Accuracy', percent(raw['accuracy']) + interval(raw['accuracy_95ci'])], ['Balanced accuracy', percent(raw['balanced_accuracy'])],
                    ['Macro F1', rounded(raw['macro_f1'], 3)], ['Sensitivity (cancer vs not)', percent(binary['sensitivity']) + interval(binary['sensitivity_95ci'])],
                    ['Specificity (cancer vs not)', percent(binary['specificity']) + interval(binary['specificity_95ci'])],
                    ['AUC (cancer vs not)', rounded(binary['auc'], 3)], ['F1 (cancer vs not)', rounded(binary['f1'], 3)]], ['Metric', 'Value (95% CI)']), '',
             f"Full tables, the confusion matrix and charts: [`research/cancer-evaluation/{metrics['modality']}/metrics.md`](../cancer-evaluation/{metrics['modality']}/metrics.md).", '',
             '## Confidence, "inconclusive" and input checks', '',
             f"- Temperature scaling fitted on {metrics['splits']['calibration_images']} calibration images: T = {metrics['calibration']['temperature']}; "
             f"expected calibration error on the test split {rounded(raw['expected_calibration_error_15_bins'], 3)} before and "
             f"{rounded(metrics['test_metrics_calibrated']['expected_calibration_error_15_bins'], 3)} after.",
             f"- A finding is shown only when the calibrated top-class probability is at least {metrics['selective']['decision_threshold']}; otherwise the result is "
             f"inconclusive ({percent(metrics['selective']['inconclusive_fraction'])} of test images; accuracy {percent(metrics['selective']['accuracy_when_answered'])} when answered).",
             f"- Wrong-area and synthetic images: {metrics['wrong_input']['caught']} of {metrics['wrong_input']['images']} were rejected by the input checks or "
             f"reported as inconclusive; {metrics['wrong_input']['would_report_finding']} would still receive a finding.", '',
             '## Known limitations', '', *[f'- {item}' for item in facts['limitations']],
             '- Confidence is a property of the model, not a personal probability of cancer. Results are research output and have no clinical validation.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--models', nargs='+', default=['oral_photo', 'lung_ct_slice', 'breast_ultrasound', 'dermoscopy'])
    parser.add_argument('--models-root', default='models/cancer')
    parser.add_argument('--output', default='../research/cancer-evaluation')
    parser.add_argument('--calibration-path', default='calibration/cancer-calibration.json')
    parser.add_argument('--write-calibration', action='store_true', help='store the fitted temperature, threshold and familiarity reference')
    parser.add_argument('--download', action='store_true', help='download the public evaluation sets and exit')
    parser.add_argument('--limit', type=int, default=0, help='evaluate at most N images per split (quick check)')
    parser.add_argument('--cards-only', action='store_true', help='regenerate model cards from existing metrics.json files')
    args = parser.parse_args()
    if args.download:
        download()
        return
    output = (ROOT / args.output).resolve()
    cards = (ROOT / '../research/model-cards').resolve()
    if args.cards_only:
        cards.mkdir(parents=True, exist_ok=True)
        for modality in args.models:
            source = output / modality / 'metrics.json'
            if source.is_file():
                (cards / f'{modality}.md').write_text(model_card(json.loads(source.read_text(encoding='utf-8'))), encoding='utf-8')
                print('model card written:', cards / f'{modality}.md')
        return
    results = {}
    for modality in args.models:
        try:
            results[modality] = evaluate(modality, ROOT / args.models_root, output, args.write_calibration, ROOT / args.calibration_path, args.limit)
            if not args.limit:
                cards.mkdir(parents=True, exist_ok=True)
                (cards / f'{modality}.md').write_text(model_card(results[modality]), encoding='utf-8')
        except FileNotFoundError as error:
            print(f'\n== {modality}: data not found ({error}). Run with --download first.')
    if results and not args.limit:
        rows = [[m['model_version'], m['splits']['test_images'], percent(m['test_metrics_uncalibrated']['accuracy']),
                 percent(m['test_metrics_uncalibrated']['balanced_accuracy']), rounded(m['test_metrics_uncalibrated']['macro_f1'], 3),
                 percent(m['test_metrics_uncalibrated']['cancer_vs_not']['sensitivity']), percent(m['test_metrics_uncalibrated']['cancer_vs_not']['specificity']),
                 rounded(m['test_metrics_uncalibrated']['cancer_vs_not']['auc'], 3), m['calibration']['temperature'],
                 percent(m['selective']['inconclusive_fraction'])] for m in results.values()]
        previous = (output / 'summary.json')
        stored = json.loads(previous.read_text()) if previous.is_file() else {}
        stored.update({modality: {'model_version': m['model_version'], 'row': row} for (modality, m), row in zip(results.items(), rows)})
        previous.write_text(json.dumps(stored, indent=1) + '\n', encoding='utf-8')
        (output / 'summary.md').write_text('\n'.join([
            '# Cancer image models: held-out evaluation summary', '',
            table([value['row'] for value in stored.values()], ['Model', 'Test images', 'Accuracy', 'Balanced acc.', 'Macro F1',
                                                                 'Cancer sensitivity', 'Cancer specificity', 'Cancer AUC', 'Temperature', 'Inconclusive']), '',
            'Per-model details, confusion matrices and charts are in each model folder. See research/CANCER_EVALUATION.md for the method.', '']),
            encoding='utf-8')
        print('\nSummary written to', output / 'summary.md')


if __name__ == '__main__':
    main()
