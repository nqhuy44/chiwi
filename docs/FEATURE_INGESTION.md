# Feature: Auto Transaction Ingestion

## Summary

Automatically captures bank transaction notifications from Android (MacroDroid/Tasker) and iOS (Shortcuts) devices, parses them using Gemini AI, and stores structured financial data — all with zero manual input.

## User Story

> As a user, I want my bank notifications to be automatically captured and logged so that I never have to manually record a transaction.

## How It Works

1. **Android**: MacroDroid/Tasker listens for notifications from bank apps → sends HTTP POST to ChiWi webhook.
2. **iOS**: Shortcuts automation triggers on bank SMS → sends content to ChiWi API via "Get Contents of URL".
3. **Gateway**: Validates `user_id`, masks PII (account numbers), forwards to Orchestrator.
4. **Ingestion Agent**: Gemini Flash extracts amount, merchant, time, direction from raw text.
5. **Tagging Agent**: Classifies category, generates tags based on historical context.
6. **Confirmation**: Telegram bot sends silent confirmation with "Edit" button.

## API Contract

### `POST /api/webhook/notification`

**Headers**:
```
X-User-Id: <telegram_user_id>
Content-Type: application/json
```

**Request Body**:
```json
{
  "source": "macrodroid",
  "app_package": "com.VCB",
  "notification_title": "Biến động số dư",
  "notification_text": "VCB: -100.000VND; 14:30 20/04/26; SD: 10.250.000; ND: highlands coffee",
  "timestamp": "2026-04-20T14:30:00+07:00"
}
```

**Response** (200):
```json
{
  "status": "saved",
  "transaction_id": "663f...",
  "parsed": {
    "amount": 100000,
    "direction": "outflow",
    "merchant": "Highlands Coffee",
    "category": "☕ Cafe",
    "confidence": "high"
  }
}
```

## Supported Bank Formats

| Bank | Format Example |
|---|---|
| Vietcombank (VCB) | `VCB: -100.000VND; 14:30 20/04; SD: 10.250.000; ND: ...` |
| Techcombank (TCB) | `TCB: TK 1234xxxx; GD: -100,000 VND; ...` |
| MB Bank | `MB: GD -100.000d TK ...xxxx luc 14:30 20/04` |
| ACB | `ACB: TK ...xxxx giam 100,000 VND ...` |
| TPBank | `TPBank: -100,000 VND tai Highlands ...` |

The Ingestion Agent handles format variations via LLM understanding rather than rigid regex.

## Error Scenarios

| Scenario | Handling |
|---|---|
| Non-financial notification | Agent returns `is_transaction: false`, silently ignored |
| Duplicate (same amount + 5 min window) | Prompt user: "Giao dịch trùng? Xác nhận?" |
| Low confidence parse | Send with ⚠️ warning + Edit button |
| Webhook auth failure | Return 401, log attempt |

## Setup Guide (Android — MacroDroid)

1. Install MacroDroid from Play Store
2. Create macro: **Trigger** → Notification Received → Select bank apps
3. **Action** → HTTP Request → POST to `https://<your-server>/api/webhook/notification`
4. Set JSON body with `%notification_title%` and `%notification_text%` variables
5. Disable battery optimization for MacroDroid
