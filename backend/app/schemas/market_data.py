from typing import Any

from pydantic import BaseModel


class MarketDataResponse(BaseModel):
    _updated: str
    _source: str
    data: Any
