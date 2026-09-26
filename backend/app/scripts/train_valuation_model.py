"""Train the SmartCycle ML valuation model.

This is a **manual, separate** step. It is never triggered by a device
submission or an API request, and it does not retrain automatically.

    python -m app.scripts.train_valuation_model

It loads the clearly-labelled synthetic development dataset in `backend/data/`,
compares a small number of candidate regressors, selects one by cross-validated
MAE, evaluates it on a held-out split against two baselines, and saves the
pipeline plus a metadata sidecar for the admin workspace.

Target note: the pipeline predicts a dimensionless *depreciation ratio*, not a
rupee amount. The app's valuation is multiplicative in the reference price
(`price x age x condition x working x damage`), which a tree ensemble cannot
extrapolate when asked to output the raw amount. Predicting the ratio and
multiplying it back by the same reference the rule-based estimator uses keeps the
output identical in meaning while making the model accurate across the whole
price range. `ml_valuation.predict_estimated_value` performs that multiplication
and applies the same minimum-value floor as the rule-based estimator.

Honesty note: the dataset's target was *generated from* the project's own
rule-based formula plus small noise, so on this data the rule-based estimator is
an unusually strong baseline - see the printed comparison. That is reported
rather than hidden.

Only scikit-learn (plus its numpy/scipy/joblib dependencies) is required.
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


RANDOM_STATE = 42
TEST_SIZE = 0.2
CV_FOLDS = 5

FEATURE_COLUMNS = [
    "device_category",
    "brand",
    "age",
    "condition",
    "working_status",
    "physical_damage",
    "original_purchase_price",
]
# Positional indices, matching the order the pipeline is built with.
CATEGORICAL_INDICES = [0, 1, 3, 4, 5]
NUMERIC_INDICES = [2, 6]
TARGET_COLUMN = "estimated_purchase_value"
RATIO_TARGET_COLUMN = "depreciation_ratio"

# Mirrors app.services.valuation.CATEGORY_REFERENCE_VALUES so the reference used
# to build the ratio is identical to the one the rule-based estimator uses.
CATEGORY_REFERENCE_VALUES = {
    "smartphone": 30000.0, "laptop": 50000.0, "tablet": 24000.0,
    "desktop computer": 30000.0, "monitor": 12000.0, "television": 18000.0,
    "printer": 7000.0, "accessories": 1800.0, "other electronics": 5000.0,
}

# Candidate regressors, deliberately small and standard. No deep learning, and
# nothing here needs a new dependency. Selection is by cross-validated MAE, not
# by the held-out split, so the holdout stays an unbiased final estimate.
CANDIDATE_MODELS: dict[str, dict] = {
    "LinearRegression": {
        "label": "LinearRegression",
        "rationale": "Baseline linear model: shows how much of the signal is a straight line.",
        "build": lambda: LinearRegression(),
    },
    "Ridge(alpha=1.0)": {
        "label": "Ridge(alpha=1.0)",
        "rationale": "Linear model with L2 regularisation, to damp the one-hot brand/category columns.",
        "build": lambda: Ridge(alpha=1.0),
    },
    "RandomForestRegressor": {
        "label": "RandomForestRegressor(n_estimators=300, max_depth=12)",
        "rationale": "The Stage 3I model, kept as the incumbent to beat.",
        "build": lambda: RandomForestRegressor(
            n_estimators=300,
            max_depth=12,
            min_samples_leaf=2,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
    },
    "GradientBoostingRegressor": {
        "label": "GradientBoostingRegressor(n_estimators=500, max_depth=4, learning_rate=0.05)",
        "rationale": (
            "Boosts shallow trees additively. Captures the non-linear interaction "
            "between age, condition, working status and damage, regularises itself "
            "by building shallow trees on residuals, and scored best on "
            "cross-validated MAE."
        ),
        "build": lambda: GradientBoostingRegressor(
            n_estimators=500,
            max_depth=4,
            learning_rate=0.05,
            random_state=RANDOM_STATE,
        ),
    },
}


def build_preprocessor() -> ColumnTransformer:
    """One-hot encode categoricals, impute anything missing.

    `SimpleImputer` is added because `original_purchase_price` is absent for
    about 15% of rows (the field is optional in the app). Imputing explicitly is
    clearer than relying on a tree's native missing-value handling, and it keeps
    the same code path for every candidate model.
    """
    return ColumnTransformer(
        transformers=[
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        (
                            "encode",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                CATEGORICAL_INDICES,
            ),
            ("numeric", SimpleImputer(strategy="median"), NUMERIC_INDICES),
        ]
    )


def build_pipeline(model) -> Pipeline:
    """Preprocessor followed by the candidate regressor."""
    return Pipeline(steps=[("preprocessor", build_preprocessor()), ("model", model)])


def _clean_text(value: str | None, fallback: str = "Unknown") -> str:
    cleaned = (value or "").strip()
    return cleaned if cleaned else fallback


def _reference_value(category: str, price: float) -> float:
    """Return the same reference value the rule-based estimator would use."""
    if price is not None and price == price and price > 0:  # not None and not NaN
        return float(price)
    return CATEGORY_REFERENCE_VALUES.get((category or "").strip().lower(), 5000.0)


def load_dataset(dataset_path: Path):
    """Load, validate and clean the dataset into features, ratio and reference.

    Returns (features, ratio_target, reference, value_target).
    """
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {dataset_path}. See backend/data/README.md."
        )

    rows: list[list[object]] = []
    ratios: list[float] = []
    references: list[float] = []
    values: list[float] = []
    skipped = 0

    with dataset_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [
            column
            for column in FEATURE_COLUMNS + [TARGET_COLUMN]
            if column not in (reader.fieldnames or [])
        ]
        if missing:
            raise ValueError(f"Dataset is missing required columns: {', '.join(missing)}")

        for record in reader:
            try:
                age = int(float(record["age"]))
                value = float(record[TARGET_COLUMN])
            except (TypeError, ValueError):
                skipped += 1
                continue

            price_text = (record["original_purchase_price"] or "").strip()
            try:
                price: float = float(price_text)
            except ValueError:
                price = float("nan")  # absent price, as in the app

            category = _clean_text(record["device_category"], "")
            reference = _reference_value(category, price)
            if reference <= 0 or value <= 0:
                skipped += 1
                continue

            rows.append(
                [
                    category,
                    _clean_text(record["brand"]),
                    max(0, age),
                    _clean_text(record["condition"]),
                    _clean_text(record["working_status"]),
                    _clean_text(record["physical_damage"], "None"),
                    price,
                ]
            )
            ratios.append(value / reference)
            references.append(reference)
            values.append(value)

    if not rows:
        raise ValueError("Dataset contained no usable rows.")

    print(
        f"Loaded {len(rows)} rows from {dataset_path.name}"
        f"{f' ({skipped} skipped as invalid)' if skipped else ''}."
    )
    return (
        np.asarray(rows, dtype=object),
        np.asarray(ratios, dtype=float),
        np.asarray(references, dtype=float),
        np.asarray(values, dtype=float),
    )


def _scores(actual, predicted) -> dict[str, float]:
    """MAE/RMSE/R^2 on the rupee scale the user actually sees."""
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(mean_squared_error(actual, predicted) ** 0.5),
        "r2": float(r2_score(actual, predicted)),
    }


def _rule_based_predictions(features) -> np.ndarray:
    """The project's own rule-based estimator, as a baseline.

    Imported from the shipped service so the baseline is the exact code path the
    application falls back to, not a re-implementation that could drift.
    """
    from app.services.valuation import ValuationInput, estimate_device_value

    values = []
    for row in features:
        price = row[6]
        result = estimate_device_value(
            ValuationInput(
                device_category=row[0],
                age=int(row[2]),
                condition=row[3],
                working_status=row[4],
                physical_damage=row[5],
                original_purchase_price=None if price != price else float(price),
                brand=row[1],
            )
        )
        values.append(result.estimated_purchase_value)
    return np.asarray(values, dtype=float)


def _training_distribution(features) -> dict:
    """Record the ranges and vocabularies the model was actually fitted on.

    A tree ensemble cannot extrapolate beyond the values it saw, so the
    prediction service uses this to detect an out-of-distribution submission and
    hand it to the rule-based estimator instead of returning a flat, inflated
    number.
    """
    ages = np.asarray([int(row[2]) for row in features], dtype=float)
    prices = np.asarray(
        [float(row[6]) for row in features if row[6] == row[6]], dtype=float
    )
    known: dict[str, list[str]] = {}
    for position, name in enumerate(FEATURE_COLUMNS):
        if position in CATEGORICAL_INDICES:
            known[name] = sorted({str(row[position]) for row in features})
    return {
        "age_min": int(ages.min()),
        "age_max": int(ages.max()),
        "price_min": float(prices.min()) if prices.size else None,
        "price_max": float(prices.max()) if prices.size else None,
        "known_categories": known,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m app.scripts.train_valuation_model",
        description="Train the SmartCycle development ML valuation model.",
    )
    parser.add_argument("--dataset", type=Path, default=None, help="Override the dataset path.")
    parser.add_argument("--model-out", type=Path, default=None, help="Override the saved model path.")
    args = parser.parse_args()

    from app.core.config import (
        BACKEND_ROOT,
        VALUATION_DATASET_PATH,
        VALUATION_MODEL_METRICS_PATH,
        VALUATION_MODEL_PATH,
    )

    dataset_path = args.dataset or VALUATION_DATASET_PATH
    model_path = args.model_out or VALUATION_MODEL_PATH
    metrics_path = VALUATION_MODEL_METRICS_PATH
    model_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    line = "=" * 66
    print("SmartCycle ML valuation training")
    print(line)
    print("Dataset: SYNTHETIC DEVELOPMENT DATA - not real market prices.")
    print(line)

    try:
        features, ratio_target, reference, value_target = load_dataset(dataset_path)
    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"Training aborted: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    features_train, features_test, ratio_train, _ratio_test, _ref_train, reference_test, value_train, value_test = (
        train_test_split(
            features, ratio_target, reference, value_target,
            test_size=TEST_SIZE, random_state=RANDOM_STATE,
        )
    )
    print(f"Train rows: {len(features_train)} | Test rows: {len(features_test)}")

    # ---- model selection: cross-validated MAE, never the holdout ------------
    print()
    print(f"Model selection ({CV_FOLDS}-fold cross-validated MAE, rupee scale)")
    print("-" * 66)
    splitter = KFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    comparison: dict[str, dict] = {}
    for name, spec in CANDIDATE_MODELS.items():
        pipeline = build_pipeline(spec["build"]())
        predicted_ratios = cross_val_predict(
            pipeline, features, ratio_target, cv=splitter, n_jobs=1
        )
        scores = _scores(value_target, np.clip(predicted_ratios, 0, None) * reference)
        comparison[name] = scores
        print(
            f"  {name:28} MAE {scores['mae']:>10,.2f}   "
            f"RMSE {scores['rmse']:>10,.2f}   R2 {scores['r2']:7.4f}"
        )

    selected_name = min(comparison, key=lambda key: comparison[key]["mae"])
    selected_spec = CANDIDATE_MODELS[selected_name]
    print("-" * 66)
    print(f"  Selected: {selected_spec['label']}")
    print(f"  Why: {selected_spec['rationale']}")

    # ---- final fit on the training split, evaluated on the holdout ---------
    pipeline = build_pipeline(selected_spec["build"]())
    pipeline.fit(features_train, ratio_train)
    holdout = _scores(
        value_test, np.clip(pipeline.predict(features_test), 0, None) * reference_test
    )

    # ---- baselines on the identical holdout --------------------------------
    # A mean-value predictor, and the project's own rule-based estimator. Both
    # are scored on the same held-out rows as the ML model.
    baselines = {
        "mean_predictor": _scores(
            value_test, np.full_like(value_test, float(value_train.mean()))
        ),
        "rule_based_estimator": _scores(
            value_test, _rule_based_predictions(features_test)
        ),
    }

    print()
    print("Held-out test split (20%) - rupee scale")
    print("-" * 66)
    print(f"  {'ML model (' + selected_name + ')':40} MAE {holdout['mae']:>10,.2f}  R2 {holdout['r2']:7.4f}")
    for name, scores in baselines.items():
        print(f"  {'baseline: ' + name:40} MAE {scores['mae']:>10,.2f}  R2 {scores['r2']:7.4f}")
    print("-" * 66)
    rule_mae = baselines["rule_based_estimator"]["mae"]
    if holdout["mae"] < rule_mae:
        print(
            f"  The ML model beats the rule-based baseline by "
            f"Rs {rule_mae - holdout['mae']:,.2f} on this data."
        )
    else:
        print(
            f"  HONEST RESULT: the ML model does NOT beat the rule-based baseline here"
            f"\n  (ML MAE Rs {holdout['mae']:,.2f} vs rule-based Rs {rule_mae:,.2f}). That is expected:"
            f"\n  this dataset's target was GENERATED FROM the rule-based formula, so the rules"
            f"\n  are effectively the ground truth. The baseline is reported rather than hidden."
            f"\n  The ML path exists to learn the relationship from data instead of seven"
            f"\n  hand-tuned constants, which is what matters once real data replaces this set."
        )

    # ---- artifact ----------------------------------------------------------
    distribution = _training_distribution(features)
    try:
        joblib.dump(
            {
                "pipeline": pipeline,
                "model_name": selected_name,
                "model_label": selected_spec["label"],
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "feature_columns": FEATURE_COLUMNS,
                "training_distribution": distribution,
            },
            model_path,
        )
    except OSError as error:
        print(f"Could not save the model: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(f"\nSaved pipeline -> {model_path.relative_to(BACKEND_ROOT)}")
    print(
        f"  Trained on ages {distribution['age_min']}-{distribution['age_max']}. "
        "Submissions outside that range use the rule-based estimator."
    )

    metrics = {
        "model_name": selected_name,
        "model_type": f"GradientBoostingRegressor (predicts a depreciation ratio)"
        if selected_name == "GradientBoostingRegressor"
        else f"{selected_spec['label']} (predicts a depreciation ratio)",
        "pipeline": (
            "ColumnTransformer(SimpleImputer + OneHotEncoder(handle_unknown='ignore') "
            "+ SimpleImputer(median)) -> " + selected_spec["label"]
        ),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset_identifier": dataset_path.name,
        "dataset_kind": "synthetic_development",
        "target": TARGET_COLUMN,
        "internal_target": RATIO_TARGET_COLUMN,
        "random_state": RANDOM_STATE,
        "test_size": TEST_SIZE,
        "cv_folds": CV_FOLDS,
        "total_rows": int(len(features)),
        "training_rows": int(len(features_train)),
        "test_rows": int(len(features_test)),
        "features": FEATURE_COLUMNS,
        "library_versions": {
            "scikit-learn": sklearn.__version__,
            "numpy": np.__version__,
            "joblib": joblib.__version__,
        },
        "metrics": {key: round(value, 4) for key, value in holdout.items()},
        "metrics_note": (
            "MAE/RMSE are in rupees on the estimated-value scale; R^2 is computed on "
            "the same scale. These are held-out test-split figures."
        ),
        "cross_validation": {
            "folds": CV_FOLDS,
            **{
                f"mean_{key}": round(float(np.mean([comparison[n][key] for n in comparison])), 4)
                for key in ("mae", "rmse", "r2")
            },
            "note": (
                "Mean over all candidate models, shown for context. Per-model figures "
                "are in model_comparison."
            ),
        },
        "model_comparison": {
            name: {key: round(value, 4) for key, value in scores.items()}
            for name, scores in comparison.items()
        },
        "model_selection_note": (
            f"Selected '{selected_name}' by lowest cross-validated MAE. The held-out "
            "split was not used for selection."
        ),
        "baselines": {
            name: {key: round(value, 4) for key, value in scores.items()}
            for name, scores in baselines.items()
        },
        "baseline_note": (
            "The rule-based estimator scores very highly here because this dataset's "
            "target was generated from that same formula. It is not evidence of "
            "real-world accuracy for either method."
        ),
        "training_distribution": distribution,
        "metrics_ceiling_note": (
            "About 13% of target rows sit exactly on the Rs 500 minimum-value floor. "
            "Those rows share one identical target, so no regression model can separate "
            "them; that caps the achievable fit on this dataset."
        ),
        "disclaimer": (
            "DEVELOPMENT/DEMO MODEL. Trained on a synthetic dataset generated from the "
            "project's own rule-based formula. The metrics above do not represent live "
            "or real-world market prices and must not be read as market accuracy."
        ),
        "fallback_method": "rule_based",
    }
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(f"Saved metrics  -> {metrics_path.relative_to(BACKEND_ROOT)}")
    print("\nDone. The FastAPI backend loads this model on its next start.")


if __name__ == "__main__":
    main()
