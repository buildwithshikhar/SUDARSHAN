"""Live-session protocol, contracts `live-client.v1` and `live-server.v1`.

Every WebSocket frame is one MessagePack map whose `t` field names the message. The client sends
`live-client` messages; the server sends `live-server` messages. The server is authoritative: a
client asks (`act`), the simulation decides, and the outcome comes back as events in the next
frame.

A trainee's frames carry only what the operator's own sensors and tracker produced, plus the
operator's own commands and the rules verdicts. They have no field that could carry ground truth:
no truth identifier, true class, true position or disposition (docs/LIVE_SESSION.md).
"""

from typing import Annotated, Literal

from pydantic import Field, FiniteFloat, JsonValue, RootModel

from .common import Contract, Slug, Text, Vec3

PROTOCOL_VERSION = 1

LiveStatus = Literal["lobby", "running", "ended", "abandoned"]
DataStatus = Literal["reference", "verified"]
Identity = Literal["hostile", "suspect", "unknown", "neutral", "friend"]
TrackStatus = Literal["tentative", "confirmed", "coasting"]
Modality = Literal["radar", "eo", "ir", "rf", "acoustic"]

#: Actions a trainee may send, and the payload keys each one takes (everything else is refused).
OperatorAction = Literal[
    "designate",
    "classify",
    "assess",
    "engage",
    "hold",
    "report",
    "track-relabel",
    "track-merge",
    "track-split",
    "track-drop",
    "sensor-cue",
]
ACTION_KEYS: dict[str, tuple[str, ...]] = {
    "designate": ("track",),
    "classify": ("track", "class_id"),
    "assess": ("track", "identity"),
    "engage": ("track", "effector_class"),
    "hold": ("track",),
    #: A structured contact report: what (class), where (bearing and range from the site), how
    #: many, heading and the operator's confidence from 0 to 1. Every field but `track` is optional.
    "report": ("track", "class_id", "count", "bearing_deg", "range_m", "heading_deg", "confidence"),
    "track-relabel": ("track", "label", "exchange"),
    "track-merge": ("tracks",),
    "track-split": ("track",),
    "track-drop": ("track",),
    "sensor-cue": ("sensor", "track", "narrow"),
}

# ----------------------------------------------------------------------------- client to server


class Start(Contract):
    """Begin ticking (lobby to running)."""

    t: Literal["start"]


class End(Contract):
    """Finish the session now; the event log is stored and verified."""

    t: Literal["end"]


class Act(Contract):
    """An operator input. `seq` is the client's own counter, echoed in the `ack`."""

    t: Literal["act"]
    seq: Annotated[int, Field(ge=0, le=2**31)]
    action: OperatorAction
    payload: dict[str, JsonValue] = {}


class Ping(Contract):
    """Latency probe: the server echoes `ts` unchanged."""

    t: Literal["ping"]
    ts: FiniteFloat


class Leave(Contract):
    """Leave without ending; the session pauses until the trainee rejoins or the grace expires."""

    t: Literal["leave"]


class LiveClientMessage(
    RootModel[Annotated[Start | End | Act | Ping | Leave, Field(discriminator="t")]]
):
    pass


# ----------------------------------------------------------------------------- server to client


class SensorSite(Contract):
    id: Slug
    profile: Slug
    modality: Modality
    position: Vec3
    boresight_deg: float


class ZoneView(Contract):
    id: Slug
    role: Literal["inner", "outer", "restricted"]
    label: Text
    center: Vec3
    radius_m: float


class AssetView(Contract):
    id: Slug
    label: Text
    position: Vec3


class FlightView(Contract):
    id: Slug
    label: Text
    from_s: float
    to_s: float
    center: Vec3
    radius_m: float


class WeatherView(Contract):
    condition: Literal["clear", "haze", "rain", "fog", "dust"]
    visibility_m: float
    wind_speed_mps: float
    wind_from_deg: float
    temperature_c: float
    cloud_cover_pct: float


class FlatTerrainView(Contract):
    kind: Literal["flat"]
    elevation_m: float


class PackTerrainView(Contract):
    """Which terrain pack to draw; the client fetches its files from `/api/v1/terrain/{id}/`."""

    kind: Literal["pack"]
    id: Slug
    version: str


class Briefing(Contract):
    """The scenario as the operator is briefed: the site, the sensors and the filed flights.
    Never the threats."""

    id: Slug
    version: str
    title: Text
    summary: Text
    duration_s: float
    start_time_of_day_h: float
    half_extent_m: float
    terrain: Annotated[FlatTerrainView | PackTerrainView, Field(discriminator="kind")]
    weather: WeatherView
    zones: list[ZoneView]
    assets: list[AssetView]
    sensors: list[SensorSite]
    filed_flights: list[FlightView]


class RuleView(Contract):
    id: Slug
    title: Text
    permits: list[str]
    authority: Literal["operator", "commander"]
    effector_classes: list[Slug]
    when: dict[str, JsonValue]


class EffectorView(Contract):
    id: Slug
    label: Text
    description: Text


class RulesView(Contract):
    """The rule pack in force, with its version, for the decision panel."""

    id: Slug
    version: str
    title: Text
    default_action: Literal["hold"]
    effector_classes: list[EffectorView]
    rules: list[RuleView]


class Welcome(Contract):
    t: Literal["welcome"]
    protocol: Literal[1]
    session_id: str
    status: LiveStatus
    tick_hz: Literal[20]
    tick: int
    briefing: Briefing
    rules: RulesView
    operator_classes: list[str]
    identities: list[Identity]
    actions: list[OperatorAction]
    data_notice: str


class SensorStatus(Contract):
    id: Slug
    modality: Modality
    bearing_deg: float
    elevation_deg: float
    fov_deg: float | None
    supports_cue: bool
    cued: bool
    outage: bool
    position: Vec3
    #: Pixels across the field of view (cameras), so a console can turn `apparent_px` into an angle.
    pixels_h: int | None = None
    data_status: DataStatus


class Report(Contract):
    """One sensor report this tick: a plot on the PPI, or something in the EO view."""

    sensor_id: Slug
    modality: Modality
    tick: int
    azimuth_deg: float
    elevation_deg: float
    range_m: float | None
    radial_speed_mps: float | None
    sigma_range_m: float | None
    sigma_azimuth_deg: float | None
    sigma_elevation_deg: float | None
    sigma_radial_mps: float | None
    reported_class: str | None
    features: dict[str, float | str | bool]
    data_status: DataStatus


class TrackView(Contract):
    id: str
    label: str
    status: TrackStatus
    tick: int
    age_s: float
    since_update_s: float
    hits: int
    position: Vec3
    velocity: Vec3
    speed_mps: float
    heading_deg: float
    sigma_position_m: float
    sigma_speed_mps: float
    class_estimate: str | None
    class_support: float
    sensors: list[str]
    data_status: DataStatus


class AssistView(Contract):
    track: str
    tick: int
    flag: Literal["threat", "no-threat"]
    proposed_class: str | None
    confidence: float
    source: str
    basis: str
    data_status: DataStatus


class TraineeEvent(Contract):
    """An event the trainee may see (`sim.audience`): tracker lifecycle, the operator's own
    commands, rules verdicts and session start and end. No ground truth."""

    seq: int
    t: float
    type: str
    actor: str
    payload: dict[str, JsonValue]


class Frame(Contract):
    """One simulation tick as the operator's sensors and tracker saw it."""

    t: Literal["frame"]
    tick: int
    time_s: float
    time_of_day_h: float
    status: LiveStatus
    reports: list[Report]
    tracks: list[TrackView]
    assist: list[AssistView]
    sensors: list[SensorStatus]
    events: list[TraineeEvent]
    data_notice: str


class Status(Contract):
    t: Literal["status"]
    status: LiveStatus
    tick: int


class AckError(Contract):
    #: `invalid` (malformed), `not-running`, `unknown-action`, `too-many` (rate limit).
    code: Literal["invalid", "not-running", "unknown-action", "too-many"]
    message: str


class Ack(Contract):
    """The server received action `seq` (ok) or refused it before it reached the simulation.
    The simulation's own decision (ROE verdict, rejection) arrives as events."""

    t: Literal["ack"]
    seq: int
    ok: bool
    tick: int | None = None
    error: AckError | None = None


class Pong(Contract):
    t: Literal["pong"]
    ts: float
    tick: int


class EndSummary(Contract):
    ticks: int
    duration_s: float
    event_count: int
    head: str
    final_state_hash: str
    #: True when the stored event chain was read back and verified.
    verified: bool


class Ended(Contract):
    t: Literal["ended"]
    status: Literal["ended", "abandoned"]
    summary: EndSummary


class Fault(Contract):
    t: Literal["error"]
    code: str
    message: str


class LiveServerMessage(
    RootModel[
        Annotated[
            Welcome | Frame | Status | Ack | Pong | Ended | Fault,
            Field(discriminator="t"),
        ]
    ]
):
    pass
