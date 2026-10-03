# ChainScope

Virtual asset attribution platform — SIH Problem Statement 26182, Team
PHOENIX. Traces a wallet address, scores which VASP it most likely
belongs to (with evidence), grades its risk, and traces multi-hop fund
flow through Neo4j.

```
chainscope/
├── backend/    FastAPI + PostgreSQL + Neo4j — the real, running API
└── frontend/   NIC/GoI-style UI, wired to call the backend
```

## Quick start

**1. Start the backend** (needs Docker):

```bash
cd backend
cp .env.example .env
docker compose up --build
docker compose exec api python -m app.data.seed
```

API is now live at http://localhost:8000 — interactive docs at
http://localhost:8000/docs

**2. Start the frontend**, in a second terminal:

```bash
cd frontend
python -m http.server 3000
```

Open http://localhost:3000/chainscope_frontend_connected.html and sign
in with `io.cyber@i4c.gov.in` / `demo123`.

## Full details

- **`backend/README.md`** — every endpoint, how the Attribution Engine
  and Risk Engine score things, how the Neo4j Graph Engine does
  multi-hop VASP proximity, what's real vs stubbed, and next steps.
