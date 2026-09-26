# Stage 3E — Real Authenticated User Dashboard

Stage 3E replaces the static demo dashboard with a real dashboard that shows only the signed-in user's own profile, devices and account-level stats. Ownership is enforced entirely on the server. Stage 3A–3D behavior is preserved: Sell Device and Track Device remain usable without logging in, and the Stage 3D authentication system was reused rather than replaced.

## Ownership relationship

Stage 3D already completed the user/device relationship, so no schema work was required:

- `backend/app/models/device.py` — `user_id` nullable `ForeignKey("users.id", ondelete="SET NULL")`, indexed, plus a `user` relationship
- `backend/app/models/user.py` — `devices` relationship back to `Device`
- `POST /api/devices` already resolved the owner through `get_optional_current_user` and stored `user_id` when a valid token was present

Devices with no owner keep `user_id = NULL`. They are never assigned, reassigned or deleted.

## Endpoint

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/users/me/devices` | bearer token | List only the caller's own devices |

`backend/app/api/routers/users.py`:

```python
query = (
    select(Device)
    .where(Device.user_id == current_user.id)
    .order_by(Device.id.desc())
)
```

- Identity comes from `current_user`, which `get_current_user` derives from the validated JWT. There is no user ID, email or owner parameter anywhere in the route, so no client-supplied identifier can influence the result.
- The ownership predicate is compiled into SQL (`WHERE devices.user_id = ?`), so filtering happens in SQLite rather than in Python.
- Returns `200` with a list, reusing the existing `DeviceResponse` schema. A new account with no devices returns `200 []`, not an error.
- `401` when the token is missing, malformed, invalid or expired.

Swagger shows the route under the `users` tag with the `HTTPBearer` lock icon and no request parameters.

## Dashboard

`frontend/src/pages/DashboardPage.jsx` now loads `/api/users/me/devices` with the existing token and renders:

- Profile card: name, email, member since, account status
- Stats computed from the returned devices: Total devices, Active devices (status other than `Completed`), Completed devices, Total estimated value (sum of `estimated_purchase_value`)
- Device table: brand + model with a category icon, category, tracking ID, estimated value, `StatusBadge`, submission date, and a Track action linking to `/track?id=<tracking_id>`
- Empty state: "You haven't submitted any devices yet." with a "Sell Your Device" button
- Loading state: "Loading your devices…" with placeholder metric values, never an empty-state message
- Error states: a specific message for an unreachable server and a generic message for any other failure, each with a "Try again" button

The existing layout, `MetricCard`, `StatusBadge`, table and typography are reused. Only additive styles were added (`.dashboard-profile*`, `.dashboard-empty-state`, `.dashboard-logout`, plus a small-screen rule).

`getMyDevices(token)` was added to `frontend/src/api/client.js` next to the existing device helpers. It reuses `ApiError` and the existing `isDeviceResponse` validator, and rejects a non-array or malformed payload so an unexpected response can never crash the page.

## Auth and error handling

- The dashboard reads `user`, `token` and `logout` from the existing `AuthContext`. No second auth or logout mechanism was added.
- On `401` the dashboard calls the shared `logout()`, which clears the stored token and auth state; the existing `RequireAuth` guard then redirects to `/login`, where a short "Please log in to view your dashboard." message is shown from the redirect state that `RequireAuth` already passes.
- The dashboard's own Log out button calls the same `logout()` and navigates home. From a protected route the shared guard's redirect lands on `/login`, which matches the existing header logout behavior.
- Network failures, unexpected API failures and malformed payloads all produce a non-technical message; raw backend errors are never rendered.

## Known test artifact

`EW-2026-0006` was created during Stage 3E browser testing with a test-tool input artifact (`ApplAsus` / `iPhone 1Zenbook 14 OLED`), which also produced a very large demo valuation. It is real data on a real account and was intentionally left in place rather than deleting a device row.

## Not implemented in this stage

Pickup scheduling or management, admin dashboard functionality or authorization, email/SMS notifications, password reset, email verification, social login, ML valuation, payments, and production deployment.
