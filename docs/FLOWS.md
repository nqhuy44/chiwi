# ChiWi — Business Logic Flows

## 1. Transaction Ingestion Flow (Notification → Stored Transaction)

```mermaid
sequenceDiagram
    participant Phone as 📱 Phone
    participant MD as MacroDroid/Tasker
    participant GW as FastAPI Gateway
    participant Orch as Orchestrator
    participant IA as Ingestion Agent
    participant TA as Tagging Agent
    participant Mongo as MongoDB
    participant Redis as Redis
    participant TG as Telegram Bot

    Phone->>MD: Bank notification received
    MD->>GW: HTTP POST /api/webhook/notification
    GW->>GW: Validate auth (user_id)
    GW->>GW: Mask PII (account numbers)
    GW->>Orch: Forward masked payload
    Orch->>Redis: Load user session context
    Orch->>IA: Route to Ingestion Agent
    IA->>IA: Gemini Flash: extract amount, merchant, time
    IA-->>Orch: Parsed transaction data
    Orch->>TA: Route to Tagging Agent
    TA->>Mongo: Query historical tags for merchant
    TA->>TA: Gemini Flash: classify category + generate tags
    TA-->>Orch: Enriched transaction
    Orch->>Mongo: Insert transaction document
    Orch->>Redis: Update daily stats cache
    Orch->>TG: Send confirmation message + Edit button
    TG->>Phone: "✅ -100k | ☕ Highlands Coffee | Cafe"
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

```mermaid
sequenceDiagram
    participant Cron as ⏰ Scheduled Worker
    participant BA as Behavioral Agent
    participant Mongo as MongoDB
    participant Redis as Redis
    participant TG as Telegram Bot
    participant User as 💬 User

    Cron->>BA: Trigger daily analysis
    BA->>Mongo: Query user profile + recent transactions
    BA->>Mongo: Query historical spending patterns
    BA->>BA: Gemini Pro: analyze behavior patterns
    Note over BA: Detected: 5th cafe this week<br/>Budget: 70% used (day 20/30)<br/>Goal: Camera lens fund stalled

    alt Spending Alert Needed
        BA->>Mongo: Insert nudge record
        BA->>TG: Send nudge message
        TG->>User: "☕ Tuần này bạn đã chi 500k cho cafe — bằng nửa cuộn Kodak Portra!"
    end

    alt Budget Warning
        BA->>Mongo: Insert nudge record
        BA->>TG: Send budget alert
        TG->>User: "⚠️ Đã dùng 70% ngân sách Ăn uống, còn 10 ngày"
    end

    alt Positive Reinforcement
        BA->>Mongo: Insert nudge record
        BA->>TG: Send encouragement
        TG->>User: "🎉 3 ngày liên tiếp chi tiêu dưới mức TB. Tiếp tục nhé!"
    end
```

## 5. Report Generation Flow

```mermaid
sequenceDiagram
    participant Trigger as ⏰ Cron / User Request
    participant RA as Reporting Agent
    participant Mongo as MongoDB
    participant TG as Telegram
    participant MiniApp as Mini App Dashboard

    Trigger->>RA: Generate weekly report
    RA->>Mongo: Aggregate transactions (last 7 days)
    RA->>RA: Gemini Pro: generate insights narrative
    Note over RA: Total: -2.5M VND<br/>Top: Food (40%), Transport (20%)<br/>Trend: +15% vs last week<br/>Insight: "Subscription renewal spike"
    RA->>Mongo: Cache report document
    RA->>TG: Send summary message
    TG->>TG: "📊 Tuần này: -2.5M | Top: 🍔 40% 🚗 20%"
    TG->>TG: Attach "Xem chi tiết" button
    Note over MiniApp: User taps → Opens Mini App<br/>with full charts & breakdown
```

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

## 7. System Startup Flow

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
