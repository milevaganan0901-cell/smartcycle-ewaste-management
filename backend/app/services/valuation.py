"""Device valuation service.

`estimate_device_value` is the original transparent rule-based estimator and is
preserved unchanged. `value_device` is the public entry point used by the API:
it tries the trained ML pipeline first and falls back to the rule-based
estimator whenever the ML path is unavailable or unusable.
"""

import logging
from dataclasses import dataclass

from app.services.ml_valuation import predict_estimated_value


logger = logging.getLogger(__name__)

ML_VALUATION_METHOD = "ml"
RULE_BASED_VALUATION_METHOD = "rule_based"


CATEGORY_REFERENCE_VALUES = {
    "smartphone": 30000.0,
    "laptop": 50000.0,
    "tablet": 24000.0,
    "desktop computer": 30000.0,
    "monitor": 12000.0,
    "television": 18000.0,
    "printer": 7000.0,
    "accessories": 1800.0,
    "other electronics": 5000.0,
}

CONDITION_FACTORS = {
    "excellent": 1.10,
    "good": 0.92,
    "fair": 0.70,
    "poor": 0.42,
    "not working": 0.22,
}

WORKING_STATUS_FACTORS = {
    "fully working": 1.00,
    "working": 1.00,
    "partially working": 0.62,
    "not working": 0.30,
}

DAMAGE_FACTORS = {
    "none": 1.00,
    "no visible damage": 1.00,
    "minor scratches": 0.96,
    "cracks or major damage": 0.68,
}

MINIMUM_DEVICE_VALUE = 500.0


@dataclass(frozen=True)
class ValuationInput:
    """Inputs used by the estimator."""

    device_category: str
    age: int
    condition: str
    working_status: str
    physical_damage: str | None = None
    original_purchase_price: float | None = None
    brand: str | None = None


@dataclass(frozen=True)
class ValuationResult:
    """Values returned by the estimator, plus which method produced them."""

    estimated_purchase_value: float
    potential_refurbished_value: float
    potential_recycled_value: float
    valuation_method: str = RULE_BASED_VALUATION_METHOD


def _factor(values: dict[str, float], value: str, default: float) -> float:
    """Look up a normalized factor with a safe fallback."""
    return values.get(value.strip().lower(), default)


def estimate_device_value(data: ValuationInput) -> ValuationResult:
    """Calculate transparent demo values from the submitted device details.

    Rules:
    1. Use the original purchase price when supplied; otherwise use a category
       reference value.
    2. Apply 12% age depreciation per year, with a 25% floor.
    3. Apply condition, working-status and physical-damage factors.
    4. Keep a minimum value so recycling-only devices still have a visible
       material-recovery value.
    """
    category_key = data.device_category.strip().lower()
    reference_value = CATEGORY_REFERENCE_VALUES.get(category_key, 5000.0)

    if data.original_purchase_price is not None and data.original_purchase_price > 0:
        reference_value = data.original_purchase_price

    # Twelve percent depreciation per year, never below 25% of the reference.
    age_factor = max(0.25, 0.88 ** data.age)
    condition_factor = _factor(CONDITION_FACTORS, data.condition, 0.60)
    working_factor = _factor(WORKING_STATUS_FACTORS, data.working_status, 0.70)
    damage_text = (data.physical_damage or "none").strip().lower()
    damage_factor = _factor(DAMAGE_FACTORS, damage_text, 0.85)

    estimated_purchase_value = max(
        MINIMUM_DEVICE_VALUE,
        reference_value * age_factor * condition_factor * working_factor * damage_factor,
    )

    # A device that is usable and not in poor condition has more refurbishment
    # potential; all other devices receive a conservative recovery estimate.
    refurbishment_factor = (
        1.25
        if data.working_status.strip().lower() in {"fully working", "working"}
        and data.condition.strip().lower() not in {"poor", "not working"}
        else 1.05
    )
    potential_refurbished_value = max(
        MINIMUM_DEVICE_VALUE,
        estimated_purchase_value * refurbishment_factor,
    )
    potential_recycled_value = max(
        MINIMUM_DEVICE_VALUE,
        estimated_purchase_value * 0.08,
    )

    return ValuationResult(
        estimated_purchase_value=round(estimated_purchase_value, 2),
        potential_refurbished_value=round(potential_refurbished_value, 2),
        potential_recycled_value=round(potential_recycled_value, 2),
    )


def _derived_values(
    estimated_purchase_value: float,
    working_status: str,
    condition: str,
) -> tuple[float, float]:
    """Apply the existing refurbishment and recovery rules to a base value.

    These rules are the project's own and are applied to whichever base value
    the estimator produced, so the ML and rule-based paths stay consistent.
    """
    refurbishment_factor = (
        1.25
        if working_status.strip().lower() in {"fully working", "working"}
        and condition.strip().lower() not in {"poor", "not working"}
        else 1.05
    )
    refurbished = max(MINIMUM_DEVICE_VALUE, estimated_purchase_value * refurbishment_factor)
    recycled = max(MINIMUM_DEVICE_VALUE, estimated_purchase_value * 0.08)
    return round(refurbished, 2), round(recycled, 2)


def value_device(data: ValuationInput) -> ValuationResult:
    """Value a device using the ML model when possible, rules otherwise.

    Flow:
    1. Ask the ML pipeline for a prediction.
    2. Accept it only if it is a finite, non-negative number.
    3. On success return `valuation_method="ml"`.
    4. On any failure fall back to the untouched rule-based estimator and
       return `valuation_method="rule_based"`.
    """
    predicted = None
    try:
        predicted = predict_estimated_value(data)
    except Exception:  # noqa: BLE001 - the request must never fail because of ML
        logger.exception("Unexpected ML valuation failure; using rule-based valuation.")

    if predicted is not None:
        refurbished, recycled = _derived_values(
            predicted, data.working_status, data.condition
        )
        return ValuationResult(
            estimated_purchase_value=predicted,
            potential_refurbished_value=refurbished,
            potential_recycled_value=recycled,
            valuation_method=ML_VALUATION_METHOD,
        )

    rule_based = estimate_device_value(data)
    return ValuationResult(
        estimated_purchase_value=rule_based.estimated_purchase_value,
        potential_refurbished_value=rule_based.potential_refurbished_value,
        potential_recycled_value=rule_based.potential_recycled_value,
        valuation_method=RULE_BASED_VALUATION_METHOD,
    )
