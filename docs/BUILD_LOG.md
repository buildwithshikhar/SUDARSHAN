# Build log

The resumable state of the build. After every `/clear`, Claude Code reads [CLAUDE.md](../CLAUDE.md), then this file, then the wave file named under **Current position**. If this file and the repo disagree, the repo (git history and CI) wins; fix this file first.

## Current position

- **Phase:** wave 4a in progress (sensor models), steps 1 to 3 of 4 done (framework, radar, EO/IR, RF, acoustic, `docs/SENSOR_MODELS.md`). Wave 3 is complete locally and waits only for the owner to confirm CI; wave 4a started at the owner's instruction before that confirmation.
- **Current wave:** 4a · Sensor models → [waves/wave-04a-sensor-models.md](waves/wave-04a-sensor-models.md)
- **Next step:** wave 4a STEP 4 (acceptance pass: cross-model checks, `make smoke` in production mode, set the wave to Done once the owner confirms CI), then wave 4b. Owner still to confirm CI for the wave 3 and 4a commits, and to record the smoke date for the live link.
- **Main is:** green locally (lint, typecheck, unit, `make prod-check`); CI result for the latest commits is owner-confirmed only (see the wave entries).
- **Deployed build:** live at https://sudarshan.centralindia.cloudapp.azure.com, running commit b722313 (wave 2 build; owner-reported, 2026-10-18).

## Planning updates

- 2026-10-17: README rewritten as a product README (banner in `docs/assets/`, status table mirrors the wave table above, capabilities all Planned). Update its status table and capability states whenever a wave is marked Done.
- 2026-10-17: [10-differentiators.md](10-differentiators.md) added. Headline features: H1 adaptive adversary, H2 sensor placement trainer, H3 site builder, H4 contact-report scoring, H5 track management with association errors, H6 counterfactual AAR, H7 recognition academy, H8 competency matrix with signed records, H9 unit readiness dashboard, H10 scenario language and signed packs, H11 director mode, H12 stress and fatigue modelling. Demo five: H2, H4, H1, H6, H8. The wave files are not yet changed; pull an entry into its wave only when that wave starts and record it in the wave entry.
- 2026-10-17: Wave execution protocol added to CLAUDE.md.
- 2026-10-17: Headline features folded into the wave files and overloaded waves split (4a/4b, 9a/9b/9c, 10a/10b, 11a/11b, 12a/12b, 13a/13b/13c, 14a/14b); see ADR-012. Waves 1, 2, 3, 5, 6, 7, 8 and 15 keep their numbers; 3, 5, 6 and 15 gained scope or edits.
- 2026-10-18: Sign-in page no longer links to About; the About and data notice page (`/about`, EN/HI) is linked from the footer on every page. No Help menu exists yet (wave 15a); link it there when built.

## Waves

Status values: Not started · In progress · Blocked · Done. A wave is Done only when its acceptance criteria are met, CI is green on `main`, and (from wave 2 on) the deployed build is verified.

| Wave | Name | Depends on | Model | Deploy | Cut | Status |
|---|---|---|---|---|---|---|
| 1 | [Repo bootstrap](waves/wave-01-repo-bootstrap.md) | — | Sonnet | Deploy-ready (prod images, smoke test) | Cut | Done |
| 2 | [Design system + app shell](waves/wave-02-design-system-shell.md) | 1 | Sonnet | **PRIORITY MILESTONE: first live link** | Cut | In progress |
| 3 | [Contracts + deterministic sim core](waves/wave-03-contracts-sim-core.md) | 1 | Opus | Keep live build green | Cut | In progress |
| 4a | [Sensor models](waves/wave-04a-sensor-models.md) | 3 | Opus | Keep live build green | Cut | In progress |
| 4b | [Tracking, fusion + AI assist](waves/wave-04b-tracking-ai-assist.md) | 4a | Opus | Keep live build green | Cut | Not started |
| 5 | [Live-session vertical slice](waves/wave-05-live-session-slice.md) | 2, 4b | Sonnet | Redeploy: playable slice | Cut | Not started |
| 6 | [Scoring + debrief](waves/wave-06-scoring-debrief.md) | 5 | Sonnet | Redeploy | Cut | Not started |
| 7 | [3D realism + terrain packs](waves/wave-07-3d-realism-terrain.md) | 5 | Sonnet (Opus if gate fails) | Keep live build green | Cut | Not started |
| 8 | [Threat breadth](waves/wave-08-threat-breadth.md) | 4a, 7 | Sonnet | Keep live build green | Cut | Not started |
| 9a | [Scenario engine](waves/wave-09a-scenario-engine.md) | 6, 8 | Opus | Redeploy: generated scenarios | Cut | Not started |
| 9b | [Site builder](waves/wave-09b-site-builder.md) | 9a, 7 | Sonnet | Redeploy | Cut | Not started |
| 9c | [Sensor placement trainer](waves/wave-09c-sensor-placement.md) | 9b, 4a, 7 | Sonnet | Redeploy | Cut | Not started |
| 10a | [Class management + rule packs](waves/wave-10a-class-management.md) | 5, 9a | Sonnet | Keep live build green | Cut | Not started |
| 10b | [Live monitor + director mode](waves/wave-10b-director-mode.md) | 10a, 3, 6 | Sonnet | Keep live build green | Cut | Not started |
| 11a | [Adaptive learning + adaptive adversary](waves/wave-11a-adaptive-learning.md) | 6, 9a | Sonnet | Keep live build green | Cut | Not started |
| 11b | [Recognition academy + progression](waves/wave-11b-recognition-academy.md) | 4a, 8, 11a | Sonnet | Keep live build green | Cut | Not started |
| 12a | [Full AAR + reports](waves/wave-12a-aar-reports.md) | 6, 10b, 11b | Sonnet | Redeploy: pilot-ready | Cut | Not started |
| 12b | [Counterfactual review + briefing export](waves/wave-12b-counterfactual-aar.md) | 12a, 10b, 3 | Sonnet | Redeploy: demo-complete (signed-record beat in 13b) | Cut | Not started |
| 13a | [Team mode](waves/wave-13a-team-mode.md) | 10b, 12a, 4b | Sonnet | Keep live build green | Depth | Not started |
| 13b | [Signed records + competency matrix](waves/wave-13b-trust-competency.md) | 12a, 11b | Sonnet | Keep live build green | Cut | Not started |
| 13c | [Admin + pack manager](waves/wave-13c-admin-packs.md) | 13b, 9a | Sonnet | Keep live build green | Cut | Not started |
| 14a | [Hardening + accessibility](waves/wave-14a-hardening.md) | 7, 12b, 13c | Sonnet | Keep live build green | Cut | Not started |
| 14b | [WebXR (optional)](waves/wave-14b-webxr.md) | 14a | Sonnet | Keep live build green | Depth | Not started |
| 15a | [Submission documentation](waves/wave-15a-submission-docs.md) | cut waves, 14a last | Sonnet | Redeploy: submission build | Cut | Not started |
| 15b | [Release 1.0 polish](waves/wave-15b-release-polish.md) | 15a, plus any depth wave built | Sonnet | Release 1.0 | Depth | Not started |

**Pilot** (the user's activity, not a wave): starts once wave 12a is Done. Waves 12b onward continue alongside it. The demo-complete live link is wave 12b.

## Submission-ready cut

The smallest ordered set of waves that gives a complete, polished, demoable live link covering every problem-statement requirement (R0–R19 in [06-requirements-traceability.md](06-requirements-traceability.md)), the five demo features from [10-differentiators.md](10-differentiators.md) and the documentation a submission needs. Waves marked **Depth** in the table above come after the cut.

**Order:** 1 → 2 → 3 → 4a → 4b → 5 → 6 → 7 → 8 → 9a → 9b → 9c → 10a → 10b → 11a → 11b → 12a → 12b → 13b → 13c → 14a → 15a. That is 22 of 25 waves. The live link exists from wave 2, becomes playable at 5, pilot-ready at 12a (pilot starts), demo-complete at 12b, and submission-ready at 15a; 13b adds the signed-record beat.

**Why it is not smaller.** Every wave in the cut is either a requirement or a dependency of one, as the wave files state them. Examples: the sensor placement trainer (9c) needs the site builder (9b); the full AAR (12a) needs the recognition academy (11b); the signed record and competency matrix (13b) need 12a and 11b; the offline and LAN checks the demo relies on (14a) need the admin wave (13c); the submission documentation (15a) depends on the cut waves with 14a last, and not on 13a or 14b.

**PS coverage in the cut**

| Requirement | Waves |
|---|---|
| R0 AI elements | 4b (AI assist), 11a (learner model, adaptive adversary) |
| R1, R12 single and swarm threats | 8 |
| R2 low cost | 15a (cost sheet), 14a |
| R3, R9 weather, day/night, NV and thermal | 4a, 7 |
| R5, R6, R7 recognise, classify, respond | 4a, 4b, 5, 6 |
| R8, R16 varied scenarios, scripted and generated | 9a (with 9b for sites) |
| R10 degraded sensors | 4a, injects in 10b |
| R11 urban and rural terrain | 7 |
| R13 unit level, offline | 10a, 10b, 13c, 14a (offline and LAN tests), 15a (instructor SOP) |
| R14 minimal hardware | 7 (floor-laptop benchmark), 14a |
| R17 decision-tree scoring | 6 |
| R18 AAR, individual and unit | 12a |
| R19 adjustable difficulty, anti-rote | 9a, 11a |
| R15 desktop or VR-capable | Desktop in the cut; the VR mode is 14b (Depth). The PS says "desktop or VR-capable", so desktop meets it; no VR claim is made. |
| R4 repetitions at scale | Mechanism in the cut; the measured figure comes from the pilot. |
| Traceability, manuals, SOPs, final report | 15a |

**Demo features in the cut (all five):** sensor placement trainer (9b, 9c), contact-report scoring (6), adaptive adversary (11a), counterfactual review (12b), signed record and competency matrix (13b). Director mode (10b) covers the inject beat.

**Depth (after the cut):** 13a team mode, 14b WebXR, 15b release 1.0 polish. Team mode is not needed by any PS clause or demo feature, so the demo's sector-handoff moment (7:00) is dropped or shown as a single-operator swarm run until 13a lands, and track handover (H5 second half) waits with it. Wave 15b documents whichever depth waves were built and adds pilot results.

### Checkpoints

Three points where a reviewer can look at the live link and check what has been built. At each, `make smoke URL=<live url>` passes (`/healthz`, `/readyz`, `/api/v1/version`) and the permanent "fictional scenario · open-source parameters" label is visible.

**Checkpoint A · after wave 8.** Playable single-operator trainer.
- Sign in as a trainee, play the scripted day scenario on radar, EO/IR, RF and acoustic consoles with a fused track table and the simulated AI assist, then finish.
- Rural and urban terrain, day, night, NV and thermal looks, modelled weather and degraded sensors.
- Single drones, swarms, decoys and clutter (birds, kites, balloons, permitted civil drones).
- Cue a sensor, fix a track swap, file a structured contact report, and see the ROE rule text and version when a response is blocked.
- Scored debrief with the decision path and report grades; the same seed and actions reproduce the same result.
- Verify: no ground truth reaches a trainee socket (test); the 12-client load test and the floor-laptop benchmark are recorded in `docs/PERFORMANCE.md`.
- Not yet: generated scenarios, instructor tools, full AAR, adaptive drills.

**Checkpoint B · after wave 12b.** Demo-complete, pilot running.
- Instructor console: cohorts, launch, live monitor with ground truth, inject macros, annotations, pause and branch.
- Generated scenarios marked "verified solvable by test run" with a novelty check; scripted library; scenario editor; site builder; sensor siting with coverage and blind spots.
- Adaptive drills, weakness-biased adversary, stress and fatigue profiles, recognition academy and progression levels.
- Seen-versus-truth replay, unit readiness dashboard, PDF and CSV export, counterfactual branches, clip export. `make demo` reproduces the seeded state labelled "reference data (seeded)".
- Verify: demo must-work items pass as automated checks; the counterfactual with no change reproduces the original score.
- Not yet: signed-record verification, competency matrix, admin tools, security review, submission documents.

**Checkpoint C · after the full cut and wave 15a.** Submission-ready.
- Signed records with a "Record chain verified" screen and CLI, competency matrix, PDF certificates with verification codes.
- Admin: users, units, signed packs, backup and restore.
- Accessibility pass with high-contrast and colour-blind-safe themes, low-bandwidth mode, recorded-feed adapter, security review, offline and two-laptop LAN tests.
- User manual, instructor and admin SOPs, API docs, cost sheet, completed traceability matrix, final report with pilot figures only as measured (pending sections labelled), release notes and the demo rehearsal checklist.
- Verify: tamper one byte of a record and verification fails at that event; the traceability matrix has no empty proof cell; the wording grep passes.
- Not yet: team mode, WebXR, release 1.0 polish (depth).

## Deployed build

The user deploys; Claude Code never does. Fill this in when a deploy happens.

| Field | Value |
|---|---|
| Host | Azure for Students Linux VM, Central India region (owner decision Q-02) |
| Live URL | https://sudarshan.centralindia.cloudapp.azure.com (wave 2 build; owner-reported, 2026-10-18) |
| Deployed commit | b722313 (owner-reported, 2026-10-18). Later commits (waves 3 and 4a) are not deployed; none changes user-facing behaviour. |
| Last verified (`/healthz`, `/readyz`, `/api/v1/version`) | not reported yet. Owner: run `make smoke URL=https://sudarshan.centralindia.cloudapp.azure.com` and `make check-deploy URL=...`, then record the date. |

## Rules for updating this log

Every wave follows these rules. They are part of each wave's acceptance criteria.

1. **On wave start:** set the wave to In progress, update **Current position**, and add a wave entry under **Wave entries** from the template below.
2. **After every merged step:** append the commit hash and one line to the wave entry's **Done** list, in the same commit or the one right after. A `/clear` must be able to resume from this file alone.
3. **Decisions:** any design decision made during the wave goes in the entry with its reason. If it changes a recorded decision, also add an ADR to [DECISIONS.md](DECISIONS.md).
4. **Open items:** anything unresolved goes in the entry and, if it needs the user, in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).
5. **Deploy check:** before a wave is Done, record that the production images built and `make smoke` passed in production mode. From wave 2 on, record the commit the user should deploy and leave **Deployed build** for the user to confirm.
6. **On wave end:** set the status to Done only when CI is green on `main`. Write the exact first step of the next wave under **Next wave entry point**, and update **Current position**.
7. **On a split:** if about 60% of the session is used before acceptance, stop at the next green commit, set the status to In progress, and log the remainder as wave n.2 (for example 9a.2) with its first step.
8. **Blocked:** set the status to Blocked, state the cause and what is needed in one line, and stop.
9. Never mark a step done that is not merged and green. Never record a red build as a resume point.

## Wave entry template

```markdown
### Wave N · Name

- Status: In progress | Blocked | Done
- Started from commit: <hash>
- Goal: <one line from the wave file>

**Done**
- <hash> <conventional commit subject>

**Decisions**
- <decision> because <reason>

**Tests**
- api: <count> passed · web: <count> passed · e2e: <count> passed · coverage: <n>%

**Deploy check**
- Production images built: yes/no · `make smoke` (production mode): pass/fail
- Commit to deploy: <hash>

**Open issues**
- <item>

**Next wave entry point**
- <exact first step>
```

## Wave entries

### Wave 1 · Repo bootstrap

- Status: Done. CI run #14 on `main` is green (owner-reported, 2026-10-18). Run #13 did not pass and was superseded by #14. Run URL: pending (see CI status under Wave 2).
- Started from commit: 24d8aca
- Goal: a clean, production-shaped monorepo with CI green: health endpoints, admin bootstrap, a bilingual placeholder page, and Docker images ready to deploy.

**Done**
- wave file completed with deliverables, tests, commit plan and verification checklist
- chore: scaffold monorepo layout, brand.json and pack READMEs
- feat(api): settings, health endpoints, user model, migration, production guard, CLIs (create-admin, seed-demo, migrate, check)
- feat(web): Vite app with tokens, i18n and the build-status screen
- test(web): key parity, token contrast, screen states, Playwright smoke and axe
- build: Dockerfiles, nginx, compose (dev and production), smoke script, Makefile
- ci: workflow (api, web, e2e, secrets, docker) and Dependabot
- docs: DESIGN, TRACEABILITY, SECURITY, RELEASE, CHANGELOG, ADR-015 and ADR-016
- pushed to origin/main at 7b16194

**Decisions**
- Compose project name and image labels are derived from `brand.json` by the Makefile, because CLAUDE.md forbids hard-coding the product name in config (the wave prompt said `sudarshan`).
- ADRs for this wave are 015 and 016: 011–013 are taken, 014 is reserved for wave 3 (placeholder in DECISIONS.md).
- Python 3.12 comes from `uv` (host has 3.10 only); `uv` installed from PyPI with `pip --user`.
- `users.is_demo` column added so the production guard can detect demo accounts.
- The container entrypoint runs `check` (guard), `migrate`, `create-admin --if-configured`, then serves, so production never migrates under a bad configuration.
- Language switch shows visible text "English" / "हिन्दी" (axe label-in-name rule rejected "EN" with a longer accessible name).
- Random secrets come from Python, not `openssl` (the host `openssl` is an Intel-only binary).
- Dev-only toolchain audit: `npm audit` reports 7 findings in the Tailwind 3 build chain; `npm audit --omit=dev` reports 0. Revisit with the Tailwind upgrade in wave 2.

**Tests**
- api: 36 passed · web: 25 passed · e2e: 8 passed (axe zero violations, EN/HI × dark/light, against the real nginx and Postgres stack) · coverage: 98% (gate 90%)
- Fresh clone: `make setup && make lint typecheck test` passes.

**Deploy check**
- Production images built: yes · `make prod-check` (production mode, throwaway project, admin bootstrap idempotent, seed-demo refused): pass · `make demo`, `make smoke`, `make e2e` on the demo stack: pass
- Commit to deploy: not applicable yet; nothing is hosted until wave 2. Latest verified commit: 7b16194 (docs-only commits may follow).

**Environment notes**
- Local web port: another project's containers hold 8080 on this machine, so `WEB_PORT=8081` is set in the git-ignored `.env`; `make smoke` and `make e2e` read it. Do not commit `.env`.
- Playwright's Chromium (about 99 MiB) was downloaded to the user cache (`~/Library/Caches/ms-playwright`) for tests only; it is not in the repo or the images.
- `gh` on this machine is an x86_64 binary and does not run (bad CPU type); `openssl` has the same problem. Secrets are generated with Python, and CI status must be read in the browser or with a working `gh`.

**UI review follow-ups** (from [evidence/wave-1/UI_REVIEW.md](evidence/wave-1/UI_REVIEW.md); heading hierarchy, Hindi label size and skeleton width are already fixed)
- Wave 2: self-host IBM Plex Sans, Plex Mono and Noto Sans Devanagari, with `tabular-nums` (findings 3, 6).
- Wave 2: give the canvas a real shell so the page is not 75% empty; replace the redundant Service and API status rows (1, 7).
- Wave 2: add the ring-and-bearing mark to the header as inline SVG; first Carbon icons in one weight (8, 9).
- Wave 2: error state names the failing endpoint and status (10).
- Repeat the review on wave 2 screens with the 12 visual snapshots.

**Hindi:** all Hindi strings are unreviewed; the sheet is [i18n/HI_REVIEW.md](i18n/HI_REVIEW.md) and Q-15 stays open.

**Open issues**
- Resolved: CI #14 is green; #13 did not pass and was superseded by #14. URL pending.
- Port 8080 on this machine is held by another project's containers (`sih-*`), which were left untouched; local runs use `WEB_PORT=8081` in the git-ignored `.env`.
- Playwright's Chromium (about 99 MiB) was downloaded with `npx playwright install`, a download beyond package registries that the wave's test requirement implies.
- Hindi strings are drafted by Claude Code and need a human reviewer (Q-15).

**Next wave entry point**
- Confirm CI green on `main`, set wave 1 to Done, then start wave 2 (design system and app shell): read docs/waves/wave-02-design-system-shell.md and begin with the self-hosted fonts and the component primitives.

### Wave 2 · Design system + app shell

- Status: In progress. All build steps are merged and verified locally; the milestone (a live link, an admin-created account signing in, `make smoke` and `make check-deploy` against it) needs the owner to deploy.
- Started from commit: aef6521
- Goal: the real design system, sign-in, role-based shell and bilingual UI, plus a deployment kit for an Azure for Students Linux VM, deployed as the first live link.

**Done**
- gate: wave 1 Done (owner-confirmed CI), Q-02 decided (Azure for Students, Linux VM)
- docs: wave 2 file completed
- feat(api): sessions, login, CSRF, rate limit, role guards, `create-user`, preferences, uploads directory
- feat(web): self-hosted fonts and UI primitives; routing, auth, role-based shell and screens
- test(web): component, auth, role, axe (EN/HI × dark/light) and visual tests; Hindi review sheet drift test
- build: Caddy HTTPS override, `deploy.sh`, `backup.sh`, `restore.sh`, uploads volume
- feat: `make check-deploy`, e2e seeding, `prod-check` extended (page load, bootstrap, cookies, CSRF, HTTPS, memory), `make backup-test`
- docs: DEPLOY runbook, FONTS, DESIGN, hosting options with measured memory, wave 2 UI review and screenshots

**Decisions**
- Host is Azure for Students, Ubuntu 24.04 LTS, x86_64 (owner decision, Q-02).
- Sessions are stored server-side with only the SHA-256 of the cookie token; `HttpOnly`, `SameSite=Lax`, `Secure` in production; CSRF token header on every unsafe request; failed-login limit (5 per 15 minutes per address and per account) held in process memory, so it applies per API instance.
- Production also refuses demo accounts at sign-in, not only at start-up.
- nginx passes the client address from Caddy's `X-Forwarded-For` and uvicorn trusts forwarded headers, because the API is reachable only through the web container; without this the login limit would key on the proxy and lock everyone out together.
- A separately hosted frontend on another registrable domain does not work with `SameSite=Lax` cookies; the supported deployment is one origin (documented in DEPLOY.md section 12).
- Sidebar modules come from one source list pinned to the UI map counts; modules not yet built route to an empty state naming their wave. Profile is built.
- The reduced-motion rule uses `transition: none`, not a tiny duration, because a 0.01 ms transition still let axe read a half-changed colour; the stored theme and language are applied by a static script before first paint.
- Visual snapshots have macOS baselines and run through `make visual`; the CI end-to-end job excludes them until Linux baselines exist. Signed-in e2e tests run one at a time because they share three seeded accounts.
- `seed-demo` accepts `DEMO_PASSWORD` (non-production only) so e2e can sign in; the password is generated per run by `infra/e2e.sh` and never stored.

**Tests**
- api: 61 passed, 99% coverage (gate 90%) · web unit: 77 passed · e2e: 45 passed (axe zero violations in EN and HI, dark and light, on sign in, About, Not found, Offline and, signed in as each role, Status, a module page, Profile (both tabs), No access and the components page) · visual: 3 tests (5 snapshots) passed
- `make lint typecheck test`, `make smoke`, `make check-deploy` (local), `make e2e`, `make visual`, `make prod-check` and `make backup-test` all pass; `make build-amd64` builds `amd64` images (about 1.5 minutes on this laptop).

**Measured memory (local, not an Azure figure)**
- Production stack idle 104 MiB, after light load 105 MiB, with Caddy 119 MiB (api 68, db 28, web 8, caddy 15). Detail and sizing advice in [HOSTING_OPTIONS.md](HOSTING_OPTIONS.md).

**Deploy check**
- Production images built: yes · `make prod-check` (production mode, HTTPS through Caddy on a local domain, HSTS and HTTP redirect, cookie flags, CSRF, admin bootstrap idempotent, seed-demo refused): pass · `make backup-test`: pass (a macOS-only pruning bug in `backup.sh` was found by the test and fixed)
- Not tested: the Azure steps, a real certificate from a public CA, an x86_64 run of the images, `deploy.sh update` and `rollback` (syntax-checked only; they need a git remote).
- Commit to deploy: the latest commit on `main` after this entry is pushed (record its hash here when you deploy).

**UI review follow-ups** (from [evidence/wave-2/UI_REVIEW.md](evidence/wave-2/UI_REVIEW.md))
- Sign-in page is sparse; top bar is busy and not responsive below about 1024 px; brand mark blurs at 24 px; Hindi body text may need 14 px after a native reader reviews it; error states do not name the failing request; Linux visual baselines for CI. Hindi stays unreviewed (Q-15).

**Environment notes**
- `WEB_PORT=8081` in the git-ignored `.env` on this machine (another project holds 8080). `make e2e` and `make visual` seed the three demo accounts in the local stack with a throwaway password.

**Hardening pass (after wave 2)**
- `create-admin` and `create-user` no longer accept `--password` (it would show in the process list and shell history); the password comes only from the environment or a hidden prompt, and is never echoed. Tests pin this.
- DEPLOY.md now states that images are built on the VM by default, adds the 2 GB swap step before the first build, documents building amd64 images on a Mac and loading them with `docker save` / `docker load` as the alternative (no registry), makes the DNS name label steps explicit, and adds a pre-deploy check that the name resolves and ports 80 and 443 are open. `deploy.sh up` warns when memory plus swap is under 3 GiB.

**Open verifications**
- **Update rehearsal: done on the real VM, 2026-10-18** (owner-reported; durations and any differences from DEPLOY.md were not supplied, add them here). **Rollback rehearsal: still open** (`deploy.sh rollback`, procedure in DEPLOY.md, "Rehearsal" steps 4 to 5); until it is run it is only syntax-checked.
- First real certificate from a public CA and a first run of the images on x86_64: not yet done (Azure steps untested).

**Follow-ups**
- Visual snapshot baselines exist for macOS only. CI excludes the `visual` project until Linux baselines are generated (run `make visual ARGS=--update-snapshots` in a Linux environment, commit `e2e/__screenshots__/linux/`, then add the project to the CI job).

**CI status**
- Owner-reported on 2026-10-18: CI #14 (Wave 1 state), #18 (Wave 2) and #24 (hardening) are green; #13 did not pass and was superseded by #14. Run URLs: pending, because `gh` cannot run on the build machine (wrong CPU architecture) and a run URL contains an ID that cannot be derived from the run number. To close: paste the three URLs from the GitHub Actions tab here.

**Live link (owner-reported, 2026-10-18)**
- URL https://sudarshan.centralindia.cloudapp.azure.com. The deployed commit and the smoke and check-deploy results were not supplied; they are recorded as pending under **Deployed build**.

**Open issues**
- The new CI steps (`make prod-check` pulling the Caddy image, `make backup-test`, e2e with seeded accounts) first ran in CI after wave 2; confirm they stay green.
- Owner to deploy; then record the live URL and commit here and run `make smoke URL=<live url>` and `make check-deploy URL=<live url>`.

**Next wave entry point**
- After the deploy is verified and recorded: wave 3 (contracts and deterministic sim core), read docs/waves/wave-03-contracts-sim-core.md and start with the Pydantic contracts.

### Wave 3 · Contracts + deterministic sim core

- Status: In progress. Every acceptance criterion is met and verified locally; set to Done once the owner confirms the CI run for the last wave 3 commit is green (CI cannot be read from this machine: `gh` is an x86_64 binary and the repository is private).
- Started from commit: 13ef48c
- Goal: versioned contracts and a deterministic, replayable simulation core that every later wave builds on.

**Done**
- 89d38a6 build: `WEB_PORT` comes from the environment or command line before `.env` (run the demo on a free port: `WEB_PORT=8090 make demo`)
- 13ef48c test(web): macOS visual baselines refreshed for the footer About link
- 87514e6 docs: start wave 3 in the build log
- ddaeffc docs: add F01 for project-authored fictional values to the data register
- dcbadab feat(api): versioned contracts with JSON Schema export and fictional example packs
- 1a7ed74 feat(sim): add the sim package with canonical JSON hashing
- 26b5ab3 chore: ignore local agent worktrees
- b02ca82 fix(api): keep pause and resume out of the action contract
- a5cfc81 feat(web): generate contract types from the JSON Schemas with a CI drift check (subagent, worktree)
- 9fe35d5 feat(sim): hash-chained event log with tamper detection (subagent, worktree)
- df3b038 feat(sim): deterministic maths, named RNG streams and waypoint kinematics
- 09c6ea0 feat(sim): fixed 20 Hz world tick, actions, snapshot/restore and replay
- b6d3a13 test(sim): golden files that pin sim behaviour with a readable diff
- 60b93de docs: add SIM_CORE with the tick model, RNG streams and determinism rules
- 37a5580 docs: record ADR-014 on the RNG scheme and tick model
- 61aae02 docs: changelog and traceability proofs for wave 3
- 191c16a fix(build): pass WEB_PORT to the demo stack only, not to prod-check

**Decisions**
- Pack files carry a `contract` field (`scenario.v1`, `rulepack.v1`, `sensor-profile.v1`) instead of `schema`, which would shadow a Pydantic method; the loader dispatches on it and refuses duplicate YAML and JSON keys.
- Register row F01 (project-authored fictional value, always `verified: false`) added so example packs and fictional effector figures cite something honest; a test checks every `source_id` in `packs/` exists in DATA_REGISTER.md.
- Scenario positions are local east-north-up metres on flat ground (no latitude and longitude), so no real-world location can be encoded.
- Pause and resume are not sim actions: a paused session stops ticking, so it cannot change a replay.
- Hashed state uses only correctly rounded IEEE operations: headings are unit vectors, sin and cos are polynomials, noise is a sum of uniforms. Reason: golden files written on macOS arm64 are checked on Linux x86_64 in CI (ADR-014, SIM_CORE.md).
- Added `session-record.v1` (inputs plus outputs of a session) as the replay format, beyond the four contracts the wave names.
- Example scenario routes were shortened so both contacts finish within the 420 s duration under the modelled headwind.
- `WEB_PORT` is passed to the demo stack's compose command only; exporting it overrode the throwaway prod-check and backup-test ports.

**Tests**
- api: 511 passed, coverage 98.6% (sim package 100%) · web unit: 83 passed · e2e: 45 passed · visual: 3 passed (5 macOS snapshots)
- Acceptance tests: identical hash after 10,000 ticks in two processes with different hash salts; replay reproduces every event and the final state; tampering detected at the edited event; examples validate and 43 malformed cases are refused (models and JSON Schemas); hypothesis keeps kinematics inside class limits (150 examples); restore at N and run to M equals a straight run (7 values of N); four physics constants each fail a golden file with a unified diff.

**Measurements (build laptop, Apple silicon, Python 3.12)**
- 10,000 ticks of the two-drone Kestrel scenario in 0.064 s (6.4 µs per tick); snapshot about 9.5 kB of JSON. API image 452 MB with numpy and PyYAML; production api container 68 MiB idle (numpy is not loaded by the API yet).

**Deploy check**
- Production images built: yes · `make prod-check` (production mode, HTTPS through Caddy, cookies, CSRF, bootstrap, memory): pass · `make backup-test`: pass · `make smoke` on the demo stack (port 8081): pass
- No user-facing change in this wave; the live build keeps working. Commit to deploy: the last wave 3 commit on `main` (record its hash in **Deployed build** when you redeploy, then run `make smoke URL=<live url>`).
- Secrets: gitleaks runs in CI only (not installed locally); no credentials were added, and `.env` stays untracked.

**Open issues**
- CI result for the wave 3 commits: owner to confirm (the CI jobs were all run locally and pass).

**Next wave entry point**
- After CI is confirmed green, set wave 3 to Done, then start wave 4a (sensor models): read docs/waves/wave-04a-sensor-models.md and begin STEP 1, the sensor framework in `services/api/sim/sensors/` (Sensor interface, degradation hooks, cue input), reading profiles through `app.contracts.loader` and drawing noise from the `sensors` RNG stream.

### Wave 4a · Sensor models

- Status: In progress. Steps 1 to 3 (framework and the four models) are merged and verified locally; step 4 (acceptance pass) remains.
- Started from commit: 5387056
- Goal: physically-motivated radar, EO/IR, RF and acoustic detection models with degradations, every parameter sourced from the data register.
- Gate note: the wave 4a prompt says to stop unless wave 3 is Done and main is green. Wave 3 is complete and green locally; the owner has not yet confirmed its CI run, and instructed this step to proceed. Set wave 3 to Done once CI is confirmed.

**Done**
- 6e4e382 feat(sim): deterministic exp, log, atan2 and angle wrapping (new `atan` too; all used by sensor geometry)
- 7ca58c3 feat(api): optional class confusion tables in the sensor profile contract (`sensor-profile.v1` schema and TypeScript regenerated)
- 418af43 feat(sim): sensor framework in `services/api/sim/sensors/` (Sensor template method, fixed draw budget, degradations, cueing, profile loader, suite and builder)
- edf5d23 docs: sensor framework in SIM_CORE, ADR-017, changelog, R10 proof and Q-19
- 902651c test(sim): cover atan for arguments beyond one
- 0d7c2c5 docs: record wave 2 live URL and start the wave 4a entry in the build log
- 2473b73 docs: record that the wave 2 live URL runs commit b722313
- Step 3, subagent B (worktree, Sonnet), merged at 573d9a8: 69a5b77 RF model, 1600458 acoustic model, 9f53b3b RF and acoustic profiles, fbd1c2e and ed6e9e2 their tests, 1ad9260 docs fragment
- Step 2, subagent A (worktree, Sonnet), merged at 4b38899: 036ca4c radar model, 0310d92 EO/IR model, 25e88fd radar and EO/IR profiles, a1d0ff7 and 7aa56ab their tests, 0e11a57 docs, 1e5ea01 profile file names
- aae206c test: one example per contract except sensor profiles; spare modality in the registry test
- 4e0b8d0 fix(packs): radar cross-sections cited F01 (not D14), EO/IR profiles named `<id>.v1.yaml`
- 5f7a3f0 fix(sim): false-alarm draws are taken during an outage; a zoom cue applies at once
- d2d1a91 feat(sim): the four models register on `sim.sensors` import
- docs commit after these: SENSOR_MODELS merged, Q-20, Q-21, ADR-018, SIM_CORE, changelog, traceability (R3, R10)

**Decisions** (full reasoning in [ADR-017](DECISIONS.md))
- Every candidate target takes a fixed 18 uniforms from the `sensors` stream whatever happens to it, so an outage, cue or probability change never shifts later noise.
- Confusion tables sit in the sensor profile as an optional `confusion` object (additive, still `sensor-profile.v1`) with one register ID and `verified` flag per table and rows that must sum to 1; flat numbered parameters would not fit the 64-parameter limit.
- Per-class signature figures (RCS, apparent size, and so on) are ordinary parameters named `<prefix>_<class_id>` with a `<prefix>_default` fallback (`SensorParams.for_class`). Steps 2 and 3 use this convention; do not invent another.
- Degradations are runtime data (`Degradation`), not a scenario field, so `scenario.v1` is unchanged; instructor injects arrive in wave 10b. The suite is not yet part of `World.state()`; waves 4b and 5 wire it in.
- Fictional fixed day length for EO/IR light: sunrise 06:00, sunset 18:00, one hour of linear twilight (no latitude is modelled).
- The profile loader checks source IDs against the register only when given one (CI test does); the production image has no `docs/` directory.
- Steps 2 and 3 must register their model with `register_model` and put the shared pieces (`polar_detection`, `report_class`, `degradation_effect`, `precision_factor`) to use rather than re-implement them.

**Tests**
- api: 904 passed, coverage 98.9% (sim package 100%) · web unit: 83 passed (includes the contract drift check) · e2e and visual: not run in this step (no web change beyond generated types)
- New: `tests/test_sensor_framework.py`, `tests/test_sensor_profile.py` (geometry, daylight, fixed draw budget, two-process determinism, coverage, outage and sector outage, effects, cueing and expiry, snapshot restore, suite and builder, provenance rejection, row-normalised confusion tables), plus `detmath` accuracy tests. No existing test was skipped, disabled or weakened.

**Deploy check**
- Production images built: yes · `make prod-check` (production mode, HTTPS through Caddy, cookies, CSRF, bootstrap, memory): pass. No API image change (`sim/` is not in the image, Q-19).
- Commit to deploy: not needed for this step (no user-facing change). Latest verified code commit: the last commit of this step on `main`.

**Open issues**
- CI result for the wave 3 and wave 4a step 1 commits: owner to confirm (all CI jobs except gitleaks, `docker build` on Linux and the Linux-only e2e were run locally).
- Smoke date for the live link: owner to record under **Deployed build** (the deployed commit, b722313, is recorded).
- Q-19: the API image does not ship `sim/` or `packs/`; fix in wave 5.
- Q-20: parameter sources with no register row (published RCS ranges, micro-Doppler frequencies, Johnson criteria, RF band plan and range table, acoustic ranges). The shipped profiles use F01 with `verified: false`; only the Johnson pixel thresholds and the thermal camera field and pixel count are `verified: true` (D12).
- Q-21: the profiles cover `rotary-small`, `fixed-wing-small`, `bird` (and `autonomous-small` for RF); wave 8 must extend every table with its new classes.
- Q-09 figures (thermal contrast, bird wing-beat band, RF and long-range acoustic ranges) remain UNVERIFIED and are labelled so in SENSOR_MODELS.md.

**Decisions in steps 2 and 3** (ADR-018)
- Closed-form, monotonic P(d) per model; RF-silent classes return exactly 0; radar micro-Doppler reuses the detect draw divided by P, so no extra draws.
- Radar RCS cited F01 (`verified: false`), not D14, because the values were not extracted from it (locked rule 1).
- Framework fixes during integration: the false-alarm hook runs during an outage (reports discarded) so the stream never shifts; `cue` applies a zoom immediately.
- `tests/test_contracts.py` still demands exactly one example per contract, except `sensor-profile.v1`, which now has one per model.
- EO/IR is one model class for `eo` and `ir`; day, night-vision and thermal are three profiles.

**Next wave entry point (superseded: steps 2 and 3 are done)**
- Historical: STEP 2 and STEP 3 could run as two subagents in separate worktrees (radar and EO/IR; RF and acoustic). Each adds `sim/sensors/<modality>.py` with a class registered by `register_model`, a profile in `packs/sensor-profiles/`, and tests. Read docs/SIM_CORE.md "Sensor framework" first; use `tests/sensor_toy.py` as the pattern for a minimal model. Cited values come from docs/02-research.md section 2 and docs/DATA_REGISTER.md; anything secondary or UNVERIFIED carries `verified: false`, and a parameter source not in the register goes to docs/OPEN_QUESTIONS.md instead of a made-up ID. Steps 2 and 3 should not both edit `sim/sensors/__init__.py` in conflicting ways: add the import of the model module there in the merge, not in the branch.

**Wave 4a, next entry point (current)**
- STEP 4: read docs/SENSOR_MODELS.md against the acceptance list; add any cross-model test still missing (for example one scenario run through all four models in a suite, twice, with identical output); record test counts and the deploy check here; then wave 4b (tracking, fusion and AI assist), starting with the tracker's input contract: `Detection.trainee_view()` from `SensorSuite.detect`, wiring the suite into `World` per SIM_CORE ("the suite is not yet part of `World.state()`").
