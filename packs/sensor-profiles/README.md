# sensor-profiles

Sensor profiles: detection and noise parameters, each with a data-register ID.

Everything in this directory is fictional / uses open-source parameters. Nothing here represents a real site, system or operational figure.

The loader reads every `*.yaml` here and matches a profile by `id` and `version`, not by file name. `radar-generic-s.v1.yaml` keeps its original name; the EO/IR profiles are named `<id>.yaml` because `tests/test_contracts.py` expects exactly one `*.v1.*` example per contract. Rename them to `<id>.v1.yaml` once that test allows several profiles.
