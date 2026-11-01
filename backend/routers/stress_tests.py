import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

from backend.database import get_db
from backend.models import (
    StressScenarioModel,
    StressEvaluationModel,
    StressTestListResponse,
    StressTestStatusResponse,
)
from backend.services.stress_testing_service import (
    generate_investigation_stress_scenarios,
    evaluate_investigation_stress_scenario,
    get_stress_tests,
    get_stress_scenario_detail,
    get_stress_test_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stress-tests"])


class GenerateScenariosRequest(BaseModel):
    investigation_id: Optional[str] = None


class EvaluateScenarioRequest(BaseModel):
    investigation_id: Optional[str] = None
    scenario_id: Optional[str] = None


def _resolve_investigation_id(conn, investigation_id: Optional[str] = None) -> str:
    """Helper to resolve explicitly passed or default latest investigation ID."""
    cursor = conn.cursor()
    if investigation_id:
        cursor.execute("SELECT id FROM investigations WHERE id = ?;", (investigation_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")
        return investigation_id

    # Fallback to most recent investigation
    cursor.execute("SELECT id FROM investigations ORDER BY created_at DESC LIMIT 1;")
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No investigations exist yet. Create an investigation first.")
    return row["id"]


# ==========================================
# 1. Investigation-Scoped Routes
# ==========================================

@router.get(
    "/api/investigations/{investigation_id}/stress-tests",
    response_model=StressTestListResponse,
)
def get_stress_tests_for_investigation(
    investigation_id: str,
    category: Optional[str] = Query(None, description="Filter scenarios by category"),
    severity: Optional[str] = Query(None, description="Filter scenarios by severity"),
    evaluation_status: Optional[str] = Query(None, description="Filter by evaluation status: evaluated, unevaluated"),
):
    """
    Returns the stress-testing baseline, summary metrics, and generated scenarios
    for an investigation, with optional category/severity/status filtering.
    """
    with get_db() as conn:
        _resolve_investigation_id(conn, investigation_id)
        resp = get_stress_tests(conn, investigation_id)

        # Apply in-memory filtering if requested
        filtered = resp.scenarios
        if category:
            cat_upper = category.upper()
            filtered = [s for s in filtered if s.category.upper() == cat_upper]
        if severity:
            sev_upper = severity.upper()
            filtered = [s for s in filtered if s.severity.upper() == sev_upper]
        if evaluation_status:
            stat_lower = evaluation_status.lower()
            filtered = [s for s in filtered if s.evaluation_status.lower() == stat_lower]

        resp.scenarios = filtered
        return resp


@router.post(
    "/api/investigations/{investigation_id}/stress-tests/generate",
    response_model=StressTestListResponse,
)
async def generate_scenarios_for_investigation(investigation_id: str):
    """
    Generates decision stress-testing scenarios across 6 core categories
    grounded in the Decision Contract, evidence graph, sufficiency assessments, and conflicts.
    Uses Gemini structured reasoning when available with deterministic fallback.
    """
    with get_db() as conn:
        _resolve_investigation_id(conn, investigation_id)
        try:
            await generate_investigation_stress_scenarios(conn, investigation_id)
            return get_stress_tests(conn, investigation_id)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            logger.error("Failed to generate stress-test scenarios: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Stress-test scenario generation failed: {str(e)}")


@router.post(
    "/api/investigations/{investigation_id}/stress-tests/{scenario_id}/evaluate",
    response_model=StressScenarioModel,
)
async def evaluate_scenario_for_investigation(investigation_id: str, scenario_id: str):
    """
    Evaluates a specific stress-test scenario against baseline requirement coverage.
    Computes per-requirement shifts and overall decision outcome degradation.
    """
    with get_db() as conn:
        _resolve_investigation_id(conn, investigation_id)
        try:
            await evaluate_investigation_stress_scenario(conn, investigation_id, scenario_id)
            return get_stress_scenario_detail(conn, investigation_id, scenario_id)
        except ValueError as ve:
            raise HTTPException(status_code=404 if "not found" in str(ve).lower() else 400, detail=str(ve))
        except Exception as e:
            logger.error("Failed to evaluate stress scenario %s: %s", scenario_id, e, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Scenario evaluation failed: {str(e)}")


@router.get(
    "/api/investigations/{investigation_id}/stress-tests/status",
    response_model=StressTestStatusResponse,
)
def get_stress_test_status_for_investigation(investigation_id: str):
    """
    Returns lightweight stress-testing pipeline status and baseline outcome.
    """
    with get_db() as conn:
        _resolve_investigation_id(conn, investigation_id)
        return get_stress_test_status(conn, investigation_id)


@router.get(
    "/api/investigations/{investigation_id}/stress-tests/{scenario_id}",
    response_model=StressScenarioModel,
)
def get_scenario_detail_for_investigation(investigation_id: str, scenario_id: str):
    """
    Returns full details for a single stress scenario including its evaluation findings.
    """
    with get_db() as conn:
        _resolve_investigation_id(conn, investigation_id)
        try:
            return get_stress_scenario_detail(conn, investigation_id, scenario_id)
        except ValueError as ve:
            raise HTTPException(status_code=404, detail=str(ve))


# ==========================================
# 2. Convenience Top-Level Routes
# ==========================================

@router.get(
    "/api/stress-tests",
    response_model=StressTestListResponse,
)
def get_stress_tests_convenience(
    investigation_id: Optional[str] = Query(None, description="Target investigation ID"),
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    evaluation_status: Optional[str] = Query(None),
):
    """Convenience endpoint resolving to the specified or most recent investigation."""
    with get_db() as conn:
        inv_id = _resolve_investigation_id(conn, investigation_id)
        resp = get_stress_tests(conn, inv_id)

        filtered = resp.scenarios
        if category:
            cat_upper = category.upper()
            filtered = [s for s in filtered if s.category.upper() == cat_upper]
        if severity:
            sev_upper = severity.upper()
            filtered = [s for s in filtered if s.severity.upper() == sev_upper]
        if evaluation_status:
            stat_lower = evaluation_status.lower()
            filtered = [s for s in filtered if s.evaluation_status.lower() == stat_lower]

        resp.scenarios = filtered
        return resp


@router.post(
    "/api/stress-tests/generate",
    response_model=StressTestListResponse,
)
async def generate_scenarios_convenience(payload: Optional[GenerateScenariosRequest] = Body(default=None)):
    """Convenience endpoint to generate scenarios for the active investigation."""
    with get_db() as conn:
        inv_id = _resolve_investigation_id(conn, payload.investigation_id if payload else None)
        try:
            await generate_investigation_stress_scenarios(conn, inv_id)
            return get_stress_tests(conn, inv_id)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            logger.error("Failed to generate stress-test scenarios: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Stress-test scenario generation failed: {str(e)}")


@router.post(
    "/api/stress-tests/evaluate",
    response_model=StressScenarioModel,
)
async def evaluate_scenario_convenience(payload: EvaluateScenarioRequest = Body(...)):
    """Convenience endpoint to evaluate a scenario."""
    if not payload.scenario_id:
        raise HTTPException(status_code=400, detail="scenario_id is required in request body.")

    with get_db() as conn:
        inv_id = _resolve_investigation_id(conn, payload.investigation_id)
        try:
            await evaluate_investigation_stress_scenario(conn, inv_id, payload.scenario_id)
            return get_stress_scenario_detail(conn, inv_id, payload.scenario_id)
        except ValueError as ve:
            raise HTTPException(status_code=404 if "not found" in str(ve).lower() else 400, detail=str(ve))
        except Exception as e:
            logger.error("Failed to evaluate stress scenario: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Scenario evaluation failed: {str(e)}")


@router.get(
    "/api/stress-tests/{scenario_id}",
    response_model=StressScenarioModel,
)
def get_scenario_convenience(
    scenario_id: str,
    investigation_id: Optional[str] = Query(None),
):
    """Convenience endpoint to inspect scenario details."""
    with get_db() as conn:
        inv_id = _resolve_investigation_id(conn, investigation_id)
        try:
            return get_stress_scenario_detail(conn, inv_id, scenario_id)
        except ValueError as ve:
            raise HTTPException(status_code=404, detail=str(ve))
