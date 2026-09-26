"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import admin, auth, devices, health, pickup, users
from app.core.config import (
    CORS_ALLOW_CREDENTIALS,
    CORS_ALLOW_HEADERS,
    CORS_ALLOW_METHODS,
    CORS_ORIGINS,
    JWT_SECRET_KEY,
)
from app.db.session import init_db


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize the local database before serving requests."""
    init_db()
    if not JWT_SECRET_KEY:
        # Not fatal: the API still starts so the rest of the system can be
        # inspected, but no token can be issued or accepted until this is set.
        logger.warning(
            "JWT_SECRET_KEY is not set. The API will start, but every "
            "authentication attempt will fail with 503 until it is configured. "
            "Set it in backend/.env or the process environment."
        )
    yield


app = FastAPI(
    title="SmartCycle API",
    description=(
        "REST API for the SmartCycle e-waste management platform.\n\n"
        "**Authentication** - call `POST /api/auth/login` to obtain a bearer "
        "token, then use the **Authorize** button above to attach it. Every "
        "endpoint marked as requiring authentication rejects anonymous "
        "callers with `401`.\n\n"
        "**Authorization** - endpoints under `/api/admin` additionally require "
        "the `admin` role and return `403` for a signed-in non-admin. A user "
        "can only ever read or modify their own devices and pickup requests; "
        "another user's records return `404` rather than `403`, so ownership is "
        "not confirmed to a stranger.\n\n"
        "**Valuation** - device valuations come from a trained scikit-learn "
        "model when one is present and from a transparent rule-based estimator "
        "otherwise. The method actually used is reported per device as "
        "`valuation_method` (`ml` or `rule_based`). Values are estimates, not "
        "offers."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# An explicit origin list, never a wildcard: the app sends credentials, and a
# wildcard plus credentials is rejected by browsers and unsafe regardless.
# Local development origins are built into the configuration, so this works on
# a fresh clone; a deployment adds its own frontend origin via
# CORS_ORIGIN_PRODUCTION.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=CORS_ALLOW_METHODS,
    allow_headers=CORS_ALLOW_HEADERS,
)

app.include_router(health.router)
app.include_router(health.router, prefix="/api/v1")
app.include_router(devices.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(pickup.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/", tags=["system"], summary="Service identification")
def root() -> dict[str, str]:
    """Return a small service identification response."""
    return {
        "service": "SmartCycle API",
        "version": app.version,
        "docs": "/docs",
        "status": "running",
    }
