import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.brand import load_brand
from app.config import Settings
from app.db import make_engine
from app.guard import StartupError, validate_production
from app.routers import health, version

log = logging.getLogger("app")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            validate_production(settings, engine)
        except StartupError as error:
            log.error("%s", error)
            raise
        yield
        engine.dispose()

    app = FastAPI(title=load_brand().productName, version=settings.app_version, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["GET"],
            allow_headers=["*"],
        )
    app.include_router(health.router)
    app.include_router(version.router)
    return app


def get_app() -> FastAPI:
    return create_app()
