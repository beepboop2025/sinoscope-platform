import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import HashChainMixin


class AuditLogEnhanced(Base, HashChainMixin):
    """Enhanced audit log with IP address tracking and tamper-evident hash chain.

    This table supersedes the original ``audit_logs`` table.  It carries all
    the same columns plus ``ip_address``, ``entry_hash``, and ``prev_hash``
    (the latter two provided by :class:`~app.models.mixins.HashChainMixin`).
    """

    __tablename__ = "audit_logs_enhanced"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    action: Mapped[str] = mapped_column(String(50))
    resource: Mapped[str] = mapped_column(String(50))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # prev_hash and entry_hash inherited from HashChainMixin

    __table_args__ = (
        Index("ix_audit_enh_user_created", "user_id", "created_at"),
        Index("ix_audit_enh_action", "action"),
    )
