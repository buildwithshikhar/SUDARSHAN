import json
from pathlib import Path

import pytest

from app import brand
from app.config import Settings


def test_blank_admin_env_is_unset() -> None:
    settings = Settings(first_admin_email="", first_admin_password="")
    assert settings.first_admin_email is None
    assert settings.first_admin_password is None


def test_cors_origin_list_splits_and_trims() -> None:
    assert Settings(cors_origins=" https://a.example , ,https://b.example").cors_origin_list == [
        "https://a.example",
        "https://b.example",
    ]


@pytest.mark.parametrize("value", ["", "change-me", "CHANGEME", "replace-with-a-long-random-value"])
def test_placeholder_secrets_are_rejected(value: str) -> None:
    assert "placeholder" in (Settings(secret_key=value).secret_problem() or "")


def test_short_secret_is_rejected() -> None:
    assert "shorter" in (Settings(secret_key="x" * 31).secret_problem() or "")


def test_long_secret_is_accepted() -> None:
    assert Settings(secret_key="x" * 32).secret_problem() is None


def test_brand_file_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "brand.json"
    path.write_text(json.dumps({"productName": "Test", "descriptor": "d", "status": "draft"}))
    monkeypatch.setenv("BRAND_FILE", str(path))
    brand.load_brand.cache_clear()
    try:
        assert brand.load_brand().productName == "Test"
    finally:
        brand.load_brand.cache_clear()


def test_brand_found_by_walking_up() -> None:
    brand.load_brand.cache_clear()
    assert brand.load_brand().productName
