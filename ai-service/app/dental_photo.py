"""Draft visible-crown localization for a clinician-corrected photo mock-up."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .dental import DentalPhoto

VISIBLE_CASE_IDS = {'crowding', 'spacing', 'diastema', 'deep-bite', 'anterior-open-bite', 'underbite', 'increased-overjet', 'anterior-crossbite', 'unilateral-posterior-crossbite', 'bilateral-posterior-crossbite', 'scissor-bite', 'midline-discrepancy', 'rotated-teeth', 'tooth-wear', 'gummy-smile', 'asymmetry'}


class PhotoPoint(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


def cross(a: PhotoPoint, b: PhotoPoint, c: PhotoPoint) -> float:
    return (b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x)


class CrownOutline(BaseModel):
    model_config = ConfigDict(extra='forbid')
    jaw: Literal['upper', 'lower', 'unknown']
    points: list[PhotoPoint] = Field(min_length=4, max_length=12)

    @model_validator(mode='after')
    def valid_polygon(self):
        points = self.points
        area = abs(sum(p.x*points[(i+1) % len(points)].y-points[(i+1) % len(points)].x*p.y for i, p in enumerate(points)))/2
        if not .00001 <= area <= .8:
            raise ValueError('Degenerate or oversized crown outline.')
        for i in range(len(points)):
            for j in range(i+1, len(points)):
                if j == i+1 or (i == 0 and j == len(points)-1):
                    continue
                a, b, c, d = points[i], points[(i+1) % len(points)], points[j], points[(j+1) % len(points)]
                if cross(a, b, c)*cross(a, b, d) < 0 and cross(c, d, a)*cross(c, d, b) < 0:
                    raise ValueError('Self-intersecting crown outline.')
        return self


class PhotoOutlineDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    image_quality: Literal['usable', 'insufficient', 'unsupported_view']
    crowns: list[CrownOutline] = Field(max_length=32)
    possible_case_ids: list[str] = Field(max_length=3)

    @model_validator(mode='after')
    def valid_evidence(self):
        if any(item not in VISIBLE_CASE_IDS for item in self.possible_case_ids) or len(set(self.possible_case_ids)) != len(self.possible_case_ids):
            raise ValueError('Unsupported photo-only discussion topic.')
        if self.image_quality != 'usable' and (self.crowns or self.possible_case_ids):
            raise ValueError('An unusable image cannot have accepted findings.')
        if self.image_quality == 'usable' and not self.crowns:
            raise ValueError('A usable image must contain a visible crown outline.')
        return self


class PhotoDetectionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    photo: DentalPhoto
    consent_local: Literal[True]


class PhotoDetectionResult(PhotoOutlineDecision):
    mode: Literal['photo-outline-draft']
    input_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    clinical_validation: Literal[False]
    geometry_dimensions: Literal['2d-visible-crowns']
