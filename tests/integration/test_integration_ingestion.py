"""
Integration tests — IngestionAgent with REAL Gemini API.

These tests call the actual Gemini Flash API to verify parsing quality
on real Vietnamese bank notification formats.

Run:  make test-integration
Skip: make test  (unit tests only, no API calls)

Requires: GEMINI_API_KEY set in .env
"""

import json
import os

import pytest

from src.agents.ingestion import IngestionAgent
from src.services.gemini import GeminiService

# Skip entire module if no API key
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("GEMINI_API_KEY", ""),
        reason="GEMINI_API_KEY not set — skipping integration tests",
    ),
]


@pytest.fixture
def gemini():
    """Real GeminiService — fresh per test to avoid event loop conflicts."""
    svc = GeminiService()
    svc.initialize()
    return svc


@pytest.fixture
def agent(gemini):
    return IngestionAgent(gemini)


# ─── Vietcombank (VCB) ───────────────────────────────────────


async def test_vcb_outflow(agent):
    """Standard VCB outflow notification."""
    result = await agent.parse(
        "VCB: GD: -500,000VND tai Highlands Coffee luc 14:30 20/10/2024. "
        "SD: 5,000,000VND"
    )
    print(f"\n[PARSED] VCB Outflow:\n{result.model_dump_json(indent=2)}")
    
    assert result.is_transaction is True
    assert result.amount == 500_000
    assert result.direction == "outflow"
    assert result.currency == "VND"
    # AI should detect the merchant name
    assert result.merchant_name is not None
    assert "highlands" in result.merchant_name.lower() or "coffee" in result.merchant_name.lower()
    assert result.confidence in ("high", "medium")


async def test_vcb_inflow(agent):
    """VCB inflow (salary transfer)."""
    result = await agent.parse(
        "VCB: GD: +15,000,000VND tu CONG TY TNHH ABC luc 09:00 01/11/2024. "
        "SD: 20,000,000VND"
    )
    print(f"\n[PARSED] VCB Inflow:\n{result.model_dump_json(indent=2)}")
    assert result.is_transaction is True
    assert result.amount == 15_000_000
    assert result.direction == "inflow"


# ─── Techcombank (TCB) ───────────────────────────────────────


async def test_tcb_outflow(agent):
    """TCB transfer notification."""
    result = await agent.parse(
        "TCB: TK 19035xxx giao dich -200,000VND tai GRAB luc 18:45 15/10/2024. "
        "SD: 3,500,000VND"
    )
    print(f"\n[PARSED] TCB Outflow:\n{result.model_dump_json(indent=2)}")
    assert result.is_transaction is True
    assert result.amount == 200_000
    assert result.direction == "outflow"
    assert result.merchant_name is not None
    assert "grab" in result.merchant_name.lower()


# ─── MB Bank ─────────────────────────────────────────────────


async def test_mb_outflow(agent):
    """MB Bank shorthand notification."""
    result = await agent.parse(
        "MB Bank: Ban vua thuc hien GD -85,000VND tai THE COFFEE HOUSE. "
        "So du: 1,200,000VND"
    )
    print(f"\n[PARSED] MB Outflow:\n{result.model_dump_json(indent=2)}")
    assert result.is_transaction is True
    assert result.amount == 85_000
    assert result.direction == "outflow"
    assert result.bank_name is not None
    assert "mb" in result.bank_name.lower()


# ─── MoMo ────────────────────────────────────────────────────


async def test_momo_outflow(agent):
    """MoMo payment notification."""
    result = await agent.parse(
        "MoMo: Giao dich thanh toan thanh cong 50,000đ tai Cua hang tien loi Circle K. "
        "Ma GD: 123456789. So du Vi: 1,000,000đ."
    )
    print(f"\n[PARSED] MoMo Outflow:\n{result.model_dump_json(indent=2)}")
    assert result.is_transaction is True
    assert result.amount == 50_000
    assert result.direction == "outflow"
    assert result.merchant_name is not None
    assert "circle k" in result.merchant_name.lower()
    assert result.bank_name is not None
    assert "momo" in result.bank_name.lower()


async def test_momo_inflow(agent):
    """MoMo peer-to-peer transfer receipt."""
    result = await agent.parse(
        "MoMo: Ban vua nhan duoc 100,000đ tu Nguyen Van A. Loi nhan: Tien an trua. "
        "So du Vi: 1,100,000đ."
    )
    print(f"\n[PARSED] MoMo Inflow:\n{result.model_dump_json(indent=2)}")
    assert result.is_transaction is True
    assert result.amount == 100_000
    assert result.direction == "inflow"
    assert result.merchant_name is not None
    assert "nguyen van a" in result.merchant_name.lower()
    assert result.bank_name is not None
    assert "momo" in result.bank_name.lower()


# ─── Non-transaction messages ────────────────────────────────


async def test_otp_message_rejected(agent):
    """OTP / promo messages must NOT be classified as transactions."""
    result = await agent.parse(
        "VCB: Ma OTP cua ban la 123456. KHONG chia se cho bat ky ai."
    )
    print(f"\n[PARSED] OTP Message:\n{result.model_dump_json(indent=2)}")
    assert result.is_transaction is False


async def test_promo_sms_rejected(agent):
    """Promotional SMS from bank."""
    result = await agent.parse(
        "VPBank: Uu dai BLACK FRIDAY giam 50% khi thanh toan qua the. "
        "Chi tiet tai vpbank.com.vn"
    )
    print(f"\n[PARSED] Promo SMS:\n{result.model_dump_json(indent=2)}")
    assert result.is_transaction is False


# ─── Edge cases ──────────────────────────────────────────────


async def test_amount_without_currency_suffix(agent):
    """Some banks don't include VND suffix."""
    result = await agent.parse(
        "ACB: GD -1,500,000 tai SHOPEE luc 22:10 05/10/2024. SD 8,000,000"
    )
    print(f"\n[PARSED] No Currency Suffix:\n{result.model_dump_json(indent=2)}")
    assert result.is_transaction is True
    assert result.amount == 1_500_000
    assert result.direction == "outflow"


async def test_large_amount_millions(agent):
    """Large transfer — rent payment."""
    result = await agent.parse(
        "VCB: GD: -7,500,000VND; ND: Tien nha thang 11. SD: 12,500,000VND"
    )
    print(f"\n[PARSED] Large Amount:\n{result.model_dump_json(indent=2)}")
    assert result.is_transaction is True
    assert result.amount == 7_500_000
    assert result.direction == "outflow"


async def test_balance_only_not_transaction(agent):
    """Balance inquiry notification is not a transaction."""
    result = await agent.parse(
        "VCB: So du TK 0451000xxx cua ban la 25,000,000VND tai 14:30 20/10/2024"
    )
    print(f"\n[PARSED] Balance Check:\n{result.model_dump_json(indent=2)}")
    # Balance check is NOT a real transaction (no money in/out)
    assert result.is_transaction is False
