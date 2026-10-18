"""The tracker: fuses the sensors' reports into tracks.

Input is `Measurement`s built from `Detection.trainee_view()`; the tracker never sees a ground-truth
reference. Each call to `update` does, in order:

1. predict every track to the tick;
2. for each sensor's batch of reports, in order of first appearance: gate every (track, report)
   pair, group the pairs into components, resolve each component (unambiguous ones directly,
   ambiguous ones through the `AmbiguityPolicy`), update the paired tracks with sequential scalar
   Kalman updates, and start tentative tracks from range reports that fell outside every gate;
3. pair bearing-only reports that no track claimed across sensors (triangulation);
4. run the lifecycle: confirm, coast, resume, drop, and fold duplicate tracks together.

Exactly one uniform is taken from the `tracking` stream per report, whatever happens to it, so an
unrelated outage cannot shift the numbers a later ambiguity receives.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contracts import TICK_HZ
from app.contracts.common import Vec3

from .. import detmath
from ..rng import RngStreams
from . import kalman
from .associate import (
    AmbiguityPolicy,
    Component,
    NominalPolicy,
    Pair,
    Resolution,
    check,
    components,
)
from .config import CHI2_GATE, TrackerConfig
from .measurement import Measurement, MeasurementError
from .model import Row, polar_to_enu, ray, rows_for
from .track import Track

STREAM = "tracking"
DEG = detmath.DEG


@dataclass(frozen=True, slots=True)
class TrackEvent:
    """A change in a track's life. Ground-truth free: it is what the tracker itself knows."""

    kind: str  # init, confirm, coast, resume, drop
    track_id: str
    tick: int
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Association:
    """A report that was used by a track (updated it, or started it). For the truth ledger."""

    track_id: str
    ref: int
    sensor_id: str


@dataclass(frozen=True, slots=True)
class Ambiguity:
    """An ambiguous component and how it was resolved (ledger and instructor, not trainees)."""

    tick: int
    sensor_id: str
    mode: str
    tracks: tuple[str, ...]
    refs: tuple[int, ...]


@dataclass(slots=True)
class UpdateResult:
    events: list[TrackEvent] = field(default_factory=list)
    associations: list[Association] = field(default_factory=list)
    ambiguities: list[Ambiguity] = field(default_factory=list)


class Tracker:
    def __init__(
        self,
        sensors: Mapping[str, Vec3],
        *,
        config: TrackerConfig | None = None,
        policy: AmbiguityPolicy | None = None,
        tick_hz: int = TICK_HZ,
    ) -> None:
        self.cfg = config or TrackerConfig()
        self.policy: AmbiguityPolicy = policy or NominalPolicy()
        self.tick_hz = tick_hz
        self.sensor_positions = dict(sensors)
        #: Live tracks (tentative, confirmed, coasting) by id, in id order.
        self.tracks: dict[str, Track] = {}
        #: Dropped tracks: id -> {tick, reason, merged_into}.
        self.graveyard: dict[str, dict[str, Any]] = {}
        self._next = 1
        self._orphans: list[Measurement] = []
        self._close: dict[str, int] = {}
        self._tick: int | None = None

    # ------------------------------------------------------------------ public helpers

    def allocate_id(self) -> str:
        track_id = f"T{self._next:03d}"
        self._next += 1
        return track_id

    def insert(self, track: Track) -> None:
        """Add a track (used by commands that clone one); keeps `tracks` in id order."""
        if track.id in self.tracks or track.id in self.graveyard:
            raise ValueError(f"track id {track.id} is already used")
        self.tracks[track.id] = track
        self.tracks = dict(sorted(self.tracks.items()))

    def drop(
        self, track_id: str, tick: int, reason: str, merged_into: str | None = None
    ) -> TrackEvent:
        track = self.tracks.pop(track_id)
        self.graveyard[track.id] = {"tick": tick, "reason": reason, "merged_into": merged_into}
        payload: dict[str, Any] = {
            "track": track.id,
            "reason": reason,
            "age_s": self._secs(tick - track.born),
        }
        if merged_into is not None:
            payload["merged_into"] = merged_into
        return TrackEvent("drop", track.id, tick, payload)

    def views(self, tick: int) -> list[dict[str, Any]]:
        return [t.view(tick, self.tick_hz) for t in self.tracks.values()]

    # ------------------------------------------------------------------ the update

    def update(
        self, tick: int, measurements: Sequence[Measurement], rng: RngStreams
    ) -> UpdateResult:
        if self._tick is not None and tick < self._tick:
            raise ValueError(f"tracker was already advanced to tick {self._tick}")
        batches: dict[str, list[int]] = {}
        for i, m in enumerate(measurements):
            if m.tick != tick:
                raise MeasurementError(
                    f"report from {m.sensor_id} is for tick {m.tick}, not {tick}"
                )
            if m.sensor_id not in self.sensor_positions:
                raise MeasurementError(f"report from unknown sensor {m.sensor_id!r}")
            batches.setdefault(m.sensor_id, []).append(i)
        result = UpdateResult()
        self._predict_all(tick)
        for sensor_id, indices in batches.items():
            self._associate(tick, sensor_id, indices, measurements, rng, result)
        self._triangulate(tick, result)
        self._lifecycle(tick, result)
        self._tick = tick
        return result

    def _predict_all(self, tick: int) -> None:
        for track in self.tracks.values():
            dt = (tick - track.last_predict) / self.tick_hz
            if dt < 0:
                raise ValueError(f"track {track.id} is ahead of tick {tick}")
            kalman.predict(track.x, track.p, dt, self.cfg.accel_sigma_mps2)
            track.last_predict = tick

    # ------------------------------------------------------------------ association

    def _associate(
        self,
        tick: int,
        sensor_id: str,
        indices: list[int],
        measurements: Sequence[Measurement],
        rng: RngStreams,
        result: UpdateResult,
    ) -> None:
        draws = {i: rng.uniform(STREAM) for i in indices}
        origin = self.sensor_positions[sensor_id]
        gated: list[Pair] = []
        rows_of: dict[tuple[str, int], list[Row]] = {}
        for i in indices:
            m = measurements[i]
            for track in self.tracks.values():
                rows = rows_for(m, origin, track.x, self.cfg)
                cost = self._cost(track, rows)
                if cost <= CHI2_GATE[len(rows)] * self.cfg.gate_scale:
                    gated.append(Pair(track.id, i, cost))
                    rows_of[(track.id, i)] = rows
        claimed: set[int] = set()
        for comp in components(sensor_id, gated):
            resolution = (
                self.policy.resolve(comp, draws[comp.measurements[0]])
                if comp.ambiguous
                else Resolution("nominal", ((comp.nominal[0].track, comp.nominal[0].index),))
            )
            check(comp, resolution)
            if comp.ambiguous:
                result.ambiguities.append(
                    Ambiguity(
                        tick,
                        sensor_id,
                        resolution.mode,
                        comp.tracks,
                        tuple(measurements[i].ref for i in comp.measurements),
                    )
                )
            claimed.update(comp.measurements)
            for track_id, i in resolution.pairs:
                m = measurements[i]
                track = self.tracks[track_id]
                self._apply(track, rows_of[(track_id, i)])
                track.note_report(tick, sensor_id, m.reported_class, m.data_status)
                result.associations.append(Association(track_id, m.ref, sensor_id))
            for i in resolution.spawn:
                self._start(tick, measurements[i], result)
        for i in indices:
            if i not in claimed:
                m = measurements[i]
                if m.has_range:
                    self._start(tick, m, result)
                else:
                    self._orphans.append(m)

    def _cost(self, track: Track, rows: list[Row]) -> float:
        total = 0.0
        for row in rows:
            total += (
                row.innovation * row.innovation / kalman.innovation_variance(track.p, row.h, row.r)
            )
        return total

    def _apply(self, track: Track, rows: list[Row]) -> None:
        """Sequential scalar updates, each innovation corrected for the state already moved."""
        prior = track.x[:]
        for row in rows:
            moved = 0.0
            for k in range(kalman.N):
                moved += row.h[k] * (track.x[k] - prior[k])
            kalman.update_scalar(track.x, track.p, row.h, row.innovation - moved, row.r)

    # ------------------------------------------------------------------ initiation

    def _start(self, tick: int, m: Measurement, result: UpdateResult) -> None:
        """A tentative track from a report that has a range."""
        assert m.range_m is not None and m.sigma_range_m is not None
        origin = self.sensor_positions[m.sensor_id]
        pos = polar_to_enu(origin, m.azimuth_deg, m.elevation_deg, m.range_m)
        sigma_range = max(m.sigma_range_m, self.cfg.min_sigma_range_m)
        sigma_az = max(m.sigma_azimuth_deg, self.cfg.min_sigma_angle_deg) * DEG
        sigma_el = max(m.sigma_elevation_deg, self.cfg.min_sigma_angle_deg) * DEG
        cross = m.range_m * max(sigma_az, sigma_el)
        track = self._birth(tick, pos, max(sigma_range, cross), m, result)
        if m.radial_speed_mps is not None:
            radial = [r for r in rows_for(m, origin, track.x, self.cfg) if r.kind == "radial"]
            self._apply(track, radial)

    def _birth(
        self, tick: int, pos: list[float], sigma: float, m: Measurement, result: UpdateResult
    ) -> Track:
        track_id = self.allocate_id()
        x = [pos[0], pos[1], pos[2], 0.0, 0.0, 0.0]
        p = kalman.zeros()
        v = self.cfg.init_speed_sigma_mps
        for i in range(3):
            p[i][i] = sigma * sigma
            p[i + 3][i + 3] = v * v
        track = Track(
            id=track_id,
            label=track_id,
            status="tentative",
            born=tick,
            last_update=tick,
            last_predict=tick,
            hit_ticks=0,
            x=x,
            p=p,
        )
        track.note_report(tick, m.sensor_id, m.reported_class, m.data_status)
        self.insert(track)
        result.associations.append(Association(track_id, m.ref, m.sensor_id))
        result.events.append(
            TrackEvent(
                "init",
                track_id,
                tick,
                {
                    "track": track_id,
                    "sensor": m.sensor_id,
                    "position": {"x": _r(x[0]), "y": _r(x[1]), "z": _r(x[2])},
                },
            )
        )
        return track

    def _triangulate(self, tick: int, result: UpdateResult) -> None:
        """Pair bearing-only reports across sensors into new tentative tracks."""
        cfg = self.cfg
        window = round(cfg.triangulation_window_s * self.tick_hz)
        self._orphans = [o for o in self._orphans if tick - o.tick <= window]
        if len(self._orphans) < 2:
            return
        min_sin = detmath.sin(cfg.triangulation_min_angle_deg * DEG)
        min_sin2 = min_sin * min_sin
        found: list[tuple[float, int, int, list[float], float]] = []
        for a in range(len(self._orphans)):
            for b in range(a + 1, len(self._orphans)):
                hit = self._intersect(self._orphans[a], self._orphans[b], min_sin2)
                if hit is not None:
                    found.append((hit[0], a, b, hit[1], hit[2]))
        used: set[int] = set()
        for _, a, b, pos, sigma in sorted(found, key=lambda f: (f[0], f[1], f[2])):
            if a in used or b in used:
                continue
            used.update((a, b))
            first, second = self._orphans[a], self._orphans[b]
            track = self._birth(tick, pos, sigma, first, result)
            track.note_report(tick, second.sensor_id, second.reported_class, second.data_status)
            result.associations.append(Association(track.id, second.ref, second.sensor_id))
        self._orphans = [o for k, o in enumerate(self._orphans) if k not in used]

    def _intersect(
        self, a: Measurement, b: Measurement, min_sin2: float
    ) -> tuple[float, list[float], float] | None:
        """Where two bearings nearly meet: (miss / tolerance, midpoint, position sigma), or None."""
        if a.sensor_id == b.sensor_id:
            return None
        cfg = self.cfg
        pa, pb = self.sensor_positions[a.sensor_id], self.sensor_positions[b.sensor_id]
        da, db = ray(a.azimuth_deg, a.elevation_deg), ray(b.azimuth_deg, b.elevation_deg)
        w = (pa.x - pb.x, pa.y - pb.y, pa.z - pb.z)
        cos_ab = da[0] * db[0] + da[1] * db[1] + da[2] * db[2]
        denom = 1.0 - cos_ab * cos_ab
        if denom < min_sin2:
            return None
        d = da[0] * w[0] + da[1] * w[1] + da[2] * w[2]
        e = db[0] * w[0] + db[1] * w[1] + db[2] * w[2]
        ta = (cos_ab * e - d) / denom
        tb = (e - cos_ab * d) / denom
        if not (
            0.0 < ta <= cfg.triangulation_max_range_m and 0.0 < tb <= cfg.triangulation_max_range_m
        ):
            return None
        qa = [pa.x + ta * da[0], pa.y + ta * da[1], pa.z + ta * da[2]]
        qb = [pb.x + tb * db[0], pb.y + tb * db[1], pb.z + tb * db[2]]
        miss = math.sqrt(sum_sq([qa[i] - qb[i] for i in range(3)]))
        sa = max(a.sigma_azimuth_deg, a.sigma_elevation_deg, cfg.min_sigma_angle_deg) * DEG
        sb = max(b.sigma_azimuth_deg, b.sigma_elevation_deg, cfg.min_sigma_angle_deg) * DEG
        spread = math.sqrt((ta * sa) * (ta * sa) + (tb * sb) * (tb * sb))
        motion = cfg.triangulation_speed_mps * abs(a.tick - b.tick) / self.tick_hz
        tolerance = cfg.triangulation_gate * spread + motion
        if miss > tolerance:
            return None
        mid = [(qa[i] + qb[i]) / 2.0 for i in range(3)]
        return miss / tolerance, mid, spread / math.sqrt(denom)

    # ------------------------------------------------------------------ lifecycle

    def _lifecycle(self, tick: int, result: UpdateResult) -> None:
        cfg, hz = self.cfg, self.tick_hz
        for track in list(self.tracks.values()):
            idle = (tick - track.last_update) / hz
            fresh = track.last_update == tick
            if track.status == "tentative":
                if (
                    track.hit_ticks >= cfg.confirm_hits
                    and (tick - track.born) / hz <= cfg.confirm_window_s
                ):
                    track.status = "confirmed"
                    result.events.append(
                        TrackEvent(
                            "confirm", track.id, tick, {"track": track.id, "hits": track.hit_ticks}
                        )
                    )
                elif (tick - track.born) / hz > cfg.confirm_window_s or idle > cfg.tentative_drop_s:
                    result.events.append(self.drop(track.id, tick, "unconfirmed"))
            elif track.status == "coasting":
                if fresh:
                    track.status = "confirmed"
                    result.events.append(
                        TrackEvent(
                            "resume", track.id, tick, {"track": track.id, "silent_s": _r(idle)}
                        )
                    )
                elif idle > cfg.drop_after_s:
                    result.events.append(self.drop(track.id, tick, "lost"))
            elif idle > cfg.coast_after_s:
                track.status = "coasting"
                result.events.append(
                    TrackEvent("coast", track.id, tick, {"track": track.id, "silent_s": _r(idle)})
                )
        self._fold_duplicates(tick, result)

    def _fold_duplicates(self, tick: int, result: UpdateResult) -> None:
        """Two confirmed tracks that stay statistically indistinguishable are one track."""
        hold = round(self.cfg.duplicate_hold_s * self.tick_hz)
        confirmed = [t for t in self.tracks.values() if t.status == "confirmed"]
        near: set[str] = set()
        for a in range(len(confirmed)):
            for b in range(a + 1, len(confirmed)):
                if self._same_target(confirmed[a], confirmed[b]):
                    near.add(f"{confirmed[a].id}|{confirmed[b].id}")
        self._close = {k: self._close.get(k, 0) + 1 for k in sorted(near)}
        for key in sorted(self._close):
            if self._close[key] < hold:
                continue
            older, younger = key.split("|")
            if older in self.tracks and younger in self.tracks:
                result.events.append(self.drop(younger, tick, "duplicate", merged_into=older))
        self._close = {
            k: v for k, v in self._close.items() if all(t in self.tracks for t in k.split("|"))
        }

    def _same_target(self, a: Track, b: Track) -> bool:
        """Position and velocity differ by no more than their summed uncertainty allows."""
        var_p = kalman.position_variance(a.p) + kalman.position_variance(b.p)
        var_v = kalman.speed_variance(a.p) + kalman.speed_variance(b.p)
        d2 = sum_sq([a.x[i] - b.x[i] for i in range(3)]) / var_p
        d2 += sum_sq([a.x[i] - b.x[i] for i in range(3, 6)]) / var_v
        return d2 <= self.cfg.duplicate_gate

    # ------------------------------------------------------------------ snapshot

    def state(self) -> dict[str, Any]:
        return {
            "next": self._next,
            "tick": self._tick,
            "tracks": [t.to_state() for t in self.tracks.values()],
            "graveyard": {k: dict(v) for k, v in sorted(self.graveyard.items())},
            "orphans": [o.to_state() for o in self._orphans],
            "close": dict(sorted(self._close.items())),
        }

    def restore(self, state: Mapping[str, Any]) -> None:
        self._next = int(state["next"])
        self._tick = state["tick"]
        self.tracks = {s["id"]: Track.from_state(s) for s in state["tracks"]}
        self.graveyard = {k: dict(v) for k, v in state["graveyard"].items()}
        self._orphans = [Measurement.from_state(s) for s in state["orphans"]]
        self._close = {k: int(v) for k, v in state["close"].items()}

    def _secs(self, ticks: int) -> float:
        return _r(ticks / self.tick_hz)


def sum_sq(values: Sequence[float]) -> float:
    total = 0.0
    for v in values:
        total += v * v
    return total


def _r(value: float) -> float:
    return round(value, 3)


__all__ = [
    "Ambiguity",
    "Association",
    "Component",
    "Tracker",
    "TrackEvent",
    "UpdateResult",
]
