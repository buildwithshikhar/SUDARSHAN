from fastapi import APIRouter, Request, Response, status
from sqlalchemy import text

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness: the process is up. Never touches the database."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz(request: Request, response: Response) -> dict[str, str]:
    """Readiness: the database answers."""
    try:
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable"}
    return {"status": "ready"}
