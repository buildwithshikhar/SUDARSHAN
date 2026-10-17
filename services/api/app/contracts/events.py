"""Event log, action log and session record contracts.

An event record is `{seq, t, type, actor, payload, prev_hash, hash}`; `hash` is the SHA-256 of
the canonical JSON of the other six fields, and `prev_hash` chains it to the record before.
"""

from typing import Annotated, Literal

from pydantic import Field, JsonValue, StringConstraints

from .common import Contract, PackRef, Seed, Sha256Hex
from .rulepack import Action

Actor = Annotated[
    str, StringConstraints(pattern=r"^(sim|system|(trainee|instructor):[a-z0-9]+(?:-[a-z0-9]+)*)$")
]
EventType = Annotated[str, StringConstraints(pattern=r"^[a-z]+(\.[a-z_]+)+$", max_length=64)]
Payload = dict[str, JsonValue]

GENESIS_HASH = "0" * 64


class EventRecord(Contract):
    seq: Annotated[int, Field(ge=0)]
    #: Simulation time in seconds (tick / tick rate), never wall-clock time.
    t: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    type: EventType
    actor: Actor
    payload: Payload
    prev_hash: Sha256Hex
    hash: Sha256Hex


class ActionRecord(Contract):
    """A trainee or instructor input, applied at the start of `tick`."""

    tick: Annotated[int, Field(ge=0)]
    actor: Actor
    action: Action | Literal["pause", "resume", "set-weather"]
    payload: Payload = {}


class SessionRecord(Contract):
    """Everything needed to replay a session and check the replay matches."""

    contract: Literal["session-record.v1"]
    scenario: PackRef
    seed: Seed
    ticks: Annotated[int, Field(ge=0)]
    actions: list[ActionRecord]
    events: list[EventRecord]
    final_state_hash: Sha256Hex
