# ChiWi — Database Design

## Overview

ChiWi uses **MongoDB** as primary data store and **Redis** for ephemeral state. MongoDB's schema-less nature handles unpredictable AI-generated metadata (dynamic tags, sentiment scores, behavioral flags).

## Entity Relationship Diagram

```mermaid
erDiagram
    USER ||--o{ TRANSACTION : "owns"
    USER ||--o{ BUDGET : "sets"
    USER ||--|| USER_PROFILE : "has"
    TRANSACTION }o--|| CATEGORY : "classified_as"
    TRANSACTION ||--o{ TAG : "has"
    USER ||--o{ NUDGE : "receives"
    USER ||--o{ REPORT : "generated_for"

    USER {
        ObjectId _id PK
        string telegram_user_id UK
        string telegram_chat_id
        string display_name
        datetime created_at
    }

    USER_PROFILE {
        ObjectId _id PK
        ObjectId user_id FK
        string occupation
        list hobbies
        dict financial_goals
        float monthly_income
        string currency
    }

    TRANSACTION {
        ObjectId _id PK
        ObjectId user_id FK
        string source
        float amount
        string currency
        string direction
        string raw_text
        string merchant_name
        ObjectId category_id FK
        list tags
        datetime transaction_time
        string agent_confidence
        bool user_corrected
        dict ai_metadata
    }

    CATEGORY {
        ObjectId _id PK
        string name
        string icon_emoji
        string parent_category
        bool is_system
    }

    BUDGET {
        ObjectId _id PK
        ObjectId user_id FK
        ObjectId category_id FK
        float limit_amount
        string period
    }

    NUDGE {
        ObjectId _id PK
        ObjectId user_id FK
        string nudge_type
        string message
        bool was_read
        bool user_acted
        datetime sent_at
    }

    REPORT {
        ObjectId _id PK
        ObjectId user_id FK
        string report_type
        string period
        dict data
        datetime generated_at
    }
```

## Collections Detail

### `users`

Primary user record linked to Telegram identity.

| Field | Type | Description |
|---|---|---|
| `_id` | ObjectId | Primary key |
| `telegram_user_id` | string | **Unique**. Telegram user ID for auth |
| `telegram_chat_id` | string | Telegram chat ID for messaging |
| `display_name` | string | User display name |
| `created_at` | datetime | Account creation timestamp |
| `updated_at` | datetime | Last update timestamp |

**Indexes**: `telegram_user_id` (unique)

---

### `user_profiles`

Extended user context consumed by the Behavioral Agent.

| Field | Type | Description |
|---|---|---|
| `user_id` | ObjectId | FK → `users` (unique) |
| `occupation` | string | e.g., "DevOps Engineer" |
| `hobbies` | list | e.g., `["film_photography", "coffee"]` |
| `financial_goals` | dict | Target amounts per goal |
| `monthly_income` | float | Estimated monthly income |
| `currency` | string | Default: "VND" |
| `preferences` | dict | Nudge frequency, report day, language |

---

### `transactions`

Core financial data. Immutable after creation.

| Field | Type | Description |
|---|---|---|
| `user_id` | ObjectId | FK → `users` |
| `source` | string | `notification` / `chat` / `voice` / `manual` |
| `amount` | float | Transaction amount |
| `currency` | string | e.g., "VND" |
| `direction` | string | `inflow` / `outflow` |
| `raw_text` | string | Original unprocessed text |
| `merchant_name` | string | AI-extracted merchant |
| `category_id` | ObjectId | FK → `categories` |
| `tags` | list | AI-generated tags: `["cafe", "morning"]` |
| `transaction_time` | datetime | When the transaction occurred |
| `created_at` | datetime | When the record was created |
| `agent_confidence` | string | `high` / `medium` / `low` |
| `user_corrected` | bool | Whether user corrected AI classification |
| `ai_metadata` | dict | Agent processing details |

**Indexes**:
- `user_id` + `transaction_time` (compound, primary query pattern)
- `user_id` + `category_id` (compound, aggregation)
- `merchant_name` (text index)

---

### `categories`

System-defined and user-customizable spending categories.

| Emoji | Name | Parent |
|---|---|---|
| 🍔 | Food & Beverage | — |
| ☕ | Cafe | Food & Beverage |
| 🚗 | Transportation | — |
| 🛒 | Shopping | — |
| 🏠 | Housing | — |
| 💡 | Utilities | Housing |
| 🎬 | Entertainment | — |
| 📸 | Hobbies | — |
| 💊 | Health | — |
| 📚 | Education | — |
| 💰 | Income | — |
| 🔄 | Transfer | — |
| ❓ | Uncategorized | — |

---

### `budgets`

Spending limits per category per time period.

| Field | Type | Description |
|---|---|---|
| `user_id` | ObjectId | FK → `users` |
| `category_id` | ObjectId | FK → `categories` |
| `limit_amount` | float | Budget limit |
| `period` | string | `weekly` / `monthly` |
| `start_date` | datetime | Period start |
| `end_date` | datetime | Period end |

---

### `nudges`

Record of every proactive message sent by the Behavioral Agent.

| Field | Type | Description |
|---|---|---|
| `user_id` | ObjectId | FK → `users` |
| `nudge_type` | string | `spending_alert`, `budget_exceeded`, `goal_progress`, `saving_streak`, `subscription_reminder` |
| `message` | string | The nudge text sent to user |
| `trigger_reason` | string | Why this nudge was triggered |
| `was_read` | bool | Whether user saw it |
| `user_acted` | bool | Whether user changed behavior |
| `sent_at` | datetime | When sent |

---

### `reports`

Generated financial reports cached for re-access.

| Field | Type | Description |
|---|---|---|
| `user_id` | ObjectId | FK → `users` |
| `report_type` | string | `daily_summary`, `weekly_summary`, `monthly_report`, `goal_progress` |
| `period` | string | e.g., "2026-W16", "2026-04" |
| `data` | dict | Full report payload |
| `generated_at` | datetime | Generation timestamp |

---

## Redis Key Schema

All keys prefixed with `chiwi:`.

| Key Pattern | Type | TTL | Purpose |
|---|---|---|---|
| `chiwi:session:{chat_id}` | Hash | 30 min | Conversation state & context |
| `chiwi:agent_state:{chat_id}` | JSON | 10 min | LangGraph agent checkpoint |
| `chiwi:rate_limit:{user_id}` | Counter | 1 min | API rate limiting |
| `chiwi:pending_confirm:{txn_id}` | Hash | 5 min | Transaction awaiting confirmation |
| `chiwi:daily_stats:{user_id}:{date}` | Hash | 24 hr | Cached daily spending |
| `chiwi:merchant_cache:{merchant}` | String | 7 days | Merchant → category cache |

## Migration Strategy

Migrations handled at the application level via versioned scripts in `scripts/migrations/`. Each migration is idempotent and tracked in a `_migrations` collection.
