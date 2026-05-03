from fastapi import APIRouter, Body, HTTPException, Query

from backend.models.violations import (
    ViolationCreateResponse,
    ViolationDetailResponse,
    ViolationListResponse,
)
from backend.services.violations import (
    community_vote,
    create_violation_report,
    fetch_violation_report_detail,
    fetch_violation_reports,
    moderate_violation_report,
)

router = APIRouter(prefix="/api/v1/violations", tags=["violations"])


@router.get("/", response_model=ViolationListResponse)
def list_violation_reports(
    limit: int = Query(100, ge=1, le=5000), offset: int = Query(0, ge=0)
) -> ViolationListResponse:
    reports = fetch_violation_reports(limit=limit, offset=offset)
    return ViolationListResponse(reports=reports)


@router.get("/{report_id}", response_model=ViolationDetailResponse)
def get_violation_report_detail(report_id: int) -> ViolationDetailResponse:
    report = fetch_violation_report_detail(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return ViolationDetailResponse(report=report)


@router.post("/", response_model=ViolationCreateResponse)
def submit_violation_report(
    lat: float = Body(...),
    lon: float = Body(...),
    violation_type: str = Body(...),
    description: str = Body(...),
    evidence_url: str | None = Body(None),
    reporter_id: int | None = Body(None),
) -> ViolationCreateResponse:
    report_id = create_violation_report(
        lat, lon, violation_type, description, evidence_url, reporter_id
    )
    return ViolationCreateResponse(report_id=report_id)


@router.patch("/{report_id}/moderate")
def moderate_report(report_id: int, status: str = Body(...)):
    moderate_violation_report(report_id, status)
    return {"success": True}


@router.post("/{report_id}/vote")
def vote_on_report(report_id: int, agree: bool = Body(...)):
    community_vote(report_id, agree)
    return {"success": True}
