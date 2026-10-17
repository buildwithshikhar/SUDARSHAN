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


def _poly(x: float, coeffs: tuple[float, ...]) -> float:
    """Horner evaluation, highest power first, in a fixed order."""
    acc = 0.0
    for c in reversed(coeffs):
        acc = acc * x + c
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


# fdlibm split of ln 2: LN2_HI has trailing zero bits, so k * LN2_HI is exact for |k| < 2**20.
_LN2_HI = 6.93147180369123816490e-01
_LN2_LO = 1.90821492927058770002e-10
_EXP = tuple(1.0 / math.factorial(n) for n in range(16))
_ATAN = tuple((-1.0) ** k / (2 * k + 1) for k in range(14))
_LOG = tuple(1.0 / (2 * k + 1) for k in range(14))


def exp(x: float) -> float:
    """e**x for |x| <= 700 (clamped), from a Taylor polynomial and an exact power-of-two scale."""
    x = -700.0 if x < -700.0 else 700.0 if x > 700.0 else x
    k = math.floor(x / 0.6931471805599453 + 0.5)
    r = (x - k * _LN2_HI) - k * _LN2_LO
    return math.ldexp(_poly(r, _EXP), k)


def log(x: float) -> float:
    """Natural logarithm for x > 0, from `frexp` (exact) and an atanh series."""
    if not x > 0.0:
        raise ValueError("log needs a positive argument")
    m, e = math.frexp(x)
    if m < 0.7071067811865476:
        m *= 2.0
        e -= 1
    f = (m - 1.0) / (m + 1.0)
    return e * _LN2_HI + (2.0 * f * _poly(f * f, _LOG) + e * _LN2_LO)


def atan(x: float) -> float:
    """Arctangent: two argument halvings (exact `sqrt`) then a short alternating series."""
    a = -x if x < 0.0 else x
    flip = a > 1.0
    if flip:
        a = 1.0 / a
    for _ in range(2):
        a = a / (1.0 + math.sqrt(1.0 + a * a))
    r = 4.0 * a * _poly(a * a, _ATAN)
    if flip:
        r = PI / 2.0 - r
    return -r if x < 0.0 else r


def atan2(y: float, x: float) -> float:
    """Angle of the vector (x, y) in radians, in (-pi, pi]; atan2(0, 0) is 0."""
    ax, ay = abs(x), abs(y)
    if ax == 0.0 and ay == 0.0:
        return 0.0
    r = atan(ay / ax) if ax >= ay else PI / 2.0 - atan(ax / ay)
    if x < 0.0:
        r = PI - r
    return -r if y < 0.0 else r


def wrap360(degrees: float) -> float:
    """Wrap an angle in degrees into [0, 360)."""
    r = degrees - 360.0 * math.floor(degrees / 360.0)
    return 0.0 if r >= 360.0 else r


def wrap180(degrees: float) -> float:
    """Wrap an angle in degrees into [-180, 180)."""
    return wrap360(degrees + 180.0) - 180.0


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
