"""Seed-share codes: a request round-trips exactly; a mistyped code is refused (SCENARIO_ENGINE.md)."""

import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.scenarios import sharecode
from app.scenarios.request import (
    ARCHETYPES,
    GENERATOR_VERSION,
    TERRAINS,
    TIMES_OF_DAY,
    WEATHERS,
    DifficultyVector,
    GeneratorRequest,
)
from app.scenarios.sharecode import ALPHABET, Decoded, ShareCodeError, decode, encode

percent = st.integers(0, 100)
requests = st.builds(
    GeneratorRequest,
    seed=st.one_of(st.sampled_from([0, 1, 2**63 - 1]), st.integers(0, 2**63 - 1)),
    terrain=st.sampled_from(TERRAINS),
    time_of_day=st.sampled_from(TIMES_OF_DAY),
    weather=st.sampled_from(WEATHERS),
    difficulty=st.builds(
        DifficultyVector,
        threat_load=percent,
        ambiguity=percent,
        speed=percent,
        stealth=percent,
        degradation=percent,
    ),
    threat_mix=st.lists(st.sampled_from(ARCHETYPES), min_size=1, max_size=6, unique=True),
    oracle_min_score=st.integers(50, 100),
    max_attempts=st.integers(1, 64),
)
versions = st.tuples(st.integers(0, 255), st.integers(0, 255), st.integers(0, 255)).map(
    lambda p: ".".join(map(str, p))
)


@settings(max_examples=300, deadline=None)
@given(requests, versions)
def test_round_trip_is_exact(request: GeneratorRequest, version: str) -> None:
    code = encode(request, version)
    assert re.fullmatch(r"[A-Z0-9-]+", code)
    assert len(code) <= 96
    assert decode(code) == Decoded(request, version)


def test_extremes_round_trip() -> None:
    for seed in (0, 2**63 - 1):
        r = GeneratorRequest(seed=seed)
        assert decode(encode(r)) == Decoded(r, GENERATOR_VERSION)


def test_shape_and_alphabet() -> None:
    code = encode(GeneratorRequest(seed=260207))
    assert code.startswith("SD1-")
    groups = code.split("-")
    assert all(len(g) == 4 for g in groups[1:-1]) and 1 <= len(groups[-1]) <= 4
    assert not set("".join(groups[1:])) - set(ALPHABET)
    assert not set("01OI") & set(ALPHABET)
    assert len(ALPHABET) == 32


def test_same_request_same_code_and_distinct_requests_differ() -> None:
    a, b = GeneratorRequest(seed=5), GeneratorRequest(seed=6)
    assert encode(a) == encode(GeneratorRequest(seed=5)) != encode(b)
    assert encode(a, "1.0.0") != encode(a, "1.0.1")


def test_tolerates_case_spaces_and_missing_dashes() -> None:
    r = GeneratorRequest(seed=99, terrain="osprey-town", time_of_day="night")
    code = encode(r)
    for form in (
        code.lower(),
        code.replace("-", ""),
        code.replace("-", " "),
        f"  {code.lower().replace('-', ' ')}\n",
        code.replace("-", "_"),
    ):
        assert decode(form).request == r


def test_every_flipped_character_is_rejected() -> None:
    code = encode(GeneratorRequest(seed=123456789, difficulty=DifficultyVector(speed=77)))
    body = code[4:]
    for i, c in enumerate(body):
        if c == "-":
            continue
        other = ALPHABET[(ALPHABET.index(c) + 1) % 32]
        with pytest.raises(ShareCodeError):
            decode(f"SD1-{body[:i]}{other}{body[i + 1 :]}")


@pytest.mark.parametrize(
    "bad",
    ["", "SD1", "SD2-ABCD", "XX1-ABCD-EFGH", "hello", "SD1-ABCD", "SD1-" + "A" * 40],
)
def test_malformed_input_is_refused(bad: str) -> None:
    with pytest.raises(ShareCodeError):
        decode(bad)


def test_bad_characters() -> None:
    good = encode(GeneratorRequest(seed=1)).replace("-", "")
    for ch in "01OI*":
        with pytest.raises(ShareCodeError, match="not used"):
            decode(good[:5] + ch + good[6:])


def _forge(payload: bytes, *, crc: bool = True, pad: int = 0) -> str:
    """A well-formed code around arbitrary payload bytes."""
    full = payload + (sharecode._crc16(payload) if crc else 0).to_bytes(2, "big")
    number = (int.from_bytes(full, "big") << sharecode._PAD_BITS) | pad
    n = sharecode._CHARS
    return "SD1" + "".join(ALPHABET[(number >> (5 * (n - 1 - i))) & 31] for i in range(n))


def _payload(**over: int) -> bytes:
    fields = {
        "seed": 7, "terrain": 0, "tod": 1, "weather": 0, "a": 40, "b": 40, "c": 40, "d": 40,
        "e": 0, "mask": 63, "min": 80, "attempts": 12, "v": 0x010000,
    }  # fmt: skip
    fields.update(over)
    return (
        fields["seed"].to_bytes(8, "big")
        + bytes(
            [fields[k] for k in ("terrain", "tod", "weather", "a", "b", "c", "d", "e", "mask")]
            + [fields["min"], fields["attempts"]]
        )
        + fields["v"].to_bytes(3, "big")
    )


def test_forge_helper_makes_a_valid_code() -> None:
    assert decode(_forge(_payload())).request.seed == 7


@pytest.mark.parametrize(
    "over",
    [
        {"terrain": 3},
        {"tod": 4},
        {"weather": 5},
        {"mask": 0},
        {"mask": 64},
        {"a": 101},
        {"e": 255},
        {"min": 49},
        {"min": 101},
        {"attempts": 0},
        {"attempts": 65},
        {"seed": 2**63},
    ],
)
def test_unknown_field_values_are_refused(over: dict[str, int]) -> None:
    with pytest.raises(ShareCodeError):
        decode(_forge(_payload(**over)))


def test_padding_bits_must_be_zero() -> None:
    with pytest.raises(ShareCodeError, match="padding"):
        decode(_forge(_payload(), pad=1))


def test_unreadable_checksum() -> None:
    with pytest.raises(ShareCodeError, match="checksum"):
        decode(_forge(_payload(), crc=False))


@pytest.mark.parametrize("version", ["1.0", "1.0.256", "a.b.c", "1.0.0.0", ""])
def test_version_that_cannot_be_carried(version: str) -> None:
    with pytest.raises(ShareCodeError, match="cannot be carried"):
        encode(GeneratorRequest(seed=1), version)


def test_share_code_fits_the_contract_field() -> None:
    from app.contracts.scenario import GeneratedFrom

    code = encode(GeneratorRequest(seed=2**63 - 1))
    GeneratedFrom(generator_version=GENERATOR_VERSION, code=code)


def test_generator_version_is_reported() -> None:
    assert decode(encode(GeneratorRequest(seed=1), "2.14.9")).generator_version == "2.14.9"
