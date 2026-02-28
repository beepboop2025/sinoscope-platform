import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_enhanced import AuditLogEnhanced
from app.models.mixins import HashChainMixin

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ChainVerificationResult:
    """Outcome of :meth:`AuditService.verify_chain`."""

    is_valid: bool
    entries_checked: int
    first_broken_at: int | None = None  # id index (0-based) where the chain breaks


# ---------------------------------------------------------------------------
# Audit service
# ---------------------------------------------------------------------------


class AuditService:
    """Enhanced audit logging with SHA-256 hash chaining.

    Every new entry's hash is derived from the previous entry's hash,
    producing a tamper-evident chain similar to a blockchain.

    Hash payload::

        SHA-256("{prev_hash or 'GENESIS'}:{action}:{resource}:{details}:{timestamp_iso}")
    """

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    @staticmethod
    async def log(
        session: AsyncSession,
        user_id: str,
        action: str,
        resource: str,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> AuditLogEnhanced:
        """Create a new audit log entry chained to the most recent one.

        Parameters
        ----------
        session:
            An active async SQLAlchemy session.
        user_id:
            The UUID of the acting user.
        action:
            Short verb describing the action (e.g. ``"create"``, ``"delete"``).
        resource:
            The resource type affected (e.g. ``"portfolio"``, ``"alert"``).
        details:
            Optional dict with additional context (serialised to JSON).
        ip_address:
            Optional client IP.

        Returns
        -------
        AuditLogEnhanced
            The persisted audit entry (already flushed).
        """
        try:
            # Fetch the most recent entry to obtain its hash.
            prev_entry = (
                await session.execute(
                    select(AuditLogEnhanced)
                    .order_by(AuditLogEnhanced.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

            prev_hash: str | None = prev_entry.entry_hash if prev_entry else None

            details_str = json.dumps(details, sort_keys=True) if details else ""
            now = datetime.utcnow()
            timestamp_iso = now.isoformat()

            content = f"{action}:{resource}:{details_str}:{timestamp_iso}"
            entry_hash = HashChainMixin.compute_hash(content, prev_hash)

            entry = AuditLogEnhanced(
                user_id=user_id,
                action=action,
                resource=resource,
                details=json.dumps(details) if details else None,
                ip_address=ip_address,
                prev_hash=prev_hash,
                entry_hash=entry_hash,
                created_at=now,
            )
            session.add(entry)
            await session.flush()
            logger.debug(
                "Audit log: user=%s action=%s resource=%s hash=%s",
                user_id,
                action,
                resource,
                entry_hash[:12],
            )
            return entry

        except Exception as e:
            logger.error("Failed to write audit log: %s", e, exc_info=True)
            raise

    # ------------------------------------------------------------------
    # Verify
    # ------------------------------------------------------------------

    @staticmethod
    async def verify_chain(
        session: AsyncSession,
        limit: int = 1000,
    ) -> ChainVerificationResult:
        """Walk the audit log chain and verify every entry's hash.

        Parameters
        ----------
        session:
            An active async SQLAlchemy session.
        limit:
            Maximum number of entries to check (oldest first).

        Returns
        -------
        ChainVerificationResult
        """
        result = await session.execute(
            select(AuditLogEnhanced)
            .order_by(AuditLogEnhanced.created_at.asc())
            .limit(limit)
        )
        entries: list[AuditLogEnhanced] = list(result.scalars().all())

        if not entries:
            return ChainVerificationResult(is_valid=True, entries_checked=0)

        prev_hash: str | None = None

        for idx, entry in enumerate(entries):
            # Reconstruct the content that was hashed at creation time.
            details_str = ""
            if entry.details:
                try:
                    details_str = json.dumps(
                        json.loads(entry.details), sort_keys=True
                    )
                except (json.JSONDecodeError, TypeError):
                    details_str = entry.details

            timestamp_iso = entry.created_at.isoformat() if entry.created_at else ""
            content = f"{entry.action}:{entry.resource}:{details_str}:{timestamp_iso}"
            expected_hash = HashChainMixin.compute_hash(content, prev_hash)

            if entry.entry_hash != expected_hash:
                logger.warning(
                    "Audit chain broken at index %d (id=%s): expected=%s got=%s",
                    idx,
                    entry.id,
                    expected_hash[:12],
                    entry.entry_hash[:12],
                )
                return ChainVerificationResult(
                    is_valid=False,
                    entries_checked=idx + 1,
                    first_broken_at=idx,
                )

            # Verify prev_hash linkage.
            if entry.prev_hash != prev_hash:
                logger.warning(
                    "Audit chain prev_hash mismatch at index %d (id=%s)",
                    idx,
                    entry.id,
                )
                return ChainVerificationResult(
                    is_valid=False,
                    entries_checked=idx + 1,
                    first_broken_at=idx,
                )

            prev_hash = entry.entry_hash

        logger.info("Audit chain verified OK: %d entries", len(entries))
        return ChainVerificationResult(
            is_valid=True,
            entries_checked=len(entries),
        )


# ---------------------------------------------------------------------------
# Convenience function (backwards-compatible with the old write_audit_log)
# ---------------------------------------------------------------------------


async def write_audit_log(
    session: AsyncSession,
    user_id: str,
    action: str,
    resource: str,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Thin wrapper kept for backwards compatibility with existing callers."""
    await AuditService.log(
        session=session,
        user_id=user_id,
        action=action,
        resource=resource,
        details=details,
        ip_address=ip_address,
    )
