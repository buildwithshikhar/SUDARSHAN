"""Production start-up guard. Production must never run on a default key or with demo accounts."""

from sqlalchemy import Engine, inspect, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import User


class StartupError(RuntimeError):
    """Raised to stop the process with a clear message."""


def validate_production(settings: Settings, engine: Engine) -> None:
    if not settings.is_production:
        return
    problem = settings.secret_problem()
    if problem is not None:
        raise StartupError(f"Refusing to start in production: {problem}.")
    # Evaluation mode keeps the seeded seats on purpose; password sign-in to them stays refused.
    if not settings.evaluation_mode and inspect(engine).has_table(User.__tablename__):
        with Session(engine) as session:
            demo = session.scalar(select(User.email).where(User.is_demo.is_(True)).limit(1))
        if demo is not None:
            raise StartupError(
                "Refusing to start in production: demo accounts exist in the database. "
                "Use a clean database and create the administrator with `create-admin`."
            )
