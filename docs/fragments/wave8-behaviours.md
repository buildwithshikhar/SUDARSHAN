# Wave 8: swarm, flock and clutter behaviours

Fragment for `SIM_CORE.md` (and the user manual's scenario chapter). Code: `services/api/sim/behaviours/`, wiring in `sim/world.py` (`GroupLayer`) and `sim/kinematics.py` (`step_steered`). Contract: `groups` and `Threat.motion` in `scenario.v1` (additive; no existing scenario changes). Tests: `tests/test_behaviours_units.py`, `test_behaviours_world.py`, `test_behaviours_rule2.py`, `test_group_contract.py`.

## Honesty

Every number in a group (weights, spacing, link range, gains, speed margin, hold times) is a project-authored fictional value: register ID F01, `verified: false`. The models named below are the basis of the behaviour and are cited as the model only, never as validation: Reynolds boids (separation, alignment, cohesion, goal), Vicsek (heading noise as the order-to-disorder knob), Olfati-Saber, Fax and Murray (consensus over a graph with link loss), Desai et al. (leader-follower), all from [02-research.md](02-research.md) section 3. Nothing here is a model of any real system, and nothing in it claims training effectiveness. The stigmergy row of that table is not implemented.

## Rule 2: kinematics only

A group member goes only to its group's own authored waypoints and to its group-mates. No code in `sim/behaviours/` or in the group part of `sim/world.py` reads defended places, zones, sensors, the operator, the tracker or the rule pack, and no function there takes one as an argument; the contract has no group field that could name a place to go other than the group's route (and a tether's anchor). There is no guidance, pursuit, targeting or terminal-attack logic of any kind. `tests/test_behaviours_rule2.py` reads the sources and fails if they mention the forbidden words, import a module that could supply a destination, or take such an argument. A route that ends in `despawn` or `loiter` ends like any other route.

## The model

A **group** (`kind` swarm or flock; a flock is made of clutter threats, a swarm of non-clutter ones) lists its **members**, ordinary `Threat` entries that keep their own class, limits, spawn and start. The group steers them; each member still obeys its own class envelope (turn rate, acceleration, speed, climb, altitude band) through `kinematics.step_steered`, the same code a route follower uses. A member's own `route` is ignored but must stay valid.

The group moves at the speed the slowest active member's envelope allows: `min(route speed, 0.85 x slowest max_speed_mps)`. The 0.85 leaves room to close up on slots.

### Topologies

- **leader-follower**: the leader flies the guide route like a route follower. Each follower holds a slot in the leader's frame with a proportional controller (0.5 per second of position error, correction capped at half the group speed) plus a separation push. A follower hears the leader through any chain of links: it is steered by the slot while it is in the leader's connected component, and otherwise holds its last formation heading and speed and flocks with the neighbours it is linked to, matching their mean speed.
- **leaderless**: a virtual guide point flies the route at the group speed (turn rate at most half the slowest member's and 20 deg/s) and waits when the group's centroid is more than `2 x spacing_m x sqrt(n) + 50 m` behind it. Members flock: weighted separation, alignment, cohesion and goal. For `saturation` they take lanes instead (below).

### Flocking terms (`boids.py`)

Heading = unit vector of `w_alignment x A + w_separation x S + w_cohesion x C + w_goal x G`, then rotated by the Vicsek noise.

- **Separation S**: away from every neighbour within `spacing_m`, linearly stronger when closer; length capped at 2.
- **Alignment A**: the consensus step `u_i + eps x sum_j (u_j - u_i)` over linked neighbours within `neighbour_radius_m`, `eps = 1/k`, which is the mean of their headings. No linked neighbour leaves the heading unchanged.
- **Cohesion C**: towards the centroid of the linked neighbours within the radius, zero while it is within 1.5 spacings and full from 2.5 spacings.
- **Goal G**: towards the guide point, fading to the guide's heading inside the group's own extent (`max(neighbour_radius_m, 1.5 x spacing_m x sqrt(n))`).
- **Vicsek noise**: rotate the formed heading by `(1 - discipline) x pi x xi`, `xi` in [-1, 1) from a keyed draw. Discipline 1 takes no draw. The draw is held for one second per member (the noise epoch), because an independent draw every tick is averaged away by the turn-rate limit and gives no disorder at all. In leader-follower groups the noise acts on the followers' desired heading, not on the leader.
- Speed: group speed plus 0.5 per second of along-track lag behind the guide, between 0.3 and 1.5 times the group speed (the member's envelope still clamps it).

### Parameters (`Group`)

| Field | Unit | Default | Meaning |
|---|---|---|---|
| `id`, `members` | slug, 2..64 threat IDs | | Members are unique across all groups and must exist; at most 32 groups. |
| `kind` | swarm / flock | swarm | A label with one check: flock = all clutter, swarm = none. |
| `topology`, `leader` | | leaderless | `leader` is required with leader-follower and refused otherwise. |
| `intent` | | transit | transit, loiter, probe or saturation (below). It fixes the formation. |
| `route`, `on_route_end` | waypoints | loiter | The guide path (no holds; inside the play area; altitude inside every member's band). End: loiter, loop or despawn. |
| `discipline` | 0..1 | 0.9 | 1 perfectly ordered, 0 disordered. |
| `spacing_m` | m, 3..200 | 20 | Desired neighbour spacing. |
| `neighbour_radius_m` | m, 5..1000 | 80 | Sensing radius for alignment, cohesion and separation; at least `spacing_m`. |
| `link_range_m` | m, 10..5000 | 150 | Pairs closer than this can be linked. |
| `link_loss` | 0..1 | 0 | Probability a link is down in a link epoch. |
| `link_epoch_s` | s, 0.5..60 | 1 | Links change only at epoch boundaries. |
| `leader_loss` | elect / disperse / loiter | elect | What the group does after the hold. |
| `leader_loss_hold_s` | s, 0..30 | 4 | The hesitation after the leader is lost. |
| `probe_standoff_m`, `probe_cycles` | m 10..5000, 1..10 | 200, 2 | Probe intent. |
| `lane_spacing_m` | m, 3..200 | 30 | Saturation lane spacing. |
| `loiter_radius_m` | m, 20..5000 | 120 | Orbit radius for loiter, for the end-of-route loiter and for `leader_loss: loiter`. |
| `weights` | 0..5 each | separation 1.0, alignment 1.5, cohesion 0.6, goal 1.0 | The four flocking weights. |

### Intents (`intents.py`)

The guide (the leader, or the virtual point) moves a cursor along the route; arrival is within the larger of 15 m and its turn radius.

- **transit**: fly the route, then `on_route_end`. Formation: a column (slot k is `k x spacing_m` behind the leader).
- **loiter**: orbit `route[0]` at `loiter_radius_m`. Formation: a cluster of staggered rows.
- **probe**: fly the route to the start of the final leg, then out to a point `probe_standoff_m` short of the final waypoint (never closer than a tenth of the leg to its start), turn back to the start of the final leg, and repeat `probe_cycles` times; then `on_route_end` there. A one-waypoint route uses where the guide started as the start of the leg. Formation: cluster. The guide never reaches the final waypoint.
- **saturation**: fly the route like transit with the members in parallel lanes, line abreast. Led: slots alternate right and left of the leader at `lane_spacing_m`. Leaderless: lane `(rank - (n-1)/2) x lane_spacing_m` across the guide track, by rank of member ID, and each member matches the guide's velocity plus the slot error, so the line arrives together. It ends like any route.

At the end of a `despawn` route every active member is retired on the same tick (`threat.despawn`, reason `route-end`).

### Link graph (`links.py`)

At each epoch boundary every pair within `link_range_m` is linked unless its keyed draw for that epoch is below `link_loss`; with loss 0 or 1 no draw is taken. The link set is kept until the next boundary (and is part of the saved state), so the cost is hash draws per epoch, not per tick. Connected components come from a union-find in fixed order. Members spawned after a boundary have no links until the next one.

### Formations (`leaderfollower.py`)

Slots are assigned to followers in order of their IDs, by rank among the active followers, so slots close up when a follower is gone. Cluster: rows of about `sqrt(followers)` members, rows `0.866 x spacing_m` apart, alternate rows shifted by half a spacing.

## Leader loss

Applies to leader-follower groups. "Removed" means the leader's status is no longer `active` (the future effector wave sets it; tests set it directly).

1. At the first group step on which the leader is not active, after it has been seen active, `group.leader_lost` is logged with `{group, leader, hold_s}` (the group step runs before movement, so a leader retired by the area check on tick t is noticed on tick t + 1). The group enters `hold`.
2. For `leader_loss_hold_s` (exactly `round(hold_s x 20)` ticks, counting the tick of the event) every follower keeps its last formation heading and speed, with no separation and no noise, and holds its altitude.
3. On the next tick, according to `leader_loss`:
   - **elect**: the lowest-ID active member becomes leader and `group.leader_elected` is logged with `{group, leader, previous}`. It takes the guide route over from the current leg (the cursor, including probe cycles, is the group's and is kept), and the followers re-form behind it with slots recomputed.
   - **disperse**: the group becomes leaderless. A virtual guide starts at the group centroid with the members' mean heading and continues towards the cursor's current waypoint. No event.
   - **loiter**: every member orbits the centroid at the moment the hold ended (fixed from then on) at `loiter_radius_m`, at the group speed. No event.
4. With a hold of 0 the event pair is logged on the same tick. A second loss starts another hold. A leader who has not spawned yet is not a lost leader: followers fly on in their current heading until it appears.

Removing a member of a leaderless group changes nothing structural: no event, the guide flies on exactly as before, the others re-flock.

`group.formed` (`{group, members}`) is logged once, on the first tick at which no member is still pending. `group.route_end` (`{group, then}`) is logged when the guide's route ends. All four are ground truth: `sim/audience.py` allows a trainee only the events on its allow-list, so any `group.*` event is withheld (tested).

## Clutter motion (`Threat.motion`, `clutter.py`)

A threat with a motion ignores its `route` and keeps its class altitude band. Both motions set the drone's air heading and airspeed so that `ux x airspeed + wind` equals the ground velocity the displacement implies, which is what the sensors read.

- **tether** (kite): `anchor` (x, y, z), `length_m` 5..300, `sway_m` 0..100, `sway_period_s` 2..60. The station is `length_m x cos 50` downwind of the anchor (mean wind plus gust; in calm air the kite keeps its bearing) at `anchor.z + length_m x sin 50`, plus `sway_m x sin(2 pi t / period)` across the wind. The kite moves to the station within the class speed and climb limits and is held inside the tether radius. The contract refuses a tether whose flying height is outside the class band.
- **drift** (balloon): `climb_mps` 0..3. It moves with the wind at zero airspeed and climbs until the top of the class band. A balloon that leaves the play area is retired like any drone.

## Determinism

- Draws are keyed and stateless: SHA-256 of `(seed, "behaviour", group, member, tick, purpose)`, 53 bits, the pattern of the assist's `keyed_uniform`. No stream was added to `rng.STREAMS`, so no other subsystem's numbers move. Noise draws are keyed on the noise epoch (second), link draws on the link epoch and the pair (`"a:b"`, smaller ID first). `Draws.count` counts hash draws; the test bounds them per epoch.
- Only `+ - * /`, `sqrt`, `floor` and `sim/detmath.py` are used. A source check forbids libm maths, numpy, `random`, time, sets and `**` in `sim/behaviours/`.
- Everything is iterated in scenario order or sorted-ID order; no set or dict-order dependence (checked by running two processes with different `PYTHONHASHSEED`).
- State: `World.state()` has a `groups` key (one entry per group: formed flag, control mode, leader, hold counter, loiter centre, route cursor, guide point and heading, link epoch and pairs, last formation values) only when the scenario has groups, so every other scenario hashes exactly as before. `World.restore` restores it and refuses a snapshot whose `groups` does not match the scenario. A memo of the noise draw is not state: it is a pure function of the key.
- Tick order: step 3b, after the picture update and the gust and before movement, plans every group once (members in scenario order); step 4 then moves each active drone in scenario order: group members with `step_steered`, clutter with its motion, others along their route.

## Authoring helpers (`arrival.py`)

Not run by the world; `spawn_s` on each member stays authoritative. `arrival_offsets(profile, n, span_s, seed, waves=3)` for `simultaneous`, `staggered`, `waves` and `trickle`; `compose_members(base_class, n, decoy_fraction, silent_fraction, seed)` returns catalogue class IDs with exact counts (`round half up`) of `decoy-small` and `autonomous-small` placed by a keyed shuffle; `formation_starts(n, spacing_m, centre, heading_deg, intent)` gives start positions in the intent's formation. `metrics.py` has the order parameter (polarisation), radius of gyration, mean nearest-neighbour distance, cohesion index (share in the largest cluster at a radius) and component count, for the tests and the after-action review.

## Measured on the build laptop

24 members for 600 ticks (link loss 0.2, discipline 0.7): about 0.4 to 0.7 s CPU and 7,300 hash draws; 64 members for 200 ticks: about 0.5 s CPU and 5,000 hash draws (Apple silicon, Python 3.12, while other work was running). That is roughly 1 ms per tick for 24 members, against the 50 ms tick budget. Not a gate: `tests/test_behaviours_world.py::test_the_cost_of_a_swarm_is_bounded_and_links_are_drawn_per_epoch_not_per_tick` prints the figures (`pytest -s`) and asserts only the bound on hash draws, which is one per member per second plus one per linked-range pair per link epoch.
