"""The threat catalogue: the `threat-class.v1` contract, the eleven shipped classes, the loader's
cross-checks, the scenario check, and the generated tables in docs/THREAT_CATALOGUE.md."""

import copy
import json
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from app.contracts import ScenarioSpec, ThreatClass
from app.contracts.loader import load_pack, parse_text
from app.contracts.threat_class import ENVELOPE_UNITS, SIGNATURE_UNITS
from sim import catalogue as catalogue_module
from sim.catalogue import Catalogue, CatalogueError, load_catalogue, markdown
from sim.sensors import register_ids

from .sim_cases import REPO

THREATS = REPO / "packs" / "threats"
SCENARIOS = sorted((REPO / "packs" / "scenarios").glob("*.v1.json"))
DOC = REPO / "docs" / "THREAT_CATALOGUE.md"
REGISTER = REPO / "docs" / "DATA_REGISTER.md"
IDS = (
    "autonomous-small",
    "balloon",
    "bird",
    "civil-drone",
    "decoy-small",
    "fixed-wing-large",
    "fixed-wing-medium",
    "fixed-wing-small",
    "fpv-small",
    "kite",
    "rotary-small",
)
RECOGNITION = {
    "rotary-small",
    "fpv-small",
    "fixed-wing-small",
    "fixed-wing-medium",
    "fixed-wing-large",
    "bird",
    "kite",
    "balloon",
}


def raw(class_id: str = "rotary-small") -> dict[str, Any]:
    data = parse_text((THREATS / f"{class_id}.v1.yaml").read_text(encoding="utf-8"), ".yaml")
    assert isinstance(data, dict)
    return data


def threat_class(class_id: str) -> ThreatClass:
    return ThreatClass.model_validate(raw(class_id))


def sv(path: str, value: Any) -> Callable[[dict[str, Any]], None]:
    """Mutation that sets a dotted path."""

    def apply(data: dict[str, Any]) -> None:
        *head, last = path.split(".")
        node: Any = data
        for key in head:
            node = node[key]
        node[last] = value

    return apply


def drop(path: str) -> Callable[[dict[str, Any]], None]:
    def apply(data: dict[str, Any]) -> None:
        *head, last = path.split(".")
        node: Any = data
        for key in head:
            node = node[key]
        del node[last]

    return apply


def copy_threats(tmp_path: Path) -> Path:
    target = tmp_path / "threats"
    shutil.copytree(THREATS, target)
    return target


def rewrite(directory: Path, class_id: str, mutate: Callable[[dict[str, Any]], None]) -> None:
    path = directory / f"{class_id}.v1.yaml"
    data = raw(class_id)
    mutate(data)
    path.write_text(json.dumps(data), encoding="utf-8")  # JSON is YAML


# ------------------------------------------------------------------------- the shipped catalogue


def test_the_shipped_catalogue_is_valid_and_holds_eleven_classes() -> None:
    catalogue = load_catalogue()
    assert catalogue.ids == IDS
    assert len(catalogue) == 11
    assert [c.id for c in catalogue] == list(IDS)
    assert "bird" in catalogue and "tank" not in catalogue


def test_the_recognition_set_is_the_operator_vocabulary_of_the_wave() -> None:
    catalogue = load_catalogue()
    assert catalogue.recognition_set == RECOGNITION
    for cls in catalogue:
        assert cls.recognition_class in RECOGNITION
        assert catalogue.recognition_class(cls.id) == cls.recognition_class
        # a recognition class is recognised as itself
        assert catalogue.get(cls.recognition_class).recognition_class == cls.recognition_class


#: (category, recognition class, default disposition, UAS group, emits)
SPECS = {
    "rotary-small": ("drone", "rotary-small", "hostile", "1", 1),
    "fpv-small": ("drone", "fpv-small", "hostile", "1", 1),
    "autonomous-small": ("drone", "rotary-small", "hostile", "1", 0),
    "decoy-small": ("drone", "rotary-small", "hostile", "1", 0),
    "civil-drone": ("drone", "rotary-small", "civil-permitted", "1", 1),
    "fixed-wing-small": ("drone", "fixed-wing-small", "hostile", "1", 1),
    "fixed-wing-medium": ("drone", "fixed-wing-medium", "hostile", "2", 1),
    "fixed-wing-large": ("drone", "fixed-wing-large", "hostile", "3", 1),
    "bird": ("clutter", "bird", "clutter", None, 0),
    "kite": ("clutter", "kite", "clutter", None, 0),
    "balloon": ("clutter", "balloon", "clutter", None, 0),
}


@pytest.mark.parametrize("class_id", IDS)
def test_each_class_has_its_documented_identity(class_id: str) -> None:
    cls = load_catalogue().get(class_id)
    category, recognition, disposition, group, emits = SPECS[class_id]
    assert (cls.category, cls.recognition_class, cls.default_disposition, cls.uas_group) == (
        category,
        recognition,
        disposition,
        group,
    )
    assert cls.signature["emits"].value == emits
    assert cls.fictional and cls.version == "1.0.0"
    for text in (cls.title, cls.summary, cls.notes):
        assert text is not None and text.en.strip() and text.hi.strip()


@pytest.mark.parametrize("class_id", IDS)
def test_every_value_is_labelled_honestly(class_id: str) -> None:
    """Nothing is claimed as measured, and no register row is invented or borrowed from X01."""
    cls = load_catalogue().get(class_id)
    ids = register_ids(REGISTER)
    for name, q in [*cls.signature.items(), *vars_of(cls.envelope)]:
        assert not q.verified, f"{class_id}:{name}"
        assert q.source_id in ids, f"{class_id}:{name}"
        assert q.source_id != "X01", f"{class_id}:{name} cites the UAV Database, not yet extracted"
    for name, q in vars_of(cls.envelope):
        assert q.source_id == "F01", f"{class_id}:{name}"


def vars_of(envelope: Any) -> list[tuple[str, Any]]:
    return [(name, getattr(envelope, name)) for name in ENVELOPE_UNITS]


def test_the_three_original_classes_keep_the_limits_the_scenarios_already_use() -> None:
    catalogue = load_catalogue()
    seen: dict[str, Any] = {}
    for path in SCENARIOS:
        spec = load_pack(path)
        assert isinstance(spec, ScenarioSpec)
        for threat in spec.threats:
            seen.setdefault(threat.class_id, threat.limits)
            assert threat.limits == seen[threat.class_id]  # one set of limits per class today
    assert set(seen) == {"rotary-small", "fixed-wing-small", "bird"}
    for class_id, limits in seen.items():
        assert catalogue.limits_for(class_id) == limits


def test_kinematics_grow_with_size_and_the_families_are_ordered() -> None:
    catalogue = load_catalogue()
    fixed = [
        catalogue.get(c) for c in ("fixed-wing-small", "fixed-wing-medium", "fixed-wing-large")
    ]
    # the shipped small fixed-wing ceiling (the Kestrel limit) is above the medium one, so the
    # altitude ceiling is not ordered; the floor, the speeds and the signature are
    for name in ("max_speed", "cruise_speed", "min_altitude"):
        values = [getattr(c.envelope, name).value for c in fixed]
        assert values == sorted(values) and len(set(values)) == 3, name
    for name in ("rcs", "size", "source_level", "emitter_power"):
        values = [c.signature[name].value for c in fixed]
        assert values == sorted(values) and len(set(values)) == 3, name
    quads = ("decoy-small", "fpv-small", "rotary-small")
    sizes = [
        catalogue.get(c).signature["size"].value
        for c in ("decoy-small", "fpv-small", "rotary-small")
    ]
    rcs = [catalogue.get(c).signature["rcs"].value for c in quads]
    assert sizes == sorted(sizes) and rcs == sorted(rcs)
    speed = {c.id: c.envelope.max_speed.value for c in catalogue}
    assert speed["fpv-small"] > speed["rotary-small"] > speed["decoy-small"]
    assert speed["fpv-small"] <= 35 and speed["rotary-small"] <= 18  # published orders of magnitude
    assert speed["balloon"] < speed["kite"] < speed["rotary-small"]
    # a bird is -30 to -19 dBsm and a small multirotor -20 to -8 in the research; kite and balloon
    # are fainter than the bird, the decoy sits at the bottom of the multirotor range
    rcs_of = {c.id: c.signature["rcs"].value for c in catalogue}
    assert -20 <= rcs_of["decoy-small"] <= rcs_of["fpv-small"] <= rcs_of["rotary-small"] <= -8
    assert rcs_of["kite"] < rcs_of["balloon"] < rcs_of["bird"]


def test_family_members_share_the_airframe_of_rotary_small() -> None:
    catalogue = load_catalogue()
    base = catalogue.get("rotary-small").signature
    for class_id in ("autonomous-small", "civil-drone"):
        sig = catalogue.get(class_id).signature
        for name in ("rcs", "aspect_swing", "size", "contrast", "contrast_eo", "band"):
            assert sig[name].value == base[name].value, (class_id, name)
    silent = catalogue.get("autonomous-small").signature
    assert silent["emits"].value == 0 and silent["hop_rate"].value == 0
    decoy, quad = catalogue.get("decoy-small").signature, base
    assert decoy["rcs"].value < quad["rcs"].value
    assert decoy["source_level"].value < quad["source_level"].value
    assert decoy["contrast"].value < 0.3 * quad["contrast"].value  # almost no thermal contrast
    assert decoy["emits"].value == 0


def test_the_airborne_clutter_has_the_signatures_the_catalogue_promises() -> None:
    catalogue = load_catalogue()
    kite, balloon, bird = (catalogue.get(c).signature for c in ("kite", "balloon", "bird"))
    for sig in (kite, balloon):
        assert sig["emits"].value == 0
        assert sig["source_level"].value <= 0  # no acoustic source
        assert sig["blades"].value == 0 and sig["rpm"].value == 0
        assert sig["contrast"].value < 0.2  # cold in thermal
    assert kite["contrast_eo"].value > 1.0  # bright and distinctive in a visible-band camera
    assert balloon["aspect_swing"].value == 0  # a sphere has no aspect
    assert bird["blades"].value * bird["rpm"].value / 60 == 12  # wing-beat 12 Hz


def test_the_fixed_wing_large_class_is_unverified_throughout() -> None:
    cls = threat_class("fixed-wing-large")
    assert cls.uas_group == "3"
    assert cls.notes is not None and "UNVERIFIED" in cls.notes.en
    assert not any(q.verified for _, q in [*cls.signature.items(), *vars_of(cls.envelope)])


@pytest.mark.parametrize("class_id", IDS)
def test_each_class_validates_against_the_exported_schema(class_id: str) -> None:
    schema = json.loads((REPO / "packs" / "schemas" / "threat-class.v1.json").read_text("utf-8"))
    jsonschema.validate(raw(class_id), schema)


# ------------------------------------------------------------------------- contract refusals

REFUSED: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
    ("missing source_id", drop("signature.rcs.source_id")),
    ("missing envelope source_id", drop("envelope.max_speed.source_id")),
    ("bad register id", sv("signature.rcs.source_id", "Z99")),
    ("bad group", sv("uas_group", "4")),
    ("numeric group", sv("uas_group", 1)),
    ("drone without group", sv("uas_group", None)),
    ("clutter with a group", lambda d: d.update(category="clutter", default_disposition="clutter")),
    ("clutter that is hostile", sv("category", "clutter")),
    ("drone that is clutter", sv("default_disposition", "clutter")),
    ("bad category", sv("category", "vehicle")),
    ("not fictional", sv("fictional", False)),
    ("bad contract", sv("contract", "threat-class.v2")),
    ("envelope min above max", sv("envelope.min_altitude.value", 500)),
    ("envelope min equals max", sv("envelope.min_altitude.value", 400)),
    ("cruise above max speed", sv("envelope.cruise_speed.value", 40)),
    ("zero speed", sv("envelope.max_speed.value", 0)),
    ("negative climb", sv("envelope.max_climb.value", -1)),
    ("speed above what a scenario allows", sv("envelope.max_speed.value", 500)),
    ("wrong envelope unit", sv("envelope.max_speed.unit", "km/h")),
    ("unknown envelope field", lambda d: d["envelope"].update(max_range=drop_value())),
    ("missing signature", drop("signature.rcs")),
    ("unknown signature", lambda d: d["signature"].update(payload=dict(d["signature"]["rcs"]))),
    ("wrong signature unit", sv("signature.rcs.unit", "m")),
    ("emits not a flag", sv("signature.emits.value", 0.5)),
    ("band outside the plan", sv("signature.band.value", 9)),
    ("fractional band", sv("signature.band.value", 1.5)),
    ("no harmonics", sv("signature.harmonics.value", 0)),
    ("fractional harmonics", sv("signature.harmonics.value", 2.5)),
    ("zero size", sv("signature.size.value", 0)),
    ("negative contrast", sv("signature.contrast.value", -1)),
    ("negative swing", sv("signature.aspect_swing.value", -1)),
    ("negative rpm", sv("signature.rpm.value", -5)),
    ("no summary", drop("summary")),
    ("missing hindi", drop("title.hi")),
    ("extra field", sv("payload", "x")),
    ("bad id", sv("id", "Rotary Small")),
]


def drop_value() -> dict[str, Any]:
    return {"value": 1, "unit": "m", "source_id": "F01", "verified": False}


@pytest.mark.parametrize(("label", "mutate"), REFUSED, ids=[label for label, _ in REFUSED])
def test_the_contract_refuses(label: str, mutate: Callable[[dict[str, Any]], None]) -> None:
    data = copy.deepcopy(raw())
    mutate(data)
    with pytest.raises(ValidationError):
        ThreatClass.model_validate(data)


def test_a_clutter_class_must_have_no_group_and_the_clutter_disposition() -> None:
    data = copy.deepcopy(raw("bird"))
    data["uas_group"] = "1"
    with pytest.raises(ValidationError, match="no UAS group"):
        ThreatClass.model_validate(data)
    data = copy.deepcopy(raw("bird"))
    data["default_disposition"] = "hostile"
    with pytest.raises(ValidationError, match="clutter disposition"):
        ThreatClass.model_validate(data)


def test_the_envelope_converts_to_scenario_limits_and_is_immutable() -> None:
    cls = threat_class("fpv-small")
    limits = cls.envelope.to_limits()
    assert (limits.max_speed_mps, limits.max_turn_rate_dps) == (35, 180)
    assert (limits.min_altitude_m, limits.max_altitude_m) == (2, 300)
    with pytest.raises(ValidationError):
        cls.envelope.max_speed = cls.envelope.cruise_speed  # type: ignore[misc]


def test_the_signature_names_are_the_ones_the_profiles_use() -> None:
    assert set(threat_class("bird").signature) == set(SIGNATURE_UNITS)
    assert set(SIGNATURE_UNITS) == {
        "rcs",
        "aspect_swing",
        "size",
        "contrast",
        "contrast_eo",
        "emits",
        "emitter_power",
        "band",
        "hop_rate",
        "source_level",
        "blades",
        "rpm",
        "harmonics",
    }


# ------------------------------------------------------------------------- the loader


def test_the_loader_refuses_a_recognition_class_outside_the_recognition_set(
    tmp_path: Path,
) -> None:
    directory = copy_threats(tmp_path)
    rewrite(directory, "civil-drone", sv("recognition_class", "quadcopter"))
    with pytest.raises(CatalogueError, match="civil-drone: recognition_class 'quadcopter'"):
        load_catalogue(directory)


def test_a_recognition_class_must_itself_be_recognised_as_itself(tmp_path: Path) -> None:
    directory = copy_threats(tmp_path)
    rewrite(directory, "civil-drone", sv("recognition_class", "decoy-small"))  # a look-alike
    with pytest.raises(CatalogueError, match="recognised as itself"):
        load_catalogue(directory)


def test_the_loader_refuses_a_file_not_named_for_its_class(tmp_path: Path) -> None:
    directory = copy_threats(tmp_path)
    (directory / "kite.v1.yaml").rename(directory / "paper-kite.v1.yaml")
    with pytest.raises(CatalogueError, match="must be named kite.v1.yaml"):
        load_catalogue(directory)


def test_the_loader_refuses_a_malformed_class_and_names_the_file(tmp_path: Path) -> None:
    directory = copy_threats(tmp_path)
    rewrite(directory, "bird", drop("signature.rcs.source_id"))
    with pytest.raises(CatalogueError, match=r"bird\.v1\.yaml"):
        load_catalogue(directory)
    rewrite(directory, "bird", lambda d: d.update(contract="nope.v1"))
    with pytest.raises(CatalogueError, match="unknown contract"):
        load_catalogue(directory)


def test_the_loader_refuses_a_pack_that_is_not_a_threat_class(tmp_path: Path) -> None:
    directory = copy_threats(tmp_path)
    profile = REPO / "packs" / "sensor-profiles" / "radar-generic-s.v1.yaml"
    shutil.copy(profile, directory / "radar-generic-s.v1.yaml")
    with pytest.raises(CatalogueError, match="not a threat class"):
        load_catalogue(directory)


def test_the_loader_refuses_an_empty_or_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(CatalogueError, match="no threat class packs"):
        load_catalogue(tmp_path)
    with pytest.raises(CatalogueError, match="no threat class packs"):
        load_catalogue(tmp_path / "absent")


def test_the_default_directory_is_the_packs_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PACKS_DIR", str(REPO / "packs"))
    assert load_catalogue().ids == IDS


def test_lookups_of_an_unknown_class_raise_key_error() -> None:
    catalogue = load_catalogue()
    for lookup in (catalogue.get, catalogue.recognition_class, catalogue.limits_for):
        with pytest.raises(KeyError, match="no class 'tank'"):
            lookup("tank")


def test_a_catalogue_orders_its_classes_by_id() -> None:
    shuffled = Catalogue([threat_class(c) for c in reversed(IDS)])
    assert shuffled.ids == IDS


# ------------------------------------------------------------------------- scenario check


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: p.name)
def test_every_shipped_scenario_passes_the_catalogue_check(path: Path) -> None:
    spec = load_pack(path)
    assert isinstance(spec, ScenarioSpec)
    assert load_catalogue().check_scenario(spec) == []


def scenario_with(**changes: Any) -> ScenarioSpec:
    data = load_pack(SCENARIOS[-1]).model_dump(mode="json")  # kestrel: flat ground
    threat = data["threats"][0]
    for key, value in changes.items():
        if key == "limits":
            threat["limits"].update(value)
        else:
            threat[key] = value
    return ScenarioSpec.model_validate(data)


def test_the_check_finds_a_threat_of_an_unknown_class() -> None:
    problems = load_catalogue().check_scenario(scenario_with(class_id="tank"))
    assert problems == ["threat contact-a: class 'tank' is not in the catalogue"]


@pytest.mark.parametrize(
    ("limits", "text"),
    [
        ({"max_speed_mps": 19}, "max_speed_mps 19 is above the rotary-small envelope (18)"),
        ({"max_accel_mps2": 5}, "max_accel_mps2"),
        ({"max_climb_mps": 6}, "max_climb_mps"),
        ({"max_descent_mps": 4}, "max_descent_mps"),
        ({"max_turn_rate_dps": 100}, "max_turn_rate_dps"),
        ({"min_altitude_m": 4}, "min_altitude_m 4 is below"),
        ({"max_altitude_m": 500}, "max_altitude_m 500 is above"),
    ],
)
def test_the_check_finds_limits_wider_than_the_class_envelope(
    limits: dict[str, float], text: str
) -> None:
    problems = load_catalogue().check_scenario(scenario_with(limits=limits))
    assert len(problems) == 1 and text in problems[0]


def test_narrower_limits_are_allowed() -> None:
    narrower = {"max_speed_mps": 17, "min_altitude_m": 10, "max_altitude_m": 300}
    assert load_catalogue().check_scenario(scenario_with(limits=narrower)) == []


def test_the_check_finds_a_disposition_the_category_cannot_have() -> None:
    catalogue = load_catalogue()
    problems = catalogue.check_scenario(scenario_with(disposition="clutter"))
    assert problems and "does not fit a drone class" in problems[0]
    bird = catalogue.limits_for("bird").model_dump(mode="json")
    problems = catalogue.check_scenario(
        scenario_with(class_id="bird", disposition="hostile", limits=bird)
    )
    assert problems and "does not fit a clutter class" in problems[0]


# ------------------------------------------------------------------------- the document

BEGIN = "<!-- BEGIN GENERATED: catalogue -->"
END = "<!-- END GENERATED: catalogue -->"


def test_the_generated_tables_in_the_document_match_the_generator() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert text.count(BEGIN) == 1 and text.count(END) == 1
    block = text.split(BEGIN)[1].split(END)[0]
    assert block.strip() == markdown(load_catalogue()).strip(), (
        "docs/THREAT_CATALOGUE.md is stale: regenerate with `python -m sim.catalogue`"
    )


def test_the_generator_prints_the_tables(capsys: pytest.CaptureFixture[str]) -> None:
    assert catalogue_module.main() == 0
    out = capsys.readouterr().out
    assert out == markdown(load_catalogue())
    assert out.count("\n| `") == 4 * 11  # one row per class in each of the four tables
    assert "0.39 [D12]" in out and "none" in out  # a non-F01 source is shown; nothing verified


def test_the_document_has_the_sections_the_brief_requires() -> None:
    text = DOC.read_text(encoding="utf-8")
    for heading in ("Purpose", "Honesty", "Classes", "Sensor profiles", "Look-alike", "Not in"):
        assert re.search(rf"^##+ .*{heading}", text, re.MULTILINE | re.IGNORECASE), heading
    for phrase in ("X01", "Q-11", "F01", "fictional"):
        assert phrase in text, phrase
    cited = set(re.findall(r"\b([DGWXF][0-9]{2})\b", text))
    assert cited <= register_ids(REGISTER)


# ------------------------------------------------------------------------- sim-check


def packs_copy(tmp_path: Path) -> Path:
    """A copy of the packs (terrain linked, not copied) that a test may damage."""
    target = tmp_path / "packs"
    shutil.copytree(REPO / "packs", target, ignore=shutil.ignore_patterns("terrain"))
    (target / "terrain").symlink_to(REPO / "packs" / "terrain")
    return target


def test_the_sim_check_reports_the_catalogue(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.simcheck import run_sim_check

    monkeypatch.setenv("PACKS_DIR", str(REPO / "packs"))
    assert "11 threat classes" in run_sim_check(20)


def test_the_sim_check_fails_when_a_scenario_leaves_the_catalogue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.simcheck import run_sim_check

    root = packs_copy(tmp_path)
    path = root / "scenarios" / "kestrel-dawn-approach.v1.json"
    data = json.loads(path.read_text("utf-8"))
    data["threats"][0]["limits"]["max_speed_mps"] = 25
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("PACKS_DIR", str(root))
    with pytest.raises(ValueError, match="kestrel-dawn-approach.v1.json: threat contact-a"):
        run_sim_check(20)


def test_the_sim_check_fails_when_a_profile_drifts_from_the_catalogue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.simcheck import run_sim_check

    root = packs_copy(tmp_path)
    path = root / "sensor-profiles" / "radar-generic-s.v1.yaml"
    path.write_text(
        path.read_text("utf-8").replace("rcs_kite: { value: -30", "rcs_kite: { value: -12"),
        encoding="utf-8",
    )
    monkeypatch.setenv("PACKS_DIR", str(root))
    with pytest.raises(ValueError, match="rcs_kite is -12, the catalogue says -30"):
        run_sim_check(20)


def test_the_sim_check_fails_without_the_threat_packs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.simcheck import run_sim_check

    root = packs_copy(tmp_path)
    shutil.rmtree(root / "threats")
    monkeypatch.setenv("PACKS_DIR", str(root))
    with pytest.raises(CatalogueError, match="no threat class packs"):
        run_sim_check(20)
