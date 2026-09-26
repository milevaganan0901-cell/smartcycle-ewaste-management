"""User registration, login, and current-user routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.user import DEFAULT_USER_ROLE, User
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a SmartCycle user",
)
def register_user(
    payload: UserCreate,
    database: Session = Depends(get_db),
) -> User:
    """Create a user with a securely hashed password."""
    email = str(payload.email).strip().lower()
    existing_user = database.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    # The role is set explicitly here so a registration payload can never
    # influence it; `UserCreate` also forbids extra fields.
    user = User(
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        is_active=True,
        role=DEFAULT_USER_ROLE,
    )
    database.add(user)
    try:
        database.commit()
        database.refresh(user)
    except IntegrityError as error:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        ) from error
    except SQLAlchemyError as error:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The account could not be created due to a database error.",
        ) from error
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Log in and receive an access token",
)
def login_user(
    payload: UserLogin,
    database: Session = Depends(get_db),
) -> Token:
    """Authenticate a user and issue a signed access token."""
    email = str(payload.email).strip().lower()
    user = database.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()
    stored_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_matches = verify_password(payload.password, stored_hash)

    if user is None or not password_matches or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        access_token = create_access_token(user.id)
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured.",
        ) from error
    return Token(access_token=access_token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the currently authenticated user",
)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return the safe user record represented by the bearer token."""
    return current_user
