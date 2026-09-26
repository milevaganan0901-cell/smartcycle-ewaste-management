"""Pydantic response schemas for the admin workspace.

Every schema here is read-only and deliberately omits `password_hash` and any
other authentication secret, even for admin consumers.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class AdminCountByStatus(BaseModel):
    """A single status bucket with its record count."""

    status: str
    count: int


class AdminRecentDevice(BaseModel):
    """Compact device record for the recent-activity list."""

    id: int
    tracking_id: str
    device_category: str
    brand: str
    model: str
    status: str
    owner_name: str | None = None
    created_at: datetime


class AdminRecentPickup(BaseModel):
    """Compact pickup record for the recent-activity list."""

    id: int
    device_tracking_id: str
    owner_name: str | None = None
    preferred_date: date
    preferred_time_slot: str
    status: str
    created_at: datetime


class AdminDashboardStats(BaseModel):
    """Aggregate platform statistics computed with SQL aggregation."""

    total_users: int
    total_devices: int
    total_pickups: int
    devices_by_status: list[AdminCountByStatus]
    pickups_by_status: list[AdminCountByStatus]
    recent_devices: list[AdminRecentDevice] = Field(default_factory=list)
    recent_pickups: list[AdminRecentPickup] = Field(default_factory=list)


class AdminValuationModelInfo(BaseModel):
    """Read-only description of the ML valuation model for the admin UI."""

    model_available: bool
    model_type: str | None = None
    pipeline: str | None = None
    dataset_kind: str | None = None
    total_rows: int | None = None
    training_rows: int | None = None
    test_rows: int | None = None
    features: list[str] = Field(default_factory=list)
    target: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    # Stage 4B: the evaluation context an admin needs to judge those metrics.
    model_name: str | None = None
    trained_at: str | None = None
    dataset_identifier: str | None = None
    cv_folds: int | None = None
    model_comparison: dict[str, dict[str, float]] = Field(default_factory=dict)
    baselines: dict[str, dict[str, float]] = Field(default_factory=dict)
    model_selection_note: str | None = None
    baseline_note: str | None = None
    metrics_ceiling_note: str | None = None
    training_age_range: str | None = None
    disclaimer: str | None = None
    fallback_method: str = "rule_based"


class AdminUserRow(BaseModel):
    """Safe user listing row. Never includes a password hash."""

    id: int
    name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    device_count: int = 0
    pickup_count: int = 0


class AdminDeviceRow(BaseModel):
    """Device listing row across all users."""

    id: int
    tracking_id: str
    device_category: str
    brand: str
    model: str
    age: int
    condition: str
    working_status: str
    location: str
    estimated_purchase_value: float
    status: str
    user_id: int | None = None
    owner_name: str | None = None
    owner_email: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminPickupRow(BaseModel):
    """Pickup listing row across all users."""

    id: int
    device_id: int
    device_tracking_id: str
    device_label: str
    user_id: int
    owner_name: str | None = None
    owner_email: str | None = None
    pickup_address: str
    preferred_date: date
    preferred_time_slot: str
    status: str
    created_at: datetime
    updated_at: datetime


__all__ = [
    "AdminCountByStatus",
    "AdminDashboardStats",
    "AdminDeviceRow",
    "AdminPickupRow",
    "AdminRecentDevice",
    "AdminRecentPickup",
    "AdminUserRow",
    "AdminValuationModelInfo",
]
