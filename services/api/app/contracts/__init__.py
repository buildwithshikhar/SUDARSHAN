"""Versioned contracts shared by the API, the sim core and (as generated types) the web app.

Pure Pydantic: nothing here imports FastAPI or the database.
"""

from pydantic import BaseModel

from .events import GENESIS_HASH, ActionRecord, EventRecord, SessionRecord
from .live import LiveClientMessage, LiveServerMessage
from .rulepack import RulePack
from .scenario import TICK_HZ, ScenarioSpec
from .score import SessionScore
from .sensor_profile import SensorProfile
from .threat_class import ThreatClass

#: Exported JSON Schemas, by file stem in packs/schemas/.
SCHEMAS: dict[str, type[BaseModel]] = {
    "scenario.v1": ScenarioSpec,
    "rulepack.v1": RulePack,
    "sensor-profile.v1": SensorProfile,
    "threat-class.v1": ThreatClass,
    "event-record.v1": EventRecord,
    "action-record.v1": ActionRecord,
    "session-record.v1": SessionRecord,
    "live-client.v1": LiveClientMessage,
    "live-server.v1": LiveServerMessage,
    "score-result.v1": SessionScore,
}

#: Pack contracts, keyed by the value of their `contract` field.
PACKS: dict[str, type[ScenarioSpec | RulePack | SensorProfile | ThreatClass]] = {
    "scenario.v1": ScenarioSpec,
    "rulepack.v1": RulePack,
    "sensor-profile.v1": SensorProfile,
    "threat-class.v1": ThreatClass,
}

__all__ = [
    "GENESIS_HASH",
    "PACKS",
    "SCHEMAS",
    "TICK_HZ",
    "ActionRecord",
    "EventRecord",
    "LiveClientMessage",
    "LiveServerMessage",
    "RulePack",
    "ScenarioSpec",
    "SensorProfile",
    "SessionRecord",
    "SessionScore",
    "ThreatClass",
]
