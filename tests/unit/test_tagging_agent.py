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
async def test_tagging_uses_merchant_cache(mock_gemini, mock_redis, mock_transaction_repo):
    """If merchant is cached, skip the LLM and DB calls entirely."""
    mock_redis.get_merchant_cache.return_value = "Cà phê / Trà sữa"

    agent = TaggingAgent(mock_gemini, mock_redis, mock_transaction_repo)
    result = await agent.enrich(_make_parsed(), user_id="u1")

    assert result["category_name"] == "Cà phê / Trà sữa"
    mock_transaction_repo.find_by_merchant.assert_not_called()
    mock_gemini.call_flash.assert_not_called()


@pytest.mark.asyncio
async def test_tagging_uses_historical_majority(mock_gemini, mock_redis, mock_transaction_repo):
    """On cache miss, use historical majority and cache the result."""
    mock_redis.get_merchant_cache.return_value = None
    mock_transaction_repo.find_by_merchant.return_value = [
        {"category_id": "Cà phê / Trà sữa", "tags": ["cafe"]},
        {"category_id": "Cà phê / Trà sữa", "tags": ["morning"]},
        {"category_id": "Khác", "tags": []},
    ]

    agent = TaggingAgent(mock_gemini, mock_redis, mock_transaction_repo)
    result = await agent.enrich(_make_parsed(), user_id="u1")

    assert result["category_name"] == "Cà phê / Trà sữa"
    assert "cafe" in result["tags"]
    assert "morning" in result["tags"]
    mock_gemini.call_flash.assert_not_called()
    mock_redis.set_merchant_cache.assert_called_once_with(
        "Highlands Coffee", "Cà phê / Trà sữa"
    )


@pytest.mark.asyncio
async def test_tagging_calls_gemini_on_no_majority(mock_gemini, mock_redis, mock_transaction_repo):
    """On cache miss and no historical majority, call Gemini with history context."""
    mock_redis.get_merchant_cache.return_value = None
    # No strict majority
    mock_transaction_repo.find_by_merchant.return_value = [
        {"category_id": "Cà phê / Trà sữa", "tags": ["cafe"]},
        {"category_id": "Ăn uống", "tags": ["lunch"]},
    ]
    mock_gemini.call_flash.return_value = {
        "category_name": "Cà phê / Trà sữa",
        "tags": ["cafe", "afternoon"],
    }

    agent = TaggingAgent(mock_gemini, mock_redis, mock_transaction_repo)
    result = await agent.enrich(_make_parsed(), user_id="u1")

    assert result["category_name"] == "Cà phê / Trà sữa"
    assert "afternoon" in result["tags"]
    mock_gemini.call_flash.assert_called_once()
    mock_redis.set_merchant_cache.assert_called_once_with(
        "Highlands Coffee", "Cà phê / Trà sữa"
    )


@pytest.mark.asyncio
async def test_tagging_fallback_to_khac(mock_gemini, mock_redis, mock_transaction_repo):
    """When Gemini fails, default category is 'Khác' and not cached."""
    mock_redis.get_merchant_cache.return_value = None
    mock_transaction_repo.find_by_merchant.return_value = []
    mock_gemini.call_flash.return_value = {}

    agent = TaggingAgent(mock_gemini, mock_redis, mock_transaction_repo)
    result = await agent.enrich(_make_parsed(), user_id="u1")

    assert result["category_name"] == "Khác"
    mock_redis.set_merchant_cache.assert_not_called()


@pytest.mark.asyncio
async def test_tagging_with_no_merchant(mock_gemini, mock_redis, mock_transaction_repo):
    """A transaction with no merchant should still call Gemini but skip cache & history."""
    mock_gemini.call_flash.return_value = {
        "category_name": "Khác",
        "tags": [],
    }

    agent = TaggingAgent(mock_gemini, mock_redis, mock_transaction_repo)
    result = await agent.enrich(_make_parsed(merchant=None), user_id="u1")

    assert result["category_name"] == "Khác"
    mock_redis.get_merchant_cache.assert_not_called()
    mock_transaction_repo.find_by_merchant.assert_not_called()
    mock_redis.set_merchant_cache.assert_not_called()


def test_majority_category():
    """Unit test for majority calculation logic."""
    assert TaggingAgent._majority_category([
        {"category_id": "A"}, {"category_id": "A"}, {"category_id": "B"}
    ]) == "A"
    
    # Needs strict majority (n > total/2)
    assert TaggingAgent._majority_category([
        {"category_id": "A"}, {"category_id": "A"},
        {"category_id": "B"}, {"category_id": "B"}
    ]) is None

    # Needs min count of 2
    assert TaggingAgent._majority_category([
        {"category_id": "A"}
    ]) is None
    
    # Ignores fallback category when finding top candidate, but still needs strict majority of total history
    assert TaggingAgent._majority_category([
        {"category_id": "A"}, {"category_id": "A"}, {"category_id": "A"}, 
        {"category_id": "Khác"}, {"category_id": "Khác"}
    ]) == "A"


def test_merge_tags():
    """Unit test for merging tags logic."""
    tags = TaggingAgent._merge_tags([
        {"tags": ["a", "b"]},
        {"tags": ["b", "c"]},
        {"tags": None},
    ])
    assert tags == ["a", "b", "c"]
