"""Generate the SmartCycle ML valuation dataset.

=============================================================================
THIS PRODUCES **SYNTHETIC** DATA. IT IS NOT REAL MARKET DATA.
=============================================================================

Every row here is invented by the process documented below. Nothing in this
file was observed, measured, scraped, collected from a recycler, or taken from
a marketplace. It must never be described as real-world pricing, a market
survey, or evidence of how much any device is actually worth. The numbers
below are *assumptions chosen to give a model something learnable*, not
findings about the e-waste market.

    python -m app.scripts.generate_valuation_dataset
    python -m app.scripts.generate_valuation_dataset --seed 20261007
    python -m app.scripts.generate_valuation_dataset --check

Deterministic: the same ``--seed`` always writes a byte-identical CSV.

Why this exists
---------------
The previous dataset was generated from the application's own rule-based
valuation formula, which made that formula an almost perfect answer key. A
model trained on it learned to imitate the fallback rather than to price
anything, and the fallback beat the model 2.9x on the same holdout. This
generator is deliberately **independent** of that formula: it does not import
``app.services.valuation``, does not reuse its constants, and does not copy
its arithmetic. It builds value from a category-specific decay curve instead,
so the model has to earn its accuracy.

The latent valuation process
----------------------------
For each device:

1.  A **brand tier** is drawn. This is the only place brand matters, and it is
    a multiplicative price-position factor, not a brand-name lookup.

2.  A **latent original price** is drawn from a category lognormal, scaled by
    the brand tier. Prices are widely spread inside a category, as they are in
    life.

3.  A **condition** is drawn from an age-dependent distribution: older devices
    skew toward Poor and Not Working. Condition is therefore correlated with
    age, which is true of real collections and which a uniform generator
    cannot express.

4.  A **working status** and a **physical damage** level are drawn.

5.  An **age depreciation curve** is applied:

        age_factor = 0.5 ** (age / half_life)

    Each category has its own half-life, so a phone decays much faster than a
    desktop. This is a curve, not a linear per-year percentage, and it is
    categorically different from the old single ``0.88 ** age`` rule.

6.  Condition, working-status and damage multipliers are applied, each drawn
    from a small uniform range rather than a single constant, so two devices
    with the same labels are not priced identically.

7.  The result approaches a **category-specific recovery floor** (a scrap or
    material-recovery value) asymptotically rather than clipping to one
    universal number. Old, broken, low-value devices converge toward that
    floor, which is how dead electronics actually behave.

8.  Three independent perturbations are applied: per-device lognormal noise,
    a per-device demand shock, and a slow-moving category-level market factor.
    Together they make the target a genuinely noisy function of the inputs, so
    an irreducible error exists and the model cannot fit perfectly.

Independence guarantees
-----------------------
This module imports only the standard library. It must never import
``app.services.valuation``, ``app.models``, ``app.db``, or any frontend code,
and a test asserts that.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import random
from pathlib import Path

# --- Configuration ---------------------------------------------------------

DEFAULT_SEED = 20261007
ROWS_PER_CATEGORY = 100
CATEGORIES = (
    "Smartphone",
    "Laptop",
    "Tablet",
    "Desktop computer",
    "Monitor",
    "Television",
    "Printer",
    "Accessories",
    "Other electronics",
)
MIN_AGE = 0
MAX_AGE = 15
AGES = tuple(range(MIN_AGE, MAX_AGE + 1))

# Ages are stratified rather than sampled at random: every age in 0..15 gets
# at least MIN_PER_AGE rows per category, and the surplus is shared out by a
# decaying weight so young devices stay the common case. This guarantees the
# old end is a real population, not a two-row tail.
MIN_PER_AGE = 5

CONDITIONS = ("Excellent", "Good", "Fair", "Poor", "Not Working")
WORKING_STATUSES = ("Fully Working", "Partially Working", "Not Working")
PHYSICAL_DAMAGE = ("None", "Minor scratches", "Cracks or major damage")

# P(condition | age band). Condition degrades with age: a twelve-year-old
# machine is much more likely to arrive as Poor or Not Working than a new one.
# Bands are (age 0-2), (3-5), (6-9), (10-12), (13-15).
CONDITION_BY_AGE_BAND = {
    (0, 2): (0.26, 0.30, 0.22, 0.13, 0.09),
    (3, 5): (0.16, 0.26, 0.27, 0.19, 0.12),
    (6, 9): (0.09, 0.20, 0.29, 0.24, 0.18),
    (10, 12): (0.05, 0.13, 0.27, 0.30, 0.25),
    (13, 15): (0.03, 0.09, 0.24, 0.33, 0.31),
}

# Multiplier ranges. Ranges rather than constants, so identical labels on two
# devices do not produce identical values.
CONDITION_RANGE = {
    "Excellent": (0.93, 1.06),
    "Good": (0.79, 0.92),
    "Fair": (0.58, 0.77),
    "Poor": (0.33, 0.54),
    "Not Working": (0.11, 0.29),
}
WORKING_RANGE = {
    "Fully Working": (0.97, 1.03),
    "Partially Working": (0.60, 0.84),
    "Not Working": (0.28, 0.54),
}
DAMAGE_RANGE = {
    "None": (0.99, 1.03),
    "Minor scratches": (0.87, 0.97),
    "Cracks or major damage": (0.60, 0.84),
}

# Per-category valuation personality. All figures are synthetic assumptions.
#   half_life    years for the value to halve, at a constant condition
#   recovery     asymptote a dead device approaches (scrap / material value)
#   price_mu     lognormal log-mean of the original purchase price
#   price_sigma  lognormal spread of that price
#   missing_p    share of rows with no recorded purchase price
CATEGORY_PROFILE = {
    "Smartphone":       {"half_life": 3.0, "recovery": 265, "price_mu": 10.05, "price_sigma": 0.58, "missing_p": 0.20},
    "Laptop":           {"half_life": 4.0, "recovery": 410, "price_mu": 10.75, "price_sigma": 0.62, "missing_p": 0.18},
    "Tablet":           {"half_life": 3.4, "recovery": 300, "price_mu": 10.10, "price_sigma": 0.60, "missing_p": 0.22},
    "Desktop computer": {"half_life": 6.0, "recovery": 360, "price_mu": 10.55, "price_sigma": 0.60, "missing_p": 0.16},
    "Monitor":          {"half_life": 5.0, "recovery": 205, "price_mu": 9.55,  "price_sigma": 0.55, "missing_p": 0.18},
    "Television":       {"half_life": 5.5, "recovery": 315, "price_mu": 10.25, "price_sigma": 0.58, "missing_p": 0.20},
    "Printer":          {"half_life": 4.5, "recovery": 240, "price_mu": 9.60,  "price_sigma": 0.62, "missing_p": 0.24},
    "Accessories":      {"half_life": 2.0, "recovery": 55,  "price_mu": 8.10,  "price_sigma": 0.70, "missing_p": 0.30},
    "Other electronics": {"half_life": 4.2, "recovery": 165, "price_mu": 9.30,  "price_sigma": 0.75, "missing_p": 0.28},
}

# Brand price-position multipliers. Synthetic: these describe a tier, not a
# measured brand valuation, and are deliberately spread so brand carries real
# signal in the data instead of ~0.3% importance as it did before.
BRAND_TIER = {
    "Apple": 1.42, "Sony": 1.30, "Samsung": 1.16, "Microsoft": 1.22,
    "Dell": 1.10, "HP": 1.08, "Lenovo": 1.04, "Asus": 1.06,
    "Acer": 0.92, "LG": 1.02, "Google": 1.24, "OnePlus": 1.12,
    "Xiaomi": 0.86, "Realme": 0.80, "TCL": 0.82, "MSI": 1.20,
    "Panasonic": 1.00, "Canon": 1.14, "Brother": 1.00, "Epson": 1.00,
    "BenQ": 1.02, "Logitech": 1.02, "Anker": 1.00, "Belkin": 0.96,
    "Misc": 0.88, "Generic": 0.74,
}

# Brand pools per category. These are the brand names the application already
# presents to users, grouped so a Printer never carries a phone brand. Only the
# vocabulary is shared with existing data; no value, price or formula is.
CATEGORY_BRANDS = {
    "Smartphone":       ("Apple", "Samsung", "Google", "OnePlus", "Xiaomi", "Realme", "TCL", "Misc", "Generic"),
    "Laptop":           ("Apple", "Dell", "HP", "Lenovo", "Asus", "Acer", "Microsoft", "MSI", "Misc", "Generic"),
    "Tablet":           ("Apple", "Samsung", "Lenovo", "Microsoft", "Xiaomi", "Misc", "Generic"),
    "Desktop computer": ("Apple", "Dell", "HP", "Lenovo", "Acer", "Microsoft", "MSI", "Misc", "Generic"),
    "Monitor":          ("Dell", "HP", "LG", "Samsung", "BenQ", "Acer", "Misc", "Generic"),
    "Television":       ("Samsung", "LG", "Sony", "TCL", "Panasonic", "Misc", "Generic"),
    "Printer":          ("HP", "Canon", "Brother", "Epson", "Panasonic", "Misc", "Generic"),
    "Accessories":      ("Anker", "Belkin", "Logitech", "Apple", "Samsung", "Misc", "Generic"),
    "Other electronics": ("Generic", "Misc", "Logitech", "Panasonic", "Belkin"),
}

# Working-status and damage sampling weights. A collection point sees mostly
# working or partly working kit, and a minority of badly damaged items.
WORKING_WEIGHTS = (0.52, 0.27, 0.21)
DAMAGE_WEIGHTS = (0.62, 0.24, 0.14)

# Column order. Must stay byte-identical to what the training loader expects.
COLUMNS = (
    "device_category",
    "brand",
    "age",
    "condition",
    "working_status",
    "physical_damage",
    "original_purchase_price",
    "estimated_purchase_value",
)

NOISE_SIGMA = 0.11      # per-device unexplained variation
DEMAND_SIGMA = 0.09     # per-device demand shock
PRICE_MISSING = None    # sentinel: leave the cell blank


# --- Helpers ---------------------------------------------------------------

def _condition_band(age: int) -> tuple[float, ...]:
    for (low, high), weights in CONDITION_BY_AGE_BAND.items():
        if low <= age <= high:
            return weights
    return CONDITION_BY_AGE_BAND[(MAX_AGE, MAX_AGE)]


def _allocate_ages(rng: random.Random, total: int) -> list[int]:
    """Stratified age allocation: a guaranteed minimum per age, surplus by decay.

    Using an exponential-decay weight for the surplus rather than a pure
    random draw is what stops ages 13-15 from collapsing to two or three rows.
    """
    base = MIN_PER_AGE
    if base * len(AGES) > total:
        raise ValueError("MIN_PER_AGE * len(AGES) exceeds ROWS_PER_CATEGORY")

    counts = {age: base for age in AGES}
    surplus = total - base * len(AGES)

    weights = [math.exp(-0.16 * age) for age in AGES]
    total_weight = sum(weights)

    # Largest-remainder apportionment so the surplus is allocated exactly.
    exact = [surplus * w / total_weight for w in weights]
    floors = [int(x) for x in exact]
    remainder = surplus - sum(floors)
    order = sorted(range(len(AGES)), key=lambda i: exact[i] - floors[i], reverse=True)
    for i in order[:remainder]:
        floors[i] += 1

    return [age for age, extra in zip(AGES, floors) for _ in range(counts[age] + extra)]


def _lognormal(rng: random.Random, mu: float, sigma: float) -> float:
    return math.exp(mu + sigma * rng.gauss(0.0, 1.0))


def _row_value(rng: random.Random, profile: dict, age: int, brand: str,
               condition: str, working: str, damage: str,
               price: float) -> float:
    """Apply the latent valuation process documented in the module docstring."""
    half_life = profile["half_life"]
    recovery = profile["recovery"]

    # 1. Category-specific decay. Different categories decay at genuinely
    #    different rates, which is the main thing the old generator lacked.
    age_factor = 0.5 ** (age / half_life)

    # 2. Each label contributes a *range*, not a point.
    condition_factor = rng.uniform(*CONDITION_RANGE[condition])
    working_factor = rng.uniform(*WORKING_RANGE[working])
    damage_factor = rng.uniform(*DAMAGE_RANGE[damage])

    # 3. Brand position.
    brand_factor = BRAND_TIER[brand]

    latent = price * age_factor * condition_factor * working_factor * damage_factor * brand_factor

    # 4. Asymptotic category recovery value. Soft rather than a hard clamp at
    #    one universal number: the approach is exponential, and the floor
    #    itself carries jitter, so dead devices do not pile onto a single
    #    identical target the way the old Rs 500 floor made 12.6% of rows do.
    floor = recovery * rng.uniform(0.80, 1.30)
    gap = latent - floor
    value = floor + gap * math.exp(-0.55 / (1.0 + age / 6.0)) if gap > 0 else floor * rng.uniform(0.85, 1.12)

    # 5. Irreducible noise: per-device, a demand shock, and a slow category
    #    market factor. Without these the target would be a deterministic
    #    function of the inputs and the model could fit it exactly, which
    #    would tell us nothing.
    market = _market_factor(rng, profile)
    value *= rng.lognormvariate(0.0, NOISE_SIGMA)
    value *= rng.lognormvariate(0.0, DEMAND_SIGMA)
    value *= market

    # 6. A small minority are effectively worthless (stripped for parts or
    #    data-bearing only), which is real but must stay a small minority.
    if rng.random() < 0.012:
        value *= rng.uniform(0.12, 0.45)

    return round(max(value, 1.0), 2)


# One slow-moving market factor per category, drawn once so the whole category
# shares a period of market conditions rather than drifting every row.
def _market_factor(rng: random.Random, profile: dict) -> float:
    key = profile["half_life"]
    factor = getattr(_market_factor, "_cache", None)
    if factor is None:
        factor = {}
        _market_factor._cache = factor
    if key not in factor:
        factor[key] = rng.lognormvariate(0.0, 0.07)
    return factor[key]


def generate_rows(seed: int = DEFAULT_SEED) -> list[dict]:
    """Build every row deterministically from ``seed``."""
    rng = random.Random(seed)
    rows: list[dict] = []

    for category in CATEGORIES:
        profile = CATEGORY_PROFILE[category]
        brands = CATEGORY_BRANDS[category]
        ages = _allocate_ages(rng, ROWS_PER_CATEGORY)

        for age in ages:
            brand = rng.choice(brands)
            condition = rng.choices(CONDITIONS, weights=_condition_band(age), k=1)[0]
            working = rng.choices(WORKING_STATUSES, weights=WORKING_WEIGHTS, k=1)[0]
            damage = rng.choices(PHYSICAL_DAMAGE, weights=DAMAGE_WEIGHTS, k=1)[0]

            # The latent price exists for every row, even when it is not
            # recorded, so the value is always internally consistent. Only the
            # *recording* of the price is sometimes absent.
            latent_price = _lognormal(rng, profile["price_mu"], profile["price_sigma"]) * BRAND_TIER[brand]
            latent_price = min(max(latent_price, 500.0), 400000.0)

            value = _row_value(rng, profile, age, brand, condition, working, damage, latent_price)

            record_price = rng.random() >= profile["missing_p"]
            rows.append({
                "device_category": category,
                "brand": brand,
                "age": age,
                "condition": condition,
                "working_status": working,
                "physical_damage": damage,
                "original_purchase_price": round(latent_price, 2) if record_price else PRICE_MISSING,
                "estimated_purchase_value": value,
            })

    return rows


def render_csv(rows: list[dict]) -> str:
    """Serialise rows to the exact text written to disk."""
    lines = [",".join(COLUMNS)]
    for row in rows:
        cells = []
        for column in COLUMNS:
            value = row[column]
            if value is PRICE_MISSING or value is None:
                cells.append("")
            elif isinstance(value, float):
                cells.append(f"{value:.2f}")
            else:
                cells.append(str(value))
        lines.append(",".join(cells))
    return "\n".join(lines) + "\n"


def dataset_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def default_output_path() -> Path:
    # backend/data/valuation_demo_dataset.csv, anchored like config.py does so
    # the path does not depend on the working directory.
    return Path(__file__).resolve().parents[2] / "data" / "valuation_demo_dataset.csv"


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.scripts.generate_valuation_dataset",
        description="Generate the SYNTHETIC SmartCycle valuation dataset (not real market data).",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help=f"Random seed (default {DEFAULT_SEED}).")
    parser.add_argument("--out", type=Path, default=None, help="Output CSV path.")
    parser.add_argument("--check", action="store_true", help="Print the hash without writing the file.")
    args = parser.parse_args()

    text = render_csv(generate_rows(args.seed))
    digest = dataset_hash(text)
    rows = len(text.strip().split("\n")) - 1

    print("SYNTHETIC dataset generated. This is NOT real market data.")
    print(f"  seed       : {args.seed}")
    print(f"  rows       : {rows}")
    print(f"  columns    : {len(COLUMNS)} ({', '.join(COLUMNS)})")
    print(f"  sha256     : {digest}")

    if args.check:
        return 0

    out = args.out or default_output_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="")
    print(f"  written to : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())