"""Routes for user analytics — events, summaries, recommendations, templates, research, teams, workspaces."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import AuthUser, require_auth
from app.models.user_analytics import (
    DashboardTemplate,
    Recommendation,
    SavedResearch,
    SharedWorkspace,
    Team,
    TeamMember,
    UsageEvent,
)
from app.schemas.user_analytics import (
    AnalyticsSummary,
    DashboardTemplateCreate,
    DashboardTemplateResponse,
    DashboardTemplateUpdate,
    RecommendationResponse,
    SavedResearchCreate,
    SavedResearchResponse,
    SavedResearchUpdate,
    SharedWorkspaceCreate,
    SharedWorkspaceResponse,
    SharedWorkspaceUpdate,
    TeamCreate,
    TeamMemberAdd,
    TeamMemberResponse,
    TeamResponse,
    TeamUpdate,
    UsageEventCreate,
    UsageEventResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["user-analytics"])


# ---------------------------------------------------------------------------
# Usage Events
# ---------------------------------------------------------------------------


@router.post("/events", response_model=UsageEventResponse, status_code=201)
async def track_event(
    body: UsageEventCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    event = UsageEvent(
        user_id=auth.user_id,
        event_type=body.event_type,
        event_data_json=body.event_data_json,
    )
    session.add(event)
    await session.flush()
    return event


# ---------------------------------------------------------------------------
# Analytics Summary
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=AnalyticsSummary)
async def get_summary(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    # Total events
    result = await session.execute(
        select(func.count(UsageEvent.id)).where(UsageEvent.user_id == auth.user_id)
    )
    total_events = result.scalar_one_or_none() or 0

    # Most viewed panels — extract from panel_view events
    result = await session.execute(
        select(UsageEvent.event_data_json)
        .where(UsageEvent.user_id == auth.user_id, UsageEvent.event_type == "panel_view")
    )
    panel_counts: dict[str, int] = {}
    for row in result.scalars().all():
        if row:
            try:
                data = json.loads(row)
                panel = data.get("panel", "unknown")
                panel_counts[panel] = panel_counts.get(panel, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass

    most_viewed = sorted(
        [{"name": k, "count": v} for k, v in panel_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    # Active days (distinct dates)
    result = await session.execute(
        select(func.count(distinct(func.date(UsageEvent.created_at))))
        .where(UsageEvent.user_id == auth.user_id)
    )
    active_days = result.scalar_one_or_none() or 0

    # Favorite symbols — extract from search/panel_view events
    result = await session.execute(
        select(UsageEvent.event_data_json)
        .where(
            UsageEvent.user_id == auth.user_id,
            UsageEvent.event_type.in_(["search", "panel_view", "api_call"]),
        )
    )
    symbol_counts: dict[str, int] = {}
    for row in result.scalars().all():
        if row:
            try:
                data = json.loads(row)
                symbol = data.get("symbol")
                if symbol:
                    symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass

    favorite_symbols = sorted(
        [{"symbol": k, "count": v} for k, v in symbol_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    return AnalyticsSummary(
        total_events=total_events,
        most_viewed_panels=most_viewed,
        active_days=active_days,
        favorite_symbols=favorite_symbols,
    )


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


@router.get("/recommendations", response_model=list[RecommendationResponse])
async def list_recommendations(
    dismissed: bool | None = Query(None),
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    query = (
        select(Recommendation)
        .where(Recommendation.user_id == auth.user_id)
        .order_by(Recommendation.created_at.desc())
    )
    if dismissed is not None:
        query = query.where(Recommendation.is_dismissed == dismissed)
    result = await session.execute(query)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Dashboard Templates CRUD
# ---------------------------------------------------------------------------


@router.get("/templates", response_model=list[DashboardTemplateResponse])
async def list_templates(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(DashboardTemplate)
        .where(
            (DashboardTemplate.is_public == True)  # noqa: E712
            | (DashboardTemplate.author_id == auth.user_id)
        )
        .order_by(DashboardTemplate.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/templates", response_model=DashboardTemplateResponse, status_code=201)
async def create_template(
    body: DashboardTemplateCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    template = DashboardTemplate(
        name=body.name,
        description=body.description,
        layout_json=body.layout_json,
        is_public=body.is_public,
        author_id=auth.user_id,
    )
    session.add(template)
    await session.flush()
    return template


@router.patch("/templates/{template_id}", response_model=DashboardTemplateResponse)
async def update_template(
    template_id: str,
    body: DashboardTemplateUpdate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(DashboardTemplate)
        .where(DashboardTemplate.id == template_id, DashboardTemplate.author_id == auth.user_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if body.name is not None:
        template.name = body.name
    if body.description is not None:
        template.description = body.description
    if body.layout_json is not None:
        template.layout_json = body.layout_json
    if body.is_public is not None:
        template.is_public = body.is_public

    await session.flush()
    await session.refresh(template)
    return template


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(DashboardTemplate)
        .where(DashboardTemplate.id == template_id, DashboardTemplate.author_id == auth.user_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    await session.delete(template)


# ---------------------------------------------------------------------------
# Saved Research CRUD
# ---------------------------------------------------------------------------


@router.get("/research", response_model=list[SavedResearchResponse])
async def list_research(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(SavedResearch)
        .where(
            (SavedResearch.user_id == auth.user_id)
            | (SavedResearch.is_public == True)  # noqa: E712
        )
        .order_by(SavedResearch.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/research", response_model=SavedResearchResponse, status_code=201)
async def create_research(
    body: SavedResearchCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    research = SavedResearch(
        user_id=auth.user_id,
        title=body.title,
        content=body.content,
        tags_json=body.tags_json,
        is_public=body.is_public,
    )
    session.add(research)
    await session.flush()
    return research


@router.patch("/research/{research_id}", response_model=SavedResearchResponse)
async def update_research(
    research_id: str,
    body: SavedResearchUpdate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(SavedResearch)
        .where(SavedResearch.id == research_id, SavedResearch.user_id == auth.user_id)
    )
    research = result.scalar_one_or_none()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    if body.title is not None:
        research.title = body.title
    if body.content is not None:
        research.content = body.content
    if body.tags_json is not None:
        research.tags_json = body.tags_json
    if body.is_public is not None:
        research.is_public = body.is_public

    await session.flush()
    await session.refresh(research)
    return research


@router.delete("/research/{research_id}", status_code=204)
async def delete_research(
    research_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(SavedResearch)
        .where(SavedResearch.id == research_id, SavedResearch.user_id == auth.user_id)
    )
    research = result.scalar_one_or_none()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")
    await session.delete(research)


# ---------------------------------------------------------------------------
# Teams CRUD
# ---------------------------------------------------------------------------


@router.get("/teams", response_model=list[TeamResponse])
async def list_teams(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    # Show teams where user is owner or member
    result = await session.execute(
        select(Team)
        .outerjoin(TeamMember, Team.id == TeamMember.team_id)
        .where((Team.owner_id == auth.user_id) | (TeamMember.user_id == auth.user_id))
        .distinct()
        .order_by(Team.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/teams", response_model=TeamResponse, status_code=201)
async def create_team(
    body: TeamCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    team = Team(
        name=body.name,
        description=body.description,
        owner_id=auth.user_id,
    )
    session.add(team)
    await session.flush()

    # Add owner as admin member
    member = TeamMember(
        team_id=team.id,
        user_id=auth.user_id,
        role="admin",
    )
    session.add(member)
    await session.flush()
    return team


@router.patch("/teams/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: str,
    body: TeamUpdate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Team).where(Team.id == team_id, Team.owner_id == auth.user_id)
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    if body.name is not None:
        team.name = body.name
    if body.description is not None:
        team.description = body.description

    await session.flush()
    await session.refresh(team)
    return team


@router.delete("/teams/{team_id}", status_code=204)
async def delete_team(
    team_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Team).where(Team.id == team_id, Team.owner_id == auth.user_id)
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    await session.delete(team)


# ---------------------------------------------------------------------------
# Team Members
# ---------------------------------------------------------------------------


@router.post("/teams/{team_id}/members", response_model=TeamMemberResponse, status_code=201)
async def add_team_member(
    team_id: str,
    body: TeamMemberAdd,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    # Only team owner or admin can add members
    result = await session.execute(
        select(Team).where(Team.id == team_id, Team.owner_id == auth.user_id)
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found or not authorized")

    # Check if already a member
    result = await session.execute(
        select(TeamMember)
        .where(TeamMember.team_id == team_id, TeamMember.user_id == body.user_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User is already a team member")

    member = TeamMember(
        team_id=team_id,
        user_id=body.user_id,
        role=body.role,
    )
    session.add(member)
    await session.flush()
    return member


@router.delete("/teams/{team_id}/members/{user_id}", status_code=204)
async def remove_team_member(
    team_id: str,
    user_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    # Only team owner can remove members
    result = await session.execute(
        select(Team).where(Team.id == team_id, Team.owner_id == auth.user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Team not found or not authorized")

    result = await session.execute(
        select(TeamMember)
        .where(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    await session.delete(member)


# ---------------------------------------------------------------------------
# Shared Workspaces CRUD
# ---------------------------------------------------------------------------


@router.get("/workspaces", response_model=list[SharedWorkspaceResponse])
async def list_workspaces(
    team_id: str | None = Query(None),
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    query = (
        select(SharedWorkspace)
        .join(Team, SharedWorkspace.team_id == Team.id)
        .outerjoin(TeamMember, Team.id == TeamMember.team_id)
        .where((Team.owner_id == auth.user_id) | (TeamMember.user_id == auth.user_id))
        .distinct()
        .order_by(SharedWorkspace.created_at.desc())
    )
    if team_id:
        query = query.where(SharedWorkspace.team_id == team_id)
    result = await session.execute(query)
    return list(result.scalars().all())


@router.post("/workspaces", response_model=SharedWorkspaceResponse, status_code=201)
async def create_workspace(
    body: SharedWorkspaceCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    # Verify user is member of the team
    result = await session.execute(
        select(Team)
        .outerjoin(TeamMember, Team.id == TeamMember.team_id)
        .where(
            Team.id == body.team_id,
            (Team.owner_id == auth.user_id) | (TeamMember.user_id == auth.user_id),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Team not found or not authorized")

    workspace = SharedWorkspace(
        team_id=body.team_id,
        name=body.name,
        workspace_config_json=body.workspace_config_json,
    )
    session.add(workspace)
    await session.flush()
    return workspace


@router.patch("/workspaces/{workspace_id}", response_model=SharedWorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    body: SharedWorkspaceUpdate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(SharedWorkspace)
        .join(Team, SharedWorkspace.team_id == Team.id)
        .where(SharedWorkspace.id == workspace_id, Team.owner_id == auth.user_id)
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if body.name is not None:
        workspace.name = body.name
    if body.workspace_config_json is not None:
        workspace.workspace_config_json = body.workspace_config_json

    await session.flush()
    await session.refresh(workspace)
    return workspace


@router.delete("/workspaces/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(SharedWorkspace)
        .join(Team, SharedWorkspace.team_id == Team.id)
        .where(SharedWorkspace.id == workspace_id, Team.owner_id == auth.user_id)
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await session.delete(workspace)
