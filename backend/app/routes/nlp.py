"""NLP pipeline routes — text analysis, document management, market briefings."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.nlp import MarketBriefing, NlpDocument
from app.schemas.nlp import (
    MarketBriefingListResponse,
    MarketBriefingResponse,
    NlpAnalyzeRequest,
    NlpAnalyzeResponse,
    NlpDocumentListResponse,
    NlpDocumentResponse,
)
from app.services.nlp_engine import NlpEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/nlp", tags=["nlp"])

# Singleton engine
_engine = NlpEngine()


@router.post("/analyze", response_model=NlpAnalyzeResponse)
async def analyze_text(body: NlpAnalyzeRequest):
    """Run NLP operations on arbitrary text.

    Supported operations: sentiment, entities, summarize, topics, fake_news.
    """
    operations = set(body.operations)
    result: dict = {}

    try:
        if "sentiment" in operations:
            s = _engine.analyze_sentiment(body.text)
            result["sentiment"] = s.to_dict()

        if "entities" in operations:
            ents = _engine.extract_entities(body.text)
            result["entities"] = [e.to_dict() for e in ents]

        if "summarize" in operations:
            result["summary"] = _engine.summarize(body.text)

        if "topics" in operations:
            result["topics"] = _engine.extract_topics(body.text)

        if "fake_news" in operations:
            result["fake_news_signals"] = _engine.detect_fake_news_signals(body.text)

    except Exception as exc:
        logger.error("NLP analysis failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="NLP analysis failed")

    return NlpAnalyzeResponse(**result)


@router.get("/documents", response_model=NlpDocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source: str | None = Query(None),
    processed: bool | None = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """List NLP-processed documents with optional filtering and pagination."""
    stmt = select(NlpDocument)
    count_stmt = select(func.count(NlpDocument.id))

    if source:
        stmt = stmt.where(NlpDocument.source == source)
        count_stmt = count_stmt.where(NlpDocument.source == source)

    if processed is not None:
        stmt = stmt.where(NlpDocument.processed == processed)
        count_stmt = count_stmt.where(NlpDocument.processed == processed)

    total = (await session.execute(count_stmt)).scalar_one()

    stmt = (
        stmt.order_by(NlpDocument.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(stmt)).scalars().all()

    return NlpDocumentListResponse(
        items=[NlpDocumentResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/documents/{doc_id}", response_model=NlpDocumentResponse)
async def get_document(doc_id: str, session: AsyncSession = Depends(get_db)):
    """Get a single NLP document by ID."""
    result = await session.execute(
        select(NlpDocument).where(NlpDocument.id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/briefings", response_model=MarketBriefingListResponse)
async def list_briefings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """List market briefings with pagination."""
    count_stmt = select(func.count(MarketBriefing.id))
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = (
        select(MarketBriefing)
        .order_by(MarketBriefing.date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(stmt)).scalars().all()

    return MarketBriefingListResponse(
        items=[MarketBriefingResponse.model_validate(r) for r in rows],
        total=total,
    )


@router.get("/briefings/latest", response_model=MarketBriefingResponse)
async def get_latest_briefing(session: AsyncSession = Depends(get_db)):
    """Get the most recent market briefing."""
    result = await session.execute(
        select(MarketBriefing).order_by(MarketBriefing.date.desc()).limit(1)
    )
    briefing = result.scalar_one_or_none()
    if not briefing:
        raise HTTPException(status_code=404, detail="No briefings available")
    return briefing
