"""Minimal deterministic GLB (glTF 2.0 binary) writer: indexed triangle meshes only."""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

ARRAY_BUFFER = 34962
ELEMENT_ARRAY_BUFFER = 34963
FLOAT = 5126
UNSIGNED_SHORT = 5123
UNSIGNED_INT = 5125

_GLB_MAGIC = 0x46546C67  # "glTF"
_CHUNK_JSON = 0x4E4F534A
_CHUNK_BIN = 0x004E4942


@dataclass
class Material:
    name: str
    base_color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    roughness: float = 0.9
    metallic: float = 0.0
    texture: int | None = None  # texture index


@dataclass
class Primitive:
    positions: NDArray[np.float32]  # (n, 3)
    normals: NDArray[np.float32]  # (n, 3)
    indices: NDArray[np.integer[Any]]  # (m,) multiple of 3
    material: int
    uvs: NDArray[np.float32] | None = None  # (n, 2)


@dataclass
class GlbBuilder:
    generator: str = "terrain-bake"
    _bin: bytearray = field(default_factory=bytearray)
    _views: list[dict[str, Any]] = field(default_factory=list)
    _accessors: list[dict[str, Any]] = field(default_factory=list)
    _images: list[dict[str, Any]] = field(default_factory=list)
    _materials: list[Material] = field(default_factory=list)
    _meshes: list[dict[str, Any]] = field(default_factory=list)

    def _add_view(self, data: bytes, target: int | None) -> int:
        while len(self._bin) % 4:
            self._bin.append(0)
        view: dict[str, Any] = {"buffer": 0, "byteOffset": len(self._bin), "byteLength": len(data)}
        if target is not None:
            view["target"] = target
        self._bin.extend(data)
        self._views.append(view)
        return len(self._views) - 1

    def _add_accessor(
        self,
        arr: NDArray[Any],
        component: int,
        kind: str,
        target: int,
        with_bounds: bool = False,
    ) -> int:
        view = self._add_view(arr.tobytes(), target)
        acc: dict[str, Any] = {
            "bufferView": view,
            "componentType": component,
            "count": int(arr.shape[0]),
            "type": kind,
        }
        if with_bounds:
            acc["min"] = [float(v) for v in arr.min(axis=0)]
            acc["max"] = [float(v) for v in arr.max(axis=0)]
        self._accessors.append(acc)
        return len(self._accessors) - 1

    def add_image(self, png: bytes) -> int:
        view = self._add_view(png, None)
        self._images.append({"bufferView": view, "mimeType": "image/png"})
        return len(self._images) - 1

    def add_material(self, mat: Material) -> int:
        self._materials.append(mat)
        return len(self._materials) - 1

    def add_mesh(self, name: str, primitives: list[Primitive]) -> None:
        prims: list[dict[str, Any]] = []
        for p in primitives:
            attrs: dict[str, int] = {
                "POSITION": self._add_accessor(
                    np.ascontiguousarray(p.positions, dtype="<f4"),
                    FLOAT,
                    "VEC3",
                    ARRAY_BUFFER,
                    True,
                ),
                "NORMAL": self._add_accessor(
                    np.ascontiguousarray(p.normals, dtype="<f4"), FLOAT, "VEC3", ARRAY_BUFFER
                ),
            }
            if p.uvs is not None:
                attrs["TEXCOORD_0"] = self._add_accessor(
                    np.ascontiguousarray(p.uvs, dtype="<f4"), FLOAT, "VEC2", ARRAY_BUFFER
                )
            n_vert = int(p.positions.shape[0])
            if n_vert <= 65535:
                idx = np.ascontiguousarray(p.indices, dtype="<u2")
                comp = UNSIGNED_SHORT
            else:
                idx = np.ascontiguousarray(p.indices, dtype="<u4")
                comp = UNSIGNED_INT
            iacc = self._add_accessor(idx.reshape(-1, 1), comp, "SCALAR", ELEMENT_ARRAY_BUFFER)
            prims.append({"attributes": attrs, "indices": iacc, "material": p.material, "mode": 4})
        self._meshes.append({"name": name, "primitives": prims})

    def build(self) -> bytes:
        materials: list[dict[str, Any]] = []
        textures: list[dict[str, Any]] = []
        for m in self._materials:
            pbr: dict[str, Any] = {
                "baseColorFactor": list(m.base_color),
                "metallicFactor": m.metallic,
                "roughnessFactor": m.roughness,
            }
            if m.texture is not None:
                pbr["baseColorTexture"] = {"index": m.texture}
            materials.append({"name": m.name, "pbrMetallicRoughness": pbr})
        for i in range(len(self._images)):
            textures.append({"sampler": 0, "source": i})
        doc: dict[str, Any] = {
            "asset": {"version": "2.0", "generator": self.generator},
            "scene": 0,
            "scenes": [{"nodes": list(range(len(self._meshes)))}],
            "nodes": [{"name": m["name"], "mesh": i} for i, m in enumerate(self._meshes)],
            "meshes": self._meshes,
            "materials": materials,
            "buffers": [{"byteLength": (len(self._bin) + 3) // 4 * 4}],
            "bufferViews": self._views,
            "accessors": self._accessors,
        }
        if self._images:
            doc["images"] = self._images
            doc["textures"] = textures
            # LINEAR_MIPMAP_LINEAR / LINEAR, clamp to edge
            doc["samplers"] = [
                {"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}
            ]
        js = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
        js += b" " * (-len(js) % 4)
        bn = bytes(self._bin) + b"\x00" * (-len(self._bin) % 4)
        total = 12 + 8 + len(js) + 8 + len(bn)
        return (
            struct.pack("<III", _GLB_MAGIC, 2, total)
            + struct.pack("<II", len(js), _CHUNK_JSON)
            + js
            + struct.pack("<II", len(bn), _CHUNK_BIN)
            + bn
        )


def parse_glb(data: bytes) -> tuple[dict[str, Any], bytes]:
    """Parse a GLB into (json document, binary chunk). Used by tests and verification."""
    magic, version, length = struct.unpack_from("<III", data, 0)
    if magic != _GLB_MAGIC or version != 2 or length != len(data):
        raise ValueError("not a valid GLB 2.0 container")
    jlen, jtype = struct.unpack_from("<II", data, 12)
    if jtype != _CHUNK_JSON:
        raise ValueError("first chunk is not JSON")
    doc = json.loads(data[20 : 20 + jlen])
    off = 20 + jlen
    blen, btype = struct.unpack_from("<II", data, off)
    if btype != _CHUNK_BIN:
        raise ValueError("second chunk is not BIN")
    return doc, data[off + 8 : off + 8 + blen]


def read_accessor(doc: dict[str, Any], binary: bytes, index: int) -> NDArray[Any]:
    acc = doc["accessors"][index]
    view = doc["bufferViews"][acc["bufferView"]]
    dtype = {FLOAT: "<f4", UNSIGNED_SHORT: "<u2", UNSIGNED_INT: "<u4"}[acc["componentType"]]
    width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}[acc["type"]]
    arr = np.frombuffer(binary, dtype=dtype, count=acc["count"] * width, offset=view["byteOffset"])
    return arr.reshape(acc["count"], width) if width > 1 else arr
