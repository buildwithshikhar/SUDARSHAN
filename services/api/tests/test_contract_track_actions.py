"""Track management and cueing are loggable actions (wave 4b), and nothing else is added."""

import json
from typing import get_args

import pytest
from pydantic import ValidationError

from app.contracts import ActionRecord
from app.contracts.events import TrackAction
from app.contracts.rulepack import Action

from .sim_cases import REPO

TRACK_ACTIONS = ("track-relabel", "track-merge", "track-split", "track-drop", "sensor-cue")


def test_the_five_track_actions_are_exactly_the_new_contract_values() -> None:
    assert get_args(TrackAction) == TRACK_ACTIONS


@pytest.mark.parametrize("name", TRACK_ACTIONS)
def test_a_track_action_is_a_valid_logged_input(name: str) -> None:
    record = ActionRecord(tick=10, actor="trainee:op-1", action=name, payload={"track": "T001"})
    assert record.action == name


def test_an_unknown_action_is_still_refused() -> None:
    with pytest.raises(ValidationError):
        ActionRecord(tick=10, actor="trainee:op-1", action="track-delete")


def test_track_actions_are_not_responses_so_no_rule_can_permit_them() -> None:
    assert not set(TRACK_ACTIONS) & set(get_args(Action))


def test_the_exported_schema_lists_them() -> None:
    schema = json.loads((REPO / "packs" / "schemas" / "action-record.v1.json").read_text())
    listed = [
        v for branch in schema["properties"]["action"]["anyOf"] for v in branch.get("enum", [])
    ]
    assert set(TRACK_ACTIONS) <= set(listed)
