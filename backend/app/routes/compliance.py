"""Compliance API routes — audit logs, retention, access, export limits, usage metering."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import AuthUser, require_auth
from app.models.compliance import (
    AccessPolicy,
    ApiUsageMeter,
    ComplianceAuditLog,
    DataRetentionPolicy,
    ExportRateLimit,
)
from app.schemas.compliance import (
    AccessPolicyCreate,
    AccessPolicyResponse,
    AccessPolicyUpdate,
    ApiUsageMeterResponse,
    AuditChainVerification,
    ComplianceAuditLogResponse,
    DataRetentionPolicyCreate,
    DataRetentionPolicyResponse,
    DataRetentionPolicyUpdate,
    ExportRateLimitResponse,
)
from app.services.compliance_engine import ComplianceEngine

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Audit Logs
# ---------------------------------------------------------------------------
@router.get("/audit-logs", response_model=list[ComplianceAuditLogResponse])
async def list_audit_logs(
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    user_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """List compliance audit logs with optional filters and pagination."""
    query = (
        select(ComplianceAuditLog)
        .order_by(ComplianceAuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if action:
        query = query.where(ComplianceAuditLog.action == action)
    if resource_type:
        query = query.where(ComplianceAuditLog.resource_type == resource_type)
    if user_id:
        query = query.where(ComplianceAuditLog.user_id == user_id)

    result = await session.execute(query)
    return list(result.scalars().all())


@router.get("/audit-chain/verify", response_model=AuditChainVerification)
async def verify_audit_chain(
    limit: int = Query(1000, ge=1, le=100000),
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Verify the integrity of the audit hash chain."""
    verification = await ComplianceEngine.verify_audit_chain(session, limit)
    return AuditChainVerification(**verification)


# ---------------------------------------------------------------------------
# Data Retention Policies
# ---------------------------------------------------------------------------
@router.get("/retention-policies", response_model=list[DataRetentionPolicyResponse])
async def list_retention_policies(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """List all data retention policies."""
    result = await session.execute(
        select(DataRetentionPolicy).order_by(DataRetentionPolicy.resource_type)
    )
    return list(result.scalars().all())


@router.post("/retention-policies", response_model=DataRetentionPolicyResponse, status_code=201)
async def create_retention_policy(
    body: DataRetentionPolicyCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Create a data retention policy."""
    # Check for duplicate resource_type
    existing = await session.execute(
        select(DataRetentionPolicy).where(DataRetentionPolicy.resource_type == body.resource_type)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Retention policy for this resource type already exists")

    policy = DataRetentionPolicy(
        resource_type=body.resource_type,
        retention_days=body.retention_days,
        auto_delete=body.auto_delete,
        description=body.description,
    )
    session.add(policy)
    await session.flush()
    return policy


@router.get("/retention-policies/{policy_id}", response_model=DataRetentionPolicyResponse)
async def get_retention_policy(
    policy_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Get a data retention policy by ID."""
    result = await session.execute(
        select(DataRetentionPolicy).where(DataRetentionPolicy.id == policy_id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Retention policy not found")
    return policy


@router.put("/retention-policies/{policy_id}", response_model=DataRetentionPolicyResponse)
async def update_retention_policy(
    policy_id: str,
    body: DataRetentionPolicyUpdate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Update a data retention policy."""
    result = await session.execute(
        select(DataRetentionPolicy).where(DataRetentionPolicy.id == policy_id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Retention policy not found")

    if body.retention_days is not None:
        policy.retention_days = body.retention_days
    if body.auto_delete is not None:
        policy.auto_delete = body.auto_delete
    if body.description is not None:
        policy.description = body.description

    await session.flush()
    return policy


@router.delete("/retention-policies/{policy_id}", status_code=204)
async def delete_retention_policy(
    policy_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Delete a data retention policy."""
    result = await session.execute(
        select(DataRetentionPolicy).where(DataRetentionPolicy.id == policy_id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Retention policy not found")
    await session.delete(policy)


# ---------------------------------------------------------------------------
# Access Policies
# ---------------------------------------------------------------------------
@router.get("/access-policies", response_model=list[AccessPolicyResponse])
async def list_access_policies(
    resource_type: str | None = Query(None),
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """List access policies, optionally filtered by resource type."""
    query = select(AccessPolicy).order_by(AccessPolicy.name)
    if resource_type:
        query = query.where(AccessPolicy.resource_type == resource_type)

    result = await session.execute(query)
    return list(result.scalars().all())


@router.post("/access-policies", response_model=AccessPolicyResponse, status_code=201)
async def create_access_policy(
    body: AccessPolicyCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Create an access policy."""
    existing = await session.execute(
        select(AccessPolicy).where(AccessPolicy.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Access policy with this name already exists")

    policy = AccessPolicy(
        name=body.name,
        resource_type=body.resource_type,
        conditions=json.dumps(body.conditions),
        allowed_roles=",".join(body.allowed_roles),
        is_active=body.is_active,
    )
    session.add(policy)
    await session.flush()
    return policy


@router.get("/access-policies/{policy_id}", response_model=AccessPolicyResponse)
async def get_access_policy(
    policy_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Get an access policy by ID."""
    result = await session.execute(
        select(AccessPolicy).where(AccessPolicy.id == policy_id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Access policy not found")
    return policy


@router.put("/access-policies/{policy_id}", response_model=AccessPolicyResponse)
async def update_access_policy(
    policy_id: str,
    body: AccessPolicyUpdate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Update an access policy."""
    result = await session.execute(
        select(AccessPolicy).where(AccessPolicy.id == policy_id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Access policy not found")

    if body.name is not None:
        policy.name = body.name
    if body.conditions is not None:
        policy.conditions = json.dumps(body.conditions)
    if body.allowed_roles is not None:
        policy.allowed_roles = ",".join(body.allowed_roles)
    if body.is_active is not None:
        policy.is_active = body.is_active

    await session.flush()
    return policy


@router.delete("/access-policies/{policy_id}", status_code=204)
async def delete_access_policy(
    policy_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Delete an access policy."""
    result = await session.execute(
        select(AccessPolicy).where(AccessPolicy.id == policy_id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Access policy not found")
    await session.delete(policy)


# ---------------------------------------------------------------------------
# Export Rate Limits
# ---------------------------------------------------------------------------
@router.get("/export-limits/{user_id}", response_model=list[ExportRateLimitResponse])
async def get_export_limits(
    user_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Get export rate limits for a user."""
    result = await session.execute(
        select(ExportRateLimit).where(ExportRateLimit.user_id == user_id)
    )
    limits = list(result.scalars().all())

    # Compute remaining for each limit
    response = []
    for limit in limits:
        data = ExportRateLimitResponse(
            id=limit.id,
            user_id=limit.user_id,
            export_type=limit.export_type,
            max_per_day=limit.max_per_day,
            current_count=limit.current_count,
            remaining=max(limit.max_per_day - limit.current_count, 0),
            last_reset=limit.last_reset,
            created_at=limit.created_at,
        )
        response.append(data)

    return response


# ---------------------------------------------------------------------------
# API Usage
# ---------------------------------------------------------------------------
@router.get("/api-usage/{user_id}", response_model=list[ApiUsageMeterResponse])
async def get_api_usage(
    user_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Get API usage metrics for a user."""
    result = await session.execute(
        select(ApiUsageMeter)
        .where(ApiUsageMeter.user_id == user_id)
        .order_by(ApiUsageMeter.period_start.desc())
        .limit(100)
    )
    return list(result.scalars().all())
