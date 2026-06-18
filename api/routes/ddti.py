"""DDTI API — serves the censorship selectivity/novelty index + the dashboard.

Reads what processors.ddti_index.DDTIIndexProcessor publishes to Redis:
  ddti:index:latest   — the ranked threat index (JSON)
  alerts:ddti         — stream of newly-sensitive / high-threat terms
"""

import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ddti", tags=["ddti"])

_DASHBOARD = Path(__file__).resolve().parent.parent.parent / "dashboards" / "ddti_dashboard.html"


def _redis():
    import redis
    return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)


@router.get("/index")
async def ddti_index():
    """Latest DDTI threat index. status='live' when real data exists."""
    try:
        r = _redis()
        raw = r.get("ddti:index:latest")
        r.close()
        if not raw:
            return JSONResponse({
                "status": "empty",
                "note": "No index computed yet. Enable ddti_probe in sources.yaml and run "
                        "generate_ddti_index once deletions accumulate.",
                "ranked": [],
            })
        data = json.loads(raw)
        data["status"] = "live"
        return data
    except Exception as e:
        logger.warning(f"[DDTI-API] index read failed: {e}")
        return JSONResponse({"status": "error", "error": str(e), "ranked": []})


@router.get("/alerts")
async def ddti_alerts(limit: int = Query(50, ge=1, le=200)):
    """Recent newly-sensitive / high-threat term alerts (newest first)."""
    try:
        r = _redis()
        items = r.lrange("alerts:ddti", 0, limit - 1)
        r.close()
        return {"alerts": [json.loads(x) for x in items]}
    except Exception as e:
        return {"alerts": [], "error": str(e)}


@router.get("/dashboard", response_class=HTMLResponse)
async def ddti_dashboard():
    """The visual dashboard (same-origin, so live fetch works without CORS)."""
    try:
        return HTMLResponse(_DASHBOARD.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return HTMLResponse("<h1>ddti_dashboard.html not found</h1>", status_code=404)
