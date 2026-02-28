"""Autonomous agent engine — 5 agent types that analyze market data and generate findings."""

import json
import logging
import statistics
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Finding:
    """Single finding produced by an agent run."""

    finding_type: str  # alert, insight, recommendation, anomaly
    severity: str  # low, medium, high, critical
    title: str
    description: str
    data_json: str | None = None


@dataclass
class AgentResult:
    """Outcome of a single agent execution."""

    findings: list[Finding] = field(default_factory=list)
    error: str | None = None


class AgentEngine:
    """Stateless engine with 5 agent types that inspect cached market data.

    All data is read from Redis (market:crypto_markets, market:stocks, etc.)
    so the agents are completely decoupled from the live data collectors.
    """

    # ------------------------------------------------------------------
    # Public entry-point
    # ------------------------------------------------------------------

    @staticmethod
    async def execute_agent(agent_config: dict, redis: Any) -> AgentResult:
        """Route to the correct agent type and run it.

        Parameters
        ----------
        agent_config:
            Dict with keys ``agent_type`` and ``config_json`` (already parsed).
        redis:
            An async Redis connection (or mock).
        """
        agent_type = agent_config.get("agent_type", "")
        try:
            config = agent_config.get("config_json", "{}")
            if isinstance(config, str):
                config = json.loads(config)
        except (json.JSONDecodeError, TypeError):
            config = {}

        handler = {
            "market_monitor": AgentEngine.market_monitor,
            "anomaly_detector": AgentEngine.anomaly_detector,
            "correlation_finder": AgentEngine.correlation_finder,
            "research_generator": AgentEngine.research_generator,
            "portfolio_advisor": AgentEngine.portfolio_advisor,
        }.get(agent_type)

        if handler is None:
            return AgentResult(error=f"Unknown agent type: {agent_type}")

        try:
            findings = await handler(config, redis)
            return AgentResult(findings=findings)
        except Exception as exc:
            logger.error("Agent %s failed: %s", agent_type, exc, exc_info=True)
            return AgentResult(error=str(exc))

    # ------------------------------------------------------------------
    # Agent implementations
    # ------------------------------------------------------------------

    @staticmethod
    async def market_monitor(config: dict, redis: Any) -> list[Finding]:
        """Check price thresholds and volume spikes.

        Config keys:
            symbols: list[str]
            price_thresholds: dict[symbol, {above: float, below: float}]
            volume_spike_factor: float (default 2.0)
        """
        findings: list[Finding] = []
        symbols = config.get("symbols", [])
        thresholds = config.get("price_thresholds", {})
        volume_spike_factor = float(config.get("volume_spike_factor", 2.0))

        # Fetch crypto market data
        raw = await redis.get("market:crypto_markets")
        crypto_data: list[dict] = []
        if raw:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            crypto_data = parsed.get("data", parsed) if isinstance(parsed, dict) else parsed

        # Fetch stock data
        raw_stocks = await redis.get("market:stocks")
        stock_data: list[dict] = []
        if raw_stocks:
            parsed = json.loads(raw_stocks) if isinstance(raw_stocks, str) else raw_stocks
            stock_data = parsed.get("data", parsed) if isinstance(parsed, dict) else parsed

        all_assets = []
        for item in crypto_data:
            all_assets.append({
                "symbol": str(item.get("symbol", "")).upper(),
                "price": float(item.get("current_price", 0) or 0),
                "volume": float(item.get("total_volume", 0) or 0),
                "avg_volume": float(item.get("total_volume", 0) or 0) * 0.8,  # approximate
            })
        for item in stock_data:
            all_assets.append({
                "symbol": str(item.get("symbol", "")).upper(),
                "price": float(item.get("price", 0) or 0),
                "volume": float(item.get("volume", 0) or 0),
                "avg_volume": float(item.get("avgVolume", item.get("avg_volume", 0)) or 0),
            })

        for asset in all_assets:
            sym = asset["symbol"]
            if symbols and sym not in [s.upper() for s in symbols]:
                continue

            # Price threshold checks
            if sym in thresholds:
                t = thresholds[sym]
                if "above" in t and asset["price"] > float(t["above"]):
                    findings.append(Finding(
                        finding_type="alert",
                        severity="high",
                        title=f"{sym} above threshold ${t['above']}",
                        description=f"{sym} current price ${asset['price']:.2f} exceeds upper threshold ${t['above']}.",
                        data_json=json.dumps({"symbol": sym, "price": asset["price"], "threshold": t["above"]}),
                    ))
                if "below" in t and asset["price"] < float(t["below"]):
                    findings.append(Finding(
                        finding_type="alert",
                        severity="high",
                        title=f"{sym} below threshold ${t['below']}",
                        description=f"{sym} current price ${asset['price']:.2f} is below lower threshold ${t['below']}.",
                        data_json=json.dumps({"symbol": sym, "price": asset["price"], "threshold": t["below"]}),
                    ))

            # Volume spike detection
            if asset["avg_volume"] > 0 and asset["volume"] > asset["avg_volume"] * volume_spike_factor:
                spike_ratio = asset["volume"] / asset["avg_volume"]
                findings.append(Finding(
                    finding_type="alert",
                    severity="medium",
                    title=f"{sym} volume spike ({spike_ratio:.1f}x avg)",
                    description=f"{sym} current volume {asset['volume']:.0f} is {spike_ratio:.1f}x the average volume.",
                    data_json=json.dumps({"symbol": sym, "volume": asset["volume"], "avg_volume": asset["avg_volume"]}),
                ))

        logger.info("market_monitor produced %d findings", len(findings))
        return findings

    @staticmethod
    async def anomaly_detector(config: dict, redis: Any) -> list[Finding]:
        """Detect unusual price movements (>3 std deviations from 20-period mean).

        Config keys:
            symbols: list[str]
            std_threshold: float (default 3.0)
            lookback: int (default 20)
        """
        findings: list[Finding] = []
        std_threshold = float(config.get("std_threshold", 3.0))

        raw = await redis.get("market:crypto_markets")
        crypto_data: list[dict] = []
        if raw:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            crypto_data = parsed.get("data", parsed) if isinstance(parsed, dict) else parsed

        for item in crypto_data:
            sym = str(item.get("symbol", "")).upper()
            price = float(item.get("current_price", 0) or 0)
            pct_change_24h = float(item.get("price_change_percentage_24h", 0) or 0)

            # Use 24h percentage change as a proxy for anomaly
            # In production, we would track historical prices for a proper rolling window
            if abs(pct_change_24h) > std_threshold * 3:
                severity = "critical" if abs(pct_change_24h) > 20 else "high"
                direction = "surged" if pct_change_24h > 0 else "dropped"
                findings.append(Finding(
                    finding_type="anomaly",
                    severity=severity,
                    title=f"{sym} {direction} {abs(pct_change_24h):.1f}% in 24h",
                    description=f"{sym} has {direction} by {abs(pct_change_24h):.1f}% in the last 24 hours, "
                                f"exceeding {std_threshold}x standard deviation threshold. Current price: ${price:.2f}.",
                    data_json=json.dumps({
                        "symbol": sym,
                        "price": price,
                        "pct_change_24h": pct_change_24h,
                        "threshold": std_threshold,
                    }),
                ))

        logger.info("anomaly_detector produced %d findings", len(findings))
        return findings

    @staticmethod
    async def correlation_finder(config: dict, redis: Any) -> list[Finding]:
        """Find assets with correlation > 0.8 or < -0.8.

        Config keys:
            symbols: list[str]
            correlation_threshold: float (default 0.8)
        """
        findings: list[Finding] = []
        threshold = float(config.get("correlation_threshold", 0.8))

        raw = await redis.get("market:crypto_markets")
        crypto_data: list[dict] = []
        if raw:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            crypto_data = parsed.get("data", parsed) if isinstance(parsed, dict) else parsed

        # Extract price change data for pseudo-correlation
        assets: list[dict] = []
        for item in crypto_data:
            sym = str(item.get("symbol", "")).upper()
            pct_1h = float(item.get("price_change_percentage_1h_in_currency", 0) or 0)
            pct_24h = float(item.get("price_change_percentage_24h", 0) or 0)
            pct_7d = float(item.get("price_change_percentage_7d_in_currency", 0) or 0)
            assets.append({"symbol": sym, "changes": [pct_1h, pct_24h, pct_7d]})

        # Compare pairs for directional similarity
        checked: set[tuple[str, str]] = set()
        for i, a in enumerate(assets):
            for j, b in enumerate(assets):
                if i >= j:
                    continue
                pair = (a["symbol"], b["symbol"])
                if pair in checked:
                    continue
                checked.add(pair)

                # Simple correlation proxy using change direction agreement
                if len(a["changes"]) < 2 or len(b["changes"]) < 2:
                    continue

                try:
                    mean_a = statistics.mean(a["changes"])
                    mean_b = statistics.mean(b["changes"])
                    stdev_a = statistics.pstdev(a["changes"])
                    stdev_b = statistics.pstdev(b["changes"])
                    if stdev_a == 0 or stdev_b == 0:
                        continue

                    n = len(a["changes"])
                    covariance = sum(
                        (a["changes"][k] - mean_a) * (b["changes"][k] - mean_b) for k in range(n)
                    ) / n
                    corr = covariance / (stdev_a * stdev_b)
                except (statistics.StatisticsError, ZeroDivisionError):
                    continue

                if abs(corr) >= threshold:
                    direction = "positive" if corr > 0 else "negative"
                    findings.append(Finding(
                        finding_type="insight",
                        severity="low",
                        title=f"{a['symbol']}/{b['symbol']} {direction} correlation ({corr:.2f})",
                        description=f"{a['symbol']} and {b['symbol']} show a {direction} correlation of {corr:.2f} "
                                    f"based on recent price changes.",
                        data_json=json.dumps({
                            "symbol_a": a["symbol"],
                            "symbol_b": b["symbol"],
                            "correlation": round(corr, 4),
                        }),
                    ))

        logger.info("correlation_finder produced %d findings", len(findings))
        return findings

    @staticmethod
    async def research_generator(config: dict, redis: Any) -> list[Finding]:
        """Summarize recent news/documents.

        Config keys:
            categories: list[str] (default ["news"])
        """
        findings: list[Finding] = []
        categories = config.get("categories", ["news"])

        for category in categories:
            raw = await redis.get(f"market:{category}")
            if not raw:
                continue

            parsed = json.loads(raw) if isinstance(raw, str) else raw
            data = parsed.get("data", parsed) if isinstance(parsed, dict) else parsed

            if isinstance(data, list) and data:
                count = len(data)
                sample_titles = [str(item.get("title", item.get("headline", "N/A"))) for item in data[:5]]
                findings.append(Finding(
                    finding_type="insight",
                    severity="low",
                    title=f"Research summary: {count} {category} items",
                    description=f"Found {count} recent {category} items. Top headlines: "
                                + "; ".join(sample_titles),
                    data_json=json.dumps({"category": category, "count": count, "samples": sample_titles}),
                ))

        logger.info("research_generator produced %d findings", len(findings))
        return findings

    @staticmethod
    async def portfolio_advisor(config: dict, redis: Any) -> list[Finding]:
        """Basic portfolio health check (concentration risk, drawdown).

        Config keys:
            holdings: list[{symbol: str, weight: float, entry_price: float}]
            max_concentration: float (default 0.3 = 30%)
            max_drawdown_pct: float (default 20.0)
        """
        findings: list[Finding] = []
        holdings = config.get("holdings", [])
        max_concentration = float(config.get("max_concentration", 0.3))
        max_drawdown_pct = float(config.get("max_drawdown_pct", 20.0))

        if not holdings:
            findings.append(Finding(
                finding_type="recommendation",
                severity="low",
                title="No portfolio holdings configured",
                description="Configure holdings in the agent config to receive portfolio health analysis.",
            ))
            return findings

        # Fetch current prices
        raw = await redis.get("market:crypto_markets")
        price_map: dict[str, float] = {}
        if raw:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            data = parsed.get("data", parsed) if isinstance(parsed, dict) else parsed
            if isinstance(data, list):
                for item in data:
                    sym = str(item.get("symbol", "")).upper()
                    price_map[sym] = float(item.get("current_price", 0) or 0)

        # Concentration check
        total_weight = sum(float(h.get("weight", 0)) for h in holdings)
        for h in holdings:
            sym = str(h.get("symbol", "")).upper()
            weight = float(h.get("weight", 0))
            if total_weight > 0:
                pct = weight / total_weight
                if pct > max_concentration:
                    findings.append(Finding(
                        finding_type="recommendation",
                        severity="medium",
                        title=f"Concentration risk: {sym} at {pct * 100:.1f}%",
                        description=f"{sym} represents {pct * 100:.1f}% of the portfolio, "
                                    f"exceeding the {max_concentration * 100:.0f}% concentration limit.",
                        data_json=json.dumps({"symbol": sym, "weight_pct": round(pct * 100, 2)}),
                    ))

        # Drawdown check
        for h in holdings:
            sym = str(h.get("symbol", "")).upper()
            entry_price = float(h.get("entry_price", 0))
            current_price = price_map.get(sym, 0)
            if entry_price > 0 and current_price > 0:
                drawdown_pct = ((entry_price - current_price) / entry_price) * 100
                if drawdown_pct > max_drawdown_pct:
                    findings.append(Finding(
                        finding_type="alert",
                        severity="high",
                        title=f"{sym} drawdown {drawdown_pct:.1f}%",
                        description=f"{sym} has declined {drawdown_pct:.1f}% from entry price ${entry_price:.2f} "
                                    f"to ${current_price:.2f}, exceeding the {max_drawdown_pct:.0f}% limit.",
                        data_json=json.dumps({
                            "symbol": sym,
                            "entry_price": entry_price,
                            "current_price": current_price,
                            "drawdown_pct": round(drawdown_pct, 2),
                        }),
                    ))

        logger.info("portfolio_advisor produced %d findings", len(findings))
        return findings
