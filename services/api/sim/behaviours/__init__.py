"""Group and clutter behaviours: swarms, flocks, kites and balloons, at kinematics level.

Pure and deterministic: no wall clock, no random stream (keyed hash draws only), no set or dict
order dependence, and only the maths in `sim/detmath.py` for anything that feeds the state hash.
Nothing here reads the scenario's places of interest, its sensors, the operator, the tracker or
the rule pack: a member steers only by its group's own route and its group-mates.
See docs/fragments/wave8-behaviours.md.
"""
