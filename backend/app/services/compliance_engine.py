"""Compliance engine — audit hash chain, retention, access, export limits, API metering."""

import hashlib
import json
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance import (
    AccessPolicy,
    ApiUsageMeter,
    ComplianceAuditLog,
    DataRetentionPolicy,
    ExportRateLimit,
)

logger = logging.getLogger(__name__)


class ComplianceEngine:
    """Compliance engine with tamper-evident audit chain and policy enforcement."""

    # ------------------------------------------------------------------
    # Audit hash chain
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_hash(prev_hash: str | None, action: str, resource_type: str, details: str | None, timestamp: str) -> str:
        """Compute SHA-256 hash for an audit chain entry.

        Format: SHA256(prev_hash:action:resource_type:details:timestamp)
        """
        parts = [
            prev_hash or "",
            action,
            resource_type,
            details or "",
            timestamp,
        ]
        payload = ":".join(parts)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    async def log_audit(
        session: AsyncSession,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        user_id: str | None = None,
        details: str | None = None,
        ip_address: str | None = None,
    ) -> ComplianceAuditLog:
        """Write a tamper-evident audit log entry.

        Each entry's hash chains to the previous entry's hash, forming a
        blockchain-like tamper-evident log.
        """
        # Get the most recent entry's hash
        result = await session.execute(
            select(ComplianceAuditLog.entry_hash)
            .order_by(ComplianceAuditLog.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        prev_hash = row if row else None

        now = datetime.now(timezone.utc)
        timestamp_str = now.isoformat()

        entry_hash = ComplianceEngine._compute_hash(
            prev_hash, action, resource_type, details, timestamp_str,
        )

        entry = ComplianceAuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            entry_hash=entry_hash,
            prev_hash=prev_hash,
        )
        session.add(entry)
        await session.flush()

        logger.info(f"Audit log: action={action} resource={resource_type} hash={entry_hash[:12]}...")
        return entry

    @staticmethod
    async def verify_audit_chain(
        session: AsyncSession,
        limit: int = 1000,
    ) -> dict:
        """Verify the integrity of the audit hash chain.

        Returns:
            Dict with is_valid, entries_checked, first_broken_at (ISO timestamp or None).
        """
        result = await session.execute(
            select(ComplianceAuditLog)
            .order_by(ComplianceAuditLog.created_at.asc())
            .limit(limit)
        )
        entries = list(result.scalars().all())

        if not entries:
            return {"is_valid": True, "entries_checked": 0, "first_broken_at": None}

        entries_checked = 0
        prev_hash: str | None = None

        for entry in entries:
            entries_checked += 1

            # Verify that prev_hash matches
            if entry.prev_hash != prev_hash:
                return {
                    "is_valid": False,
                    "entries_checked": entries_checked,
                    "first_broken_at": entry.created_at.isoformat() if entry.created_at else None,
                }

            # Recompute hash and compare
            timestamp_str = entry.created_at.isoformat() if entry.created_at else ""
            expected_hash = ComplianceEngine._compute_hash(
                entry.prev_hash, entry.action, entry.resource_type,
                entry.details, timestamp_str,
            )

            if entry.entry_hash != expected_hash:
                return {
                    "is_valid": False,
                    "entries_checked": entries_checked,
                    "first_broken_at": entry.created_at.isoformat() if entry.created_at else None,
                }

            prev_hash = entry.entry_hash

        return {"is_valid": True, "entries_checked": entries_checked, "first_broken_at": None}

    # ------------------------------------------------------------------
    # Data retention
    # ------------------------------------------------------------------
    @staticmethod
    async def check_retention(session: AsyncSession) -> list[dict]:
        """Find records that are past their retention period.

        Returns a list of dicts with resource_type and count of expired records.
        """
        result = await session.execute(
            select(DataRetentionPolicy).where(DataRetentionPolicy.auto_delete.is_(True))
        )
        policies = list(result.scalars().all())

        expired: list[dict] = []
        now = datetime.now(timezone.utc)

        for policy in policies:
            cutoff = now - timedelta(days=policy.retention_days)

            # Check compliance audit logs for this resource type
            count_result = await session.execute(
                select(func.count(ComplianceAuditLog.id)).where(
                    ComplianceAuditLog.resource_type == policy.resource_type,
                    ComplianceAuditLog.created_at < cutoff,
                )
            )
            count = count_result.scalar() or 0

            if count > 0:
                expired.append({
                    "resource_type": policy.resource_type,
                    "count": count,
                    "retention_days": policy.retention_days,
                    "cutoff_date": cutoff.isoformat(),
                })

        return expired

    @staticmethod
    async def enforce_retention(session: AsyncSession) -> dict:
        """Delete records that have exceeded their retention period.

        Returns summary of deleted records by resource type.
        """
        result = await session.execute(
            select(DataRetentionPolicy).where(DataRetentionPolicy.auto_delete.is_(True))
        )
        policies = list(result.scalars().all())

        deleted_summary: dict[str, int] = {}
        now = datetime.now(timezone.utc)

        for policy in policies:
            cutoff = now - timedelta(days=policy.retention_days)

            del_result = await session.execute(
                delete(ComplianceAuditLog).where(
                    ComplianceAuditLog.resource_type == policy.resource_type,
                    ComplianceAuditLog.created_at < cutoff,
                )
            )
            deleted_count = del_result.rowcount or 0

            if deleted_count > 0:
                deleted_summary[policy.resource_type] = deleted_count
                logger.info(
                    f"Retention: deleted {deleted_count} records for "
                    f"resource_type={policy.resource_type} (>{policy.retention_days}d)"
                )

        return deleted_summary

    # ------------------------------------------------------------------
    # Access policies
    # ------------------------------------------------------------------
    @staticmethod
    async def check_access(
        session: AsyncSession,
        user_role: str,
        resource_type: str,
    ) -> dict:
        """Check if a user role is allowed to access a resource type.

        Returns:
            Dict with allowed (bool) and matching_policy (name or None).
        """
        result = await session.execute(
            select(AccessPolicy).where(
                AccessPolicy.resource_type == resource_type,
                AccessPolicy.is_active.is_(True),
            )
        )
        policies = list(result.scalars().all())

        for policy in policies:
            allowed_roles = [r.strip() for r in policy.allowed_roles.split(",")]
            if user_role in allowed_roles:
                # Check conditions (if any)
                try:
                    conditions = json.loads(policy.conditions) if policy.conditions else {}
                except (json.JSONDecodeError, TypeError):
                    conditions = {}

                # For now, if conditions are empty or not parseable, allow
                # Future: implement condition evaluation
                return {"allowed": True, "matching_policy": policy.name}

        # No matching policy found — deny by default
        if policies:
            return {"allowed": False, "matching_policy": None}

        # No policies defined for this resource — allow (permissive default)
        return {"allowed": True, "matching_policy": None}

    # ------------------------------------------------------------------
    # Export rate limiting
    # ------------------------------------------------------------------
    @staticmethod
    async def check_export_limit(
        session: AsyncSession,
        user_id: str,
        export_type: str,
    ) -> dict:
        """Check how many exports a user has remaining today.

        Returns:
            Dict with remaining, max_per_day, current_count.
        """
        today = date.today()

        result = await session.execute(
            select(ExportRateLimit).where(
                ExportRateLimit.user_id == user_id,
                ExportRateLimit.export_type == export_type,
            )
        )
        limit_row = result.scalar_one_or_none()

        if limit_row is None:
            # No limit configured — create one with defaults
            limit_row = ExportRateLimit(
                user_id=user_id,
                export_type=export_type,
                max_per_day=100,
                current_count=0,
                last_reset=today,
            )
            session.add(limit_row)
            await session.flush()

        # Reset counter if it is a new day
        if limit_row.last_reset < today:
            limit_row.current_count = 0
            limit_row.last_reset = today
            await session.flush()

        remaining = max(limit_row.max_per_day - limit_row.current_count, 0)

        return {
            "remaining": remaining,
            "max_per_day": limit_row.max_per_day,
            "current_count": limit_row.current_count,
        }

    # ------------------------------------------------------------------
    # API usage metering
    # ------------------------------------------------------------------
    @staticmethod
    async def meter_api_usage(
        session: AsyncSession,
        user_id: str,
        endpoint: str,
        method: str,
    ) -> int:
        """Increment the API usage counter for a user/endpoint/method.

        Meters are tracked in hourly periods.

        Returns:
            Updated count for the current period.
        """
        now = datetime.now(timezone.utc)
        period_start = now.replace(minute=0, second=0, microsecond=0)
        period_end = period_start + timedelta(hours=1)

        result = await session.execute(
            select(ApiUsageMeter).where(
                ApiUsageMeter.user_id == user_id,
                ApiUsageMeter.endpoint == endpoint,
                ApiUsageMeter.method == method,
                ApiUsageMeter.period_start == period_start,
            )
        )
        meter = result.scalar_one_or_none()

        if meter is None:
            meter = ApiUsageMeter(
                user_id=user_id,
                endpoint=endpoint,
                method=method,
                count=1,
                period_start=period_start,
                period_end=period_end,
            )
            session.add(meter)
            await session.flush()
            return 1

        meter.count += 1
        await session.flush()
        return meter.count
