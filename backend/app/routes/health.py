import logging
from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import text

from app.database import async_session_factory
from app.redis import get_redis

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health_check():
    status = {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

    # Check database
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        status["database"] = "connected"
    except Exception as e:
        status["database"] = f"error: {e}"
        status["status"] = "degraded"

    # Check Redis
    try:
        r = get_redis()
        await r.ping()
        status["redis"] = "connected"
    except Exception as e:
        status["redis"] = f"error: {e}"
        status["status"] = "degraded"

    # Check collector last update
    try:
        r = get_redis()
        last_update = await r.get("collector:last_update")
        if last_update:
            status["collector_last_update"] = last_update
    except Exception:
        pass

    return status
