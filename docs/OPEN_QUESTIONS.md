# Open questions

Everything the research marked unverified or undecided. Owner is **SD** (the user) or **Claude Code** (CC). Close an item by resolving it, recording the outcome in [DECISIONS.md](DECISIONS.md) if it is a decision, and moving the row to **Closed** with the date.

## Open

### Decisions

| ID | Question | Owner | How to close | Needed by |
|---|---|---|---|---|
| Q-01 | **Choose a licence** for the repository. Depends on dataset terms: ODbL share-alike (G02), CC BY attribution (D14) and any pack we ship. No LICENSE file exists yet, by instruction. | SD | After Q-05 and Q-06: pick MIT, Apache-2.0 or AGPL-3.0 for code and CC BY for docs, check each against bundled packs, then add LICENSE and a NOTICE file in a separate commit. | Before the repo goes public or release 1.0 |
| Q-02 | **Choice of host** for the live link: Docker-capable, persistent storage, reachable by evaluators. Render free is excluded. | SD | Pick a provider (VPS, or a container host with a volume) and note it in BUILD_LOG.md. Claude Code then adds host config to docs/DEPLOY.md. | Start of wave 2 deployment |
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

### Product and pilot

| ID | Question | Owner | How to close | Needed by |
|---|---|---|---|---|
| Q-13 | **Pilot logistics**: recruit 12 volunteers for 4 sessions, consent form text, and whether the institute needs ethics sign-off. | SD | Ask IILM whether sign-off is needed; draft the consent form; Claude Code adds data export and delete in wave 13. | Before wave 12 completes |
| Q-14 | **VR headset access**: none assumed. Decide whether any headset test is attempted. | SD | If none, keep the wording "VR mode, emulator-tested". | Wave 14 |
| Q-15 | **Hindi translation review**: who reviews the HI strings for correct military and technical terms. | SD | Name a reviewer; Claude Code produces a glossary file for them in wave 2. | Wave 2 onward |
| Q-16 | **Real Doppler RAD-DAR** dataset (D17) was not found. | SD | Supply a link, or the row stays dropped. | Optional |

## Closed

| ID | Question | Resolution | Date |
|---|---|---|---|
| — | Q1–Q6 from docs/00-gap-check.md (trainee, hardware and VR, next milestone, team, pilot size, Hindi) | Answered; see [DECISIONS.md](DECISIONS.md) ADR-002 to ADR-010 | 2026-10-17 |
| — | Platform name | SUDARSHAN confirmed, ADR-001 | 2026-10-17 |
