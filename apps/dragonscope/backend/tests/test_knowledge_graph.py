"""Tests for the knowledge graph — engine unit tests and API integration tests."""

import json

import pytest

from app.services.knowledge_graph_engine import KnowledgeGraphEngine


# ── Unit tests — KnowledgeGraphEngine ─────────────────────────────────────────

@pytest.fixture
def engine():
    return KnowledgeGraphEngine()


@pytest.fixture
def sample_entities():
    return [
        {"id": "e1", "name": "Alphabet", "entity_type": "company", "properties_json": None},
        {"id": "e2", "name": "Google", "entity_type": "company", "properties_json": None},
        {"id": "e3", "name": "YouTube", "entity_type": "company", "properties_json": None},
        {"id": "e4", "name": "Sundar Pichai", "entity_type": "person", "properties_json": None},
        {"id": "e5", "name": "Technology", "entity_type": "sector", "properties_json": None},
        {"id": "e6", "name": "Apple", "entity_type": "company", "properties_json": None},
        {"id": "e7", "name": "Tim Cook", "entity_type": "person", "properties_json": None},
        {"id": "e8", "name": "TSMC", "entity_type": "company", "properties_json": None},
    ]


@pytest.fixture
def sample_relationships():
    return [
        {"id": "r1", "source_id": "e1", "target_id": "e2", "relation_type": "owns", "weight": 1.0, "properties_json": None},
        {"id": "r2", "source_id": "e1", "target_id": "e3", "relation_type": "owns", "weight": 1.0, "properties_json": None},
        {"id": "r3", "source_id": "e4", "target_id": "e1", "relation_type": "board_member", "weight": 1.0, "properties_json": None},
        {"id": "r4", "source_id": "e4", "target_id": "e6", "relation_type": "board_member", "weight": 0.5, "properties_json": None},
        {"id": "r5", "source_id": "e1", "target_id": "e5", "relation_type": "located_in", "weight": 1.0, "properties_json": None},
        {"id": "r6", "source_id": "e6", "target_id": "e5", "relation_type": "located_in", "weight": 1.0, "properties_json": None},
        {"id": "r7", "source_id": "e1", "target_id": "e6", "relation_type": "competes_with", "weight": 0.8, "properties_json": None},
        {"id": "r8", "source_id": "e8", "target_id": "e6", "relation_type": "supplies", "weight": 0.9, "properties_json": None},
        {"id": "r9", "source_id": "e7", "target_id": "e6", "relation_type": "board_member", "weight": 1.0, "properties_json": None},
    ]


class TestGraphBuilding:
    def test_build_graph(self, engine, sample_entities, sample_relationships):
        graph = engine.build_graph(sample_entities, sample_relationships)
        assert graph.number_of_nodes() == len(sample_entities)
        assert graph.number_of_edges() == len(sample_relationships)

    def test_build_empty_graph(self, engine):
        graph = engine.build_graph([], [])
        assert graph.number_of_nodes() == 0
        assert graph.number_of_edges() == 0

    def test_node_attributes(self, engine, sample_entities, sample_relationships):
        graph = engine.build_graph(sample_entities, sample_relationships)
        assert graph.nodes["e1"]["name"] == "Alphabet"
        assert graph.nodes["e1"]["entity_type"] == "company"

    def test_edge_attributes(self, engine, sample_entities, sample_relationships):
        graph = engine.build_graph(sample_entities, sample_relationships)
        edge = graph.edges["e1", "e2"]
        assert edge["relation_type"] == "owns"
        assert edge["weight"] == 1.0


class TestBfsNeighborFinding:
    def test_find_neighbors_depth_1(self, engine, sample_entities, sample_relationships):
        graph = engine.build_graph(sample_entities, sample_relationships)
        neighbors = engine.find_neighbors(graph, "e1", max_depth=1)
        neighbor_ids = {n["id"] for n in neighbors}
        # Direct neighbors of Alphabet: Google (owns), YouTube (owns),
        # Sundar (board_member incoming), Technology (located_in), Apple (competes_with)
        assert "e2" in neighbor_ids  # Google
        assert "e3" in neighbor_ids  # YouTube

    def test_find_neighbors_depth_2(self, engine, sample_entities, sample_relationships):
        graph = engine.build_graph(sample_entities, sample_relationships)
        neighbors = engine.find_neighbors(graph, "e1", max_depth=2)
        neighbor_ids = {n["id"] for n in neighbors}
        # Should reach TSMC (supplies Apple, depth 2 from Alphabet via Apple)
        assert "e8" in neighbor_ids

    def test_find_neighbors_nonexistent(self, engine, sample_entities, sample_relationships):
        graph = engine.build_graph(sample_entities, sample_relationships)
        neighbors = engine.find_neighbors(graph, "nonexistent")
        assert neighbors == []

    def test_depth_field(self, engine, sample_entities, sample_relationships):
        graph = engine.build_graph(sample_entities, sample_relationships)
        neighbors = engine.find_neighbors(graph, "e1", max_depth=2)
        for n in neighbors:
            assert 1 <= n["depth"] <= 2


class TestOwnershipChain:
    def test_ownership_chain(self, engine, sample_entities, sample_relationships):
        graph = engine.build_graph(sample_entities, sample_relationships)
        chains = engine.find_ownership_chain(graph, "e1")
        # Alphabet owns Google and YouTube
        assert len(chains) >= 1
        # Each chain starts with e1
        for chain in chains:
            assert chain[0] == "e1"

    def test_ownership_chain_leaf_node(self, engine, sample_entities, sample_relationships):
        graph = engine.build_graph(sample_entities, sample_relationships)
        chains = engine.find_ownership_chain(graph, "e2")  # Google — no owns edges out
        assert chains == []

    def test_ownership_chain_nonexistent(self, engine, sample_entities, sample_relationships):
        graph = engine.build_graph(sample_entities, sample_relationships)
        chains = engine.find_ownership_chain(graph, "nonexistent")
        assert chains == []


class TestBoardInterlocks:
    def test_find_interlocks(self, engine, sample_entities, sample_relationships):
        graph = engine.build_graph(sample_entities, sample_relationships)
        interlocks = engine.find_board_interlocks(graph)
        # Sundar Pichai is board_member of both Alphabet (e1) and Apple (e6)
        assert len(interlocks) >= 1
        sundar = [i for i in interlocks if i["person_id"] == "e4"]
        assert len(sundar) == 1
        assert "e1" in sundar[0]["company_ids"]
        assert "e6" in sundar[0]["company_ids"]

    def test_no_interlocks_with_filter(self, engine, sample_entities, sample_relationships):
        graph = engine.build_graph(sample_entities, sample_relationships)
        # Filter to only TSMC — no board members
        interlocks = engine.find_board_interlocks(graph, company_ids=["e8"])
        assert interlocks == []


class TestSupplyChain:
    def test_supply_chain(self, engine, sample_entities, sample_relationships):
        graph = engine.build_graph(sample_entities, sample_relationships)
        chain = engine.find_supply_chain(graph, "e6")  # Apple
        upstream = [c for c in chain if c["direction"] == "upstream"]
        downstream = [c for c in chain if c["direction"] == "downstream"]
        # TSMC supplies Apple (upstream)
        assert any(c["id"] == "e8" for c in upstream)

    def test_supply_chain_nonexistent(self, engine, sample_entities, sample_relationships):
        graph = engine.build_graph(sample_entities, sample_relationships)
        chain = engine.find_supply_chain(graph, "nonexistent")
        assert chain == []


class TestEventPropagation:
    def test_propagate_event(self, engine, sample_entities, sample_relationships):
        graph = engine.build_graph(sample_entities, sample_relationships)
        results = engine.propagate_event(graph, "e1", event_impact=1.0, decay=0.7)
        # Impact should propagate to neighbors
        assert len(results) > 0
        # All impacts should be less than the initial 1.0
        for r in results:
            assert abs(r["impact"]) < 1.0

    def test_propagate_event_decay(self, engine, sample_entities, sample_relationships):
        graph = engine.build_graph(sample_entities, sample_relationships)
        results = engine.propagate_event(graph, "e1", event_impact=1.0, decay=0.5)
        depth_1 = [r for r in results if r["depth"] == 1]
        depth_2 = [r for r in results if r["depth"] == 2]
        # Depth-2 impacts should be smaller than depth-1 on average
        if depth_1 and depth_2:
            avg_d1 = sum(abs(r["impact"]) for r in depth_1) / len(depth_1)
            avg_d2 = sum(abs(r["impact"]) for r in depth_2) / len(depth_2)
            assert avg_d2 <= avg_d1

    def test_propagate_event_nonexistent(self, engine, sample_entities, sample_relationships):
        graph = engine.build_graph(sample_entities, sample_relationships)
        results = engine.propagate_event(graph, "nonexistent", event_impact=1.0)
        assert results == []


class TestNaturalLanguageQuery:
    def test_query_by_name(self, engine, sample_entities, sample_relationships):
        result = engine.query_natural_language("Alphabet", sample_entities, sample_relationships)
        entity_names = [e["name"] for e in result["entities"]]
        assert "Alphabet" in entity_names

    def test_query_by_type(self, engine, sample_entities, sample_relationships):
        result = engine.query_natural_language("all companies", sample_entities, sample_relationships)
        for e in result["entities"]:
            if e["entity_type"] == "company":
                break
        else:
            pytest.fail("No company entities found")

    def test_query_by_relation(self, engine, sample_entities, sample_relationships):
        result = engine.query_natural_language("ownership", sample_entities, sample_relationships)
        rel_types = [r["relation_type"] for r in result["relationships"]]
        assert "owns" in rel_types


# ── Integration tests — API endpoints ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_entity(client):
    resp = await client.post(
        "/api/knowledge-graph/entities",
        json={"name": "TestCorp", "entity_type": "company"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "TestCorp"
    assert data["entity_type"] == "company"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_entity_invalid_type(client):
    resp = await client.post(
        "/api/knowledge-graph/entities",
        json={"name": "Test", "entity_type": "invalid"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_entities_empty(client):
    resp = await client.get("/api/knowledge-graph/entities")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_entity_not_found(client):
    resp = await client.get("/api/knowledge-graph/entities/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_and_get_entity(client):
    create = await client.post(
        "/api/knowledge-graph/entities",
        json={"name": "GetCorp", "entity_type": "company"},
    )
    eid = create.json()["id"]

    resp = await client.get(f"/api/knowledge-graph/entities/{eid}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "GetCorp"


@pytest.mark.asyncio
async def test_create_relationship(client):
    e1 = await client.post(
        "/api/knowledge-graph/entities",
        json={"name": "ParentCo", "entity_type": "company"},
    )
    e2 = await client.post(
        "/api/knowledge-graph/entities",
        json={"name": "ChildCo", "entity_type": "company"},
    )

    resp = await client.post(
        "/api/knowledge-graph/relationships",
        json={
            "source_id": e1.json()["id"],
            "target_id": e2.json()["id"],
            "relation_type": "owns",
            "weight": 0.9,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["relation_type"] == "owns"


@pytest.mark.asyncio
async def test_create_relationship_invalid_type(client):
    e1 = await client.post(
        "/api/knowledge-graph/entities",
        json={"name": "A", "entity_type": "company"},
    )
    e2 = await client.post(
        "/api/knowledge-graph/entities",
        json={"name": "B", "entity_type": "company"},
    )

    resp = await client.post(
        "/api/knowledge-graph/relationships",
        json={
            "source_id": e1.json()["id"],
            "target_id": e2.json()["id"],
            "relation_type": "invalid_type",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_relationships_empty(client):
    resp = await client.get("/api/knowledge-graph/relationships")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_query_endpoint(client):
    await client.post(
        "/api/knowledge-graph/entities",
        json={"name": "QueryCorp", "entity_type": "company"},
    )

    resp = await client.post(
        "/api/knowledge-graph/query",
        json={"query": "QueryCorp", "max_depth": 2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "entities" in data
    assert "relationships" in data
    assert "paths" in data


@pytest.mark.asyncio
async def test_ownership_not_found(client):
    resp = await client.get("/api/knowledge-graph/ownership/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_interlocks_empty(client):
    resp = await client.get("/api/knowledge-graph/interlocks")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_supply_chain_not_found(client):
    resp = await client.get("/api/knowledge-graph/supply-chain/nonexistent-id")
    assert resp.status_code == 404
