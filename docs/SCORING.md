# Scoring

How a finished session is scored and how the debrief explains it. The evaluator is `services/api/app/scoring/`: a pure function of the scenario, the rule pack and the stored event log. It uses no random numbers and no clock, so scoring the same log again gives the same bytes. The result is the `score-result.v1` contract (`app/contracts/score.py`, JSON Schema in `packs/schemas/`, TypeScript in `apps/web/src/contracts/`).

**Honesty note.** Every timing standard, weight, credit and tolerance below is fictional and editable: no public doctrinal standard exists for them (Q-12). They live in the rule pack (`packs/rule-packs/*.yaml`, the `thresholds`, `weights` and `scoring` sections) and each score records the rule-pack and scenario versions it used. The score measures what the operator did against this scenario's rules. It is not validated as a measure of operator skill, and no result here is claimed as training effectiveness.

## What the log must hold

The evaluator never looks at the simulation. It reads these events (full log, ground truth included; a trainee only ever sees the debrief after the session ends):

| Event | Used for |
|---|---|
| `ledger.first_report` `{drone, sensor, modality}` | The first detectable moment: the first time any sensor reported the drone. Every timing standard is measured from it |
| `action.designate`, `sensor_cue`, `classify`, `assess`, `hold`, `report`, `engage` with `target` | What the operator did, and the real drone behind the track at that moment (`null` for a track that followed nothing real) |
| `roe.verdict` with `target`, `permitted`, `context`, `rule_id` | Blocked attempts, the rule behind a permitted response, and whether the operator had a positive ID |
| `action.report` with `truth` `{class_id, disposition, x, y, heading_deg, count}` | What a contact report is graded against, taken when it was filed |
| `ledger.swap`, `split`, `merge`, `restored` with `error_id` | Track errors, and whether the operator fixed them |

## The tree, per contact

A contact is a scenario threat that a sensor reported at least once (`presented`). Marks are 0 to 1.

| Node | What earns marks |
|---|---|
| **Detect** | Time from the first report to the operator's first action on the contact (any of designate, cue, classify, assess, hold, report, engage), in the capped bands below against `thresholds.detect_within_s`. No action: 0 |
| **Classify** | The operator's final class equals the real class: `classify_correct_share` (0.7) plus the remainder by timing (the first call that committed to that class, against `classify_within_s`). A wrong class, `unknown` or none: 0. A clutter contact classified as a drone class is also a *false alarm* finding |
| **Assess** | The final identity looked up in `assess_credit[disposition][identity]`. Hostile: hostile 1.0, suspect 0.5, unknown 0.1. Civil: neutral 1.0, friend 0.5, unknown 0.25. Clutter: neutral 1.0, unknown 0.25, friend 0.25. Everything else 0 |
| **Respond** | Hostile contact: the best response, `respond_credit` (engage 1.0, report 0.6, hold 0.25, none 0), times 0.7 if the permitted effector is not the first the rule lists (the lowest escalation), times `1 - respond_timing_share x (1 - timing band)` against `respond_within_s`. Any other contact: 1.0 for holding fire. Each response the rules blocked on the contact subtracts `blocked_attempt_penalty` (0.15) |

**Capped timing bands.** Elapsed time divided by the standard gives a factor. Up to the first band's `max_factor` (1.0) earns that band's mark (1.0), and nothing earns more, so being faster than the standard never pays and rushing cannot buy marks. Slower bands earn less (2.0 gives 0.75, 3.0 gives 0.5, 5.0 gives 0.25); beyond the last band, 0. The pack is refused if a slower band earns more than a faster one.

**Decision score.** The weighted mean of the four nodes (`weights.detect`, `classify`, `assess`, `respond`, renormalised over their sum).

**Contact score.** A hostile contact also has a contact report (below), graded separately: score = decision x (1 − `weights.report`) + report score x `weights.report`. Any other contact has no report: score = decision.

**ROE hard-fail gate.** An engagement that went ahead on a contact that was not hostile (neutral, friend, civil or clutter), or without a positive ID (the track classified, not `unknown`, and assessed hostile or suspect, as logged in the verdict's context), fails the contact: score 0, whatever the nodes earned. The nodes are still listed so the debrief can show the path. A response the rules blocked is not a breach.

**Track errors.** Each unfixed swap, split or merge that touched the contact (a `ledger.*` error with no `ledger.restored` for its `error_id`) subtracts `track_error_penalty` (0.15), capped at `track_error_cap` (0.30). One the operator fixed costs nothing.

**Contacts left out.** A contact no sensor reported (`presented: false`) cannot be scored. A clutter or civil contact the operator never acted on (`worked: false`) is left out too: leaving it alone was the right call. A hostile contact that was presented and never worked scores 0.

## Session score

The mean of the scored contacts' scores, less `false_engagement_penalty` (0.15, capped at 0.45) for each engagement on a track that followed nothing real. Also reported: `decision_score` (mean decision, 0 for a hard-failed contact) and `report_score` (mean over hostile contacts).

## Contact report

The operator files `what` (class), `where` (bearing and range from the site, the first defended asset), `how many`, `heading` and a `confidence` from 0 to 1 with the `report` action. Each field is optional; a missing field earns 0. Tolerances are in `scoring.report`.

| Field | Marks |
|---|---|
| what | 1 if the class is right, else 0 |
| where | 1 within `position_tolerance_m` (150 m) of the real position when filed; falls linearly to 0 at 3 x that |
| count | 1 exact, `count_off_by_one_score` (0.5) off by one, 0 otherwise. The truth is the number of same-class contacts within `count_radius_m` (250 m) of the contact |
| heading | 1 within `heading_tolerance_deg` (20°) of the real ground course; linear to 0 at 3 x that. A heading 40° out earns 0.5 |
| calibration | `1 − (confidence − q)²`, where q is the weighted mean of the four graded fields. Stating 80% about a report that was 80% right is the best a report can do |

**Worked example.** Class right (1.0), position within tolerance (1.0), count off by one (0.5), heading 40° out (0.5): q = (0.30 x 1 + 0.25 x 1 + 0.15 x 0.5 + 0.15 x 0.5) / 0.85 = 0.8235. With a stated confidence of 0.8, calibration = 1 − (0.8 − 0.8235)² = 0.9994. Report quality = 0.30 + 0.25 + 0.075 + 0.075 + 0.15 x 0.9994 = 0.8499. Timeliness (first report against `report_within_s`) then adds `timeliness_weight` (0.2) of the score: report score = 0.8 x quality + 0.2 x timeliness. The last report filed for a contact is the one graded.

## Signal-detection metrics

Per session: a *signal trial* is a presented hostile contact; a *noise trial* is a presented civil or clutter contact, or a track that followed nothing real and was assessed. The response is positive when the operator's final assessment is hostile or suspect. Hit rate = hits / signal trials; false-alarm rate = false alarms / noise trials. d′ = z(H) − z(FA) and the criterion c = −(z(H) + z(FA)) / 2. When either rate is exactly 0 or 1 both are replaced by the log-linear estimates (hits + 0.5) / (signals + 1) and (false alarms + 0.5) / (noise + 1), and `corrected` is true. The form of c is the standard one and has not been checked against a primary source.

## First three lessons

Each mark lost has a cost in the units of the contact's score (a node's shortfall times its share of the weights, a penalty, a hard fail's whole score). The three costliest become lessons, ties broken by contact order then node order. A lesson is a key and the parameters of the node or finding it comes from, plus the contact's label.

## Explanations

The evaluator returns keys and parameters only. The console renders them from the `scoring.*` entries of the EN and HI message catalogues (`apps/web/src/i18n/`); `app/scoring/keys.py` lists every key and `tests/test_scoring_keys.py` fails if one is missing in either language. Parameters are rendered like this:

- `class`, `given`, `actual` in a classify or report-what message: a class ID, shown as `live.class.<id>`.
- `given`, `actual` in an assess message: an identity (`live.identity.<id>`) and a disposition (`scoring.disposition.<id>`).
- `seconds`, `standard`: seconds, one decimal. `timing`, `timeliness`, `stated`, `achieved`, `credit`: fractions shown as percentages. `error_m`, `tolerance_m`: metres. `error_deg`, `tolerance_deg`: degrees.
- `worst_field`: a report field, shown as `scoring.reportField.<field>`. `first_action`: an operator action. `effector`: an effector class ID from the rule pack.
- `threat` in a lesson: the contact's `{en, hi}` label.

## Keys

| Node | Reasons |
|---|---|
| Detect | `detect.band`, `detect.missed` |
| Classify | `classify.correct`, `classify.wrong`, `classify.unknown`, `classify.missing` |
| Assess | `assess.exact`, `assess.partial`, `assess.wrong`, `assess.missing` |
| Respond | `respond.engage`, `respond.engage-higher`, `respond.report-only`, `respond.hold-only`, `respond.none`, `respond.hold-fire` |
| Report | `report.missing`, `report.filed`, `report.no-truth`, `report.<field>.<ok|partial|wrong|missing>` |
| Findings | `finding.hard-fail.engaged-non-hostile`, `finding.hard-fail.no-positive-id`, `finding.track-error.<swap|split|merge>`, `finding.blocked-attempt`, `finding.false-alarm`, `finding.false-engagement`, `finding.not-presented`, `finding.not-worked` |
| Lessons | `lesson.<node reason>` for the reasons that lose marks, `lesson.hard-fail.*`, `lesson.track-error`, `lesson.blocked-attempt`, `lesson.false-engagement` |

## Where it runs

`GET /api/v1/sessions/{id}/score` (owner only, after the session has ended) returns the stored score. The score is computed and stored when the session ends (`training_sessions.score`); an ended session without one is scored on first request. Abandoned sessions are not scored.

## Tests

| What | Where |
|---|---|
| Golden event-log fixtures: every node outcome and every hard-fail case produce exactly the expected scores and explanations | `tests/test_scoring_golden.py`, `tests/golden/scoring/` |
| Rushing into a breach never beats a compliant slower response (hypothesis) | `tests/test_scoring_properties.py` |
| d′ against reference values, with the log-linear correction | `tests/test_scoring_sdt.py` |
| Report grading and re-scoring determinism | `tests/test_scoring_report.py` |
| An unfixed seeded track swap lowers the affected contact's score; a fixed one does not | `tests/test_scoring_track_errors.py` |
| Every reason and lesson key has an English and a Hindi message | `tests/test_scoring_keys.py` |
| The score endpoint, storage and migration | `tests/test_scoring_endpoint.py` |
