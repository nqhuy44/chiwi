"""REST endpoints for on-demand report retrieval."""

from fastapi import APIRouter, HTTPException, Query

from src.core.config import settings
from src.core.dependencies import container

router = APIRouter(prefix="/api")

_VALID_PERIODS = {
    "today", "this_week", "this_month", "last_week", "last_month"
}

_VALID_REPORT_TYPES = {
    "summary", "daily_summary", "weekly_summary", "monthly_report"
}


@router.get("/reports/{report_type}")
async def get_report(
    report_type: str,
    period: str = Query(default="this_month"),
    user_id: str = Query(default=""),
) -> dict:
    """Generate and return a financial report for a user.

    Auth: ``user_id`` must be in the configured allow-list.
    The report is generated on-demand via the Reporting Agent and returned
    as structured JSON (same text that would be sent via Telegram).
    """
    if user_id not in settings.allowed_user_id_list:
        raise HTTPException(status_code=401, detail="Unauthorized user")

    if report_type not in _VALID_REPORT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid report_type. Valid values: {sorted(_VALID_REPORT_TYPES)}",
        )

    if period not in _VALID_PERIODS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period. Valid values: {sorted(_VALID_PERIODS)}",
        )

    orchestrator = container.orchestrator
    result = await orchestrator.route("report", {
        "user_id": user_id,
        "period": period,
    })

    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("response_text", "Report generation failed"))

    return {
        "report_type": report_type,
        "period": period,
        "status": result.get("status", "success"),
        "text": result.get("response_text", ""),
    }
