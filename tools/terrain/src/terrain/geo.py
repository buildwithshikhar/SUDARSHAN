"""Local equirectangular frame and a bilinear height field."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class Projection:
    """Equirectangular projection about a centre. x east, y north, metres."""

    lat0: float
    lon0: float

    @property
    def m_per_deg_lat(self) -> float:
        phi = math.radians(self.lat0)
        return 111132.92 - 559.82 * math.cos(2 * phi) + 1.175 * math.cos(4 * phi)

    @property
    def m_per_deg_lon(self) -> float:
        phi = math.radians(self.lat0)
        return 111412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi) + 0.118 * math.cos(5 * phi)

    def forward(
        self, lon: FloatArray | float, lat: FloatArray | float
    ) -> tuple[FloatArray, FloatArray]:
        x = (np.asarray(lon, dtype=np.float64) - self.lon0) * self.m_per_deg_lon
        y = (np.asarray(lat, dtype=np.float64) - self.lat0) * self.m_per_deg_lat
        return x, y

    def inverse(
        self, x: FloatArray | float, y: FloatArray | float
    ) -> tuple[FloatArray, FloatArray]:
        lon = self.lon0 + np.asarray(x, dtype=np.float64) / self.m_per_deg_lon
        lat = self.lat0 + np.asarray(y, dtype=np.float64) / self.m_per_deg_lat
        return lon, lat

    def bbox(
        self, half_extent_m: float, margin_m: float = 0.0
    ) -> tuple[float, float, float, float]:
        """(lon_min, lat_min, lon_max, lat_max) of the square plus a margin."""
        h = half_extent_m + margin_m
        lon_a, lat_a = self.inverse(-h, -h)
        lon_b, lat_b = self.inverse(h, h)
        return float(lon_a), float(lat_a), float(lon_b), float(lat_b)


def bilinear(grid: FloatArray, row: FloatArray, col: FloatArray) -> FloatArray:
    """Bilinear sample of ``grid`` at fractional (row, col). Indices are clamped to the grid."""
    n_rows, n_cols = grid.shape
    row = np.clip(row, 0.0, n_rows - 1.0)
    col = np.clip(col, 0.0, n_cols - 1.0)
    r0 = np.minimum(np.floor(row).astype(np.int64), n_rows - 2)
    c0 = np.minimum(np.floor(col).astype(np.int64), n_cols - 2)
    fr = row - r0
    fc = col - c0
    top = grid[r0, c0] * (1 - fc) + grid[r0, c0 + 1] * fc
    bot = grid[r0 + 1, c0] * (1 - fc) + grid[r0 + 1, c0 + 1] * fc
    return np.asarray(top * (1 - fr) + bot * fr, dtype=np.float64)


@dataclass(frozen=True)
class HeightField:
    """Heights (metres above the datum) on a square grid; row 0 is the south edge."""

    values: FloatArray  # shape (size, size), [row (y), col (x)]
    half_extent_m: float
    cell_m: float

    @property
    def size(self) -> int:
        return int(self.values.shape[0])

    def sample(self, x: FloatArray | float, y: FloatArray | float) -> FloatArray:
        col = (np.asarray(x, dtype=np.float64) + self.half_extent_m) / self.cell_m
        row = (np.asarray(y, dtype=np.float64) + self.half_extent_m) / self.cell_m
        return bilinear(self.values, row, col)
