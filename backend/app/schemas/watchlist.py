from datetime import datetime

from pydantic import BaseModel, Field


class WatchlistItemResponse(BaseModel):
    id: str
    watchlist_id: str
    symbol: str
    asset_type: str
    added_at: datetime

    model_config = {"from_attributes": True}


class WatchlistItemCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    asset_type: str = "stock"


class WatchlistResponse(BaseModel):
    id: str
    user_id: str
    name: str
    created_at: datetime
    updated_at: datetime
    items: list[WatchlistItemResponse] = []

    model_config = {"from_attributes": True}


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
