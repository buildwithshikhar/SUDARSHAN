"""Oracle solvability across the whole request space: 50 requests on every push, 1,000 nightly
(`python -m app.cli scenario-sweep --count 1000`). Each request is generated and the stored spec is
cleared again by a fresh oracle run: "verified solvable by test run"."""

import os

import pytest
from typer.testing import CliRunner

from app.cli import cli
from app.scenarios.request import ARCHETYPES, TERRAINS
from app.scenarios.sweep import check_one, run_sweep, sweep_request

COUNT = int(os.environ.get("SOLVABILITY_SEEDS", "50"))
JOBS = int(os.environ.get("SOLVABILITY_JOBS", "2"))


def test_the_sweep_spreads_its_requests_over_the_whole_space() -> None:
    requests = [sweep_request(i) for i in range(120)]
    assert {r.terrain for r in requests} == set(TERRAINS)
    assert {a for r in requests for a in r.threat_mix} == set(ARCHETYPES)
    assert len({r.time_of_day for r in requests}) == 4 and len({r.weather for r in requests}) == 5
    assert sweep_request(7) == sweep_request(7) and sweep_request(7) != sweep_request(8)
    assert all(0 <= r.difficulty.degradation <= 60 for r in requests)


def test_a_single_request_is_generated_and_cleared_again() -> None:
    result = check_one(3)
    assert result.ok and result.detail.startswith("gen-") and result.attempts >= 1


def test_the_sweep_command_reports_and_exits_zero_when_all_pass() -> None:
    out = CliRunner().invoke(cli, ["scenario-sweep", "--count", "2", "--start", "3", "--jobs", "1"])
    assert out.exit_code == 0, out.output
    assert "2 of 2 verified solvable by test run" in out.output


def test_the_sweep_command_exits_one_when_a_request_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.scenarios import sweep

    monkeypatch.setattr(
        sweep, "check_one", lambda i: sweep.SweepResult(i, False, "no scenario", 5, 3)
    )
    out = CliRunner().invoke(cli, ["scenario-sweep", "--count", "1"])
    assert out.exit_code == 1 and "request 0: no scenario" in out.output


@pytest.mark.solvability
def test_every_request_of_the_sweep_is_verified_solvable_by_test_run() -> None:
    results = run_sweep(COUNT, jobs=JOBS)
    failed = [f"{r.index}: {r.detail}" for r in results if not r.ok]
    assert not failed, "\n".join(failed)
