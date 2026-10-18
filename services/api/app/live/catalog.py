"""The scenarios a trainee can play: those whose sensors and rules load."""

import logging
import threading
from dataclasses import dataclass
from pathlib import Path

from app.contracts.loader import load_pack
from app.contracts.paths import packs_root
from app.contracts.scenario import ScenarioSpec
from sim.roe import RuleEngine, load_rule_engine
from sim.tracking.picture import Picture

log = logging.getLogger("app.live")


@dataclass(frozen=True)
class CatalogEntry:
    spec: ScenarioSpec
    #: The rule engine is a pure function of the pack, so sessions share it.
    engine: RuleEngine
    #: Sensor modality by sensor ID, for the briefing.
    modalities: dict[str, str]


class ScenarioCatalog:
    """Parses the scenario files once and keeps the playable ones."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root
        self._entries: dict[str, CatalogEntry] | None = None
        self._lock = threading.Lock()

    def _load(self) -> dict[str, CatalogEntry]:
        root = self._root or packs_root() / "scenarios"
        found: dict[str, CatalogEntry] = {}
        for path in sorted([*root.glob("*.json"), *root.glob("*.yaml")]):
            try:
                spec = load_pack(path)
                if not isinstance(spec, ScenarioSpec):
                    continue
                engine = load_rule_engine(spec)
                picture = Picture.build(spec, spec.default_seed)  # the sensors must load
            except Exception as error:  # noqa: BLE001 - an unplayable scenario is only not listed
                log.warning("scenario %s is not playable: %r", path.name, error)
                continue
            found[spec.id] = CatalogEntry(
                spec, engine, {s.id: s.params.modality for s in picture.suite.sensors}
            )
        return found

    def entries(self) -> dict[str, CatalogEntry]:
        with self._lock:
            if self._entries is None:
                self._entries = self._load()
            return self._entries

    def get(self, scenario_id: str, version: str | None = None) -> CatalogEntry | None:
        entry = self.entries().get(scenario_id)
        if entry is not None and version is not None and entry.spec.version != version:
            return None
        return entry
