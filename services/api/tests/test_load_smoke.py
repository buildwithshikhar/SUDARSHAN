"""The load harness itself: 3 scripted clients for 4 seconds against a server it starts."""

import asyncio
import json
from pathlib import Path

import pytest

from tests.load.run_load import Config, main, render, run_load


def test_the_load_harness_runs_and_reports() -> None:
    report = asyncio.run(run_load(Config(clients=3, seconds=4)))
    agg = report["aggregate"]
    assert agg["dropped_sessions"] == 0, report["clients"]
    assert agg["verified_sessions"] == 3
    assert 15 < agg["frame_rate_hz"]["min"] <= agg["frame_rate_hz"]["max"] < 25
    assert agg["interframe_ms"]["count"] > 150 and agg["tick_gaps"] == 0
    assert agg["ping_rtt_ms"]["count"] >= 6 and agg["ping_rtt_ms"]["p99"] < 500
    stats = report["server"]["stats"]
    assert stats["completed_total"] == 3 and stats["lag_drops"] == 0
    assert stats["tick_jitter_ms"]["count"] > 150
    assert report["server"]["rss_mb"] > 20
    text = render(report)
    assert "dropped sessions : 0" in text and "ping RTT" in text and "server tick jitter" in text


def test_the_command_line_writes_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "report.json"
    code = main(["--clients", "2", "--seconds", "2", "--json", str(out)])
    assert code == 0
    report = json.loads(out.read_text())
    assert report["config"] == {
        "clients": 2,
        "seconds": 2.0,
        "scenario": "harrier-morning-watch",
        "own_server": True,
    }
    assert len(report["clients"]) == 2 and "frame rate" in capsys.readouterr().out
