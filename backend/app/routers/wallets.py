from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.graph import graph
from app.models import AuditLog, User, Vasp, Wallet, WalletEdge
from app.schemas import (
    AttributionCandidate, EvidenceItem, GraphEdge, InvestigationResult,
    RiskAssessment, RiskFactor, WalletSummaryOut,
)
from app.security import get_current_user
from app.services import blockchain
from app.services.attribution import attribute
from app.services.pdf_report import build_wallet_report
from app.services.risk import assess

router = APIRouter(prefix="/wallets", tags=["wallets"])


def _fetch_and_cache_live(address: str, db: Session) -> Wallet:
    """
    Wallet wasn't in Postgres — try a live lookup via the Blockchain
    Data Engine and cache the result as a normal Wallet row so every
    later request for the same address hits the cache, not the chain
    API again. Raises HTTPException(404) with an explanatory message
    on any failure (bad address, no API key, no history, etc).
    """
    try:
        fetched = blockchain.fetch_wallet(address)
    except blockchain.BlockchainFetchError as e:
        raise HTTPException(status_code=404, detail=str(e))

    wallet = Wallet(
        address=fetched.address, chain=fetched.chain,
        balance_display=fetched.balance_display, first_seen=fetched.first_seen,
        tx_count=fetched.tx_count,
        # Public transaction history alone doesn't tell you about sanctions
        # listings or scam reports — those need an external intelligence
        # feed this prototype doesn't have. Only flag what's genuinely
        # inferable from the fetched activity itself.
        flag_sanctions=False, flag_scam_report=False, flag_dormant_revival=False,
        flag_rapid_movement=fetched.tx_count > 300,
    )
    wallet.edges = [
        WalletEdge(to_address=e.to_address, amount=e.amount, direction=e.direction)
        for e in fetched.edges
    ]
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return wallet


@router.get("", response_model=list[WalletSummaryOut])
def list_wallets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Every wallet currently on record. In this prototype that's the
    seeded specimen set; in production it would be every address ever
    examined (the Blockchain Data Engine caches on first lookup).
    """
    return db.query(Wallet).all()


@router.get("/{address}/examine", response_model=InvestigationResult)
def examine_wallet(
    address: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    The core pipeline: fetch the cached wallet + its edges (in a full
    deployment this step calls the Blockchain Data Engine live), run
    the Attribution Engine against the VASP directory, then the Risk
    Engine, and return everything the frontend needs to render the
    examination page in one call.
    """
    wallet = (
        db.query(Wallet)
        .options(joinedload(Wallet.edges))
        .filter(Wallet.address == address)
        .first()
    )
    if not wallet:
        # Not cached yet — try a live lookup before giving up. This is what
        # turns the seeded specimen dataset into a real system: any valid
        # ETH or BTC address works, not just the six that were pre-loaded.
        wallet = _fetch_and_cache_live(address, db)

    vasps = db.query(Vasp).options(joinedload(Vasp.addresses)).all()
    vasp_lookup = {a.address: v for v in vasps for a in v.addresses}

    candidates = attribute(wallet.edges, wallet.chain, vasps)
    risk = assess(wallet, candidates)

    # Keep the Graph Engine current with whatever's just been examined.
    # A Neo4j outage must never fail an examination — graph.sync_wallet
    # already swallows connection errors internally.
    graph.sync_wallet(wallet, vasp_lookup)

    db.add(AuditLog(
        user_email=user.email, action="EXAMINATION",
        detail=(
            f"{address[:10]}... -> "
            f"{candidates[0].vasp.name + ' at ' + str(candidates[0].score) + '%' if candidates else 'no candidate'}, "
            f"graded {risk.level}"
        ),
    ))
    db.commit()

    return InvestigationResult(
        address=wallet.address,
        chain=wallet.chain,
        balance_display=wallet.balance_display,
        first_seen=wallet.first_seen,
        tx_count=wallet.tx_count,
        edges=[
            GraphEdge(
                to_address=e.to_address,
                amount=e.amount,
                direction=e.direction,
                is_vasp=e.to_address in vasp_lookup,
                vasp_name=vasp_lookup[e.to_address].name if e.to_address in vasp_lookup else None,
                risk_grade=vasp_lookup[e.to_address].risk_grade if e.to_address in vasp_lookup else None,
            )
            for e in wallet.edges
        ],
        candidates=[
            AttributionCandidate(
                vasp_name=c.vasp.name,
                vasp_type=c.vasp.vasp_type,
                score=c.score,
                interactions=c.interactions,
                volume=c.volume,
                evidence=[EvidenceItem(title=e["title"], detail=e["detail"]) for e in c.evidence],
            )
            for c in candidates
        ],
        risk=RiskAssessment(
            score=risk.score, level=risk.level, remark=risk.remark,
            factors=[RiskFactor(name=f["name"], points=f["points"]) for f in risk.factors],
        ),
    )


@router.get("/{address}/report.pdf")
def wallet_report_pdf(
    address: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """
    Freshly computed PDF (Form CS-2) for a wallet that's already been
    examined at least once. Recomputes attribution + risk from current
    data rather than reading a cache, so it always reflects the current
    VASP directory — for a frozen snapshot as-filed, use
    /cases/{case_number}/report.pdf instead.
    """
    wallet = (
        db.query(Wallet).options(joinedload(Wallet.edges))
        .filter(Wallet.address == address).first()
    )
    if not wallet:
        raise HTTPException(404, "Wallet has not been examined yet — examine it first.")

    vasps = db.query(Vasp).options(joinedload(Vasp.addresses)).all()
    candidates = attribute(wallet.edges, wallet.chain, vasps)
    risk = assess(wallet, candidates)

    pdf_bytes = build_wallet_report(
        officer=user.email, designation=user.role, wallet=wallet, candidates=candidates,
        risk_score=risk.score, risk_level=risk.level, risk_remark=risk.remark,
        risk_factors=risk.factors,
    )
    db.add(AuditLog(user_email=user.email, action="REPORT EXPORTED (PDF)",
                     detail=f"Wallet report for {address[:10]}..."))
    db.commit()

    filename = f"ChainScope_{address[:10]}.pdf"
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
