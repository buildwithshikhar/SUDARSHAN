# Build log

The resumable state of the build. After every `/clear`, Claude Code reads [CLAUDE.md](../CLAUDE.md), then this file, then the wave file named under **Current position**. If this file and the repo disagree, the repo (git history and CI) wins; fix this file first.

## Current position

- **Phase:** wave 8 built (threat breadth); every acceptance criterion has a passing test except the floor-laptop benchmark with the real swarm (the owner runs `/bench`; harness and protocol in [PERFORMANCE.md](PERFORMANCE.md)), the redeploy and the post-deploy check (map under the wave 8 entry). Wave 7's gate is pending for the same reason. CI for each pushed commit is read with `gh` (see **CI status**).
- **Current wave:** 8 · Threat breadth → [waves/wave-08-threat-breadth.md](waves/wave-08-threat-breadth.md) (built; gate pending)
- **Next step:** wave 9a (scenario engine), entry point under the wave 8 entry. Owner: run `/bench` on the floor laptop (waves 7 and 8 share the gate), redeploy, run the wave 5 to 8 post-deploy checks, answer Q-26, Q-27, Q-11 (download X01) and Q-29.
- **Main is:** see **CI status**; green locally (lint, typecheck, unit, real-stack e2e, visual, mock e2e, `make prod-check`).
- **Deployed build:** live at https://sudarshan.centralindia.cloudapp.azure.com, running commit b722313 (wave 2 build; owner-reported, 2026-10-18).

## CI status (confirmed with `gh`, 2026-10-19)

CI on `main` is read with `gh run list --repo buildwithshikhar/SUDARSHAN --branch main` and `gh run view <id> --log-failed`; it is no longer "owner to confirm".

| Waves | Runs | Result |
|---|---|---|
| 1, 2 | #1 to #26 | Green apart from cancelled early runs. Run #27 (b6d3a13, wave 3) failed only in the `docker` job (`make prod-check`); green from #32 (5387056, end of wave 3). |
| 3, 4a, 4b | #32 to #37 | Green (#37 is 1f65e46, the wave 4b acceptance). |
| 5, 6, 7 | #38 (e881ca0) to #44 (e1480d6) | **Red** on the `api` job: 10 failures in run #38 and 17 in run #44, all `AssertionError: no 'ended' message within 4000 messages` (tests/test_live_rest.py, tests/test_scoring_endpoint.py), plus `test_live_no_truth` failing on the same cause (its working actions reached a session that had already finished). Run #38 also had one `web` unit failure (workspace.test.tsx, load-sensitive, since made deterministic in 8fde989; `web` was green in #44). |

**Result:** run 39166665271 on 55b2b6b (the fixes, `make ci-api` and these notes): all six jobs green (api, web, e2e, docker, terrain, secrets). CI is green on `main` again after seven red runs.

**Wave 8:** run 39207730379 on 16f690f (wave 8 complete): all six jobs green (api, web, e2e, docker, terrain, secrets), read with `gh`.

**Cause of the red `api` job (run #38 and every run after it).** Not numerical: the scripted scenarios give identical state hashes (every 100th tick, 8,400 ticks, both packs) on macOS and on x86-64 Linux in this repo's compose project, so no detmath change or cross-platform golden test was needed. The cause was pacing. The tests run the live loop at 100x; the loop ran flat out and finished a whole 420 s scenario in seconds, while the test reader sat behind Starlette's in-process WebSocket, which buffers without limit (a real socket pushes back). On a slower reader (CI) the reader was thousands of frames behind, so the `ended` message was past the 4,000 messages the helper reads, or the working actions arrived after the session had ended. It passed on the build laptop only because the reader there kept up. Reproduced on x86-64 Linux with `make ci-api` (2 CPUs); the same files then passed 8 of 8 runs at 1 and 2 CPUs.

**Fix.** (1) `app/live/manager.py`: above real time (`speed > 1`, test-only) the loop waits for a client that falls behind instead of skipping frames; at 1x it still skips, as before. (2) `tests/live_support.py`: the test socket has flow control (a 50-frame window) so the queue the loop watches can fill. (3) `tests/test_live_pacing.py` proves a slow reader sees every tick and nothing is dropped. No test was skipped, loosened or given a bigger limit; the 4,000 limit stands. `make ci-api` runs the API tests on x86-64 Linux inside the compose project (`infra/docker-compose.ci.yml`).

**Cause of the failing `report.spec.ts` mock-e2e test** ("Escape cancels without filing…", failing since before wave 7). A bug in `src/ui/Dialog.tsx`, not in the test: closing a dialog from state calls `dialog.close()`, and the browser fires the `close` event a task later. If the same keys reopened the form before that event arrived, the late event called `onClose` and cleared the new state, so the form unmounted under the user (Playwright then saw the Skip details button detach until the timeout). Reproduced under CPU load, with logs showing the event arriving after the reopen. `Dialog` now ignores the event for its own close when the parent wants the dialog open; `tests/components.test.tsx` has a test that fails without the fix. The spec is unchanged.

**Found while checking, not fixed.** `e2e/mock/bench.spec.ts` ("runs against the real baked pack…") fails on the build laptop with and without these changes: a phase records no frames (`frames > 0` fails), most likely because software rendering of the full scene takes over a second a frame here and the runner drops frames over 1 s. It is not in CI (mock e2e is local only). Open question Q-28.

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
| 4a | [Sensor models](waves/wave-04a-sensor-models.md) | 3 | Opus | Keep live build green | Cut | Done (CI pending) |
| 4b | [Tracking, fusion + AI assist](waves/wave-04b-tracking-ai-assist.md) | 4a | Opus | Keep live build green | Cut | Done (CI pending) |
| 5 | [Live-session vertical slice](waves/wave-05-live-session-slice.md) | 2, 4b | Sonnet | Redeploy: playable slice | Cut | Done (CI pending) |
| 6 | [Scoring + debrief](waves/wave-06-scoring-debrief.md) | 5 | Sonnet | Redeploy | Cut | Done (CI pending) |
| 7 | [3D realism + terrain packs](waves/wave-07-3d-realism-terrain.md) | 5 | Sonnet (Opus if gate fails) | Keep live build green | Cut | In progress (built; floor-laptop gate and CI pending) |
| 8 | [Threat breadth](waves/wave-08-threat-breadth.md) | 4a, 7 | Sonnet | Keep live build green | Cut | In progress (built; floor-laptop benchmark, CI and redeploy pending) |
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

- Status: Done, CI pending. All four steps are merged; every acceptance criterion has a passing test (table under **Acceptance map**). The one thing outstanding is the owner's confirmation of the CI run for the last wave 4a commit (gitleaks and the Linux `docker build` run only in CI).
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
- 0bfb462 test(sim): run all four models together on the Kestrel scenario, twice, identically
- 4c81a23 test(sim): pin the wave 4a acceptance criteria across all six shipped sensor profiles (step 4: `test_sensor_acceptance.py`, 439 tests)
- docs commit after these: step 4 acceptance map, wave marked Done with CI pending

**Acceptance map** (step 4; `tests/test_sensor_acceptance.py` is the cross-model file, the others are the per-model files)
| Criterion | Proof |
|---|---|
| P(d) non-increasing in range, every sensor | `test_sensor_acceptance.py::test_pd_never_rises_with_range_for_every_sensor` (6 profiles × 4 classes × 3 light levels × 5 conditions); per model: `test_pd_never_rises_with_range` in the radar, EO/IR, RF and acoustic files |
| Weather and time of day shift P(d) as specified | `test_sensor_acceptance.py::test_no_weather_improves_on_clear_air_and_most_sensors_feel_some`, `::test_every_sensor_loses_something_to_at_least_one_modelled_condition`, `::test_night_never_helps_and_light_independent_sensors_do_not_care`; per model: `test_worse_visibility_never_helps`, `test_night_collapses_day_eo_helps_nv_partly_and_does_not_touch_thermal`, `test_rain_and_low_visibility_lower_pd_and_clear_air_is_best`, `test_weather_and_time_of_day_shift_pd_only_as_documented`, `test_wind_lowers_pd_and_raises_the_noise_monotonically` |
| Confusion matrices row-normalised | `test_sensor_acceptance.py::test_every_confusion_row_of_every_profile_sums_to_one` (tolerance 1e-9); contract refusal in `test_sensor_profile.py::test_malformed_confusion_tables_are_refused` |
| RF-silent targets never detected by RF | `test_sensor_rf.py::test_a_silent_class_has_zero_pd_at_every_range_and_under_every_condition`, `::test_a_silent_class_is_never_detected_even_when_every_roll_is_lucky`, `::test_a_silent_class_stays_unseen_with_a_receiver_that_hears_everything` |
| Deterministic for a seed | `test_sensor_models_together.py::test_a_scenario_run_through_all_models_repeats_exactly`; per model, `..._is_deterministic_for_a_seed_and_differs_between_seeds` and `..._identical_in_two_processes_with_different_hash_salts` |
| Cue narrows EO/IR field and improves precision, deterministically | `test_sensor_eoir.py::test_a_narrow_cue_narrows_the_field_and_improves_precision_and_range_deterministically` |
| Loader rejects parameters without a source, flags `verified: false` | `test_sensor_profile.py::test_a_parameter_without_complete_provenance_is_refused`, `::test_unverified_values_are_listed`; `test_sensor_acceptance.py::test_every_parameter_and_table_of_every_profile_cites_a_register_row`, `::test_only_values_with_a_stated_source_figure_are_marked_verified` |
| SENSOR_MODELS.md: equations, parameters with register IDs, honesty note | `test_sensor_acceptance.py::test_each_model_section_gives_equations_parameters_and_an_honesty_note`, `::test_every_profile_parameter_is_named_in_its_section`, `::test_every_register_id_a_profile_uses_appears_in_its_section`, `::test_every_register_id_the_document_cites_is_a_register_row`, `::test_the_thermal_honesty_note_says_it_is_not_radiometric` |
| Every feature has tests; none skipped or weakened | coverage 99.19% (every `sim/` module 100%); no existing test edited in step 4 (one new file) |
| Production images build; production-mode stack passes `make smoke` | `make prod-check` (runs `smoke.sh` against the production-mode stack): PASS, 2026-10-18 |
| CI green (lint, typecheck, unit, e2e, gitleaks, docker build); no secrets in git | lint, typecheck, unit, e2e, visual pass locally; gitleaks and Linux `docker build` run in CI only: **pending owner confirmation** |
| Deployed build still works | no API image or web change in wave 4a; commit to deploy is optional; `make smoke URL=<live url>` after the owner redeploys: **pending owner** |

**Step 4 result**
- Added `tests/test_sensor_acceptance.py` (439 tests, 1 new file) after finding the per-model files covered every criterion but not across all six profiles at once or the document against the profiles. No product code needed a fix: the new tests passed on the models as written. Two of my first assertions were wrong (an RF rain margin that ignored the documented "few thousandths", and an unlike-optics camera ranking already covered by the same-optics test) and were corrected in the tests, not in the models.
- Final run: `make lint typecheck test` pass (api 1,728 passed, coverage 99.19%; web unit 83 passed); `make e2e` 45 passed; `make visual` 3 passed (5 snapshots); `make prod-check` PASS (api 83 MiB, four containers 222 MiB).

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
- After steps 2 and 3: api 1,290 passed, coverage 99.2% (every sim module 100%), web unit 83 passed; `make lint typecheck test` green. New: `test_sensor_radar.py`, `test_sensor_eoir.py`, `test_sensor_rf.py`, `test_sensor_acoustic.py`, `test_sensor_models_together.py`. e2e and visual not run (no web change).
- Step 1 detail: `tests/test_sensor_framework.py`, `tests/test_sensor_profile.py` (geometry, daylight, fixed draw budget, two-process determinism, coverage, outage and sector outage, effects, cueing and expiry, snapshot restore, suite and builder, provenance rejection, row-normalised confusion tables), plus `detmath` accuracy tests. No existing test was skipped, disabled or weakened.

**Deploy check**
- Production images built: yes · `make prod-check` (production mode, HTTPS through Caddy, cookies, CSRF, bootstrap, memory): pass. No API image change (`sim/` is not in the image, Q-19).
- After steps 2 and 3: `make prod-check` pass again (it runs `smoke.sh` against the production-mode stack; api 68 MiB idle, 210 MiB for the four containers). Still no API image change.
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

**Next wave entry point (superseded: wave 4b is done)**
- Wave 4b (tracking, fusion and AI assist): read docs/waves/wave-04b-tracking-ai-assist.md and start with the tracker's input contract: `Detection.trainee_view()` from `SensorSuite.detect`, wiring the suite into `World` per SIM_CORE ("the suite is not yet part of `World.state()`"). Before any sensor figure is shown to a trainee, resolve Q-20 (register rows for the sensor sources).

### Wave 4b · Tracking, fusion + AI assist

- Status: Done, CI pending. All four steps are merged; every acceptance criterion has a passing test (table below). Outstanding: the owner's confirmation of the CI run for the last wave 4b commit (gitleaks and the Linux `docker build` run only in CI).
- Started from commit: b06c25e
- Goal: a tracker that fuses the four sensors, fails in the ways real trackers fail (swaps, splits, merges), supports sensor cueing, and a seeded simulated AI assist.
- Done by: main session (Opus-grade design, run on Sonnet 5.5) for the tracker, the picture and the world wiring; two Sonnet subagents in separate worktrees for the error policy, ledger, commands and cueing (A) and the AI assist (B); both merged by the main session.

**Done**
- f76447a feat(sim): `Detection.trainee_view()` carries `data_status`; the sensor template stamps it from the profile (Q-20 labelling)
- 890834b feat(sim): tracker: `Measurement.from_view` (tracker input contract), six-state Kalman filter, gated nearest-neighbour association by components, lifecycle, triangulation, ambiguity-policy hook; `Detection.sigma_radial_mps`
- 038e171 fix(sim): snapshot copies of track state; duplicate tracks by a statistical test; tracker core tests
- 124bb1d feat(api): `track-relabel|merge|split|drop` and `sensor-cue` in `action-record.v1` (schemas and web types regenerated)
- Step 3, subagent B (worktree, Sonnet), merged at c996910: 793c0d2 AI assist, e005eb7 its tests, 44ca92d docs fragment
- Step 2, subagent A (worktree, Sonnet), merged at 6488afd: ed41bcf error policy, 70634d5 truth ledger, 30096f1 commands, e385a86 cue-to-track, fddc651 / 1a697c6 / 850de09 / e07bcac tests, 5868ed0 docs fragment
- 66afc49 feat(sim): initiation-exclusion zone; bearing-only spawns wait for a partner; package exports; documented swap re-derived on the final tracker (seed 1014, tick 648)
- a1b536b feat(sim): `Picture` and its `World`/`replay` hooks; wiring tests
- Acceptance pass (2026-10-18): every criterion re-checked against a named, passing test (map below, no test missing); then `feat(sim)` session record `picture` flag and `feat(sim)` `ErrorModel.difficulty`
- 5e2373d, 115ac33 test(sim): tracker edge cases, documentation parity, triangulation limits; 538c812 docs: SENSOR_MODELS "Tracking", SIM_CORE, ADR-019, Q-20 update, Q-22, traceability, changelog

**Acceptance map**
| Criterion | Proof |
|---|---|
| Tracker: initiation, association under clutter, coasting through a short outage | `test_tracker_core.py::test_a_range_report_starts_a_tentative_track...`, `::test_association_under_clutter_keeps_the_real_track_on_the_real_target`, `::test_a_track_coasts_through_a_short_outage_and_resumes_with_the_same_id` |
| Seeded crossing gives a swap at a documented tick; a relabel restores the true identity in the log | Rig path: `test_tracking_ambiguity.py::test_the_documented_swap_is_found_at_the_same_tick_every_time` (seed 1014, ledger tick 648; policy swap at 624), `test_tracking_commands.py::test_exchanging_the_labels_of_the_documented_swap_restores_the_picture`. World path through the action log: `test_tracking_wiring.py::test_the_seeded_crossing_swaps_at_the_documented_tick` (seed 195, tick 624) and `::test_a_relabel_logged_as_an_action_restores_the_true_identity_in_the_log` (`ledger.restored` at tick 640) |
| Errors deterministic for a seed, never for well-separated targets | `test_tracking_ambiguity.py::test_the_swap_is_the_same_in_two_processes_with_different_hash_salts`, `::test_targets_that_stay_apart_never_err_whatever_the_seed` (300 seeds, zero swap, split or merge); `test_tracker_core.py::test_a_lone_target_never_gets_a_second_track_from_a_gate_edge_outlier` |
| AI assist empirical hit and false-alarm rates within a stated tolerance | `test_tracking_assist.py` (40,000 trials per rate, tolerance 5 standard errors; hit 0.9005 vs 0.90, false alarm 0.0804 vs 0.08) |
| SENSOR_MODELS.md tracking section | `docs/SENSOR_MODELS.md` "Tracking"; `test_tracking_docs.py` checks every tracker, error-model and assist parameter is documented with its default |
| No sensor figure shown unlabelled (Q-20) | `test_sensor_provenance.py`; `test_tracking_wiring.py::test_everything_a_trainee_is_shown_is_labelled_reference_data`, `::test_trainee_events_and_frames_carry_no_ground_truth` |
| Every feature has tests; none skipped or weakened | coverage 99.5% (every `sim/tracking/` module 100% in the full run); no existing test edited except the pins in subagent A's own new files, re-derived and explained under Decisions |
| Production images build; production-mode stack passes `make smoke` | `make prod-check`: PASS, 2026-10-18 (api 68 MiB idle, four containers 204 MiB) |
| CI green | lint, typecheck, unit pass locally; gitleaks and Linux `docker build` run in CI only: **pending owner confirmation** |
| Deployed build still works | no API image or web change (`sim/` is not in the image, Q-19; web gained only regenerated types); commit to deploy optional; `make smoke URL=<live url>` after a redeploy: **pending owner** |

**Decisions** (full reasoning in [ADR-019](DECISIONS.md))
- The tracker sees only `Detection.trainee_view()`; ground truth reaches the ledger by a report reference number and never flows back.
- Errors are cut from one `tracking` draw per report and can occur only in an ambiguous component (two tracks or two reports inside gates), so they are impossible for separated targets.
- Q-20 is handled by labelling, not by waiting for register rows: every trainee-visible detection, track and assist view carries `data_status: "reference"` while any profile value is `verified: false`. The rows themselves are still open (Q-20), as is the unverified tracker, error and assist parameter set (new Q-22).
- Found by testing: `Track.to_state` returned live lists (snapshots mutated); duplicate folding by a fixed 20 m let crossing targets fold, so it is now a statistical test on position and velocity; about 1 % of seeds split a lone drone on gate-edge noise, so an initiation-exclusion zone (2.5 times the gate around a live track) was added. Subagent A's pinned numbers (documented swap seed 47 tick 648, merge tick 467, "only seed 4 splits") were derived on the earlier tracker; they were re-derived on the final one (seed 1014, tick 648; merge tick 131; no split in 300 seeds), not loosened.
- The picture attaches to `World` optionally with a `picture` key in the state only when present, so no golden file changed. The AI assist uses keyed SHA-256 draws instead of a new RNG stream for the same reason.
- `ErrorModel.difficulty` (default 1.0, bit-identical to before) multiplies the three error probabilities; totals above 1 are shrunk in proportion. Documented in SENSOR_MODELS, F01, `verified: false`.
- Swaps are rare at default maxima (4 of 300 seeds on the documented crossing; 1 under the nominal policy). A scenario raises `swap_max` for more; a persistent swap is mostly undone by the filter's velocity memory (documented).

**Tests**
- Acceptance pass, final run: `make lint typecheck test` pass (api 2,019 passed, coverage 99.51%; web unit 83 passed); `make e2e` 45 passed; `make visual` 3 passed. New: `test_tracking_difficulty.py` (13), replay-flag tests in `test_tracking_wiring.py`, `picture` in `test_contracts.py`. One existing test edited: the pinned default `ErrorModel.to_state()` in `test_tracking_ambiguity.py` now includes `difficulty: 1.0` (additive; no expectation loosened).
- Before the pass: api 2,007 passed, coverage 99.5% (every `sim/` module 100%; the two `tracker.py` branches missed in the full run were covered afterwards by `test_tracker_edges.py`) · web unit: 83 passed (contract drift check included) · e2e and visual: not run (no web change beyond regenerated types)
- New: `test_sensor_provenance.py` (10), `test_tracker_core.py` (48), `test_tracker_edges.py` (10), `test_tracking_ambiguity.py` (26), `test_tracking_ledger.py` (32), `test_tracking_commands.py` (40), `test_tracking_cueing.py` (16), `test_tracking_assist.py` (65), `test_tracking_wiring.py` (17), `test_tracking_docs.py` (6), `test_contract_track_actions.py` (9).

**Deploy check**
- Production images built: yes · `make prod-check` (production mode, HTTPS through Caddy, runs `smoke.sh`): pass, 2026-10-18.
- Commit to deploy: not needed (no user-facing change; the API image does not contain `sim/`). Latest verified code commit: the last wave 4b commit on `main`.

**Open issues**
- CI result for the wave 3, 4a and 4b commits: owner to confirm.
- Smoke date for the live link: owner to record under **Deployed build**.
- Q-19: the API image does not ship `sim/` or `packs/`; wave 5 must fix it first (`Picture` and the profiles are now what the live session imports).
- Q-20 (register rows for sensor sources) and Q-22 (tracker, error and assist parameters are F01): figures stay labelled reference data.
- Closed in the acceptance pass: `session-record.v1` now has a `picture` flag (default false) set by `replay.run`, and `replay` reads it. Wave 5 creates live sessions with `picture=True`.

**Next wave entry point**
- Wave 5 (live-session slice): read docs/waves/wave-05-live-session-slice.md. First step: close Q-19 (copy `services/api/sim` and `packs/` into `infra/Dockerfile.api`, extend `make prod-check` to import `sim` and build a `Picture` for the example scenario), then the WebSocket protocol. Send a trainee only `picture.TRAINEE_EVENT_TYPES` and `Picture.trainee_frame()`; add the "no ground truth reaches a trainee socket" test against them.

### Wave 5 · Live-session vertical slice

- Status: Done, CI pending. Every acceptance criterion has a passing test or measurement (map below). Outstanding: the owner's confirmation of the CI run (gitleaks and the Linux `docker build` run only in CI), the redeploy, and the post-deploy check.
- Started from commit: 1f65e46
- Goal: one scripted scenario playable end to end in the browser, server-authoritative, on the live link.
- Done by: main session (sim, ROE, scenario, contracts, integration, e2e) and two Sonnet subagents in separate worktrees (A: server transport; B: workspace UI), both merged by the main session.

**Done**
- 7d48c6f build(api): `sim/` and `packs/` ship in the API image; `make prod-check` runs `sim-check` inside it (Q-19 closed)
- c80fffa feat(sim): operator actions on tracks, ROE engine, trainee allow-list, Harrier Field scenario, live protocol contracts, `docs/LIVE_SESSION.md`, ADR-020; tests `test_roe.py`, `test_world_operator.py`, `test_audience.py`, `test_harrier_scenario.py`
- Step 1, subagent A, merged at de13f03: live session manager, MessagePack wire format, REST and WebSocket endpoints, `training_sessions` table (migration 0003), nginx WebSocket upgrade, load harness (13 commits 56a954e..310a2bc)
- 8ed02d8 build(api): uvicorn `--ws-max-size 65536`
- Step 2, subagent B, merged at e1dfd44: protocol client, store, key flow, scripted mock session, EO view, radar PPI, track table, decision panel, lobby, workspace and ended screens, EN and HI strings, DESIGN.md "Workspace" (9 commits 420f6ce..7e1d3b1)
- bcc275a feat(api): the scenario list carries the briefing and rule pack; sensor status carries `pixels_h` (both asked for by B; the EO angular size no longer hard-codes 1920)
- Step 3 tests: real-stack e2e `e2e/live-session.spec.ts` (keyboard only: cue, relabel, classify, assess, a blocked response, end, log verified; axe in Hindi light; a stranger cannot open another account's session), lobby visual snapshots, a Kestrel socket test; docs (PERFORMANCE.md, SIM_CORE, TRACEABILITY, CHANGELOG, Q-23, Q-24)

**Acceptance map**
| Criterion | Proof |
|---|---|
| A trainee signs in, starts the scenario, detects, classifies, responds, finishes; the log verifies | `e2e/live-session.spec.ts` (real nginx, API and Postgres, keyboard only; reads `/sessions/{id}/log` and asserts `verified`); `test_live_socket.py` plays whole sessions |
| No ground truth reaches a trainee socket | `test_live_no_truth.py` (a whole session over a real socket, every frame scanned for drone IDs, `truth`, `disposition`, `true_class`, `ledger`, `threat.`), `test_audience.py`, `test_live_protocol.py` (every message validates against the Pydantic model and the JSON Schema) |
| Load test: 12 clients, 5 minutes, jitter and latency, no dropped session | Table below; `docs/PERFORMANCE.md` |
| The ROE validator blocks a forbidden response and shows rule text and version | `test_roe.py`, `test_world_operator.py`, e2e (verdict shows the rule title, `training-baseline 1.0.0` and the unmet condition), `e2e/mock/workspace.spec.ts` |
| A cue and a relabel from the UI appear in the event log and change the track table | `e2e/live-session.spec.ts` (table shows `ALPHA-1`; log holds `sensor.cue` and `track.relabel`) |
| Keyboard-operable and axe-clean | e2e keyboard run; axe on the populated workspace in English dark and Hindi light (real stack) and on the mock suite (EN/HI, dark/light) |
| EN and HI for every new string | `tests/live/i18nCoverage.test.ts` and the existing key-parity test; Hindi is an unreviewed draft (Q-15) |
| Every new screen has populated, empty, loading and error states | `tests/live/lobby.test.tsx`, `tests/live/workspace.test.tsx`, `e2e/mock/screens.spec.ts` |
| Reference data labelled (Q-20) | track table REF marker and legend, detail strip (`workspace.test.tsx`); `data_status` on every frame item (`test_live_protocol.py`) |
| Event log stored at session end, verified on read | `test_live_rest.py` (tamper detection at the edited sequence number, `?deep=1` replay) |
| Lint, typecheck, unit, e2e, visual, prod-check, smoke pass locally | Test counts below |
| After the user redeploys, an admin-created trainee can play on the live link | **Pending owner** (steps below) |

**Decisions** (ADR-020)
- Operators act on tracks, never drone IDs; the real drone is logged as `target` for scoring and stripped for trainees.
- ROE verdicts cite the permitting rule or the closest one (with what is missing) and always the pack version; no change to `rulepack.v1`. An effector mismatch counts double when picking the closest rule.
- The EO view is drawn from EO reports at the sensor's angular size, so there is no server-side entity list to leak.
- A disconnect pauses the session (no ticks) and a grace of 120 s abandons it; one API worker holds all running sessions.
- The world is built at first connect (lobby), not at first `start`, because the lobby frame needs the sensors; nothing has ticked, so the state is identical (subagent A).
- A WebSocket with no `Origin` header is accepted (a browser always sends one; the load client does not); cross-site and `null` origins are refused at the handshake. nginx now forwards `Host $http_host` so the check sees the port.
- Tuning the Harrier scenario: a first layout put the quadcopter's path through the bird flock and produced 91 identity swaps in 420 s; the flock was moved to the south-east, away from the approach.
- Test pins adjusted, additive only: `test_there_is_one_example_of_each_pack_contract` names the two scenario packs; the scenario-list key-set assertion gained `briefing` and `rule_pack`; two web tests that used the unbuilt Drills module as their placeholder now use Today (subagent B). Nothing was skipped, disabled or loosened.

**Tests**
- api: 2,186 passed, coverage 99.21% (about 150 new) · web unit: 281 passed (83 before) · e2e (real stack): 48 (45 before plus 3 live-session) · mock e2e: 40 · visual: 4 (two new lobby snapshots) · `make lint typecheck test` pass
- The first full e2e run failed once in the Hindi axe test's cleanup step (a UI language switch on the profile page never settled); the cleanup now resets preferences through the API, and the spec passed three times afterwards.

**Load test** (12 clients x 300 s, loopback, quiet build laptop, one API process; 2026-10-18)
- Sessions dropped 0 (12 of 12 verified); frame rate 20.0 Hz, 0 tick gaps (71,988 frames)
- Message latency (ping RTT): p50 3.1 ms, p95 14.3, p99 19.3, max 36.1
- Inter-frame arrival jitter (|dt - 50 ms|): p50 0.8 ms, p95 9.4, p99 19.5, max 163.2
- Server tick lateness: p50 0.7 ms, p95 3.9, p99 10.1, max 146.1; tick cost p50 0.7 ms, p99 2.6; lag drops 0; 25% of one core, 90 MB resident
- A first run during heavy parallel builds showed 24 lag drops (whole-process stalls of about 0.5 s) and is not quoted. Re-run on the LAN and the deployed host before quoting there.

**Deploy check**
- Production images built: yes · `make prod-check` (production mode, HTTPS through Caddy, now also `sim-check` in the API container): pass · `make smoke` on the demo stack (port 8081): pass
- Commit to deploy: the last commit on `main` after this entry (the hash is in the final report; record it under **Deployed build** when you redeploy). This build changes the web app, the API image (`sim/`, `packs/`, `msgpack`), nginx (WebSocket upgrade) and adds migration 0003, which the container entrypoint applies at start.
- Post-deploy check (owner): (1) create a trainee on the live host, for example `docker compose exec api python -m app.cli create-user --email <address> --role trainee` (the password comes from the prompt or `NEW_USER_PASSWORD`, never an argument); (2) sign in at https://sudarshan.centralindia.cloudapp.azure.com, open Drills, create a Harrier Field session, begin it, and confirm the status reads Connected and tracks appear; (3) `make smoke URL=https://sudarshan.centralindia.cloudapp.azure.com` and `make check-deploy URL=...`; (4) record the date under **Deployed build**. If the status stays "Connecting", the proxy in front of nginx is not passing WebSocket upgrades (Caddy does by default).

**Open issues**
- CI result for the wave 3, 4a, 4b and 5 commits: owner to confirm.
- Hindi strings are unreviewed drafts (Q-15); the review sheet was regenerated.
- Q-23: no wave owns the RF waterfall and acoustic spectrogram consoles; checkpoint A needs them. Q-24: Kestrel is also playable (radar only).
- The first-run load figures above are loopback only; LAN and deployed-host runs are still to do. Single worker only; more than one API worker needs session affinity.
- A trainee cannot yet use a commander-authority rule (class B response): team mode is wave 13a.
- `connect-src 'self'` in the nginx CSP should cover same-origin WebSockets in current browsers; older Safari may need an explicit `ws:`/`wss:` entry (untested).
- The workspace has no instructor navigation entry (instructors reach the lobby by URL); wave 10a adds the instructor flow.

**Next wave entry point**
- Wave 6 (scoring and debrief): read docs/waves/wave-06-scoring-debrief.md. First step: STEP 1, the evaluator in `services/api/app/scoring/`, walking each threat's Detect, Classify, Assess, Respond tree over the stored event log and ground truth. Its inputs already exist: `roe.verdict` and `action.*` (with `target`) for the operator's calls, `threat.spawn`, `ledger.*` and `assist.assess` for truth, `Threat.disposition` for what each contact really was, and `GET /api/v1/sessions/{id}/log` for the stored log. Replace the session ended screen's "Scoring and debrief are not part of this build" note with the debrief.

### Wave 6 · Scoring + debrief

- Status: Done, CI pending. Every acceptance criterion has a passing test (map below). Outstanding: the owner's confirmation of the CI run (gitleaks and the Linux `docker build` run only in CI), the redeploy, and the post-deploy check.
- Started from commit: e881ca0
- Goal: explainable decision-tree scoring for every threat and a debrief screen that says why.
- Done by: main session (evaluator, sim truth events, contracts, endpoint, integration, real-stack e2e) and two Sonnet subagents in separate worktrees (A: golden fixtures and property tests; B: debrief screen, report form, EN/HI templates). Both hit a session rate limit once and were resumed from their saved work.

**Done**
- 9bf2ad5 feat(api): evaluator `app/scoring/`, `score-result.v1`, pack `scoring` section, `ledger.first_report`, report truth, migration 0004, `GET /sessions/{id}/score`, `docs/SCORING.md`
- d23bc70 docs: Q-23 proposal (wave 8 owns the RF and acoustic consoles; nothing built)
- fa8d226 test(api): score endpoint, storage, re-scoring, ownership, migration 0004
- Step 2, subagent A, merged at 6692d2d: 37 hand-derived golden fixtures, properties, d′, report, track-error, unit and edge tests; two evaluator fixes (a rounding gap in a hard-fail cost; floating-point noise in report quality)
- 7143341 fix(scoring): from A's review: a breach earns nothing in Respond (`respond.breach`), a blocked attempt is costed once in contact-score units, lesson ties sort on rounded costs; seven goldens re-derived by hand
- Step 3, subagent B, merged at fa60f63: Debrief screen, contact-report form, `renderReason` with EN and HI templates for all 71 keys, mock score and Playwright mock specs
- fa60f63 `score-result.v1` gains `scenario_title` and `report_weight` (B's request; no second request in the debrief); `tests/test_scoring_keys.py`
- 75b40f8 real-stack debrief e2e, traceability proofs for R5, R6, R7, R17, changelog, README

**Acceptance map**
| Criterion | Proof |
|---|---|
| Golden fixtures (at least 10) cover each node outcome and each hard-fail case and give exactly the expected scores and explanations | `tests/test_scoring_golden.py`: 37 hand-derived cases in `tests/golden/scoring/` (expected values derived independently with exact fractions, then compared with the evaluator) |
| Rushing into an ROE breach never scores higher than a compliant slower response | `tests/test_scoring_properties.py::test_a_rushed_roe_breach_never_beats_a_slower_compliant_response` (hypothesis) and companions |
| d′ matches reference values, with the log-linear correction | `tests/test_scoring_sdt.py` (24) |
| A report with correct class, position in tolerance, count off by one, heading 40° out gets the documented marks; re-scoring is identical | `tests/test_scoring_report.py` (61), golden case 37 (the worked example in SCORING.md) |
| An unfixed seeded track swap lowers the affected threat's score; fixing it does not | `tests/test_scoring_track_errors.py` (real simulation, Kestrel seed 195, relabel at tick 640) |
| Debrief is axe-clean, bilingual, shows rule-pack version and seed | `e2e/debrief.spec.ts` (real stack: EN dark and HI light, axe, `training-baseline 1.0.0`, seed), `e2e/mock/debrief.spec.ts`, `e2e/mock/a11y.spec.ts` |
| Traceability proof cells for R5, R6, R7, R17 | `docs/TRACEABILITY.md` |
| Every new string in EN and HI; every new screen has the four states; keyboard; axe | `tests/test_scoring_keys.py`, `tests/live/scoringKeys.test.ts`, `tests/live/debrief.test.tsx` (loading, empty, 409, 404, network), `tests/live/reportForm.test.tsx`, `e2e/mock/report.spec.ts` |
| Production images build; production stack passes smoke | `make prod-check`: PASS; `make smoke` on the demo stack: PASS |
| CI green | lint, typecheck, unit, e2e, visual, mock e2e pass locally; gitleaks and the Linux `docker build` run only in CI: **pending owner confirmation** |
| Deployed build still works after the redeploy | **Pending owner** (steps below) |

**Decisions**
- The rule pack gained an optional `scoring` section and `thresholds.respond_within_s` with defaults, written out in the baseline pack, which stays at 1.0.0: no session has been stored against it in the field (waves 5 and 6 are not deployed) and a bump would churn about twenty existing assertions. From the first pilot session a pack content change bumps its version.
- New truth events and fields instead of re-simulating at scoring time: `ledger.first_report`, `target` on cue and verdict events, `truth` on a filed report. They are scoring-only and stripped for a trainee (`sim.audience`).
- A clutter or civil contact the operator never acted on is left out of the mean (`worked: false`); a hostile contact never worked scores 0. A breach scores 0 and its Respond node earns nothing. A blocked attempt is not a breach.
- The report is graded separately and combined by the pack's `weights.report`. The score is computed and stored when the session ends (0.2 ms for a full session) and recorded with the pack and scenario versions.
- Q-23 resolved on paper only: wave 8 (threat breadth) is proposed as the owner of the RF waterfall and acoustic spectrogram consoles, as a new first step (reasons in OPEN_QUESTIONS Q-23). No wave file was changed and nothing was built; the owner approves the move.
- Existing assertions edited, none loosened: the migration 0003 test now upgrades to 0003 rather than head; the socket payload tests gained report cases; B replaced the "scoring is not part of this build" assertion and fixed two waits on a stale transport.

**Tests**
- api: 2,485 passed, coverage 99.08% (about 300 new) · web unit: 324 passed (281 before) · e2e (real stack): 50 (48 before plus 2 debrief) · mock e2e: 67 · visual: 4 · `make lint typecheck test` pass
- Two existing tests are timing-sensitive under heavy parallel load and failed once in subagent A's loaded run, passing alone and in the quiet full run: `test_eventlog.py::test_property_round_trip_and_verify` (hypothesis deadline) and `test_load_smoke.py::test_the_load_harness_runs_and_reports`.

**Deploy check**
- Production images built: yes · `make prod-check` (production mode, HTTPS through Caddy, `sim-check` in the API container): pass · `make smoke` on the demo stack (port 8081): pass
- Commit to deploy: the last commit on `main` after this entry (the hash is in the final report; record it under **Deployed build** when you redeploy). The build adds migration 0004, which the container entrypoint applies at start, and the Debrief screen.
- Post-deploy check (owner): create a trainee on the live host (`docker compose ... exec api python -m app.cli create-user --email <address> --role trainee`, password from the prompt or `NEW_USER_PASSWORD`); sign in, play a Harrier Field session for a minute, file a contact report from the Respond step, end the session, open the debrief and check it shows the rule pack `training-baseline 1.0.0`, the seed and the first three lessons; then `make smoke URL=https://sudarshan.centralindia.cloudapp.azure.com` and `make check-deploy URL=...`, and record the date under **Deployed build**.

**Open issues**
- CI result for the wave 3, 4a, 4b, 5 and 6 commits: owner to confirm.
- Hindi strings (71 scoring messages and the debrief screen) are unreviewed drafts (Q-15); the review sheet was regenerated.
- Q-23: owner to approve moving the RF and acoustic consoles into wave 8 (proposal recorded; nothing built). Q-24 stands.
- Effector class IDs show raw (`ec-a`) in the debrief because the score carries no rule-pack labels.
- The score measures what was done against this scenario's fictional rules; it is not claimed as a validated measure of skill, and no timing standard has a public doctrinal source (Q-12).
- The two timing-sensitive tests above should get a longer hypothesis deadline or a looser bound if they flake in CI.

**Next wave entry point**
- Wave 7 (3D realism and terrain packs): read docs/waves/wave-07-3d-realism-terrain.md. First step: STEP 1, the terrain pipeline in `tools/terrain/` (an SRTM tile and an OSM extract that you download into `data/raw/`, which git ignores, baked to a heightmap mesh, building glTF and a pack manifest with attribution), then LOS occlusion in the sim core from the baked heightmap. This step needs the raw downloads and Q-04 (the floor laptop) for the benchmark gate: if the raw data is not in `data/raw/`, stop and ask for it. Wave 7 also needs your confirmation on Q-23 (consoles) before wave 8 starts.

### Wave 7 · 3D realism + terrain packs

- Status: In progress. Everything the build can prove has a passing test (map below), and CI is green on 16f690f. Outstanding: the owner's floor-laptop run of `/bench` (the gate), CI confirmation, the redeploy and the post-deploy check.
- Started from commit: 4dd9610
- Goal: a convincing offline 3D scene on real-shaped generic terrain that meets the benchmark gate on the floor laptop.
- Done by: main session (flaky tests, format, line of sight, contract, endpoint, scenario, bench, CI, docs) and two Sonnet subagents in separate worktrees (A: bake pipeline and packs; B: scene look, loader, quality tiers). B hit a session rate limit once and was resumed from its saved work.

**Done**
- 8fde989 test(api): the two load-sensitive tests are deterministic. The load harness has a frame-count mode (`--frames`) and its test asserts structure, not speed (timing arithmetic is checked on synthetic samples); Hypothesis has no per-example deadline. Each ran 5 times quiet and 5 times under 8 CPU burners, all green.
- bf59307 docs: [TERRAIN_PACKS.md](TERRAIN_PACKS.md), the binding pack format
- 232734b feat(sim): `sim/terrain.py` (ground, building raster, `blocked`), `scenario.v1` terrain union, radar and EO/IR occlusion after the draw
- 43055e1 feat(api): `GET /api/v1/terrain/{pack}/{file}`, briefing `terrain`
- Step 1, subagent A, merged at fb350d6: `tools/terrain` (own uv project, `make terrain`, `python -m terrain bake|scan|verify`), packs `heron-ridge` (rural, 1.9 MB, 41 buildings, 704 trees, 141 m relief) and `osprey-town` (urban, 2.6 MB, 1,125 buildings, 45 trees), reproducible byte for byte, attribution shipped
- 863b2ab feat(packs): datum is the lowest post (heights never negative), packs re-baked; scenario "Heron Ridge: low approach"; CI `terrain` job
- Step 2, subagent B, merged at 51c2d0c: terrain loader and `heightAt`, EO scene (terrain, buildings, trees with wind sway, sun, moon and stars, ACES, height fog, rain), thermal white-hot and black-hot and night-vision passes, reticle readouts, quality tiers with an fps probe, EN and HI strings
- 48be352 feat(web): `/bench` harness and JS budget script (`npm run bundle:check`, in CI); docs (ADR-021, traceability R9, R11, R14, performance protocol, Q-25 to Q-27)
- 47d0bac feat(api): `sim-check` loads the terrain pack of every pack scenario (so the production image proves it ships them)
- Fix found only on the real stack: the nginx CSP (`connect-src 'self'`) blocked the glTF loader's `blob:` texture fetch, so the terrain drew untextured; now `img-src 'self' data: blob:; connect-src 'self' blob:`, covered by `e2e/terrain.spec.ts` and by `make prod-check` (which also checks the pack files are served and need sign-in)

**Acceptance map**
| Criterion | Proof |
|---|---|
| Packs reproducible from the bake scripts; raw downloads outside git; attribution ships | `tools/terrain/tests` (69; two bakes byte-identical, hashes verified), `python -m terrain verify`, CI `terrain` job; `data/raw/` is git-ignored; `ATTRIBUTION.md` in each pack |
| LOS: a target behind terrain or a building is not detected | `tests/test_terrain_los.py` (29: ridge, building, roof, shipped packs, sensors, random streams unchanged), `tests/test_heron_ridge_scenario.py` (the village delays the hostile track from 31 s to 58 s) |
| JS bundle at most 1.5 MB gzipped (CI) | `npm run bundle:check` in CI: 319 kB total, 144 kB first load |
| First load at most 8 s from the local server | Not measured separately; the first-load JS is 144 kB and the scene chunk loads lazily with the session. To record with the floor laptop run. |
| Benchmark gate on the floor laptop | **Pending owner.** Harness: `/bench` (`tests/live/bench.test.ts`, `e2e/mock/bench.spec.ts` against the real baked pack). No figure is claimed. |
| EN and HI for every new string | `tests/i18n.test.ts` parity, `tests/live/i18nCoverage.test.ts`; HI review sheet regenerated (Q-15) |
| New screens: states, keyboard, axe | `/bench` (idle, loading, running, done, error; keyboard; axe en and hi) in `e2e/mock/bench.spec.ts`; EO controls in `e2e/mock/eo3d.spec.ts` |
| Tests for every feature; none weakened | API 2,535 passed (99.09% coverage); web unit 443 (324 before); tools 69; real-stack e2e 51 (50 before); mock e2e 77 of 78 (see below); visual 4. Assertions edited, none loosened: the briefing key set and scenario list gained `terrain` and the new scenario, one workspace test title was reworded by B with its assertions unchanged |
| Production images build; stack passes smoke | `make prod-check`: PASS; `make smoke` on the demo stack (port 8081): PASS |
| CI green | lint, typecheck, unit, real-stack e2e, visual pass locally; gitleaks and the Linux `docker build` run only in CI: **pending owner confirmation** |
| Deployed build still works after the redeploy | **Pending owner** (steps below) |

**Decisions**
- ADR-021 (datum at the lowest post, flat or pack terrain, line of sight after the draw, the serving contract and the gate definition).
- The pack scenario authors `z` as height above the datum, so "ground plus 12 m" is written as the sum; the contract does not know ground height (a later wave may add an AGL helper).
- Tests that exercise terrain build tiny synthetic packs, not the 4.5 MB shipped ones; two tests also load the shipped packs.
- The new scenario is checked for what it claims (the pack is on disk, sensors and flights sit above the ground, terrain delays the hostile track but it is tracked at about 1.2 km, outside twice the inner zone). It is **not** claimed "verified solvable" because no oracle-defender run was done; that belongs to wave 9a.
- Real coordinates appear only in `tools/terrain/areas.json` (Q-27); no pack file or screen names a place. The osprey-town centre sits 1.8 km east of the town centre because the SRTM tile starts at 74.0 E.

**Tests**
- api: 2,535 passed, coverage 99.09% · tools/terrain: 69 · web unit: 443 passed · real-stack e2e: 51 passed · mock e2e: 77 passed, 1 failed (`report.spec.ts` "Escape cancels without filing, and Skip details files a bare report": the Skip details button detaches and re-attaches until the 90 s timeout; it fails on 4dd9610, before this wave, as well as on every later commit, so it is not caused by wave 7, and it is not in CI, which runs the real stack only; cause not found, to fix at the next touch of the report dialog) · visual: 4 passed.

**Deploy check**
- Production images built: yes · `make prod-check` (production mode, HTTPS through Caddy; now also checks both packs are served to a signed-in user and refused to a signed-out one, the CSP allows `blob:`, and `sim-check` loads the pack of every pack scenario): **PASS** (222 MiB total in the memory table) · `make smoke` on the demo stack (port 8081): pass
- Commit to deploy: the last commit on `main` after this entry (the hash is in the final report). This build changes the web app, the API image (`sim/terrain.py`, `packs/terrain/` about 4.5 MB, `packs/scenarios/heron-ridge-low-approach`), and the nginx CSP (rebuild the web image). No migration.
- Post-deploy check (owner): (1) sign in as a trainee, open Drills, create a "Heron Ridge: low approach" session, begin it and confirm the status reads Connected, the EO view shows textured farmland with "Terrain: Heron Ridge · reference data", and tracks appear (the quad should appear late, behind the village); (2) open the browser console and confirm no Content Security Policy errors; (3) `make smoke URL=https://sudarshan.centralindia.cloudapp.azure.com` and `make check-deploy URL=...`; (4) record the date under **Deployed build**. The benchmark is separate: `/bench` exists only when the API reports demo mode, so the live production host does not serve it. On the floor laptop run `make demo` (or serve it from the instructor laptop on the LAN), sign in as a demo account, open `/bench`, and record the JSON in PERFORMANCE.md.

**Open issues**
- The benchmark gate has not been run on the floor laptop (Q-04). If it fails, stop and say so; the fix continues on Opus.
- CI result for the wave 3, 4a, 4b, 5, 6 and 7 commits: owner to confirm.
- Hindi strings (`/bench`, EO mode and graphics controls) are unreviewed drafts (Q-15).
- Q-25 (RF is not occluded), Q-26 (thin building coverage, default heights), Q-27 (coordinates in git), Q-06 (ODbL position recorded, owner to confirm), Q-23 still open.
- The thermal look has been judged on software rendering only; the white-hot ground can saturate under automatic gain on a flat scene. Revisit with real-GPU screenshots.
- The mock EO camera keeps its flat-ground position when a terrain pack is named in the dev-server mock, so mock screenshots of a pack put the camera under the ground; real sessions place sensors from the scenario.
- One pre-existing mock-e2e failure (above).

**Next wave entry point**
- First, the owner's benchmark and the Q-23 decision. Then wave 8 (threat breadth): read docs/waves/wave-08-threat-breadth.md. First step: STEP 1, the catalogue in `packs/threats/` (YAML per class with envelope and signature parameters, each with a register source ID; generic names only; clutter types). Wave 8 must re-run `/bench` with the real 24-drone swarm and 30 birds in place of the placeholder markers, and every class must instantiate in both terrain packs (`packs/terrain/heron-ridge` and `osprey-town`). If Q-23 is approved, the RF waterfall and acoustic spectrogram consoles are its new first step.

### Wave 8 · Threat breadth

- Status: In progress. Everything the build can prove has a passing test (map below). Outstanding: the owner's floor-laptop run of `/bench` with the real swarm, the redeploy and the post-deploy check.
- Started from commit: 9f89b42
- Goal: the full threat and clutter library, including swarms, decoys and RF-silent threats, at behaviour level only.
- Done by: main session (operator vocabulary and scoring, breadth scene, bench replay, integration, docs) and three Sonnet subagents in separate worktrees (W: RF and acoustic consoles; A: threat catalogue and sensor-profile extension; B: behaviours; W2: nine classes and instanced meshes). W and A hit a session rate limit once and were resumed from their saved work. At most two ran at once.

**Done**
- Step 0 (owner-approved change to the wave file, Q-23): RF spectrum and acoustic spectrogram consoles as tabs under the radar PPI, synthesised from sensor reports and labelled reference data; the RF console and the docs say RF is not occluded by terrain (Q-25); the EO terrain notice says building heights are generic defaults (Q-26). Subagent W, merged at 1476885.
- bb5ee76 fix(web): the benchmark counts slow frames and leaves out only paused intervals (Q-28 root cause: a frame over one second was dropped, so software rendering recorded none; the spec passes)
- Step 1, subagent A, merged at c95ba60: `threat-class.v1`, eleven classes in `packs/threats/`, `sim/catalogue.py`, all six sensor profiles extended (Q-21 closed), `docs/THREAT_CATALOGUE.md` with generated tables
- d603b08 feat(sim): nine operator classes (recognition classes), scoring, report truth and assist use them; kite and balloon are non-threats for the assist
- Step 2, subagent B, merged at fc274b3: `groups` and `Threat.motion` in `scenario.v1`, `sim/behaviours/`, `step_steered`, `GroupLayer` in the world, events `group.*` (ground truth)
- Subagent W2, merged at ad1d8f6: labels for the new classes (EN, HI), instanced meshes, the mock session with nine classes
- 8e3040f feat(sim): the breadth scene (24 swarm, 30 flock, 2 kites, 1 balloon, six sensors) and its recorded trajectory; `/bench` replays the real behaviours
- docs: SIM_CORE and DESIGN sections, ADR-022 and ADR-023, traceability R1 and R12, changelog, PERFORMANCE, Q-11, Q-21, Q-22, Q-23, Q-25, Q-28, Q-29

**Acceptance map**
| Criterion | Proof |
|---|---|
| No guidance, targeting or terminal-attack logic anywhere; code review note (locked rule 2) | **Code review note.** I read the whole `sim/behaviours/` package (1,341 lines) and the group part of `sim/world.py` and `sim/kinematics.py`: a member's inputs are its group's authored route, the guide that flies it and its group-mates' positions and headings; nothing takes or reads an asset, zone, sensor, operator, tracker or rule pack; saturation is parallel lanes along a route and ends like any route (loiter, loop or despawn); probe is out-and-back along the group's own final leg; there is no pursuit, aiming, closing-rate or terminal-phase code. The catalogue holds envelopes and sensor signatures only. `tests/test_behaviours_rule2.py` reads the sources and fails on the forbidden words, on imports that could supply a destination and on arguments that name one. The contract has no field that could carry a destination other than the group's own route (and a tether anchor). |
| Every class instantiates in both terrain packs | `tests/test_catalogue_flights.py` (11 classes × 2 packs: spawns, flies 600 ticks inside its envelope, identical state hash twice) and `tests/test_breadth_scene.py` (swarm, flock, kites, balloon with six sensors on both packs) |
| Swarm determinism and cohesion-metric tests; removing a leader changes behaviour as specified | `tests/test_behaviours_world.py` (hash twice, two processes with different hash salts, mid-run snapshot, replay; polarisation and radius of gyration sweeps over discipline and link loss; leader removal per `leader_loss` mode with hold, election and event ticks; a leaderless group unaffected), `test_behaviours_units.py`, `test_group_contract.py` |
| Benchmark scene with the real 24-drone swarm and 30 birds still meets the gate | Harness runs on the real recorded behaviours (`tests/live/bench.test.ts`, `e2e/mock/bench.spec.ts`, `test_breadth_scene.py` checks the trajectory file). **Gate not run: pending owner** (floor laptop). No figure is claimed. |
| `docs/THREAT_CATALOGUE.md` lists every class and clutter type with parameters and register IDs | Generated block checked by `test_threat_catalogue.py` |
| Every new string in EN and HI | `tests/i18n.test.ts`, `tests/live/i18nCoverage.test.ts`; Hindi unreviewed (Q-15), sheet regenerated (821 strings) |
| New screens: four states, keyboard, axe | Consoles: `e2e/mock/consoles.spec.ts` (7: placement, keyboard tabs, honesty text, cursor keys, 1366×768, Hindi, axe en/hi × dark/light), `tests/live/sensorConsoles.test.tsx`; classes: `e2e/mock/classes.spec.ts` (16) |
| CI green, tests for every feature, none weakened | Tests below; see **CI status** for the pushed run |
| Production images build; stack passes `make smoke` | `make prod-check` (see Deploy check) |

**Decisions** (ADR-022, ADR-023)
- Eleven truth classes, nine recognition classes; the first four keep their key positions. Sensor labels are coarse look-alike families (radar cannot tell an FPV from a quadcopter).
- Profile versions were not bumped (additive rows, nothing stored in the field); from the first pilot session a content change bumps the version. The sensor profile parameter limit is 128.
- All envelope and signature values are F01 `verified: false`; X01 was not downloaded (no network beyond registries), Q-11 stays open. The trainee sees them as reference data (Q-20).
- Existing assertions edited, none loosened: `test_non_threat_set_is_the_bird_only_for_now` became the three-class set; three sensor tests that called an unlisted class "kite" now use "unlisted-class"; the sensor acoustic test's label assertions grew with the labels; the old placeholder-scene bench tests were replaced by tests of the recorded scene (the placeholder no longer exists); `decision.test.ts` "ignores a digit beyond the options" now tests Assess (Classify has nine options).
- The console tables precede the track table in the page, so `beginSession` in the mock e2e uses a `trackRows(page)` helper.

**Tests**
- api: 3,705 passed, coverage 99.24% (every `sim/` module 100%) · web unit: 544 passed (443 before wave 8) · real-stack e2e: 51 passed · mock e2e: 101 passed (includes `report.spec.ts` and `bench.spec.ts`, both failing before) · visual: 4 passed · `make lint typecheck test` pass

**Open issues**
- The benchmark gate (waves 7 and 8) has not been run on the floor laptop (Q-04). If it fails, stop and say so; the fix continues on Opus.
- Hindi strings are unreviewed drafts (Q-15). Q-11 (X01), Q-26, Q-27, Q-29 are open.
- The follower's link range must cover the formation or the follower falls back to flocking; the scenario generator (9a) must set it. Stigmergy is not implemented.
- The 12-client load test was not re-run with a swarm scenario. No shipped scenario uses groups yet: the swarm exists in the engine, the tests and `/bench`; wave 9a generates scenarios with it.
- The RF and acoustic consoles are synthesised from reports (the server sends no spectra); the mock acoustic sensor's range (330 m) is mock data.

**Next wave entry point**
- Wave 9a (scenario engine): read docs/waves/wave-09a-scenario-engine.md. First step: the scenario generator's feature space and sampler, using `sim/behaviours/arrival.py` (`arrival_offsets`, `compose_members`, `formation_starts`) and `Catalogue.limits_for` for member limits, and `Catalogue.check_scenario` as a hard constraint; solvability by an oracle-defender run comes next. Set each group's `link_range_m` to cover its formation.

**Deploy check**
- Production images built: yes · `make prod-check` (production mode, HTTPS through Caddy, `sim-check` inside the API image now also loads the threat catalogue and checks every pack scenario): **PASS** (285 MiB for four containers; the API container read 145 MiB right after `sim-check`, 68 MiB idle in wave 4b) · `make smoke` runs inside it.
- Commit to deploy: the last commit on `main` after this entry (the hash is in the final report). This build changes the web app (consoles, meshes, nine classes, `/scenes/` data file), the API image (`packs/threats/`, `sim/catalogue.py`, `sim/behaviours/`, `sim/breadth.py`, extended sensor profiles) and `scenario.v1` (additive). No migration.
- Post-deploy check (owner): sign in as a trainee, open Drills, start Harrier Field, confirm Connected, the radar PPI with the RF and acoustic tabs below it (the RF tab reads "Synthesised from sensor reports · reference data" and the not-occluded note), and the Classify list shows nine classes; then `make smoke URL=https://sudarshan.centralindia.cloudapp.azure.com` and `make check-deploy URL=...`; record the date under **Deployed build**. Benchmark: on the floor laptop run `make demo`, open `/bench`, run, and paste the JSON into PERFORMANCE.md.
