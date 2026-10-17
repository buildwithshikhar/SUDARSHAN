"""Export the contract JSON Schemas to packs/schemas/.

python -m app.contracts.export          write the schema files
python -m app.contracts.export --check  exit 1 if any file differs from the models
"""

import json
import sys
from pathlib import Path
from typing import Any

from . import SCHEMAS

SCHEMA_DIR = Path(__file__).resolve().parents[4] / "packs" / "schemas"
DIALECT = "https://json-schema.org/draft/2020-12/schema"


def render(name: str) -> str:
    schema: dict[str, Any] = {
        "$schema": DIALECT,
        "$id": f"{name}.json",
        **SCHEMAS[name].model_json_schema(mode="validation"),
    }
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def stale(directory: Path = SCHEMA_DIR) -> list[str]:
    """File names that are missing, differ from the models, or no longer have a model."""
    out = [
        f"{name}.json"
        for name in SCHEMAS
        if not (directory / f"{name}.json").is_file()
        or (directory / f"{name}.json").read_text(encoding="utf-8") != render(name)
    ]
    known = {f"{name}.json" for name in SCHEMAS}
    out += sorted(p.name for p in directory.glob("*.json") if p.name not in known)
    return out


def write(directory: Path = SCHEMA_DIR) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in SCHEMAS:
        (directory / f"{name}.json").write_text(render(name), encoding="utf-8")


def main(argv: list[str]) -> int:
    if "--check" in argv:
        bad = stale()
        if bad:
            print("schemas out of date: " + ", ".join(bad), file=sys.stderr)
            print("run `make schemas` and commit packs/schemas/", file=sys.stderr)
            return 1
        print(f"{len(SCHEMAS)} schemas up to date")
        return 0
    write()
    print(f"wrote {len(SCHEMAS)} schemas to {SCHEMA_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
