import hashlib
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` columns with server defaults."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class SoftDeleteMixin:
    """Adds ``is_deleted`` and ``deleted_at`` columns for soft-delete support."""

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )


class HashChainMixin:
    """Adds ``prev_hash`` and ``entry_hash`` columns for tamper-evident hash chaining.

    The chain uses SHA-256:  ``hash = SHA-256("{prev_hash or 'GENESIS'}:{content}")``

    Consumers should call :meth:`compute_hash` to generate ``entry_hash`` before
    persisting a new row.
    """

    prev_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="SHA-256 hash of the preceding entry (None for the first entry).",
    )
    entry_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash of this entry's content chained to the previous hash.",
    )

    @staticmethod
    def compute_hash(content: str, prev_hash: str | None = None) -> str:
        """Compute a SHA-256 hash chaining *content* to *prev_hash*.

        Parameters
        ----------
        content:
            The string payload to hash (typically a canonical representation of
            the entry's significant fields).
        prev_hash:
            The ``entry_hash`` of the immediately preceding entry, or ``None``
            if this is the first entry in the chain.

        Returns
        -------
        str
            64-character lower-case hex digest.
        """
        prefix = prev_hash if prev_hash else "GENESIS"
        raw = f"{prefix}:{content}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
