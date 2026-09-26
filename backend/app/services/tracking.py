"""Server-side tracking ID generation."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device


def generate_tracking_id(database: Session, current_time: datetime | None = None) -> str:
    """Return the next sequential ``EW-YYYY-NNNN`` ID for the current year.

    The lookup only considers IDs in the current year, so the first device
    created in a new year naturally starts at ``0001``.
    """
    timestamp = current_time or datetime.now(timezone.utc)
    prefix = f"EW-{timestamp.year}-"
    last_id = database.execute(
        select(Device.tracking_id)
        .where(Device.tracking_id.like(f"{prefix}%"))
        .order_by(Device.tracking_id.desc())
        .limit(1)
    ).scalar_one_or_none()

    next_number = 1
    if last_id:
        suffix = last_id.rsplit("-", 1)[-1]
        if suffix.isdigit():
            next_number = int(suffix) + 1

    if next_number > 9999:
        raise ValueError(f"Tracking ID capacity reached for {timestamp.year}.")

    return f"{prefix}{next_number:04d}"
