"""Pydantic request and response schemas for pickup requests."""

from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.pickup import ALLOWED_PICKUP_STATUSES, ALLOWED_PICKUP_TIME_SLOTS


PickupTimeSlot = Literal[
    "9:00 AM – 12:00 PM",
    "12:00 PM – 3:00 PM",
    "3:00 PM – 6:00 PM",
]

PickupStatus = Literal[
    "Requested",
    "Scheduled",
    "Collected",
    "Cancelled",
]

MAX_PICKUP_WINDOW_DAYS = 365


class PickupCreate(BaseModel):
    """Pickup details supplied when a user requests collection."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    device_id: int = Field(ge=1)
    pickup_address: str = Field(min_length=5, max_length=255)
    preferred_date: date
    preferred_time_slot: PickupTimeSlot

    @field_validator("preferred_date")
    @classmethod
    def validate_preferred_date(cls, value: date) -> date:
        """Reject past dates and dates beyond the booking window."""
        today = date.today()
        if value < today:
            raise ValueError("Choose a pickup date that is today or later.")
        if value > today + timedelta(days=MAX_PICKUP_WINDOW_DAYS):
            raise ValueError("Choose a pickup date within the next 12 months.")
        return value

    @field_validator("preferred_time_slot", mode="before")
    @classmethod
    def normalize_time_slot(cls, value: object) -> object:
        """Trim whitespace before literal validation."""
        return value.strip() if isinstance(value, str) else value


class PickupStatusUpdate(BaseModel):
    """Restricted pickup status update payload.

    Reuses the same `Literal` validation style as `DeviceStatusUpdate`, so an
    unknown, empty or malformed status is rejected before it can reach the
    database.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    status: PickupStatus

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: object) -> object:
        """Normalize surrounding whitespace before literal validation."""
        return value.strip() if isinstance(value, str) else value


class PickupResponse(BaseModel):
    """Complete pickup representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    pickup_address: str
    preferred_date: date
    preferred_time_slot: PickupTimeSlot
    status: str
    created_at: datetime
    updated_at: datetime


__all__ = [
    "ALLOWED_PICKUP_STATUSES",
    "ALLOWED_PICKUP_TIME_SLOTS",
    "MAX_PICKUP_WINDOW_DAYS",
    "PickupCreate",
    "PickupResponse",
    "PickupStatus",
    "PickupStatusUpdate",
    "PickupTimeSlot",
]
