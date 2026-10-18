"""Every explanation the evaluator can give exists in English and in Hindi."""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.scoring.keys import ALL_KEYS, FINDING_REASONS, LESSON_KEYS, NODE_REASONS, REPORT_REASONS

I18N = Path(__file__).resolve().parents[3] / "apps" / "web" / "src" / "i18n"
GOLDEN = Path(__file__).parent / "golden" / "scoring"
DEVANAGARI = re.compile("[ऀ-ॿ]")
PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def catalogue(language: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((I18N / f"{language}.json").read_text(encoding="utf-8"))
    return data["scoring"]  # type: ignore[no-any-return]


def lookup(tree: dict[str, Any], key: str) -> object:
    node: Any = tree
    for part in key.split("."):
        node = node[part]
    return node


def test_the_key_lists_have_no_duplicates() -> None:
    assert len(ALL_KEYS) == len(set(ALL_KEYS))
    assert len(ALL_KEYS) == (
        len(NODE_REASONS) + len(REPORT_REASONS) + len(FINDING_REASONS) + len(LESSON_KEYS)
    )


@pytest.mark.parametrize("key", ALL_KEYS)
def test_every_key_has_a_message_in_both_languages(key: str) -> None:
    english, hindi = lookup(catalogue("en"), key), lookup(catalogue("hi"), key)
    assert isinstance(english, str) and english.strip(), f"{key}: no English"
    assert isinstance(hindi, str) and hindi.strip(), f"{key}: no Hindi"
    assert DEVANAGARI.search(hindi), f"{key}: the Hindi message has no Devanagari text"
    assert set(PLACEHOLDER.findall(english)) == set(PLACEHOLDER.findall(hindi)), key


def test_every_key_a_golden_fixture_produces_is_listed() -> None:
    seen: set[str] = set()
    for path in sorted(GOLDEN.glob("*.json")):
        expected = json.loads(path.read_text(encoding="utf-8")).get("expect", {})
        seen |= set(re.findall(r'"(?:reason|key)": "([a-z][a-z0-9.-]+)"', json.dumps(expected)))
    assert seen, "no keys found in the golden fixtures"
    assert seen <= set(ALL_KEYS), sorted(seen - set(ALL_KEYS))
