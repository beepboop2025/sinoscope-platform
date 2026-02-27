"""Tests for Compliance System."""

import hashlib
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance import (
    AccessPolicy,
    ComplianceAuditLog,
    DataRetentionPolicy,
    ExportRateLimit,
)
from app.services.compliance_engine import ComplianceEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def compliance_session(db_session: AsyncSession):
    """Alias for db_session for clarity."""
    return db_session


# ---------------------------------------------------------------------------
# Audit Hash Chain
# ---------------------------------------------------------------------------
class TestAuditHashChain:
    """Test the tamper-evident audit hash chain."""

    @pytest.mark.asyncio
    async def test_create_first_entry(self, compliance_session):
        """First entry should have prev_hash=None."""
        entry = await ComplianceEngine.log_audit(
            session=compliance_session,
            action="create",
            resource_type="portfolio",
            resource_id="p-001",
            user_id="user-001",
            details="Created portfolio",
        )
        assert entry.entry_hash is not None
        assert len(entry.entry_hash) == 64  # SHA-256 hex length
        assert entry.prev_hash is None

    @pytest.mark.asyncio
    async def test_chain_links(self, compliance_session):
        """Second entry should chain to first entry's hash."""
        entry1 = await ComplianceEngine.log_audit(
            session=compliance_session,
            action="create",
            resource_type="portfolio",
            resource_id="p-001",
        )

        entry2 = await ComplianceEngine.log_audit(
            session=compliance_session,
            action="update",
            resource_type="portfolio",
            resource_id="p-001",
        )

        assert entry2.prev_hash == entry1.entry_hash
        assert entry2.entry_hash != entry1.entry_hash

    @pytest.mark.asyncio
    async def test_verify_valid_chain(self, compliance_session):
        """Valid chain should pass verification."""
        for i in range(5):
            await ComplianceEngine.log_audit(
                session=compliance_session,
                action=f"action_{i}",
                resource_type="test",
                resource_id=f"r-{i}",
                details=f"Detail {i}",
            )

        result = await ComplianceEngine.verify_audit_chain(compliance_session)
        assert result["is_valid"] is True
        assert result["entries_checked"] == 5
        assert result["first_broken_at"] is None

    @pytest.mark.asyncio
    async def test_verify_empty_chain(self, compliance_session):
        """Empty chain should be considered valid."""
        result = await ComplianceEngine.verify_audit_chain(compliance_session)
        assert result["is_valid"] is True
        assert result["entries_checked"] == 0

    @pytest.mark.asyncio
    async def test_detect_tampering(self, compliance_session):
        """Tampering with an entry should be detected."""
        for i in range(3):
            await ComplianceEngine.log_audit(
                session=compliance_session,
                action=f"action_{i}",
                resource_type="test",
                details=f"Original detail {i}",
            )

        # Tamper with the second entry
        result = await compliance_session.execute(
            select(ComplianceAuditLog).order_by(ComplianceAuditLog.created_at.asc())
        )
        entries = list(result.scalars().all())
        entries[1].details = "TAMPERED"
        await compliance_session.flush()

        verification = await ComplianceEngine.verify_audit_chain(compliance_session)
        assert verification["is_valid"] is False
        assert verification["entries_checked"] <= 3

    @pytest.mark.asyncio
    async def test_hash_deterministic(self, compliance_session):
        """Same inputs should produce the same hash."""
        hash1 = ComplianceEngine._compute_hash(
            "prev", "create", "portfolio", "details", "2024-01-01T00:00:00"
        )
        hash2 = ComplianceEngine._compute_hash(
            "prev", "create", "portfolio", "details", "2024-01-01T00:00:00"
        )
        assert hash1 == hash2

    @pytest.mark.asyncio
    async def test_hash_changes_with_input(self, compliance_session):
        """Different inputs should produce different hashes."""
        hash1 = ComplianceEngine._compute_hash(
            "prev", "create", "portfolio", "details", "2024-01-01T00:00:00"
        )
        hash2 = ComplianceEngine._compute_hash(
            "prev", "update", "portfolio", "details", "2024-01-01T00:00:00"
        )
        assert hash1 != hash2

    @pytest.mark.asyncio
    async def test_audit_log_with_ip(self, compliance_session):
        """Audit log should store IP address."""
        entry = await ComplianceEngine.log_audit(
            session=compliance_session,
            action="login",
            resource_type="session",
            ip_address="192.168.1.1",
        )
        assert entry.ip_address == "192.168.1.1"


# ---------------------------------------------------------------------------
# Data Retention
# ---------------------------------------------------------------------------
class TestRetentionPolicy:
    """Test data retention policy enforcement."""

    @pytest.mark.asyncio
    async def test_check_retention_no_expired(self, compliance_session):
        """When no records are expired, check should return empty."""
        policy = DataRetentionPolicy(
            resource_type="test_resource",
            retention_days=365,
            auto_delete=True,
        )
        compliance_session.add(policy)
        await compliance_session.flush()

        # Add a recent audit entry
        await ComplianceEngine.log_audit(
            session=compliance_session,
            action="test",
            resource_type="test_resource",
        )

        expired = await ComplianceEngine.check_retention(compliance_session)
        # The recently created entry should not be expired
        test_expired = [e for e in expired if e["resource_type"] == "test_resource"]
        assert len(test_expired) == 0

    @pytest.mark.asyncio
    async def test_enforce_retention_deletes_old(self, compliance_session):
        """Enforce retention should delete old records."""
        policy = DataRetentionPolicy(
            resource_type="ephemeral",
            retention_days=0,  # 0 days = delete immediately
            auto_delete=True,
        )
        compliance_session.add(policy)
        await compliance_session.flush()

        # Create an audit entry
        await ComplianceEngine.log_audit(
            session=compliance_session,
            action="old_action",
            resource_type="ephemeral",
        )

        # Manually backdate the created_at to force expiry
        result = await compliance_session.execute(
            select(ComplianceAuditLog).where(
                ComplianceAuditLog.resource_type == "ephemeral"
            )
        )
        entry = result.scalar_one()
        entry.created_at = datetime.now(timezone.utc) - timedelta(days=1)
        await compliance_session.flush()

        # Enforce retention
        deleted = await ComplianceEngine.enforce_retention(compliance_session)
        assert "ephemeral" in deleted
        assert deleted["ephemeral"] >= 1

    @pytest.mark.asyncio
    async def test_retention_does_not_delete_without_auto_delete(self, compliance_session):
        """Retention should NOT delete if auto_delete is False."""
        policy = DataRetentionPolicy(
            resource_type="permanent",
            retention_days=0,
            auto_delete=False,
        )
        compliance_session.add(policy)
        await compliance_session.flush()

        await ComplianceEngine.log_audit(
            session=compliance_session,
            action="keep",
            resource_type="permanent",
        )

        deleted = await ComplianceEngine.enforce_retention(compliance_session)
        assert "permanent" not in deleted


# ---------------------------------------------------------------------------
# Access Policy
# ---------------------------------------------------------------------------
class TestAccessPolicy:
    """Test access policy checks."""

    @pytest.mark.asyncio
    async def test_access_allowed(self, compliance_session):
        """User with matching role should be allowed."""
        policy = AccessPolicy(
            name="admin-portfolio-access",
            resource_type="portfolio",
            conditions="{}",
            allowed_roles="admin,manager",
            is_active=True,
        )
        compliance_session.add(policy)
        await compliance_session.flush()

        result = await ComplianceEngine.check_access(
            session=compliance_session,
            user_role="admin",
            resource_type="portfolio",
        )
        assert result["allowed"] is True
        assert result["matching_policy"] == "admin-portfolio-access"

    @pytest.mark.asyncio
    async def test_access_denied(self, compliance_session):
        """User without matching role should be denied."""
        policy = AccessPolicy(
            name="admin-only",
            resource_type="secret_resource",
            conditions="{}",
            allowed_roles="admin",
            is_active=True,
        )
        compliance_session.add(policy)
        await compliance_session.flush()

        result = await ComplianceEngine.check_access(
            session=compliance_session,
            user_role="viewer",
            resource_type="secret_resource",
        )
        assert result["allowed"] is False

    @pytest.mark.asyncio
    async def test_inactive_policy_ignored(self, compliance_session):
        """Inactive policy should not be considered."""
        policy = AccessPolicy(
            name="inactive-policy",
            resource_type="resource_x",
            conditions="{}",
            allowed_roles="admin",
            is_active=False,
        )
        compliance_session.add(policy)
        await compliance_session.flush()

        result = await ComplianceEngine.check_access(
            session=compliance_session,
            user_role="admin",
            resource_type="resource_x",
        )
        # No active policy found — permissive default
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_no_policy_allows_access(self, compliance_session):
        """No policy for resource type should allow access (permissive default)."""
        result = await ComplianceEngine.check_access(
            session=compliance_session,
            user_role="anyone",
            resource_type="unconfigured_resource",
        )
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_multiple_roles_comma_separated(self, compliance_session):
        """Policy with multiple roles should allow any matching role."""
        policy = AccessPolicy(
            name="multi-role",
            resource_type="dashboard",
            conditions="{}",
            allowed_roles="admin, analyst, viewer",
            is_active=True,
        )
        compliance_session.add(policy)
        await compliance_session.flush()

        for role in ["admin", "analyst", "viewer"]:
            result = await ComplianceEngine.check_access(
                session=compliance_session,
                user_role=role,
                resource_type="dashboard",
            )
            assert result["allowed"] is True, f"Role '{role}' should be allowed"


# ---------------------------------------------------------------------------
# Export Rate Limit
# ---------------------------------------------------------------------------
class TestExportRateLimit:
    """Test export rate limiting."""

    @pytest.mark.asyncio
    async def test_initial_limit(self, compliance_session):
        """New user should have full remaining exports."""
        result = await ComplianceEngine.check_export_limit(
            session=compliance_session,
            user_id="user-001",
            export_type="csv",
        )
        assert result["remaining"] == 100
        assert result["current_count"] == 0

    @pytest.mark.asyncio
    async def test_check_creates_record(self, compliance_session):
        """check_export_limit should create a record if none exists."""
        await ComplianceEngine.check_export_limit(
            session=compliance_session,
            user_id="user-002",
            export_type="pdf",
        )

        qr = await compliance_session.execute(
            select(ExportRateLimit).where(
                ExportRateLimit.user_id == "user-002",
                ExportRateLimit.export_type == "pdf",
            )
        )
        record = qr.scalar_one_or_none()
        assert record is not None
