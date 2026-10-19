"""Saved scenarios: rows of `scenario_records` (authored in the editor, or generated and kept).

A row holds the `scenario.v1` JSON and the SHA-256 of its canonical form. Reading it back checks the
hash, so a row edited outside the application is refused instead of played.
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.contracts import ScenarioSpec
from app.models import ScenarioRecord
from sim.canonical import canonical_json

log = logging.getLogger("app.scenarios")


def spec_sha256(spec: ScenarioSpec) -> str:
    return hashlib.sha256(canonical_json(spec.model_dump(mode="json"))).hexdigest()


@dataclass(frozen=True, slots=True)
class Saved:
    """A saved scenario as read back: the spec and what was kept beside it."""

    spec: ScenarioSpec
    owner_id: str | None
    origin: str
    yaml: str | None
    request: dict[str, Any] | None
    code: str | None
    checks: list[dict[str, Any]]
    features: dict[str, float] | None
    spec_sha256: str


def _read(row: ScenarioRecord) -> Saved | None:
    try:
        spec = ScenarioSpec.model_validate_json(row.spec)
        if spec_sha256(spec) != row.spec_sha256:
            raise ValueError("the stored hash does not match the spec")
        return Saved(
            spec,
            row.owner_id,
            row.origin,
            row.yaml,
            json.loads(row.request) if row.request else None,
            row.code,
            json.loads(row.checks) if row.checks else [],
            json.loads(row.features) if row.features else None,
            row.spec_sha256,
        )
    except (ValueError, TypeError) as error:
        log.warning("saved scenario %s is unreadable and is skipped: %s", row.id, error)
        return None


class ScenarioStore:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory

    def get(self, scenario_id: str) -> Saved | None:
        with self._factory() as db:
            row = db.get(ScenarioRecord, scenario_id)
            return None if row is None else _read(row)

    def all(self) -> list[Saved]:
        with self._factory() as db:
            rows = db.scalars(select(ScenarioRecord).order_by(ScenarioRecord.id))
            return [saved for row in rows if (saved := _read(row)) is not None]

    def put(
        self,
        spec: ScenarioSpec,
        *,
        owner_id: str | None,
        origin: str,
        yaml: str | None = None,
        request: dict[str, Any] | None = None,
        code: str | None = None,
        checks: list[dict[str, Any]] | None = None,
        features: dict[str, float] | None = None,
    ) -> Saved:
        """Insert, or replace the row of the same id."""
        values = {
            "version": spec.version,
            "owner_id": owner_id,
            "origin": origin,
            "spec": json.dumps(spec.model_dump(mode="json"), sort_keys=True, ensure_ascii=False),
            "spec_sha256": spec_sha256(spec),
            "yaml": yaml,
            "request": None if request is None else json.dumps(request, sort_keys=True),
            "code": code,
            "checks": None if checks is None else json.dumps(checks, sort_keys=True),
            "features": None if features is None else json.dumps(features, sort_keys=True),
        }
        with self._factory() as db:
            row = db.get(ScenarioRecord, spec.id)
            if row is None:
                db.add(ScenarioRecord(id=spec.id, **values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            db.commit()
            row = db.get(ScenarioRecord, spec.id)
            assert row is not None
            saved = _read(row)
            assert saved is not None
            return saved

    def delete(self, scenario_id: str) -> bool:
        with self._factory() as db:
            row = db.get(ScenarioRecord, scenario_id)
            if row is None:
                return False
            db.delete(row)
            db.commit()
            return True
