"""Electro-optical and infrared cameras: Johnson-criteria detection and recognition.

A camera sees a target as `size / (range x IFOV)` pixels. That figure, reduced by atmospheric
transmission, the light level and the target's contrast, is compared with the Johnson detection
and recognition thresholds. One model serves three modes through the profile: day EO, night
vision (an `eo` profile that keeps most of its performance in the dark) and thermal (`ir`, which
does not depend on light). Thermal here is a rendering and detection model, not radiometric, and
the weather is modelled. See docs/SENSOR_MODELS.md.
"""

import math

from .. import detmath
from .base import Observation, Sensor
from .degradation import Effects
from .detection import Detection
from .suite import register_model

#: Koschmieder constant: contrast falls to 2 % over the meteorological visibility range.
_KOSCHMIEDER = 3.912
#: Measurement sigma is scaled by sqrt(detect threshold / apparent size), within these limits.
_SIGMA_SCALE = (0.5, 3.0)


@register_model
class EoIrSensor(Sensor):
    modalities = ("eo", "ir")
    supports_cue = True
    needs_line_of_sight = True
    required_params = (
        "pixels_h",
        "johnson_detect_px",
        "johnson_recognise_px",
        "johnson_slope",
        "size_default",
        "contrast_default",
        "low_light_floor",
        "extinction_scale",
        "sigma_pixels",
        "haze_pd_loss",
        "haze_noise_gain",
        "glare_pd_loss",
        "glare_noise_gain",
    )
    #: `default` when the target reaches the recognition threshold, `distant` when only detected.
    confusion_keys = ("default", "distant")

    # ------------------------------------------------------------------ optics

    def fov_deg(self) -> float:
        """Current full field of view: the cue's zoom, else the wide field."""
        fov = self.pointing.fov_deg
        assert fov is not None  # a cue-capable sensor always has a field (fov_wide is required)
        return fov

    def ifov_rad(self, fov_deg: float | None = None) -> float:
        """Instantaneous field of view: one pixel's angle."""
        fov = self.fov_deg() if fov_deg is None else fov_deg
        return fov * detmath.DEG / self.params.value("pixels_h", "px")

    def light_factor(self, daylight: float) -> float:
        """1 in daylight; at night the sensor keeps `low_light_floor` of its performance."""
        floor = self.params.value("low_light_floor", "ratio")
        return floor + (1.0 - floor) * daylight

    def transmission(self, slant_range_m: float, visibility_m: float) -> float:
        """Beer-Lambert contrast transmission over the path, from the visibility range."""
        beta = (
            self.params.value("extinction_scale", "ratio") * _KOSCHMIEDER / max(visibility_m, 1.0)
        )
        return detmath.exp(-beta * slant_range_m)

    def geometric_px(self, class_id: str, slant_range_m: float) -> float:
        """Apparent size in pixels with perfect air and contrast: size / (range x IFOV)."""
        size = self.params.for_class("size", class_id, "m")
        return size / (max(slant_range_m, 1.0) * self.ifov_rad())

    def effective_px(self, obs: Observation) -> float:
        """The pixel figure compared with the Johnson thresholds."""
        contrast = self.params.for_class("contrast", obs.truth.class_id, "ratio")
        return (
            self.geometric_px(obs.truth.class_id, obs.geometry.slant_range_m)
            * self.transmission(obs.geometry.slant_range_m, obs.env.visibility_m)
            * self.light_factor(obs.env.daylight)
            * contrast
        )

    # ------------------------------------------------------------------ detection

    def p_detect(self, obs: Observation) -> float:
        """Johnson detection: r^k / (1 + r^k) with r = apparent size / detection threshold."""
        p = self.params
        ratio = max(self.effective_px(obs) / p.value("johnson_detect_px", "px"), 1e-9)
        return detmath.clamp(
            1.0 / (1.0 + detmath.exp(-p.value("johnson_slope", "ratio") * detmath.log(ratio))),
            0.0,
            1.0,
        )

    def recognised(self, obs: Observation) -> bool:
        return self.effective_px(obs) >= self.params.value("johnson_recognise_px", "px")

    def precision_factor(self) -> float:
        """Angular sigma is a fixed number of pixels, so it shrinks with the field of view."""
        return self.fov_deg() / self.params.value("fov_wide", "deg")

    def measure(self, obs: Observation) -> Detection:
        """Angle-only report: a camera has no range or radial speed."""
        p = self.params
        px = self.effective_px(obs)
        detect_px = p.value("johnson_detect_px", "px")
        k = detmath.clamp(math.sqrt(detect_px / px), *_SIGMA_SCALE)
        wide_ifov_deg = self.ifov_rad(p.value("fov_wide", "deg")) / detmath.DEG
        sigma = p.value("sigma_pixels", "px") * wide_ifov_deg * k  # at the wide field
        recognised = self.recognised(obs)
        return self.polar_detection(
            obs,
            sigma_range_m=None,
            sigma_azimuth_deg=sigma,
            sigma_elevation_deg=sigma,
            reported_class=self.report_class(obs, "default" if recognised else "distant"),
            features={
                "apparent_px": self.geometric_px(obs.truth.class_id, obs.geometry.slant_range_m),
                "recognised": recognised,
            },
        )

    # ------------------------------------------------------------------ degradations

    def degradation_effect(self, kind: str, severity: float) -> Effects | None:
        """Haze and glare cost probability and add noise, each scaled by the profile's figures.

        The effect does not know the sun's position or the range, so glare is a fixed loss for the
        injected severity (the instructor sets it for a low sun); the thermal profile loses little.
        """
        p = self.params
        if kind in ("haze", "glare"):
            return Effects(
                pd_factor=1.0 - p.value(f"{kind}_pd_loss", "ratio") * severity,
                noise_factor=1.0 + p.value(f"{kind}_noise_gain", "ratio") * severity,
            )
        return None


__all__ = ["EoIrSensor"]
