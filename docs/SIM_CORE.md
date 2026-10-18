# Simulation core

The sim core (`services/api/sim/`) is the single source of truth for every session. It is pure Python and numpy: it imports nothing from FastAPI or the database, opens no sockets, starts no threads and never reads the wall clock. Given the same **scenario spec, seed and action log**, it produces the same events and the same state hash, tick for tick, in any process on any machine. Replay, re-scoring, snapshots for director mode, counterfactual review and solvability checks all depend on that, so it is tested in CI. The decision record is [ADR-014](DECISIONS.md#adr-014--rng-scheme-and-tick-model).

Threat behaviour is kinematics only: a drone flies its scripted route inside its class limits. There is no guidance, pursuit or terminal behaviour, and the contracts have no field that could carry one (locked rule 2).

## Contracts

Versioned Pydantic models in `services/api/app/contracts/`, exported as JSON Schema (draft 2020-12) to `packs/schemas/` and generated as TypeScript into `apps/web/src/contracts/`.

| Contract | File | Notes |
|---|---|---|
| `scenario.v1` | JSON | World (flat terrain, play area, time of day, weather), zones, defended assets, sensor placements, threats with class limits and routes. Local east-north-up metres; no latitude or longitude. |
| `rulepack.v1` | YAML | Fictional, editable rules of engagement, generic effector classes, scoring weights (sum to 1) and timing thresholds. |
| `sensor-profile.v1` | YAML | Every numeric parameter is `{value, unit, source_id, verified}`; `source_id` must be a row in [DATA_REGISTER.md](DATA_REGISTER.md). |
| `event-record.v1` | JSONL | `{seq, t, type, actor, payload, prev_hash, hash}` |
| `action-record.v1` | in a session record | A trainee or instructor input, applied at the start of its tick. |
| `session-record.v1` | JSON | Inputs (scenario reference, seed, ticks, actions) and outputs (events, final state hash) of one session. |

Every pack carries `contract`, `id`, a semantic `version` and `fictional: true`. Unknown fields are refused, models are immutable, and the YAML loader is safe-only and refuses duplicate keys.

Change a contract in the Pydantic model, then run `make schemas` and commit the regenerated `packs/schemas/` and `apps/web/src/contracts/`. CI fails if either is stale (`tests/test_contracts.py`, `npm run contracts:check`). A breaking change is a new version (`scenario.v2`), never an edit to v1 once packs exist in the field.

## Tick model

- Fixed 20 Hz: one tick is exactly 0.05 s of simulation time. Time is `tick / 20`, computed from the integer tick, never accumulated.
- The server decides when to tick. Pause means "stop calling `step`", so pause and resume never reach the simulation and cannot change a replay.
- `World.step` always runs in this order:
  1. apply the actions recorded for this tick, in log order;
  2. spawn threats whose spawn tick has come, in scenario order (`spawn_tick = ceil(spawn_s × 20)`, rounded first so 0.15 s is tick 3);
  2b. if the world has a sensor picture (wave 4b, below): the sensors report, the tracker updates, the ledger and the assist run;
  3. advance the wind gust;
  4. move every active drone, in scenario order, then retire drones that left the play area;
  5. increment the tick.
- Events carry the tick being processed. A session ends with `session.end`, whose payload holds the final state hash.

Per drone, per tick: waypoint arrival and mode changes, heading (turn-rate limited), airspeed (acceleration limited), altitude (climb and descent limited and clamped to the altitude band), then position from the air velocity plus the wind. A waypoint counts as reached within the larger of 15 m and the current turn radius, so a slow-turning airframe cannot orbit it. Holding and end-of-route loitering fly a clockwise 120 m orbit. On route end a threat loiters, loops or despawns, as the scenario says.

Measured on the build laptop (Apple silicon, Python 3.12): the Kestrel scenario with two drones runs 10,000 ticks in 0.064 s, about 6.4 µs per tick (155,000 ticks per second); a snapshot is about 9.5 kB of JSON.

## Random streams

- One numpy `PCG64` generator per subsystem, seeded from `SeedSequence(seed, spawn_key=(key,))`, where `key` is the first 8 bytes of SHA-256 of the stream name.
- Streams: `weather`, `kinematics`, `spawn`, `sensors`, `tracking`, `adversary` (`sim/rng.py`, `STREAMS`). A stream depends only on the seed and its own name, so adding a stream or drawing more from one never shifts another. New subsystems add a name at the end of `STREAMS`.
- Uniform draws use `Generator.random()` (53 random bits times 2⁻⁵³, exact). Gaussian-like noise uses the sum of four uniforms (`normalish`: zero mean, unit variance, bounded at ±2√3), because numpy's normal sampler can call the platform `log`.

## Determinism rules for contributors

1. No wall-clock time, `random`, `uuid4`, `os.urandom` or Python's `hash()` in `sim/`. Draw from a named stream.
2. Iterate in a fixed order: scenario order, sorted keys or explicit lists. Never iterate a `set`, and never rely on the order of a dict built from unordered input.
3. Values that feed the state hash use only `+ - * /`, `sqrt`, `floor`, comparisons and the polynomials in `sim/detmath.py`. Do not use `math.sin`, `math.atan2`, `numpy` transcendentals or numpy reductions (`sum`, `mean`) on hashed state: they may differ in the last bit between platforms. Keep headings as unit vectors.
4. Hashed state is plain JSON (Python `float`, `int`, `str`, `bool`, `None`, lists and dicts). Convert numpy scalars with `float()`.
5. Event payloads hold JSON values only; positions and speeds are rounded to 3 decimals there for readability. The state keeps full precision.
6. A change to a constant in `sim/constants.py` or to the tick order is a behaviour change: regenerate the golden files on purpose and say why in the commit.

## Event log

`sim/eventlog.py`. Each record's `hash` is SHA-256 of the canonical JSON (sorted keys, compact separators, UTF-8, no NaN) of its other six fields; `prev_hash` links it to the previous record (64 zeros for the first). `verify(records, expected_head=None)` returns the position of the first bad record or `None`. Editing a record is caught at that record. A tamperer who also recomputes its hash is caught at the next record. The last record, and truncation, are caught only against a head kept elsewhere: wave 13b signs the head.

## Snapshot, restore and replay

- `World.snapshot()` returns the full state (tick, weather and gust, every RNG stream's state, every drone, event count and head) plus the event log so far, as plain JSON. `World.restore(spec, snapshot)` checks the scenario ID and version, the event chain and head, and the threat list, then continues exactly. Restoring at tick N and running to M gives the same state hash and events as a straight run (`tests/test_sim_world.py`).
- `World.state_hash()` is SHA-256 of the canonical state without the event records; the event head stands in for them.
- `sim.replay.run(spec, seed, actions, ticks)` returns the world and a `session-record.v1`. `session-record.v1` has a `picture` flag (default false; records without it read as false), set by `run(..., picture=True)`. `replay(spec, record)` re-runs it, with a picture when the record says it had one, and reports the first divergent event and whether the final state hash matches.

## Sensor framework

`services/api/sim/sensors/` (wave 4a). Sensors read the world and produce noisy detections; they never change it. Four things are shared by every modality model, so the models stay short and behave alike.

- **Interface.** `Sensor.detect(world, t, rng)` is a template method. In order: bring the cue pointing up to tick `t`; skip unless `t` is a multiple of the profile's `update_interval`; build the `Environment` (modelled weather, visibility, wind, daylight) and the `Effects` of active degradations; then, for every active drone in scenario order, take the draws, check coverage, ask the model for `p_detect(obs)`, scale it by the degradation factor and compare with the detect draw; on a hit ask the model for `measure(obs)`. A model also may add `false_alarms`, `degradation_effect` and `precision_factor`.
- **Draw budget.** Every candidate target consumes 18 uniforms from the `sensors` stream (detect, classify, four 4-uniform noises) whether or not it is in range, blocked, missed or detected. An outage, a cue or a change of detection probability therefore never shifts the noise a later target receives. The stream order is sensors in scenario order, then targets in scenario order; adding a sensor to a scenario shifts later sensors' numbers, as any scenario edit would. False-alarm hooks must also take a fixed number of draws per call, and the framework calls the hook during an outage too (discarding its reports), so an outage never shifts the stream.
- **Degradations** (`Degradation`) are data: sensor, kind, window in ticks, severity, and a clockwise sector for `sector-outage`. `outage` and `sector-outage` are handled by the framework; other kinds (`clutter`, `haze`, `glare`, `interference`, `wind-noise`) are interpreted by the model, which returns `Effects` (probability factor, sigma factor, clutter factor) or nothing. Effects combine in injection order. Wave 10b turns instructor injects into these.
- **Cueing** (`CueRequest`, `Sensor.cue`). A slew cue points the sensor at a bearing and elevation at the profile's `slew_rate` (instant if absent); a narrow cue also tightens the field of view between `fov_narrow` and `fov_wide` (immediately, like a zoom: `cue` applies the new field of view before it returns, while the slew starts with the next tick). A cue holds for `cue_hold` seconds (default 10), then the sensor returns to its boresight. Only models with `supports_cue` accept cues, and the profile must then give `fov_wide` and `fov_narrow`. A sensor with a field of view only sees targets inside it, so a narrowed sensor can lose a target it was not told about; precision is tied to the field through the model's `precision_factor`.
- **Profiles.** `SensorParams` wraps a validated `sensor-profile.v1`. `value(name, unit)` refuses a profile written in another unit; `require` lists every missing parameter at once; `for_class(prefix, class_id)` reads `<prefix>_<class_id>` (hyphens become underscores) and falls back to `<prefix>_default`; `unverified` lists every value still marked `verified: false`; `check_sources(register)` refuses a source ID that is not a row in [DATA_REGISTER.md](DATA_REGISTER.md). A parameter without a unit, a register-shaped source ID and a `verified` flag is refused by the contract itself.
- **Confusion tables** are part of the profile (`confusion`, keyed by context such as `default` or `thermal`): labels, one row per true class, one register ID and `verified` flag for the whole matrix, rows summing to 1 (refused otherwise). `build_sensors` refuses a scenario with a threat class that a model's table has no row for.
- **Output.** `Detection` carries noisy azimuth and elevation, optional range and radial speed, the one-sigma values actually applied, a reported class and modality features. `truth_id` links it to the drone for scoring and the instructor; `Detection.trainee_view()` omits it, and false alarms have the same shape as real contacts.

The four modality models are in `sim/sensors/radar.py`, `eoir.py` (modalities `eo` and `ir`), `rf.py` and `acoustic.py`, registered when `sim.sensors` is imported. Their equations, parameters with register IDs and honesty notes are in [SENSOR_MODELS.md](SENSOR_MODELS.md). Micro-Doppler in the radar reuses the detect draw divided by `p` (uniform given a hit) so it costs no extra random numbers.
- **State.** `Sensor.state()` and `SensorSuite.state()` return plain JSON (pointing, cue expiry, degradations); with the `sensors` stream state in the world snapshot, restoring both continues exactly (`tests/test_sensor_framework.py`). Inside a session the suite belongs to the sensor picture, which ticks it (below).

Geometry (`Geometry.between`) gives compass azimuth, elevation, slant and ground range, radial speed and aspect. It uses `detmath.atan2` and the other deterministic maths (`exp`, `log`, `wrap360`), never `math.atan2`, because detections reach the event log.

## Sensor picture and tracking

`services/api/sim/tracking/` (wave 4b). `Picture` bundles a `SensorSuite`, a `Tracker`, a `TruthLedger` and an `AiAssist`. A `World` built with `picture=Picture.build(spec, seed)` runs `Picture.update` once per tick (step 2b, after the tick's actions and spawns, before anything moves) and sends the actions `track-relabel`, `track-merge`, `track-split`, `track-drop` and `sensor-cue` to `Picture.apply`; a rejected one is logged as `action.rejected`. Without a picture the world is unchanged and hashes as before.

- **State.** `World.state()` gains a `picture` key only when one is attached, so every existing golden file is untouched. It holds the suite, tracker, ledger and assist state, the report counter and the ground-truth reference of recent reports (kept for 2 s for triangulation, then forgotten). Snapshots copy; `World.restore(spec, snapshot, picture=Picture.build(spec, seed))` needs a picture exactly when the snapshot has one.
- **Replay.** `replay.run(..., picture=True)` and `replay.replay(..., picture=True)`. The session record does not yet say whether it had a picture; the caller must know (wave 5 always records with one).
- **Streams.** The tracker takes exactly one uniform per report from `tracking`; the sensors keep the `sensors` stream; the assist uses no stream (keyed SHA-256 draws), so nothing here shifts another subsystem.
- **Events.** `track.init|confirm|coast|resume|drop`, `track.relabel|merge|split`, `sensor.cue` carry no ground truth (`picture.TRAINEE_EVENT_TYPES`). `ledger.swap|split|merge|restored` and `assist.assess` name true drones and are for the instructor and scoring (`TRUTH_EVENT_TYPES`). The model, the error model and the assist are in [SENSOR_MODELS.md](SENSOR_MODELS.md), "Tracking".
- **Tracker input.** `Measurement.from_view(Detection.trainee_view())` only; it refuses `truth_id`. Ground truth reaches the ledger through the report's reference number, kept inside the picture.

## Operator actions and rules of engagement

Wave 5. A trainee works with tracks, so an operator action names a track (`payload.track`), never a drone. `World` handles it in `_operator_action` (`sim/world.py`):

1. The track must be live and the payload may carry only the keys of that action (`classify` takes `class_id`, one of `OPERATOR_CLASSES`; `assess` takes `identity`; `engage` takes `effector_class`, an ID in the rule pack). Anything else is logged as `action.rejected`.
2. With a rule engine attached (`World(..., roe=load_rule_engine(spec))`, which needs a picture), `sim/roe.py` evaluates the action for the track's context: the operator's own earlier assessment (identity, class), the role of the smallest scenario zone that contains the track, and the track's class support as confidence. The result is logged first as `roe.verdict` (action, track, context, `permitted`, `code`, rule ID and title, pack ID and version, detail).
3. Only a permitted action takes effect: it updates `World.operator[track]`, sets the real drone's `assigned_*` fields when the ledger can name it, and is logged as `action.<name>` with `target`, the real drone behind the track or `None` for a false alarm. A blocked response is logged as the verdict alone.

The verdict is a pure function of the rule pack and that context (`RuleEngine.evaluate`). Rules only permit. If a rule permits the action, every condition holds, the session has its authority and (for `engage`) it lists the effector class, the verdict cites it. Otherwise it cites the closest rule (fewest gaps, an effector mismatch counting double because the effector is the operator's own choice) and says what is missing: `conditions` (with `detail.unmet`: field, required, actual), `effector`, or `authority` (a commander rule is not available to a single operator). `no-rule` means the pack has no rule that permits the action at all. `hold` is always permitted (`default-hold` when no rule matches). Operator state joins the hashed state only when a rule engine is attached, so earlier golden files are untouched; entries for vanished tracks are dropped on the next action. `session-record.v1` has a `roe` flag, and `replay` rebuilds the engine from the scenario's rule pack when it is set.

`sim/audience.py` is the allow-list of events a trainee may receive (tracker lifecycle, the operator's own accepted actions and rejections, `roe.verdict`, session start and end), with `target` removed. See [LIVE_SESSION.md](LIVE_SESSION.md).

## Golden files

`services/api/tests/golden/*.txt` pin the event list, 10-second state samples and final state hash for a fixed set of cases (`tests/sim_cases.py`: the Kestrel scenario with three seeds and action logs, up to 12,000 ticks). A behaviour change prints a unified diff of the changed lines. To accept an intended change:

```sh
cd services/api
UPDATE_GOLDEN=1 uv run pytest tests/test_sim_golden.py
git diff tests/golden/   # read it, then commit with the reason
```

## Tests

| What | Where |
|---|---|
| Examples validate; malformed inputs are refused by the models and the JSON Schemas; schemas and TS types are current | `tests/test_contracts.py`, `apps/web/tests/contracts.test.ts` |
| Same inputs give the same hash after 10,000 ticks in two processes with different hash salts | `tests/test_sim_world.py` |
| Replay reproduces every event and the final state; divergence is reported at the first different event | `tests/test_sim_world.py` |
| Tampering with any event breaks verification at that event | `tests/test_eventlog.py`, `tests/test_sim_world.py` |
| Kinematics stay inside the class limits (hypothesis) | `tests/test_sim_kinematics.py` |
| Restore at N and run to M equals a straight run | `tests/test_sim_world.py` |
| Changing a physics constant fails a golden file with a readable diff | `tests/test_sim_golden.py` |
| Sensor framework: geometry, fixed draw budget, determinism in two processes, coverage, degradations, cueing, restore, profile provenance, row-normalised confusion tables | `tests/test_sensor_framework.py`, `tests/test_sensor_profile.py` |
| Tracker, association, lifecycle, triangulation, Kalman filter | `tests/test_tracker_core.py`, `test_tracker_edges.py` |
| Association errors, truth ledger, track commands, cue-to-track | `tests/test_tracking_ambiguity.py`, `test_tracking_ledger.py`, `test_tracking_commands.py`, `test_tracking_cueing.py` |
| Simulated AI assist rates and reproducibility | `tests/test_tracking_assist.py` |
| Picture in the world: determinism, replay, snapshot, actions, who sees what | `tests/test_tracking_wiring.py`, `test_contract_track_actions.py` |
| ROE verdicts, closest-rule explanations, authority and effector gaps | `tests/test_roe.py` |
| Operator actions on tracks: verdict then effect, `target` logged, rejections, hashing, snapshot and replay | `tests/test_world_operator.py` |
| What a trainee may see of the log and of each frame | `tests/test_audience.py` |
| The Harrier Field scenario and an oracle defender run | `tests/test_harrier_scenario.py` |
| Reference-data labels on trainee-visible figures (Q-20) | `tests/test_sensor_provenance.py` |
| Sensor models: P(d) never rises with range, weather and time of day move it as documented, RF-silent targets are never detected by RF, micro-Doppler separates rotor from bird, a cue narrows the EO/IR field and improves precision, shipped profiles load against the register and list their unverified values | `tests/test_sensor_radar.py`, `test_sensor_eoir.py`, `test_sensor_rf.py`, `test_sensor_acoustic.py` |
