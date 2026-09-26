# Stage 3D — Authentication

Stage 3D adds secure registration, login, logout and current-user retrieval to SmartCycle, and prepares a nullable device-ownership relationship for later stages. Stage 3A, 3B and 3C behavior is preserved: Sell Device and Track Device remain usable without logging in.

## User model

`backend/app/models/user.py`, table `users`:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | integer | primary key, autoincrement |
| `name` | string(120) | required |
| `email` | string(320) | required, unique, indexed, stored lowercase |
| `password_hash` | string(255) | required, Argon2id hash, never returned |
| `is_active` | boolean | required, default `True` |
| `created_at` | datetime(timezone=True) | set on insert |
| `updated_at` | datetime(timezone=True) | set on insert and update |

`devices` is a relationship back to `Device`.

Schemas in `backend/app/schemas/user.py`:

- `UserCreate`: `name`, `email`, `password`, `confirm_password` (input only, never contains `password_hash`)
- `UserLogin`: `email`, `password`
- `UserResponse`: `id`, `name`, `email`, `created_at` (never contains `password` or `password_hash`)
- `Token`: `access_token`, `token_type`

## Endpoints

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/auth/register` | public | Create an account, returns `201` and `UserResponse` |
| `POST` | `/api/auth/login` | public | Verify credentials, returns `200` and `Token` |
| `GET` | `/api/auth/me` | bearer token | Returns `UserResponse` for the token owner |

Status codes:

- `201` registration success
- `400` duplicate email
- `422` schema validation (missing fields, invalid email, password shorter than 8 characters, mismatched confirmation)
- `200` login success
- `401` login failure — always `Incorrect email or password`, whether the email is unknown or the password is wrong, so the response never reveals whether an email is registered
- `401` missing, malformed, invalid or expired token on protected endpoints
- `503` authentication not configured (`JWT_SECRET_KEY` missing)

Database errors are converted into clean 4xx/5xx responses. Stack traces, SQL details and internal exceptions are never returned to the client.

## Password hashing

`pwdlib[argon2]` (`PasswordHash.recommended()`, Argon2id). Hashes look like `$argon2id$v=19$m=65536,...`; plaintext passwords are never stored or logged.

`passlib[bcrypt]` was evaluated first but is unmaintained and breaks against the current `bcrypt` release (`module 'bcrypt' has no attribute '__about__'`), so the maintained `pwdlib` wrapper over Argon2 was used instead.

Login always verifies a password against a hash, using a dummy hash when the email is unknown, so response time does not reveal whether an account exists.

## Tokens

- Library: `PyJWT`
- Algorithm: `HS256`
- Expiry: 480 minutes (8 hours), configurable with `ACCESS_TOKEN_EXPIRE_MINUTES`
- Claims: `sub` (user id), `iat`, `exp`
- Signing secret: `JWT_SECRET_KEY` environment variable, never hardcoded

`get_current_user` in `backend/app/api/deps.py` is the reusable dependency for any future protected endpoint. It reads the `Authorization: Bearer <token>` header, validates the token, loads the user, rejects inactive users, and raises a clean `401` otherwise. `get_optional_current_user` is available for endpoints that stay public but may attach ownership when a token happens to be present.

## Device ownership

`backend/app/models/device.py` gained a nullable `user_id` foreign key to `users.id` (`ondelete="SET NULL"`) plus a `user` relationship.

Migration approach, without Alembic:

1. `Base.metadata.create_all` creates the new `users` table and, on a fresh database, creates `devices.user_id` with its foreign key.
2. `init_db` then inspects the live `devices` table. If `user_id` is missing, it runs `ALTER TABLE devices ADD COLUMN user_id INTEGER` and creates `ix_devices_user_id` with `CREATE INDEX IF NOT EXISTS`. Both statements are idempotent.
3. SQLite cannot attach a foreign-key constraint to a column that already exists through `ALTER TABLE`, so databases created before Stage 3D keep a plain nullable column. Fresh databases get the real constraint. Application-level behavior is identical.

Existing device rows are never backfilled or re-owned; they keep `user_id = NULL`. `POST /api/devices` does not require authentication. When a valid token is present the device is associated with that user, otherwise it is created anonymously exactly as in Stage 3B.

## Frontend

- `src/api/client.js`: `registerUser`, `loginUser`, `getCurrentUser` next to the existing device helpers, reusing `ApiError` and the existing network-error message. `createDevice` now attaches `Authorization` when a token exists, which is what makes ownership association work from the app.
- `src/auth/authStorage.js`: isolated `localStorage` wrapper (`smartcycle.access_token`) for get, set and clear.
- `src/context/AuthContext.jsx`: React context exposing `user`, `token`, `isAuthenticated`, `isRestoring`, `login`, `register` and `logout`. On load it calls `GET /api/auth/me`; an invalid or expired token is cleared and the visitor is treated as logged out.
- `src/components/RequireAuth.jsx`: route guard that shows a brief session check, then redirects to `/login` with the attempted location in router state.
- `src/pages/LoginPage.jsx` and `src/pages/RegisterPage.jsx`: existing forms wired to the API with client-side field validation before submit and backend errors shown after submit.
- `src/components/SiteHeader.jsx`: shows the visitor's first name, a Dashboard link and a Log out button when authenticated; Login and Get started when not.

Redirect rules: successful registration returns the visitor to `/login` with a confirmation message, and successful login returns them to the page they originally requested or to `/dashboard`. Logout clears the token and returns to `/`.

## Environment variables

```text
JWT_SECRET_KEY               required, signing secret, never hardcode or commit
ACCESS_TOKEN_EXPIRE_MINUTES  optional, defaults to 480
DATABASE_URL                 optional, defaults to the local SQLite file
CORS_ORIGINS                 optional, defaults to the local Vite origins
```

Set it for each backend start:

```bash
export JWT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
```

## Not implemented in this stage

Pickup scheduling or management, admin authentication or authorization, admin user management, email verification, password reset, SMS or notifications, OAuth or social login, ML valuation, production deployment, and any requirement that Sell Device or Track Device needs a login.
