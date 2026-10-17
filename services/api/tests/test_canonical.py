import math

import pytest

from sim.canonical import canonical_json, sha256_hex


def test_key_order_and_whitespace_do_not_matter() -> None:
    assert canonical_json({"b": 1, "a": [1.5, "x"]}) == b'{"a":[1.5,"x"],"b":1}'
    assert sha256_hex({"b": 1, "a": 2}) == sha256_hex({"a": 2, "b": 1})


def test_text_is_utf8_not_escaped() -> None:
    assert canonical_json({"hi": "संपर्क"}) == '{"hi":"संपर्क"}'.encode()


def test_floats_use_shortest_round_trip_repr() -> None:
    assert canonical_json([0.1, 3 / 20, 1e-7, 2.0]) == b"[0.1,0.15,1e-07,2.0]"


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_numbers_are_refused(bad: float) -> None:
    with pytest.raises(ValueError):
        canonical_json({"v": bad})


def test_known_digest_is_stable() -> None:
    # pinned so an accidental change to the canonical form fails loudly
    assert (
        sha256_hex({"seq": 0}) == "0b4a4b8d8ded37902ac671f24db72af504765ef7016d8030dc18b71edd42d092"
    )
