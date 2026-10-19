"""The generator: determinism, the hard constraints, the relaxation ladder, the sampler."""

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from app.contracts import ScenarioSpec
from app.scenarios import generator as gen
from app.scenarios.constraints import Rejection, hard_constraints, link_range_problems, standoff_m
from app.scenarios.features import features_of
from app.scenarios.generator import STAGES, GenerationFailed, generate
from app.scenarios.oracle import play
from app.scenarios.request import DifficultyVector, GeneratorRequest
from app.scenarios.sampler import STANDOFF_M, Sampler, scenario_id, sim_seed
from app.scenarios.sharecode import decode, encode
from app.scenarios.solvability import evaluate, solved
from sim.catalogue import load_catalogue

CAT = load_catalogue()


def req(seed: int = 3, **kw: Any) -> GeneratorRequest:
    base: dict[str, Any] = {
        "seed": seed,
        "difficulty": DifficultyVector(
            threat_load=10, ambiguity=10, speed=30, stealth=20, degradation=0
        ),
        "threat_mix": ["single"],
    }
    base.update(kw)
    return GeneratorRequest(**base)


# ----------------------------------------------------------------------------- determinism


def test_the_same_request_and_version_give_a_byte_identical_spec() -> None:
    a, b = generate(req()), generate(req())
    assert a.spec_json() == b.spec_json() and a.spec_sha256 == b.spec_sha256
    assert hashlib.sha256(a.spec_json()).hexdigest() == a.spec_sha256
    assert generate(req(4)).spec_sha256 != a.spec_sha256


def test_two_processes_with_different_hash_salts_agree() -> None:
    code = (
        "import sys; sys.path.insert(0, '.');"
        "from app.scenarios.generator import generate;"
        "from app.scenarios.request import GeneratorRequest;"
        "print(generate(GeneratorRequest(seed=3, threat_mix=['single'])).spec_sha256)"
    )
    root = Path(__file__).resolve().parents[1]
    out = set()
    for salt in ("1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": salt}
        done = subprocess.run(  # noqa: S603 - this interpreter, a fixed script
            [sys.executable, "-c", code],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        out.add(done.stdout.strip())
    assert (
        len(out) == 1
        and next(iter(out)) == generate(GeneratorRequest(seed=3, threat_mix=["single"])).spec_sha256
    )


def test_a_share_code_regenerates_the_identical_spec() -> None:
    made = generate(req())
    again = generate(decode(made.code).request)
    assert again.spec_json() == made.spec_json() and made.code == encode(made.request)


# ----------------------------------------------------------------------------- what is returned


def test_a_generated_scenario_carries_its_id_metadata_and_every_check() -> None:
    made = generate(req())
    spec = made.spec
    assert spec.id == scenario_id(made.request) and spec.id.startswith("gen-1-0-0-3-")
    assert spec.meta is not None and spec.meta.origin == "generated" and spec.meta.playable
    assert spec.meta.generated is not None and spec.meta.generated.code == made.code
    assert spec.meta.generated.generator_version == "1.0.0" and "generated" in spec.meta.tags
    assert [c.name for c in made.checks] == [
        "hostile-presented", "hostile-answered", "no-failures", "oracle-score",
        "difficulty-targets", "diversity",
    ]  # fmt: skip
    assert all(c.passed for c in made.checks) and made.wording == "verified solvable by test run"
    assert made.attempts >= 1 and made.relaxations == () and made.oracle_score >= 0.8
    assert made.features == features_of(spec) and made.diversity.passes is None
    assert spec.default_seed == sim_seed(3, 0 if made.attempts == 1 else made.attempts - 1)


def test_the_accepted_spec_is_cleared_again_by_a_fresh_oracle_run() -> None:
    for seed in (1, 2):
        made = generate(req(seed, terrain="heron-ridge"))
        assert solved(evaluate(made.spec, play(made.spec, made.spec.default_seed), 80))


def test_generated_routes_keep_the_stand_off_and_groups_cover_their_formation() -> None:
    for seed in range(4):
        r = req(
            seed, threat_mix=["swarm", "decoy-mix"], difficulty=DifficultyVector(threat_load=45)
        )
        spec = Sampler(r, 0, CAT).build()
        reach = standoff_m(spec)
        assert reach is not None and (reach >= STANDOFF_M or hard_constraints(spec, CAT))
    made = generate(req(5, threat_mix=["swarm"], difficulty=DifficultyVector(threat_load=45)))
    reach = standoff_m(made.spec)
    assert reach is not None and reach >= STANDOFF_M and link_range_problems(made.spec) == []
    assert made.spec.groups, "a swarm request makes a group"


def test_the_difficulty_request_is_realised_in_the_features() -> None:
    low = generate(req(7)).features
    high = generate(
        req(7, difficulty=DifficultyVector(threat_load=60, ambiguity=55, speed=30, stealth=20))
    ).features
    assert high["threat_count"] > low["threat_count"]
    assert high["id_ambiguity"] > low["id_ambiguity"]


# ----------------------------------------------------------------------------- the sampler


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("single", {"rotary-small", "autonomous-small"}),
        ("fast-mover", {"fpv-small"}),
        ("fixed-wing", {"fixed-wing-small", "fixed-wing-medium"}),
        ("silent-raid", {"autonomous-small"}),
    ],
)
def test_each_archetype_draws_its_class(kind: str, expected: set[str]) -> None:
    spec = Sampler(req(2, threat_mix=[kind]), 0, CAT).build()
    hostile = {t.class_id for t in spec.threats if t.disposition == "hostile"}
    assert hostile and hostile <= expected


def test_a_swarm_makes_a_leader_follower_group_and_a_decoy_mix_has_decoys() -> None:
    swarm = Sampler(
        req(2, threat_mix=["swarm"], difficulty=DifficultyVector(threat_load=50)), 0, CAT
    ).build()
    (group, *_) = [g for g in swarm.groups if g.kind == "swarm"]
    assert group.topology == "leader-follower" and group.leader in group.members
    decoy = Sampler(
        req(2, threat_mix=["decoy-mix"], difficulty=DifficultyVector(threat_load=60, ambiguity=70)),
        0,
        CAT,
    ).build()
    assert any(t.class_id == "decoy-small" for t in decoy.threats)


def test_ambiguity_adds_look_alikes_and_degradation_adds_degradations() -> None:
    plain = Sampler(req(2, difficulty=DifficultyVector(ambiguity=0, degradation=0)), 0, CAT).build()
    busy = Sampler(
        req(2, difficulty=DifficultyVector(ambiguity=90, degradation=80), time_of_day="night"),
        0,
        CAT,
    ).build()
    assert all(t.disposition == "hostile" for t in plain.threats) and plain.degradations == []
    kinds = {t.class_id for t in busy.threats}
    assert kinds & {"bird", "kite", "balloon", "civil-drone"} and busy.degradations
    assert busy.filed_flights and {s.profile.id for s in busy.sensors} >= {
        "eo-generic-nv",
        "ir-generic-thermal",
    }


def test_terrain_time_and_weather_shape_the_world() -> None:
    spec = Sampler(req(2, terrain="osprey-town", time_of_day="dusk", weather="fog"), 0, CAT).build()
    assert spec.world.terrain.kind == "pack" and spec.world.half_extent_m == 1500.0
    assert spec.world.start_time_of_day_h == 18.0 and spec.world.weather.condition == "fog"
    assert [z.radius_m for z in spec.zones] == [450.0, 1100.0]


def test_attempts_give_different_candidates_and_the_same_attempt_the_same() -> None:
    def build(attempt: int) -> ScenarioSpec:
        return Sampler(req(2), attempt, CAT).build()

    assert build(0) == build(0) and build(0) != build(1)
    assert build(0).default_seed != build(1).default_seed


# ----------------------------------------------------------------------------- constraints


def test_a_route_that_comes_too_close_fails_the_stand_off() -> None:
    spec = Sampler(req(2), 0, CAT).build()
    hostile = next(t for t in spec.threats if t.disposition == "hostile")
    near = hostile.route[-1].model_copy(
        update={"position": hostile.route[-1].position.model_copy(update={"x": 20.0, "y": 20.0})}
    )
    moved = spec.model_copy(
        update={
            "threats": [
                t.model_copy(update={"route": [*t.route[:-1], near]}) if t.id == hostile.id else t
                for t in spec.threats
            ]
        }
    )
    reach = standoff_m(moved)
    assert reach is not None and reach < STANDOFF_M
    assert [r.reason for r in hard_constraints(moved, CAT)] == ["standoff"]
    assert hard_constraints(spec, CAT) == []


def test_a_group_whose_link_range_is_too_short_is_refused() -> None:
    spec = Sampler(
        req(2, threat_mix=["swarm"], difficulty=DifficultyVector(threat_load=45)), 0, CAT
    ).build()
    g = spec.groups[0]
    short = spec.model_copy(
        update={"groups": [g.model_copy(update={"link_range_m": 10.0}), *spec.groups[1:]]}
    )
    assert link_range_problems(spec) == [] and len(link_range_problems(short)) == 1
    assert "link-range" in [r.reason for r in hard_constraints(short, CAT)]


def test_a_scenario_with_no_hostile_contact_has_no_stand_off() -> None:
    spec = Sampler(req(2), 0, CAT).build()
    calm = spec.model_copy(
        update={"threats": [t.model_copy(update={"disposition": "clutter"}) for t in spec.threats]}
    )
    assert standoff_m(calm) is None


# ----------------------------------------------------------------------------- the ladder


def test_with_no_history_the_diversity_stages_are_skipped() -> None:
    assert [s.name for s in STAGES][:3] == ["requested", "diversity-halved", "diversity-dropped"]
    assert generate(req()).relaxations == ()


def test_a_history_the_candidate_cannot_differ_from_relaxes_the_filter_and_says_so() -> None:
    first = generate(req())
    same = [first.features] * 3
    made = generate(req(), same, threshold=1.0)
    assert made.relaxations[:2] == (
        "the diversity threshold was halved",
        "the diversity filter was dropped",
    )
    assert made.diversity.passes is False  # honest: it was accepted with the filter relaxed
    diversity_check = next(c for c in made.checks if c.name == "diversity")
    assert not diversity_check.passed and "relaxed" in diversity_check.detail
    assert made.wording == "verified solvable by test run"
    roomy = generate(req(), same, threshold=0.0001)
    assert roomy.relaxations == () and roomy.diversity.passes is True


def test_the_ladder_eases_the_request_and_logs_what_it_changed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, int]] = []
    real = hard_constraints

    def refuse_until_eased(spec: ScenarioSpec, cat: Any) -> Any:
        calls.append((len(spec.threats), 0))
        # refuse every candidate with more than one hostile contact
        if sum(t.disposition == "hostile" for t in spec.threats) > 1:
            return [Rejection("standoff", "forced")]
        return real(spec, cat)

    monkeypatch.setattr("app.scenarios.generator.hard_constraints", refuse_until_eased)
    r = req(9, threat_mix=["single", "fast-mover"], max_attempts=2,
            difficulty=DifficultyVector(threat_load=80, ambiguity=10))  # fmt: skip
    made = gen.generate(r)
    assert sum(t.disposition == "hostile" for t in made.spec.threats) == 1
    assert any("threat load 80 to" in line for line in made.relaxations)
    assert made.rejections["standoff"] >= 2


def test_nothing_unsolved_is_ever_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    real = evaluate

    def never_solved(spec: ScenarioSpec, result: Any, bar: int) -> Any:
        checks = real(spec, result, bar)
        return [
            checks[0],
            checks[1],
            checks[2].__class__("no-failures", False, 1, "x", "c"),
            checks[3],
        ]

    monkeypatch.setattr("app.scenarios.generator.evaluate", never_solved)
    with pytest.raises(GenerationFailed, match="oracle:no-failures") as caught:
        gen.generate(req(max_attempts=1))
    assert caught.value.attempts == len(STAGES) - 2 and caught.value.request.seed == 3
    assert caught.value.rejections == {"oracle:no-failures": len(STAGES) - 2}


def test_describe_names_each_kind_of_relaxation() -> None:
    r = req(difficulty=DifficultyVector(threat_load=80, ambiguity=60, stealth=70, degradation=50))
    texts = [gen._describe(s, r, gen._eased(r, s)) for s in STAGES[1:]]
    assert texts[0].startswith("the diversity threshold") and texts[1].startswith(
        "the diversity filter"
    )
    assert "widened" in texts[2] and "threat load 80 to 55" in texts[3] and "to 30" in texts[4]
    assert texts[5] == "the request was eased to a single drone at low load"
    assert gen._eased(r, STAGES[0]) is r
    last = gen._eased(r, STAGES[-1])
    assert last.threat_mix == ["single"] and last.difficulty.threat_load == 5


def test_fidelity_holds_threat_count_and_ambiguity_to_the_request() -> None:
    r = req(difficulty=DifficultyVector(threat_load=50, ambiguity=50))
    feats = features_of(Sampler(r, 0, CAT).build())
    ok = gen._fidelity(r, feats, 1.0)
    assert ok.passed
    far = gen._fidelity(req(difficulty=DifficultyVector(threat_load=100, ambiguity=0)), feats, 0.1)
    assert not far.passed and "threat_count" in far.detail and far.code == "generator.targets"
