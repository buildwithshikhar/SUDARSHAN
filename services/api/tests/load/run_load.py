"""Load test for the live session: scripted trainees play the real protocol against a server.

    uv run python -m tests.load.run_load --clients 12 --seconds 300 [--url http://host:port] [--json out.json]

With no `--url` the script starts the API itself (uvicorn in a subprocess on a free port, with a
temporary SQLite database and 12 new trainee accounts) and stops it afterwards. With `--url` it
drives a running server: the accounts `load-1@load.example` .. `load-N@load.example` must exist
(`python -m app.cli create-user`) and share `--password`; pass `--admin-email` and
`--admin-password` to also read the server's tick statistics from `/api/v1/sessions/stats`.

Each client signs in, creates a session, opens the WebSocket, starts, and plays: it classifies,
assesses, cues the EO sensor, reports and responds on the tracks that appear, and pings once a
second. It reports its frame rate, the arrival jitter of its frames, ping round trips and whether
its session survived. The generator is a single asyncio process, so on a small machine part of the
jitter it measures is its own.
"""

import argparse
import asyncio
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import msgpack  # type: ignore[import-untyped]
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from app.live.manager import percentiles

API_ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "correct-horse-battery-load"
FRAME_MS = 50.0
SCENARIO = "harrier-morning-watch"


@dataclass
class Config:
    clients: int = 12
    seconds: float = 300.0
    url: str | None = None
    password: str = PASSWORD
    admin_email: str | None = None
    admin_password: str | None = None
    scenario: str = SCENARIO
    # When set, each client plays until it has received this many frames and pings every
    # `PING_EVERY_FRAMES` frames, so a run's length and content do not depend on the wall clock.
    # `seconds` then only bounds a hung run.
    frames: int | None = None


PING_EVERY_FRAMES = 20
HANG_GUARD_S = 300.0


@dataclass
class ClientResult:
    index: int
    frames: int = 0
    seconds: float = 0.0
    first_tick: int = 0
    last_tick: int = 0
    tick_gaps: int = 0
    actions: int = 0
    acks_ok: int = 0
    acks_refused: int = 0
    events: int = 0
    dt_ms: list[float] = field(default_factory=list)
    jitter_ms: list[float] = field(default_factory=list)
    rtt_ms: list[float] = field(default_factory=list)
    dropped: bool = False
    error: str | None = None
    ended_status: str | None = None
    verified: bool = False

    def summary(self) -> dict[str, Any]:
        return {
            "client": self.index,
            "frames": self.frames,
            "frame_rate_hz": round(self.frames / self.seconds, 2) if self.seconds else 0.0,
            "ticks": self.last_tick - self.first_tick,
            "tick_gaps": self.tick_gaps,
            "interframe_ms": percentiles(self.dt_ms),
            "jitter_ms": percentiles(self.jitter_ms),
            "ping_rtt_ms": percentiles(self.rtt_ms),
            "actions": self.actions,
            "acks_ok": self.acks_ok,
            "acks_refused": self.acks_refused,
            "events": self.events,
            "dropped": self.dropped,
            "error": self.error,
            "ended": self.ended_status,
            "verified": self.verified,
        }


def email_of(index: int) -> str:
    return f"load-{index}@load.example"


# ----------------------------------------------------------------------------- one scripted client


async def play(
    config: Config, base: str, index: int, ready: asyncio.Barrier, result: ClientResult
) -> None:
    """Sign in, create a session, connect, start, play for `config.seconds`, end."""
    try:
        async with httpx.AsyncClient(base_url=base, timeout=30) as http:
            login = await http.post(
                "/api/v1/auth/login", json={"email": email_of(index), "password": config.password}
            )
            login.raise_for_status()
            csrf = {"X-CSRF-Token": login.json()["csrf"]}
            created = await http.post(
                "/api/v1/sessions", json={"scenario_id": config.scenario}, headers=csrf
            )
            created.raise_for_status()
            session_id = created.json()["id"]
            headers = {"Cookie": f"session={http.cookies.get('session')}", "Origin": base}
            ws_url = base.replace("http", "ws", 1) + f"/api/v1/sessions/{session_id}/ws"
            async with connect(ws_url, additional_headers=headers, max_size=2**22) as ws:
                try:
                    await _session(config, ws, ready, result)
                except ConnectionClosed as closed:
                    result.dropped = True
                    result.error = f"closed {closed.rcvd.code if closed.rcvd else '?'}"
            status = (await http.get(f"/api/v1/sessions/{session_id}")).json()["status"]
            result.ended_status = result.ended_status or status
            result.dropped = result.dropped or status not in ("ended", "running")
    except Exception as error:  # noqa: BLE001 - a failed client is a result, not a crash
        result.dropped = True
        result.error = repr(error)
        if not ready.broken:
            await ready.abort()


async def _session(config: Config, ws: Any, ready: asyncio.Barrier, result: ClientResult) -> None:
    async def recv() -> dict[str, Any]:
        message: dict[str, Any] = msgpack.unpackb(await ws.recv(), raw=False)
        return message

    def send(message: dict[str, Any]) -> Any:
        return ws.send(msgpack.packb(message, use_bin_type=True))

    welcome = await recv()
    classes: list[str] = welcome["operator_classes"]
    effector: str = welcome["rules"]["effector_classes"][0]["id"]
    await recv()  # the join frame
    await ready.wait()  # every client starts together
    await send({"t": "start"})

    seq = 0
    plan: dict[str, list[tuple[int, str, dict[str, Any]]]] = {}
    pings: dict[float, float] = {}
    began = time.monotonic()
    by_frames = config.frames is not None
    end_at = began + (HANG_GUARD_S if by_frames else config.seconds)
    last_arrival: float | None = None
    next_ping = began + 1.0

    async def ping(now: float) -> None:
        stamp = float(f"{now:.6f}")
        pings[stamp] = now
        await send({"t": "ping", "ts": stamp})

    while (now := time.monotonic()) < end_at:
        if by_frames and result.frames >= (config.frames or 0):
            break
        if not by_frames and now >= next_ping:
            next_ping += 1.0
            await ping(now)
        try:
            message = await asyncio.wait_for(recv(), timeout=max(0.05, end_at - now))
        except TimeoutError:
            continue
        arrived = time.monotonic()
        kind = message["t"]
        if kind == "pong":
            sent = pings.pop(message["ts"], None)
            if sent is not None:
                result.rtt_ms.append((arrived - sent) * 1000.0)
        elif kind == "ack":
            result.acks_ok += bool(message["ok"])
            result.acks_refused += not message["ok"]
        elif kind == "ended":
            result.ended_status, result.verified = message["status"], message["summary"]["verified"]
            result.seconds = arrived - began
            return
        elif kind == "frame" and message["status"] == "running":
            tick = message["tick"]
            if result.frames == 0:
                result.first_tick = tick
            else:
                result.tick_gaps += tick - result.last_tick - 1
            result.last_tick = tick
            result.frames += 1
            if by_frames and result.frames % PING_EVERY_FRAMES == 0:
                await ping(arrived)
            result.events += len(message["events"])
            if last_arrival is not None:
                result.dt_ms.append((arrived - last_arrival) * 1000.0)
                result.jitter_ms.append(abs((arrived - last_arrival) * 1000.0 - FRAME_MS))
            last_arrival = arrived
            for action, payload in _due(plan, message, classes, effector):
                seq += 1
                result.actions += 1
                await send({"t": "act", "seq": seq, "action": action, "payload": payload})
        elif kind == "error":
            result.dropped = True
            result.error = f"{message['code']}: {message['message']}"
            return

    result.seconds = time.monotonic() - began
    await send({"t": "end"})
    while True:  # the final frames, then `ended`
        message = await asyncio.wait_for(recv(), timeout=60)
        if message["t"] == "ended":
            result.ended_status, result.verified = message["status"], message["summary"]["verified"]
            return


def _due(
    plan: dict[str, list[tuple[int, str, dict[str, Any]]]],
    frame: dict[str, Any],
    classes: list[str],
    effector: str,
) -> list[tuple[str, dict[str, Any]]]:
    """The actions a trainee would take about now: work each new confirmed track in turn."""
    tick = frame["tick"]
    for track in frame["tracks"]:
        track_id = track["id"]
        if track["status"] != "confirmed" or track_id in plan:
            continue
        estimate = track["class_estimate"]
        label = estimate if estimate in classes else "unknown"
        plan[track_id] = [
            (tick + 10, "classify", {"track": track_id, "class_id": label}),
            (tick + 20, "assess", {"track": track_id, "identity": "suspect"}),
            (tick + 30, "sensor-cue", {"sensor": "eo-1", "track": track_id}),
            (tick + 60, "report", {"track": track_id}),
            (tick + 100, "engage", {"track": track_id, "effector_class": effector}),
            (tick + 140, "hold", {"track": track_id}),
        ]
    due: list[tuple[str, dict[str, Any]]] = []
    for steps in plan.values():
        while steps and steps[0][0] <= tick:
            _, action, payload = steps.pop(0)
            due.append((action, payload))
    return due


# ----------------------------------------------------------------------------- the server


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def process_usage(pid: int) -> tuple[float, float]:
    """(CPU seconds, resident MB) of a process, from `ps`."""
    out = subprocess.run(  # noqa: S603
        ["ps", "-o", "rss=,time=", "-p", str(pid)],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()
    if len(out) != 2:
        return 0.0, 0.0
    days, _, clock = out[1].rpartition("-")
    seconds = 0.0
    for part in clock.split(":"):
        seconds = seconds * 60 + float(part)
    return seconds + (float(days) * 86400 if days else 0.0), int(out[0]) / 1024.0


class OwnServer:
    """A throwaway API process with a temporary database and `clients` trainee accounts."""

    def __init__(self, clients: int) -> None:
        self.clients = clients
        self.tmp = tempfile.TemporaryDirectory(prefix="load-")
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.admin_email = "load-admin@load.example"
        self.process: subprocess.Popen[bytes] | None = None

    def _environment(self) -> dict[str, str]:
        env = dict(os.environ)
        env.update(
            APP_ENV="demo",
            DATABASE_URL=f"sqlite:///{self.tmp.name}/load.db",
            SECRET_KEY=secrets.token_urlsafe(48),
            UPLOAD_DIR=f"{self.tmp.name}/uploads",
            SESSION_GRACE_S="120",
        )
        return env

    def start(self) -> None:
        from sqlalchemy.orm import Session

        from alembic import command
        from app.cli import _alembic_config
        from app.config import Settings
        from app.db import make_engine
        from app.models import Role
        from app.users import create_user

        settings = Settings(database_url=f"sqlite:///{self.tmp.name}/load.db")
        command.upgrade(_alembic_config(settings), "head")
        with Session(make_engine(settings.database_url)) as db:
            for index in range(1, self.clients + 1):
                create_user(db, email_of(index), PASSWORD, Role.trainee)
            create_user(db, self.admin_email, PASSWORD, Role.admin)
        self.process = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:get_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
                "--log-level",
                "warning",
                "--proxy-headers",
            ],
            cwd=API_ROOT,
            env=self._environment(),
        )
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"{self.url}/healthz", timeout=1).status_code == 200:
                    return
            except httpx.HTTPError:
                time.sleep(0.2)
        raise RuntimeError("the API did not become healthy")

    def stop(self) -> None:
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:  # pragma: no cover
                self.process.kill()
        self.tmp.cleanup()


# ----------------------------------------------------------------------------- the run


async def server_stats(base: str, email: str, password: str) -> dict[str, Any] | None:
    async with httpx.AsyncClient(base_url=base, timeout=30) as http:
        login = await http.post("/api/v1/auth/login", json={"email": email, "password": password})
        if login.status_code != 200:
            return None
        response = await http.get("/api/v1/sessions/stats")
        stats: dict[str, Any] | None = response.json() if response.status_code == 200 else None
        return stats


async def run_clients(config: Config, base: str) -> tuple[list[ClientResult], float]:
    ready = asyncio.Barrier(config.clients)
    results = [ClientResult(i) for i in range(1, config.clients + 1)]
    began = time.monotonic()
    await asyncio.gather(*(play(config, base, r.index, ready, r) for r in results))
    return results, time.monotonic() - began


def aggregate(results: list[ClientResult]) -> dict[str, Any]:
    rates = [r.frames / r.seconds for r in results if r.seconds]
    return {
        "clients": len(results),
        "dropped_sessions": sum(r.dropped for r in results),
        "verified_sessions": sum(r.verified for r in results),
        "frame_rate_hz": {
            "min": round(min(rates, default=0.0), 2),
            "mean": round(sum(rates) / len(rates), 2) if rates else 0.0,
            "max": round(max(rates, default=0.0), 2),
        },
        "tick_gaps": sum(r.tick_gaps for r in results),
        "interframe_ms": percentiles([x for r in results for x in r.dt_ms]),
        "jitter_ms": percentiles([x for r in results for x in r.jitter_ms]),
        "ping_rtt_ms": percentiles([x for r in results for x in r.rtt_ms]),
        "actions": sum(r.actions for r in results),
        "acks_refused": sum(r.acks_refused for r in results),
    }


async def run_load(config: Config) -> dict[str, Any]:
    own = OwnServer(config.clients) if config.url is None else None
    admin = (config.admin_email, config.admin_password)
    if own is not None:
        await asyncio.to_thread(own.start)
        admin = (own.admin_email, PASSWORD)
    base = (own.url if own else config.url or "").rstrip("/")
    try:
        usage_before = process_usage(own.process.pid) if own and own.process else (0.0, 0.0)
        results, wall = await run_clients(config, base)
        usage_after = process_usage(own.process.pid) if own and own.process else (0.0, 0.0)
        stats = await server_stats(base, admin[0], admin[1]) if admin[0] and admin[1] else None
    finally:
        if own is not None:
            await asyncio.to_thread(own.stop)
    report: dict[str, Any] = {
        "config": {
            "clients": config.clients,
            "seconds": config.seconds,
            "frames": config.frames,
            "scenario": config.scenario,
            "own_server": own is not None,
        },
        "wall_s": round(wall, 1),
        "aggregate": aggregate(results),
        "clients": [r.summary() for r in results],
        "server": {"stats": stats},
    }
    if own is not None:
        cpu = usage_after[0] - usage_before[0]
        report["server"]["cpu_percent_of_one_core"] = round(100.0 * cpu / wall, 1) if wall else 0.0
        report["server"]["rss_mb"] = round(usage_after[1], 1)
    return report


def render(report: dict[str, Any]) -> str:
    agg = report["aggregate"]
    lines = [
        f"Live-session load: {agg['clients']} clients x "
        + (
            f"{report['config']['frames']} frames "
            if report["config"]["frames"] is not None
            else f"{report['config']['seconds']:.0f} s "
        )
        + f"(wall {report['wall_s']} s)",
        f"  dropped sessions : {agg['dropped_sessions']}   verified at end: {agg['verified_sessions']}",
        "  frame rate (Hz)  : "
        f"min {agg['frame_rate_hz']['min']}  mean {agg['frame_rate_hz']['mean']}  "
        f"max {agg['frame_rate_hz']['max']}   tick gaps: {agg['tick_gaps']}",
    ]
    for label, key in (
        ("inter-frame (ms)", "interframe_ms"),
        ("arrival jitter  ", "jitter_ms"),
        ("ping RTT (ms)   ", "ping_rtt_ms"),
    ):
        p = agg[key]
        lines.append(
            f"  {label} : p50 {p['p50']}  p95 {p['p95']}  p99 {p['p99']}  max {p['max']}  "
            f"(n={p['count']})"
        )
    lines.append(f"  actions sent {agg['actions']}, refused {agg['acks_refused']}")
    server = report["server"]
    stats = server.get("stats")
    if stats:
        for label, key in (
            ("server tick jitter", "tick_jitter_ms"),
            ("server tick cost  ", "tick_cost_ms"),
        ):
            p = stats[key]
            lines.append(
                f"  {label} (ms): p50 {p['p50']}  p95 {p['p95']}  p99 {p['p99']}  max {p['max']}  "
                f"(n={p['count']})"
            )
        lines.append(
            f"  server: lag drops {stats['lag_drops']}, frames dropped {stats['frames_dropped']}, "
            f"completed {stats['completed_total']}, abandoned {stats['abandoned_total']}"
        )
    if "cpu_percent_of_one_core" in server:
        lines.append(
            f"  server process: {server['cpu_percent_of_one_core']} % of one core, "
            f"RSS {server['rss_mb']} MB"
        )
    failed = [c for c in report["clients"] if c["dropped"]]
    lines += [f"  client {c['client']} dropped: {c['error']}" for c in failed]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load test for the live session.")
    parser.add_argument("--clients", type=int, default=12)
    parser.add_argument("--seconds", type=float, default=300.0)
    parser.add_argument(
        "--frames", type=int, help="play for this many frames instead of --seconds (deterministic)"
    )
    parser.add_argument("--url", help="drive a running server instead of starting one")
    parser.add_argument("--password", default=PASSWORD, help="password of the load-N accounts")
    parser.add_argument("--admin-email")
    parser.add_argument("--admin-password")
    parser.add_argument("--json", type=Path, help="also write the full report here")
    args = parser.parse_args(argv)
    config = Config(
        clients=args.clients,
        seconds=args.seconds,
        frames=args.frames,
        url=args.url,
        password=args.password,
        admin_email=args.admin_email,
        admin_password=args.admin_password,
    )
    report = asyncio.run(run_load(config))
    print(render(report))
    if args.json:
        args.json.write_text(json.dumps(report, indent=2))
    return 1 if report["aggregate"]["dropped_sessions"] else 0


if __name__ == "__main__":
    sys.exit(main())
