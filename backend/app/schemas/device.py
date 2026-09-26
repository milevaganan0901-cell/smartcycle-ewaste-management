"""Pydantic request and response schemas for device management."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.device import ALLOWED_DEVICE_STATUSES


DeviceStatus = Literal[
    "Submitted",
    "Under Review",
    "Pickup Scheduled",
    "Collected",
    "Inspection",
    "Refurbishment",
    "Recycling",
    "Completed",
]


class DeviceCreate(BaseModel):
    """User-provided device details accepted by the create endpoint."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    device_category: str = Field(min_length=1, max_length=100)
    brand: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=120)
    age: int = Field(ge=0)
    condition: str = Field(min_length=1, max_length=50)
    working_status: str = Field(min_length=1, max_length=50)
    physical_damage: str | None = Field(default="None", max_length=255)
    accessories: str | None = Field(default=None, max_length=500)
    original_purchase_price: float | None = Field(default=None, ge=0)
    location: str = Field(min_length=1, max_length=150)

    @field_validator("physical_damage", "accessories", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        """Convert blank optional text values to null."""
        if isinstance(value, str):
            return value.strip() or None
        return value


class DeviceResponse(BaseModel):
    """Complete device representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tracking_id: str
    device_category: str
    brand: str
    model: str
    age: int
    condition: str
    working_status: str
    physical_damage: str | None
    accessories: str | None
    original_purchase_price: float | None
    location: str
    estimated_purchase_value: float
    potential_refurbished_value: float
    potential_recycled_value: float
    valuation_method: str
    status: str
    created_at: datetime
    updated_at: datetime


class DeviceStatusUpdate(BaseModel):
    """Restricted status update payload."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    status: DeviceStatus

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: object) -> object:
        """Normalize surrounding whitespace before literal validation."""
        return value.strip() if isinstance(value, str) else value


__all__ = ["ALLOWED_DEVICE_STATUSES", "DeviceCreate", "DeviceResponse", "DeviceStatusUpdate", "DeviceStatus"]
