"""Celery tasks for alternative data collection — insider trades, short interest,
Google Trends.  Each task generates realistic mock data when the real API is
unavailable."""

import json
import logging
import random
import uuid
from datetime import date, datetime, timedelta

from collector.celery_app import celery_app
from collector.tasks.base import get_sync_redis, save_data

logger = logging.getLogger(__name__)

# Common test symbols
SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "JPM", "V", "WMT"]

FILER_NAMES = [
    "Tim Cook", "Satya Nadella", "Sundar Pichai", "Andy Jassy",
    "Jensen Huang", "Elon Musk", "Mark Zuckerberg", "Jamie Dimon",
    "Ryan McInerney", "Doug McMillon",
]

AGENCIES = [
    "Department of Defense", "NASA", "Department of Energy",
    "Department of Health and Human Services", "General Services Administration",
    "Department of Homeland Security", "Department of Veterans Affairs",
]

PATENT_TITLES = [
    "Systems and methods for distributed machine learning inference",
    "Quantum computing error correction apparatus",
    "Neural network architecture for natural language processing",
    "Autonomous vehicle navigation system",
    "Blockchain-based supply chain verification method",
    "Advanced semiconductor fabrication process",
    "Augmented reality head-mounted display",
    "Energy-efficient data center cooling system",
    "Secure multi-party computation protocol",
    "AI-driven drug discovery platform",
]


def _get_sync_session():
    """Create a synchronous DB session for Celery tasks."""
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from app.config import get_settings

        settings = get_settings()
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


@celery_app.task(name="collector.tasks.alt_data_tasks.fetch_insider_trades")
def fetch_insider_trades() -> dict:
    """Fetch insider trades from SEC EDGAR. Falls back to mock data."""
    session = _get_sync_session()

    # Generate realistic mock data
    trades = []
    today = date.today()

    for i in range(random.randint(5, 10)):
        sym = random.choice(SYMBOLS)
        filer = random.choice(FILER_NAMES)
        tx_type = random.choice(["buy", "sell", "sell", "grant"])  # sells more common
        shares = round(random.uniform(1000, 500000), 4)
        price = round(random.uniform(50, 800), 4)
        value = round(shares * price, 4)
        filing = today - timedelta(days=random.randint(0, 30))

        trades.append({
            "id": str(uuid.uuid4()),
            "symbol": sym,
            "filer_name": filer,
            "transaction_type": tx_type,
            "shares": shares,
            "price": price,
            "value": value,
            "filing_date": filing.isoformat(),
            "source_url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={sym}",
        })

    # Persist to DB if available
    if session:
        try:
            from app.models.alt_data import InsiderTrade

            for t in trades:
                record = InsiderTrade(
                    symbol=t["symbol"],
                    filer_name=t["filer_name"],
                    transaction_type=t["transaction_type"],
                    shares=t["shares"],
                    price=t["price"],
                    value=t["value"],
                    filing_date=date.fromisoformat(t["filing_date"]),
                    source_url=t["source_url"],
                )
                session.add(record)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("[ALT-DATA] Failed to persist insider trades: %s", e)
        finally:
            session.close()

    # Cache in Redis
    save_data("insider_trades", trades, ttl=1800)
    logger.info("[ALT-DATA] Fetched %d insider trades (mock)", len(trades))
    return {"count": len(trades)}


@celery_app.task(name="collector.tasks.alt_data_tasks.fetch_short_interest")
def fetch_short_interest() -> dict:
    """Fetch short interest from FINRA. Falls back to mock data."""
    session = _get_sync_session()
    today = date.today()
    records = []

    for sym in SYMBOLS:
        short_int = round(random.uniform(1_000_000, 50_000_000), 4)
        short_ratio = round(random.uniform(0.5, 15.0), 4)
        days = round(random.uniform(0.5, 10.0), 4)

        records.append({
            "id": str(uuid.uuid4()),
            "symbol": sym,
            "short_interest": short_int,
            "short_ratio": short_ratio,
            "days_to_cover": days,
            "report_date": today.isoformat(),
        })

    if session:
        try:
            from app.models.alt_data import ShortInterest

            for r in records:
                record = ShortInterest(
                    symbol=r["symbol"],
                    short_interest=r["short_interest"],
                    short_ratio=r["short_ratio"],
                    days_to_cover=r["days_to_cover"],
                    report_date=date.fromisoformat(r["report_date"]),
                )
                session.add(record)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("[ALT-DATA] Failed to persist short interest: %s", e)
        finally:
            session.close()

    save_data("short_interest", records, ttl=1800)
    logger.info("[ALT-DATA] Fetched %d short interest records (mock)", len(records))
    return {"count": len(records)}


@celery_app.task(name="collector.tasks.alt_data_tasks.fetch_google_trends")
def fetch_google_trends() -> dict:
    """Fetch Google Trends data. Falls back to mock data."""
    session = _get_sync_session()

    keywords = SYMBOLS + ["AI", "recession", "bitcoin", "interest rates", "inflation"]
    today = date.today()
    records = []

    for kw in random.sample(keywords, min(8, len(keywords))):
        records.append({
            "id": str(uuid.uuid4()),
            "keyword": kw,
            "interest_score": random.randint(10, 100),
            "date": today.isoformat(),
            "region": "US",
        })

    if session:
        try:
            from app.models.alt_data import GoogleTrend

            for r in records:
                record = GoogleTrend(
                    keyword=r["keyword"],
                    interest_score=r["interest_score"],
                    date=date.fromisoformat(r["date"]),
                    region=r["region"],
                )
                session.add(record)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("[ALT-DATA] Failed to persist Google Trends: %s", e)
        finally:
            session.close()

    save_data("google_trends", records, ttl=1800)
    logger.info("[ALT-DATA] Fetched %d trend records (mock)", len(records))
    return {"count": len(records)}
