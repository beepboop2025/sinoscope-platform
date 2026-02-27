"""Pydantic v2 schemas for autonomous agents."""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# AgentConfig
# ---------------------------------------------------------------------------
class AgentConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    agent_type: str = Field(pattern=r"^(market_monitor|anomaly_detector|correlation_finder|research_generator|portfolio_advisor)$")
    config_json: str  # JSON string with thresholds, symbols, etc.
    is_active: bool = True
    schedule_cron: str | None = None


class AgentConfigUpdate(BaseModel):
    name: str | None = None
    config_json: str | None = None
    is_active: bool | None = None
    schedule_cron: str | None = None


class AgentConfigResponse(BaseModel):
    id: str
    name: str
    agent_type: str
    config_json: str
    is_active: bool
    schedule_cron: str | None = None
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# AgentRun
# ---------------------------------------------------------------------------
class AgentRunResponse(BaseModel):
    id: str
    agent_id: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    findings_count: int
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# AgentFinding
# ---------------------------------------------------------------------------
class AgentFindingResponse(BaseModel):
    id: str
    agent_run_id: str
    finding_type: str
    severity: str
    title: str
    description: str
    data_json: str | None = None
    acknowledged: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentFindingList(BaseModel):
    findings: list[AgentFindingResponse]
    total: int


# ---------------------------------------------------------------------------
# EscalationRule
# ---------------------------------------------------------------------------
class EscalationRuleCreate(BaseModel):
    finding_type: str = Field(pattern=r"^(alert|insight|recommendation|anomaly)$")
    min_severity: str = Field(pattern=r"^(low|medium|high|critical)$")
    channel: str = Field(pattern=r"^(email|webhook|in_app)$")
    channel_config_json: str | None = None
    is_active: bool = True


class EscalationRuleUpdate(BaseModel):
    finding_type: str | None = None
    min_severity: str | None = None
    channel: str | None = None
    channel_config_json: str | None = None
    is_active: bool | None = None


class EscalationRuleResponse(BaseModel):
    id: str
    user_id: str
    finding_type: str
    min_severity: str
    channel: str
    channel_config_json: str | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
