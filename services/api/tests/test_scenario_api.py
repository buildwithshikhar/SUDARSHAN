"""The scenario library, the tools and the generator over HTTP: roles, shapes, storage."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.paths import packs_root
from app.models import TrainingSession, User
from app.routers import scenarios as router
from app.scenarios.generator import GenerationFailed
from app.scenarios.insights import Insights
from app.scenarios.request import GeneratorRequest

from .live_support import EMAILS, login

HARRIER = "harrier-morning-watch"
LOW = {
    "seed": 3,
    "terrain": "flat",
    "difficulty": {
        "threat_load": 10,
        "ambiguity": 10,
        "speed": 30,
        "stealth": 20,
        "degradation": 0,
    },
    "threat_mix": ["single"],
}


def pack_yaml(name: str) -> str:
    return (packs_root() / "scenarios" / f"{name}.v1.yaml").read_text("utf-8")


def curriculum_yaml() -> str:
    return pack_yaml("curriculum-01-first-contact")


@pytest.fixture
def author(live_client: TestClient) -> tuple[TestClient, dict[str, str]]:
    return live_client, login(live_client, "instructor")


# ----------------------------------------------------------------------------- roles


def test_the_tools_need_an_instructor_or_an_administrator(live_client: TestClient) -> None:
    assert live_client.get("/api/v1/scenario-library").status_code == 401
    csrf = login(live_client, "trainee")
    assert live_client.get("/api/v1/scenario-library").status_code == 403
    body = {"yaml": "x"}
    assert (
        live_client.post("/api/v1/scenario-tools/validate", json=body, headers=csrf).status_code
        == 403
    )
    assert live_client.get("/api/v1/generator/archive").status_code == 403
    login(live_client, "admin")
    assert live_client.get("/api/v1/scenario-library").status_code == 200


# ----------------------------------------------------------------------------- library


def test_the_library_lists_packs_in_curriculum_order_with_their_facts(author: Any) -> None:
    client, _ = author
    rows = client.get("/api/v1/scenario-library").json()
    ids = [r["id"] for r in rows]
    assert HARRIER in ids and "curriculum-01-first-contact" in ids
    curriculum = [r for r in rows if r["curriculum_order"] is not None]
    assert [r["curriculum_order"] for r in curriculum] == sorted(
        r["curriculum_order"] for r in curriculum
    )
    assert ids.index("curriculum-01-first-contact") < ids.index(HARRIER)  # curriculum first
    harrier = next(r for r in rows if r["id"] == HARRIER)
    assert harrier["origin"] == "scripted" and harrier["terrain"] == "flat"
    assert harrier["hostile_count"] == 1 and harrier["contact_count"] == 5
    assert harrier["solvability"] == {
        "status": "unchecked",
        "oracle_score": None,
        "checked_at_run": None,
    }
    assert harrier["can_delete"] is False and harrier["rule_pack"]["id"] == "training-baseline"
    kestrel = next(r for r in rows if r["id"] == "kestrel-dawn-approach")
    assert kestrel["origin"] == "example"
    assert set(harrier) >= {
        "title",
        "summary",
        "tags",
        "difficulty",
        "time_of_day",
        "weather",
        "degraded",
    }


def test_a_known_verdict_shows_in_the_library(author: Any) -> None:
    client, _ = author
    insights: Insights = client.app.state.insights
    entry = client.app.state.live.catalog.get(HARRIER)
    insights.verdict(entry.spec)
    row = next(r for r in client.get("/api/v1/scenario-library").json() if r["id"] == HARRIER)
    assert row["solvability"]["status"] == "verified" and row["solvability"]["oracle_score"] > 0.8


def test_one_scenario_with_its_text_lint_and_checks(author: Any) -> None:
    client, _ = author
    item = client.get(f"/api/v1/scenario-library/{HARRIER}").json()
    assert item["spec"]["id"] == HARRIER and item["yaml"].startswith("# Fictional scenario")
    assert [c["name"] for c in item["checks"]] == [
        "hostile-presented",
        "hostile-answered",
        "no-failures",
        "oracle-score",
    ]
    assert item["solvability_wording"] == "verified solvable by test run"
    assert set(item["features"]) >= {"threat_count", "stealth"} and item["code"] is None
    assert client.get("/api/v1/scenario-library/nothing").status_code == 404


# ----------------------------------------------------------------------------- tools


def test_validate_reports_errors_with_their_line(author: Any) -> None:
    client, csrf = author
    ok = client.post(
        "/api/v1/scenario-tools/validate", json={"yaml": curriculum_yaml()}, headers=csrf
    )
    body = ok.json()
    assert (
        body["valid"] is True
        and body["errors"] == []
        and body["spec"]["id"] == "curriculum-01-first-contact"
    )
    assert all(i["severity"] in ("error", "warning") for i in body["lint"])
    text = curriculum_yaml().replace("duration_s: ", "duration_s: not-a-number #", 1)
    bad = client.post("/api/v1/scenario-tools/validate", json={"yaml": text}, headers=csrf).json()
    assert bad["valid"] is False and bad["spec"] is None and bad["lint"] == []
    line = next(i for i, ln in enumerate(text.splitlines(), 1) if "not-a-number" in ln)
    assert bad["errors"][0]["line"] == line and bad["errors"][0]["code"].startswith("schema.")


def test_check_runs_the_oracle_and_the_diversity_filter(author: Any) -> None:
    client, csrf = author
    body = client.post(
        "/api/v1/scenario-tools/check", json={"yaml": curriculum_yaml()}, headers=csrf
    ).json()
    assert body["valid"] and body["solvability"]["ran"] and body["solvability"]["solved"]
    assert body["solvability"]["wording"] == "verified solvable by test run"
    assert len(body["solvability"]["checks"]) == 4 and body["solvability"]["seconds"] >= 0
    assert body["diversity"] == {
        "history_size": 0,
        "novelty": None,
        "threshold": 0.15,
        "passes": None,
        "nearest": [],
    }
    assert set(body["features"]) >= {"threat_count"}


def test_check_of_a_broken_scenario_does_not_run_the_oracle(author: Any) -> None:
    client, csrf = author
    body = client.post("/api/v1/scenario-tools/check", json={"yaml": "a: [1"}, headers=csrf).json()
    assert body["valid"] is False and body["solvability"]["ran"] is False
    assert body["solvability"]["wording"] == "not verified solvable" and body["errors"]


def test_check_compares_with_what_the_user_has_played(author: Any) -> None:
    client, csrf = author
    with Session(client.app.state.engine) as db:
        user_id = db.scalar(select(User.id).where(User.email == EMAILS["instructor"]))
        assert user_id is not None
        db.add(
            TrainingSession(
                user_id=user_id,
                scenario_id="curriculum-01-first-contact",
                scenario_version="1.0.0",
                seed=1,
                status="ended",
            )
        )
        db.commit()
    body = client.post(
        "/api/v1/scenario-tools/check", json={"yaml": curriculum_yaml()}, headers=csrf
    ).json()
    assert body["diversity"]["history_size"] == 1
    assert body["diversity"]["novelty"] == 0.0 and body["diversity"]["passes"] is False


def test_preview_returns_what_happened_with_the_truth_paths(author: Any) -> None:
    client, csrf = author
    body = client.post(
        "/api/v1/scenario-tools/preview", json={"yaml": curriculum_yaml()}, headers=csrf
    ).json()
    assert body["ok"] and body["finished_s"] > 0 and body["oracle_score"] > 0.8
    hostile = [c for c in body["contacts"] if c["disposition"] == "hostile"]
    assert hostile and all(c["first_report_s"] is not None and c["answered_s"] for c in hostile)
    assert body["path"]["step_s"] == 2.0 and any(t["points"] for t in body["path"]["threats"])
    assert body["coverage"] and body["coverage"][0]["sensors"]
    bad = client.post("/api/v1/scenario-tools/preview", json={"yaml": "a: [1"}, headers=csrf)
    assert bad.status_code == 422 and bad.json()["detail"]["errors"]


# ----------------------------------------------------------------------------- saving


def authored(text: str, new_id: str) -> str:
    return text.replace("id: curriculum-01-first-contact", f"id: {new_id}", 1)


def test_an_authored_scenario_is_saved_listed_playable_and_deletable(author: Any) -> None:
    client, csrf = author
    text = authored(curriculum_yaml(), "my-first-watch")
    saved = client.post(
        "/api/v1/scenario-library", json={"yaml": text, "tags": ["mine"]}, headers=csrf
    )
    assert saved.status_code == 201, saved.text
    row = saved.json()
    assert row["id"] == "my-first-watch" and row["origin"] == "authored" and row["tags"] == ["mine"]
    assert row["can_delete"] is True and row["solvability"]["status"] == "verified"
    assert row["curriculum_order"] == 1  # kept from the text
    listed = {r["id"]: r for r in client.get("/api/v1/scenario-library").json()}
    assert listed["my-first-watch"]["solvability"]["status"] == "verified"
    assert "my-first-watch" in {s["id"] for s in client.get("/api/v1/scenarios").json()}
    item = client.get("/api/v1/scenario-library/my-first-watch").json()
    assert item["yaml"].startswith("# Fictional scenario") and item["checks"]
    assert client.delete("/api/v1/scenario-library/my-first-watch", headers=csrf).status_code == 204
    assert client.delete("/api/v1/scenario-library/my-first-watch", headers=csrf).status_code == 404


def test_saving_refuses_what_it_should(author: Any) -> None:
    client, csrf = author

    def post(text: str) -> Any:
        return client.post("/api/v1/scenario-library", json={"yaml": text}, headers=csrf)

    assert post("a: [1").status_code == 422
    assert post(authored(curriculum_yaml(), "gen-1-0-0-1-abc")).status_code == 422
    assert post(curriculum_yaml()).status_code == 409  # a shipped scenario has that id
    broken = authored(curriculum_yaml(), "no-cover").replace("sensors:", "sensors_gone:", 1)
    assert post(broken).status_code == 422
    assert client.delete(f"/api/v1/scenario-library/{HARRIER}", headers=csrf).status_code == 403
    assert client.delete("/api/v1/scenario-library/zzz", headers=csrf).status_code == 404


def test_only_the_owner_or_an_administrator_changes_a_saved_scenario(
    live_client: TestClient,
) -> None:
    csrf = login(live_client, "instructor")
    text = authored(curriculum_yaml(), "owned-watch")
    assert (
        live_client.post("/api/v1/scenario-library", json={"yaml": text}, headers=csrf).status_code
        == 201
    )
    live_client.post("/api/v1/auth/logout", headers=csrf)
    other = login(live_client, "admin")
    row = next(
        r for r in live_client.get("/api/v1/scenario-library").json() if r["id"] == "owned-watch"
    )
    assert row["can_delete"] is True  # an administrator may
    assert (
        live_client.delete("/api/v1/scenario-library/owned-watch", headers=other).status_code == 204
    )


# ----------------------------------------------------------------------------- generator


def test_generate_from_a_request_and_from_its_code(author: Any) -> None:
    client, csrf = author
    one = client.post("/api/v1/generator/generate", json={"request": LOW}, headers=csrf)
    assert one.status_code == 200, one.text
    made = one.json()
    assert made["solvability_wording"] == "verified solvable by test run" and made["saved"] is False
    assert made["spec"]["meta"]["origin"] == "generated" and made["code"].startswith("SD1-")
    assert [c["name"] for c in made["checks"]][:4] == [
        "hostile-presented", "hostile-answered", "no-failures", "oracle-score",
    ]  # fmt: skip
    again = client.post(
        "/api/v1/generator/generate", json={"code": made["code"]}, headers=csrf
    ).json()
    assert again["spec_sha256"] == made["spec_sha256"] and again["spec"] == made["spec"]
    assert again["id"] == made["id"]


def test_generate_and_keep_makes_a_playable_scenario(author: Any) -> None:
    client, csrf = author
    made = client.post(
        "/api/v1/generator/generate", json={"request": LOW, "save": True}, headers=csrf
    ).json()
    assert made["saved"] is True
    row = next(r for r in client.get("/api/v1/scenario-library").json() if r["id"] == made["id"])
    assert row["origin"] == "generated" and row["solvability"]["status"] == "verified"
    item = client.get(f"/api/v1/scenario-library/{made['id']}").json()
    assert item["code"] == made["code"] and item["request"]["seed"] == 3
    assert made["id"] in {s["id"] for s in client.get("/api/v1/scenarios").json()}


def test_generate_needs_exactly_one_of_request_and_code(author: Any) -> None:
    client, csrf = author
    url = "/api/v1/generator/generate"
    assert client.post(url, json={}, headers=csrf).status_code == 422
    assert (
        client.post(url, json={"request": LOW, "code": "SD1-AAAA"}, headers=csrf).status_code == 422
    )
    bad = client.post(url, json={"code": "nonsense"}, headers=csrf)
    assert bad.status_code == 422 and "code" in bad.json()["detail"].lower()


def test_a_failed_generation_is_a_422_with_the_reasons(
    author: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, csrf = author

    def fail(request: GeneratorRequest, history: Any = ()) -> Any:
        raise GenerationFailed(request, 5, {"oracle:no-failures": 5})

    monkeypatch.setattr(router, "generate", fail)
    response = client.post("/api/v1/generator/generate", json={"request": LOW}, headers=csrf)
    assert response.status_code == 422 and "oracle:no-failures x5" in response.json()["detail"]
    batch = client.post(
        "/api/v1/generator/batch", json={"request": LOW, "count": 2}, headers=csrf
    ).json()
    assert batch["results"] == [] and [f["seed"] for f in batch["failures"]] == [3, 4]


def test_a_batch_varies_the_seed_and_keeps_each_different(author: Any) -> None:
    client, csrf = author
    body = client.post(
        "/api/v1/generator/batch", json={"request": LOW, "count": 3, "save": True}, headers=csrf
    ).json()
    assert [r["request"]["seed"] for r in body["results"]] == [3, 4, 5] and body["failures"] == []
    assert len({r["id"] for r in body["results"]}) == 3 and all(r["saved"] for r in body["results"])
    assert (
        client.post(
            "/api/v1/generator/batch", json={"request": LOW, "count": 13}, headers=csrf
        ).status_code
        == 422
    )


def test_the_archive_holds_the_solved_scenarios_the_instance_knows(author: Any) -> None:
    client, csrf = author
    empty = client.get("/api/v1/generator/archive").json()
    assert empty["cells"] == [] and empty["metrics"]["filled"] == 0
    insights: Insights = client.app.state.insights
    for name in (HARRIER, "heron-ridge-low-approach"):
        insights.verdict(client.app.state.live.catalog.get(name).spec)
    client.post("/api/v1/generator/generate", json={"request": LOW, "save": True}, headers=csrf)
    body = client.get("/api/v1/generator/archive?x=approach_speed&y=threat_count").json()
    assert body["metrics"]["filled"] >= 2 and body["metrics"]["total"] == 144
    assert body["metrics"]["coverage"] > 0 and body["metrics"]["qd_score"] > 1.5
    assert body["heatmap"]["x_axis"] == "approach_speed" and len(body["heatmap"]["values"]) == 6
    assert [a["name"] for a in body["axes"]] == ["threat_count", "id_ambiguity", "approach_speed"]
    assert client.get("/api/v1/generator/archive?x=nope&y=threat_count").status_code == 422


def test_codes_encode_and_decode(author: Any) -> None:
    client, csrf = author
    coded = client.post("/api/v1/generator/code", json={"request": LOW}, headers=csrf).json()
    assert coded["code"].startswith("SD1-") and coded["generator_version"] == "1.0.0"
    back = client.get("/api/v1/generator/code", params={"code": coded["code"]}).json()
    assert back["request"]["seed"] == 3 and back["matches"] is True
    assert back["current_version"] == "1.0.0"
    assert client.get("/api/v1/generator/code", params={"code": "SD1-NOPE"}).status_code == 422
