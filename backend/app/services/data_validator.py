"""
Category-specific validation for market data ticks.

Validates price bounds per asset category, checks for suspicious price
changes, and produces a quality score based on freshness, completeness,
and validity.

Usage:
    from app.services.data_validator import validate_tick, ValidationResult

    result = validate_tick("crypto", {"symbol": "BTC", "price": 65000.0, ...})
    if not result.is_valid:
        logger.warning("Invalid tick: %s", result.warnings)
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Price bounds per category: (min_exclusive, max_inclusive) ──────────────────
PRICE_BOUNDS: dict[str, tuple[float, float]] = {
    "crypto": (0.0, 1_000_000.0),
    "forex": (0.0, 10_000.0),
    "stocks": (0.0, 1_000_000.0),
    "bonds": (-10.0, 30.0),
    "commodities": (0.0, 100_000.0),
}

# ── Required fields per category ──────────────────────────────────────────────
REQUIRED_FIELDS: dict[str, list[str]] = {
    "crypto": ["symbol", "price"],
    "forex": ["symbol", "price"],
    "stocks": ["symbol", "price"],
    "bonds": ["symbol", "price"],
    "commodities": ["symbol", "price"],
}

# ── Freshness windows (seconds) per category: full-score window ───────────────
FRESHNESS_WINDOWS: dict[str, float] = {
    "crypto": 120.0,       # 2 minutes
    "forex": 300.0,        # 5 minutes
    "stocks": 3600.0,      # 1 hour
    "bonds": 86400.0,      # 1 day
    "commodities": 3600.0, # 1 hour
}

# Suspicious change: flag if price changes by more than this fraction
SUSPICIOUS_CHANGE_THRESHOLD = 0.50  # 50%


@dataclass
class ValidationResult:
    """Outcome of validating a single tick."""

    is_valid: bool = True
    quality_score: float = 1.0  # 0.0 – 1.0
    warnings: list[str] = field(default_factory=list)


def validate_tick(category: str, data: dict[str, Any]) -> ValidationResult:
    """
    Validate a single market-data tick.

    Args:
        category: Asset category (crypto, forex, stocks, bonds, commodities).
        data: Tick payload — must include at least the fields listed in
              REQUIRED_FIELDS for the category.

    Returns:
        ValidationResult with is_valid, quality_score, and any warnings.
    """
    result = ValidationResult()

    if category not in PRICE_BOUNDS:
        result.warnings.append(f"Unknown category '{category}' — skipping bounds check")
        # Still score completeness
        _score_completeness(result, category, data)
        _score_freshness(result, category, data)
        return result

    # ── Completeness ──────────────────────────────────────────────────────────
    completeness = _score_completeness(result, category, data)

    # ── Validity (bounds check) ───────────────────────────────────────────────
    validity = _score_validity(result, category, data)

    # ── Freshness ─────────────────────────────────────────────────────────────
    freshness = _score_freshness(result, category, data)

    # ── Suspicious change detection ───────────────────────────────────────────
    _check_suspicious_change(result, data)

    # ── Composite quality score (weighted) ────────────────────────────────────
    result.quality_score = round(
        0.3 * freshness + 0.3 * completeness + 0.4 * validity, 3
    )

    # Mark invalid if the bounds check failed hard
    if validity == 0.0:
        result.is_valid = False

    return result


# ── Scoring helpers ───────────────────────────────────────────────────────────


def _score_completeness(
    result: ValidationResult, category: str, data: dict[str, Any]
) -> float:
    """Return 0.0–1.0 based on how many required fields are present."""
    required = REQUIRED_FIELDS.get(category, ["symbol", "price"])
    if not required:
        return 1.0

    present = sum(1 for f in required if data.get(f) is not None)
    score = present / len(required)

    missing = [f for f in required if data.get(f) is None]
    if missing:
        result.warnings.append(f"Missing fields: {missing}")

    return score


def _score_validity(
    result: ValidationResult, category: str, data: dict[str, Any]
) -> float:
    """Return 1.0 if price is within bounds, 0.0 if out of bounds."""
    price = data.get("price")
    if price is None:
        return 0.0

    try:
        price = float(price)
    except (TypeError, ValueError):
        result.warnings.append(f"Non-numeric price: {data.get('price')!r}")
        return 0.0

    lower, upper = PRICE_BOUNDS[category]
    if price <= lower or price > upper:
        result.warnings.append(
            f"Price {price} out of bounds for {category} ({lower}, {upper}]"
        )
        result.is_valid = False
        return 0.0

    return 1.0


def _score_freshness(
    result: ValidationResult, category: str, data: dict[str, Any]
) -> float:
    """Return 0.0–1.0 based on data age vs category window."""
    ts = data.get("timestamp") or data.get("time") or data.get("updated_at")
    if ts is None:
        # No timestamp — can't judge freshness, give neutral score
        return 0.5

    try:
        if isinstance(ts, (int, float)):
            age_seconds = time.time() - ts
        else:
            # Assume ISO-format string; attempt parse
            from datetime import datetime, timezone

            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            age_seconds = (datetime.now(timezone.utc) - dt).total_seconds()
    except Exception:
        result.warnings.append(f"Unparseable timestamp: {ts!r}")
        return 0.5

    window = FRESHNESS_WINDOWS.get(category, 3600.0)
    if age_seconds <= 0:
        return 1.0
    if age_seconds >= window * 3:
        result.warnings.append(f"Data is stale ({age_seconds:.0f}s old, window={window:.0f}s)")
        return 0.0

    # Linear decay from 1.0 to 0.0 over 3x the window
    return max(0.0, 1.0 - age_seconds / (window * 3))


def _check_suspicious_change(result: ValidationResult, data: dict[str, Any]) -> None:
    """Flag a tick if change_pct exceeds the threshold."""
    change_pct = data.get("change_pct")
    if change_pct is None:
        return

    try:
        change_pct = float(change_pct)
    except (TypeError, ValueError):
        return

    if abs(change_pct) > SUSPICIOUS_CHANGE_THRESHOLD * 100:
        result.warnings.append(
            f"Suspicious price change: {change_pct:.2f}% exceeds "
            f"{SUSPICIOUS_CHANGE_THRESHOLD * 100:.0f}% threshold"
        )
