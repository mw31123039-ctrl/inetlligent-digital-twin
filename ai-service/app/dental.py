"""Shared local dental photograph input validation."""
import base64
import binascii
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DentalPhoto(BaseModel):
    model_config = ConfigDict(extra='forbid')
    view: Literal['Frontal bite', 'Right bite', 'Left bite', 'Upper arch', 'Lower arch', 'Smile / profile']
    data_url: str = Field(max_length=350000)

    @model_validator(mode='after')
    def valid_photo(self):
        prefix = 'data:image/jpeg;base64,'
        if not self.data_url.startswith(prefix):
            raise ValueError('Use a locally re-encoded JPEG photo.')
        try:
            raw = base64.b64decode(self.data_url[len(prefix):], validate=True)
        except (ValueError, binascii.Error):
            raise ValueError('Invalid photo encoding.') from None
        if not raw.startswith(b'\xff\xd8\xff') or len(raw) < 100 or not raw.endswith(b'\xff\xd9'):
            raise ValueError('Invalid JPEG photo.')
        return self
