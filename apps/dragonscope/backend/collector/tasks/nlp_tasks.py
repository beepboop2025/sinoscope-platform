"""Celery tasks for the NLP pipeline — document processing, briefing generation,
sentiment aggregation."""

import json
import logging
import uuid
from datetime import date, datetime

from collector.celery_app import celery_app
from collector.tasks.base import get_sync_redis, save_data

logger = logging.getLogger(__name__)


def _get_nlp_engine():
    """Lazy import to avoid circular dependency at module load."""
    from app.services.nlp_engine import NlpEngine
    return NlpEngine()


def _get_sync_session():
    """Create a synchronous DB session for Celery tasks.

    Falls back to a no-op if sync engine is not configured.
    """
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from app.config import get_settings

        settings = get_settings()
        # Convert async URL to sync
        db_url = settings.DATABASE_URL
        if db_url.startswith("postgresql+asyncpg"):
            db_url = db_url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1)
        elif db_url.startswith("sqlite+aiosqlite"):
            db_url = db_url.replace("sqlite+aiosqlite", "sqlite", 1)

        engine = create_engine(db_url)
        return Session(engine)
    except Exception as e:
        logger.error("Failed to create sync session: %s", e)
        return None


@celery_app.task(name="collector.tasks.nlp_tasks.process_document")
def process_document(document_id: str | None = None) -> dict:
    """Run NLP pipeline on unprocessed documents.

    If *document_id* is provided, process that specific document.
    Otherwise, process all unprocessed documents (up to 50).
    """
    engine = _get_nlp_engine()
    session = _get_sync_session()

    if session is None:
        logger.warning("[NLP] No DB session — skipping document processing")
        return {"processed": 0}

    try:
        from app.models.nlp import NlpDocument

        if document_id:
            docs = session.query(NlpDocument).filter(NlpDocument.id == document_id).all()
        else:
            docs = (
                session.query(NlpDocument)
                .filter(NlpDocument.processed == False)  # noqa: E712
                .limit(50)
                .all()
            )

        processed_count = 0
        for doc in docs:
            try:
                # Sentiment
                sentiment = engine.analyze_sentiment(doc.content)
                doc.sentiment_score = sentiment.score
                doc.sentiment_label = sentiment.label

                # Entities
                entities = engine.extract_entities(doc.content)
                doc.entities_json = json.dumps([e.to_dict() for e in entities])

                # Summary
                doc.summary = engine.summarize(doc.content)

                # Topics
                topics = engine.extract_topics(doc.content)
                doc.topics_json = json.dumps(topics)

                doc.processed = True
                processed_count += 1

            except Exception as e:
                logger.error("[NLP] Error processing doc %s: %s", doc.id, e)

        session.commit()
        logger.info("[NLP] Processed %d documents", processed_count)
        return {"processed": processed_count}

    except Exception as e:
        session.rollback()
        logger.error("[NLP] process_document failed: %s", e)
        return {"processed": 0, "error": str(e)}
    finally:
        session.close()


@celery_app.task(name="collector.tasks.nlp_tasks.generate_briefing")
def generate_briefing() -> dict:
    """Generate daily market briefing from recent documents."""
    engine = _get_nlp_engine()
    session = _get_sync_session()

    if session is None:
        logger.warning("[NLP] No DB session — skipping briefing generation")
        return {"generated": False}

    try:
        from app.models.nlp import MarketBriefing, NlpDocument

        # Get recent processed documents (last 24 hours worth)
        from sqlalchemy import func
        docs = (
            session.query(NlpDocument)
            .filter(NlpDocument.processed == True)  # noqa: E712
            .order_by(NlpDocument.created_at.desc())
            .limit(100)
            .all()
        )

        doc_dicts = [
            {
                "title": d.title,
                "content": d.content,
                "source": d.source,
                "sentiment_score": float(d.sentiment_score) if d.sentiment_score else None,
                "entities_json": d.entities_json,
            }
            for d in docs
        ]

        briefing_data = engine.generate_briefing(doc_dicts)

        # Check if briefing for today already exists
        today = date.today()
        existing = (
            session.query(MarketBriefing)
            .filter(MarketBriefing.date == today)
            .first()
        )

        if existing:
            existing.summary = briefing_data["summary"]
            existing.market_mood = briefing_data["market_mood"]
            existing.key_events_json = briefing_data["key_events_json"]
            existing.sector_highlights_json = briefing_data.get("sector_highlights_json")
            existing.generated_at = datetime.utcnow()
        else:
            briefing = MarketBriefing(
                date=today,
                summary=briefing_data["summary"],
                market_mood=briefing_data["market_mood"],
                key_events_json=briefing_data["key_events_json"],
                sector_highlights_json=briefing_data.get("sector_highlights_json"),
            )
            session.add(briefing)

        session.commit()

        # Cache briefing in Redis
        save_data("market_briefing", briefing_data, ttl=3600)

        logger.info("[NLP] Generated market briefing for %s", today.isoformat())
        return {"generated": True, "mood": briefing_data["market_mood"]}

    except Exception as e:
        session.rollback()
        logger.error("[NLP] generate_briefing failed: %s", e)
        return {"generated": False, "error": str(e)}
    finally:
        session.close()


@celery_app.task(name="collector.tasks.nlp_tasks.aggregate_sentiment")
def aggregate_sentiment() -> dict:
    """Aggregate sentiment by symbol from recent documents.

    Stores results in Redis for quick dashboard access.
    """
    engine = _get_nlp_engine()
    session = _get_sync_session()

    if session is None:
        logger.warning("[NLP] No DB session — skipping sentiment aggregation")
        return {"symbols": 0}

    try:
        from app.models.nlp import NlpDocument

        docs = (
            session.query(NlpDocument)
            .filter(NlpDocument.processed == True)  # noqa: E712
            .filter(NlpDocument.sentiment_score.isnot(None))
            .order_by(NlpDocument.created_at.desc())
            .limit(500)
            .all()
        )

        # Extract ticker symbols from entities and group sentiment
        symbol_sentiments: dict[str, list[float]] = {}
        for doc in docs:
            if not doc.entities_json:
                continue
            try:
                entities = json.loads(doc.entities_json)
            except (json.JSONDecodeError, TypeError):
                continue

            tickers = [
                e["text"].lstrip("$")
                for e in entities
                if e.get("entity_type") == "ticker"
            ]
            for ticker in tickers:
                symbol_sentiments.setdefault(ticker, []).append(
                    float(doc.sentiment_score)
                )

        # Compute averages
        result: dict[str, dict] = {}
        for sym, scores in symbol_sentiments.items():
            avg = sum(scores) / len(scores)
            result[sym] = {
                "symbol": sym,
                "avg_sentiment": round(avg, 4),
                "doc_count": len(scores),
                "label": "positive" if avg > 0.1 else ("negative" if avg < -0.1 else "neutral"),
            }

        # Save to Redis
        save_data("sentiment_by_symbol", result, ttl=1800)

        logger.info("[NLP] Aggregated sentiment for %d symbols", len(result))
        return {"symbols": len(result)}

    except Exception as e:
        session.rollback()
        logger.error("[NLP] aggregate_sentiment failed: %s", e)
        return {"symbols": 0, "error": str(e)}
    finally:
        session.close()
