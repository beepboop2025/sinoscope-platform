from datetime import datetime

from pydantic import BaseModel, Field


class HoldingResponse(BaseModel):
    id: str
    portfolio_id: str
    symbol: str
    asset_type: str
    quantity: float
    avg_cost: float
    notes: str | None = None
    added_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HoldingCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    asset_type: str = "stock"
    quantity: float = Field(gt=0)
    avg_cost: float = Field(ge=0)
    notes: str | None = None


class PortfolioResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    holdings: list[HoldingResponse] = []

    model_config = {"from_attributes": True}


class PortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class PortfolioUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
