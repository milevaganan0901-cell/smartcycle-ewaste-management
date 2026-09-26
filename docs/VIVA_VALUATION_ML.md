# Viva explanation — the SmartCycle valuation model

Written for a 2nd-year AI/ML student defending this project. Everything here is
measured from the actual code and data, not aspirational.

---

## 1. Why use machine learning here?

The user tells us a device's **category, brand, age, condition, working status,
physical damage and original purchase price**, and we must output **one number**:
an estimated resale value.

The obvious alternative is a formula. The project ships one — seven hand-tuned
multipliers in `app/services/valuation.py`. A formula is fine when you *know* the
relationships. But real resale pricing depends on interactions nobody can write
down by hand: a 5-year-old phone that still works is worth something very
different from a 5-year-old phone that does not, and that difference is not
simply "condition factor × working factor".

Machine learning lets us **learn the relationship from data** instead of
encoding it as constants. The honest part of this answer: on *our current
synthetic data* the formula still wins (see §9). ML is the path that keeps
working when real data replaces the demo set.

## 2. Input and output

**Input — 7 features, all of which the Sell Device form already collects:**

| Feature | Type | Example |
| --- | --- | --- |
| `device_category` | categorical | Laptop |
| `brand` | categorical | Apple |
| `age` | numeric (years) | 3 |
| `condition` | categorical | Good |
| `working_status` | categorical | Fully Working |
| `physical_damage` | categorical | None |
| `original_purchase_price` | numeric, ~15% missing | 95000 |

No new fields were added. Two existing fields were considered and **rejected**:
`model` (free text, effectively unique per device — useless as a category) and
`accessories` (genuinely relevant to resale, but absent from the dataset, so
adding it would mean inventing data).

**Output — one number:** the estimated value in rupees. Two derived figures
(refurbished and recycled value) are computed from it by fixed project rules, so
they stay consistent whichever path produced the base number.

## 3. Why is this a regression problem?

The target is a **continuous quantity** — a price in rupees. There is no
"class" to predict. Classification predicts "laptop / monitor / phone";
regression predicts "₹54,359". So this is supervised **regression**.

## 4. Which algorithm, and why?

We compared four, fairly, and let the numbers decide:

| Model | Cross-validated MAE | R² |
| --- | --- | --- |
| LinearRegression | 2,317.89 | 0.9177 |
| Ridge(alpha=1.0) | 2,279.38 | 0.9193 |
| RandomForestRegressor *(Stage 3I)* | 1,321.33 | 0.9516 |
| **GradientBoostingRegressor** | **774.14** | **0.9856** |

**Chosen: `GradientBoostingRegressor(n_estimators=500, max_depth=4, learning_rate=0.05)`.**

Why gradient boosting fits this problem:

- It builds an **ensemble of shallow trees one after another**, where each new
  tree corrects the errors of the ones before it. Depreciation is exactly the
  kind of relationship where the *shape* matters more than a single formula.
- Shallow trees (depth 4) are naturally regularised — the model cannot memorise
  a few hundred rows, which is a real risk at this dataset size.
- It handles **mixed feature types** well once categoricals are encoded, and it
  needs no scaling, no feature engineering, and no new dependency.
- It is a standard scikit-learn estimator. No deep learning is warranted for
  420 rows, and none is used.

Random Forest was a reasonable incumbent and still works, but averaging many
deep trees independently left ~40% more error than boosting did on the same
comparison.

## 5. What are MAE and R², in plain language?

**MAE — Mean Absolute Error.** Average size of the mistake, in rupees.
"Our model is off by about ₹822 on a typical device." Because it averages
*absolute* errors, being wrong by ₹5,000 twice counts the same as being wrong by
₹10,000 once. **Lower is better.**

**R² — R-squared.** How much of the variation in price the model explains.
0 would mean "no better than always guessing the average price"; 1 would be
perfect. Our 0.9916 means the model explains ~99% of the variation *in this
dataset*. **Higher is better.**

**RMSE — Root Mean Squared Error.** Like MAE, but large errors are punished
harder because they are squared first. It is always ≥ MAE. It answers "what
happens when we are badly wrong?"

**The single most important caveat:** these numbers describe performance **on
the dataset we used**. They are not market accuracy. See §9.

## 6. What preprocessing is done, and why?

Reproducible, inside a scikit-learn `Pipeline`, so it can never drift from
training to serving:

1. **Missing values.** `original_purchase_price` is missing for ~15% of rows
   because the field is optional in the form. Numeric gaps are filled with the
   **median**, categorical gaps with the **most frequent** value. Filling
   explicitly is clearer than relying on a tree's implicit handling, and it
   measurably improved accuracy.
2. **Categorical encoding.** `OneHotEncoder` turns "Laptop" into a column of
   0s and a single 1. Crucially it uses `handle_unknown="ignore"`, so a brand
   or category the model has never seen does not crash the request — it is
   encoded as all-zeros, i.e. treated neutrally.
3. **No scaling needed.** Tree models do not care about feature magnitude, so
   no `StandardScaler`. Keeping it out is simpler and avoids a pointless step.

## 7. Why predict a *ratio* instead of a price?

This is the most interesting design decision in the project.

The app's valuation is **multiplicative**: `price × age × condition × working ×
damage`. A tree ensemble **cannot extrapolate** — it only outputs values it has
seen before. Ask it for a ₹5,00,000 laptop when training only saw up to
₹71,724, and it returns something near the top of its range regardless.

So instead the model predicts a **dimensionless depreciation ratio** — "this
device is worth about 35% of its reference value" — and the application
multiplies that ratio by the same reference value the rule-based estimator
uses. The ratio generalises across the whole price range; the multiplication
supplies the scale. The output means exactly the same thing as the formula's.

## 8. What does the fallback do?

`predict_estimated_value()` returns `None` — and the caller silently uses the
rule-based estimator — whenever:

- the model file is **missing** or **corrupt**;
- the pipeline **raises** during prediction;
- the predicted ratio is **NaN, infinite or negative**;
- the submitted `age` is **outside the range the model was trained on**;
- `condition`, `working_status`, `physical_damage` or `device_category` is a
  value the model **never saw in training**.

That last group was added in Stage 4B after finding a real bug. A tree is
constant past its outermost split, so a **15-year-old laptop was being quoted
₹17,838 — the same as a 9-year-old one, and more than the correct ₹11,500.**
The training run now records the distribution it was fitted on, and anything
outside it goes to the rules, which extrapolate properly.

**Brand is deliberately *not* guarded.** We measured it: brand carries ~0.3% of
the model's importance, the rule-based estimator ignores brand entirely, and the
form collects brand as free text. Guarding it would downgrade most real
submissions for no accuracy gain.

The guarantee: **a device submission never fails because ML failed.** The
response is always a valid valuation, and it always states which method produced
it (`valuation_method: "ml"` or `"rule_based"`).

## 9. The model's real limitations — say these before you are asked

1. **The training data is synthetic.** 420 rows generated by this project's own
   formula, not collected from any market. Every metric describes performance on
   invented data.
2. **The rule-based estimator beats the ML model on this data** (MAE ₹287 vs
   ₹822). That is the honest result and it is displayed in the admin panel. The
   reason is that the data was generated *from* that formula, so the formula is
   effectively ground truth here.
3. **12.6% of target rows sit exactly on the ₹500 floor**, sharing one identical
   value. No model can separate identical targets, which caps the achievable fit.
4. **Category distributions are implausibly uniform**, which is itself evidence
   the data is synthetic.
5. **420 rows is small.** Nine device categories and 26 brands on 420 rows means
   the model falls back to category averages for rare combinations. It is enough
   to demonstrate the pipeline, not to price real inventory.
6. **The model cannot extrapolate.** This is a property of tree ensembles in
   general, and the reason for the distribution guard.
7. **No external validation.** There is no real market data to validate against,
   so "accuracy" cannot be claimed in any sense.

## 10. Likely viva questions

**"Why not deep learning?"**
420 rows, seven features, and a target generated by a known formula. A neural
network would memorise this dataset and tell us nothing extra, while being far
harder to explain and debug. Boosted trees are the right capacity for this
problem.

**"Isn't your R² of 0.99 suspiciously high?"**
Yes — and that is exactly why we do not call it market accuracy. The target is
the project's own formula plus ±7% noise, so the model is learning a function we
already know. The 0.99 shows the pipeline works, not that the pricing is right.

**"If the formula is better, why keep the model at all?"**
Because the formula is seven hand-picked constants. It cannot learn, and it
cannot adapt when real data arrives. Keeping it as the fallback is deliberate —
it is the safety net that makes the ML path safe to enable at all. But on the
current data it is the better estimator, and we report that rather than hiding
it.

**"How do you know the model isn't just memorising?"**
It was scored on an 84-row split it never saw during fitting, and the candidate
models were compared using 5-fold cross-validation, with the holdout reserved so
it could not influence selection. A repeated cross-validation with five
different seeds confirmed the ranking is stable (±6.90 for the winner).

**"What stops a user getting a wildly wrong price?"**
Input is schema-validated first (negative age or price returns 422). Then the
output is checked for being a finite, non-negative number. Then the submission is
checked against the distribution the model was trained on. Fail any of those and
the rules answer instead. Every response is labelled with which method was used.

**"Where does the model file live?"**
`backend/data/valuation_model.joblib`, loaded lazily once per process behind a
lock. It is never retrained on a request or at startup — training is a manual
`python -m app.scripts.train_valuation_model`. The file is git-ignored because it
is a 4 MB regenerable binary; the app runs without it via the fallback.
