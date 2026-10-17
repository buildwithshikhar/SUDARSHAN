# 08 · Hero demo: the 10-minute story

**Story in one line:** one operator, one ordinary laptop, one night shift that gets worse every minute. Then the review shows exactly what they saw, what was really there, and what to train next.

Setting: a fictional unit position, "Post KESARI", on generic rural terrain with a small fictional town to the east (urban pack). All names, ROE and effector values are fictional and are labelled on screen. Everything runs from `make demo` with fixed seeds, so every rehearsal is identical.

Cast: the **presenter** as instructor, plus one **volunteer** (or the presenter) as trainee on a second laptop. Two additional class seats are scripted bots, labelled "simulated trainee (demo)" on screen; this is honest and visible.

| Time | Beat | What the audience sees | Features exercised | PS ref (06) |
|---|---|---|---|---|
| 0:00–0:45 | **The problem** | One slide with the PS line "costly, weather-dependent, do not scale". Then the presenter unplugs the Wi-Fi and says: "Everything you'll see runs on this laptop, offline." | Offline mode, floor laptop | R2, R13, R14 |
| 0:45–2:00 | **Instructor sets the drill** | Cohort "Demo Section", curriculum stage "Perimeter watch". Generator studio: a difficulty vector, a seed, and the validation badges "Solvable (oracle) ✓" and "Novel for this trainee: distance 0.41 ✓". The data-honesty label is visible. | Instructor console, generator, solvability, diversity check, rule pack | R16, R19 |
| 2:00–3:30 | **Run 1, day, rural: one drone among clutter** | Radar plots: a flock of birds, a permitted civil drone with a filed flight, and one unknown quadcopter. The trainee cross-cues EO onto the unknown. The AI assist says "bird 62%", which is wrong. The trainee checks the micro-Doppler blade flash and RF control-link burst and classifies it as quadcopter, hostile. The response per ROE is report plus RF jam. | Radar, EO, RF, AI assist with errors, classify, respond | R0, R5, R6, R7, R11 |
| 3:30–4:15 | **"Can't they just memorise it?"** | Re-run "the same drill": a new seed gives a different bearing, clutter and timing. Flash the generator diversity grid (coverage heat map). | Randomisation, diversity metric | R8, R19 |
| 4:15–5:00 | **Live monitor** | Class grid of three seats, with a ground-truth overlay on the trainee's seat and a missed track flashing on a bot seat. The instructor annotates "missed low approach from NE". | Live monitor, annotation | R4, R13 |
| 5:00–6:00 | **The hold-fire decision** | A drone loiters over the town. The trainee selects hard-kill and the decision panel shows the ROE rule "R-7: no kinetic engagement over populated area (fictional)", so the action is blocked. The trainee hands off and tracks instead. | ROE validator, explainable rules | R7, R17 |
| 6:00–7:00 | **It gets worse** | The instructor injects: time jumps to 02:00, fog rolls in, the radar north sector goes down, and an **RF-silent** autonomous drone appears. RF shows nothing. The trainee switches EO to thermal (hot motor spots) and the acoustic spectrogram shows harmonics. Detected late but correct. | Inject, night, weather, degraded sensors, thermal and acoustic | R3, R9, R10 |
| 7:00–8:00 | **Swarm** | 16 drones plus 4 decoys from two axes over the town. The track table fills. Team mode: sector handoff to the second operator. The fps counter stays visible in the corner (honest about performance). | Swarm models, team handoff, performance | R1, R12 |
| 8:00–9:30 | **After-action review** | Split replay of "what you saw" against "ground truth" at the RF-silent drone moment. The decision-tree path for that threat: Detect 31 s late against a 10 s standard (explained), Classify correct, Respond compliant. Then the confusion matrix (the bird/quad confusion), reaction-time curve, miss-zone heat map (NE low sector), the unit view over repeated sessions, a "Record chain verified ✓" badge and the PDF export. The next recommended drill appears automatically: "Night, low-altitude NE, RF-silent". | Scoring, AAR, learner model, recommender, signed records | R17, R18, R19, R0 |
| 9:30–10:00 | **Close** | Three honest lines: built from open research datasets and published specifications, in fictional scenarios; results shown are from our own pilot of N volunteers (or "reference data" if the pilot isn't done); zero licence cost, runs at unit level on hardware you already have. Tagline. | — | R2, R13 |

## Must-work list (demo acceptance)

1. `make demo` from a clean clone gives the identical seeded state, every time.
2. Offline: the whole script runs with networking disabled.
3. Two-laptop LAN join in under 30 s.
4. The AI assist is wrong in Run 1 by design, from a fixed seed.
5. The ROE block at 5:00 shows the rule text and its version.
6. Inject → night + fog + radar sector outage + RF-silent drone, all from one instructor macro.
7. 16 + 4 swarm at ≥ 30 fps on the floor laptop.
8. AAR replay jumps to a bookmarked moment in one click.
9. PDF export in under 5 s.
10. Fallback: a recorded 1080p video of the same seeds, plus pre-generated AAR data, if hardware fails on the day.

## Honesty checks on the script

- Never say "validated", "doctrine-accurate" or "real data". Say "modelled", "fictional", "open data".
- Pilot numbers on screen only if measured. Otherwise show the label "reference data (seeded)".
- Effector names are generic classes. No real system is named.
