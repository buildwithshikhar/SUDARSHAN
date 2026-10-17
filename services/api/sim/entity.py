"""Simulation entities. Wave 3 has one kind: a drone flying a scripted route.

The trainee-facing fields (designated, assigned class and identity) record what the trainee has
said about the contact. They never feed back into the drone's motion.
"""

from dataclasses import asdict, dataclass
from typing import Any, Literal

from app.contracts.scenario import Threat

from .detmath import heading_vector

Status = Literal["pending", "active", "despawned"]
Mode = Literal["route", "hold", "loiter"]


@dataclass(slots=True)
class Drone:
    id: str
    status: Status
    x: float
    y: float
    z: float
    #: Unit vector of the air heading, (east, north).
    ux: float
    uy: float
    airspeed: float
    vz: float
    leg: int
    mode: Mode
    hold_ticks_left: int
    designated: bool = False
    assigned_class: str | None = None
    assigned_identity: str | None = None

    @classmethod
    def pending(cls, threat: Threat) -> "Drone":
        ux, uy = heading_vector(threat.start_heading_deg)
        return cls(
            id=threat.id,
            status="pending",
            x=threat.start.x,
            y=threat.start.y,
            z=threat.start.z,
            ux=ux,
            uy=uy,
            airspeed=threat.start_speed_mps,
            vz=0.0,
            leg=0,
            mode="route",
            hold_ticks_left=0,
        )

    def to_state(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> "Drone":
        return cls(**state)
