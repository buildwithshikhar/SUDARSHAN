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
from app.routers import auth, health, sessions, users, version

log = logging.getLogger("app")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = make_engine(settings.database_url)

    session_factory = make_session_factory(engine)
    live = SessionManager(
        session_factory,
        ScenarioCatalog(),
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
        yield
        await live.shutdown()
        engine.dispose()

    app = FastAPI(title=load_brand().productName, version=settings.app_version, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.live = live
    app.state.rate_limiter = LoginRateLimiter(
        settings.login_max_attempts, settings.login_window_seconds
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
    app.include_router(users.router)
    app.include_router(sessions.router)
    return app


def get_app() -> FastAPI:
    return create_app()
