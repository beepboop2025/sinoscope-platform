"""Knowledge graph engine built on networkx.

Provides graph construction, BFS neighbor finding, DFS ownership chains,
board interlock detection, supply chain traversal, and event propagation.
"""

import json
import logging
from collections import deque

import networkx as nx

logger = logging.getLogger(__name__)


class KnowledgeGraphEngine:
    """In-memory graph engine backed by networkx DiGraph."""

    def build_graph(
        self,
        entities: list[dict],
        relationships: list[dict],
    ) -> nx.DiGraph:
        """Build a directed graph from entity and relationship dicts.

        Args:
            entities: list of dicts with at least ``id``, ``name``, ``entity_type``.
            relationships: list of dicts with ``id``, ``source_id``, ``target_id``,
                           ``relation_type``, ``weight``.
        """
        g = nx.DiGraph()

        for ent in entities:
            g.add_node(
                ent["id"],
                name=ent.get("name", ""),
                entity_type=ent.get("entity_type", ""),
                properties=ent.get("properties_json"),
            )

        for rel in relationships:
            source = rel["source_id"]
            target = rel["target_id"]
            if source in g and target in g:
                g.add_edge(
                    source,
                    target,
                    id=rel["id"],
                    relation_type=rel.get("relation_type", ""),
                    weight=float(rel.get("weight", 1.0)),
                    properties=rel.get("properties_json"),
                )

        logger.debug(
            "Built graph with %d nodes and %d edges",
            g.number_of_nodes(),
            g.number_of_edges(),
        )
        return g

    def find_neighbors(
        self,
        graph: nx.DiGraph,
        entity_id: str,
        max_depth: int = 2,
    ) -> list[dict]:
        """BFS traversal up to *max_depth* hops, returning discovered nodes.

        Returns a list of dicts with ``id``, ``name``, ``entity_type``, ``depth``.
        """
        if entity_id not in graph:
            return []

        visited: set[str] = {entity_id}
        queue: deque[tuple[str, int]] = deque([(entity_id, 0)])
        result: list[dict] = []

        while queue:
            node, depth = queue.popleft()
            if depth > 0:
                data = graph.nodes[node]
                result.append({
                    "id": node,
                    "name": data.get("name", ""),
                    "entity_type": data.get("entity_type", ""),
                    "depth": depth,
                })
            if depth < max_depth:
                # Outgoing neighbors
                for neighbor in graph.successors(node):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, depth + 1))
                # Incoming neighbors (treat graph as undirected for discovery)
                for neighbor in graph.predecessors(node):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, depth + 1))

        return result

    def find_ownership_chain(
        self,
        graph: nx.DiGraph,
        entity_id: str,
    ) -> list[list[str]]:
        """DFS through ``owns`` / ``subsidiary_of`` edges starting from *entity_id*.

        Returns all chains (lists of entity IDs) reachable via ownership edges.
        """
        ownership_types = {"owns", "subsidiary_of"}

        if entity_id not in graph:
            return []

        chains: list[list[str]] = []
        stack: list[tuple[str, list[str]]] = [(entity_id, [entity_id])]

        while stack:
            node, path = stack.pop()
            extended = False

            for neighbor in graph.successors(node):
                edge_data = graph.edges[node, neighbor]
                if edge_data.get("relation_type") in ownership_types:
                    if neighbor not in path:  # avoid cycles
                        extended = True
                        stack.append((neighbor, path + [neighbor]))

            if not extended and len(path) > 1:
                chains.append(path)

        return chains

    def find_board_interlocks(
        self,
        graph: nx.DiGraph,
        company_ids: list[str] | None = None,
    ) -> list[dict]:
        """Find people who sit on multiple company boards.

        If *company_ids* is provided, only look at those companies;
        otherwise scan all ``board_member`` edges.

        Returns list of dicts: ``person_id``, ``person_name``, ``company_ids``,
        ``interlock_score``.
        """
        # Map person -> set of companies via board_member edges
        person_companies: dict[str, set[str]] = {}

        for u, v, data in graph.edges(data=True):
            if data.get("relation_type") != "board_member":
                continue
            # u is person, v is company (or vice versa — check entity_type)
            u_type = graph.nodes[u].get("entity_type", "")
            v_type = graph.nodes[v].get("entity_type", "")

            person_id: str | None = None
            company_id: str | None = None

            if u_type == "person" and v_type == "company":
                person_id, company_id = u, v
            elif v_type == "person" and u_type == "company":
                person_id, company_id = v, u
            else:
                continue

            if company_ids and company_id not in company_ids:
                continue

            person_companies.setdefault(person_id, set()).add(company_id)

        # Filter to people on 2+ boards
        interlocks: list[dict] = []
        for pid, companies in person_companies.items():
            if len(companies) >= 2:
                data = graph.nodes.get(pid, {})
                interlocks.append({
                    "person_id": pid,
                    "person_name": data.get("name", ""),
                    "company_ids": sorted(companies),
                    "interlock_score": round(len(companies) / max(len(company_ids or companies), 1), 4),
                })

        interlocks.sort(key=lambda x: x["interlock_score"], reverse=True)
        return interlocks

    def find_supply_chain(
        self,
        graph: nx.DiGraph,
        entity_id: str,
    ) -> list[dict]:
        """Follow ``supplies`` edges from *entity_id* to map the supply chain.

        Returns list of dicts: ``id``, ``name``, ``entity_type``, ``direction``
        (``upstream`` or ``downstream``), ``depth``.
        """
        if entity_id not in graph:
            return []

        result: list[dict] = []

        # Downstream: entity_id supplies -> X
        visited_down: set[str] = {entity_id}
        queue: deque[tuple[str, int]] = deque([(entity_id, 0)])
        while queue:
            node, depth = queue.popleft()
            for neighbor in graph.successors(node):
                edge = graph.edges[node, neighbor]
                if edge.get("relation_type") == "supplies" and neighbor not in visited_down:
                    visited_down.add(neighbor)
                    data = graph.nodes[neighbor]
                    result.append({
                        "id": neighbor,
                        "name": data.get("name", ""),
                        "entity_type": data.get("entity_type", ""),
                        "direction": "downstream",
                        "depth": depth + 1,
                    })
                    queue.append((neighbor, depth + 1))

        # Upstream: X supplies -> entity_id
        visited_up: set[str] = {entity_id}
        queue = deque([(entity_id, 0)])
        while queue:
            node, depth = queue.popleft()
            for neighbor in graph.predecessors(node):
                edge = graph.edges[neighbor, node]
                if edge.get("relation_type") == "supplies" and neighbor not in visited_up:
                    visited_up.add(neighbor)
                    data = graph.nodes[neighbor]
                    result.append({
                        "id": neighbor,
                        "name": data.get("name", ""),
                        "entity_type": data.get("entity_type", ""),
                        "direction": "upstream",
                        "depth": depth + 1,
                    })
                    queue.append((neighbor, depth + 1))

        return result

    def propagate_event(
        self,
        graph: nx.DiGraph,
        entity_id: str,
        event_impact: float,
        decay: float = 0.7,
    ) -> list[dict]:
        """Propagate an event from *entity_id* through the graph with a decay
        factor applied at each hop.

        Returns list of dicts: ``entity_id``, ``entity_name``, ``impact``, ``depth``.
        """
        if entity_id not in graph:
            return []

        results: list[dict] = []
        visited: set[str] = {entity_id}
        queue: deque[tuple[str, float, int]] = deque([(entity_id, event_impact, 0)])

        while queue:
            node, impact, depth = queue.popleft()

            if depth > 0:
                data = graph.nodes[node]
                results.append({
                    "entity_id": node,
                    "entity_name": data.get("name", ""),
                    "impact": round(impact, 4),
                    "depth": depth,
                })

            # Stop propagation when impact becomes negligible
            next_impact = impact * decay
            if abs(next_impact) < 0.01:
                continue

            for neighbor in graph.successors(node):
                if neighbor not in visited:
                    visited.add(neighbor)
                    edge_weight = float(graph.edges[node, neighbor].get("weight", 1.0))
                    queue.append((neighbor, next_impact * edge_weight, depth + 1))

            for neighbor in graph.predecessors(node):
                if neighbor not in visited:
                    visited.add(neighbor)
                    edge_weight = float(graph.edges[neighbor, node].get("weight", 1.0))
                    queue.append((neighbor, next_impact * edge_weight, depth + 1))

        results.sort(key=lambda x: abs(x["impact"]), reverse=True)
        return results

    def query_natural_language(
        self,
        query: str,
        entities: list[dict],
        relationships: list[dict],
    ) -> dict:
        """Simple keyword-based matching against entity names and relationship types.

        Returns a dict with ``entities``, ``relationships``, and ``paths`` keys.
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        matched_entity_ids: set[str] = set()
        matched_entities: list[dict] = []

        # Match entities by name overlap
        for ent in entities:
            name_lower = ent.get("name", "").lower()
            name_words = set(name_lower.split())
            # Check if any query word appears in the entity name
            if query_words & name_words or query_lower in name_lower:
                matched_entity_ids.add(ent["id"])
                matched_entities.append(ent)

        # Also match by entity_type if query mentions it
        type_keywords = {
            "company": "company",
            "companies": "company",
            "person": "person",
            "people": "person",
            "sector": "sector",
            "sectors": "sector",
            "country": "country",
            "countries": "country",
            "exchange": "exchange",
            "exchanges": "exchange",
        }
        for keyword, etype in type_keywords.items():
            if keyword in query_lower:
                for ent in entities:
                    if ent.get("entity_type") == etype and ent["id"] not in matched_entity_ids:
                        matched_entity_ids.add(ent["id"])
                        matched_entities.append(ent)

        # Match relationships touching matched entities
        matched_rels: list[dict] = []
        for rel in relationships:
            if rel["source_id"] in matched_entity_ids or rel["target_id"] in matched_entity_ids:
                matched_rels.append(rel)
                # Also include the other end entity
                for eid in (rel["source_id"], rel["target_id"]):
                    if eid not in matched_entity_ids:
                        matched_entity_ids.add(eid)
                        # Find entity dict
                        for ent in entities:
                            if ent["id"] == eid:
                                matched_entities.append(ent)
                                break

        # Also match by relation_type keywords in query
        relation_keywords = {
            "owns": "owns",
            "ownership": "owns",
            "subsidiary": "subsidiary_of",
            "competes": "competes_with",
            "competition": "competes_with",
            "supplies": "supplies",
            "supply": "supplies",
            "board": "board_member",
            "director": "board_member",
            "located": "located_in",
            "listed": "listed_on",
        }
        for keyword, rtype in relation_keywords.items():
            if keyword in query_lower:
                for rel in relationships:
                    if rel.get("relation_type") == rtype and rel not in matched_rels:
                        matched_rels.append(rel)
                        for eid in (rel["source_id"], rel["target_id"]):
                            if eid not in matched_entity_ids:
                                matched_entity_ids.add(eid)
                                for ent in entities:
                                    if ent["id"] == eid:
                                        matched_entities.append(ent)
                                        break

        return {
            "entities": matched_entities,
            "relationships": matched_rels,
            "paths": [],  # paths require graph traversal; empty for keyword match
        }
