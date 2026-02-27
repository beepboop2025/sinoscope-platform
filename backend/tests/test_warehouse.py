"""Tests for data warehouse — overview and quality scoring."""

import pytest


@pytest.mark.asyncio
async def test_warehouse_overview_empty(client, seed_user):
    """Test overview endpoint returns valid structure when warehouse is empty."""
    resp = await client.get("/api/warehouse/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["totalAssets"] == 0
    assert data["totalFactRecords"] == 0
    assert "etlHealthSummary" in data
    assert data["etlHealthSummary"]["healthy"] == 0
    assert data["etlHealthSummary"]["degraded"] == 0
    assert data["etlHealthSummary"]["failed"] == 0
    assert "qualitySummary" in data
    assert data["qualitySummary"]["tablesChecked"] == 0


@pytest.mark.asyncio
async def test_etl_health_empty(client, seed_user):
    """Test ETL health endpoint returns empty list when no checks have run."""
    resp = await client.get("/api/warehouse/etl-health")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_quality_scores_empty(client, seed_user):
    """Test quality scores endpoint returns empty list initially."""
    resp = await client.get("/api/warehouse/quality-scores")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_trigger_quality_check(client, seed_user):
    """Test triggering a quality check on a known table."""
    resp = await client.post("/api/warehouse/quality-check/dim_assets")
    assert resp.status_code == 201
    data = resp.json()
    assert data["tableName"] == "dim_assets"
    assert "freshnessScore" in data
    assert "completenessScore" in data
    assert "validityScore" in data
    assert "overallScore" in data
    assert 0.0 <= data["overallScore"] <= 1.0


@pytest.mark.asyncio
async def test_trigger_quality_check_unknown_table(client, seed_user):
    """Test quality check on unknown table returns low scores."""
    resp = await client.post("/api/warehouse/quality-check/nonexistent_table")
    assert resp.status_code == 201
    data = resp.json()
    assert data["tableName"] == "nonexistent_table"
    # Unknown table should have low scores
    assert data["freshnessScore"] == 0.0
    assert data["completenessScore"] == 0.0


@pytest.mark.asyncio
async def test_quality_scores_after_check(client, seed_user):
    """Test quality scores reflect previous checks."""
    # Trigger two checks
    await client.post("/api/warehouse/quality-check/dim_assets")
    await client.post("/api/warehouse/quality-check/fact_prices")

    resp = await client.get("/api/warehouse/quality-scores")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_lineage_empty(client, seed_user):
    """Test lineage for a record that doesn't exist."""
    resp = await client.get("/api/warehouse/lineage/dim_assets/nonexistent-id")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_overview_reflects_quality_checks(client, seed_user):
    """Test that overview includes quality summary after running checks."""
    await client.post("/api/warehouse/quality-check/dim_assets")

    resp = await client.get("/api/warehouse/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["qualitySummary"]["tablesChecked"] >= 1
