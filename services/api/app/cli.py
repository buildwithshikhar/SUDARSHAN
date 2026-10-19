"""Operations CLI: python -m app.cli <command>."""

import os
import secrets
from pathlib import Path

import typer
from alembic.config import Config
from sqlalchemy.orm import Session

from alembic import command
from app.config import Settings
from app.db import make_engine
from app.guard import StartupError, validate_production
from app.models import Role
from app.passwords import WeakPasswordError, check_password
from app.users import UserError, create_admin, create_user, upsert_demo_user

cli = typer.Typer(add_completion=False, no_args_is_help=True)

DEMO_ACCOUNTS: tuple[tuple[str, Role], ...] = (
    ("admin@demo.invalid", Role.admin),
    ("instructor@demo.invalid", Role.instructor),
    ("trainee@demo.invalid", Role.trainee),
)


def _alembic_config(settings: Settings) -> Config:
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    return config


@cli.command()
def check() -> None:
    """Run the production start-up guard without starting the server."""
    settings = Settings()
    try:
        validate_production(settings, make_engine(settings.database_url))
    except StartupError as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(code=3) from error
    typer.echo(f"start-up checks passed ({settings.app_env})")


@cli.command("sim-check")
def sim_check() -> None:
    """Load an example scenario and run a few ticks with a sensor picture (image check, Q-19)."""
    from app.simcheck import run_sim_check

    try:
        typer.echo(run_sim_check())
    except Exception as error:  # noqa: BLE001 - any failure means the image is not usable
        typer.echo(f"error: sim-check failed: {error!r}", err=True)
        raise typer.Exit(code=4) from error


@cli.command("pack-lock")
def pack_lock(
    check: bool = typer.Option(False, "--check", help="Only report; change nothing."),
) -> None:
    """Record each sensor profile, threat class and rule pack content hash beside its version.

    A pack whose content changed must carry a higher version first; the command refuses to lock
    new content under the old one.
    """
    from sim.provenance import lock_problems, refresh_lock

    if check:
        problems = lock_problems()
        for line in problems:
            typer.echo(f"error: {line}", err=True)
        raise typer.Exit(code=1 if problems else 0)
    try:
        changes = refresh_lock()
    except ValueError as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo("\n".join(changes) if changes else "packs/versions.lock.json is up to date")


@cli.command("scenario-sweep")
def scenario_sweep(
    count: int = typer.Option(50, min=1, help="How many requests to generate and check."),
    start: int = typer.Option(0, min=0, help="Index of the first request of the sweep."),
    jobs: int = typer.Option(1, min=1, max=16, help="Processes to use."),
) -> None:
    """Generate scenarios for a sweep of requests and check each with a fresh oracle run.

    Exits 1 if any request fails to produce a scenario verified solvable by test run. The push
    check runs 50 of these; the nightly job runs 1,000.
    """
    from app.scenarios.sweep import run_sweep

    results = run_sweep(count, start, jobs)
    failed = [r for r in results if not r.ok]
    for r in failed:
        typer.echo(f"request {r.index}: {r.detail}", err=True)
    eased = sum(1 for r in results if r.relaxations)
    typer.echo(
        f"{len(results) - len(failed)} of {len(results)} verified solvable by test run; "
        f"{eased} needed a relaxation"
    )
    if failed:
        raise typer.Exit(code=1)


@cli.command()
def migrate() -> None:
    """Apply database migrations."""
    command.upgrade(_alembic_config(Settings()), "head")
    typer.echo("migrations applied")


@cli.command("create-admin")
def create_admin_command(
    email: str | None = typer.Option(None, envvar="FIRST_ADMIN_EMAIL"),
    if_configured: bool = typer.Option(
        False, "--if-configured", help="Do nothing, successfully, when the environment is not set."
    ),
) -> None:
    """Create the first administrator (idempotent).

    The password is never a command-line argument (it would show in the process list and shell
    history): it comes from FIRST_ADMIN_PASSWORD, or from a hidden prompt.
    """
    email = email or None
    password = os.environ.get("FIRST_ADMIN_PASSWORD") or None
    if if_configured and (email is None or password is None):
        typer.echo("first admin not configured; skipping")
        return
    if email is None:
        email = typer.prompt("Admin email")
    if password is None:
        password = typer.prompt("Admin password", hide_input=True, confirmation_prompt=True)
    engine = make_engine(Settings().database_url)
    try:
        with Session(engine, expire_on_commit=False) as session:
            result = create_admin(session, email, password)
    except UserError as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"admin {'created' if result.created else 'exists'}: {result.user.email}")


@cli.command("create-user")
def create_user_command(
    email: str = typer.Option(..., help="Account email address"),
    role: Role = typer.Option(..., help="trainee, instructor or admin"),
) -> None:
    """Create an account (idempotent).

    The password is never a command-line argument: it comes from NEW_USER_PASSWORD or from a
    hidden prompt.
    """
    password = os.environ.get("NEW_USER_PASSWORD") or None
    if password is None:
        password = typer.prompt("Password", hide_input=True, confirmation_prompt=True)
    engine = make_engine(Settings().database_url)
    try:
        with Session(engine, expire_on_commit=False) as session:
            result = create_user(session, email, password, role)
    except UserError as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(
        f"user {'created' if result.created else 'exists'}: {result.user.email} ({role.value})"
    )


@cli.command("seed-demo")
def seed_demo() -> None:
    """Create one admin, one instructor and one trainee for a demo. Never in production."""
    settings = Settings()
    if settings.is_production:
        typer.echo("error: seed-demo refuses to run when APP_ENV=production", err=True)
        raise typer.Exit(code=2)
    fixed = os.environ.get("DEMO_PASSWORD") or None
    if fixed is not None:
        try:
            check_password(fixed)
        except WeakPasswordError as error:
            typer.echo(f"error: DEMO_PASSWORD rejected: {error}", err=True)
            raise typer.Exit(code=1) from error
    engine = make_engine(settings.database_url)
    typer.echo(
        "Demo accounts (demo use only; passwords are new on every run unless DEMO_PASSWORD is set):"
    )
    with Session(engine) as session:
        for email, role in DEMO_ACCOUNTS:
            password = fixed or secrets.token_urlsafe(12)
            upsert_demo_user(session, email, role, password)
            typer.echo(f"  {role.value:<11} {email:<26} {password}")


if __name__ == "__main__":
    cli()
