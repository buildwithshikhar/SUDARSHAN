# Wave 3 · Contracts + deterministic sim core

| | |
|---|---|
| Depends on | 1 |
| Deployment | Keep the live build green. No new user-facing feature. |

**Goal.** Versioned contracts and a deterministic, replayable simulation core that every later wave builds on.

## Scope

- Pydantic models with exported JSON Schemas: scenario spec (`scenario.v1`), rule pack (`rulepack.v1`, YAML), sensor profile (`sensor-profile.v1`, every parameter has a `source_id`), event record (`{seq, t, type, actor, payload, prev_hash, hash}`).
- Sim core as a pure Python package (numpy, no FastAPI imports): fixed 20 Hz tick, seeded RNG with independent streams per subsystem, world state (flat terrain, time of day and weather as state), single-drone kinematics (waypoint follower with speed, climb and turn limits; kinematics only).
- Hash-chained event log (SHA-256) and replay from spec + seed + action log.
- TypeScript types generated from the JSON Schemas into `apps/web`, with a CI drift check.
- One fictional example each: rule pack, sensor profile stub, scenario.
- State snapshot and restore at any tick (used by director-mode branching and counterfactual review), and golden-file regression tests that pin sim behaviour.

## Out of scope

- Sensor models, WebSocket transport and any UI.

## Acceptance criteria

- Same spec + seed + action log gives an identical state hash after 10,000 ticks, in two separate processes.
- Replay of a recorded session reproduces every event and the final state exactly.
- Tampering with any event breaks chain verification at that event.
- Schemas validate the examples and reject malformed inputs (tests for each).
- Property tests (hypothesis) keep kinematics inside the class limits.
- Restoring a snapshot at tick N and running to tick M gives the same state hash as a straight run (test).
- Changing a physics constant fails a golden-file test with a readable diff.
- ADR added for the RNG scheme and tick model.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

## Brief

````text
ROLE: Build wave 3 (Contracts + deterministic sim core) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). Follow the project rules in CONTRIBUTING.md, above all the content rules.

READ FIRST: docs/BUILD_LOG.md (confirm wave 2 is Done and main is green; if not, stop and tell me). Then: docs/05-architecture.md (§1, §3.2, §5) and docs/02-research.md §3 (swarm models, for future-proofing the entity model only).

GOAL: Versioned contracts and a deterministic, replayable simulation core that every later wave builds on.

STEP 1 — Contracts (main track first; everything else depends on them)
- services/api/app/contracts/: Pydantic v2 models for ScenarioSpec, RulePack, SensorProfile (each numeric parameter is {value, unit, source_id, verified}), EventRecord.
- Export JSON Schemas to packs/schemas/*.v1.json via a make target; CI fails if exported schemas differ from the models.
- Generate TS types into apps/web/src/contracts/ (json-schema-to-typescript); CI drift check.

STEP 2 — Sim core (track A, worktree)
- services/api/sim/: World, Entity, Kinematics, Clock (20 Hz fixed), Rng (numpy PCG64, one named stream per subsystem derived from the scenario seed).
- Single-drone waypoint follower with max speed, climb rate and turn rate from the spec. No guidance or attack logic.
- Deterministic iteration order everywhere (no dict or set ordering surprises, no wall-clock time).

STEP 3 — Event log and replay (track B, worktree)
- EventLog with SHA-256 chaining over canonical JSON; verify() returns the first bad seq.
- Replayer: spec + seed + action log → identical event stream and final state hash.

STEP 4 — Tests and docs (main track)
- Determinism across two processes, replay equality, tamper detection, schema round-trips, hypothesis tests on kinematics.
- Snapshot/restore: restore at tick N and run to M equals a straight run (state hash). Golden files for a fixed scenario set, with a readable diff on failure.
- docs/SIM_CORE.md: tick model, RNG streams, determinism rules for future contributors.
- ADR-014 in docs/DECISIONS.md: RNG scheme and tick model.

OUT OF SCOPE (do not build):
- Sensor models, WebSocket transport and any UI.

ACCEPTANCE (all must be true):
- Same spec + seed + action log gives an identical state hash after 10,000 ticks, in two separate processes.
- Replay of a recorded session reproduces every event and the final state exactly.
- Tampering with any event breaks chain verification at that event.
- Schemas validate the examples and reject malformed inputs (tests for each).
- Property tests (hypothesis) keep kinematics inside the class limits.
- Restoring a snapshot at tick N and running to tick M gives the same state hash as a straight run (test).
- Changing a physics constant fails a golden-file test with a readable diff.
- ADR added for the RNG scheme and tick model.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 3" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 4a.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 3.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 4a.
````
