from __future__ import annotations

import io
import zipfile
from pathlib import Path

import numpy as np
import pytest

from conftest import LAT0, LON0, make_tile
from terrain.geo import HeightField, Projection, bilinear
from terrain.srtm import VOID, SrtmError, SrtmTile, fill_voids


def test_projection_round_trip_and_scale() -> None:
    p = Projection(17.7, 74.0)
    lon, lat = p.inverse(1234.5, -987.6)
    x, y = p.forward(lon, lat)
    assert float(x) == pytest.approx(1234.5, abs=1e-6)
    assert float(y) == pytest.approx(-987.6, abs=1e-6)
    # About 110.6 km per degree of latitude and 106 km per degree of longitude at 17.7 N.
    assert p.m_per_deg_lat == pytest.approx(110_650, abs=60)
    assert p.m_per_deg_lon == pytest.approx(106_110, abs=80)
    x0, y0 = p.forward(74.0, 17.7)
    assert float(x0) == 0.0 and float(y0) == 0.0


def test_projection_north_and_east_are_positive() -> None:
    p = Projection(17.7, 74.0)
    x, y = p.forward(74.001, 17.701)
    assert float(x) > 0 and float(y) > 0


def test_bbox_covers_square() -> None:
    p = Projection(LAT0, LON0)
    lo_lon, lo_lat, hi_lon, hi_lat = p.bbox(2000, 100)
    assert lo_lon < LON0 < hi_lon and lo_lat < LAT0 < hi_lat
    x, y = p.forward(hi_lon, hi_lat)
    assert float(x) == pytest.approx(2100, abs=1e-6)
    assert float(y) == pytest.approx(2100, abs=1e-6)


def test_bilinear_is_exact_on_a_plane() -> None:
    rr, cc = np.mgrid[0:6, 0:7]
    grid = 3.0 * rr + 5.0 * cc + 2.0
    r = np.array([0.25, 2.5, 4.9, 5.0])
    c = np.array([0.5, 3.75, 5.2, 6.0])
    assert np.allclose(bilinear(grid, r, c), 3.0 * r + 5.0 * c + 2.0)


def test_bilinear_clamps_outside() -> None:
    grid = np.arange(9, dtype=float).reshape(3, 3)
    assert bilinear(grid, np.array([-5.0]), np.array([-5.0]))[0] == 0.0
    assert bilinear(grid, np.array([9.0]), np.array([9.0]))[0] == 8.0


def test_heightfield_samples_vertices_and_midpoints() -> None:
    vals = np.arange(25, dtype=float).reshape(5, 5)  # row = y index, col = x index
    hf = HeightField(vals, half_extent_m=100.0, cell_m=50.0)
    assert hf.size == 5
    assert float(hf.sample(-100.0, -100.0)) == 0.0  # south-west corner
    assert float(hf.sample(100.0, -100.0)) == 4.0  # south-east corner
    assert float(hf.sample(-100.0, 100.0)) == 20.0  # north-west corner
    assert float(hf.sample(-75.0, -100.0)) == pytest.approx(0.5)


def test_fill_voids_interpolates_a_plane() -> None:
    rr, cc = np.mgrid[0:12, 0:12]
    plane = 2.0 * rr + 3.0 * cc
    void = np.zeros(plane.shape, dtype=bool)
    void[4:7, 5:8] = True
    holed = np.where(void, 0.0, plane).astype(float)
    filled = fill_voids(holed, void)
    assert not np.isnan(filled).any()
    assert np.abs(filled[void] - plane[void]).max() <= 3.0 + 1e-9
    assert np.array_equal(filled[~void], plane[~void])


def test_fill_voids_rejects_all_void() -> None:
    with pytest.raises(SrtmError):
        fill_voids(np.zeros((3, 3)), np.ones((3, 3), dtype=bool))


def _hgt_bytes(raw: np.ndarray) -> bytes:
    return raw.astype(">i2").tobytes()


def test_tile_parses_name_and_big_endian() -> None:
    raw = np.arange(16, dtype=np.int16).reshape(4, 4) + 100
    t = SrtmTile.from_bytes("S05W060.hgt", _hgt_bytes(raw))
    assert (t.lat_sw, t.lon_sw) == (-5, -60)
    assert np.array_equal(t.raw, raw)
    with pytest.raises(SrtmError):
        SrtmTile.from_bytes("nonsense.hgt", _hgt_bytes(raw))
    with pytest.raises(SrtmError):
        SrtmTile.from_bytes("N17E074.hgt", b"\x00" * 10)


def test_tile_from_zip_reads_in_memory(tmp_path: Path) -> None:
    raw = make_tile().raw
    zpath = tmp_path / "N17E074.SRTMGL1.hgt.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("N17E074.hgt", _hgt_bytes(raw))
    t = SrtmTile.from_zip(zpath)
    assert np.array_equal(t.raw, raw)
    assert not list(tmp_path.glob("*.hgt"))  # nothing extracted to disk


def test_tile_from_zip_without_hgt(tmp_path: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "hi")
    zpath = tmp_path / "x.zip"
    zpath.write_bytes(buf.getvalue())
    with pytest.raises(SrtmError):
        SrtmTile.from_zip(zpath)


def test_sample_orientation_north_up_and_east_right() -> None:
    n = 11
    rr, cc = np.mgrid[0:n, 0:n]
    raw = (cc * 10 + (n - 1 - rr) * 100).astype(np.int16)  # grows east and north
    t = SrtmTile(17, 74, raw)
    assert t.sample(np.array([17.0]), np.array([74.0]))[0] == 0  # SW corner
    assert t.sample(np.array([17.0]), np.array([75.0]))[0] == 100  # SE corner
    assert t.sample(np.array([18.0]), np.array([74.0]))[0] == 1000  # NW corner
    assert t.sample(np.array([17.55]), np.array([74.25]))[0] == pytest.approx(0.55 * 1000 + 25)


def test_sample_fills_voids_before_interpolating() -> None:
    t = make_tile()
    raw = t.raw.copy()
    raw[48:53, 48:53] = VOID
    holed = SrtmTile(17, 74, raw)
    lat = np.array([17.5])
    lon = np.array([74.5])
    got = holed.sample(lat, lon)[0]
    plane = 500.0 + 300.0 * 0.5 + 100.0 * 0.5  # the surrounding terrain without the bump
    assert abs(got - plane) < 15.0  # the fill is a smooth estimate from the rim
    assert got > 0  # never the raw -32768


def test_sample_outside_tile_raises() -> None:
    with pytest.raises(SrtmError):
        make_tile().sample(np.array([18.2]), np.array([74.5]))
