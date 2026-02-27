"""Pydantic schemas for the NLP pipeline."""

from datetime import date, datetime

from pydantic import BaseModel, Field


# ── Sentiment ─────────────────────────────────────────────────────────────────

class SentimentResult(BaseModel):
    score: float = Field(ge=-1.0, le=1.0, description="Sentiment score from -1 (negative) to 1 (positive)")
    label: str = Field(description="Sentiment label: positive, negative, or neutral")


# ── Analysis request / response ───────────────────────────────────────────────

class NlpAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50000)
    operations: list[str] = Field(
        description="Operations to perform: sentiment, entities, summarize, topics"
    )


class EntityResult(BaseModel):
    text: str
    entity_type: str  # "ticker", "monetary", "percentage", "date", "organization"
    start: int | None = None
    end: int | None = None


class FakeNewsSignals(BaseModel):
    all_caps_ratio: float
    exclamation_density: float
    credibility_score: float
    flags: list[str]


class NlpAnalyzeResponse(BaseModel):
    sentiment: SentimentResult | None = None
    entities: list[EntityResult] | None = None
    summary: str | None = None
    topics: list[str] | None = None
    fake_news_signals: FakeNewsSignals | None = None


# ── Document CRUD ─────────────────────────────────────────────────────────────

class NlpDocumentCreate(BaseModel):
    source: str = Field(max_length=20)
    source_id: str = Field(max_length=255)
    title: str = Field(max_length=512)
    content: str


class NlpDocumentResponse(BaseModel):
    id: str
    source: str
    source_id: str
    title: str
    content: str
    summary: str | None = None
    sentiment_score: float | None = None
    sentiment_label: str | None = None
    entities_json: str | None = None
    topics_json: str | None = None
    processed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NlpDocumentListResponse(BaseModel):
    items: list[NlpDocumentResponse]
    total: int
    page: int
    page_size: int


# ── Market Briefing ───────────────────────────────────────────────────────────

class MarketBriefingResponse(BaseModel):
    id: str
    date: date
    summary: str
    market_mood: str
    key_events_json: str
    sector_highlights_json: str | None = None
    generated_at: datetime

    model_config = {"from_attributes": True}


class MarketBriefingListResponse(BaseModel):
    items: list[MarketBriefingResponse]
    total: int
