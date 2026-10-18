# SUDARSHAN documentation

Planning pack for SIH 2026 PS 26247, plus the working documents that drive the build. Files 00–09 are the planning deliverables, moved here unchanged except for the confirmed platform name and status notes at the top of 00, 01 and 09.

## Working documents

| File | What it is |
|---|---|
| [BUILD_LOG.md](BUILD_LOG.md) | Resumable build state: wave list, status, deploy record and the rules every wave follows. |
| [waves/](waves/README.md) | One file per build wave: scope, acceptance criteria, model and paste-ready Claude Code prompt. Wave 2 is the priority milestone (first live link). |
| [DATA_REGISTER.md](DATA_REGISTER.md) | Operational dataset table: licence, what we may ship, calibration-only sources and items needing verification. |
| [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) | Everything unverified or undecided, each with an owner and how to close it. |
| [DECISIONS.md](DECISIONS.md) | Decision log, one short ADR per decision. |
| [DESIGN.md](DESIGN.md) | Design system tokens, rules for every screen and the banned list. |
| [SIM_CORE.md](SIM_CORE.md) | Simulation core: contracts, tick model, random streams, determinism rules, event log, snapshots, replay and golden files. |
| [TERRAIN_PACKS.md](TERRAIN_PACKS.md) | Terrain pack format, frame, bake pipeline, line-of-sight and serving contract. |
| [TRACEABILITY.md](TRACEABILITY.md) | Live requirements traceability; the built-proof column fills as waves land. |
| [HOSTING_OPTIONS.md](HOSTING_OPTIONS.md) | Four Docker-capable hosting options compared for Q-02; all prices unverified. |
| [i18n/HI_REVIEW.md](i18n/HI_REVIEW.md) | Every Hindi string with a blank reviewer-verdict column (unreviewed). |
| [evidence/wave-1/UI_REVIEW.md](evidence/wave-1/UI_REVIEW.md) | Wave 1 screenshots and a frank UI critique. |
| [RELEASE.md](RELEASE.md) | Release process stub, including the dataset-licence re-check. |

## Planning pack

| File | What it is |
|---|---|
| [PS-26247.md](PS-26247.md) | Official problem-statement text as supplied (source typos kept). |
| [00-gap-check.md](00-gap-check.md) | Requirement gaps, the six questions and the defaults now accepted. |
| [01-naming.md](01-naming.md) | Naming-conflict check on SUDARSHAN, alternatives, tagline and wordmark direction. |
| [02-research.md](02-research.md) | Cited research brief: current training practice, sensors, swarms, scoring, adaptive learning, generation. |
| [03-data-register.md](03-data-register.md) | Full research register of 26 open datasets with sizes, terms, sources and notes. |
| [04-engine.md](04-engine.md) | Engine comparison and the Three.js decision, with the performance benchmark gate. |
| [05-architecture.md](05-architecture.md) | Technical architecture, data flows, deployment view and a PPT-ready slide description. |
| [06-requirements-traceability.md](06-requirements-traceability.md) | Every PS clause mapped to a mechanism, a proof type and its risk. |
| [07-ui-map.md](07-ui-map.md) | Full UI map with counts, the live-session layout and the design-system direction. |
| [08-demo.md](08-demo.md) | The 10-minute storytelling demo script and its must-work list. |
| [09-build-waves.md](09-build-waves.md) | The original 15-wave build plan in dependency order, with the first wave 1 prompt. |
| [10-differentiators.md](10-differentiators.md) | Prioritised features beyond the PS: 12 headline features, the 5-feature demo cut, waves and acceptance tests. |

Section headings inside 00–09 keep their original deliverable numbers (01–09, 03b). Cross-references such as "see 02" or "(04)" use those numbers:

| Original number | File here |
|---|---|
| 01 | 00-gap-check.md |
| 02 | 01-naming.md |
| 03 | 02-research.md |
| 03b | 03-data-register.md |
| 04 | 04-engine.md |
| 05 | 05-architecture.md |
| 06 | 06-requirements-traceability.md |
| 07 | 07-ui-map.md |
| 08 | 08-demo.md |
| 09 | 09-build-waves.md |
