"""The simulated AI assist: a seeded stand-in classifier over fused tracks.

There is no detector here and no accuracy claim. The assist looks at the true class of the drone a
track follows (a `TruthRef` the pipeline supplies, `None` for a false track) and answers with the
configured hit rate, false-alarm rate and class accuracy. It exists so a trainee can practise
deciding how far to trust a machine suggestion that is right most of the time and wrong some of it.
Every figure in `AssistConfig` is a project-authored fictional value (data-register ID F01,
`verified: false`), and every output is labelled "simulated assist" and `data_status: reference`,
even for a fully verified track.

Draws are stateless and keyed. A draw is SHA-256 of a canonical encoding of `(seed, "assist",
track_id, epoch, purpose)`, so the result for a track and its n-th assessment does not depend on
which other tracks were assessed first, how often, or in what order. The assist needs no stream in
`sim/rng.py`, and its state is only a counter and a tick per track.

Only `Assessment.view()` may reach a trainee. `Assessment.record()` adds the ground truth for the
instructor log and the after-action review.
"""

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.contracts import TICK_HZ

#: Classes that are not threats. Wave 8 extends this set with the other benign classes.
NON_THREAT_CLASSES: frozenset[str] = frozenset({"bird"})

#: Shown beside every suggestion, so the console can never read as a real detector.
SOURCE = "simulated assist"
BASIS = "configured hit and false-alarm rates; no real detector"
DATA_STATUS = "reference"

_UNKNOWN = "unknown"
_TWO53 = 9007199254740992.0  # 2**53, written out so no float power is ever taken
_SQRT12 = 1.7320508075688772  # as RngStreams.normalish: four uniforms, unit variance
_CONF_MIN = 0.05
_CONF_MAX = 0.99


def is_threat(class_id: str | None) -> bool:
    """A track on no real drone (`None`) and a bird are not threats; any other class is."""
    return class_id is not None and class_id not in NON_THREAT_CLASSES


def keyed_uniform(seed: int, *key: str | int) -> float:
    """A double in [0, 1) from the first 53 bits of SHA-256 over `(seed, "assist", *key)`.

    The encoding is compact ASCII JSON of the list, which keeps `1` and `"1"` apart and cannot be
    made ambiguous by a separator inside a track ID. Scaling by 2**-53 is exact on every platform.
    """
    payload = json.dumps([seed, "assist", *key], separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(payload.encode("ascii")).digest()
    return float(int.from_bytes(digest[:8], "big") >> 11) / _TWO53


@dataclass(frozen=True)
class AssistConfig:
    hit_rate: float = 0.90
    false_alarm_rate: float = 0.08
    class_accuracy: float = 0.85
    labels: tuple[str, ...] = ("rotary-small", "fixed-wing-small", "bird", "unknown")
    confidence_correct_mean: float = 0.80
    confidence_wrong_mean: float = 0.55
    confidence_sigma: float = 0.12
    reassess_s: float = 5.0

    def __post_init__(self) -> None:
        for name in ("hit_rate", "false_alarm_rate", "class_accuracy"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1, got {value}")
        for name in ("confidence_correct_mean", "confidence_wrong_mean"):
            value = getattr(self, name)
            if not _CONF_MIN <= value <= _CONF_MAX:
                raise ValueError(f"{name} must be between {_CONF_MIN} and {_CONF_MAX}, got {value}")
        sigma = self.confidence_sigma
        if not (math.isfinite(sigma) and sigma >= 0.0):
            raise ValueError(f"confidence_sigma must be finite and not negative, got {sigma}")
        if not (math.isfinite(self.reassess_s) and self.reassess_s > 0.0):
            raise ValueError(f"reassess_s must be finite and positive, got {self.reassess_s}")
        if len(set(self.labels)) != len(self.labels) or len(self.labels) < 2:
            raise ValueError("labels must hold at least two distinct entries")
        if any(not label for label in self.labels):
            raise ValueError("labels must not be empty strings")

    def to_state(self) -> dict[str, Any]:
        return {
            "hit_rate": self.hit_rate,
            "false_alarm_rate": self.false_alarm_rate,
            "class_accuracy": self.class_accuracy,
            "labels": list(self.labels),
            "confidence_correct_mean": self.confidence_correct_mean,
            "confidence_wrong_mean": self.confidence_wrong_mean,
            "confidence_sigma": self.confidence_sigma,
            "reassess_s": self.reassess_s,
        }


@dataclass(frozen=True)
class TruthRef:
    """The true class of the drone a track follows; `None` for a false track."""

    class_id: str | None


@dataclass(frozen=True)
class Assessment:
    track_id: str
    tick: int
    threat: bool
    proposed_class: str
    confidence: float
    correct_flag: bool
    true_class: str | None

    def view(self) -> dict[str, Any]:
        """What a trainee may see. No truth beyond the (possibly wrong) proposed class."""
        return {
            "track": self.track_id,
            "tick": self.tick,
            "flag": "threat" if self.threat else "no-threat",
            "proposed_class": self.proposed_class,
            "confidence": self.confidence,
            "source": SOURCE,
            "basis": BASIS,
            "data_status": DATA_STATUS,
        }

    def record(self) -> dict[str, Any]:
        """The instructor log entry: the trainee view plus the ground truth."""
        return {**self.view(), "correct_flag": self.correct_flag, "true_class": self.true_class}


class AiAssist:
    def __init__(self, seed: int, config: AssistConfig | None = None) -> None:
        self.seed = seed
        self.config = config if config is not None else AssistConfig()
        self._interval = max(1, math.floor(self.config.reassess_s * TICK_HZ + 0.5))
        self._seen: dict[str, tuple[int, int]] = {}  # track id -> (assessments so far, last tick)

    def assess(self, view: Mapping[str, Any], truth: TruthRef, tick: int) -> Assessment | None:
        """One assessment of a confirmed track that is due, else `None` (nothing is consumed)."""
        if view.get("status") != "confirmed":
            return None
        track_id = str(view["id"])
        epoch, last_tick = self._seen.get(track_id, (0, tick))
        if epoch > 0 and tick - last_tick < self._interval:
            return None

        cfg = self.config
        really_threat = is_threat(truth.class_id)
        p_flag = cfg.hit_rate if really_threat else cfg.false_alarm_rate
        flag = self._u(track_id, epoch, "flag") < p_flag

        correct = truth.class_id if truth.class_id is not None else _UNKNOWN
        if self._u(track_id, epoch, "class") < cfg.class_accuracy:
            proposed = correct
        else:
            wrong = [label for label in cfg.labels if label != correct]
            index = min(int(self._u(track_id, epoch, "pick") * len(wrong)), len(wrong) - 1)
            proposed = wrong[index]

        total = 0.0
        for i in range(4):
            total += self._u(track_id, epoch, f"conf{i}")
        mean = cfg.confidence_correct_mean if flag == really_threat else cfg.confidence_wrong_mean
        raw = mean + cfg.confidence_sigma * (total - 2.0) * _SQRT12
        confidence = round(min(max(raw, _CONF_MIN), _CONF_MAX), 3)

        self._seen[track_id] = (epoch + 1, tick)
        return Assessment(
            track_id=track_id,
            tick=tick,
            threat=flag,
            proposed_class=proposed,
            confidence=confidence,
            correct_flag=flag == really_threat,
            true_class=truth.class_id,
        )

    def forget(self, track_id: str) -> None:
        """Drop a dropped track's counter, so a reused ID starts again at epoch 0."""
        self._seen.pop(track_id, None)

    def state(self) -> dict[str, Any]:
        return {
            "tracks": {
                track_id: {"epoch": epoch, "last_tick": last_tick}
                for track_id, (epoch, last_tick) in sorted(self._seen.items())
            }
        }

    def restore(self, state: Mapping[str, Any]) -> None:
        try:
            seen = {
                str(track_id): (int(entry["epoch"]), int(entry["last_tick"]))
                for track_id, entry in state["tracks"].items()
            }
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ValueError("snapshot is not an AI assist state") from exc
        if any(epoch < 1 for epoch, _ in seen.values()):
            raise ValueError("snapshot is not an AI assist state: epoch must be at least 1")
        self._seen = seen

    def _u(self, track_id: str, epoch: int, purpose: str) -> float:
        return keyed_uniform(self.seed, track_id, epoch, purpose)
