"""Pickup request routes for the authenticated user.

Ownership is enforced from the validated bearer token only. Neither route nor
body accepts a user identifier, and every read is filtered by `user_id` in SQL.
A device or pickup that belongs to somebody else is reported as "not found" so
the API never confirms that another account's record exists.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.device import Device
from app.models.pickup import PickupRequest
from app.models.user import User
from app.schemas.pickup import PickupCreate, PickupResponse


router = APIRouter(prefix="/pickups", tags=["pickups"])


def _find_owned_device(device_id: int, current_user: User, database: Session) -> Device:
    """Return a device only when the authenticated user owns it."""
    device = database.execute(
        select(Device).where(
            Device.id == device_id,
            Device.user_id == current_user.id,
        )
    ).scalar_one_or_none()

    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No device matching that ID was found on your account.",
        )
    return device


def _find_owned_pickup(pickup_id: int, current_user: User, database: Session) -> PickupRequest:
    """Return a pickup request only when the authenticated user owns it."""
    pickup = database.execute(
        select(PickupRequest).where(
            PickupRequest.id == pickup_id,
            PickupRequest.user_id == current_user.id,
        )
    ).scalar_one_or_none()

    if pickup is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That pickup request was not found on your account.",
        )
    return pickup


@router.post(
    "",
    response_model=PickupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request pickup for one of your own devices",
)
def create_pickup_request(
    payload: PickupCreate,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> PickupRequest:
    """Create a pickup request for a device owned by the authenticated user."""
    device = _find_owned_device(payload.device_id, current_user, database)

    existing_request = database.execute(
        select(PickupRequest).where(
            PickupRequest.device_id == device.id,
            PickupRequest.user_id == current_user.id,
            PickupRequest.status != "Cancelled",
        )
    ).scalar_one_or_none()

    if existing_request is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pickup request already exists for this device.",
        )

    pickup = PickupRequest(
        user_id=current_user.id,
        device_id=device.id,
        pickup_address=payload.pickup_address,
        preferred_date=payload.preferred_date,
        preferred_time_slot=payload.preferred_time_slot,
        status="Requested",
    )
    database.add(pickup)
    try:
        database.commit()
        database.refresh(pickup)
        return pickup
    except IntegrityError as error:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pickup request already exists for this device.",
        ) from error
    except SQLAlchemyError as error:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The pickup request could not be saved due to a database error.",
        ) from error


@router.get(
    "/my",
    response_model=list[PickupResponse],
    summary="List your own pickup requests",
)
def list_my_pickup_requests(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[PickupRequest]:
    """Return only the pickup requests belonging to the authenticated user."""
    query = (
        select(PickupRequest)
        .where(PickupRequest.user_id == current_user.id)
        .order_by(PickupRequest.id.desc())
    )

    try:
        return list(database.execute(query).scalars().all())
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Your pickup requests could not be loaded due to a database error.",
        ) from error


@router.get(
    "/{pickup_id}",
    response_model=PickupResponse,
    summary="Get one of your own pickup requests",
)
def get_pickup_request(
    pickup_id: int,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> PickupRequest:
    """Return a single pickup request owned by the authenticated user."""
    return _find_owned_pickup(pickup_id, current_user, database)
