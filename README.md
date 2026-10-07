# SmartCycle — Smart E-Waste Management System

> **Give your old electronics a second life.**

SmartCycle is a full-stack web application for responsible collection,
refurbishment and recycling of used electronics. A user submits a device, gets an
estimated value back, receives a tracking ID, and can book a doorstep pickup. An
administrator reviews submissions, drives device and pickup statuses forward, and
watches platform-wide statistics.

Built with **React + Vite** on the front end and **FastAPI + SQLAlchemy +
SQLite** on the back end, with JWT authentication and a scikit-learn valuation
model that falls back to a transparent rule-based estimator.

> **Read this first.** The ML model is trained on a **synthetic demonstration
> dataset**, not on real market prices. Every value the application shows is an
> **estimate for demonstration purposes**, never a guaranteed or exact market
> price. See [Limitations](#limitations--what-this-is-not).

---

## Table of contents

- [Problem statement](#problem-statement)
- [Objectives](#objectives)
- [Features](#features)
- [Technology stack](#technology-stack)
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Database design](#database-design)
- [API overview](#api-overview)
- [Device valuation: ML with a rule-based fallback](#device-valuation-ml-with-a-rule-based-fallback)
- [The SmartCycle valuation model](#the-smartcycle-valuation-model)
- [Authentication and authorization](#authentication-and-authorization)
- [Installation](#installation)
- [Environment variables](#environment-variables)
- [Running the project](#running-the-project)
- [Testing](#testing)
- [Sample demo workflow](#sample-demo-workflow)
- [Documentation](#documentation)
- [Limitations — what this is not](#limitations--what-this-is-not)
- [Future improvements](#future-improvements)
- [Deployment Preparation](#deployment-preparation)

---

## Problem statement

Electronic waste is growing faster than the channels designed to handle it.
Discarded phones, laptops and monitors usually end up in general bins or
informal recycling, where recoverable material — gold, copper, cobalt, rare earths
— is lost and hazardous substances leak into soil and water.

Two things make this hard for an individual household:

1. **Nobody knows what a device is worth.** Resale value is opaque. Owners
   cannot judge an offer, and they often default to throwing the device away
   rather than dealing with the uncertainty.
2. **Getting it collected is friction.** Finding a recycler, arranging a
   drop-off, and missing a working-hour window all add up. Most people never
   start the process.

SmartCycle addresses both: an instant, explainable estimate removes the price
uncertainty, and a tracked doorstep pickup removes the effort.

## Objectives

- Give an owner an **immediate, honest estimate** for a used device, plus
  separate refurbishment and recycling figures.
- Make the device's journey **trackable** with a tracking ID that works without
  an account.
- Let an owner **request a pickup** and follow its status.
- Give an administrator **real operational data** — users, devices, pickups and
  status counts — and the ability to move both device and pickup lifecycles
  forward.
- Enforce **ownership and role boundaries on the server**, never only in the UI.
- Degrade **gracefully**: if the ML model is missing or unusable, the app keeps
  valuing devices with the rule-based estimator instead of failing.

## Features

### Public

| Page | What it does |
| --- | --- |
| **Home** | Marketing overview, how the process works, demonstration impact metrics |
| **Sell Device** | Full device submission form with validation; returns the estimated, refurbished and recycled values and the tracking ID |
| **Track Device** | Look up any device by tracking ID and follow its status timeline |
| **How It Works** | The four-step process explained |
| **About** | Project background |
| **Contact** | Static contact information (form is front-end only) |
| **Login / Register** | Real authentication against the backend |

### Authenticated (any user)

| Page | What it does |
| --- | --- |
| **User Dashboard** | The signed-in user's own profile, device count, total estimated value, device table and pickup table — all from the database |
| **Request Pickup** | Pickup form scoped to the user's own devices |

### Admin only

| Page | What it does |
| --- | --- |
| **Admin Dashboard** | Real aggregate statistics, user list, device list with status filters and inline status controls, pickup list with status controls, and ML model status with evaluation metrics |

Every admin surface is protected in the **backend**. Hiding a nav link is a
usability convenience, not a security control.

## Technology stack

### Frontend

| Technology | Version | Why |
| --- | --- | --- |
| React | 18.3 | Component model for a multi-page app |
| react-router-dom | 7.18 | Client-side routing and route guards |
| Vite | 6.1 | Fast dev server and production bundling |

No UI framework — the stylesheet is hand-written CSS, so there is no design-system
dependency to learn or to break.

### Backend

| Technology | Version | Why |
| --- | --- | --- |
| FastAPI | latest | Typed, async-ready, automatic OpenAPI docs |
| SQLAlchemy | 2.x | ORM with a real session/transaction model |
| SQLite | stdlib | Zero-setup local database |
| PyJWT | latest | Signed access tokens |
| pwdlib[argon2] | latest | Argon2 password hashing |
| scikit-learn | latest | `RandomForestRegressor` valuation pipeline |
| uvicorn | latest | ASGI server |

## Architecture

Two flows matter. Both are worth being able to explain in a viva.

### Flow 1 — React → FastAPI → SQLAlchemy → SQLite

```
Browser
  │  React single-page app (Vite dev server / static build)
  │  fetch() with Authorization: Bearer <JWT>
  ▼
FastAPI (uvicorn)
  │  CORSMiddleware — explicit origin allowlist
  │  router → Depends(get_current_user / get_current_admin)
  │  Pydantic schema validates the request body
  ▼
SQLAlchemy ORM
  │  request-scoped Session, filtered by the authenticated user's id
  ▼
SQLite file (backend/smartcycle.db)
```

Key properties:

- The browser never sends a `user_id` or a role. Ownership is derived from the
  **validated JWT subject**, looked up in the database on every request. A user
  cannot become an admin by editing a request.
- One session per request, created by `get_db()` and always closed.
- Queries are filtered at the database level (`WHERE user_id = :current_user`),
  never by filtering full tables in Python.

### Flow 2 — device data → valuation service → ML model → rule-based fallback

```
POST /api/devices  (device attributes)
  │
  ▼
services/valuation.py :: value_device()          ← single entry point
  │
  ├─► services/ml_valuation.py :: predict_estimated_value()
  │     ├─ loads the cached pipeline (once, thread-safe)
  │     ├─ predicts a dimensionless depreciation RATIO
  │     ├─ ratio × reference price  →  rupee value
  │     └─ rejects anything non-finite or negative → returns None
  │
  │   ratio usable? ── yes ──► valuation_method = "ml"
  │        │
  │        no  (model missing / corrupt / NaN / negative / raised)
  │        ▼
  └─► services/valuation.py :: estimate_device_value()
            transparent rules: reference price
            × age depreciation × condition × working status × damage
            (floored at a minimum so scrap still has value)
        │
        ▼
   valuation_method = "rule_based"
  │
  ▼
refurbished and recycled values derived from whichever base value was chosen
  │
  ▼
stored on the device row, returned to the client, and displayed
  └─ the UI always shows WHICH method produced the number
```

**Why a ratio and not a rupee amount?** The app's valuation is *multiplicative*
in the reference price. A tree cannot extrapolate to a rupee target far outside
its training range, so the model learns the shape of the depreciation curve and
the rule-based reference value supplies the scale. Both paths therefore mean the
same thing, and the fallback is a genuine substitute rather than a different
quantity.

**Refurbished and recycled** are derived from whichever base value was produced,
using the project's own fixed factors, so the two paths stay consistent.

## Project structure

```text
smart-ewaste-management/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py                 get_current_user / get_optional_current_user /
│   │   │   │                            get_current_admin — the security boundary
│   │   │   └── routers/
│   │   │       ├── health.py            liveness endpoint
│   │   │       ├── auth.py              register, login, me
│   │   │       ├── devices.py           submit, look up by tracking ID, admin list,
│   │   │       │                        status update (admin), delete (admin)
│   │   │       ├── users.py             the signed-in user's own devices
│   │   │       ├── pickup.py            create / list / read own pickups
│   │   │       └── admin.py             admin statistics, users, devices, pickups,
│   │   │                                status updates, model status
│   │   ├── core/
│   │   │   ├── config.py                every tunable, read from the environment
│   │   │   └── security.py              Argon2 hashing, JWT create/decode
│   │   ├── db/
│   │   │   ├── base.py                  declarative base
│   │   │   └── session.py               engine, session factory, get_db, init_db,
│   │   │                                SQLite foreign-key pragma
│   │   ├── models/                      SQLAlchemy models: user, device, pickup
│   │   ├── schemas/                     Pydantic request/response models
│   │   ├── scripts/
│   │   │   ├── create_admin.py          CLI: create or promote an admin
│   │   │   ├── train_valuation_model.py CLI: manual, deterministic ML training
│   │   │   └── run_api_tests.py         dependency-free test suite
│   │   ├── services/
│   │   │   ├── valuation.py             rule-based estimator + ML-first entry point
│   │   │   ├── ml_valuation.py          lazy, thread-safe model loading + prediction
│   │   │   └── tracking.py              tracking ID generation
│   │   └── main.py                      app factory, CORS, router registration
│   ├── data/
│   │   ├── README.md                    dataset provenance and honesty notes
│   │   ├── valuation_demo_dataset.csv   900 SYNTHETIC rows (committed)
│   │   ├── valuation_model.joblib       trained pipeline (NOT committed — regenerate)
│   │   └── valuation_model_metrics.json evaluation metrics (committed)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/client.js                every API call in one place
│   │   ├── auth/authStorage.js          JWT persistence
│   │   ├── components/                  layout, header, footer, badges, timeline,
│   │   │                                metric cards, route guards, icons
│   │   ├── context/AuthContext.jsx      session state
│   │   ├── data/demoData.js             marketing-page copy and demonstration metrics
│   │   ├── pages/                       one file per route
│   │   ├── App.jsx                      routes
│   │   ├── main.jsx                     entry point
│   │   └── styles.css                   all styling
│   ├── .env.example
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── docs/
│   ├── DEPLOYMENT.md                    what deployment would require
│   └── STAGE_*.md                       per-stage implementation notes
├── .gitignore
└── README.md
```

## Database design

Three tables. SQLite file at `backend/smartcycle.db`, created on startup.

```
┌──────────────┐              ┌──────────────────┐              ┌───────────────────┐
│    users     │              │     devices      │              │  pickup_requests  │
├──────────────┤              ├──────────────────┤              ├───────────────────┤
│ id      PK   │──┐           │ id           PK  │──┐           │ id            PK  │
│ name         │  │           │ tracking_id  UQ │  │           │ user_id       FK  │
│ email    UQ  │  │           │ user_id      FK │  └──────────▶│ device_id     FK  │
│ password_hash│  │           │ device_category │              │ pickup_address    │
│ role         │  │           │ brand           │              │ preferred_date    │
│ is_active    │  └──────────▶│ model           │              │ preferred_time_   │
│ created_at   │  SET NULL    │ age             │              │   slot           │
└──────────────┘  on delete   │ condition       │              │ status           │
                              │ working_status  │              │ created_at       │
   role: "user" | "admin"      │ physical_damage │              │ updated_at       │
   (no HTTP path to "admin")   │ accessories     │              └───────────────────┘
                              │ original_purchase_price              ON DELETE CASCADE
                              │ location         │
                              │ estimated_purchase_value
                              │ potential_refurbished_value
                              │ potential_recycled_value
                              │ valuation_method  "ml" | "rule_based"
                              │ status            lifecycle value
                              │ created_at / updated_at
                              └──────────────────┘
```

Design notes:

- **`devices.user_id` is `ON DELETE SET NULL`** — a device record survives an
  account being removed, preserving the valuation history. Legacy rows created
  before ownership existed have `user_id = NULL`.
- **`pickup_requests` cascades** from both `users` and `devices`, so a pickup can
  never outlive what it refers to.
- **Foreign keys are actually enforced.** SQLite ignores `ondelete` unless
  `PRAGMA foreign_keys=ON` is set per connection, which `app/db/session.py` does.
  `PRAGMA foreign_key_check` reports clean.
- **No Alembic.** `init_db()` creates missing tables and applies a small number
  of idempotent `ADD COLUMN` migrations. It cannot express renames, drops or data
  migrations — see [Limitations](#limitations--what-this-is-not).
- The trained model is **not** in the database. It is a file on disk, loaded
  lazily.

## API overview

Interactive documentation with a working **Authorize** button is served at
`/docs` (Swagger UI) and `/redoc`.

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/` | public | Service identification |
| `GET` | `/health`, `/api/v1/health` | public | Liveness |
| `POST` | `/api/auth/register` | public | Create an account (role always `"user"`) |
| `POST` | `/api/auth/login` | public | Returns a bearer token |
| `GET` | `/api/auth/me` | authenticated | The current user |
| `POST` | `/api/devices` | authenticated | Submit a device; returns the valuation and tracking ID |
| `GET` | `/api/devices/{tracking_id}` | public | Look up one device by tracking ID (Track Device) |
| `GET` | `/api/devices` | **admin** | List all devices, optional status filter |
| `PATCH` | `/api/devices/{tracking_id}/status` | **admin** | Update a device status |
| `DELETE` | `/api/devices/{tracking_id}` | **admin** | Delete a device and its pickups |
| `GET` | `/api/users/me/devices` | authenticated | The current user's own devices |
| `POST` | `/api/pickups` | authenticated | Request pickup for an **owned** device |
| `GET` | `/api/pickups/my` | authenticated | The current user's own pickups |
| `GET` | `/api/pickups/{pickup_id}` | authenticated | One **owned** pickup |
| `GET` | `/api/admin/dashboard` | **admin** | Aggregate statistics |
| `GET` | `/api/admin/users` | **admin** | All users |
| `GET` | `/api/admin/devices` | **admin** | All devices |
| `GET` | `/api/admin/pickups` | **admin** | All pickups |
| `PATCH` | `/api/admin/devices/{device_id}/status` | **admin** | Update a device status |
| `PATCH` | `/api/admin/pickups/{pickup_id}/status` | **admin** | Update a pickup status |
| `GET` | `/api/admin/valuation-model` | **admin** | Model availability and metrics |

Status codes are used deliberately:

| Code | Meaning here |
| --- | --- |
| `400` | Duplicate email at registration |
| `401` | Missing, malformed, expired or wrongly signed token |
| `403` | Authenticated, but the admin role is required |
| `404` | Not found — **also** used for another user's record, so ownership is not confirmed to a stranger |
| `409` | A pickup already exists for this device |
| `422` | Validation failed; the response names the offending fields |
| `500` | Database error, with a generic message and details logged server-side only |

No response ever contains a stack trace, a file path, a database credential, a
JWT secret or a password hash.

## Device valuation: ML with a rule-based fallback

> Full detail, including the dataset audit, model comparison and baseline
> numbers, is in [The SmartCycle valuation model](#the-smartcycle-valuation-model).

### The rule-based estimator

Transparent, deterministic, and the original estimator - **unchanged** since
Stage 3A:

```
reference = original_purchase_price, or the category reference value if absent
value     = max(500,
                reference
                x max(0.25, 0.88 ** age)     # 12% per year, floored at 25%
                x condition factor           # excellent 1.10 ... not working 0.22
                x working-status factor      # fully working 1.00 ... not working 0.30
                x damage factor)             # none 1.00 ... cracks 0.68

refurbished = max(500, value x 1.25 or 1.05) # 1.25 only if usable and not poor
recycled    = max(500, value x 0.08)
```

### Which model is this? (read this first)

Two model generations exist in this repository, and they are **not** comparable.
Confusing them is the single easiest way to misread this README.

| | **ML Valuation v2** | **Previous shipped model** |
| --- | --- | --- |
| Status | **Local only — NOT deployed to production** | **Currently running in production** |
| Estimator | `RandomForestRegressor(n_estimators=300, max_depth=12, min_samples_leaf=2, random_state=42)` | `GradientBoostingRegressor(n_estimators=500, max_depth=4, learning_rate=0.05)` |
| Training data | 900-row synthetic dataset, generated **independently** of the rule-based formula | 420-row synthetic dataset, generated **from** the rule-based formula |
| Holdout MAE | **Rs 1,656.43** | Rs 822.12 |
| Where documented | [ML Valuation v2 — local synthetic-development benchmark](#ml-valuation-v2--local-synthetic-development-benchmark) | [Previous shipped model / historical baseline](#previous-shipped-model--historical-baseline) |

**Neither MAE is a production metric, and neither is comparable to the other.**
They were trained on different data, different targets and different algorithms.
The v2 MAE is *higher* not because the model got worse but because it was stopped
from being handed the answer: the v1 dataset's target was computed from the very
rule-based formula the model is compared against, so a low error there mostly
measures formula reproduction. The v2 dataset was generated independently, so its
error measures how well the model fits a generator whose assumptions are
synthetic. **Neither figure is real-market validation of any kind.**

### The ML pipeline

Applies to both generations; the estimator differs as tabulated above.

- A scikit-learn ensemble inside a `ColumnTransformer` with `SimpleImputer` +
  `OneHotEncoder(handle_unknown="ignore")`.
- Predicts a **depreciation ratio**; the ratio is multiplied by the same
  reference value the rules use.
- Loaded lazily on first use, cached in memory behind a lock - **not** reloaded
  per prediction. Retraining therefore needs an API restart.
- Reproducible: `random_state=42`, `test_size=0.2`, and 5-fold cross-validation
  for model selection.
- The saved artifact also records the **training distribution**, so a submission
  outside it is handed to the rules rather than given a flat, wrong ML number.

### Previous shipped model / historical baseline

The figures in this subsection describe the **previously shipped** model, which
is what production runs today. They are retained for historical comparison only.
For the current local work see
[ML Valuation v2](#ml-valuation-v2--local-synthetic-development-benchmark).

- Estimator: `GradientBoostingRegressor(n_estimators=500, max_depth=4,
  learning_rate=0.05)`
- Training data: the previous **420-row** synthetic dataset, whose target was
  generated from the project's **own rule-based formula** plus +/-7% noise
  (audited in [`backend/data/README.md`](backend/data/README.md))
- 5-fold CV selection: LinearRegression 2,317.89 · Ridge 2,279.38 ·
  RandomForestRegressor 1,321.33 · **GradientBoosting 774.14**
- Holdout (84 rows):

| Predictor | MAE | RMSE | R2 |
| --- | --- | --- | --- |
| **ML model (GradientBoosting)** | **Rs 822.12** | Rs 1,488.16 | **0.9916** |
| Baseline: mean-value predictor | Rs 10,582.17 | Rs 16,363.65 | -0.0190 |
| Baseline: **rule-based estimator** | **Rs 287.31** | Rs 585.10 | **0.9987** |

**These numbers mean very little, and the project says so everywhere.** A high
R2 on data whose target was generated from a known formula only demonstrates
that the function is learnable. It is **not** evidence of real-world accuracy,
and it is not presented as such in the UI, the API, the admin panel or the docs.

**The rule-based estimator scored better than the model on that dataset** (MAE
Rs 287.31 versus Rs 822.12) because the rules were effectively ground truth on
data derived from themselves. That result was measured, displayed in the admin
panel, and explained rather than hidden — and it is the specific reason ML v2
replaced the dataset rather than the estimator.

> **These numbers are historical.** They are **not** production metrics for the
> current code, and they are **not** comparable to the v2 figures, which come
> from different data, a different target and a different algorithm.

### The training data is synthetic

| Property | Value |
| --- | --- |
| Rows | 900 |
| Generator | `backend/app/scripts/generate_valuation_dataset.py`, fixed seed `20261007` - regenerable byte-for-byte |
| Source | Generated independently by that committed generator. **Not** scraped, **not** collected from users, and **not** derived from the rule-based valuation formula. |
| Real market data | None |
| Public dataset used instead | No - searched for, downloaded, licence-verified, and rejected on documented grounds |

### When the fallback engages

Any of the following returns the rule-based estimate, silently and automatically:

- the model file is missing
- the model file is corrupt or is not a usable pipeline
- the pipeline raises during prediction
- the predicted ratio is `NaN`, infinite, or negative
- the resulting value is not finite or is negative
- **`age` falls outside the range the model was trained on** (Stage 4B)
- **`condition`, `working_status`, `physical_damage` or `device_category` is a
  value the model never saw in training** (Stage 4B)

The response always states which path ran, via `valuation_method`
(`"ml"` or `"rule_based"`), and the UI labels the number accordingly
(*"ML Estimate"* / *"Rule-Based Estimate"*). **Training is never triggered by an
API request** - it is a manual CLI step.

## The SmartCycle valuation model

> **The current valuation model is a development/demo model trained on synthetic
> data and should not be interpreted as a production market-pricing model.**

### The problem being solved

A user submits a device. The system must return **one number** — an estimated
resale value in rupees. The alternative is a formula, and the project ships one
(seven hand-tuned multipliers). Machine learning is used to **learn that
relationship from data** rather than encode it as constants, which is the
property that matters once real transaction data replaces the demo set.

### Input features

Seven, all already collected by the Sell Device form. **No new fields were
added.**

| Feature | Type | Notes |
| --- | --- | --- |
| `device_category` | categorical | 9 app categories |
| `brand` | categorical | free text in the form |
| `age` | numeric, years | `ge=0`, no upper bound |
| `condition` | categorical | Excellent -> Not Working |
| `working_status` | categorical | Fully / Partially / Not Working |
| `physical_damage` | categorical | None / Minor scratches / Cracks |
| `original_purchase_price` | numeric | optional; missing in ~15% of rows |

Two existing fields were considered and **rejected**: `model` (free text,
effectively unique per device) and `accessories` (genuinely relevant to resale,
but absent from the dataset, so including it would mean inventing data).

### Target variable

`estimated_purchase_value`, in rupees. Two derived figures (refurbished and
recycled value) are computed from it by fixed project rules, so they stay
consistent whichever path produced the base number.

### Dataset source and type

| Property | Value |
| --- | --- |
| File | `backend/data/valuation_demo_dataset.csv` |
| Type | **Synthetic development dataset** |
| Provenance | Generated **in this repo** by the project's own rule-based formula plus uniform noise in `[0.93, 1.07]` |
| Collected from real users? | **No** |
| Scraped from a marketplace? | **No** |
| Licence | N/A - original work for this project |
| Records | **900** |
| Missing values | `original_purchase_price` only, 189 rows (21.0%) |
| Duplicates | **0** |
| Impossible values | **0** (no negative age, no non-positive price, no negative target) |
| Regenerable | Yes, byte-for-byte, via `python -m app.scripts.generate_valuation_dataset` (seed `20261007`) |

**How to read these metrics.** The dataset is synthetic, so every figure
below measures how closely the model fits the committed generator's assumptions.
It is **not** real-world accuracy.

This was deliberately changed in ML-v2. The previous 420-row dataset was
generated *from* the rule-based formula, which made that formula close to
ground truth and the model 2.9x worse than the fallback it was imitating. The
current 900-row dataset is produced by
`backend/app/scripts/generate_valuation_dataset.py` (seed `20261007`), which
does **not** import or reuse `app/services/valuation.py`. The model now has to
learn the relationship rather than reproduce a formula it was handed.

Measured data-quality audit, including the leak review and the full public
dataset search, is in [`backend/data/README.md`](backend/data/README.md).

#### A public dataset was searched for, and rejected on the record

- **UCI ML Repository** - 0 results for `e-waste`, `used device`, `resale`,
  `laptop`, `hardware price`. The only `smartphone` hits are Human Activity
  Recognition datasets, unrelated to pricing.
- **Kaggle `recell-used-devices-prices`** (CC0 Public Domain, 3,454 rows) and
  **`used-handheld-device-data`** (CC0) were downloaded, licence-verified and
  inspected. The second is the **same 3,454 records** with renamed columns, so
  one candidate rather than two.

Rejected because **five of the seven required features are absent** - including
`working_status` and `condition`, which together drive ~68% of the model - the
target is a **unitless normalised score** with no currency (converting it to
rupees would be fabrication), and it covers **2 of the app's 9 device
categories**. No citation is invented and no further scraping was done.

### Preprocessing

Reproducible inside a scikit-learn `Pipeline`, so it cannot drift between
training and serving:

- **Categorical** - `SimpleImputer(most_frequent)` then
  `OneHotEncoder(handle_unknown="ignore")`. An unseen brand or category is
  encoded neutrally instead of crashing.
- **Numeric** - `SimpleImputer(median)`, because the purchase price is optional.
- **No scaling.** Tree models are scale-invariant, so `StandardScaler` would be
  a pointless step.

### Model used, and how it was chosen

Four candidates, compared on **5-fold cross-validated MAE** - deliberately not
on the holdout, so the holdout remains an unbiased final estimate.

The **previous shipped model** selected
`GradientBoostingRegressor(n_estimators=500, max_depth=4, learning_rate=0.05)`
from these cross-validated figures:

| Model | CV MAE | CV R2 |
| --- | --- | --- |
| LinearRegression | 2,317.89 | 0.9177 |
| Ridge(alpha=1.0) | 2,279.38 | 0.9193 |
| RandomForestRegressor | 1,321.33 | 0.9516 |
| **GradientBoostingRegressor** | **774.14** | **0.9856** |

**ML v2 re-ran the identical selection process on the new dataset and picked a
different winner**, `RandomForestRegressor(n_estimators=300, max_depth=12,
min_samples_leaf=2, random_state=42)`, because GradientBoosting placed last there
(CV MAE 1,714.71 versus 1,550.00). The selection logic, the candidate set, the
hyperparameters and the split were not changed — the data was, and the ranking
followed. Full figures in
[ML Valuation v2](#ml-valuation-v2--local-synthetic-development-benchmark).

Both are standard scikit-learn ensembles — no new dependency, no deep learning.

#### Why the model predicts a ratio, not a rupee amount

The app's valuation is multiplicative in the reference price, and a **tree
ensemble cannot extrapolate** - asked for a price beyond its training range it
returns the top of that range regardless. So the model predicts a dimensionless
**depreciation ratio**, and the application multiplies it by the same reference
value the rules use. The ratio generalises across the whole price range; the
multiplication supplies the scale. Both paths mean the same thing.

### Training process

```bash
cd backend
python -m app.scripts.train_valuation_model
```

Manual and separate. Never triggered by a device submission, never at server
start. It loads the dataset, compares the four candidates by cross-validated MAE,
fits the winner on the training split, scores it once on the untouched holdout
against two baselines, then writes:

- `backend/data/valuation_model.joblib` - the pipeline plus the **training
  distribution** it was fitted on
- `backend/data/valuation_model_metrics.json` - metrics, model comparison,
  baselines, library versions, timestamp and notes

Restart the API afterwards; the pipeline is cached on first use.

### Evaluation metrics

**MAE** is the average size of the mistake in rupees - "off by about Rs 1,656 on a
typical device" for the current local model. Lower is better. **RMSE** is the
same idea but punishes large errors harder. **R2** is the share of price
variation explained; 0 means no better than guessing the average, 1 is perfect.

**These are two separate evaluations. Read the label before the number.**

#### ML Valuation v2 — local synthetic-development benchmark

**Not deployed to production.** Produced on branch `ml-valuation-v2`, local only.

- Estimator: `RandomForestRegressor(n_estimators=300, max_depth=12,
  min_samples_leaf=2, random_state=42)`
- Training data: the committed **900-row** synthetic dataset from
  `backend/app/scripts/generate_valuation_dataset.py` (fixed seed `20261007`),
  generated **independently** of the rule-based formula
- Holdout split: 180 rows (720 train / 180 test, `test_size=0.2`)

| Predictor | MAE | RMSE | R2 |
| --- | --- | --- | --- |
| **ML model (RandomForestRegressor)** | **Rs 1,656.43** | **Rs 5,892.80** | **0.5669** |
| Baseline: mean-value predictor | Rs 4,377.74 | Rs 8,959.10 | -0.0012 |
| Baseline: **rule-based estimator** | **Rs 2,358.24** | Rs 5,749.36 | 0.5877 |

#### Baseline comparison — the honest result

**On this synthetic benchmark the ML model has a lower holdout MAE than the
rule-based baseline** (Rs 1,656.43 versus Rs 2,358.24, better by Rs 701.81).
That is a reversal of the previous model's result, and it is a genuine one: the
v2 generator does not import `app/services/valuation.py`, so the rules are no
longer a restatement of the answer key and this is a real comparison between two
independent estimators rather than a model being scored against its own source.

**What that comparison does and does not establish:**

- It establishes that on this data the model captured the generator's structure,
  and that the two estimators are not equivalent.
- It establishes **nothing about real-world pricing accuracy.** The "ground
  truth" here is a synthetic generator whose half-lives, recovery values and
  price distributions are assumptions this project invented, not measurements.
  Beating a second estimator on invented data is not market validation.
- The margin is modest and the R2 comparison is actually *worse* for the model
  (0.5669 versus 0.5877). Neither model dominates the other, and MAE alone does
  not make the model "better" in any useful sense.
- Error is heavy-tailed — median roughly Rs 530, but the 99th percentile is in
  the tens of thousands — because the generator includes a small "stripped for
  parts" tail that no feature marks. That is irreducible by construction, and it
  is why RMSE sits far above MAE.

**None of these are production metrics.** They are not deployed, not measured on
real transactions, and not comparable to the previous model's figures.

#### Previous shipped model / historical baseline

Superseded by v2 and retained for comparison. **Currently running in
production**, trained on the previous 420-row dataset whose target was generated
from the rule-based formula. Held-out test split, 84 rows, rupee scale:

| Predictor | MAE | RMSE | R2 |
| --- | --- | --- | --- |
| **ML model (GradientBoosting)** | **Rs 822.12** | Rs 1,488.16 | **0.9916** |
| Baseline: mean-value predictor | Rs 10,582.17 | Rs 16,363.65 | -0.0190 |
| Baseline: **rule-based estimator** | **Rs 287.31** | Rs 585.10 | **0.9987** |

**The ML model did not beat the rule-based baseline on that dataset.** The rules
were ~2.9x more accurate here (MAE Rs 287 vs Rs 822). That is expected rather
than a defect: the target was *generated from* that formula, so the rules were
effectively ground truth on that data and no model could beat reproducing it plus
its irreducible noise. The training script printed this outcome explicitly, the
metrics sidecar recorded it, and the admin panel displayed it.

What that comparison did establish honestly:

- The pipeline works end to end and generalises (R2 0.9916 held out, four
  candidates compared, stable across seeds).
- It is far better than a trivial mean predictor, so it learned real structure.
- **It offered no accuracy advantage over the rules on that data.**

#### Why these metrics are not market accuracy

This applies to the **ML v2** figures above, which are the ones a reader is most
likely to mistake for a result:

1. The target is produced by a synthetic generator, so a high R2 shows the
   function is learnable and nothing more.
2. **No two rows share an identical target.** All 900 target values are
   distinct, and no row sits on a universal floor value, so there is no
   degenerate group that caps the achievable fit.
3. `device_category` is exactly uniform at 100 rows per category by
   construction - a deliberate anti-starvation measure that is itself an
   artificial property, not evidence of market realism.
4. **900 rows across 9 categories and 26 brands is still nowhere near enough for
   real pricing**, and ages 0-15 cover only what the generator was told to
   cover.
5. There is no real market to validate against.
6. **The previous model's figures are not a benchmark for these ones.** They come
   from different data, a different target and a different algorithm, so the two
   MAEs cannot be compared. The old model's R2 of 0.9916 looks better precisely
   because its target was the rule-based formula itself.

### Fallback mechanism

`predict_estimated_value()` returns `None`, and the caller uses the rule-based
estimator, whenever:

- the model file is **missing** or **corrupt**;
- the pipeline **raises**;
- the ratio is **NaN, infinite or negative**;
- **`age` is outside the trained range** (0-9);
- `condition`, `working_status`, `physical_damage` or `device_category` is a
  value **never seen in training**.

The last two groups were added in Stage 4B after finding a real bug: a tree is
constant past its outermost split, so a **15-year-old laptop was quoted Rs 17,838
- the same as a 9-year-old one and more than the correct Rs 11,500.** Out-of-range
submissions now return exactly the rule-based figure.

**Brand is deliberately exempt.** Measured importance is ~0.3%, the rules ignore
brand entirely, and the form collects brand as free text - guarding it would
downgrade most real submissions for no gain.

The guarantee: **a device submission never fails because ML failed.** Every
response is a valid valuation labelled with `valuation_method: "ml"` or
`"rule_based"`. No confidence percentage or certainty claim is ever returned.

### Limitations of the model itself

- Synthetic training data, generated independently of the fallback formula.
- **ML v2 has a lower holdout MAE than the rules on this synthetic benchmark, and
  that is not a claim about real-world accuracy.** The previous shipped model
  scored *worse* than the rules on the older dataset; neither result transfers to
  real pricing, because neither dataset is real.
- **ML v2 is not deployed.** The model running in production is still the
  previous one, on the previous dataset.
- Cannot extrapolate - hence the distribution guard.
- No row shares an identical target, but the whole dataset is still synthetic.
- `brand` and `device_category` contribute almost nothing (~0.3% and ~0.8%);
  age, working status and condition carry ~92% of the decision.
- Retraining requires an API restart (the pipeline is cached).
- The model artifact is git-ignored and must be regenerated after cloning.

### For a viva

A question-and-answer explanation covering why ML is used, why regression fits,
why boosting was chosen, what MAE and R2 mean, what preprocessing does, what
the fallback does, and the model's real limitations is in
[`docs/VIVA_VALUATION_ML.md`](docs/VIVA_VALUATION_ML.md).

### Retraining

```bash
cd backend
python -m app.scripts.train_valuation_model
# optional: --dataset <path>  --model-out <path>
```

---

## Authentication and authorization

### Passwords

- Hashed with **Argon2** (`pwdlib[argon2]`). Plaintext is never stored, logged
  or returned.
- Login failures return one generic `401 Incorrect email or password` for both
  an unknown email and a wrong password, so accounts cannot be enumerated.
- Password length is enforced at the schema level.

> Argon2 rather than bcrypt via `passlib`: `passlib` 1.7.4 is incompatible with
> `bcrypt >= 4.1` (`module 'bcrypt' has no attribute '__about__'`). `pwdlib` is
> the maintained successor.

### Tokens

- HS256 JWT signed with `JWT_SECRET_KEY`, read from the **environment**. There
  is no default and no fallback: if it is unset the app raises rather than
  issuing a token signed with something guessable.
- Claims: `sub` (user id), `iat`, `exp`. Default lifetime 480 minutes.
- The secret is read from the environment on every use, so rotating it and
  restarting invalidates all issued tokens.
- Verified rejections: expired token, token signed with another secret,
  `alg=none` token, and a non-string `sub`.

### Authorization

| Boundary | Enforced by |
| --- | --- |
| Any protected endpoint | `get_current_user` → `401` |
| Every `/api/admin/*` route | `get_current_admin` → `401` then `403` |
| Reading a device list | `get_current_admin` |
| Deleting a device | `get_current_admin` |
| Changing a device or pickup status | `get_current_admin` |
| Creating a pickup | ownership of `device_id` is verified → `404` otherwise |
| Reading a pickup by id | `user_id` is matched → `404` otherwise |
| Listing devices or pickups | filtered by the JWT subject's user id |

Three rules hold throughout:

1. **The client is never trusted.** No endpoint accepts a `user_id` or a role
   from the request.
2. **The frontend guards are cosmetic.** `RequireAuth` and `RequireAdmin` improve
   UX; the backend is the boundary.
3. **No self-promotion.** `role` is a single column set to `"user"` at
   registration. The only way to become an admin is the CLI:

   ```bash
   cd backend
   python -m app.scripts.create_admin --email you@example.com --name "Your Name"
   ```

   It also supports `--promote` to promote an existing account, and
   `--password` for a non-interactive password.

## Installation

### Prerequisites

- **Python 3.11+**
- **Node.js 22 LTS** (or another currently supported LTS) and npm
- SQLite (bundled with Python — nothing to install)

```bash
node --version
npm --version
python3 --version
```

## Environment variables

Every backend setting is read from the environment, and **`backend/.env` is
loaded automatically at startup**. Real environment variables always take
precedence over `.env`, so a container or process manager can override anything
without editing a file. The only local setup step is:

```bash
cd backend
cp .env.example .env
```

Both `.env.example` files contain placeholders only.

### Backend — `backend/.env.example`

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `JWT_SECRET_KEY` | **yes** | — | Signs access tokens. No default and no fallback: the API starts without it but refuses to issue or accept tokens (`503`) and warns at startup. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `480` | Token lifetime. Nonsense or non-positive values fall back to the default. |
| `CORS_ORIGIN_PRODUCTION` | no | empty | The deployed frontend origin. **Added to** the allowlist; the development origins are always kept. |
| `CORS_ORIGINS` | no | dev origins | Full allowlist override. Replaces the built-in development origins. Wildcards are discarded with a warning. |
| `DATABASE_PATH` | no | `smartcycle.db` | SQLite file. Relative paths resolve against `backend/`, not the working directory. |
| `DATABASE_URL` | no | derived from `DATABASE_PATH` | Full SQLAlchemy URL. Takes precedence over `DATABASE_PATH`. |
| `SMARTCYCLE_DATA_DIR` | no | `data` | Dataset / model / metrics directory. |
| `VALUATION_MODEL_PATH` | no | `data/valuation_model.joblib` | Trained pipeline. |
| `VALUATION_MODEL_METRICS_PATH` | no | `data/valuation_model_metrics.json` | Metrics sidecar. |
| `VALUATION_DATASET_PATH` | no | `data/valuation_demo_dataset.csv` | Synthetic training data. |
| `SMARTCYCLE_ENV_FILE` | no | `backend/.env` | Load configuration from a different file. |

Generate a development secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Frontend — `frontend/.env.example`

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `VITE_API_URL` | no | dev `http://127.0.0.1:8000`; production same-origin | Backend base URL |

> `VITE_*` values are **inlined into the browser bundle at build time** and are
> public. Never put a secret in a `VITE_` variable. Changing the API target
> requires a rebuild. Local development needs no `.env` at all.

See [Deployment Preparation](#deployment-preparation) for the production
perspective on each of these.

## Running the project

Two terminals.

### Terminal 1 — backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# the only configuration step: copy the template and fill in the one required value
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste into JWT_SECRET_KEY

uvicorn app.main:app --reload --port 8000
```

`.env` is read automatically at startup, so no `export` is needed. Exporting
`JWT_SECRET_KEY` in the shell works too and takes precedence.

API: <http://127.0.0.1:8000> · Docs: <http://127.0.0.1:8000/docs>

### Terminal 2 — frontend

```bash
cd frontend
npm install
npm run dev
```

App: <http://127.0.0.1:5173>

### Optional — train the ML model

The API runs without it and falls back to the rule-based estimator. To use ML
valuation, train it (takes a few seconds):

```bash
cd backend
python -m app.scripts.train_valuation_model
```

Restart the API afterwards — the model is cached on first use.

### Optional — create an admin

```bash
cd backend
python -m app.scripts.create_admin --email you@example.com --name "Your Name"
```

### Production bundle

```bash
cd frontend
npm run build     # static output in frontend/dist/
npm run preview   # serves it locally on :4173
```

`npm run preview` uses port 4173, which is **not** a built-in development
origin. Add `http://127.0.0.1:4173` to `CORS_ORIGINS` if you want to test a
built bundle against a local API.

A production build with `VITE_API_URL` unset sends API calls to the **same
origin** as the page. Set `VITE_API_URL` at build time if the API lives on a
different host:

```bash
VITE_API_URL=https://api.your-domain.example.com npm run build
```

## Testing

The suite is **dependency free** — standard library only, no pytest, no extra
packages. It runs against a live server and the real SQLite database, and
creates its own timestamped throwaway users.

```bash
cd backend

# API checks — the server must already be running
ADMIN_EMAIL=you@example.com ADMIN_PASSWORD='...' python -m app.scripts.run_api_tests

# plus the in-process valuation and ML-fallback checks
ADMIN_EMAIL=you@example.com ADMIN_PASSWORD='...' python -m app.scripts.run_api_tests --unit

# valuation / ML checks only, no server needed
python -m app.scripts.run_api_tests --unit-only
```

Admin checks are skipped with a notice when no admin credential is supplied.

**95 checks** covering authentication, authorization, ownership isolation,
device creation, device tracking, pickup creation, pickup ownership, admin
access, admin device and pickup status updates, valuation, the rule-based
estimator, and every ML fallback path. See
[`docs/STAGE_3J.md`](docs/STAGE_3J.md) for the full breakdown.

Other checks run during development:

```bash
cd frontend
npm run build                    # must succeed
npm audit --audit-level=high     # 0 vulnerabilities
```

## Sample demo workflow

A five-minute walkthrough that exercises the whole system.

**1. Register and log in** — `/register`, then `/login`. You land on the User
Dashboard with an empty state.

**2. Sell a device** — `/sell`. Try `Laptop`, `Apple`, `MacBook Air 13`, age `3`,
`Good`, `Fully Working`, `No visible damage`, purchase price `95000`. Submit.

**3. Read the valuation** — you get an estimated value plus separate refurbished
and recycled figures, and the page states which method produced the number
(*ML Estimate* if the model is trained, otherwise *Rule-Based Estimate*). Copy
the tracking ID, e.g. `EW-2026-0042`.

**4. Track the device** — `/track`, paste the tracking ID. You see the device,
its valuation and its status timeline. This works **without logging in**; the
tracking ID is the shared reference.

**5. Request a pickup** — from the dashboard, `Request pickup` on that device.
Choose a date and time slot. It appears under *My pickup requests* with status
`Requested`.

**6. Admin reviews** — log out, log in as an admin, open `/admin`. The statistics
show your device and pickup. Change the device status to `Inspection` and the
pickup status to `Scheduled`.

**7. Owner sees the update** — log back in as the user. The dashboard and
`/track` both show the new statuses immediately.

**8. Isolation** — register a second account. It sees none of the first
account's devices or pickups, and cannot reach them by crafting requests. This
is enforced by the backend, not by the UI.

## Documentation

| Document | Contents |
| --- | --- |
| [`docs/STAGE_4B.md`](docs/STAGE_4B.md) | ML improvement stage: model selection, the extrapolation bug, baseline comparison, and the public-dataset search |
| [`docs/VIVA_VALUATION_ML.md`](docs/VIVA_VALUATION_ML.md) | Viva-ready ML explanation with likely examiner questions |
| [`docs/STAGE_3J.md`](docs/STAGE_3J.md) | The QA/security audit: findings, fixes, test coverage, verification results |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | What deployment would require, and what is not ready |
| [`docs/STAGE_4E_PLAN.md`](docs/STAGE_4E_PLAN.md) | Cloud deployment plan: hosting, database persistence, environment variables, URLs, HTTPS, custom domain |
| `docs/STAGE_4D.md` | Git hygiene, security audit and regression verification |
| [`backend/data/README.md`](backend/data/README.md) | Measured dataset audit, leakage review, and the documented public-dataset search |
| `docs/STAGE_3A.md` … `STAGE_3I.md` | Per-stage implementation notes and decisions |

## Limitations — what this is not

Stated plainly, because a demo that overstates itself is worth less than one
that does not.

**About the valuation**

1. **The training data is synthetic.** It is produced by
   `backend/app/scripts/generate_valuation_dataset.py` (fixed seed `20261007`),
   independently of the rule-based formula it is compared against. The model has
   never seen a real transaction.
2. **The metrics do not indicate real-world accuracy.** The ML v2 benchmark
   figures (MAE Rs 1,656.43 / RMSE Rs 5,892.80 / R2 0.5669) measure how well the
   model fits a synthetic generator. The previous shipped model's figures
   (MAE Rs 822.12 / R2 0.9916) measured something narrower still - how well it
   reproduced a formula it was trained on. **Neither is a market result, and
   neither is a production metric.**
3. **Values are estimates, not offers.** Nothing here is a guaranteed price, an
   exact market price, or a commitment to buy.
4. **The category reference values are invented** for demonstration.
4a. **The two benchmark comparisons point in opposite directions, and neither is
   real.** The previous shipped model scored *worse* than the rule-based
   estimator (MAE Rs 822 vs Rs 287) because that dataset's target was generated
   from the rules themselves. ML v2, trained on an independently generated
   dataset, scores *better* than the rules (MAE Rs 1,656.43 vs Rs 2,358.24). Both
   figures are measured and displayed; both are measured against synthetic data,
   so neither says anything about real-world pricing. **ML v2 is not deployed —
   production still runs the previous model.**
4b. **A tree ensemble cannot extrapolate.** Before Stage 4B a 15-year-old
   laptop was quoted the same as a 9-year-old one and *more* than the correct
   value. A distribution guard now routes such submissions to the rules.
4c. **The training target has no degenerate group.** All 900 target values
   are distinct, so unlike the previous dataset no rows share an identical
   target. Values still approach per-category recovery floors rather than
   one shared number.
5. **The rule-based fallback and the dataset generator are independent.** The
   generator does not import `app/services/valuation.py`, so the fallback is
   no longer the source of the training data. It remains a working,
   transparent estimator — and now a genuinely separate second opinion.

**Architecture and engineering**

6. **SQLite is a hard blocker for real deployment.** It is single-writer, so it
   cannot back multiple instances, and it stores everything in one local file —
   on any platform with an ephemeral filesystem (most container and serverless
   platforms) **every deploy or restart can destroy all user, device and pickup
   data** unless a persistent volume is mounted. Network filesystems are
   unsupported. The database *path* is configurable and working-directory
   independent, but the *engine* is the limitation. See
   [Database considerations](#database-considerations).
7. **No migration tool.** `init_db()` handles table creation and a few
   `ADD COLUMN` cases only — no renames, drops, type changes or data migrations.
8. **The JWT lives in `localStorage`**, so any script on the page can read it.
   A production system should use `HttpOnly` cookies.
9. **No refresh tokens or revocation** — an issued token is valid for its full
   lifetime.
10. **No rate limiting** on login or registration.
11. **Admin list endpoints are unpaginated** and load whole tables.
12. **No CI, no containerisation, no structured logging or monitoring.**

**Product scope**

13. **The Contact form is front-end only** — nothing is stored or sent.
14. **Marketing statistics on the public pages are demonstration figures**, not
    measured impact.
15. **Social media icons are visual placeholders** with no links.
16. **Pickup approval, agent assignment and status history are not implemented.**
    There is no status-transition validation; an admin may set any allowed status.
17. **No email**: no verification, no password reset, no notifications.
18. **No device list in the UI for regular users** beyond their own dashboard —
    `GET /api/devices` is admin-only by design.
19. **`GET /api/devices/{tracking_id}` is public by design** so Track Device works
    without an account. Anyone who knows a tracking ID can read that device's
    details, including its valuation. This is a deliberate product trade-off, and
    a real deployment would want to reconsider it.
20. **The ML model is not committed.** Run the training script after cloning.
    This is a deliberate choice, documented in `.gitignore`.
21. **The SQLite database file is not committed either.** It holds real
    accounts, email addresses, street addresses and locations, so publishing it
    would leak personal data. The schema is recreated automatically on first
    start. The reasoning is written out in `.gitignore`.

## Future improvements

Roughly in order of value:

1. Real pricing data, from a lawful source, with a documented refresh process —
   the single change that would make the ML model mean something.
2. Alembic migrations, then PostgreSQL.
3. `HttpOnly` cookie sessions with refresh-token rotation and revocation.
4. Rate limiting and account lockout on authentication endpoints.
5. Pagination and server-side filtering on the admin lists.
6. Server-side validation of device status transitions, plus a status history /
   audit log.
7. Email verification, password reset and pickup notifications.
8. Photo upload with moderation for device condition.
9. Real contact-form delivery.
10. CI running the build and the test suite, plus containerisation.
11. Accessibility and usability testing with real users rather than automated
    checks alone.

## Deployment Preparation

> **Deployment has not yet been performed.** SmartCycle has never been deployed
> to any hosting service. It runs only on a local machine. Nothing in this
> section has been executed against a real host, and no production URL exists.

This section describes what a deployment *would* involve. A longer version, with
the rationale behind each choice, is in
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md), and the concrete hosting, database
and environment decisions still to be made are laid out in
[`docs/STAGE_4E_PLAN.md`](docs/STAGE_4E_PLAN.md).

The repository is initialised, clean and ready to publish. Creating the GitHub
repository, adding a remote and pushing are deliberately left to you.

### Architecture recap

Two flows, unchanged from development:

- **React (Vite SPA) → FastAPI → SQLAlchemy → SQLite.** The browser never sends a
  `user_id` or a role; ownership and admin rights are derived from the validated
  JWT on every request, and queries are filtered at the database level.
- **Device data → `value_device()` → ML model → rule-based fallback.** The model
  predicts a depreciation ratio, which is applied to the same reference value the
  rules use. Any ML failure falls back silently and the result is labelled.

### Environment variables

**Backend** — all read from the environment, and `backend/.env` is loaded
automatically at startup. Real environment variables always win over `.env`.

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `JWT_SECRET_KEY` | **yes** | — | Signs access tokens. No default, no fallback. The API starts without it but refuses to issue or accept tokens (`503`) and logs a warning. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `480` | Token lifetime. Non-positive or non-numeric values fall back to the default. |
| `CORS_ORIGIN_PRODUCTION` | no | empty | The deployed frontend origin. **Added to** the allowlist; local development origins are always kept. |
| `CORS_ORIGINS` | no | dev origins | Full allowlist override. Replaces the built-in development origins, so list them too if you still want local dev. |
| `DATABASE_PATH` | no | `smartcycle.db` | SQLite file. Relative paths resolve against `backend/`, **not** the working directory. |
| `DATABASE_URL` | no | derived | Full SQLAlchemy URL, for an absolute path or a future non-SQLite backend. Takes precedence over `DATABASE_PATH`. |
| `SMARTCYCLE_DATA_DIR` | no | `data` | Dataset / model / metrics directory. |
| `VALUATION_MODEL_PATH` | no | `data/valuation_model.joblib` | Trained pipeline. |
| `VALUATION_MODEL_METRICS_PATH` | no | `data/valuation_model_metrics.json` | Metrics shown in the admin workspace. |
| `VALUATION_DATASET_PATH` | no | `data/valuation_demo_dataset.csv` | Synthetic training data. |
| `SMARTCYCLE_ENV_FILE` | no | `backend/.env` | Load configuration from a different file. |

**Frontend** — `VITE_*` only, inlined at build time and **public**:

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `VITE_API_URL` | no | dev: `http://127.0.0.1:8000`; production: same origin | Backend base URL. |

### Frontend configuration

The API base URL is resolved in this order:

1. `VITE_API_URL` from the environment.
2. `http://127.0.0.1:8000` **in development only**, so `npm run dev` needs no
   configuration.
3. **Same origin** in a production build, which is correct when a reverse proxy
   serves the SPA and the API from one host.

A localhost address is therefore **never baked into a production bundle** — the
development branch is eliminated at build time. If the API is on a different
host, set `VITE_API_URL` at build time:

```bash
VITE_API_URL=https://api.your-domain.example.com npm run build
```

This is a build-time value with no runtime override, so changing the API target
means rebuilding.

### Backend configuration

`backend/.env` is loaded automatically, so the only local setup step is copying
the template and filling it in. Every path is anchored to the backend directory,
so the app behaves identically however it is launched — from `backend/`, from
the repository root, or from `/tmp`.

```bash
cd backend
cp .env.example .env
# then set JWT_SECRET_KEY to a generated value
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Local development setup

Two terminals:

```bash
# Terminal 1 - backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env          # fill in JWT_SECRET_KEY
uvicorn app.main:app --reload --port 8000

# Terminal 2 - frontend
cd frontend
npm install
npm run dev
```

No other configuration is required: CORS already permits the development origin,
and the frontend already knows the development API URL.

### Production build command

```bash
cd frontend
npm ci
npm run build        # static output in frontend/dist/
npm run preview      # optional local check of the built bundle
```

`npm run preview` serves on port 4173, which is **not** a development origin. Add
`http://127.0.0.1:4173` to `CORS_ORIGINS` if you want to test a built bundle
against a local API.

### Backend startup command

Development:

```bash
uvicorn app.main:app --reload --port 8000
```

Production-shaped (still not a deployment):

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

`--workers 1` is deliberate: SQLite does not handle concurrent writers well.
Raising the worker count requires a different database first. `--reload` must
never be used outside development.

### CORS configuration approach

- The allowlist is **always explicit**. A wildcard is never used, and
  `CORS_ORIGINS='*'` is **discarded with a warning** rather than forwarded,
  because the API sends credentials and browsers reject `*` alongside them.
- Development origins are built in and always retained, so a production-only
  setting can never break local development.
- A deployment adds its own origin with `CORS_ORIGIN_PRODUCTION`, including the
  scheme — `https://app.example.com`, not a bare host.
- The frontend origin and the backend allowlist must agree. If they disagree the
  browser blocks the request, and the backend log will show no matching
  `Access-Control-Allow-Origin`.

### Database considerations

The database path is configurable and resolved reliably, but **SQLite itself is a
significant constraint** and this is not a soft caveat:

- SQLite is a **single-writer, file-based** database. It does not support
  concurrent writers, so it cannot safely back **multiple application
  instances** or horizontal scaling.
- It stores everything in **one local file**. Most container platforms and
  serverless platforms give an **ephemeral filesystem**, so the file — and every
  user, device and pickup record in it — is **lost on every redeploy or
  restart** unless a persistent volume is explicitly mounted.
- Writing to a network filesystem (NFS, many shared volumes) is unsupported or
  unsafe because of file locking.
- There is **no migration tool**. `init_db()` creates missing tables and applies
  a few `ADD COLUMN` cases; it cannot express renames, drops, type changes or
  data migrations.
- There is **no backup mechanism** and **no soft delete** — losing the file loses
  everything.

**Consider this before any actual deployment.** For anything beyond a single
local instance, SQLite should be replaced with a client-server database such as
PostgreSQL, together with a real migration tool. That is a deliberate scope
decision for this project, not an oversight.

### ML model considerations

- Training is a **manual** step: `python -m app.scripts.train_valuation_model`.
  It is never triggered at startup or by an API request.
- The model path is configurable (`VALUATION_MODEL_PATH`) and defaults to an
  absolute location under `backend/data/`, so a deployment can place it wherever
  it likes.
- The pipeline is cached in memory on first use, so **retraining requires an API
  restart**.
- If the model is missing, unreadable, or returns an unusable number, the API
  falls back to the rule-based estimator and labels the result `rule_based`.
  A deployment therefore works even if the model is never trained.
- **The model is trained on synthetic data and does not represent real market
  prices.** It is a demonstration artefact. Shipping it does not make the
  valuations commercially meaningful.

### Security considerations

- `JWT_SECRET_KEY` has **no default**. Supply it from a secret manager, never a
  file in the repository. Rotating it and restarting invalidates every issued
  token.
- `.env` is git-ignored; `.env.example` contains placeholders only.
- No secret is hardcoded anywhere in the source, and no secret is ever logged.
- Passwords are Argon2-hashed. Login failures return one generic message for
  both an unknown email and a wrong password, so accounts cannot be enumerated.
- Admin authorization and ownership are enforced in the **backend**. Frontend
  route guards are a convenience, never the boundary.
- **Before exposing this to the internet**, note that the access token is stored
  in `localStorage` and is therefore readable by any script running on the page;
  a stored XSS becomes a session theft. There are also no refresh tokens, no
  server-side revocation, no rate limiting, no HTTPS enforcement and no CSP. A
  production deployment should replace the token mechanism first.

### Known deployment limitations

| Limitation | Impact |
| --- | --- |
| SQLite | Cannot scale to multiple instances; at risk on ephemeral filesystems. See above. |
| No migrations | Schema changes are limited to additive `ADD COLUMN`. |
| Token in `localStorage` | XSS-readable; not acceptable for a public deployment. |
| No refresh or revocation | A token is valid for its full lifetime. |
| No rate limiting | Login and registration are brute-forceable. |
| No HTTPS enforcement | Credentials would cross the network in plaintext. |
| Unpaginated admin lists | Whole tables are loaded; fine at demo scale only. |
| No CI or containerisation | Nothing is built or tested automatically. |
| Synthetic training data | Valuations are not commercially meaningful. |
| Contact form is front-end only | Nothing is stored or sent. |
