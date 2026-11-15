"""Input checks for one prepared 2D research image.

Rule-based measurements only. They catch clear mismatches (a color photograph sent to a CT
model, a blank export, an unusable blur) before or alongside inference. They cannot verify
anatomy, the acquisition device or clinical image quality.

Thresholds were set from measurements on the local reference images (323 oral photographs and the
installed verification images) so that none of them is rejected; see research/CANCER_EVALUATION.md (section 6).
"""
from functools import lru_cache
from typing import Literal

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

COLOR_INPUTS = frozenset({'skin_photo', 'dermoscopy', 'oral_photo'})
GRAY_INPUTS = frozenset({'lung_ct_slice', 'mammogram', 'breast_ultrasound', 'breast_mri_slice'})
EXPECTED_INPUT = {
    'skin_photo': 'a color photograph of skin',
    'dermoscopy': 'a color dermoscopy image of one skin lesion',
    'oral_photo': 'a color photograph of the inside of the mouth',
    'lung_ct_slice': 'a grayscale CT slice of the chest',
    'mammogram': 'a grayscale mammogram',
    'breast_ultrasound': 'a grayscale breast ultrasound image',
    'breast_mri_slice': 'a grayscale breast MRI slice',
}

# A pixel counts as colored when its RGB channels differ by more than this many 8-bit levels.
COLORED_PIXEL_SPREAD = 24
BLANK_CONTRAST = 6.0
LOW_CONTRAST = 12.0
SEVERE_BLUR = 3.0
BLUR = 6.0
OVEREXPOSED_LIMIT = .5
OVEREXPOSED_WARN = .25
VERY_DARK_COLOR, DARK_COLOR, VERY_DARK_GRAY = 20.0, 40.0, 8.0
GRAY_REJECT_COLORED, GRAY_LIMIT_COLORED = .35, .05
COLOR_REJECT_COLORED, COLOR_LIMIT_COLORED = .02, .08
SMALL_SIDE = 128
ELONGATED_RATIO = 2.5

Severity = Literal['info', 'warning', 'limiting', 'reject']
CheckCode = Literal[
    'blank-image', 'low-contrast', 'overexposed', 'bright-areas', 'very-dark', 'dark', 'severe-blur', 'blur',
    'unexpected-color', 'color-content', 'unexpected-grayscale', 'weak-color', 'small-image', 'elongated-image',
    'face-detected', 'content-not-verified',
]


class _Closed(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class InputCheck(_Closed):
    """One observation about the image. 'limiting' makes the finding inconclusive; 'reject' stops analysis."""
    code: CheckCode
    severity: Severity
    message: str = Field(min_length=1, max_length=240)


class ImageChecks(_Closed):
    width: int = Field(ge=32, le=2048)
    height: int = Field(ge=32, le=2048)
    brightness: float = Field(ge=0, le=255)
    contrast: float = Field(ge=0, le=128)
    sharpness: float = Field(ge=0)
    colored_fraction: float = Field(ge=0, le=1)
    overexposed_fraction: float = Field(ge=0, le=1)
    decision: Literal['accepted', 'accepted-with-warnings', 'rejected']
    findings: list[InputCheck] = Field(max_length=12)


def measure(image: np.ndarray) -> dict[str, float]:
    """Return simple statistics of a BGR uint8 image; no model is involved."""
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
        raise ValueError('A decoded 8-bit color image is required.')
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    # Sharpness is compared at a common scale so that large uploads are not favored.
    factor = 512 / max(height, width)
    reduced = cv2.resize(gray, (max(1, round(width * factor)), max(1, round(height * factor))), interpolation=cv2.INTER_AREA) if factor < 1 else gray
    spread = image.max(axis=2).astype(np.int16) - image.min(axis=2).astype(np.int16)
    return {
        'width': float(width), 'height': float(height),
        'brightness': float(gray.mean()), 'contrast': float(gray.std()),
        'sharpness': float(cv2.Laplacian(reduced, cv2.CV_64F).var()),
        'colored_fraction': float((spread > COLORED_PIXEL_SPREAD).mean()),
        'overexposed_fraction': float((gray >= 251).mean()),
    }


@lru_cache(maxsize=1)
def _face_detector():
    try:
        detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        return None if detector.empty() else detector
    except Exception:
        return None


def face_visible(image: np.ndarray) -> bool:
    """Conservative frontal-face check. Used only as a privacy and wrong-input warning."""
    detector = _face_detector()
    if detector is None:
        return False
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    factor = 480 / max(height, width)
    if factor < 1:
        gray = cv2.resize(gray, (max(1, round(width * factor)), max(1, round(height * factor))), interpolation=cv2.INTER_AREA)
    side = max(48, int(min(gray.shape) * .3))
    try:
        return len(detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=12, minSize=(side, side))) > 0
    except cv2.error:
        return False


def check_image(image: np.ndarray, modality: str, model_input: tuple[int, int] = (224, 224)) -> ImageChecks:
    """Measure the image and decide whether it may be analyzed for this input type."""
    if modality not in EXPECTED_INPUT:
        raise ValueError('Unsupported modality.')
    stats = measure(image)
    expected = EXPECTED_INPUT[modality]
    findings: list[InputCheck] = []

    def add(code: str, severity: str, message: str):
        findings.append(InputCheck(code=code, severity=severity, message=message))

    if stats['contrast'] < BLANK_CONTRAST:
        add('blank-image', 'reject', 'This image is almost uniform, so there is nothing for the model to analyze. It may be a blank, very dark or washed-out export.')
    elif stats['contrast'] < LOW_CONTRAST:
        add('low-contrast', 'warning', 'Low image contrast. Model scores may be unreliable.')

    if stats['overexposed_fraction'] > OVEREXPOSED_LIMIT:
        add('overexposed', 'limiting', 'More than half of this image is pure white. It looks overexposed or like a document or screenshot, not ' + expected + '.')
    elif stats['overexposed_fraction'] > OVEREXPOSED_WARN:
        add('bright-areas', 'warning', 'Large areas of this image are pure white. Check for overexposure or glare.')

    colored = stats['colored_fraction']
    if modality in COLOR_INPUTS:
        if stats['brightness'] < VERY_DARK_COLOR:
            add('very-dark', 'limiting', 'This image is very dark. Retake or export it with normal lighting.')
        elif stats['brightness'] < DARK_COLOR:
            add('dark', 'warning', 'This image is dark. Model scores may be unreliable.')
        if colored < COLOR_REJECT_COLORED:
            add('unexpected-grayscale', 'reject', 'This image is grayscale, but this model expects ' + expected + '. Choose a matching image or a different area.')
        elif colored < COLOR_LIMIT_COLORED:
            add('weak-color', 'limiting', 'This image has almost no color, which is unusual for ' + expected + '.')
    else:
        if stats['brightness'] < VERY_DARK_GRAY:
            add('very-dark', 'limiting', 'This image is almost entirely black. Check the export window and brightness.')
        if colored > GRAY_REJECT_COLORED:
            add('unexpected-color', 'reject', 'This looks like a color photograph, but this model expects ' + expected + '. Choose a matching image or a different area.')
        elif colored > GRAY_LIMIT_COLORED:
            add('color-content', 'limiting', 'Part of this image is in color (for example an overlay or annotation). This model expects ' + expected + '.')

    if stats['sharpness'] < SEVERE_BLUR and stats['contrast'] >= BLANK_CONTRAST:
        add('severe-blur', 'limiting', 'This image is very blurred. Fine detail the model relies on is missing.')
    elif stats['sharpness'] < BLUR and stats['contrast'] >= BLANK_CONTRAST:
        add('blur', 'warning', 'This image looks soft or slightly blurred.')

    shorter, longer = sorted((stats['width'], stats['height']))
    if shorter < min(SMALL_SIDE, *model_input):
        add('small-image', 'warning', 'This image is smaller than the model input and is enlarged before analysis.')
    if longer / shorter > ELONGATED_RATIO:
        add('elongated-image', 'warning', 'This image is very elongated. The model stretches every image to a square, which distorts it.')
    if not any(item.severity == 'reject' for item in findings) and face_visible(image):
        add('face-detected', 'warning', 'A face may be visible. Use a close-up, de-identified image of the area only.')
    add('content-not-verified', 'info', 'Anatomy, imaging device and clinical image quality are not verified automatically.')

    rejected = any(item.severity == 'reject' for item in findings)
    flagged = any(item.severity in ('warning', 'limiting') for item in findings)
    return ImageChecks(width=int(stats['width']), height=int(stats['height']), brightness=stats['brightness'], contrast=min(128.0, stats['contrast']),
                       sharpness=stats['sharpness'], colored_fraction=colored, overexposed_fraction=stats['overexposed_fraction'],
                       decision='rejected' if rejected else 'accepted-with-warnings' if flagged else 'accepted', findings=findings)
