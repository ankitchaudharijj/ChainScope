"""
VASP Attribution Engine (architecture doc component 08).

Weighted evidence model — every score is computed from the wallet's
actual transaction edges against the VASP directory, nothing is
hardcoded per-wallet. Weights:

    direct interaction exists     40 points (flat, once any hit exists)
    share of traced volume        up to 25
    repetition of interaction     up to 20  (5 pts per hit, capped)
    chain consistency             10        (wallet & cluster same chain)
    cluster breadth               up to 5   (distinct addresses touched)

Score is capped at 97 — attribution is always probabilistic, a
system should never claim absolute certainty on 100.
"""
from dataclasses import dataclass, field

from app.models import Vasp, WalletEdge


@dataclass
class Candidate:
    vasp: Vasp
    score: int
    interactions: int
    volume: float
    evidence: list[dict] = field(default_factory=list)


def attribute(edges: list[WalletEdge], wallet_chain: str, vasps: list[Vasp]) -> list[Candidate]:
    total_volume = sum(e.amount for e in edges) or 1.0  # guard against div-by-zero
    results: list[Candidate] = []

    for vasp in vasps:
        cluster = {a.address for a in vasp.addresses}
        hits = [e for e in edges if e.to_address in cluster]
        if not hits:
            continue

        vol = sum(e.amount for e in hits)
        share = vol / total_volume
        unique_addrs = len({e.to_address for e in hits})

        s_direct = 40
        s_volume = min(25.0, share * 50)
        s_repeat = min(20.0, len(hits) * 5)
        s_chain = 10 if wallet_chain == vasp.chain else 0
        s_breadth = min(5.0, unique_addrs * 2.5)

        score = min(97, round(s_direct + s_volume + s_repeat + s_chain + s_breadth))

        evidence = [
            {
                "title": "Direct interaction with a recorded cluster",
                "detail": f"{len(hits)} transfer(s) to addresses listed under {vasp.name}",
            },
            {
                "title": "Share of traced fund flow",
                "detail": f"{share*100:.1f} per cent of the wallet's total traced volume "
                          f"moved to this cluster",
            },
        ]
        if unique_addrs > 1:
            evidence.append({
                "title": "Multiple addresses of one cluster",
                "detail": f"{unique_addrs} distinct addresses of the same cluster were "
                          f"touched, consistent with an operating account rather than "
                          f"a single transfer",
            })
        if s_chain:
            evidence.append({
                "title": "Chain consistency",
                "detail": f"The wallet and the cluster both operate on {wallet_chain}",
            })
        evidence.append({
            "title": "Basis of the directory entry",
            "detail": vasp.evidence_source,
        })

        results.append(Candidate(vasp=vasp, score=score, interactions=len(hits),
                                  volume=vol, evidence=evidence))

    results.sort(key=lambda c: c.score, reverse=True)
    return results
