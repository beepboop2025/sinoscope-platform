"""
Data quality API routes.

Exposes data-quality health reports via:
    GET /data-quality       — full report across all categories
    GET /data-quality/{cat} — single-category report

Note: main.py includes this router with prefix="/api", so the full
paths are /api/data-quality and /api/data-quality/{category}.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.services.data_quality import DataQualityService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/data-quality", tags=["data-quality"])

_quality_service = DataQualityService()


@router.get("")
async def get_quality_report() -> dict[str, Any]:
    """Return a full quality report for all data categories."""
    try:
        report = await _quality_service.get_quality_report()
    except Exception as e:
        logger.error("Failed to generate quality report: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate quality report")

    return {
        "overall_grade": report.overall_grade,
        "overall_score": report.overall_score,
        "checked_at": report.checked_at,
        "categories": {
            name: {
                "freshness_score": cq.freshness_score,
                "completeness_score": cq.completeness_score,
                "record_count": cq.record_count,
                "last_updated": cq.last_updated,
                "grade": cq.grade,
            }
            for name, cq in report.categories.items()
        },
    }


@router.get("/{category}")
async def get_category_quality(category: str) -> dict[str, Any]:
    """Return quality metrics for a specific data category."""
    try:
        cq = await _quality_service.get_category_quality(category)
    except Exception as e:
        logger.error("Failed to get quality for %s: %s", category, e)
        raise HTTPException(status_code=500, detail="Failed to get category quality")

    return {
        "category": cq.category,
        "freshness_score": cq.freshness_score,
        "completeness_score": cq.completeness_score,
        "record_count": cq.record_count,
        "last_updated": cq.last_updated,
        "grade": cq.grade,
    }
