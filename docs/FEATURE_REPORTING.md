# Feature: Financial Reporting & Dashboard

## Summary

The Reporting Agent generates periodic financial summaries with narrative insights (not just numbers) and serves data to a Telegram Mini App dashboard for visual charts.

## User Stories

> As a user, I want a weekly financial summary in Telegram so I can stay aware of my spending trends.

> As a user, I want to open a dashboard with charts to see my spending breakdown visually.

## Report Types

### Daily Summary (Auto — End of Day)
```
📊 Tổng kết ngày 20/04:
💸 Chi tiêu: -850,000₫
📈 Thu nhập: +0₫

Top danh mục:
  🍔 Ăn uống: -350k (3 giao dịch)
  🚗 Di chuyển: -250k (2 giao dịch)
  ☕ Cafe: -250k (2 giao dịch)

💡 So với TB ngày: +15% chi tiêu
```

### Weekly Summary (Auto — Monday 09:00)
```
📊 Tuần 16 (14-20/04):
💸 Tổng chi: -4,500,000₫
📈 Tổng thu: +30,000,000₫
💰 Tiết kiệm: 25,500,000₫ (85%)

Top 5 danh mục:
  🍔 Ăn uống: -1,800k (40%)
  🚗 Di chuyển: -900k (20%)
  🛒 Mua sắm: -700k (16%)
  🎬 Giải trí: -600k (13%)
  📸 Sở thích: -500k (11%)

📉 So với tuần trước: +12% chi tiêu
🎯 Mục tiêu lens: 45% (6.75M / 15M)
💡 Insight: "Chi tiêu cafe tăng 30% — cân nhắc pha tại nhà"
```

### Monthly Report (Auto — 1st of Month)
Full month analysis including:
- Income vs. expense breakdown
- Category trend charts (via Mini App)
- Budget compliance per category
- Goal progress with projected completion dates
- Personalized financial advice from Gemini Pro

### Goal Progress (On Demand)
```
🎯 Mục tiêu: Mua lens Sigma 56mm
💰 Đã tiết kiệm: 6,750,000₫ / 15,000,000₫ (45%)
📅 Tốc độ hiện tại: ~1.5M/tháng
📆 Dự kiến hoàn thành: Tháng 10/2026
💡 Mẹo: Giảm 200k/tuần cafe → hoàn thành sớm 2 tháng
```

## API Contract

### `GET /api/reports/{report_type}`

**Query Params**:

| Param | Type | Description |
|---|---|---|
| `period` | string | e.g., "2026-04-20", "2026-W16", "2026-04" |
| `format` | string | `telegram` (formatted text) or `json` (Mini App data) |

**Response** (JSON format):
```json
{
  "report_type": "weekly_summary",
  "period": "2026-W16",
  "data": {
    "total_income": 30000000,
    "total_expense": 4500000,
    "savings_rate": 0.85,
    "categories": [
      { "name": "Food & Beverage", "emoji": "🍔", "amount": 1800000, "pct": 0.40, "txn_count": 12 },
      { "name": "Transportation", "emoji": "🚗", "amount": 900000, "pct": 0.20, "txn_count": 7 }
    ],
    "vs_last_period": 0.12,
    "goals": [
      { "name": "Camera Lens", "current": 6750000, "target": 15000000, "pct": 0.45 }
    ],
    "insights": [
      "Chi tiêu cafe tăng 30% so với tuần trước",
      "3 giao dịch subscription phát hiện: Netflix, Spotify, iCloud"
    ]
  },
  "generated_at": "2026-04-21T09:00:00+07:00"
}
```

### Telegram Commands

| Command | Action |
|---|---|
| `/report` or "báo cáo" | Weekly summary |
| `/today` or "hôm nay" | Today's summary |
| `/goal` or "mục tiêu" | Goal progress |
| `/budget` or "ngân sách" | Budget status |

## Telegram Mini App Dashboard

The Mini App provides rich visual charts that Telegram's text interface cannot deliver.

**Dashboard Sections**:

| Section | Chart Type | Data |
|---|---|---|
| Spending Overview | Donut chart | Category breakdown |
| Daily Trend | Line chart | Last 30 days spending |
| Budget Status | Progress bars | Per-category budget usage |
| Goal Tracker | Progress ring | Each financial goal |
| Category Compare | Bar chart | This week vs last week |

**Tech**: React + lightweight chart library, served as a static page embedded in Telegram Mini App.

## Caching Strategy

Reports are cached in MongoDB `reports` collection to avoid re-computation:
- Daily summaries: regenerated at end of day
- Weekly summaries: regenerated Monday morning
- Monthly reports: regenerated 1st of month
- On-demand reports: cached for 1 hour
