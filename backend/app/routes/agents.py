"""Routes for autonomous agents — CRUD configs, trigger runs, list findings, escalation rules."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import AuthUser, require_auth
from app.models.agent import AgentConfig, AgentFinding, AgentRun, EscalationRule
from app.redis import get_redis
from app.schemas.agent import (
    AgentConfigCreate,
    AgentConfigResponse,
    AgentConfigUpdate,
    AgentFindingList,
    AgentFindingResponse,
    AgentRunResponse,
    EscalationRuleCreate,
    EscalationRuleResponse,
    EscalationRuleUpdate,
)
from app.services.agent_engine import AgentEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])


# ---------------------------------------------------------------------------
# Agent Configs CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=list[AgentConfigResponse])
async def list_agents(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(AgentConfig)
        .where(AgentConfig.user_id == auth.user_id)
        .order_by(AgentConfig.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=AgentConfigResponse, status_code=201)
async def create_agent(
    body: AgentConfigCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    agent = AgentConfig(
        name=body.name,
        agent_type=body.agent_type,
        config_json=body.config_json,
        is_active=body.is_active,
        schedule_cron=body.schedule_cron,
        user_id=auth.user_id,
    )
    session.add(agent)
    await session.flush()
    return agent


@router.get("/{agent_id}", response_model=AgentConfigResponse)
async def get_agent(
    agent_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(AgentConfig).where(AgentConfig.id == agent_id, AgentConfig.user_id == auth.user_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.patch("/{agent_id}", response_model=AgentConfigResponse)
async def update_agent(
    agent_id: str,
    body: AgentConfigUpdate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(AgentConfig).where(AgentConfig.id == agent_id, AgentConfig.user_id == auth.user_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if body.name is not None:
        agent.name = body.name
    if body.config_json is not None:
        agent.config_json = body.config_json
    if body.is_active is not None:
        agent.is_active = body.is_active
    if body.schedule_cron is not None:
        agent.schedule_cron = body.schedule_cron

    await session.flush()
    await session.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(AgentConfig).where(AgentConfig.id == agent_id, AgentConfig.user_id == auth.user_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await session.delete(agent)


# ---------------------------------------------------------------------------
# Agent Runs
# ---------------------------------------------------------------------------


@router.post("/{agent_id}/run", response_model=AgentRunResponse, status_code=201)
async def trigger_agent_run(
    agent_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    result = await session.execute(
        select(AgentConfig).where(AgentConfig.id == agent_id, AgentConfig.user_id == auth.user_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    run = AgentRun(
        agent_id=agent.id,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    await session.flush()

    # Execute agent synchronously (for small workloads; use Celery for heavy ones)
    agent_result = await AgentEngine.execute_agent(
        {"agent_type": agent.agent_type, "config_json": agent.config_json},
        redis,
    )

    if agent_result.error:
        run.status = "failed"
        run.error_message = agent_result.error
    else:
        run.status = "completed"
        run.findings_count = len(agent_result.findings)

        for f in agent_result.findings:
            finding = AgentFinding(
                agent_run_id=run.id,
                finding_type=f.finding_type,
                severity=f.severity,
                title=f.title,
                description=f.description,
                data_json=f.data_json,
            )
            session.add(finding)

    run.completed_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(run)
    return run


@router.get("/runs", response_model=list[AgentRunResponse])
async def list_runs(
    agent_id: str | None = Query(None),
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    query = (
        select(AgentRun)
        .join(AgentConfig, AgentRun.agent_id == AgentConfig.id)
        .where(AgentConfig.user_id == auth.user_id)
        .order_by(AgentRun.created_at.desc())
    )
    if agent_id:
        query = query.where(AgentRun.agent_id == agent_id)
    result = await session.execute(query)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


@router.get("/findings", response_model=AgentFindingList)
async def list_findings(
    severity: str | None = Query(None),
    finding_type: str | None = Query(None),
    acknowledged: bool | None = Query(None),
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    query = (
        select(AgentFinding)
        .join(AgentRun, AgentFinding.agent_run_id == AgentRun.id)
        .join(AgentConfig, AgentRun.agent_id == AgentConfig.id)
        .where(AgentConfig.user_id == auth.user_id)
        .order_by(AgentFinding.created_at.desc())
    )
    if severity:
        query = query.where(AgentFinding.severity == severity)
    if finding_type:
        query = query.where(AgentFinding.finding_type == finding_type)
    if acknowledged is not None:
        query = query.where(AgentFinding.acknowledged == acknowledged)

    result = await session.execute(query)
    findings = list(result.scalars().all())
    return AgentFindingList(findings=findings, total=len(findings))


@router.post("/findings/{finding_id}/acknowledge", response_model=AgentFindingResponse)
async def acknowledge_finding(
    finding_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(AgentFinding)
        .join(AgentRun, AgentFinding.agent_run_id == AgentRun.id)
        .join(AgentConfig, AgentRun.agent_id == AgentConfig.id)
        .where(AgentFinding.id == finding_id, AgentConfig.user_id == auth.user_id)
    )
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    finding.acknowledged = True
    await session.flush()
    await session.refresh(finding)
    return finding


# ---------------------------------------------------------------------------
# Escalation Rules CRUD
# ---------------------------------------------------------------------------


@router.get("/escalation-rules", response_model=list[EscalationRuleResponse])
async def list_escalation_rules(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(EscalationRule)
        .where(EscalationRule.user_id == auth.user_id)
        .order_by(EscalationRule.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/escalation-rules", response_model=EscalationRuleResponse, status_code=201)
async def create_escalation_rule(
    body: EscalationRuleCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    rule = EscalationRule(
        user_id=auth.user_id,
        finding_type=body.finding_type,
        min_severity=body.min_severity,
        channel=body.channel,
        channel_config_json=body.channel_config_json,
        is_active=body.is_active,
    )
    session.add(rule)
    await session.flush()
    return rule


@router.patch("/escalation-rules/{rule_id}", response_model=EscalationRuleResponse)
async def update_escalation_rule(
    rule_id: str,
    body: EscalationRuleUpdate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(EscalationRule).where(EscalationRule.id == rule_id, EscalationRule.user_id == auth.user_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Escalation rule not found")

    if body.finding_type is not None:
        rule.finding_type = body.finding_type
    if body.min_severity is not None:
        rule.min_severity = body.min_severity
    if body.channel is not None:
        rule.channel = body.channel
    if body.channel_config_json is not None:
        rule.channel_config_json = body.channel_config_json
    if body.is_active is not None:
        rule.is_active = body.is_active

    await session.flush()
    await session.refresh(rule)
    return rule


@router.delete("/escalation-rules/{rule_id}", status_code=204)
async def delete_escalation_rule(
    rule_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(EscalationRule).where(EscalationRule.id == rule_id, EscalationRule.user_id == auth.user_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Escalation rule not found")
    await session.delete(rule)
