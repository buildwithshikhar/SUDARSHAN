"""The sensor interface every modality model implements.

`Sensor.detect(world, t, rng)` is a template method. The framework does what is the same for every
modality, in a fixed order: advance the cue state, honour the update interval, build the
environment and the effects of active degradations, then for every active drone in scenario order
take a fixed block of random draws, check coverage, ask the model for a probability of detection
and, on a hit, ask it for the measurement. A model supplies only `p_detect` and `measure` (and,
optionally, false alarms, a degradation response and a precision hook).
"""

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, ClassVar

from app.contracts import TICK_HZ
from app.contracts.scenario import ScenarioSpec, SensorPlacement

from .. import detmath
from ..rng import RngStreams
from .cue import DEFAULT_CUE_HOLD_S, CueRequest, CueResult, Pointing
from .degradation import Degradation, Effects, combine
from .detection import Detection, Draws, FeatureValue
from .geometry import Environment, Geometry, Truth, truths
from .profile import ProfileError, SensorParams

if TYPE_CHECKING:
    from ..world import World


@dataclass(frozen=True, slots=True)
class Observation:
    """One sensor looking at one drone at one tick: everything a model needs to decide."""

    t: int
    truth: Truth
    geometry: Geometry
    env: Environment
    effects: Effects
    draws: Draws


class Sensor(ABC):
    #: Profile modalities this model can run (a model may serve both `eo` and `ir`).
    modalities: ClassVar[tuple[str, ...]]
    #: True if the model supports `cue`; the profile then needs `fov_wide` and `fov_narrow` (deg).
    supports_cue: ClassVar[bool] = False
    #: Parameters the model reads beyond `instrumented_range` and `update_interval`.
    required_params: ClassVar[tuple[str, ...]] = ()
    #: Confusion tables the model samples from; each must exist and cover every scenario class.
    confusion_keys: ClassVar[tuple[str, ...]] = ()

    def __init__(self, placement: SensorPlacement, params: SensorParams) -> None:
        if (placement.profile.id, placement.profile.version) != (params.id, params.version):
            raise ProfileError(
                f"sensor {placement.id} asks for {placement.profile.id} {placement.profile.version}"
                f" but was given {params.id} {params.version}"
            )
        if params.modality not in self.modalities:
            raise ProfileError(
                f"profile {params.id} is {params.modality}, but {type(self).__name__} runs "
                f"{', '.join(self.modalities)}"
            )
        params.require("instrumented_range", "update_interval", *self.required_params)
        if self.supports_cue:
            params.require("fov_wide", "fov_narrow")
            if params.value("fov_narrow", "deg") > params.value("fov_wide", "deg"):
                raise ProfileError(f"profile {params.id}: fov_narrow is wider than fov_wide")
        for key in self.confusion_keys:
            params.confusion(key)
        self.id = placement.id
        self.placement = placement
        self.params = params
        self.position = placement.position
        self.instrumented_range_m = params.value("instrumented_range", "m")
        self.period_ticks = max(1, math.floor(params.value("update_interval", "s") * TICK_HZ + 0.5))
        self._min_elevation = params.optional("min_elevation", "deg")
        self._max_elevation = params.optional("max_elevation", "deg")
        self._slew_rate = params.optional("slew_rate", "deg/s")
        hold_s = params.optional("cue_hold", "s")
        self._hold_ticks = math.floor((DEFAULT_CUE_HOLD_S if hold_s is None else hold_s) * TICK_HZ)
        self.home = Pointing(placement.boresight_deg, 0.0, params.optional("fov_wide", "deg"))
        self._pointing = self.home
        self._target = self.home
        self._cue_until: int | None = None
        self._last_tick: int | None = None
        self.degradations: list[Degradation] = []

    # ------------------------------------------------------------------ what a model supplies

    @abstractmethod
    def p_detect(self, obs: Observation) -> float:
        """Probability of detecting this target now, before degradations scale it."""

    @abstractmethod
    def measure(self, obs: Observation) -> Detection:
        """The report for a detected target. Draw noise only from `obs.draws`."""

    def false_alarms(
        self, world: "World", t: int, rng: RngStreams, env: Environment, fx: Effects
    ) -> list[Detection]:
        """Reports with no target behind them. Must take a fixed number of draws per call."""
        return []

    def degradation_effect(self, kind: str, severity: float) -> Effects | None:
        """What a non-universal degradation does to this modality; `None` if nothing."""
        return None

    def precision_factor(self) -> float:
        """Multiplies every measurement sigma; models tie it to pointing or field of view."""
        return 1.0

    # ------------------------------------------------------------------ the tick

    def detect(self, world: "World", t: int, rng: RngStreams) -> list[Detection]:
        """Detections at tick `t` (pass `world.tick`). Deterministic for a given stream state."""
        self._advance(t)
        if t % self.period_ticks != 0:
            return []
        env = Environment.of(world, t)
        fx = self.effects_at(t)
        found: list[Detection] = []
        for truth in truths(world):
            draws = Draws.take(rng)
            if fx.outage:
                continue
            geometry = Geometry.between(self.position, truth)
            if not self.in_coverage(geometry, fx):
                continue
            obs = Observation(t, truth, geometry, env, fx, draws)
            p = detmath.clamp(self.p_detect(obs) * fx.pd_factor, 0.0, 1.0)
            if draws.detect < p:
                found.append(self.measure(obs))
        # Called during an outage too, so its draws are taken and the stream never shifts.
        alarms = self.false_alarms(world, t, rng, env, fx)
        if not fx.outage:
            found.extend(alarms)
        # Provenance: one profile-level flag, so models cannot forget it (Q-20).
        reference = bool(self.params.unverified)
        return [replace(d, reference_data=reference) for d in found]

    def in_coverage(self, g: Geometry, fx: Effects) -> bool:
        if g.slant_range_m > self.instrumented_range_m:
            return False
        if self._min_elevation is not None and g.elevation_deg < self._min_elevation:
            return False
        if self._max_elevation is not None and g.elevation_deg > self._max_elevation:
            return False
        p = self._pointing
        if p.fov_deg is not None:
            half = p.fov_deg / 2.0
            if abs(detmath.wrap180(g.azimuth_deg - p.azimuth_deg)) > half:
                return False
            if abs(g.elevation_deg - p.elevation_deg) > half:
                return False
        return not fx.blocks(g.azimuth_deg)

    # ------------------------------------------------------------------ measurement helpers

    def report_class(self, obs: Observation, key: str = "default") -> str:
        """Class label this sensor reports for the target, from its confusion table."""
        return self.params.confusion(key).sample(obs.truth.class_id, obs.draws.classify)

    def polar_detection(
        self,
        obs: Observation,
        *,
        sigma_range_m: float | None,
        sigma_azimuth_deg: float,
        sigma_elevation_deg: float,
        sigma_radial_mps: float | None = None,
        reported_class: str | None = None,
        features: dict[str, FeatureValue] | None = None,
    ) -> Detection:
        """Build a detection from true geometry plus noise scaled by degradations and pointing.

        Noise is `sigma * scale * draw`: range from draw 0, azimuth 1, elevation 2, radial speed
        3. The reported sigmas are the scaled ones, which is what a tracker should weight by.
        """
        scale = obs.effects.noise_factor * self.precision_factor()
        g, n = obs.geometry, obs.draws.noise
        s_az, s_el = sigma_azimuth_deg * scale, sigma_elevation_deg * scale
        s_r = None if sigma_range_m is None else sigma_range_m * scale
        s_v = None if sigma_radial_mps is None else sigma_radial_mps * scale
        return Detection(
            sensor_id=self.id,
            modality=self.params.modality,
            tick=obs.t,
            truth_id=obs.truth.id,
            azimuth_deg=detmath.wrap360(g.azimuth_deg + s_az * n[1]),
            elevation_deg=detmath.clamp(g.elevation_deg + s_el * n[2], -90.0, 90.0),
            range_m=None if s_r is None else max(0.0, g.slant_range_m + s_r * n[0]),
            radial_speed_mps=None if s_v is None else g.radial_speed_mps + s_v * n[3],
            sigma_range_m=s_r,
            sigma_azimuth_deg=s_az,
            sigma_elevation_deg=s_el,
            reported_class=reported_class,
            features=features or {},
        )

    # ------------------------------------------------------------------ degradations

    def inject(self, degradation: Degradation) -> None:
        if degradation.sensor_id != self.id:
            raise ValueError(f"degradation for {degradation.sensor_id} given to {self.id}")
        self.degradations.append(degradation)

    def effects_at(self, t: int) -> Effects:
        parts: list[Effects] = []
        for d in self.degradations:
            if not d.active(t):
                continue
            if d.kind == "outage":
                parts.append(Effects(outage=True))
            elif d.kind == "sector-outage":
                assert d.sector_from_deg is not None and d.sector_to_deg is not None
                parts.append(Effects(blocked_sectors=((d.sector_from_deg, d.sector_to_deg),)))
            else:
                effect = self.degradation_effect(d.kind, d.severity)
                if effect is not None:
                    parts.append(effect)
        return combine(parts)

    # ------------------------------------------------------------------ cueing

    @property
    def pointing(self) -> Pointing:
        return self._pointing

    def cue(self, request: CueRequest, t: int) -> CueResult:
        """Point the sensor at a bearing, optionally narrowing its field of view."""
        if request.sensor_id != self.id:
            return CueResult(False, f"cue is for {request.sensor_id}, not {self.id}")
        if not self.supports_cue:
            return CueResult(False, "this sensor cannot be cued")
        self._advance(t)
        if self.effects_at(t).outage:
            return CueResult(False, "sensor is out of service")
        lo, hi = self._min_elevation, self._max_elevation
        if (lo is not None and request.elevation_deg < lo) or (
            hi is not None and request.elevation_deg > hi
        ):
            return CueResult(False, "elevation is outside the sensor's limits")
        fov_wide = self.params.value("fov_wide", "deg")
        fov_narrow = self.params.value("fov_narrow", "deg")
        fov: float | None = self._target.fov_deg
        if request.kind == "narrow":
            requested = fov_narrow if request.fov_deg is None else request.fov_deg
            fov = detmath.clamp(requested, fov_narrow, fov_wide)
        self._target = Pointing(detmath.wrap360(request.bearing_deg), request.elevation_deg, fov)
        self._cue_until = t + self._hold_ticks
        self._advance(t)  # a zoom takes effect at once; the slew starts with the next tick
        return CueResult(True, None, self._target)

    def _advance(self, t: int) -> None:
        """Bring the pointing up to tick `t`: expire a cue, slew at the profile's rate."""
        if self._last_tick is not None and t < self._last_tick:
            raise ValueError(f"sensor {self.id} was already advanced to tick {self._last_tick}")
        if self._cue_until is not None and t >= self._cue_until:
            self._target = self.home
            self._cue_until = None
        dt = 0.0 if self._last_tick is None else (t - self._last_tick) / TICK_HZ
        self._last_tick = t
        limit = math.inf if self._slew_rate is None else self._slew_rate * dt
        cur, tgt = self._pointing, self._target
        d_az = detmath.wrap180(tgt.azimuth_deg - cur.azimuth_deg)
        az = (
            tgt.azimuth_deg
            if abs(d_az) <= limit
            else detmath.wrap360(cur.azimuth_deg + (limit if d_az > 0 else -limit))
        )
        d_el = tgt.elevation_deg - cur.elevation_deg
        el = (
            tgt.elevation_deg
            if abs(d_el) <= limit
            else cur.elevation_deg + (limit if d_el > 0 else -limit)
        )
        self._pointing = Pointing(az, el, tgt.fov_deg)

    # ------------------------------------------------------------------ snapshot

    def state(self) -> dict[str, Any]:
        def point(p: Pointing) -> list[float | None]:
            return [p.azimuth_deg, p.elevation_deg, p.fov_deg]

        return {
            "id": self.id,
            "pointing": point(self._pointing),
            "target": point(self._target),
            "cue_until": self._cue_until,
            "last_tick": self._last_tick,
            "degradations": [d.to_state() for d in self.degradations],
        }

    def restore(self, state: dict[str, Any]) -> None:
        if state["id"] != self.id:
            raise ValueError(f"state for {state['id']} given to {self.id}")
        self._pointing = Pointing(*state["pointing"])
        self._target = Pointing(*state["target"])
        self._cue_until = state["cue_until"]
        self._last_tick = state["last_tick"]
        self.degradations = [Degradation.from_state(d) for d in state["degradations"]]

    # ------------------------------------------------------------------ scenario check

    def check_scenario(self, spec: ScenarioSpec) -> None:
        """Refuse a scenario whose threat classes this sensor's confusion tables do not cover."""
        for key in self.confusion_keys:
            matrix = self.params.confusion(key)
            missing = sorted({t.class_id for t in spec.threats if not matrix.has(t.class_id)})
            if missing:
                raise ProfileError(
                    f"sensor {self.id}: confusion table {key!r} has no row for {', '.join(missing)}"
                )
