<!-- Fragment for docs/SENSOR_MODELS.md, "Tracking" (wave 4b, subagent A). To be merged by the lead. -->

### Association errors

A track can only be confused where it has company. The tracker groups the gated (track, report) pairs of one sensor into *components* and asks the error policy (`sim/tracking/ambiguity.py`) only about **ambiguous** ones: two tracks inside each other's gates, or two reports inside one gate. A component with one track and one report is updated as it is and the policy is never consulted; the tests also hand the policy such a component and check that it offers no error and answers nominal. So two targets that stay apart cannot be mixed up by this model. (The tracker's own noise can still start a second track on a drone after a radar dropout; that is reported by the ledger as a split and happens without any error policy.)

The tracker takes one uniform per report from the `tracking` stream and hands the policy the one for the component's first report. The unit interval is cut into consecutive intervals in the order swap, split, merge, nominal; a mode that does not apply to the component has probability 0 and takes no interval. `c` is the association cost of a gated pair (normalised innovation squared), `N` the nearest-neighbour assignment, `k = swap_scale`.

| Mode | Applies when | What happens | Probability |
|---|---|---|---|
| swap | at least two tracks, two reports, and a complete alternative pairing with as many pairs as `N`, every pair inside the gate (components beyond 8 tracks or 8 reports are not searched) | the cheapest such alternative `A` is used: the tracks exchange reports | `swap_max * exp(-max(0, cost(A) - cost(N)) / k)` |
| split | at least one report left unpaired by `N` | `N` is applied, and the unpaired report with the best fit starts a new tentative track | `split_max * (1 - exp(-clutter_gain * n))`, `n` = unpaired reports |
| merge | `N` has at least two pairs | the dearest nominal pair (ties: larger track id) is dropped: that track gets no report this tick | `merge_max * exp(-c_d / k)`, `c_d` = cost of the dropped pair |

Costs are summed in sorted order and the exponential is `sim.detmath.exp`, so a draw gives the same resolution on every platform. The policy holds no state. `ErrorModel` refuses probabilities outside [0, 1], a non-positive scale, and maxima that sum to more than 1.

| Parameter | Unit | Value | Source | Verified |
|---|---|---|---|---|
| `swap_max` | probability | 0.5 | F01 | no |
| `swap_scale` | association cost (NIS) | 4.0 | F01 | no |
| `split_max` | probability | 0.15 | F01 | no |
| `merge_max` | probability | 0.15 | F01 | no |
| `clutter_gain` | per extra plot | 0.5 | F01 | no |

All five are project-authored fictional values (F01, `verified: false`); none is fitted to any real tracker.

**What it produces.** A swap that lasts one update is mostly undone by the filter's own velocity memory, so persistent swaps are uncommon at these maxima. Measured on the crossing geometry in `tests/tracking_cases.py` (two rotary-small drones at 15 m/s passing 1500 m from a radar, 900 ticks, 300 seeds, no false alarms): 7 runs end with a swap recorded by the ledger under the default policy and 4 under the nominal policy (which swaps only through noise). The documented swap is seed 47: the policy swaps the two tracks' reports at tick 624, and the ledger records the exchange at tick 648, when the last five reports of each track name the other drone. With the nominal policy that seed gives no swap. Two drones flying side by side 12 m apart are folded into one track by the tracker's own duplicate rule in 13 of 20 seeds with the nominal policy and 15 of 20 with the default one (700 ticks). These figures are a property of this toy tracker, not a claim about real ones.

### Truth ledger

`sim/tracking/ledger.py`. The ledger is told ground truth through a separate channel (`observe(tick, result, truth)`, where `truth` maps a report's reference number to the true drone id, or `None` for a false alarm) and never feeds anything back to the tracker. Its events are for the instructor and for scoring; `TRUTH_EVENT_KINDS` (`swap`, `split`, `merge`, `restored`) lists what a trainee's picture must filter out, because the payloads name the true drones.

- **Identity.** The plurality of true drones behind the last five reports a track used. False alarms stay in the window and count for nothing. It needs at least three real reports; ties go to the name that sorts first. Otherwise unknown.
- **Label registry.** When a track is confirmed, its current label is bound to its identity (as soon as that is known). A track is *consistent* when its label is bound to the drone it is following. Relabelling a track that was consistent binds the new label to the same drone; relabelling an inconsistent track binds nothing, so a wrong picture cannot be made right by naming it.
- **Swap.** A confirmed track's identity changes from drone A to drone B and its label no longer fits. A second track that changed to A on the same or the previous tick is its partner and shares the `error_id`. A track going back to the drone its label is bound to is not a new error.
- **Split.** One drone followed by two or more confirmed tracks for 40 consecutive ticks, once per episode. Copies made by the operator's own `track-split` are not counted.
- **Merge.** A track dropped with reason `duplicate` or `merged-error` whose identity and whose survivor's are different real drones.
- **Restored.** A swap when every live track it touched is consistent again (relabelling, a revert, or the tracks being dropped); a split when the drone is followed by fewer than two confirmed tracks (a fold, a merge or a drop); a merge when both drones again have a distinct confirmed track following them. Until then the error stays in `open_errors()`. Each error has an `error_id` that never repeats, and `restored` events carry `{error_id, error_kind, tracks, truths, tick}`.

Events are `LedgerEvent(kind, payload)`; payloads are plain JSON with the true identities and the tick. `state()` and `restore()` give sorted plain JSON and continue exactly. An operator merge of two tracks that follow different drones is not recorded as a tracker error; that is a command for the scoring layer to judge.

### Track commands

`sim/tracking/commands.py`: pure functions on a `Tracker`, each returning `CommandOutcome(ok, reason, events, effects)`. `events` are `(event_type, payload)` for the session log (`track.relabel`, `track.merge`, `track.split`, `track.drop`; a rejection is logged as `track.command_rejected`). `effects` tell the picture what to pass to the ledger (`("relabel", track, label)`, `("merge", survivor, absorbed)`, `("split", source, new)`, `("drop", track)`); `TruthLedger.on_effects` does that in order. A rejected command changes nothing.

| Action | Payload | Rule |
|---|---|---|
| `track-relabel` | `track`, `label`, optional `exchange` | label 1 to 24 printable characters after stripping; refused if another live track wears it, unless `exchange` is set, which gives that track this one's old label in the same step |
| `track-merge` | `tracks`: two ids | two different live tracks, neither tentative; the lower id survives with its filter state untouched, gaining the other's class votes and sensors (reference data taints verified); the other is dropped with reason `merged` |
| `track-split` | `track` | clones a live track; the copy is confirmed (tentative stays tentative), born now, and competes for reports, so one starves and is folded back unless there really are two targets |
| `track-drop` | `track` | drop with reason `operator` |

`apply` also refuses unknown actions, unknown fields, wrong types and unknown tracks, with a reason. There is no undo: a command is reversed only by another logged command, so the log tells the whole story and a replay needs no special case.

### Cueing a sensor to a track

`sim/tracking/cueing.py`: `cue_for_track(tracker, suite, tick, sensor_id, track_id, narrow=True)` projects the track's estimate to the cue tick (`x + v dt`, with `dt` since the track was last predicted), takes the bearing and elevation from the sensor's own position, and sends a `CueRequest` (`narrow` or `slew`) to the suite. A narrow cue asks for a field of view of `2 atan(3 sigma_position / range)`; the sensor clamps it between its narrow and wide fields, so a well-known track gets a tight look and an uncertain one a wide look. The sensor decides, and its own reason is passed on: a radar "cannot be cued", a sensor in outage is "out of service", an elevation outside its limits is refused. An unknown sensor or track is refused before the sensor is asked. The payload is JSON only: `{sensor, track, bearing_deg, elevation_deg, fov_deg, accepted, reason}`. The cue points at the *estimate*, so a drifted track misses the drone, and a narrowed camera can lose a target it was not told about. `apply_cue` runs the `sensor-cue` action (`sensor`, `track`, optional `narrow`).

### Honesty note

This is fictional tracker behaviour. The error model, its probabilities and the ledger's windows and thresholds are project-authored (F01, `verified: false`); they are not a model of any real tracker or fusion system and make no claim about how often real ones err. The figures above describe this simulator on fictional scenarios built from open research datasets and published specifications.
