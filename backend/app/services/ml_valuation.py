"""ML-assisted device valuation prediction.

The trained pipeline lives on disk (never in SQLite) and is loaded lazily on
first use. Every failure mode - missing file, corrupt file, unexpected input,
out-of-distribution input, prediction error - returns ``None`` so the caller can
fall back to the rule-based estimator. Technical details are logged server-side
only and are never surfaced to API clients.

Stage 4B added a distribution guard. A tree ensemble cannot extrapolate past the
values it was trained on: asked to price a 15-year-old laptop when the training
data only went to 9 years, it returns the value it last memorised for the oldest
bucket - flat, and *higher* than the correct answer. The training run records the
ranges and vocabularies it saw, and a submission outside them is handed straight
to the rule-based estimator, which extrapolates correctly via its decay curve.
"""

import logging
import math
import threading
from typing import Any

import numpy as np

from app.core.config import VALUATION_MODEL_PATH


logger = logging.getLogger(__name__)

# The trained pipeline predicts a dimensionless depreciation ratio rather than a
# rupee amount, because the app's valuation is multiplicative in the reference
# price. Multiplying the ratio back by the same reference the rule-based
# estimator uses keeps the output identical in meaning.
# These reference values mirror app.services.valuation.CATEGORY_REFERENCE_VALUES.
CATEGORY_REFERENCE_VALUES = {
    "smartphone": 30000.0, "laptop": 50000.0, "tablet": 24000.0,
    "desktop computer": 30000.0, "monitor": 12000.0, "television": 18000.0,
    "printer": 7000.0, "accessories": 1800.0, "other electronics": 5000.0,
}
DEFAULT_REFERENCE_VALUE = 5000.0
MINIMUM_DEVICE_VALUE = 500.0

# Features the pipeline was trained on, in the exact order it expects.
FEATURE_COLUMNS = [
    "device_category",
    "brand",
    "age",
    "condition",
    "working_status",
    "physical_damage",
    "original_purchase_price",
]

# How far outside the trained age range a submission may sit and still be priced
# by the model. Deliberately zero: a tree is constant beyond its outermost split,
# so a value one year outside the trained range receives exactly the same
# prediction as the boundary year rather than a slightly-adjusted one. Measured
# on this dataset that is a ~25% overvaluation (Rs 16,060 instead of Rs 12,811 at
# age 10), so there is nothing to gain from slack and a real cost. The
# rule-based estimator extrapolates correctly, so it is used instead.
AGE_TOLERANCE = 0

_lock = threading.Lock()
_pipeline: Any | None = None
_metadata: dict | None = None
_load_attempted = False


def _load_pipeline() -> Any | None:
    """Load and cache the trained pipeline. Returns None when unavailable."""
    global _pipeline, _metadata, _load_attempted

    with _lock:
        if _load_attempted:
            return _pipeline
        _load_attempted = True

        try:
            if not VALUATION_MODEL_PATH.exists():
                logger.warning(
                    "ML valuation model not found at %s; using rule-based valuation.",
                    VALUATION_MODEL_PATH,
                )
                return None

            import joblib  # imported lazily so the API still starts without it

            loaded = joblib.load(VALUATION_MODEL_PATH)

            # Stage 4B artifacts are a dict of {"pipeline": ..., metadata...}.
            # An older bare pipeline is still accepted, but it carries no
            # training distribution, so the out-of-distribution guard is skipped
            # for it and only the numeric sanity checks apply.
            if isinstance(loaded, dict) and "pipeline" in loaded:
                pipeline = loaded["pipeline"]
                metadata = loaded.get("training_distribution") or {}
            else:
                pipeline = loaded
                metadata = {}

            if not hasattr(pipeline, "predict"):
                logger.error(
                    "ML valuation model at %s is not a usable pipeline; using rule-based valuation.",
                    VALUATION_MODEL_PATH,
                )
                return None

            _pipeline = pipeline
            _metadata = metadata if isinstance(metadata, dict) else {}
            logger.info("Loaded ML valuation model from %s.", VALUATION_MODEL_PATH)
            return _pipeline
        except Exception:  # noqa: BLE001 - any load problem must not break valuation
            logger.exception(
                "Failed to load the ML valuation model; using rule-based valuation."
            )
            return None


def is_model_available() -> bool:
    """Return whether a usable ML model can be loaded right now."""
    return _load_pipeline() is not None


def model_age_range() -> tuple[int, int] | None:
    """Return the age range the loaded model was trained on, if recorded."""
    if _load_pipeline() is None or not _metadata:
        return None
    low, high = _metadata.get("age_min"), _metadata.get("age_max")
    if low is None or high is None:
        return None
    return int(low), int(high)


def _is_within_training_distribution(data) -> bool:
    """Whether this submission is close enough to the training data to price.

    A tree ensemble is piecewise constant: outside the values it saw, it returns
    the value of the nearest split rather than continuing the trend. On this
    dataset that means a 15-year-old laptop is quoted the same as a 9-year-old
    one, and *more* than the rule-based estimator would quote. Any categorical
    value the model never saw is encoded as an all-zero row, which is likewise a
    blind guess rather than a prediction.

    Both cases are reported as "outside the training distribution" and handed to
    the rule-based estimator, which extrapolates properly. Brand is exempt - see
    the comment in the loop below. When the artifact carries no recorded
    distribution (an older model), the guard is skipped and only the numeric
    sanity checks apply.
    """
    if not _metadata:
        return True

    try:
        age = int(data.age)
    except (TypeError, ValueError):
        return False

    low = _metadata.get("age_min")
    high = _metadata.get("age_max")
    if low is not None and high is not None:
        if age < int(low) - AGE_TOLERANCE or age > int(high) + AGE_TOLERANCE:
            logger.info(
                "Submitted age %s is outside the trained range %s-%s; using rule-based valuation.",
                age, low, high,
            )
            return False

    known = _metadata.get("known_categories") or {}
    # Brand is deliberately NOT guarded. Measured on this dataset it carries
    # roughly 0.3% of the model's total feature importance, the rule-based
    # estimator has no brand term at all, and the Sell Device form collects brand
    # as free text rather than a fixed list. Guarding it would silently downgrade
    # most real submissions to the rule-based estimator for no accuracy gain,
    # while OneHotEncoder's handle_unknown="ignore" already gives the neutral
    # "average brand" encoding.
    for name in ("device_category", "condition", "working_status", "physical_damage"):
        allowed = known.get(name)
        if not allowed:
            continue
        value = {
            "device_category": (data.device_category or "").strip(),
            "condition": (data.condition or "").strip() or "Unknown",
            "working_status": (data.working_status or "").strip() or "Unknown",
            "physical_damage": (data.physical_damage or "").strip() or "None",
        }[name]
        if value not in allowed:
            logger.info(
                "Submitted %s %r was not seen in training; using rule-based valuation.",
                name, value,
            )
            return False

    return True


def _build_feature_row(data) -> list[object]:
    """Build one pipeline input row from a ValuationInput, in feature order.

    A missing purchase price becomes NaN so the pipeline's imputer treats it as
    missing, which is how the training data represents an absent price.
    """
    price = data.original_purchase_price
    return [
        (data.device_category or "").strip(),
        (data.brand or "").strip() or "Unknown",
        int(data.age),
        (data.condition or "").strip() or "Unknown",
        (data.working_status or "").strip() or "Unknown",
        (data.physical_damage or "").strip() or "None",
        float(price) if price is not None else float("nan"),
    ]


def _reference_value(data) -> float:
    """Return the reference value the rule-based estimator would have used."""
    price = data.original_purchase_price
    if price is not None:
        try:
            price_value = float(price)
        except (TypeError, ValueError):
            price_value = float("nan")
        if price_value == price_value and price_value > 0:  # not NaN and positive
            return price_value

    category = (data.device_category or "").strip().lower()
    return CATEGORY_REFERENCE_VALUES.get(category, DEFAULT_REFERENCE_VALUE)


def predict_estimated_value(data) -> float | None:
    """Predict an estimated device value, or return None to trigger a fallback.

    The pipeline predicts a depreciation ratio; that ratio is applied to the
    same reference value the rule-based estimator uses. The result is only
    accepted when it is finite, non-negative, and the submission was close
    enough to the training data for a tree ensemble to mean anything by it.
    """
    pipeline = _load_pipeline()
    if pipeline is None:
        return None

    if not _is_within_training_distribution(data):
        return None

    try:
        features = np.asarray([_build_feature_row(data)], dtype=object)
        ratio = float(pipeline.predict(features)[0])
    except Exception:  # noqa: BLE001 - any prediction problem must not break valuation
        logger.exception("ML valuation prediction failed; using rule-based valuation.")
        return None

    if not math.isfinite(ratio) or ratio < 0:
        logger.warning(
            "ML valuation returned an unusable ratio (%r); using rule-based valuation.",
            ratio,
        )
        return None

    try:
        prediction = ratio * _reference_value(data)
    except (TypeError, ValueError):
        logger.exception("ML valuation reference computation failed; using rule-based valuation.")
        return None

    if not math.isfinite(prediction) or prediction < 0:
        logger.warning(
            "ML valuation produced an unusable value (%r); using rule-based valuation.",
            prediction,
        )
        return None

    return max(MINIMUM_DEVICE_VALUE, round(prediction, 2))


def reset_model_cache() -> None:
    """Clear the cached pipeline so the next call reloads from disk (tests)."""
    global _pipeline, _metadata, _load_attempted
    with _lock:
        _pipeline = None
        _metadata = None
        _load_attempted = False
