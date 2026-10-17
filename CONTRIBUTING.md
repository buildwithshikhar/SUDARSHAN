# Contributing

SUDARSHAN is a solo project built with Claude Code. This file states the rules that apply to every commit, human or Claude Code. [CLAUDE.md](CLAUDE.md) holds the full standing instructions, including the locked rules.

## Commit convention

Conventional Commits, small and focused, one logical change per commit.

```
<type>(<optional scope>): <imperative summary, lower case, no full stop, under 72 characters>

<body: what changed and why, wrapped at about 72 columns>
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`. Breaking changes use `!` after the type and a `BREAKING CHANGE:` footer.

## Branch and merge rules

- Push to `main` only. Subagents work in git worktrees and merge to `main` when their tests pass.
- CI must be green on `main` before a wave is marked done. Never carry a red build across a `/clear`.
- Never rewrite published history on `main`.

## Claude Code rules

1. Stay inside this repository. Touch no Docker objects outside this repo's compose project.
2. Never deploy. The user deploys; Claude Code prepares config, docs and smoke tests.
3. Never put credentials, tokens or keys in the repo, in logs or on slides. Commit only `.env.example` with placeholders.
4. Production mode blocks demo accounts. Credentials come from first-admin environment variables or the `create-admin` CLI.
5. Follow the wave workflow in [docs/BUILD_LOG.md](docs/BUILD_LOG.md): update the log after every merged step, write tests with every feature, at most 2 subagents at once.
6. Do not rewrite research documents (`docs/00`–`09`). Record new decisions in [docs/DECISIONS.md](docs/DECISIONS.md) and open items in [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md).

## Content rules

- **Honesty.** No claims of real operational or classified data, validated training effectiveness or doctrine accuracy. Use: "built from open research datasets and published specifications, in fictional scenarios."
- **Defensive only.** Recognise, classify, respond. No content on building, arming or operating attack drones, and no real-world targeting detail.
- **Data.** Datasets are "calibrated from", never "trained on". Scenarios are "verified solvable by test run", never "provably solvable". See [docs/DATA_REGISTER.md](docs/DATA_REGISTER.md).

## Licence

No licence has been chosen yet (see [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md), Q-01). Until one is added, all rights are reserved.
