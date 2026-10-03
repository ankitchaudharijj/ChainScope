from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import AuditLog, Case, User, Vasp, Wallet
from app.schemas import CaseCreate, CaseOut, CaseStatusUpdate
from app.security import get_current_user
from app.services.attribution import attribute
from app.services.pdf_report import build_case_report
from app.services.risk import assess

router = APIRouter(prefix="/cases", tags=["cases"])


def _next_case_number(db: Session) -> str:
    from datetime import datetime
    year = datetime.utcnow().year
    count = db.query(Case).count() + 1
    return f"CS-{year}-{count:04d}"


@router.post("", response_model=CaseOut, status_code=201)
def file_case(
    payload: CaseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Re-runs the examination pipeline for the given wallet and files the
    result as a case, storing the full snapshot (candidates + evidence +
    risk factors) so the report can be reproduced exactly later even if
    the VASP directory changes afterwards.
    """
    wallet = (
        db.query(Wallet)
        .options(joinedload(Wallet.edges))
        .filter(Wallet.address == payload.wallet_address)
        .first()
    )
    if not wallet:
        raise HTTPException(404, "Wallet has not been examined — examine it first.")

    vasps = db.query(Vasp).options(joinedload(Vasp.addresses)).all()
    candidates = attribute(wallet.edges, wallet.chain, vasps)
    risk = assess(wallet, candidates)
    top = candidates[0] if candidates else None

    case = Case(
        case_number=_next_case_number(db),
        wallet_address=wallet.address,
        chain=wallet.chain,
        attributed_vasp=top.vasp.name if top else "",
        confidence=top.score if top else 0,
        risk_score=risk.score,
        risk_level=risk.level,
        status="Open",
        filed_by=user.email,
        snapshot={
            "balance_display": wallet.balance_display,
            "first_seen": wallet.first_seen,
            "tx_count": wallet.tx_count,
            "candidates": [
                {"vasp_name": c.vasp.name, "vasp_type": c.vasp.vasp_type, "score": c.score,
                 "interactions": c.interactions, "volume": c.volume, "evidence": c.evidence}
                for c in candidates
            ],
            "risk_factors": risk.factors,
            "risk_remark": risk.remark,
        },
    )
    db.add(case)
    db.add(AuditLog(user_email=user.email, action="CASE FILED",
                     detail=f"{case.case_number} for {wallet.address[:10]}..."))
    db.commit()
    db.refresh(case)
    return case


@router.get("", response_model=list[CaseOut])
def list_cases(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Case).order_by(Case.filed_at.desc()).all()


@router.get("/{case_number}", response_model=CaseOut)
def get_case(case_number: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = db.query(Case).filter(Case.case_number == case_number).first()
    if not case:
        raise HTTPException(404, "Case not found")
    return case


@router.patch("/{case_number}/status", response_model=CaseOut)
def update_status(
    case_number: str, payload: CaseStatusUpdate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """Supervisors move a case through Open -> Under Review -> Closed."""
    case = db.query(Case).filter(Case.case_number == case_number).first()
    if not case:
        raise HTTPException(404, "Case not found")

    allowed = {"Open", "Under Review", "Closed"}
    if payload.status not in allowed:
        raise HTTPException(422, f"Status must be one of {sorted(allowed)}")

    old = case.status
    case.status = payload.status
    db.add(AuditLog(user_email=user.email, action="CASE STATUS CHANGED",
                     detail=f"{case_number}: {old} -> {payload.status}"))
    db.commit()
    db.refresh(case)
    return case


@router.get("/{case_number}/report.pdf")
def case_report_pdf(
    case_number: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """
    PDF rebuilt from the case's frozen snapshot — always matches what
    was on record when the case was filed, even if the VASP directory
    or scoring logic has changed since.
    """
    case = db.query(Case).filter(Case.case_number == case_number).first()
    if not case:
        raise HTTPException(404, "Case not found")

    pdf_bytes = build_case_report(officer=user.email, designation=user.role, case=case)
    db.add(AuditLog(user_email=user.email, action="REPORT EXPORTED (PDF)",
                     detail=f"Case report for {case_number}"))
    db.commit()

    filename = f"ChainScope_{case_number}.pdf"
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
