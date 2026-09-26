"""System health route."""

from fastapi import APIRouter

from app.schemas.health import HealthResponse


router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Health Check")
def health_check() -> HealthResponse:
    """Confirm that the API process is running.

    `version` tracks `app.version` so a deployed instance can be identified
    without guessing. The previous hard-coded `stage` field reported
    "stage-3g" from Stage 3G onwards and is replaced rather than kept, because
    a stale stage label in a health check is worse than no label at all.
    """
    from app.main import app

    return HealthResponse(
        status="ok",
        service="SmartCycle API",
        version=app.version,
    )
