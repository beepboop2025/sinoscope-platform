"""Knowledge graph routes — entity/relationship CRUD, graph queries, ownership, interlocks."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.knowledge_graph import (
    BoardInterlock,
    KgEntity,
    KgRelationship,
    OwnershipChain,
)
from app.schemas.knowledge_graph import (
    BoardInterlockResponse,
    EventPropagationResult,
    KgEntityCreate,
    KgEntityResponse,
    KgEntityWithRelationships,
    KgPath,
    KgQueryRequest,
    KgQueryResponse,
    KgRelationshipCreate,
    KgRelationshipResponse,
    OwnershipChainResponse,
)
from app.services.knowledge_graph_engine import KnowledgeGraphEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge-graph", tags=["knowledge-graph"])

_engine = KnowledgeGraphEngine()


# ── Helper: load all entities/relationships and build graph ───────────────────

async def _build_full_graph(session: AsyncSession):
    """Load all entities and relationships from DB and build a networkx graph."""
    ent_rows = (await session.execute(select(KgEntity))).scalars().all()
    rel_rows = (await session.execute(select(KgRelationship))).scalars().all()

    entities = [
        {
            "id": e.id,
            "name": e.name,
            "entity_type": e.entity_type,
            "properties_json": e.properties_json,
        }
        for e in ent_rows
    ]
    relationships = [
        {
            "id": r.id,
            "source_id": r.source_id,
            "target_id": r.target_id,
            "relation_type": r.relation_type,
            "weight": float(r.weight),
            "properties_json": r.properties_json,
        }
        for r in rel_rows
    ]

    graph = _engine.build_graph(entities, relationships)
    return graph, entities, relationships


# ── Entity CRUD ───────────────────────────────────────────────────────────────

@router.post("/entities", response_model=KgEntityResponse, status_code=201)
async def create_entity(
    body: KgEntityCreate,
    session: AsyncSession = Depends(get_db),
):
    """Create a new knowledge graph entity."""
    valid_types = {"company", "person", "sector", "country", "exchange"}
    if body.entity_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"entity_type must be one of {sorted(valid_types)}",
        )

    entity = KgEntity(
        name=body.name,
        entity_type=body.entity_type,
        properties_json=body.properties_json,
    )
    session.add(entity)
    await session.flush()
    await session.refresh(entity)
    return entity


@router.get("/entities", response_model=list[KgEntityResponse])
async def list_entities(
    entity_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_db),
):
    """List knowledge graph entities with optional type filter."""
    stmt = select(KgEntity).order_by(KgEntity.name).limit(limit)
    if entity_type:
        stmt = stmt.where(KgEntity.entity_type == entity_type)
    rows = (await session.execute(stmt)).scalars().all()
    return rows


@router.get("/entities/{entity_id}", response_model=KgEntityWithRelationships)
async def get_entity(entity_id: str, session: AsyncSession = Depends(get_db)):
    """Get entity details including its relationships."""
    result = await session.execute(
        select(KgEntity)
        .where(KgEntity.id == entity_id)
        .options(
            selectinload(KgEntity.outgoing_relationships),
            selectinload(KgEntity.incoming_relationships),
        )
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    outgoing = [
        KgRelationshipResponse.model_validate(r)
        for r in entity.outgoing_relationships
    ]
    incoming = [
        KgRelationshipResponse.model_validate(r)
        for r in entity.incoming_relationships
    ]

    resp = KgEntityWithRelationships.model_validate(entity)
    resp.outgoing = outgoing
    resp.incoming = incoming
    return resp


# ── Relationship CRUD ─────────────────────────────────────────────────────────

@router.post("/relationships", response_model=KgRelationshipResponse, status_code=201)
async def create_relationship(
    body: KgRelationshipCreate,
    session: AsyncSession = Depends(get_db),
):
    """Create a new relationship between two entities."""
    valid_types = {
        "owns", "subsidiary_of", "competes_with", "supplies",
        "board_member", "located_in", "listed_on",
    }
    if body.relation_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"relation_type must be one of {sorted(valid_types)}",
        )

    # Verify both entities exist
    for eid in (body.source_id, body.target_id):
        res = await session.execute(select(KgEntity).where(KgEntity.id == eid))
        if not res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Entity {eid} not found")

    rel = KgRelationship(
        source_id=body.source_id,
        target_id=body.target_id,
        relation_type=body.relation_type,
        weight=body.weight,
        properties_json=body.properties_json,
    )
    session.add(rel)
    await session.flush()
    await session.refresh(rel)
    return rel


@router.get("/relationships", response_model=list[KgRelationshipResponse])
async def list_relationships(
    relation_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_db),
):
    """List relationships with optional type filter."""
    stmt = select(KgRelationship).order_by(KgRelationship.created_at.desc()).limit(limit)
    if relation_type:
        stmt = stmt.where(KgRelationship.relation_type == relation_type)
    rows = (await session.execute(stmt)).scalars().all()
    return rows


# ── Natural Language Query ────────────────────────────────────────────────────

@router.post("/query", response_model=KgQueryResponse)
async def query_graph(
    body: KgQueryRequest,
    session: AsyncSession = Depends(get_db),
):
    """Natural language graph query — keyword-based matching."""
    _, entities, relationships = await _build_full_graph(session)

    result = _engine.query_natural_language(body.query, entities, relationships)

    return KgQueryResponse(
        entities=[KgEntityResponse(**e) for e in result["entities"]],
        relationships=[KgRelationshipResponse(**r) for r in result["relationships"]],
        paths=[KgPath(**p) for p in result["paths"]],
    )


# ── Ownership Chain ───────────────────────────────────────────────────────────

@router.get("/ownership/{entity_id}")
async def get_ownership_chain(
    entity_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Compute ownership chain for an entity via owns/subsidiary_of edges."""
    # Verify entity exists
    res = await session.execute(select(KgEntity).where(KgEntity.id == entity_id))
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Entity not found")

    graph, _, _ = await _build_full_graph(session)
    chains = _engine.find_ownership_chain(graph, entity_id)

    return {
        "entity_id": entity_id,
        "chains": chains,
        "max_depth": max((len(c) for c in chains), default=0),
    }


# ── Board Interlocks ──────────────────────────────────────────────────────────

@router.get("/interlocks", response_model=list[dict])
async def get_board_interlocks(
    session: AsyncSession = Depends(get_db),
):
    """Find people sitting on multiple company boards."""
    graph, _, _ = await _build_full_graph(session)
    interlocks = _engine.find_board_interlocks(graph)
    return interlocks


# ── Supply Chain ──────────────────────────────────────────────────────────────

@router.get("/supply-chain/{entity_id}")
async def get_supply_chain(
    entity_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Map upstream and downstream supply chain for an entity."""
    # Verify entity exists
    res = await session.execute(select(KgEntity).where(KgEntity.id == entity_id))
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Entity not found")

    graph, _, _ = await _build_full_graph(session)
    chain = _engine.find_supply_chain(graph, entity_id)

    upstream = [c for c in chain if c["direction"] == "upstream"]
    downstream = [c for c in chain if c["direction"] == "downstream"]

    return {
        "entity_id": entity_id,
        "upstream": upstream,
        "downstream": downstream,
        "total": len(chain),
    }
