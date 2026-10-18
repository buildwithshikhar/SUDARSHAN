"""The load harness itself: 3 scripted clients for a fixed number of frames against a server it starts."""

import asyncio
import json
from pathlib import Path

import pytest

from tests.load.run_load import (
    PING_EVERY_FRAMES,
    ClientResult,
    Config,
    aggregate,
    main,
    render,
    run_load,
)

FRAMES = 120


def test_the_load_harness_runs_and_reports() -> None:
    # Frame-count mode: the run is as long as it needs to be, and nothing asserted below is a
    # speed. How fast frames arrive is machine load and is covered by the statistics test.
    report = asyncio.run(run_load(Config(clients=3, frames=FRAMES)))
    agg = report["aggregate"]
    assert agg["dropped_sessions"] == 0, report["clients"]
    assert agg["verified_sessions"] == 3
    assert all(c["frames"] == FRAMES and c["tick_gaps"] == 0 for c in report["clients"])
    assert agg["interframe_ms"]["count"] == 3 * (FRAMES - 1) and agg["tick_gaps"] == 0
    assert agg["ping_rtt_ms"]["count"] >= 3 * (FRAMES // PING_EVERY_FRAMES - 1)
    stats = report["server"]["stats"]
    assert stats["completed_total"] == 3
    assert stats["tick_jitter_ms"]["count"] >= FRAMES and "lag_drops" in stats
    assert report["server"]["rss_mb"] > 20
    text = render(report)
    assert "dropped sessions : 0" in text and "ping RTT" in text and "server tick jitter" in text
    assert f"{FRAMES} frames" in text


def test_the_statistics_are_computed_from_the_recorded_samples() -> None:
    # Timing figures from synthetic arrivals, so the arithmetic is checked without a clock.
    a = ClientResult(1, frames=100, seconds=5.0, dt_ms=[50.0] * 99, jitter_ms=[0.0] * 99)
    b = ClientResult(2, frames=90, seconds=5.0, dt_ms=[55.0] * 89, jitter_ms=[5.0] * 89)
    b.rtt_ms, b.tick_gaps, b.verified = [2.0, 4.0], 3, True
    agg = aggregate([a, b])
    assert agg["frame_rate_hz"] == {"min": 18.0, "mean": 19.0, "max": 20.0}
    assert agg["tick_gaps"] == 3 and agg["verified_sessions"] == 1
    assert agg["interframe_ms"]["count"] == 188 and agg["jitter_ms"]["max"] == 5.0
    assert agg["ping_rtt_ms"]["count"] == 2


def test_the_command_line_writes_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "report.json"
    code = main(["--clients", "2", "--frames", "40", "--json", str(out)])
    assert code == 0
    report = json.loads(out.read_text())
    assert report["config"] == {
        "clients": 2,
        "seconds": 300.0,
        "frames": 40,
        "scenario": "harrier-morning-watch",
        "own_server": True,
    }
    assert len(report["clients"]) == 2 and "frame rate" in capsys.readouterr().out
