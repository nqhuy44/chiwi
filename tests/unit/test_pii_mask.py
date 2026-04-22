"""Tests for PII masking — must preserve transaction amounts."""

from src.api.middleware.pii_mask import mask_pii


def test_mask_preserves_vnd_amount():
    """PII mask must NOT strip VND amounts (this was a bug)."""
    text = "VCB: -500,000VND; 14:30 20/10/24; SD: 10,250,000VND"
    masked = mask_pii(text)
    assert "500,000" in masked
    assert "10,250,000" in masked


def test_mask_account_number_with_prefix():
    """Account numbers prefixed with TK/STK should be masked."""
    text = "TCB: TK 1234567890 giao dich -100,000VND"
    masked = mask_pii(text)
    assert "1234567890" not in masked
    assert "100,000" in masked
    assert "***ACCOUNT***" in masked


def test_mask_phone_number():
    text = "Lien he 0912345678 de biet them"
    masked = mask_pii(text)
    assert "0912345678" not in masked
    assert "***PHONE***" in masked


def test_mask_card_number():
    text = "The 1234-5678-9012-3456 giao dich"
    masked = mask_pii(text)
    assert "1234-5678-9012-3456" not in masked
    assert "***CARD***" in masked


def test_mask_preserves_date():
    """Dates like 20/10/24 must not be mangled."""
    text = "Giao dich luc 14:30 20/10/24"
    masked = mask_pii(text)
    assert "20/10/24" in masked
    assert "14:30" in masked
