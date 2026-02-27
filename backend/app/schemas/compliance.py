"""Pydantic v2 schemas for compliance system."""

from datetime import date, datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Compliance Audit Log
# ---------------------------------------------------------------------------
class ComplianceAuditLogResponse(BaseModel):
    id: str
    user_id: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    details: str | None = None
    ip_address: str | None = None
    entry_hash: str
    prev_hash: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ComplianceAuditLogCreate(BaseModel):
    action: str = Field(min_length=1, max_length=100)
    resource_type: str = Field(min_length=1, max_length=100)
    resource_id: str | None = None
    details: str | None = None


class AuditChainVerification(BaseModel):
    is_valid: bool
    entries_checked: int
    first_broken_at: str | None = None  # ISO timestamp of first broken link


# ---------------------------------------------------------------------------
# Data Retention Policy
# ---------------------------------------------------------------------------
class DataRetentionPolicyResponse(BaseModel):
    id: str
    resource_type: str
    retention_days: int
    auto_delete: bool
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DataRetentionPolicyCreate(BaseModel):
    resource_type: str = Field(min_length=1, max_length=100)
    retention_days: int = Field(ge=1, le=36500)
    auto_delete: bool = False
    description: str | None = None


class DataRetentionPolicyUpdate(BaseModel):
    retention_days: int | None = Field(default=None, ge=1, le=36500)
    auto_delete: bool | None = None
    description: str | None = None


# ---------------------------------------------------------------------------
# Access Policy
# ---------------------------------------------------------------------------
class AccessPolicyResponse(BaseModel):
    id: str
    name: str
    resource_type: str
    conditions: str  # JSON string
    allowed_roles: str  # comma-separated
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccessPolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    resource_type: str = Field(min_length=1, max_length=100)
    conditions: dict = Field(default_factory=dict)
    allowed_roles: list[str] = Field(min_length=1)
    is_active: bool = True


class AccessPolicyUpdate(BaseModel):
    name: str | None = None
    conditions: dict | None = None
    allowed_roles: list[str] | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Export Rate Limit
# ---------------------------------------------------------------------------
class ExportRateLimitResponse(BaseModel):
    id: str
    user_id: str
    export_type: str
    max_per_day: int
    current_count: int
    remaining: int = 0  # computed field
    last_reset: date
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# API Usage Meter
# ---------------------------------------------------------------------------
class ApiUsageMeterResponse(BaseModel):
    id: str
    user_id: str
    endpoint: str
    method: str
    count: int
    period_start: datetime
    period_end: datetime

    model_config = {"from_attributes": True}
