"""
Blockchain Data Engine (architecture doc component 04).

Fetches real transaction history for a wallet address directly from
public chain-indexer APIs — Etherscan for Ethereum, Blockstream's
Esplora API for Bitcoin — and normalises both into the same shape the
rest of the system already works with (a Wallet plus its WalletEdge
rows). This is what app/data/seed.py's static data stands in for when
no live lookup is available.

Deliberately simple: enough real history to run attribution, risk, and
graph proximity on, not a production-grade chain indexer. Etherscan
needs a free API key (see .env.example); Blockstream's API needs none.

Honesty note for whoever reads this next: the VASP directory this gets
matched against (app/data/seed.py) is two things layered together — a
synthetic demo set (VASPS) built to give the seeded specimen wallets
predictable, pedagogical scores, plus a small real, source-cited set
(REAL_VASPS: Binance, Coinbase, Kraken, Tornado Cash) built from
publicly tagged Etherscan addresses and OFAC/court filings, so a
live-fetched wallet that has genuinely interacted with one of those
services will actually get attributed. Even so, this is a handful of
addresses, not a production directory — real coverage (thousands of
verified deposit-address clusters) is a data-licensing / OSINT job,
not something a prototype's seed file can replace. A live-fetched
wallet that hasn't touched one of these specific addresses will still,
correctly, come back "no candidate identified".
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from app.config import settings

log = logging.getLogger("chainscope.blockchain")

ETHERSCAN_BASE = "https://api.etherscan.io/api"
BLOCKSTREAM_BASE = "https://blockstream.info/api"
REQUEST_TIMEOUT = 10.0
MAX_TX_TO_FETCH = 50  # keeps the fund-flow graph and report readable


class BlockchainFetchError(Exception):
    """Raised whenever a live address can't be fetched — bad format, no
    history, no API key configured, or the upstream API itself failing.
    The router turns this straight into a 404 with the message as-is."""


@dataclass
class FetchedEdge:
    to_address: str
    amount: float
    direction: str  # "in" / "out"


@dataclass
class FetchedWallet:
    address: str
    chain: str
    balance_display: str
    first_seen: str
    tx_count: int
    edges: list[FetchedEdge] = field(default_factory=list)


def detect_chain(address: str) -> str | None:
    a = address.strip()
    if a.lower().startswith("0x") and len(a) == 42:
        return "ETH"
    if a.startswith(("bc1", "1", "3")):
        return "BTC"
    return None


def fetch_wallet(address: str) -> FetchedWallet:
    chain = detect_chain(address)
    if chain == "ETH":
        return _fetch_eth(address)
    if chain == "BTC":
        return _fetch_btc(address)
    raise BlockchainFetchError(
        f"'{address}' doesn't match a recognised Ethereum (0x… , 42 chars) "
        f"or Bitcoin address format."
    )


def _fetch_eth(address: str) -> FetchedWallet:
    if not settings.etherscan_api_key:
        raise BlockchainFetchError(
            "Live Ethereum lookups need an ETHERSCAN_API_KEY (free at "
            "etherscan.io/apis) — set it in .env, or examine one of the "
            "seeded specimen addresses instead."
        )

    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        bal_resp = client.get(ETHERSCAN_BASE, params={
            "module": "account", "action": "balance", "address": address,
            "tag": "latest", "apikey": settings.etherscan_api_key,
        })
        bal_resp.raise_for_status()
        bal_data = bal_resp.json()

        tx_resp = client.get(ETHERSCAN_BASE, params={
            "module": "account", "action": "txlist", "address": address,
            "startblock": 0, "endblock": 99999999, "page": 1,
            "offset": MAX_TX_TO_FETCH, "sort": "desc",
            "apikey": settings.etherscan_api_key,
        })
        tx_resp.raise_for_status()
        tx_data = tx_resp.json()

    if bal_data.get("status") == "0":
        msg = str(bal_data.get("message", ""))
        result = str(bal_data.get("result", ""))
        if "invalid" in msg.lower() or "invalid" in result.lower():
            raise BlockchainFetchError(f"Etherscan rejected '{address}' as an invalid address.")
    if bal_data.get("message") == "NOTOK":
        raise BlockchainFetchError(
            f"Etherscan API call failed: {bal_data.get('result', 'unknown error')} "
            f"— check ETHERSCAN_API_KEY and rate limits."
        )

    try:
        wei = int(bal_data.get("result") or "0")
    except (TypeError, ValueError):
        # Etherscan sometimes puts the error text in `result` with a generic
        # `message` — whatever this is, it isn't a balance, so treat it as a
        # failed lookup rather than crashing on the int() conversion.
        raise BlockchainFetchError(
            f"Etherscan returned an unexpected balance response for '{address}': "
            f"{bal_data.get('result')!r}"
        )
    balance_eth = wei / 1e18

    txs = tx_data.get("result")
    if not isinstance(txs, list) or not txs:
        raise BlockchainFetchError(f"No Ethereum transaction history found for {address}.")

    addr_lower = address.lower()
    edges: list[FetchedEdge] = []
    timestamps: list[int] = []

    for tx in txs:
        value_eth = int(tx.get("value") or "0") / 1e18
        if value_eth == 0:
            continue  # skip 0-value calls — contract interactions, approvals, etc.
        frm = (tx.get("from") or "").lower()
        to = (tx.get("to") or "").lower()
        ts = tx.get("timeStamp")
        if ts:
            timestamps.append(int(ts))
        if frm == addr_lower:
            edges.append(FetchedEdge(to_address=to, amount=value_eth, direction="out"))
        elif to == addr_lower:
            edges.append(FetchedEdge(to_address=frm, amount=value_eth, direction="in"))

    first_seen = (
        datetime.fromtimestamp(min(timestamps), tz=timezone.utc).strftime("%d/%m/%Y")
        if timestamps else "unknown"
    )

    return FetchedWallet(
        address=address, chain="ETH",
        balance_display=f"{balance_eth:.4f} ETH",
        first_seen=first_seen, tx_count=len(txs), edges=edges,
    )


def _fetch_btc(address: str) -> FetchedWallet:
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        info_resp = client.get(f"{BLOCKSTREAM_BASE}/address/{address}")
        if info_resp.status_code == 400:
            raise BlockchainFetchError(f"'{address}' was rejected as an invalid Bitcoin address.")
        info_resp.raise_for_status()
        info = info_resp.json()

        tx_resp = client.get(f"{BLOCKSTREAM_BASE}/address/{address}/txs")
        tx_resp.raise_for_status()
        txs = tx_resp.json()[:MAX_TX_TO_FETCH]

    stats = info.get("chain_stats", {})
    funded = stats.get("funded_txo_sum", 0)
    spent = stats.get("spent_txo_sum", 0)
    balance_btc = (funded - spent) / 1e8
    tx_count = stats.get("tx_count", len(txs))

    if not txs:
        raise BlockchainFetchError(f"No Bitcoin transaction history found for {address}.")

    edges: list[FetchedEdge] = []
    timestamps: list[int] = []

    for tx in txs:
        status = tx.get("status", {})
        if status.get("block_time"):
            timestamps.append(status["block_time"])

        is_sender = any(
            (vin.get("prevout") or {}).get("scriptpubkey_address") == address
            for vin in tx.get("vin", [])
        )
        if is_sender:
            # this address funded the transaction — outputs to *other*
            # addresses are what it sent onward
            for vout in tx.get("vout", []):
                out_addr = vout.get("scriptpubkey_address")
                value_btc = (vout.get("value") or 0) / 1e8
                if out_addr and out_addr != address and value_btc > 0:
                    edges.append(FetchedEdge(to_address=out_addr, amount=value_btc, direction="out"))
        else:
            # this address only appears as a recipient — it received funds;
            # the counterparty is whoever funded the transaction's first input
            src = None
            if tx.get("vin"):
                src = (tx["vin"][0].get("prevout") or {}).get("scriptpubkey_address")
            for vout in tx.get("vout", []):
                if vout.get("scriptpubkey_address") == address:
                    value_btc = (vout.get("value") or 0) / 1e8
                    if value_btc > 0:
                        edges.append(FetchedEdge(to_address=src or "unknown", amount=value_btc, direction="in"))

    first_seen = (
        datetime.fromtimestamp(min(timestamps), tz=timezone.utc).strftime("%d/%m/%Y")
        if timestamps else "unknown"
    )

    return FetchedWallet(
        address=address, chain="BTC",
        balance_display=f"{balance_btc:.4f} BTC",
        first_seen=first_seen, tx_count=tx_count, edges=edges,
    )
