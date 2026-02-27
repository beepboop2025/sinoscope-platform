"""Routes for data warehouse — overview, ETL health, quality, lineage."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import AuthUser, require_auth
from app.schemas.warehouse import (
    DataLineageResponse,
    DataQualityScoreResponse,
    EtlHealthResponse,
    WarehouseOverview,
)
from app.services.warehouse_engine import WarehouseEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/warehouse", tags=["warehouse"])


@router.get("/overview", response_model=WarehouseOverview)
async def get_overview(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    return await WarehouseEngine.get_overview(session)


@router.get("/etl-health", response_model=list[EtlHealthResponse])
async def get_etl_health(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    return await WarehouseEngine.check_etl_health(session)


@router.get("/quality-scores", response_model=list[DataQualityScoreResponse])
async def get_quality_scores(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    return await WarehouseEngine.get_quality_scores(session)


@router.get("/lineage/{table_name}/{record_id}", response_model=list[DataLineageResponse])
async def get_lineage(
    table_name: str,
    record_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    return await WarehouseEngine.get_lineage(session, table_name, record_id)


@router.post("/quality-check/{table_name}", response_model=DataQualityScoreResponse, status_code=201)
async def trigger_quality_check(
    table_name: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    return await WarehouseEngine.run_quality_check(session, table_name)
