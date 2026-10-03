"""
Seeds the database with the same specimen dataset used by the frontend
prototypes, plus one demo login. Run once after the tables exist:

    python -m app.data.seed

Safe to re-run — it checks for existing rows before inserting.
"""
from app.database import Base, SessionLocal, engine
from app.graph import graph
from app.models import AuditLog, Case, User, Vasp, VaspAddress, Wallet, WalletEdge
from app.security import hash_password

VASPS = [
    dict(name="BinEx Global", chain="ETH", vasp_type="Centralised exchange",
         evidence_source="Deposit addresses disclosed under regulatory filing",
         risk_grade="low", addresses=["0xDEP001", "0xDEP002", "0xDEP003"]),
    dict(name="CoinHarbor", chain="ETH", vasp_type="Centralised exchange",
         evidence_source="Open-source intelligence and on-chain label set",
         risk_grade="low", addresses=["0xDEP101", "0xDEP102"]),
    dict(name="SwiftSwap", chain="ETH", vasp_type="Instant swap service",
         evidence_source="Service hot-wallet pattern observed over 14 months",
         risk_grade="medium", addresses=["0xDEP201", "0xDEP202"]),
    dict(name="VaultPay", chain="BTC", vasp_type="Custodial wallet provider",
         evidence_source="Proof-of-reserve address published by the provider",
         risk_grade="low", addresses=["bc1qDEP01", "bc1qDEP02"]),
    dict(name="ObscuraMix", chain="ETH", vasp_type="Mixing service",
         evidence_source="Sanctions listing supported by on-chain tracing",
         risk_grade="high", addresses=["0xMIX001", "0xMIX002"]),
]
"""
^ Synthetic specimen directory. These addresses only exist in this file —
they don't correspond to any real service — and every WALLETS entry
below was hand-built to interact with them, so the attribution scores
in the prototype demo stay fixed and predictable. Kept exactly as-is;
don't add real addresses into this list or the demo scores will drift.
"""

REAL_VASPS = [
    # Every address below is a publicly tagged, real on-chain address —
    # verifiable at the Etherscan/OFAC/court-filing links given in each
    # evidence_source. This is what makes live-fetched wallets (via
    # app/services/blockchain.py) capable of a genuine attribution hit
    # instead of always coming back "no candidate identified". It is
    # still a tiny, hand-picked list — real production coverage (the
    # thousands of deposit-cluster addresses a commercial chain-analytics
    # vendor tracks) is a licensed-data job, not something scraped
    # together for a prototype.
    dict(name="Binance", chain="ETH", vasp_type="Centralised exchange",
         evidence_source="Etherscan public address tag 'Binance: Hot Wallet 20' — "
                          "etherscan.io/address/0xf977814e90da44bfa03b6295a0616a897441acec",
         risk_grade="low",
         addresses=["0xf977814e90da44bfa03b6295a0616a897441acec",
                     "0xa180fe01b906a1be37be6c534a3300785b20d947"]),
    dict(name="Coinbase", chain="ETH", vasp_type="Centralised exchange",
         evidence_source="Etherscan public address tags 'Coinbase 1' / 'Coinbase 12' — "
                          "etherscan.io/address/0x71660c4005ba85c37ccec55d0c4493e66fe775d3",
         risk_grade="low",
         addresses=["0x71660c4005ba85c37ccec55d0c4493e66fe775d3",
                     "0x503828976d22510aad0201ac7ec88293211d23da"]),
    dict(name="Kraken", chain="ETH", vasp_type="Centralised exchange",
         evidence_source="Etherscan public address tags 'Kraken: Hot Wallet' / 'Kraken 6' — "
                          "etherscan.io/address/0xe9f7ecae3a53d2a67105292894676b00d1fab785",
         risk_grade="low",
         addresses=["0xe9f7ecae3a53d2a67105292894676b00d1fab785",
                     "0x53d284357ec70ce289d6d64134dfac8e511c8a3d"]),
    dict(name="Tornado Cash", chain="ETH", vasp_type="Mixing service",
         evidence_source="OFAC SDN-listed Aug 2022 - Mar 2025 (sanctions vacated after a "
                          "2025 court ruling that OFAC overstepped its authority sanctioning "
                          "immutable, decentralised software); still treated as elevated-AML-"
                          "risk by exchanges/compliance tooling given its mixing function. "
                          "0.1 ETH and 100 ETH pool contracts, per court filings and Etherscan.",
         risk_grade="high",
         # Lowercased deliberately: Etherscan's tx-list API always returns
         # addresses lowercase, and attribution matching is an exact string
         # comparison against WalletEdge.to_address — a live-fetched wallet's
         # edges would silently never match a mixed-case (checksummed)
         # address here. Unlike ETH, base58 BTC addresses below ARE
         # case-sensitive and must be left exactly as published.
         addresses=["0x12d66f87a04a9e220743712ce6d9bb1b5616b8fc",
                     "0xa160cdab225685da1d56aa342ad8841c3b53f291"]),
    dict(name="Binance", chain="BTC", vasp_type="Centralised exchange",
         evidence_source="Widely documented as the largest single BTC address on public "
                          "rich-list trackers (Arkham, BitInfoCharts) — holds roughly 1.2% "
                          "of circulating BTC supply, attributed to Binance cold storage",
         risk_grade="low",
         addresses=["34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo"]),
]


WALLETS = [
    dict(address="0x71C4A2E9B3D8F1A6C5E2B7D9A4F3C8E1B6D2A9F2", chain="ETH",
         balance_display="2.41 ETH", first_seen="03/11/2024", tx_count=182,
         flag_sanctions=True, flag_rapid_movement=True, flag_scam_report=False, flag_dormant_revival=False,
         edges=[("0xA1B2C3", 1.2, "out"), ("0xA1B2C3", 0.8, "out"), ("0xD4E5F6", 3.5, "out"),
                ("0xDEP001", 5.0, "out"), ("0xDEP002", 2.2, "out"), ("0xMIX001", 4.1, "out"),
                ("0xA1B2C3", 0.6, "in"), ("0xDEP001", 1.1, "in")]),

    dict(address="0x9F2E7A1C4B8D3E6F0A5C2B9D7E4F1A8C3B6D0E11", chain="ETH",
         balance_display="0.08 ETH", first_seen="21/06/2025", tx_count=24,
         flag_sanctions=False, flag_rapid_movement=False, flag_scam_report=False, flag_dormant_revival=False,
         edges=[("0xDEP101", 0.5, "out"), ("0xDEP101", 0.3, "out"), ("0xDEP102", 0.2, "out"),
                ("0xB7C8D9", 0.15, "out"), ("0xDEP101", 0.9, "in")]),

    dict(address="0x3A8B5C2D9E6F1A4B7C0D3E8F5A2B9C6D1E4F7A0B", chain="ETH",
         balance_display="11.90 ETH", first_seen="14/02/2024", tx_count=641,
         flag_sanctions=True, flag_rapid_movement=True, flag_scam_report=True, flag_dormant_revival=False,
         edges=[("0xMIX001", 8.0, "out"), ("0xMIX002", 6.4, "out"), ("0xMIX001", 5.2, "out"),
                ("0xE1F2A3", 2.1, "out"), ("0xDEP201", 1.3, "out"), ("0xMIX002", 3.3, "in")]),

    dict(address="bc1q4x7f2m9k3p8s5t1v6w0y2z4a7b9c3d1e5f31", chain="BTC",
         balance_display="0.734 BTC", first_seen="09/01/2025", tx_count=97,
         flag_sanctions=False, flag_rapid_movement=False, flag_scam_report=False, flag_dormant_revival=True,
         edges=[("bc1qDEP01", 0.4, "out"), ("bc1qDEP01", 0.25, "out"), ("bc1qAAA11", 0.1, "out"),
                ("bc1qDEP02", 0.18, "out"), ("bc1qAAA11", 0.3, "in"), ("bc1qDEP01", 0.6, "in")]),

    dict(address="0xC5D8E1F4A7B0C3D6E9F2A5B8C1D4E7F0A3B6C9D2", chain="ETH",
         balance_display="0.00 ETH", first_seen="30/08/2025", tx_count=11,
         flag_sanctions=False, flag_rapid_movement=True, flag_scam_report=True, flag_dormant_revival=False,
         edges=[("0xDEP201", 2.0, "out"), ("0xDEP202", 1.8, "out"), ("0xF0A1B2", 0.9, "out"),
                ("0xDEP201", 4.6, "in")]),

    dict(address="0x2B9D4F7A1C6E3B8D5F0A2C7E4B1D6F3A8C5E0B7D", chain="ETH",
         balance_display="0.42 ETH", first_seen="17/03/2025", tx_count=58,
         flag_sanctions=False, flag_rapid_movement=False, flag_scam_report=False, flag_dormant_revival=False,
         edges=[("0xDEP001", 0.9, "out"), ("0xDEP101", 0.7, "out"), ("0xC1D2E3", 0.4, "out"),
                ("0xDEP001", 0.5, "in")]),
]

# Edges the Blockchain Data Engine's fuller crawl would have found one hop
# further out — i.e. what these wallets' *counterparties* went on to do,
# which is outside the scope of any single wallet's own WalletEdge rows in
# Postgres. This is exactly the "looks clean at 1 hop, isn't at 2" case the
# Graph Engine exists to catch:
#   - 0xB7C8D9 is a plain counterparty of the low-risk wallet #2 above; it
#     later moved funds on to a CoinHarbor deposit address.
#   - 0xC1D2E3 is a plain counterparty of wallet #6 above; it later moved
#     funds on to an ObscuraMix (mixer) address.
GRAPH_ONLY_EDGES = [
    ("0xB7C8D9", "0xDEP102", 0.4, "ETH"),
    ("0xC1D2E3", "0xMIX001", 1.1, "ETH"),
]


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == "io.cyber@i4c.gov.in").first():
            db.add(User(
                email="io.cyber@i4c.gov.in",
                hashed_password=hash_password("demo123"),
                role="Investigating Officer",
            ))
            print("Seeded demo user: io.cyber@i4c.gov.in / demo123")

        if db.query(Vasp).count() == 0:
            all_vasps = VASPS + REAL_VASPS
            for v in all_vasps:
                vasp = Vasp(name=v["name"], chain=v["chain"], vasp_type=v["vasp_type"],
                            evidence_source=v["evidence_source"], risk_grade=v["risk_grade"])
                vasp.addresses = [VaspAddress(address=a) for a in v["addresses"]]
                db.add(vasp)
            print(f"Seeded {len(VASPS)} synthetic + {len(REAL_VASPS)} real VASP directory entries")

        if db.query(Wallet).count() == 0:
            for w in WALLETS:
                wallet = Wallet(
                    address=w["address"], chain=w["chain"],
                    balance_display=w["balance_display"], first_seen=w["first_seen"],
                    tx_count=w["tx_count"], flag_sanctions=w["flag_sanctions"],
                    flag_rapid_movement=w["flag_rapid_movement"],
                    flag_scam_report=w["flag_scam_report"],
                    flag_dormant_revival=w["flag_dormant_revival"],
                )
                wallet.edges = [
                    WalletEdge(to_address=to, amount=amt, direction=d)
                    for to, amt, d in w["edges"]
                ]
                db.add(wallet)
            print(f"Seeded {len(WALLETS)} specimen wallets")

        db.commit()
        print("Postgres seed complete.")
    finally:
        db.close()

    seed_graph()


def seed_graph():
    """
    Mirrors the same specimen data into Neo4j, plus the two graph-only
    multi-hop edges. Safe to re-run — every write below is a MERGE.
    """
    vasp_by_address = {addr: v for v in (VASPS + REAL_VASPS) for addr in v["addresses"]}

    for v in VASPS + REAL_VASPS:
        for addr in v["addresses"]:
            graph.upsert_address(addr, v["chain"], is_vasp=True,
                                  vasp_name=v["name"], risk_grade=v["risk_grade"])

    for w in WALLETS:
        graph.upsert_address(w["address"], w["chain"], is_vasp=False)
        for to, amt, direction in w["edges"]:
            vasp = vasp_by_address.get(to)
            graph.upsert_address(to, w["chain"], is_vasp=bool(vasp),
                                  vasp_name=vasp["name"] if vasp else None,
                                  risk_grade=vasp["risk_grade"] if vasp else None)
            if direction == "out":
                graph.upsert_edge(w["address"], to, amt, w["chain"])
            else:
                graph.upsert_edge(to, w["address"], amt, w["chain"])

    for frm, to, amt, chain in GRAPH_ONLY_EDGES:
        vasp = vasp_by_address.get(to)
        graph.upsert_address(frm, chain, is_vasp=False)
        graph.upsert_address(to, chain, is_vasp=bool(vasp),
                              vasp_name=vasp["name"] if vasp else None,
                              risk_grade=vasp["risk_grade"] if vasp else None)
        graph.upsert_edge(frm, to, amt, chain)

    print(f"Graph seed: {len(VASPS)+len(REAL_VASPS)} VASPs ({len(VASPS)} synthetic + "
          f"{len(REAL_VASPS)} real), {len(WALLETS)} wallets, "
          f"{len(GRAPH_ONLY_EDGES)} multi-hop demonstration edge(s).")
    print("If this line printed with no warnings above, Neo4j was reachable "
          "and the graph is seeded. Warnings above mean Neo4j wasn't up yet — "
          "re-run this script once it is.")


if __name__ == "__main__":
    run()
