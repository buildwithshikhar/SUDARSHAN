"""The live protocol on the wire: MessagePack encoding, the server's messages and the checks on a
trainee's actions.

Frames are built as plain dicts (no Pydantic on the 20 Hz path); the tests validate every message
type against the `live-server.v1` models and the exported JSON Schema, which is what keeps these
builders honest.
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, get_args

import msgpack  # type: ignore[import-untyped]

from app.contracts import TICK_HZ, EventRecord
from app.contracts.live import ACTION_KEYS, OperatorAction
from app.contracts.scenario import ScenarioSpec
from sim.audience import trainee_event
from sim.roe import OPERATOR_CLASSES, RuleEngine
from sim.tracking.picture import DATA_NOTICE
from sim.world import IDENTITIES, World

#: The largest message a client may send, in bytes.
MAX_CLIENT_FRAME = 16 * 1024
ACTIONS: tuple[str, ...] = get_args(OperatorAction)
#: Keys a payload may omit; every other key of an action is required.
OPTIONAL_KEYS = frozenset({"exchange", "narrow"})
_BOOLEAN_KEYS = frozenset({"exchange", "narrow"})
_TEXT_MAX = 64


def pack(message: Mapping[str, Any]) -> bytes:
    data: bytes = msgpack.packb(message, use_bin_type=True)
    return data


def unpack(data: bytes) -> Any:
    """Decode one client message; raises `ValueError` for anything that is not MessagePack."""
    try:
        return msgpack.unpackb(data, raw=False, strict_map_key=True)
    except Exception as error:  # msgpack raises several unrelated types for bad input
        raise ValueError("not a MessagePack message") from error


# ----------------------------------------------------------------------------- actions


def check_payload(action: str, payload: object) -> str | None:
    """Why a client's action payload is refused, or `None` when it is well formed.

    Only the keys listed for the action in `ACTION_KEYS` are allowed, each of the right JSON type.
    A client can name a track, never a drone: `target` is not a key of any action.
    """
    allowed = ACTION_KEYS.get(action)
    if allowed is None:
        return f"unknown action {action!r}"
    if not isinstance(payload, dict):
        return "the payload must be a map"
    extra = sorted(str(k) for k in payload if k not in allowed)
    if extra:
        return f"{action} does not take {', '.join(extra)}"
    missing = [k for k in allowed if k not in payload and k not in OPTIONAL_KEYS]
    if missing:
        return f"{action} needs {', '.join(missing)}"
    for key, value in payload.items():
        if key in _BOOLEAN_KEYS:
            if not isinstance(value, bool):
                return f"{key} must be true or false"
        elif key == "tracks":
            if (
                not isinstance(value, list)
                or len(value) != 2
                or not all(isinstance(v, str) and 0 < len(v) <= _TEXT_MAX for v in value)
            ):
                return "tracks must be a list of two track ids"
        elif not isinstance(value, str) or not 0 < len(value) <= _TEXT_MAX:
            return f"{key} must be text of 1 to {_TEXT_MAX} characters"
    return None


# ----------------------------------------------------------------------------- server messages


def briefing(spec: ScenarioSpec, modalities: Mapping[str, str]) -> dict[str, Any]:
    """The scenario as the operator is briefed. Built field by field so that nothing about the
    threats can be added by accident."""
    weather = spec.world.weather
    return {
        "id": spec.id,
        "version": spec.version,
        "title": spec.title.model_dump(),
        "summary": spec.summary.model_dump(),
        "duration_s": spec.duration_s,
        "start_time_of_day_h": spec.world.start_time_of_day_h,
        "half_extent_m": spec.world.half_extent_m,
        "weather": {
            "condition": weather.condition,
            "visibility_m": weather.visibility_m,
            "wind_speed_mps": weather.wind_speed_mps,
            "wind_from_deg": weather.wind_from_deg,
            "temperature_c": weather.temperature_c,
            "cloud_cover_pct": weather.cloud_cover_pct,
        },
        "zones": [z.model_dump(mode="json") for z in spec.zones],
        "assets": [a.model_dump(mode="json") for a in spec.assets],
        "sensors": [
            {
                "id": s.id,
                "profile": s.profile.id,
                "modality": modalities[s.id],
                "position": s.position.model_dump(),
                "boresight_deg": s.boresight_deg,
            }
            for s in spec.sensors
        ],
        "filed_flights": [f.model_dump(mode="json") for f in spec.filed_flights],
    }


def welcome(session_id: str, status: str, world: World, engine: RuleEngine) -> dict[str, Any]:
    picture = world.picture
    assert picture is not None
    modalities = {s.id: s.params.modality for s in picture.suite.sensors}
    return {
        "t": "welcome",
        "protocol": 1,
        "session_id": session_id,
        "status": status,
        "tick_hz": TICK_HZ,
        "tick": world.tick,
        "briefing": briefing(world.spec, modalities),
        "rules": engine.summary(),
        "operator_classes": list(OPERATOR_CLASSES),
        "identities": list(IDENTITIES),
        "actions": list(ACTIONS),
        "data_notice": DATA_NOTICE,
    }


def trainee_events(records: Iterable[EventRecord]) -> list[dict[str, Any]]:
    """The events a trainee may see, from a run of log records."""
    return [e for e in map(trainee_event, records) if e is not None]


def frame(world: World, status: str, records: Sequence[EventRecord]) -> dict[str, Any]:
    """One tick as the operator's sensors and tracker saw it, plus the new trainee events."""
    picture = world.picture
    assert picture is not None
    message = picture.trainee_frame(world.tick)
    message["t"] = "frame"
    message["time_s"] = world.time_s
    message["time_of_day_h"] = world.time_of_day_h
    message["status"] = status
    message["events"] = trainee_events(records)
    return message


def ack(
    seq: int, tick: int | None = None, *, error: tuple[str, str] | None = None
) -> dict[str, Any]:
    if error is None:
        return {"t": "ack", "seq": seq, "ok": True, "tick": tick}
    return {
        "t": "ack",
        "seq": seq,
        "ok": False,
        "tick": tick,
        "error": {"code": error[0], "message": error[1]},
    }


def fault(code: str, message: str) -> dict[str, Any]:
    return {"t": "error", "code": code, "message": message}
