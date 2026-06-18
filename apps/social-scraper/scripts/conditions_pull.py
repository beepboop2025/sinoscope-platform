#!/usr/bin/env python3
"""End-to-end China economic conditions pull (no Celery).

This script wires the CBB collectors, the pure conditions-index computation,
and durable storage tiers together in one runnable file.

Storage tiers (all best-effort, independent):
  1. Disk snapshot   — data/cbb/snapshots/cbb_<utc>.json
  2. Disk history    — data/cbb/history.jsonl (compact append-only log)
  3. Postgres        — conditions_index_snapshots rows, IF reachable.
  4. Redis           — cbb:latest, IF reachable.

Usage:
    python scripts/conditions_pull.py
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from collectors.comtrade_mirror import ComtradeMirrorCollector
from collectors.cn_indicators import CNIndicatorsCollector
from processors.conditions_index import compute_conditions
from storage.models import ConditionsIndexSnapshot
from api.database import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("conditions_pull")

OUT_DIR = ROOT / "data" / "cbb"
SNAPSHOT_DIR = OUT_DIR / "snapshots"
HISTORY_PATH = OUT_DIR / "history.jsonl"
TAXONOMY_PATH = ROOT / "config" / "cbb_taxonomy.json"


# ── Input helpers ────────────────────────────────────────────────────────────
def _load_taxonomy() -> dict:
    try:
        with open(TAXONOMY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Could not load taxonomy from %s: %s", TAXONOMY_PATH, e)

    # Minimal inline fallback so the script can run before the config fragment lands.
    return {
        "sectors": {
            "electronics_machinery": {
                "hs_codes": ["84", "85", "90"],
                "region": "coastal_export",
                "cn_hf_sources": ["ccfi", "scfi"],
            },
            "textiles_apparel": {
                "hs_codes": ["61", "62", "63"],
                "region": "coastal_export",
                "cn_hf_sources": ["ccfi"],
            },
            "autos": {
                "hs_codes": ["87"],
                "region": "inland",
                "cn_hf_sources": ["cpca_retail_pv", "cpca_wholesale_pv"],
            },
            "steel": {
                "hs_codes": ["72", "73"],
                "region": "northeast",
                "cn_hf_sources": ["bdi"],
            },
            "cement": {
                "hs_codes": ["25", "68"],
                "region": "inland",
                "cn_hf_sources": [],
            },
            "coal": {
                "hs_codes": ["27"],
                "region": "inland",
                "cn_hf_sources": ["bdi"],
            },
            "transport_logistics": {
                "hs_codes": ["86", "88", "89"],
                "region": "national",
                "cn_hf_sources": ["bdi", "ccfi", "scfi"],
            },
            "property": {
                "hs_codes": ["94"],
                "region": "national",
                "cn_hf_sources": [],
            },
            "consumer_macro": {
                "hs_codes": ["29", "33", "39"],
                "region": "national",
                "cn_hf_sources": ["yiwu_index"],
            },
        }
    }


def _query_sentiment_mentions() -> list[dict]:
    """Load sentiment sector scores from Postgres (best-effort)."""
    try:
        from storage.models import SentimentScore

        db = SessionLocal()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            rows = db.query(SentimentScore).filter(SentimentScore.created_at >= cutoff).all()
            mentions: list[dict] = []
            for row in rows:
                scores = row.sector_scores or {}
                for sector in scores.keys():
                    mentions.append(
                        {
                            "date": row.created_at or datetime.now(timezone.utc),
                            "sector": sector,
                            "score": float(row.overall or 0.0),
                        }
                    )
            return mentions
        finally:
            db.close()
    except Exception as e:
        logger.warning("Sentiment query failed: %s", e)
        return []


def _to_records(parsed: Any) -> list[dict]:
    if isinstance(parsed, pd.DataFrame):
        return parsed.replace({pd.NA: None}).to_dict("records")
    return list(parsed or [])


def _records_from_economic_data(
    trade_rows: list[dict], indicator_rows: list[dict]
) -> tuple[list[dict], list[dict]]:
    """Convert EconomicData-style records into compute_conditions inputs."""
    trade: list[dict] = []
    indicators: list[dict] = []

    for row in trade_rows:
        # Accept either raw collector records or EconomicData dicts.
        if "flow" in row and "hs" in row:
            trade.append(row)
            continue

        ind = str(row.get("indicator", ""))
        meta = row.get("metadata") or row.get("extra_data") or {}
        if not isinstance(meta, dict):
            meta = {}

        if ind.startswith("trade_"):
            parts = ind.split("_")
            if len(parts) >= 3:
                _, flow, hs = parts[:3]
                trade.append(
                    {
                        "date": row.get("date"),
                        "flow": flow,
                        "hs": hs,
                        "value": float(row.get("value") or 0.0),
                        "reporter": meta.get("reporter", "156"),
                        "partner": meta.get("partner", "0"),
                        "net_weight": meta.get("netWeight", 0.0),
                    }
                )

    for row in indicator_rows:
        if row.get("indicator") is not None and row.get("value") is not None:
            indicators.append(
                {
                    "date": row.get("date"),
                    "indicator": row.get("indicator"),
                    "value": float(row.get("value") or 0.0),
                }
            )

    return trade, indicators


async def _collect_trade() -> list[dict]:
    """Run the Comtrade mirror collector and return trade records."""
    collector = ComtradeMirrorCollector({"recent_months": 3})
    try:
        raw = await collector.collect()
        parsed = await collector.parse(raw)
        return _to_records(parsed)
    except Exception as e:
        logger.warning("Trade collection failed: %s", e)
        return []
    finally:
        await collector.close()


async def _collect_cn_indicators() -> list[dict]:
    """Run the CN indicators collector and return indicator records."""
    collector = CNIndicatorsCollector({})
    try:
        raw = await collector.collect()
        parsed = await collector.parse(raw)
        return _to_records(parsed)
    except Exception as e:
        logger.warning("CN indicator collection failed: %s", e)
        return []
    finally:
        await collector.close()


# ── Storage helpers ──────────────────────────────────────────────────────────
def _store_snapshot(index: list[dict], now: datetime) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%dT%H%M%S")
    snap_path = SNAPSHOT_DIR / f"cbb_{stamp}.json"
    payload = {
        "generated_at": now.isoformat(),
        "count": len(index),
        "index": index,
    }
    snap_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return snap_path


def _append_history(index: list[dict], now: datetime) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_at": now.isoformat(),
        "count": len(index),
        "sectors": [
            {
                "sector": r["sector"],
                "period": r["period"],
                "D": r["D"],
                "momentum": r["momentum"],
                "confidence": r["confidence"],
            }
            for r in index
        ],
    }
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")


def _store_postgres(index: list[dict], now: datetime) -> str:
    try:
        db = SessionLocal()
        try:
            for row in index:
                snapshot = ConditionsIndexSnapshot(
                    generated_at=now,
                    period=row.get("period"),
                    sector=row["sector"],
                    region=row.get("region"),
                    diffusion=row.get("D", 0.0),
                    sentiment=row.get("SD", 0.0),
                    anchor=row.get("AS", 0.0),
                    momentum=row.get("momentum", 0.0),
                    mirror_gap=row.get("mirror_gap"),
                    confidence=row.get("confidence", "low"),
                    n_mentions=row.get("n_mentions", 0),
                    inputs=row.get("inputs", {}),
                )
                db.add(snapshot)
            db.commit()
            return "ok"
        finally:
            db.close()
    except Exception as e:
        return f"unavailable ({type(e).__name__})"


def _store_redis(index: list[dict], now: datetime) -> str:
    try:
        import redis

        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
        payload = {
            "generated_at": now.isoformat(),
            "status": "live",
            "count": len(index),
            "index": index,
        }
        r.set("cbb:latest", json.dumps(payload, ensure_ascii=False), ex=7200)
        r.close()
        return "ok"
    except Exception as e:
        return f"unavailable ({type(e).__name__})"


def _print_table(index: list[dict]) -> None:
    print("\n=== China Economic Conditions Index ===")
    header = (
        f"{'Sector':<22} {'Region':<14} {'Period':<8} {'D':>8} "
        f"{'SD':>8} {'AS':>8} {'Mom':>8} {'Gap':>8} {'Conf':>6} {'N':>5}"
    )
    print(header)
    print("-" * len(header))
    for row in index:
        gap = f"{row['mirror_gap']:.1f}" if row.get("mirror_gap") is not None else "-"
        print(
            f"{row['sector']:<22} {row['region']:<14} {row['period']:<8} "
            f"{row['D']:>8.2f} {row['SD']:>8.2f} {row['AS']:>8.2f} "
            f"{row['momentum']:>8.2f} {gap:>8} {row['confidence']:>6} {row['n_mentions']:>5d}"
        )
    print(f"\nTotal sectors: {len(index)}")


# ── Main entry point ─────────────────────────────────────────────────────────
async def main():
    now = datetime.now(timezone.utc)
    taxonomy = _load_taxonomy()
    if not taxonomy.get("sectors"):
        print("No taxonomy available; aborting.")
        return []

    print("[conditions_pull] Collecting trade data...")
    trade_raw = await _collect_trade()
    print(f"[conditions_pull] Trade records: {len(trade_raw)}")

    print("[conditions_pull] Collecting CN high-frequency indicators...")
    cn_raw = await _collect_cn_indicators()
    print(f"[conditions_pull] CN indicator records: {len(cn_raw)}")

    print("[conditions_pull] Loading sentiment mentions...")
    sentiment = _query_sentiment_mentions()
    print(f"[conditions_pull] Sentiment mentions: {len(sentiment)}")

    trade_records, indicator_records = _records_from_economic_data(trade_raw, cn_raw)
    index = compute_conditions(trade_records, indicator_records, sentiment, taxonomy, now)

    # Disk tiers (always attempted).
    snap_path = _store_snapshot(index, now)
    _append_history(index, now)

    # Remote tiers (best-effort).
    db_status = _store_postgres(index, now)
    redis_status = _store_redis(index, now)

    print("\n=== Storage ===")
    print(f"  snapshot : {snap_path}")
    print(f"  history  : {HISTORY_PATH}")
    print(f"  postgres : {db_status}")
    print(f"  redis    : {redis_status}")

    _print_table(index)
    return index


if __name__ == "__main__":
    asyncio.run(main())
