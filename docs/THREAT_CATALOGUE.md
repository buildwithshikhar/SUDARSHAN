# Threat catalogue

The classes of contact a scenario may fly: eight drone classes and three kinds of airborne clutter. Each class is one `threat-class.v1` file in `packs/threats/<id>.v1.yaml` (contract in `services/api/app/contracts/threat_class.py`, JSON Schema in `packs/schemas/threat-class.v1.json`), loaded and checked by `services/api/sim/catalogue.py`. The catalogue answers three questions: how may a class move (its envelope), what does it look, sound and transmit like to each sensor (its signature), and which operator-vocabulary class is it scored as (its recognition class).

## Purpose

- Give scenarios, sensors and scoring one list of classes, so a class cannot exist in a scenario and be missing from a sensor (Q-21).
- Give every class the kinematic limits a scenario threat must stay inside (`python -m app.cli sim-check` and the tests enforce it).
- Keep the sensor profiles and the catalogue in step: a test asserts that every sensor profile resolves each class to the catalogue's signature and has a confusion-table row for it.

## Honesty

- Every class is fictional and generic. No class names a real vehicle, manufacturer or product, and no figure is a real performance figure. The classes are built from open research datasets and published specifications, in fictional scenarios.
- Kinematics and signatures only. A class has an envelope and a signature, nothing else: no guidance, payload, targeting or terminal behaviour, and no instruction for building or operating a vehicle. The contract has no field that could carry one.
- Every value is project-authored: register ID F01, `verified: false`. The exceptions are the figures the shipped sensor profiles already cited for the three original classes, which keep their register IDs (D08, D10, D11, D12) and are still `verified: false`. The UAV Database (X01, CC0) has **not been downloaded**, so no value is taken from it; extracting envelopes from it is pending (Q-11). Replace a value's F01 with X01 only when the figure has been extracted and checked.
- `uas_group` is the US DoD UAS group used as a neutral public reference ([02-research.md](02-research.md) section 2). It is a label and not a bound: the group figures are not checked against the envelope. The shipped `fixed-wing-small` ceiling (1200 m, the limit the Kestrel scenario already uses) is above the published Group 1 ceiling. The Group 3 speed and altitude cells are unverified in the research, so every `fixed-wing-large` value is unverified.
- Wing-beat of a bird as one blade at 12 Hz (720 rpm) comes from a secondary source and is unverified (Q-09).

## Classes

Generated from `packs/threats/*.v1.yaml` by `python -m sim.catalogue` (a test fails if this block drifts from the files). Each cell is the value in the unit named in the column header; a register ID in brackets follows when it is not F01. The Register column lists the IDs used by the row, and Verified the parameters marked `verified: true` (none).

<!-- BEGIN GENERATED: catalogue -->

#### Classes

| Class | Category | Scored as | UAS group | Default disposition | Summary |
|---|---|---|---|---|---|
| `autonomous-small` | drone | `rotary-small` | 1 | hostile | A multirotor that flies a stored route with no control link. It has the airframe of a rotary-small drone and transmits nothing, so a passive RF detector never hears it. |
| `balloon` | clutter | `balloon` | none | clutter | A free balloon drifting with the wind: very slow, low radar return, no radio, no sound, cold in thermal. |
| `bird` | clutter | `bird` | none | clutter | A bird in flight: slow wing-beat, no radio, no engine. The commonest confuser for a small drone. |
| `civil-drone` | drone | `rotary-small` | 1 | civil-permitted | A civil quadcopter flying a filed flight plan. Every sensor sees it as a small rotary drone; the flight plan, not the signature, tells it apart. |
| `decoy-small` | drone | `rotary-small` | 1 | hostile | A cheap, lightweight multirotor flown in numbers: weak radar return, quiet, no radio link and almost no thermal contrast. Slower than a camera quadcopter. |
| `fixed-wing-large` | drone | `fixed-wing-large` | 3 | hostile | A generic large fixed-wing drone of the Group 3 size class, flying high and fast on a long route. Every value is unverified; the Group 3 speed and altitude cells are unverified in the research. |
| `fixed-wing-medium` | drone | `fixed-wing-medium` | 2 | hostile | A generic long-endurance fixed-wing drone flying a one-way or loitering route: faster, with a larger radar and optical size, a piston-engine tone and a 900 MHz telemetry link. Group 2 size class. |
| `fixed-wing-small` | drone | `fixed-wing-small` | 1 | hostile | A small electric fixed-wing drone flying a route at cruise speed: faster than a quadcopter, cooler in thermal, with a 900 MHz link. |
| `fpv-small` | drone | `fpv-small` | 1 | hostile | A fast, agile quadcopter flown through a live video link. Faster and louder than a camera quadcopter, with a higher-pitched rotor tone and a hopping 5.8 GHz video and control link. |
| `kite` | clutter | `kite` | none | clutter | A tethered kite: slow, very low radar return, no radio and no sound source, bright and distinctive to a daylight camera. |
| `rotary-small` | drone | `rotary-small` | 1 | hostile | A commercial off-the-shelf quadcopter flown by an operator over a control link. |

#### Envelope

| Class | `max_speed` (m/s) | `cruise_speed` (m/s) | `max_accel` (m/s2) | `max_climb` (m/s) | `max_descent` (m/s) | `max_turn_rate` (deg/s) | `min_altitude` (m) | `max_altitude` (m) | Register | Verified |
|---|---|---|---|---|---|---|---|---|---|---|
| `autonomous-small` | 18 | 10 | 4 | 5 | 3.5 | 90 | 5 | 400 | F01 | none |
| `balloon` | 6 | 1.5 | 0.5 | 3 | 3 | 30 | 20 | 1500 | F01 | none |
| `bird` | 18 | 9 | 6 | 4 | 5 | 120 | 8 | 180 | F01 | none |
| `civil-drone` | 16 | 8 | 4 | 5 | 3.5 | 90 | 5 | 120 | F01 | none |
| `decoy-small` | 12 | 8 | 3 | 3 | 3 | 60 | 10 | 250 | F01 | none |
| `fixed-wing-large` | 90 | 65 | 2.5 | 8 | 10 | 8 | 300 | 5400 | F01 | none |
| `fixed-wing-medium` | 55 | 38 | 2 | 5 | 6 | 12 | 100 | 1000 | F01 | none |
| `fixed-wing-small` | 31 | 24 | 2.5 | 4 | 5 | 20 | 60 | 1200 | F01 | none |
| `fpv-small` | 35 | 22 | 12 | 12 | 12 | 180 | 2 | 300 | F01 | none |
| `kite` | 12 | 3 | 2 | 3 | 3 | 60 | 10 | 150 | F01 | none |
| `rotary-small` | 18 | 10 | 4 | 5 | 3.5 | 90 | 5 | 400 | F01 | none |

#### Signature: radar, camera and thermal parameters

| Class | `rcs` (dBsm) | `aspect_swing` (dB) | `size` (m) | `contrast` (ratio) | `contrast_eo` (ratio) | Register | Verified |
|---|---|---|---|---|---|---|---|
| `autonomous-small` | -16 | 4 | 0.39 | 1 | 1 | F01 | none |
| `balloon` | -26 | 0 | 0.8 | 0.1 | 1.2 | F01 | none |
| `bird` | -22 | 3 | 0.79 [D12] | 1 | 1 | D12, F01 | none |
| `civil-drone` | -16 | 4 | 0.39 | 1 | 1 | F01 | none |
| `decoy-small` | -20 | 3 | 0.3 | 0.2 | 0.8 | F01 | none |
| `fixed-wing-large` | 3 | 6 | 6 | 1 | 1 | F01 | none |
| `fixed-wing-medium` | -3 | 5 | 3 | 0.9 | 1 | F01 | none |
| `fixed-wing-small` | -10 | 4 | 1.2 | 0.8 | 1 | F01 | none |
| `fpv-small` | -18 | 4 | 0.32 | 1.1 | 1 | F01 | none |
| `kite` | -30 | 2 | 1 | 0.15 | 1.3 | F01 | none |
| `rotary-small` | -16 | 4 | 0.39 [D12] | 1 | 1 | D12, F01 | none |

#### Signature: RF and acoustic parameters

| Class | `emits` (flag) | `emitter_power` (dBm) | `band` (index) | `hop_rate` (Hz) | `source_level` (dB) | `blades` (count) | `rpm` (rpm) | `harmonics` (count) | Register | Verified |
|---|---|---|---|---|---|---|---|---|---|---|
| `autonomous-small` | 0 | 0 | 1 | 0 | 76 | 2 [D11] | 5400 [D11] | 6 [D10] | D10, D11, F01 | none |
| `balloon` | 0 | 0 | 1 | 0 | -10 | 0 | 0 | 1 | F01 | none |
| `bird` | 0 | 0 | 1 | 0 | 52 | 1 | 720 | 1 | F01 | none |
| `civil-drone` | 1 | 20 | 1 | 80 | 78 | 2 | 6000 | 6 | F01 | none |
| `decoy-small` | 0 | 0 | 1 | 0 | 68 | 2 | 7200 | 4 | F01 | none |
| `fixed-wing-large` | 1 | 33 | 5 | 0 | 86 | 3 | 2400 | 6 | F01 | none |
| `fixed-wing-medium` | 1 | 30 | 3 | 0 | 80 | 2 | 3600 | 5 | F01 | none |
| `fixed-wing-small` | 1 | 20 | 3 | 0 | 72 | 2 | 3000 | 3 | F01 | none |
| `fpv-small` | 1 | 27 | 2 | 120 | 82 | 2 | 9000 | 6 | F01 | none |
| `kite` | 0 | 0 | 1 | 0 | -10 | 0 | 0 | 1 | F01 | none |
| `rotary-small` | 1 [D08] | 20 | 1 [D08] | 80 | 78 | 2 [D11] | 6000 [D11] | 6 [D10] | D08, D10, D11, F01 | none |

<!-- END GENERATED: catalogue -->

Notes on particular classes:

- `autonomous-small` is the airframe of `rotary-small` with no control link: it emits nothing, so a passive RF detector never hears it. Its acoustic figures (76 dB, 5400 rpm) are the ones the shipped acoustic profile already carried for it, slightly quieter than `rotary-small`.
- `civil-drone` has the signature of `rotary-small` and a lower altitude ceiling. Its default disposition is `civil-permitted`; telling it from a hostile quadcopter is done with the filed flight plan, not the sensors.
- `decoy-small` is cheap and lightweight: weaker radar return, quieter, no radio and almost no thermal contrast, and slower. It is scored as `rotary-small`.
- `kite` and `balloon` have no acoustic source (a source level of -10 dB, below the array's noise floor at every range) and no radio. Kite is bright and distinctive in a visible-band camera; balloon is cold in a thermal camera.

## How a class maps to the sensor profiles

The signature uses the sensor profiles' parameter names without the `_<class>` suffix. For a class `fixed-wing-medium` and the signature name `rcs`, the radar profile parameter is `rcs_fixed_wing_medium` (hyphens become underscores). A sensor looks up `<name>_<class>` and falls back to `<name>_default`, so a profile lists a class only where it differs from its default; the test resolves every class through the same fallback.

| Signature name | Read by | Profile parameter |
|---|---|---|
| `rcs`, `aspect_swing` | radar | `rcs_<class>`, `aspect_swing_<class>` |
| `size` | day and night-vision cameras, thermal camera | `size_<class>` |
| `contrast` | thermal camera | `contrast_<class>` (1.0 is the multirotor reference) |
| `contrast_eo` | day and night-vision cameras | `contrast_<class>` = the camera's `contrast_default` times this factor |
| `emits`, `emitter_power`, `band`, `hop_rate` | passive RF detector | `emits_<class>`, `emitter_power_<class>`, `band_<class>`, `hop_rate_<class>` (band indices: 1 2.4 GHz, 2 5.8 GHz, 3 900 MHz, 4 433 MHz, 5 1.2-1.3 GHz) |
| `source_level`, `blades`, `rpm`, `harmonics` | acoustic array | `source_level_<class>`, `blades_<class>`, `rpm_<class>`, `harmonics_<class>` |

The envelope converts to the scenario's `KinematicLimits` (`Catalogue.limits_for`): `max_speed` to `max_speed_mps`, `max_accel` to `max_accel_mps2`, and so on. `cruise_speed` is a typical route speed for scenario authors and is not a limit. A scenario threat's own limits may be narrower than the envelope, never wider (`Catalogue.check_scenario`).

## Labels and the look-alike rule

A sensor reports a coarse label, not the truth class. The catalogue's `recognition_class` is the class a truth class is scored as in the operator vocabulary: `rotary-small`, `fpv-small`, `fixed-wing-small`, `fixed-wing-medium`, `fixed-wing-large`, `bird`, `kite`, `balloon`. `autonomous-small`, `decoy-small` and `civil-drone` are scored as `rotary-small`; the other five classes are their own.

Each sensor's confusion table has one row per truth class. The rule behind the rows, set out per sensor in [SENSOR_MODELS.md](SENSOR_MODELS.md) ("Class coverage and the look-alike rule"):

- A sensor mostly reports a class as its own look-alike family. Radar cannot tell `fpv-small` from `rotary-small`, so it labels it `rotary-small` most of the time and `fpv-small` only sometimes; a decoy, a pre-programmed multirotor and a civil quadcopter are labelled like a quad.
- Medium and large fixed-wing are labelled `fixed-wing-small`, `fixed-wing-medium` or `fixed-wing-large`, with the sensor's size resolution deciding the spread.
- A kite and a balloon are labelled `bird`, `kite`, `balloon` or `unknown`. A visible-band camera resolves them best when it recognises the target; radar and acoustic mostly say `unknown` or `bird`; the thermal camera sees a balloon poorly.
- The trainee separates the classes a sensor cannot, by combining features and behaviour.

## Not in the catalogue

Deliberately absent:

- Any real aircraft, vehicle, manufacturer, product or performance figure, and any real site.
- Guidance, targeting, payload, release, terminal-attack or warhead logic, and any instruction for building, arming or operating a vehicle.
- Swarm and flock behaviour (a later step) and effector classes (rule packs hold the fictional ROE and effector classes).
- Measured data. Nothing here is `verified: true`; X01 extraction is pending (Q-11).
- Classes beyond these eleven (helicopters, crewed aircraft and ground clutter are not modelled).
