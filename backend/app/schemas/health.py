"""Health response schema."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response returned by the health endpoints."""

    status: str
    service: str
    version: str
    environment: str
    database: str
