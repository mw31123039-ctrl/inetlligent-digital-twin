"""Train an experimental oral-lesion photograph classifier on a pinned public dataset.

Source labels are benign LESIONS versus malignant LESIONS, never normal mouths.
Only original photographs enter the split. Patient identifiers are not supplied;
duplicate-group separation must not be described as independent-patient validation.
No application/account photos or credentials are read by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import time
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import cv2
import numpy as np
import torch
from PIL import Image, ImageOps
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms

SOURCE = 'https://data.mendeley.com/datasets/mhjyrn35p4/2'
SOURCE_DOI = '10.17632/mhjyrn35p4.2'
ARCHIVE_URL = 'https://data.mendeley.com/public-api/zip/mhjyrn35p4/download/2'
ARCHIVE_SHA256 = '23fdb08ae926782a9abd579b7f0e0123b90a3d8b284e043c31a7748f0268b70f'
BASE_URL = 'https://download.pytorch.org/models/resnet18-f37072fd.pth'
# Full fingerprint of the official torchvision checkpoint (URL hash prefix f37072fd).
BASE_SHA256 = 'f37072fd47e89c5e827621c5baffa7500819f7896bbacec160b1a16c560e07ec'
LABELS = ['benign_lesion', 'malignant_lesion']
MEAN, STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
ATTRIBUTION = (
    'Chandrashekar H S, Geetha Kiran A, Murali S, Dinesh M S, Nanditha B R. '
    'Oral Images Dataset, Mendeley Data V2 (2021), doi:10.17632/mhjyrn35p4.2. '
    'Source images licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). '
    'This local derivative uses original photographs only and trains a new supervised '
    'research classifier. Labels/provenance are supplied by the dataset authors and '
    'are not independently reviewed by this application. ImageNet ResNet18 initial '
    'weights are from official torchvision; preserve the relevant source notices.'
)


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            sha.update(chunk)
    return sha.hexdigest()


def write_json(path: Path, value: dict | list):
    temporary = path.with_suffix(path.suffix + '.part')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def download(url: str, destination: Path, expected_sha256: str):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and digest(destination).startswith(expected_sha256):
        return
    print(f'Downloading {destination.name}', flush=True)
    request = urllib.request.Request(url, headers={'User-Agent': 'HumanTwin-Research/1.0'})
    temporary = destination.with_suffix(destination.suffix + '.part')
    with urllib.request.urlopen(request, timeout=90) as source, temporary.open('wb') as output:
        shutil.copyfileobj(source, output, 1024 * 1024)
    actual = digest(temporary)
    if not actual.startswith(expected_sha256):
        raise ValueError(f'Fingerprint mismatch for {destination.name}; refusing the artifact.')
    temporary.replace(destination)
    print(f'Verified {destination.name}: {actual}', flush=True)


def rgb_image(path: Path) -> Image.Image:
    with Image.open(path) as original:
        return ImageOps.exif_transpose(original).convert('RGB')


def perceptual_hash(image: Image.Image) -> int:
    gray = np.asarray(image.convert('L').resize((32, 32), Image.Resampling.BILINEAR), np.float32)
    low = cv2.dct(gray)[:8, :8].reshape(-1)
    threshold = np.median(low[1:])
    bits = low > threshold
    bits[0] = False
    return sum(int(bit) << index for index, bit in enumerate(bits))


def prepare_dataset(archive: Path, destination: Path, seed: int) -> tuple[list[dict], dict]:
    if digest(archive) != ARCHIVE_SHA256:
        raise ValueError('Dataset archive fingerprint mismatch.')
    originals = destination / 'originals'
    originals.mkdir(parents=True, exist_ok=True)
    members, source_counts = [], Counter()
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            parts = PurePosixPath(info.filename.replace('\\', '/')).parts
            if any(part in ('..', '') for part in parts) or PurePosixPath(info.filename).is_absolute():
                raise ValueError('Unsafe archive member path.')
            lowered = [part.lower() for part in parts]
            if not any(part in ('original_data', 'original data', 'originaldata') for part in lowered):
                continue
            if Path(parts[-1]).suffix.lower() not in ('.jpg', '.jpeg', '.png', '.bmp'):
                continue
            if info.file_size > 20 * 1024 * 1024:
                raise ValueError('An original image exceeds the expected resource limit.')
            class_parts = [part for part in lowered[:-1] if 'benign' in part or 'malignant' in part]
            if len(class_parts) != 1:
                raise ValueError(f'Ambiguous source class directory: {info.filename}')
            label = 0 if 'benign' in class_parts[0] else 1
            raw = bundle.read(info)
            raw_sha256 = hashlib.sha256(raw).hexdigest()
            target = originals / LABELS[label] / f'{raw_sha256}{Path(parts[-1]).suffix.lower()}'
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(raw)
            image = rgb_image(target)
            if min(image.size) < 32 or max(image.size) > 20000:
                raise ValueError('Unexpected image dimensions in original data.')
            image_array = np.asarray(image)
            pixel_sha256 = hashlib.sha256(str(image.size).encode() + image_array.tobytes()).hexdigest()
            variants = [image, ImageOps.mirror(image), ImageOps.flip(image), image.rotate(180)]
            hashes = sorted({perceptual_hash(variant) for variant in variants})
            members.append({'source_member': info.filename, 'path': str(target), 'label': label,
                            'raw_sha256': raw_sha256, 'pixel_sha256': pixel_sha256,
                            'phashes': hashes, 'width': image.width, 'height': image.height})
            source_counts[LABELS[label]] += 1
    if dict(source_counts) != {LABELS[0]: 165, LABELS[1]: 158}:
        raise ValueError(f'Expected exactly 165 benign and 158 malignant original photographs, got {dict(source_counts)}.')

    # Connected components preserve exact and near-identical variants together.
    parents = list(range(len(members)))

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left, right):
        a, b = find(left), find(right)
        if a != b:
            parents[max(a, b)] = min(a, b)

    duplicate_pairs = []
    for i, first in enumerate(members):
        for j in range(i):
            second = members[j]
            exact = first['raw_sha256'] == second['raw_sha256'] or first['pixel_sha256'] == second['pixel_sha256']
            distance = min((a ^ b).bit_count() for a in first['phashes'] for b in second['phashes'])
            if exact or distance <= 6:
                union(i, j)
                duplicate_pairs.append({'first': first['source_member'], 'second': second['source_member'],
                                        'kind': 'exact' if exact else 'perceptual', 'phash_distance': distance})
    groups = {}
    for index, item in enumerate(members):
        groups.setdefault(find(index), []).append(item)
    removed_groups = [items for items in groups.values() if len({item['label'] for item in items}) > 1]
    cross_label = {item['source_member'] for items in removed_groups for item in items}
    kept = []
    split_counts = {}
    for label in range(2):
        candidates = [items for items in groups.values() if items[0]['label'] == label and not any(item['source_member'] in cross_label for item in items)]
        random.Random(seed + label).shuffle(candidates)
        if len(candidates) < 10:
            raise ValueError('Not enough distinct image groups for stratified train/validation/test research splits.')
        train_end = round(len(candidates) * .70)
        validation_end = train_end + max(1, round(len(candidates) * .15))
        partitions = {'train': candidates[:train_end], 'validation': candidates[train_end:validation_end], 'test': candidates[validation_end:]}
        for split, subset in partitions.items():
            split_counts.setdefault(split, {})[LABELS[label]] = {'images': sum(len(group) for group in subset), 'duplicate_groups': len(subset)}
            for items in subset:
                group_id = min(item['raw_sha256'] for item in items)
                for item in items:
                    kept.append(item | {'split': split, 'group_id': group_id})
    if len({item['source_member'] for item in kept}) != len(kept):
        raise ValueError('Source records are not unique.')
    for split in ('train', 'validation', 'test'):
        own = {item['group_id'] for item in kept if item['split'] == split}
        others = {item['group_id'] for item in kept if item['split'] != split}
        if own & others:
            raise ValueError('Duplicate groups cross partition boundaries.')
    audit = {'source_original_counts': dict(source_counts), 'original_images': len(members), 'augmented_source_images_used': 0,
             'duplicate_groups': len(groups), 'duplicate_pairs': duplicate_pairs,
             'cross_label_images_excluded': sorted(cross_label), 'cross_label_groups_excluded': len(removed_groups),
             'split_counts': split_counts, 'patient_identifiers_available': False, 'patient_disjoint': None,
             'grouping': 'SHA-256 raw/decoded RGB pixels plus <=6-bit 64-bit pHash distance across flip/180-degree variants; connected components',
             'grouping_limitations': 'Pixel similarity is not a patient identifier. Other crops, visits and visually distinct photographs of one patient may cross splits.',
             'source_filenames_sample': [item['source_member'] for item in members[:12]]}
    write_json(destination / 'split-manifest.json', [{key: value for key, value in item.items() if key != 'phashes'} for item in kept])
    write_json(destination / 'dataset-audit.json', audit)
    print('Original source counts:', dict(source_counts), flush=True)
    print('Duplicate-aware split counts:', json.dumps(split_counts), flush=True)
    print('Patient identities are unavailable; splits are image-group separated only.', flush=True)
    return kept, audit


class OralDataset(Dataset):
    def __init__(self, records: list[dict], split: str, train: bool = False):
        self.records = [item for item in records if item['split'] == split]
        operations = [transforms.Resize((224, 224), interpolation=transforms.InterpolationMode.BILINEAR)]
        if train:
            operations += [transforms.RandomHorizontalFlip(), transforms.RandomRotation(10),
                           transforms.ColorJitter(brightness=.1, contrast=.1, saturation=.1)]
        self.transform = transforms.Compose(operations + [transforms.ToTensor(), transforms.Normalize(MEAN, STD)])

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        item = self.records[index]
        return self.transform(rgb_image(Path(item['path']))), item['label']


def metrics(confusion: np.ndarray) -> dict:
    total = int(confusion.sum())
    recall = [float(confusion[i, i] / confusion[i].sum()) if confusion[i].sum() else 0.0 for i in range(2)]
    precision = [float(confusion[i, i] / confusion[:, i].sum()) if confusion[:, i].sum() else 0.0 for i in range(2)]
    f1 = [2 * p * r / (p + r) if p + r else 0.0 for p, r in zip(precision, recall)]
    return {'unit': 'images', 'images': total, 'confusion_matrix_rows_actual_columns_predicted': confusion.tolist(),
            'accuracy': float(np.trace(confusion) / total), 'balanced_accuracy': sum(recall) / 2,
            'macro_f1': sum(f1) / 2, 'malignant_image_sensitivity': recall[1], 'benign_image_specificity': recall[0],
            'per_class': {label: {'support_images': int(confusion[i].sum()), 'precision': precision[i], 'recall': recall[i], 'f1': f1[i]} for i, label in enumerate(LABELS)}}


def save_verification_examples(records: list[dict], output: Path) -> list[dict]:
    directory = output / 'examples'
    directory.mkdir(parents=True, exist_ok=True)
    examples = []
    for label in range(2):
        item = next(record for record in records if record['split'] == 'test' and record['label'] == label)
        filename = LABELS[label] + '.png'
        target = directory / filename
        rgb_image(Path(item['path'])).resize((224, 224), Image.Resampling.BILINEAR).save(target, format='PNG')
        examples.append({'filename': filename, 'path': str(target), 'source_url': SOURCE, 'doi': SOURCE_DOI,
                         'license': 'CC-BY-4.0', 'source_member': item['source_member'],
                         'source_sha256': item['raw_sha256'], 'prepared_image_sha256': digest(target),
                         'source_label': LABELS[label], 'split': 'test',
                         'selection': 'First fixed held-out example of this source class; no selection by prediction.',
                         'preparation': 'EXIF orientation -> RGB -> PIL bilinear stretch224 -> lossless PNG. Browser may re-encode JPEG.'})
    write_json(directory / 'source-manifest.json', {'attribution': ATTRIBUTION, 'examples': examples})
    return examples


def evaluate(model, loader, device, criterion):
    model.eval()
    confusion = np.zeros((2, 2), np.int64)
    loss, total = 0.0, 0
    with torch.inference_mode():
        for pixels, targets in loader:
            pixels, targets = pixels.to(device), targets.to(device)
            logits = model(pixels)
            loss += float(criterion(logits, targets)) * len(targets)
            total += len(targets)
            predictions = logits.argmax(1).cpu().tolist()
            for expected, predicted in zip(targets.cpu().tolist(), predictions):
                confusion[expected, predicted] += 1
    return metrics(confusion) | {'weighted_cross_entropy': loss / total}


def train(args):
    root = Path(__file__).resolve().parents[1]
    data = (root / args.data_dir).resolve()
    output = (root / args.model_dir).resolve()
    data.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    started = time.time()
    print('Preparing public oral-lesion research training.', flush=True)
    write_json(output / 'progress.json', {'stage': 'preparing', 'clinical_validation': False})
    archive = data / 'mhjyrn35p4-2.zip'
    if not archive.exists() and not args.download:
        raise ValueError('Run with --download to fetch the pinned public source archive.')
    download(ARCHIVE_URL, archive, ARCHIVE_SHA256)
    records, audit = prepare_dataset(archive, data, args.seed)
    (data / 'ATTRIBUTION.txt').write_text(ATTRIBUTION + '\n', encoding='utf-8')
    (output / 'ATTRIBUTION.txt').write_text(ATTRIBUTION + '\n', encoding='utf-8')
    base_path = data / 'resnet18-f37072fd.pth'
    if models.ResNet18_Weights.IMAGENET1K_V1.url != BASE_URL:
        raise ValueError('Unexpected torchvision ResNet18 source checkpoint URL.')
    download(BASE_URL, base_path, BASE_SHA256)
    base_digest = digest(base_path)

    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    torch.set_num_threads(4)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    device = torch.device('cuda' if args.device == 'auto' and torch.cuda.is_available() else 'cpu' if args.device == 'auto' else args.device)
    if device.type == 'cuda' and not torch.cuda.is_available():
        raise ValueError('CUDA was requested but is not available.')
    print('Training device:', device, torch.cuda.get_device_name(0) if device.type == 'cuda' else '', flush=True)
    model = models.resnet18(weights=None)
    # Only trusted official state tensors are deserialized; never arbitrary model code.
    model.load_state_dict(torch.load(base_path, map_location='cpu', weights_only=True))
    model.fc = nn.Linear(model.fc.in_features, 2)
    model.to(device)
    datasets = {split: OralDataset(records, split, train=split == 'train') for split in ('train', 'validation', 'test')}
    generator = torch.Generator().manual_seed(args.seed)
    loaders = {split: DataLoader(dataset, batch_size=args.batch_size, shuffle=split == 'train', num_workers=0,
                                 generator=generator if split == 'train' else None, pin_memory=device.type == 'cuda')
               for split, dataset in datasets.items()}
    counts = Counter(item['label'] for item in records if item['split'] == 'train')
    weights = torch.tensor([sum(counts.values()) / (2 * counts[index]) for index in range(2)], dtype=torch.float32, device=device)
    criterion = nn.CrossEntropyLoss(weight=weights)
    best_key = (-1.0, float('-inf'))
    best_state, best_epoch, trace = None, None, []
    head_epochs = min(3, args.epochs)
    optimizer = None
    for epoch in range(1, args.epochs + 1):
        phase = 'head' if epoch <= head_epochs else 'layer4-and-head'
        if epoch in (1, head_epochs + 1):
            for parameter in model.parameters():
                parameter.requires_grad = False
            for parameter in model.fc.parameters():
                parameter.requires_grad = True
            if phase == 'head':
                optimizer = torch.optim.AdamW(model.fc.parameters(), lr=5e-4, weight_decay=1e-4)
            else:
                for parameter in model.layer4.parameters():
                    parameter.requires_grad = True
                optimizer = torch.optim.AdamW([{'params': model.layer4.parameters(), 'lr': 5e-5}, {'params': model.fc.parameters(), 'lr': 3e-4}], weight_decay=1e-4)
        model.train()
        # Freeze BatchNorm running statistics so tiny batches do not replace the source statistics.
        for module in model.modules():
            if isinstance(module, nn.BatchNorm2d):
                module.eval()
        train_loss, seen = 0.0, 0
        for pixels, targets in loaders['train']:
            pixels, targets = pixels.to(device), targets.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(pixels)
            loss = criterion(logits, targets)
            loss.backward()
            optimizer.step()
            train_loss += float(loss.detach()) * len(targets)
            seen += len(targets)
        validation = evaluate(model, loaders['validation'], device, criterion)
        key = (validation['balanced_accuracy'], -validation['weighted_cross_entropy'])
        if key > best_key:
            best_key, best_epoch = key, epoch
            best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
        entry = {'epoch': epoch, 'phase': phase, 'train_weighted_cross_entropy': train_loss / seen,
                 'validation': validation, 'elapsed_seconds': round(time.time() - started, 2)}
        trace.append(entry)
        write_json(output / 'progress.json', {'stage': 'training', 'epoch': epoch, 'epochs': args.epochs,
                   'best_epoch': best_epoch, 'validation_balanced_accuracy': validation['balanced_accuracy'], 'clinical_validation': False})
        write_json(output / 'training-trace.json', trace)
        print(f"Epoch {epoch}/{args.epochs} {phase}: train loss {train_loss / seen:.4f}; validation balanced accuracy {validation['balanced_accuracy']:.4f}; best epoch {best_epoch}", flush=True)
    if best_state is None:
        raise ValueError('Training did not produce a candidate state.')
    model.load_state_dict(best_state)
    model.eval()
    validation = evaluate(model, loaders['validation'], device, criterion)
    # The test set is evaluated once, after all model-selection decisions.
    test = evaluate(model, loaders['test'], device, criterion)
    torch.save(best_state, output / 'best-state.pt')
    model.to('cpu').eval()
    write_json(output / 'progress.json', {'stage': 'exporting', 'best_epoch': best_epoch, 'clinical_validation': False})
    temporary_model = output / 'model.part.onnx'
    sample = torch.zeros((1, 3, 224, 224), dtype=torch.float32)
    torch.onnx.export(model, sample, temporary_model, input_names=['pixel_values'], output_names=['logits'],
                      dynamic_axes={'pixel_values': {0: 'batch'}, 'logits': {0: 'batch'}}, opset_version=17,
                      do_constant_folding=True, dynamo=False)
    import onnx
    import onnxruntime as ort
    onnx.checker.check_model(onnx.load(temporary_model))
    options = ort.SessionOptions(); options.intra_op_num_threads = 4; options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(temporary_model), sess_options=options, providers=['CPUExecutionProvider'])
    check_indices = [next(i for i, item in enumerate(datasets['test'].records) if item['label'] == label) for label in range(2)]
    maximum_error, parity = 0.0, []
    for index in check_indices:
        tensor, label = datasets['test'][index]
        pixels = tensor.unsqueeze(0)
        with torch.inference_mode():
            expected = model(pixels).numpy()
        actual = session.run(None, {'pixel_values': pixels.numpy()})[0]
        difference = float(np.max(np.abs(expected - actual)))
        if not np.allclose(expected, actual, atol=1e-4, rtol=1e-4):
            raise ValueError('Exported ONNX output differs from the trained PyTorch model.')
        maximum_error = max(maximum_error, difference)
        parity.append({'source_member': datasets['test'].records[index]['source_member'], 'expected_label': LABELS[label],
                       'predicted_label': LABELS[int(actual.argmax(1)[0])], 'maximum_absolute_logit_difference': difference})
    both = torch.stack([datasets['test'][i][0] for i in check_indices])
    batch_logits = session.run(None, {'pixel_values': both.numpy()})[0]
    if batch_logits.shape != (2, 2):
        raise ValueError('The exported dynamic batch contract failed verification.')
    temporary_model.replace(output / 'model.onnx')
    model_sha = digest(output / 'model.onnx')
    examples = save_verification_examples(records, output)
    report = {
        'schema_version': 'humantwin-oral-training-v1', 'training_performed': True, 'clinical_validation': False,
        'created_at': datetime.now(timezone.utc).isoformat(), 'task': 'Benign-lesion vs malignant-lesion classification on oral photographs',
        'labels': LABELS, 'source': {'url': SOURCE, 'doi': SOURCE_DOI, 'archive_url': ARCHIVE_URL,
                                    'archive_sha256': ARCHIVE_SHA256, 'license': 'CC-BY-4.0', 'attribution': ATTRIBUTION},
        'initial_weights': {'url': BASE_URL, 'sha256': base_digest, 'official_torchvision_hash_prefix': 'f37072fd',
                            'source': 'torchvision ResNet18_Weights.IMAGENET1K_V1'},
        'preprocessing': {'color': 'RGB', 'resize': 'PIL bilinear stretch to 224x224', 'scale': 1 / 255, 'mean': MEAN, 'std': STD,
                          'train_augmentation_only': ['horizontal flip', 'rotation +-10 degrees', 'brightness/contrast/saturation jitter +-0.1']},
        'dataset_audit': audit, 'seed': args.seed, 'epochs': args.epochs, 'head_epochs': head_epochs,
        'selected_epoch': best_epoch, 'selection': 'Highest validation balanced accuracy; validation weighted CE breaks ties. Test is not used for selection.',
        'optimizer': {'type': 'AdamW', 'head_lr': .0005, 'finetune_layer4_lr': .00005, 'finetune_head_lr': .0003, 'weight_decay': .0001},
        'batch_size': args.batch_size, 'class_weights': weights.detach().cpu().tolist(),
        'batchnorm_running_statistics': 'frozen', 'validation': validation, 'test_once': test,
        'patient_disjoint': None, 'held_out_subjects': None, 'independent_patient_validation_available': False,
        'runtime': {'torch': torch.__version__, 'torchvision': __import__('torchvision').__version__, 'onnxruntime': ort.__version__,
                    'training_device': str(device), 'gpu_name': torch.cuda.get_device_name(0) if device.type == 'cuda' else None,
                    'cpu_threads': 4, 'cudnn_deterministic': True},
        'onnx': {'opset': 17, 'weights_sha256': model_sha, 'max_absolute_parity_error': maximum_error,
                 'real_test_image_parity_checks': parity, 'dynamic_batch_verified': True},
        'verification_examples': examples,
        'elapsed_seconds': round(time.time() - started, 2),
        'limitations': ['Only 323 original source photographs before duplicate exclusions.',
                       'No patient identifiers or verified patient separation; image-level metrics may be optimistic.',
                       'Source labels and capture provenance are not independently reviewed by this application.',
                       'No clinical accuracy, personal cancer probability, normal-mouth screen, cancer stage, tumor location or treatment prediction is established.',
                       'No independent external-patient, skin-tone, device or geographical validation has been performed.'],
    }
    write_json(output / 'report.json', report)
    manifest = {'schema_version': 'humantwin-cancer-model-v1', 'track': 'oral', 'modality': 'oral_photo',
                'model_version': 'oral-resnet18-mendeley-v1', 'target': report['task'],
                'source_url': SOURCE, 'license': 'CC-BY-4.0', 'weights_sha256': model_sha,
                'input_size': [224, 224], 'color': 'RGB', 'resize': 'stretch', 'scale': 1 / 255,
                'mean': MEAN, 'std': STD, 'labels': LABELS, 'output': 'logits',
                'runtime': 'onnxruntime', 'interpolation': 'pil-bilinear',
                'evaluation': {'reference': 'Local report.json: measured image-group test metrics; no independent patient validation.',
                               'patient_disjoint': None, 'held_out_subjects': None, 'sensitivity': None, 'specificity': None},
                'research_only': True}
    # Activate only after complete model export, measured report and parity verification.
    write_json(output / 'manifest.json', manifest)
    write_json(output / 'progress.json', {'stage': 'complete', 'best_epoch': best_epoch, 'clinical_validation': False,
                                        'test_image_balanced_accuracy': test['balanced_accuracy'], 'weights_sha256': model_sha})
    print(json.dumps({'completed': True, 'model': str(output / 'model.onnx'), 'best_epoch': best_epoch,
                      'test_image_metrics': test, 'patient_disjoint': None, 'elapsed_seconds': report['elapsed_seconds']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--epochs', type=int, default=11)
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--device', choices=('auto', 'cpu', 'cuda'), default='auto')
    parser.add_argument('--data-dir', default='training-data/cancer-oral')
    parser.add_argument('--model-dir', default='models/cancer/oral_photo')
    args = parser.parse_args()
    if not 4 <= args.epochs <= 12 or not 1 <= args.batch_size <= 64:
        parser.error('Use 4–12 epochs and a batch size between 1 and 64.')
    train(args)
