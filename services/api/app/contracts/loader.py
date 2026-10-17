"""Load pack files (YAML or JSON) into contract models.

The YAML loader is safe-only and rejects duplicate keys, which plain `yaml.safe_load` would
silently overwrite.
"""

import json
from pathlib import Path
from typing import Any

import yaml

from . import PACKS
from .rulepack import RulePack
from .scenario import ScenarioSpec
from .sensor_profile import SensorProfile

Pack = ScenarioSpec | RulePack | SensorProfile


class PackError(ValueError):
    pass


class _StrictLoader(yaml.SafeLoader):
    pass


def _mapping(loader: _StrictLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in result:
            raise PackError(f"duplicate key {key!r} at line {key_node.start_mark.line + 1}")
        result[key] = loader.construct_object(value_node)
    return result


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PackError(f"duplicate key {key!r}")
        result[key] = value
    return result


def parse_text(text: str, suffix: str) -> Any:
    if suffix in {".yaml", ".yml"}:
        return yaml.load(text, Loader=_StrictLoader)  # noqa: S506 - strict SafeLoader subclass
    if suffix == ".json":
        return json.loads(text, object_pairs_hook=_reject_duplicates)
    raise PackError(f"unsupported pack file type {suffix!r}")


def load_pack(path: Path) -> Pack:
    """Read and validate one pack; the `contract` field selects the model."""
    data = parse_text(path.read_text(encoding="utf-8"), path.suffix)
    if not isinstance(data, dict):
        raise PackError(f"{path.name}: a pack must be a mapping")
    model = PACKS.get(str(data.get("contract")))
    if model is None:
        raise PackError(f"{path.name}: unknown contract {data.get('contract')!r}")
    return model.model_validate(data)
