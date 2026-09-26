# Stage 3G — Admin Role and Real Admin Dashboard

Stage 3G introduces a simple `user` / `admin` role enforced entirely on the backend, and connects the existing Admin Dashboard to real, database-backed statistics and lists. Stages 3A–3F are unchanged in behavior.

## Model change

`backend/app/models/user.py` gained one column:

| Column | Type | Notes |
| --- | --- | --- |
| `role` | String(20) | not null, default `"user"` |

Module constants `DEFAULT_USER_ROLE = "user"`, `ADMIN_ROLE = "admin"` and `ALLOWED_USER_ROLES` live beside the model, plus an `is_admin` convenience property.

### Migration

The project uses raw `Base.metadata.create_all` (no Alembic), so the new column is added with the same idempotent `ALTER TABLE` pattern already used for `devices.user_id`, inside `init_db()`:

```python
if "role" not in user_columns:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20)"))
        connection.execute(
            text("UPDATE users SET role = :role WHERE role IS NULL OR role = ''")
            .bindparams(role=DEFAULT_USER_ROLE)
        )
```

Running `init_db()` is safe to repeat. Existing accounts are backfilled to `"user"`, never to `"admin"`, and no user, device or pickup row was deleted or modified beyond that default.

Registration sets the role explicitly:

```python
user = User(..., role=DEFAULT_USER_ROLE)
```

`UserCreate` uses `extra="forbid"`, so a `role` field in a registration body is rejected with `422 extra_forbidden`. There is no API route that changes a role.

## Admin authorization

`get_current_admin` in `backend/app/api/deps.py`:

```python
def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != ADMIN_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access is required for this resource.",
        )
    return current_user
```

It reuses `get_current_user`, so an absent, malformed, invalid or expired token fails with `401` before the role is ever considered; a valid non-admin token fails with `403`. Every admin route depends on this — no route uses a frontend check.

**The backend is the security boundary.** The frontend `RequireAdmin` guard only improves UX; a non-admin who bypasses it still receives `403` from the API.

## Creating a development admin

There is no HTTP endpoint for this. Use the CLI, which reuses the Stage 3D `hash_password` helper:

```bash
cd backend
source .venv/bin/activate

# Create a new admin (password is prompted for, not echoed)
python -m app.scripts.create_admin --email admin@example.com --name "SmartCycle Admin"

# Or create with an explicit password
python -m app.scripts.create_admin --email admin@example.com --password 'your-password'

# Or promote an existing account
python -m app.scripts.create_admin --promote existing.user@example.com
```

The script calls `init_db()` first, validates the email with the same `EmailStr` type the login schema uses (so it cannot create an account that cannot log in), refuses to overwrite an existing account, and never prints a password.

## Admin endpoints

All four are read-only and admin-only, in `backend/app/api/routers/admin.py` with prefix `/admin`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/admin/dashboard` | Aggregated stats, status breakdowns, recent activity |
| `GET` | `/api/admin/users` | All accounts with role and record counts |
| `GET` | `/api/admin/devices` | All devices across all users, with owner |
| `GET` | `/api/admin/pickups` | All pickup requests across all users |

Totals use `func.count()`, status breakdowns use `GROUP BY`, and per-user device/pickup counts are `LEFT JOIN`ed subqueries — no full-table load into Python.

Status buckets always report every value from `ALLOWED_DEVICE_STATUSES` and `ALLOWED_PICKUP_STATUSES` (including zeros), so the UI uses the models' exact status strings rather than inventing any.

`/api/admin/users` never selects `password_hash`; no response anywhere contains a password, hash, or token.

## Frontend

- `src/api/client.js` — `getAdminDashboard`, `getAdminUsers`, `getAdminDevices`, `getAdminPickups`, each with response-shape validation and friendly error mapping.
- `src/pages/AdminDashboardPage.jsx` — the existing page wired to real data: overview metrics, device status breakdown, pickup status breakdown, device management table (with a status filter), users table, pickups table, and recent activity lists. Loading and error states included.
- `src/components/RequireAdmin.jsx` — route guard. Unauthenticated users are redirected to Login; a signed-in non-admin gets an explicit "Administrator access required" screen explaining the standard user role, with a link back to their dashboard. No admin data is ever rendered.
- `src/context/AuthContext.jsx` — exposes `isAdmin` from `user.role`.
- `src/components/SiteHeader.jsx` — the Admin link renders only when `isAdmin`.
- `src/App.jsx` — `/admin` wrapped in `RequireAdmin`.
- `src/data/demoData.js` — removed the now-unused sample `adminDevices` list.

`UserResponse` gained `role` and `is_active` so the frontend can render role-aware navigation. It still never exposes `password` or `password_hash`.

## Verification

- No token / invalid token / expired token on all four admin routes → `401`
- Normal authenticated user on all four admin routes → `403`
- Admin on all four routes → `200` with real rows; no `password` substring anywhere in the payload
- New registration → `role = "user"`, and that account gets `403` on admin APIs
- Logged-out `/admin` → redirected to Login; signed-in non-admin `/admin` → denied screen, no admin data
- Admin nav link absent for normal users, present for the admin
- Stats track live data: a normal user's new device and pickup immediately changed the counts
- Admin lists show data from 7 distinct device owners and 3 distinct pickup owners
- Stage 3A–3F re-verified for normal users (device create/get/404, `/api/auth/me`, own devices, own pickups, pickup create/422/409, dashboard, Track Device)
- `npm run build` and `npm audit --audit-level=high` (0 vulnerabilities) pass; no browser console errors; backend log free of tracebacks and 5xx

## Not implemented in this stage

Admin device status changes, pickup approval/rejection, pickup agent assignment, email/SMS notifications, payments, ML valuation, AI chatbot, deployment, analytics platforms or advanced reporting/export, logistics/maps integration, and any role management beyond the single `user` / `admin` flag.
