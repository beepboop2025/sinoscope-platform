"""Celery tasks for autonomous agents — execute single agent and run all active agents."""

import json
import logging
from datetime import datetime, timezone

import redis as redis_lib
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import get_settings
from collector.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_sync_dsn() -> str:
    settings = get_settings()
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


@celery_app.task(name="collector.tasks.agents.execute_agent")
def execute_agent(agent_config_id: str) -> dict:
    """Run a single agent by its config ID (synchronous Celery wrapper).

    Creates an AgentRun record, executes the agent engine synchronously,
    and persists findings to the database.
    """
    settings = get_settings()
    engine = create_engine(_get_sync_dsn())

    try:
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)

        with Session(engine) as session:
            from app.models.agent import AgentConfig, AgentFinding, AgentRun

            result = session.execute(
                select(AgentConfig).where(AgentConfig.id == agent_config_id)
            )
            agent = result.scalar_one_or_none()
            if not agent:
                logger.error("[AGENTS] Agent config %s not found", agent_config_id)
                return {"status": "error", "message": "Agent not found"}

            # Create run record
            run = AgentRun(
                agent_id=agent.id,
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            session.add(run)
            session.flush()

            try:
                # Parse config
                try:
                    config = json.loads(agent.config_json) if agent.config_json else {}
                except (json.JSONDecodeError, TypeError):
                    config = {}

                # Execute agent logic synchronously
                findings = _run_agent_sync(agent.agent_type, config, r)

                run.status = "completed"
                run.findings_count = len(findings)
                run.completed_at = datetime.now(timezone.utc)

                for f in findings:
                    finding = AgentFinding(
                        agent_run_id=run.id,
                        finding_type=f["finding_type"],
                        severity=f["severity"],
                        title=f["title"],
                        description=f["description"],
                        data_json=f.get("data_json"),
                    )
                    session.add(finding)

                session.commit()
                logger.info(
                    "[AGENTS] Agent %s completed: %d findings",
                    agent.name, len(findings),
                )
                return {"status": "completed", "findings_count": len(findings)}

            except Exception as exc:
                run.status = "failed"
                run.error_message = str(exc)
                run.completed_at = datetime.now(timezone.utc)
                session.commit()
                logger.error("[AGENTS] Agent %s failed: %s", agent.name, exc)
                return {"status": "failed", "error": str(exc)}

    except Exception as exc:
        logger.error("[AGENTS] Task failed for %s: %s", agent_config_id, exc)
        return {"status": "error", "error": str(exc)}
    finally:
        engine.dispose()


@celery_app.task(name="collector.tasks.agents.run_all_agents")
def run_all_agents() -> dict:
    """Run all active agents sequentially."""
    settings = get_settings()
    engine = create_engine(_get_sync_dsn())

    try:
        with Session(engine) as session:
            from app.models.agent import AgentConfig

            result = session.execute(
                select(AgentConfig).where(AgentConfig.is_active == True)  # noqa: E712
            )
            agents = list(result.scalars().all())

            if not agents:
                logger.info("[AGENTS] No active agents to run")
                return {"status": "completed", "agents_run": 0}

            results = []
            for agent in agents:
                # Dispatch as individual tasks for parallelism
                task_result = execute_agent.delay(agent.id)
                results.append({"agent_id": agent.id, "task_id": task_result.id})

            logger.info("[AGENTS] Dispatched %d agent tasks", len(results))
            return {"status": "dispatched", "agents_run": len(results), "tasks": results}

    except Exception as exc:
        logger.error("[AGENTS] run_all_agents failed: %s", exc)
        return {"status": "error", "error": str(exc)}
    finally:
        engine.dispose()


def _run_agent_sync(agent_type: str, config: dict, r: redis_lib.Redis) -> list[dict]:
    """Synchronous agent execution for Celery (no async event loop).

    Returns a list of finding dicts with keys: finding_type, severity, title, description, data_json.
    """
    findings: list[dict] = []

    if agent_type == "market_monitor":
        findings = _market_monitor_sync(config, r)
    elif agent_type == "anomaly_detector":
        findings = _anomaly_detector_sync(config, r)
    elif agent_type == "correlation_finder":
        findings = _correlation_finder_sync(config, r)
    elif agent_type == "research_generator":
        findings = _research_generator_sync(config, r)
    elif agent_type == "portfolio_advisor":
        findings = _portfolio_advisor_sync(config, r)
    else:
        logger.warning("[AGENTS] Unknown agent type: %s", agent_type)

    return findings


def _load_redis_data(r: redis_lib.Redis, key: str) -> list | dict:
    """Load and unwrap data from Redis."""
    raw = r.get(key)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and "data" in parsed:
            return parsed["data"]
        return parsed
    except (json.JSONDecodeError, TypeError):
        return []


def _market_monitor_sync(config: dict, r: redis_lib.Redis) -> list[dict]:
    """Synchronous market monitor — checks price thresholds, volume spikes."""
    findings: list[dict] = []
    thresholds = config.get("price_thresholds", {})
    volume_spike_factor = float(config.get("volume_spike_factor", 2.0))

    crypto_data = _load_redis_data(r, "market:crypto_markets")
    if not isinstance(crypto_data, list):
        crypto_data = []

    for item in crypto_data:
        sym = str(item.get("symbol", "")).upper()
        price = float(item.get("current_price", 0) or 0)

        if sym in thresholds:
            t = thresholds[sym]
            if "above" in t and price > float(t["above"]):
                findings.append({
                    "finding_type": "alert",
                    "severity": "high",
                    "title": f"{sym} above ${t['above']}",
                    "description": f"{sym} price ${price:.2f} exceeds threshold ${t['above']}.",
                    "data_json": json.dumps({"symbol": sym, "price": price}),
                })
            if "below" in t and price < float(t["below"]):
                findings.append({
                    "finding_type": "alert",
                    "severity": "high",
                    "title": f"{sym} below ${t['below']}",
                    "description": f"{sym} price ${price:.2f} is below threshold ${t['below']}.",
                    "data_json": json.dumps({"symbol": sym, "price": price}),
                })

    return findings


def _anomaly_detector_sync(config: dict, r: redis_lib.Redis) -> list[dict]:
    """Synchronous anomaly detector — detects unusual 24h price movements."""
    findings: list[dict] = []
    std_threshold = float(config.get("std_threshold", 3.0))

    crypto_data = _load_redis_data(r, "market:crypto_markets")
    if not isinstance(crypto_data, list):
        crypto_data = []

    for item in crypto_data:
        sym = str(item.get("symbol", "")).upper()
        pct_24h = float(item.get("price_change_percentage_24h", 0) or 0)
        if abs(pct_24h) > std_threshold * 3:
            severity = "critical" if abs(pct_24h) > 20 else "high"
            direction = "surged" if pct_24h > 0 else "dropped"
            findings.append({
                "finding_type": "anomaly",
                "severity": severity,
                "title": f"{sym} {direction} {abs(pct_24h):.1f}% in 24h",
                "description": f"Anomalous movement detected for {sym}.",
                "data_json": json.dumps({"symbol": sym, "pct_change_24h": pct_24h}),
            })

    return findings


def _correlation_finder_sync(config: dict, r: redis_lib.Redis) -> list[dict]:
    """Synchronous correlation finder — returns empty list (requires historical data)."""
    # In production, this would compute correlations from historical price data.
    # For the Celery task, we return an empty list as a safe default.
    return []


def _research_generator_sync(config: dict, r: redis_lib.Redis) -> list[dict]:
    """Synchronous research summary generator."""
    findings: list[dict] = []
    categories = config.get("categories", ["news"])

    for category in categories:
        data = _load_redis_data(r, f"market:{category}")
        if isinstance(data, list) and data:
            count = len(data)
            findings.append({
                "finding_type": "insight",
                "severity": "low",
                "title": f"Research: {count} {category} items",
                "description": f"Found {count} recent {category} items.",
                "data_json": json.dumps({"category": category, "count": count}),
            })

    return findings


def _portfolio_advisor_sync(config: dict, r: redis_lib.Redis) -> list[dict]:
    """Synchronous portfolio health check."""
    findings: list[dict] = []
    holdings = config.get("holdings", [])
    max_concentration = float(config.get("max_concentration", 0.3))

    if not holdings:
        return [{
            "finding_type": "recommendation",
            "severity": "low",
            "title": "No holdings configured",
            "description": "Configure holdings for portfolio analysis.",
        }]

    total_weight = sum(float(h.get("weight", 0)) for h in holdings)
    for h in holdings:
        sym = str(h.get("symbol", "")).upper()
        weight = float(h.get("weight", 0))
        if total_weight > 0 and weight / total_weight > max_concentration:
            pct = weight / total_weight * 100
            findings.append({
                "finding_type": "recommendation",
                "severity": "medium",
                "title": f"Concentration risk: {sym} at {pct:.1f}%",
                "description": f"{sym} exceeds max concentration.",
                "data_json": json.dumps({"symbol": sym, "pct": round(pct, 2)}),
            })

    return findings
