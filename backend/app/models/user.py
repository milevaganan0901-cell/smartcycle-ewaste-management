"""User account model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.models.device import Device
    from app.models.pickup import PickupRequest


DEFAULT_USER_ROLE = "user"
ADMIN_ROLE = "admin"
ALLOWED_USER_ROLES = (DEFAULT_USER_ROLE, ADMIN_ROLE)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """A SmartCycle user account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=DEFAULT_USER_ROLE,
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
    devices: Mapped[list[Device]] = relationship(
        "Device",
        back_populates="user",
    )
    pickup_requests: Mapped[list[PickupRequest]] = relationship(
        "PickupRequest",
        back_populates="user",
    )

    @property
    def is_admin(self) -> bool:
        """Return whether this account holds the admin role."""
        return self.role == ADMIN_ROLE
