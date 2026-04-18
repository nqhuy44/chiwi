"""Tests for the Orchestrator — Think-First routing and notification pipeline."""

import pytest

from src.core.orchestrator import Orchestrator


@pytest.fixture
def orchestrator(mock_gemini, mock_redis, mock_transaction_repo):
    return Orchestrator(
        gemini=mock_gemini,
        redis=mock_redis,
        transaction_repo=mock_transaction_repo,
    )


@pytest.mark.asyncio
async def test_classify_notification_source(orchestrator):
    event_type = await orchestrator.classify_event({"source": "macrodroid"})
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
        "source": "tasker",
        "notification_text": "TCB: -100,000VND tai GRAB. 14:30 20/10/24",
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
            "source": "macrodroid",
            "notification_text": "VCB: OTP 123456",
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
        {"source": "macrodroid", "notification_text": "", "user_id": "u1"},
    )

    assert result["status"] == "empty_notification"
    mock_transaction_repo.insert.assert_not_called()
