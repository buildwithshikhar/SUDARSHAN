"""The generator's sampler: one candidate scenario from a request and an attempt number.

Pure and deterministic. Every choice is a keyed SHA-256 draw (`sim.behaviours.draws`) named by what
it decides, so adding a draw never shifts another, and positions and speeds are rounded to 0.1 so
the spec's canonical JSON is the same on every platform. Nothing here runs the simulation; the
generator checks the candidate afterwards (docs/SCENARIO_ENGINE.md).

Threat behaviour is kinematics only (locked rule 2). A hostile contact flies authored waypoints in
from the edge of the play area and ends by loitering at a stand-off or flying past and leaving;
no route aims at the defended place, and none comes within `STANDOFF_M` of it.
"""

import hashlib
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.contracts import ScenarioSpec
from app.contracts.loader import load_pack as load_pack_file
from app.contracts.paths import packs_root
from app.contracts.sensor_profile import SensorProfile
from sim import detmath
from sim.behaviours import draws
from sim.behaviours.arrival import arrival_offsets, compose_members, formation_starts
from sim.catalogue import Catalogue
from sim.terrain import Terrain, load_pack, pack_dir

from .request import GENERATOR_VERSION, GeneratorRequest

#: No route comes closer than this to the defended place, orbit and formation included.
STANDOFF_M = 250.0
#: Radius of the orbit a drone flies when it loiters (sim/constants.py ORBIT_RADIUS_M).
ORBIT_M = 120.0
#: Seconds the oracle and a trainee need between a contact first being covered and it reaching the
#: inner zone: the rule pack's `respond_within_s` plus a margin the sampler aims for.
REACTION_MARGIN_S = 20.0
RESPOND_S = 45.0

START_HOUR = {"dawn": 6.0, "day": 12.0, "dusk": 18.0, "night": 23.0}
#: (condition, visibility in metres, wind m/s, gust sigma, cloud cover %)
WEATHER = {
    "clear": ("clear", 20000.0, 3.0, 0.5, 20.0),
    "haze": ("haze", 6000.0, 2.0, 0.4, 40.0),
    "rain": ("rain", 4000.0, 6.0, 1.2, 90.0),
    "fog": ("fog", 900.0, 1.0, 0.2, 100.0),
    "dust": ("dust", 2500.0, 8.0, 1.5, 30.0),
}
TEMPERATURE_C = {"dawn": 14.0, "day": 28.0, "dusk": 22.0, "night": 12.0}

SITE_NAMES = (
    ("Falcon Depot", "फाल्कन डिपो"),
    ("Kestrel Yard", "केस्ट्रेल यार्ड"),
    ("Osprey Annex", "ऑस्प्रे एनेक्स"),
    ("Merlin Station", "मर्लिन स्टेशन"),
    ("Harrier Store", "हैरियर स्टोर"),
    ("Lanner Post", "लैनर पोस्ट"),
    ("Goshawk Camp", "गॉशॉक कैंप"),
    ("Sparrow Hill Depot", "स्पैरो हिल डिपो"),
)
TERRAIN_NAMES = {
    "flat": ("open ground", "खुला मैदान"),
    "heron-ridge": ("farmland and low hills", "खेत और नीची पहाड़ियाँ"),
    "osprey-town": ("a small town", "एक छोटा कस्बा"),
}
TIME_NAMES = {
    "dawn": ("dawn", "भोर"),
    "day": ("daytime", "दिन"),
    "dusk": ("dusk", "सायंकाल"),
    "night": ("night", "रात"),
}
WEATHER_NAMES = {
    "clear": ("clear", "साफ़"),
    "haze": ("haze", "धुंध"),
    "rain": ("rain", "बारिश"),
    "fog": ("fog", "कोहरा"),
    "dust": ("dust", "धूल"),
}
ARCHETYPE_NAMES = {
    "single": ("a single drone", "एक अकेला ड्रोन"),
    "swarm": ("a swarm", "एक झुंड"),
    "fast-mover": ("a fast mover", "एक तेज़ ड्रोन"),
    "fixed-wing": ("a fixed-wing drone", "एक स्थिर-पंख ड्रोन"),
    "decoy-mix": ("a swarm with decoys", "नकली ड्रोन सहित एक झुंड"),
    "silent-raid": ("radio-silent drones", "रेडियो-शांत ड्रोन"),
}
GROUP_ARCHETYPES = ("swarm", "decoy-mix")


@lru_cache(maxsize=4)
def _profile_versions(root: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for path in sorted((Path(root) / "sensor-profiles").glob("*.yaml")):
        pack = load_pack_file(path)
        if isinstance(pack, SensorProfile):
            found[pack.id] = pack.version
    return found


def profile_versions() -> dict[str, str]:
    """The version of every sensor profile in the packs, by profile ID."""
    return _profile_versions(str(packs_root()))


def r1(value: float) -> float:
    """Round to a tenth of a metre (or metre per second): the spec's own precision."""
    return round(value, 1) + 0.0


def text(en: str, hi: str) -> dict[str, str]:
    return {"en": en, "hi": hi}


def sim_seed(seed: int, attempt: int) -> int:
    """The seed the candidate is simulated with: a hash of the request seed and the attempt."""
    digest = hashlib.sha256(f"{seed}:{attempt}:run".encode("ascii")).digest()
    return int.from_bytes(digest[:8], "big") >> 1


@dataclass(frozen=True, slots=True)
class Site:
    """The play area and zones around the defended place at the origin."""

    pack: Terrain | None
    pack_id: str | None
    half_extent_m: float
    inner_m: float
    outer_m: float

    def ground(self, x: float, y: float) -> float:
        return 0.0 if self.pack is None else float(self.pack.ground_m(x, y))

    @property
    def spawn_limit_m(self) -> float:
        """The farthest a contact may start from the origin along a bearing."""
        return self.half_extent_m * 0.85


def site_for(terrain: str) -> Site:
    if terrain == "flat":
        return Site(None, None, 5000.0, 900.0, 3200.0)
    pack = load_pack(pack_dir(terrain))
    return Site(pack, terrain, pack.half_extent_m, 500.0, 1500.0)


class Draw:
    """Keyed draws for one candidate."""

    def __init__(self, seed: int, attempt: int) -> None:
        self.seed, self.attempt = seed, attempt

    def u(self, *key: object) -> float:
        return draws.uniform(
            self.seed, "generator", ".".join(str(k) for k in key), self.attempt, "g"
        )

    def between(self, low: float, high: float, *key: object) -> float:
        return low + (high - low) * self.u(*key)

    def pick(self, options: list[Any] | tuple[Any, ...], *key: object) -> Any:
        return options[min(len(options) - 1, math.floor(self.u(*key) * len(options)))]


def polar(bearing_deg: float, range_m: float) -> tuple[float, float]:
    ux, uy = detmath.heading_vector(bearing_deg)
    return ux * range_m, uy * range_m


def bearing_of(x: float, y: float) -> float:
    return detmath.wrap360(detmath.atan2(x, y) / detmath.DEG)


@dataclass(slots=True)
class Plan:
    """What the sampler has built so far."""

    threats: list[dict[str, Any]]
    groups: list[dict[str, Any]]
    filed_flights: list[dict[str, Any]]
    #: Approach bearings of the hostile events, for aiming cameras.
    bearings: list[float]
    #: The last time any hostile route ends, for the scenario's length.
    hostile_end_s: float


class Sampler:
    def __init__(self, request: GeneratorRequest, attempt: int, catalogue: Catalogue) -> None:
        self.request = request
        self.attempt = attempt
        self.catalogue = catalogue
        self.d = Draw(request.seed, attempt)
        self.site = site_for(request.terrain)
        diff = request.difficulty
        self.load, self.amb = diff.threat_load / 100.0, diff.ambiguity / 100.0
        self.speed, self.stealth = diff.speed / 100.0, diff.stealth / 100.0
        self.degr = diff.degradation / 100.0

    # ------------------------------------------------------------------ pieces

    def limits(self, class_id: str) -> dict[str, float]:
        return self.catalogue.limits_for(class_id).model_dump(mode="json")

    def height(self, x: float, y: float, agl: float, class_id: str) -> float:
        """A `z` that is `agl` above the ground at (x, y), kept inside the class's altitude band."""
        lim = self.catalogue.get(class_id).envelope
        z = self.site.ground(x, y) + agl
        return r1(min(max(z, lim.min_altitude.value + 1.0), lim.max_altitude.value - 1.0))

    def threat(
        self,
        name: str,
        class_id: str,
        label: tuple[str, str],
        start: tuple[float, float, float],
        heading: float,
        speed: float,
        spawn_s: float,
        route: list[tuple[float, float, float, float]],
        on_end: str,
        disposition: str | None = None,
    ) -> dict[str, Any]:
        cls = self.catalogue.get(class_id)
        return {
            "id": name,
            "class_id": class_id,
            "disposition": disposition or cls.default_disposition,
            "label": text(*label),
            "spawn_s": r1(spawn_s),
            "start": {"x": r1(start[0]), "y": r1(start[1]), "z": r1(start[2])},
            "start_heading_deg": r1(heading % 360.0),
            "start_speed_mps": r1(speed),
            "limits": self.limits(class_id),
            "route": [
                {"position": {"x": r1(x), "y": r1(y), "z": r1(z)}, "speed_mps": r1(s)}
                for x, y, z, s in route
            ],
            "on_route_end": on_end,
        }

    # ------------------------------------------------------------------ hostile events

    def cruise(self, class_id: str) -> float:
        """The route speed for a class: from its cruise speed towards 85% of its top speed as the
        speed axis rises, and never faster than the play area leaves time to answer."""
        env = self.catalogue.get(class_id).envelope
        cruise, top = env.cruise_speed.value, env.max_speed.value
        v = cruise + self.speed * (0.85 * top - cruise)
        room = self.site.spawn_limit_m - self.site.inner_m
        return max(4.0, min(v, room / (RESPOND_S + REACTION_MARGIN_S)))

    def spawn_range(self, v: float) -> float:
        slack = 30.0 * (1.0 - self.speed)
        reach = self.site.inner_m + v * (RESPOND_S + REACTION_MARGIN_S + slack)
        return min(self.site.spawn_limit_m, max(reach, self.site.inner_m + 400.0))

    def standoff(self, reserve: float, key: str) -> float:
        """Where an approach ends: inside the inner zone for most, outside it for some."""
        floor = STANDOFF_M + ORBIT_M + reserve
        inside = self.d.u(key, "inside") < 0.7
        top = self.site.inner_m * 0.85 if inside else self.site.inner_m * 1.5
        low = min(floor, top)
        return r1(max(floor, self.d.between(low, max(top, floor), key, "standoff")))

    def approach(
        self, key: str, bearing: float, v: float, agl: float, class_id: str, reserve: float = 0.0
    ) -> tuple[list[tuple[float, float, float, float]], tuple[float, float, float]]:
        """A dog-leg from the edge of the play area to a stand-off: (route, start)."""
        r0 = min(self.spawn_range(v), self.site.half_extent_m * 0.9 - 1.5 * reserve - 50.0)
        rs = self.standoff(reserve, key)
        side = self.d.pick((-1.0, 1.0), key, "side")
        lateral = side * self.d.between(0.08, 0.22, key, "lateral") * r0
        mx, my = polar(bearing, r0 * 0.62)
        px, py = polar(bearing + 90.0, lateral)
        sx, sy = polar(bearing, r0)
        wobble = self.d.between(-20.0, 20.0, key, "wobble")
        ex, ey = polar(bearing + wobble, rs)
        route = [
            (mx + px, my + py, self.height(mx + px, my + py, agl, class_id), v),
            (ex, ey, self.height(ex, ey, agl * 0.8, class_id), v * 0.8),
        ]
        return route, (sx, sy, self.height(sx, sy, agl, class_id))

    def hostile_budget(self) -> int:
        """Hostile contacts asked for: the inverse of the `threat_count` axis."""
        return max(1, round(math.exp(self.load * math.log(25.0)) - 1.0))

    def plan_events(self) -> list[tuple[str, int, float]]:
        """(archetype, contacts, bearing) per hostile event."""
        budget = self.hostile_budget()
        events = 1 + (self.load >= 0.35) + (self.load >= 0.7)
        events = min(events, budget)
        base = self.d.between(0.0, 360.0, "bearing")
        out: list[tuple[str, int, float]] = []
        left = budget
        mix = list(self.request.threat_mix)
        for e in range(events):
            share = left if e == events - 1 else max(1, round(budget / events))
            share = min(share, left)
            allowed = [a for a in mix if a not in GROUP_ARCHETYPES or share >= 4] or mix
            kind = self.d.pick(allowed, "archetype", e)
            if kind in GROUP_ARCHETYPES:
                size = min(24, max(4, share))
            elif kind in ("single", "fixed-wing"):
                size = min(share, 3)
            else:
                size = min(share, 4)
            left = max(0, left - size)
            bearing = (base + (0.0 if e == 0 else self.d.between(70.0, 290.0, "turn", e))) % 360.0
            out.append((kind, size, bearing))
        return out

    def hostile(self, plan: Plan) -> None:
        for e, (kind, size, bearing) in enumerate(self.plan_events()):
            start_s = 8.0 + 55.0 * e + self.d.between(0.0, 25.0, "event-start", e)
            plan.bearings.append(bearing)
            if kind in GROUP_ARCHETYPES:
                self.swarm(plan, e, kind, size, bearing, start_s)
            else:
                self.singles(plan, e, kind, size, bearing, start_s)

    def singles(
        self, plan: Plan, e: int, kind: str, size: int, bearing: float, start_s: float
    ) -> None:
        for i in range(size):
            key = f"h{e}-{i}"
            class_id = self.hostile_class(kind, key)
            v = self.cruise(class_id)
            agl = 110.0 - self.stealth * 80.0 + self.d.between(-12.0, 12.0, key, "agl")
            theta = bearing + self.d.between(-12.0, 12.0, key, "spread")
            route, start = self.approach(key, theta, v, agl, class_id)
            if kind == "fixed-wing":
                route, start = self.fly_past(key, theta, v, agl + 40.0, class_id)
            spawn = start_s + i * self.d.between(10.0, 22.0, key, "gap")
            first = route[0]
            heading = bearing_of(first[0] - start[0], first[1] - start[1])
            end = "despawn" if kind == "fixed-wing" else "loiter"
            name = f"hostile-{e + 1}{chr(97 + i)}"
            label = (f"Contact H{e + 1}{chr(65 + i)}", f"संपर्क H{e + 1}{chr(65 + i)}")
            plan.threats.append(
                self.threat(name, class_id, label, start, heading, v, spawn, route, end)
            )
            plan.hostile_end_s = max(plan.hostile_end_s, spawn + self.route_s(start, route) + 30.0)

    def hostile_class(self, kind: str, key: str) -> str:
        if kind == "fast-mover":
            return "fpv-small"
        if kind == "fixed-wing":
            return "fixed-wing-medium" if self.speed > 0.55 else "fixed-wing-small"
        if kind == "silent-raid":
            return "autonomous-small"
        silent = self.d.u(key, "silent") < self.stealth * 0.5
        return "autonomous-small" if silent else "rotary-small"

    def fly_past(
        self, key: str, bearing: float, v: float, agl: float, class_id: str
    ) -> tuple[list[tuple[float, float, float, float]], tuple[float, float, float]]:
        """A fixed-wing pass: in from the edge, across the area at a distance, out the far side."""
        r0 = self.spawn_range(v)
        pass_r = max(STANDOFF_M + 80.0, self.d.between(0.55, 0.95, key, "pass") * self.site.inner_m)
        side = self.d.pick((-1.0, 1.0), key, "side")
        sx, sy = polar(bearing, r0)
        mx, my = polar(bearing + side * 80.0, pass_r)
        ex, ey = polar(bearing + side * 170.0, r0 * 0.9)
        route = [
            (mx, my, self.height(mx, my, agl, class_id), v),
            (ex, ey, self.height(ex, ey, agl, class_id), v),
        ]
        return route, (sx, sy, self.height(sx, sy, agl, class_id))

    def route_s(
        self, start: tuple[float, float, float], route: list[tuple[float, float, float, float]]
    ) -> float:
        t, (x, y, z) = 0.0, start
        for nx, ny, nz, s in route:
            t += math.dist((x, y, z), (nx, ny, nz)) / max(s, 0.1)
            x, y, z = nx, ny, nz
        return t

    def swarm_spacing(self, n: int) -> float:
        """Member spacing. Tight formations are the ambiguous ones (the tracker mixes up members
        that stay inside each other's gates), so the ambiguity axis closes them up; the contract
        allows at most 200 m."""
        return r1(min(200.0, 210.0 - 100.0 * self.amb))

    def swarm(self, plan: Plan, e: int, kind: str, n: int, bearing: float, start_s: float) -> None:
        key = f"g{e}"
        decoys = min(0.6, 0.15 + 0.5 * self.amb) if kind == "decoy-mix" else 0.0
        silent = round(self.stealth * 0.25 * 100) / 100.0
        classes = compose_members("rotary-small", n, decoys, silent, self.request.seed + e)
        lead = classes.index("rotary-small") if "rotary-small" in classes else 0
        classes[0], classes[lead] = classes[lead], classes[0]
        v = self.cruise("rotary-small") * 0.9
        agl = 110.0 - self.stealth * 70.0 + self.d.between(-10.0, 10.0, key, "agl")
        intent = self.d.pick(("transit", "saturation", "loiter"), key, "intent")
        spacing = self.swarm_spacing(n)
        edge = self.site.half_extent_m - 40.0
        for _ in range(8):  # close the formation up until it starts inside the play area
            extent = spacing * math.sqrt(n) * 0.75
            route, start = self.approach(key, bearing, v, agl, "rotary-small", reserve=extent)
            heading = bearing_of(route[0][0] - start[0], route[0][1] - start[1])
            spots = formation_starts(n, spacing, (start[0], start[1]), heading, intent)
            if all(abs(x) <= edge and abs(y) <= edge for x, y in spots) or spacing <= 40.0:
                break
            spacing = r1(max(40.0, spacing * 0.85))
        arrival = self.d.pick(("simultaneous", "staggered", "waves", "trickle"), key, "arrival")
        offsets = arrival_offsets(arrival, n, 6.0 + 2.0 * n, self.request.seed + e)
        ids = [f"swarm-{e + 1}-{i:02d}" for i in range(n)]
        for i, (name, class_id, (x, y)) in enumerate(zip(ids, classes, spots, strict=True)):
            label = (f"Contact S{e + 1}-{i + 1:02d}", f"संपर्क S{e + 1}-{i + 1:02d}")
            z = self.height(x, y, agl, class_id)
            plan.threats.append(
                self.threat(
                    name,
                    class_id,
                    label,
                    (x, y, z),
                    heading,
                    v,
                    start_s + offsets[i],
                    [(x, y, z, 5.0)],
                    "loiter",
                )
            )
        centre = route[-1]
        guide = [(centre[0], centre[1], centre[2], v)] if intent == "loiter" else route
        radius = max(math.hypot(x - start[0], y - start[1]) for x, y in spots)
        diameter = 2.0 * radius
        plan.groups.append(
            {
                "id": f"swarm-{e + 1}",
                "kind": "swarm",
                "members": ids,
                "topology": "leader-follower",
                "leader": ids[0],
                "intent": intent,
                "route": [
                    {"position": {"x": r1(x), "y": r1(y), "z": r1(z)}, "speed_mps": r1(s)}
                    for x, y, z, s in guide
                ],
                "on_route_end": "loiter",
                "discipline": r1(0.85 + 0.1 * (1.0 - self.speed)),
                "spacing_m": spacing,
                "lane_spacing_m": spacing,
                "neighbour_radius_m": r1(max(80.0, spacing * 2.0)),
                "link_range_m": r1(min(5000.0, (diameter + spacing) * 1.25 + 50.0)),
                "loiter_radius_m": r1(min(5000.0, max(90.0, radius + spacing))),
            }
        )
        plan.hostile_end_s = max(
            plan.hostile_end_s, start_s + offsets[-1] + self.route_s(start, route) + 40.0
        )

    # ------------------------------------------------------------------ look-alikes

    def clutter(self, plan: Plan) -> None:
        a = self.amb
        n_hostile = len([t for t in plan.threats if t["disposition"] == "hostile"])
        wanted = 0 if a < 0.05 else round(n_hostile * a / max(0.05, 1.0 - min(a, 0.95)))
        wanted = min(max(wanted, 1 if a >= 0.15 else 0), 40)
        civil = 0 if a < 0.2 else (1 if a < 0.7 else 2)
        birds = max(0, wanted - civil)
        flock = birds if birds >= 8 else 0
        singles = 0 if flock else birds
        kites = 0 if a < 0.35 else (1 if a < 0.7 else 2)
        balloons = 1 if a >= 0.5 else 0
        for i in range(min(singles, 6)):
            self.bird(plan, f"bird-{i + 1}", i)
        if flock:
            self.flock(plan, min(flock, 30))
        for i in range(kites):
            self.kite(plan, i)
        for i in range(balloons):
            self.balloon(plan, i)
        for i in range(civil):
            self.civil(plan, i)

    def spot(self, key: str, low: float, high: float) -> tuple[float, float]:
        bearing = self.d.between(0.0, 360.0, key, "bearing")
        return polar(bearing, self.d.between(low, high, key, "range"))

    def bird(self, plan: Plan, name: str, i: int) -> None:
        cx, cy = self.spot(name, 700.0, 1.0 * self.site.outer_m * 0.7)
        route = []
        for k in range(4):
            x, y = cx + 130.0 * (k % 2 * 2 - 1), cy + 130.0 * (k // 2 * 2 - 1)
            route.append(
                (x, y, self.height(x, y, self.d.between(30.0, 110.0, name, "agl", k), "bird"), 8.5)
            )
        start = route[0]
        plan.threats.append(
            self.threat(
                name,
                "bird",
                (f"Bird {i + 1}", f"पक्षी {i + 1}"),
                (start[0], start[1], start[2]),
                self.d.between(0.0, 360.0, name, "heading"),
                8.5,
                3.0 + i * 0.4,
                route,
                "loop",
            )
        )

    def flock(self, plan: Plan, n: int) -> None:
        cx, cy = self.spot("flock", 800.0, self.site.outer_m * 0.7)
        z = self.height(cx, cy, 60.0, "bird")
        spots = formation_starts(n, 8.0, (cx, cy), 0.0, "loiter")
        ids = [f"flock-{i:02d}" for i in range(n)]
        for i, (name, (x, y)) in enumerate(zip(ids, spots, strict=True)):
            plan.threats.append(
                self.threat(
                    name,
                    "bird",
                    (f"Bird {i + 1:02d}", f"पक्षी {i + 1:02d}"),
                    (x, y, self.height(x, y, 60.0, "bird")),
                    0.0,
                    8.0,
                    3.0,
                    [(x, y, z, 8.0)],
                    "loiter",
                )
            )
        plan.groups.append(
            {
                "id": "flock",
                "kind": "flock",
                "members": ids,
                "topology": "leaderless",
                "intent": "loiter",
                "route": [{"position": {"x": r1(cx), "y": r1(cy), "z": r1(z)}, "speed_mps": 9.0}],
                "on_route_end": "loiter",
                "discipline": 0.7,
                "spacing_m": 8.0,
                "neighbour_radius_m": 60.0,
                "link_range_m": 200.0,
                "loiter_radius_m": 60.0,
            }
        )

    def kite(self, plan: Plan, i: int) -> None:
        key = f"kite-{i + 1}"
        ax, ay = self.spot(key, 300.0, 700.0)
        gz = self.site.ground(ax, ay)
        anchor = {"x": r1(ax), "y": r1(ay), "z": r1(gz)}
        t = self.threat(
            key,
            "kite",
            (f"Kite {i + 1}", f"पतंग {i + 1}"),
            (ax, ay, self.height(ax, ay, 40.0, "kite")),
            0.0,
            1.0,
            2.0,
            [(ax, ay, self.height(ax, ay, 40.0, "kite"), 1.0)],
            "loiter",
        )
        t["motion"] = {
            "kind": "tether",
            "anchor": anchor,
            "length_m": 80.0,
            "sway_m": 20.0,
            "sway_period_s": r1(9.0 + 3.0 * i),
        }
        plan.threats.append(t)

    def balloon(self, plan: Plan, i: int) -> None:
        key = f"balloon-{i + 1}"
        x, y = self.spot(key, 400.0, 900.0)
        z = self.height(x, y, 40.0, "balloon")
        t = self.threat(
            key,
            "balloon",
            (f"Balloon {i + 1}", f"गुब्बारा {i + 1}"),
            (x, y, z),
            0.0,
            0.5,
            2.0,
            [(x, y, z, 0.5)],
            "loiter",
        )
        t["motion"] = {"kind": "drift", "climb_mps": 0.5}
        plan.threats.append(t)

    def civil(self, plan: Plan, i: int) -> None:
        key = f"civil-{i + 1}"
        cx, cy = self.spot(key, 600.0, self.site.outer_m * 0.75)
        radius = r1(self.d.between(180.0, 320.0, key, "radius"))
        agl = self.d.between(60.0, 100.0, key, "agl")
        route = []
        for k in range(4):
            x = cx + radius * (1, 0, -1, 0)[k]
            y = cy + radius * (0, 1, 0, -1)[k]
            route.append((x, y, self.height(x, y, agl, "civil-drone"), 7.0))
        start = route[0]
        plan.threats.append(
            self.threat(
                key,
                "civil-drone",
                (f"Civil flight {i + 1}", f"नागरिक उड़ान {i + 1}"),
                start[:3],
                90.0,
                6.0,
                12.0 + 6.0 * i,
                route,
                "loop",
            )
        )
        plan.filed_flights.append(
            {
                "id": f"ff-civil-{i + 1}",
                "label": text(f"Filed civil flight {i + 1}", f"दर्ज नागरिक उड़ान {i + 1}"),
                "from_s": 0.0,
                "to_s": 1.0,
                "center": {
                    "x": r1(cx),
                    "y": r1(cy),
                    "z": r1(self.height(cx, cy, agl, "civil-drone")),
                },
                "radius_m": r1(radius + 120.0),
            }
        )

    # ------------------------------------------------------------------ the rest of the scenario

    def sensors(self, bearings: list[float]) -> list[dict[str, Any]]:
        tod = self.request.time_of_day
        placed: list[dict[str, Any]] = []

        def add(sensor_id: str, profile: str, version: str, x: float, y: float, aim: float) -> None:
            ground = self.site.ground(x, y)
            placed.append(
                {
                    "id": sensor_id,
                    "profile": {"id": profile, "version": version},
                    "position": {"x": r1(x), "y": r1(y), "z": r1(ground + 6.0)},
                    "boresight_deg": r1(aim % 360.0),
                }
            )

        jitter = self.d.between(-20.0, 20.0, "sensor-jitter")
        add(
            "radar-1", "radar-generic-s", self.version("radar-generic-s"), -60.0 + jitter, 40.0, 0.0
        )
        for i, b in enumerate(bearings):
            x, y = -50.0 + 12.0 * i, 48.0 + 6.0 * i
            if tod in ("day", "dawn", "dusk"):
                add(f"eo-{i + 1}", "eo-generic-day", self.version("eo-generic-day"), x, y, b)
            if tod in ("night", "dawn", "dusk"):
                night = "eo-generic-nv" if tod == "night" else "ir-generic-thermal"
                add(
                    f"ir-{i + 1}",
                    "ir-generic-thermal",
                    self.version("ir-generic-thermal"),
                    x + 4,
                    y,
                    b,
                )
                if tod == "night":
                    add(f"nv-{i + 1}", night, self.version(night), x, y, b)
        add("rf-1", "rf-generic-passive", self.version("rf-generic-passive"), 70.0, -30.0, 0.0)
        add(
            "ac-1",
            "acoustic-generic-array",
            self.version("acoustic-generic-array"),
            20.0,
            60.0,
            0.0,
        )
        return placed

    def version(self, profile_id: str) -> str:
        return profile_versions()[profile_id]

    def degradations(self, sensors: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
        count = round(self.degr * 3 + 0.2)
        if count == 0:
            return []
        kinds = {
            "radar-generic-s": ("clutter", "sector-outage", "outage"),
            "eo-generic-day": ("haze", "glare", "outage"),
            "eo-generic-nv": ("haze", "outage"),
            "ir-generic-thermal": ("haze", "outage"),
            "rf-generic-passive": ("interference", "outage"),
            "acoustic-generic-array": ("wind-noise", "outage"),
        }
        out: list[dict[str, Any]] = []
        for i in range(count):
            sensor = self.d.pick(sensors, "degrade-sensor", i)
            kind = self.d.pick(kinds[sensor["profile"]["id"]], "degrade-kind", i)
            start = self.d.between(0.15, 0.55, "degrade-start", i) * duration
            length = 10.0 + 70.0 * self.degr * self.d.between(0.6, 1.0, "degrade-length", i)
            item: dict[str, Any] = {
                "sensor": sensor["id"],
                "kind": kind,
                "from_s": r1(start),
                "to_s": r1(min(start + length, duration - 1.0)),
                "severity": r1(0.4 + 0.5 * self.degr),
            }
            if kind == "sector-outage":
                centre = self.d.between(0.0, 360.0, "degrade-sector", i)
                item["sector_from_deg"] = r1((centre - 25.0) % 360.0)
                item["sector_to_deg"] = r1((centre + 25.0) % 360.0)
            out.append(item)
        return out

    # ------------------------------------------------------------------ assemble

    def build(self) -> ScenarioSpec:
        plan = Plan([], [], [], [], 0.0)
        self.hostile(plan)
        self.clutter(plan)
        r = self.request
        duration = float(min(600, max(180, math.ceil((plan.hostile_end_s + 60.0) / 30.0) * 30)))
        for f in plan.filed_flights:
            f["to_s"] = duration
        sensors = self.sensors(plan.bearings)
        name_en, name_hi = SITE_NAMES[
            min(len(SITE_NAMES) - 1, math.floor(self.d.u("site") * len(SITE_NAMES)))
        ]
        condition, visibility, wind, gust, cloud = WEATHER[r.weather]
        gz = self.site.ground(0.0, 0.0)
        terrain: dict[str, Any] = (
            {"kind": "flat", "elevation_m": 0}
            if self.site.pack is None
            else {"kind": "pack", "id": self.site.pack_id, "version": self.site.pack.version}
        )
        t_en, t_hi = TIME_NAMES[r.time_of_day]
        g_en, g_hi = TERRAIN_NAMES[r.terrain]
        w_en, w_hi = WEATHER_NAMES[r.weather]
        kinds_en = ", ".join(ARCHETYPE_NAMES[a][0] for a in r.threat_mix[:3])
        kinds_hi = ", ".join(ARCHETYPE_NAMES[a][1] for a in r.threat_mix[:3])
        data: dict[str, Any] = {
            "contract": "scenario.v1",
            "id": "pending",
            "version": "1.0.0",
            "title": text(f"{name_en}: generated, {t_en}", f"{name_hi}: उत्पन्न, {t_hi}"),
            "summary": text(
                f"A generated watch over {g_en} at {t_en}, {w_en} weather. Hostile contacts: "
                f"{kinds_en}.",
                f"{g_hi} पर {t_hi}, {w_hi} मौसम में एक उत्पन्न निगरानी। शत्रु संपर्क: {kinds_hi}।",
            ),
            "fictional": True,
            "default_seed": sim_seed(r.seed, self.attempt),
            "duration_s": duration,
            "world": {
                "terrain": terrain,
                "half_extent_m": self.site.half_extent_m,
                "start_time_of_day_h": START_HOUR[r.time_of_day],
                "weather": {
                    "condition": condition,
                    "visibility_m": visibility,
                    "wind_speed_mps": wind,
                    "wind_from_deg": r1(self.d.between(0.0, 360.0, "wind")),
                    "gust_sigma_mps": gust,
                    "temperature_c": TEMPERATURE_C[r.time_of_day],
                    "cloud_cover_pct": cloud,
                },
            },
            "rule_pack": {"id": "training-baseline", "version": "1.0.0"},
            "zones": [
                {
                    "id": "inner",
                    "role": "inner",
                    "label": text("Inner zone", "आंतरिक क्षेत्र"),
                    "center": {"x": 0, "y": 0, "z": r1(gz)},
                    "radius_m": self.site.inner_m,
                },
                {
                    "id": "outer",
                    "role": "outer",
                    "label": text("Outer zone", "बाहरी क्षेत्र"),
                    "center": {"x": 0, "y": 0, "z": r1(gz)},
                    "radius_m": self.site.outer_m,
                },
            ],
            "assets": [
                {
                    "id": "site",
                    "label": text(name_en, name_hi),
                    "position": {"x": 0, "y": 0, "z": r1(gz)},
                }
            ],
            "sensors": sensors,
            "degradations": self.degradations(sensors, duration),
            "filed_flights": plan.filed_flights,
            "threats": plan.threats,
            "groups": plan.groups,
        }
        spec = ScenarioSpec.model_validate(data)
        return spec


def request_hash(request: GeneratorRequest) -> str:
    """Six hex characters naming a request, for the scenario id."""
    from sim.canonical import canonical_json

    body = canonical_json({"request": request.model_dump(mode="json"), "v": GENERATOR_VERSION})
    return hashlib.sha256(body).hexdigest()[:6]


def scenario_id(request: GeneratorRequest) -> str:
    """`gen-<version>-<seed>-<hash>`: a pure function of the request and the generator version."""
    version = GENERATOR_VERSION.replace(".", "-")
    return f"gen-{version}-{request.seed}-{request_hash(request)}"
