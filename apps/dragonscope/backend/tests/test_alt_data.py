"""Tests for alternative data endpoints — schema validation and empty state."""

import pytest


@pytest.mark.asyncio
async def test_insider_trades_empty(client):
    resp = await client.get("/api/alt-data/insider-trades")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_insider_trades_with_symbol_filter(client):
    resp = await client.get("/api/alt-data/insider-trades", params={"symbol": "AAPL"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_short_interest_empty(client):
    resp = await client.get("/api/alt-data/short-interest")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_short_interest_with_symbol_filter(client):
    resp = await client.get("/api/alt-data/short-interest", params={"symbol": "TSLA"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_trends_empty(client):
    resp = await client.get("/api/alt-data/trends")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_trends_with_keyword_filter(client):
    resp = await client.get("/api/alt-data/trends", params={"keyword": "AI"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_government_contracts_empty(client):
    resp = await client.get("/api/alt-data/government-contracts")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_government_contracts_with_vendor_filter(client):
    resp = await client.get("/api/alt-data/government-contracts", params={"vendor": "Microsoft"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_patents_empty(client):
    resp = await client.get("/api/alt-data/patents")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_patents_with_assignee_filter(client):
    resp = await client.get("/api/alt-data/patents", params={"assignee": "Apple"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_jobs_empty(client):
    resp = await client.get("/api/alt-data/jobs")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_jobs_with_company_filter(client):
    resp = await client.get("/api/alt-data/jobs", params={"company": "Google"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_weather_empty(client):
    resp = await client.get("/api/alt-data/weather")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_weather_with_region_filter(client):
    resp = await client.get("/api/alt-data/weather", params={"region": "Florida"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_summary_empty(client):
    resp = await client.get("/api/alt-data/summary/AAPL")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "AAPL"
    assert data["insider_trades_count"] == 0
    assert data["short_interest_latest"] is None
    assert data["trend_score"] is None
    assert data["recent_contracts"] == 0
