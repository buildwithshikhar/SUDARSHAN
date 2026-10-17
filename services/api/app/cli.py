"""Operations CLI: python -m app.cli <command>."""

import secrets
from pathlib import Path

import typer
from alembic.config import Config
from sqlalchemy.orm import Session

from alembic import command
from app.config import Settings
from app.db import make_engine
from app.models import Role
from app.users import UserError, create_admin, upsert_demo_user

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
def migrate() -> None:
    """Apply database migrations."""
    command.upgrade(_alembic_config(Settings()), "head")
    typer.echo("migrations applied")


@cli.command("create-admin")
def create_admin_command(
    email: str | None = typer.Option(None, envvar="FIRST_ADMIN_EMAIL"),
    password: str | None = typer.Option(None, envvar="FIRST_ADMIN_PASSWORD"),
    if_configured: bool = typer.Option(
        False, "--if-configured", help="Do nothing, successfully, when the environment is not set."
    ),
) -> None:
    """Create the first administrator (idempotent)."""
    email = email or None
    password = password or None
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


@cli.command("seed-demo")
def seed_demo() -> None:
    """Create one admin, one instructor and one trainee for a demo. Never in production."""
    settings = Settings()
    if settings.is_production:
        typer.echo("error: seed-demo refuses to run when APP_ENV=production", err=True)
        raise typer.Exit(code=2)
    engine = make_engine(settings.database_url)
    typer.echo("Demo accounts (demo use only; passwords are new on every run):")
    with Session(engine) as session:
        for email, role in DEMO_ACCOUNTS:
            password = secrets.token_urlsafe(12)
            upsert_demo_user(session, email, role, password)
            typer.echo(f"  {role.value:<11} {email:<26} {password}")


if __name__ == "__main__":
    cli()
