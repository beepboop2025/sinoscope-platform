"""Knowledge graph models — entities, relationships, ownership chains, interlocks."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KgEntity(Base):
    """Node in the knowledge graph — company, person, sector, country, or exchange."""

    __tablename__ = "kg_entities"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), index=True)
    entity_type: Mapped[str] = mapped_column(
        String(20), index=True
    )  # "company", "person", "sector", "country", "exchange"
    properties_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON object with arbitrary properties
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    outgoing_relationships: Mapped[list["KgRelationship"]] = relationship(
        "KgRelationship",
        foreign_keys="KgRelationship.source_id",
        back_populates="source_entity",
        cascade="all, delete-orphan",
    )
    incoming_relationships: Mapped[list["KgRelationship"]] = relationship(
        "KgRelationship",
        foreign_keys="KgRelationship.target_id",
        back_populates="target_entity",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_kg_entities_name_type", "name", "entity_type"),
    )


class KgRelationship(Base):
    """Edge in the knowledge graph — directional relationship between two entities."""

    __tablename__ = "kg_relationships"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("kg_entities.id", ondelete="CASCADE"), index=True
    )
    target_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("kg_entities.id", ondelete="CASCADE"), index=True
    )
    relation_type: Mapped[str] = mapped_column(
        String(30), index=True
    )  # "owns", "subsidiary_of", "competes_with", "supplies", "board_member", "located_in", "listed_on"
    weight: Mapped[float] = mapped_column(Numeric(5, 4), default=1.0)
    properties_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    source_entity: Mapped["KgEntity"] = relationship(
        "KgEntity", foreign_keys=[source_id], back_populates="outgoing_relationships"
    )
    target_entity: Mapped["KgEntity"] = relationship(
        "KgEntity", foreign_keys=[target_id], back_populates="incoming_relationships"
    )

    __table_args__ = (
        Index("ix_kg_rel_source_target", "source_id", "target_id"),
        Index("ix_kg_rel_type", "relation_type"),
    )


class OwnershipChain(Base):
    """Precomputed ownership chain from a root entity through owns/subsidiary_of edges."""

    __tablename__ = "ownership_chains"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    root_entity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("kg_entities.id", ondelete="CASCADE"), index=True
    )
    chain_data_json: Mapped[str] = mapped_column(Text)  # JSON array of entity IDs
    depth: Mapped[int] = mapped_column(Integer)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BoardInterlock(Base):
    """Precomputed board interlock — a person sitting on multiple company boards."""

    __tablename__ = "board_interlocks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    person_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("kg_entities.id", ondelete="CASCADE"), index=True
    )
    company_ids_json: Mapped[str] = mapped_column(Text)  # JSON array of company entity IDs
    interlock_score: Mapped[float] = mapped_column(Numeric(5, 4))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
