"""Tests for the Orchestrator — Think-First routing and notification pipeline."""

import pytest

from src.core.orchestrator import Orchestrator


from unittest.mock import MagicMock, patch

@pytest.fixture
def orchestrator(
    mock_gemini,
    mock_redis,
    mock_telegram,
    mock_transaction_repo,
    mock_budget_repo,
    mock_budget_event_repo,
    mock_goal_repo,
    mock_correction_repo,
    mock_nudge_repo,
    mock_subscription_repo,
):
    with patch("src.core.orchestrator.get_profile") as mock_get_profile:
        # Return a mock profile with a default timezone
        mock_profile = MagicMock()
        mock_profile.timezone = "Asia/Ho_Chi_Minh"
        mock_profile.chat_id = "12345678"
        mock_get_profile.return_value = mock_profile
        
        yield Orchestrator(
            gemini=mock_gemini,
            redis=mock_redis,
            telegram=mock_telegram,
            transaction_repo=mock_transaction_repo,
            budget_repo=mock_budget_repo,
            budget_event_repo=mock_budget_event_repo,
            goal_repo=mock_goal_repo,
            correction_repo=mock_correction_repo,
            nudge_repo=mock_nudge_repo,
            subscription_repo=mock_subscription_repo,
        )


@pytest.mark.asyncio
async def test_classify_notification_source(orchestrator):
    event_type = await orchestrator.classify_event({"source": "android"})
    assert event_type == "notification"


@pytest.mark.asyncio
async def test_classify_default_is_chat(orchestrator):
    event_type = await orchestrator.classify_event({"source": "unknown"})
    assert event_type == "chat"


@pytest.mark.asyncio
async def test_notification_pipeline_stores_transaction(
    orchestrator, mock_gemini, mock_transaction_repo
):
    """End-to-end: notification -> parsed -> tagged -> stored."""
    # Gemini returns parsed data on first call (ingestion),
    # then tagging result on second call
    mock_gemini.call_flash.side_effect = [
        {
            "is_transaction": True,
            "amount": 100000,
            "direction": "outflow",
            "merchant_name": "Grab",
            "transaction_time": "2024-10-20T14:30:00",
            "bank_name": "Techcombank",
            "confidence": "high",
        },
        {"category_name": "Di chuyển", "tags": ["grab", "commute"]},
    ]

    payload = {
        "source": "android",
        "raw_text": "TCB: -100,000VND tai GRAB. 14:30 20/10/24",
        "user_id": "user_1",
    }

    result = await orchestrator.route("notification", payload)

    assert result["status"] == "stored"
    assert result["transaction_id"] == "mock_txn_id_123"
    mock_transaction_repo.insert.assert_called_once()

    # Verify the stored document
    inserted = mock_transaction_repo.insert.call_args[0][0]
    assert inserted.user_id == "user_1"
    assert inserted.amount == 100000
    assert inserted.direction == "outflow"
    assert inserted.merchant_name == "Grab"
    assert inserted.category_id == "Di chuyển"
    assert "grab" in inserted.tags


@pytest.mark.asyncio
async def test_notification_skips_non_transaction(
    orchestrator, mock_gemini, mock_transaction_repo
):
    """When ingestion says not a transaction, skip storage."""
    mock_gemini.call_flash.return_value = {"is_transaction": False}

    result = await orchestrator.route(
        "notification",
        {
            "source": "android",
            "raw_text": "VCB: OTP 123456",
            "user_id": "user_1",
        },
    )

    assert result["status"] == "not_transaction"
    mock_transaction_repo.insert.assert_not_called()


@pytest.mark.asyncio
async def test_notification_empty_text(orchestrator, mock_transaction_repo):
    """Empty notification_text returns empty status without LLM calls."""
    result = await orchestrator.route(
        "notification",
        {"source": "android", "raw_text": "", "user_id": "u1"},
    )

    assert result["status"] == "empty_notification"
    mock_transaction_repo.insert.assert_not_called()

@pytest.mark.asyncio
async def test_chat_pipeline_stores_transaction(
    orchestrator, mock_gemini, mock_transaction_repo
):
    """End-to-end: chat message -> conversational parsed -> tagged -> stored."""
    # Gemini call_pro for conversational parsing
    mock_gemini.call_pro.return_value = {
        "intent": "log_transaction",
        "payload": {
            "amount": 50000,
            "currency": "VND",
            "direction": "outflow",
            "merchant_name": "Highlands",
            "transaction_time": "2026-04-20T10:00:00Z"
        },
        "response_text": "Đã ghi nhận 50k tại Highlands."
    }
    # Gemini call_flash for tagging fallback
    mock_gemini.call_flash.return_value = {
        "category_name": "Cà phê / Trà sữa",
        "tags": ["cafe"]
    }

    payload = {
        "source": "telegram",
        "message": "hôm qua uống highlands 50k",
        "user_id": "user_1",
        "chat_id": "chat_1"
    }

    result = await orchestrator.route("chat", payload)

    assert result["status"] == "stored"
    assert result["transaction_id"] == "mock_txn_id_123"
    assert result["response_text"] == "Đã ghi nhận 50k tại Highlands."
    mock_transaction_repo.insert.assert_called_once()
    mock_gemini.call_pro.assert_called_once()
    
    # Tagging might be called either from cache/DB or flash, here flash is called.
    mock_gemini.call_flash.assert_called_once()

    inserted = mock_transaction_repo.insert.call_args[0][0]
    assert inserted.source == "chat"
    assert inserted.amount == 50000
    assert inserted.merchant_name == "Highlands"
    assert inserted.category_id == "Cà phê / Trà sữa"

@pytest.mark.asyncio
async def test_chat_pipeline_general_chat(
    orchestrator, mock_gemini, mock_transaction_repo
):
    """End-to-end: general chat skips storage."""
    mock_gemini.call_pro.return_value = {
        "intent": "general_chat",
        "payload": {},
        "response_text": "Chào bạn!"
    }

    payload = {
        "source": "telegram",
        "message": "chào chiwi",
        "user_id": "user_1",
        "chat_id": "chat_1"
    }

    result = await orchestrator.route("chat", payload)

    assert result["status"] == "chat_processed"
    assert result["intent"] == "general_chat"
    assert result["response_text"] == "Chào bạn!"
    mock_transaction_repo.insert.assert_not_called()

@pytest.mark.asyncio
async def test_chat_pipeline_request_report(
    orchestrator, mock_gemini, mock_transaction_repo
):
    """End-to-end: request report generates summary."""
    mock_gemini.call_pro.return_value = {
        "intent": "request_report",
        "payload": {},
        "response_text": ""
    }
    mock_gemini.call_flash.return_value = {
        "report_text": "Báo cáo: Tổng chi 0 VND."
    }
    mock_transaction_repo.find_by_user.return_value = []

    payload = {
        "source": "telegram",
        "message": "tổng kết hôm nay",
        "user_id": "user_1",
        "chat_id": "chat_1"
    }

    result = await orchestrator.route("chat", payload)

    assert result["status"] == "success"
    assert result["response_text"] == "Báo cáo: Tổng chi 0 VND."
    mock_transaction_repo.find_by_user.assert_called_once()
    mock_gemini.call_pro.assert_called_once()
    mock_gemini.call_flash.assert_called_once()
