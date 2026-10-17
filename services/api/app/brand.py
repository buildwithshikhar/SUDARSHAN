"""Product identity, read from brand.json. The name is never hard-coded elsewhere."""

import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel


class Brand(BaseModel):
    productName: str  # noqa: N815 - mirrors the brand.json keys
    descriptor: str
    status: str


def _locate() -> Path:
    override = os.environ.get("BRAND_FILE")
    if override:
        return Path(override)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "brand.json"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("brand.json not found; set BRAND_FILE")


@lru_cache(maxsize=1)
def load_brand() -> Brand:
    return Brand.model_validate(json.loads(_locate().read_text(encoding="utf-8")))
