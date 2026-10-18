"""The packs shipped in packs/terrain must match their manifests. Reads packs only, not raw data."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import terrain.pack as pack_mod
from conftest import make_tile
from terrain.cli import main
from terrain.osm import OsmData
from terrain.pack import Area, bake_area, verify_pack, write_pack

PACKS = Path(__file__).resolve().parents[3] / "packs" / "terrain"
COMMITTED = sorted(p.parent for p in PACKS.glob("*/manifest.json"))
EXPECTED = ("heron-ridge", "osprey-town")


def test_committed_packs_verify_against_their_manifests() -> None:
    if not COMMITTED:
        pytest.skip("no baked packs under packs/terrain yet (run make terrain)")
    assert [p.name for p in COMMITTED] == list(EXPECTED)
    for pack in COMMITTED:
        assert verify_pack(pack) == [], pack.name


def test_committed_packs_are_honestly_labelled_and_small() -> None:
    if not COMMITTED:
        pytest.skip("no baked packs under packs/terrain yet (run make terrain)")
    for pack in COMMITTED:
        m = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
        assert m["label"].startswith("reference data")
        assert m["bake"]["reproducible"] is True
        assert sum(f.stat().st_size for f in pack.iterdir()) < 6_000_000
        attribution = (pack / "ATTRIBUTION.md").read_text(encoding="utf-8")
        assert "OpenStreetMap contributors" in attribution and "ODbL" in attribution
        assert "SRTM" in attribution and "fictional" in attribution
        assert m["name"] in ("Heron Ridge", "Osprey Town")
        for bad in ("Satara", "Maharashtra", "India"):
            assert bad not in json.dumps(m) and bad not in attribution


def test_cli_verify_reports_ok_and_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    osm_data: OsmData,
    area: Area,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(pack_mod, "read_osm", lambda path, bbox: osm_data)
    files, _ = bake_area(area, make_tile(), tmp_path / "x.pbf")
    write_pack(tmp_path / "p", files)
    assert main(["verify", str(tmp_path / "p")]) == 0
    assert "OK" in capsys.readouterr().out
    (tmp_path / "p" / "vegetation.json").write_bytes(b"{}")
    assert main(["verify", str(tmp_path / "p")]) == 1
    assert "vegetation.json" in capsys.readouterr().err
