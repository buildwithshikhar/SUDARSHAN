"""Operator track commands: relabel, merge, split and drop, as pure functions on a `Tracker`.

These are what a trainee does to fix the picture, or to break it. Each returns a
`CommandOutcome`:

- `events`: `(event_type, payload)` pairs for the session's event log, with types like
  `track.relabel`. A rejection is also logged (`track.command_rejected`) so the log shows what the
  operator tried.
- `effects`: tuples telling the picture what changed, so it can pass it on to the truth ledger:
  `("relabel", track, label)`, `("merge", survivor, absorbed)`, `("split", source, new)`,
  `("drop", track)`.

A rejected command changes nothing. Nothing is undone by an "undo": the effect of a command is
reversed only by another command, which is logged in its own right, so the log tells the whole
story and a replay needs no special case.

Commands use only the tracker's public handles; they read no ground truth.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from ..sensors.detection import DATA_REFERENCE, DATA_VERIFIED
from .tracker import Tracker

EVENT_TYPE = re.compile(r"^[a-z]+(\.[a-z_]+)+$")
LABEL_MAX = 24
REJECTED = "track.command_rejected"

Effect = tuple[Any, ...]
Event = tuple[str, dict[str, Any]]


@dataclass(frozen=True, slots=True)
class CommandOutcome:
    ok: bool
    reason: str | None = None
    events: list[Event] = field(default_factory=list)
    effects: tuple[Effect, ...] = ()


def _reject(action: str, reason: str, **detail: Any) -> CommandOutcome:
    return CommandOutcome(
        False, reason, [(REJECTED, {"action": action, "reason": reason, **detail})]
    )


def _order(track_id: str) -> tuple[int, str]:
    """Numeric-aware id order, so T999 sorts before T1000."""
    return len(track_id), track_id


def relabel(
    tracker: Tracker, tick: int, track: str, label: str, exchange: bool = False
) -> CommandOutcome:
    """Rename a track. A name another live track wears is refused unless `exchange` is set, which
    gives the other track this one's old name in the same step."""
    if track not in tracker.tracks:
        return _reject("track-relabel", f"no live track {track!r}", track=track)
    name = label.strip()
    if not 1 <= len(name) <= LABEL_MAX:
        return _reject(
            "track-relabel", f"a label is 1 to {LABEL_MAX} characters", track=track, label=label
        )
    if not name.isprintable():
        return _reject("track-relabel", "a label may not contain control characters", track=track)
    mine = tracker.tracks[track]
    if name == mine.label:
        return _reject("track-relabel", f"track {track} is already labelled {name!r}", track=track)
    other = next((t for t in tracker.tracks.values() if t.id != track and t.label == name), None)
    if other is not None and not exchange:
        return _reject(
            "track-relabel",
            f"label {name!r} is on track {other.id}; exchange labels to take it",
            track=track,
            label=name,
        )
    previous = mine.label
    mine.label = name
    effects: list[Effect] = [("relabel", track, name)]
    payload: dict[str, Any] = {"track": track, "label": name, "previous": previous}
    if other is not None:
        other.label = previous
        effects.append(("relabel", other.id, previous))
        payload["exchanged_with"] = other.id
    return CommandOutcome(True, None, [("track.relabel", payload)], tuple(effects))


def merge(tracker: Tracker, tick: int, tracks: tuple[str, ...] | list[str]) -> CommandOutcome:
    """Fold two live, non-tentative tracks into the one with the lower id.

    The survivor keeps its filter state and takes the other's class votes and sensors; the other
    is dropped with reason "merged".
    """
    ids = list(tracks)
    if len(ids) != 2 or ids[0] == ids[1]:
        return _reject("track-merge", "a merge needs exactly two different tracks", tracks=ids)
    missing = [t for t in ids if t not in tracker.tracks]
    if missing:
        return _reject("track-merge", f"no live track {missing[0]!r}", tracks=ids)
    if any(tracker.tracks[t].status == "tentative" for t in ids):
        return _reject("track-merge", "a tentative track cannot be merged", tracks=ids)
    survivor_id, absorbed_id = sorted(ids, key=_order)
    survivor, absorbed = tracker.tracks[survivor_id], tracker.tracks[absorbed_id]
    for name, count in absorbed.votes.items():
        survivor.votes[name] = survivor.votes.get(name, 0) + count
    survivor.sensors = sorted({*survivor.sensors, *absorbed.sensors})
    if absorbed.data_status != DATA_VERIFIED:
        survivor.data_status = DATA_REFERENCE
    tracker.drop(absorbed_id, tick, "merged", merged_into=survivor_id)
    return CommandOutcome(
        True,
        None,
        [("track.merge", {"survivor": survivor_id, "absorbed": absorbed_id})],
        (("merge", survivor_id, absorbed_id),),
    )


def split(tracker: Tracker, tick: int, track: str) -> CommandOutcome:
    """Copy a track into two. The copy is confirmed (a tentative track stays tentative) and born
    now; both then compete for reports, so one starves and is folded back unless there really
    are two targets."""
    if track not in tracker.tracks:
        return _reject("track-split", f"no live track {track!r}", track=track)
    source = tracker.tracks[track]
    clone = source.clone(tracker.allocate_id())
    clone.born = tick
    if source.status != "tentative":
        clone.status = "confirmed"
    tracker.insert(clone)
    return CommandOutcome(
        True,
        None,
        [("track.split", {"source": track, "new": clone.id})],
        (("split", track, clone.id),),
    )


def drop(tracker: Tracker, tick: int, track: str) -> CommandOutcome:
    """Remove a track, reason "operator"."""
    if track not in tracker.tracks:
        return _reject("track-drop", f"no live track {track!r}", track=track)
    event = tracker.drop(track, tick, "operator")
    return CommandOutcome(True, None, [("track.drop", dict(event.payload))], (("drop", track),))


# ---------------------------------------------------------------------- dispatch


def _text(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) else None


def _do_relabel(tracker: Tracker, tick: int, payload: Mapping[str, Any]) -> CommandOutcome:
    track, label, exchange = (
        _text(payload, "track"),
        _text(payload, "label"),
        payload.get("exchange", False),
    )
    if track is None or label is None or not isinstance(exchange, bool):
        return _reject("track-relabel", "needs track (text), label (text) and optional exchange")
    return relabel(tracker, tick, track, label, exchange)


def _do_merge(tracker: Tracker, tick: int, payload: Mapping[str, Any]) -> CommandOutcome:
    tracks = payload.get("tracks")
    if not isinstance(tracks, (list, tuple)) or not all(isinstance(t, str) for t in tracks):
        return _reject("track-merge", "needs tracks: a list of two track ids")
    return merge(tracker, tick, list(tracks))


def _single(
    action: str, run: Callable[[Tracker, int, str], CommandOutcome]
) -> Callable[[Tracker, int, Mapping[str, Any]], CommandOutcome]:
    def go(tracker: Tracker, tick: int, payload: Mapping[str, Any]) -> CommandOutcome:
        track = _text(payload, "track")
        if track is None:
            return _reject(action, "needs track (text)")
        return run(tracker, tick, track)

    return go


_ACTIONS: dict[
    str, tuple[frozenset[str], Callable[[Tracker, int, Mapping[str, Any]], CommandOutcome]]
] = {
    "track-relabel": (frozenset({"track", "label", "exchange"}), _do_relabel),
    "track-merge": (frozenset({"tracks"}), _do_merge),
    "track-split": (frozenset({"track"}), _single("track-split", split)),
    "track-drop": (frozenset({"track"}), _single("track-drop", drop)),
}

ACTIONS = tuple(_ACTIONS)


def apply(tracker: Tracker, tick: int, action: str, payload: Mapping[str, Any]) -> CommandOutcome:
    """Run the action named in an action record against the tracker. Never raises on bad input."""
    entry = _ACTIONS.get(action)
    if entry is None:
        return _reject(action, f"unknown track command {action!r}")
    keys, run = entry
    if not isinstance(payload, Mapping):
        return _reject(action, "the payload must be an object")
    unknown = sorted(str(k) for k in payload if k not in keys)
    if unknown:
        return _reject(action, f"unexpected field {unknown[0]!r}")
    return run(tracker, tick, payload)
