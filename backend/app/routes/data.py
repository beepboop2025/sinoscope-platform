import json
import logging
import os
import re
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.services.cache import get_cached_json

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.get("/data/{category}")
async def get_market_data(category: str):
    """Get market data by category. Reads from Redis cache first, falls back to JSON files."""
    # Validate category name (prevent path traversal)
    if not re.match(r"^[a-zA-Z0-9_-]+$", category):
        raise HTTPException(status_code=400, detail="Invalid category")

    # Try Redis cache first
    cached = await get_cached_json(f"market:{category}")
    if cached:
        return cached

    # Fallback to JSON file (for backward compatibility with collector)
    data_dir = settings.DATA_DIR
    if not data_dir:
        # Default to the server/data directory
        data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "server", "data")

    file_path = os.path.join(data_dir, f"{category}.json")
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Read error")
