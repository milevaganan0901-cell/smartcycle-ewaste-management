"""Reusable authentication dependencies."""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import ADMIN_ROLE, User


bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Authentication required.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _user_from_credentials(
    credentials: HTTPAuthorizationCredentials | None,
    database: Session,
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        payload = decode_access_token(credentials.credentials)
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured.",
        ) from error
    except jwt.PyJWTError as error:
        raise _unauthorized("Invalid or expired authentication token.") from error

    subject = payload.get("sub")
    if subject is None:
        raise _unauthorized("Invalid or expired authentication token.")

    try:
        user_id = int(subject)
    except (TypeError, ValueError) as error:
        raise _unauthorized("Invalid or expired authentication token.") from error

    user = database.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Invalid or expired authentication token.")
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    database: Session = Depends(get_db),
) -> User:
    """Return the active user represented by a valid bearer token."""
    return _user_from_credentials(credentials, database)


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    database: Session = Depends(get_db),
) -> User | None:
    """Return a valid user when a token is present, otherwise return None."""
    if credentials is None:
        return None
    try:
        return _user_from_credentials(credentials, database)
    except HTTPException:
        return None


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """Return the authenticated user only when they hold the admin role.

    This is the security boundary for every admin endpoint. It reuses
    `get_current_user`, so an unauthenticated or expired token still fails with
    401 before the role is ever considered. A signed-in non-admin user receives
    403. Frontend route guards are only a convenience and never a substitute.
    """
    if current_user.role != ADMIN_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access is required for this resource.",
        )
    return current_user
