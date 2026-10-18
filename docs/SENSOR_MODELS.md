# Sensor models

One section per sensor model, in `services/api/sim/sensors/`. Each model supplies a probability of detection `P(d)` and a measurement function; the shared framework (see [SIM_CORE.md](SIM_CORE.md), "Sensor framework") handles update intervals, coverage, random draws, degradations that every sensor shares (outage, sector outage), cueing, and snapshots. Parameters live in sensor-profile YAML under `packs/sensor-profiles/`; each has a unit, a data-register ID ([DATA_REGISTER.md](DATA_REGISTER.md)) and a `verified` flag.

## Honesty rules for every model

- These are fictional sensors in fictional scenarios, built from open research datasets and published specifications. Parameters are **calibrated from** those sources, **never trained on** them.
- `verified: true` means the value is the figure stated in [02-research.md](02-research.md) section 2 for its source. Everything else is `verified: false` and is listed by `SensorParams.unverified` so documents and the UI can show the uncertainty. A project-authored value uses register ID F01.
- Weather is **modelled**. Thermal imagery is a **rendering and detection model, not radiometric**.
- A model never decides what a trainee should do. It produces noisy, sometimes wrong reports; fusing them is the trainee's job.
- No model names a real system or quotes a real performance figure.

All arithmetic that reaches a detection uses only `+ - * /`, `sqrt` and `sim.detmath` (`exp`, `log`, `sin`), so detections are bit-identical across platforms. Every candidate target consumes 18 uniforms from the `sensors` stream whatever happens to it.

## Radar

`sim/sensors/radar.py`, `RadarSensor`, modality `radar`, profile `radar-generic-s` 0.2.0 (`packs/sensor-profiles/radar-generic-s.v1.yaml`). No cueing (`supports_cue = False`); it covers all bearings inside its elevation limits.

### Purpose

A short-range surveillance radar that sees small, slow, low targets poorly, is blind to targets crossing at zero radial speed, picks up clutter plots, and offers micro-Doppler as the cue that separates a rotor from a wing-beat when radar cross-section (RCS) alone cannot.

### Equations

Signal-to-noise ratio in dB, for slant range `R` (floored at 1 m):

```
RCS_eff  = rcs_<class> + aspect_swing_<class> * (2 sin^2(aspect) - 1)      dBsm, bounded by +/- swing
SNR      = snr_ref + RCS_eff - (40 / ln 10) * ln(R / snr_ref_range)
           - L_weather - L_clutter
L_weather = 2 * loss_<condition> * clamp(weather_ref_visibility / visibility, 0.5, 2) * R / 1000
L_clutter = exp(-max(elevation, 0) / clutter_elevation)
            * (clutter_floor_loss + notch_depth * exp(-(radial_speed / notch_speed)^2))
P(d)     = logistic((SNR - detection_threshold) / pd_slope)
```

`aspect` is the angle between the target's velocity and the line to the sensor (0 head-on, 180 tail-on), so broadside gives `+swing`. `L_weather` is a two-way loss: the condition's one-way dB/km figure, scaled up as visibility falls below the reference. `L_clutter` is the low-slow-small penalty: ground clutter near the horizon, plus a Doppler notch that removes targets with near-zero radial speed. `P(d)` is non-increasing in range (every term is).

Measurement noise: range, azimuth, elevation and radial speed sigmas from the profile, multiplied by `clamp(exp(0.5 * ln10/10 * (noise_ref_snr - SNR)), 0.5, 4)` (the square root of the SNR shortfall) and by the degradation noise factor. Noise comes from the framework's four noise draws via `polar_detection`.

Micro-Doppler. Given a detection, `u = draws.detect / P` is uniform on [0, 1) and independent of the classify draw, so it is reused as the signature draw at no cost in random numbers. The signature is resolved if `u < logistic((SNR - detection_threshold - md_resolve_margin) / md_resolve_slope)`. If resolved, the label (`rotor`, `wing-beat` or `none`) is sampled from the `micro_doppler` table using `u` rescaled; if not, the label is `none`. A label other than `none` adds `md_modulation_hz = md_hz_<label> * (1 + md_hz_spread * noise[3])` (the radial-speed noise draw is reused: both are Doppler estimates). The report's `features` are `micro_doppler` and, when present, `md_modulation_hz`.

Classification. The reported class is sampled from `default` when the signature was resolved and from `unresolved` when not.

False alarms. Each update takes `false_alarm_slots` slots of 8 uniforms each, always. A slot becomes a plot with probability `false_alarm_rate * clutter_factor / slots`. A plot has a uniform bearing, range `instrumented_range * (0.1 + 0.9 sqrt(u))`, an elevation biased to the horizon, a radial speed within `false_alarm_speed`, a class from the `clutter` row of `default`, and a micro-Doppler label from the `clutter` row of `micro_doppler`. It has the same fields as a real contact and no `truth_id`. Plots in a blocked sector are dropped after the draws.

### Parameters

| Name | Unit | Value | Register | Verified |
|---|---|---|---|---|
| `instrumented_range` | m | 4600 | F01 | no |
| `update_interval` | s | 1.2 | F01 | no |
| `min_elevation` / `max_elevation` | deg | -2 / 38 | F01 | no |
| `snr_ref` (SNR of a 0 dBsm target at `snr_ref_range`) | dB | 45 | F01 | no |
| `snr_ref_range` | m | 1000 | F01 | no |
| `detection_threshold` | dB | 13 | F01 | no |
| `pd_slope` | dB | 2.5 | F01 | no |
| `rcs_rotary_small` | dBsm | -16 | F01 | no |
| `rcs_fixed_wing_small` | dBsm | -10 | F01 | no |
| `rcs_bird` | dBsm | -22 | F01 | no |
| `rcs_default` | dBsm | -16 | F01 | no |
| `aspect_swing_rotary_small` / `_fixed_wing_small` / `_bird` / `_default` | dB | 4 / 4 / 3 / 4 | F01 | no |
| `clutter_elevation` | deg | 3 | F01 | no |
| `clutter_floor_loss` | dB | 3 | F01 | no |
| `notch_speed` | m/s | 2.5 | F01 | no |
| `notch_depth` | dB | 12 | F01 | no |
| `weather_ref_visibility` | m | 5000 | F01 | no |
| `loss_clear` / `loss_haze` / `loss_fog` / `loss_dust` / `loss_rain` | dB/km | 0 / 0.01 / 0.02 / 0.04 / 0.25 | F01 | no |
| `sigma_range` | m | 7.5 | F01 | no |
| `sigma_azimuth` / `sigma_elevation` | deg | 0.6 / 1.0 | F01 | no |
| `sigma_radial` | m/s | 0.4 | F01 | no |
| `noise_ref_snr` | dB | 20 | F01 | no |
| `md_resolve_margin` / `md_resolve_slope` | dB | 6 / 2 | F01 | no |
| `md_hz_rotor` | Hz | 120 | F01 | no |
| `md_hz_wing_beat` | Hz | 12 | F01 | no (UNVERIFIED, Q-09: secondary source only) |
| `md_hz_spread` | ratio | 0.1 | F01 | no |
| `false_alarm_rate` / `false_alarm_slots` | count | 0.2 / 4 | F01 | no |
| `false_alarm_speed` | m/s | 6 | F01 | no |
| `clutter_pd_loss` / `clutter_noise_gain` / `clutter_false_alarm_gain` | ratio | 0.4 / 0.5 / 9 | F01 | no |

The RCS values sit inside the ranges in [02-research.md](02-research.md) section 2 (small multirotor about -20 to -8 dBsm, birds about -30 to -19 dBsm) and are project-authored (F01): the published ranges (Ezuma et al. 2019, Seidaliyeva 2023) have no row in the data register yet (Q-20), and the values were not extracted from the KTH/SAAB set (D14). They stay `verified: false`. With the shipped aspect swings, a multirotor spans -20 to -12 dBsm and a bird -25 to -19 dBsm, so RCS alone cannot separate them. At neutral aspect, no weather and no clutter, `P(d)` is 0.5 at about 2.5 km for a small rotary contact, 1.8 km for a bird and 3.6 km for a small fixed-wing contact.

### Confusion matrices

Three tables, all F01 and unverified, each row-normalised and each with a `clutter` row for false alarms. Labels for `default` and `unresolved`: `rotary-small`, `fixed-wing-small`, `bird`, `unknown`. Labels for `micro_doppler`: `rotor`, `wing-beat`, `none`.

| True class | `default` (resolved), correct label | `unresolved`, correct label | `micro_doppler` modal label |
|---|---|---|---|
| `rotary-small` | 0.86 | 0.44 | `rotor` 0.90 |
| `fixed-wing-small` | 0.78 | 0.40 | `none` 0.65, `rotor` 0.30 (propeller modulation) |
| `bird` | 0.85 | 0.44 | `wing-beat` 0.80 |

### Degradations

| Kind | Effect |
|---|---|
| `outage` | Framework: no detections and no false alarms for the window. |
| `sector-outage` | Framework: targets and false alarms in the clockwise sector are dropped. |
| `clutter` | `pd_factor = 1 - clutter_pd_loss * severity`, `noise_factor = 1 + clutter_noise_gain * severity`, false-alarm factor `1 + clutter_false_alarm_gain * severity`. |
| `haze`, `glare`, `interference`, `wind-noise` | No effect on radar. |

### Cueing

None. A radar cannot be cued and has no field of view to narrow; wave 4b's cue output goes to the EO/IR sensors.

### Honesty note

This radar is a trainer's model of how the picture looks, not a model of any real radar. The power budget, thresholds, clutter and false-alarm figures are project-authored. The micro-Doppler frequencies are illustrative; the 5 to 20 Hz bird wing-beat band is from a secondary source and unverified (Q-09).

## EO/IR

`sim/sensors/eoir.py`, `EoIrSensor`, modalities `eo` and `ir`, `supports_cue = True`. One model, three profiles:

| Mode | Profile | Modality | Difference |
|---|---|---|---|
| Day | `eo-generic-day` 0.1.0 | `eo` | Keeps 3 % of its performance in the dark. |
| Night vision | `eo-generic-nv` 0.1.0 | `eo` | Keeps 70 % in the dark; blooms in bright light. |
| Thermal | `ir-generic-thermal` 0.1.0 | `ir` | Independent of light; passes haze better; the research-section camera (320 px, 24 degrees). |

### Purpose

Cameras that give excellent angles and recognition at short range and nothing at long range, sharply better when cued to a narrow field of view, and strongly dependent on light and visibility (except thermal for light).

### Equations

```
IFOV            = fov / pixels_h                            (radians; fov is the current field of view)
px_geometric    = size_<class> / (R * IFOV)                 (apparent size, pixels)
T               = exp(-extinction_scale * 3.912 / visibility * R)     Beer-Lambert, 2 % contrast at the visibility range
L               = low_light_floor + (1 - low_light_floor) * daylight
px_effective    = px_geometric * T * L * contrast_<class>
P(d)            = r^k / (1 + r^k),  r = px_effective / johnson_detect_px,  k = johnson_slope
recognised      = px_effective >= johnson_recognise_px
```

`daylight` is the framework's 0..1 fraction (linear through a one-hour twilight at fictional sunrise 06:00 and sunset 18:00). `R` is floored at 1 m. `P(d)` is non-increasing in range because `px_effective` is.

Reference check from the research section: for the 320 x 256, 24 degree thermal camera, `IFOV` is 1.309 mrad, so 5 px is reached at about 60 m for the 0.39 m drone and 120 m for the 0.79 m bird, and 15 px at about 20 m and 40 m in clear air. The tests assert these.

Measurement. The camera reports azimuth and elevation only (no range, no radial speed). The angular sigma is `sigma_pixels * IFOV_wide * clamp(sqrt(johnson_detect_px / px_effective), 0.5, 3)` and `precision_factor() = fov / fov_wide` multiplies it, so the sigma equals `sigma_pixels` pixels of the *current* field of view. The framework treats the field as a square cone, so elevation uses the same width as azimuth. Features reported: `apparent_px` (geometric) and `recognised`.

Classification. `default` when recognised, `distant` when only detected.

### Parameters

All three profiles read the same names. Values are given as day / night vision / thermal.

| Name | Unit | Value | Register | Verified |
|---|---|---|---|---|
| `instrumented_range` | m | 3500 / 2500 / 3000 | F01 | no |
| `update_interval` | s | 0.2 / 0.2 / 0.2 | F01 | no |
| `min_elevation` / `max_elevation` | deg | -10 / 85 | F01 | no |
| `slew_rate`, `cue_hold` | deg/s, s | 40, 10 | F01 | no |
| `fov_wide` | deg | 30 / 20 / 24 | F01 / F01 / D12 | no / no / yes (thermal) |
| `fov_narrow` | deg | 2.5 / 3 / 6 | F01 | no |
| `pixels_h` | px | 1920 / 1280 / 320 | F01 / F01 / D12 | no / no / yes (thermal) |
| `johnson_detect_px` | px | 5 | D12 | yes |
| `johnson_recognise_px` | px | 15 | D12 | yes |
| `johnson_slope` | ratio | 3 | F01 | no |
| `size_rotary_small` | m | 0.39 | D12 | no (derived from the section-2 ranges) |
| `size_bird` | m | 0.79 | D12 | no (derived) |
| `size_fixed_wing_small` | m | 1.2 | F01 | no |
| `size_default` | m | 0.5 | F01 | no |
| `contrast_default` | ratio | 0.9 / 0.75 / 0.8 | F01 | no |
| `contrast_rotary_small`, `_bird`, `_fixed_wing_small` (thermal only) | ratio | 1.0, 1.0, 0.8 | F01 | no (UNVERIFIED, Q-09) |
| `low_light_floor` | ratio | 0.03 / 0.7 / 1.0 | F01 | no |
| `extinction_scale` | ratio | 1.0 / 0.9 / 0.6 | F01 | no |
| `sigma_pixels` | px | 0.8 / 1.1 / 1.0 | F01 | no |
| `haze_pd_loss` / `haze_noise_gain` | ratio | 0.5, 0.6 / 0.5, 0.6 / 0.2, 0.3 | F01 | no |
| `glare_pd_loss` / `glare_noise_gain` | ratio | 0.7, 1.0 / 0.8, 1.2 / 0.1, 0.2 | F01 | no |

The sizes follow from the research figures: 5 px x 60 m x 1.309 mrad = 0.39 m, and 15 px x 20 m x 1.309 mrad is the same; 5 px x 120 m x 1.309 mrad = 0.79 m. Thermal contrast for motors and batteries (and the bird and fixed-wing figures) is **UNVERIFIED** (Q-09): they are project-authored with `verified: false`.

### Confusion matrices

Two tables per profile, F01, unverified, row-normalised; labels `rotary-small`, `fixed-wing-small`, `bird`, `unknown`.

| Profile | `default` (recognised), correct label | `distant` (detected only), correct label |
|---|---|---|
| Day | 0.90 / 0.88 / 0.86 | 0.40 / 0.40 / 0.38 |
| Night vision | 0.82 / 0.80 / 0.78 | 0.32 / 0.32 / 0.30 |
| Thermal | 0.85 / 0.82 / 0.80 | 0.35 / 0.35 / 0.33 |

Entries are `rotary-small` / `fixed-wing-small` / `bird`. At a few pixels a bird and a drone are easily confused, which is the point of the `distant` tables.

### Degradations

| Kind | Effect |
|---|---|
| `outage`, `sector-outage` | Framework. A cue to a sensor in outage is refused. |
| `haze` | `pd_factor = 1 - haze_pd_loss * severity`, `noise_factor = 1 + haze_noise_gain * severity`. |
| `glare` | `pd_factor = 1 - glare_pd_loss * severity`, `noise_factor = 1 + glare_noise_gain * severity`. Day EO and night vision suffer most; thermal little. |
| `clutter`, `interference`, `wind-noise` | No effect on EO/IR. |

The degradation hook sees no environment and no range, so a degradation is a fixed multiplier for its severity: haze is separate from the visibility already in the modelled weather, and glare does not track the sun's position (the instructor injects it for a low sun). This is a deliberate simplification.

### Cueing

A `CueRequest` of kind `narrow` points the sensor and zooms between `fov_narrow` and `fov_wide`, taking effect at the sensor's next update. A narrower field shrinks the IFOV in proportion, so apparent size, `P(d)`, the detection and recognition ranges and the angular precision all improve by `fov_wide / fov` (four times for thermal at 6 degrees), and the sensor can no longer see targets outside the narrow field. The cue holds for `cue_hold` seconds and the sensor then returns to its boresight and wide field. Tests assert the narrowing, the sigma reduction, the larger `P(d)` and range, and determinism.

### Honesty note

Thermal is a rendering and detection model, not radiometric: there is no temperature, emissivity or sensor noise-equivalent figure. The pixel thresholds, camera format and field of view for thermal are the figures in the research section (D12, Svanstrom et al.); every other number, and all motor and battery contrast, is project-authored or unverified. Weather and light are modelled.

## RF

**Purpose.** A passive RF detector. It hears what a drone transmits (control link, video link) and reports a bearing, a wide-beam elevation and band features. It measures no range. An RF-silent drone (autonomous, pre-programmed, fibre-optic) is invisible to it, which is the point of the sensor in training: no single sensor is decisive.

**Equations.** Distances in metres (floored at 1 m), frequency `f` in MHz, powers in dBm, gains and losses in dB. Logarithms use `sim.detmath.log` (`20 log10 x = (20 / ln 10) ln x`).

```
FSPL(d, f)  = 20 log10(d) + 20 log10(f) - 27.55
rain_loss   = rain_attenuation * d / 1000          (only when weather condition is rain)
P_rx        = emitter_power + rx_gain - FSPL(d, f) - rain_loss
noise       = noise_floor + 20 log10(noise_factor)  (noise_factor from interference, else 1)
margin      = P_rx - noise - required_snr
P(d)        = emits ? 1 / (1 + exp(-margin / transition_width)) : 0
```

`P(d)` is monotonic non-increasing in range. For a class with `emits = 0` it is exactly 0, whatever the draws, noise, degradations or receiver settings. The framework then multiplies by the degradation `pd_factor` (1 for RF) and compares with the detect draw.

Measurement: azimuth and elevation noise `sigma * noise_factor * draw`; range is `None`. Features: `band` (label), `hopping` (bool), `hop_rate_hz` (only when hopping; relative noise `sigma_hop_rate`), `rssi_dbm` (`P_rx` plus noise `sigma_rssi`). The reported class is sampled from the `default` confusion table.

Band plan (index in `band_<class>`, labels and centre frequencies in code, `rf.BANDS`):

| Index | Label | Centre (MHz) |
|---|---|---|
| 1 | 2.4 GHz | 2440 |
| 2 | 5.8 GHz | 5800 |
| 3 | 900 MHz | 900 |
| 4 | 433 MHz | 433 |
| 5 | 1.2-1.3 GHz | 1250 |

**Wi-Fi and Bluetooth confusers.** `false_alarms` takes exactly `false_alarm_slots x 7` uniforms per call (occur, azimuth, elevation, class, band, signal, hop), used or not. A slot produces a report when its first draw is below `false_alarm_probability x clutter_factor`. The report has the shape of a contact (no `truth_id`, no range, `band`, `rssi_dbm`, `hopping`, optional `hop_rate_hz`) and is labelled from the `wifi-bluetooth` row of the confusion table. Reports in a blocked sector are dropped after the draws are taken. During a full outage the hook still runs, so its draws are taken, but its reports are discarded.

**Parameters.** Every value is a project-authored fictional figure, `verified: false`.

| Name | Unit | Value | Register ID | Verified |
|---|---|---|---|---|
| `instrumented_range` | m | 3000 | F01 | no |
| `update_interval` | s | 1.0 | F01 | no |
| `rx_gain` | dB | 3 | F01 | no |
| `noise_floor` | dBm | -95 | F01 | no |
| `required_snr` | dB | 10 | F01 | no |
| `transition_width` | dB | 3 | F01 | no |
| `rain_attenuation` | dB/km | 0.03 | F01 | no |
| `sigma_azimuth` / `sigma_elevation` | deg | 9 / 18 | F01 | no |
| `sigma_rssi` | dB | 2.5 | F01 | no |
| `sigma_hop_rate` | ratio | 0.08 | F01 | no |
| `interference_noise_rise` | dB | 15 | F01 | no |
| `interference_false_alarm_gain` | ratio | 12 | F01 | no |
| `false_alarm_slots` | count | 2 | D09 | no |
| `false_alarm_probability` | ratio | 0.015 | D09 | no |
| `confuser_hop_rate` | Hz | 800 | D09 | no |
| `confuser_margin_span` | dB | 14 | D09 | no |
| `confuser_elevation_max` | deg | 25 | F01 | no |
| `emits_<class>` | flag | rotary 1 (D08), fixed-wing 1 (F01), bird 0, autonomous 0, default 1 | D08 / F01 | no |
| `emitter_power_<class>` | dBm | 20 / 20 / 0 / 0, default 20 | F01 | no |
| `band_<class>` | index | rotary 1 (D08), fixed-wing 3, bird 1, autonomous 1, default 1 | D08 / F01 | no |
| `hop_rate_<class>` | Hz | rotary 80, others 0 | F01 | no |
| confusion `default` | | see below | D09 | no |

**Confusion.** Rows are the true emitter, columns `rotary-small`, `fixed-wing-small`, `wifi-bluetooth`, `unknown`; every row sums to 1. Rotary: 0.80 / 0.03 / 0.09 / 0.08. Fixed-wing: 0.06 / 0.72 / 0.10 / 0.12. The `wifi-bluetooth` row labels false alarms: 0.10 / 0.04 / 0.72 / 0.14. The `bird` and `autonomous-small` rows are `unknown` = 1; they exist so a scenario may contain those classes, and are never sampled because those classes are never detected.

**Degradations.**
- `interference`: raises the noise floor by `interference_noise_rise x severity` dB, carried as an amplitude ratio in `Effects.noise_factor`. P(d) falls, every sigma grows by the same ratio, and `clutter_factor = 1 + gain x severity` raises the false-alarm rate. Stacked injects add in decibels.
- `outage`, `sector-outage`: handled by the framework.
- `haze`, `glare`, `clutter`, `wind-noise`: no effect on RF.
- Weather: only `rain` has any effect (0.03 dB/km, negligible at these bands; a few thousandths of P(d) at 2 km). Fog, dust, haze, wind and temperature do nothing. Time of day has no effect.

**Honesty note.** Fictional parameters built from open research datasets and published specifications, in fictional scenarios. D08 (DroneRF) and D09 (CardRF) are calibration-only: parameters are "calibrated from" them in structure, not trained on them, and none is marked verified. The band plan (2.4 and 5.8 GHz, 900 MHz and 433 MHz, 1.2/1.3 GHz, frequency hopping) comes from secondary sources, so it is `verified: false`. The RF detection-range table in the research is UNVERIFIED (Q-09); the 3 km range limit is a project value. Weather is modelled, not measured.

## Acoustic

**Purpose.** A microphone array that hears rotor and propeller noise out to a short, hard range limit, without needing line of sight. It gives a coarse bearing, no range, and tonal features (blade-pass frequency, harmonic count, tonal flag) that help tell a rotor from a fixed-wing from a bird. Wind is its main enemy.

**Equations.** Decibels in the processed band; `d` in metres (floored at 1 m).

```
level   = source_level - 20 log10(d) - absorption * d / 1000
wind    = wind_noise_base + wind_noise_slope * wind_speed
noise   = 10 log10( 10^(background/10) + 10^(wind/10) + [rain] 10^(rain_noise/10) ) + 20 log10(noise_factor)
SNR     = level + array_gain - noise
P(d)    = 1 / (1 + exp(-(SNR - detection_snr) / transition_width))
```

`P(d)` is monotonic non-increasing in range and in wind speed. Coverage is the profile `instrumented_range` (hard limit) with no elevation limit and no sight-line test. Time of day has no effect; of the modelled weather only wind speed and rain matter.

Measurement: azimuth and elevation noise as RF; range `None`. Features:
- `blade_pass_hz` = `blades x rpm / 60` plus noise `sigma_blade_pass` (a bird's wing-beat is one "blade" at its beat rate), never below 0.
- `harmonics` = `max(1, min(cap, 1 + floor((SNR - detection_snr) / harmonic_step)))`, where `cap` is `harmonics_<class>`.
- `tonal` = `harmonics >= tonal_min_harmonics`.
- `snr_db` = SNR plus noise `sigma_snr`.

**Parameters.** All `verified: false`.

| Name | Unit | Value | Register ID | Verified |
|---|---|---|---|---|
| `instrumented_range` | m | 300 | F01 | no |
| `update_interval` | s | 0.5 | F01 | no |
| `background_noise` | dB | 38 | F01 | no |
| `wind_noise_base` | dB | 20 | F01 | no |
| `wind_noise_slope` | dB/mps (dB per m/s) | 2.5 | F01 | no |
| `rain_noise` | dB | 44 | F01 | no |
| `absorption` | dB/km | 5 | F01 | no |
| `array_gain` | dB | 12 | F01 | no |
| `detection_snr` | dB | 6 | F01 | no |
| `transition_width` | dB | 2.5 | F01 | no |
| `harmonic_step` | dB | 3 | F01 | no |
| `tonal_min_harmonics` | count | 2 | F01 | no |
| `sigma_azimuth` / `sigma_elevation` | deg | 12 / 20 | F01 | no |
| `sigma_blade_pass` | Hz | 4 | D10 | no |
| `sigma_snr` | dB | 1.5 | F01 | no |
| `wind_noise_penalty` | dB | 12 | F01 | no |
| `source_level_<class>` | dB | rotary 78, fixed-wing 72, bird 52, autonomous 76, default 76 | F01 | no |
| `blades_<class>` | count | 2, 2, 1, 2, default 2 | D11 (rotor classes) / F01 | no |
| `rpm_<class>` | rpm | 6000, 3000, 720 (bird, UNVERIFIED), 5400, default 5400 | D11 / F01 | no |
| `harmonics_<class>` | count | 6, 3, 1, 6, default 4 | D10 / F01 | no |
| confusion `default` | | see below | D12 | no |

Resulting fundamentals: rotary 200 Hz, fixed-wing 100 Hz, autonomous 180 Hz, bird 12 Hz. The bird wing-beat band (5-20 Hz) against the drone fundamental (50-400 Hz) is UNVERIFIED (Q-09): `verified: false`.

**Confusion.** Rows are the true source, columns `rotary-small`, `fixed-wing-small`, `bird`, `unknown`; every row sums to 1. Rotary: 0.82 / 0.05 / 0.03 / 0.10. Fixed-wing: 0.12 / 0.62 / 0.10 / 0.16. Bird: 0.04 / 0.14 / 0.58 / 0.24. Autonomous: 0.80 / 0.05 / 0.03 / 0.12. Each source is most often labelled as itself (the autonomous rotor as `rotary-small`).

**Degradations.**
- `wind-noise`: an extra noise-floor penalty of `wind_noise_penalty x severity` dB (amplitude ratio in `noise_factor`), so P(d) falls and sigmas grow. It stacks with real wind from the weather.
- `outage`, `sector-outage`: handled by the framework.
- `haze`, `glare`, `clutter`, `interference`: no effect on the array.
- Weather: wind speed (including gusts) raises the noise floor linearly in decibels; `rain` adds a rain-noise source. Fog, dust, haze, temperature and visibility do nothing. Time of day has no effect.

**Honesty note.** Fictional parameters built from open research datasets and published specifications, in fictional scenarios. D10 (DroneAudioDataset, indoor recordings), D11 (DREGON) and D12 (Svanstrom multi-sensor set) are calibration-only: parameters are "calibrated from" them in structure, not trained on them, and none is marked verified. The 50-300 m detection range is from secondary literature (not in the data register), so the 300 m limit is a project value; long-range acoustic ranges are UNVERIFIED (Q-09). Weather is modelled, not measured.
