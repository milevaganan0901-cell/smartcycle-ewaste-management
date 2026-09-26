# Deployment readiness (documentation only)

**Deployment has not yet been performed.** SmartCycle has never been deployed to
any hosting service; it runs only on a local machine. Nothing in this document has
been executed against a real host, and no production URL exists. This page
records what a deployment *would* require so the gaps are explicit rather than
discovered later.

No production URL, host name or credential appears here, and none should ever be
committed.

---

## 1. What is deployment-ready today

| Area | Status |
| --- | --- |
| Frontend production bundle | `npm run build` succeeds (Vite, static output in `frontend/dist/`) |
| Backend ASGI app | Starts under `uvicorn`; all routers and OpenAPI schema load |
| Database schema | Created idempotently on startup by `init_db()` |
| Authentication | Argon2 password hashing, signed JWT access tokens, expiry enforced |
| Authorization | Owner-scoped queries and an admin role enforced server-side |
| Configuration | All tunables read from environment variables |
| Secrets | No secret is hardcoded; nothing sensitive is committed |
| Tests | Dependency-free API + service suite (`app.scripts.run_api_tests`) |
| ML model | Regenerable by a manual script; API degrades gracefully without it |

## 2. What is NOT deployment-ready

These are the real blockers. Each is a deliberate scope decision, not an
oversight.

| Gap | Why it blocks a real deployment |
| --- | --- |
| **SQLite** | Single-writer, file-based. Cannot back multiple app instances, and at risk of total data loss on any platform with an ephemeral filesystem. Detailed below. |
| **No migrations** | `init_db()` uses `ALTER TABLE ... ADD COLUMN` for a handful of columns. It cannot express renames, drops, type changes or data migrations. Alembic is the right tool. |
| **JWT in `localStorage`** | Readable by any script running on the page. A stored XSS becomes a session theft. Production should use a short-lived access token plus an `HttpOnly`, `Secure`, `SameSite` refresh cookie. |
| **No refresh tokens / revocation** | An issued token is valid for its full lifetime with no server-side way to revoke it. Logout only clears client state. |
| **No rate limiting** | Login and registration are unthrottled, so credentials can be brute-forced. |
| **No HTTPS enforcement** | Tokens and passwords would cross the network in plaintext. |
| **No account verification or password reset** | No email delivery of any kind. |
| **No structured logging or monitoring** | Only default uvicorn logging. No error tracking, no health-based alerting. |
| **No CI** | Nothing runs the build or the tests automatically on push. |
| **No containerisation** | No Dockerfile, no `docker-compose`, no process supervision. |
| **Synthetic training data** | The ML model is a demonstration artefact and is not fit for pricing real devices. |
| **Admin list endpoints unpaginated** | Admin views load whole tables. Fine at demo scale, not at real volume. |

## 3. Environment variables required in production

`backend/.env` is loaded automatically at startup, and real environment variables
always take precedence over it. At minimum:

| Variable | Requirement in production |
| --- | --- |
| `JWT_SECRET_KEY` | **Mandatory.** A long random value from a secret manager, never a file in the repo and never a default. Rotating it invalidates all issued tokens. |
| `CORS_ORIGIN_PRODUCTION` | The exact deployed frontend origin, including the scheme. Added to the allowlist; development origins are always retained so this cannot break local development. |
| `DATABASE_PATH` or `DATABASE_URL` | Point at the real database file. Relative paths are anchored to `backend/`, not the working directory. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Short (e.g. 15–30) once refresh tokens exist. |

Optional, with their current defaults:

| Variable | Default | Purpose |
| --- | --- | --- |
| `CORS_ORIGINS` | dev origins | Full allowlist override. Replaces the built-in development origins, so list them too if local development must keep working. |
| `SMARTCYCLE_DATA_DIR` | `data` | Where the dataset, model and metrics live. |
| `VALUATION_MODEL_PATH` | `data/valuation_model.joblib` | Trained pipeline. Absent ⇒ rule-based fallback. |
| `VALUATION_MODEL_METRICS_PATH` | `data/valuation_model_metrics.json` | Metrics shown in the admin workspace. |
| `VALUATION_DATASET_PATH` | `data/valuation_demo_dataset.csv` | Synthetic training data. |
| `SMARTCYCLE_ENV_FILE` | `backend/.env` | Load configuration from a different file. |

### SQLite in detail — read this before deploying

SQLite is the single largest blocker, and the constraint is technical rather
than a matter of polish:

- **Single writer.** Only one process may write at a time. It cannot safely back
  more than one application instance, and `--workers > 1` is not safe.
- **One local file.** Most container platforms and all serverless platforms use
  an **ephemeral filesystem**. Every redeploy, restart or scale event can
  **destroy every user, device and pickup record** unless a persistent volume is
  explicitly mounted and backed up.
- **Network filesystems are unsupported** (NFS and many shared volumes), because
  file locking cannot be relied upon.
- **No migration tool** and **no backup mechanism** ship with the project.
- **No soft delete**, so there is no recovery path from an accidental deletion.

For anything beyond a single local instance, replace SQLite with a
client-server database (PostgreSQL is the usual choice) and introduce a real
migration tool. The path configuration in this project is deliberately
CWD-independent, so the change is a URL, a driver and a migration - not a
rewrite.

## 4. Backend start command

Development:

```bash
cd backend
source .venv/bin/activate
export JWT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
uvicorn app.main:app --reload --port 8000
```

A production-shaped command (still not a deployment):

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

`--workers 1` is deliberate: SQLite does not handle concurrent writers well.
Raising the worker count requires a different database first.

`--reload` must never be used outside development.

## 5. Frontend build command

```bash
cd frontend
npm ci
npm run build      # emits static files into frontend/dist/
npm run preview    # local check of the production bundle
```

`frontend/dist/` is fully static and can be served by any web server or CDN.

Two production-only notes:

1. The API base URL is baked in at **build** time from `VITE_API_URL`. Rebuild
   the bundle to change targets; there is no runtime override.
2. With `VITE_API_URL` unset, a production build sends API calls to the **same
   origin** as the page. No localhost address is ever baked into a production
   bundle; the development fallback is eliminated at build time. Set
   `VITE_API_URL` when the API is on a different host.
3. `npm run preview` serves on port 4173, which is **not** a built-in
   development origin. Add it to `CORS_ORIGINS` if you want to test a production
   bundle against a local API, otherwise the browser blocks the requests.

## 6. Database setup

1. Provide `DATABASE_URL`.
2. Start the API once. `init_db()` runs on startup and creates any missing
   tables, then applies the idempotent column additions.
3. Create the first admin from a shell on the server, never over HTTP:

   ```bash
   cd backend
   python -m app.scripts.create_admin --email you@example.com --name "Your Name"
   ```

4. Back up the database file on a schedule. There is no built-in backup.

If the database is ever reset, every user, device and pickup record is lost.
There is no soft-delete and no export.

## 7. ML model setup

Training is a **manual** step and is never triggered by an API request:

```bash
cd backend
python -m app.scripts.train_valuation_model
```

This writes `valuation_model.joblib` plus a metrics sidecar. Behaviour:

- Model present ⇒ valuations are labelled `valuation_method: "ml"`.
- Model absent, unreadable or returning an unusable number ⇒ automatic,
  silent fallback to the rule-based estimator, labelled `"rule_based"`.

The pipeline is cached in memory on first use, so **retraining requires an API
restart** to take effect.

The model is intentionally not committed (see `.gitignore`); run the command
above after cloning. Shipping real pricing would additionally require real
training data, which this project does not have.

## 8. Production CORS

- `allow_origins` is an explicit list. A wildcard is never used, and
  `CORS_ORIGINS='*'` is **discarded with a warning** rather than forwarded.
- `allow_credentials=True` is set. A browser rejects
  `Access-Control-Allow-Origin: *` alongside credentials, and allowing every
  origin would let any site make authenticated requests on a user's behalf.
- Development origins are built in and **always retained**, so a
  production-only setting can never break local development.
- Add the deployed origin with `CORS_ORIGIN_PRODUCTION`. Multiple origins are
  comma-separated.
- `CORS_ORIGINS` replaces the whole list, development origins included.
- Add the scheme: `https://app.example.com`, not a bare host.
- Do not add the API's own origin unless the API also serves the frontend.
- The frontend origin and this allowlist must agree; a mismatch is blocked by
  the browser and shows up as a missing `Access-Control-Allow-Origin` header.

## 9. Production secret handling

- Secrets come from the process environment or the platform's secret manager
  (for example a mounted file, or the platform's encrypted configuration).
- `.env` is git-ignored. `.env.example` holds placeholders only.
- `JWT_SECRET_KEY` must never be committed, logged, echoed, or included in an
  error message. The app raises a clear error and refuses to issue tokens when
  it is unset, rather than falling back to a default.
- Rotate by setting a new value and restarting; all existing tokens stop working.
- The ML model and dataset are not secrets, but the dataset is synthetic and
  should stay clearly labelled as such.

## 10. Suggested order of work before a real launch

1. Move off SQLite and introduce Alembic migrations.
2. Replace the `localStorage` token with `HttpOnly` cookie sessions plus
   refresh-token rotation and server-side revocation.
3. Add rate limiting to authentication endpoints.
4. Enforce HTTPS and add HSTS, `X-Content-Type-Options`, and a CSP.
5. Add structured logging, error tracking and uptime monitoring.
6. Add pagination to the admin list endpoints.
7. Add CI running `npm run build` and the backend test suite on every push.
8. Replace the synthetic dataset with real, lawfully obtained pricing data —
   and only then treat valuations as anything more than a demonstration.
