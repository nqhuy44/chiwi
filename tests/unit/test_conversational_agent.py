"""Tests for the Conversational Agent — chat to intent parsing."""

import pytest

from src.agents.conversational import ConversationalAgent

@pytest.mark.asyncio
async def test_conversational_agent_log_transaction(mock_gemini):
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

    agent = ConversationalAgent(mock_gemini)
    result = await agent.process_message("hôm qua uống highlands 50k", "chat123")

    assert result.intent == "log_transaction"
    assert result.payload["amount"] == 50000
    assert result.response_text == "Đã ghi nhận 50k tại Highlands."
    mock_gemini.call_pro.assert_called_once()

@pytest.mark.asyncio
async def test_conversational_agent_general_chat(mock_gemini):
    mock_gemini.call_pro.return_value = {
        "intent": "general_chat",
        "payload": {},
        "response_text": "Chào bạn, mình có thể giúp gì?"
    }

    agent = ConversationalAgent(mock_gemini)
    result = await agent.process_message("chào chiwi", "chat123")

    assert result.intent == "general_chat"
    assert not result.payload
    assert result.response_text == "Chào bạn, mình có thể giúp gì?"

@pytest.mark.asyncio
async def test_conversational_agent_empty_response(mock_gemini):
    mock_gemini.call_pro.return_value = {}

    agent = ConversationalAgent(mock_gemini)
    result = await agent.process_message("blabla", "chat123")

    assert result.intent == "general_chat"
    assert result.response_text == "Xin lỗi, mình chưa rõ ý bạn. Bạn có thể nói cụ thể hơn không?"
