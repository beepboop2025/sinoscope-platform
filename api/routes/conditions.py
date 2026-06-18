"""China Economic Conditions API — serves the CBB conditions index + report + dashboard.

Reads what processors.conditions_index.ConditionsIndexProcessor publishes to Redis:
  cbb:latest  — the latest sector-by-sector conditions snapshot (JSON)
"""

import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conditions", tags=["conditions"])

_DASHBOARD = Path(__file__).resolve().parent.parent.parent / "dashboards" / "conditions_dashboard.html"
_REPORT_PATH = Path(os.getenv("DATA_DIR", "./data")) / "cbb" / "reports" / "latest.md"

_SAMPLE_REPORT = """# China Economic Conditions Report (sample)

> This is a fallback sample. Run `processors/conditions_report.py` to generate a live report.

## Sector summary

| Sector | Region | D | Momentum | Confidence |
|--------|--------|---|----------|------------|
| Electronics & machinery | coastal_export | 12.3 | ▲ | high |
| Textiles & apparel | coastal_export | -8.1 | ▼ | med |
| Steel & metals | northeast | 3.4 | ▬ | low |
| Property & construction | national | -22.7 | ▼ | med |
| Logistics & freight | national | 7.8 | ▲ | high |

## Cross-source triangulation

- Mirror-reported trade gaps are widest in property-linked sectors.
- High-frequency freight indicators are turning up while official manufacturing PMI is flat.
"""


def _redis():
    import redis
    return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)


@router.get("/index")
async def conditions_index():
    """Latest China economic conditions index. status='live' when real data exists."""
    try:
        r = _redis()
        raw = r.get("cbb:latest")
        r.close()
        if not raw:
            return JSONResponse({
                "status": "empty",
                "note": "No conditions index computed yet. Run processors/conditions_index or "
                        "scripts/conditions_pull.py to populate cbb:latest.",
                "sectors": [],
            })
        data = json.loads(raw)
        data["status"] = "live"
        return data
    except Exception as e:
        logger.warning(f"[Conditions-API] index read failed: {e}")
        return JSONResponse({"status": "error", "error": str(e), "sectors": []})


@router.get("/report")
async def conditions_report():
    """Latest China economic conditions markdown report."""
    try:
        if _REPORT_PATH.exists():
            report = _REPORT_PATH.read_text(encoding="utf-8")
            return {"status": "live", "report": report}
    except Exception as e:
        logger.warning(f"[Conditions-API] report read failed: {e}")

    return {"status": "sample", "report": _SAMPLE_REPORT}


@router.get("/dashboard", response_class=HTMLResponse)
async def conditions_dashboard():
    """The visual conditions dashboard (same-origin, so live fetch works without CORS)."""
    try:
        return HTMLResponse(_DASHBOARD.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return HTMLResponse("<h1>conditions_dashboard.html not found</h1>", status_code=404)
