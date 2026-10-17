"""Physics and timing constants of the sim core.

The golden-file tests pin behaviour that depends on these values, so changing one fails them with
a readable diff. That is intended: regenerate the golden files on purpose (see docs/SIM_CORE.md)
and say why in the commit.
"""

from app.contracts import TICK_HZ

DT = 1.0 / TICK_HZ  # 0.05 s per tick

#: Smallest horizontal distance at which a waypoint counts as reached. The working radius is the
#: larger of this and the current turn radius, so a slow-turning airframe cannot orbit a waypoint.
ARRIVAL_RADIUS_MIN_M = 15.0

#: Radius of the orbit flown while holding at a waypoint or loitering at the end of a route.
ORBIT_RADIUS_M = 120.0

#: How hard the orbit controller pulls back to the circle, per orbit radius of error.
ORBIT_GAIN = 2.0

#: Vertical speed command per metre of altitude error, before the climb and descent limits.
CLIMB_GAIN_PER_S = 0.5

#: Correlation time of the wind gust process (first-order Gauss-Markov).
GUST_TAU_S = 4.0

#: Decimal places kept for positions and speeds in event payloads (readability only; the state
#: itself keeps full precision).
PAYLOAD_DECIMALS = 3
