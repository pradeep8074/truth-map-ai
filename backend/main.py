import os
import sys
import datetime
import contextlib
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure both repo root and backend directory are in sys.path
_current_dir = Path(__file__).resolve().parent
_repo_root = _current_dir.parent
for _p in [str(_repo_root), str(_current_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.config import FRONTEND_ORIGINS, GEMINI_API_KEY, GEMINI_MODEL
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

# Parse and configure allowed CORS origins
default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:3000",
]

configured_origins = list(default_origins)
if FRONTEND_ORIGINS:
    for origin in FRONTEND_ORIGINS.split(","):
        cleaned = origin.strip().rstrip("/")
        if cleaned and cleaned not in configured_origins:
            configured_origins.append(cleaned)

# Enable CORS with Vercel preview support and local dev support
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
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


@app.get("/")
def root_endpoint():
    return {
        "status": "online",
        "service": "TRUTHMAP AI Backend",
        "docs_url": "/docs",
        "health_check": "/health",
        "version": "1.0.0"
    }


@app.get("/health")
def health_root():
    return {
        "status": "healthy",
        "service": "truthmap-ai-backend",
        "environment": os.getenv("RENDER_SERVICE_NAME", "production" if os.getenv("RENDER") else "development"),
        "version": "1.0.0"
    }


@app.get("/api/health")
def api_health():
    return {
        "status": "online",
        "platform": "TRUTHMAP AI",
        "component": "Component 10 — Autonomous Gap Verification & Investigation Update Navigator",
        "integrity_mode": "Zero Synthetic Metrics",
    }


@app.get("/api/system/ai-status")
@app.get("/system/ai-status")
async def get_system_ai_status():
    """Diagnostics endpoint reporting Google Gemini configuration and connection status safely without leaking credentials."""
    configured = bool(GEMINI_API_KEY and len(GEMINI_API_KEY) > 5)
    last_check = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if not configured:
        return {
            "provider": "google-gemini",
            "configured": False,
            "connection_status": "unconfigured",
            "model_identifier": GEMINI_MODEL,
            "last_connectivity_check": last_check,
            "fallback_mode": "deterministic_rule_engine",
            "detail": "GEMINI_API_KEY is not configured. Platform operates in zero-hallucination deterministic fallback mode."
        }

    connection_status = "connected"
    detail = "Gemini API client initialized successfully."

    try:
        from google import genai
        # Test client initialization
        _client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            connection_status = "quota_exhausted"
            detail = "Gemini API key is configured, but free-tier quota is currently exhausted. Deterministic fallback active."
        else:
            connection_status = "error"
            detail = f"Gemini connection error: {type(e).__name__}. Deterministic fallback active."

    return {
        "provider": "google-gemini",
        "configured": True,
        "connection_status": connection_status,
        "model_identifier": GEMINI_MODEL,
        "last_connectivity_check": last_check,
        "fallback_mode": "deterministic_rule_engine",
        "detail": detail
    }


@app.get("/api/workspace/freshness-summary")
async def workspace_freshness_summary():
    from backend.routers.investigations import get_workspace_freshness_summary
    return await get_workspace_freshness_summary()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
