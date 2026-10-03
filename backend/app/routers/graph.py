from fastapi import APIRouter, Depends

from app.graph import graph
from app.models import User
from app.schemas import ProximityHit, SubgraphEdge, SubgraphNode, SubgraphOut
from app.security import get_current_user

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/{address}/proximity", response_model=list[ProximityHit])
def vasp_proximity(
    address: str, max_hops: int = 4, user: User = Depends(get_current_user)
):
    """
    Known VASPs reachable from this address within max_hops, following
    the fund-flow direction outward. A hit at hop_count 1 duplicates
    what the Attribution Engine already scores directly; hops 2 and
    above are the multi-hop signal Postgres alone can't surface —
    funds routed through an intermediary before reaching an exchange.
    """
    hits = graph.vasp_proximity(address, max_hops)
    return [
        ProximityHit(
            vasp_address=h["vasp_address"], vasp_name=h["vasp_name"],
            risk_grade=h["risk_grade"], hop_count=h["hop_count"],
            path=h["path_addresses"],
        )
        for h in hits
    ]


@router.get("/{address}/subgraph", response_model=SubgraphOut)
def subgraph(address: str, depth: int = 2, user: User = Depends(get_current_user)):
    """The local fund-flow neighbourhood around an address, for graph visualisation."""
    data = graph.subgraph(address, depth)
    return SubgraphOut(
        nodes=[SubgraphNode(**n) for n in data["nodes"]],
        edges=[SubgraphEdge(**e) for e in data["edges"]],
    )
