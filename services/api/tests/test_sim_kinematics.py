"""Deterministic maths, RNG streams and waypoint kinematics (property tests stay inside limits)."""

import hashlib
import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.contracts.scenario import KinematicLimits, Threat
from sim import detmath
from sim.constants import DT
from sim.entity import Drone
from sim.kinematics import Envelope, step
from sim.rng import STREAMS, RngStreams, stream_key

# ---------------------------------------------------------------------------- detmath


@pytest.mark.parametrize("x", [i * 0.0731 - 10.0 for i in range(274)])
def test_polynomial_sin_and_cos_match_libm_closely(x: float) -> None:
    # headings stay within about +-3 pi; range reduction costs a few ulps further out
    assert detmath.sin(x) == pytest.approx(math.sin(x), abs=4e-15)
    assert detmath.cos(x) == pytest.approx(math.cos(x), abs=4e-15)


def test_heading_vector_uses_compass_convention() -> None:
    for degrees, expected in [(0, (0, 1)), (90, (1, 0)), (180, (0, -1)), (270, (-1, 0))]:
        x, y = detmath.heading_vector(degrees)
        assert (x, y) == pytest.approx(expected, abs=1e-15)
        assert math.hypot(x, y) == pytest.approx(1.0, abs=1e-15)


def test_unit_of_zero_is_north() -> None:
    assert detmath.unit(0.0, 0.0) == (0.0, 1.0)


def test_rotate_towards_limits_the_turn_and_picks_the_short_way() -> None:
    step_rad = 10 * detmath.DEG
    c, s = detmath.cos(step_rad), detmath.sin(step_rad)
    north, east, west = (0.0, 1.0), (1.0, 0.0), (-1.0, 0.0)
    right = detmath.rotate_towards(north, east, c, s)
    left = detmath.rotate_towards(north, west, c, s)
    assert right[0] > 0 and left[0] < 0  # turns towards the target side
    assert right[0] * north[0] + right[1] * north[1] == pytest.approx(c, abs=1e-15)
    near = detmath.heading_vector(5)
    assert detmath.rotate_towards(north, near, c, s) == near  # within one step: snap to target


# ---------------------------------------------------------------------------- RNG streams


def test_stream_key_is_the_sha256_prefix_of_the_name() -> None:
    # never Python's hash(), which is salted per process
    digest = hashlib.sha256(b"weather").digest()
    assert stream_key("weather") == int.from_bytes(digest[:8], "big")
    assert stream_key("weather") != stream_key("kinematics")


def test_same_seed_same_numbers_different_seed_different_numbers() -> None:
    a, b, c = RngStreams(42), RngStreams(42), RngStreams(43)
    draws = [a.uniform("weather") for _ in range(5)]
    assert draws == [b.uniform("weather") for _ in range(5)]
    assert draws != [c.uniform("weather") for _ in range(5)]


def test_streams_are_independent_of_each_other() -> None:
    quiet, busy = RngStreams(7), RngStreams(7)
    for _ in range(1000):
        busy.uniform("sensors")  # heavy use of one stream ...
    # ... never shifts another
    assert [quiet.uniform("weather") for _ in range(10)] == [
        busy.uniform("weather") for _ in range(10)
    ]


def test_normalish_is_bounded_with_unit_variance() -> None:
    rng = RngStreams(3)
    draws = np.array([rng.normalish("weather") for _ in range(20_000)])
    assert np.all(np.abs(draws) <= 2 * math.sqrt(3))
    assert abs(draws.mean()) < 0.03
    assert abs(draws.std() - 1.0) < 0.03


def test_rng_state_round_trips() -> None:
    rng = RngStreams(11)
    rng.uniform("weather")
    saved = rng.state()
    expected = [rng.uniform(name) for name in STREAMS]
    other = RngStreams(999)
    other.restore(saved)
    assert [other.uniform(name) for name in STREAMS] == expected
    with pytest.raises(ValueError, match="do not match"):
        other.restore({"weather": saved["weather"]})


# ---------------------------------------------------------------------------- kinematics


@st.composite
def limits(draw: st.DrawFn) -> KinematicLimits:
    low = draw(st.floats(0, 300))
    return KinematicLimits(
        max_speed_mps=draw(st.floats(1, 60)),
        max_accel_mps2=draw(st.floats(0.2, 12)),
        max_climb_mps=draw(st.floats(0.5, 15)),
        max_descent_mps=draw(st.floats(0.5, 15)),
        max_turn_rate_dps=draw(st.floats(3, 180)),
        min_altitude_m=low,
        max_altitude_m=low + draw(st.floats(5, 800)),
    )


@st.composite
def threats(draw: st.DrawFn) -> Threat:
    lim = draw(limits())
    coord = st.floats(-3000, 3000)
    alt = st.floats(lim.min_altitude_m, lim.max_altitude_m)
    speed = st.floats(0.5, lim.max_speed_mps)

    def point() -> dict[str, float]:
        return {"x": draw(coord), "y": draw(coord), "z": draw(alt)}

    route = [
        {"position": point(), "speed_mps": draw(speed), "hold_s": draw(st.sampled_from([0, 0, 3]))}
        for _ in range(draw(st.integers(1, 4)))
    ]
    return Threat.model_validate(
        {
            "id": "t",
            "class_id": "c",
            "label": {"en": "T", "hi": "T"},
            "spawn_s": 0,
            "start": point(),
            "start_heading_deg": draw(st.floats(0, 359.99)),
            "start_speed_mps": draw(st.floats(0, lim.max_speed_mps)),
            "limits": lim.model_dump(),
            "route": route,
            "on_route_end": draw(st.sampled_from(["loiter", "loop", "despawn"])),
        }
    )


EPS = 1e-9


@settings(max_examples=150, deadline=None)
@given(
    threat=threats(),
    wind=st.tuples(st.floats(-15, 15), st.floats(-15, 15)),
    ticks=st.integers(1, 600),
)
def test_kinematics_stay_inside_the_class_limits(
    threat: Threat, wind: tuple[float, float], ticks: int
) -> None:
    env = Envelope.of(threat.limits)
    lim = threat.limits
    d = Drone.pending(threat)
    d.status = "active"
    for _ in range(ticks):
        before = (d.ux, d.uy, d.airspeed)
        step(d, threat, env, wind)
        if d.status != "active":
            break
        assert 0.0 <= d.airspeed <= lim.max_speed_mps + EPS
        # the start speed may be above the first waypoint's: still only max_accel per second
        assert abs(d.airspeed - before[2]) <= lim.max_accel_mps2 * DT + EPS
        assert -lim.max_descent_mps - EPS <= d.vz <= lim.max_climb_mps + EPS
        assert lim.min_altitude_m <= d.z <= lim.max_altitude_m
        assert math.hypot(d.ux, d.uy) == pytest.approx(1.0, abs=1e-12)
        turned = d.ux * before[0] + d.uy * before[1]
        assert turned >= env.cos_turn - 1e-12  # heading change within max_turn_rate * dt


def test_a_drone_flies_its_route_and_despawns_at_the_end() -> None:
    threat = Threat.model_validate(
        {
            "id": "t",
            "class_id": "c",
            "label": {"en": "T", "hi": "T"},
            "spawn_s": 0,
            "start": {"x": 0, "y": 0, "z": 50},
            "start_heading_deg": 180,  # facing away: must turn round first
            "start_speed_mps": 10,
            "limits": {
                "max_speed_mps": 20,
                "max_accel_mps2": 3,
                "max_climb_mps": 4,
                "max_descent_mps": 4,
                "max_turn_rate_dps": 30,
                "min_altitude_m": 10,
                "max_altitude_m": 300,
            },
            "route": [
                {"position": {"x": 0, "y": 800, "z": 120}, "speed_mps": 18, "hold_s": 5},
                {"position": {"x": 600, "y": 800, "z": 60}, "speed_mps": 12},
            ],
            "on_route_end": "despawn",
        }
    )
    d = Drone.pending(threat)
    d.status = "active"
    env = Envelope.of(threat.limits)
    events: list[str] = []
    for _ in range(4000):
        events += [kind for kind, _ in step(d, threat, env, (0.0, 0.0))]
        if "threat.despawn" in events:
            break
    assert events == ["threat.waypoint", "threat.waypoint", "threat.route_end", "threat.despawn"]


def test_loop_returns_to_the_first_waypoint_and_loiter_keeps_orbiting() -> None:
    base = {
        "id": "t",
        "class_id": "c",
        "label": {"en": "T", "hi": "T"},
        "spawn_s": 0,
        "start": {"x": 0, "y": 0, "z": 50},
        "start_heading_deg": 0,
        "start_speed_mps": 10,
        "limits": {
            "max_speed_mps": 15,
            "max_accel_mps2": 3,
            "max_climb_mps": 4,
            "max_descent_mps": 4,
            "max_turn_rate_dps": 45,
            "min_altitude_m": 10,
            "max_altitude_m": 300,
        },
        "route": [
            {"position": {"x": 0, "y": 400, "z": 50}, "speed_mps": 10},
            {"position": {"x": 400, "y": 400, "z": 50}, "speed_mps": 10},
        ],
    }
    for mode, expected_leg in (("loop", 0), ("loiter", 1)):
        threat = Threat.model_validate(base | {"on_route_end": mode})
        d = Drone.pending(threat)
        d.status = "active"
        env = Envelope.of(threat.limits)
        seen: list[str] = []
        for _ in range(4000):
            seen += [kind for kind, _ in step(d, threat, env, (0.0, 0.0))]
            if "threat.route_end" in seen:
                break
        assert d.leg == expected_leg and d.status == "active"
        if mode == "loiter":
            for _ in range(2400):  # two minutes of orbit around the last waypoint
                step(d, threat, env, (0.0, 0.0))
            distance = math.hypot(d.x - 400, d.y - 400)
            assert 80 < distance < 160  # on the orbit, not drifting away


def test_subsystems_get_their_own_numpy_generator() -> None:
    rng = RngStreams(5)
    assert isinstance(rng["sensors"], np.random.Generator)
    assert rng["sensors"] is not rng["tracking"]


# ---------------------------------------------------------------------------- exp, log, atan2


@pytest.mark.parametrize("x", [i * 0.37 - 40.0 for i in range(217)])
def test_exp_matches_libm_closely(x: float) -> None:
    assert detmath.exp(x) == pytest.approx(math.exp(x), rel=1e-14)


@pytest.mark.parametrize("x", [1e-9, 0.01, 0.5, 0.7071, 1.0, 1.4143, 2.0, 10.0, 12345.678, 3.2e8])
def test_log_matches_libm_closely(x: float) -> None:
    assert detmath.log(x) == pytest.approx(math.log(x), rel=1e-13, abs=1e-15)


def test_log_refuses_non_positive_arguments() -> None:
    for bad in (0.0, -1.0):
        with pytest.raises(ValueError):
            detmath.log(bad)


def test_exp_and_log_invert_each_other() -> None:
    for x in (-30.0, -1.5, 0.0, 0.25, 7.0, 55.0):
        assert detmath.log(detmath.exp(x)) == pytest.approx(x, abs=1e-12)


def test_exp_clamps_instead_of_overflowing() -> None:
    assert math.isfinite(detmath.exp(1e6))
    assert detmath.exp(-1e6) >= 0.0


@pytest.mark.parametrize("y", [-9.0, -1.0, -0.2, 0.0, 0.3, 1.0, 40.0])
@pytest.mark.parametrize("x", [-7.0, -1.0, -1e-3, 0.0, 1e-3, 2.0, 55.0])
def test_atan2_matches_libm_closely(y: float, x: float) -> None:
    assert detmath.atan2(y, x) == pytest.approx(math.atan2(y, x), abs=2e-15)


def test_atan2_of_the_origin_is_zero() -> None:
    assert detmath.atan2(0.0, 0.0) == 0.0


def test_angle_wrapping() -> None:
    assert detmath.wrap360(-1e-20) == 0.0
    assert detmath.wrap360(-10.0) == 350.0
    assert detmath.wrap360(725.0) == 5.0
    assert detmath.wrap180(190.0) == -170.0
    assert detmath.wrap180(-190.0) == 170.0
    assert detmath.wrap180(180.0) == -180.0


@pytest.mark.parametrize("x", [-1e6, -37.0, -1.0, -0.4, 0.0, 1e-9, 0.7, 1.0, 1.5, 250.0])
def test_atan_matches_libm_closely(x: float) -> None:
    assert detmath.atan(x) == pytest.approx(math.atan(x), abs=2e-15)
