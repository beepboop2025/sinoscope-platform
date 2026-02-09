import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def write_audit_log(
    session: AsyncSession,
    user_id: str,
    action: str,
    resource: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Write an audit log entry."""
    try:
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            details=json.dumps(details) if details else None,
        )
        session.add(log_entry)
        await session.flush()
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")
