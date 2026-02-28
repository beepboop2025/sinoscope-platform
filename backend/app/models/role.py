import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    permissions: Mapped[str] = mapped_column(
        Text,
        comment="Comma-separated permission strings",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Permission constants
# ---------------------------------------------------------------------------

PERMISSIONS = [
    "read:data",
    "read:portfolios",
    "write:portfolios",
    "read:watchlists",
    "write:watchlists",
    "read:alerts",
    "write:alerts",
    "read:quant",
    "write:quant",
    "read:backtest",
    "write:backtest",
    "read:nlp",
    "write:nlp",
    "read:kg",
    "write:kg",
    "read:agents",
    "write:agents",
    "read:warehouse",
    "read:compliance",
    "write:compliance",
    "admin:users",
    "admin:system",
]

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "viewer": [
        "read:data",
    ],
    "user": [
        "read:data",
        "read:portfolios",
        "write:portfolios",
        "read:watchlists",
        "write:watchlists",
        "read:alerts",
        "write:alerts",
    ],
    "analyst": [
        "read:data",
        "read:portfolios",
        "write:portfolios",
        "read:watchlists",
        "write:watchlists",
        "read:alerts",
        "write:alerts",
        "read:quant",
        "write:quant",
        "read:backtest",
        "write:backtest",
        "read:nlp",
        "write:nlp",
        "read:kg",
        "write:kg",
        "read:agents",
        "write:agents",
        "read:warehouse",
        "read:compliance",
    ],
    "admin": list(PERMISSIONS),  # all permissions
}

# ---------------------------------------------------------------------------
# Seed data — use in migrations or startup to ensure default roles exist
# ---------------------------------------------------------------------------

DEFAULT_ROLES: list[dict[str, str]] = [
    {
        "name": "viewer",
        "description": "Read-only access to market data.",
        "permissions": ",".join(ROLE_PERMISSIONS["viewer"]),
    },
    {
        "name": "user",
        "description": "Standard user. Can manage own portfolios, watchlists, and alerts.",
        "permissions": ",".join(ROLE_PERMISSIONS["user"]),
    },
    {
        "name": "analyst",
        "description": "Power user with access to quant, backtest, NLP, and knowledge-graph endpoints.",
        "permissions": ",".join(ROLE_PERMISSIONS["analyst"]),
    },
    {
        "name": "admin",
        "description": "Full administrative access to all system features.",
        "permissions": ",".join(ROLE_PERMISSIONS["admin"]),
    },
]
