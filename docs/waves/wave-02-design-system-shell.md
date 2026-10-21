# Wave 2 · Design system + app shell

> **PRIORITY MILESTONE: first deployable slice.** This wave produces the first live link of the platform, the next SIH milestone. Nothing in wave 3 starts until the live link is verified and recorded in [BUILD_LOG.md](../BUILD_LOG.md).

| | |
|---|---|
| Depends on | 1 |
| Deployment | **PRIORITY MILESTONE: first live link.** The user deploys this wave; it must be live before wave 3 starts. |

**Goal.** The real design system, sign-in, role-based shell and bilingual UI, deployed as the first live link.

## Scope

- Design tokens complete; IBM Plex Sans, IBM Plex Mono and Noto Sans Devanagari self-hosted (OFL); IBM Carbon icons only.
- Base components: button, input, select, checkbox, table (compact and comfortable), panel, tabs, dialog, badge, inline alert, empty/loading/error states, tooltip.
- Auth: sign in and out, secure session cookie, argon2, rate-limited login; RBAC for trainee, instructor and admin with route guards on web and API.
- App shell with the role-based sidebar groups from `docs/07-ui-map.md`; modules not built yet show an honest empty state naming the wave that delivers them.
- Shared screens: Sign in, About and data notice, Not found, No access, Offline or server unreachable.
- Theme switch (dark default, light) and language switch (EN/HI), both persisted per user.
- `create-user` CLI so the admin can create instructor and trainee accounts in production.
- Deployment kit for the chosen host (Azure for Students Linux VM): `docs/DEPLOY.md`, HTTPS override, deploy, backup and restore scripts, `make smoke URL=...` and `make check-deploy URL=...` against a remote URL.

## Out of scope

- Any simulation, scoring or session feature.

## Files to read

`CONTRIBUTING.md`, `docs/BUILD_LOG.md`, this file, `docs/evidence/wave-1/UI_REVIEW.md`, `docs/HOSTING_OPTIONS.md`, `docs/OPEN_QUESTIONS.md`, `docs/07-ui-map.md` (design system, sidebar, screens), `docs/DESIGN.md`, `docs/DECISIONS.md` ADR-005 and ADR-006. Nothing else.

## Decisions already made

- **Host:** Azure for Students, Linux VM, Ubuntu 24.04 LTS, x86_64 (Q-02, owner). The kit assumes a plain VM with Docker; no provider SDKs, CLIs or credentials.
- **Hindi** remains unreviewed (Q-15). No string, doc or screen may call it verified or reviewed.

## Deliverables

**A. Design system and UI follow-ups (from the wave 1 review)**
- Self-hosted IBM Plex Sans, IBM Plex Mono and Noto Sans Devanagari (OFL), bundled by the build with their licence texts kept in the repo; `docs/FONTS.md` records sources, versions and licences. No font CDN.
- Tabular numerals on all data (Plex Mono for values, `tabular-nums` app-wide).
- IBM Carbon icons only, 16 and 20 px, used where they carry meaning (navigation, alerts), not on every button.
- Components: Button, Input, Select, Checkbox, Table (28 and 36 px rows), Panel, Tabs, Dialog, Badge, InlineAlert, Tooltip, EmptyState, LoadingState, ErrorState, plus a `/dev/components` route that exists only in demo mode.
- A header mark driven by `brand.json` (monogram of the product name in a ring-and-bearing frame), the redundant "Service" row removed, and a rebalanced layout: top bar, sidebar, page header, content grid and status strip, so no screen is a small panel in an empty canvas.
- Real content on the first screen after sign-in ("Status": build panel, session panel, and a table of the role's modules with the wave that delivers each).

**B. Auth and RBAC**
- Login, logout and `me` endpoints; argon2; server-side sessions in the database with a random id (only its hash stored), `HttpOnly` `SameSite=Lax` cookie (`Secure` in production), CSRF token required on every unsafe request, in-process login rate limit (5 failures per 15 minutes per address and account) with a uniform error and constant-time verification for unknown users.
- Role dependency for API routes; `GET /api/v1/users` (admin) as the first real guarded route.
- Per-user language and theme stored on the account and applied after sign-in.
- `create-user` CLI (email, role, password from prompt or env; refuses weak passwords) and the same password rules for `create-admin`.

**C. Shell and screens**
- Role-based sidebar from one source list (`apps/web/src/nav/modules.ts`) matching `docs/07-ui-map.md`: trainee 3 groups and 6 modules, instructor 4 and 10, admin 3 and 8, plus a shared Account group. A unit test pins these counts. Unbuilt modules show an EmptyState naming the arriving wave.
- Screens: Sign in, Status, Profile and preferences, About and data notice, Not found, No access, Offline or server unreachable. Route guards on the web mirror the API.

**D. Deployment kit for an Azure for Students Linux VM**
- `infra/docker-compose.https.yml`: Caddy with automatic HTTPS, configured only by `DOMAIN` and `ACME_EMAIL`; works with the VM's Azure DNS name when there is no domain of one's own.
- Production compose with persistent volumes for the database and uploads; production mode still refuses demo accounts; credentials only from env vars or the `create-admin` CLI.
- `infra/deploy.sh` (init, up, update, rollback, status, logs, create-admin, backup, restore) and `infra/backup.sh` / `infra/restore.sh`, with a local backup-and-restore test.
- linux/amd64 image builds documented for an ARM Mac.
- `make check-deploy URL=...`: healthz, readyz, version and one page load against a deployed URL.
- `docs/DEPLOY.md`: a first-time-user runbook covering the Azure portal steps (create the VM, open ports 22, 80 and 443 in the network security group, SSH keys, deallocate when idle, budget alerts), server setup, first deploy, update, rollback, the health checks, and what to change when a domain is added.
- Memory of the production stack measured under `make prod-check` and recorded in `docs/HOSTING_OPTIONS.md` as a local measurement.
- Nothing is deployed, no Azure endpoint is contacted and no credential or key enters the repo.

## Tests

- **Unit (api):** login success and failure, uniform error, rate limit, session expiry and revocation, CSRF rejection, role guards for all three roles on every guarded route, preferences, password rules, `create-user`, uploads directory, migration up and down. Coverage ≥ 90%.
- **Unit (web, Vitest):** every component (rendering, keyboard behaviour, ARIA), auth flows with a mocked API, route guards, module counts from the source list, EN/HI key parity, token contrast, the Hindi review sheet is up to date.
- **Integration:** the API against Postgres in the compose CI job; backup and restore round trip.
- **End to end (Playwright):** sign in and out for each role, role-based routes, theme and language persistence, offline screen, keyboard-only navigation of the shell.
- **Accessibility:** axe with zero violations in English and Hindi, dark and light, on sign-in, About, Not found, Offline, and (signed in) Status, a module empty state, Profile and No access for each role.
- **Visual:** committed snapshots for sign-in, shell and About, run with `make visual` (macOS baselines; the CI end-to-end job excludes them until Linux baselines exist, logged as a follow-up).
- **Determinism:** not applicable; there is no simulation yet.

## Docs and log updates

`docs/FONTS.md`, `docs/DEPLOY.md`, `docs/DESIGN.md` (fonts, icons, shell), `docs/HOSTING_OPTIONS.md` (measured memory), `docs/TRACEABILITY.md` (R13 and R14 notes only if proof exists), `docs/i18n/HI_REVIEW.md` regenerated and still unreviewed, `.env.example`, `CHANGELOG.md`, `docs/evidence/wave-2/` (four screenshots and an honest `UI_REVIEW.md`), and the Wave 2 entry in `docs/BUILD_LOG.md` after every merged step.

## Commit plan

1. `docs: complete wave 2 file`
2. `feat(api): add sessions, login, CSRF, rate limit and role guards`
3. `feat(api): add create-user CLI, preferences and uploads directory`
4. `feat(web): self-host fonts and add UI primitives`
5. `feat(web): add routing, auth, role-based shell and screens`
6. `test(web): add component, auth, axe and visual tests`
7. `build: add HTTPS override, deploy, backup and restore scripts`
8. `feat: add check-deploy target and memory measurement to prod-check`
9. `docs: add DEPLOY, FONTS, evidence and hosting measurements`
10. `docs: log wave 2`

## Model and effort

If about 60% of the session is used before acceptance, stop at the next green commit and log the remainder as wave 2.2; the natural split is (2a) auth, design system, shell and screens, (2b) the deployment kit and measurement.

## Stop conditions

The prompt's list, plus: stop at the deploy step and ask the owner to deploy; stop if any step would contact Azure or any other provider.

## Verification checklist

1. `make lint typecheck test` exits 0; API coverage ≥ 90%.
2. `make demo`, then open the stack and sign in with a printed demo account as each role; the sidebar matches the role and unbuilt modules name their wave.
3. `make e2e` reports zero axe violations in EN/HI × dark/light; `make visual` passes.
4. `make smoke` and `make prod-check` pass; prod-check output includes the memory table and a passing HTTPS check on a local domain.
5. `make check-deploy URL=http://localhost:<port>` passes against a running stack.
6. `infra/backup-test.sh` (or `make backup-test`) restores a marker user and file after a destructive change.
7. `git grep -n -i "<product name>"` outside `brand.json`, docs and the README finds nothing in `apps`, `services`, `infra`, `Makefile`, `.github`.
8. No credentials in git history; `.env` files ignored; `gitleaks` in CI.
9. Screenshots in `docs/evidence/wave-2/` match the final build and the review is honest about what is still weak.
10. The wave does not mark the milestone met: the owner deploys, then `make smoke URL=<live url>` and `make check-deploy URL=<live url>` run and are recorded.

## Acceptance criteria

- Token contrast unit test passes for every text/background pair at WCAG AA in both themes.
- Fonts are self-hosted with licences recorded in `docs/FONTS.md`; the wave 1 review follow-ups are addressed and `docs/evidence/wave-2/` holds four screenshots and an honest review (screenshot check).
- `infra/backup-test.sh` shows a database and uploads restore round trip; `make prod-check` prints the measured memory and passes an HTTPS check on a local domain.
- Playwright: sign-in, shell for each role, About, Not found, No access and Offline are axe-clean in both themes and both languages; visual snapshots committed for sign-in, shell and About.
- RBAC tests: each role sees only its routes and API endpoints.
- Production mode refuses demo accounts; the first admin comes only from env vars or `create-admin`.
- `docs/DEPLOY.md` covers host requirements (Docker, persistent storage), env vars, `VITE_API_URL` and `CORS_ORIGINS` for a split frontend, first admin, backups, rollback and the `/healthz` check.
- **Milestone:** the user has deployed this commit, the live link shows the sign-in page, an admin-created account can sign in, and `make smoke URL=<live url>` passes. Record the URL and commit in the build log.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.

## Brief

````text
ROLE: Build wave 2 (Design system + app shell) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). Follow the project rules in CONTRIBUTING.md, above all the content rules.

READ FIRST: docs/BUILD_LOG.md (confirm wave 1 is Done and main is green; if not, stop and tell me). Then: docs/07-ui-map.md (design system, sidebar and screens) and docs/DECISIONS.md ADR-005 and ADR-006.

GOAL: The real design system, sign-in, role-based shell and bilingual UI, deployed as the first live link.

STEP 1 — Design system (track A, worktree)
- Complete the tokens in docs/07-ui-map.md as CSS variables and a Tailwind theme; remove any default Tailwind palette from use.
- Self-host IBM Plex Sans, IBM Plex Mono and Noto Sans Devanagari (OFL; keep the licence files). tabular-nums for all numbers.
- IBM Carbon icons (Apache-2.0) only, 16 and 20 px.
- Components: button, input, select, checkbox, table (28/36 px rows), panel, tabs, dialog, badge, inline alert, tooltip, and EmptyState / LoadingState / ErrorState. Storybook is not needed; a /dev/components route in demo mode only is enough.
- Token contrast unit test (WCAG AA, both themes).

STEP 2 — Auth and RBAC (track B, worktree)
- Login endpoint with argon2, secure HttpOnly SameSite session cookie, CSRF protection, login rate limit, logout.
- Role guard dependency for API routes; tests per role.
- create-user CLI (email, role; password from prompt or env; refuses weak passwords).

STEP 3 — Shell (main track, after A and B merge)
- Role-based sidebar with the groups and modules from docs/07-ui-map.md. Unbuilt modules route to an EmptyState: "Arrives in wave N" (translated).
- Screens: Sign in, About and data notice (honest-data statement, defensive-only scope, no-affiliation line), Not found, No access, Offline.
- Theme and language switches persisted per user; all strings in EN and HI.
- Playwright + axe on every route, both themes, both languages; visual snapshots for sign-in, shell and About.

STEP 4 — Deployment kit
- docs/DEPLOY.md as described in the acceptance criteria. No provider credentials, no provider tokens.
- make smoke accepts URL=. Production compose keeps the DB on a persistent volume.
- If docs/OPEN_QUESTIONS.md shows a chosen host, add its config file; otherwise keep the kit host-neutral and say so.
- Then stop and ask me to deploy. When I give you the live URL, run make smoke against it and record the result.

OUT OF SCOPE (do not build):
- Any simulation, scoring or session feature.

ACCEPTANCE (all must be true):
- Token contrast unit test passes for every text/background pair at WCAG AA in both themes.
- Playwright: sign-in, shell for each role, About, Not found, No access and Offline are axe-clean in both themes and both languages; visual snapshots committed for sign-in, shell and About.
- RBAC tests: each role sees only its routes and API endpoints.
- Production mode refuses demo accounts; the first admin comes only from env vars or `create-admin`.
- `docs/DEPLOY.md` covers host requirements (Docker, persistent storage), env vars, `VITE_API_URL` and `CORS_ORIGINS` for a split frontend, first admin, backups, rollback and the `/healthz` check.
- **Milestone:** the user has deployed this commit, the live link shows the sign-in page, an admin-created account can sign in, and `make smoke URL=<live url>` passes. Record the URL and commit in the build log.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 2" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 3.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 2.2, stop);
- the deploy step is reached (ask me to deploy; never deploy yourself).
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 3.
````
