"""SRTM 1 arc-second tile reader (HGT, big-endian int16) with void fill."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from .geo import FloatArray, bilinear

VOID = -32768


class SrtmError(ValueError):
    pass


def fill_voids(elev: FloatArray, void: NDArray[np.bool_]) -> FloatArray:
    """Fill voids by repeated 4-neighbour averaging of valid cells (deterministic)."""
    out = elev.copy()
    mask = void.copy()
    if mask.all():
        raise SrtmError("window contains no valid SRTM cells")
    while mask.any():
        valid = ~mask
        padded = np.pad(np.where(valid, out, 0.0), 1)
        pvalid = np.pad(valid.astype(np.float64), 1)
        total = padded[:-2, 1:-1] + padded[2:, 1:-1] + padded[1:-1, :-2] + padded[1:-1, 2:]
        count = pvalid[:-2, 1:-1] + pvalid[2:, 1:-1] + pvalid[1:-1, :-2] + pvalid[1:-1, 2:]
        fillable = mask & (count > 0)
        out[fillable] = total[fillable] / count[fillable]
        mask = mask & ~fillable
    return np.asarray(out, dtype=np.float64)


@dataclass(frozen=True)
class SrtmTile:
    """A 1x1 degree tile. Row 0 is the north edge (lat_sw + 1), column 0 the west edge."""

    lat_sw: int
    lon_sw: int
    raw: NDArray[np.int16]

    @property
    def samples(self) -> int:
        return int(self.raw.shape[0])

    @classmethod
    def from_bytes(cls, name: str, data: bytes) -> SrtmTile:
        m = re.search(r"([NS])(\d{2})([EW])(\d{3})", name.upper())
        if not m:
            raise SrtmError(f"cannot read tile origin from name {name!r}")
        lat = int(m.group(2)) * (1 if m.group(1) == "N" else -1)
        lon = int(m.group(4)) * (1 if m.group(3) == "E" else -1)
        n = int(round((len(data) / 2) ** 0.5))
        if n * n * 2 != len(data) or n < 2:
            raise SrtmError("HGT size is not a square number of int16 samples")
        raw = np.frombuffer(data, dtype=">i2").reshape(n, n)
        return cls(lat, lon, raw.astype(np.int16))

    @classmethod
    def from_zip(cls, path: Path) -> SrtmTile:
        with zipfile.ZipFile(path) as zf:
            names = sorted(n for n in zf.namelist() if n.lower().endswith(".hgt"))
            if not names:
                raise SrtmError(f"no .hgt member in {path.name}")
            return cls.from_bytes(names[0], zf.read(names[0]))

    def contains(self, lat: float, lon: float) -> bool:
        return self.lat_sw <= lat <= self.lat_sw + 1 and self.lon_sw <= lon <= self.lon_sw + 1

    def sample(self, lat: FloatArray, lon: FloatArray) -> FloatArray:
        """Bilinear elevation (m) at the given coordinates; voids are filled first."""
        lat = np.asarray(lat, dtype=np.float64)
        lon = np.asarray(lon, dtype=np.float64)
        if not (
            self.contains(float(np.min(lat)), float(np.min(lon)))
            and self.contains(float(np.max(lat)), float(np.max(lon)))
        ):
            raise SrtmError("requested area lies outside the SRTM tile")
        steps = self.samples - 1
        row = (self.lat_sw + 1 - lat) * steps
        col = (lon - self.lon_sw) * steps
        pad = 64  # margin so a void on the window edge still has valid neighbours to fill from
        r_lo = max(int(np.floor(np.min(row))) - pad, 0)
        r_hi = min(int(np.ceil(np.max(row))) + pad + 1, self.samples)
        c_lo = max(int(np.floor(np.min(col))) - pad, 0)
        c_hi = min(int(np.ceil(np.max(col))) + pad + 1, self.samples)
        win = self.raw[r_lo:r_hi, c_lo:c_hi].astype(np.float64)
        void = self.raw[r_lo:r_hi, c_lo:c_hi] == VOID
        if void.any():
            win = fill_voids(win, void)
        return bilinear(win, row - r_lo, col - c_lo)
