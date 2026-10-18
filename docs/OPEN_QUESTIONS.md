# Open questions

Everything the research marked unverified or undecided. Owner is **SD** (the user) or **Claude Code** (CC). Close an item by resolving it, recording the outcome in [DECISIONS.md](DECISIONS.md) if it is a decision, and moving the row to **Closed** with the date.

## Open

### Decisions

| ID | Question | Owner | How to close | Needed by |
|---|---|---|---|---|
| Q-01 | **Choose a licence** for the repository. Depends on dataset terms: ODbL share-alike (G02), CC BY attribution (D14) and any pack we ship. No LICENSE file exists yet, by instruction. | SD | After Q-05 and Q-06: pick MIT, Apache-2.0 or AGPL-3.0 for code and CC BY for docs, check each against bundled packs, then add LICENSE and a NOTICE file in a separate commit. | Before the repo goes public or release 1.0 |
| Q-03 | **SIH submission format** for the next milestone: required fields, file types and size limits, and whether a video or slides are needed beyond the live link. | SD | Read the SIH portal instructions and paste them into this file. Claude then prepares the matching material. | Before the next milestone |
| Q-04 | **Floor laptop** for the benchmark gate: which machine, with what specs, will run the wave 7 harness. | SD | Name the machine and record specs in docs/PERFORMANCE.md. | Wave 7 |

### Licences and naming

| ID | Question | Owner | How to close | Needed by |
|---|---|---|---|---|
| Q-05 | **Dataset licences unconfirmed**: Anti-UAV 300/410/600 (D01–D03), MAV-VID (D05), DroneRF data field (D08), CardRF (D09), DroneAudioDataset (D10), Svanström exact wording (D12), NYU 60 GHz (D15), MAFAT (D16), DREGON details (D11), IMD and GODL-India (W04), Bhuvan terms (G03), Drone-vs-Bird size and agreement (D06). | SD | Open each source page, copy the licence text into docs/DATA_REGISTER.md and update the row. Write to the authors if a page states none. | Before any raw sample ships; re-check each release |
| Q-06 | **ODbL share-alike scope** for a bundled OSM-derived terrain pack: does it force the pack, or only the derived database, under ODbL? | SD | Read the ODbL FAQ and OSM "Collective Database" guidance; record the answer in DECISIONS.md. | Wave 7 |
| Q-07 | **IP India trade-mark search** for SUDARSHAN, Classes 9, 41, 42, at https://tmrsearch.ipindia.gov.in/eregister/. | SD | Run the search, log the result in docs/01-naming.md. | Before any public use |
| Q-08 | **Name association risk**: SUDARSHAN overlaps Mission Sudarshan Chakra and the IAF S-400. The user kept the name (ADR-001). Confirm the mitigation: descriptor line, no-affiliation line, no chakra or emblem imagery. | SD | Review the title slide and About screen against the rule; revisit only if an evaluator raises it. | Before submission |

### Sensor and domain figures from secondary sources

| ID | Question | Owner | How to close | Needed by |
|---|---|---|---|---|
| Q-09 | **Sensor figures marked UNVERIFIED**: motor and battery thermal contrast, bird wing-beat band (5–20 Hz) vs drone fundamental (50–400 Hz), RF detection-range table, long-range acoustic ranges, Group 3–5 speed and altitude cells. | CC (wave 4) | Find a primary source for each; until then keep `verified: false` in the sensor profile and show uncertainty in docs/SENSOR_MODELS.md. | Wave 4 |
| Q-10 | **Secondary-source anchors**: Guvenc et al. 2018; Taha & Shoufan beyond the abstract; TC 25-20 primary text; ECD model names; SDT criterion form; Hunicke/Hamlet venue; FSRS data needs. | CC | Fetch the primary text or drop the citation. | Wave 15 (final report) |
| Q-11 | **Drone-class cells** for the threat catalogue where the research only has secondary sources. | CC (wave 8) | Use X01 (CC0) and public specifications; mark unsupported values `verified: false`. | Wave 8 |
| Q-12 | **Timing standards** for scoring (detect within N seconds) have no public doctrinal source. | SD | Accept them as fictional and editable, labelled so in the UI (current default). Revisit only if an instructor supplies a standard. | Wave 6 |
| Q-20 | **Sensor parameter sources with no register row.** Published small-UAS and bird RCS ranges (Ezuma et al. 2019, Seidaliyeva 2023; small multirotor about −20 to −8 dBsm, bird about −30 to −19 dBsm); micro-Doppler rotor and wing-beat modulation frequencies; Johnson detection and recognition criteria (Svanström 2021, Kaleem & Rehmani); RF band plan (2.4 and 5.8 GHz, 900 and 433 MHz, 1.2 and 1.3 GHz, hopping) and RF detection-range table (Seidaliyeva 2023, secondary RF-detection page); acoustic detection range of about 50 to 300 m and the 2026 MEMS array at about 60 m (Ghouli 2026, Kaleem & Rehmani). Wave 4b made the label automatic: every trainee-visible detection, track and assist view carries `data_status: "reference"` while any value is `verified: false` (ADR-019, `tests/test_sensor_provenance.py`), so nothing is shown unlabelled; the register rows are still wanted. The shipped profiles use F01 with `verified: false` for these (radar, RF and acoustic figures) or D12 for the camera figures stated in docs/02-research.md. | CC (SD to approve rows) | Add a register row per source with its licence and what was derived from it, then move the matching parameters off F01 and set `verified` only where the profile value is the source's stated figure. Q-09 covers the figures that are also unverified in the research. | Before wave 5 ships a console as anything but reference data |
| Q-21 | **Radar and acoustic profiles cover three classes.** `rotary-small`, `fixed-wing-small` and `bird` (radar, acoustic, with `autonomous-small` for RF); `build_sensors` refuses a scenario whose threat class has no row in a sensor's confusion table or per-class figures. | CC (wave 8) | When wave 8 adds threat classes (FPV, swarm member, kite, balloon, permitted civil drone), extend every profile's tables and per-class parameters in the same change, with a test that every class in the catalogue is covered. | Wave 8 |
| Q-22 | **Tracker, error-model and assist parameters are project-authored.** `TrackerConfig`, `ErrorModel` and `AssistConfig` values (gates, confirmation counts, swap/split/merge maxima, assist hit, false-alarm and class rates) are F01, `verified: false`, and the wave-8 catalogue classes are missing from `NON_THREAT_CLASSES`. | CC (wave 8, wave 11a) | Extend `NON_THREAT_CLASSES` with kite, balloon and permitted civil drone in wave 8; tune the defaults against pilot data in wave 11a if an effect on learning is claimed. Until then show them as reference data. | Wave 8 |

### Product and pilot

| ID | Question | Owner | How to close | Needed by |
|---|---|---|---|---|
| Q-13 | **Pilot logistics**: recruit 12 volunteers for 4 sessions, consent form text, and whether the institute needs ethics sign-off. | SD | Ask IILM whether sign-off is needed; draft the consent form; Claude Code adds data export and delete in wave 13c. | Before wave 12a completes |
| Q-14 | **VR headset access**: none assumed. Decide whether any headset test is attempted. | SD | If none, keep the wording "VR mode, emulator-tested". | Wave 14 |
| Q-15 | **Hindi translation review**: who reviews the HI strings for correct military and technical terms. | SD | Name a reviewer. The review sheet [i18n/HI_REVIEW.md](i18n/HI_REVIEW.md) lists every Hindi string with a blank verdict column; all Hindi is unreviewed until that column is filled. Claude Code adds a glossary file in wave 2. | Wave 2 onward |
| Q-16 | **Real Doppler RAD-DAR** dataset (D17) was not found. | SD | Supply a link, or the row stays dropped. | Optional |
| Q-17 | **Optional AAR narration backend**: wave 12b ships a deterministic template narrator. Decide whether a local language-model backend is wanted, and which licence and hardware budget applies. | SD | Name a model that fits the 8 GB floor and has an open licence, or keep template-only. | Before wave 12b |

## Closed

| ID | Question | Resolution | Date |
|---|---|---|---|
| — | Q1–Q6 from docs/00-gap-check.md (trainee, hardware and VR, next milestone, team, pilot size, Hindi) | Answered; see [DECISIONS.md](DECISIONS.md) ADR-002 to ADR-010 | 2026-10-17 |
| — | Platform name | SUDARSHAN confirmed, ADR-001 | 2026-10-17 |
| Q-02 | Choice of host for the live link | **Decided by owner:** Azure for Students, Linux VM (Ubuntu 24.04 LTS, x86_64). Options compared in [HOSTING_OPTIONS.md](HOSTING_OPTIONS.md); deployment kit and runbook in wave 2 ([DEPLOY.md](DEPLOY.md)). VM size to be chosen from the measured memory in HOSTING_OPTIONS.md. | 2026-10-17 |
| Q-19 | API image did not ship `sim/` or `packs/` | Closed in wave 5: `infra/Dockerfile.api` copies both, `app.contracts.paths.packs_root()` finds the packs in a checkout and in the image (`PACKS_DIR` overrides), and `make prod-check` runs `python -m app.cli sim-check` inside the API container. `tests/test_image_contents.py` fails if the Dockerfile stops copying them. | 2026-10-18 |
| Q-18 | Documentation inside the submission cut | Wave 15 split into 15a (in the cut) and 15b (depth), ADR-013 | 2026-10-17 |
