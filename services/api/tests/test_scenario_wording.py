"""Every UI, doc and API string about solvability says "verified solvable by test run". Nothing
the scenario engine ships may say "provably" or "guaranteed" (ADR-008)."""

import json
import re
from pathlib import Path

from app.scenarios.solvability import NOT_VERIFIED, VERIFIED

REPO = Path(__file__).resolve().parents[3]
BANNED = re.compile(r"provabl|guarante", re.IGNORECASE)


def shipped_files() -> list[Path]:
    api = REPO / "services" / "api" / "app"
    files = [
        *sorted((api / "scenarios").glob("*.py")),
        api / "routers" / "scenarios.py",
        REPO / "docs" / "SCENARIO_ENGINE.md",
        *sorted((REPO / "packs" / "scenarios").glob("*.yaml")),
        *sorted((REPO / "packs" / "scenarios").glob("*.md")),
    ]
    web = REPO / "apps" / "web" / "src"
    if (web / "scenarios").is_dir():
        files += [p for p in sorted((web / "scenarios").rglob("*")) if p.is_file()]
    return files


def test_no_shipped_scenario_text_says_provably_or_guaranteed() -> None:
    files = shipped_files()
    assert len(files) > 20
    hits = [
        f"{p.relative_to(REPO)}:{n}: {line.strip()[:80]}"
        for p in files
        for n, line in enumerate(p.read_text("utf-8").splitlines(), 1)
        if BANNED.search(line)
    ]
    assert not hits, "\n".join(hits)


def test_the_message_catalogues_have_no_banned_word_in_the_scenario_namespace() -> None:
    for lang in ("en", "hi"):
        catalogue = json.loads((REPO / "apps/web/src/i18n" / f"{lang}.json").read_text("utf-8"))
        text = json.dumps(catalogue.get("scenarios", {}), ensure_ascii=False)
        assert not BANNED.search(text), lang


def test_the_fixed_phrases_are_the_agreed_ones() -> None:
    assert VERIFIED == "verified solvable by test run"
    assert NOT_VERIFIED == "not verified solvable"
    doc = (REPO / "docs" / "SCENARIO_ENGINE.md").read_text("utf-8")
    assert "verified solvable by test run" in doc


def test_the_checker_catches_what_it_is_for() -> None:
    for phrase in ("provably solvable", "Guaranteed to work", "a guarantee", "PROVABLE"):
        assert BANNED.search(phrase), phrase
    assert not BANNED.search("verified solvable by test run")
