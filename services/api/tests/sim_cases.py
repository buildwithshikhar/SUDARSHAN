"""Fixed scenarios, seeds and action logs shared by the sim tests and golden files."""

from pathlib import Path
from typing import Any

from app.contracts import ActionRecord, ScenarioSpec
from app.contracts.loader import load_pack

REPO = Path(__file__).resolve().parents[3]
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def kestrel() -> ScenarioSpec:
    spec = load_pack(REPO / "packs" / "scenarios" / "kestrel-dawn-approach.v1.json")
    assert isinstance(spec, ScenarioSpec)
    return spec


def act(tick: int, actor: str, action: str, **payload: Any) -> ActionRecord:
    return ActionRecord.model_validate(
        {"tick": tick, "actor": actor, "action": action, "payload": payload}
    )


#: A plausible operator and instructor session against the Kestrel scenario.
KESTREL_ACTIONS = [
    act(400, "trainee:op-1", "designate", target="contact-a"),
    act(520, "trainee:op-1", "classify", target="contact-a", class_id="rotary-small"),
    act(700, "trainee:op-1", "assess", target="contact-a", identity="suspect"),
    act(700, "trainee:op-1", "report", target="contact-a", text="Rotary contact, north-east"),
    act(900, "trainee:op-1", "designate", target="contact-b"),  # not spawned yet: rejected
    act(1500, "instructor:lead", "set-weather", wind_speed_mps=7.5, wind_from_deg=270),
    act(2700, "trainee:op-1", "designate", target="contact-b"),
    act(3100, "trainee:op-1", "engage", target="contact-a", effector_class="ec-a"),
    act(3100, "trainee:op-1", "hold"),
    act(4200, "trainee:op-1", "set-weather", condition="clear"),  # trainee may not: rejected
    act(5000, "instructor:lead", "set-weather", condition="fog", visibility_m=900),
]

#: (name, seed, ticks, actions) for each golden file.
GOLDEN_CASES: list[tuple[str, int, int, list[ActionRecord]]] = [
    ("kestrel-default-seed", 240117, 8400, KESTREL_ACTIONS),
    ("kestrel-seed-1-no-actions", 1, 8400, []),
    ("kestrel-long-run", 99, 12000, KESTREL_ACTIONS),
]
