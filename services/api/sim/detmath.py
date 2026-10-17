"""Platform-independent arithmetic for everything that feeds the state hash.

IEEE-754 guarantees correctly rounded `+ - * /` and `sqrt`, so they give the same bits on every
machine. `math.sin`, `math.atan2` and numpy's vectorised transcendentals come from the platform
maths library and may differ in the last bit between macOS and Linux, which would change state
hashes after a few thousand ticks. The sim core therefore keeps headings as unit vectors and uses
the polynomials below, built only from the guaranteed operations, evaluated in a fixed order.
"""

import math

PI = 3.141592653589793
DEG = PI / 180.0

# Taylor coefficients (-1)^k / n!: correctly rounded divisions, identical everywhere. After
# reduction to |r| <= pi/4 the first omitted term is below 1e-20.
_SIN = tuple((-1.0) ** k / math.factorial(2 * k + 1) for k in range(10))
_COS = tuple((-1.0) ** k / math.factorial(2 * k) for k in range(10))
# pi/2 split in two (Cody-Waite) so the reduction keeps the bits a single constant would lose.
_PIO2_HI = 1.5707963267948966
_PIO2_LO = 6.123233995736766e-17


def _poly(x2: float, coeffs: tuple[float, ...]) -> float:
    acc = 0.0
    for c in reversed(coeffs):
        acc = acc * x2 + c
    return acc


def _sincos(x: float) -> tuple[float, float]:
    """sin and cos of x via the quadrant q = round(x / (pi/2)) and |r| <= pi/4."""
    q = math.floor(x / _PIO2_HI + 0.5)
    r = (x - q * _PIO2_HI) - q * _PIO2_LO
    r2 = r * r
    s, c = r * _poly(r2, _SIN), _poly(r2, _COS)
    return ((s, c), (c, -s), (-s, -c), (-c, s))[q % 4]


def sin(x: float) -> float:
    return _sincos(x)[0]


def cos(x: float) -> float:
    return _sincos(x)[1]


def clamp(value: float, low: float, high: float) -> float:
    return low if value < low else high if value > high else value


def heading_vector(degrees: float) -> tuple[float, float]:
    """Unit vector (east, north) for a compass heading in degrees (0 = north, clockwise)."""
    rad = degrees * DEG
    return unit(sin(rad), cos(rad))


def unit(x: float, y: float) -> tuple[float, float]:
    """Normalise (x, y); the zero vector maps to north so a heading is always defined."""
    n = math.sqrt(x * x + y * y)
    if n == 0.0:
        return 0.0, 1.0
    return x / n, y / n


def rotate_towards(
    u: tuple[float, float], d: tuple[float, float], cos_max: float, sin_max: float
) -> tuple[float, float]:
    """Turn unit vector u towards unit vector d by at most the angle whose cos and sin are given."""
    dot = u[0] * d[0] + u[1] * d[1]
    if dot >= cos_max:
        return d
    cross = u[0] * d[1] - u[1] * d[0]  # > 0: d is anticlockwise of u (a left turn)
    s = sin_max if cross > 0.0 else -sin_max
    return unit(u[0] * cos_max - u[1] * s, u[0] * s + u[1] * cos_max)
