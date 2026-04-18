from fastapi import APIRouter

from src.core.schemas import ReportRequest

router = APIRouter(prefix="/api")


@router.get("/reports/{report_type}")
async def get_report(
    report_type: str,
    period: str = "",
    format: str = "json",
) -> dict:
    """Get a financial report."""
    # TODO: Route to Reporting Agent or return cached report
    return {
        "report_type": report_type,
        "period": period,
        "data": {},
        "status": "not_implemented",
    }
