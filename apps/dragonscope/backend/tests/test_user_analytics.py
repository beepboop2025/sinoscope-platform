"""Tests for user analytics — event tracking, summary, teams, research."""

import json

import pytest


@pytest.mark.asyncio
async def test_track_event(client, seed_user):
    resp = await client.post(
        "/api/analytics/events",
        json={
            "eventType": "panel_view",
            "eventDataJson": json.dumps({"panel": "PanelChart", "symbol": "BTC"}),
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["eventType"] == "panel_view"


@pytest.mark.asyncio
async def test_analytics_summary_empty(client, seed_user):
    resp = await client.get("/api/analytics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["totalEvents"] == 0
    assert data["activeDays"] == 0
    assert data["mostViewedPanels"] == []
    assert data["favoriteSymbols"] == []


@pytest.mark.asyncio
async def test_analytics_summary_with_events(client, seed_user):
    """Track several events and verify summary aggregation."""
    # Track panel views
    for _ in range(3):
        await client.post(
            "/api/analytics/events",
            json={
                "eventType": "panel_view",
                "eventDataJson": json.dumps({"panel": "PanelChart", "symbol": "BTC"}),
            },
        )
    await client.post(
        "/api/analytics/events",
        json={
            "eventType": "panel_view",
            "eventDataJson": json.dumps({"panel": "PanelML"}),
        },
    )
    await client.post(
        "/api/analytics/events",
        json={
            "eventType": "search",
            "eventDataJson": json.dumps({"symbol": "ETH"}),
        },
    )

    resp = await client.get("/api/analytics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["totalEvents"] == 5
    assert data["activeDays"] >= 1

    # PanelChart should be most viewed
    panels = data["mostViewedPanels"]
    assert len(panels) >= 1
    assert panels[0]["name"] == "PanelChart"
    assert panels[0]["count"] == 3


@pytest.mark.asyncio
async def test_dashboard_template_crud(client, seed_user):
    """Test CRUD for dashboard templates."""
    resp = await client.post(
        "/api/analytics/templates",
        json={
            "name": "Crypto Overview",
            "description": "A layout for crypto traders",
            "layoutJson": json.dumps({"panels": ["PanelChart", "PanelML"]}),
            "isPublic": True,
        },
    )
    assert resp.status_code == 201
    template_id = resp.json()["id"]

    resp = await client.get("/api/analytics/templates")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    resp = await client.patch(
        f"/api/analytics/templates/{template_id}",
        json={"name": "Updated Crypto Overview"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Crypto Overview"

    resp = await client.delete(f"/api/analytics/templates/{template_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_saved_research_crud(client, seed_user):
    """Test CRUD for saved research."""
    resp = await client.post(
        "/api/analytics/research",
        json={
            "title": "BTC Market Analysis",
            "content": "Bitcoin is showing strong momentum...",
            "tagsJson": json.dumps(["bitcoin", "analysis"]),
            "isPublic": False,
        },
    )
    assert resp.status_code == 201
    research_id = resp.json()["id"]

    resp = await client.get("/api/analytics/research")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    resp = await client.patch(
        f"/api/analytics/research/{research_id}",
        json={"title": "Updated BTC Analysis"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated BTC Analysis"

    resp = await client.delete(f"/api/analytics/research/{research_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_team_crud(client, seed_user):
    """Test team creation and membership."""
    # Create team
    resp = await client.post(
        "/api/analytics/teams",
        json={
            "name": "Alpha Team",
            "description": "Market analysis team",
        },
    )
    assert resp.status_code == 201
    team_id = resp.json()["id"]

    # List teams
    resp = await client.get("/api/analytics/teams")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    # Update team
    resp = await client.patch(
        f"/api/analytics/teams/{team_id}",
        json={"name": "Alpha Team v2"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Alpha Team v2"

    # Delete team
    resp = await client.delete(f"/api/analytics/teams/{team_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_shared_workspace_crud(client, seed_user):
    """Test shared workspace lifecycle."""
    # Create team first
    team_resp = await client.post(
        "/api/analytics/teams",
        json={"name": "Research Team"},
    )
    team_id = team_resp.json()["id"]

    # Create workspace
    resp = await client.post(
        "/api/analytics/workspaces",
        json={
            "teamId": team_id,
            "name": "Shared Dashboard",
            "workspaceConfigJson": json.dumps({"panels": ["PanelChart"]}),
        },
    )
    assert resp.status_code == 201
    workspace_id = resp.json()["id"]

    # List workspaces
    resp = await client.get("/api/analytics/workspaces")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    # Update workspace
    resp = await client.patch(
        f"/api/analytics/workspaces/{workspace_id}",
        json={"name": "Updated Dashboard"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Dashboard"

    # Delete workspace
    resp = await client.delete(f"/api/analytics/workspaces/{workspace_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_recommendations_list(client, seed_user):
    """Test recommendations endpoint returns empty list initially."""
    resp = await client.get("/api/analytics/recommendations")
    assert resp.status_code == 200
    assert resp.json() == []
