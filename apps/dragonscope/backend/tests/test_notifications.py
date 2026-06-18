"""Tests for notifications — sending, template rendering, CRUD."""

import json

import pytest


@pytest.mark.asyncio
async def test_create_channel(client, seed_user):
    resp = await client.post(
        "/api/notifications/channels",
        json={
            "channelType": "email",
            "configJson": json.dumps({"to": "user@example.com"}),
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["channelType"] == "email"
    assert data["isActive"] is True


@pytest.mark.asyncio
async def test_list_channels(client, seed_user):
    await client.post(
        "/api/notifications/channels",
        json={
            "channelType": "email",
            "configJson": json.dumps({"to": "a@b.com"}),
        },
    )
    await client.post(
        "/api/notifications/channels",
        json={
            "channelType": "telegram",
            "configJson": json.dumps({"chat_id": "123"}),
        },
    )
    resp = await client.get("/api/notifications/channels")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_send_notification(client, seed_user):
    """Test sending a notification through a channel (mocked dispatch)."""
    # Create channel
    create = await client.post(
        "/api/notifications/channels",
        json={
            "channelType": "email",
            "configJson": json.dumps({"to": "test@example.com"}),
        },
    )
    channel_id = create.json()["id"]

    # Send notification
    resp = await client.post(
        "/api/notifications/send",
        json={
            "channelId": channel_id,
            "subject": "Test Alert",
            "body": "BTC just hit $100k!",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "sent"
    assert data["subject"] == "Test Alert"
    assert data["sentAt"] is not None


@pytest.mark.asyncio
async def test_send_notification_invalid_channel(client, seed_user):
    resp = await client.post(
        "/api/notifications/send",
        json={
            "channelId": "nonexistent-id",
            "subject": "Test",
            "body": "Test body",
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_deliveries(client, seed_user):
    """Test listing deliveries after sending notifications."""
    create = await client.post(
        "/api/notifications/channels",
        json={
            "channelType": "webhook",
            "configJson": json.dumps({"url": "https://hooks.example.com/abc"}),
        },
    )
    channel_id = create.json()["id"]

    await client.post(
        "/api/notifications/send",
        json={
            "channelId": channel_id,
            "subject": "Alert 1",
            "body": "Body 1",
        },
    )
    await client.post(
        "/api/notifications/send",
        json={
            "channelId": channel_id,
            "subject": "Alert 2",
            "body": "Body 2",
        },
    )

    resp = await client.get("/api/notifications/deliveries")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # Filter by status
    resp = await client.get("/api/notifications/deliveries?status=sent")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_template_crud_and_rendering(client, seed_user):
    """Test creating a template and using it to send a notification."""
    # Create template
    resp = await client.post(
        "/api/notifications/templates",
        json={
            "name": "price_alert",
            "subject": "Price Alert: {{symbol}}",
            "bodyTemplate": "{{symbol}} is now at ${{price}}. Threshold: ${{threshold}}.",
            "channelType": "email",
        },
    )
    assert resp.status_code == 201
    template_id = resp.json()["id"]
    assert resp.json()["name"] == "price_alert"

    # List templates
    resp = await client.get("/api/notifications/templates")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Create channel
    create = await client.post(
        "/api/notifications/channels",
        json={
            "channelType": "email",
            "configJson": json.dumps({"to": "user@example.com"}),
        },
    )
    channel_id = create.json()["id"]

    # Send with template
    resp = await client.post(
        "/api/notifications/send",
        json={
            "channelId": channel_id,
            "subject": "ignored when template used",
            "body": "ignored",
            "templateId": template_id,
            "templateVars": {
                "symbol": "BTC",
                "price": "100000",
                "threshold": "95000",
            },
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "sent"
    assert "BTC" in data["subject"]
    assert "100000" in data["body"]


@pytest.mark.asyncio
async def test_digest_crud(client, seed_user):
    """Test CRUD for digest configurations."""
    resp = await client.post(
        "/api/notifications/digests",
        json={
            "frequency": "daily",
            "includePortfolio": True,
            "includeAlerts": True,
            "includeMarketSummary": True,
        },
    )
    assert resp.status_code == 201
    digest_id = resp.json()["id"]

    resp = await client.get("/api/notifications/digests")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = await client.patch(
        f"/api/notifications/digests/{digest_id}",
        json={"frequency": "weekly"},
    )
    assert resp.status_code == 200
    assert resp.json()["frequency"] == "weekly"

    resp = await client.delete(f"/api/notifications/digests/{digest_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_scheduled_report_crud(client, seed_user):
    """Test CRUD for scheduled reports."""
    resp = await client.post(
        "/api/notifications/reports",
        json={
            "reportType": "portfolio",
            "scheduleCron": "0 9 * * *",
            "format": "json",
        },
    )
    assert resp.status_code == 201
    report_id = resp.json()["id"]

    resp = await client.get("/api/notifications/reports")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = await client.patch(
        f"/api/notifications/reports/{report_id}",
        json={"format": "csv"},
    )
    assert resp.status_code == 200
    assert resp.json()["format"] == "csv"

    resp = await client.delete(f"/api/notifications/reports/{report_id}")
    assert resp.status_code == 204
