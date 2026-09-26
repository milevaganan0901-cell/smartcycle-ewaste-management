"""System health route."""

from fastapi import APIRouter

from app.schemas.health import HealthResponse


router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Confirm that the API process is running."""
    return HealthResponse(
        status="ok",
        service="SmartCycle API",
        stage="stage-3g",
    )
