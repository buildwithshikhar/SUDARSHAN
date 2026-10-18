"""What each audience may see of the event log.

A trainee's console gets only events that hold no ground truth, with the one field that does
(`target`, the real drone behind a track an action was about, and `truth`, what a contact report
is graded against) removed. The instructor and scoring
see everything. This module is the single place that decides: the live transport and the stored
log endpoint both call `trainee_event`.
"""

from typing import Any

from app.contracts import EventRecord

from .tracking.picture import TRAINEE_EVENT_TYPES

#: Operator input events (the action as the operator gave it) and their outcome.
_ACTION_EVENTS = frozenset(
    {
        "action.designate",
        "action.classify",
        "action.assess",
        "action.engage",
        "action.hold",
        "action.report",
        "action.track_relabel",
        "action.track_merge",
        "action.track_split",
        "action.track_drop",
        "action.sensor_cue",
        "action.rejected",
    }
)
TRAINEE_EVENTS = (
    TRAINEE_EVENT_TYPES | _ACTION_EVENTS | {"roe.verdict", "session.start", "session.end"}
)
#: Fields removed from a trainee's copy of an event payload.
_TRUTH_FIELDS = frozenset({"target", "truth"})


def trainee_event(record: EventRecord) -> dict[str, Any] | None:
    """The trainee's copy of an event, or `None` if the trainee may not see it."""
    if record.type not in TRAINEE_EVENTS:
        return None
    payload = {k: v for k, v in record.payload.items() if k not in _TRUTH_FIELDS}
    echoed = payload.get("payload")
    if record.type == "action.rejected" and isinstance(echoed, dict):
        payload["payload"] = {k: v for k, v in echoed.items() if k not in _TRUTH_FIELDS}
    return {
        "seq": record.seq,
        "t": record.t,
        "type": record.type,
        "actor": record.actor,
        "payload": payload,
    }
