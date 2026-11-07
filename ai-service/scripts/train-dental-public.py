"""Train an experimental, single-class RGB tooth detector from a pinned public export.

No patient photos from the app are used. Published boxes are not crown masks or
clinician-verified diagnostic labels. All reported scores are image-level only.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import urllib.request
import zipfile
from pathlib import Path

ARCHIVE_SHA256 = '2eb4d4cd3c7f6e8b7ace234e7cc215323498cc5a531f1c87902db616d2e147c1'
SOURCE = 'https://universe.roboflow.com/dentalmate6v/intraoral-tooth-numbering-fdi/dataset/1'
ARCHIVE_URL = 'https://huggingface.co/datasets/Frallex/FDI_Intraoral/resolve/d9e032ddb9142325c3ca5cd399e14f03c6bd3bb7/FDI%20Intraoral%20Dataset.zip'
WEIGHTS_URL = 'https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt'
WEIGHTS_SHA256 = '0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1'


def download(url: str, path: Path, expected_sha256: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.part')
    with urllib.request.urlopen(url, timeout=90) as response, temporary.open('wb') as output:
        shutil.copyfileobj(response, output, 65536)
    if hashlib.sha256(temporary.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError('Downloaded asset fingerprint mismatch.')
    temporary.replace(path)


def prepare(archive: Path, destination: Path) -> dict:
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('Public dataset archive fingerprint mismatch.')
    destination.mkdir(parents=True, exist_ok=True)
    # Group variants of a source image; remove overlaps from training first.
    # The export has no patient IDs: do not claim patient-disjoint evaluation.
    used_sources, used_hashes, counts, removed = set(), set(), {}, 0
    expected_files = set()
    with zipfile.ZipFile(archive) as bundle:
        for partition in ('test', 'valid', 'train'):
            counts[partition] = 0
            for kind in ('images', 'labels'):
                (destination / partition / kind).mkdir(parents=True, exist_ok=True)
            records = sorted(n for n in bundle.namelist() if re.fullmatch(rf'{partition}/images/[^/]+\.jpg', n))
            current_sources, current_hashes = set(), set()
            for member in records:
                name = Path(member).name
                group = re.sub(r'\.rf\..*', '', name).lower()
                raw = bundle.read(member)
                digest = hashlib.sha256(raw).hexdigest()
                if group in used_sources or digest in used_hashes:
                    removed += 1
                    continue
                label = member.replace('/images/', '/labels/').rsplit('.', 1)[0] + '.txt'
                lines = []
                for line in bundle.read(label).decode('utf-8').splitlines():
                    parts = line.split()
                    if len(parts) != 5:
                        raise ValueError('Expected object-detection boxes, not masks.')
                    index, x, y, width, height = map(float, parts)
                    if not (index.is_integer() and 0 <= index < 34 and 0 <= x <= 1 and 0 <= y <= 1 and 0 < width <= 1 and 0 < height <= 1):
                        raise ValueError('Invalid source annotation.')
                    # Intentionally collapse numbering classes; no FDI predictions.
                    lines.append(f'0 {x} {y} {width} {height}')
                if not lines:
                    continue
                (destination / partition / 'images' / name).write_bytes(raw)
                output_label = destination / partition / 'labels' / (Path(name).stem + '.txt')
                output_label.write_text('\n'.join(lines) + '\n')
                expected_files.update([(destination / partition / 'images' / name).resolve(), output_label.resolve()])
                counts[partition] += 1
                current_sources.add(group)
                current_hashes.add(digest)
            used_sources.update(current_sources)
            used_hashes.update(current_hashes)
    actual_files = {p.resolve() for partition in ('test', 'valid', 'train') for kind in ('images', 'labels')
                    for p in (destination / partition / kind).rglob('*') if p.is_file()}
    if actual_files != expected_files:
        raise ValueError('The prepared directory contains files outside this pinned export. Use a new dataset directory.')
    data = destination / 'tooth.yaml'
    data.write_text('path: ' + json.dumps(destination.resolve().as_posix()) + '\ntrain: train/images\nval: valid/images\ntest: test/images\nnames: [visible_tooth]\n')
    provenance = {'source': SOURCE, 'dataset_author': 'DentalMate6v', 'dataset_license': 'CC-BY-4.0',
                  'mirror': 'https://huggingface.co/datasets/Frallex/FDI_Intraoral',
                  'mirror_revision': 'd9e032ddb9142325c3ca5cd399e14f03c6bd3bb7',
                  'archive_sha256': ARCHIVE_SHA256, 'images': counts, 'removed_cross_split_duplicates': removed,
                  'patient_disjoint_verified': False, 'independent_annotation_review': False,
                  'label_transformation': '34 numbering labels collapsed to visible_tooth; bounding boxes only',
                  'clinical_validation': False}
    (destination / 'provenance.json').write_text(json.dumps(provenance, indent=2))
    return provenance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, default=Path('training-data/public/frallex/fdi-intraoral.zip'))
    parser.add_argument('--dataset', type=Path, default=Path('training-data/public/visible-teeth-v1'))
    parser.add_argument('--output', type=Path, default=Path('models/dental-public'))
    parser.add_argument('--weights', default='models/dental-public/source/yolo11n.pt')
    parser.add_argument('--epochs', type=int, default=30)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--download', action='store_true', help='Download the pinned public dataset and official base weights if absent.')
    args = parser.parse_args()
    if args.download and not args.archive.is_file():
        download(ARCHIVE_URL, args.archive, ARCHIVE_SHA256)
    if args.download and not Path(args.weights).is_file():
        download(WEIGHTS_URL, Path(args.weights), WEIGHTS_SHA256)
    provenance = prepare(args.archive, args.dataset)
    print(json.dumps(provenance), flush=True)
    if args.prepare_only:
        return
    if hashlib.sha256(Path(args.weights).read_bytes()).hexdigest() != WEIGHTS_SHA256:
        raise ValueError('Expected the pinned official base checkpoint; untrusted pickle is not loaded.')
    os.environ['YOLO_OFFLINE'] = 'true'
    os.environ['YOLO_AUTOINSTALL'] = 'false'
    runtime_config = (args.output / 'runtime-config').resolve()
    runtime_config.mkdir(parents=True, exist_ok=True)
    os.environ['YOLO_CONFIG_DIR'] = str(runtime_config)
    import torch
    from ultralytics import YOLO, settings
    settings.update({'sync': False})
    if not torch.cuda.is_available():
        raise RuntimeError('A CUDA-capable training runtime is required for this run.')
    print(json.dumps({'device': torch.cuda.get_device_name(0), 'torch': torch.__version__}), flush=True)
    model = YOLO(args.weights)
    def record_plan(trainer):
        plan = {'run': Path(trainer.save_dir).name, 'epochs': args.epochs,
                'train_images': provenance['images']['train'], 'validation_images': provenance['images']['valid']}
        (args.output / 'training-plan.json').write_text(json.dumps(plan))
    model.add_callback('on_train_start', record_plan)
    model.train(data=str((args.dataset / 'tooth.yaml').resolve()), epochs=args.epochs, imgsz=640,
                batch=16, device=0, workers=0, amp=False, cache=False, seed=731, deterministic=True,
                project=str((args.output / 'runs').resolve()), name='visible-teeth', exist_ok=False,
                patience=8, plots=False, verbose=False, pretrained=True, fliplr=0, flipud=0,
                mosaic=0, close_mosaic=0, degrees=5, translate=.05, scale=.15)
    best = Path(model.trainer.best)
    trained = YOLO(str(best))
    test = trained.val(data=str((args.dataset / 'tooth.yaml').resolve()), split='test',
                       imgsz=640, batch=16, device=0, workers=0, plots=False, verbose=False)
    exported = Path(trained.export(format='onnx', imgsz=640, dynamic=False, simplify=False, opset=12, device='cpu'))
    import cv2
    import numpy as np
    runtime = cv2.dnn.readNetFromONNX(str(exported))
    runtime.setInput(np.zeros((1, 3, 640, 640), np.float32))
    output = runtime.forward()
    if output.shape != (1, 5, 8400) or not np.isfinite(output).all():
        raise ValueError('Exported model does not match the local inference contract.')
    # Activate only a finished export and report; inference never loads pickle.
    args.output.mkdir(parents=True, exist_ok=True)
    temporary = args.output / 'detector.pending.onnx'
    shutil.copyfile(exported, temporary)
    sha = hashlib.sha256(temporary.read_bytes()).hexdigest()
    report = {**provenance, 'format': 'humantwin-public-tooth-detector-v1', 'architecture': 'yolo11n',
              'training_performed': True, 'epochs_completed': int(model.trainer.epoch + 1),
              'software_license': 'AGPL-3.0', 'model_sha256': sha, 'input_size': 640,
              'train_images': provenance['images']['train'], 'validation_images': provenance['images']['valid'],
              'test_images': provenance['images']['test'], 'validation_kind': 'image-level-boxes',
              'test_box_metrics': {k: float(v) for k, v in test.results_dict.items()},
              'outlines': 'Per-box local GrabCut refinement; no supervised crown-mask validation',
              'condition_classifier_trained': False}
    temporary.replace(args.output / 'detector.onnx')
    pending_report = args.output / 'report.pending.json'
    pending_report.write_text(json.dumps(report, indent=2))
    pending_report.replace(args.output / 'report.json')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
