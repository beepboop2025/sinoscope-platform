"""Pydantic schemas for the knowledge graph system."""

from datetime import datetime

from pydantic import BaseModel, Field


# ── Entity CRUD ───────────────────────────────────────────────────────────────

class KgEntityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    entity_type: str = Field(
        description="Entity type: company, person, sector, country, exchange"
    )
    properties_json: str | None = None


class KgEntityUpdate(BaseModel):
    name: str | None = None
    entity_type: str | None = None
    properties_json: str | None = None


class KgEntityResponse(BaseModel):
    id: str
    name: str
    entity_type: str
    properties_json: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KgEntityWithRelationships(KgEntityResponse):
    outgoing: list["KgRelationshipResponse"] = []
    incoming: list["KgRelationshipResponse"] = []


# ── Relationship CRUD ─────────────────────────────────────────────────────────

class KgRelationshipCreate(BaseModel):
    source_id: str
    target_id: str
    relation_type: str = Field(
        description="Relation type: owns, subsidiary_of, competes_with, supplies, board_member, located_in, listed_on"
    )
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    properties_json: str | None = None


class KgRelationshipResponse(BaseModel):
    id: str
    source_id: str
    target_id: str
    relation_type: str
    weight: float
    properties_json: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Query ─────────────────────────────────────────────────────────────────────

class KgQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    max_depth: int = Field(default=3, ge=1, le=10)


class KgPath(BaseModel):
    entities: list[str]  # ordered list of entity IDs forming a path
    relationships: list[str]  # ordered list of relationship IDs along the path


class KgQueryResponse(BaseModel):
    entities: list[KgEntityResponse]
    relationships: list[KgRelationshipResponse]
    paths: list[KgPath]


# ── Ownership Chain ───────────────────────────────────────────────────────────

class OwnershipChainResponse(BaseModel):
    id: str
    root_entity_id: str
    chain_data_json: str
    depth: int
    computed_at: datetime

    model_config = {"from_attributes": True}


# ── Board Interlock ───────────────────────────────────────────────────────────

class BoardInterlockResponse(BaseModel):
    id: str
    person_id: str
    company_ids_json: str
    interlock_score: float
    computed_at: datetime

    model_config = {"from_attributes": True}


# ── Event Propagation ─────────────────────────────────────────────────────────

class EventPropagationResult(BaseModel):
    entity_id: str
    entity_name: str
    impact: float
    depth: int
