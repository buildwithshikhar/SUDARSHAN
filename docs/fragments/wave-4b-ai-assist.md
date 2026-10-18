## Simulated AI assist

Code: `services/api/sim/tracking/assist.py`. Tests: `services/api/tests/test_tracking_assist.py`.

### Purpose

The assist gives the trainee a machine suggestion on each fused track: threat or no threat, a proposed class and a confidence. It exists to train calibrated trust, meaning when to accept a suggestion that is right most of the time and when to question it. It is a **stand-in**. There is no detector behind it, and it makes no accuracy claim.

### Design

- **Input.** A confirmed track's `Track.view()` (the fused track) and a `TruthRef`, the true class of the drone the track follows (`None` for a false track). The assist is a simulated classifier, so it may look at the truth; nothing it outputs carries the truth beyond the possibly wrong proposed class. It does not import the ledger or the tracker.
- **Flag.** A drone class is flagged as a threat with probability `hit_rate`. A bird, any other non-threat class (`NON_THREAT_CLASSES`, extended in wave 8) and a false track are flagged with probability `false_alarm_rate`.
- **Proposed class.** With probability `class_accuracy` the true class (for a false track the correct answer is `unknown`); otherwise a wrong label chosen evenly from `labels` without the correct one.
- **Confidence.** Centred on `confidence_correct_mean` when the flag is right and on `confidence_wrong_mean` when it is wrong, with `confidence_sigma` spread (the sum of four keyed uniforms, centred and scaled as `RngStreams.normalish`), clamped to 0.05 to 0.99 and rounded to three places. It is informative but imperfect.
- **When.** A track is assessed when it is `confirmed` and either never assessed or at least `reassess_s` (100 ticks at 20 Hz) since its last assessment. Tentative and coasting tracks return nothing and consume nothing. The epoch is the number of assessments of that track so far.
- **Draws are stateless and keyed.** Each draw is the first 53 bits of SHA-256 over the compact ASCII JSON of `[seed, "assist", track_id, epoch, purpose]`, divided by 2^53. Purposes are `flag`, `class`, `pick` and `conf0` to `conf3`. The result for a track's n-th assessment therefore does not depend on call order, on other tracks, or on the process, and the assist needs no RNG stream and no snapshot of draw positions. Only a counter and a last tick per track are kept (`state()`, `restore()`, `forget()`), as sorted-key JSON.
- **Output.** `Assessment.view()` is what a trainee may see: `track`, `tick`, `flag` (`threat` or `no-threat`), `proposed_class`, `confidence`, `source` = "simulated assist", `basis` = "configured hit and false-alarm rates; no real detector", `data_status` = `reference`. `Assessment.record()` adds `correct_flag` and `true_class` for the instructor log; those keys never appear in `view()` (tested).

### Parameters

All are project-authored fictional values. None is measured or sourced.

| Name | Unit | Value | Register | Verified |
|---|---|---|---|---|
| `hit_rate`: P(flag as threat, track is a threat) | probability | 0.90 | F01 | no |
| `false_alarm_rate`: P(flag as threat, track is a bird, other clutter or a false track) | probability | 0.08 | F01 | no |
| `class_accuracy`: P(proposed class is the true one) | probability | 0.85 | F01 | no |
| `labels`: pool a wrong class is drawn from | labels | rotary-small, fixed-wing-small, bird, unknown | F01 | no |
| `confidence_correct_mean` | confidence | 0.80 | F01 | no |
| `confidence_wrong_mean` | confidence | 0.55 | F01 | no |
| `confidence_sigma` | confidence | 0.12 | F01 | no |
| `reassess_s` | s | 5.0 | F01 | no |

### What the tolerance test shows

For each of the default configuration and a second one (hit 0.6, false alarm 0.3), the test assesses 40,000 independent (track, epoch) pairs (10,000 tracks, 4 epochs) for a threat, for a bird and for a false track. The empirical rate must lie within 5 binomial standard errors, 5 sqrt(p (1 - p) / n), of the configured value:

| Rate | Configured | Tolerance (n = 40,000) | Measured, default | Measured, alternative |
|---|---|---|---|---|
| Hit rate | 0.90 / 0.60 | 0.0075 / 0.0122 | 0.9005 | 0.5972 |
| False-alarm rate | 0.08 / 0.30 | 0.0068 / 0.0115 | 0.0804 (bird), 0.0805 (false track) | 0.3002, 0.3012 |
| Class accuracy | 0.85 | 0.0089 | 0.8496 | 0.8496 |

The same test checks that wrong classes are drawn evenly from the other labels, that mean confidence is higher when the flag is right (and near its configured centre), that confidence stays in 0.05 to 0.99, that the keyed uniform is uniform over 10 bins (100,000 draws, each bin within 5 sigma) and uncorrelated between purposes, and that outputs are identical across call orders, processes and hash salts.

It shows that the implementation delivers the configured rates and is reproducible. It does **not** show that any rate resembles a real detector, a real operator-assist tool or any field performance: the rates are inputs, not results.

### Honesty note

This module is a stand-in with configured rates. There is no real detector, no model trained on data, and no accuracy claim. Wherever the assist is shown it is labelled "simulated assist" with its basis, and its `data_status` is always `reference`, even on a track whose own data is verified, because the assist is configured and not measured. Any statement about how well trainees use an assist must come from our own measured pilot, not from these rates.
