from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyResponse(BaseModel):
    id: str
    provider: str
    label: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    key: str = Field(min_length=1)
    label: str | None = None
