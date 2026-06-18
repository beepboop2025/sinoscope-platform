"""
Data quality monitoring service.

Computes per-category freshness, completeness, and overall health grades
by inspecting Redis-cached market data.

Usage:
    from app.services.data_quality import DataQualityService

    svc = DataQualityService()
    report = await svc.get_quality_report()
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.redis import get_redis

logger = logging.getLogger(__name__)

# ── Category configuration ────────────────────────────────────────────────────
# full_score_window: data younger than this gets 100% freshness
# required_fields: fields that must be present for completeness scoring

CATEGORY_CONFIG: dict[str, dict[str, Any]] = {
    "crypto": {
        "full_score_window": 120.0,      # 2 minutes
        "required_fields": ["symbol", "price", "market_cap", "volume"],
    },
    "forex": {
        "full_score_window": 300.0,      # 5 minutes
        "required_fields": ["symbol", "price", "change_pct"],
    },
    "stocks": {
        "full_score_window": 3600.0,     # 1 hour
        "required_fields": ["symbol", "price", "volume", "change_pct"],
    },
    "bonds": {
        "full_score_window": 86400.0,    # 1 day
        "required_fields": ["symbol", "price"],
    },
    "commodities": {
        "full_score_window": 3600.0,     # 1 hour
        "required_fields": ["symbol", "price"],
    },
    "indices": {
        "full_score_window": 3600.0,
        "required_fields": ["symbol", "price", "change_pct"],
    },
}


@dataclass
class CategoryQuality:
    """Quality metrics for a single data category."""

    category: str
    freshness_score: float = 0.0        # 0.0–1.0
    completeness_score: float = 0.0     # 0.0–1.0
    record_count: int = 0
    last_updated: str | None = None     # ISO timestamp
    grade: str = "F"


@dataclass
class QualityReport:
    """Full quality report across all data categories."""

    overall_grade: str = "F"
    overall_score: float = 0.0
    categories: dict[str, CategoryQuality] = field(default_factory=dict)
    checked_at: str = ""


class DataQualityService:
    """Evaluates market-data quality from Redis cache."""

    async def get_quality_report(self) -> QualityReport:
        """
        Check all configured categories and build a health report.

        Returns:
            QualityReport with per-category breakdown and overall grade.
        """
        report = QualityReport(
            checked_at=datetime.now(timezone.utc).isoformat(),
        )

        scores: list[float] = []

        for category, config in CATEGORY_CONFIG.items():
            cq = await self._evaluate_category(category, config)
            report.categories[category] = cq
            combined = 0.5 * cq.freshness_score + 0.5 * cq.completeness_score
            scores.append(combined)

        if scores:
            report.overall_score = round(sum(scores) / len(scores), 3)

        report.overall_grade = _score_to_grade(report.overall_score)
        return report

    async def get_category_quality(self, category: str) -> CategoryQuality:
        """
        Evaluate quality for a single category.

        Args:
            category: One of the keys in CATEGORY_CONFIG, or an arbitrary
                      Redis key suffix under ``market:<category>``.

        Returns:
            CategoryQuality for the requested category.
        """
        config = CATEGORY_CONFIG.get(category, {
            "full_score_window": 3600.0,
            "required_fields": ["symbol", "price"],
        })
        return await self._evaluate_category(category, config)

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _evaluate_category(
        self, category: str, config: dict[str, Any]
    ) -> CategoryQuality:
        cq = CategoryQuality(category=category)

        try:
            r = get_redis()
            raw = await r.get(f"market:{category}")
        except Exception as e:
            logger.warning("Redis read failed for market:%s: %s", category, e)
            return cq

        if raw is None:
            return cq

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid JSON in market:%s", category)
            return cq

        # Data may be a list of records or a dict with a nested list
        records: list[dict[str, Any]] = []
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            # Try common wrapper keys
            for key in ("data", "items", "records", "results"):
                if isinstance(data.get(key), list):
                    records = data[key]
                    break
            if not records:
                # Treat the dict itself as a single record
                records = [data]

        cq.record_count = len(records)

        # ── Freshness ─────────────────────────────────────────────────────────
        cq.freshness_score, cq.last_updated = self._compute_freshness(
            records, config["full_score_window"]
        )

        # ── Completeness ──────────────────────────────────────────────────────
        cq.completeness_score = self._compute_completeness(
            records, config["required_fields"]
        )

        # ── Grade ─────────────────────────────────────────────────────────────
        combined = 0.5 * cq.freshness_score + 0.5 * cq.completeness_score
        cq.grade = _score_to_grade(combined)

        return cq

    @staticmethod
    def _compute_freshness(
        records: list[dict[str, Any]], full_score_window: float
    ) -> tuple[float, str | None]:
        """Return (score 0–1, most_recent_timestamp_iso)."""
        now = time.time()
        most_recent: float | None = None

        for rec in records:
            ts = rec.get("timestamp") or rec.get("time") or rec.get("updated_at")
            if ts is None:
                continue
            try:
                if isinstance(ts, (int, float)):
                    epoch = float(ts)
                else:
                    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                    epoch = dt.timestamp()
                if most_recent is None or epoch > most_recent:
                    most_recent = epoch
            except Exception:
                continue

        if most_recent is None:
            return 0.5, None  # Unknown freshness

        age = now - most_recent
        last_updated_iso = datetime.fromtimestamp(most_recent, tz=timezone.utc).isoformat()

        if age <= 0:
            return 1.0, last_updated_iso
        if age >= full_score_window * 3:
            return 0.0, last_updated_iso

        score = max(0.0, 1.0 - age / (full_score_window * 3))
        return round(score, 3), last_updated_iso

    @staticmethod
    def _compute_completeness(
        records: list[dict[str, Any]], required_fields: list[str]
    ) -> float:
        """Return 0.0–1.0 average completeness across all records."""
        if not records or not required_fields:
            return 0.0

        total = 0.0
        for rec in records:
            present = sum(1 for f in required_fields if rec.get(f) is not None)
            total += present / len(required_fields)

        return round(total / len(records), 3)


def _score_to_grade(score: float) -> str:
    """Convert a 0.0–1.0 score to a letter grade."""
    if score >= 0.9:
        return "A"
    if score >= 0.75:
        return "B"
    if score >= 0.6:
        return "C"
    if score >= 0.4:
        return "D"
    return "F"
