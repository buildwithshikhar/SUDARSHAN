from __future__ import annotations

import numpy as np
import pytest

from conftest import LAT0, LON0, rect_ll
from terrain.buildings import (
    building_height,
    centroid,
    clean_ring,
    default_height_m,
    filter_sensitive,
    is_simple,
    make_buildings,
    parse_height_tag,
    parse_levels_tag,
    point_in_ring,
    sensitive_reason,
    signed_area,
)
from terrain.geo import HeightField, Projection
from terrain.osm import Polygon


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("12", 12.0),
        ("12.5", 12.5),
        ("12 m", 12.0),
        ("7,5", 7.5),
        ("30 ft", 9.1),
        ("0", None),
        ("tall", None),
        ("", None),
        (None, None),
        ("900", None),
    ],
)
def test_parse_height_tag(raw: str | None, want: float | None) -> None:
    assert parse_height_tag(raw) == want


def test_parse_levels_tag() -> None:
    assert parse_levels_tag("3") == 3
    assert parse_levels_tag("2.0") == 2
    assert parse_levels_tag("0") is None
    assert parse_levels_tag("many") is None
    assert parse_levels_tag(None) is None


def test_height_source_priority() -> None:
    assert building_height({"height": "10", "building:levels": "5"}, "w1") == (10.0, "tag")
    assert building_height({"building:levels": "4"}, "w1") == (12.0, "levels")
    h, src = building_height({"building": "yes"}, "w1")
    assert src == "default" and 5.0 <= h <= 8.5
    assert building_height({"height": "bad", "building:levels": "2"}, "w1") == (6.0, "levels")


def test_default_height_is_deterministic_and_bounded() -> None:
    ids = [f"w{i}" for i in range(2000)]
    hs = [default_height_m(i) for i in ids]
    assert hs == [default_height_m(i) for i in ids]
    assert min(hs) >= 5.0 and max(hs) <= 8.5
    assert len(set(hs)) > 20  # real variation, not a constant


def test_clean_ring_rounds_drops_closing_point_and_duplicates() -> None:
    ring = clean_ring(
        [(0.04, 0.0), (10.0, 0.0), (10.01, 0.02), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
    )
    assert ring == [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    assert clean_ring([(0, 0), (1, 1), (0, 0)]) is None


def test_signed_area_and_orientation() -> None:
    ccw = [(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)]
    assert signed_area(ccw) == 12.0
    assert signed_area(ccw[::-1]) == -12.0
    assert centroid(ccw) == (2.0, 1.5)


def test_is_simple_detects_bowtie_and_accepts_concave() -> None:
    bowtie = [(0.0, 0.0), (10.0, 10.0), (10.0, 0.0), (0.0, 10.0)]
    assert not is_simple(bowtie)
    l_shape = [(0.0, 0.0), (10.0, 0.0), (10.0, 4.0), (4.0, 4.0), (4.0, 10.0), (0.0, 10.0)]
    assert is_simple(l_shape)


def test_point_in_ring() -> None:
    sq = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    assert point_in_ring(5, 5, sq) and not point_in_ring(11, 5, sq)


@pytest.mark.parametrize(
    "tags",
    [
        {"military": "barracks"},
        {"landuse": "military"},
        {"building": "bunker"},
        {"amenity": "prison"},
        {"amenity": "police"},
        {"power": "substation"},
        {"power": "plant"},
        {"aeroway": "helipad"},
        {"government": "military"},
        {"man_made": "surveillance"},
    ],
)
def test_sensitive_features_are_flagged(tags: dict[str, str]) -> None:
    assert sensitive_reason(tags) is not None


@pytest.mark.parametrize(
    "tags",
    [{"building": "house"}, {"amenity": "school"}, {"landuse": "farmland"}, {"natural": "wood"}],
)
def test_ordinary_features_are_not_flagged(tags: dict[str, str]) -> None:
    assert sensitive_reason(tags) is None


def test_filter_sensitive_splits_and_counts() -> None:
    polys = [
        Polygon("w1", {"building": "yes"}, []),
        Polygon("w2", {"building": "military"}, []),
        Polygon("w3", {"landuse": "military"}, []),
        Polygon("w4", {"power": "substation"}, []),
    ]
    kept, dropped, reasons = filter_sensitive(polys)
    assert [p.osm_id for p in kept] == ["w1"]
    assert [p.osm_id for p in dropped] == ["w2", "w3", "w4"]
    assert reasons["landuse=military"] == 1


def _flat_field(half: float = 500.0, cell: float = 50.0, slope: float = 0.0) -> HeightField:
    n = int(2 * half / cell) + 1
    ys, _ = np.mgrid[0:n, 0:n]
    return HeightField(ys * cell * slope, half, cell)


def test_make_buildings_validity_orientation_and_report() -> None:
    proj = Projection(LAT0, LON0)
    cw = rect_ll(0, 0, 20, 10)[::-1]  # clockwise on input
    bowtie_xy = [(100, 100), (120, 120), (120, 100), (100, 120)]
    bowtie = [(*proj.inverse(x, y),) for x, y in bowtie_xy]
    bowtie_ll = [(float(a), float(b)) for a, b in bowtie] + [
        (float(bowtie[0][0]), float(bowtie[0][1]))
    ]
    polys = [
        Polygon("w1", {"building": "yes", "height": "9"}, cw),
        Polygon("w2", {"building": "yes", "building:levels": "3"}, rect_ll(60, 60, 10, 10)),
        Polygon("w3", {"building": "yes"}, rect_ll(-100, -100, 10, 10)),
        Polygon("w4", {"building": "yes"}, bowtie_ll),
        Polygon("w5", {"building": "yes"}, rect_ll(480, 0, 40, 10)),  # crosses the edge
        Polygon("w6", {"building": "yes"}, rect_ll(200, 200, 0.5, 0.5)),  # tiny
        Polygon("w7", {"building": "no"}, rect_ll(300, 300, 10, 10)),
        Polygon("w8", {"landuse": "farmland"}, rect_ll(-300, -300, 50, 50)),
        Polygon("w1", {"building": "yes"}, rect_ll(0, 0, 20, 10)),  # duplicate id
    ]
    blds, rep = make_buildings(polys, proj, _flat_field(), 500.0)
    assert [b.id for b in blds] == ["w1", "w2", "w3"]
    assert rep.kept == 3 and rep.dropped_invalid == 2 and rep.dropped_outside == 1
    assert dict(rep.height_source) == {"tag": 1, "levels": 1, "default": 1}
    for b in blds:
        assert signed_area(b.footprint) > 0  # counter-clockwise
        assert b.footprint[0] != b.footprint[-1]  # not closed
        assert len(b.footprint) >= 3
        assert all(abs(c) <= 500.0 for p in b.footprint for c in p)
        assert all(round(c, 1) == c for p in b.footprint for c in p)
    assert blds[0].height_m == 9.0 and blds[1].height_m == 9.0


def test_make_buildings_base_is_lowest_terrain_under_footprint() -> None:
    proj = Projection(LAT0, LON0)
    hf = _flat_field(slope=0.1)  # rises 0.1 m per metre going north
    poly = Polygon("w1", {"building": "yes"}, rect_ll(0, 100, 10, 40))
    (b,) = make_buildings([poly], proj, hf, 500.0)[0]
    # the field is (y + 500) * 0.1, so the south edge at y = 100 m is the lowest point: 60 m
    assert b.base_m == pytest.approx(60.0, abs=0.2)


def test_make_buildings_drops_centroids_inside_exclusion_rings() -> None:
    proj = Projection(LAT0, LON0)
    poly = Polygon("w1", {"building": "yes"}, rect_ll(10, 10, 10, 10))
    keep = Polygon("w2", {"building": "yes"}, rect_ll(300, 300, 10, 10))
    excl = [[(-50.0, -50.0), (50.0, -50.0), (50.0, 50.0), (-50.0, 50.0)]]
    blds, rep = make_buildings([poly, keep], proj, _flat_field(), 500.0, excl)
    assert [b.id for b in blds] == ["w2"]
    assert rep.dropped_sensitive == 1
