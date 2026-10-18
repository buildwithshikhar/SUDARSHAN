"""Passive RF detector: bearing and band features from a link budget, silent emitters unseen.

The model is a link budget. Received power is emitter power plus receive gain minus free-space
path loss (and a very small rain loss); the probability of detection is a logistic function of
the margin over the noise floor plus the required signal-to-noise ratio. An RF-silent class
(autonomous, pre-programmed or fibre-optic drones) has `emits_<class> = 0` and a probability of
exactly zero, whatever the noise, the degradations or the draws. A passive receiver measures no
range: reports carry bearing and a wide-beam elevation, and the band, hop-pattern and signal
strength as features. Wi-Fi and Bluetooth emitters appear as false alarms shaped like contacts.
"""

import math
from typing import TYPE_CHECKING, ClassVar

from app.contracts.scenario import ScenarioSpec, SensorPlacement

from .. import detmath
from ..rng import RngStreams
from .base import Observation, Sensor
from .decibel import amplitude_db, db_to_amplitude, sigmoid
from .degradation import Effects
from .detection import Detection, FeatureValue
from .geometry import Environment
from .profile import ProfileError, SensorParams
from .suite import register_model

if TYPE_CHECKING:
    from ..world import World

#: Band plan: index in the profile (`band_<class>`, from 1), label reported, centre frequency in
#: MHz. Secondary-source plan (docs/02-research.md section 2), so profiles using it are unverified.
BANDS: tuple[tuple[str, float], ...] = (
    ("2.4 GHz", 2440.0),
    ("5.8 GHz", 5800.0),
    ("900 MHz", 900.0),
    ("433 MHz", 433.0),
    ("1.2-1.3 GHz", 1250.0),
)
#: Row of the confusion table that Wi-Fi / Bluetooth false alarms are labelled from.
CONFUSER_CLASS = "wifi-bluetooth"
#: Free-space path loss in dB for d in metres and f in MHz: 20 log d + 20 log f - 27.55.
FSPL_OFFSET_DB = 27.55
#: Uniforms per false-alarm slot per call: occur, azimuth, elevation, class, band, signal, hop.
FALSE_ALARM_DRAWS = 7
#: Share of confusers on 2.4 GHz (the rest are 5.8 GHz), and of those that hop (Bluetooth-like).
CONFUSER_BAND_SPLIT = 0.7
CONFUSER_HOP_SPLIT = 0.5
#: Per-class parameter prefixes (`<prefix>_<class>` with `<prefix>_default` as the fallback).
PER_CLASS = ("emits", "emitter_power", "band", "hop_rate")


@register_model
class RfSensor(Sensor):
    modalities = ("rf",)
    supports_cue = False
    required_params = (
        "rx_gain",
        "noise_floor",
        "required_snr",
        "transition_width",
        "rain_attenuation",
        "sigma_azimuth",
        "sigma_elevation",
        "sigma_rssi",
        "sigma_hop_rate",
        "interference_noise_rise",
        "interference_false_alarm_gain",
        "false_alarm_slots",
        "false_alarm_probability",
        "confuser_hop_rate",
        "confuser_margin_span",
        "confuser_elevation_max",
    )
    confusion_keys: ClassVar[tuple[str, ...]] = ("default",)

    def __init__(self, placement: SensorPlacement, params: SensorParams) -> None:
        super().__init__(placement, params)
        if not params.confusion().has(CONFUSER_CLASS):
            raise ProfileError(f"profile {params.id}: confusion table has no {CONFUSER_CLASS} row")
        self._slots = max(0, math.floor(params.value("false_alarm_slots", "count") + 0.5))

    # ------------------------------------------------------------------ link budget

    def band(self, class_id: str) -> tuple[str, float]:
        """Label and centre frequency (MHz) of the class's link."""
        index = math.floor(self.params.for_class("band", class_id, "index") + 0.5)
        if not 1 <= index <= len(BANDS):
            raise ProfileError(f"profile {self.params.id}: band index {index} is not in the plan")
        return BANDS[index - 1]

    def received_dbm(self, obs: Observation) -> float:
        """Received power: emitter power + receive gain - free-space loss - rain loss."""
        p, cid = self.params, obs.truth.class_id
        distance = max(obs.geometry.slant_range_m, 1.0)
        fspl = amplitude_db(distance) + amplitude_db(self.band(cid)[1]) - FSPL_OFFSET_DB
        rain = 0.0
        if obs.env.condition == "rain":
            rain = p.value("rain_attenuation", "dB/km") * distance / 1000.0
        eirp = p.for_class("emitter_power", cid, "dBm")
        return eirp + p.value("rx_gain", "dB") - fspl - rain

    def margin_db(self, obs: Observation) -> float:
        """Received power above the (interference-raised) noise floor plus the required SNR."""
        p = self.params
        floor = p.value("noise_floor", "dBm") + amplitude_db(obs.effects.noise_factor)
        return self.received_dbm(obs) - floor - p.value("required_snr", "dB")

    def p_detect(self, obs: Observation) -> float:
        if self.params.for_class("emits", obs.truth.class_id, "flag") < 0.5:
            return 0.0  # RF-silent: nothing to hear, under any condition
        return sigmoid(self.margin_db(obs) / self.params.value("transition_width", "dB"))

    # ------------------------------------------------------------------ measurement

    def measure(self, obs: Observation) -> Detection:
        p, cid = self.params, obs.truth.class_id
        scale = obs.effects.noise_factor * self.precision_factor()
        n = obs.draws.noise  # n[0] and n[3] are free: there is no range or radial speed
        hop_rate = p.for_class("hop_rate", cid, "Hz")
        features: dict[str, FeatureValue] = {
            "band": self.band(cid)[0],
            "rssi_dbm": self.received_dbm(obs) + p.value("sigma_rssi", "dB") * scale * n[0],
            "hopping": hop_rate > 0.0,
        }
        if hop_rate > 0.0:
            relative = p.value("sigma_hop_rate", "ratio") * scale * n[3]
            features["hop_rate_hz"] = max(0.0, hop_rate * (1.0 + relative))
        return self.polar_detection(
            obs,
            sigma_range_m=None,
            sigma_azimuth_deg=p.value("sigma_azimuth", "deg"),
            sigma_elevation_deg=p.value("sigma_elevation", "deg"),
            reported_class=self.report_class(obs),
            features=features,
        )

    # ------------------------------------------------------------------ confusers

    def false_alarms(
        self, world: "World", t: int, rng: RngStreams, env: Environment, fx: Effects
    ) -> list[Detection]:
        """Wi-Fi / Bluetooth emitters that look like contacts; interference makes them commoner.

        Every slot takes `FALSE_ALARM_DRAWS` uniforms whether or not it produces a report.
        """
        p = self.params
        chance = detmath.clamp(
            p.value("false_alarm_probability", "ratio") * fx.clutter_factor, 0, 1
        )
        scale = fx.noise_factor * self.precision_factor()
        floor = p.value("noise_floor", "dBm") + p.value("required_snr", "dB")
        found: list[Detection] = []
        for _ in range(self._slots):
            u = [rng.uniform("sensors") for _ in range(FALSE_ALARM_DRAWS)]
            azimuth = u[1] * 360.0
            if u[0] >= chance or fx.blocks(azimuth):
                continue
            hops = u[6] < CONFUSER_HOP_SPLIT
            features: dict[str, FeatureValue] = {
                "band": BANDS[0 if u[4] < CONFUSER_BAND_SPLIT else 1][0],
                "rssi_dbm": floor + p.value("confuser_margin_span", "dB") * u[5],
                "hopping": hops,
            }
            if hops:
                features["hop_rate_hz"] = p.value("confuser_hop_rate", "Hz")
            found.append(
                Detection(
                    sensor_id=self.id,
                    modality=p.modality,
                    tick=t,
                    truth_id=None,
                    azimuth_deg=azimuth,
                    elevation_deg=u[2] * p.value("confuser_elevation_max", "deg"),
                    sigma_azimuth_deg=p.value("sigma_azimuth", "deg") * scale,
                    sigma_elevation_deg=p.value("sigma_elevation", "deg") * scale,
                    reported_class=p.confusion().sample(CONFUSER_CLASS, u[3]),
                    features=features,
                )
            )
        return found

    # ------------------------------------------------------------------ degradations

    def degradation_effect(self, kind: str, severity: float) -> Effects | None:
        """Interference raises the noise floor (P(d) falls, sigmas grow) and the false alarms.

        The rise is carried as a noise amplitude ratio, so stacked injects add in decibels. No
        other kind touches RF: haze, glare, radar clutter and wind noise do not matter here.
        """
        if kind != "interference":
            return None
        rise = self.params.value("interference_noise_rise", "dB") * severity
        gain = self.params.value("interference_false_alarm_gain", "ratio")
        return Effects(noise_factor=db_to_amplitude(rise), clutter_factor=1.0 + gain * severity)

    # ------------------------------------------------------------------ scenario check

    def check_scenario(self, spec: ScenarioSpec) -> None:
        """As the framework, and every threat class must resolve every per-class parameter."""
        super().check_scenario(spec)
        for threat in spec.threats:
            for prefix in PER_CLASS:
                self.params.for_class(prefix, threat.class_id)
            self.band(threat.class_id)
