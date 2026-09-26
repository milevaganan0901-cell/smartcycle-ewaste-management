# Stage 3H — Admin Status Updates

Stage 3H lets an authenticated administrator change a device's status and a pickup request's status through validated, database-persisted endpoints, and confirms those changes propagate automatically to the owning user's dashboard and to Track Device. Stages 3A–3G are preserved.

## Security fix included in this stage

While inspecting the existing device API, a **pre-existing Stage 3A vulnerability** was found: `PATCH /api/devices/{tracking_id}/status` had **no authentication dependency at all**. It was verified live before the fix — an anonymous `curl` with no token, and a normal user token, both changed any device's status, including devices owned by other users.

Stage 3H requires that "normal users must be unable to update status themselves", so the existing `get_current_admin` dependency from Stage 3G was applied to that route as well. There is now exactly one authorization path to change a status, and it is admin-only. The route's behaviour is otherwise unchanged.

## Endpoints

Both live in the existing `app/api/routers/admin.py` (prefix `/admin`), following the project's existing router conventions.

### Device status

```text
PATCH /api/admin/devices/{device_id}/status
```

- Depends on `get_current_admin` (JWT + admin role read from the validated token).
- Body validated by the existing `DeviceStatusUpdate` schema, whose `status` field is a `Literal` over the project's existing `ALLOWED_DEVICE_STATUSES`. Unknown, empty, null, wrong-type or whitespace-only values are rejected with `422` before anything is written. Extra fields (for example `user_id`) are rejected with `422 extra_forbidden`.
- `404` when the device id does not exist; `422` for a non-integer id.
- Writes **only** `status` and `updated_at`. `user_id`, ownership, valuation and every other field are untouched.
- Returns the full updated `DeviceResponse`.

### Pickup status

```text
PATCH /api/admin/pickups/{pickup_id}/status
```

- Depends on `get_current_admin`.
- Body validated by the new `PickupStatusUpdate` schema in `app/schemas/pickup.py`, whose `status` field is a `Literal` over the existing `ALLOWED_PICKUP_STATUSES`.
- `404` when the pickup id does not exist.
- Writes **only** `status` and `updated_at`. The owner, device link, address and time slot are untouched.
- Returns the full updated `PickupResponse`.

The existing `DeviceStatusUpdate` schema was reused rather than duplicated; only the pickup equivalent was genuinely missing. No new auth or authorization system was introduced.

## Status values and transition rules

| Record | Allowed values |
| --- | --- |
| Device | `Submitted`, `Under Review`, `Pickup Scheduled`, `Collected`, `Inspection`, `Refurbishment`, `Recycling`, `Completed` |
| Pickup | `Requested`, `Scheduled`, `Collected`, `Cancelled` |

These are taken directly from `ALLOWED_DEVICE_STATUSES` and `ALLOWED_PICKUP_STATUSES` in the models — no new status values were invented, and the two lifecycles remain separate.

**No transition rules were added.** The project had none, and Stage 3A's endpoint freely accepted any defined value. Adding a state machine would have broken existing behaviour and gone beyond this stage, so validation is limited to the defined value sets.

The frontend builds its dropdown options from the backend's own `devices_by_status` / `pickups_by_status` buckets returned by `GET /api/admin/dashboard`, so the selectable values are the server's, not a separately hardcoded React list.

## Frontend

`src/pages/AdminDashboardPage.jsx` was extended, not redesigned:

- Each device row gained an "Update status" `<select>` populated from the backend's device status buckets.
- Each pickup row gained an "Update status" `<select>` populated from the backend's pickup status buckets.
- A per-row `updating` map drives the "Saving…" indicator and **disables the control while a request is in flight**, which is what prevents duplicate submissions.
- On success the row is updated in place, the aggregate statistics are refreshed, and a success banner names the record and the new status.
- On failure a single clear, non-technical message is shown. Statuses are only applied after the server confirms, so a failed or offline request never leaves a misleading badge.
- 401, 403, 404, 422, network and generic failures each map to their own message; raw backend errors are never rendered.

`src/api/client.js` gained `updateAdminDeviceStatus` and `updateAdminPickupStatus`, which reuse the existing `ApiError` and `readResponseBody` helpers and validate the returned payload shape.

## Database changes

None. `Device.status`, `Device.updated_at`, `PickupRequest.status` and `PickupRequest.updated_at` all already existed. No migration, no new table, no column added, and no user, device or pickup row deleted.

## Propagation

Both user-facing pages already fetch live data from the API, so no synchronization code was needed. Verified end-to-end:

- Admin set `EW-2026-0010` to `Pickup Scheduled`; `GET /api/devices/EW-2026-0010` (the Track Device endpoint) returned `Pickup Scheduled`, and the Track Device page showed it with the status guide highlighting it.
- The owning user's `/api/users/me/devices` and the User Dashboard showed the same new status.
- Admin set a pickup to `Scheduled`; the owning user's `/api/pickups/my` and the User Dashboard pickup table both showed `Scheduled`.

## Verification

- Admin updates: device `200`, pickup `200`
- Normal user on both admin update routes: `403` (own and other users' records alike)
- Normal user on the legacy `PATCH /api/devices/{tracking_id}/status`: `403`
- Unauthenticated on all three update routes: `401`
- Invalid statuses: unknown, empty, whitespace-only, null, wrong type, missing field, extra field — all `422` for both device and pickup
- Bad ids: device `999999` → `404`, `abc` → `422`, pickup `999999` → `404`, `0` → `404`
- Persistence confirmed by re-reading through the API and directly from SQLite
- Duplicate submission blocked in the UI (the control is disabled while saving)
- Network failure shows "Unable to reach the server…" and leaves the status unchanged
- User A cannot see User B's devices or pickups; A reading B's pickup by id → `404`
- Registration, login, logout, Sell Device, pickup creation all still work
- `npm run build` and `npm audit --audit-level=high` (0 vulnerabilities) pass; no browser console errors on any of the 11 routes; backend log free of tracebacks and 5xx

## Not implemented in this stage

ML/AI valuation, payments, email or SMS notifications, courier/logistics integration, maps, pickup-agent accounts, delivery tracking, production deployment, advanced analytics or report generation, a mobile application, a status-history or audit-log system, and any status transition state machine.
