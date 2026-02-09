from datetime import datetime

from pydantic import BaseModel, EmailStr


class PreferencesResponse(BaseModel):
    id: str
    user_id: str
    default_workspace: str
    theme: str
    refresh_interval: int
    notifications: bool

    model_config = {"from_attributes": True}


class PreferencesUpdate(BaseModel):
    default_workspace: str | None = None
    theme: str | None = None
    refresh_interval: int | None = None
    notifications: bool | None = None


class UserResponse(BaseModel):
    id: str
    clerk_id: str
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
    created_at: datetime
    updated_at: datetime
    preferences: PreferencesResponse | None = None

    model_config = {"from_attributes": True}


class UserSync(BaseModel):
    email: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None

    model_config = {"from_attributes": True}
