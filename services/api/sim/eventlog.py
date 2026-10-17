"""Hash-chained event log: an append-only record of everything the simulation did.

Each record's hash covers its own six fields, and its `prev_hash` is the hash of the record
before, so editing, deleting, inserting or reordering any record breaks the chain at a position
`verify` can name. A tamperer who recomputes the hash of record k is caught at k + 1, whose
`prev_hash` no longer matches. The last record has no successor, so it is only protected by
comparing the log head with a value kept elsewhere (wave 13b signs the head).
"""

import json
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from app.contracts import TICK_HZ
from app.contracts.events import GENESIS_HASH, EventRecord, Payload

from .canonical import canonical_json, sha256_hex


class ChainError(ValueError):
    """The log is not an intact chain; `seq` is the position of the first bad record."""

    def __init__(self, seq: int, message: str | None = None) -> None:
        super().__init__(message or f"event log is not intact at record {seq}")
        self.seq = seq


def record_hash(seq: int, t: float, type: str, actor: str, payload: Payload, prev_hash: str) -> str:
    """SHA-256 of the canonical JSON of the six hashed fields (everything except `hash`)."""
    return sha256_hex(
        {
            "seq": seq,
            "t": t,
            "type": type,
            "actor": actor,
            "payload": payload,
            "prev_hash": prev_hash,
        }
    )


def _coerce(item: EventRecord | Mapping[str, Any]) -> EventRecord | None:
    """Validate a mapping as a record; None when it is not one (so the caller can report it)."""
    if isinstance(item, EventRecord):
        return item
    try:
        return EventRecord.model_validate(item)
    except ValidationError:
        return None


def verify(
    records: Sequence[EventRecord | Mapping[str, Any]], expected_head: str | None = None
) -> int | None:
    """Return the position of the first bad record, or None when the chain is intact.

    Hashes are always recomputed from the fields, never trusted, so the check also catches
    payloads mutated in place after a record was stored. `expected_head` closes the one gap the
    chain cannot: a rewrite of the last record, or a truncated log, shows as a head mismatch and
    is reported at the last position.
    """
    prev = GENESIS_HASH
    for i, item in enumerate(records):
        rec = _coerce(item)
        if rec is None or rec.seq != i or rec.prev_hash != prev:
            return i
        try:
            expected = record_hash(rec.seq, rec.t, rec.type, rec.actor, rec.payload, prev)
        except ValueError:  # e.g. a NaN smuggled into a payload by in-place mutation
            return i
        if rec.hash != expected:
            return i
        prev = rec.hash
    if expected_head is not None and prev != expected_head:
        return max(len(records) - 1, 0)
    return None


class EventLog:
    """Append-only chain of `EventRecord`s with `t` derived from the tick, never a clock."""

    def __init__(self, tick_hz: int = TICK_HZ) -> None:
        if tick_hz < 1:
            raise ValueError("tick_hz must be a positive integer")
        self._tick_hz = tick_hz
        self._records: list[EventRecord] = []
        self._last_tick = 0

    def append(
        self, tick: int, type: str, actor: str, payload: Payload | None = None
    ) -> EventRecord:
        """Add one event at `tick`. Raises ValueError for a tick going backwards or a payload
        that is not finite JSON; the log is unchanged in that case."""
        if tick < self._last_tick:
            raise ValueError(f"tick {tick} is earlier than the previous event at {self._last_tick}")
        try:
            # A canonical round trip deep-copies the payload (later caller mutation cannot reach
            # the stored record) and rejects NaN, infinity and non-JSON values.
            stored: Payload = json.loads(canonical_json(payload or {}))
        except TypeError as exc:
            raise ValueError(f"payload is not JSON-serialisable: {exc}") from exc
        seq = len(self._records)
        t = tick / self._tick_hz
        prev = self.head
        record = EventRecord(
            seq=seq,
            t=t,
            type=type,
            actor=actor,
            payload=stored,
            prev_hash=prev,
            hash=record_hash(seq, t, type, actor, stored, prev),
        )
        self._records.append(record)
        self._last_tick = tick
        return record

    @property
    def head(self) -> str:
        return self._records[-1].hash if self._records else GENESIS_HASH

    @property
    def records(self) -> tuple[EventRecord, ...]:
        return tuple(self._records)

    def __len__(self) -> int:
        return len(self._records)

    @classmethod
    def from_records(
        cls, records: Sequence[EventRecord | Mapping[str, Any]], tick_hz: int = TICK_HZ
    ) -> "EventLog":
        """Load a stored log, refusing it with `ChainError` at the first bad record."""
        bad = verify(records)
        if bad is not None:
            raise ChainError(bad)
        log = cls(tick_hz)
        for item in records:
            rec = _coerce(item)
            assert rec is not None  # verify() accepted it
            log._records.append(rec)
        if log._records:
            log._last_tick = round(log._records[-1].t * tick_hz)
        return log

    def to_jsonl(self) -> str:
        """One canonical JSON record per line, with a trailing newline when non-empty."""
        return "".join(
            canonical_json(r.model_dump(mode="json")).decode() + "\n" for r in self._records
        )

    @classmethod
    def from_jsonl(cls, text: str, tick_hz: int = TICK_HZ) -> "EventLog":
        """Inverse of `to_jsonl`; a line that is not JSON is reported at its position."""
        # Split on "\n" only: canonical JSON keeps U+0085, U+2028 and friends raw inside strings,
        # and str.splitlines() would cut a record in half at them.
        lines = text.split("\n")
        if lines[-1] == "":
            lines.pop()
        rows: list[Any] = []
        for i, line in enumerate(lines):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ChainError(i, f"record {i} is not valid JSON: {exc.msg}") from exc
        return cls.from_records(rows, tick_hz)
