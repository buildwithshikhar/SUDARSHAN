### Tracker and fusion

Code: `services/api/sim/tracking/` (`measurement.py`, `kalman.py`, `model.py`, `associate.py`, `tracker.py`, `track.py`, `config.py`). Tests: `tests/test_tracker_core.py`.

**Input contract.** The tracker's only input is a `Measurement` built from `Detection.trainee_view()`: noisy azimuth and elevation, optional range and radial speed with the one-sigma values actually applied, a reported class, and `data_status`. `Measurement.from_view` refuses a dict that carries `truth_id`, so the algorithm cannot depend on ground truth; ground truth reaches the ledger by a separate channel (the report's reference number, assigned by the caller) and never flows back. Sensor positions are known to the tracker, as a trainee knows where their own sensors are.

**Reference data (Q-20).** Every detection carries `data_status`: `reference` unless every parameter and confusion table of its sensor profile is `verified: true`. All six shipped profiles contain unverified values, so every report, track and assist view a trainee receives is `reference`. A track is `reference` as soon as one report behind it was. The console must show these figures as reference data, never as measured performance.

**State and filter.** Each track holds six states (east, north, up position and velocity) and a 6×6 covariance, in plain Python floats using only `+ - * /` and `sqrt` so snapshots and hashes are bit-identical on every platform. Prediction is a constant-velocity model with continuous white-noise acceleration (`accel_sigma_mps2`), so the result does not depend on how often it is stepped (tested). A report becomes up to four scalar measurements of the predicted state, linearised about it: range, azimuth, elevation (angles in radians, azimuth wrapped) and radial speed. They are applied one at a time, each innovation corrected for the state already moved, so no matrix inverse is needed.

**Association.** For each sensor's reports at a tick, each (track, report) pair is gated on the normalised innovation squared (the sum of each row's innovation²/S), against the 99 % chi-square value for the number of rows (`CHI2_GATE`). Pairs that share a track or a report form a *component*. A component of one track and one report is updated directly. Anything larger is *ambiguous* (two tracks inside each other's gates, or a second report such as another target or a clutter plot inside one gate) and goes to the ambiguity policy; the default is the nearest-neighbour assignment, so the tracker alone fails only as noise makes it. Exactly one uniform is taken from the `tracking` stream per report, whatever happens, so the stream position depends only on how many reports were processed.

**Initiation.** A report with a range that no track claims starts a tentative track; its radial speed seeds the velocity. Bearing-only reports that no track claims (EO/IR, RF, acoustic) are held for `triangulation_window_s`; two from different sensors whose rays pass within `triangulation_gate` miss distances, and are not nearly parallel, start a track at the midpoint. Clutter plots start tentative tracks that are dropped unconfirmed.

**Lifecycle.** Tentative → confirmed after `confirm_hits` ticks with an associated report inside `confirm_window_s`, otherwise dropped (`unconfirmed`, also after `tentative_drop_s` of silence). Confirmed → coasting after `coast_after_s` without a report; a coasting track that gets a report resumes under the same ID; after `drop_after_s` it is dropped (`lost`). Two confirmed tracks whose position and velocity estimates stay statistically indistinguishable for `duplicate_hold_s` are one track: the younger is dropped (`duplicate`, `merged_into` the older). If they were two targets, that is a merge error (see the error model).

**Fusion of class.** Each track counts the classes its reports named (ignoring `unknown`); the class estimate is the most voted and `class_support` its share.

**Parameters.** All tracker parameters are project-authored (register F01, `verified: false`). `tests/test_tracker_core.py` and `tests/test_tracking_wiring.py` check that every field of `TrackerConfig` appears in this table.

| Name | Unit | Value | Meaning |
|---|---|---|---|
| `accel_sigma_mps2` | m/s² | 2.0 | process noise: one-sigma acceleration of a manoeuvring small drone |
| `init_speed_sigma_mps` | m/s | 25 | speed uncertainty of a new track |
| `gate_scale` | ratio | 1.0 | multiplies the 99 % chi-square gate |
| `min_sigma_angle_deg` | deg | 0.05 | floor on an angular sigma |
| `min_sigma_range_m` | m | 1.0 | floor on a range sigma |
| `default_sigma_radial_mps` | m/s | 1.0 | radial-speed sigma when a report gives none |
| `confirm_hits` | count | 3 | associated ticks to confirm |
| `confirm_window_s` | s | 10 | time allowed to confirm |
| `tentative_drop_s` | s | 4 | silence that drops a tentative track |
| `coast_after_s` | s | 3 | silence before a confirmed track coasts |
| `drop_after_s` | s | 15 | silence before a coasting track is dropped |
| `duplicate_gate` | chi-square, 6 dof | 12.592 | indistinguishability limit for folding two tracks |
| `duplicate_hold_s` | s | 3 | time they must stay indistinguishable |
| `triangulation_window_s` | s | 0.5 | how long bearing-only reports wait for a partner |
| `triangulation_min_angle_deg` | deg | 8 | rays closer than this are too parallel |
| `triangulation_gate` | ratio | 3 | accepted miss distance in sigmas |
| `triangulation_speed_mps` | m/s | 30 | allowance for target motion between the two reports |
| `triangulation_max_range_m` | m | 8000 | longest ray used |
