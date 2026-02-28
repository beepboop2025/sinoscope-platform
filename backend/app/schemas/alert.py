from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AlertResponse(BaseModel):
    id: str
    user_id: str
    symbol: str
    condition: str
    threshold: float
    is_active: bool
    triggered: bool
    triggered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    condition: Literal["price_above", "price_below", "pct_change_above", "pct_change_below"]
    threshold: float


class AlertUpdate(BaseModel):
    is_active: bool | None = None
    condition: Literal["price_above", "price_below", "pct_change_above", "pct_change_below"] | None = None
    threshold: float | None = None
