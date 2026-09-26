"""Database engine, session factory, and FastAPI dependency."""

from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import DATABASE_URL
from app.db.base import Base


connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        """Make SQLite honour the foreign keys declared on the models.

        SQLite ignores `ForeignKey(..., ondelete=...)` unless this pragma is set
        per connection, so without it the schema's CASCADE and SET NULL rules
        are decorative and orphaned rows are possible.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped database session."""
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


def init_db() -> None:
    """Create tables and apply the lightweight local column migrations."""
    from app.models import DEFAULT_USER_ROLE, Device, PickupRequest, User  # noqa: F401

    # New tables are added by create_all without touching existing ones.
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)

    # Alembic is not present yet. SQLite cannot add a foreign-key constraint to
    # an existing column with ALTER TABLE, so the nullable column and its index
    # are added idempotently. Existing device rows remain untouched.
    device_columns = {column["name"] for column in inspector.get_columns("devices")}
    if "user_id" not in device_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE devices ADD COLUMN user_id INTEGER"))

    with engine.begin() as connection:
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_devices_user_id ON devices (user_id)")
        )

    # Stage 3I: record which method produced each stored valuation. Existing
    # rows were all valued by the rule-based estimator, so they are backfilled
    # to "rule_based" and their stored values are left untouched.
    device_columns = {column["name"] for column in inspector.get_columns("devices")}
    if "valuation_method" not in device_columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE devices ADD COLUMN valuation_method VARCHAR(20)")
            )
            connection.execute(
                text(
                    "UPDATE devices SET valuation_method = 'rule_based' "
                    "WHERE valuation_method IS NULL OR valuation_method = ''"
                )
            )

    # Stage 3G: the admin role is a new column on an existing table, so it is
    # added the same idempotent way. Existing accounts keep working and are
    # backfilled to the default user role rather than admin.
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "role" not in user_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20)"))
            connection.execute(
                text(
                    "UPDATE users SET role = :role WHERE role IS NULL OR role = ''"
                ).bindparams(role=DEFAULT_USER_ROLE)
            )
