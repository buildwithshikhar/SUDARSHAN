from __future__ import annotations

import struct

import numpy as np
import pytest

from terrain.buildings import Building, signed_area
from terrain.glb import GlbBuilder, Material, Primitive, parse_glb, read_accessor
from terrain.meshes import building_primitives, terrain_primitive, triangulate


def _tri_area(ring: list[tuple[float, float]], tris: list[tuple[int, int, int]]) -> float:
    total = 0.0
    for a, b, c in tris:
        total += signed_area([ring[a], ring[b], ring[c]])
    return total


def test_triangulate_convex_and_concave_cover_the_area() -> None:
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    assert len(triangulate(square)) == 2
    assert _tri_area(square, triangulate(square)) == pytest.approx(100.0)
    ell = [(0.0, 0.0), (10.0, 0.0), (10.0, 4.0), (4.0, 4.0), (4.0, 10.0), (0.0, 10.0)]
    tris = triangulate(ell)
    assert len(tris) == 4
    assert _tri_area(ell, tris) == pytest.approx(signed_area(ell))
    assert all(
        signed_area([ell[a], ell[b], ell[c]]) > 0 for a, b, c in tris
    )  # every triangle counter-clockwise


def test_terrain_primitive_geometry_and_winding() -> None:
    n = 5
    rr, cc = np.mgrid[0:n, 0:n]
    h = (cc * 2.0 + rr * 1.0).astype(np.float64)  # rises east and north
    prim = terrain_primitive(h, 100.0, 0)
    assert prim.positions.shape == (25, 3) and prim.indices.shape == ((n - 1) ** 2 * 6,)
    pos = prim.positions
    # Y-up mapping three = (x, z, -y): vertex 0 is the south-west corner.
    assert tuple(pos[0]) == (-100.0, 0.0, 100.0)
    assert tuple(pos[n - 1]) == (100.0, 8.0, 100.0)  # south-east: x east, z = -y = +100
    assert tuple(pos[n * (n - 1)]) == (-100.0, 4.0, -100.0)  # north-west
    assert prim.uvs is not None
    assert tuple(prim.uvs[0]) == (0.0, 1.0)  # south-west = bottom-left of the image
    assert tuple(prim.uvs[n * n - 1]) == (1.0, 0.0)  # north-east = top-right
    # Every triangle faces up (+Y) and agrees with its vertex normals.
    tri = prim.indices.reshape(-1, 3)
    for a, b, c in tri:
        normal = np.cross(pos[b] - pos[a], pos[c] - pos[a])
        assert normal[1] > 0
        assert np.dot(normal, prim.normals[a]) > 0
    assert np.allclose(np.linalg.norm(prim.normals, axis=1), 1.0, atol=1e-5)


def test_building_primitives_walls_face_outward_and_roofs_up() -> None:
    b = Building("w1", [(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)], 2.0, 7.0, "tag")
    walls, roofs = building_primitives([b], 0, 1)
    assert walls.positions.shape == (16, 3) and walls.indices.shape == (24,)
    assert roofs.positions.shape == (4, 3) and roofs.indices.shape == (6,)
    centre = np.array([5.0, 5.0, -3.0])  # building centre (x, mid-height, -y)
    for a, bb, c in walls.indices.reshape(-1, 3):
        p = walls.positions
        normal = np.cross(p[bb] - p[a], p[c] - p[a])
        assert np.dot(normal, walls.normals[a]) > 0
        assert np.dot(normal, p[a] - centre) > 0  # points away from the building
    assert np.min(walls.positions[:, 1]) == 2.0 and np.max(walls.positions[:, 1]) == 9.0
    assert np.all(roofs.positions[:, 1] == 9.0)
    for a, bb, c in roofs.indices.reshape(-1, 3):
        p = roofs.positions
        assert np.cross(p[bb] - p[a], p[c] - p[a])[1] > 0


def test_glb_round_trip_matches_input() -> None:
    gb = GlbBuilder()
    m0 = gb.add_material(Material("a"))
    pos = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
    nrm = np.tile(np.array([[0, 0, 1]], dtype=np.float32), (3, 1))
    gb.add_mesh("m", [Primitive(pos, nrm, np.array([0, 1, 2], dtype=np.uint32), m0)])
    data = gb.build()
    assert len(data) % 4 == 0
    doc, binary = parse_glb(data)
    assert doc["asset"]["version"] == "2.0"
    prim = doc["meshes"][0]["primitives"][0]
    assert doc["accessors"][prim["attributes"]["POSITION"]]["count"] == 3
    assert doc["accessors"][prim["attributes"]["POSITION"]]["max"] == [1.0, 1.0, 0.0]
    assert np.array_equal(read_accessor(doc, binary, prim["attributes"]["POSITION"]), pos)
    assert np.array_equal(read_accessor(doc, binary, prim["indices"]), [0, 1, 2])
    assert doc["accessors"][prim["indices"]]["componentType"] == 5123  # uint16 for small meshes


def test_glb_uses_uint32_indices_for_large_meshes_and_embeds_images() -> None:
    n = 70000
    gb = GlbBuilder()
    mat = gb.add_material(Material("t", texture=gb.add_image(b"\x89PNG\r\n\x1a\nfake")))
    pos = np.zeros((n, 3), dtype=np.float32)
    nrm = np.zeros((n, 3), dtype=np.float32)
    idx = np.array([0, 1, n - 1], dtype=np.uint32)
    gb.add_mesh("big", [Primitive(pos, nrm, idx, mat)])
    doc, binary = parse_glb(gb.build())
    prim = doc["meshes"][0]["primitives"][0]
    assert doc["accessors"][prim["indices"]]["componentType"] == 5125
    assert read_accessor(doc, binary, prim["indices"])[2] == n - 1
    view = doc["bufferViews"][doc["images"][0]["bufferView"]]
    assert binary[view["byteOffset"] : view["byteOffset"] + 8] == b"\x89PNG\r\n\x1a\n"
    assert doc["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"] == {"index": 0}


def test_parse_glb_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_glb(b"not a glb at all, really")
    with pytest.raises((ValueError, struct.error)):
        parse_glb(b"")
