"""Tracking and fusion (wave 4b): turn sensor reports into tracks that fail the way real ones do.

The tracker's only input is a `Measurement` built from `Detection.trainee_view()`. See
docs/SENSOR_MODELS.md ("Tracking") for the error model and its parameters.
"""

from .associate import AmbiguityPolicy, Component, NominalPolicy, Pair, Resolution
from .config import CHI2_GATE, TrackerConfig
from .measurement import Measurement, MeasurementError
from .track import Track
from .tracker import Ambiguity, Association, Tracker, TrackEvent, UpdateResult

__all__ = [
    "CHI2_GATE",
    "Ambiguity",
    "AmbiguityPolicy",
    "Association",
    "Component",
    "Measurement",
    "MeasurementError",
    "NominalPolicy",
    "Pair",
    "Resolution",
    "Track",
    "TrackEvent",
    "Tracker",
    "TrackerConfig",
    "UpdateResult",
]
