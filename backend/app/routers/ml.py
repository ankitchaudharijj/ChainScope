from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import User, Vasp, Wallet
from app.schemas import BehaviourOut, ClusterMember, ClusterOut
from app.security import get_current_user
from app.services.ml_engine import ml_engine

router = APIRouter(prefix="/ml", tags=["ml"])


def _vasp_lookup(db: Session) -> dict:
    vasps = db.query(Vasp).options(joinedload(Vasp.addresses)).all()
    return {a.address: v for v in vasps for a in v.addresses}


@router.get("/{address}/behaviour", response_model=BehaviourOut)
def behaviour(address: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Classifies this wallet's transaction pattern with a trained
    RandomForest over engineered features — a second, ML-derived signal
    alongside the Risk Engine's rule-based score, not a replacement for
    it. Requires the wallet to have been examined already (so its edges
    are cached) — call /wallets/{address}/examine first.
    """
    wallet = (
        db.query(Wallet).options(joinedload(Wallet.edges))
        .filter(Wallet.address == address).first()
    )
    if not wallet:
        raise HTTPException(404, "Wallet has not been examined yet — examine it first.")

    result = ml_engine.classify(wallet, wallet.edges, _vasp_lookup(db))
    return BehaviourOut(
        label=result.label, confidence=result.confidence,
        class_probabilities=result.class_probabilities,
    )


@router.get("/clusters", response_model=ClusterOut)
def clusters(
    n_clusters: int = 3,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Groups every wallet currently on record (the seeded specimens plus
    anything examined via a live lookup) into behavioural clusters —
    the ML half of "Wallet Clustering (ML + Graph)" in the architecture.
    """
    wallets = db.query(Wallet).options(joinedload(Wallet.edges)).all()
    if not wallets:
        return ClusterOut(n_clusters=0, members=[])

    pairs = [(w, w.edges) for w in wallets]
    results = ml_engine.cluster(pairs, _vasp_lookup(db), n_clusters=n_clusters)
    return ClusterOut(
        n_clusters=len({r["cluster_id"] for r in results}),
        members=[ClusterMember(**r) for r in results],
    )
