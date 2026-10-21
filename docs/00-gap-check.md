# 01 · Gap check on requirements

> **Status (2026-10-17):** Q1–Q6 are answered and the defaults in section A were accepted; see [DECISIONS.md](DECISIONS.md). Section D is kept as written at the time.

Project: SIH26247 · PS 26247 "AI-Enabled Drone & Counter-Drone Threat Simulation Trainer" (MoD / Defence Services Staff College)
Platform: SUDARSHAN
Status: decisions marked **DEFAULT** are what the rest of the pack assumes until you override them.

## A. Gaps that change research and design (questions for you)

| # | Gap | Why it matters | DEFAULT used until you answer |
|---|-----|----------------|-------------------------------|
| Q1 | **Who is the trainee?** Unit-level operator (sensor operator, detachment commander) or DSSC staff officer (planning, sensor siting, command decisions)? | DSSC trains mid-career officers for staff roles, but the PS says "usable at unit level". The answer changes the screen set, the scoring tree and the hero demo. | Operator core plus a **detachment-commander role** (team mode). A staff-planning layer (sensor siting on a map, coverage gaps) is a stretch module, not core. |
| Q2 | **Hardware floor and VR.** What is the weakest machine it must run on, and do you have a VR headset to test WebXR? | Sets the 3D budget (draw calls, shadows, post-processing) and whether we can honestly claim "VR-capable". | Floor: 8 GB RAM laptop, integrated graphics (Intel Iris Xe class), no internet. No headset: WebXR built and tested in the WebXR emulator, labelled "VR mode, emulator-tested". |
| Q3 | **Next SIH milestone.** Is the next thing you must submit the idea-stage PPT, or a working prototype? | Decides whether slides and the architecture diagram come before build wave 1. | Idea PPT first: deliverables 05 and 08 are written PPT-ready; build waves follow. |
| Q4 | **Team.** Who writes code, and can waves run in parallel across people? | Decides whether waves can run in parallel across people or stay strictly serial. | Team build; max 2 parallel tracks per wave. |
| Q5 | **Pilot size.** How many civilian volunteers can you get, for how many sessions each? | The evidence plan needs enough people for a learning curve and a new-seed rote-learning test. | 12 volunteers × 4 sessions (about 30 min each). Fewer than 8 and we report case studies, not curves. |
| Q6 | **Hindi UI.** Bilingual English/Hindi? | i18n is cheap if wired in wave 1 and painful to retrofit. | Yes: i18n framework from wave 1, English complete, Hindi for all trainee-facing strings. |

## B. Undecided items I will decide by default (override any)

1. **Where the "AI" is.** The PS title says AI-enabled; evaluators will look for it. DEFAULT, four places, each honest and measurable:
   - adaptive learning model (per-skill proficiency, next-scenario recommendation) — module F;
   - AI threat behaviour (swarm and evasive-drone behaviour models with randomised intent) — module C;
   - constrained procedural generator with solvability and diversity checks — module D;
   - a simulated "AI detection assist" in the sensor console that has its own modelled false-alarm and miss rates, so trainees learn to judge machine confidence rather than trust it. No real detector accuracy is claimed.
2. **How the open datasets are used.** DEFAULT: they calibrate signature models (RF bands and hop patterns, acoustic spectra, micro-Doppler shape, apparent size versus range) and feed a licence-permitting recognition library. We do not train a production detector, and we never claim real-world detection accuracy.
3. **Effectors and responses.** DEFAULT: abstract, fictional effector classes (report/alert, track and monitor, RF jam, GNSS deny, kinetic soft-kill / hard-kill, hand off, hold fire), with fictional ranges and probabilities in an editable ROE pack. No real system names or performance figures. (Locked rule 2.)
4. **Offline and air-gap.** DEFAULT: everything runs from the Docker bundle with no CDN, no online map tiles, fonts and terrain bundled. Classrooms often have no internet.
5. **Unit-level classroom shape.** DEFAULT: one instructor laptop as the LAN server, up to 12 trainee browsers.
6. **Scoring authority.** DEFAULT: all weights, thresholds and ROE are a versioned, instructor-editable rule pack; every score shows which rule-pack version produced it.
7. **Data protection for the pilot.** DEFAULT: written consent form, pseudonymous IDs, no personal data beyond a call-sign and cohort, export and delete on request.

## C. Missing from the requirements (now added to the plan)

- A **sensor-fusion / track picture** view (common operating picture). Real C-UAS operators work from a fused track list, not four separate sensors.
- **Civil clutter and false alarms** as a scored element (birds, kites, balloons, permitted civil drones). Classification accuracy means nothing without negatives.
- **Rule-pack and scenario-pack versioning** so AAR results stay comparable across sessions.
- **Performance budget and telemetry** (FPS, frame time on the floor laptop) as a tested acceptance criterion, not a hope.
- **Instructor workflow for a class**: cohort creation, assigning a curriculum, running a session for many trainees at once.
- **Export**: PDF AAR reports and CSV for the unit's own records.

## D. Already done

- Project instructions already say "Platform name: SUDARSHAN (working name, pending the naming-conflict check below)", and the Standards changelog has the 2026-10-17 entry. No further edit made.
