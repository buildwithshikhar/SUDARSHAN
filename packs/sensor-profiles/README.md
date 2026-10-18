# sensor-profiles

Sensor profiles: detection and noise parameters, each with a data-register ID.

Everything in this directory is fictional / uses open-source parameters. Nothing here represents a real site, system or operational figure.

The loader reads every `*.yaml` here and matches a profile by `id` and `version`, not by file name. Files are named `<id>.v1.yaml` after the contract version.
