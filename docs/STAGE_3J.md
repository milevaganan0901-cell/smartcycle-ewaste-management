# Stage 3J — Final quality assurance, security, documentation & deployment readiness

This stage adds no features. It audits, hardens, tests and documents what Stages
1–3I already built.

**No database was reset and no existing user, device or pickup record was
deleted.** Every fix below is additive or a restriction that was previously
missing; pre-existing rows keep their original values and their original
`valuation_method`.

---

## 1. Findings and fixes

### 1.1 Critical — `DELETE /api/devices/{tracking_id}` was completely unauthenticated

The Stage 3A device router shipped a `DELETE` route with no `Depends` and no
ownership check. Anyone who knew or guessed a tracking ID could permanently
delete another user's submission.

Verified before the fix, against the real database:

```
created throwaway device EW-2026-0038
ANONYMOUS DELETE -> 204 No Content
after anonymous delete, lookup -> 404
```

That was a real row destroyed by an unauthenticated request.

**Fix.** `delete_device` now requires `get_current_admin`, matching the rest of
the device-management surface. The frontend never called `DELETE`, so no client
code changed. A non-admin — including the device's own owner — receives `403`;
anonymous callers receive `401`.

### 1.2 High — `GET /api/devices` leaked every device to anonymous callers

The public device listing returned all submissions, including owner location,
original purchase price, condition and both valuation figures.

```
records returned to ANONYMOUS user: 27
fields exposed: accessories, age, brand, condition, created_at, device_category,
  estimated_purchase_value, id, location, model, original_purchase_price,
  physical_damage, potential_recycled_value, potential_refurbished_value,
  status, tracking_id, updated_at, valuation_method, working_status
```

The frontend never used this route (only `POST /api/devices` and
`GET /api/devices/{tracking_id}`), so restricting it broke nothing.

**Fix.** The listing is now admin-only. `GET /api/devices/{tracking_id}` stays
public on purpose: the tracking ID is the product's intended shared reference
for the Track Device flow, and that flow depends on it.

### 1.3 Medium — deleting a device with a pickup request returned 500

`PickupRequest.device_id` is declared `ON DELETE CASCADE` and is
`nullable=False`. The ORM relationship declared no cascade, so deleting a parent
tried to null a non-nullable foreign key and raised `IntegrityError`, which the
router correctly surfaced as a generic 500. The device survived, so this was an
availability bug rather than data loss — but delete was broken for exactly the
devices it mattered most for.

**Fix.** The relationship now declares `cascade="all, delete-orphan"` with
`passive_deletes=True`, matching the schema's stated intent.

### 1.4 Medium — SQLite was ignoring every declared foreign key

`PRAGMA foreign_keys` was `0`. SQLite does not apply
`ForeignKey(..., ondelete=...)` unless the pragma is set per connection, so the
schema's `CASCADE` and `SET NULL` rules were decorative and orphaned rows were
possible.

**Fix.** A `connect` event listener issues `PRAGMA foreign_keys=ON` for SQLite
databases. `PRAGMA foreign_key_check` now reports clean, and the full test
suite still passes with enforcement active.

### 1.5 Low — a dead "Settings" button in the admin workspace

`AdminDashboardPage` rendered a gear `<button title="Settings">` with no
`onClick` and no handler — a control that looked interactive and did nothing.
It was the only such button in the codebase. Removed, along with the
`.icon-button-large` rule and the now-unused `settings` icon that it alone
used. No feature was added in its place.

### 1.6 Low — stale and inaccurate API metadata

`GET /` reported `"stage": "stage-3g"` and the app was versioned `0.7.0` while
the project was at 3J. The OpenAPI description was a generic one-liner.

**Fix.** Version `1.0.0`; the root response reports the real version and points
at `/docs`; the OpenAPI description now documents the bearer-token flow, the
admin role boundary, the `404`-not-`403` ownership behaviour, and the honest
valuation semantics. The `HTTPBearer` scheme was already registered, so
Swagger's **Authorize** button works and protected routes are visibly marked.

## 2. Dead code removed

| Removed | Reason |
| --- | --- |
| `backend/app/api/routers/valuation.py` | Docstring-only placeholder; never registered. Valuation lives in `app/services/`. Misleading, since valuation *is* implemented. |
| `backend/app/api/routers/tracking.py` | Same. |
| `backend/app/utils/` | Empty package, never imported. |
| `frontend/src/hooks/`, `frontend/src/layouts/` | Contained only `.gitkeep`; never imported. |
| `components/.gitkeep`, `pages/.gitkeep` | Redundant in non-empty directories. |
| `smart-e-waste-management-system-project-plan.json` | An internal agent-session transcript (session IDs, token/cost metadata, raw messages). Checked for secrets first — none present — but it has no place in a public repository. |
| `.icon-button-large`, `settings` icon | Orphaned by 1.5. |

## 3. Files that were audited and found already correct

No `console.log`, `debugger`, `TODO`, `FIXME` or commented-out code anywhere in
the frontend or backend. Every `print()` is in one of the two legitimate CLI
scripts. No hardcoded secrets: `JWT_SECRET_KEY` is read from the environment and
the app refuses to issue tokens when it is unset. CORS uses an explicit parsed
origin list, never `*`, and credentials are enabled. No user input reaches raw
SQL — the only literal SQL is fixed DDL in `init_db()`. `localStorage` holds the
JWT and nothing else.

## 4. New test suite

`backend/app/scripts/run_api_tests.py` — standard library only, no test
framework, no new dependencies. Runs against a live server and the real SQLite
database.

```bash
# API checks (server must be running)
ADMIN_EMAIL=... ADMIN_PASSWORD=... python -m app.scripts.run_api_tests

# add the in-process valuation/ML checks
ADMIN_EMAIL=... ADMIN_PASSWORD=... python -m app.scripts.run_api_tests --unit

# valuation/ML checks only, no server needed
python -m app.scripts.run_api_tests --unit-only
```

**95 checks, all passing.** Grouped coverage:

- **Authentication** — register, duplicate email, invalid email, weak password,
  confirmation mismatch, login, wrong password, unknown email (both return the
  same generic `401`), `/api/auth/me` with/without/garbage token, no password in
  any response.
- **Authorization** — a normal user is `403` from all five admin endpoints and
  from both status-update routes; anonymous is `401`; the device list, the
  device delete and both status updates are all closed to non-admins.
- **Ownership isolation** — User A and User B each own a device and a pickup.
  Neither can see the other's device or pickup, cannot create a pickup for the
  other's device, cannot read the other's pickup by id, and cannot delete the
  other's device. Verified by direct API calls with both users' real tokens.
- **Devices and tracking** — server-side tracking ID, lookup by tracking ID,
  unknown ID `404`, negative age and incomplete body `422`.
- **Valuation** — numeric, finite, non-negative, `valuation_method` present,
  refurbished and recycled values present.
- **Pickups** — own device, duplicate `409`, past date `422`, invalid time slot
  `422`, owner-scoped listing.
- **Admin** — every endpoint reachable, no password in the user list, device and
  pickup status updates persist, invalid statuses `422`, unknown ids `404`,
  owner sees the change on the dashboard *and* via Track Device.
- **Admin delete and cascade** — admin deletes a device, it disappears, and its
  pickup request is cascaded away rather than orphaned.
- **Rule-based estimator** — standalone correctness, works without a purchase
  price, a non-working device values below a working one.
- **ML and fallback** — model loads and predicts; `value_device` prefers ML;
  missing model, corrupt model, `NaN` ratio, negative ratio and a raising
  pipeline all fall back to the rule-based estimator with an identical value.
  The model file is moved aside and restored, and restoration is asserted.

The failure-mode tests deliberately break things, so the service's own
server-side warning logs are suppressed during that section only; the tracebacks
they would print are the logging behaviour working, not test failures.

## 5. Verification performed

| Check | Result |
| --- | --- |
| Frontend `npm run build` | Pass — 68 modules, 311.77 kB JS (87.83 kB gzip), 59.43 kB CSS |
| `npm audit --audit-level=high` | 0 vulnerabilities |
| Backend startup | Pass |
| Backend test suite | 95/95 |
| ML training script | Pass, and byte-identical metrics across two runs (`random_state=42`) |
| Rule-based fallback | Verified for 5 distinct failure modes |
| JWT validation | Expired, wrong-secret, `alg=none` and non-string-`sub` tokens all rejected |
| CORS | Allowed origin reflected; `https://evil.example.com` gets `400` and no ACAO header |
| Error leakage | `404`/`422` bodies clean; no stack traces, paths, secrets or hashes |
| Responsive layout | 50 checks (10 pages × 5 widths: 360/414/768/1024/1440) — zero horizontal overflow |
| Lighthouse | Accessibility 1.0, Best Practices 1.0, SEO 1.0, zero failures, on 4 pages |
| Database integrity | 0 orphans, 0 duplicate emails, 0 duplicate tracking IDs, `foreign_key_check` clean, all hashes `$argon2id$` |
| End-to-end demo | All 15 stages pass, including cross-user isolation |

## 6. A performance observation that is *not* a bug

Every admin endpoint is called exactly twice per page load in the **dev server**.
This is React 18 `StrictMode` double-invoking effects in development. The
production bundle was inspected and contains `react-dom.production` and none of
React DOM's development-only double-invoke code, so this does not occur in a
built bundle. No change was made. If it ever matters, the fix is an
`AbortController` in the effect, not removing `StrictMode`.

## 7. Documentation

- `README.md` rewritten: problem statement, objectives, features, stack,
  architecture, real structure, workflows, database design, API overview,
  install, environment variables, running, testing, demo walkthrough,
  limitations, future work, and a viva-ready architecture section.
- `docs/DEPLOYMENT.md` added: what is and is not deployment-ready, required
  environment variables, start and build commands, database setup, ML setup,
  CORS, and secret handling. Documentation only — nothing was deployed.
- `backend/.env.example` completed with the four Stage 3I variables that were
  missing.
- `.gitignore` rewritten: virtual environments, caches, `node_modules`, build
  output, `.env`, local databases, the regenerable model artifact, IDE/OS files
  and local agent artifacts.
- `docs/STAGE_3J.md` (this file).

## 8. Decisions

**The trained model is not committed.** `valuation_model.joblib` is ~3.9 MB and
is derived entirely from the committed synthetic dataset, so it is fully
regenerable with one documented command. The API falls back to the rule-based
estimator when it is absent, so the app runs without it. `.gitignore` lists it
and the reason inline.

**`GET /api/devices/{tracking_id}` stays public.** Track Device is designed
around a shared tracking ID. Removing public read access would break the core
product flow. The trade-off is documented as a known limitation.
