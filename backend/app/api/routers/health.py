"""System health route."""

from fastapi import APIRouter

from app.core.config import ENVIRONMENT, IS_SQLITE
from app.schemas.health import HealthResponse


router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Health Check")
def health_check() -> HealthResponse:
    """Confirm that the API process is running.

    Reports the version, the environment name, and which database engine is
    configured. This is deliberately non-sensitive: it names the engine, never
    a host, database name, username or password, so it is safe to expose on a
    public deployment and useful for confirming which build is live.
    """
    from app.main import app

    return HealthResponse(
        status="ok",
        service="SmartCycle API",
        version=app.version,
        environment=ENVIRONMENT,
        database="sqlite" if IS_SQLITE else "postgresql",
    )
