from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.graph import graph
from app.routers import auth, audit, cases, graph as graph_router, ml, vasps, wallets

# create tables on startup if they don't exist yet (fine for a prototype;
# swap for Alembic migrations before this goes anywhere near production)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ChainScope API",
    description="Backend for the ChainScope virtual asset attribution system "
                 "(Team PHOENIX, SIH Problem Statement 26182).",
    version="0.9.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(wallets.router)
app.include_router(cases.router)
app.include_router(vasps.router)
app.include_router(audit.router)
app.include_router(graph_router.router)
app.include_router(ml.router)


@app.on_event("shutdown")
def shutdown_graph_driver():
    graph.close()


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
