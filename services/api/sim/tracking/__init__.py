"""Tracking and fusion (wave 4b): turn sensor reports into tracks that fail the way real ones do.

The tracker's only input is a `Measurement` built from `Detection.trainee_view()`. See
docs/SENSOR_MODELS.md ("Tracking") for the error model and its parameters. `Picture`
(`picture.py`) puts the sensors, tracker, ground-truth ledger and AI assist into a `World`.
"""

from . import commands, cueing
from .ambiguity import ErrorModel, ErrorPolicy
from .assist import (
    NON_THREAT_CLASSES,
    AiAssist,
    Assessment,
    AssistConfig,
    TruthRef,
    is_threat,
    keyed_uniform,
)
from .associate import AmbiguityPolicy, Component, NominalPolicy, Pair, Resolution
from .commands import CommandOutcome
from .config import CHI2_GATE, TrackerConfig
from .cueing import CueOutcome
from .ledger import ERROR_KINDS, TRUTH_EVENT_KINDS, LedgerEvent, TruthLedger
from .measurement import Measurement, MeasurementError
from .track import Track
from .tracker import Ambiguity, Association, Tracker, TrackEvent, UpdateResult

__all__ = [
    "CHI2_GATE",
    "ERROR_KINDS",
    "NON_THREAT_CLASSES",
    "TRUTH_EVENT_KINDS",
    "AiAssist",
    "Ambiguity",
    "AmbiguityPolicy",
    "Assessment",
    "AssistConfig",
    "Association",
    "CommandOutcome",
    "Component",
    "CueOutcome",
    "ErrorModel",
    "ErrorPolicy",
    "LedgerEvent",
    "Measurement",
    "MeasurementError",
    "NominalPolicy",
    "Pair",
    "Resolution",
    "Track",
    "TrackEvent",
    "Tracker",
    "TrackerConfig",
    "TruthLedger",
    "TruthRef",
    "UpdateResult",
    "commands",
    "cueing",
    "is_threat",
    "keyed_uniform",
]
