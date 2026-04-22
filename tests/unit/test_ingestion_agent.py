"""Tests for the Ingestion Agent — bank notification parsing."""

import pytest

from src.agents.ingestion import IngestionAgent


@pytest.mark.asyncio
async def test_parse_valid_vcb_notification(mock_gemini):
    """Given a valid VCB notification, agent returns parsed transaction."""
    mock_gemini.call_flash.return_value = {
        "is_transaction": True,
        "amount": 500000,
        "currency": "VND",
        "direction": "outflow",
        "merchant_name": "Highlands Coffee",
        "transaction_time": "2024-10-20T14:30:00",
        "bank_name": "Vietcombank",
        "confidence": "high",
    }

    agent = IngestionAgent(mock_gemini)
    result = await agent.parse(
        "VCB: -500,000VND; 14:30 20/10/24; ND: highlands coffee"
    )

    assert result.is_transaction is True
    assert result.amount == 500000
    assert result.direction == "outflow"
    assert result.merchant_name == "Highlands Coffee"
    assert result.confidence == "high"
    mock_gemini.call_flash.assert_called_once()


@pytest.mark.asyncio
async def test_parse_non_transaction(mock_gemini):
    """Given a non-financial notification, is_transaction must be false."""
    mock_gemini.call_flash.return_value = {"is_transaction": False}

    agent = IngestionAgent(mock_gemini)
    result = await agent.parse("VCB: OTP cua ban la 123456")

    assert result.is_transaction is False
    assert result.amount is None


@pytest.mark.asyncio
async def test_parse_empty_gemini_response(mock_gemini):
    """When Gemini fails, return non-transaction with raw text preserved."""
    mock_gemini.call_flash.return_value = {}

    agent = IngestionAgent(mock_gemini)
    result = await agent.parse("unknown format")

    assert result.is_transaction is False
    assert result.raw_text == "unknown format"


@pytest.mark.asyncio
async def test_parse_invalid_timestamp_gracefully(mock_gemini):
    """An unparseable transaction_time should not crash the agent."""
    mock_gemini.call_flash.return_value = {
        "is_transaction": True,
        "amount": 100000,
        "direction": "outflow",
        "transaction_time": "not-a-date",
        "confidence": "low",
    }

    agent = IngestionAgent(mock_gemini)
    result = await agent.parse("some notification")

    assert result.is_transaction is True
    assert result.transaction_time is None


@pytest.mark.asyncio
async def test_pii_masked_before_llm_call(mock_gemini):
    """Verify the text passed to Gemini has PII stripped."""
    mock_gemini.call_flash.return_value = {"is_transaction": False}

    agent = IngestionAgent(mock_gemini)
    await agent.parse("TCB: TK 1234567890 giao dich -100,000VND")

    # Inspect what was sent to Gemini
    call_args = mock_gemini.call_flash.call_args
    sent_text = call_args[0][1]  # (system_prompt, user_message)
    assert "1234567890" not in sent_text
    assert "100,000" in sent_text  # amount preserved
