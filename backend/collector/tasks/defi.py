import logging
import time
from datetime import datetime

from collector.celery_app import celery_app
from collector.tasks.base import can_request, consume_token, save_data, safe_fetch

logger = logging.getLogger(__name__)


@celery_app.task(name="collector.tasks.defi.fetch_defi")
def fetch_defi():
    # Protocols
    if can_request("defillama"):
        consume_token("defillama")
        try:
            resp = safe_fetch("https://api.llama.fi/protocols")
            data = resp.json()
            protocols = [
                {
                    "name": p.get("name", ""),
                    "symbol": p.get("symbol", ""),
                    "tvl": p.get("tvl", 0) or 0,
                    "change1h": p.get("change_1h", 0) or 0,
                    "change1d": p.get("change_1d", 0) or 0,
                    "change7d": p.get("change_7d", 0) or 0,
                    "category": p.get("category", ""),
                    "chains": (p.get("chains") or [])[:5],
                    "url": p.get("url", ""),
                }
                for p in (data or [])[:50]
            ]
            save_data("defi_protocols", protocols, ttl=900)
            logger.info(f"[DEFI] Protocols updated: {len(protocols)}")
        except Exception as e:
            logger.error(f"[DEFI] Protocols error: {e}")

    time.sleep(0.5)

    # Chain TVL
    if can_request("defillama"):
        consume_token("defillama")
        try:
            resp = safe_fetch("https://api.llama.fi/v2/chains")
            data = resp.json()
            chains = [
                {
                    "name": c.get("name", ""),
                    "tvl": c.get("tvl", 0) or 0,
                    "tokenSymbol": c.get("tokenSymbol", ""),
                }
                for c in (data or [])[:20]
            ]
            save_data("defi_chains", chains, ttl=900)
            logger.info(f"[DEFI] Chains updated: {len(chains)}")
        except Exception as e:
            logger.error(f"[DEFI] Chains error: {e}")

    time.sleep(0.5)

    # Total TVL history
    if can_request("defillama"):
        consume_token("defillama")
        try:
            resp = safe_fetch("https://api.llama.fi/v2/historicalChainTvl")
            data = resp.json()
            recent = [
                {
                    "date": datetime.utcfromtimestamp(d["date"]).strftime("%Y-%m-%d"),
                    "tvl": d.get("tvl", 0),
                }
                for d in (data or [])[-30:]
            ]
            save_data("defi_tvl_history", recent, ttl=900)
            logger.info("[DEFI] TVL history updated")
        except Exception as e:
            logger.error(f"[DEFI] TVL error: {e}")

    time.sleep(0.5)

    # Yields
    if can_request("defillama"):
        consume_token("defillama")
        try:
            resp = safe_fetch("https://yields.llama.fi/pools")
            data = resp.json()
            pools = sorted(
                [
                    p for p in (data.get("data") or [])
                    if p.get("tvlUsd", 0) > 1000000 and 0 < p.get("apy", 0) < 100
                ],
                key=lambda p: p.get("tvlUsd", 0),
                reverse=True,
            )[:40]
            pools = [
                {
                    "pool": p.get("pool", ""),
                    "project": p.get("project", ""),
                    "symbol": p.get("symbol", ""),
                    "chain": p.get("chain", ""),
                    "tvl": p.get("tvlUsd", 0),
                    "apy": p.get("apy", 0),
                    "apyBase": p.get("apyBase", 0) or 0,
                    "apyReward": p.get("apyReward", 0) or 0,
                    "stablecoin": p.get("stablecoin", False),
                }
                for p in pools
            ]
            save_data("defi_yields", pools, ttl=900)
            logger.info(f"[DEFI] Yields updated: {len(pools)} pools")
        except Exception as e:
            logger.error(f"[DEFI] Yields error: {e}")

    time.sleep(0.5)

    # Stablecoins
    if can_request("defillama"):
        consume_token("defillama")
        try:
            resp = safe_fetch("https://stablecoins.llama.fi/stablecoins?includePrices=true")
            data = resp.json()
            stables = [
                {
                    "name": s.get("name", ""),
                    "symbol": s.get("symbol", ""),
                    "pegType": s.get("pegType", ""),
                    "circulating": (s.get("circulating") or {}).get("peggedUSD", 0),
                    "price": s.get("price", 1),
                }
                for s in (data.get("peggedAssets") or [])[:15]
            ]
            save_data("defi_stablecoins", stables, ttl=900)
            logger.info(f"[DEFI] Stablecoins updated: {len(stables)}")
        except Exception as e:
            logger.error(f"[DEFI] Stablecoins error: {e}")
