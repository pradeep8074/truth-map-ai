import contextlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import init_db
from backend.routers import investigations, sources, contracts, graph, conflicts, sufficiency, stress_tests, reports, fragility, navigator


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database schema
    init_db()
    yield


app = FastAPI(
    title="TRUTHMAP AI — Evidence Intelligence Engine",
    description="Backend API for live source ingestion, cryptographic provenance tracking, atomic claim extraction, decision contract compilation, and evidence dependency graph.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local Vite development frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(investigations.router)
app.include_router(sources.router)
app.include_router(contracts.router)
app.include_router(graph.router)
app.include_router(conflicts.router)
app.include_router(sufficiency.router)
app.include_router(stress_tests.router)
app.include_router(reports.router)
app.include_router(fragility.router)
app.include_router(navigator.router)


@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "platform": "TRUTHMAP AI",
        "component": "Component 10 — Autonomous Gap Verification & Investigation Update Navigator",
        "integrity_mode": "Zero Synthetic Metrics",
    }


@app.get("/api/workspace/freshness-summary")
async def workspace_freshness_summary():
    from backend.routers.investigations import get_workspace_freshness_summary
    return await get_workspace_freshness_summary()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
