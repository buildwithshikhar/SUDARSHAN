from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.brand import load_brand

router = APIRouter(prefix="/api/v1")


class VersionInfo(BaseModel):
    productName: str  # noqa: N815 - public JSON keys are camelCase
    descriptor: str
    version: str
    gitSha: str  # noqa: N815
    buildTime: str  # noqa: N815
    env: str


@router.get("/version")
def version(request: Request) -> VersionInfo:
    settings = request.app.state.settings
    brand = load_brand()
    return VersionInfo(
        productName=brand.productName,
        descriptor=brand.descriptor,
        version=settings.app_version,
        gitSha=settings.git_sha,
        buildTime=settings.build_time,
        env=settings.app_env,
    )
