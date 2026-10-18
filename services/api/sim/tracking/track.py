"""A track: a filtered estimate with a lifecycle, and the view a trainee gets of it."""

import math
from dataclasses import dataclass, field
from typing import Any, Literal

from .. import detmath
from ..sensors.detection import DATA_REFERENCE, DATA_VERIFIED
from . import kalman

Status = Literal["tentative", "confirmed", "coasting"]


@dataclass(slots=True)
class Track:
    id: str
    #: What the operator calls this track. Starts as the id; `relabel` changes it.
    label: str
    status: Status
    born: int
    #: Tick of the last associated report.
    last_update: int
    #: Tick the state was last predicted to.
    last_predict: int
    #: Ticks on which at least one report was associated.
    hit_ticks: int
    x: list[float]
    p: list[list[float]]
    votes: dict[str, int] = field(default_factory=dict)
    sensors: list[str] = field(default_factory=list)
    data_status: str = DATA_REFERENCE
    last_hit_tick: int = -1

    def note_report(
        self, tick: int, sensor_id: str, reported_class: str | None, status: str
    ) -> None:
        """Book-keeping when a report is associated (the filter update is separate)."""
        if tick != self.last_hit_tick:
            self.hit_ticks += 1
            self.last_hit_tick = tick
        self.last_update = tick
        if sensor_id not in self.sensors:
            self.sensors = sorted([*self.sensors, sensor_id])
        if reported_class is not None and reported_class != "unknown":
            self.votes[reported_class] = self.votes.get(reported_class, 0) + 1
        # Reference data stays reference data: one unverified input taints the estimate.
        if status != DATA_VERIFIED:
            self.data_status = DATA_REFERENCE

    def class_estimate(self) -> tuple[str | None, float]:
        """Most-voted reported class and its share of the votes (ties go to the name first)."""
        total = sum(self.votes.values())
        if total == 0:
            return None, 0.0
        best = sorted(self.votes.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        return best[0], best[1] / total

    def clone(self, new_id: str) -> "Track":
        return Track(
            id=new_id,
            label=new_id,
            status=self.status,
            born=self.born,
            last_update=self.last_update,
            last_predict=self.last_predict,
            hit_ticks=self.hit_ticks,
            x=self.x[:],
            p=[row[:] for row in self.p],
            votes=dict(self.votes),
            sensors=list(self.sensors),
            data_status=self.data_status,
            last_hit_tick=self.last_hit_tick,
        )

    def view(self, tick: int, tick_hz: int) -> dict[str, Any]:
        """What a trainee's console shows: the estimate and its uncertainty, never the truth."""
        vx, vy = self.x[3], self.x[4]
        cls, share = self.class_estimate()
        return {
            "id": self.id,
            "label": self.label,
            "status": self.status,
            "tick": tick,
            "age_s": _r((tick - self.born) / tick_hz),
            "since_update_s": _r((tick - self.last_update) / tick_hz),
            "hits": self.hit_ticks,
            "position": {"x": _r(self.x[0]), "y": _r(self.x[1]), "z": _r(self.x[2])},
            "velocity": {"x": _r(vx), "y": _r(vy), "z": _r(self.x[5])},
            "speed_mps": _r(math.sqrt(vx * vx + vy * vy + self.x[5] * self.x[5])),
            "heading_deg": _r(detmath.wrap360(detmath.atan2(vx, vy) / detmath.DEG)),
            "sigma_position_m": _r(kalman.position_sigma(self.p)),
            "sigma_speed_mps": _r(kalman.speed_sigma(self.p)),
            "class_estimate": cls,
            "class_support": _r(share),
            "sensors": list(self.sensors),
            "data_status": self.data_status,
        }

    def to_state(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "status": self.status,
            "born": self.born,
            "last_update": self.last_update,
            "last_predict": self.last_predict,
            "hit_ticks": self.hit_ticks,
            "x": self.x,
            "p": self.p,
            "votes": dict(sorted(self.votes.items())),
            "sensors": list(self.sensors),
            "data_status": self.data_status,
            "last_hit_tick": self.last_hit_tick,
        }

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> "Track":
        return cls(
            id=state["id"],
            label=state["label"],
            status=state["status"],
            born=state["born"],
            last_update=state["last_update"],
            last_predict=state["last_predict"],
            hit_ticks=state["hit_ticks"],
            x=list(state["x"]),
            p=[list(row) for row in state["p"]],
            votes=dict(state["votes"]),
            sensors=list(state["sensors"]),
            data_status=state["data_status"],
            last_hit_tick=state["last_hit_tick"],
        )


def _r(value: float) -> float:
    return round(value, 3)
