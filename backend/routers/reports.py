from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from backend.database import get_db
from backend.models import (
    DecisionReportModel,
    DecisionReportListResponse,
    DecisionReportStatusResponse,
)
from backend.services.report_service import (
    generate_decision_report,
    get_investigation_reports,
    get_latest_investigation_report,
    get_report_by_id,
    get_report_status,
)

router = APIRouter(tags=["Intelligence Reports"])


@router.post(
    "/api/investigations/{investigation_id}/reports/generate",
    response_model=DecisionReportModel,
    summary="Generate a new versioned Decision Intelligence Report",
)
def generate_report_endpoint(
    investigation_id: str,
    fast: bool = Query(False, description="Fast compile using instant deterministic engine"),
):
    with get_db() as db:
        try:
            report = generate_decision_report(db, investigation_id, fast_mode=fast)
            return report
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.get(
    "/api/investigations/{investigation_id}/reports",
    response_model=DecisionReportListResponse,
    summary="List all historical report versions for an investigation",
)
def list_reports_endpoint(investigation_id: str):
    with get_db() as db:
        try:
            return get_investigation_reports(db, investigation_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to list reports: {str(e)}")


@router.get(
    "/api/investigations/{investigation_id}/reports/latest",
    response_model=DecisionReportModel,
    summary="Fetch the latest published report for an investigation",
)
def get_latest_report_endpoint(investigation_id: str):
    with get_db() as db:
        report = get_latest_investigation_report(db, investigation_id)
        if not report:
            raise HTTPException(
                status_code=404,
                detail=f"No decision intelligence report found for investigation '{investigation_id}'. Click 'Generate Report' to compile one.",
            )
        return report


@router.get(
    "/api/investigations/{investigation_id}/reports/status",
    response_model=DecisionReportStatusResponse,
    summary="Get report readiness, version, robustness, and staleness status",
)
def get_report_status_endpoint(investigation_id: str):
    with get_db() as db:
        return get_report_status(db, investigation_id)


@router.get(
    "/api/investigations/{investigation_id}/reports/{report_id}",
    response_model=DecisionReportModel,
    summary="Get a specific report version by ID",
)
def get_report_by_id_endpoint(investigation_id: str, report_id: str):
    with get_db() as db:
        report = get_report_by_id(db, investigation_id, report_id)
        if not report:
            raise HTTPException(
                status_code=404,
                detail=f"Report '{report_id}' not found for investigation '{investigation_id}'.",
            )
        return report


# Top-level convenience aliases
@router.get(
    "/api/reports",
    response_model=DecisionReportListResponse,
    summary="List reports by investigation_id query parameter",
)
def get_reports_alias(investigation_id: str = Query(..., description="Investigation ID")):
    with get_db() as db:
        return get_investigation_reports(db, investigation_id)


@router.post(
    "/api/reports/generate",
    response_model=DecisionReportModel,
    summary="Generate report by investigation_id query parameter",
)
def generate_report_alias(investigation_id: str = Query(..., description="Investigation ID")):
    with get_db() as db:
        try:
            return generate_decision_report(db, investigation_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/api/reports/latest",
    response_model=DecisionReportModel,
    summary="Fetch latest report by investigation_id query parameter",
)
def get_latest_report_alias(investigation_id: str = Query(..., description="Investigation ID")):
    with get_db() as db:
        report = get_latest_investigation_report(db, investigation_id)
        if not report:
            raise HTTPException(status_code=404, detail="No report found")
        return report


@router.get(
    "/api/reports/{report_id}",
    response_model=DecisionReportModel,
    summary="Fetch report by report_id across investigations",
)
def get_report_alias_by_id(report_id: str):
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute("SELECT investigation_id FROM decision_intelligence_reports WHERE id = ?;", (report_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")
        return get_report_by_id(db, row["investigation_id"], report_id)
