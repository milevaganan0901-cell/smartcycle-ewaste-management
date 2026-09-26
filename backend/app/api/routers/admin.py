"""Administrative routes.

Every route depends on `get_current_admin`, so access is enforced by the backend
regardless of what the frontend does.

The two PATCH routes change **only** `status` (and the automatic `updated_at`).
They never touch `user_id`, ownership, valuation or any other field, and there
is no route to approve a pickup, assign an agent, or edit a device.

Totals and status breakdowns use SQL `count()` / `group by` aggregation rather
than loading rows into Python.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models.device import ALLOWED_DEVICE_STATUSES, Device
from app.models.pickup import ALLOWED_PICKUP_STATUSES, PickupRequest
from app.models.user import User
from app.schemas.admin import (
    AdminCountByStatus,
    AdminDashboardStats,
    AdminDeviceRow,
    AdminPickupRow,
    AdminRecentDevice,
    AdminRecentPickup,
    AdminUserRow,
    AdminValuationModelInfo,
)
from app.schemas.device import DeviceResponse, DeviceStatusUpdate
from app.schemas.pickup import PickupResponse, PickupStatusUpdate


router = APIRouter(prefix="/admin", tags=["admin"])

RECENT_ACTIVITY_LIMIT = 5


def _database_error(message: str, error: Exception) -> HTTPException:
    """Convert a database failure into a safe 500 response."""
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=message,
    )


def _counts_by_status(
    database: Session,
    model,
    allowed_statuses: tuple[str, ...],
) -> list[AdminCountByStatus]:
    """Return one count per allowed status, computed with a GROUP BY query."""
    rows = database.execute(
        select(model.status, func.count(model.id))
        .group_by(model.status)
    ).all()
    found = {status_name: count for status_name, count in rows}

    # Report every known status, including zero-count ones, so the UI can use
    # the model's exact status values.
    return [
        AdminCountByStatus(status=status_name, count=found.get(status_name, 0))
        for status_name in allowed_statuses
    ]


@router.get(
    "/dashboard",
    response_model=AdminDashboardStats,
    summary="Get aggregated platform statistics",
)
def get_admin_dashboard(
    _: User = Depends(get_current_admin),
    database: Session = Depends(get_db),
) -> AdminDashboardStats:
    """Return real counts, status breakdowns and recent activity."""
    try:
        total_users = database.execute(select(func.count(User.id))).scalar_one()
        total_devices = database.execute(select(func.count(Device.id))).scalar_one()
        total_pickups = database.execute(select(func.count(PickupRequest.id))).scalar_one()

        recent_devices = [
            AdminRecentDevice(
                id=device.id,
                tracking_id=device.tracking_id,
                device_category=device.device_category,
                brand=device.brand,
                model=device.model,
                status=device.status,
                owner_name=owner_name,
                created_at=device.created_at,
            )
            for device, owner_name in database.execute(
                select(Device, User.name)
                .outerjoin(User, User.id == Device.user_id)
                .order_by(Device.id.desc())
                .limit(RECENT_ACTIVITY_LIMIT)
            ).all()
        ]

        recent_pickups = [
            AdminRecentPickup(
                id=pickup.id,
                device_tracking_id=tracking_id,
                owner_name=owner_name,
                preferred_date=pickup.preferred_date,
                preferred_time_slot=pickup.preferred_time_slot,
                status=pickup.status,
                created_at=pickup.created_at,
            )
            for pickup, tracking_id, owner_name in database.execute(
                select(PickupRequest, Device.tracking_id, User.name)
                .join(Device, Device.id == PickupRequest.device_id)
                .join(User, User.id == PickupRequest.user_id)
                .order_by(PickupRequest.id.desc())
                .limit(RECENT_ACTIVITY_LIMIT)
            ).all()
        ]

        return AdminDashboardStats(
            total_users=total_users,
            total_devices=total_devices,
            total_pickups=total_pickups,
            devices_by_status=_counts_by_status(database, Device, ALLOWED_DEVICE_STATUSES),
            pickups_by_status=_counts_by_status(database, PickupRequest, ALLOWED_PICKUP_STATUSES),
            recent_devices=recent_devices,
            recent_pickups=recent_pickups,
        )
    except SQLAlchemyError as error:
        raise _database_error(
            "The admin statistics could not be loaded due to a database error.",
            error,
        ) from error


@router.get(
    "/users",
    response_model=list[AdminUserRow],
    summary="List all users",
)
def list_admin_users(
    _: User = Depends(get_current_admin),
    database: Session = Depends(get_db),
) -> list[AdminUserRow]:
    """Return every account with its role and record counts.

    `password_hash` is never selected, so it cannot reach the response.
    """
    device_counts = (
        select(Device.user_id, func.count(Device.id).label("device_count"))
        .group_by(Device.user_id)
        .subquery()
    )
    pickup_counts = (
        select(PickupRequest.user_id, func.count(PickupRequest.id).label("pickup_count"))
        .group_by(PickupRequest.user_id)
        .subquery()
    )

    try:
        rows = database.execute(
            select(
                User.id,
                User.name,
                User.email,
                User.role,
                User.is_active,
                User.created_at,
                func.coalesce(device_counts.c.device_count, 0),
                func.coalesce(pickup_counts.c.pickup_count, 0),
            )
            .outerjoin(device_counts, device_counts.c.user_id == User.id)
            .outerjoin(pickup_counts, pickup_counts.c.user_id == User.id)
            .order_by(User.id.desc())
        ).all()
    except SQLAlchemyError as error:
        raise _database_error(
            "The user list could not be loaded due to a database error.",
            error,
        ) from error

    return [
        AdminUserRow(
            id=row[0],
            name=row[1],
            email=row[2],
            role=row[3],
            is_active=row[4],
            created_at=row[5],
            device_count=row[6],
            pickup_count=row[7],
        )
        for row in rows
    ]


@router.get(
    "/devices",
    response_model=list[AdminDeviceRow],
    summary="List devices across all users",
)
def list_admin_devices(
    _: User = Depends(get_current_admin),
    database: Session = Depends(get_db),
) -> list[AdminDeviceRow]:
    """Return every device submission with its owner, newest first."""
    try:
        rows = database.execute(
            select(
                Device,
                User.name,
                User.email,
            )
            .outerjoin(User, User.id == Device.user_id)
            .order_by(Device.id.desc())
        ).all()
    except SQLAlchemyError as error:
        raise _database_error(
            "The device list could not be loaded due to a database error.",
            error,
        ) from error

    return [
        AdminDeviceRow(
            id=device.id,
            tracking_id=device.tracking_id,
            device_category=device.device_category,
            brand=device.brand,
            model=device.model,
            age=device.age,
            condition=device.condition,
            working_status=device.working_status,
            location=device.location,
            estimated_purchase_value=device.estimated_purchase_value,
            status=device.status,
            user_id=device.user_id,
            owner_name=owner_name,
            owner_email=owner_email,
            created_at=device.created_at,
            updated_at=device.updated_at,
        )
        for device, owner_name, owner_email in rows
    ]


@router.get(
    "/pickups",
    response_model=list[AdminPickupRow],
    summary="List pickup requests across all users",
)
def list_admin_pickups(
    _: User = Depends(get_current_admin),
    database: Session = Depends(get_db),
) -> list[AdminPickupRow]:
    """Return every pickup request with its owner and device, newest first."""
    try:
        rows = database.execute(
            select(PickupRequest, Device, User)
            .join(Device, Device.id == PickupRequest.device_id)
            .join(User, User.id == PickupRequest.user_id)
            .order_by(PickupRequest.id.desc())
        ).all()
    except SQLAlchemyError as error:
        raise _database_error(
            "The pickup list could not be loaded due to a database error.",
            error,
        ) from error

    return [
        AdminPickupRow(
            id=pickup.id,
            device_id=pickup.device_id,
            device_tracking_id=device.tracking_id,
            device_label=f"{device.brand} {device.model}",
            user_id=user.id,
            owner_name=user.name,
            owner_email=user.email,
            pickup_address=pickup.pickup_address,
            preferred_date=pickup.preferred_date,
            preferred_time_slot=pickup.preferred_time_slot,
            status=pickup.status,
            created_at=pickup.created_at,
            updated_at=pickup.updated_at,
        )
        for pickup, device, user in rows
    ]


@router.patch(
    "/devices/{device_id}/status",
    response_model=DeviceResponse,
    summary="Update a device status (admin only)",
)
def update_admin_device_status(
    device_id: int,
    payload: DeviceStatusUpdate,
    _: User = Depends(get_current_admin),
    database: Session = Depends(get_db),
) -> Device:
    """Set a device's lifecycle status.

    `DeviceStatusUpdate` validates the value against the existing
    `ALLOWED_DEVICE_STATUSES` literal, so an unknown, empty or malformed status
    is rejected with 422 before anything is written. Only `status` and the
    automatic `updated_at` are modified; the owner, valuation and all other
    fields are left untouched.
    """
    device = database.get(Device, device_id)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No device matching that ID was found.",
        )

    device.status = payload.status
    device.updated_at = datetime.now(timezone.utc)
    try:
        database.commit()
        database.refresh(device)
    except SQLAlchemyError as error:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The device status could not be updated due to a database error.",
        ) from error
    return device


@router.patch(
    "/pickups/{pickup_id}/status",
    response_model=PickupResponse,
    summary="Update a pickup request status (admin only)",
)
def update_admin_pickup_status(
    pickup_id: int,
    payload: PickupStatusUpdate,
    _: User = Depends(get_current_admin),
    database: Session = Depends(get_db),
) -> PickupRequest:
    """Set a pickup request's status.

    `PickupStatusUpdate` validates the value against the existing
    `ALLOWED_PICKUP_STATUSES` literal, so an unknown, empty or malformed status
    is rejected with 422. Only `status` and the automatic `updated_at` are
    modified; the owner, device link, address and slot are left untouched.
    """
    pickup = database.get(PickupRequest, pickup_id)
    if pickup is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pickup request matching that ID was found.",
        )

    pickup.status = payload.status
    pickup.updated_at = datetime.now(timezone.utc)
    try:
        database.commit()
        database.refresh(pickup)
    except SQLAlchemyError as error:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The pickup status could not be updated due to a database error.",
        ) from error
    return pickup


@router.get(
    "/valuation-model",
    response_model=AdminValuationModelInfo,
    summary="Get ML valuation model status and evaluation metrics (admin only)",
)
def get_valuation_model_info(
    _: User = Depends(get_current_admin),
) -> AdminValuationModelInfo:
    """Report whether the ML model is loaded, plus its training metrics.

    The metrics come from the training run's sidecar file and describe the
    synthetic demonstration dataset only. They are never exposed to normal
    users, because this route is admin-only.
    """
    import json

    from app.core.config import VALUATION_MODEL_METRICS_PATH
    from app.services.ml_valuation import is_model_available

    available = is_model_available()

    metrics_payload: dict = {}
    try:
        if VALUATION_MODEL_METRICS_PATH.exists():
            metrics_payload = json.loads(
                VALUATION_MODEL_METRICS_PATH.read_text(encoding="utf-8")
            )
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The model metrics could not be read.",
        ) from error

    if not available:
        return AdminValuationModelInfo(
            model_available=False,
            fallback_method="rule_based",
            disclaimer=(
                "The ML valuation model is not currently loaded, so new "
                "submissions use the rule-based estimate instead."
            ),
        )

    distribution = metrics_payload.get("training_distribution") or {}
    age_min, age_max = distribution.get("age_min"), distribution.get("age_max")
    age_range = (
        f"{age_min}-{age_max} years" if age_min is not None and age_max is not None else None
    )

    return AdminValuationModelInfo(
        model_available=True,
        model_type=metrics_payload.get("model_type"),
        pipeline=metrics_payload.get("pipeline"),
        dataset_kind=metrics_payload.get("dataset_kind"),
        total_rows=metrics_payload.get("total_rows"),
        training_rows=metrics_payload.get("training_rows"),
        test_rows=metrics_payload.get("test_rows"),
        features=metrics_payload.get("features", []),
        target=metrics_payload.get("target"),
        metrics=metrics_payload.get("metrics", {}),
        model_name=metrics_payload.get("model_name"),
        trained_at=metrics_payload.get("trained_at"),
        dataset_identifier=metrics_payload.get("dataset_identifier"),
        cv_folds=metrics_payload.get("cv_folds"),
        model_comparison=metrics_payload.get("model_comparison", {}),
        baselines=metrics_payload.get("baselines", {}),
        model_selection_note=metrics_payload.get("model_selection_note"),
        baseline_note=metrics_payload.get("baseline_note"),
        metrics_ceiling_note=metrics_payload.get("metrics_ceiling_note"),
        training_age_range=age_range,
        disclaimer=metrics_payload.get("disclaimer"),
        fallback_method="rule_based",
    )
