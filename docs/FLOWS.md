# ChiWi — Business Logic Flows

## 1. Transaction Ingestion Flow (Android → Stored Transaction)

The Android app is a **sensor only** — it captures the raw notification text and forwards it verbatim. All AI parsing happens server-side so bank format changes are fixed with a backend deploy, not a mobile release.

```mermaid
sequenceDiagram
    participant Android as 📱 Android App
    participant GW as FastAPI Gateway
    participant Orch as Orchestrator
    participant IA as Ingestion Agent
    participant TA as Tagging Agent
    participant Mongo as MongoDB
    participant Redis as Redis
    participant TG as Telegram Bot

    Android->>GW: POST /api/webhook/notification {raw_text, bank_hint, timestamp}
    Note over Android: Android only captures + forwards.<br/>No parsing on mobile.
    GW->>GW: Validate auth (X-User-Id)
    GW->>GW: Mask PII (account numbers, phone numbers)
    GW->>Orch: Forward masked payload
    Orch->>IA: Route to Ingestion Agent
    IA->>IA: Gemini Flash: extract amount, merchant, direction, time
    IA-->>Orch: ParsedTransaction (or is_transaction=false → stop)
    Orch->>TA: Route to Tagging Agent
    TA->>Redis: Check merchant cache (7-day TTL)
    TA->>Mongo: Query historical tags for merchant
    TA->>TA: Gemini Flash: classify category + generate tags
    TA-->>Orch: Enriched transaction
    Orch->>Mongo: Insert TransactionDocument
    Orch->>TG: "✅ -100k | ☕ Highlands Coffee | Cafe"
```

## 2. Chat-to-Transaction Flow (Natural Language → Transaction)

```mermaid
sequenceDiagram
    participant User as 💬 User
    participant TG as Telegram
    participant GW as FastAPI Gateway
    participant Orch as Orchestrator
    participant CA as Conversational Agent
    participant TA as Tagging Agent
    participant Mongo as MongoDB
    participant Redis as Redis

    User->>TG: "Hôm qua ăn phở hết 60k"
    TG->>GW: Telegram webhook update
    GW->>GW: Validate chat_id
    GW->>Orch: Forward message
    Orch->>Redis: Load conversation history
    Orch->>CA: Route to Conversational Agent
    CA->>CA: Gemini Pro: resolve intent + temporal refs
    Note over CA: "hôm qua" → 2026-04-19<br/>"phở" → Food<br/>"60k" → 60,000 VND
    CA-->>Orch: Structured transaction data
    Orch->>TA: Route to Tagging Agent
    TA->>TA: Tags: ["pho", "lunch", "street_food"]
    TA-->>Orch: Enriched transaction
    Orch->>Mongo: Insert transaction
    Orch->>Redis: Update session + stats
    Orch->>TG: "✅ Đã ghi: -60k | 🍔 Phở | Hôm qua"
    TG->>User: Confirmation + Edit button
```

## 3. User Correction Flow

```mermaid
sequenceDiagram
    participant User as 💬 User
    participant TG as Telegram
    participant GW as FastAPI
    participant Orch as Orchestrator
    participant Mongo as MongoDB
    participant Redis as Redis

    User->>TG: Tap "✏️ Edit" button
    TG->>GW: Callback query
    GW->>Orch: Edit request for txn_id
    Orch->>TG: Show category options (inline keyboard)
    TG->>User: "Chọn danh mục: 🍔 🚗 🛒 🎬 📸 ..."
    User->>TG: Tap "🚗 Transportation"
    TG->>GW: Category selection callback
    GW->>Orch: Update category
    Orch->>Mongo: Update transaction (category + user_corrected=true)
    Orch->>Redis: Update merchant_cache (learn from correction)
    Orch->>TG: "✅ Đã cập nhật: 🚗 Di chuyển"
    TG->>User: Confirmation
```

## 4. Behavioral Nudge Flow

Two entry points share the same `BehavioralAgent.analyze()` pipeline.

### 4a. Cron Worker Path (Scheduled)

```mermaid
sequenceDiagram
    participant Cron as ⏰ worker.py (cron)
    participant Orch as Orchestrator
    participant Profiles as user_profiles.json
    participant BA as Behavioral Agent
    participant NudgeRepo as NudgeRepository
    participant Mongo as MongoDB
    participant TG as Telegram Bot
    participant User as 💬 User

    Cron->>Profiles: configured_user_ids()
    loop For each configured user
        Cron->>Cron: _collect_triggers(user_id) → trigger list
        Note over Cron: Phase 3.2 seam: spending_alert,<br/>budget_warning, goal_progress etc.
        loop For each trigger
            Cron->>Orch: route("scheduled", {user_id, nudge_type, trigger_data, chat_id})
            Orch->>BA: analyze(NudgeRequest)
            BA->>Profiles: get_profile(user_id) → timezone, hobbies, tone
            BA->>BA: _spam_check()
            Note over BA: quiet hours 22:00–07:00 (user tz)<br/>daily limit (NUDGE_MAX_PER_DAY)<br/>24 h dedup by nudge_type
            alt Spam check passes
                BA->>BA: Build TOON payload (profile + trigger_data)
                BA->>BA: Gemini Pro → {message, should_send}
                alt should_send = true
                    BA->>TG: send_silent_message(chat_id, message)
                    BA->>NudgeRepo: insert(NudgeDocument)
                    TG->>User: "☕ 500k cafe — bằng nửa cuộn Kodak Portra!"
                end
            end
        end
    end
```

### 4b. Telegram Command Path (`/nudge`)

```mermaid
sequenceDiagram
    participant User as 💬 User
    participant TG as Telegram
    participant GW as FastAPI Gateway
    participant WH as webhook.py handler
    participant Orch as Orchestrator
    participant BA as Behavioral Agent
    participant NudgeRepo as NudgeRepository
    participant Mongo as MongoDB

    User->>TG: /nudge [spending|budget|goal|streak|sub|impulse]
    TG->>GW: Telegram webhook update
    GW->>WH: _handle_command("nudge", args, chat_id, from_id)
    WH->>Mongo: _spending_summary(from_id)
    Note over WH: Queries this week's transactions<br/>{period, total_outflow, top_categories}
    WH->>Orch: route("scheduled", {user_id=from_id, nudge_type, trigger_data={…summary, source="telegram"}, chat_id})
    Orch->>BA: analyze(NudgeRequest)
    BA->>BA: get_profile(user_id) → load profile
    Note over BA: source="telegram" → skip spam block,<br/>always should_send=true
    BA->>BA: Build TOON payload → Gemini Pro
    BA->>TG: send_silent_message(chat_id, message)
    BA->>NudgeRepo: insert(NudgeDocument)
    TG->>User: Personalised nudge message
```

## 5. Report Generation Flow

```mermaid
sequenceDiagram
    participant Trigger as ⏰ Cron / User Request
    participant RA as Reporting Agent
    participant Mongo as MongoDB
    participant TG as Telegram

    Trigger->>RA: Generate weekly report
    RA->>Mongo: Aggregate transactions (last 7 days)
    RA->>RA: Gemini Flash: generate insights narrative
    Note over RA: Total: -2.5M VND<br/>Top: Food (40%), Transport (20%)<br/>Trend: +15% vs last week
    RA->>Mongo: Cache report document
    RA->>TG: Send formatted summary
    TG->>TG: "📊 Tuần này: -2.5M | Top: 🍔 40% 🚗 20%"
```

> Visual dashboard (charts, drill-downs) is out of scope for this repo — deferred to the Android app in a separate repository.

## 6. Voice Input Flow

```mermaid
sequenceDiagram
    participant User as 🎤 User
    participant TG as Telegram
    participant GW as FastAPI
    participant Orch as Orchestrator
    participant CA as Conversational Agent
    participant TA as Tagging Agent
    participant Mongo as MongoDB

    User->>TG: Send voice message
    TG->>GW: Voice file URL
    GW->>Orch: Forward voice data
    Orch->>CA: Route to Conversational Agent
    CA->>CA: Gemini Flash: speech-to-text
    Note over CA: "đổ xăng hai trăm nghìn"
    CA->>CA: Gemini Pro: parse intent + amount
    Note over CA: amount: 200000, category: Transportation
    CA-->>Orch: Structured transaction
    Orch->>TA: Enrich with tags
    TA-->>Orch: ["gas", "motorbike", "commute"]
    Orch->>Mongo: Insert transaction
    Orch->>TG: "✅ -200k | 🚗 Đổ xăng"
```

## 7. Subscription Management Flow

### 7a. Register a subscription (chat)

```mermaid
sequenceDiagram
    participant User as 💬 User
    participant TG as Telegram
    participant Orch as Orchestrator
    participant CA as Conversational Agent
    participant SubRepo as SubscriptionRepository

    User->>TG: "đăng ký Netflix 260k mỗi tháng"
    TG->>Orch: route("chat", ...)
    Orch->>CA: process_message()
    CA->>CA: Gemini Pro → intent: set_subscription
    Note over CA: name=Netflix, amount=260000,<br/>period=monthly
    CA-->>Orch: IntentResult
    Orch->>SubRepo: insert(SubscriptionDocument)
    Orch->>TG: "✅ Netflix 260k/tháng. Kỳ tới: 27/05 🔄"
    TG->>User: Confirmation
```

### 7b. Auto-detect unregistered recurring charge

```mermaid
sequenceDiagram
    participant Phone as 📱 Phone
    participant Orch as Orchestrator
    participant SubRepo as SubscriptionRepository
    participant TxnRepo as TransactionRepository
    participant TG as Telegram Bot
    participant User as 💬 User

    Phone->>Orch: Bank notification "Netflix trừ 260k"
    Orch->>Orch: Ingestion → Tagging → Store transaction
    Orch->>SubRepo: find_by_merchant(user_id, "Netflix")
    SubRepo-->>Orch: None (not registered)
    Orch->>TxnRepo: find_by_merchant(user_id, "Netflix", limit=5)
    Orch->>Orch: _is_recurring_pattern() → True
    Note over Orch: ≥2 prior outflows, ±30% amount,<br/>7–40 day intervals
    Orch->>TG: "🔄 Netflix có vẻ là phí định kỳ. Đăng ký theo dõi không?"
    TG->>User: Prompt message
    Note over User: User can reply "đăng ký Netflix 260k mỗi tháng"
```

### 7c. Incoming charge matches registered subscription

```mermaid
sequenceDiagram
    participant Phone as 📱 Phone
    participant Orch as Orchestrator
    participant SubRepo as SubscriptionRepository

    Phone->>Orch: Bank notification "Netflix trừ 260k"
    Orch->>Orch: Ingestion → Tagging → Store transaction
    Orch->>SubRepo: find_by_merchant(user_id, "Netflix")
    SubRepo-->>Orch: SubscriptionDocument found
    Orch->>SubRepo: mark_charged(sub_id, charged_at)
    Note over SubRepo: last_charged_at = now<br/>next_charge_date += 30 days
```

### 7d. Manual mark paid (chat)

```mermaid
sequenceDiagram
    participant User as 💬 User
    participant TG as Telegram
    participant Orch as Orchestrator
    participant CA as Conversational Agent
    participant SubRepo as SubscriptionRepository

    User->>TG: "Netflix đã trả rồi"
    TG->>Orch: route("chat", ...)
    Orch->>CA: process_message()
    CA->>CA: Gemini Pro → intent: mark_subscription_paid
    CA-->>Orch: {subscription_merchant: "Netflix"}
    Orch->>SubRepo: find_by_merchant(user_id, "Netflix")
    Orch->>SubRepo: mark_charged(sub_id, now)
    Orch->>TG: "✅ Netflix đã thanh toán kỳ này! Kỳ tới: 27/06 🔄"
    TG->>User: Confirmation
```

### 7e. Subscription reminder (cron)

```mermaid
sequenceDiagram
    participant Cron as ⏰ worker.py
    participant SubRepo as SubscriptionRepository
    participant Orch as Orchestrator
    participant BA as Behavioral Agent
    participant TG as Telegram Bot
    participant User as 💬 User

    Cron->>SubRepo: find_upcoming(user_id, within_hours=48)
    SubRepo-->>Cron: [Netflix — 260k — next: tomorrow]
    Cron->>Orch: route("scheduled", {nudge_type: subscription_reminder, trigger_data: {...}})
    Orch->>BA: analyze(NudgeRequest)
    BA->>BA: Gemini Pro → reminder message
    BA->>TG: send_silent_message()
    TG->>User: "🔄 Netflix trừ 260k ngày mai"
```

## 8. System Startup Flow

```mermaid
flowchart TD
    A[docker-compose up] --> B[chiwi-redis starts]
    A --> C[chiwi-mongo starts]
    B & C --> D[chiwi-api starts]
    D --> E[Load .env config]
    E --> F[Connect MongoDB]
    E --> G[Connect Redis]
    F & G --> H[Register Telegram webhook]
    H --> I[Start Uvicorn server]
    I --> J[Health check: GET /health]
    A --> K[chiwi-worker starts]
    K --> L[Register cron schedules]
    L --> M["Daily: Behavioral analysis (08:00)"]
    L --> N["Weekly: Report generation (Monday 09:00)"]
    L --> O["Hourly: Budget check"]
```

## 9. Analytics Flow (Comparison / Trend)

```mermaid
sequenceDiagram
    participant User as 💬 User
    participant TG as Telegram
    participant GW as FastAPI Gateway
    participant Orch as Orchestrator
    participant CA as Conversational Agent
    participant AA as Analytics Agent
    participant Mongo as MongoDB

    User->>TG: "so sánh chi tiêu tuần này với tuần trước"
    TG->>GW: Telegram webhook update
    GW->>Orch: Forward message
    Orch->>CA: Route to Conversational Agent
    CA->>CA: Gemini Pro: classify intent
    Note over CA: intent: request_analysis<br/>analysis_type: compare<br/>period: this_week<br/>compare_period: last_week
    CA-->>Orch: Structured analysis request
    Orch->>Mongo: Query transactions (this week)
    Orch->>Mongo: Query transactions (last week)
    Orch->>AA: Route to Analytics Agent
    AA->>AA: Pre-aggregate per category
    AA->>AA: Gemini Pro: generate comparative insight
    Note over AA: Total: +19% vs last week<br/>Food: +25%, Cafe: -33%<br/>Transport: +25%
    AA-->>Orch: Formatted analysis report
    Orch->>TG: Send analysis to user
    TG->>User: Comparative analysis with trends
```

## 10. Budget Management Flows

### 10a. Set a budget (chat)

```mermaid
sequenceDiagram
    participant User as 💬 User
    participant TG as Telegram
    participant Orch as Orchestrator
    participant CA as Conversational Agent
    participant BudgetRepo as BudgetRepository

    User->>TG: "Đặt ngân sách ăn uống 3 triệu mỗi tháng"
    TG->>Orch: route("chat", ...)
    Orch->>CA: process_message()
    CA->>CA: Gemini Pro → intent: set_budget
    Note over CA: category=food, limit=3000000, period=monthly
    CA-->>Orch: IntentResult
    Orch->>BudgetRepo: insert(BudgetDocument) + BudgetEvent(created)
    Orch->>TG: "✅ Ngân sách Ăn uống: 3,000,000đ/tháng"
    TG->>User: Confirmation
```

### 10b. View budgets (chat)

```mermaid
sequenceDiagram
    participant User as 💬 User
    participant TG as Telegram
    participant Orch as Orchestrator
    participant CA as Conversational Agent
    participant BudgetRepo as BudgetRepository

    User->>TG: "Ngân sách của tôi thế nào?"
    TG->>Orch: route("chat", ...)
    Orch->>CA: process_message()
    CA->>CA: Gemini Pro → intent: ask_budget
    Orch->>BudgetRepo: find_active(user_id)
    Orch->>Orch: Compute spend-to-limit ratio for each budget
    Orch->>TG: Usage bars per category
    TG->>User: "🍔 Ăn uống: 2.1M / 3M [████░] 70%"
```

### 10c. Modify a budget (update / temp override / silence / disable)

```mermaid
sequenceDiagram
    participant User as 💬 User
    participant TG as Telegram
    participant Orch as Orchestrator
    participant CA as Conversational Agent
    participant BudgetRepo as BudgetRepository

    User->>TG: "Tăng tạm ngân sách mua sắm 500k tháng này"
    TG->>Orch: route("chat", ...)
    Orch->>CA: process_message()
    CA->>CA: Gemini Pro → intent: temp_increase_budget
    Note over CA: category=shopping, amount=500000
    CA-->>Orch: IntentResult
    Orch->>BudgetRepo: set_temp_limit(budget_id, temp_limit, expires_at)
    Orch->>BudgetRepo: insert BudgetEvent(temp_override_set)
    Orch->>TG: "✅ Ngân sách Mua sắm tạm tăng +500k tháng này"
    TG->>User: Confirmation
```

Other intents follow the same pattern:
- `update_budget` → updates `limit_amount` permanently + BudgetEvent(`limit_updated`)
- `silence_budget` → sets `is_silenced=True` + BudgetEvent(`silenced`); budget is still tracked but no alert nudges
- `disable_budget` → sets `is_active=False` + BudgetEvent(`disabled`)

## 11. Spending vs Average Flow

```mermaid
sequenceDiagram
    participant User as 💬 User
    participant TG as Telegram
    participant Orch as Orchestrator
    participant CA as Conversational Agent
    participant SpendingAvg as spending_avg.py
    participant Mongo as MongoDB

    User->>TG: "Cafe tháng này so với trung bình không?"
    TG->>Orch: route("chat", ...)
    Orch->>CA: process_message()
    CA->>CA: Gemini Pro → intent: ask_spending_vs_avg
    Note over CA: period=this_month
    CA-->>Orch: IntentResult
    Orch->>SpendingAvg: compute_avg_all_categories(user_id, period)
    SpendingAvg->>Mongo: Aggregate past 2+ complete periods per category
    SpendingAvg-->>Orch: {category: {avg, current, delta_pct}}
    Orch->>TG: Comparison table with deltas
    TG->>User: "☕ Cafe: 850k (TB: 600k) ▲42%\n🍔 Ăn uống: 1.2M (TB: 1.5M) ▼20%"
```
