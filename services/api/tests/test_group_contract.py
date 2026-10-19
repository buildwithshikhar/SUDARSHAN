"""The `groups` and `motion` additions to scenario.v1: defaults, ranges and cross-checks."""

import json
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from app.contracts import ScenarioSpec
from app.contracts.paths import packs_root
from app.contracts.scenario import Drift, Group, Tether
from tests.behaviour_support import group, member, scenario, wp


def threats(n: int = 3, **kw: Any) -> list[dict[str, Any]]:
    return [member(f"m{i}", 100.0 * i, 0.0, **kw) for i in range(n)]


def build(groups: list[dict[str, Any]], n: int = 3, **kw: Any) -> ScenarioSpec:
    return scenario(threats(n, **kw), groups)


ROUTE = [wp(1000.0, 0.0)]


def test_a_minimal_group_is_valid_and_every_field_has_a_default() -> None:
    spec = build([group(["m0", "m1", "m2"], ROUTE)])
    g = spec.groups[0]
    assert (g.kind, g.topology, g.leader, g.intent) == ("swarm", "leaderless", None, "transit")
    assert (g.on_route_end, g.discipline, g.spacing_m) == ("loiter", 0.9, 20.0)
    assert (g.leader_loss, g.leader_loss_hold_s, g.link_epoch_s, g.link_loss) == (
        "elect",
        4.0,
        1.0,
        0,
    )
    assert (g.weights.separation, g.weights.alignment, g.weights.cohesion, g.weights.goal) == (
        1.0,
        1.5,
        0.6,
        1.0,
    )


def test_a_scenario_without_groups_or_motion_is_unchanged() -> None:
    spec = scenario(threats(2))
    assert spec.groups == [] and all(t.motion is None for t in spec.threats)


def test_a_leader_follower_group_needs_a_leader_among_its_members() -> None:
    ok = build([group(["m0", "m1"], ROUTE, topology="leader-follower", leader="m1")])
    assert ok.groups[0].leader == "m1"
    with pytest.raises(ValidationError, match="needs a leader"):
        build([group(["m0", "m1"], ROUTE, topology="leader-follower")])
    with pytest.raises(ValidationError, match="one of the members"):
        build([group(["m0", "m1"], ROUTE, topology="leader-follower", leader="m2")])
    with pytest.raises(ValidationError, match="no leader"):
        build([group(["m0", "m1"], ROUTE, leader="m0")])


def test_members_must_exist_be_unique_and_belong_to_one_group() -> None:
    with pytest.raises(ValidationError, match="is not a threat"):
        build([group(["m0", "zz"], ROUTE)])
    with pytest.raises(ValidationError, match="more than once|duplicate"):
        build([group(["m0", "m0"], ROUTE)])
    with pytest.raises(ValidationError, match="is in groups g1 and g2"):
        build([group(["m0", "m1"], ROUTE), group(["m1", "m2"], ROUTE, id="g2")])
    with pytest.raises(ValidationError):
        build([group(["m0", "m1"], ROUTE), group(["m2", "m3"], ROUTE)], n=4)  # same group ID
    with pytest.raises(ValidationError):
        build([group(["m0"], ROUTE)])  # fewer than two members


def test_a_group_needs_a_route_without_holds_and_inside_the_play_area() -> None:
    with pytest.raises(ValidationError):
        build([group(["m0", "m1"], [])])
    held = {"position": {"x": 0, "y": 0, "z": 60}, "speed_mps": 5, "hold_s": 5}
    with pytest.raises(ValidationError, match="cannot hold"):
        build([group(["m0", "m1"], [held])])
    with pytest.raises(ValidationError, match="leaves the play area"):
        build([group(["m0", "m1"], [wp(99999.0, 0.0)])])


def test_the_route_altitude_must_suit_every_member() -> None:
    with pytest.raises(ValidationError, match="altitude is outside the band"):
        build([group(["m0", "m1"], [wp(0.0, 0.0, z=2000.0)])])


def test_neighbour_radius_cannot_be_smaller_than_the_spacing() -> None:
    with pytest.raises(ValidationError, match="at least spacing_m"):
        build([group(["m0", "m1"], ROUTE, spacing_m=60.0, neighbour_radius_m=30.0)])


def test_a_member_cannot_have_its_own_motion() -> None:
    kite = member("m0", 0.0, 0.0, class_id="kite", z=60.0)
    kite["motion"] = {
        "kind": "tether",
        "anchor": {"x": 0, "y": 0, "z": 0},
        "length_m": 80,
        "sway_m": 10,
        "sway_period_s": 8,
    }
    other = member("m1", 50.0, 0.0, class_id="kite", z=60.0)
    with pytest.raises(ValidationError, match="own motion"):
        scenario([kite, other], [group(["m0", "m1"], ROUTE, kind="flock")])


def test_a_flock_is_clutter_and_a_swarm_is_not() -> None:
    birds = [member(f"b{i}", 10.0 * i, 0.0, class_id="bird", z=60.0) for i in range(3)]
    ok = scenario(birds, [group(["b0", "b1", "b2"], ROUTE, kind="flock")])
    assert ok.groups[0].kind == "flock"
    with pytest.raises(ValidationError, match="a flock is made of clutter"):
        build([group(["m0", "m1"], ROUTE, kind="flock")])
    with pytest.raises(ValidationError, match="a swarm is made of non-clutter"):
        scenario(birds, [group(["b0", "b1"], ROUTE)])


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("discipline", 1.2),
        ("discipline", -0.1),
        ("spacing_m", 2.0),
        ("spacing_m", 250.0),
        ("link_loss", 1.5),
        ("link_epoch_s", 0.4),
        ("leader_loss_hold_s", 31.0),
        ("probe_cycles", 0),
        ("probe_cycles", 11),
        ("lane_spacing_m", 2.0),
        ("kind", "pack"),
        ("intent", "attack"),
        ("leader_loss", "flee"),
        ("on_route_end", "land"),
        ("topology", "mesh"),
        ("weights", {"separation": 6.0}),
        ("weights", {"unknown": 1.0}),
    ],
)
def test_group_fields_are_range_checked(field: str, bad: Any) -> None:
    with pytest.raises(ValidationError):
        build([group(["m0", "m1"], ROUTE, **{field: bad})])


def test_group_limits_hold_at_the_edges() -> None:
    g = Group.model_validate(
        group(
            ["a", "b"],
            ROUTE,
            discipline=0.0,
            spacing_m=3.0,
            neighbour_radius_m=5.0,
            link_epoch_s=0.5,
            leader_loss_hold_s=0.0,
            probe_cycles=10,
        )
    )
    assert g.spacing_m == 3.0 and g.probe_cycles == 10


def test_there_are_at_most_32_groups_of_at_most_64_members() -> None:
    names = [f"m{i}" for i in range(65)]
    with pytest.raises(ValidationError):
        Group.model_validate(group(names, ROUTE))
    many = [member(f"m{i}", float(i), 0.0) for i in range(66)]
    groups = [group([f"m{2 * i}", f"m{2 * i + 1}"], ROUTE, id=f"g{i}") for i in range(33)]
    with pytest.raises(ValidationError):
        scenario(many, groups)


# ---------------------------------------------------------------------------- motion


def kite_threat(**kw: Any) -> dict[str, Any]:
    t = member("kite-1", 0.0, 0.0, class_id="kite", z=60.0)
    t["motion"] = {
        "kind": "tether",
        "anchor": {"x": 0, "y": 0, "z": 0},
        "length_m": 100,
        "sway_m": 20,
        "sway_period_s": 8,
        **kw,
    }
    return t


def test_a_tether_and_a_drift_validate_and_keep_the_required_route() -> None:
    balloon = member("balloon-1", 0.0, 500.0, class_id="balloon", z=100.0, speed=1.0)
    balloon["motion"] = {"kind": "drift", "climb_mps": 0.5}
    spec = scenario([kite_threat(), balloon])
    assert isinstance(spec.threats[0].motion, Tether)
    assert isinstance(spec.threats[1].motion, Drift)
    assert spec.threats[0].route  # the route is still required, and still valid
    bad = member("b", 0.0, 0.0)
    bad["motion"] = {"kind": "drift", "climb_mps": 0.5}
    bad["route"] = []
    with pytest.raises(ValidationError):
        scenario([bad])


@pytest.mark.parametrize(
    "bad",
    [
        {"length_m": 4.0},
        {"length_m": 301.0},
        {"sway_m": -1.0},
        {"sway_m": 101.0},
        {"sway_period_s": 1.0},
        {"sway_period_s": 61.0},
    ],
)
def test_tether_fields_are_range_checked(bad: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        scenario([kite_threat(**bad)])


def test_drift_climb_is_range_checked() -> None:
    for climb in (-0.1, 3.1):
        t = member("b", 0.0, 0.0, class_id="balloon", z=100.0, speed=1.0)
        t["motion"] = {"kind": "drift", "climb_mps": climb}
        with pytest.raises(ValidationError):
            scenario([t])


def test_a_motion_kind_is_a_discriminated_union() -> None:
    t = kite_threat()
    t["motion"] = {"kind": "orbit", "climb_mps": 1.0}
    with pytest.raises(ValidationError):
        scenario([t])


def test_a_kite_must_fly_inside_its_class_altitude_band() -> None:
    with pytest.raises(ValidationError, match="tethered flying height"):
        scenario([kite_threat(length_m=300)])  # 230 m up, above the 150 m ceiling
    t = kite_threat(length_m=8)  # 6 m up, below the 10 m floor
    with pytest.raises(ValidationError, match="tethered flying height"):
        scenario([t])
    t = kite_threat()
    t["motion"]["anchor"] = {"x": 99999, "y": 0, "z": 0}
    with pytest.raises(ValidationError, match="anchor outside the play area"):
        scenario([t])


# ---------------------------------------------------------------------------- JSON Schema


def test_the_published_json_schema_accepts_groups_and_motion() -> None:
    schema = json.loads((packs_root() / "schemas" / "scenario.v1.json").read_text("utf-8"))
    validator = Draft202012Validator(schema)
    balloon = member("balloon-1", 0.0, 500.0, class_id="balloon", z=100.0, speed=1.0)
    balloon["motion"] = {"kind": "drift", "climb_mps": 0.5}
    spec = scenario(
        [*threats(2), kite_threat(), balloon],
        [group(["m0", "m1"], ROUTE, topology="leader-follower", leader="m0")],
    )
    document = json.loads(spec.model_dump_json())
    assert list(validator.iter_errors(document)) == []
    document["groups"][0]["discipline"] = 3
    assert list(validator.iter_errors(document))
