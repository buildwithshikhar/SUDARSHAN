"""The truth ledger: which real drone each track is really following, and where it is wrong.

The tracker knows nothing about ground truth. The ledger is told it through a separate channel
(`observe`'s `truth` argument maps a report's reference number to the drone that caused it, or to
`None` for a false alarm) and never feeds anything back into the tracker. Its output is for the
instructor and for scoring; `TRUTH_EVENT_KINDS` lists the event kinds a trainee's picture must
filter out, because they name the true identities.

Identity. A track's identity is the plurality of the true drones behind the last five reports it
used (false alarms are kept in the window but say nothing); it needs at least three real reports
and breaks ties alphabetically. Until then it is unknown (`None`).

Label registry. When a track is confirmed, its current label is bound to its identity: the label
the operator sees stands for that drone. A track is *consistent* when its label is bound to its
current identity. An operator who relabels a track that was consistent binds the new label to the
same drone; relabelling an inconsistent track never creates a binding, so a wrong picture cannot
be made right by naming it.

Errors, each with an `error_id` that never repeats:

- swap: a confirmed track's identity changes from a real drone A to a real drone B and its label
  no longer stands for what it follows. A second track that changed to A on the same or the
  previous tick is its partner and shares the error. A track that goes back to the drone its
  label is bound to is not a new error; it restores the old one.
- split: one real drone is followed by two or more confirmed tracks for 40 consecutive ticks,
  once per episode. Duplicates made on purpose by the operator's own `split` are not counted.
- merge: a dropped track with reason "duplicate" or "merged-error" whose identity and whose
  survivor's identity are different real drones.

An error stays in `open_errors()` until restored: a swap when every live track it touched is
consistent again, a split when the drone is followed by fewer than two confirmed tracks, a merge
when both drones again have a distinct confirmed track following them. A restoration is reported
as a "restored" event. Tracks that are dropped no longer count against an error.
"""

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .tracker import UpdateResult

WINDOW = 5
MIN_REAL = 3
#: A split is declared when one drone has had two or more confirmed tracks this many ticks.
SPLIT_TICKS = 40

ERROR_KINDS = ("swap", "split", "merge")
TRUTH_EVENT_KINDS = ("swap", "split", "merge", "restored")
_MERGE_DROP_REASONS = ("duplicate", "merged-error")


@dataclass(frozen=True, slots=True)
class LedgerEvent:
    kind: str  # swap, split, merge, restored
    payload: dict[str, Any]


class TruthLedger:
    def __init__(self) -> None:
        self._window: dict[str, deque[str | None]] = {}
        #: Last known identity of every track, for spotting a change.
        self._identity: dict[str, str] = {}
        self._live: set[str] = set()
        self._confirmed: set[str] = set()
        #: Confirmed tracks whose label is not yet bound (identity still unknown).
        self._unbound: set[str] = set()
        self._labels: dict[str, str] = {}
        #: label -> the drone it stands for.
        self._registry: dict[str, str] = {}
        #: Tracks made by the operator's own split; not counted as tracker splits.
        self._by_operator: set[str] = set()
        self._errors: dict[int, dict[str, Any]] = {}
        self._next_error = 1
        #: track -> (tick, from, to, error id) of recent identity changes, for partnering.
        self._changes: dict[str, tuple[int, str, str, int]] = {}
        #: drone -> (first tick, last tick) of the current run with two or more tracks.
        self._runs: dict[str, tuple[int, int]] = {}
        self._episodes: set[str] = set()

    # ------------------------------------------------------------------ queries

    def identity_of(self, track_id: str) -> str | None:
        """The real drone a track is following, or `None` while there is too little evidence."""
        return _identity(self._window.get(track_id, ()))

    def label_of(self, track_id: str) -> str:
        return self._labels.get(track_id, track_id)

    def consistent(self, track_id: str) -> bool:
        """True if the track's label is bound to the drone the track is really following."""
        identity = self.identity_of(track_id)
        return identity is not None and self._registry.get(self.label_of(track_id)) == identity

    def open_errors(self) -> list[dict[str, Any]]:
        return [_public(e) for _, e in sorted(self._errors.items()) if e["open"]]

    def errors(self) -> list[dict[str, Any]]:
        """Every error so far, open or restored, in error_id order."""
        return [_public(e) for _, e in sorted(self._errors.items())]

    # ------------------------------------------------------------------ feeding it

    def observe(
        self, tick: int, result: UpdateResult, truth: Mapping[int, str | None]
    ) -> list[LedgerEvent]:
        """Take one tracker update and the ground truth of its reports; return new findings."""
        for assoc in result.associations:
            if assoc.ref not in truth:
                raise ValueError(f"no ground truth for report {assoc.ref}")
            self._live.add(assoc.track_id)
            self._window.setdefault(assoc.track_id, deque(maxlen=WINDOW)).append(truth[assoc.ref])
        out: list[LedgerEvent] = []
        for event in result.events:
            if event.kind == "init":
                self._live.add(event.track_id)
            elif event.kind == "confirm":
                self._live.add(event.track_id)
                self._confirmed.add(event.track_id)
                self._unbound.add(event.track_id)
            elif event.kind == "drop":
                out.extend(self._dropped(tick, event.track_id, event.payload))
        self._bind()
        out.extend(self._swaps(tick))
        out.extend(self._splits(tick))
        out.extend(self._restorations(tick))
        return out

    def on_effects(self, tick: int, effects: Iterable[tuple[Any, ...]]) -> list[LedgerEvent]:
        """Pass on the `effects` of a `commands.CommandOutcome`, in order."""
        out: list[LedgerEvent] = []
        for effect in effects:
            kind, args = effect[0], effect[1:]
            if kind == "relabel":
                out.extend(self.on_relabel(tick, *args))
            elif kind == "merge":
                out.extend(self.on_merge(tick, *args))
            elif kind == "split":
                out.extend(self.on_split(tick, *args))
            elif kind == "drop":
                out.extend(self.on_drop(tick, *args))
            else:
                raise ValueError(f"unknown command effect {kind!r}")
        return out

    def on_relabel(self, tick: int, track: str, label: str) -> list[LedgerEvent]:
        """The operator renamed a track. A consistent track carries its binding to the new name."""
        was_consistent = self.consistent(track)
        self._labels[track] = label
        identity = self.identity_of(track)
        if was_consistent and identity is not None:
            self._registry[label] = identity
        return self._restorations(tick)

    def on_merge(self, tick: int, survivor: str, absorbed: str) -> list[LedgerEvent]:
        """The operator merged two tracks: `absorbed` is gone, `survivor` keeps its identity."""
        self._live.discard(absorbed)
        return self._restorations(tick)

    def on_split(self, tick: int, source: str, new: str) -> list[LedgerEvent]:
        """The operator cloned `source` into `new`; the copy is theirs, not a tracker error."""
        self._live.add(new)
        self._by_operator.add(new)
        self._window[new] = deque(self._window.get(source, ()), maxlen=WINDOW)
        if source in self._identity:
            self._identity[new] = self._identity[source]
        if source in self._confirmed:
            self._confirmed.add(new)
        return self._restorations(tick)

    def on_drop(self, tick: int, track: str) -> list[LedgerEvent]:
        self._live.discard(track)
        return self._restorations(tick)

    # ------------------------------------------------------------------ detection

    def _bind(self) -> None:
        """Bind the label of every newly confirmed track as soon as its identity is known."""
        for track in sorted(self._unbound):
            identity = self.identity_of(track)
            if identity is not None:
                self._registry[self.label_of(track)] = identity
                self._identity[track] = identity
                self._unbound.discard(track)

    def _swaps(self, tick: int) -> list[LedgerEvent]:
        moved: list[tuple[str, str, str]] = []
        for track in sorted(self._live):
            now = self.identity_of(track)
            before = self._identity.get(track)
            if now is None or now == before:
                continue
            self._identity[track] = now
            if before is not None and track in self._confirmed and not self.consistent(track):
                moved.append((track, before, now))
        known = {t: c for t, c in self._changes.items() if c[0] >= tick - 1}
        for track, was, now in moved:
            known[track] = (tick, was, now, 0)
        out: list[LedgerEvent] = []
        for track, was, now in moved:
            partner = _partner(known, track, was, now)
            error_id = known[track][3]
            if error_id == 0 and partner is not None:
                error_id = known[partner][3]
                if error_id != 0 and not self._errors[error_id]["open"]:
                    error_id = 0
            if error_id == 0:
                error_id = self._open("swap", tick)
            known[track] = (*known[track][:3], error_id)
            if partner is not None and known[partner][3] == 0:
                known[partner] = (*known[partner][:3], error_id)
            error = self._errors[error_id]
            error["tracks"] = sorted({*error["tracks"], track, *([partner] if partner else [])})
            error["truths"] = sorted({*error["truths"], was, now})
            out.append(
                LedgerEvent(
                    "swap",
                    {
                        "error_id": error_id,
                        "from_truth": was,
                        "partner": partner,
                        "tick": tick,
                        "to_truth": now,
                        "track": track,
                    },
                )
            )
        self._changes = known
        return out

    def _splits(self, tick: int) -> list[LedgerEvent]:
        followers: dict[str, list[str]] = {}
        for track in sorted(self._live):
            identity = self.identity_of(track)
            if identity is not None and self._counts(track):
                followers.setdefault(identity, []).append(track)
        out: list[LedgerEvent] = []
        for drone in sorted({*self._runs, *followers}):
            tracks = followers.get(drone, [])
            if len(tracks) < 2:
                self._runs.pop(drone, None)
                self._episodes.discard(drone)
                continue
            first, last = self._runs.get(drone, (tick, tick))
            if tick - last > 1:
                first = tick
            self._runs[drone] = (first, tick)
            if tick - first + 1 >= SPLIT_TICKS and drone not in self._episodes:
                self._episodes.add(drone)
                error_id = self._open("split", tick)
                self._errors[error_id].update(tracks=tracks, truths=[drone])
                out.append(
                    LedgerEvent(
                        "split",
                        {"error_id": error_id, "tick": tick, "tracks": tracks, "truth": drone},
                    )
                )
        return out

    def _dropped(self, tick: int, track: str, payload: Mapping[str, Any]) -> list[LedgerEvent]:
        survivor = payload.get("merged_into")
        out: list[LedgerEvent] = []
        if payload.get("reason") in _MERGE_DROP_REASONS and survivor is not None:
            lost, kept = self.identity_of(track), self.identity_of(survivor)
            if lost is not None and kept is not None and lost != kept:
                error_id = self._open("merge", tick)
                self._errors[error_id].update(
                    tracks=sorted([track, survivor]),
                    truths=sorted([lost, kept]),
                    truth_dropped=lost,
                    truth_survivor=kept,
                )
                out.append(
                    LedgerEvent(
                        "merge",
                        {
                            "dropped": track,
                            "error_id": error_id,
                            "survivor": survivor,
                            "tick": tick,
                            "truth_dropped": lost,
                            "truth_survivor": kept,
                        },
                    )
                )
        self._live.discard(track)
        return out

    # ------------------------------------------------------------------ restoration

    def _restorations(self, tick: int) -> list[LedgerEvent]:
        out: list[LedgerEvent] = []
        for error_id, error in sorted(self._errors.items()):
            if error["open"] and self._is_restored(error):
                error["open"] = False
                error["restored_tick"] = tick
                out.append(
                    LedgerEvent(
                        "restored",
                        {
                            "error_id": error_id,
                            "error_kind": error["kind"],
                            "tick": tick,
                            "tracks": list(error["tracks"]),
                            "truths": list(error["truths"]),
                        },
                    )
                )
        return out

    def _is_restored(self, error: dict[str, Any]) -> bool:
        if error["kind"] == "swap":
            return all(self.consistent(t) for t in error["tracks"] if t in self._live)
        if error["kind"] == "split":
            return len(self._followers(error["truths"][0])) < 2
        lost = self._followers(error["truth_dropped"])
        kept = self._followers(error["truth_survivor"])
        return any(a != b for a in lost for b in kept)

    def _counts(self, track: str) -> bool:
        """A confirmed track the tracker made itself."""
        return track in self._confirmed and track not in self._by_operator

    def _followers(self, drone: str) -> list[str]:
        return [t for t in sorted(self._live) if self._counts(t) and self.identity_of(t) == drone]

    def _open(self, kind: str, tick: int) -> int:
        error_id = self._next_error
        self._next_error += 1
        self._errors[error_id] = {
            "id": error_id,
            "kind": kind,
            "tick": tick,
            "open": True,
            "restored_tick": None,
            "tracks": [],
            "truths": [],
        }
        return error_id

    # ------------------------------------------------------------------ snapshot

    def state(self) -> dict[str, Any]:
        """Plain JSON with sorted keys, enough to continue exactly."""
        return {
            "by_operator": sorted(self._by_operator),
            "changes": {t: list(c) for t, c in sorted(self._changes.items())},
            "confirmed": sorted(self._confirmed),
            "episodes": sorted(self._episodes),
            "errors": {str(k): _public(e) for k, e in sorted(self._errors.items())},
            "identity": dict(sorted(self._identity.items())),
            "labels": dict(sorted(self._labels.items())),
            "live": sorted(self._live),
            "next_error": self._next_error,
            "registry": dict(sorted(self._registry.items())),
            "runs": {d: list(r) for d, r in sorted(self._runs.items())},
            "unbound": sorted(self._unbound),
            "windows": {t: list(w) for t, w in sorted(self._window.items())},
        }

    def restore(self, state: Mapping[str, Any]) -> None:
        self._by_operator = set(state["by_operator"])
        self._changes = {t: (c[0], c[1], c[2], c[3]) for t, c in state["changes"].items()}
        self._confirmed = set(state["confirmed"])
        self._episodes = set(state["episodes"])
        self._errors = {int(k): _public(e) for k, e in state["errors"].items()}
        self._identity = dict(state["identity"])
        self._labels = dict(state["labels"])
        self._live = set(state["live"])
        self._next_error = int(state["next_error"])
        self._registry = dict(state["registry"])
        self._runs = {d: (r[0], r[1]) for d, r in state["runs"].items()}
        self._unbound = set(state["unbound"])
        self._window = {t: deque(w, maxlen=WINDOW) for t, w in state["windows"].items()}


def _partner(
    known: Mapping[str, tuple[int, str, str, int]], track: str, was: str, now: str
) -> str | None:
    """Another track that changed to the drone this one left, on the same or the previous tick.

    Preferred: one that came from the drone this one now follows (a true exchange), then the most
    recent, then the lower track id.
    """
    candidates = [
        (source != now, -when, other)
        for other, (when, source, target, _) in known.items()
        if other != track and target == was
    ]
    return min(candidates)[2] if candidates else None


def _identity(window: Iterable[str | None]) -> str | None:
    counts: dict[str, int] = {}
    for item in window:
        if item is not None:
            counts[item] = counts.get(item, 0) + 1
    if sum(counts.values()) < MIN_REAL:
        return None
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def _public(error: Mapping[str, Any]) -> dict[str, Any]:
    return {k: (list(v) if isinstance(v, list) else v) for k, v in sorted(error.items())}
