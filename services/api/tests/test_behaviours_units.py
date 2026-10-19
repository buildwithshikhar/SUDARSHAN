"""Unit tests of the pure behaviour modules: draws, boids, links, formations, intents, arrival
helpers, clutter motion and metrics."""

import hashlib
import json
import math

import pytest

from app.contracts.scenario import TETHER_SIN_ELEVATION
from sim import detmath
from sim.behaviours import arrival, boids, clutter, draws, intents, leaderfollower, links, metrics
from sim.constants import DT

# ---------------------------------------------------------------------------- draws


def test_a_draw_is_the_keyed_sha256_scaled_by_two_to_the_minus_53() -> None:
    payload = json.dumps([5, "behaviour", "g", "m", 9, "noise"], separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("ascii")).digest()
    expected = float(int.from_bytes(digest[:8], "big") >> 11) / 9007199254740992.0
    assert draws.uniform(5, "g", "m", 9, "noise") == expected
    assert 0.0 <= expected < 1.0


def test_a_draw_depends_on_every_part_of_its_key_and_on_nothing_else() -> None:
    base = draws.uniform(5, "g", "m", 9, "noise")
    keys = [
        (6, "g", "m", 9, "noise"),
        (5, "h", "m", 9, "noise"),
        (5, "g", "n", 9, "noise"),
        (5, "g", "m", 10, "noise"),
        (5, "g", "m", 9, "link"),
    ]
    assert all(draws.uniform(*k) != base for k in keys)
    # taking other draws in between changes nothing: the draw is stateless
    for k in keys:
        draws.uniform(*k)
    assert draws.uniform(5, "g", "m", 9, "noise") == base


def test_signed_draws_cover_minus_one_to_one() -> None:
    values = [draws.signed(1, "g", "m", t, "noise") for t in range(400)]
    assert -1.0 <= min(values) < -0.9 and 0.9 < max(values) < 1.0


def test_the_draw_counter_counts_hash_draws() -> None:
    d = draws.Draws(5, "g")
    assert d.uniform("m", 1, "noise") == draws.uniform(5, "g", "m", 1, "noise")
    assert d.signed("m", 1, "noise") == draws.signed(5, "g", "m", 1, "noise")
    assert d.count == 2


# ---------------------------------------------------------------------------- boids


def test_separation_pushes_away_from_a_close_neighbour_only() -> None:
    near = boids.separation(0.0, 0.0, 1.0, 0.0, [(10.0, 0.0, 1.0)], 20.0)
    assert near[0] < 0 and near[1] == 0 and near[0] == pytest.approx(-0.5)
    assert boids.separation(0.0, 0.0, 1.0, 0.0, [(20.0, 0.0, 1.0)], 20.0) == (0.0, 0.0)


def test_separation_is_capped_and_breaks_a_tie_by_side() -> None:
    crowd = [(1.0, 0.0, 1.0)] * 30
    sx, sy = boids.separation(0.0, 0.0, 1.0, 0.0, crowd, 20.0)
    assert math.hypot(sx, sy) == pytest.approx(boids.SEPARATION_CAP)
    left = boids.separation(0.0, 0.0, 1.0, 0.0, [(0.0, 0.0, 1.0)], 20.0)
    right = boids.separation(0.0, 0.0, 1.0, 0.0, [(0.0, 0.0, -1.0)], 20.0)
    assert left == (-0.0, 1.0) or left == (0.0, 1.0)
    assert right[1] == -1.0


def test_alignment_is_the_consensus_step_and_with_no_neighbour_changes_nothing() -> None:
    assert boids.alignment(1.0, 0.0, []) == (1.0, 0.0)
    ax, ay = boids.alignment(1.0, 0.0, [(0.0, 1.0), (0.0, -1.0), (0.0, 1.0)])
    # u + (1/3) * sum(u_j - u) is the mean of the neighbours' headings
    assert (ax, ay) == pytest.approx((0.0, 1.0 / 3.0))


def test_cohesion_pulls_only_beyond_the_dead_band_and_saturates() -> None:
    assert boids.cohesion(0.0, 0.0, [], 20.0) == (0.0, 0.0)
    assert boids.cohesion(0.0, 0.0, [(25.0, 0.0)], 20.0) == (0.0, 0.0)  # inside 1.5 spacings
    assert boids.cohesion(0.0, 0.0, [(0.0, 0.0)], 20.0) == (0.0, 0.0)  # on top of the centroid
    mid = boids.cohesion(0.0, 0.0, [(40.0, 0.0), (40.0, 0.0)], 20.0)
    assert mid == pytest.approx((0.5, 0.0))
    far = boids.cohesion(0.0, 0.0, [(0.0, 500.0)], 20.0)
    assert far == pytest.approx((0.0, 1.0))


def test_goal_heads_for_the_guide_far_away_and_flies_its_heading_close_in() -> None:
    far = boids.goal(0.0, 0.0, 1000.0, 0.0, 0.0, 1.0, 100.0)
    assert far == pytest.approx((1.0, 0.0))
    close = boids.goal(0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 100.0)
    assert close[1] > 0.98
    assert boids.goal(3.0, 4.0, 3.0, 4.0, 0.0, 1.0, 100.0) == (0.0, 1.0)


def test_noise_rotates_by_one_minus_discipline_times_pi_times_xi() -> None:
    assert boids.noise_rotate(0.0, 1.0, 1.0, 0.7) == (0.0, 1.0)  # discipline 1: no noise
    assert boids.noise_rotate(0.0, 1.0, 0.0, 0.0) == (0.0, 1.0)  # xi 0: no rotation
    x, y = boids.noise_rotate(0.0, 1.0, 0.0, 0.5)  # a quarter turn anticlockwise
    assert (x, y) == pytest.approx((-1.0, 0.0), abs=1e-12)
    x, y = boids.noise_rotate(1.0, 0.0, 0.5, -1.0)  # (1 - 0.5) * 180 degrees clockwise
    assert (x, y) == pytest.approx((0.0, -1.0), abs=1e-12)
    for xi in (-1.0, -0.3, 0.9):
        nx, ny = boids.noise_rotate(0.6, 0.8, 0.3, xi)
        assert math.hypot(nx, ny) == pytest.approx(1.0)


def test_blend_weights_the_four_terms_and_keeps_the_heading_when_they_cancel() -> None:
    assert boids.blend(0.0, 1.0, (0, 0), (0, 0), (0, 0), (0, 0), (1, 1, 1, 1)) == (0.0, 1.0)
    # all weight on the goal: the heading is the goal's direction
    h = boids.blend(0.0, 1.0, (0.0, 1.0), (0, 0), (0, 0), (1.0, 0.0), (0.0, 0.0, 0.0, 2.0))
    assert h == pytest.approx((1.0, 0.0))
    # weights are (separation, alignment, cohesion, goal)
    h = boids.blend(0.0, 1.0, (1.0, 0.0), (0.0, 1.0), (0, 0), (0, 0), (0.0, 1.0, 0.0, 0.0))
    assert h == pytest.approx((1.0, 0.0))
    h = boids.blend(0.0, 1.0, (1.0, 0.0), (0.0, 1.0), (0, 0), (0, 0), (1.0, 0.0, 0.0, 0.0))
    assert h == pytest.approx((0.0, 1.0))


# ---------------------------------------------------------------------------- links


def _line(n: int, gap: float) -> tuple[list[str], list[float], list[float]]:
    return [f"m{i}" for i in range(n)], [i * gap for i in range(n)], [0.0] * n


def test_links_join_pairs_in_range_and_need_no_draw_without_loss() -> None:
    ids, xs, ys = _line(4, 100.0)
    calls: list[links.Pair] = []

    def down(pair: links.Pair) -> float:
        calls.append(pair)
        return 0.5

    pairs = links.rebuild(ids, xs, ys, 150.0, 0.0, down)
    assert pairs == [("m0", "m1"), ("m1", "m2"), ("m2", "m3")]
    assert calls == []


def test_total_loss_removes_every_link_without_a_draw_and_partial_loss_draws_per_pair() -> None:
    ids, xs, ys = _line(4, 100.0)
    assert links.rebuild(ids, xs, ys, 150.0, 1.0, lambda p: pytest.fail("no draw")) == []
    calls: list[links.Pair] = []

    def down(pair: links.Pair) -> float:
        calls.append(pair)
        return 0.0 if pair == ("m1", "m2") else 0.9  # only m1-m2 is below the loss

    pairs = links.rebuild(ids, xs, ys, 250.0, 0.5, down)
    # a draw only for pairs in range (m0-m3 is 300 m apart)
    assert ("m0", "m3") not in calls and len(calls) == 5
    assert ("m1", "m2") not in pairs and ("m0", "m1") in pairs
    assert pairs == sorted(pairs)


def test_pairs_are_canonical() -> None:
    assert links.pair_of("b", "a") == ("a", "b") == links.pair_of("a", "b")


def test_components_come_from_a_union_find_in_a_fixed_order() -> None:
    ids = ["d", "c", "b", "a", "e"]
    graph = links.Graph(ids, [("a", "b"), ("c", "d"), ("b", "c"), ("x", "a")])
    assert graph.components() == [["d", "c", "b", "a"], ["e"]]
    assert graph.neighbours("b") == ["a", "c"]
    assert graph.linked("a", "b") and not graph.linked("a", "e")  # x is not a member
    assert links.component_count(ids, [("a", "b")]) == 4
    assert links.component_count(ids, []) == 5
    # the result does not depend on the order the pairs are listed in
    pairs = [("a", "b"), ("c", "d"), ("b", "c"), ("d", "e")]
    assert links.Graph(ids, pairs).components() == links.Graph(ids, pairs[::-1]).components()


def test_distance() -> None:
    assert links.distance(0.0, 0.0, 3.0, 4.0) == 5.0


# ---------------------------------------------------------------------------- formations


def test_a_column_puts_followers_in_line_behind_the_leader() -> None:
    assert leaderfollower.offsets("column", 4, 10.0) == [
        (0.0, 0.0),
        (-10.0, 0.0),
        (-20.0, 0.0),
        (-30.0, 0.0),
    ]


def test_a_line_abreast_alternates_sides_at_even_spacing() -> None:
    out = leaderfollower.offsets("line", 6, 30.0)
    assert [r for _, r in out] == [0.0, 30.0, -30.0, 60.0, -60.0, 90.0]
    assert all(f == 0.0 for f, _ in out)


def test_a_cluster_is_staggered_rows_behind_the_leader() -> None:
    out = leaderfollower.offsets("cluster", 8, 20.0)
    assert out[0] == (0.0, 0.0) and len(out) == 8
    rows = sorted({round(f, 6) for f, _ in out[1:]})
    assert len(rows) >= 2 and all(f < 0 for f in rows)
    first_row = [r for f, r in out[1:] if f == rows[-1]]
    second_row = [r for f, r in out[1:] if f == rows[-2]]
    assert first_row and second_row
    # spacing within a row is the formation spacing
    assert sorted(first_row)[1] - sorted(first_row)[0] == pytest.approx(20.0)
    # and the second row is shifted by half a spacing
    assert min(second_row) - min(first_row) == pytest.approx(10.0)
    assert leaderfollower.offsets("cluster", 1, 20.0) == [(0.0, 0.0)]


def test_lane_offsets_are_evenly_spaced_across_the_track() -> None:
    lanes = [leaderfollower.lane_offset(r, 5, 30.0) for r in range(5)]
    assert lanes == [-60.0, -30.0, 0.0, 30.0, 60.0]


def test_the_formation_follows_the_intent() -> None:
    assert [
        leaderfollower.formation_for(i) for i in ("transit", "loiter", "probe", "saturation")
    ] == [
        "column",
        "cluster",
        "cluster",
        "line",
    ]


def test_slots_are_laid_out_in_the_leaders_frame() -> None:
    # leader at (100, 50) flying east: forward is +x, right is -y
    x, y = leaderfollower.to_world(100.0, 50.0, 1.0, 0.0, (-10.0, 20.0))
    assert (x, y) == pytest.approx((90.0, 30.0))
    # flying north: forward is +y, right is +x
    x, y = leaderfollower.to_world(0.0, 0.0, 0.0, 1.0, (5.0, 7.0))
    assert (x, y) == pytest.approx((7.0, 5.0))


def test_the_slot_controller_is_proportional_and_capped() -> None:
    vx, vy = leaderfollower.follow(0.0, 0.0, 4.0, 0.0, 10.0, 0.0, (0.0, 0.0), 5.0, 100.0)
    assert (vx, vy) == pytest.approx((10.0 + 0.5 * 4.0, 0.0))
    vx, vy = leaderfollower.follow(0.0, 0.0, 400.0, 0.0, 10.0, 0.0, (0.0, 0.0), 5.0, 3.0)
    assert (vx, vy) == pytest.approx((13.0, 0.0))  # the correction stops at 3 m/s
    vx, vy = leaderfollower.follow(0.0, 0.0, 0.0, 0.0, 10.0, 0.0, (-1.0, 0.5), 2.0, 3.0)
    assert (vx, vy) == pytest.approx((8.0, 1.0))  # separation adds to the velocity


def test_heading_and_speed_of_a_velocity() -> None:
    assert leaderfollower.heading_and_speed(3.0, 4.0, (0.0, 1.0)) == ((0.6, 0.8), 5.0)
    assert leaderfollower.heading_and_speed(0.0, 0.0, (0.0, 1.0)) == ((0.0, 1.0), 0.0)


# ---------------------------------------------------------------------------- intents


def _params(intent: str = "transit", end: str = "loiter", cycles: int = 2) -> intents.IntentParams:
    return intents.IntentParams(intent, end, 120.0, 300.0, cycles)


ROUTE: list[intents.Leg] = [(1000.0, 0.0, 50.0, 10.0), (1000.0, 1000.0, 60.0, 12.0)]


def test_transit_flies_the_legs_in_order_and_orbits_the_end_when_told_to_loiter() -> None:
    cur = intents.Cursor()
    a = intents.guide(_params(), ROUTE, cur, 0.0, 0.0, 15.0)
    assert (a.x, a.y, a.z, a.speed, a.orbit, a.ended) == (1000.0, 0.0, 50.0, 10.0, 0.0, False)
    a = intents.guide(_params(), ROUTE, cur, 995.0, 0.0, 15.0)
    assert cur.leg == 1 and (a.x, a.y, a.speed) == (1000.0, 1000.0, 12.0)
    a = intents.guide(_params(), ROUTE, cur, 1000.0, 999.0, 15.0)
    assert a.ended and a.orbit == 120.0 and (a.x, a.y) == (1000.0, 1000.0) and not a.despawn
    a = intents.guide(_params(), ROUTE, cur, 1000.0, 999.0, 15.0)
    assert not a.ended and a.orbit == 120.0


def test_a_route_can_loop_or_despawn() -> None:
    cur = intents.Cursor()
    intents.guide(_params(end="loop"), ROUTE, cur, 1000.0, 0.0, 15.0)
    a = intents.guide(_params(end="loop"), ROUTE, cur, 1000.0, 1000.0, 15.0)
    assert a.ended and cur.leg == 0 and cur.phase == "run" and (a.x, a.y) == (1000.0, 0.0)
    cur = intents.Cursor()
    intents.guide(_params(end="despawn"), ROUTE, cur, 1000.0, 0.0, 15.0)
    a = intents.guide(_params(end="despawn"), ROUTE, cur, 1000.0, 1000.0, 15.0)
    assert a.ended and a.despawn
    assert intents.guide(_params(end="despawn"), ROUTE, cur, 1000.0, 1000.0, 15.0).despawn


def test_loiter_orbits_the_first_waypoint_and_never_ends() -> None:
    cur = intents.Cursor()
    a = intents.guide(_params("loiter"), ROUTE, cur, 5000.0, 5000.0, 15.0)
    assert (a.x, a.y, a.orbit, a.ended) == (1000.0, 0.0, 120.0, False)


def test_probe_stops_short_turns_back_and_repeats_then_ends() -> None:
    route: list[intents.Leg] = [(0.0, 0.0, 60.0, 10.0), (1000.0, 0.0, 60.0, 10.0)]
    p = _params("probe", "despawn", cycles=2)
    cur = intents.Cursor()
    a = intents.guide(p, route, cur, 0.0, 0.0, 15.0)  # at the start of the final leg
    assert cur.phase == "out" or cur.phase == "run"
    seen: list[str] = []
    x = 0.0
    for _ in range(200):
        a = intents.guide(p, route, cur, x, 0.0, 15.0)
        seen.append(cur.phase)
        if a.despawn:
            break
        x = a.x  # the guide reaches whatever it is sent to
    assert a.despawn and cur.cycle == 2
    assert seen.count("back") >= 2
    start, turn = intents.probe_points(route, cur, 300.0)
    assert start[:2] == (0.0, 0.0) and turn[:2] == (700.0, 0.0)  # 300 m short of the end


def test_probe_with_one_waypoint_uses_where_the_guide_started_and_can_loop_or_loiter() -> None:
    route: list[intents.Leg] = [(800.0, 0.0, 60.0, 10.0)]
    p = _params("probe", "loop", cycles=1)
    cur = intents.Cursor()
    a = intents.guide(p, route, cur, 0.0, 0.0, 15.0)
    assert cur.phase == "out" and (cur.ox, cur.oy) == (0.0, 0.0) and a.x == pytest.approx(500.0)
    a = intents.guide(p, route, cur, 500.0, 0.0, 15.0)  # turn back
    assert cur.phase == "back" and cur.cycle == 1 and a.x == 0.0
    a = intents.guide(p, route, cur, 0.0, 0.0, 15.0)  # loop: start again from the first leg
    assert a.ended and cur.phase == "out" and cur.cycle == 0
    # loiter after the last cycle: orbit the start of the final leg
    cur = intents.Cursor()
    p = _params("probe", "loiter", cycles=1)
    for x in (0.0, 500.0, 0.0):
        a = intents.guide(p, route, cur, x, 0.0, 15.0)
    assert a.ended and a.orbit == 120.0 and (a.x, a.y) == (0.0, 0.0)


def test_probe_standoff_never_passes_the_start_of_the_leg() -> None:
    route: list[intents.Leg] = [(0.0, 0.0, 60.0, 10.0), (100.0, 0.0, 60.0, 10.0)]
    start, turn = intents.probe_points(route, intents.Cursor(), 5000.0)
    assert turn[0] == pytest.approx(10.0)  # a tenth of the leg from the start
    same: list[intents.Leg] = [(5.0, 5.0, 60.0, 10.0), (5.0, 5.0, 60.0, 10.0)]
    s, t = intents.probe_points(same, intents.Cursor(), 300.0)
    assert s == t


def test_a_probe_route_longer_than_two_points_runs_the_early_legs_first() -> None:
    route: list[intents.Leg] = [
        (0.0, 500.0, 60.0, 10.0),
        (0.0, 0.0, 60.0, 10.0),
        (1000.0, 0.0, 60.0, 10.0),
    ]
    p = _params("probe", "despawn", cycles=1)
    cur = intents.Cursor()
    intents.guide(p, route, cur, -500.0, 0.0, 15.0)
    assert cur.phase == "run" and cur.leg == 0
    intents.guide(p, route, cur, 0.0, 500.0, 15.0)
    assert cur.leg == 1 and cur.phase == "run"
    a = intents.guide(p, route, cur, 0.0, 0.0, 15.0)
    assert cur.phase == "out" and a.x == pytest.approx(700.0)


def test_the_cursor_survives_a_round_trip_through_state() -> None:
    cur = intents.Cursor(leg=2, phase="back", cycle=3, ox=1.5, oy=-2.5, cx=7.0, cy=8.0)
    assert intents.Cursor.from_state(cur.to_state()) == cur
    fresh = intents.Cursor()
    assert intents.Cursor.from_state(fresh.to_state()) == fresh


# ---------------------------------------------------------------------------- arrival


def test_simultaneous_arrivals_are_all_at_the_start() -> None:
    assert arrival.arrival_offsets("simultaneous", 5, 60.0, 1) == [0.0] * 5
    assert arrival.arrival_offsets("staggered", 1, 60.0, 1) == [0.0]


def test_staggered_arrivals_are_evenly_spread_over_the_span() -> None:
    out = arrival.arrival_offsets("staggered", 5, 40.0, 1)
    assert out == [0.0, 10.0, 20.0, 30.0, 40.0]


def test_waves_share_the_members_out_in_bursts() -> None:
    out = arrival.arrival_offsets("waves", 10, 60.0, 1, waves=3)
    assert out == [0.0] * 4 + [30.0] * 3 + [60.0] * 3
    assert arrival.arrival_offsets("waves", 4, 60.0, 1, waves=1) == [0.0] * 4
    assert arrival.arrival_offsets("waves", 3, 60.0, 1, waves=9) == [0.0, 30.0, 60.0]


def test_a_trickle_is_keyed_sorted_and_inside_the_span() -> None:
    a = arrival.arrival_offsets("trickle", 20, 120.0, 7)
    assert a == arrival.arrival_offsets("trickle", 20, 120.0, 7)
    assert a != arrival.arrival_offsets("trickle", 20, 120.0, 8)
    assert a == sorted(a) and a[0] >= 0.0 and a[-1] < 120.0


def test_arrival_profiles_are_checked() -> None:
    with pytest.raises(ValueError, match="unknown arrival profile"):
        arrival.arrival_offsets("stampede", 3, 10.0, 1)
    with pytest.raises(ValueError, match="at least 1"):
        arrival.arrival_offsets("staggered", 0, 10.0, 1)


def test_compose_members_gives_exact_counts_and_is_keyed() -> None:
    out = arrival.compose_members("rotary-small", 20, 0.25, 0.15, 11)
    assert out.count("decoy-small") == 5 and out.count("autonomous-small") == 3
    assert out.count("rotary-small") == 12 and len(out) == 20
    assert out == arrival.compose_members("rotary-small", 20, 0.25, 0.15, 11)
    assert out != arrival.compose_members("rotary-small", 20, 0.25, 0.15, 12)
    assert arrival.compose_members("fpv-small", 5, 0.0, 0.0, 1) == ["fpv-small"] * 5


def test_compose_members_rounds_half_up_and_refuses_impossible_mixes() -> None:
    out = arrival.compose_members("rotary-small", 10, 0.25, 0.0, 3)  # 2.5 rounds to 3
    assert out.count("decoy-small") == 3
    with pytest.raises(ValueError, match="exceed"):
        arrival.compose_members("rotary-small", 10, 0.7, 0.5, 3)
    with pytest.raises(ValueError, match="between 0 and 1"):
        arrival.compose_members("rotary-small", 10, 1.5, 0.0, 3)


def test_formation_starts_lay_members_out_in_the_intent_formation() -> None:
    column = arrival.formation_starts(4, 10.0, (100.0, 100.0), 90.0, "transit")
    assert column[0] == (100.0, 100.0)
    assert column[1] == pytest.approx((90.0, 100.0), abs=1e-9)  # behind a leader flying east
    line = arrival.formation_starts(3, 30.0, (0.0, 0.0), 0.0, "saturation")  # flying north
    assert sorted(x for x, _ in line) == pytest.approx([-30.0, 0.0, 30.0], abs=1e-9)
    assert all(abs(y) < 1e-9 for _, y in line)


# ---------------------------------------------------------------------------- clutter

BAND = clutter.Band(max_speed=12.0, max_climb=3.0, max_descent=3.0, min_alt=10.0, max_alt=150.0)


def _fly_kite(
    seconds: float, wind: tuple[float, float], start: tuple[float, float, float]
) -> list[clutter.Moved]:
    x, y, z = start
    ux, uy = 0.0, 1.0
    out: list[clutter.Moved] = []
    for tick in range(int(seconds * 20)):
        m = clutter.tether_step(
            x, y, z, ux, uy, tick * DT, (0.0, 0.0, 0.0), 100.0, 30.0, 10.0, wind, BAND
        )
        x, y, z, ux, uy = m.x, m.y, m.z, m.ux, m.uy
        out.append(m)
    return out


def test_a_kite_settles_downwind_of_its_anchor_and_never_leaves_the_line() -> None:
    track = _fly_kite(120.0, (4.0, 0.0), (10.0, 0.0, 20.0))
    for m in track:
        assert math.sqrt(m.x * m.x + m.y * m.y + m.z * m.z) <= 100.0 + 1e-9
        assert BAND.min_alt <= m.z <= BAND.max_alt
    late = track[-400:]
    assert all(m.x > 0 for m in late)  # downwind of the anchor
    assert max(m.z for m in late) == pytest.approx(100.0 * TETHER_SIN_ELEVATION, abs=1.0)
    assert max(m.y for m in late) > 20.0 and min(m.y for m in late) < -20.0  # it sways


def test_the_motion_reproduces_the_ground_velocity_from_air_velocity_plus_wind() -> None:
    wind = (4.0, -1.0)
    x, y, z = 30.0, 10.0, 40.0
    ux, uy = 0.0, 1.0
    for tick in range(300):
        m = clutter.tether_step(
            x, y, z, ux, uy, tick * DT, (0.0, 0.0, 0.0), 100.0, 30.0, 10.0, wind, BAND
        )
        gx = m.ux * m.airspeed + wind[0]
        gy = m.uy * m.airspeed + wind[1]
        assert gx == pytest.approx((m.x - x) / DT, abs=1e-9)
        assert gy == pytest.approx((m.y - y) / DT, abs=1e-9)
        assert m.vz == pytest.approx((m.z - z) / DT)
        x, y, z, ux, uy = m.x, m.y, m.z, m.ux, m.uy


def test_a_kite_in_calm_air_keeps_its_bearing_and_respects_the_class_speed_limit() -> None:
    track = _fly_kite(60.0, (0.0, 0.0), (0.0, -20.0, 30.0))
    assert all(m.y < 0.0 for m in track[200:])  # still on the side it started, to the south
    # ground speed never exceeds the class maximum
    prev = (0.0, -20.0)
    for m in track:
        assert math.hypot(m.x - prev[0], m.y - prev[1]) / DT <= BAND.max_speed + 1e-6
        prev = (m.x, m.y)


def test_a_kite_started_outside_its_line_is_drawn_back_onto_it() -> None:
    m = clutter.tether_step(
        400.0, 0.0, 50.0, 0.0, 1.0, 0.0, (0.0, 0.0, 0.0), 100.0, 0.0, 10.0, (3.0, 0.0), BAND
    )
    assert math.sqrt(m.x * m.x + m.y * m.y + m.z * m.z) <= 100.0 + 1e-9


def test_a_kite_that_does_not_move_keeps_its_air_heading() -> None:
    # at its station in still air with no sway: no displacement, so the heading is unchanged
    reach = 100.0 * clutter.TETHER_COS_ELEVATION
    z = 100.0 * TETHER_SIN_ELEVATION
    m = clutter.tether_step(
        0.0, reach, z, 0.6, 0.8, 0.0, (0.0, 0.0, 0.0), 100.0, 0.0, 10.0, (0.0, 0.0), BAND
    )
    assert m.airspeed == pytest.approx(0.0, abs=1e-9) and (m.ux, m.uy) == (0.6, 0.8)


def test_a_balloon_drifts_with_the_wind_and_stops_climbing_at_its_ceiling() -> None:
    band = clutter.Band(6.0, 3.0, 3.0, 20.0, 60.0)
    x, y, z = 0.0, 0.0, 50.0
    for _ in range(400):
        m = clutter.drift_step(x, y, z, 0.0, 1.0, 1.0, (2.0, -1.0), band)
        assert m.airspeed == 0.0 and (m.ux, m.uy) == (0.0, 1.0)
        assert m.x - x == pytest.approx(2.0 * DT) and m.y - y == pytest.approx(-1.0 * DT)
        x, y, z = m.x, m.y, m.z
    assert z == 60.0 and m.vz == 0.0
    assert x == pytest.approx(2.0 * 400 * DT)


# ---------------------------------------------------------------------------- metrics


def test_polarisation_is_one_for_an_aligned_group_and_zero_for_opposed_pairs() -> None:
    assert metrics.polarisation([0.0, 0.0, 0.0], [1.0, 1.0, 1.0]) == pytest.approx(1.0)
    assert metrics.polarisation([1.0, -1.0], [0.0, 0.0]) == pytest.approx(0.0)
    assert metrics.polarisation([1.0, 0.0], [0.0, 1.0]) == pytest.approx(math.sqrt(0.5))


def test_radius_of_gyration_and_centroid() -> None:
    assert metrics.centroid([0.0, 10.0], [0.0, 20.0]) == (5.0, 10.0)
    assert metrics.radius_of_gyration([-3.0, 3.0], [0.0, 0.0]) == 3.0
    assert metrics.radius_of_gyration([5.0], [5.0]) == 0.0


def test_nearest_neighbour_and_cohesion_index() -> None:
    xs, ys = [0.0, 10.0, 100.0], [0.0, 0.0, 0.0]
    assert metrics.mean_nearest_neighbour(xs, ys) == pytest.approx((10.0 + 10.0 + 90.0) / 3.0)
    assert metrics.cohesion_index(xs, ys, 20.0) == pytest.approx(2.0 / 3.0)
    assert metrics.cohesion_index(xs, ys, 200.0) == 1.0
    assert metrics.cohesion_index([0.0], [0.0], 1.0) == 1.0


def test_component_count() -> None:
    assert metrics.component_count(["a", "b", "c"], [("a", "b")]) == 2


def test_the_maths_matches_the_deterministic_helpers() -> None:
    # headings built here use the same polynomial sin and cos the sim does
    h = detmath.heading_vector(30.0)
    assert metrics.polarisation([h[0]], [h[1]]) == pytest.approx(1.0)
