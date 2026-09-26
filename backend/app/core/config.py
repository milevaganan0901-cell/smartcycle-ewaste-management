"""Application configuration for the local backend.

Every tunable is read from the environment. A `.env` file in `backend/` is
loaded automatically so that the documented local workflow is only:

    cp .env.example .env      # then fill in the values
    uvicorn app.main:app

Real environment variables always take precedence over `.env`, so a process
manager or container can override anything without editing a file.

No secret is defined here. `JWT_SECRET_KEY` has no default and no fallback: the
application starts without it (so the rest of the system is inspectable) but
refuses to issue or accept tokens, and logs a warning at startup.
"""

import logging
import os
from pathlib import Path


logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _load_env_file() -> Path | None:
    """Load `backend/.env` if present, without overriding the real environment.

    The file's location can be pointed elsewhere with `SMARTCYCLE_ENV_FILE`,
    which is useful when several deployments share one checkout.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dotenv is a declared dependency
        return None

    env_path = Path(os.getenv("SMARTCYCLE_ENV_FILE", BACKEND_ROOT / ".env"))
    if not env_path.is_absolute():
        env_path = BACKEND_ROOT / env_path
    if not env_path.is_file():
        return None

    load_dotenv(env_path, override=False)
    return env_path


ENV_FILE = _load_env_file()


def _resolve_path(raw: str, base: Path) -> Path:
    """Resolve a configured path against `base` when it is relative.

    Paths are anchored to the backend directory rather than the process working
    directory, so the app behaves the same however it is launched.
    """
    candidate = Path(raw).expanduser()
    return candidate if candidate.is_absolute() else (base / candidate)


def _sqlite_url(raw_url: str) -> str:
    """Anchor a relative SQLite URL to the backend directory.

    SQLite resolves `sqlite:///relative.db` against the process working
    directory, which silently points at a different file depending on where the
    server was started. An absolute 4-slash URL and `:memory:` are left alone.
    """
    prefix = "sqlite:///"
    if not raw_url.startswith(prefix):
        return raw_url

    path_part = raw_url[len(prefix) :]
    if not path_part or path_part == ":memory:" or path_part.startswith("/"):
        return raw_url
    return f"{prefix}{BACKEND_ROOT / path_part}"


# --- Database --------------------------------------------------------------
# Two ways to point at the database:
#   DATABASE_PATH  - just the SQLite file. Preferred, unambiguous.
#   DATABASE_URL   - a full SQLAlchemy URL, for an absolute path or a future
#                    non-SQLite backend.
DATABASE_PATH = _resolve_path(
    os.getenv("DATABASE_PATH", "smartcycle.db"),
    BACKEND_ROOT,
)
DATABASE_URL = _sqlite_url(os.getenv("DATABASE_URL", "")) or f"sqlite:///{DATABASE_PATH}"

# --- CORS ------------------------------------------------------------------
# Local development origins are built in and always kept, so a fresh clone
# works with no CORS configuration and a production-only setting can never
# break local development. A deployment adds its own frontend origin with
# CORS_ORIGIN_PRODUCTION. The list is always explicit: a wildcard is unsafe
# alongside allow_credentials=True and is discarded rather than forwarded.
CORS_DEV_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
CORS_ORIGIN_PRODUCTION = os.getenv("CORS_ORIGIN_PRODUCTION", "").strip()


def _split_origins(*raw_values: str) -> list[str]:
    """Split comma-separated origin lists, dropping blanks and duplicates.

    A wildcard is discarded rather than forwarded. The API sends credentials,
    so `allow_origins=["*"]` is rejected by browsers and unsafe regardless; the
    operator gets a warning instead of a confusing CORS failure at runtime.
    """
    origins: list[str] = []
    for raw in raw_values:
        for origin in raw.split(","):
            cleaned = origin.strip().rstrip("/")
            if not cleaned:
                continue
            if cleaned == "*":
                logger.warning(
                    "CORS: ignoring the wildcard origin '*'. The API uses "
                    "credentials, so list the exact frontend origin(s) instead."
                )
                continue
            if cleaned not in origins:
                origins.append(cleaned)
    return origins


def _resolve_origins() -> list[str]:
    """Build the origin allowlist.

    Rules, in order:
      1. `CORS_ORIGINS`, if set to something meaningful, is the complete list.
      2. Otherwise the local development origins are always included, so local
         development can never be broken by a production-only setting.
      3. `CORS_ORIGIN_PRODUCTION` is added on top in every case, which is how a
         deployment opts in to its own frontend origin without having to
         remember to re-list the development ones.
    """
    explicit = _split_origins(os.getenv("CORS_ORIGINS", ""))
    if explicit:
        return _split_origins(*explicit, CORS_ORIGIN_PRODUCTION)

    return _split_origins(CORS_DEV_ORIGINS, CORS_ORIGIN_PRODUCTION)


CORS_ORIGINS = _resolve_origins()
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = ["Authorization", "Content-Type", "Accept"]

# --- Authentication --------------------------------------------------------
# No default, on purpose. A guessable signing key would let anyone mint tokens.
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"


def _positive_int(name: str, default: int) -> int:
    """Read a positive integer setting, falling back on nonsense values."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


ACCESS_TOKEN_EXPIRE_MINUTES = _positive_int("ACCESS_TOKEN_EXPIRE_MINUTES", 480)

# --- ML valuation artifacts ------------------------------------------------
# The trained pipeline is a file on disk, never stored in SQLite, and is loaded
# lazily on first use. Relative overrides are anchored to the backend directory.
DATA_DIR = _resolve_path(os.getenv("SMARTCYCLE_DATA_DIR", "data"), BACKEND_ROOT)
VALUATION_MODEL_PATH = _resolve_path(
    os.getenv("VALUATION_MODEL_PATH", str(DATA_DIR / "valuation_model.joblib")),
    BACKEND_ROOT,
)
VALUATION_MODEL_METRICS_PATH = _resolve_path(
    os.getenv("VALUATION_MODEL_METRICS_PATH", str(DATA_DIR / "valuation_model_metrics.json")),
    BACKEND_ROOT,
)
VALUATION_DATASET_PATH = _resolve_path(
    os.getenv("VALUATION_DATASET_PATH", str(DATA_DIR / "valuation_demo_dataset.csv")),
    BACKEND_ROOT,
)

# Never train on request or at startup. The model is produced by the manual
# script `python -m app.scripts.train_valuation_model`.
TRAIN_MODEL_ON_STARTUP = False
