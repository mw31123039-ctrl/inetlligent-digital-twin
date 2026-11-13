"""Train one bounded oral-model experiment; compare, export and optionally promote.

Only the pinned licensed public originals are read. Existing user uploads, accounts
and private images are never training sources. The reused historical test split can
veto activation and is explicitly development evidence, not a new blind test.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import random
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms

from app.cancer import ModelManifest
from app.cancer_release import review_upgrade
from app.cancer_training import audit_partitions, binary_metrics, partition_fingerprint, promotion_reasons

spec = importlib.util.spec_from_file_location('oral_source_training', Path(__file__).with_name('train-oral-cancer.py'))
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)

BASE_URL = 'https://download.pytorch.org/models/efficientnet_b0_rwightman-7f5810bc.pth'
BASE_HASH = '7f5810bc96def8f7552d5b7e68d53c4786f81167d28291b21c0d90e1fca14934'
# Public original identities, labels, duplicate groups and original seed-42 splits.
# Absolute local paths are excluded so the same source split is portable.
FIXED_SPLIT_SHA256 = '28995dd0fb4b369c1351f11c124a0a07e90a797656d50ea8c1c19b9caf9491a7'


class CachedPublicImages(Dataset):
    def __init__(self, records, split, originals_root):
        self.records = [item for item in records if item['split'] == split]
        self.images = []
        for item in self.records:
            path = Path(item['path']).resolve()
            if not path.is_relative_to(originals_root.resolve()) or source.digest(path) != item['raw_sha256']:
                raise ValueError('Training accepts only fingerprinted public original images.')
            self.images.append(source.rgb_image(path).resize((224, 224), Image.Resampling.BILINEAR))
        operations = []
        if split == 'train':
            operations += [transforms.RandomHorizontalFlip(), transforms.RandomRotation(10),
                           transforms.ColorJitter(brightness=.1, contrast=.1, saturation=.1)]
        self.transform = transforms.Compose(operations + [transforms.ToTensor(), transforms.Normalize(source.MEAN, source.STD)])

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        return self.transform(self.images[index]), self.records[index]['label']


def probabilities(model, loader, device):
    values, labels = [], []
    model.eval()
    with torch.inference_mode():
        for pixels, targets in loader:
            values.append(model(pixels.to(device)).softmax(1).cpu().numpy())
            labels.extend(targets.tolist())
    return np.array(labels), np.concatenate(values)


def baseline_probabilities(directory, loader):
    import onnxruntime as ort
    manifest = ModelManifest.model_validate_json((directory / 'manifest.json').read_text())
    if manifest.labels != source.LABELS or manifest.interpolation != 'pil-bilinear' or manifest.input_size != (224, 224) or manifest.mean != source.MEAN or manifest.std != source.STD or manifest.scale != 1 / 255 or manifest.color != 'RGB' or manifest.output != 'logits':
        raise ValueError('The installed oral baseline has an unsupported comparison contract.')
    if source.digest(directory / 'model.onnx') != manifest.weights_sha256:
        raise ValueError('The installed baseline fingerprint is invalid.')
    options = ort.SessionOptions(); options.intra_op_num_threads = 4; options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(directory / 'model.onnx'), sess_options=options, providers=['CPUExecutionProvider'])
    values, labels = [], []
    for pixels, targets in loader:
        logits = session.run(None, {'pixel_values': pixels.numpy()})[0].astype(np.float64)
        scores = np.exp(logits - logits.max(1, keepdims=True)); scores /= scores.sum(1, keepdims=True)
        values.append(scores); labels.extend(targets.tolist())
    return np.array(labels), np.concatenate(values)


class ProbabilityMean(nn.Module):
    def __init__(self, efficientnet, resnet=None):
        super().__init__()
        self.efficientnet, self.resnet = efficientnet, resnet

    def forward(self, pixel_values):
        scores = self.efficientnet(pixel_values).softmax(1)
        if self.resnet is not None:
            scores = (scores + self.resnet(pixel_values).softmax(1)) / 2
        return scores


def export_candidate(efficientnet, baseline, kind, validation_loader, output, old_manifest, run_id):
    import onnx
    import onnxruntime as ort
    resnet = None
    if kind == 'equal-probability-ensemble':
        resnet = models.resnet18(weights=None)
        resnet.fc = nn.Linear(resnet.fc.in_features, 2)
        state_path = baseline / 'best-state.pt'
        resnet.load_state_dict(torch.load(state_path, map_location='cpu', weights_only=True))
        # Confirm checkpoint is really the installed baseline, not an unrelated state file.
        labels, expected = baseline_probabilities(baseline, validation_loader)
        _, actual = probabilities(resnet, validation_loader, torch.device('cpu'))
        if not np.allclose(expected, actual, atol=1e-5, rtol=1e-4):
            raise ValueError('The baseline state does not reproduce the installed ONNX model.')
    model = ProbabilityMean(efficientnet.to('cpu').eval(), resnet).eval()
    output.mkdir(parents=True, exist_ok=False)
    temporary = output / 'model.onnx'
    torch.onnx.export(model, torch.zeros(1, 3, 224, 224), temporary, input_names=['pixel_values'], output_names=['probabilities'],
                      dynamic_axes={'pixel_values': {0: 'batch'}, 'probabilities': {0: 'batch'}},
                      opset_version=17, do_constant_folding=True, dynamo=False)
    onnx.checker.check_model(onnx.load(temporary))
    options = ort.SessionOptions(); options.intra_op_num_threads = 4; options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(temporary), sess_options=options, providers=['CPUExecutionProvider'])
    maximum_error = 0.0
    checked = 0
    with torch.inference_mode():
        for pixels, _ in validation_loader:
            expected = model(pixels).numpy()
            actual = session.run(None, {'pixel_values': pixels.numpy()})[0]
            if not np.allclose(expected, actual, atol=1e-5, rtol=1e-4):
                raise ValueError('Export changed the selected model outputs.')
            maximum_error = max(maximum_error, float(np.abs(expected - actual).max()))
            checked += len(pixels)
    manifest = copy.deepcopy(old_manifest)
    manifest.update(model_version='oral-' + ('ensemble' if kind == 'equal-probability-ensemble' else 'efficientnet') + '-' + run_id,
                    weights_sha256=source.digest(temporary), output='probabilities')
    manifest['evaluation']['reference'] = 'Local report.json: reused image-group development splits; not independent patient validation.'
    ModelManifest.model_validate(manifest)
    source.write_json(output / 'manifest.json', manifest)
    (output / 'ATTRIBUTION.txt').write_text(source.ATTRIBUTION + '\n', encoding='utf-8')
    if (baseline / 'examples').exists():
        shutil.copytree(baseline / 'examples', output / 'examples')
    torch.save({'efficientnet': efficientnet.state_dict(), 'resnet': resnet.state_dict() if resnet is not None else None}, output / 'research-state.pt')
    return {'weights_sha256': manifest['weights_sha256'], 'validation_images_checked': checked,
            'maximum_absolute_probability_difference': maximum_error, 'dynamic_batch_verified': True}


def run(args):
    started = time.perf_counter()
    data = ROOT / 'training-data/cancer-oral'
    baseline = ROOT / 'models/cancer/oral_photo'
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = ROOT / 'models/cancer-experiments' / run_id
    output.mkdir(parents=True, exist_ok=False)
    manifest_path = data / 'split-manifest.json'
    raw_manifest = manifest_path.read_bytes()
    records = json.loads(raw_manifest)
    audit = audit_partitions(records)
    if partition_fingerprint(records) != FIXED_SPLIT_SHA256:
        raise ValueError('The original public source identities, labels or fixed splits have changed.')
    if audit['counts'] != {'train': [115, 111], 'validation': [25, 24], 'test': [25, 23]}:
        raise ValueError('This experiment requires the original fixed 226/49/48 image split.')
    old_manifest = json.loads((baseline / 'manifest.json').read_text())
    # Pre-register the bounded search and activation rules before reading any test pixels.
    protocol = {'run_id': run_id, 'created_at': datetime.now(timezone.utc).isoformat(),
                'clinical_validation': False, 'split_manifest_sha256': hashlib.sha256(raw_manifest).hexdigest(),
                'normalized_public_split_sha256': FIXED_SPLIT_SHA256,
                'source_archive_sha256': source.ARCHIVE_SHA256, 'baseline_weights_sha256': old_manifest['weights_sha256'],
                'seed': args.seed, 'maximum_epochs': args.epochs, 'patience': 7,
                'candidates': ['efficientnet-b0-finetuned', 'equal-probability-ensemble'],
                'selection': 'Validation only: strictly higher balanced accuracy and no lower sensitivity or specificity than baseline. NLL breaks ties.',
                'activation_veto': 'The one validation-selected candidate must not regress on the reused 48-image historical audit. This makes that split development evidence, not a new blind test.',
                'new_independent_test_available': False, 'patient_disjoint': None,
                'training_sources': 'Pinned CC-BY-4.0 original public photographs only; no account or uploaded images.',
                'architecture_reference': 'https://docs.pytorch.org/vision/0.22/models/generated/torchvision.models.efficientnet_b0.html',
                'augmentation': ['horizontal flip', 'rotation +-10 degrees', 'brightness/contrast/saturation jitter +-0.1'],
                'preprocessing': 'RGB -> PIL bilinear stretch224 -> ImageNet mean/std. Training and inference deliberately share the same full-image resize; no central lesion crop.'}
    source.write_json(output / 'protocol.json', protocol)
    source.write_json(output / 'progress.json', {'stage': 'preparing', 'clinical_validation': False})
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    torch.set_num_threads(4)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark = False; torch.backends.cudnn.deterministic = True
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print('Experiment:', run_id, 'device:', device, flush=True)
    datasets = {split: CachedPublicImages(records, split, data / 'originals') for split in ('train', 'validation')}
    generator = torch.Generator().manual_seed(args.seed)
    loaders = {split: DataLoader(dataset, batch_size=16, shuffle=split == 'train', num_workers=0,
                                 generator=generator if split == 'train' else None) for split, dataset in datasets.items()}
    targets, baseline_scores = baseline_probabilities(baseline, loaders['validation'])
    baseline_validation = binary_metrics(targets, baseline_scores)
    checkpoint = data / Path(BASE_URL).name
    if models.EfficientNet_B0_Weights.IMAGENET1K_V1.url != BASE_URL:
        raise ValueError('Unexpected pretrained source.')
    source.download(BASE_URL, checkpoint, BASE_HASH)
    model = models.efficientnet_b0(weights=None)
    model.load_state_dict(torch.load(checkpoint, map_location='cpu', weights_only=True))
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, 2)
    model.to(device)
    weights = torch.tensor([226 / (2 * count) for count in audit['counts']['train']], device=device)
    criterion = nn.CrossEntropyLoss(weight=weights)
    trace, best_key, best_epoch, best_state, best_kind = [], (-1., -math.inf), 0, None, None
    fallback_key, fallback_state, fallback_epoch = (-1., -math.inf), None, 0
    optimizer = None
    for epoch in range(1, args.epochs + 1):
        if epoch in (1, 4):
            for parameter in model.parameters():
                parameter.requires_grad = False
            for parameter in model.classifier.parameters():
                parameter.requires_grad = True
            groups = [{'params': model.classifier.parameters(), 'lr': 5e-4 if epoch == 1 else 3e-4}]
            if epoch == 4:
                for parameter in model.features[4:].parameters():
                    parameter.requires_grad = True
                groups.append({'params': model.features[4:].parameters(), 'lr': 3e-5})
            optimizer = torch.optim.AdamW(groups, weight_decay=1e-4)
        model.train()
        for module in model.modules():
            if isinstance(module, nn.BatchNorm2d):
                module.eval()
        epoch_loss, seen = 0., 0
        for pixels, labels in loaders['train']:
            pixels, labels = pixels.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(pixels), labels)
            if not torch.isfinite(loss):
                raise ValueError('Non-finite training loss; no candidate will be activated.')
            loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 5.); optimizer.step()
            epoch_loss += float(loss.detach()) * len(labels); seen += len(labels)
        labels, scores = probabilities(model, loaders['validation'], device)
        candidate_scores = {'efficientnet-b0-finetuned': scores, 'equal-probability-ensemble': (scores + baseline_scores) / 2}
        measurements = {}
        for kind, values in candidate_scores.items():
            measured = binary_metrics(labels, values)
            measurements[kind] = measured
            key = measured['balanced_accuracy'], -measured['negative_log_likelihood']
            if key > fallback_key:
                fallback_key, fallback_epoch = key, epoch
                fallback_state = {name: tensor.detach().cpu().clone() for name, tensor in model.state_dict().items()}
            if not promotion_reasons(baseline_validation, measured) and key > best_key:
                best_key, best_epoch, best_kind = key, epoch, kind
                best_state = {name: tensor.detach().cpu().clone() for name, tensor in model.state_dict().items()}
        trace.append({'epoch': epoch, 'train_weighted_cross_entropy': epoch_loss / seen, 'validation': measurements})
        source.write_json(output / 'training-trace.json', trace)
        source.write_json(output / 'progress.json', {'stage': 'training', 'epoch': epoch, 'maximum_epochs': args.epochs,
                          'best_eligible_epoch': best_epoch or None, 'clinical_validation': False})
        print(f'Epoch {epoch}/{args.epochs}: loss={epoch_loss/seen:.4f}, efficientnet val={measurements["efficientnet-b0-finetuned"]["balanced_accuracy"]:.4f}, ensemble val={measurements["equal-probability-ensemble"]["balanced_accuracy"]:.4f}, eligible best={best_epoch or "none"}', flush=True)
        if epoch >= 11 and epoch - max(best_epoch, fallback_epoch) >= 7:
            break
    report = dict(protocol, training_performed=True, epochs_completed=len(trace), baseline_validation=baseline_validation,
                  initial_weights={'url': BASE_URL, 'sha256': source.digest(checkpoint)},
                  training_device=str(device), gpu_name=torch.cuda.get_device_name(0) if device.type == 'cuda' else None,
                  selected_kind=best_kind, selected_epoch=best_epoch or None, activation_requested=args.activate,
                  activated=False, independent_patient_validation_available=False)
    if best_state is None:
        report['activation_rejection'] = ['Neither candidate improved validation while retaining both class recalls.']
        torch.save(fallback_state, output / 'rejected-research-state.pt')
    else:
        model.load_state_dict(best_state)
        _, learned = probabilities(model, loaders['validation'], device)
        chosen = (learned + baseline_scores) / 2 if best_kind == 'equal-probability-ensemble' else learned
        report['selected_validation'] = binary_metrics(targets, chosen)
        # Freeze candidate identity before opening historical audit images.
        source.write_json(output / 'selection-before-audit.json', {'kind': best_kind, 'epoch': best_epoch,
                          'validation': report['selected_validation'], 'used_test_pixels_for_selection': False})
        test_set = CachedPublicImages(records, 'test', data / 'originals')
        test_loader = DataLoader(test_set, batch_size=16, shuffle=False, num_workers=0)
        test_labels, old_test = baseline_probabilities(baseline, test_loader)
        _, learned_test = probabilities(model, test_loader, device)
        chosen_test = (learned_test + old_test) / 2 if best_kind == 'equal-probability-ensemble' else learned_test
        report['baseline_historical_audit'] = binary_metrics(test_labels, old_test)
        report['selected_historical_audit'] = binary_metrics(test_labels, chosen_test)
        reasons = promotion_reasons(baseline_validation, report['selected_validation'],
                                    report['baseline_historical_audit'], report['selected_historical_audit'])
        report['activation_rejection'] = reasons
        candidate = output / 'candidate'
        report['onnx_export'] = export_candidate(model, baseline, best_kind, loaders['validation'], candidate, old_manifest, run_id)
        source.write_json(candidate / 'report.json', report)
        if args.activate:
            if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != protocol['split_manifest_sha256'] or source.digest(baseline / 'model.onnx') != old_manifest['weights_sha256']:
                raise ValueError('Baseline/split changed during training; refusing activation.')
            cohort = {'schema_version': 'humantwin-cancer-cohort-v1', 'modality': 'oral_photo',
                      'labels': old_manifest['labels'], 'records': records}
            review = review_upgrade(ROOT / 'models', 'oral_photo', candidate, cohort, data / 'originals',
                                     activate=not reasons)
            source.write_json(output / 'release-review.json', review)
            report['activation_rejection'] = sorted(set(reasons + review['reasons']))
            report['activated'] = review['activated']
            if review['activated']:
                report['rollback_directory'] = review['activation']['backup_directory']
                source.write_json(baseline / 'report.json', report)
    report['elapsed_seconds'] = round(time.perf_counter() - started, 2)
    source.write_json(output / 'report.json', report)
    source.write_json(output / 'progress.json', {'stage': 'complete', 'activated': report['activated'], 'clinical_validation': False})
    print(json.dumps({'completed': True, 'activated': report['activated'], 'report': str(output / 'report.json'),
                      'selected_kind': best_kind, 'validation': report.get('selected_validation'),
                      'historical_audit': report.get('selected_historical_audit'), 'rejection': report.get('activation_rejection')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--epochs', type=int, default=24)
    parser.add_argument('--seed', type=int, default=20261113)
    parser.add_argument('--activate', action='store_true', help='Activate only if both predeclared development gates pass; preserve rollback artifacts.')
    args = parser.parse_args()
    if not 11 <= args.epochs <= 30:
        parser.error('Use a bounded experiment of 11 to 30 epochs.')
    run(args)
