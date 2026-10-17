# Decision log

ADR-style, one short entry per decision. Newest at the bottom. A changed decision gets a new entry that supersedes the old one; old entries are not edited.

Status values: **Accepted**, **Superseded by ADR-n**.

---

## ADR-001 · Platform name: SUDARSHAN

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Context:** The naming check ([01-naming.md](01-naming.md)) found strong overlap with Mission Sudarshan Chakra and the IAF S-400 "Sudarshan", and recommended NIGAH. The user chose to keep SUDARSHAN.
- **Decision:** The platform is SUDARSHAN. In code the name is one value, `productName` in `brand.json` at the repo root (created in wave 1); nothing else hard-codes it. Descriptor line: "Counter-UAS Threat Recognition Trainer".
- **Consequences:**
  - A rename is a one-line `brand.json` change plus a find-and-replace in docs prose.
  - The association risk stays, so every surface carries the line "independent student project, no official affiliation" and avoids chakra, shield, crest, tricolour and emblem imagery.
  - The IP India trade-mark search (Classes 9, 41, 42) is still open; see [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

## ADR-002 · Engine: Three.js

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user, on the analysis in [04-engine.md](04-engine.md)
- **Context:** Browser-based, offline, 8 GB integrated-graphics floor, local scenes up to about 20 × 20 km, WebXR optional.
- **Decision:** Three.js with `WebGLRenderer` as the shipping path; `WebGPURenderer` only behind a flag and only if our benchmark shows a gain. MapLibre GL with offline vector tiles for the 2D map. CesiumJS rejected (offline-tiles burden, no official WebXR); Babylon.js is the fallback only if Three.js XR fails our tests.
- **Consequences:** The benchmark gate in 04 is a wave 7 acceptance criterion, and its result in `docs/PERFORMANCE.md` is the only performance claim we make.

## ADR-003 · Trainee model: operator plus detachment commander

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Context:** DSSC trains staff officers, but the PS says "usable at unit level" ([00-gap-check.md](00-gap-check.md) Q1).
- **Decision:** The core trainee is the sensor operator. The detachment commander is a second role in team mode (sector split, handoff). A staff-planning layer (sensor siting, coverage gaps) is a stretch module, not core.
- **Consequences:** Scoring, the UI map and the hero demo target the operator first; team mode (waves 10 and 13) adds the commander.

## ADR-004 · Hardware floor: 8 GB laptop, integrated graphics; VR deferred

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Context:** The PS asks for minimal specialised hardware ([00-gap-check.md](00-gap-check.md) Q2).
- **Decision:** The floor is an 8 GB RAM laptop with integrated graphics (Intel Iris Xe class) and no internet. No VR headset is assumed. WebXR stays optional and deferred to wave 14.
- **Consequences:** Without a headset, the only VR claim allowed is "VR mode, emulator-tested". Quality tiers and the benchmark gate are tuned to this floor.

## ADR-005 · Hindi UI from the first wave

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Context:** i18n is cheap when wired in early and painful to retrofit ([00-gap-check.md](00-gap-check.md) Q6).
- **Decision:** English and Hindi from wave 1. Wave 1 wires the i18n framework with EN and HI strings for its placeholder page; wave 2 makes it a requirement for every trainee-facing string, with Noto Sans Devanagari self-hosted.
- **Consequences:** No hard-coded user-facing strings. CI checks that every EN key has an HI entry.

## ADR-006 · Deployment is first-class; host must be Docker-capable with persistent storage

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Context:** The next SIH milestone is a deployable live link of the platform.
- **Decision:** The first deployable slice (wave 2) goes live early, and every later wave keeps the deployed build working. Hosting needs a Docker-capable host with persistent storage. Render free is unsuitable (no persistent disk, sleeps). A Vercel frontend needs `VITE_API_URL` at build time and `CORS_ORIGINS` on the backend. Health is verified at `/healthz`.
- **Consequences:** Every wave's acceptance includes production images building and `make smoke` passing in production mode. The user deploys; Claude Code never does. The host choice is open ([OPEN_QUESTIONS.md](OPEN_QUESTIONS.md)).

## ADR-007 · Data licence policy: "calibrated from", never "trained on"

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** project standard, from [02-research.md](02-research.md) §7 and [03-data-register.md](03-data-register.md)
- **Context:** Most open drone datasets are research-only, non-commercial, or state no data licence.
- **Decision:** Datasets are used to derive and cite numeric parameters. Raw samples ship only under a confirmed open licence. Non-commercial, research-only and "not stated" sources are never redistributed and never shown as clips. Licence status is re-checked before each release.
- **Consequences:** Every parameter carries a register ID from [DATA_REGISTER.md](DATA_REGISTER.md). Pitch wording: "parameters calibrated from published open research datasets".

## ADR-008 · Scenarios are "verified solvable by test run", not "provably solvable"

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** project standard, from [02-research.md](02-research.md) §6
- **Context:** The generator accepts a scenario only if a headless oracle defender wins it within the time budget. That is a practical check; a formal guarantee would need a constraint encoding we are not building.
- **Decision:** All docs, UI and slides say "verified solvable by test run" (or "verified solvable by an oracle run"). Never "provably solvable" or "guaranteed solvable".
- **Consequences:** The scenario record stores the seed, generator version and every check result, so the AAR can show what was verified.

## ADR-009 · Team: solo, with Claude Code for all coding

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Decision:** One person; Claude Code writes all code. Waves run in strict dependency order, with at most 2 worktree subagents per wave.
- **Consequences:** `docs/BUILD_LOG.md` must carry all state across `/clear`.

## ADR-010 · Pilot: 12 civilian volunteers × 4 sessions

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Decision:** 12 civilian student volunteers, 4 sessions each (about 30 minutes), starting once wave 12 is green. Consent form, pseudonymous IDs, no personal data beyond a call-sign and cohort.
- **Consequences:** Effectiveness claims are limited to what this pilot measures (learning curves, a new-seed rote-learning test), at Kirkpatrick levels 1–2. With fewer than 8 volunteers we report case studies, not curves.

## ADR-011 · Headline differentiators and README direction

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Context:** The PS items are the floor; evaluators need visible capability beyond them. The README also needed to read as a product page, not a planning note.
- **Decision:** Twelve headline features (H1–H12 in [10-differentiators.md](10-differentiators.md)), with five in the 10-minute demo: sensor placement trainer, contact-report scoring, adaptive adversary, counterfactual AAR, signed record with competency matrix. The README is product-led, lists every capability as Planned until merged and deployed, and keeps one neutral data line; the earlier "Honest data", "Scope and safety" and "Affiliation" sections are removed from it. The locked rules in CLAUDE.md are unchanged and still govern the UI labels and wording.
- **Consequences:** Headline features are scheduled into existing waves, not new ones, and wave files change only when each wave starts. The README capability and status tables are updated as waves land.

## ADR-012 · Headline features scheduled into waves; overloaded waves split

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Context:** ADR-011 chose twelve headline features. Placing them in the existing 15 waves overloaded several, and the user asked for site builder and sensor placement trainer in separate waves.
- **Decision:** Wave files now carry the headline features. Split waves: 4 → 4a sensor models, 4b tracking and AI assist; 9 → 9a scenario engine, 9b site builder, 9c sensor placement trainer; 10 → 10a class management and rule packs, 10b live monitor and director mode; 11 → 11a adaptive learning with adversary and fatigue, 11b recognition academy and progression; 12 → 12a full AAR and reports, 12b counterfactual review; 13 → 13a team mode, 13b signed records and competency matrix, 13c admin and pack manager; 14 → 14a hardening, 14b WebXR (optional). Waves 3, 5, 6 and 15 gained scope or edits; 1, 2, 7 and 8 are unchanged. Remainder of an unfinished session is logged as `<wave>.2`.
- **Consequences:** The pilot (ADR-010) starts once wave 12a is Done, not 12. The demo-complete live link is 12b; the signed-record beat of the demo needs 13b. Wave 9a stays on Opus; 9b and 9c are Sonnet. Wave 14b may be skipped without blocking release 1.0. Narration (12b) ships as a template narrator only; a local-model backend is an open question.

## ADR-013 · Wave 15 split into 15a (in the cut) and 15b (depth); review checkpoints

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Context:** Wave 15 depended on all waves, so the documentation a submission needs (manuals, SOPs, cost sheet, traceability, final report) sat outside the Submission-ready cut (Q-18).
- **Decision:** 15a covers those documents, release notes for the submission and the demo rehearsal; it depends only on the cut waves, with 14a last, and joins the cut (22 of 25 waves). 15b covers the 1.0 polish, documentation of any depth wave built, and pilot results; it is depth, with 13a and 14b. Three review checkpoints are defined in the build log: A after wave 8, B after wave 12b, C after the cut and 15a.
- **Consequences:** The cut ends at 15a. The wave 3 ADR for the RNG scheme and tick model is now ADR-014. Any depth wave built must be documented in 15b, and the manuals state what is not built.

