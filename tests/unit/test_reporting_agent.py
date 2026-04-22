"""Unit tests for ReportingAgent."""

import pytest
from unittest.mock import AsyncMock

from src.agents.reporting import ReportingAgent
from src.core.schemas import ReportRequest

@pytest.fixture
def mock_gemini():
    gemini = AsyncMock()
    gemini.call_pro.return_value = {"report_text": "Báo cáo test: Hôm nay bạn đã chi tiêu 50k."}
    return gemini

@pytest.fixture
def reporting_agent(mock_gemini):
    return ReportingAgent(mock_gemini)

@pytest.mark.asyncio
async def test_generate_report_success(reporting_agent, mock_gemini):
    request = ReportRequest(user_id="user123", report_type="daily_summary", period="2026-04-22")
    transactions = [
        {"amount": 50000, "direction": "outflow", "category_id": "Cafe", "merchant_name": "Highlands"},
        {"amount": 100000, "direction": "outflow", "category_id": "Food", "merchant_name": "Pho"},
    ]
    
    result = await reporting_agent.generate(request, transactions)
    
    assert result["status"] == "success"
    assert result["report_type"] == "daily_summary"
    assert result["data"]["total_outflow"] == 150000
    assert result["data"]["total_inflow"] == 0
    assert result["data"]["transaction_count"] == 2
    assert "Báo cáo test" in result["report_text"]
    
    mock_gemini.call_pro.assert_called_once()
    call_args = mock_gemini.call_pro.call_args[0]
    prompt = call_args[1]
    assert "150,000" in prompt
    assert "Highlands" in prompt
