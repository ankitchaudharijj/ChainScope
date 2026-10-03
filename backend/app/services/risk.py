"""
Risk Engine (architecture doc component 10).

Factor-based, additive scoring — each adverse indicator that applies
adds its fixed weight. Capped at 100.
"""
from dataclasses import dataclass, field

from app.models import Wallet
from app.services.attribution import Candidate

SANCTIONS = 30
MIXER = 25
SCAM = 18
RAPID = 12
VELOCITY = 10
DORMANT = 8
HIGH_TX_THRESHOLD = 300


@dataclass
class RiskResult:
    score: int
    level: str
    remark: str
    factors: list[dict] = field(default_factory=list)


def assess(wallet: Wallet, candidates: list[Candidate]) -> RiskResult:
    factors: list[dict] = []

    if wallet.flag_sanctions:
        factors.append({"name": "Exposure to a sanctioned entity", "points": SANCTIONS})

    mixer_hit = any(c.vasp.vasp_type.lower().find("mixing") != -1 for c in candidates)
    if mixer_hit:
        factors.append({"name": "Funds routed through a mixing service", "points": MIXER})

    if wallet.flag_scam_report:
        factors.append({"name": "Address named in a reported fraud", "points": SCAM})

    if wallet.flag_rapid_movement:
        factors.append({"name": "Rapid onward movement of funds", "points": RAPID})

    if wallet.tx_count > HIGH_TX_THRESHOLD:
        factors.append({"name": "High counterparty velocity", "points": VELOCITY})

    if wallet.flag_dormant_revival:
        factors.append({"name": "Revived after prolonged dormancy", "points": DORMANT})

    if not factors:
        factors.append({"name": "No adverse indicator identified", "points": 0})

    score = min(100, sum(f["points"] for f in factors))
    level = "HIGH" if score >= 60 else "MEDIUM" if score >= 30 else "LOW"
    remark = (
        "Escalation to the Nodal Officer is advised before further action."
        if level == "HIGH" else
        "Continued monitoring is recommended."
        if level == "MEDIUM" else
        "No immediate action is indicated on the present record."
    )
    return RiskResult(score=score, level=level, remark=remark, factors=factors)
