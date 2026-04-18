# Feature: Conversational Finance Interface

## Summary

Interact with ChiWi via natural Vietnamese language in Telegram. Log transactions by chatting ("ăn phở 60k hôm qua"), ask spending questions, request reports, and manage budgets — all through conversation.

## User Stories

> As a user, I want to log a transaction by simply chatting in Vietnamese so that tracking spending feels effortless.

> As a user, I want to ask "tháng này chi bao nhiêu?" and get an instant answer.

> As a user, I want to send a voice message to log spending when I can't type.

## Supported Intents

| Intent | Example Input | Agent Action |
|---|---|---|
| `log_transaction` | "Ăn phở 60k hôm qua" | Parse → Tag → Store → Confirm |
| `log_transaction` | "Đổ xăng 200k" | Parse → Tag → Store → Confirm |
| `ask_balance` | "Tháng này chi bao nhiêu rồi?" | Query → Respond |
| `ask_category` | "Tuần này ăn uống hết bao nhiêu?" | Aggregate → Respond |
| `request_report` | "Báo cáo tuần" | Route to Reporting Agent |
| `set_budget` | "Đặt ngân sách cafe 500k/tuần" | Create budget → Confirm |
| `set_goal` | "Mình muốn mua lens 15 triệu" | Update profile → Confirm |
| `general_chat` | "Chào ChiWi" | Friendly response |

## Vietnamese Language Handling

### Amount Parsing

| Input | Parsed Amount |
|---|---|
| "50k" | 50,000 VND |
| "2 củ" | 2,000,000 VND |
| "trăm rưỡi" | 150,000 VND |
| "3 triệu 5" | 3,500,000 VND |
| "một xị" | 100,000 VND |

### Temporal Resolution

| Input | Resolved Date (assuming today = Apr 20) |
|---|---|
| "hôm qua" | Apr 19 |
| "hôm kia" | Apr 18 |
| "thứ 6 tuần trước" | Apr 11 |
| "đầu tháng" | Apr 1 |
| "tháng trước" | March 2026 |

## API Contract

### Telegram Webhook (handled automatically)

The Telegram Bot API sends updates to `POST /api/webhook/telegram`.

**Text message handling**:
```json
{
  "update_id": 123456,
  "message": {
    "chat": { "id": 123456789 },
    "from": { "id": 123456789 },
    "text": "Ăn phở 60k hôm qua"
  }
}
```

**Voice message handling**:
```json
{
  "update_id": 123457,
  "message": {
    "chat": { "id": 123456789 },
    "voice": {
      "file_id": "AwACAgIA...",
      "duration": 3
    }
  }
}
```

## Conversation State (Redis)

Multi-turn conversations are tracked in Redis with 30-minute TTL:

```json
{
  "chat_id": "123456789",
  "last_intent": "log_transaction",
  "pending_confirmation": null,
  "context": {
    "last_category": "food",
    "last_amount": 60000,
    "turn_count": 2
  }
}
```

## Response Format

All bot responses use Telegram HTML formatting with emoji for quick visual scanning:

```
✅ Đã ghi: -60,000₫ | 🍔 Phở | 19/04
📍 Danh mục: Ăn uống
🏷️ Tags: pho, lunch, street_food
[✏️ Sửa] [❌ Xóa]
```
