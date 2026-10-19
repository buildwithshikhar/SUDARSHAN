"""Seed-share codes: a generator request, its seed and the generator version in a short string.

A code such as `SD1-4F2K-...` carries everything `generate` needs, so an instructor can hand a
scenario to a colleague in a message: decode it, generate again, and the spec is identical (same
request, same generator version). A code made by another generator version still decodes, and the
caller warns that the spec will differ.

Layout (24 bytes, big-endian): seed (8), terrain (1), time of day (1), weather (1), the five
difficulty values (5), the threat-mix bitmask (1), `oracle_min_score` (1), `max_attempts` (1), the
generator version as major, minor, patch (3) and a CRC-16/CCITT-FALSE of the first 22 bytes (2).
The bytes are written in a 32-character alphabet without look-alikes (no 0, 1, O, I), in groups of
four after the prefix `SD1-`; the 1 is the version of this code format.
"""

import re
from dataclasses import dataclass

from pydantic import ValidationError

from .request import (
    ARCHETYPES,
    GENERATOR_VERSION,
    TERRAINS,
    TIMES_OF_DAY,
    WEATHERS,
    DifficultyVector,
    GeneratorRequest,
)

PREFIX = "SD1"
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_INDEX = {c: i for i, c in enumerate(ALPHABET)}
_PAYLOAD_BYTES = 22
_TOTAL_BYTES = _PAYLOAD_BYTES + 2
_CHARS = -(-_TOTAL_BYTES * 8 // 5)
_PAD_BITS = _CHARS * 5 - _TOTAL_BYTES * 8
_GROUP = 4
_VERSION = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")
_STRIP = re.compile(r"[\s\-_]+")


class ShareCodeError(ValueError):
    """The text is not a seed-share code this generator can read."""


@dataclass(frozen=True, slots=True)
class Decoded:
    request: GeneratorRequest
    generator_version: str


def _crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _version_bytes(version: str) -> bytes:
    found = _VERSION.match(version)
    parts = [int(p) for p in found.groups()] if found else []
    if len(parts) != 3 or any(p > 255 for p in parts):
        raise ShareCodeError(f"generator version {version!r} cannot be carried in a code")
    return bytes(parts)


def encode(request: GeneratorRequest, generator_version: str = GENERATOR_VERSION) -> str:
    """The share code for a request made for this generator version."""
    d = request.difficulty
    mask = sum(1 << ARCHETYPES.index(a) for a in request.threat_mix)
    payload = (
        request.seed.to_bytes(8, "big")
        + bytes(
            [
                TERRAINS.index(request.terrain),
                TIMES_OF_DAY.index(request.time_of_day),
                WEATHERS.index(request.weather),
                d.threat_load,
                d.ambiguity,
                d.speed,
                d.stealth,
                d.degradation,
                mask,
                request.oracle_min_score,
                request.max_attempts,
            ]
        )
        + _version_bytes(generator_version)
    )
    raw = payload + _crc16(payload).to_bytes(2, "big")
    number = int.from_bytes(raw, "big") << _PAD_BITS
    text = "".join(ALPHABET[(number >> (5 * (_CHARS - 1 - i))) & 31] for i in range(_CHARS))
    groups = [text[i : i + _GROUP] for i in range(0, len(text), _GROUP)]
    return "-".join([PREFIX, *groups])


def _normalise(code: str) -> str:
    text = _STRIP.sub("", code).upper()
    if not text.startswith(PREFIX):
        raise ShareCodeError("not a seed-share code: it should start with SD1")
    return text[len(PREFIX) :]


def decode(code: str) -> Decoded:
    """The request and generator version a code carries; `ShareCodeError` if it is malformed.

    Case, spaces and missing dashes are tolerated."""
    body = _normalise(code)
    if len(body) != _CHARS:
        raise ShareCodeError(
            f"a seed-share code has {_CHARS} characters after SD1, not {len(body)}"
        )
    number = 0
    for c in body:
        if c not in _INDEX:
            raise ShareCodeError(f"character {c!r} is not used in seed-share codes")
        number = (number << 5) | _INDEX[c]
    if number & ((1 << _PAD_BITS) - 1):
        raise ShareCodeError("the code is malformed (padding bits are set)")
    raw = (number >> _PAD_BITS).to_bytes(_TOTAL_BYTES, "big")
    payload, check = raw[:_PAYLOAD_BYTES], int.from_bytes(raw[_PAYLOAD_BYTES:], "big")
    if _crc16(payload) != check:
        raise ShareCodeError("the checksum does not match: the code was mistyped or changed")
    return Decoded(_request(payload), ".".join(str(b) for b in payload[19:22]))


def _request(payload: bytes) -> GeneratorRequest:
    seed = int.from_bytes(payload[:8], "big")
    terrain, tod, weather = payload[8], payload[9], payload[10]
    mask = payload[16]
    if terrain >= len(TERRAINS) or tod >= len(TIMES_OF_DAY) or weather >= len(WEATHERS):
        raise ShareCodeError("the code names a terrain, time of day or weather this build lacks")
    if not 0 < mask < 1 << len(ARCHETYPES):
        raise ShareCodeError("the code names no threat mix, or one this build lacks")
    try:
        return GeneratorRequest.model_validate(
            {
                "seed": seed,
                "terrain": TERRAINS[terrain],
                "time_of_day": TIMES_OF_DAY[tod],
                "weather": WEATHERS[weather],
                "difficulty": DifficultyVector(
                    threat_load=payload[11],
                    ambiguity=payload[12],
                    speed=payload[13],
                    stealth=payload[14],
                    degradation=payload[15],
                ),
                "threat_mix": [a for i, a in enumerate(ARCHETYPES) if mask >> i & 1],
                "oracle_min_score": payload[17],
                "max_attempts": payload[18],
            }
        )
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(p) for p in first["loc"])
        raise ShareCodeError(f"the code carries a value out of range ({where})") from error
