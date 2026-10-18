"""`GET /api/v1/terrain/{pack}/{file}`: signed-in users, an allow-list of files, nothing else."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.routers import terrain as terrain_router
from tests.live_support import live_app, login
from tests.terrain_support import write_pack

PACK = "endpoint-pack"


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    directory = write_pack(tmp_path / "packs", PACK)
    (directory / "terrain.glb").write_bytes(b"glTF\x02\x00\x00\x00")
    (directory / "ATTRIBUTION.md").write_text("# Attribution\n© OpenStreetMap contributors\n")
    (directory / "secret.txt").write_text("not served")
    monkeypatch.setattr(terrain_router, "pack_dir", lambda pack_id: tmp_path / "packs" / pack_id)
    with live_app(tmp_path) as client:
        yield client


def test_a_signed_in_user_reads_each_kind_of_file(served: TestClient) -> None:
    login(served)
    manifest = served.get(f"/api/v1/terrain/{PACK}/manifest.json")
    assert manifest.status_code == 200 and manifest.json()["id"] == PACK
    assert manifest.headers["content-type"].startswith("application/json")
    assert "max-age" in manifest.headers["cache-control"]
    heights = served.get(f"/api/v1/terrain/{PACK}/heights.i16")
    assert heights.status_code == 200 and len(heights.content) == 41 * 41 * 2
    assert heights.headers["content-type"] == "application/octet-stream"
    glb = served.get(f"/api/v1/terrain/{PACK}/terrain.glb")
    assert glb.headers["content-type"] == "model/gltf-binary" and glb.content.startswith(b"glTF")
    notice = served.get(f"/api/v1/terrain/{PACK}/ATTRIBUTION.md")
    assert "OpenStreetMap contributors" in notice.text


def test_every_role_that_plays_or_administers_can_read(served: TestClient) -> None:
    for who in ("trainee2", "instructor", "admin"):
        login(served, who)
        assert served.get(f"/api/v1/terrain/{PACK}/manifest.json").status_code == 200


def test_signing_in_is_required(served: TestClient) -> None:
    assert served.get(f"/api/v1/terrain/{PACK}/manifest.json").status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        f"{PACK}/secret.txt",  # exists, not on the allow-list
        f"{PACK}/vegetation.json",  # on the list, not in this pack
        f"{PACK}/buildings.glb",
        "no-such-pack/manifest.json",
        "Bad_Pack/manifest.json",
        "..%2f..%2fetc/manifest.json",
        f"{PACK}/..%2fmanifest.json",
        f"{PACK}/manifest.json%00.png",
    ],
)
def test_anything_else_is_a_404(served: TestClient, path: str) -> None:
    login(served)
    assert served.get(f"/api/v1/terrain/{path}").status_code == 404


def test_the_shipped_scenarios_name_no_missing_pack() -> None:
    # Every scenario that names a pack must have it on disk (flat scenarios name none).
    from app.contracts import ScenarioSpec
    from app.contracts.loader import load_pack
    from app.contracts.scenario import PackTerrain
    from tests.sim_cases import REPO

    for path in sorted((REPO / "packs" / "scenarios").glob("*.json")):
        spec = load_pack(path)
        assert isinstance(spec, ScenarioSpec)
        if isinstance(spec.world.terrain, PackTerrain):
            assert (REPO / "packs" / "terrain" / spec.world.terrain.id / "manifest.json").is_file()
