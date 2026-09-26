"""Authenticated routes for the current user's own account data."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.device import Device
from app.models.user import User
from app.schemas.device import DeviceResponse


router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me/devices",
    response_model=list[DeviceResponse],
    summary="List the devices submitted by the current user",
)
def list_my_devices(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[Device]:
    """Return only the devices owned by the authenticated user.

    The identity comes exclusively from the validated bearer token, never from
    a request parameter, and the ownership filter is applied in SQL.
    """
    query = (
        select(Device)
        .where(Device.user_id == current_user.id)
        .order_by(Device.id.desc())
    )

    try:
        return list(database.execute(query).scalars().all())
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Your devices could not be loaded due to a database error.",
        ) from error
