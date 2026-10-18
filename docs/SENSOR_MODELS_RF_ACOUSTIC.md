# Sensor models: RF and acoustic (fragment)

Fragment for the main session to merge into `docs/SENSOR_MODELS.md`, then delete. Code: `services/api/sim/sensors/rf.py`, `acoustic.py`, `decibel.py`. Profiles: `packs/sensor-profiles/rf-generic-passive.v1.yaml`, `acoustic-generic-array.v1.yaml`. Tests: `tests/test_sensor_rf.py`, `tests/test_sensor_acoustic.py`.

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

**Wi-Fi and Bluetooth confusers.** `false_alarms` takes exactly `false_alarm_slots x 7` uniforms per call (occur, azimuth, elevation, class, band, signal, hop), used or not. A slot produces a report when its first draw is below `false_alarm_probability x clutter_factor`. The report has the shape of a contact (no `truth_id`, no range, `band`, `rssi_dbm`, `hopping`, optional `hop_rate_hz`) and is labelled from the `wifi-bluetooth` row of the confusion table. Reports in a blocked sector are dropped after the draws are taken. No false alarms are produced during a full outage (the framework does not call the hook).

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
