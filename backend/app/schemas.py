"""
Pydantic models — the shape of what the API accepts and returns.
Kept separate from models.py (the DB tables) on purpose: the DB shape
and the API shape are allowed to drift as either evolves.
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------- auth ----------
class LoginRequest(BaseModel):
    email: str
    password: str
    role: str = "Investigating Officer"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str
    role: str


# ---------- vasp directory ----------
class VaspOut(BaseModel):
    id: int
    name: str
    chain: str
    vasp_type: str
    evidence_source: str
    risk_grade: str
    address_count: int

    class Config:
        from_attributes = True


# ---------- wallet listing ----------
class WalletSummaryOut(BaseModel):
    address: str
    chain: str
    balance_display: str

    class Config:
        from_attributes = True


# ---------- graph engine ----------
class ProximityHit(BaseModel):
    vasp_address: str
    vasp_name: str | None
    risk_grade: str | None
    hop_count: int
    path: list[str]


class SubgraphNode(BaseModel):
    address: str
    is_vasp: bool | None = False
    vasp_name: str | None = None
    risk_grade: str | None = None


class SubgraphEdge(BaseModel):
    from_address: str
    to_address: str
    amount: float
    tx_count: int
    from_is_vasp: bool | None = False
    from_vasp_name: str | None = None
    from_risk_grade: str | None = None
    to_is_vasp: bool | None = False
    to_vasp_name: str | None = None
    to_risk_grade: str | None = None


class SubgraphOut(BaseModel):
    nodes: list[SubgraphNode]
    edges: list[SubgraphEdge]


# ---------- AI/ML engine ----------
class BehaviourOut(BaseModel):
    label: str
    confidence: float
    class_probabilities: dict[str, float]


class ClusterMember(BaseModel):
    address: str
    cluster_id: int
    cluster_description: str


class ClusterOut(BaseModel):
    n_clusters: int
    members: list[ClusterMember]


# ---------- investigation ----------
class EvidenceItem(BaseModel):
    title: str
    detail: str


class AttributionCandidate(BaseModel):
    vasp_name: str
    vasp_type: str
    score: int
    interactions: int
    volume: float
    evidence: list[EvidenceItem]


class RiskFactor(BaseModel):
    name: str
    points: int


class RiskAssessment(BaseModel):
    score: int
    level: str
    remark: str
    factors: list[RiskFactor]


class GraphEdge(BaseModel):
    to_address: str
    amount: float
    direction: str
    is_vasp: bool
    vasp_name: str | None = None
    risk_grade: str | None = None


class InvestigationResult(BaseModel):
    address: str
    chain: str
    balance_display: str
    first_seen: str
    tx_count: int
    edges: list[GraphEdge]
    candidates: list[AttributionCandidate]
    risk: RiskAssessment


# ---------- cases ----------
class CaseCreate(BaseModel):
    wallet_address: str = Field(..., description="Must have been examined first")


class CaseOut(BaseModel):
    id: int
    case_number: str
    wallet_address: str
    chain: str
    attributed_vasp: str
    confidence: int
    risk_score: int
    risk_level: str
    status: str
    filed_by: str
    filed_at: datetime
    snapshot: dict[str, Any]

    class Config:
        from_attributes = True


class CaseStatusUpdate(BaseModel):
    status: str


# ---------- audit ----------
class AuditOut(BaseModel):
    id: int
    timestamp: datetime
    user_email: str
    action: str
    detail: str

    class Config:
        from_attributes = True
