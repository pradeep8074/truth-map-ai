import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List

from backend.database import get_db
from backend.models import (
    DecisionFragilityResultModel,
    FragilityAnalysisResponse,
    FragilityStatusResponse,
    SensitivitySimulationRequest,
    SensitivityExperimentResult,
    SensitivityAnalysisResponse,
    FragilityRecommendationsResponse,
    FragilityMethodologyResponse,
)
from backend.services.fragility_service import (
    execute_fragility_analysis,
    get_latest_fragility_result,
    get_fragility_status,
    get_fragility_methodology,
)
from backend.services.sensitivity_service import (
    simulate_sensitivity_experiment,
    list_sensitivity_experiments,
    generate_fragility_recommendations,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Fragility Index & Sensitivity"])


@router.post(
    "/api/investigations/{investigation_id}/fragility/analyze",
    response_model=FragilityAnalysisResponse,
    summary="Execute Decision Fragility Index evaluation",
)
def run_fragility_analysis_endpoint(investigation_id: str, allow_gemini: bool = Query(True)):
    with get_db() as db:
        try:
            result = execute_fragility_analysis(db, investigation_id, allow_gemini=allow_gemini)
            return FragilityAnalysisResponse(
                status="success",
                investigation_id=investigation_id,
                run_id=result.run_id,
                result=result,
                message="Decision Fragility Index evaluation completed successfully.",
            )
        except ValueError as e:
            msg = str(e)
            if "PREREQ_" in msg or "does not exist" in msg:
                raise HTTPException(status_code=400 if "PREREQ_" in msg else 404, detail=msg)
            raise HTTPException(status_code=400, detail=msg)
        except Exception as e:
            logger.error(f"Fragility evaluation failed for {investigation_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to evaluate fragility: {str(e)}")


@router.get(
    "/api/investigations/{investigation_id}/fragility/latest",
    response_model=DecisionFragilityResultModel,
    summary="Get latest Decision Fragility Index evaluation result",
)
def get_latest_fragility_endpoint(investigation_id: str):
    with get_db() as db:
        try:
            result = get_latest_fragility_result(db, investigation_id)
            if not result:
                raise HTTPException(
                    status_code=404,
                    detail=f"No fragility evaluation found for investigation {investigation_id}. Trigger analysis first.",
                )
            return result
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch fragility result: {str(e)}")


@router.get(
    "/api/investigations/{investigation_id}/fragility/status",
    response_model=FragilityStatusResponse,
    summary="Get status overview of fragility evaluation",
)
def get_fragility_status_endpoint(investigation_id: str):
    with get_db() as db:
        try:
            return get_fragility_status(db, investigation_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch fragility status: {str(e)}")


@router.post(
    "/api/investigations/{investigation_id}/fragility/sensitivity/simulate",
    response_model=SensitivityExperimentResult,
    summary="Run an isolated in-memory counterfactual sensitivity simulation",
)
def simulate_sensitivity_endpoint(investigation_id: str, request: SensitivitySimulationRequest):
    with get_db() as db:
        try:
            experiment = simulate_sensitivity_experiment(db, investigation_id, request)
            return experiment
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Sensitivity simulation failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to simulate sensitivity: {str(e)}")


@router.get(
    "/api/investigations/{investigation_id}/fragility/sensitivity/results",
    response_model=SensitivityAnalysisResponse,
    summary="List all hypothetical sensitivity simulation experiments",
)
def list_sensitivity_results_endpoint(investigation_id: str):
    with get_db() as db:
        try:
            latest = get_latest_fragility_result(db, investigation_id)
            baseline_dfi = latest.dfi_score if latest else 0.0
            baseline_class = latest.classification if latest else "NOT_ASSESSED"

            experiments = list_sensitivity_experiments(db, investigation_id)
            return SensitivityAnalysisResponse(
                investigation_id=investigation_id,
                baseline_dfi=baseline_dfi,
                baseline_classification=baseline_class,
                experiments=experiments,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch sensitivity experiments: {str(e)}")


@router.get(
    "/api/investigations/{investigation_id}/fragility/recommendations",
    response_model=FragilityRecommendationsResponse,
    summary="Get prioritized evidence improvement actions with projected DFI reductions",
)
def get_fragility_recommendations_endpoint(investigation_id: str):
    with get_db() as db:
        try:
            return generate_fragility_recommendations(db, investigation_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to generate recommendations: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {str(e)}")


@router.get(
    "/api/fragility/methodology",
    response_model=FragilityMethodologyResponse,
    summary="Get methodology v1.2.0-deterministic specification",
)
def get_methodology_endpoint():
    try:
        return get_fragility_methodology()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch methodology: {str(e)}")
