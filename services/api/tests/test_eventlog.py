"""The event log is a hash chain: any edit is reported at the record that was edited."""

import copy
import hashlib
import json
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.contracts import GENESIS_HASH, EventRecord
from sim.canonical import canonical_json
from sim.eventlog import ChainError, EventLog, record_hash, verify

N = 30
TYPES = ["sim.tick_start", "sensor.detection", "track.classified", "effector.engaged"]
ACTORS = ["sim", "system", "trainee:op-1", "instructor:cdr"]
BAD = "f" * 64


def build_log(n: int = N) -> EventLog:
    log = EventLog()
    for i in range(n):
        log.append(
            tick=i * 3,
            type=TYPES[i % len(TYPES)],
            actor=ACTORS[i % len(ACTORS)],
            payload={"n": i, "nested": {"vals": [i, i + 0.5], "tag": f"x{i}"}, "ok": i % 2 == 0},
        )
    return log


def dicts(log: EventLog) -> list[dict[str, Any]]:
    return [r.model_dump(mode="json") for r in log.records]


def rehash(rec: dict[str, Any]) -> dict[str, Any]:
    """What a tamperer who understands the format does after editing a record."""
    rec["hash"] = record_hash(
        rec["seq"], rec["t"], rec["type"], rec["actor"], rec["payload"], rec["prev_hash"]
    )
    return rec


# --- append ---------------------------------------------------------------------------------


def test_append_builds_a_valid_chain() -> None:
    log = build_log()
    assert len(log) == N
    prev = GENESIS_HASH
    for i, rec in enumerate(log.records):
        assert isinstance(rec, EventRecord)
        assert rec.seq == i
        assert rec.prev_hash == prev
        assert rec.t == (i * 3) / 20
        assert rec.hash == record_hash(
            rec.seq, rec.t, rec.type, rec.actor, rec.payload, rec.prev_hash
        )
        prev = rec.hash
    assert log.head == prev
    assert log.records[0].prev_hash == GENESIS_HASH


def test_time_is_exact_tick_division() -> None:
    log = EventLog()
    assert log.append(3, "sim.tick_start", "sim").t == 0.15
    assert EventLog(tick_hz=10).append(3, "sim.tick_start", "sim").t == 0.3


def test_empty_log_head_is_genesis_and_payload_defaults_to_empty() -> None:
    log = EventLog()
    assert log.head == GENESIS_HASH
    assert len(log) == 0
    assert log.records == ()
    assert log.append(0, "sim.tick_start", "sim").payload == {}


def test_tick_hz_must_be_positive() -> None:
    with pytest.raises(ValueError, match="tick_hz"):
        EventLog(tick_hz=0)


def test_equal_ticks_are_allowed_and_decreasing_ticks_are_refused() -> None:
    log = EventLog()
    log.append(5, "sim.tick_start", "sim")
    log.append(5, "sensor.detection", "sim")
    with pytest.raises(ValueError, match="earlier"):
        log.append(4, "sensor.detection", "sim")
    with pytest.raises(ValueError, match="earlier"):
        EventLog().append(-1, "sim.tick_start", "sim")
    assert len(log) == 2
    assert verify(log.records) is None


@pytest.mark.parametrize(
    "payload",
    [
        {"x": float("nan")},
        {"x": float("inf")},
        {"x": {"y": [1, float("-inf")]}},
        {"x": {1, 2}},
        {"x": object()},
        {"x": b"bytes"},
        {1: "a", "b": 2},  # keys of mixed types cannot be ordered canonically
    ],
)
def test_append_refuses_non_finite_or_non_json_payloads(payload: Any) -> None:
    log = build_log(3)
    head = log.head
    with pytest.raises(ValueError):
        log.append(100, "sim.tick_start", "sim", payload)
    assert len(log) == 3
    assert log.head == head


@pytest.mark.parametrize(
    ("type_", "actor"),
    [("Bad Type", "sim"), ("sim.tick_start", "Trainee:1"), ("sim.tick_start", "")],
)
def test_append_refuses_invalid_type_or_actor(type_: str, actor: str) -> None:
    log = EventLog()
    with pytest.raises(ValueError):
        log.append(0, type_, actor)
    assert len(log) == 0


def test_append_deep_copies_the_payload() -> None:
    payload: dict[str, Any] = {"a": {"b": [1, 2]}}
    log = EventLog()
    log.append(0, "sim.tick_start", "sim", payload)
    payload["a"]["b"].append(3)
    payload["c"] = 1
    assert log.records[0].payload == {"a": {"b": [1, 2]}}
    assert verify(log.records) is None


def test_non_string_keys_are_normalised_like_the_stored_form() -> None:
    log = EventLog()
    rec = log.append(0, "sim.tick_start", "sim", {1: "a"})  # type: ignore[dict-item]
    assert rec.payload == {"1": "a"}
    assert EventLog.from_jsonl(log.to_jsonl()).head == log.head


# --- verify: intact -------------------------------------------------------------------------


def test_verify_accepts_an_intact_log_as_objects_and_dicts() -> None:
    log = build_log(200)
    assert verify(log.records) is None
    assert verify(dicts(log)) is None
    assert verify(log.records, expected_head=log.head) is None
    assert verify(dicts(log), expected_head=log.head) is None


def test_records_are_a_snapshot() -> None:
    log = build_log(3)
    snapshot = log.records
    log.append(100, "sim.tick_start", "sim")
    assert len(snapshot) == 3
    assert len(log.records) == 4


def test_jsonl_round_trip() -> None:
    log = build_log()
    text = log.to_jsonl()
    assert text.endswith("\n")
    assert text.count("\n") == N
    assert text.splitlines()[0].encode() == canonical_json(dicts(log)[0])
    back = EventLog.from_jsonl(text)
    assert back.records == log.records
    assert back.head == log.head
    assert back.to_jsonl() == text
    assert verify(back.records, expected_head=log.head) is None


def test_jsonl_survives_unicode_line_separators_inside_strings() -> None:
    """U+0085, U+2028 and U+2029 stay raw in canonical JSON; only "\\n" separates records."""
    log = EventLog()
    log.append(0, "sim.tick_start", "sim", {"note": "a\x85b c d\x0be\r\nf"})
    log.append(1, "sim.tick_start", "sim", {"note": "x"})
    text = log.to_jsonl()
    assert text.count("\n") == 2
    assert EventLog.from_jsonl(text).records == log.records


def test_from_jsonl_accepts_a_missing_trailing_newline() -> None:
    log = build_log(3)
    assert EventLog.from_jsonl(log.to_jsonl().rstrip("\n")).head == log.head


def test_empty_log_serialises_to_empty_text() -> None:
    assert EventLog().to_jsonl() == ""
    back = EventLog.from_jsonl("")
    assert len(back) == 0
    assert back.head == GENESIS_HASH


def test_a_loaded_log_can_be_extended_and_keeps_tick_order() -> None:
    log = build_log(5)
    loaded = EventLog.from_records(dicts(log))
    last_tick = 4 * 3
    with pytest.raises(ValueError, match="earlier"):
        loaded.append(last_tick - 1, "sim.tick_start", "sim")
    loaded.append(last_tick, "sim.tick_start", "sim")
    assert len(loaded) == 6
    assert verify(loaded.records) is None


def test_records_validated_elsewhere_verify() -> None:
    """Plain EventRecord instances (as held by a session record) verify like log records."""
    log = build_log(4)
    parsed = [EventRecord.model_validate(d) for d in dicts(log)]
    assert verify(parsed, expected_head=log.head) is None


# --- verify: tamper detection at the tampered event -----------------------------------------


def _t(rec: dict[str, Any]) -> None:
    rec["t"] = rec["t"] + 1.0


def _type(rec: dict[str, Any]) -> None:
    rec["type"] = "sim.other"


def _actor(rec: dict[str, Any]) -> None:
    rec["actor"] = "instructor:zz"


def _payload_value(rec: dict[str, Any]) -> None:
    rec["payload"]["n"] = rec["payload"]["n"] + 1


def _payload_key(rec: dict[str, Any]) -> None:
    rec["payload"]["extra"] = 1


def _payload_nested(rec: dict[str, Any]) -> None:
    rec["payload"]["nested"]["vals"][0] = -1


def _payload_removed(rec: dict[str, Any]) -> None:
    del rec["payload"]["ok"]


def _seq(rec: dict[str, Any]) -> None:
    rec["seq"] = rec["seq"] + 1


def _prev_hash(rec: dict[str, Any]) -> None:
    rec["prev_hash"] = BAD


def _hash(rec: dict[str, Any]) -> None:
    rec["hash"] = BAD


MUTATIONS = [
    _t,
    _type,
    _actor,
    _payload_value,
    _payload_key,
    _payload_nested,
    _payload_removed,
    _seq,
    _prev_hash,
    _hash,
]


@pytest.mark.parametrize("mutate", MUTATIONS, ids=lambda f: f.__name__.lstrip("_"))
def test_any_field_edit_is_caught_at_that_event(mutate: Any) -> None:
    log = build_log()
    for k in range(N):
        rows = copy.deepcopy(dicts(log))
        mutate(rows[k])
        assert verify(rows) == k, f"{mutate.__name__} at {k}"
        assert verify(rows, expected_head=log.head) == k
        with pytest.raises(ChainError) as err:
            EventLog.from_records(rows)
        assert err.value.seq == k


def test_in_place_mutation_of_a_stored_payload_is_caught() -> None:
    for k in (0, 7, N - 1):
        log = build_log()
        log.records[k].payload["n"] = 12345  # frozen model, mutable dict inside
        assert verify(log.records) == k
        with pytest.raises(ChainError) as err:
            EventLog.from_records(log.records)
        assert err.value.seq == k


def test_in_place_nan_in_a_stored_payload_is_reported_not_raised() -> None:
    log = build_log(5)
    log.records[2].payload["n"] = float("nan")
    assert verify(log.records) == 2


def test_recomputed_hash_is_caught_at_the_next_record() -> None:
    log = build_log()
    for k in range(N - 1):
        rows = copy.deepcopy(dicts(log))
        rows[k]["payload"]["n"] = -7
        rehash(rows[k])
        assert verify(rows) == k + 1
        assert verify(rows, expected_head=log.head) == k + 1


def test_recomputed_last_record_is_only_caught_by_the_head() -> None:
    log = build_log()
    rows = copy.deepcopy(dicts(log))
    rows[-1]["payload"]["n"] = -7
    rehash(rows[-1])
    assert verify(rows) is None
    assert verify(rows, expected_head=log.head) == N - 1


def test_a_fully_rewritten_tail_is_caught_only_by_the_head() -> None:
    log = build_log()
    rows = copy.deepcopy(dicts(log))
    for k in range(10, N):
        rows[k]["payload"]["n"] = -k
        if k > 10:
            rows[k]["prev_hash"] = rows[k - 1]["hash"]
        rehash(rows[k])
    assert verify(rows) is None
    assert verify(rows, expected_head=log.head) == N - 1


# --- verify: structural edits ---------------------------------------------------------------


def test_deleting_a_record_is_caught_where_it_was() -> None:
    log = build_log()
    for k in range(N - 1):
        rows = dicts(log)
        del rows[k]
        assert verify(rows) == k


def test_deleting_the_last_record_is_caught_only_by_the_head() -> None:
    rows = dicts(build_log())[:-1]
    assert verify(rows) is None
    assert verify(rows, expected_head=build_log().head) == N - 2


def test_inserting_a_record_is_caught_just_after_it() -> None:
    log = build_log()
    for k in range(N):
        rows = dicts(log)
        rows.insert(k, copy.deepcopy(rows[k]))
        assert verify(rows) == k + 1


def test_inserting_a_forged_record_is_caught_just_after_it() -> None:
    log = build_log()
    rows = dicts(log)
    forged = {
        "seq": 10,
        "t": 3.0,
        "type": "sim.forged",
        "actor": "sim",
        "payload": {},
        "prev_hash": rows[9]["hash"],
    }
    forged["hash"] = record_hash(10, 3.0, "sim.forged", "sim", {}, rows[9]["hash"])
    rows.insert(10, forged)
    assert verify(rows) == 11


def test_swapping_two_records_is_caught_at_the_first() -> None:
    log = build_log()
    for i, j in [(0, 1), (3, 20), (28, 29), (0, N - 1)]:
        rows = dicts(log)
        rows[i], rows[j] = rows[j], rows[i]
        assert verify(rows) == i


def test_truncation_is_caught_only_with_the_head() -> None:
    log = build_log()
    for m in range(N):
        kept = log.records[:m]
        assert verify(kept) is None
        assert verify(kept, expected_head=log.head) == max(m - 1, 0)


def test_empty_log_with_and_without_head() -> None:
    assert verify([]) is None
    assert verify([], expected_head=GENESIS_HASH) is None
    assert verify([], expected_head=BAD) == 0


def test_a_log_starting_mid_chain_is_refused_at_zero() -> None:
    rows = dicts(build_log())[1:]
    assert verify(rows) == 0


# --- invalid mappings and errors ------------------------------------------------------------


def test_invalid_mappings_are_reported_at_their_position() -> None:
    log = build_log()
    for k in (0, 5, N - 1):
        bad_actor = dicts(log)
        bad_actor[k]["actor"] = "Not An Actor"
        missing = dicts(log)
        del missing[k]["payload"]
        extra = dicts(log)
        extra[k]["surprise"] = 1
        bad_hash = dicts(log)
        bad_hash[k]["hash"] = "xyz"
        negative_t = dicts(log)
        negative_t[k]["t"] = -1.0
        for rows in (bad_actor, missing, extra, bad_hash, negative_t):
            assert verify(rows) == k
            with pytest.raises(ChainError) as err:
                EventLog.from_records(rows)
            assert err.value.seq == k


def test_non_mapping_rows_are_reported() -> None:
    rows: list[Any] = [*dicts(build_log(2)), ["not", "a", "record"]]
    assert verify(rows) == 2


def test_chain_error_carries_position_and_message() -> None:
    err = ChainError(4)
    assert err.seq == 4
    assert "4" in str(err)
    assert isinstance(err, ValueError)
    assert str(ChainError(1, "custom")) == "custom"


def test_from_jsonl_reports_the_first_bad_line() -> None:
    lines = build_log(6).to_jsonl().splitlines()
    tampered = lines.copy()
    row = json.loads(tampered[3])
    row["payload"]["n"] = -1
    tampered[3] = json.dumps(row)
    with pytest.raises(ChainError) as err:
        EventLog.from_jsonl("\n".join(tampered) + "\n")
    assert err.value.seq == 3

    broken = lines.copy()
    broken[2] = "{not json"
    with pytest.raises(ChainError, match="not valid JSON") as err2:
        EventLog.from_jsonl("\n".join(broken) + "\n")
    assert err2.value.seq == 2

    with pytest.raises(ChainError) as err3:
        EventLog.from_jsonl("\n".join([*lines[:2], "", *lines[2:]]) + "\n")
    assert err3.value.seq == 2

    with pytest.raises(ChainError) as err4:
        EventLog.from_jsonl("\n".join([*lines[:2], "[1]"]) + "\n")
    assert err4.value.seq == 2


# --- golden digest --------------------------------------------------------------------------


def test_golden_head_pins_the_canonical_form() -> None:
    log = EventLog()
    log.append(0, "sim.session_start", "system", {"seed": 42, "scenario": "demo-range"})
    log.append(3, "sensor.detection", "sim", {"track": "T01", "range_m": 1250.5, "ok": True})
    log.append(
        40,
        "trainee.classified",
        "trainee:op-1",
        {"label": "multirotor", "conf": [0.75, 0.25], "note": "नमस्ते"},
    )
    assert [r.hash for r in log.records] == GOLDEN_HASHES
    assert log.head == GOLDEN_HASHES[-1]


GOLDEN_HASHES = [
    "31248676bba10e271805c0b66a23ae334e77109787459560703e731a1df27cec",
    "d6cf61c171b47bbf90b328a03b7df48b27c5cef96066c275394580d2946c04ce",
    "5351b0ff29d561d3fca3ee25ddfbc578b8d6583a183f3bac0b0e5b5b9d508c6a",
]


def test_golden_first_hash_matches_an_independent_sha256() -> None:
    """Hash the literal canonical text with hashlib, so the pin is not circular."""
    text = (
        '{"actor":"system","payload":{"scenario":"demo-range","seed":42},'
        f'"prev_hash":"{GENESIS_HASH}","seq":0,"t":0.0,"type":"sim.session_start"}}'
    )
    assert hashlib.sha256(text.encode()).hexdigest() == GOLDEN_HASHES[0]


# --- property-based -------------------------------------------------------------------------

json_leaf = (
    st.none()
    | st.booleans()
    | st.integers(min_value=-(2**53), max_value=2**53)
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(alphabet=st.characters(codec="utf-8"), max_size=12)
)
json_value = st.recursive(
    json_leaf,
    lambda inner: (
        st.lists(inner, max_size=3)
        | st.dictionaries(
            st.text(alphabet=st.characters(codec="utf-8"), max_size=6),
            inner,
            max_size=3,
        )
    ),
    max_leaves=8,
)
payloads = st.dictionaries(
    st.text(alphabet="abcxyz_", min_size=1, max_size=4), json_value, max_size=4
)
events = st.lists(
    st.tuples(
        st.integers(min_value=0, max_value=5),
        st.sampled_from(TYPES),
        st.sampled_from(ACTORS),
        payloads,
    ),
    min_size=1,
    max_size=12,
)


def build_from(spec: list[tuple[int, str, str, dict[str, Any]]]) -> EventLog:
    log = EventLog()
    tick = 0
    for step, type_, actor, payload in spec:
        tick += step
        log.append(tick, type_, actor, payload)
    return log


@given(events)
def test_property_round_trip_and_verify(spec: list[tuple[int, str, str, dict[str, Any]]]) -> None:
    log = build_from(spec)
    assert verify(log.records, expected_head=log.head) is None
    back = EventLog.from_jsonl(log.to_jsonl())
    assert back.records == log.records
    assert back.head == log.head
    assert back.to_jsonl() == log.to_jsonl()


@given(events, st.data())
def test_property_tampering_is_caught_at_k_and_recompute_at_k_plus_1(
    spec: list[tuple[int, str, str, dict[str, Any]]], data: st.DataObject
) -> None:
    log = build_from(spec)
    n = len(log)
    k = data.draw(st.integers(min_value=0, max_value=n - 1))
    field = data.draw(
        st.sampled_from(["t", "type", "actor", "payload", "seq", "prev_hash", "hash"])
    )
    rows = dicts(log)
    rec = rows[k]
    if field == "t":
        rec["t"] = rec["t"] + 0.05
    elif field == "type":
        rec["type"] = "sim.changed"
    elif field == "actor":
        rec["actor"] = "instructor:changed"
    elif field == "payload":
        rec["payload"] = {**rec["payload"], "tampered": data.draw(json_value)}
    elif field == "seq":
        rec["seq"] = rec["seq"] + 1
    elif field == "prev_hash":
        rec["prev_hash"] = BAD
    else:
        rec["hash"] = BAD
    assert verify(rows) == k

    # A tamperer who fixes the hash is caught by the next record, or by the head at the end.
    if field in ("t", "type", "actor", "payload"):
        rehash(rec)
        assert verify(rows) == (k + 1 if k + 1 < n else None)
        assert verify(rows, expected_head=log.head) == min(k + 1, n - 1)
