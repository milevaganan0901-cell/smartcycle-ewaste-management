# Stage 4B — Real-world data & ML valuation improvement

No new features and no architecture change. React/Vite, FastAPI, SQLAlchemy,
SQLite, JWT and the scikit-learn pipeline are all exactly as they were. The goal
was to make the valuation system more **credible, transparent, rigorously
evaluated and maintainable** — including being honest where it is weak.

**No database was reset.** No existing user, device or pickup was deleted, and
every pre-existing device keeps its original stored valuation.

---

## 1. What the audit found

### 1.1 The dataset is synthetic, and that is now measured rather than asserted

420 rows, 7 features, no duplicates, no impossible values, and — decisively —
**implausibly uniform category distributions** (condition 18.3%–24.0% across 5
grades, physical damage 32.9%–34.0% across 3). Real survey data is never that
balanced. Full audit in [`backend/data/README.md`](../backend/data/README.md).

The decisive structural fact: **the target was generated from the project's own
rule-based formula plus ±7% noise.** That makes the rules near-ground-truth on
this data, which has a large consequence for how the metrics must be read.

### 1.2 A genuine bug: the ML path over-valued devices outside its training range

A tree ensemble is piecewise constant. Asked to price a device older than
anything in training, it returns the value of the nearest split rather than
continuing the trend. Measured on a laptop, with no purchase price given:

| Age | ML estimate (before) | Rule-based |
| --- | --- | --- |
| 5 | ₹23,072 | ₹24,276 |
| 9 | ₹17,838 | ₹14,558 |
| 10 | **₹17,838** | ₹12,811 |
| 15 | **₹17,838** | ₹11,500 |
| 25 | **₹17,838** | ₹11,500 |

A 25-year-old laptop was quoted the same as a 9-year-old one, and **more** than
the correct answer — a flat, inflated, silently wrong price. The `age` field has
no upper bound in the API schema (`ge=0`), so any user could trigger this
directly. There was a test asserting the fallback for a *missing* model, but
nothing for a nonsensical *output*.

**Fix.** The training run now records the distribution it was fitted on
(age range and the exact categorical vocabularies) into the artifact. A
submission outside it is handed to the rule-based estimator, which extrapolates
correctly. Out-of-range submissions are now **identical** to the rules.

### 1.3 The evaluation was thinner than it looked

Stage 3I reported three numbers from one 80/20 split, with no model comparison,
no cross-validation and **no baseline**. A single split on 420 rows is a weak
basis for a model claim.

---

## 2. Model selection (evidence, not assertion)

Four candidates, selected by **5-fold cross-validated MAE** — deliberately *not*
on the holdout, so the holdout stays an unbiased final estimate.

| Model | CV MAE | CV R² |
| --- | --- | --- |
| LinearRegression | 2,317.89 | 0.9177 |
| Ridge(alpha=1.0) | 2,279.38 | 0.9193 |
| RandomForestRegressor *(Stage 3I incumbent)* | 1,321.33 | 0.9516 |
| **GradientBoostingRegressor** | **774.14** | **0.9856** |

A repeated-CV stability check (5 seeds × 5 folds) confirmed the ranking is not
noise: GBM 779.88 ± 6.90 versus RandomForest 1,294.81 ± 40.59.

**Selected: `GradientBoostingRegressor(n_estimators=500, max_depth=4, learning_rate=0.05)`.**
A standard scikit-learn ensemble — no new dependency, no deep learning. It beats
the incumbent by ~40% on cross-validated MAE. The final fit is on the training
split and scored once on the untouched holdout.

## 3. Preprocessing

`ColumnTransformer` with two explicit branches:

- **Categorical** (category, brand, condition, working status, damage):
  `SimpleImputer(most_frequent)` → `OneHotEncoder(handle_unknown="ignore")`.
- **Numeric** (age, purchase price): `SimpleImputer(median)`.

Stage 3I passed numerics straight through and relied on the tree's implicit NaN
handling. Imputing explicitly is clearer, works identically for every candidate
model, and measurably helped (RandomForest MAE 1,674.19 → 1,626.34 on the same
split). `handle_unknown="ignore"` means an unseen brand or category is encoded
neutrally rather than crashing.

## 4. Results — stated honestly

### Held-out test split (84 rows), rupee scale

| Predictor | MAE | RMSE | R² |
| --- | --- | --- | --- |
| **ML model (GradientBoosting)** | **₹822.12** | ₹1,488.16 | **0.9916** |
| Baseline: mean-value predictor | ₹10,582.17 | ₹16,363.65 | −0.0190 |
| Baseline: **rule-based estimator** | **₹287.31** | ₹585.10 | **0.9987** |

### The headline finding, not buried

**The ML model does not beat the rule-based baseline on this dataset.** ML MAE
₹822.12 versus rules ₹287.31 — the simpler estimator is roughly 2.9× more
accurate here.

This is expected and is not a defect in either implementation. The dataset's
target was *generated from* the rule-based formula, so the rules are effectively
the ground truth on this data and no model can do better than reproduce the
formula plus its irreducible noise. The model-selection script prints this
outcome explicitly, the metrics sidecar records it, and the admin panel displays
it.

What the comparison does honestly establish:

- The ML pipeline works end to end and generalises (R² 0.9916 held out, five
  candidates compared, stable across seeds).
- It is far better than a trivial mean predictor, so it has learned real
  structure rather than memorising a constant.
- **It provides no accuracy advantage over the rules *on this data*.** Its
  purpose is to learn the relationship from data instead of seven hand-tuned
  constants — which only becomes an advantage once real transaction data
  replaces this set. That is a statement about the future, not a claim of
  present benefit.

### Why the metrics cannot be called "accuracy"

1. The target is a formula plus noise, so a high R² shows the function is
   learnable. It says nothing about real markets.
2. **12.6% of target rows sit exactly on the ₹500 floor**, sharing one identical
   value. No regression model can separate them; this caps the achievable fit.
3. There is no external validation set. There is no real market to validate
   against.

### Feature importance (GradientBoosting, grouped)

| Feature group | Importance |
| --- | --- |
| `age` | 23.7% |
| `working_status` | 45.4% |
| `condition` | 23.3% |
| `physical_damage` | 3.1% |
| `original_purchase_price` | 3.3% |
| `device_category` | ~0.8% |
| `brand` | ~0.3% |

Age, working status and condition carry ~92% of the model's decisions — which
matches the generating process exactly, since the formula has no brand or
category term. This measurement is the evidence behind the brand exemption in
the distribution guard below.

## 5. Public dataset search — performed, and rejected on the record

Genuinely searched, downloaded and inspected. Full evidence in
[`backend/data/README.md`](../backend/data/README.md) §5.

- **UCI ML Repository**: 0 results for `e-waste`, `electronic waste`,
  `used device`, `resale`, `laptop`, `hardware price`. The only `smartphone`
  hits are Human Activity Recognition datasets, unrelated to pricing.
- **Kaggle `recell-used-devices-prices`**: CC0 Public Domain, 3,454 rows.
  Downloaded, licence confirmed via the Kaggle API, contents inspected.
- **Kaggle `used-handheld-device-data`**: CC0, 3,454 rows. Verified to be the
  **same records** (100% numerical agreement), just renamed columns — so one
  candidate, not two.

**Rejected** because five of the seven required features are absent — including
`working_status` and `condition`, which together drive ~68% of the model — the
target is a **unitless normalised score** with no currency (converting it to
rupees would be fabrication), and it covers **2 of the application's 9 device
categories**.

No citation is invented, no dataset is scraped further, and the synthetic
dataset is retained and clearly labelled. Forcing an ill-fitting public dataset
in to look more advanced would have made the project less honest.

## 6. The distribution guard (the safety fix)

Prediction now refuses the model, and hands the submission to the rules, when:

| Condition | Why | Evidence |
| --- | --- | --- |
| `age` outside the trained range (0–9) | A tree cannot extrapolate; it returns a flat, inflated value | ₹17,838 vs ₹11,500 at age 15 |
| `condition`, `working_status`, `physical_damage` or `device_category` never seen in training | One-hot encodes to all-zeros, so the model guesses blind — and these carry ~72% of importance | feature importance table |
| Prediction is NaN, infinite or negative | Not a number a user should be shown | pre-existing check |
| Model missing, corrupt, or raising | Any load or predict failure | pre-existing check |

**`brand` is deliberately exempt.** Measured importance is ~0.3%, the
rule-based estimator has no brand term at all, and the Sell Device form collects
brand as **free text**, not a fixed list. Guarding it would silently downgrade
most real submissions for no accuracy gain. `handle_unknown="ignore"` already
gives the neutral "average brand" encoding.

An initial version allowed one year of slack around the age range. Measurement
showed that admitted a ~25% overvaluation (₹16,060 instead of ₹12,811 at age 10)
for no benefit, because a tree is *constant* past its outermost split — so the
tolerance was tightened to zero.

## 7. Preserved flow

```
validate input (422 on bad data)
  → attempt ML prediction if within the trained distribution
      → validate output: finite, non-negative
  → on ANY failure: rule-based estimator
  → always return a valid valuation
```

A device submission has never failed because of the ML path, and still cannot.
The API never returns a confidence percentage, a certainty claim, or a
guarantee; a test now asserts no such field exists in the response.

## 8. Artifact and metadata

`backend/data/valuation_model.joblib` is a dict of `{pipeline, model_name,
model_label, trained_at, feature_columns, training_distribution}`. The loader
**also accepts a bare pipeline**, so a Stage 3I artifact keeps working.

`backend/data/valuation_model_metrics.json` now records model name, pipeline,
`trained_at`, dataset identifier, dataset kind, library versions, held-out
metrics, per-model cross-validation comparison, **both baselines**, the selection
note, the baseline note, the metrics-ceiling note, and the trained distribution.
All of it is surfaced by the admin-only `GET /api/admin/valuation-model` and
shown in the admin panel, including the baseline comparison.

**Not committed** — a ~4 MB regenerable binary derived entirely from the
committed dataset. `python -m app.scripts.train_valuation_model` rebuilds it.
The dataset and the metrics sidecar are committed because they are small,
readable and needed to understand the model.

## 9. Testing

**122 checks pass** (up from 95), no test removed. New coverage:

- **Guard:** trained age range reported; in-range priced by ML; out-of-range
  refused; no flat inflated price at +5/+15/+30 years; unseen brand still uses
  ML; unseen condition / working status / category fall back and still return a
  positive estimate; missing price still uses ML.
- **Prediction sanity:** 18 category × age × condition × price combinations all
  finite, positive and within a sane band of their reference; refurbished and
  recycled values always positive and consistent.
- **Persistence:** the stored estimate is returned identically on re-read; no
  confidence or certainty field in the response.
- **Validation:** negative age, negative price, missing field, blank brand all
  `422`; an out-of-range submission is accepted rather than rejected.
- **Unchanged and still passing:** authentication, authorization, ownership
  isolation, tracking, pickup and admin workflows.

## 10. Documentation

- [`backend/data/README.md`](../backend/data/README.md) — rewritten: measured
  data-quality audit, leakage review, and the full public-dataset search with
  licence verification and rejection reasons.
- `README.md` — new **SmartCycle Valuation Model** section, including the viva
  explanation.
- `docs/VIVA_VALUATION_ML.md` — the viva explanation on its own page.
- `docs/STAGE_4B.md` — this file.

## 11. Honest bottom line

The valuation system is now **measurably better and considerably more honest**.
It has a real model-selection process, cross-validation, two baselines, a
sanity guard that fixes a genuine overvaluation bug, and documentation that
states plainly what the numbers mean.

It is **still a demo**. The dataset is synthetic and generated from the very
formula it is meant to replace, the rule-based estimator still scores better on
it, and no figure here says anything about real market prices. The correct
sentence, unchanged and repeated in the UI, the API, the admin panel and the
docs, is:

> The current valuation model is a development/demo model trained on synthetic
> data and should not be interpreted as a production market-pricing model.
