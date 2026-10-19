"""Locked rule 2, enforced on the source: threat behaviour is kinematics only.

A group member steers by its group's own route and its group-mates. Nothing in `sim/behaviours`,
or in the group part of `sim/world.py`, may mention defended places, zones, targets, attacks,
engagements, impacts, dives, terminal phases, pursuit or interception, or read anything that
could supply one (assets, zones, sensors, the operator, the tracker, the rules of engagement).
These words may appear in this test file only.
"""

import importlib
import inspect
import io
import pkgutil
import re
import tokenize
from pathlib import Path

import sim.behaviours

SIM = Path(__file__).resolve().parents[1] / "sim"
BEHAVIOURS = sorted((SIM / "behaviours").glob("*.py"))
FORBIDDEN = re.compile(
    r"\b(assets?|zones?|defended|targets?|targeting|attack\w*|engage\w*|impact\w*|dives?|diving|"
    r"terminal|pursu\w+|intercept\w*)\b",
    re.IGNORECASE,
)


def group_part_of_world() -> str:
    text = (SIM / "world.py").read_text("utf-8")
    start, end = text.index("# --- groups: begin"), text.index("# --- groups: end")
    assert start < end
    return text[start:end]


def test_there_are_behaviour_sources_to_check() -> None:
    names = {p.name for p in BEHAVIOURS}
    assert {"boids.py", "groups.py", "intents.py", "clutter.py", "links.py", "draws.py"} <= names


def test_behaviour_sources_never_use_the_forbidden_words() -> None:
    for path in BEHAVIOURS:
        found = FORBIDDEN.findall(path.read_text("utf-8"))
        assert not found, f"{path.name}: {found}"


def test_the_group_part_of_the_world_never_uses_the_forbidden_words() -> None:
    found = FORBIDDEN.findall(group_part_of_world())
    assert not found, found


def test_the_checker_catches_what_it_is_for() -> None:
    for word in ("the defended asset", "zone", "terminal phase", "pursuit", "target", "dive"):
        assert FORBIDDEN.search(word), word
    assert not FORBIDDEN.search("a flock of divergent diverse headings")


def test_behaviours_import_nothing_that_could_supply_a_place_to_go() -> None:
    banned = (
        "world",
        "sensors",
        "tracking",
        "roe",
        "audience",
        "recognition",
        "catalogue",
        "terrain",
    )
    for path in BEHAVIOURS:
        for line in path.read_text("utf-8").splitlines():
            if not line.startswith(("import ", "from ")):
                continue
            modules = re.split(r"[ ,]+", line.replace("from ", "").replace("import ", " "))
            for module in modules:
                parts = [m for m in module.split(".") if m]
                assert not any(p in banned for p in parts), f"{path.name}: {line}"


def test_no_behaviour_function_takes_a_scenario_asset_or_zone() -> None:
    bad_names = re.compile(r"asset|zone|defended|scenario|spec\b|world|sensor|operator|roe", re.I)
    bad_types = ("DefendedAsset", "Zone", "ScenarioSpec", "World", "Threat", "SensorPlacement")
    checked = 0
    for info in pkgutil.iter_modules(sim.behaviours.__path__):
        module = importlib.import_module(f"sim.behaviours.{info.name}")
        callables = []
        for _, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) and obj.__module__ == module.__name__:
                callables.append(obj)
            elif inspect.isclass(obj) and obj.__module__ == module.__name__:
                callables += [f for _, f in inspect.getmembers(obj, inspect.isfunction)]
        for fn in callables:
            for name, param in inspect.signature(fn).parameters.items():
                assert not bad_names.search(name), f"{module.__name__}.{fn.__name__}({name})"
                annotation = str(param.annotation)
                assert not any(t in annotation for t in bad_types), (
                    f"{module.__name__}.{fn.__name__}({name}: {annotation})"
                )
            checked += 1
    assert checked > 40


def test_the_group_contract_has_no_field_that_could_carry_a_place_to_go() -> None:
    from app.contracts.scenario import Group, Tether

    fields = set(Group.model_fields) | set(Tether.model_fields)
    assert not [f for f in fields if FORBIDDEN.search(f)], fields
    # a group's route is its own; the only positions in a group are its route waypoints, and a
    # tether's anchor
    assert "route" in Group.model_fields and "anchor" in Tether.model_fields


def code_only(text: str) -> str:
    """The source without comments and string literals (docstrings), for the code patterns."""
    keep = [
        t.string
        for t in tokenize.generate_tokens(io.StringIO(text).readline)
        if t.type not in (tokenize.COMMENT, tokenize.STRING)
    ]
    return " ".join(keep)


def test_determinism_rules_hold_in_the_sources() -> None:
    patterns = {
        r"\bmath\.(sin|cos|tan|atan\w*|exp|log\w*|pow|hypot|fsum)\b": "libm maths",
        r"\bimport (random|time|uuid|secrets|numpy)\b|\bfrom (random|time|numpy)\b": "forbidden import",
        r"\bos\.urandom\b|\bdatetime\b|\bhash\(": "wall clock or salted hash",
        r"\b(frozen)?set\(": "a set",
        r"\*\s*\*": "a power operator",
    }
    for path in BEHAVIOURS:
        text = code_only(path.read_text("utf-8"))
        for pattern, what in patterns.items():
            assert not re.search(pattern, text), f"{path.name}: {what}"
