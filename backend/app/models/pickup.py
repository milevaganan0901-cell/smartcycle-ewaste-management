"""Pickup request persistence model and its own lifecycle statuses.

The pickup lifecycle is deliberately separate from the device lifecycle in
`app.models.device`. A pickup describes a collection appointment; it does not
change or replace the device status, which remains an operations concern.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.models.device import Device
    from app.models.user import User


ALLOWED_PICKUP_STATUSES = (
    "Requested",
    "Scheduled",
    "Collected",
    "Cancelled",
)

ALLOWED_PICKUP_TIME_SLOTS = (
    "9:00 AM – 12:00 PM",
    "12:00 PM – 3:00 PM",
    "3:00 PM – 6:00 PM",
)


def utc_now() -> datetime:
    """Return an aware UTC timestamp for model timestamps."""
    return datetime.now(timezone.utc)


class PickupRequest(Base):
    """A collection request raised by a user for one of their own devices."""

    __tablename__ = "pickup_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pickup_address: Mapped[str] = mapped_column(String(255), nullable=False)
    preferred_date: Mapped[Date] = mapped_column(Date, nullable=False)
    preferred_time_slot: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="Requested",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="pickup_requests")
    device: Mapped["Device"] = relationship("Device", back_populates="pickup_requests")
