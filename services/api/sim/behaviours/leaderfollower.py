"""Leader-follower formation slots and the follower's proportional controller.

Slots are positions in the leader's frame: `forward` along the leader's heading and `right` to the
right of it. The formation follows from the group's intent: a column for transit, staggered rows
(a cluster) for loiter and probe, and a line abreast for saturation. Followers take slots in
order of their IDs, and the slots close up when a follower is gone, because a slot belongs to a
rank and not to a member. Model basis: Desai et al., followers holding range and bearing to a
leader (docs/02-research.md section 3); the spacing and gain are fictional, project-authored
values.
"""

import math

from .. import detmath

Offset = tuple[float, float]  # (forward, right) in metres

#: Distance between rows of a cluster, as a fraction of the spacing (sin 60 degrees).
ROW_FACTOR = 0.866
#: Velocity correction in m/s per metre of slot error.
SLOT_GAIN_PER_S = 0.5

FORMATION_OF_INTENT = {
    "transit": "column",
    "loiter": "cluster",
    "probe": "cluster",
    "saturation": "line",
}


def formation_for(intent: str) -> str:
    return FORMATION_OF_INTENT[intent]


def lane_offset(rank: int, count: int, lane_spacing: float) -> float:
    """Right-hand offset of lane `rank` of `count`, centred on the track."""
    return (rank - (count - 1) / 2.0) * lane_spacing


def offsets(formation: str, count: int, spacing: float) -> list[Offset]:
    """Slot offsets for `count` members, the leader first at (0, 0)."""
    out: list[Offset] = [(0.0, 0.0)]
    followers = count - 1
    per_row = max(2, math.isqrt(followers - 1) + 1) if followers > 0 else 2
    for k in range(1, count):
        if formation == "column":
            out.append((-k * spacing, 0.0))
        elif formation == "line":
            side = (k + 1) // 2
            out.append((0.0, side * spacing if k % 2 == 1 else -side * spacing))
        else:
            row, col = (k - 1) // per_row + 1, (k - 1) % per_row
            stagger = spacing / 2.0 if row % 2 == 0 else 0.0
            out.append(
                (-row * spacing * ROW_FACTOR, (col - (per_row - 1) / 2.0) * spacing + stagger)
            )
    return out


def to_world(lx: float, ly: float, lux: float, luy: float, slot: Offset) -> tuple[float, float]:
    """Slot position in world coordinates for a frame at (lx, ly) heading (lux, luy)."""
    forward, right = slot
    return lx + lux * forward + luy * right, ly + luy * forward - lux * right


def follow(
    px: float,
    py: float,
    slot_x: float,
    slot_y: float,
    frame_vx: float,
    frame_vy: float,
    sep: tuple[float, float],
    sep_speed: float,
    max_correction: float,
) -> tuple[float, float]:
    """Desired velocity: the frame's own velocity plus a proportional pull to the slot (at most
    `max_correction` m/s, so a far slot is closed on steadily) plus the separation push scaled by
    `sep_speed` (m/s)."""
    cx, cy = SLOT_GAIN_PER_S * (slot_x - px), SLOT_GAIN_PER_S * (slot_y - py)
    n = math.sqrt(cx * cx + cy * cy)
    if n > max_correction:
        cx, cy = cx / n * max_correction, cy / n * max_correction
    return frame_vx + cx + sep[0] * sep_speed, frame_vy + cy + sep[1] * sep_speed


def heading_and_speed(
    vx: float, vy: float, fallback: tuple[float, float]
) -> tuple[tuple[float, float], float]:
    """Unit heading and speed of a desired velocity; a (near) zero velocity keeps `fallback`."""
    speed = math.sqrt(vx * vx + vy * vy)
    if speed < 1e-9:
        return fallback, 0.0
    return detmath.unit(vx, vy), speed
