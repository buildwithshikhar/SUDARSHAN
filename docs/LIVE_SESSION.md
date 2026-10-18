# Live session

How a trainee plays a scenario in the browser (wave 5). The simulation runs on the server; the browser receives what the operator's own sensors and tracker produced and sends the operator's commands back. The messages are the `live-client.v1` and `live-server.v1` contracts (`services/api/app/contracts/live.py`, exported to `packs/schemas/`, generated as TypeScript in `apps/web/src/contracts/`).

## Who sees what

| Audience | Gets |
|---|---|
| Trainee socket | `welcome` (briefing, rules, vocabularies), `frame` (reports, tracks, assist views, sensor status, trainee events), `ack`, `status`, `pong`, `ended`, `error` |
| Stored log, trainee | The same events, through `sim.audience.trainee_event` (see below) |
| Stored log, instructor and admin | The full chain, including `threat.*`, `ledger.*` and `assist.assess` |

`sim/audience.py` is the single allow-list. A trainee never receives `truth_id`, a drone ID, a threat's class or position, `disposition`, the ledger or the true outcome of an assist assessment. The `target` field of logged operator actions (the real drone behind a track) is stripped. `tests/test_live_no_truth.py` runs a session over a real socket and fails if any frame contains a drone ID, a `truth_id`, or an event type outside the allow-list.

Everything derived from a sensor parameter that is still `verified: false` carries `data_status: "reference"` (Q-20). The console must show it as reference data.

## REST (`/api/v1`, session cookie, CSRF header on unsafe methods)

| Method and path | Role | Meaning |
|---|---|---|
| `GET /scenarios` | trainee, instructor | Playable scenarios: `id`, `version`, `title`, `summary`, `duration_s`, `default_seed`, `start_time_of_day_h`, `weather_condition` |
| `POST /sessions` `{scenario_id, seed?}` | trainee, instructor | Create a session in `lobby`. Any earlier unfinished session of this user is marked `abandoned`. Returns the session |
| `GET /sessions` | trainee, instructor | The caller's sessions, newest first |
| `GET /sessions/{id}` | owner | One session |
| `GET /sessions/{id}/log` | owner | The stored event log, verified on read: `{verified, first_bad_seq, event_count, head, final_state_hash, events}`. A trainee gets the trainee events; instructor and admin get all. `?deep=1` also replays the session from its inputs and reports `replay_matches` |
| `GET /sessions/{id}/score` | owner | The scored debrief (`score-result.v1`) of an ended session; 409 before it ends. It names the real class of each contact, so it is only given after the end ([SCORING.md](SCORING.md)) |
| `GET /sessions/stats` | admin | Live-session counts and tick jitter percentiles |

A session row: `id`, `scenario_id`, `scenario_version`, `seed`, `status` (`lobby`, `running`, `ended`, `abandoned`), `created_at`, `started_at`, `ended_at`, `ticks`.

Admins cannot play (they see no trainee data).

## WebSocket `/api/v1/sessions/{id}/ws`

- Authenticated by the session cookie on the upgrade request. The `Origin` header must match the request host or be in `CORS_ORIGINS`; anything else is refused (the handshake is a GET, so this is the CSRF defence).
- Binary frames, one MessagePack map each, keyed by `t`. Text frames are refused.
- Close codes: `4401` not signed in, `4403` not allowed (not the owner, or wrong role), `4404` no such session, `4408` superseded by a newer connection of the same user, `4409` the session has already ended (read the log instead), `4413` frame too large (limit 16 KiB), `1013` the server is full (`MAX_LIVE_SESSIONS`, default 32).

### Server to client

| `t` | When | Content |
|---|---|---|
| `welcome` | once, right after the upgrade | Briefing (site, zones, sensors, filed flights; never the threats), the rules in force with their version, vocabularies (`operator_classes`, `identities`, `actions`), the data notice |
| `frame` | every tick while `running` (20 Hz); one on join and one on each status change | `tick`, `time_s`, `time_of_day_h`, `reports`, `tracks`, `assist`, `sensors`, `events` (trainee events logged since the previous frame), `data_notice` |
| `status` | lobby to running, running to paused-by-disconnect and back | `status`, `tick` |
| `ack` | for each `act` | `seq`, `ok`; on `ok: false` an `error` with a code and message. `ok: true` means the action is queued for the next tick, not that it succeeded |
| `pong` | for each `ping` | `ts` echoed, `tick` |
| `ended` | once, when the session ends | `summary`: ticks, duration, event count, chain head, final state hash, `verified` |
| `error` | before a close the server initiates | `code`, `message` |

### Client to server

| `t` | Content |
|---|---|
| `start` | lobby to running |
| `act` | `seq` (client counter), `action`, `payload` |
| `end` | finish now |
| `ping` | `ts` (a client timestamp, echoed) |
| `leave` | leave without ending |

Operator actions and their payloads (anything else in a payload is refused with `invalid`; a client can never name a drone, only a track):

| `action` | `payload` | What it does |
|---|---|---|
| `designate` | `track` | Marks the track as being worked |
| `classify` | `track`, `class_id` (one of `operator_classes`) | Records the operator's classification |
| `assess` | `track`, `identity` (one of `identities`) | Records the operator's assessment: hostile, suspect, unknown, neutral, friend |
| `engage` | `track`, `effector_class` (an ID from the rules) | A response, checked against the rule pack |
| `hold` | `track` | Hold fire on the track; always allowed |
| `report` | `track`, and optionally `class_id`, `count` (1 to 99), `bearing_deg` (0 to under 360) and `range_m` (0 to 50,000) from the site, `heading_deg`, `confidence` (0 to 1) | File a contact report on the track, checked against the rule pack. Every field is optional, a field left out earns no marks, and each is graded in the debrief ([SCORING.md](SCORING.md)) |
| `track-relabel` | `track`, `label`, `exchange?` | Rename a track; `exchange` takes a name another track wears |
| `track-merge` | `tracks` (two IDs) | Fold two tracks into one |
| `track-split` | `track` | Copy a track into two |
| `track-drop` | `track` | Remove a track |
| `sensor-cue` | `sensor`, `track`, `narrow?` | Point a cueable sensor at the track (EO and IR) |

The server stamps each action with the next tick and the trainee's actor ID, so the action log is the server's, not the client's.

### Events a trainee sees

`track.init|confirm|coast|resume|drop|relabel|merge|split`, `sensor.cue`, `action.<name>` (with `target` and `truth` removed) (the operator's own accepted actions), `action.rejected` (the simulation refused: unknown track, bad value, sensor refused a cue), `roe.verdict`, `session.start`, `session.end`.

`roe.verdict` is logged before every operator action on a track:

```json
{"action": "engage", "track": "T014", "effector_class": "ec-b",
 "context": {"identity": "suspect", "classification": "rotary-small", "zone_role": "outer", "confidence": 0.82},
 "permitted": false, "code": "effector",
 "rule_id": "suspect-outer-zone", "rule_title": {"en": "...", "hi": "..."},
 "pack_id": "training-baseline", "pack_version": "1.0.0", "authority": "operator",
 "detail": {"effector_class": "ec-b", "allowed": ["ec-a"]}}
```

`code` is `permitted` (the rule that permits it), `default-hold` (hold with no rule), `no-rule` (no rule in the pack permits this action), `conditions` (the closest rule's unmet conditions are in `detail.unmet`: field, required, actual), `effector` (that rule does not list the chosen effector class), or `authority` (that rule needs a commander; a single-operator session has none). A blocked response changes nothing: no `action.engage` follows. The console renders the text from the codes in either language and shows the rule title and the pack version.

## Session lifecycle

1. `POST /sessions` creates the session (`lobby`); the world is built at the first `start`.
2. The client opens the WebSocket and receives `welcome` and one `frame`. The same user can reconnect at any time; the new connection supersedes the old one (`4408`).
3. `start` begins ticking. The server schedules ticks against a monotonic clock (tick *n* is due at *start + n × 0.05 s*). A late tick runs at once; if the loop is more than 0.5 s behind it drops the lag and counts it (`GET /sessions/stats`). Simulation time never depends on wall time.
4. If the client disconnects (or sends `leave`) while `running`, the session pauses: no ticks run. If it does not return within `SESSION_GRACE_S` (default 120) the session is stored as `abandoned`. Pausing by disconnect is not a sim action and cannot change a replay.
5. The session ends when the scenario duration is reached, the trainee sends `end`, or the grace expires. The server appends `session.end`, stores the session record (`session-record.v1`, with `picture` and `roe` set) in the database, reads it back, verifies the hash chain, and only then sends `ended` with `verified`.

One API worker process holds all live sessions. Compose runs one worker; running more is not supported in this wave (sessions live in memory while running).

## Browser

- The workspace loads `welcome`, then renders every `frame`. It interpolates between the last two frames to 60 fps (track positions along their velocity, sensor pointing, the radar sweep is drawn from the clock, not from frames). The server's tick is the only clock that matters; a frame older than the current one is dropped.
- The EO view is drawn from EO and IR `reports` (azimuth, elevation, `apparent_px`, `reported_class`) and the sensor's pointing and field of view: a report is a small mesh placed on its bearing at an angular size, never at a position the sensors did not measure. Between a sensor's updates the last report is held for 0.4 s.
- The radar PPI draws radar `reports` as plots with phosphor decay and confirmed `tracks` as symbols.
- Keys: `Tab` / `Shift+Tab` select the next/previous track, `C` classify, `A` assess, `R` respond, `H` hold fire, `U` cue the EO sensor onto the selected track, `L` relabel, `?` shortcuts. `1` to `9` choose in a step, `Enter` commits, `Esc` cancels.
