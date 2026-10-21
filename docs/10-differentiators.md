# 10 · Differentiators: features beyond the problem statement

The PS items (see [06-requirements-traceability.md](06-requirements-traceability.md)) are the floor. This catalogue lists what takes SUDARSHAN well past them. It is prioritised, and each entry has a wave, dependencies and a one-line acceptance test. Wave numbers refer to [waves/](waves/README.md). Every headline feature and supporting feature below is scheduled into the wave files (accepted in ADR-012); overloaded waves were split into lettered parts to make room.

## How entries are ranked

Score = evaluator impact (does it show something a typical simulator does not) × credibility (can it be built and demonstrated honestly on the floor laptop) ÷ effort. Effort: **S** under a day of build work, **M** one wave-sized step, **L** a wave or more on its own.

Constraints that apply to every entry: threat behaviour stays kinematic (no guidance or terminal-attack logic); no real systems or figures; nothing claims validated training effectiveness; anything described as "AI" is a small, inspectable, deterministic or seeded model.

## Headline features (12)

| # | Feature | Effort | Wave | Demo |
|---|---|---|---|---|
| H1 | Adaptive adversary | L | 11a | Yes |
| H2 | Sensor placement trainer with viewshed coverage | L | 9c | Yes |
| H3 | Site builder | M | 9b | |
| H4 | Structured contact-report scoring | M | 6 | Yes |
| H5 | Track management with association errors, cueing and handover | L | 4b (errors, cueing), 13a (handover) | |
| H6 | Counterfactual after-action review | L | 12b | Yes |
| H7 | Drone recognition academy | M | 11b | |
| H8 | Competency matrix with signed, hash-chained records and certificates | M | 13b | Yes |
| H9 | Unit readiness dashboard | M | 12a | |
| H10 | Scenario authoring language, validator and signed packs | M | 9a (language), 13c (signing) | |
| H11 | Instructor director mode | M | 10b | |
| H12 | Stress and fatigue modelling | M | 11a | |

### The five for the 10-minute demo

Chosen because each is visible in under 90 seconds, runs from fixed seeds and replaces or sharpens an existing beat in [08-demo.md](08-demo.md) rather than adding length.

1. **H2 Sensor placement trainer** replaces the "instructor sets the drill" beat (0:45–2:00): the instructor places a radar and an EO post, the viewshed shows a blind spot, and the scenario is run against that layout.
2. **H4 Contact-report scoring** extends Run 1: the trainee's report (what, where, how many, heading, confidence) is graded line by line.
3. **H1 Adaptive adversary** replaces the "new seed" beat (3:30–4:15): the next run approaches through the sector the trainee missed, and the instructor panel says why.
4. **H6 Counterfactual AAR** extends the review beat: from the late-detection moment, branch "classified 12 s earlier" and show the changed outcome and score.
5. **H8 Signed record and competency matrix** closes the review: "Record chain verified" and the trainee's updated qualification level.

H11 director mode already appears in the script as the inject macro; H5 and H7 are strong second-day features if time allows.

## Catalogue

### H1 · Adaptive adversary
- **What:** The scenario generator reads the trainee's recent per-skill weaknesses (from the learner model) and biases threat behaviour: approach sector, altitude band, timing, use of clutter and of known sensor degradations. Difficulty sliders still exist; this adds weakness-targeted variation. Behaviour stays kinematic and bounded by the rule pack.
- **Why it wins:** Moves from "random harder" to "trains what you are bad at", and the instructor panel can show the reason in plain words.
- **Effort:** L · **Wave:** 11a · **Depends on:** learner model (11a), generator and oracle check (9a)
- **Acceptance:** Given a seeded trainee history with a weak NE low-altitude skill, the next generated scenario has its main approach in that sector with probability ≥ 0.7 over 100 seeds, and still passes the oracle solvability check.

### H2 · Sensor placement trainer
- **What:** The trainee or instructor places radar, EO/IR, RF and acoustic sensors on terrain. The platform computes a viewshed and per-sensor coverage, marks blind spots, then runs a scenario against that layout and scores the layout by detections gained or missed.
- **Why it wins:** Trains siting, not just watching; it is visual, interactive and unusual in this class of trainer.
- **Effort:** L · **Wave:** 9c · **Depends on:** site builder (9b), terrain and line-of-sight (7), sensor profiles (4a)
- **Acceptance:** On a fixed terrain pack, moving a radar behind a ridge changes the computed blind-spot area, and a scenario run on the two layouts gives different, reproducible detection times.

### H3 · Site builder
- **What:** The instructor draws a perimeter, assets and approach routes on the map; the generator then builds scenarios that respect that site. Sites are fictional and stored as a pack.
- **Why it wins:** Makes training specific to a unit's own (fictional or generalised) layout without custom development.
- **Effort:** M · **Wave:** 9b · **Depends on:** scenario engine (9a), terrain pack and map (7)
- **Acceptance:** A drawn site with two approach routes produces 20 generated scenarios whose threat paths all follow one of the two routes and all pass the solvability check.

### H4 · Structured contact-report scoring
- **What:** The trainee files a contact report with fields for what, where, how many, heading and confidence. Each field is graded against ground truth with tolerances, and the report gets a quality score separate from the decision score. Confidence is checked for calibration.
- **Why it wins:** Reporting is a real skill and is rarely scored; calibration shows uncertainty explicitly.
- **Effort:** M · **Wave:** 6 · **Depends on:** scoring engine, ground-truth log (and track commands from 4b)
- **Acceptance:** A report with correct class, position within tolerance, count off by one and heading off by 40° gets the documented per-field marks, and the result is identical on re-scoring.

### H5 · Track management with association errors, cueing and handover
- **What:** The tracker can swap identities, split one target into two tracks or merge two, as real trackers do under crossing and clutter. The trainee fixes these, cues a second sensor onto a track, and hands a track to another operator with its history.
- **Why it wins:** Tracks are where operators actually fail; most simulators give perfect tracks.
- **Effort:** L · **Wave:** 4b (errors, cueing; UI in 5; scoring in 6), 13a (handover in team mode) · **Depends on:** sensor models (4a), team mode (13a)
- **Acceptance:** With a seeded crossing geometry, the tracker produces a documented swap at a known tick, scoring marks the unfixed swap, and the fix action restores identity in the log.

### H6 · Counterfactual after-action review
- **What:** From any moment in a replay, branch the run with one changed action or timing ("classified 12 s earlier", "held fire") and replay forward from the verified log, showing the changed outcome and score next to the original.
- **Why it wins:** Turns review from description into experiment; only possible because the sim is deterministic.
- **Effort:** L · **Wave:** 12b · **Depends on:** snapshots (3), scoring (6), replay (12a), branch plumbing (10b)
- **Acceptance:** Branching at a bookmark with an unchanged action reproduces the original score exactly; branching with an earlier classification changes only downstream events and is marked as a branch in the record.

### H7 · Drone recognition academy
- **What:** A signature explorer with spectrograms, micro-Doppler, RF waterfalls and acoustic views, rendered from our own sensor models, with study mode and quiz mode (spaced repetition).
- **Why it wins:** Teaches the recognition skill directly and shows the sensor models are physical, not decorative.
- **Effort:** M · **Wave:** 11b · **Depends on:** sensor models (4a), threat breadth (8), learner model (11a)
- **Acceptance:** Each catalogued class has at least three generated signature views, and a 10-question quiz is reproducible from its seed and records per-class accuracy.

### H8 · Competency matrix and signed training records
- **What:** A matrix of skills against qualification levels per trainee and per unit, driven by assessed sessions. Session records are hash-chained and signed; certificates export as PDF with a verification code, and a CLI verifies the chain.
- **Why it wins:** It is what a training authority needs: evidence that can be checked, not a score screen.
- **Effort:** M · **Wave:** 13b · **Depends on:** event log chain (5), progression levels (11b), AAR (12a)
- **Acceptance:** `verify-record` passes on an untouched record and fails, naming the first broken event, after one byte of the log is altered.

### H9 · Unit readiness dashboard
- **What:** Weakness heat map across a detachment, trends over sessions, and cohort comparison, with a data-table alternative for every chart.
- **Why it wins:** Gives the commander the unit view, not only individual scores.
- **Effort:** M · **Wave:** 12a · **Depends on:** scoring (6), skill tags (11a)
- **Acceptance:** On the seeded demo cohort the heat map matches a hand-computed skill-by-trainee table and loads in under 2 s.

### H10 · Scenario authoring language, validator and signed packs
- **What:** A YAML scenario format with a schema validator, a linter (unreachable timings, missing sensor coverage, ROE inconsistencies), seed sharing, and export/import of signed scenario packs for offline transfer.
- **Why it wins:** Scenarios become portable, reviewable artefacts and can be versioned in git.
- **Effort:** M · **Wave:** 9a (language, validator, linter), 13c (signing, pack manager) · **Depends on:** contracts (3), signing key (13b)
- **Acceptance:** A scenario with a threat timed before the minimum reaction window fails lint with the offending line number; a pack with a tampered file is rejected on import.

### H11 · Instructor director mode
- **What:** Live injects, pause, branch, annotate and score-while-watching, with every instructor action logged as an instructor event.
- **Why it wins:** Lets one instructor run a drill like an exercise controller, with a clean audit trail.
- **Effort:** M · **Wave:** 10b · **Depends on:** class management (10a), scoring (6), snapshots (3)
- **Acceptance:** A scripted inject macro produces identical state on two runs from the same seed, and the log marks each instructor event with its author and tick.

### H12 · Stress and fatigue modelling
- **What:** Alert fatigue from false alarms, vigilance decline on long night shifts and time-pressure modes. These change the scenario (nuisance alarm rate, workload) and the scoring context; they do not claim to measure the trainee's physiology.
- **Why it wins:** Reproduces why good operators miss things late in a shift.
- **Effort:** M · **Wave:** 11a · **Depends on:** generator (9a), scoring (6)
- **Acceptance:** A 40-minute night profile with a raised false-alarm rate lowers late-shift detection rate in a headless population of seeded policy agents, and the profile is recorded with the session.

## Supporting features (not headline)

| Feature | What | Effort | Wave | Depends on | Acceptance |
|---|---|---|---|---|---|
| Deterministic replays, seed reproduction, golden-file regression | Replay any session from seed and action log; golden files guard sim behaviour in CI | M | 3 | sim core | A changed physics constant fails the golden test with a readable diff |
| Replay export and PDF AAR reports | Video/GIF clip of a replay moment; PDF briefing report | M | 12a (PDF), 12b (clip) | AAR, replay | A bookmarked moment exports a clip under 15 s; the PDF builds in under 5 s |
| Offline-first LAN deployment, installer, low-bandwidth mode | One command installs; a classroom joins over LAN; reduced frame rate and detail on weak links | M | 1, 14a | Compose, WS client | Two laptops join in under 30 s with networking to the internet disabled |
| Accessibility: bilingual UI, high-contrast and colour-blind-safe themes, keyboard-first | EN/HI from wave 1; extra themes tested | S per screen | 2 onward, 14a | design system | axe-clean in CI and every screen operable by keyboard alone |
| Sensor adapter interface | A documented interface that lets a recorded or external feed in open formats (CSV, JSON, GeoJSON) drive the trainer instead of the simulator | M | 14a | contracts (3) | A recorded track file in the open format plays through the same consoles with no sim code change |
| Optional offline narration of the AAR | Switchable, local-only summary text generated from the scored log; off by default, never alters scores | M | 12b | AAR | With narration off the AAR is byte-identical; with it on, every sentence cites a log event ID |
| Professional progression | Competency levels and qualification status, no points, badges or confetti | S | 11b (levels), 13b (matrix) | H8 | Level changes only from assessed sessions meeting stated thresholds |

## Dropped, merged or deferred

- **Merged:** "Replay export" and "PDF AAR" into one supporting entry; "Unit readiness dashboard" keeps trends and cohort comparison.
- **Merged:** Bilingual UI, themes and keyboard operation into one accessibility entry; they are already requirements, not differentiators.
- **Narrowed:** Sensor adapter limited to open formats and a recorded-feed demonstration. Live integration with any real system is not planned.
- **Deferred:** WebXR remains optional, now wave 14b ([DECISIONS.md](DECISIONS.md)).
- **Dropped:** Cartoon-style gamification (points, leaderboards between trainees); it conflicts with the quality bar. Replaced by professional progression.

## Placement summary by wave

| Wave | Differentiators |
|---|---|
| 3 | Snapshots for branching, golden-file regression |
| 4b | H5 (association errors, cueing, track commands) |
| 5 | Cue and track-command controls in the UI |
| 6 | H4, scoring of unfixed track errors |
| 9a | H10 (language, validator, linter, seed sharing) |
| 9b | H3 |
| 9c | H2 |
| 10b | H11 |
| 11a | H1, H12 |
| 11b | H7, professional progression |
| 12a | H9, PDF AAR |
| 12b | H6, replay clip export, optional narration |
| 13a | H5 (handover) |
| 13b | H8 |
| 13c | H10 (signed packs) |
| 14a | Sensor adapter, low-bandwidth mode, accessibility themes |
