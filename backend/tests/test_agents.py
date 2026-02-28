"""Tests for autonomous agents — creation, market monitor, anomaly detection."""

import json

import pytest


@pytest.mark.asyncio
async def test_create_agent(client, seed_user):
    resp = await client.post(
        "/api/agents",
        json={
            "name": "BTC Monitor",
            "agent_type": "market_monitor",
            "config_json": json.dumps({
                "symbols": ["BTC"],
                "price_thresholds": {"BTC": {"above": 100000, "below": 20000}},
            }),
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "BTC Monitor"
    assert data["agentType"] == "market_monitor"
    assert data["isActive"] is True


@pytest.mark.asyncio
async def test_list_agents(client, seed_user):
    # Create two agents
    await client.post(
        "/api/agents",
        json={
            "name": "Agent 1",
            "agent_type": "anomaly_detector",
            "config_json": "{}",
        },
    )
    await client.post(
        "/api/agents",
        json={
            "name": "Agent 2",
            "agent_type": "correlation_finder",
            "config_json": "{}",
        },
    )
    resp = await client.get("/api/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_update_agent(client, seed_user):
    create = await client.post(
        "/api/agents",
        json={
            "name": "Old Name",
            "agent_type": "market_monitor",
            "config_json": "{}",
        },
    )
    agent_id = create.json()["id"]

    resp = await client.patch(
        f"/api/agents/{agent_id}",
        json={"name": "New Name", "isActive": False},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"
    assert resp.json()["isActive"] is False


@pytest.mark.asyncio
async def test_delete_agent(client, seed_user):
    create = await client.post(
        "/api/agents",
        json={
            "name": "To Delete",
            "agent_type": "research_generator",
            "config_json": "{}",
        },
    )
    agent_id = create.json()["id"]

    resp = await client.delete(f"/api/agents/{agent_id}")
    assert resp.status_code == 204

    # Verify deleted
    resp = await client.get(f"/api/agents/{agent_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_market_monitor_run(client, seed_user, mock_redis):
    """Test triggering an agent run with market data in Redis."""
    # Seed Redis with crypto data where BTC > 100000
    crypto_data = json.dumps({
        "data": [
            {
                "symbol": "BTC",
                "current_price": 105000,
                "total_volume": 5000000000,
                "price_change_percentage_24h": 3.5,
            },
        ],
    })
    await mock_redis.set("market:crypto_markets", crypto_data)

    # Create agent with BTC price threshold
    create = await client.post(
        "/api/agents",
        json={
            "name": "BTC Threshold Monitor",
            "agent_type": "market_monitor",
            "config_json": json.dumps({
                "symbols": ["BTC"],
                "price_thresholds": {"BTC": {"above": 100000}},
            }),
        },
    )
    agent_id = create.json()["id"]

    # Trigger run
    resp = await client.post(f"/api/agents/{agent_id}/run")
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "completed"
    assert data["findingsCount"] >= 1


@pytest.mark.asyncio
async def test_anomaly_detection_run(client, seed_user, mock_redis):
    """Test anomaly detection with large price movements."""
    crypto_data = json.dumps({
        "data": [
            {
                "symbol": "DOGE",
                "current_price": 0.15,
                "total_volume": 2000000000,
                "price_change_percentage_24h": 25.0,  # >9% threshold (3*3)
            },
            {
                "symbol": "ETH",
                "current_price": 3500,
                "total_volume": 10000000000,
                "price_change_percentage_24h": 2.0,  # Below threshold
            },
        ],
    })
    await mock_redis.set("market:crypto_markets", crypto_data)

    create = await client.post(
        "/api/agents",
        json={
            "name": "Anomaly Detector",
            "agent_type": "anomaly_detector",
            "config_json": json.dumps({"std_threshold": 3.0}),
        },
    )
    agent_id = create.json()["id"]

    resp = await client.post(f"/api/agents/{agent_id}/run")
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "completed"
    # DOGE should trigger, ETH should not
    assert data["findingsCount"] >= 1


@pytest.mark.asyncio
async def test_findings_list_and_acknowledge(client, seed_user, mock_redis):
    """Test listing findings and acknowledging one."""
    crypto_data = json.dumps({
        "data": [
            {
                "symbol": "BTC",
                "current_price": 105000,
                "total_volume": 5000000000,
                "price_change_percentage_24h": 3.5,
            },
        ],
    })
    await mock_redis.set("market:crypto_markets", crypto_data)

    create = await client.post(
        "/api/agents",
        json={
            "name": "Monitor",
            "agent_type": "market_monitor",
            "config_json": json.dumps({
                "price_thresholds": {"BTC": {"above": 100000}},
            }),
        },
    )
    agent_id = create.json()["id"]
    await client.post(f"/api/agents/{agent_id}/run")

    # List findings
    resp = await client.get("/api/agents/findings")
    assert resp.status_code == 200
    findings = resp.json()["findings"]
    assert len(findings) >= 1

    # Acknowledge first finding
    finding_id = findings[0]["id"]
    resp = await client.post(f"/api/agents/findings/{finding_id}/acknowledge")
    assert resp.status_code == 200
    assert resp.json()["acknowledged"] is True


@pytest.mark.asyncio
async def test_escalation_rules_crud(client, seed_user):
    """Test CRUD for escalation rules."""
    # Create
    resp = await client.post(
        "/api/agents/escalation-rules",
        json={
            "findingType": "alert",
            "minSeverity": "high",
            "channel": "email",
            "channelConfigJson": json.dumps({"email": "test@example.com"}),
        },
    )
    assert resp.status_code == 201
    rule_id = resp.json()["id"]

    # List
    resp = await client.get("/api/agents/escalation-rules")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Update
    resp = await client.patch(
        f"/api/agents/escalation-rules/{rule_id}",
        json={"minSeverity": "critical"},
    )
    assert resp.status_code == 200
    assert resp.json()["minSeverity"] == "critical"

    # Delete
    resp = await client.delete(f"/api/agents/escalation-rules/{rule_id}")
    assert resp.status_code == 204
