# ChainScope API

FastAPI backend for ChainScope (Team PHOENIX, SIH Problem Statement 26182).
Implements the Backend API Layer, VASP Attribution Engine, and Risk Engine
from the system architecture — the same scoring logic used by the frontend
prototypes, now running server-side against a real Postgres database.

## Run it (Docker — easiest)

Requires Docker Desktop installed and running.

```bash
cd chainscope/backend
cp .env.example .env
docker compose up --build
```

Once it's up, seed the demo data (one time):

```bash
docker compose exec api python -m app.data.seed
```

The API is now live at **http://localhost:8000**
Interactive docs (try every endpoint from the browser): **http://localhost:8000/docs**

## Run it without Docker

Requires Python 3.12 and a running PostgreSQL server.

```bash
cd chainscope/backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env — set DATABASE_URL to your local Postgres instance

python -m app.data.seed         # creates tables + loads demo data
uvicorn app.main:app --reload
```

## Try it

Login (demo credentials, seeded above):

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"io.cyber@i4c.gov.in","password":"demo123"}'
```

Copy the `access_token` from the response, then:

```bash
TOKEN="paste it here"

curl http://localhost:8000/wallets/0x71C4A2E9B3D8F1A6C5E2B7D9A4F3C8E1B6D2A9F2/examine \
  -H "Authorization: Bearer $TOKEN"

curl http://localhost:8000/vasps -H "Authorization: Bearer $TOKEN"

curl -X POST http://localhost:8000/cases \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"wallet_address":"0x71C4A2E9B3D8F1A6C5E2B7D9A4F3C8E1B6D2A9F2"}'

curl http://localhost:8000/cases -H "Authorization: Bearer $TOKEN"
curl http://localhost:8000/audit -H "Authorization: Bearer $TOKEN"

curl "http://localhost:8000/graph/0x9F2E7A1C4B8D3E6F0A5C2B9D7E4F1A8C3B6D0E11/proximity" \
  -H "Authorization: Bearer $TOKEN"

curl "http://localhost:8000/ml/0x9F2E7A1C4B8D3E6F0A5C2B9D7E4F1A8C3B6D0E11/behaviour" \
  -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8000/ml/clusters" -H "Authorization: Bearer $TOKEN"
```

Six specimen wallet addresses are seeded — see `app/data/seed.py` for
the full list, or just check the `/wallets` calls in the frontend
prototype's sample chips, they're the same six.

## Endpoints

| Method | Path                          | Purpose                                    |
|--------|-------------------------------|---------------------------------------------|
| POST   | `/auth/login`                 | Sign in, get a JWT session token             |
| GET    | `/wallets`                    | List every wallet on record                  |
| GET    | `/wallets/{address}/examine`  | Run attribution + risk (live-fetches if not cached) |
| POST   | `/cases`                      | File the last examination as a case          |
| GET    | `/cases`                      | List all filed cases                         |
| GET    | `/cases/{case_number}`        | Fetch one case                               |
| PATCH  | `/cases/{case_number}/status` | Change a case's status                       |
| GET    | `/vasps`                      | List the VASP directory                      |
| GET    | `/wallets/{address}/report.pdf` | Fresh PDF (Form CS-2), recomputed live      |
| GET    | `/cases/{case_number}/report.pdf` | PDF frozen to the case's filed snapshot   |
| GET    | `/graph/{address}/proximity`  | Multi-hop VASPs reachable from this address  |
| GET    | `/graph/{address}/subgraph`   | Local fund-flow neighbourhood, for a graph UI|
| GET    | `/ml/{address}/behaviour`     | ML behaviour classification (needs examine first) |
| GET    | `/ml/clusters`                | Groups all known wallets by behavioural similarity |
| GET    | `/audit`                      | List the audit log                           |
| GET    | `/health`                     | Liveness check                               |

Every route except `/auth/login` and `/health` requires
`Authorization: Bearer <token>`.

## The AI/ML Engine

A separate concern from the rule-based Risk Engine: `app/services/
ml_engine.py` trains a `RandomForestClassifier` (scikit-learn) at
startup on a small synthetic labelled dataset — five behaviour classes
(Normal, Exchange-like, Mixer-related, High-risk, Rapid Fund Movement),
each a Gaussian cluster in a 10-feature space (tx count, unique
counterparties, amount statistics, VASP/mixer interaction share,
dormancy and sanctions flags). It's a real, fitted model — training
takes a couple of seconds at app startup, visible in the logs — not a
lookup table re-stating the risk rules, though the class centres were
designed using the same domain reasoning as those rules.

`GET /ml/{address}/behaviour` returns the predicted label with a
confidence and the full class-probability distribution — treat this as
a second, ML-derived signal alongside the Risk Engine's score, not a
replacement for it. Because it's trained on synthetic examples rather
than labelled real-world fraud data, expect it to be genuinely
uncertain on edge cases — in testing, a scam-flagged wallet with no
actual mixer interaction still got classified "Mixer-related" as its
top label at 43%, with "High-risk" a fairly close second. That's an
honest reflection of a small, synthetic training set, not a bug to
paper over.

`GET /ml/clusters` runs KMeans across every wallet currently on record
and groups them by behavioural similarity — the ML half of "Wallet
Clustering (ML + Graph)" in the architecture doc; `/graph/*` is the
other half. With only a handful of wallets seeded, don't expect
dramatic cluster separation — this becomes more meaningful once more
wallets have been examined.

## The Graph Engine — why it's a separate component

Postgres stores each wallet's *own* recorded edges — enough for the
Attribution Engine, which only checks "did this wallet directly touch
a known deposit address". But laundering commonly works by routing
funds through one or more clean-looking intermediary wallets before
they reach an exchange, specifically to defeat a single-hop check.

`GET /graph/{address}/proximity` runs a variable-length Cypher path
query outward from the address to any node tagged as a known VASP,
up to 4 hops, and returns the *shortest* path to each one found. A
hit at 1 hop duplicates what the Attribution Engine already scores
directly; a hit at 2+ hops is the multi-hop signal the flat Postgres
tables can't surface on their own — this is the actual reason a
graph database is worth the extra moving part instead of just using
recursive SQL.

Two of the seeded specimen wallets demonstrate this on purpose — see
`GRAPH_ONLY_EDGES` in `app/data/seed.py`:

- Wallet `0x9F2E7A1C...` looks clean at 1 hop (its only VASP contact
  is CoinHarbor directly). Its counterparty `0xB7C8D9`, however, later
  moved funds on to a *different* CoinHarbor deposit address — a 2-hop
  proximity hit that only the Graph Engine catches.
- Wallet `0x2B9D4F7A...` looks entirely low-risk at 1 hop. Its
  counterparty `0xC1D2E3` later moved funds on to ObscuraMix, a known
  mixer — a 2-hop mixer-proximity signal, exactly the kind of thing a
  risk analyst would want flagged even though the wallet's own direct
  transactions never touch a mixer address.

Try it once the stack is up:

```bash
curl "http://localhost:8000/graph/0x9F2E7A1C4B8D3E6F0A5C2B9D7E4F1A8C3B6D0E11/proximity" \
  -H "Authorization: Bearer $TOKEN"
```

The Graph Engine degrades gracefully: if Neo4j is unreachable, every
`graph.*` call catches the connection error and returns an empty
result rather than raising, so `/wallets/{address}/examine` and every
other endpoint keep working — the graph signal is an enrichment, not
a hard dependency for the rest of the API.

**Testing note:** this sandbox has no Docker and no network access to
download a Neo4j server, so the Cypher queries and ingestion logic
were verified two ways — a full FastAPI run against SQLite exercising
every endpoint including a deliberately unreachable Neo4j (confirms
nothing crashes), and a mocked-driver test of `app/graph.py` covering
hop/depth clamping, parameter binding, result-shape parsing, and
graceful degradation. The Cypher itself has **not** been executed
against a live Neo4j server — run `docker compose up`, then open
**http://localhost:7474** (Neo4j Browser, login `neo4j` /
`chainscope123`) and try a query like `MATCH (n) RETURN n LIMIT 50` to
confirm the graph looks right before relying on it for a demo.

## What's stubbed vs real

**Real, computed server-side:** attribution scoring, risk scoring, case
filing, audit logging, authentication, multi-hop graph proximity via
Neo4j, live blockchain lookups (Etherscan for ETH, Blockstream for
BTC), ML behaviour classification / clustering, and PDF report
generation — all of this actually runs, no hardcoded per-wallet answers.
`/wallets/{address}/examine` checks Postgres first; on a cache miss it
calls the Blockchain Data Engine (`app/services/blockchain.py`) for any
validly-formatted address, not just the six seeded specimens, and
caches what it gets back so the same address doesn't hit the chain API
twice.

**A small real VASP directory now exists too:** alongside the synthetic
demo set (`VASPS` in `app/data/seed.py` — kept so the six seeded
specimen wallets always score the same way for a demo), there's now
`REAL_VASPS`: publicly tagged addresses for Binance, Coinbase, Kraken
and Tornado Cash, each with its evidence cited (Etherscan address tags,
OFAC/court filings, public BTC rich-list trackers). A live-fetched
wallet that has genuinely transacted with one of those addresses will
get a real attribution hit — try sending a search for any well-known
Binance or Coinbase deposit address. That said, it's still nine
hand-picked addresses, not a production directory; a live-fetched
wallet that hasn't touched one of these specific addresses will still,
correctly, come back "no candidate identified" — a real production
directory (thousands of verified deposit-address clusters) is a
data-licensing / OSINT job, not something a seed file can substitute
for. Sanctions and scam-report flags on a live-fetched wallet are also
always `false` (public transaction history alone doesn't tell you
that) — only `flag_rapid_movement` gets inferred, from transaction
count.

**One more thing to know:** Etherscan lookups need a free API key
(`ETHERSCAN_API_KEY` in `.env` — sign up at etherscan.io/apis). Without
one, ETH addresses outside the seeded set return a clear 404 rather
than a live result; Bitcoin lookups need no key at all.

## The Report Engine — PDF export

Two entry points, both building the same "Form CS-2" layout with
`reportlab` (`app/services/pdf_report.py`) — no external PDF tooling,
no system dependencies beyond the pure-Python package:

- **`GET /wallets/{address}/report.pdf`** — recomputes attribution and
  risk from current data and renders a PDF on the spot. Use this for a
  quick export before a case is even filed.
- **`GET /cases/{case_number}/report.pdf`** — renders straight from the
  case's frozen snapshot, so it always matches what was on record at
  filing time, even if the VASP directory or scoring logic changes
  later. This is the one meant for attaching to an actual case file.

Both are wired into the frontend's examination page ("Download PDF"
next to "File as case") and its Report tab. Verified end-to-end: filed
a real case, downloaded the PDF, and parsed it back with `pypdf` to
confirm the extracted text actually contains the case number, the
attributed VASP, the risk grading and all five report sections — not
just that some PDF bytes came back.

## Connecting the frontend

`../frontend/chainscope_frontend_connected.html` (one level up from this
folder) is the same NIC/GoI-style UI, wired to call this API instead of
computing everything in the browser. To use it:

1. Bring the API up as above and seed it.
2. From the `chainscope/frontend` folder, run `python -m http.server 3000`
   and open `http://localhost:3000/chainscope_frontend_connected.html`
   (the default `CORS_ORIGINS` includes `http://localhost:3000` and
   `null`, so opening the file directly by double-click also works).
3. On the login screen, the **API Base URL** field defaults to
   `http://localhost:8000` — change it if your API is running elsewhere.
4. Sign in with `io.cyber@i4c.gov.in` / `demo123` (or any user you add
   to the `users` table).

If the frontend shows a "Could not reach the API" message, the backend
isn't running, isn't reachable at that URL, or its `CORS_ORIGINS`
doesn't include the origin the frontend is being served from — check
`.env` and restart the API after changing it.

## Next steps toward the full architecture

1. **Expand the real VASP directory** — nine hand-picked addresses
   (`REAL_VASPS` in `app/data/seed.py`) is a start, not real coverage.
   Growing it toward thousands of verified deposit-address clusters is
   an OSINT / licensed-data job, not a coding one.
2. **Real training data for the ML Engine** — `app/services/ml_engine.py`
   currently trains on synthetic examples; swapping in labelled
   real-world data would need either a licensed dataset or manually
   labelled historical cases.
3. **Alembic** — proper migrations instead of `create_all` before any
   real deployment.
