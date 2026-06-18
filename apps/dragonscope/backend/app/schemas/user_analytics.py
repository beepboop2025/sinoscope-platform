"""Pydantic v2 schemas for user analytics."""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# UsageEvent
# ---------------------------------------------------------------------------
class UsageEventCreate(BaseModel):
    event_type: str = Field(pattern=r"^(page_view|panel_view|api_call|search|export)$")
    event_data_json: str | None = None


class UsageEventResponse(BaseModel):
    id: str
    user_id: str
    event_type: str
    event_data_json: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------
class RecommendationResponse(BaseModel):
    id: str
    user_id: str
    rec_type: str
    title: str
    description: str | None = None
    data_json: str | None = None
    is_dismissed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# DashboardTemplate
# ---------------------------------------------------------------------------
class DashboardTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    layout_json: str
    is_public: bool = True


class DashboardTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    layout_json: str | None = None
    is_public: bool | None = None


class DashboardTemplateResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    layout_json: str
    is_public: bool
    author_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# SavedResearch
# ---------------------------------------------------------------------------
class SavedResearchCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1)
    tags_json: str | None = None
    is_public: bool = False


class SavedResearchUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    tags_json: str | None = None
    is_public: bool | None = None


class SavedResearchResponse(BaseModel):
    id: str
    user_id: str
    title: str
    content: str
    tags_json: str | None = None
    is_public: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------
class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class TeamUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class TeamResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    owner_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# TeamMember
# ---------------------------------------------------------------------------
class TeamMemberAdd(BaseModel):
    user_id: str
    role: str = Field(default="member", pattern=r"^(member|admin)$")


class TeamMemberResponse(BaseModel):
    id: str
    team_id: str
    user_id: str
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# SharedWorkspace
# ---------------------------------------------------------------------------
class SharedWorkspaceCreate(BaseModel):
    team_id: str
    name: str = Field(min_length=1, max_length=255)
    workspace_config_json: str


class SharedWorkspaceUpdate(BaseModel):
    name: str | None = None
    workspace_config_json: str | None = None


class SharedWorkspaceResponse(BaseModel):
    id: str
    team_id: str
    name: str
    workspace_config_json: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Analytics Summary
# ---------------------------------------------------------------------------
class AnalyticsSummary(BaseModel):
    total_events: int
    most_viewed_panels: list[dict[str, int]]
    active_days: int
    favorite_symbols: list[dict[str, int]]
