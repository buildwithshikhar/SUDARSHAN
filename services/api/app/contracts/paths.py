"""Where the packs live: `packs/` in a source checkout, `/app/packs` in the production image.

`PACKS_DIR` overrides the search (used by tests and by an operator who mounts packs elsewhere).
"""

import os
from pathlib import Path


def packs_root() -> Path:
    override = os.environ.get("PACKS_DIR")
    if override:
        return Path(override)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "packs"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("packs/ not found; set PACKS_DIR")
