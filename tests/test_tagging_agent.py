"""Tests for the Tagging Agent — category + tags classification."""

import pytest

from src.agents.tagging import TaggingAgent
from src.core.schemas import ParsedTransaction


def _make_parsed(merchant: str | None = "Highlands Coffee") -> ParsedTransaction:
    return ParsedTransaction(
        is_transaction=True,
        amount=50000,
        currency="VND",
        direction="outflow",
        merchant_name=merchant,
        raw_text="raw notification text",
        confidence="high",
    )


@pytest.mark.asyncio
async def test_tagging_uses_merchant_cache(mock_gemini, mock_redis):
    """If merchant is cached, skip the LLM call entirely."""
    mock_redis.get_merchant_cache.return_value = "Cà phê / Trà sữa"

    agent = TaggingAgent(mock_gemini, mock_redis)
    result = await agent.enrich(_make_parsed(), user_id="u1")

    assert result["category_name"] == "Cà phê / Trà sữa"
    mock_gemini.call_flash.assert_not_called()


@pytest.mark.asyncio
async def test_tagging_calls_gemini_on_cache_miss(mock_gemini, mock_redis):
    """On cache miss, call Gemini and cache the result."""
    mock_redis.get_merchant_cache.return_value = None
    mock_gemini.call_flash.return_value = {
        "category_name": "Cà phê / Trà sữa",
        "tags": ["cafe", "morning"],
    }

    agent = TaggingAgent(mock_gemini, mock_redis)
    result = await agent.enrich(_make_parsed(), user_id="u1")

    assert result["category_name"] == "Cà phê / Trà sữa"
    assert "cafe" in result["tags"]
    mock_gemini.call_flash.assert_called_once()
    mock_redis.set_merchant_cache.assert_called_once_with(
        "Highlands Coffee", "Cà phê / Trà sữa"
    )


@pytest.mark.asyncio
async def test_tagging_fallback_to_khac(mock_gemini, mock_redis):
    """When Gemini fails, default category is 'Khác' and not cached."""
    mock_redis.get_merchant_cache.return_value = None
    mock_gemini.call_flash.return_value = {}

    agent = TaggingAgent(mock_gemini, mock_redis)
    result = await agent.enrich(_make_parsed(), user_id="u1")

    assert result["category_name"] == "Khác"
    mock_redis.set_merchant_cache.assert_not_called()


@pytest.mark.asyncio
async def test_tagging_with_no_merchant(mock_gemini, mock_redis):
    """A transaction with no merchant should still call Gemini but skip cache."""
    mock_gemini.call_flash.return_value = {
        "category_name": "Khác",
        "tags": [],
    }

    agent = TaggingAgent(mock_gemini, mock_redis)
    result = await agent.enrich(_make_parsed(merchant=None), user_id="u1")

    assert result["category_name"] == "Khác"
    mock_redis.get_merchant_cache.assert_not_called()
    mock_redis.set_merchant_cache.assert_not_called()
