"""Canonical JSON and SHA-256 hashing, shared by the event log and state hashes.

Keys are sorted, separators are compact, text is UTF-8 and NaN or infinity is refused, so the
same value always gives the same bytes. Floats use Python's shortest round-trip repr, which is
identical on every platform for IEEE-754 doubles.
"""

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()
