"""Sensor framework: detection models run against the sim's ground truth.

Sensors read the world and produce noisy detections; they never change it. The interface is in
`base`, shared degradation and cue handling in `degradation` and `cue`, profile loading in
`profile`. The four modality models (radar, EO/IR, RF, acoustic) register themselves on import
below. See docs/SIM_CORE.md (sensor framework) and docs/SENSOR_MODELS.md.
"""

from .base import Observation, Sensor
from .confusion import ConfusionMatrix
from .cue import DEFAULT_CUE_HOLD_S, CueRequest, CueResult, Pointing
from .degradation import KINDS, Degradation, Effects
from .detection import DRAWS_PER_CANDIDATE, Detection, Draws
from .geometry import Environment, Geometry, Truth
from .profile import (
    ProfileError,
    SensorParams,
    load_sensor_profile,
    register_ids,
    resolve_profile,
)
from .suite import MODELS, SensorSuite, build_sensors, default_profile_dir, register_model

# Imported last: each module registers its model with `register_model`.
from . import acoustic, eoir, radar, rf  # isort: skip  # noqa: E402,I001

__all__ = [
    "acoustic",
    "eoir",
    "radar",
    "rf",
    "DEFAULT_CUE_HOLD_S",
    "DRAWS_PER_CANDIDATE",
    "KINDS",
    "MODELS",
    "ConfusionMatrix",
    "CueRequest",
    "CueResult",
    "Degradation",
    "Detection",
    "Draws",
    "Effects",
    "Environment",
    "Geometry",
    "Observation",
    "Pointing",
    "ProfileError",
    "Sensor",
    "SensorParams",
    "SensorSuite",
    "Truth",
    "build_sensors",
    "default_profile_dir",
    "load_sensor_profile",
    "register_ids",
    "register_model",
    "resolve_profile",
]
