# Stage 4D — Git hygiene, security audit, regression verification

No application behaviour, UI or ML approach changed in this stage. The work was
repository preparation, a security audit, a full regression run, a build check
and deployment planning.

**No database was reset.** No user, device or pickup record was deleted.

---

## 1. Security audit (performed before recommending any push)

The rule for this stage was that if anything dangerous were found, work would
stop and be reported rather than a push recommended. **Nothing dangerous was
found.** The audit was run against the *staged* content, not the working tree,
because that is what would actually be published.

### Secrets — by category, never by value

| Category checked | Result |
| --- | --- |
| Hardcoded `JWT_SECRET_KEY` | **None.** The only two matches in the repository are shell commands that *generate* a secret at runtime via `secrets.token_urlsafe(48)` |
| API keys / access tokens / client secrets | **None** |
| Cloud token shapes (`AKIA…`, `ASIA…`, `ghp_…`, `github_pat_…`, `sk-…`, `AIza…`, `xox…`) | **None** |
| PEM / RSA / OpenSSH private key blocks | **None** |
| Long high-entropy base64-like literals in tracked source | **None** (matches were documentation file paths) |
| Real password hashes (Argon2) | **None.** Two documentation mentions were checked programmatically against all 68 live database hashes — both are illustrative (`$argon2id$v=19$m=65536,...` and a bare `$argon2id$` prefix in a verification table) |
| Personal email domains (gmail, yahoo, hotmail…) | **None.** The only addresses present use `example.com` |
| Machine-specific absolute paths in tracked files | **None** |
| Passwords in tracked source | One test fixture, `TestSuite123!` in `app/scripts/run_api_tests.py`, with an inline comment explaining it is a throwaway for randomly-stamped throwaway accounts. Every admin password used during development was confirmed absent from all tracked files |
| Unsafe HTML injection (`dangerouslySetInnerHTML`, `innerHTML`) | **None** |
| External image/CDN dependencies | **None** — all visuals are inline SVG |

### `.env` protection

`backend/.env` exists locally and contains a real locally-generated development
secret. It is **ignored** by `.gitignore:33` (`.env`), verified with
`git check-ignore -v`. The value in it was additionally searched for across all
staged blobs and is **not present in any file that would be committed**.

The `.env.example` templates are committed and contain placeholders only.

### Deliberate decisions on files that could have leaked

| File | Size | Decision | Why |
| --- | --- | --- | --- |
| `backend/.env` | 8 KB | **Excluded** | Holds a real local secret. Ignored, verified. |
| `backend/smartcycle.db` | 128 KB | **Excluded** | Holds 68 real accounts with Argon2 hashes, plus device submissions containing names, email addresses, street addresses and locations. Committing it would publish personal data and a credential database. The schema is recreated automatically on first start. |
| `backend/data/valuation_model.joblib` | 1.1 MB | **Excluded** | A regenerable binary derived entirely from the committed dataset. One command rebuilds it. |
| `frontend/dist/` | — | **Excluded** | Build output, reproducible with `npm run build`. |
| `node_modules/`, `.venv/`, `__pycache__/` | — | **Excluded** | Standard. |
| `backend/data/valuation_demo_dataset.csv` | — | **Committed** | The provenance record for the model. Synthetic, small, human-readable. |
| `backend/data/valuation_model_metrics.json` | — | **Committed** | Small, readable, and what the admin panel displays. |

## 2. Repository

Initialised locally with a single commit on branch `main`. 92 tracked files.
Working tree clean.

**No remote was configured and nothing was pushed.** Verified: `git remote -v`
returns empty and the reflog contains exactly one entry (the initial commit).
No GitHub repository was created, and no credentials, tokens or keys were
requested or used at any point.

## 3. One minimal fix

`GET /health` and `GET /api/v1/health` reported `"stage": "stage-3g"` — a label
stale since Stage 3G, and misleading in a health check used to identify a
deployed instance. The field now reports `app.version`, matching the root
endpoint that Stage 3J already fixed.

```
before: {"status":"ok","service":"SmartCycle API","stage":"stage-3g"}
after:  {"status":"ok","service":"SmartCycle API","version":"1.0.0"}
```

This is the only application change in Stage 4D. `docs/STAGE_3J.md` still
mentions the old `stage` value as a historical record of the Stage 3J fix; that
was deliberately left intact.

## 4. Regression verification (29 checks, real API, real database)

Full user and admin journeys through the running backend:

- **User:** register → login → dashboard → sell device → ML valuation
  (₹54,359.22 via `ml`) → tracking ID `EW-2026-0085` → track device → pickup
  request → owner sees it.
- **Admin:** login → dashboard (69 users / 85 devices / 52 pickups) → device
  status update → pickup status update.
- **Persistence and propagation:** owner dashboard and Track Device both reflect
  the admin's status changes.
- **Authorization:** normal user `403` on all five admin endpoints and on the
  full device list; anonymous `401`.
- **Ownership isolation:** User B cannot see A's devices, cannot read A's pickup
  by id (`404`), cannot craft a pickup for A's device (`404`), cannot delete
  A's device (`403`); A's device survived every attempt.
- **API documentation:** `/openapi.json` serves 20 paths with the `HTTPBearer`
  scheme declared on 16 operations; `/docs` (Swagger UI) and `/redoc` both
  return 200; `/api/v1/health` responds.
- **No tracebacks and no 5xx** in the backend log.

The existing suite was also re-run: **122/122 passing**.

## 5. Portability verification

The backend was started the way a production host would run it — **environment
variables only, no `.env` file, from an unrelated working directory**, with the
database and ML data pointed elsewhere:

- Health, root, `/docs` all responded correctly.
- `CORS_ORIGIN_PRODUCTION=https://app.example.com` was reflected, and the
  development origin remained allowed.
- The database was created at the configured `DATABASE_PATH`, not inside the
  repository.
- The ML model loaded from the configured `SMARTCYCLE_DATA_DIR` and produced a
  real ML valuation on a fresh database (`EW-2026-0001`, ₹46,005.56 via `ml`).
- The `create_admin` CLI worked against that fresh database.

This confirms the application does not depend on a particular checkout path or
on the local `.env`.

## 6. Build verification

- `npm run build` — 69 modules, 318.65 kB JS (90.00 kB gzip), 62.11 kB CSS.
  **No warnings, no errors.**
- `npm audit --audit-level=high` — **0 vulnerabilities**.
- No `127.0.0.1` or `:8000` anywhere in the built output. (The single remaining
  `localhost` string is react-router's internal location sentinel, not project
  configuration.)
- Backend compiles and starts cleanly.

## 7. Documentation

- `docs/STAGE_4E_PLAN.md` — **new.** The concrete cloud deployment decisions:
  frontend hosting, backend hosting, database persistence, ML artifact delivery,
  environment variables to set, CORS origin, public URLs, HTTPS and custom
  domain, plus the manual GitHub steps.
- `docs/STAGE_4D.md` — **new.** This file.
- `README.md` — documentation table updated to link both, and the Deployment
  Preparation section now states that the repository is ready to publish and
  that creating the repo and pushing are deliberately left to the reader.

## 8. Not done, deliberately

- No GitHub repository created, no remote added, nothing pushed.
- No hosting accounts created or contacted.
- No deployment of any kind.
- No credentials, tokens, API keys or SSH keys requested, generated or used.
- No application features added.
