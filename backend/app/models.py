"""
Database tables.

  User         -> investigators / supervisors who can log in
  Vasp         -> a known VASP directory entry (Layer 7 in the architecture doc)
  VaspAddress  -> one address belonging to a VASP's cluster (1 VASP -> many addresses)
  Wallet       -> a wallet that has been examined at least once (cached blockchain data)
  WalletEdge   -> one transaction edge belonging to a wallet
  Case         -> a filed case; stores the attribution + risk snapshot at filing time
  AuditLog     -> append-only action log, for compliance and evidentiary purposes
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(150), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="Investigating Officer")
    created_at = Column(DateTime, default=now_utc)


class Vasp(Base):
    __tablename__ = "vasps"

    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    chain = Column(String(10), nullable=False)            # ETH / BTC
    vasp_type = Column(String(100), nullable=False)        # Centralised exchange, Mixer, ...
    evidence_source = Column(Text, nullable=False)
    risk_grade = Column(String(10), nullable=False, default="low")  # low / medium / high

    addresses = relationship(
        "VaspAddress", back_populates="vasp", cascade="all, delete-orphan"
    )


class VaspAddress(Base):
    __tablename__ = "vasp_addresses"

    id = Column(Integer, primary_key=True)
    address = Column(String(120), nullable=False, index=True)
    vasp_id = Column(Integer, ForeignKey("vasps.id"), nullable=False)

    vasp = relationship("Vasp", back_populates="addresses")


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True)
    address = Column(String(120), unique=True, nullable=False, index=True)
    chain = Column(String(10), nullable=False)
    balance_display = Column(String(50), default="")
    first_seen = Column(String(30), default="")
    tx_count = Column(Integer, default=0)

    # risk flags consumed by the risk engine
    flag_sanctions = Column(Boolean, default=False)
    flag_rapid_movement = Column(Boolean, default=False)
    flag_scam_report = Column(Boolean, default=False)
    flag_dormant_revival = Column(Boolean, default=False)

    edges = relationship(
        "WalletEdge", back_populates="wallet", cascade="all, delete-orphan"
    )


class WalletEdge(Base):
    __tablename__ = "wallet_edges"

    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    to_address = Column(String(120), nullable=False)
    amount = Column(Float, nullable=False)
    direction = Column(String(3), nullable=False)  # "in" / "out"

    wallet = relationship("Wallet", back_populates="edges")


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True)
    case_number = Column(String(30), unique=True, nullable=False)
    wallet_address = Column(String(120), nullable=False)
    chain = Column(String(10), nullable=False)

    attributed_vasp = Column(String(150), default="")
    confidence = Column(Integer, default=0)
    risk_score = Column(Integer, default=0)
    risk_level = Column(String(10), default="LOW")

    # full computed snapshot (ranked candidates + evidence + risk factors) so
    # the report can be regenerated exactly as it stood at filing time
    snapshot = Column(JSON, default=dict)

    status = Column(String(20), default="Open")
    filed_by = Column(String(150), nullable=False)
    filed_at = Column(DateTime, default=now_utc)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=now_utc)
    user_email = Column(String(150), nullable=False)
    action = Column(String(100), nullable=False)
    detail = Column(Text, default="")
