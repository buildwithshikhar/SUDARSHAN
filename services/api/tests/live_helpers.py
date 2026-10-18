"""Shared helpers for the wave 5 tests: the Harrier Field scenario with a picture and rules."""

from pathlib import Path

from app.contracts import ActionRecord
from app.contracts.loader import load_pack
from app.contracts.scenario import ScenarioSpec
from sim.roe import load_rule_engine
from sim.tracking.picture import Picture
from sim.world import World

REPO = Path(__file__).resolve().parents[3]
HARRIER = REPO / "packs" / "scenarios" / "harrier-morning-watch.v1.json"
ACTOR = "trainee:t-1"


def harrier_spec() -> ScenarioSpec:
    spec = load_pack(HARRIER)
    assert isinstance(spec, ScenarioSpec)
    return spec


def harrier_world(seed: int | None = None) -> World:
    spec = harrier_spec()
    seed = spec.default_seed if seed is None else seed
    return World(spec, seed, picture=Picture.build(spec, seed), roe=load_rule_engine(spec))


def act(world: World, action: str, **payload: object) -> ActionRecord:
    return ActionRecord(tick=world.tick, actor=ACTOR, action=action, payload=payload)


def run_until_track(world: World, truth: str, *, limit_s: float = 300.0) -> str:
    """Step until a confirmed track follows the drone `truth`; return the track id."""
    assert world.picture is not None
    for _ in range(int(limit_s * 20)):
        world.step()
        for track_id, track in world.picture.tracker.tracks.items():
            if track.status == "confirmed" and world.picture.ledger.identity_of(track_id) == truth:
                return track_id
    raise AssertionError(f"no confirmed track on {truth} within {limit_s} s")


def events(world: World, kind: str) -> list[dict[str, object]]:
    return [dict(r.payload) for r in world.log.records if r.type == kind]
