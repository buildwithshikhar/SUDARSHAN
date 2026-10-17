"""Versioned contracts shared by the API, the sim core and (as generated types) the web app.

Pure Pydantic: nothing here imports FastAPI or the database.
"""

from pydantic import BaseModel

from .events import GENESIS_HASH, ActionRecord, EventRecord, SessionRecord
from .rulepack import RulePack
from .scenario import TICK_HZ, ScenarioSpec
from .sensor_profile import SensorProfile

#: Exported JSON Schemas, by file stem in packs/schemas/.
SCHEMAS: dict[str, type[BaseModel]] = {
    "scenario.v1": ScenarioSpec,
    "rulepack.v1": RulePack,
    "sensor-profile.v1": SensorProfile,
    "event-record.v1": EventRecord,
    "action-record.v1": ActionRecord,
    "session-record.v1": SessionRecord,
}

#: Pack contracts, keyed by the value of their `contract` field.
PACKS: dict[str, type[ScenarioSpec | RulePack | SensorProfile]] = {
    "scenario.v1": ScenarioSpec,
    "rulepack.v1": RulePack,
    "sensor-profile.v1": SensorProfile,
}

__all__ = [
    "GENESIS_HASH",
    "PACKS",
    "SCHEMAS",
    "TICK_HZ",
    "ActionRecord",
    "EventRecord",
    "RulePack",
    "ScenarioSpec",
    "SensorProfile",
    "SessionRecord",
]
