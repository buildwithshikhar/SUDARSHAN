"""The feature vector: eight axes from the spec alone."""

import pytest

from app.contracts import ScenarioSpec
from app.contracts.loader import load_pack
from app.contracts.paths import packs_root
from app.scenarios import features as F
from app.scenarios.features import AXES, Features, features_of, reaction_windows

from .behaviour_support import group, member, scenario, wp
from .live_helpers import harrier_spec


def pack_scenario(name: str) -> ScenarioSpec:
    spec = load_pack(packs_root() / "scenarios" / f"{name}.v1.json")
    assert isinstance(spec, ScenarioSpec)
    return spec


def test_a_feature_vector_has_eight_named_axes_in_order() -> None:
    assert AXES == (
        "threat_count",
        "id_ambiguity",
        "approach_speed",
        "bearing_spread",
        "clutter_density",
        "degradation_load",
        "timing_tightness",
        "stealth",
    )
    f = features_of(harrier_spec())
    assert list(f.as_dict()) == list(AXES)
    assert all(0.0 <= v <= 1.0 for v in f.values)
    assert Features.from_dict(f.as_dict()) == f and f["id_ambiguity"] == f.values[1]
    with pytest.raises(ValueError, match="8 values"):
        Features((0.0,))


def test_harrier_reads_as_one_hostile_among_look_alikes() -> None:
    f = features_of(harrier_spec()).as_dict()
    assert f["threat_count"] == pytest.approx(0.215338, abs=1e-6)  # one hostile of 24
    assert f["id_ambiguity"] == 0.8  # four of five contacts are not a plain hostile drone
    assert f["clutter_density"] == 0.15  # three birds of 20
    assert f["bearing_spread"] == 0.0 and f["degradation_load"] == 0.0 and f["stealth"] == 0.0


def test_the_same_spec_gives_the_same_vector_every_time() -> None:
    spec = pack_scenario("heron-ridge-low-approach")
    assert features_of(spec) == features_of(spec)


def test_a_low_flying_hostile_counts_as_stealthy() -> None:
    f = features_of(pack_scenario("heron-ridge-low-approach"))
    assert f["stealth"] == 1.0  # the quad comes in about 30 m above the ground


def test_degradations_raise_the_degradation_axis_by_time_and_severity() -> None:
    data = harrier_spec().model_dump(mode="json")
    n = len(data["sensors"])
    data["degradations"] = [
        {"sensor": "radar-1", "kind": "outage", "from_s": 0, "to_s": 210},
        {"sensor": "eo-1", "kind": "haze", "from_s": 0, "severity": 0.5},
    ]
    spec = ScenarioSpec.model_validate(data)
    expected = (0.5 + 0.5) / n
    assert features_of(spec)["degradation_load"] == pytest.approx(expected, abs=1e-6)


def test_bearing_spread_is_zero_for_one_direction_and_high_for_all_round() -> None:
    def hostile(name: str, x: float, y: float) -> dict[str, object]:
        return member(name, x, y, z=60.0)

    one_way = scenario([hostile("a", 1000, 0), hostile("b", 1200, 10), hostile("c", 900, -10)])
    all_round = scenario(
        [
            hostile("a", 1000, 0),
            hostile("b", -1000, 0),
            hostile("c", 0, 1000),
            hostile("d", 0, -1000),
        ]
    )
    assert features_of(one_way)["bearing_spread"] < 0.01
    assert features_of(all_round)["bearing_spread"] == pytest.approx(1.0)


def test_group_members_take_their_groups_speed() -> None:
    members = [member(f"m{i}", 100.0 * i, 0.0) for i in range(3)]
    swarm = scenario(members, [group(["m0", "m1", "m2"], [wp(1000.0, 0.0, speed=14.0)])])
    assert features_of(swarm)["approach_speed"] == pytest.approx(14.0 / F.SPEED_FULL_MPS)
    alone = scenario(members)
    assert features_of(alone)["approach_speed"] == pytest.approx(5.0 / F.SPEED_FULL_MPS)


def test_decoys_count_towards_ambiguity() -> None:
    plain = scenario([member("a", 900, 0), member("b", 950, 0)])
    mixed = scenario([member("a", 900, 0), member("b", 950, 0, class_id="decoy-small")])
    assert features_of(plain)["id_ambiguity"] == 0.0
    assert features_of(mixed)["id_ambiguity"] == 0.5


def test_reaction_windows_run_from_first_cover_to_the_inner_zone() -> None:
    spec = pack_scenario("heron-ridge-low-approach")
    hostile = [t for t in spec.threats if t.disposition == "hostile"]
    windows = reaction_windows(spec, hostile)
    window = windows["contact-quad"]
    assert window is not None and 0 < window < spec.duration_s


def test_a_hostile_no_sensor_covers_has_no_window() -> None:
    spec = harrier_spec()
    hostile = [t for t in spec.threats if t.disposition == "hostile"]
    far = hostile[0].model_copy(update={"id": "far"})
    far = far.model_copy(update={"start": far.start.model_copy(update={"x": 5800.0, "y": 5800.0})})
    far = far.model_copy(
        update={"route": [w.model_copy(update={"position": far.start}) for w in far.route]}
    )
    assert reaction_windows(spec, [far]) == {"far": None}
