# Stage 3I — ML-Assisted Valuation

Stage 3I adds a real, trained, explainable machine-learning estimator for device value. The ML path is primary for **new** submissions; the original rule-based estimator is preserved and used automatically whenever the ML path is unavailable or returns something unusable. Stages 3A–3H are preserved.

> **This model is a demonstration ML pipeline trained on development data. It is not a representation of live market prices.**

## Dataset

`backend/data/valuation_demo_dataset.csv` — 420 rows.

**This dataset is SYNTHETIC.** It is not collected from users, not scraped from
marketplaces, and is not real market data. See `backend/data/README.md` for the
full provenance write-up.

Targets were generated with the project's **own documented rule-based formula**
(plus a small deterministic noise term) so the provenance is fully explainable
and reproducible from a fixed seed. The practical consequence is important and
stated wherever the metrics appear: **a high R² here shows the function is
learnable, and says nothing about real-world accuracy.**

## Features and target

Features use only fields that already exist on the `Device` model:

| Feature | Type |
| --- | --- |
| `device_category` | categorical |
| `brand` | categorical |
| `age` | numeric |
| `condition` | categorical |
| `working_status` | categorical |
| `physical_damage` | categorical |
| `original_purchase_price` | numeric (nullable) |

`accessories`, `location`, `status` and ownership fields are excluded: they are
not valuation drivers, and several are free text. `brand` was added to
`ValuationInput` as an optional field; it does not change the request schema.

**Target:** `estimated_purchase_value` — the same concept the app already used.
It is not redefined.

The pipeline predicts a dimensionless **depreciation ratio**
(`estimated_purchase_value / reference_price`); `ml_valuation` multiplies that
ratio back by the same reference value the rule-based estimator uses. The app's
valuation is multiplicative in the reference price, and a tree regressor cannot
extrapolate when asked to output the raw rupee amount directly — asking it to do
so systematically under- or over-shot by 25–60%. Predicting the ratio keeps the
output identical in meaning while making the model accurate across the whole
price range. This reduced MAE from ₹3,828 to ₹1,674 and raised R² from 0.81 to 0.96.

## Model and preprocessing

- **Model:** `RandomForestRegressor` (`n_estimators=300`, `max_depth=12`, `min_samples_leaf=2`, `random_state=42`).
- **Why:** the relationship between age, condition, damage and price is
  non-linear and interactive; a forest captures that without assuming a straight
  line, trains in seconds on 420 rows, tolerates unseen categories, and exposes
  feature importances, which keeps it explainable. `LinearRegression` cannot
  represent the interactions, and deep learning is unjustified at this data size.
- **Preprocessing:** a single `ColumnTransformer` inside the saved `Pipeline` —
  `OneHotEncoder(handle_unknown="ignore")` for the five categorical columns and
  `passthrough` for `age` and `original_purchase_price`. Because preprocessing
  is bundled into the pipeline, prediction time needs no manual preprocessing.
- `random_state=42` everywhere, so training is reproducible.

## Training

Manual and separate. It never runs on a device submission or an API request.

```bash
cd backend
python -m app.scripts.train_valuation_model
```

The script validates and cleans the CSV, splits 80/20, trains, evaluates, and
saves both artifacts.

## Evaluation metrics (actual)

Measured on the held-out 84-row test split, scored on the **rupee value scale**:

| Metric | Value |
| --- | --- |
| MAE | ₹1,674.19 |
| RMSE | ₹3,410.41 |
| R² | 0.9557 |

**These figures describe performance on the synthetic demonstration dataset only.
They do not establish real-world or live-market accuracy**, and the dataset's
target was generated from the rule-based formula this model is meant to help
replace. The same disclaimer is returned by the admin API, stored in the metrics
sidecar, printed by the training script, and rendered in the Admin Dashboard.

## Where the model lives

- Model: `backend/data/valuation_model.joblib`
- Metrics sidecar: `backend/data/valuation_model_metrics.json`
- **The model is a file on disk and is never stored in SQLite.**

Paths come from `app/core/config.py` (`VALUATION_MODEL_PATH`,
`VALUATION_MODEL_METRICS_PATH`, `VALUATION_DATASET_PATH`) and can be
overridden with the same environment variables for tests.

`app/services/ml_valuation.py` loads the pipeline **lazily on first use** and
caches it in a thread-safe way, so the app still starts when the model is
missing.

## Fallback mechanism

`app/services/valuation.py` keeps `estimate_device_value` — the original
rule-based function — completely intact and callable. The new `value_device` is
the entry point the API uses:

1. Ask the ML pipeline for a prediction.
2. Accept it only if finite and non-negative, then clamp to the same
   `MINIMUM_DEVICE_VALUE = 500` floor the rules use.
3. On success return `valuation_method="ml"`.
4. On **any** failure return `valuation_method="rule_based"` from the untouched
   rule-based estimator.

Triggers for the fallback: model file missing, corrupt or unloadable, a pipeline
without `predict`, an exception while loading or predicting, a non-finite ratio
or value, a negative value, a NaN/missing reference, or a missing feature.

**The Sell Device request never fails because of ML.** Technical details are
logged server-side via `logging` and never returned to the client. Verified by
deleting the model file and by writing garbage into it — both produced a
successful `201` with `valuation_method="rule_based"`.

## API changes

`DeviceResponse` gained one field. No existing field was changed or removed.

```json
{
  "estimated_purchase_value": 122044.14,
  "potential_refurbished_value": 152555.18,
  "potential_recycled_value": 9763.53,
  "valuation_method": "ml",
  "...": "unchanged"
}
```

`valuation_method` is `"ml"` or `"rule_based"`. It is persisted on the device
record via a new `devices.valuation_method` column, added with the project's
existing idempotent `ALTER TABLE` approach and backfilled to `rule_based` — which
is accurate, because every pre-existing value was produced by the rule-based
estimator. **No existing device or stored valuation was modified or re-valued.**

New admin-only endpoint:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/admin/valuation-model` | Model status + evaluation metrics + disclaimer |

It depends on `get_current_admin`, so normal users get `403` and anonymous
callers `401`. This information is never exposed to normal users.

## Frontend

- `src/pages/SellDevicePage.jsx` and `src/pages/TrackDevicePage.jsx` show a
  **"Valuation method"** row: `Machine Learning Estimate` or `Rule-Based
  Estimate`. An unknown or missing value falls back to the rule-based label.
  The demo notices were reworded to state the estimate is not a guaranteed
  price and not a representation of live market prices. No confidence
  percentage is shown anywhere.
- `src/pages/AdminDashboardPage.jsx` gained a small "ML model status" card in
  the existing side column: status, model type, dataset rows, MAE/RMSE/R², the
  disclaimer, and a note that the fallback engages automatically.
- `src/api/client.js` gained `getAdminValuationModel`. `isDeviceResponse` was
  left unchanged, so every existing consumer keeps working.

## Verification (15 tests)

Training completes and prints metrics; model + metrics files are created; the
backend loads the model; a normal submission returns `valuation_method="ml"`
with a finite, non-negative, numeric value; the value and method persist in
SQLite; the tracking ID is still generated; deleting the model file and
corrupting it both yield a successful submission with `rule_based`; Track
Device, the User Dashboard, the pickup workflow (create + 409 duplicate), the
Admin Dashboard, Stage 3H status management, and authentication all still work;
non-admin and anonymous access to the model endpoint are `403`/`401`. Zero
browser console errors on all 11 routes; no tracebacks or 5xx in the backend log.

## Limitations

- The training data is synthetic, so the metrics are not evidence of real-world
  accuracy, and a production model would need genuine market data.
- The target was generated from the rule-based formula, so the ML model largely
  reproduces that formula's behaviour rather than discovering new pricing.
- Brand is treated as a categorical signal only; there is no model-name or
  spec-level understanding, so an unseen brand falls back to the category
  average.
- Values are rounded estimates for demonstration, not quotes.
- No live market feed, no scraping, no confidence intervals, no automatic
  retraining, no deep learning, no vision-based inspection.
