from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog, User
from app.schemas import LoginRequest, TokenResponse
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        # deliberately the same error for "no such user" and "wrong password" —
        # do not let the API reveal which officer IDs exist
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect officer ID or password",
        )

    token = create_access_token(user.email, user.role)
    db.add(AuditLog(user_email=user.email, action="LOGIN",
                     detail=f"{user.role} session opened"))
    db.commit()

    return TokenResponse(access_token=token, email=user.email, role=user.role)
