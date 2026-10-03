"""
Graph Engine (architecture doc component 05).

Postgres holds each wallet's own directly-recorded edges — fine for the
Attribution Engine, which only needs to know who *this* wallet talked
to. But laundering typically works by routing funds through one or
more intermediary wallets before they reach an exchange, precisely so
that a direct, single-hop check won't catch it. Finding "is this
wallet two or three hops from a known VASP, through wallets it never
directly touched a deposit address of" is exactly the kind of query
that's natural in Cypher and painful as recursive SQL — that's the
whole reason this component exists separately from the Postgres
tables.

Degrades gracefully: every public method catches connection errors
and returns an empty result rather than raising, so the rest of the
API keeps working even if Neo4j is unreachable — the graph proximity
signal is an enrichment, not a hard dependency.
"""
import logging

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

from app.config import settings

log = logging.getLogger("chainscope.graph")

MAX_PROXIMITY_HOPS = 4
MAX_SUBGRAPH_DEPTH = 3


class Graph:
    def __init__(self):
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )

    def close(self):
        self._driver.close()

    # ---------- ingestion ----------

    def upsert_address(self, address: str, chain: str, is_vasp: bool = False,
                        vasp_name: str | None = None, risk_grade: str | None = None):
        query = """
        MERGE (a:Address {address: $address})
        SET a.chain = $chain,
            a.is_vasp = $is_vasp,
            a.vasp_name = $vasp_name,
            a.risk_grade = $risk_grade
        """
        self._run(query, address=address, chain=chain, is_vasp=is_vasp,
                  vasp_name=vasp_name, risk_grade=risk_grade)

    def upsert_edge(self, from_address: str, to_address: str, amount: float, chain: str):
        """
        Directional: from_address sent funds to to_address. Multiple
        transfers between the same pair accumulate onto one relationship
        rather than creating a new edge each time — the graph tracks
        "has this pair ever transacted and how much", not a full ledger
        (Postgres already has the itemised ledger for the wallets we've
        actually examined).
        """
        query = """
        MERGE (a:Address {address: $from_address})
        ON CREATE SET a.chain = $chain
        MERGE (b:Address {address: $to_address})
        ON CREATE SET b.chain = $chain
        MERGE (a)-[r:SENT]->(b)
        ON CREATE SET r.amount = $amount, r.tx_count = 1
        ON MATCH  SET r.amount = r.amount + $amount, r.tx_count = r.tx_count + 1
        """
        self._run(query, from_address=from_address, to_address=to_address,
                  amount=amount, chain=chain)

    def sync_wallet(self, wallet, vasp_lookup: dict):
        """
        Pushes one examined wallet's direct edges into the graph —
        called after every /wallets/{address}/examine so the graph
        stays current with whatever the Blockchain Data Engine has
        seen. vasp_lookup maps a counterparty address to its Vasp row,
        same lookup the attribution endpoint already built.
        """
        self.upsert_address(wallet.address, wallet.chain, is_vasp=False)
        for edge in wallet.edges:
            vasp = vasp_lookup.get(edge.to_address)
            self.upsert_address(
                edge.to_address, wallet.chain,
                is_vasp=bool(vasp),
                vasp_name=vasp.name if vasp else None,
                risk_grade=vasp.risk_grade if vasp else None,
            )
            if edge.direction == "out":
                self.upsert_edge(wallet.address, edge.to_address, edge.amount, wallet.chain)
            else:
                self.upsert_edge(edge.to_address, wallet.address, edge.amount, wallet.chain)

    # ---------- queries ----------

    def vasp_proximity(self, address: str, max_hops: int = MAX_PROXIMITY_HOPS) -> list[dict]:
        """
        Every known VASP reachable from `address` by following SENT
        edges outward, up to max_hops. Returns the *shortest* path found
        to each VASP — a wallet 1 hop from a VASP is a direct hit (and
        the Attribution Engine will already have scored it); a wallet
        2+ hops away is a proximity signal the flat edge table alone
        would never surface.
        """
        hops = max(1, min(int(max_hops), MAX_PROXIMITY_HOPS))
        # Neo4j doesn't allow a bound parameter inside a variable-length
        # pattern (*1..$n) — hops is server-side sanitised above, not
        # user-supplied text, so interpolating it here is safe.
        query = f"""
        MATCH path = (start:Address {{address: $address}})-[:SENT*1..{hops}]->(vasp:Address {{is_vasp: true}})
        WITH vasp, path, length(path) AS hop_count
        ORDER BY hop_count ASC
        WITH vasp, collect(path)[0] AS shortest_path, min(hop_count) AS hop_count
        RETURN vasp.address AS vasp_address,
               vasp.vasp_name AS vasp_name,
               vasp.risk_grade AS risk_grade,
               hop_count,
               [n IN nodes(shortest_path) | n.address] AS path_addresses
        ORDER BY hop_count ASC
        """
        rows = self._run(query, address=address)
        return [dict(r) for r in rows] if rows is not None else []

    def subgraph(self, address: str, depth: int = 2) -> dict:
        """
        Every node and edge within `depth` hops of `address`, either
        direction — enough to draw a local fund-flow neighbourhood
        around a wallet for visualisation.
        """
        d = max(1, min(int(depth), MAX_SUBGRAPH_DEPTH))
        query = f"""
        MATCH (start:Address {{address: $address}})-[rel:SENT*1..{d}]-(:Address)
        UNWIND rel AS r
        WITH DISTINCT r
        RETURN startNode(r).address AS from_address, endNode(r).address AS to_address,
               r.amount AS amount, r.tx_count AS tx_count,
               startNode(r).is_vasp AS from_is_vasp, startNode(r).vasp_name AS from_vasp_name,
               startNode(r).risk_grade AS from_risk_grade,
               endNode(r).is_vasp AS to_is_vasp, endNode(r).vasp_name AS to_vasp_name,
               endNode(r).risk_grade AS to_risk_grade
        """
        rows = self._run(query, address=address)
        edges = [dict(r) for r in rows] if rows is not None else []
        nodes = {}
        for e in edges:
            nodes[e["from_address"]] = {"address": e["from_address"], "is_vasp": e["from_is_vasp"], "vasp_name": e["from_vasp_name"], "risk_grade": e["from_risk_grade"]}
            nodes[e["to_address"]] = {"address": e["to_address"], "is_vasp": e["to_is_vasp"], "vasp_name": e["to_vasp_name"], "risk_grade": e["to_risk_grade"]}
        nodes.setdefault(address, {"address": address, "is_vasp": False, "vasp_name": None, "risk_grade": None})
        return {"nodes": list(nodes.values()), "edges": edges}

    # ---------- internals ----------

    def _run(self, query: str, **params):
        try:
            with self._driver.session() as session:
                result = session.run(query, **params)
                return list(result)
        except ServiceUnavailable as e:
            log.warning("Neo4j unavailable — graph enrichment skipped: %s", e)
            return None
        except Exception as e:  # noqa: BLE001 — a graph outage must never break the API
            log.warning("Neo4j query failed — graph enrichment skipped: %s", e)
            return None


graph = Graph()
