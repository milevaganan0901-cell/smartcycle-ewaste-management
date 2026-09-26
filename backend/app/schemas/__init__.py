"""Pydantic request and response schemas."""

from app.schemas.admin import (
    AdminCountByStatus,
    AdminDashboardStats,
    AdminDeviceRow,
    AdminPickupRow,
    AdminRecentDevice,
    AdminRecentPickup,
    AdminUserRow,
)
from app.schemas.device import DeviceCreate, DeviceResponse, DeviceStatusUpdate
from app.schemas.pickup import PickupCreate, PickupResponse
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse

__all__ = [
    "AdminCountByStatus",
    "AdminDashboardStats",
    "AdminDeviceRow",
    "AdminPickupRow",
    "AdminRecentDevice",
    "AdminRecentPickup",
    "AdminUserRow",
    "DeviceCreate",
    "DeviceResponse",
    "DeviceStatusUpdate",
    "PickupCreate",
    "PickupResponse",
    "Token",
    "UserCreate",
    "UserLogin",
    "UserResponse",
]
