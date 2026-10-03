from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import User, Vasp
from app.schemas import VaspOut
from app.security import get_current_user

router = APIRouter(prefix="/vasps", tags=["vasps"])


@router.get("", response_model=list[VaspOut])
def list_vasps(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    vasps = db.query(Vasp).options(joinedload(Vasp.addresses)).all()
    return [
        VaspOut(
            id=v.id, name=v.name, chain=v.chain, vasp_type=v.vasp_type,
            evidence_source=v.evidence_source, risk_grade=v.risk_grade,
            address_count=len(v.addresses),
        )
        for v in vasps
    ]
