"""Acoustic array: tonal rotor noise against background, wind and rain noise, short range.

The model is a sonar-style budget in decibels. The source level of the class falls with spherical
spreading (20 log10 of range) and a linear atmospheric absorption; the array adds a processing
gain; the noise is the power sum of background, wind (linear in wind speed) and rain noise. The
probability of detection is a logistic function of the SNR above the detection threshold, so it
falls monotonically with range and with wind. A hard `instrumented_range` limits coverage, and
there is no line-of-sight requirement. The reports carry a coarse bearing and no range, plus the
blade-pass frequency, the number of harmonics visible (it grows with SNR) and a tonal flag.
Time of day has no effect (sound does not depend on light); of the modelled weather only wind
speed and rain matter.
"""

import math
from typing import ClassVar

from app.contracts.scenario import ScenarioSpec

from .base import Observation, Sensor
from .decibel import amplitude_db, db_to_amplitude, db_to_power, power_db, sigmoid
from .degradation import Effects
from .detection import Detection, FeatureValue
from .suite import register_model

#: Per-class parameter prefixes (`<prefix>_<class>` with `<prefix>_default` as the fallback).
PER_CLASS = ("source_level", "blades", "rpm", "harmonics")


@register_model
class AcousticSensor(Sensor):
    modalities = ("acoustic",)
    supports_cue = False
    required_params = (
        "background_noise",
        "wind_noise_base",
        "wind_noise_slope",
        "rain_noise",
        "absorption",
        "array_gain",
        "detection_snr",
        "transition_width",
        "harmonic_step",
        "tonal_min_harmonics",
        "sigma_azimuth",
        "sigma_elevation",
        "sigma_blade_pass",
        "sigma_snr",
        "wind_noise_penalty",
    )
    confusion_keys: ClassVar[tuple[str, ...]] = ("default",)

    # ------------------------------------------------------------------ noise and SNR

    def noise_db(self, obs: Observation) -> float:
        """Background, wind and rain noise added as powers, then the wind-noise penalty."""
        p = self.params
        wind = p.value("wind_noise_base", "dB") + p.value("wind_noise_slope", "dB/mps") * (
            obs.env.wind_speed_mps
        )
        power = db_to_power(p.value("background_noise", "dB")) + db_to_power(wind)
        if obs.env.condition == "rain":
            power += db_to_power(p.value("rain_noise", "dB"))
        return power_db(power) + amplitude_db(obs.effects.noise_factor)

    def snr_db(self, obs: Observation) -> float:
        """Source level - spreading - absorption + array gain - noise, in decibels."""
        p = self.params
        distance = max(obs.geometry.slant_range_m, 1.0)
        level = (
            p.for_class("source_level", obs.truth.class_id, "dB")
            - amplitude_db(distance)
            - p.value("absorption", "dB/km") * distance / 1000.0
        )
        return level + p.value("array_gain", "dB") - self.noise_db(obs)

    def p_detect(self, obs: Observation) -> float:
        p = self.params
        excess = self.snr_db(obs) - p.value("detection_snr", "dB")
        return sigmoid(excess / p.value("transition_width", "dB"))

    # ------------------------------------------------------------------ measurement

    def harmonics_visible(self, class_id: str, snr_db: float) -> int:
        """Harmonics above the noise: one at the detection threshold, one more per step of SNR."""
        p = self.params
        cap = max(1, math.floor(p.for_class("harmonics", class_id, "count") + 0.5))
        extra = math.floor(
            (snr_db - p.value("detection_snr", "dB")) / p.value("harmonic_step", "dB")
        )
        return max(1, min(cap, 1 + extra))

    def blade_pass_hz(self, class_id: str) -> float:
        """Fundamental: blades x revolutions per second (a wing-beat rate fits the same form)."""
        p = self.params
        return p.for_class("blades", class_id, "count") * p.for_class("rpm", class_id, "rpm") / 60.0

    def measure(self, obs: Observation) -> Detection:
        p, cid = self.params, obs.truth.class_id
        scale = obs.effects.noise_factor * self.precision_factor()
        n = obs.draws.noise  # n[0] and n[3] are free: there is no range or radial speed
        snr = self.snr_db(obs)
        visible = self.harmonics_visible(cid, snr)
        features: dict[str, FeatureValue] = {
            "blade_pass_hz": max(
                0.0, self.blade_pass_hz(cid) + p.value("sigma_blade_pass", "Hz") * scale * n[3]
            ),
            "harmonics": float(visible),
            "tonal": visible >= p.value("tonal_min_harmonics", "count"),
            "snr_db": snr + p.value("sigma_snr", "dB") * scale * n[0],
        }
        return self.polar_detection(
            obs,
            sigma_range_m=None,
            sigma_azimuth_deg=p.value("sigma_azimuth", "deg"),
            sigma_elevation_deg=p.value("sigma_elevation", "deg"),
            reported_class=self.report_class(obs),
            features=features,
        )

    # ------------------------------------------------------------------ degradations

    def degradation_effect(self, kind: str, severity: float) -> Effects | None:
        """Wind noise is an extra noise-floor penalty, carried as an amplitude ratio (sigmas grow).

        Nothing else touches the array: haze, glare, interference and clutter are not acoustic.
        """
        if kind != "wind-noise":
            return None
        return Effects(
            noise_factor=db_to_amplitude(self.params.value("wind_noise_penalty", "dB") * severity)
        )

    # ------------------------------------------------------------------ scenario check

    def check_scenario(self, spec: ScenarioSpec) -> None:
        """As the framework, and every threat class must resolve every per-class parameter."""
        super().check_scenario(spec)
        for threat in spec.threats:
            for prefix in PER_CLASS:
                self.params.for_class(prefix, threat.class_id)
