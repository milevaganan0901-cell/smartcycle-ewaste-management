# Stage 3F — Pickup Requests

Stage 3F adds a real, database-backed pickup request workflow. A signed-in user can request collection for one of their own devices, see their pickup requests and their status on the dashboard, and follow the request through the existing tracking flow. Ownership is enforced entirely on the server from the validated JWT. Stages 3A–3E are unchanged in behavior.

## Data model

`backend/app/models/pickup.py`, table `pickup_requests`:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | integer | primary key, autoincrement |
| `user_id` | integer | `ForeignKey("users.id", ondelete="CASCADE")`, required, indexed |
| `device_id` | integer | `ForeignKey("devices.id", ondelete="CASCADE")`, required, indexed |
| `pickup_address` | string(255) | required |
| `preferred_date` | date | required |
| `preferred_time_slot` | string(50) | required, one of the three fixed slots |
| `status` | string(20) | required, default `Requested` |
| `created_at` | datetime(timezone=True) | set on insert |
| `updated_at` | datetime(timezone=True) | set on insert and update |

Relationships: `User.pickup_requests` ↔ `PickupRequest.user`, and `Device.pickup_requests` ↔ `PickupRequest.device`.

`ALLOWED_PICKUP_STATUSES = ("Requested", "Scheduled", "Collected", "Cancelled")` and `ALLOWED_PICKUP_TIME_SLOTS = ("9:00 AM – 12:00 PM", "12:00 PM – 3:00 PM", "3:00 PM – 6:00 PM")`.

The pickup lifecycle is deliberately **separate** from `ALLOWED_DEVICE_STATUSES` in `app/models/device.py`. Requesting a pickup does not change a device's status; that remains an operations concern.

There is **no `contact_info` column**. The `User` model already stores the account email, so the pickup flow reuses it instead of duplicating contact data.

### How the table was created

The project uses raw `Base.metadata.create_all` in `init_db()` (no Alembic). `PickupRequest` is exported from `app/models/__init__.py` and imported in `init_db`, so `create_all` creates the new table additively. The existing `users` and `devices` tables and all of their rows are untouched; the idempotent `ALTER TABLE` step for `devices.user_id` is unchanged.

## Endpoints

All routes live in `backend/app/api/routers/pickup.py` with prefix `/pickups`, registered as `app.include_router(pickup.router, prefix="/api")`. All three require a bearer token.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/pickups` | Create a pickup request for one of your own devices (201) |
| `GET` | `/api/pickups/my` | List your own pickup requests (200, `[]` when none) |
| `GET` | `/api/pickups/{pickup_id}` | Get one of your own pickup requests (200) |

Schemas in `backend/app/schemas/pickup.py`: `PickupCreate` (`device_id`, `pickup_address`, `preferred_date`, `preferred_time_slot`) and `PickupResponse` (id, device_id, pickup_address, preferred_date, preferred_time_slot, status, created_at, updated_at). `UserResponse` and `DeviceResponse` are reused unchanged; no schema was duplicated.

### Status codes and errors

| Situation | Response |
| --- | --- |
| Created | `201` + `PickupResponse` |
| Missing/blank/short address, missing or malformed date, past date, date beyond 12 months, missing or invalid time slot, extra fields | `422` with a field-level message |
| Device does not exist **or belongs to another user** | `404` "No device matching that ID was found on your account." |
| Pickup does not exist **or belongs to another user** | `404` "That pickup request was not found on your account." |
| A non-cancelled pickup already exists for the device | `409` "A pickup request already exists for this device." |
| No / invalid / expired token | `401` |
| Database failure | `500` with a safe message |

Not-found is used rather than forbidden for someone else's record so the API never confirms that another account's device or pickup exists.

## Ownership enforcement

`current_user` comes from the existing `get_current_user` dependency, which validates the JWT and loads the user. No route accepts a user identifier, so nothing a client sends can change whose data is returned:

- **Creation** looks up the device with `select(Device).where(Device.id == device_id, Device.user_id == current_user.id)`. The `user_id` predicate is part of the query, so another user's device simply does not match.
- **Listing** filters with `select(PickupRequest).where(PickupRequest.user_id == current_user.id)`, compiled to `WHERE pickup_requests.user_id = ?`.
- **Single read** uses `select(PickupRequest).where(PickupRequest.id == pickup_id, PickupRequest.user_id == current_user.id)`.

A `user_id` in the request body is rejected by `extra="forbid"` before any lookup runs. A `user_id` query parameter is ignored because the route declares no such parameter.

## Frontend

- `src/api/client.js` — added `getMyPickups(token)` and `createPickupRequest(token, pickup)`, plus an `isPickupResponse` shape validator, following the existing device/auth helper pattern. Errors are mapped to friendly, non-technical messages.
- `src/pages/PickupRequestPage.jsx` — the pickup form at `/dashboard/pickup`, protected by the existing `RequireAuth`. The device `<select>` is populated only from `getMyDevices`, so it can only ever list the user's own devices; a `?device=` query value is applied only if that device is in the user's own list. Fields: device, pickup address, preferred date (`min` is today), preferred time slot. The sidebar shows the selected device, its tracking ID, and a note that the account email is used for contact.
- `src/components/PickupStatusBadge.jsx` — small badge reusing the existing `.status-badge` classes. Added as a separate component so the shared `StatusBadge` used by devices, the dashboard and Track Device is untouched.
- `src/pages/DashboardPage.jsx` — additionally fetches `getMyPickups` and shows real pickup data: a new **Pickup** column in the device table (status, preferred date, time slot), a truck action linking to `/dashboard/pickup?device=<id>` only for devices without an open request, and a new **My pickup requests** section listing device, status, preferred date, time slot, address summary and requested date. Existing profile, stats, device table, Track action, loading/error states and logout are unchanged.
- `src/App.jsx` — added the protected `/dashboard/pickup` route.
- `src/styles.css` — additive rules only (`.pickup-cell`, `.pickup-cell-muted`, `.dashboard-pickup-heading`, `.dashboard-empty-state-compact`).

`SellDevicePage` was not reworked. Its result-card button was labelled "Request Pickup" while actually navigating to `/track?id=…`; the label is now "Track this device" and the side tip points to the dashboard, so the text matches the actual behaviour. No Stage 3B logic changed.

### States handled

Loading (both sections), empty device list, empty pickup list, network failure, generic API failure, backend field errors, duplicate request (409), device not found / not owned (404), session expiry (401 → shared `logout()` → `RequireAuth` redirect to Login), and a signed-in user with no devices (submit disabled with an explanation).

## Verification

- Create for own device → 201; unauthenticated create → 401; own list → 200; other user's pickup by id → 404; other user's device id → 404; nonexistent id → 404; `id=0` → 422
- Missing address, blank address, missing date, past date, >12-month date, malformed date, missing time slot, invalid time slot, `user_id` in body → all 422 with clear messages
- Duplicate pickup → 409; expired/garbage token → 401
- Full User A / User B isolation, including crafted browser requests for another user's device and pickup
- Sell Device (logged in and logged out), Track Device, Stage 3E dashboard isolation and Stage 3D auth all still pass
- `npm run build` and `npm audit --audit-level=high` (0 vulnerabilities) pass; no new browser console errors; backend log free of errors and tracebacks

## Not implemented in this stage

Admin pickup management, admin authorization, admin status controls, email/SMS notifications, payment processing, ML valuation, AI chatbot, analytics, real logistics or maps integration, and deployment.
