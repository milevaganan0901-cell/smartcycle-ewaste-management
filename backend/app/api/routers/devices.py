"""Device submission and lifecycle routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_optional_current_user
from app.db.session import get_db
from app.models.device import ALLOWED_DEVICE_STATUSES, Device
from app.models.user import User
from app.schemas.device import DeviceCreate, DeviceResponse, DeviceStatusUpdate
from app.services.tracking import generate_tracking_id
from app.services.valuation import ValuationInput, value_device


router = APIRouter(prefix="/devices", tags=["devices"])


def _find_device(database: Session, tracking_id: str) -> Device:
    """Find a device or return a consistent 404 response."""
    try:
        device = database.execute(
            select(Device).where(Device.tracking_id == tracking_id)
        ).scalar_one_or_none()
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The device lookup could not be completed due to a database error.",
        ) from error
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with tracking ID '{tracking_id}' was not found.",
        )
    return device


@router.post(
    "",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a device submission",
)
def create_device(
    payload: DeviceCreate,
    database: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> Device:
    """Create a device, assign its tracking ID, and calculate its values.

    Valuation is ML-first with an automatic rule-based fallback, so a
    missing or unusable ML model never fails the submission.
    """
    try:
        valuation = value_device(
            ValuationInput(
                device_category=payload.device_category,
                brand=payload.brand,
                age=payload.age,
                condition=payload.condition,
                working_status=payload.working_status,
                physical_damage=payload.physical_damage,
                original_purchase_price=payload.original_purchase_price,
            )
        )
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unable to calculate the demo estimate: {error}",
        ) from error

    # The retry protects sequential ID generation if two local requests try to
    # claim the same ID at the same time.
    for attempt in range(3):
        try:
            tracking_id = generate_tracking_id(database)
        except SQLAlchemyError as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The next tracking ID could not be generated due to a database error.",
            ) from error
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(error),
            ) from error

        device = Device(
            tracking_id=tracking_id,
            user_id=current_user.id if current_user is not None else None,
            device_category=payload.device_category,
            brand=payload.brand,
            model=payload.model,
            age=payload.age,
            condition=payload.condition,
            working_status=payload.working_status,
            physical_damage=payload.physical_damage,
            accessories=payload.accessories,
            original_purchase_price=payload.original_purchase_price,
            location=payload.location,
            estimated_purchase_value=valuation.estimated_purchase_value,
            potential_refurbished_value=valuation.potential_refurbished_value,
            potential_recycled_value=valuation.potential_recycled_value,
            valuation_method=valuation.valuation_method,
            status="Submitted",
        )
        database.add(device)
        try:
            database.commit()
            database.refresh(device)
            return device
        except IntegrityError as error:
            database.rollback()
            if attempt == 2:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="The device could not be saved because its tracking ID was not unique.",
                ) from error
        except SQLAlchemyError as error:
            database.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The device could not be saved due to a database error.",
            ) from error

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="The device could not be assigned a unique tracking ID.",
    )


@router.get(
    "",
    response_model=list[DeviceResponse],
    summary="List device submissions (admin only)",
)
def list_devices(
    status_filter: str | None = Query(default=None, alias="status"),
    _: User = Depends(get_current_admin),
    database: Session = Depends(get_db),
) -> list[Device]:
    """Return all devices, optionally filtered by lifecycle status.

    Stage 3J audit fix: this listing previously required no authentication and
    exposed every submission - including owner location, original purchase
    price and valuations - to anonymous callers. It is now restricted to admins,
    matching `/api/admin/devices`.

    A single device remains publicly readable by tracking ID via
    `GET /api/devices/{tracking_id}`, because the tracking ID is the product's
    intended shared reference for the Track Device flow.
    """
    query = select(Device).order_by(Device.id.desc())
    if status_filter is not None:
        normalized_status = status_filter.strip()
        if normalized_status not in ALLOWED_DEVICE_STATUSES:
            allowed = ", ".join(ALLOWED_DEVICE_STATUSES)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status. Allowed values: {allowed}.",
            )
        query = query.where(Device.status == normalized_status)

    try:
        return list(database.execute(query).scalars().all())
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The device list could not be loaded due to a database error.",
        ) from error


@router.get(
    "/{tracking_id}",
    response_model=DeviceResponse,
    summary="Get a device by tracking ID",
)
def get_device(
    tracking_id: str,
    database: Session = Depends(get_db),
) -> Device:
    """Return one device or a clear 404 response."""
    return _find_device(database, tracking_id)


@router.patch(
    "/{tracking_id}/status",
    response_model=DeviceResponse,
    summary="Update a device lifecycle status (admin only)",
)
def update_device_status(
    tracking_id: str,
    payload: DeviceStatusUpdate,
    _: User = Depends(get_current_admin),
    database: Session = Depends(get_db),
) -> Device:
    """Update only the device status and its modification timestamp.

    This endpoint used to be reachable without authentication, which let anyone
    change any device's status. Stage 3G introduced `get_current_admin` and
    Stage 3H requires that only an administrator can change a status, so the
    existing `get_current_admin` dependency is now applied here as well. The
    admin console uses `PATCH /api/admin/devices/{device_id}/status`; both
    routes behave identically.
    """
    device = _find_device(database, tracking_id)
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


@router.delete(
    "/{tracking_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a device submission (admin only)",
)
def delete_device(
    tracking_id: str,
    _: User = Depends(get_current_admin),
    database: Session = Depends(get_db),
) -> Response:
    """Delete a device submission and its pickup requests.

    Stage 3J security fix: this endpoint previously required no authentication
    and no ownership, so any anonymous caller who knew or guessed a tracking ID
    could permanently delete another user's submission. It is now restricted to
    administrators, matching the rest of the device management surface.

    The `PickupRequest.device_id` column is declared `ON DELETE CASCADE`, so the
    ORM relationship is configured to match; previously deleting a device that
    had a pickup request failed with a 500 because the ORM tried to null a
    non-nullable foreign key instead of cascading.
    """
    device = _find_device(database, tracking_id)
    try:
        database.delete(device)
        database.commit()
    except SQLAlchemyError as error:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The device could not be deleted due to a database error.",
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
