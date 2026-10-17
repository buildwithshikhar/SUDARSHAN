# Wave 2 · Design system + app shell

> **PRIORITY MILESTONE: first deployable slice.** This wave produces the first live link of the platform, the next SIH milestone. Nothing in wave 3 starts until the live link is verified and recorded in [BUILD_LOG.md](../BUILD_LOG.md).

| | |
|---|---|
| Depends on | 1 |
| Recommended model | Sonnet |
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
- Deployment kit: `docs/DEPLOY.md`, `make smoke URL=...` against a remote URL, and host-specific config only if the host is already chosen in `docs/OPEN_QUESTIONS.md`.

## Out of scope

- Any simulation, scoring or session feature.

## Acceptance criteria

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

## Prompt (paste into Claude Code, Sonnet)

````text
ROLE: You are building wave 2 (Design system + app shell) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). CLAUDE.md is loaded: follow it, above all the LOCKED RULES.

READ FIRST: docs/BUILD_LOG.md (confirm wave 1 is Done and main is green; if not, stop and tell me). Then: docs/07-ui-map.md (design system, sidebar and screens) and docs/DECISIONS.md ADR-005 and ADR-006.

GOAL: The real design system, sign-in, role-based shell and bilingual UI, deployed as the first live link.

STEP 1 — Design system (subagent A, worktree)
- Complete the tokens in docs/07-ui-map.md as CSS variables and a Tailwind theme; remove any default Tailwind palette from use.
- Self-host IBM Plex Sans, IBM Plex Mono and Noto Sans Devanagari (OFL; keep the licence files). tabular-nums for all numbers.
- IBM Carbon icons (Apache-2.0) only, 16 and 20 px.
- Components: button, input, select, checkbox, table (28/36 px rows), panel, tabs, dialog, badge, inline alert, tooltip, and EmptyState / LoadingState / ErrorState. Storybook is not needed; a /dev/components route in demo mode only is enough.
- Token contrast unit test (WCAG AA, both themes).

STEP 2 — Auth and RBAC (subagent B, worktree)
- Login endpoint with argon2, secure HttpOnly SameSite session cookie, CSRF protection, login rate limit, logout.
- Role guard dependency for API routes; tests per role.
- create-user CLI (email, role; password from prompt or env; refuses weak passwords).

STEP 3 — Shell (main session, after A and B merge)
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
- about 60% of the session is used before acceptance (commit green work, log it as wave 2.b, stop);
- the deploy step is reached (ask me to deploy; never deploy yourself).
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 3.
````
