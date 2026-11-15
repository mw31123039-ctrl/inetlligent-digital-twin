"""Preprocessing parity with each installed model's own reference pipeline.

Runs only where the installed models and the optional reference libraries are present; it never
modifies a model file. The tolerance is one float32 rounding step after normalization.
"""
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from app.cancer import ModelManifest, load_bundle, prepare_input

MODELS = Path('models/cancer')
VERIFICATION = Path('models/cancer/verification')
HF_MODELS = {'dermoscopy': 'dermoscopy.jpg', 'breast_ultrasound': 'breast_ultrasound.jpg'}


def installed(modality):
    return (MODELS / modality / 'manifest.json').is_file() and (MODELS / modality / 'model.onnx').is_file()


def manifest(modality):
    return ModelManifest.model_validate_json((MODELS / modality / 'manifest.json').read_bytes())


def service_tensor(path, config):
    return prepare_input(cv2.imread(str(path), cv2.IMREAD_COLOR), config)


@pytest.mark.parametrize('modality', list(HF_MODELS))
def test_manifest_matches_the_retained_hugging_face_preprocessor_config(modality):
    config_path = MODELS / modality / 'source/preprocessor_config.json'
    if not installed(modality) or not config_path.is_file():
        pytest.skip('model source configuration is not installed')
    source, config = json.loads(config_path.read_text()), manifest(modality)
    size = source.get('size', 224)
    size = (size['width'], size['height']) if isinstance(size, dict) else (size, size)
    assert tuple(config.input_size) == size and config.resize == 'stretch' and source.get('do_center_crop') in (None, False)
    assert source.get('resample', 2) == 2 and config.interpolation == 'pil-bilinear'
    assert config.scale == pytest.approx(source.get('rescale_factor', 1 / 255))
    assert config.mean == pytest.approx(source['image_mean']) and config.std == pytest.approx(source['image_std'])


@pytest.mark.parametrize('modality', list(HF_MODELS))
def test_service_tensor_equals_the_transformers_vit_image_processor(modality):
    if not installed(modality) or not (VERIFICATION / HF_MODELS[modality]).is_file():
        pytest.skip('model or verification image is not installed')
    transformers = pytest.importorskip('transformers')
    processor = transformers.ViTImageProcessor(**{key: value for key, value in json.loads((MODELS / modality / 'source/preprocessor_config.json').read_text()).items()
                                                  if key in {'do_normalize', 'do_resize', 'image_mean', 'image_std', 'size', 'resample', 'rescale_factor', 'do_rescale'}})
    path = VERIFICATION / HF_MODELS[modality]
    expected = processor(Image.open(path).convert('RGB'), return_tensors='np')['pixel_values']
    assert np.abs(service_tensor(path, manifest(modality)) - expected).max() < 1e-5


@pytest.mark.parametrize('modality,image', [('lung_ct_slice', VERIFICATION / 'lung_ct_slice.jpg'), ('oral_photo', Path('models/cancer/oral_photo/examples/benign_lesion.png'))])
def test_service_tensor_equals_the_training_torchvision_transform(modality, image):
    if not installed(modality) or not image.is_file():
        pytest.skip('model or reference image is not installed')
    transforms = pytest.importorskip('torchvision.transforms')
    config = manifest(modality)
    # Same test-time transform as source/src/dataset.py (lung) and scripts/train-oral-cancer.py (oral).
    reference = transforms.Compose([transforms.Resize(tuple(config.input_size[::-1]), interpolation=transforms.InterpolationMode.BILINEAR),
                                    transforms.ToTensor(), transforms.Normalize(config.mean, config.std)])
    expected = reference(Image.open(image).convert('RGB')).numpy()[None]
    assert np.abs(service_tensor(image, config) - expected).max() < 1e-5


@pytest.mark.parametrize('modality', ['dermoscopy', 'oral_photo', 'lung_ct_slice', 'breast_ultrasound'])
def test_installed_models_expose_a_verified_heatmap_method(modality):
    if not installed(modality):
        pytest.skip('model is not installed')
    pytest.importorskip('onnx')
    _, runner = load_bundle(MODELS / modality, modality)
    expected = 'attention-rollout' if modality in HF_MODELS else 'grad-cam'
    assert runner.explainer is not None and runner.explainer.method == expected
