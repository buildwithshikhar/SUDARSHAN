# Release process

A stub, completed in wave 15. The shape of a release:

1. **Green main.** CI passes on the release commit, including `make prod-check`.
2. **Licence re-check.** Every row in [DATA_REGISTER.md](DATA_REGISTER.md) is re-checked against its source, and the date is recorded in the register. A row whose licence cannot be confirmed is not shipped. This step is repeated before every release, not only the first.
3. **Wording check.** The grep test over user-facing text passes (no "validated", "doctrine-accurate", "real data", "trained on" or "provably" except where quoted as forbidden wording).
4. **Documentation.** `CHANGELOG.md` has the release section, [TRACEABILITY.md](TRACEABILITY.md) has no empty proof cell, release notes are written.
5. **Hand-off.** The maintainer tags the commit and deploys it; the build log records the deployed commit and the result of `make smoke URL=<live url>`.

Claude Code prepares steps 1 to 4 and never tags or deploys.
