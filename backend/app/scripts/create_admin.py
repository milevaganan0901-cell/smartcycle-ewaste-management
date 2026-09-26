"""Create or promote a development admin account from the command line.

This is a local development tool, not an API. There is deliberately no HTTP
endpoint that can change a role, so nobody can become an admin through the
running application.

Usage (from the `backend` directory):

    python -m app.scripts.create_admin
    python -m app.scripts.create_admin --email admin@example.com --password 'S3cret-pass' --name 'Site Admin'
    python -m app.scripts.create_admin --promote existing.user@example.com

The password is hashed with the same Argon2 helper the API uses, and it is
never printed in plain text.
"""

import argparse
import getpass
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.security import hash_password
from app.db.session import SessionLocal, init_db
from app.models.user import ADMIN_ROLE, DEFAULT_USER_ROLE, User


MIN_PASSWORD_LENGTH = 8


def _validate_email(email: str) -> str:
    """Reject emails the login schema would refuse, so the account is usable."""
    try:
        # Validate with the same type the API schemas use.
        TypeAdapter(EmailStr).validate_python(email)
        return email.strip().lower()
    except ValidationError:
        print(
            f"'{email}' is not a valid email address, so the account could not log in.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


def _read_password() -> str:
    """Read a password without echoing it, falling back to a plain argument."""
    try:
        return getpass.getpass("Admin password: ")
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(1) from None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.scripts.create_admin",
        description="Create or promote a local development admin account.",
    )
    parser.add_argument("--email", help="Email for a new admin account.")
    parser.add_argument("--password", help="Password (prefer the interactive prompt).")
    parser.add_argument("--name", default="SmartCycle Admin", help="Display name for a new account.")
    parser.add_argument(
        "--promote",
        metavar="EMAIL",
        help="Promote an existing account to admin instead of creating one.",
    )
    return parser.parse_args()


def _create_admin(email: str, name: str, password: str) -> None:
    with SessionLocal() as database:
        existing = database.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()

        if existing is not None:
            database.rollback()
            print(f"An account already exists for {email}.", file=sys.stderr)
            print("Use --promote to make it an admin.", file=sys.stderr)
            raise SystemExit(1)

        admin = User(
            name=name.strip() or "SmartCycle Admin",
            email=email,
            password_hash=hash_password(password),
            is_active=True,
            role=ADMIN_ROLE,
        )
        database.add(admin)
        database.commit()
        print(f"Created admin account: {email}")


def _promote_admin(email: str) -> None:
    with SessionLocal() as database:
        user = database.execute(select(User).where(User.email == email)).scalar_one_or_none()

        if user is None:
            database.rollback()
            print(f"No account found for {email}.", file=sys.stderr)
            raise SystemExit(1)

        if user.role == ADMIN_ROLE:
            print(f"{email} is already an admin.")
            return

        user.role = ADMIN_ROLE
        database.commit()
        print(f"Promoted {email} to admin (was: {DEFAULT_USER_ROLE}).")


def main() -> None:
    args = _parse_args()

    if bool(args.promote) == bool(args.email):
        print("Provide exactly one of --email or --promote.", file=sys.stderr)
        raise SystemExit(1)

    init_db()

    try:
        if args.promote:
            _promote_admin(_validate_email(args.promote))
            return

        password = args.password or _read_password()
        if len(password) < MIN_PASSWORD_LENGTH:
            print(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        _create_admin(_validate_email(args.email), args.name, password)
    except SQLAlchemyError as error:
        print(f"The database could not be updated: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
