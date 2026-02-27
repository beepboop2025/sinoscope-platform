"""NLP pipeline models — documents, sentiment, and market briefings."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NlpDocument(Base):
    """Source document tracked through the NLP pipeline."""

    __tablename__ = "nlp_documents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    source: Mapped[str] = mapped_column(String(20))  # "sec", "news", "reddit", "arxiv"
    source_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(512))
    content: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )  # -1.0 to 1.0
    sentiment_label: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # "positive", "negative", "neutral"
    entities_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON array of extracted entities
    topics_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON array of extracted topics
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_nlp_documents_source", "source"),
        Index("ix_nlp_documents_processed", "processed"),
        Index("ix_nlp_documents_created_at", "created_at"),
    )


class MarketBriefing(Base):
    """Auto-generated daily market briefing from NLP analysis."""

    __tablename__ = "market_briefings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    summary: Mapped[str] = mapped_column(Text)
    market_mood: Mapped[str] = mapped_column(String(20))  # e.g. "bullish", "bearish", "neutral"
    key_events_json: Mapped[str] = mapped_column(Text)  # JSON array of key events
    sector_highlights_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON array of sector highlights
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
