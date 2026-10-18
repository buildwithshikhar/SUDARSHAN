"""docs/SENSOR_MODELS.md ("Tracking") describes the code that is there, parameter for parameter."""

import re
from dataclasses import fields

import pytest

from sim.tracking import AssistConfig, ErrorModel, TrackerConfig

from .sim_cases import REPO
from .tracking_cases import SWAP_SEED, SWAP_TICK


def tracking_section() -> str:
    text = (REPO / "docs" / "SENSOR_MODELS.md").read_text(encoding="utf-8")
    start = text.index("\n## Tracking")
    return text[start:]


@pytest.mark.parametrize("config", [TrackerConfig, ErrorModel, AssistConfig])
def test_every_parameter_is_named_in_the_tracking_section(config: type) -> None:
    section = tracking_section()
    missing = [f.name for f in fields(config) if f"`{f.name}`" not in section]
    assert missing == [], f"{config.__name__}: {missing} not documented"


def test_the_documented_defaults_are_the_ones_in_code() -> None:
    section = tracking_section()
    rows = dict(re.findall(r"^\| `(\w+)` \| [^|]+ \| ([0-9.]+) \|", section, re.MULTILINE))
    cfg = TrackerConfig()
    for name in ("accel_sigma_mps2", "init_exclusion_scale", "confirm_hits", "duplicate_gate"):
        assert float(rows[name]) == float(getattr(cfg, name)), name
    model = ErrorModel()
    for name in ("swap_max", "swap_scale", "split_max", "merge_max", "clutter_gain"):
        assert float(rows[name]) == float(getattr(model, name)), name


def test_the_documented_swap_is_the_pinned_one() -> None:
    section = tracking_section()
    assert f"seed {SWAP_SEED}" in section and f"tick {SWAP_TICK}" in section


def test_the_section_states_what_the_honesty_rules_require() -> None:
    section = tracking_section().lower()
    for phrase in (
        "no real detector",
        "reference data",
        "q-20",
        "fictional",
        "no accuracy claim",
        "not a claim about",
    ):
        assert phrase in section, phrase
