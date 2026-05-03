# ChiWi Mobile API

REST endpoints for the Android dashboard. All responses are JSON. No AI is invoked on any of these paths — every response is a direct database read or a pre-computed Redis-cached payload, so latency is fast and predictable.

The interactive Swagger UI is available at `https://<domain>/docs`.

---

## Base URL

```
https://<domain>/api/mobile
```

---

Every request must include a valid JSON Web Token (JWT) in the `Authorization` header:

```
Authorization: Bearer <jwt_token>
```

Tokens are obtained via the `/api/auth/login` endpoint. Standard JWT rules apply:
- **Access Token**: Valid for 30 minutes. Required for all `/api/mobile/*` requests.
- **Refresh Token**: Valid for 7 days. Used to obtain new access tokens.

Missing or expired tokens return **401 Unauthorized**.

---

## Common types

**Datetime** — all `datetime` fields are ISO 8601 strings in UTC, e.g. `"2026-04-29T03:00:00Z"`.

**Amounts** — all monetary amounts are in **VND** (integers after rounding).

**Direction** — `"inflow"` (money received), `"outflow"` (money spent), or `"savingflow"` (money accumulated for a goal).

**Period** values accepted by endpoints that take a `period` query param:

| Value | Meaning |
|---|---|
| `today` | From 00:00 today (ICT) to now |
| `this_week` | Monday 00:00 to now |
| `this_month` | 1st 00:00 to now |
| `last_week` | Previous Mon–Sun |
| `last_month` | Previous calendar month |
| `last_month_same_period` | From 1st of last month to the same relative day (e.g. May 10 -> April 10) |
| `last_7_days` | Rolling 7 days |
| `last_30_days` | Rolling 30 days |
| `custom` | Requires `start_date` and `end_date` query params |

**Timezone Note**: All relative periods (today, this_month, etc.) are calculated using the user's specific timezone (default: `Asia/Ho_Chi_Minh`).

---

---

## Endpoints

### `GET /dashboard`

Home-screen payload. Returns period totals, top spending categories, 5 most recent transactions, budget alerts, and upcoming subscriptions in one request.

**Cached in Redis for 5 minutes.** The cache is invalidated automatically whenever a transaction is written, deleted, or corrected.

#### Request

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <jwt_token>` |

No query parameters.

#### Response `200`

```json
{
  "computed_at": "2026-04-29T03:00:00Z",
  "is_cached": true,
  "periods": {
    "today": 150000,
    "yesterday": 120000,
    "this_week": 1200000,
    "last_week_same_period": 1100000,
    "this_month": 8000000,
    "last_month_same_period": 7500000
  },
  "top_categories": [
    { "name": "Ăn uống", "icon": "🍔", "amount": 1800000, "tx_count": 21 },
    { "name": "Di chuyển", "icon": "🚗", "amount": 920000, "tx_count": 14 }
  ],
  "recent_transactions": [
    {
      "id": "6630e1a2b4e9f00012345678",
      "amount": 45000,
      "direction": "outflow",
      "merchant": "Highlands Coffee",
      "category": "Cafe",
      "icon": "☕",
      "note": "",
      "timestamp": "2026-04-29T02:31:00Z",
      "locked": false,
      "source": "android"
    }
  ],
  "budget_alerts": [
    {
      "category": "Ăn uống",
      "icon": "🍔",
      "spent": 1800000,
      "limit": 2000000,
      "percent_used": 90
    }
  ],
  "upcoming_subscriptions": [
    { 
      "name": "Netflix", 
      "amount": 260000, 
      "next_charge_date": "2026-05-02T00:00:00Z",
      "due_in_days": 1 
    }
  ],
  "just_paid_subscriptions": [
    {
      "name": "Spotify",
      "amount": 59000,
      "paid_at": "2026-04-30T10:15:00Z"
    }
  ]
}
```

| Field | Description |
|---|---|
| `is_cached` | `true` if served from Redis cache, `false` if freshly computed |
| `periods` | Stats for `today`, `this_week`, and `this_month` |
| `top_categories` | Up to 5 highest-spend outflow categories this month |
| `recent_transactions` | 5 most recent transactions regardless of period |
| `upcoming_subscriptions` | Active subscriptions due within the next 3 days |
| `just_paid_subscriptions` | Subscriptions confirmed/paid within the last 3 days |
| `budget_alerts` | Budgets where `percent_used ≥ 80` |

---

### `GET /transactions`

Paginated transaction list with optional filters.

#### Request

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <jwt_token>` |

| Query param | Type | Default | Description |
|---|---|---|---|
| `period` | string | `null` | **Primary Filter**. See period table. Defines the absolute boundaries for the list. |
| `start_date` | string | — | ISO8601 date. Overrides `period`. Defines the absolute start boundary. |
| `end_date` | string | — | ISO8601 date. Overrides `period`. Defines the absolute end boundary. |
| `offset_days` | int | `0` | **Sliding Window Offset**. Days to look back from *now*. Used for batch-loading within the filter boundaries. |
| `window_size` | int | `7` | **Sliding Window Size**. The size of the time block in days. |
| `limit` | int | `20` | Max items per page *within* a time block. |
| `cursor` | string | — | `id` for next page *within* the same time block. |
| `goal_id` | string | — | Filter by specific goal ID. |

#### Response `200`

```json
{
  "transactions": [
    {
      "id": "6630e1a2b4e9f00012345678",
      "amount": 45000,
      "direction": "outflow",
      "merchant": "Highlands Coffee",
      "category": "Cafe",
      "icon": "☕",
      "timestamp": "2026-05-01T02:31:00Z",
      "locked": false,
      "source": "android",
      "goal_id": "6630d002b4e9f00012340002"
    }
  ],
  "next_cursor": "6630e0c1b4e9f00012345670",
  "next_offset_days": 0,
  "total_in_period": 47
}
```

| Field | Description |
|---|---|
| `next_cursor` | Cursor for pagination *within the current time block*. |
| `next_offset_days` | Use this as `offset_days` in the next call if `next_cursor` is null. `null` means no more blocks in the filter. |
| `total_in_period` | Total items matching the *Filter Range* (not just the window). |

#### How Pagination Works (Intersection Logic)

The API calculates the intersection of your **Filter Range** (e.g., `this_month`) and the **Sliding Window** (e.g., `last 7 days`).

1. **Within a block**: If a 7-day block has 50 transactions and `limit=20`, use `next_cursor` to fetch all 50.
2. **Between blocks**: When `next_cursor` is `null`, use `next_offset_days` to fetch the next 7-day block.
3. **Boundary Check**: If the next block falls entirely outside the `period` (e.g., you are filtering `this_month` and scroll into last month), `next_offset_days` will be `null`.

#### Example: Lazy Load within "This Month" (Assume today is May 15)

1. **Load first 7 days of May**:
   `GET /api/mobile/transactions?period=this_month&offset_days=0&window_size=7`
   → Returns transactions from May 8 to May 15.

2. **Load next 7 days of May**:
   `GET /api/mobile/transactions?period=this_month&offset_days=7&window_size=7`
   → Returns transactions from May 1 to May 8.

3. **Try to load more**:
   `GET /api/mobile/transactions?period=this_month&offset_days=14&window_size=7`
   → Returns `transactions: []` and `next_offset_days: null` because April is outside "this_month".

---

### `GET /budgets`

Active budgets with current spend versus limit for the ongoing budget cycle.

#### Request

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <jwt_token>` |

No query parameters.

#### Response `200`

```json
{
  "budgets": [
    {
      "id": "6630d001b4e9f00012340001",
      "category": "Ăn uống",
      "icon": "🍔",
      "period": "monthly",
      "limit": 2000000,
      "spent": 1800000,
      "remaining": 200000,
      "percent_used": 90,
      "window_start": "2026-04-01T00:00:00Z",
      "window_end": "2026-04-30T23:59:59Z",
      "alert_enabled": true
    }
  ]
}
```

| Field | Description |
|---|---|
| `period` | `"weekly"`, `"monthly"`, or `"yearly"` |
| `limit` | Effective limit for the current cycle (may differ from the base limit if a temporary override is active) |
| `window_start` / `window_end` | UTC bounds of the current budget cycle |
| `alert_enabled` | `false` if the user silenced nudge alerts for this budget |

---

### `GET /goals`

Active savings goals with progress tracking.

#### Request

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <jwt_token>` |

No query parameters.

#### Response `200`

```json
{
  "goals": [
    {
      "id": "6630d002b4e9f00012340002",
      "name": "Máy ảnh Fujifilm X100VI",
      "category": "Hobbies",
      "icon": "📸",
      "target_amount": 20000000,
      "saved_amount": 8000000,
      "percent_achieved": 40,
      "monthly_needed": 2000000,
      "deadline": "2026-10-01T00:00:00Z",
      "on_track": true,
      "status": "active"
    }
  ]
}
```

| Field | Description |
|---|---|
| `monthly_needed` | Amount to save per month to hit the goal by the deadline. `null` if no deadline is set. |
| `on_track` | `true` if current savings pace meets the deadline target. |
| `percent_achieved` | Capped at 100 even if `saved_amount > target_amount`. |
| `status` | `"active"`, `"achieved"`, `"cancelled"` |

---

### `POST /goals`

Create a new savings goal.

#### Request

```json
{
  "name": "Mua xe mới",
  "target_amount": 50000000,
  "deadline": "2027-01-01T00:00:00Z",
  "category": "Tiết kiệm",
  "icon": "🚗"
}
```

#### Response `200`

Returns the created `MobileGoalItem`.

---

### `PATCH /goals/{id}`

Update an existing goal. Accepts any subset of fields.

#### Request

```json
{
  "target_amount": 55000000,
  "status": "active"
}
```

#### Response `200`

Returns the updated `MobileGoalItem`.

---

### `DELETE /goals/{id}`

Delete a goal.

#### Response `200`

```json
{ "status": "ok" }
```

---

### `POST /goals/{id}/accumulate`

Manually record an accumulation (saving) for a specific goal. This creates a `savingflow` transaction and updates the goal progress.

#### Request

```json
{
  "amount": 500000
}
```

#### Response `200`

Returns the updated `MobileGoalItem`.

---

### `GET /subscriptions`

Active recurring subscriptions with next charge date and a monthly cost summary.

#### Request

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <jwt_token>` |

No query parameters.

#### Response `200`

```json
{
  "subscriptions": [
    {
      "id": "6630d003b4e9f00012340003",
      "name": "Netflix",
      "amount": 260000,
      "period": "monthly",
      "next_charge_date": "2026-05-02T00:00:00Z",
      "due_in_days": 3,
      "is_overdue": false
    },
    {
      "id": "6630d004b4e9f00012340004",
      "name": "Spotify",
      "amount": 59000,
      "period": "monthly",
      "next_charge_date": "2026-04-28T00:00:00Z",
      "due_in_days": -1,
      "is_overdue": true
    }
  ],
  "monthly_total": 319000
}
```

| Field | Description |
|---|---|
| `due_in_days` | Days until next charge. Negative means overdue. |
| `is_overdue` | `true` if `next_charge_date` is in the past and no payment has been recorded. |
| `monthly_total` | Sum of all subscriptions normalised to a monthly equivalent (weekly × 4.33, yearly ÷ 12). |

---

### `GET /nudges`

Recent AI nudges (financial insights and behaviour tips) sent by the system in the last 30 days.

#### Request

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <jwt_token>` |

| Query param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | `20` | Max nudges to return, 1–50 |

#### Response `200`

```json
{
  "nudges": [
    {
      "id": "6630d005b4e9f00012340005",
      "type": "spending_spike",
      "body": "Tuần này bạn tiêu cafe nhiều hơn 40% so với trung bình. Bằng nửa cuộn Kodak Portra đấy! ☕📷",
      "sent_at": "2026-04-28T01:00:00Z"
    }
  ]
}
```

| Field | Description |
|---|---|
| `type` | Nudge category: `spending_spike`, `budget_warning`, `goal_milestone`, `subscription_reminder`, `impulse_check`, `saving_streak` |
| `body` | Full nudge message in Vietnamese. |

---

### `GET /categories/spending`

Category breakdown for a period — suitable for pie charts and bar charts.

#### Request

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <jwt_token>` |

| Query param | Type | Default | Description |
|---|---|---|---|
| `period` | string | `this_month` | See period table above |
| `start_date` | string | — | ISO8601 date (overrides period) |
| `end_date` | string | — | ISO8601 date (overrides period) |


#### Response `200`

```json
{
  "period": "this_month",
  "total_outflow": 4320000,
  "breakdown": [
    { "name": "Ăn uống", "icon": "🍔", "amount": 1800000, "tx_count": 21, "percent": 41.7 },
    { "name": "Di chuyển", "icon": "🚗", "amount": 920000, "tx_count": 14, "percent": 21.3 },
    { "name": "Cafe",      "icon": "☕", "amount": 600000, "tx_count":  9, "percent": 13.9 }
  ]
}
```

Results are sorted by `amount` descending. Only **outflow** transactions are counted. `percent` values sum to 100.

---

### `POST /chat`

Natural-language chat endpoint. The Android app sends free-form text and receives structured JSON — identical behaviour to the Telegram chat but without Telegram as the transport.

This is an **AI endpoint**: it invokes the Orchestrator pipeline (Conversational Agent → Tagging Agent → Store) so latency depends on Gemini API response time (~200–800ms).

#### Request

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <jwt_token>` |

```json
{
  "message": "Ăn phở 60k hôm qua"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `message` | string | Yes | Free-form Vietnamese text. Same inputs as Telegram: log expenses, ask balance, request reports, set budgets, etc. |

#### Response `200`

```json
{
  "status": "stored",
  "intent": "log_transaction",
  "response_text": "✅ Đã ghi: -60,000đ | Ăn uống | Phở",
  "transaction_id": "6630e1a2b4e9f00012345678",
  "actions": [
    {
      "label": "🗑️ Xoá",
      "action": "delete_confirm",
      "payload": { "id": "6630e1a2b4e9f00012345678" }
    },
    {
      "label": "✅ Xác nhận",
      "action": "confirm_txn",
      "payload": { "id": "6630e1a2b4e9f00012345678" }
    }
  ]
}
```

| Field | Description |
|---|---|
| `status` | `"stored"` (transaction saved), `"chat_processed"` (query answered), `"error"` |
| `intent` | Detected intent: `log_transaction`, `ask_balance`, `request_report`, `request_analysis`, `set_budget`, `ask_budget`, `set_goal`, `set_subscription`, etc. `null` if not classified. |
| `response_text` | Vietnamese response text ready to display in the app. May contain HTML formatting tags (`<b>`, `<i>`). |
| `transaction_id` | Present only when `intent` = `log_transaction` and the transaction was stored successfully. |
| `actions` | Action buttons the app can render. Each has a `label` (display text), `action` (machine ID), and `payload` (data for the action). Empty array when no actions are applicable. |

#### Example messages

| User message | Intent | What happens |
|---|---|---|
| `"Ăn phở 60k hôm qua"` | `log_transaction` | Parses and stores a 60k outflow transaction |
| `"Đầu tư 10tr vào cổ phiếu"` | `log_accumulation` | Adds 10M to the "cổ phiếu" goal as a `savingflow` |
| `"Tháng này chi bao nhiêu?"` | `ask_balance` | Returns income/expense/net for the current month |
| `"Báo cáo tuần này"` | `request_report` | Generates an AI-powered weekly spending report |
| `"Đặt ngân sách ăn uống 3 triệu"` | `set_budget` | Creates a monthly 3M budget for food |
| `"Cafe tuần này so với bình thường?"` | `ask_spending_vs_avg` | Compares current spending vs historical average |

---

### `GET /export`

Export user transaction data in structured format.

#### Request

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <jwt_token>` |

| Query param | Type | Default | Description |
|---|---|---|---|
| `format` | string | `csv` | `csv` or `json` |
| `period` | string | `this_month` | See period table |

#### Response `200`

- If `format=csv`: Returns a downloadable CSV file.
- If `format=json`: Returns a JSON array of transaction records.

---

### `POST /reports`

Manually trigger an AI report generation for a specific period.

#### Request

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <jwt_token>` |

```json
{
  "report_type": "weekly_summary",
  "period": "2026-W16"
}
```

#### Response `200`

Returns the generated report object (same as standard `/chat` response for reports).

---

### `POST /analysis`

Manually trigger an AI financial analysis (e.g., spending trends).

#### Request

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <jwt_token>` |

```json
{
  "analysis_type": "spending_trends",
  "period": "this_month"
}
```

#### Response `200`

Returns the generated analysis object.

---

### `GET /profile`

Retrieve the current user's profile and personalization settings.

#### Response `200`

```json
{
  "display_name": "Nguyen Quy Huy",
  "occupation": "Senior DevOps Engineer",
  "hobbies": ["film_photography", "coffee"],
  "communication_tone": "friendly",
  "timezone": "Asia/Ho_Chi_Minh"
}
```

---

### `PATCH /profile`

Update user profile settings. Accepts any subset of fields.

#### Request

Accepts any subset of fields from the `GET /profile` response.

#### Response `200`

Returns the updated profile.

---

### `DELETE /user`

**DANGER: Permanent Account Deletion.**

Triggers the cascading delete of all user data (Transactions, Budgets, Goals, Subscriptions, Nudges, Profile). This action is irreversible.

#### Response `200`

```json
{ "status": "success", "message": "All user data has been permanently deleted" }
```

---

### `POST /analyze-notification`

Analyze a raw notification text using the Ingestion Agent without saving it. This allows the mobile app to show a preview/confirmation dialog to the user before storing the transaction.

#### Request

```json
{
  "package_name": "com.vietcombank.mobile",
  "text": "Vietcombank: TK 123*****890 -100,000 VND. So du: 5,000,000 VND. 29/04/2026 09:31"
}
```

#### Response `200`

```json
{
  "is_transaction": true,
  "amount": 100000,
  "merchant": "Vietcombank",
  "category": "Ăn uống",
  "currency": "VND"
}
```

---

### `POST /approve-pending`

Save a transaction that was previously analyzed and confirmed by the user in the mobile UI.

#### Request

```json
{
  "package_name": "com.vietcombank.mobile",
  "raw_text": "Vietcombank: TK 123*****890 -100,000 VND. So du: 5,000,000 VND. 29/04/2026 09:31",
  "amount": 100000,
  "merchant": "Vietcombank",
  "category": "Ăn uống",
  "note": "Ăn trưa"
}
```

#### Response `200`

```json
{
  "status": "ok",
  "transaction_id": "6630e1a2b4e9f00012345678"
}
```

---

## Error responses

| Status | When |
|---|---|
| `400 Bad Request` | Unsupported `period` value |
| `401 Unauthorized` | Missing, expired, or invalid JWT |
| `500 Internal Server Error` | Unexpected server error |

All error bodies follow:

```json
{ "detail": "human-readable message" }
```

---

## Notification webhook (Android → Server)

This endpoint is used by the Android app to forward raw bank notification text. It is **not** a dashboard read — it triggers the AI ingestion pipeline server-side.

### `POST /api/webhook/notification`

#### Request

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <jwt_token>` |

```json
{
  "raw_text": "Vietcombank: TK 123*****890 -100,000 VND. So du: 5,000,000 VND. 29/04/2026 09:31",
  "bank_hint": "Vietcombank",
  "timestamp": "2026-04-29T02:31:00Z"
}
```

| Field | Required | Description |
|---|---|---|
| `raw_text` | Yes | Raw notification text exactly as shown on the phone |
| `bank_hint` | No | Bank name hint to improve parsing accuracy |
| `timestamp` | Yes | ISO 8601 datetime when the notification appeared on the device |

#### Response `200`

```json
{ "status": "queued" }
```

The response is returned immediately (the AI processing happens in the background). The user sees a Telegram confirmation message when parsing is complete.

---

## Caching notes

- `GET /dashboard` is cached in Redis per user for **5 minutes**. `is_cached: true` in the response indicates a cache hit. The cache is proactively invalidated on every transaction write, delete, or correction — so the dashboard is always fresh after any data change, not just after the TTL expires.
- All other endpoints query MongoDB directly on every request. For list endpoints with large datasets, use the `limit` and `cursor` params to keep response sizes manageable.

---

### Auth & Profile

#### `POST /api/mobile/logout`
Logs out the current user and invalidates the session.

**Response `200`**
```json
{
  "status": "success",
  "message": "Logged out successfully"
}
```

#### `GET /api/mobile/profile`
Retrieves the user's personalization settings.

**Response `200`**
```json
{
  "occupation": "Software Engineer",
  "hobbies": ["Coding", "Gaming"],
  "interests": ["Finance", "AI"],
  "communication_tone": "friendly",
  "assistant_personality": "encouraging",
  "nudge_frequency": "daily",
  "language": "vi",
  "timezone": "Asia/Ho_Chi_Minh",
  "chat_id": "12345678"
}
```

#### `PATCH /api/mobile/profile`
Partially updates profile fields.

**Request Body**
Any fields from the profile response can be sent.
```json
{
  "assistant_personality": "strict",
  "occupation": "Freelancer"
}
```

**Response `200`** (Updated profile object)

#### `POST /api/auth/register`
Creates a new user identity and default profile.

**Request Body**
```json
{
  "username": "nqhuy44",
  "password": "secure_password",
  "full_name": "Nguyen Quy Huy",
  "email": "huy@example.com"
}
```

**Response `200`**
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "user_id": "uuid-v4-string"
}
```

#### `DELETE /api/mobile/user`
Permanently delete user account and all related data (GDPR compliant).

**Response `200`**
```json
{
  "status": "success",
  "message": "All user data has been permanently deleted"
}
```

#### `POST /api/auth/request-reset`
Request a password reset code sent to the user's email.

**Request Body**
```json
{
  "email": "huy@example.com"
}
```

**Response `200`**
```json
{
  "message": "If that email is registered, a reset code has been sent."
}
```

#### `POST /api/auth/confirm-reset`
Confirm the reset code and update the password.

**Request Body**
```json
{
  "email": "huy@example.com",
  "code": "123456",
  "new_password": "new_secure_password"
}
```

**Response `200`**
```json
{
  "message": "Password has been successfully reset."
}
```
