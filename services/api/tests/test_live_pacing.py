"""A run faster than real time waits for a client that falls behind; it does not skip frames."""

import time

from fastapi.testclient import TestClient

from tests.live_support import WINDOW, connect, create_session, fast, login


def test_a_fast_run_waits_for_a_slow_reader_and_drops_nothing(live_client: TestClient) -> None:
    csrf = login(live_client)
    fast(live_client, 100)
    row = create_session(live_client, csrf)
    manager = live_client.app.state.live  # type: ignore[attr-defined]
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "start"})
        time.sleep(0.5)  # at 100x an unchecked run would be 1,000 ticks on by now
        ticks = [frame["tick"] for frame in sock.frames(600)]
        assert ticks == list(range(ticks[0], ticks[0] + 600)), "a frame was skipped"
        assert ticks[0] < 400, "the run did not wait for the reader"
        assert manager.frames_dropped == 0
    assert WINDOW < 100  # the writer stalls before the queue the loop watches is full
