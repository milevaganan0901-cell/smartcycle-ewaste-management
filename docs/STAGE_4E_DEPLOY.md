# Stage 4E — Cloud deployment preparation

> **Nothing has been deployed.** No repository has been pushed, no hosting
> account created, and no service is publicly reachable. This document records
> the hosting decision and the exact manual steps required to deploy.

---

## 1. Hosting decision (free, no payment, no credit card)

Free tiers were checked for current terms rather than assumed. Two options were
**rejected on evidence**:

| Rejected | Why |
| --- | --- |
| **Render free PostgreSQL** | Free Postgres instances **expire 30 days after creation**, after which the data is deleted. Unusable as a real database. |
| **Koyeb free tier** | Following the February 2026 Mistral acquisition, **new users can no longer sign up for the free Starter tier**. The entry point is now a paid Pro plan. |

### Chosen

| Layer | Platform | Plan | Credit card | Verified terms |
| --- | --- | --- | --- | --- |
| Frontend | **Vercel** | Free (Hobby) | Not required | Free static hosting with automatic Vite framework detection and SPA rewrites |
| Backend | **Render** | Free web service | Not required for the free path | $0; 512 MB RAM, 0.1 CPU; spins down after 15 min idle; ~1 min cold start; 750 instance hours/month; 25 GB bandwidth |
| Database | **Neon** | Free | Not required | **Permanent** (not a trial); 0.5 GB storage; 100 CU-hours/month; scales to zero after 5 min idle; standard `postgresql://` connection string |

**Why this combination:** all three are genuinely free without a card, Neon is
the only surveyed provider whose free database is permanent rather than
expiring, and Vercel + Render + Neon needs **no code change** — the existing
`DATABASE_URL` variable already selects the engine, and the frontend already
reads `VITE_API_URL` at build time.

**Why not deploy the frontend from Render too?** It would work, but separating
the static SPA onto Vercel gives a CDN, preview deployments per push, and
automatic SPA history fallback without configuration.

## 2. Code changes made in this stage

PostgreSQL support only. Local development is unchanged and still uses SQLite.

| File | Change |
| --- | --- |
| `app/core/config.py` | Added `ENVIRONMENT` / `IS_PRODUCTION` and `IS_SQLITE`. `DATABASE_URL` is now documented and passed through for any scheme; SQLite paths are still anchored to `backend/`. |
| `app/db/session.py` | Engine creation branches on `IS_SQLITE`. SQLite keeps `check_same_thread: False` and the foreign-key pragma. Hosted databases get `pool_pre_ping`, `pool_recycle=300`, `pool_size=5`, `max_overflow=5` — settings chosen because free tiers scale to zero and drop idle connections. |
| `app/api/routers/health.py`, `app/schemas/health.py` | Health now reports `version`, `environment` and the database **engine name** only. It never exposes a host, database name, username or password. |
| `requirements.txt` | Added `psycopg[binary]`. SQLAlchemy 2.x maps a bare `postgresql://` URL to psycopg 3, which is the driver that makes a provider-supplied string work unedited. `psycopg2` alone would have raised `ModuleNotFoundError`. |
| `.env.example` | Documented `ENVIRONMENT` and the PostgreSQL `DATABASE_URL` form. |

No model was rewritten. The models were checked against the PostgreSQL dialect
and already compile cleanly: `SERIAL` primary keys, `VARCHAR(n)`, `BOOLEAN`,
`FLOAT`, `DATE`, `TIMESTAMP WITH TIME ZONE`, the `CHECK` constraint, and both
`ON DELETE SET NULL` / `ON DELETE CASCADE` rules. No SQLite-only type is used
anywhere, and no `AUTOINCREMENT`, `PRAGMA` or `sqlite_master` token reaches the
PostgreSQL DDL.

Verified: 122/122 tests still pass, local development still resolves to
SQLite, and a `postgresql://` URL selects the psycopg dialect with the correct
pool settings and no SQLite-only `connect_args`.

## 3. Environment variables for the deployed services

Set these in each platform's dashboard. **Never commit real values.**

### Backend (Render)

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | The Neon connection string, including `?sslmode=require` |
| `JWT_SECRET_KEY` | A freshly generated 48+ byte random value |
| `CORS_ORIGIN_PRODUCTION` | The deployed Vercel URL, e.g. `https://smartcycle-ewaste.vercel.app` |
| `ENVIRONMENT` | `production` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` (or lower) |
| `PYTHON_VERSION` | `3.12.8` (or whichever the build log confirms) |

Render build and start commands:

```
Build Command:  pip install -r requirements.txt && python -m app.scripts.train_valuation_model
Start Command:  uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Training during the build is what makes ML valuation work on a free tier:
Render wipes local files on redeploy, so the model would otherwise be absent
and every valuation would fall back to the rules. Omitting the training command
is a valid, supported choice — the app just reports `rule_based`.

### Frontend (Vercel)

| Variable | Value |
| --- | --- |
| `VITE_API_URL` | The deployed Render URL, e.g. `https://smartcycle-api.onrender.com` |

Framework preset **Vite**, build command `npm run build`, output directory
`dist`. `VITE_API_URL` is inlined at build time, so changing the API URL means
redeploying the frontend.

## 4. After the first admin is needed

There is deliberately **no public admin-registration endpoint and no hardcoded
admin credential.** From a shell on the Render service (or locally against the
same database):

```bash
python -m app.scripts.create_admin --email you@example.com --name "Your Name"
```

The script prompts for a password interactively, so nothing is typed into a
shell history or a log.

## 5. Real free-tier limitations to expect

These are genuine and will be visible to anyone using the deployed site.

1. **Cold starts.** Render spins down after 15 minutes idle and needs roughly a
   minute to wake. The first visitor after a quiet period waits. Neon scales to
   zero after 5 minutes, adding a few hundred milliseconds.
2. **The ML model is rebuilt on every deploy**, and the filesystem is wiped
   between deploys, so the model exists only for the life of that build.
3. **0.5 GB database.** Ample for a portfolio project; not for real traffic.
4. **750 backend instance hours per month.** One always-on service would consume
   roughly 720, so a second service on the same workspace would exhaust it.
5. **No persistent disk on the free backend tier.** Anything written to the
   filesystem outside the database is lost on redeploy — this is exactly why the
   database is PostgreSQL rather than SQLite.
6. **Free-tier instances may be resource-limited or throttled** by the provider
   under load. This is not a production deployment and should not be described
   as one.
7. **No custom domain** on the free tiers, so the URLs stay on
   `*.vercel.app` and `*.onrender.com`. A custom domain is a paid add-on on
   both providers and was deliberately not purchased.
