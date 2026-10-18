from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

import terrain.pack as pack_mod
from terrain.buildings import signed_area
from terrain.glb import parse_glb
from terrain.landcover import landcover_class, render_landcover
from terrain.osm import OsmData
from terrain.pack import (
    FILE_ORDER,
    Area,
    bake_area,
    build_files,
    load_areas,
    verify_pack,
    write_pack,
)
from terrain.srtm import SrtmTile
from terrain.vegetation import MAX_TREES, scatter_trees


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch, osm_data: OsmData) -> None:
    monkeypatch.setattr(pack_mod, "read_osm", lambda path, bbox: osm_data)


def test_bake_is_byte_identical_across_runs(
    patched: None, area: Area, tile: SrtmTile, tmp_path: Path
) -> None:
    a, _ = bake_area(area, tile, tmp_path / "x.pbf")
    b, _ = bake_area(area, tile, tmp_path / "x.pbf")
    assert a.keys() == b.keys()
    for name in a:
        assert hashlib.sha256(a[name]).digest() == hashlib.sha256(b[name]).digest(), name
    assert json.loads(a["manifest.json"])["bake"]["reproducible"] is True


def test_pack_contents_match_the_spec(
    patched: None, area: Area, tile: SrtmTile, tmp_path: Path
) -> None:
    files, rep = bake_area(area, tile, tmp_path / "x.pbf")
    assert set(files) == {*FILE_ORDER, "manifest.json"}
    m = json.loads(files["manifest.json"])
    assert m["format"] == "terrain-pack.v1" and m["id"] == "test-area"
    assert m["heightmap"]["size"] == 33 and m["heightmap"]["cell_m"] == 31.25
    assert m["frame"]["half_extent_m"] == 500
    assert [s["register_id"] for s in m["sources"]] == ["G01", "G02"]
    assert set(m["files"]) == set(FILE_ORDER)
    for name, digest in m["files"].items():
        assert hashlib.sha256(files[name]).hexdigest() == digest

    # heights: int16 little-endian, row-major, relative to a datum rounded to 0.1 m
    q = np.frombuffer(files["heights.i16"], dtype="<i2").reshape(33, 33)
    assert len(files["heights.i16"]) == 33 * 33 * 2
    assert q.min() == 0 or 0 <= q.min() <= 1  # the datum is the lowest post, rounded down
    assert round(float(q.min()) * 0.1, 1) == m["heightmap"]["min_m"]
    assert round(float(q.max()) * 0.1, 1) == m["heightmap"]["max_m"]
    assert round(m["frame"]["datum_m"], 1) == m["frame"]["datum_m"]
    # plane rises east and north in the synthetic tile, so row 0 / column 0 is the low corner
    assert q[0, 0] < q[0, 32] and q[0, 0] < q[32, 0]

    # buildings: w4 (military) and w5 (inside the dropped military area) are gone;
    # w6 crosses the edge
    b = json.loads(files["buildings.json"])
    assert b["format"] == "terrain-buildings.v1"
    ids = [x["id"] for x in b["buildings"]]
    assert ids == ["w1", "w2", "w3"] == sorted(ids)
    assert m["buildings"]["count"] == 3
    assert m["buildings"]["height_source"] == {"tag": 1, "levels": 1, "default": 1}
    assert m["bake"]["dropped_buildings"] == {
        "invalid_footprint": 0,
        "outside_square": 1,
        "sensitive_feature": 2,
        "over_building_cap": 0,
    }
    for x in b["buildings"]:
        assert signed_area([tuple(p) for p in x["footprint"]]) > 0
        assert x["height_source"] in ("tag", "levels", "default")

    # vegetation: sorted by (y, x), within the square, heights 5 to 14 m
    v = json.loads(files["vegetation.json"])
    trees = v["trees"]
    assert trees == sorted(trees, key=lambda t: (t[1], t[0], t[2]))
    assert m["vegetation"]["count"] == len(trees) > 0
    assert all(abs(t[0]) <= 500 and abs(t[1]) <= 500 and 5.0 <= t[2] <= 14.0 for t in trees)

    # no timestamps or real place names in the manifest or attribution
    text = files["manifest.json"].decode() + files["ATTRIBUTION.md"].decode()
    assert "Test Area" in text and "OpenStreetMap contributors" in text and "ODbL" in text
    assert "Derivative Database" in text and "SRTM" in text
    assert "fictional" in text
    assert rep.sensitive_areas_dropped == 2  # military landuse and building


def test_meshes_parse_and_agree_with_the_data(
    patched: None, area: Area, tile: SrtmTile, tmp_path: Path
) -> None:
    files, _ = bake_area(area, tile, tmp_path / "x.pbf")
    doc, binary = parse_glb(files["terrain.glb"])
    assert len(doc["images"]) == 1 and doc["images"][0]["mimeType"] == "image/png"
    view = doc["bufferViews"][doc["images"][0]["bufferView"]]
    png = binary[view["byteOffset"] : view["byteOffset"] + view["byteLength"]]
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    prim = doc["meshes"][0]["primitives"][0]
    assert doc["accessors"][prim["attributes"]["POSITION"]]["count"] == 33 * 33
    assert doc["accessors"][prim["indices"]]["count"] == 32 * 32 * 6
    assert "TEXCOORD_0" in prim["attributes"]

    bdoc, _ = parse_glb(files["buildings.glb"])
    prims = bdoc["meshes"][0]["primitives"]
    assert len(prims) == 2 and len(bdoc["materials"]) == 2  # walls and roofs
    assert bdoc["accessors"][prims[0]["attributes"]["POSITION"]]["count"] == 3 * 16
    assert bdoc["accessors"][prims[1]["attributes"]["POSITION"]]["count"] == 3 * 4


def test_verify_pack_accepts_and_detects_tampering(
    patched: None, area: Area, tile: SrtmTile, tmp_path: Path
) -> None:
    files, _ = bake_area(area, tile, tmp_path / "x.pbf")
    out = tmp_path / "pack"
    write_pack(out, files)
    assert verify_pack(out) == []
    (out / "buildings.json").write_bytes(files["buildings.json"] + b" ")
    assert any("buildings.json" in e for e in verify_pack(out))
    (out / "buildings.json").write_bytes(files["buildings.json"])
    (out / "extra.txt").write_text("x")
    assert any("extra.txt" in e for e in verify_pack(out))
    (out / "extra.txt").unlink()
    (out / "heights.i16").unlink()
    assert any("heights.i16" in e for e in verify_pack(out))
    assert verify_pack(tmp_path / "nowhere")


def test_building_cap_keeps_largest_and_updates_counts(
    patched: None, area: Area, tile: SrtmTile, tmp_path: Path
) -> None:
    capped = Area(**{**area.__dict__, "building_cap": 2})
    files, rep = build_files(capped, tile, tmp_path / "x.pbf")
    ids = [x["id"] for x in json.loads(files["buildings.json"])["buildings"]]
    assert ids == ["w1", "w2"]  # 200 m2 and 144 m2 beat 120 m2
    assert rep.buildings.dropped_over_cap == 1 and rep.buildings.kept == 2
    assert sum(rep.buildings.height_source.values()) == 2


def test_different_seed_changes_only_the_scatter(
    patched: None, area: Area, tile: SrtmTile, tmp_path: Path
) -> None:
    a, _ = build_files(area, tile, tmp_path / "x.pbf")
    b, _ = build_files(Area(**{**area.__dict__, "seed": 8}), tile, tmp_path / "x.pbf")
    assert a["heights.i16"] == b["heights.i16"] and a["buildings.json"] == b["buildings.json"]
    assert a["vegetation.json"] != b["vegetation.json"]


def test_scatter_is_capped_seeded_and_inside_polygons() -> None:
    square = [(-900.0, -900.0), (900.0, -900.0), (900.0, 900.0), (-900.0, 900.0)]
    areas = [("w1", "forest", square)]
    t1 = scatter_trees(areas, [(0.0, 0.0, 9.0)], 1000.0, seed=1)
    t2 = scatter_trees(areas, [(0.0, 0.0, 9.0)], 1000.0, seed=1)
    assert t1 == t2 and len(t1) == MAX_TREES  # 1800 x 1800 m would give ~14700 trees
    assert (0.0, 0.0, 9.0) in t1  # mapped trees are never thinned
    assert all(abs(x) <= 900 and abs(y) <= 900 for x, y, _ in t1)


def test_scatter_respects_polygon_shape() -> None:
    tri = [(0.0, 0.0), (300.0, 0.0), (0.0, 300.0)]
    trees = scatter_trees([("w1", "forest", tri)], [], 500.0, seed=3)
    assert trees and all(x + y <= 300.0 and x >= 0 and y >= 0 for x, y, _ in trees)
    assert scatter_trees([("w1", "water", tri)], [], 500.0, seed=3) == []


def test_landcover_classes() -> None:
    assert landcover_class({"natural": "water"}) == "water"
    assert landcover_class({"landuse": "forest"}) == "forest"
    assert landcover_class({"landuse": "orchard"}) == "orchard"
    assert landcover_class({"landuse": "residential"}) == "built"
    assert landcover_class({"amenity": "school"}) is None


def test_texture_is_deterministic_png() -> None:
    sq = [(-100.0, -100.0), (100.0, -100.0), (100.0, 100.0), (-100.0, 100.0)]
    areas = [("water", sq)]
    roads = [("primary", [(-200.0, 0.0), (200.0, 0.0)])]
    a = render_landcover(areas, roads, [], 250.0, 64, 5)
    assert a == render_landcover(areas, roads, [], 250.0, 64, 5)
    assert a[:8] == b"\x89PNG\r\n\x1a\n"
    assert a != render_landcover(areas, roads, [], 250.0, 64, 6)  # the noise seed matters


def test_load_areas_reads_the_committed_config() -> None:
    areas = load_areas(Path(__file__).resolve().parents[1] / "areas.json")
    assert [a.id for a in areas] == ["heron-ridge", "osprey-town"]
    heron, osprey = areas
    assert (heron.half_extent_m, osprey.half_extent_m) == (2000.0, 1500.0)
    assert heron.cell_m == osprey.cell_m == 31.25
    assert int(round(2 * heron.half_extent_m / heron.cell_m)) + 1 == 129
    assert int(round(2 * osprey.half_extent_m / osprey.cell_m)) + 1 == 97
    for a in areas:  # the real coordinates stay in this file, never in the names
        assert a.name in ("Heron Ridge", "Osprey Town")
