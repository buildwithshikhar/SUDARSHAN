"""Surveillance radar: radar-equation detection, clutter, rain loss and a micro-Doppler cue.

A model of what a trainee's console would show, not of a real radar. Probability of detection is a
logistic in the signal-to-noise margin; SNR follows the radar equation in decibels (R^-4 with the
target's radar cross-section) less two-way weather loss and a low-slow-small penalty. Every figure
comes from the sensor profile, and every transcendental goes through `sim.detmath` because
detections reach the event log. See docs/SENSOR_MODELS.md for the equations and parameters.
"""

import math
from typing import TYPE_CHECKING

from app.contracts.scenario import SensorPlacement

from .. import detmath
from ..rng import RngStreams
from .base import Observation, Sensor
from .degradation import Effects
from .detection import STREAM, Detection, FeatureValue
from .geometry import Environment, Geometry
from .profile import ProfileError, SensorParams
from .suite import register_model

if TYPE_CHECKING:
    from ..world import World

_LN10 = 2.302585092994046
#: Decibels lost per natural-log unit of range under the R^-4 law: 40 / ln 10.
_R4_DB = 40.0 / _LN10
_SQRT3 = 1.7320508075688772
#: Uniform draws per false-alarm slot: occurrence, bearing, range, elevation, radial speed,
#: reported class, micro-Doppler label, micro-Doppler jitter.
_FALSE_ALARM_DRAWS = 8
#: Stand-in class that the confusion tables use for a clutter plot.
CLUTTER = "clutter"
#: Largest and smallest factors applied to measurement sigmas as SNR falls and rises.
_SIGMA_SCALE = (0.5, 4.0)


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + detmath.exp(-x))


@register_model
class RadarSensor(Sensor):
    modalities = ("radar",)
    supports_cue = False
    required_params = (
        "sigma_range",
        "sigma_azimuth",
        "sigma_elevation",
        "sigma_radial",
        "snr_ref",
        "snr_ref_range",
        "detection_threshold",
        "pd_slope",
        "rcs_default",
        "aspect_swing_default",
        "notch_speed",
        "notch_depth",
        "clutter_elevation",
        "clutter_floor_loss",
        "weather_ref_visibility",
        "noise_ref_snr",
        "md_resolve_margin",
        "md_resolve_slope",
        "md_hz_rotor",
        "md_hz_wing_beat",
        "md_hz_spread",
        "false_alarm_rate",
        "false_alarm_slots",
        "false_alarm_speed",
        "clutter_pd_loss",
        "clutter_noise_gain",
        "clutter_false_alarm_gain",
    )
    #: `default` when micro-Doppler is resolved, `unresolved` when not, `micro_doppler` for the
    #: label the signature processing reports.
    confusion_keys = ("default", "unresolved", "micro_doppler")

    def __init__(self, placement: SensorPlacement, params: SensorParams) -> None:
        super().__init__(placement, params)
        for key in self.confusion_keys:
            if not self.params.confusion(key).has(CLUTTER):
                raise ProfileError(
                    f"profile {self.params.id}: confusion table {key!r} needs a {CLUTTER!r} row "
                    "for false alarms"
                )

    # ------------------------------------------------------------------ signal model

    def effective_rcs_dbsm(self, class_id: str, aspect_deg: float) -> float:
        """Mean RCS for the class plus a bounded aspect term: +swing broadside, -swing nose/tail."""
        p = self.params
        s = detmath.sin(aspect_deg * detmath.DEG)
        swing = p.for_class("aspect_swing", class_id, "dB")
        return p.for_class("rcs", class_id, "dBsm") + swing * (2.0 * s * s - 1.0)

    def weather_loss_db(self, slant_range_m: float, env: Environment) -> float:
        """Two-way attenuation: the condition's dB/km, scaled up as visibility falls."""
        p = self.params
        one_way = p.optional(f"loss_{env.condition}", "dB/km") or 0.0
        ref = p.value("weather_ref_visibility", "m")
        scale = detmath.clamp(ref / max(env.visibility_m, 1.0), 0.5, 2.0)
        return 2.0 * one_way * scale * slant_range_m / 1000.0

    def clutter_loss_db(self, g: Geometry) -> float:
        """Low-slow-small penalty: ground clutter near the horizon, plus a Doppler notch that
        removes targets whose radial speed is near zero (they sit in the clutter filter)."""
        p = self.params
        elevation = max(g.elevation_deg, 0.0)
        exposure = detmath.exp(-elevation / p.value("clutter_elevation", "deg"))
        v = g.radial_speed_mps / p.value("notch_speed", "m/s")
        notch = p.value("notch_depth", "dB") * detmath.exp(-v * v)
        return exposure * (p.value("clutter_floor_loss", "dB") + notch)

    def snr_db(self, obs: Observation) -> float:
        p, g = self.params, obs.geometry
        slant = max(g.slant_range_m, 1.0)
        return (
            p.value("snr_ref", "dB")
            + self.effective_rcs_dbsm(obs.truth.class_id, g.aspect_deg)
            - _R4_DB * detmath.log(slant / p.value("snr_ref_range", "m"))
            - self.weather_loss_db(slant, obs.env)
            - self.clutter_loss_db(g)
        )

    def p_detect(self, obs: Observation) -> float:
        p = self.params
        margin = self.snr_db(obs) - p.value("detection_threshold", "dB")
        return detmath.clamp(_logistic(margin / p.value("pd_slope", "dB")), 0.0, 1.0)

    # ------------------------------------------------------------------ measurement

    def _sigma_scale(self, snr_db: float) -> float:
        """Measurement sigma grows as SNR falls: sqrt of the SNR ratio to a reference SNR."""
        gap = self.params.value("noise_ref_snr", "dB") - snr_db
        return detmath.clamp(detmath.exp(0.5 * gap * _LN10 / 10.0), *_SIGMA_SCALE)

    def _resolve_probability(self, snr_db: float) -> float:
        p = self.params
        margin = snr_db - p.value("detection_threshold", "dB") - p.value("md_resolve_margin", "dB")
        return _logistic(margin / p.value("md_resolve_slope", "dB"))

    def _micro_doppler_hz(self, label: str, jitter: float) -> float:
        base = self.params.value(f"md_hz_{label.replace('-', '_')}", "Hz")
        return max(0.0, base * (1.0 + self.params.value("md_hz_spread", "ratio") * jitter))

    def measure(self, obs: Observation) -> Detection:
        """The report for a detected target.

        Given a detection, `draws.detect / p` is uniform on [0, 1) and independent of the
        classify draw, so it serves as the micro-Doppler draw without costing another random
        number: first whether the signature resolved, then (rescaled) which label it shows.
        """
        p = self.params
        snr = self.snr_db(obs)
        p_hit = detmath.clamp(self.p_detect(obs) * obs.effects.pd_factor, 0.0, 1.0)
        u = min(obs.draws.detect / max(p_hit, 1e-12), 1.0 - 1e-12)
        p_resolve = self._resolve_probability(snr)
        resolved = u < p_resolve
        label = "none"
        if resolved:
            label = p.confusion("micro_doppler").sample(obs.truth.class_id, u / p_resolve)
        features: dict[str, FeatureValue] = {"micro_doppler": label}
        if label != "none":
            # Both are Doppler estimates, so the frequency jitter shares the radial-speed noise.
            features["md_modulation_hz"] = self._micro_doppler_hz(label, obs.draws.noise[3])
        k = self._sigma_scale(snr)
        return self.polar_detection(
            obs,
            sigma_range_m=p.value("sigma_range", "m") * k,
            sigma_azimuth_deg=p.value("sigma_azimuth", "deg") * k,
            sigma_elevation_deg=p.value("sigma_elevation", "deg") * k,
            sigma_radial_mps=p.value("sigma_radial", "m/s") * k,
            reported_class=self.report_class(obs, "default" if resolved else "unresolved"),
            features=features,
        )

    # ------------------------------------------------------------------ degradations

    def degradation_effect(self, kind: str, severity: float) -> Effects | None:
        """Clutter lowers Pd, widens the measurements and multiplies the false-alarm rate."""
        if kind != "clutter":
            return None
        p = self.params
        return Effects(
            pd_factor=1.0 - p.value("clutter_pd_loss", "ratio") * severity,
            noise_factor=1.0 + p.value("clutter_noise_gain", "ratio") * severity,
            clutter_factor=1.0 + p.value("clutter_false_alarm_gain", "ratio") * severity,
        )

    # ------------------------------------------------------------------ false alarms

    def false_alarms(
        self, world: "World", t: int, rng: RngStreams, env: Environment, fx: Effects
    ) -> list[Detection]:
        """Clutter plots shaped like contacts. Always `slots x 8` uniforms, whatever happens."""
        p = self.params
        slots = math.floor(p.value("false_alarm_slots", "count") + 0.5)
        per_slot = detmath.clamp(
            p.value("false_alarm_rate", "count") * fx.clutter_factor / slots, 0.0, 1.0
        )
        low = 0.0 if self._min_elevation is None else self._min_elevation
        high = 30.0 if self._max_elevation is None else self._max_elevation
        speed = p.value("false_alarm_speed", "m/s")
        found: list[Detection] = []
        for _ in range(slots):
            u = [rng.uniform(STREAM) for _ in range(_FALSE_ALARM_DRAWS)]
            azimuth = u[1] * 360.0
            if u[0] >= per_slot or fx.blocks(azimuth):
                continue
            label = p.confusion("micro_doppler").sample(CLUTTER, u[6])
            features: dict[str, FeatureValue] = {"micro_doppler": label}
            if label != "none":
                jitter = (2.0 * u[7] - 1.0) * _SQRT3  # uniform with unit variance, like the noise
                features["md_modulation_hz"] = self._micro_doppler_hz(label, jitter)
            found.append(
                Detection(
                    sensor_id=self.id,
                    modality="radar",
                    tick=t,
                    truth_id=None,
                    azimuth_deg=azimuth,
                    elevation_deg=low + (high - low) * u[3] * u[3],  # clutter hugs the horizon
                    range_m=self.instrumented_range_m * (0.1 + 0.9 * math.sqrt(u[2])),
                    radial_speed_mps=(2.0 * u[4] - 1.0) * speed,
                    sigma_range_m=p.value("sigma_range", "m") * fx.noise_factor,
                    sigma_azimuth_deg=p.value("sigma_azimuth", "deg") * fx.noise_factor,
                    sigma_elevation_deg=p.value("sigma_elevation", "deg") * fx.noise_factor,
                    reported_class=p.confusion("default").sample(CLUTTER, u[5]),
                    features=features,
                )
            )
        return found


__all__ = ["CLUTTER", "RadarSensor"]
