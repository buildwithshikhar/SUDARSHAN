import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.brand import load_brand
from app.config import Settings
from app.db import make_engine, make_session_factory
from app.guard import StartupError, validate_production
from app.live.catalog import ScenarioCatalog
from app.live.manager import SessionManager
from app.ratelimit import LoginRateLimiter
from app.routers import auth, health, scenarios, sessions, terrain, users, version
from app.scenarios.insights import Insights
from app.scenarios.store import ScenarioStore

log = logging.getLogger("app")


async def _warm(live: SessionManager, insights: Insights) -> None:
    """Check the shipped scenarios with the oracle defender in the background, so the library can
    say which are verified solvable by test run without making a request wait for it."""
    try:
        specs = [e.spec for e in (await asyncio.to_thread(live.catalog.entries)).values()]
        await asyncio.to_thread(insights.warm, specs)
    except Exception:  # noqa: BLE001 - the library only shows "not yet checked"
        log.exception("could not check the shipped scenarios")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = make_engine(settings.database_url)

    session_factory = make_session_factory(engine)
    scenario_store = ScenarioStore(session_factory)
    insights = Insights()
    live = SessionManager(
        session_factory,
        ScenarioCatalog(saved=scenario_store),
        grace_s=settings.session_grace_s,
        max_sessions=settings.max_live_sessions,
        act_rate=settings.live_act_rate,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            validate_production(settings, engine)
        except StartupError as error:
            log.error("%s", error)
            raise
        Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
        try:  # sessions left running by an earlier process can never resume
            await asyncio.to_thread(live.abandon_stale)
        except SQLAlchemyError:
            log.warning("could not mark stale live sessions (is the database migrated?)")
        warm = asyncio.create_task(_warm(live, insights)) if settings.scenario_warmup else None
        yield
        if warm is not None:
            warm.cancel()
        await live.shutdown()
        engine.dispose()

    app = FastAPI(title=load_brand().productName, version=settings.app_version, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.live = live
    app.state.scenario_store = scenario_store
    app.state.insights = insights
    app.state.rate_limiter = LoginRateLimiter(
        settings.login_max_attempts, settings.login_window_seconds
    )
    app.state.evaluation_limiter = LoginRateLimiter(
        settings.evaluation_rate_max, settings.evaluation_rate_window_seconds
    )
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH"],
            allow_headers=["Content-Type", "X-CSRF-Token"],
        )
    app.include_router(health.router)
    app.include_router(version.router)
    app.include_router(auth.router)
    if settings.evaluation_mode:
        app.include_router(auth.evaluation_router())
    app.include_router(users.router)
    app.include_router(sessions.router)
    app.include_router(scenarios.router)
    app.include_router(terrain.router)
    return app


def get_app() -> FastAPI:
    return create_app()
