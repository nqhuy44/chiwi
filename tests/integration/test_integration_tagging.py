"""
Integration tests — TaggingAgent with REAL Gemini API.

Verifies that Gemini correctly classifies Vietnamese merchants
into the expected category list.

Run:  make test-integration
"""

import json
import os

import pytest

from src.agents.tagging import TaggingAgent
from src.core.schemas import ParsedTransaction
from src.services.gemini import GeminiService
from src.services.redis_client import RedisClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("GEMINI_API_KEY", ""),
        reason="GEMINI_API_KEY not set — skipping integration tests",
    ),
]

# Valid categories from TaggingAgent's system prompt
VALID_CATEGORIES = {
    "Ăn uống", "Cà phê / Trà sữa", "Di chuyển", "Mua sắm",
    "Giải trí", "Sức khỏe", "Giáo dục", "Hóa đơn & Tiện ích",
    "Chuyển khoản", "Thu nhập", "Tiết kiệm", "Đầu tư", "Khác",
}


@pytest.fixture
def gemini():
    svc = GeminiService()
    svc.initialize()
    return svc


@pytest.fixture
def redis_stub():
    """Disconnected Redis — forces Gemini fallback on every call."""
    return RedisClient()  # not connected, all methods return None


@pytest.fixture
def agent(gemini, redis_stub):
    return TaggingAgent(gemini, redis_stub)


def _txn(merchant: str, amount: float = 50000, direction: str = "outflow") -> ParsedTransaction:
    return ParsedTransaction(
        is_transaction=True,
        amount=amount,
        currency="VND",
        direction=direction,
        merchant_name=merchant,
        raw_text=f"Test: -{amount}VND tai {merchant}",
        confidence="high",
    )


async def test_coffee_shop_categorized(agent):
    result = await agent.enrich(_txn("Highlands Coffee"), user_id="u1")
    print(f"\n[TAGGING] Highlands Coffee:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
    assert result["category_name"] in VALID_CATEGORIES
    assert result["category_name"] in ("Cà phê / Trà sữa", "Ăn uống")


async def test_grab_categorized_as_transport(agent):
    result = await agent.enrich(_txn("Grab", amount=35000), user_id="u1")
    print(f"\n[TAGGING] Grab:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
    assert result["category_name"] in VALID_CATEGORIES
    assert result["category_name"] == "Di chuyển"


async def test_shopee_categorized_as_shopping(agent):
    result = await agent.enrich(_txn("Shopee", amount=250000), user_id="u1")
    print(f"\n[TAGGING] Shopee:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
    assert result["category_name"] in VALID_CATEGORIES
    assert result["category_name"] == "Mua sắm"


async def test_electric_bill_categorized(agent):
    result = await agent.enrich(_txn("EVN HCMC", amount=500000), user_id="u1")
    print(f"\n[TAGGING] EVN HCMC:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
    assert result["category_name"] in VALID_CATEGORIES
    assert result["category_name"] == "Hóa đơn & Tiện ích"


async def test_salary_inflow_categorized(agent):
    result = await agent.enrich(
        _txn("CONG TY TNHH ABC", amount=15000000, direction="inflow"),
        user_id="u1",
    )
    print(f"\n[TAGGING] Salary Inflow:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
    assert result["category_name"] in VALID_CATEGORIES
    assert result["category_name"] in ("Thu nhập", "Chuyển khoản")


async def test_result_always_has_tags_list(agent):
    """Tags should always be a list, even if empty."""
    result = await agent.enrich(_txn("Random Store"), user_id="u1")
    print(f"\n[TAGGING] Random Store:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
    assert isinstance(result["tags"], list)


async def test_unknown_merchant_returns_valid_category(agent):
    """Even unknown merchants should map to a valid category."""
    result = await agent.enrich(_txn("XYZABC123"), user_id="u1")
    print(f"\n[TAGGING] Unknown Merchant:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
    assert result["category_name"] in VALID_CATEGORIES
