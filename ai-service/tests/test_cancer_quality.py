"""Input checks and heatmap arithmetic; synthetic images plus the local reference images when present."""
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.cancer_explain import attention_rollout, grad_cam, normalized, replay_head
from app.cancer_quality import check_image, measure

ORAL = Path('training-data/cancer-oral/originals')
VERIFICATION = Path('models/cancer/verification')


def texture(gray=False, seed=0, size=(160, 200)):
    rng = np.random.default_rng(seed)
    noise = cv2.GaussianBlur(rng.normal(0, 1, size).astype(np.float32), (0, 0), 1.5)
    noise = (noise / noise.std() * 30)[:, :, None]
    base = np.full((*size, 3), (128, 128, 128) if gray else (90, 110, 200), np.float32)
    return np.clip(base + noise, 0, 255).astype(np.uint8)


def codes(result, severity=None):
    return {item.code for item in result.findings if severity is None or item.severity == severity}


def test_matching_images_are_accepted_for_their_own_input_type():
    assert check_image(texture(), 'oral_photo').decision != 'rejected'
    assert check_image(texture(gray=True), 'lung_ct_slice').decision != 'rejected'
    assert 'content-not-verified' in codes(check_image(texture(), 'dermoscopy'), 'info')


def test_color_and_grayscale_mismatches_are_rejected_in_both_directions():
    assert 'unexpected-color' in codes(check_image(texture(), 'lung_ct_slice'), 'reject')
    assert 'unexpected-color' in codes(check_image(texture(), 'breast_ultrasound'), 'reject')
    assert 'unexpected-grayscale' in codes(check_image(texture(gray=True), 'dermoscopy'), 'reject')
    assert 'unexpected-grayscale' in codes(check_image(texture(gray=True), 'oral_photo'), 'reject')


def test_a_colored_annotation_on_a_scan_limits_rather_than_rejects():
    scan = texture(gray=True)
    scan[:, :30] = (0, 200, 255)
    result = check_image(scan, 'lung_ct_slice')
    assert result.decision == 'accepted-with-warnings' and 'color-content' in codes(result, 'limiting')


def test_blank_dark_overexposed_and_blurred_images_are_flagged():
    assert 'blank-image' in codes(check_image(np.full((64, 64, 3), 128, np.uint8), 'lung_ct_slice'), 'reject')
    dark = (texture() * .1).astype(np.uint8)
    assert codes(check_image(dark, 'oral_photo')) & {'very-dark', 'blank-image'}
    page = np.full((300, 400, 3), 255, np.uint8)
    cv2.putText(page, 'Report 2026', (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 2, (40, 40, 40), 4)
    page[:, :40] = (30, 90, 200)
    assert 'overexposed' in codes(check_image(page, 'dermoscopy'), 'limiting')
    blurred = cv2.GaussianBlur(texture(), (0, 0), 9)
    blurred = np.clip(blurred.astype(np.int16) + np.linspace(-50, 50, blurred.shape[1], dtype=np.int16)[None, :, None], 0, 255).astype(np.uint8)
    assert 'severe-blur' in codes(check_image(blurred, 'dermoscopy'), 'limiting')


def test_small_and_elongated_images_only_warn():
    small = cv2.resize(texture(), (64, 48), interpolation=cv2.INTER_AREA)
    assert 'small-image' in codes(check_image(small, 'oral_photo'), 'warning')
    strip = cv2.resize(texture(), (400, 100), interpolation=cv2.INTER_AREA)
    assert 'elongated-image' in codes(check_image(strip, 'oral_photo'), 'warning')


def test_measurements_reject_unsupported_arrays():
    with pytest.raises(ValueError):
        measure(np.zeros((10, 10), np.uint8))
    with pytest.raises(ValueError):
        check_image(texture(), 'x-ray')


@pytest.mark.skipif(not ORAL.is_dir(), reason='local oral reference images are not installed')
def test_no_local_oral_reference_photograph_is_rejected_or_limited():
    paths = sorted(path for path in ORAL.glob('*/*') if path.suffix.lower() in {'.jpg', '.jpeg', '.png'})
    assert len(paths) > 100
    for path in paths:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        factor = min(1, 2048 / max(image.shape[:2]))
        if factor < 1:
            image = cv2.resize(image, (round(image.shape[1] * factor), round(image.shape[0] * factor)), interpolation=cv2.INTER_AREA)
        result = check_image(image, 'oral_photo')
        assert result.decision != 'rejected', path.name
        assert not codes(result, 'limiting'), (path.name, codes(result, 'limiting'))


@pytest.mark.skipif(not VERIFICATION.is_dir(), reason='verification images are not installed')
@pytest.mark.parametrize('name,modality', [('dermoscopy.jpg', 'dermoscopy'), ('lung_ct_slice.jpg', 'lung_ct_slice'),
                                           ('breast_ultrasound.jpg', 'breast_ultrasound')])
def test_installed_verification_images_pass_their_own_checks_and_fail_the_others(name, modality):
    image = cv2.imread(str(VERIFICATION / name), cv2.IMREAD_COLOR)
    assert check_image(image, modality).decision != 'rejected'
    others = {'dermoscopy': 'lung_ct_slice', 'lung_ct_slice': 'dermoscopy', 'breast_ultrasound': 'oral_photo'}
    assert check_image(image, others[modality]).decision == 'rejected'


def test_grad_cam_for_a_pooled_linear_head_reproduces_the_logits():
    rng = np.random.default_rng(1)
    features, weight, bias = rng.random((1, 6, 5, 5)), rng.normal(size=(3, 6)), rng.normal(size=3)
    logits = replay_head(features, weight, bias)
    for target in range(3):
        raw = np.tensordot(weight[target], features[0], axes=(0, 0))
        assert raw.mean() + bias[target] == pytest.approx(logits[target])
        assert np.array_equal(grad_cam(features, weight, target), np.maximum(raw, 0))
    with pytest.raises(ValueError):
        grad_cam(rng.random((1, 4, 5, 5)), weight, 0)


def test_attention_rollout_finds_the_patch_the_cls_token_reads():
    tokens = 1 + 3 * 3
    attention = np.full((1, 2, tokens, tokens), .01)
    attention[0, :, 0, 5] = 1
    attention /= attention.sum(axis=-1, keepdims=True)
    grid = attention_rollout([attention, attention])
    assert grid.shape == (3, 3) and np.unravel_index(grid.argmax(), grid.shape) == (1, 1)
    with pytest.raises(ValueError):
        attention_rollout([np.ones((1, 2, 11, 11)) / 11])
    values = normalized(grid)
    assert max(values) == 1 and min(values) >= 0 and len(values) == 9
    assert normalized(np.zeros((2, 2))) == [0, 0, 0, 0]
