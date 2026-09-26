"""Device persistence model and lifecycle statuses."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.models.pickup import PickupRequest
    from app.models.user import User


ALLOWED_DEVICE_STATUSES = (
    "Submitted",
    "Under Review",
    "Pickup Scheduled",
    "Collected",
    "Inspection",
    "Refurbishment",
    "Recycling",
    "Completed",
)


def utc_now() -> datetime:
    """Return an aware UTC timestamp for model timestamps."""
    return datetime.now(timezone.utc)


class Device(Base):
    """A submitted electronic device and its current lifecycle status."""

    __tablename__ = "devices"
    __table_args__ = (
        CheckConstraint("age >= 0", name="ck_devices_age_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user: Mapped["User | None"] = relationship("User", back_populates="devices")
    tracking_id: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    device_category: Mapped[str] = mapped_column(String(100), nullable=False)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    condition: Mapped[str] = mapped_column(String(50), nullable=False)
    working_status: Mapped[str] = mapped_column(String(50), nullable=False)
    physical_damage: Mapped[str | None] = mapped_column(String(255), nullable=True)
    accessories: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_purchase_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    location: Mapped[str] = mapped_column(String(150), nullable=False)
    estimated_purchase_value: Mapped[float] = mapped_column(Float, nullable=False)
    potential_refurbished_value: Mapped[float] = mapped_column(Float, nullable=False)
    potential_recycled_value: Mapped[float] = mapped_column(Float, nullable=False)
    valuation_method: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="rule_based",
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="Submitted")
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

    pickup_requests: Mapped[list[PickupRequest]] = relationship(
        "PickupRequest",
        back_populates="device",
        # Matches the `ondelete="CASCADE"` declared on PickupRequest.device_id.
        # Without it the ORM tries to null a non-nullable foreign key when a
        # device is deleted, which fails instead of cascading.
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
