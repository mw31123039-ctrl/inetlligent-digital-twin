"""Install real public research classifiers from pinned, fingerprinted artifacts.

Downloads no app/patient data and executes no repository-provided Python. The
reported checks establish software loading/export parity, not medical accuracy.
Run from ai-service after `uv sync --all-groups` (or the cancer-models group).
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import os
import shutil
import time
import urllib.parse
import urllib.request
from pathlib import Path

SERVICE = Path(__file__).resolve().parents[1]
SOURCES = {
    'dermoscopy': {
        'repo': 'sazio/skin-mole-vit-onnx',
        'revision': '25be9e61a71125de9502648c1f6adceb7a882637',
        'weights': 'onnx/model_quantized.onnx',
        'sha256': '85c5c07ec67e94d7b34c83624c36f6a729ef3c47747cf1465212c911db5badfa',
        'track': 'skin', 'version': 'ham10000-vit-q8-25be9e61',
        'target': 'HAM10000 seven-category dermoscopic lesion classification',
        'license': 'MIT (ONNX repository); preserve upstream model and dataset terms',
        'metadata': ['README.md', 'config.json', 'preprocessor_config.json'],
        'metadata_sha256': {
            'README.md': '71ca6f1d6438fd1a0f6ca4182965bd8ab70d237920133a4e9d86be5147f4c648',
            'config.json': 'b87a1c8ce86cbfdd49e84809c53d2e6047b266c23fab26cc250f6f32e7a4d7ce',
            'preprocessor_config.json': 'a441e8801008a137948cbc1ef1df228afc518e407110df81636255a071c77686',
        },
        'labels': ['benign_keratosis-like_lesions', 'basal_cell_carcinoma', 'actinic_keratoses', 'vascular_lesions', 'melanocytic_Nevi', 'melanoma', 'dermatofibroma'],
        'evaluation': 'Published model card; no independently verified patient-disjoint clinical evaluation supplied.',
    },
    'breast_ultrasound': {
        'repo': 'hugging-science/breast-cancer-detector-2',
        'revision': '257147b35a8d94aca77a556a374bf9260976a453',
        'weights': 'model.safetensors',
        'sha256': 'e29b66258ae29485d63c6527a89016752bea22898bff373ea754ce4877d1acef',
        'track': 'breast', 'version': 'busi-vit-257147b3-onnx',
        'target': 'Breast ultrasound dataset categories: benign, malignant and normal',
        'license': 'Apache-2.0 (published model card); preserve dataset terms',
        'metadata': ['README.md', 'config.json', 'preprocessor_config.json', 'eval/benchmark_results.csv', 'eval/info.txt'],
        'metadata_sha256': {
            'README.md': '68be4497d06f42eba792914a370675a99ebc7ddb9f8fc98a70184b09d9c3764f',
            'config.json': 'cf1d2affd30ede1297e745c4e7ffe06031ceb6cb1c5f4ec2ce06a0d2ccb10738',
            'preprocessor_config.json': '90d1ae427c27d2b9dcb01f6a62ba96aa67aac2de1697c59cd212055b5035c4a2',
            'eval/benchmark_results.csv': '49b6086448f2ad694bc78127b829339ccb54ab57720d5c0ec3a410720b10b621',
            'eval/info.txt': '85ee664bf7daf61b44cfca01316edd157f4407b785b0ff44087e3ad3f0a369bb',
        },
        'labels': ['benign', 'malignant', 'normal'],
        'evaluation': 'Author-reported benchmark files retained with source; patient separation and external clinical validity unverified.',
    },
    'lung_ct_slice': {
        'repo': 'yunussgultekiin/lung-cancer-efficientnet-b0',
        'revision': '506c398b6fd10b3e9f046c908c2b59bb33547faf',
        'weights': 'outputs/models/best_efficientnet_b0.pt',
        'sha256': '6dd98c2c7d015f805eddcad55f46359f631ef079fd824daced41ae8af787a24c',
        'track': 'lung', 'version': 'lung-efficientnet-b0-506c398b-onnx',
        'target': 'Single CT-slice dataset classification: adenocarcinoma, large-cell, normal and squamous-cell categories',
        'license': 'MIT repository LICENSE; model card declares Apache-2.0; retain both notices and dataset terms',
        'metadata': ['README.md', 'LICENSE', 'src/config.py', 'src/model.py', 'src/dataset.py', 'outputs/reports/classification_report.txt'],
        'metadata_sha256': {
            'README.md': '0a24597162b53edc18de67a9ea90f46adc9b71169144d9f0bd357ae2fcbce33d',
            'LICENSE': '1b53f3cfe885ce62bb8bda1cea8c04ca19e2988eadcb4388a91a6de01270ba57',
            'src/config.py': '856ea6fc6b34f33db888748bc77868acd252995dcd5b815b2d6d56859c16a985',
            'src/model.py': '9122e608b07083703b9309caed5021071c2c36702c7d1d51bb397244da586f71',
            'src/dataset.py': 'b090968629bb14b06c71227c1096de3dca1deea2414a47837ad3a3443d67d37b',
            'outputs/reports/classification_report.txt': '74c130147df96ac42ed0a7ecf55ad576290801d90041a71a4d5182fa9e91bd1b',
        },
        'labels': ['adenocarcinoma', 'large.cell.carcinoma', 'normal', 'squamous.cell.carcinoma'],
        'evaluation': 'Author image-group holdout:165 images; patient IDs unavailable. No patient-disjoint clinical validation established.',
    },
}


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def json_write(path: Path, value: dict):
    temporary = path.with_suffix(path.suffix + '.part')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def software_versions() -> dict:
    versions = {}
    for name in ['torch', 'torchvision', 'onnx', 'onnxruntime', 'transformers', 'safetensors', 'pillow']:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def download(source: dict, name: str, destination: Path, expected: str | None = None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and (expected is None or digest(destination) == expected):
        return
    url = f"https://huggingface.co/{source['repo']}/resolve/{source['revision']}/{urllib.parse.quote(name, safe='/')}"
    temporary = destination.with_suffix(destination.suffix + '.download')
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'HumanTwin-research-model-installer/1'})
            downloaded, next_progress = 0, 32 * 1024 * 1024
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open('wb') as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk); downloaded += len(chunk)
                    if downloaded >= next_progress:
                        print(f"{source['repo']}: downloaded {downloaded // (1024 * 1024)} MiB", flush=True)
                        next_progress += 32 * 1024 * 1024
            if expected is not None and digest(temporary) != expected:
                raise ValueError(f'Fingerprint mismatch for {name}; artifact was not installed.')
            temporary.replace(destination)
            return
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1 + attempt)


def ort_session(path: Path):
    import onnxruntime as ort
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    options.log_severity_level = 3
    return ort.InferenceSession(str(path), sess_options=options, providers=['CPUExecutionProvider'])


def validate_onnx(path: Path, labels: list[str], reference=None) -> dict:
    import numpy as np
    session = ort_session(path)
    inputs, outputs = session.get_inputs(), session.get_outputs()
    if len(inputs) != 1 or len(outputs) != 1 or inputs[0].type != 'tensor(float)':
        raise ValueError('The installed classifier must have one float32 image input and one output.')
    sample = np.random.default_rng(43).normal(0, .8, (1, 3, 224, 224)).astype(np.float32)
    started = time.perf_counter()
    logits = np.asarray(session.run(None, {inputs[0].name: sample})[0])
    elapsed = (time.perf_counter() - started) * 1000
    if logits.shape != (1, len(labels)) or not np.isfinite(logits).all():
        raise ValueError('The ONNX classifier output does not match its label contract.')
    report = {'software_smoke_test': True, 'output_shape': list(logits.shape), 'warmup_ms': round(elapsed, 2),
              'clinical_validation': False, 'patient_data_used': False}
    if reference is not None:
        import torch
        with torch.inference_mode():
            expected = reference(torch.from_numpy(sample)).detach().cpu().numpy()
        maximum = float(np.max(np.abs(logits - expected)))
        if not np.allclose(logits, expected, rtol=.001, atol=.001):
            raise ValueError(f'ONNX export did not match its source model: maximum absolute logit difference {maximum}.')
        report['source_export_max_abs_logit_error'] = maximum
        report['source_export_parity'] = True
    return report


def export_torch(model, destination: Path):
    import torch
    model = model.cpu().eval()
    torch.set_num_threads(4)
    sample = torch.zeros((1, 3, 224, 224), dtype=torch.float32)
    with torch.inference_mode():
        torch.onnx.export(model, sample, str(destination), input_names=['pixel_values'], output_names=['logits'],
                          dynamic_axes={'pixel_values': {0: 'batch'}, 'logits': {0: 'batch'}},
                          opset_version=17, dynamo=False)
    return model


def build_manifest(modality: str, weights_hash: str) -> dict:
    source = SOURCES[modality]
    mean, std = ([.485, .456, .406], [.229, .224, .225]) if modality == 'lung_ct_slice' else ([.5] * 3, [.5] * 3)
    return {
        'schema_version': 'humantwin-cancer-model-v1', 'track': source['track'], 'modality': modality,
        'model_version': source['version'], 'target': source['target'],
        'source_url': f"https://huggingface.co/{source['repo']}/tree/{source['revision']}",
        'license': source['license'], 'weights_sha256': weights_hash, 'input_size': [224, 224],
        'color': 'RGB', 'resize': 'stretch', 'interpolation': 'pil-bilinear', 'runtime': 'onnxruntime',
        'scale': 1 / 255, 'mean': mean, 'std': std, 'labels': source['labels'], 'output': 'logits',
        'evaluation': {'reference': source['evaluation'], 'patient_disjoint': None, 'held_out_subjects': None,
                       'sensitivity': None, 'specificity': None}, 'research_only': True,
    }


def install(modality: str, root: Path, force: bool = False):
    source = SOURCES[modality]
    directory = root / modality
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / 'manifest.json'
    if not force and manifest_path.is_file() and (directory / 'model.onnx').is_file():
        existing = json.loads(manifest_path.read_text(encoding='utf-8'))
        if existing == build_manifest(modality, digest(directory / 'model.onnx')):
            print(json.dumps({'modality': modality, 'state': 'already-installed', 'weights_sha256': existing['weights_sha256']}), flush=True)
            return
    source_directory = directory / 'source'
    for name in source['metadata']:
        download(source, name, source_directory / name, source['metadata_sha256'][name])
    weights = source_directory / source['weights']
    download(source, source['weights'], weights, source['sha256'])
    destination = directory / 'model.staging.onnx'
    model = None
    if modality == 'dermoscopy':
        config = json.loads((source_directory / 'config.json').read_text(encoding='utf-8'))
        labels = [config['id2label'][str(index)] for index in range(len(config['id2label']))]
        if labels != source['labels']:
            raise ValueError('Unexpected published dermoscopy label mapping.')
        shutil.copyfile(weights, destination)
    elif modality == 'breast_ultrasound':
        import torch
        from transformers import ViTForImageClassification
        torch.set_num_threads(4)
        classifier = ViTForImageClassification.from_pretrained(str(source_directory), local_files_only=True,
                                                              use_safetensors=True, attn_implementation='eager')
        labels = [classifier.config.id2label[index] for index in range(classifier.config.num_labels)]
        if labels != ['benign', 'malignant', 'normal']:
            raise ValueError('Unexpected published ultrasound label mapping.')

        class LogitsOnly(torch.nn.Module):
            def __init__(self, network):
                super().__init__(); self.network = network

            def forward(self, pixel_values):
                return self.network(pixel_values=pixel_values).logits

        model = export_torch(LogitsOnly(classifier), destination)
    else:
        import torch
        from torchvision.models import efficientnet_b0
        labels = source['labels']
        config_text = (source_directory / 'src/config.py').read_text(encoding='utf-8')
        declared_labels = next((ast.literal_eval(node.value) for node in ast.parse(config_text).body
                                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                                and node.target.id == 'CLASS_NAMES'), None)
        if list(declared_labels or []) != labels:
            raise ValueError('The published lung configuration no longer matches the reviewed labels.')
        classifier = efficientnet_b0(weights=None)
        classifier.classifier = torch.nn.Sequential(torch.nn.Dropout(p=.2, inplace=True), torch.nn.Linear(1280, 4))
        classifier.load_state_dict(torch.load(weights, map_location='cpu', weights_only=True), strict=True)
        model = export_torch(classifier, destination)
    report = validate_onnx(destination, labels, model)
    weights_hash = digest(destination)
    manifest = build_manifest(modality, weights_hash)
    source_files = {str(path.relative_to(source_directory)).replace('\\', '/'): digest(path)
                    for path in source_directory.rglob('*') if path.is_file()}
    report.update({'modality': modality, 'source_repository': source['repo'], 'source_revision': source['revision'],
                   'source_weights_sha256': source['sha256'], 'installed_weights_sha256': weights_hash,
                   'source_files_sha256': source_files, 'labels': labels, 'source_evaluation_is_unverified': True,
                   'software_versions': software_versions()})
    destination.replace(directory / 'model.onnx')
    json_write(directory / 'installation-report.json', report)
    json_write(manifest_path, manifest)
    print(json.dumps({'modality': modality, 'state': 'installed-research-only', 'weights_sha256': weights_hash,
                      'software_check': report}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', nargs='+', choices=list(SOURCES), default=list(SOURCES))
    parser.add_argument('--model-dir', type=Path, default=Path(os.environ.get('CANCER_MODEL_DIR', SERVICE / 'models/cancer')))
    parser.add_argument('--force', action='store_true', help='Re-export/reinstall even if an existing fingerprint matches.')
    arguments = parser.parse_args()
    for modality in arguments.models:
        install(modality, arguments.model_dir.resolve(), arguments.force)


if __name__ == '__main__':
    main()
