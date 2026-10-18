"""A six-state constant-velocity Kalman filter in plain Python floats.

State is (x, y, z, vx, vy, vz) in local east-north-up metres. Only `+ - * /` and `sqrt` are used,
in a fixed order, so the result is bit-identical on every platform and may be hashed (SIM_CORE,
determinism rule 3). Measurements are applied as sequential scalar updates, which needs no matrix
inverse.
"""

import math

N = 6
Vector = list[float]
Matrix = list[list[float]]


def zeros() -> Matrix:
    return [[0.0] * N for _ in range(N)]


def predict(x: Vector, p: Matrix, dt: float, accel_sigma: float) -> None:
    """Advance state and covariance by `dt` seconds, in place.

    P' = F P F^T + Q with F = [[I, dt I], [0, I]] and the continuous white-noise-acceleration
    process noise Q = sigma_a^2 [[dt^3/3, dt^2/2], [dt^2/2, dt]] per axis.
    """
    if dt == 0.0:
        return
    for i in range(3):
        x[i] += dt * x[i + 3]
    rows: Matrix = [[p[i][j] + dt * p[i + 3][j] for j in range(N)] for i in range(3)]
    rows += [p[i + 3][:] for i in range(3)]
    for row in rows:
        for j in range(3):
            row[j] += dt * row[j + 3]
    q = accel_sigma * accel_sigma
    qpp, qpv, qvv = q * dt * dt * dt / 3.0, q * dt * dt / 2.0, q * dt
    for i in range(3):
        rows[i][i] += qpp
        rows[i][i + 3] += qpv
        rows[i + 3][i] += qpv
        rows[i + 3][i + 3] += qvv
    for i in range(N):
        p[i][:] = rows[i]


def update_scalar(x: Vector, p: Matrix, h: Vector, innovation: float, r: float) -> float:
    """Apply one scalar measurement with row `h`, innovation and variance `r`; returns S.

    P' = P - K (h P) is used with P symmetric, then the result is symmetrised again so rounding
    cannot make it drift.
    """
    ph = [0.0] * N
    for i in range(N):
        total = 0.0
        for j in range(N):
            total += p[i][j] * h[j]
        ph[i] = total
    s = r
    for i in range(N):
        s += h[i] * ph[i]
    k = [v / s for v in ph]
    for i in range(N):
        x[i] += k[i] * innovation
    for i in range(N):
        for j in range(N):
            p[i][j] -= k[i] * ph[j]
    for i in range(N):
        for j in range(i + 1, N):
            avg = (p[i][j] + p[j][i]) / 2.0
            p[i][j] = avg
            p[j][i] = avg
    return s


def innovation_variance(p: Matrix, h: Vector, r: float) -> float:
    """S = h P h^T + r, without changing the state."""
    s = r
    for i in range(N):
        row = 0.0
        for j in range(N):
            row += p[i][j] * h[j]
        s += h[i] * row
    return s


def position_variance(p: Matrix) -> float:
    """Mean variance over the three position axes, m^2."""
    return (p[0][0] + p[1][1] + p[2][2]) / 3.0


def speed_variance(p: Matrix) -> float:
    return (p[3][3] + p[4][4] + p[5][5]) / 3.0


def position_sigma(p: Matrix) -> float:
    """One-sigma position uncertainty (root of the mean position variance), m."""
    return math.sqrt(position_variance(p))


def speed_sigma(p: Matrix) -> float:
    return math.sqrt(speed_variance(p))
