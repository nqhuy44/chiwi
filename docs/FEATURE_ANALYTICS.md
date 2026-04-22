# Feature: Financial Analytics

## Summary

The Analytics Agent provides deep financial analysis capabilities that go beyond simple reporting summaries. It handles period-over-period comparisons, spending trend detection, category deep-dives, and anomaly identification.

## User Stories

> As a user, I want to compare my spending this week vs last week so I can see if I'm improving.

> As a user, I want to see spending trends over this month so I can identify patterns.

> As a user, I want to analyze a specific category (e.g., "Ăn uống") in detail across periods.

## Analysis Types

### Compare (Period-over-Period)

Compares spending between two time periods. Shows per-category differences with trend indicators.

```
📊 So sánh chi tiêu: Tuần này vs Tuần trước

<b>Tuần này:</b> 2,500,000 VND (15 giao dịch)
<b>Tuần trước:</b> 2,100,000 VND (12 giao dịch)
📈 Tăng 19% (+400,000 VND)

<b>Chi tiết theo danh mục:</b>
🍽️ Ăn uống: 1,200k → 1,500k 📈 +25%
☕ Cà phê: 300k → 200k 📉 -33%
🚗 Di chuyển: 400k → 500k 📈 +25%
🛒 Mua sắm: 200k → 300k 📈 +50%

<b>Nhận xét của Mai:</b>
Chi tiêu ăn uống tăng khá nhiều nha. Nhưng bạn đã giảm café tốt lắm! 🎉
```

### Trend (Spending Direction)

Analyzes spending patterns over a period to identify trends per category.

```
📊 Xu hướng chi tiêu tháng 4/2026

<b>Tổng chi:</b> 8,500,000 VND (52 giao dịch)
<b>Trung bình ngày:</b> 386,000 VND

<b>Xu hướng theo danh mục:</b>
🍽️ Ăn uống: 📈 Tăng dần (tuần 1: 800k → tuần 3: 1.2M)
☕ Cà phê: ➡️ Ổn định (~250k/tuần)
🚗 Di chuyển: 📉 Giảm dần (tuần 1: 600k → tuần 3: 350k)

<b>Nhận xét của Mai:</b>
Di chuyển giảm rất tốt! Có phải bạn đang đi xe buýt nhiều hơn không? 💪
```

### Deep Dive (Category/Merchant) — *Planned for follow-up*

Drills into a specific category or merchant to show detailed breakdowns across time.

## Intent Routing

| User Message | Intent | Analysis Type |
|---|---|---|
| "so sánh tuần này với tuần trước" | `request_analysis` | `compare` |
| "so sánh chi tiêu tháng này tháng trước" | `request_analysis` | `compare` |
| "xu hướng chi tiêu tháng này" | `request_analysis` | `trend` |
| "phân tích chi tiêu ăn uống" | `request_analysis` | `deep_dive` |

## Technical Details

| Property | Value |
|---|---|
| **Agent File** | `src/agents/analytics.py` |
| **Prompt File** | `src/agents/prompts/analytics.md` |
| **LLM** | Gemini 2.5 Pro (reasoning-heavy) |
| **Schema** | `AnalysisRequest` in `src/core/schemas.py` |
| **Date Utils** | `get_comparison_ranges()` in `src/core/utils.py` |

## API Contract

Analytics is triggered via the Telegram chat interface. The Conversational Agent classifies the intent as `request_analysis` and the Orchestrator routes to the Analytics Agent.

### AnalysisRequest Schema

```python
class AnalysisRequest(BaseModel):
    user_id: str
    analysis_type: Literal["compare", "trend", "deep_dive"]
    period: str  # e.g., "this_week", "this_month"
    compare_period: str | None = None  # e.g., "last_week"
    category_filter: str | None = None  # e.g., "Ăn uống"
```

## Error Handling

| Scenario | Behavior |
|---|---|
| Invalid Period | If the user requests a period not yet supported (e.g., "năm 2020"), Mai responds that she doesn't support it yet and suggests valid alternatives. |
| No Data Found | If no transactions are found for the requested period, Mai provides a friendly message noting the lack of spending and gives encouraging savings advice. |
| Missing Comparison | For comparison requests, if data for one period is missing, Mai focuses the analysis on the available data while noting the missing comparison. |

## Limitations

- `deep_dive` analysis type is planned but not yet implemented.
- Trend analysis currently works within a single period (no cross-month trends).
- Maximum 200 transactions per period to stay within LLM context limits.
