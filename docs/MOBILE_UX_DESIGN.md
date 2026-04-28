# ChiWi Mobile App — UX/UI Design Specification

> **Scope:** Android-first (Kotlin + Jetpack Compose). This document covers design principles, visual language, component system, screen inventory, and key interaction flows for all core areas: Dashboard, Transactions, Budget, Goals, Subscriptions, Nudges (Behavioral), Analytics, and User Profile.

---

## 1. Design Principles

| Principle                      | Expression in ChiWi                                                                                                  |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| **Zero friction**              | Capture happens in the background; confirmation is one tap; budget/goal setup is a single bottom sheet               |
| **Trust through transparency** | Always show what was captured and why before committing; budgets show remaining — not just spent                     |
| **Mai's voice**                | Friendly, warm, Vietnamese. Mai speaks in first person. Error states say "Mình chưa thấy…" not "No data found."      |
| **Numbers as the hero**        | Amounts, totals, and progress are always the largest, most prominent element on any screen                           |
| **Calm by default**            | Red/warning colours appear only when something genuinely needs attention; celebrate progress with emerald and indigo |
| **Proactive, not nagging**     | Nudges feel like tips from a smart friend — never alarms. One nudge per day max.                                     |

---

## 2. Visual Language

### 2.1 Colour System (Modern Indigo & Emerald)

```
Primary         #4F46E5   Indigo — primary actions, active states, goal progress
Primary Dark    #4338CA   Pressed/focused states
Primary Light   #E0E7FF   Light indigo — progress bar track, chip backgrounds
Outflow         #F43F5E   Rose/Red — outflow amounts, delete, over-budget
Inflow          #10B981   Emerald Green — inflow amounts, goal milestones, streaks
Warning         #F59E0B   Amber — budget warnings (70–100%), subscription due
Danger Bg       #FFF1F2   Light rose — over-budget card backgrounds
Warning Bg      #FFFBEB   Light amber — near-budget card backgrounds
Success Bg      #ECFDF5   Light emerald — goal achieved, saving streak
Neutral 900     #111827   Primary text (slate grey, not pure black)
Neutral 700     #374151   Secondary text — transaction metadata
Neutral 600     #4B5563   Tertiary labels, captions
Neutral 200     #E5E7EB   Dividers, disabled states, progress tracks
Neutral 50      #F9FAFB   Page background
Surface         #FFFFFF   Cards, bottom sheets, dialogs
Gradient Start  #4F46E5   → used in summary header cards
Gradient End    #7C3AED   → violet for depth
```

**Colour usage rules:**

- Outflow amounts always render in `Outflow`; inflow in `Inflow`
- `Primary` is reserved for the single primary CTA per screen
- Never use `Outflow` rose for anything other than money going out and destructive actions
- Background pages use `Neutral 50`; cards use `Surface` (white)
- Budget cards shift from `Primary` → `Warning` → `Outflow` as spend % rises
- Goals use `Primary` (in-progress) and `Inflow` (achieved)

### 2.2 Typography

Base font: **Roboto** (system default, full Vietnamese glyph support).

| Role     | Size  | Weight       | Line height | Usage                               |
| -------- | ----- | ------------ | ----------- | ----------------------------------- |
| Display  | 32 sp | Bold 700     | 40 sp       | Balance totals, hero amounts        |
| Headline | 24 sp | SemiBold 600 | 32 sp       | Screen titles, large amounts        |
| Title    | 18 sp | Medium 500   | 28 sp       | Card titles, section headers        |
| Body     | 16 sp | Regular 400  | 24 sp       | Transaction descriptions, body copy |
| Label    | 14 sp | Medium 500   | 20 sp       | Tags, badges, button text           |
| Caption  | 12 sp | Regular 400  | 18 sp       | Timestamps, metadata, footnotes     |

### 2.3 Spacing & Layout

- Base unit: **8 dp**
- Screen horizontal padding: **16 dp**
- Card internal padding: **16 dp**
- Section gap: **24 dp**
- Between cards: **12 dp**
- Minimum touch target: **48 × 48 dp**
- Corner radius: **16 dp** (cards — slightly more rounded for modern feel), **8 dp** (chips/badges), **28 dp** (primary buttons full-width), **24 dp** (circular progress rings)

### 2.4 Elevation & Depth

- Page background: 0 dp (flat, `Neutral 50`)
- Cards: 2 dp shadow `rgba(0,0,0,0.08)` — a bit more lift for modern feel
- Header summary card: 4 dp + gradient background
- Bottom sheets: 8 dp
- Dialogs / modals: 12 dp
- Floating Action Button: 6 dp

### 2.5 Gradient Cards

Summary and status cards that need visual weight use a subtle gradient:

```
Background: LinearGradient(
  colors = [#4F46E5, #7C3AED],
  start = TopStart,
  end = BottomEnd
)
```

Text on gradient surfaces: white (`#FFFFFF`) for primary, `rgba(255,255,255,0.75)` for secondary.

### 2.6 Iconography

**Material Symbols Rounded** (`weight=400, grade=0, optical size=24`). Never mix families.

| Context      | Icon                                     |
| ------------ | ---------------------------------------- |
| Inflow       | `arrow_downward` → Inflow emerald        |
| Outflow      | `arrow_upward` → Outflow rose            |
| Delete       | `delete_outline`                         |
| Confirm      | `check_circle_outline`                   |
| Dashboard    | `home`                                   |
| Transactions | `receipt_long`                           |
| Kế hoạch     | `savings`                                |
| Analytics    | `bar_chart`                              |
| Profile      | `person_outline`                         |
| Budget       | `account_balance_wallet`                 |
| Goal         | `flag`                                   |
| Subscription | `autorenew`                              |
| Nudge        | `lightbulb_outline`                      |
| Calendar     | `calendar_today`                         |
| Notification | `notifications`                          |
| Category     | `label`                                  |
| Streak       | `local_fire_department` → Inflow emerald |
| Milestone    | `emoji_events`                           |

---

## 3. Component Library

### 3.1 Transaction Card

```
┌────────────────────────────────────────────┐
│  ┌──┐  Highlands Coffee         ─ 45.000đ  │
│  │☕│  Cà phê / Trà sữa  ·  14:32  Thứ 2  │
│  └──┘                                      │
└────────────────────────────────────────────┘
```

- Category icon (24 dp) on a 40 dp circle tinted with category colour (opacity 0.15)
- Amount: Title weight, right-aligned, `Outflow` or `Inflow` colour
- Tap → Transaction Detail sheet; long-press → quick actions

### 3.2 Amount Display

```
  ─ 45.000đ          + 15.000.000đ
```

- `formatAmount()`: `NumberFormat` with locale `vi_VN`, no decimal for VND
- Prefix `─` for outflow, `+` for inflow, always coloured

### 3.3 Period Selector

Horizontal scrollable chip row:

```
[ Hôm nay ]  [ Tuần này ]  [ Tháng này ]  [ Tháng trước ]  [ Tuỳ chọn ]
```

- Selected: `Primary` background, white text, 2 dp shadow
- Unselected: `Neutral 50` background, `Neutral 600` text, `Neutral 200` border
- "Tuỳ chọn" opens date range picker

### 3.4 Summary Header Card (Gradient)

```
┌──────────────────────────────────────────┐  ← gradient #4F46E5 → #7C3AED
│  Tháng 4 · 2026              ↻ refresh   │
│                                          │
│  ─ 3.450.000đ                            │  ← Display, white
│  Chi tiêu   · 23 giao dịch              │  ← Caption, white 75%
│                                          │
│  ┌──────────────┐  ┌──────────────┐      │
│  │ Chi ra       │  │ Nhận vào     │      │  ← white cards on gradient
│  │ ─ 3.450.000  │  │ + 15.000.000 │      │
│  └──────────────┘  └──────────────┘      │
└──────────────────────────────────────────┘
```

### 3.5 Budget Progress Card

```
┌────────────────────────────────────────────┐
│  🍽  Ăn uống                               │
│  1.200.000đ / 2.000.000đ                   │
│  ┌──────────────────────────────────────┐  │
│  │████████████████░░░░░░░░░░░░░░░░░░░│  │  ← animated fill bar
│  └──────────────────────────────────────┘  │
│  Còn 800.000đ · 12 ngày còn lại     60%   │
└────────────────────────────────────────────┘
```

**Progress bar states (animated colour transition):**

| Spend % | Bar colour               | Card border    | Background tint      |
| ------- | ------------------------ | -------------- | -------------------- |
| < 70%   | `Primary #4F46E5`        | none           | `Surface`            |
| 70–90%  | `Warning #F59E0B`        | `Warning` 1 dp | `Warning Bg #FFFBEB` |
| 90–100% | `Outflow #F43F5E`        | `Outflow` 1 dp | `Danger Bg #FFF1F2`  |
| > 100%  | Full `Outflow` + pulsing | `Outflow` 2 dp | `Danger Bg`          |

When over budget, show extra label below bar:

```
  ⚠ Vượt ngân sách 200.000đ
```

When no budget set for a category, show:

```
  ─ Chưa đặt ngân sách    [ Đặt ngay → ]
```

### 3.6 Goal Progress Card

```
┌────────────────────────────────────────────┐
│                       ╭──────────────────╮  │
│  🎯 Mua laptop        │     ◯  65%       │  │  ← Circular ring
│                       │  13.0M / 20M     │  │     Primary colour
│  Dự kiến hoàn thành   ╰──────────────────╯  │
│  Tháng 8 · 2026                             │
│  ──────────────────────────────────────     │
│  Mini bar: [■■■■■■■░░░] last 6 months      │
└────────────────────────────────────────────┘
```

- Circular progress: `Canvas`-drawn arc, track = `Primary Light`, fill = `Primary`
- When achieved (100%): ring turns `Inflow` emerald + confetti micro-animation
- Centre text: percentage if < 100%, `🏆` emoji if 100%

### 3.7 Subscription Card

```
┌────────────────────────────────────────────┐
│  ┌────┐  Spotify                ─ 59.000đ  │
│  │ 🎵 │  Hàng tháng                        │
│  └────┘  ┌─────────────┐                   │
│          │  3 ngày nữa │                   │  ← due-date chip
│          └─────────────┘                   │
└────────────────────────────────────────────┘
```

**Due-date chip states:**

| State    | Chip colour                  | Text             |
| -------- | ---------------------------- | ---------------- |
| Overdue  | `Outflow` bg, white text     | "Quá hạn X ngày" |
| Today    | `Warning` bg, white text     | "Hôm nay"        |
| 1–3 days | `Warning Bg`, `Warning` text | "X ngày nữa"     |
| 4–7 days | `Neutral 200`, `Neutral 700` | "X ngày nữa"     |
| > 7 days | `Neutral 50`, `Neutral 600`  | "X ngày nữa"     |

- Swipe right on card → "✅ Đã thanh toán" (mark paid with haptic feedback)
- Swipe left → confirm-delete bottom sheet

### 3.8 Nudge Card ("Từ Mai")

```
┌────────────────────────────────────────────┐
│  ┌──┐  Mai                           ✕    │
│  │🤖│  💡 Gợi ý chi tiêu                  │  ← nudge type badge
│  └──┘  ─────────────────────────────────  │
│        "Tuần này bạn chi cà phê nhiều hơn  │
│         tuần trước 40%. Mình thấy bạn hay  │
│         ghé Highlands lắm đó! 😄"          │
│                                            │
│              [ Xem chi tiết →  ]           │
└────────────────────────────────────────────┘
```

**Nudge type badge colours:**

| Type                  | Icon | Accent           |
| --------------------- | ---- | ---------------- |
| Spending spike        | 📈   | `Outflow`        |
| Budget warning        | 💳   | `Warning`        |
| Impulse detection     | 💡   | Violet `#7C3AED` |
| Saving streak         | 🔥   | `Inflow`         |
| Subscription reminder | 🔔   | `Warning`        |
| Goal milestone        | 🏆   | `Primary`        |

- Dismissible: swipe up or tap ✕ (stored locally, won't re-show for 24 h)
- CTA navigates to the relevant screen (budget detail, analytics, subscription)

### 3.9 Notification Capture Sheet

See Section 5.2 for full spec.

### 3.10 Primary Button

```
[  ✅  Xác nhận giao dịch  ]   ← full-width, 56 dp tall, 28 dp corner
```

- Background: `Primary`, Text: white, Label weight 500
- Pressed: `Primary Dark` + scale(0.97) animation

### 3.11 Destructive Button

```
[  🗑️  Xoá giao dịch  ]        ← outlined, border+text = Outflow
```

### 3.12 Section Chip Tab Bar

Used inside Kế hoạch screen for sub-navigation:

```
[ Ngân sách ]  [ Mục tiêu ]  [ Định kỳ ]
```

- Underline indicator (not filled chip) for tab-style navigation
- Active: `Primary` underline + `Primary` text
- Inactive: `Neutral 600` text

---

## 4. Navigation Structure

```
Bottom Navigation Bar (5 tabs):
├── 🏠  Tổng quan       (Dashboard)
├── 🧾  Giao dịch       (Transaction list)
├── 💰  Kế hoạch        (Budget + Goals + Subscriptions)
├── 📊  Phân tích       (Analytics)
└── 👤  Hồ sơ           (Profile & Settings)
```

- Active tab: `Primary` icon + label
- Inactive tab: `Neutral 600` icon, no label
- The notification capture flow is a modal overlay — it appears above any tab without disrupting navigation state
- Badge (amber dot) appears on Kế hoạch tab when any budget is > 90% or a subscription is due within 3 days

**Kế hoạch tab — internal top tabs:**

```
[ Ngân sách ]  [ Mục tiêu ]  [ Định kỳ ]
```

Implemented as `TabRow` with `HorizontalPager`.

---

## 5. Screens & Flows

### 5.1 Dashboard (Tổng quan)

**Purpose:** One-glance financial health + proactive suggestions.

```
┌──────────────────────────────────────────┐
│  Chào buổi sáng, Mai 👋                  │  ← time-of-day greeting
│                                          │
│  ┌──────────────────────────────────┐    │
│  │  Tháng 4 · 2026       ↻         │    │  ← gradient header card
│  │  ─ 3.450.000đ                   │    │
│  │  Chi tiêu  ·  23 giao dịch      │    │
│  │  ┌──────────┐  ┌──────────┐     │    │
│  │  │ Chi ra   │  │ Nhận vào │     │    │
│  │  │ 3.45M    │  │ 15.0M    │     │    │
│  │  └──────────┘  └──────────┘     │    │
│  └──────────────────────────────────┘    │
│                                          │
│  [ Hôm nay ] [ Tuần ] [ Tháng ] ...     │  ← period selector
│                                          │
│  ─── Gợi ý từ Mai ──────────────────    │  ← nudge cards (max 2)
│  [Nudge Card — budget warning]           │
│                                          │
│  ─── Ngân sách tháng này ───────────    │  ← mini budget preview
│  Ăn uống  ████████░░░  60%  800k còn    │
│  Cà phê   ████████████  90% ⚠ gần đầy  │
│  Xem tất cả →                            │
│                                          │
│  ─── Chi theo danh mục ─────────────    │
│  [Donut chart]                           │
│  ● Ăn uống    1.2M   35%                │
│  ...                                     │
│                                          │
│  ─── Giao dịch gần đây ─────────────    │
│  [Transaction Card]                      │
│  [Transaction Card]                      │
│  Xem tất cả →                            │
└──────────────────────────────────────────┘
```

**Behaviour:**

- Default period: "Tháng này"
- Trend % compares to the same period previous month/week
- Mini budget preview shows top 3 categories by spend; "Xem tất cả" navigates to Kế hoạch → Ngân sách
- Nudge cards auto-dismissible, max 2 shown, ordered by priority
- Pull-to-refresh syncs from backend

**Dashboard Donut:** max 6 slices (remaining = "Khác"). Tap a slice → filter Transaction List to that category.

---

### 5.2 Transaction Capture Flow (Notification Confirm/Cancel)

**Trigger:** `NotificationListenerService` detects a bank notification.

**Step 1 — Local quick-parse**

On device: regex-extract candidate amount and direction (preview only). Authoritative parse happens on backend after confirmation.

```kotlin
data class NotificationPreview(
    val rawText: String,
    val candidateAmount: Long?,      // null if regex can't extract
    val candidateDirection: String?, // "inflow" | "outflow" | null
    val bankHint: String?,
    val capturedAt: Instant,
)
```

**Step 2 — Confirmation Bottom Sheet**

Slide up with `ModalBottomSheet`. On Android 12+ use `Notification.Builder.setFullScreenIntent` for lock-screen-equivalent appearance. Auto-dismiss after 60 seconds.

```
┌──────────────────────────────────────────┐
│  ▬▬▬▬▬                                   │  ← drag handle
│                                          │
│  🔔 Phát hiện giao dịch                 │
│                                          │
│  ┌──────────────────────────────────┐    │
│  │  Techcombank                     │    │
│  │  ─ 450.000đ                      │    │  ← large, Outflow rose
│  │  "Thanh toan GrabFood..."        │    │  ← raw text, 2-line truncate
│  └──────────────────────────────────┘    │
│                                          │
│  Giao dịch này có đúng không?            │
│                                          │
│  [ ❌  Bỏ qua  ]   [ ✅  Ghi lại ]      │  ← equal weight, 50/50
│                                          │
│  ← Auto-huỷ sau 60s ─────────────●     │  ← progress bar
└──────────────────────────────────────────┘
```

**On "✅ Ghi lại":**

1. Dismiss sheet immediately (optimistic UI)
2. Show top snackbar: "Đang ghi…" with spinner
3. `POST /api/webhook/notification` with `{raw_text, bank_hint, timestamp}`
4. On success → snackbar: "✅ Đã ghi [amount]" for 2 s, Dashboard background refresh
5. On failure → enqueue to offline Room queue, snackbar: "📴 Sẽ ghi khi có mạng"

**On "❌ Bỏ qua":** Dismiss silently. Nothing sent.
**On auto-dismiss (60s):** Same as Bỏ qua.

**Offline queue (WorkManager):**

- Room table: `pending_transactions(id, raw_text, bank_hint, captured_at, retry_count)`
- Periodic check every 5 min; max 3 retries; failed → badge on Dashboard

**Sheet display states:**

| State               | Amount display                | Behaviour                     |
| ------------------- | ----------------------------- | ----------------------------- |
| Amount found        | Large, coloured               | Show immediately              |
| Amount not found    | "Số tiền chưa rõ" grey italic | Show — user can still confirm |
| Bank hint found     | Bank name in header           | —                             |
| Bank hint not found | Omit bank name                | —                             |

---

### 5.3 Transaction List (Giao dịch)

```
┌──────────────────────────────────────────┐
│  Giao dịch                       🔍  ⚙  │
│  [ Hôm nay ] [ Tuần ] [ Tháng ] ...     │
│                                          │
│  Thứ Hai, 28/4                          │  ← sticky date header
│  [Transaction Card]                      │
│  [Transaction Card]                      │
│                                          │
│  Chủ Nhật, 27/4                         │
│  [Transaction Card]                      │
└──────────────────────────────────────────┘
```

**Transaction Detail Bottom Sheet** (tap any card):

```
┌──────────────────────────────────────────┐
│  ▬▬▬▬▬                                   │
│  ┌──┐  Highlands Coffee                  │
│  │☕│  ─ 45.000đ                          │  ← Headline size
│  └──┘                                    │
│  ─────────────────────────────────────   │
│  Danh mục    Cà phê / Trà sữa           │
│  Thời gian   14:32  Thứ Hai 28/4        │
│  Nguồn       Tin nhắn ngân hàng         │
│  Ngân hàng   Techcombank                │
│  Trạng thái  ● Chờ xác nhận             │  ← or ● Đã xác nhận (emerald)
│  ─────────────────────────────────────   │
│  [ 🗑️  Xoá ]          [ ✅  Xác nhận ]  │  ← hidden if locked=true
└──────────────────────────────────────────┘
```

- "Đã xác nhận" emerald badge replaces action buttons when `locked=true`
- Delete: show confirmation dialog first ("Xoá giao dịch này? Bạn cần nhập lại nếu muốn theo dõi.")

---

### 5.4 Kế hoạch — Ngân sách (Budget)

**Purpose:** Monthly budget setup and spend tracking per category.

```
┌──────────────────────────────────────────┐
│  [ Ngân sách ] [ Mục tiêu ] [ Định kỳ ] │  ← top chip tabs
│  ─────────────────────────────────────   │
│  ┌──────────────────────────────────┐    │
│  │  Tháng 4 · 2026        12 ngày  │    │  ← gradient header card
│  │  Chi: 3.450.000 / 5.000.000đ    │    │
│  │  ██████████████░░░░░░░░  69%    │    │  ← overall progress bar
│  │  Còn 1.550.000đ                 │    │
│  └──────────────────────────────────┘    │
│                                          │
│  ─── Theo danh mục ─────────────────    │
│  [Budget Progress Card — Ăn uống 60%]   │
│  [Budget Progress Card — Cà phê 90% ⚠] │
│  [Budget Progress Card — Di chuyển 45%] │
│  [Budget Card — "Chưa đặt" Shopping]    │
│                                          │
│                          [ + Thêm ]  ←  FAB bottom-right
└──────────────────────────────────────────┘
```

**Budget Detail Bottom Sheet** (tap any category card):

```
┌──────────────────────────────────────────┐
│  ▬▬▬▬▬                                   │
│  🍽  Ăn uống                             │
│                                          │
│  Ngân sách tháng:  [ 2.000.000đ    ▶ ]  │  ← inline editable amount
│                                          │
│  ████████████████░░░░░░  60%            │  ← large progress bar
│  Đã chi 1.200.000đ  ·  Còn 800.000đ    │
│                                          │
│  12 giao dịch tháng này                  │
│  [mini transaction list, last 3]         │
│                                          │
│  Lặp lại tháng sau?        [ ON  ]      │  ← auto-renew toggle
│                                          │
│  [ Xoá ngân sách ]    [ Lưu thay đổi ]  │
└──────────────────────────────────────────┘
```

**Set / Edit Budget:**

- Tap the amount field → inline number picker (Vietnamese-style keyboard)
- Amount in VND, thousands-separated
- After save → optimistic update card colour + progress bar animation

**Empty state:**

```
  💰
  "Chưa có ngân sách nào.
   Đặt ngân sách để Mai giúp bạn theo dõi nhé!"
  [ Đặt ngân sách đầu tiên ]
```

---

### 5.5 Kế hoạch — Mục tiêu (Goals)

**Purpose:** Savings goals with progress tracking and projected completion.

```
┌──────────────────────────────────────────┐
│  [ Ngân sách ] [ Mục tiêu ] [ Định kỳ ] │
│  ─────────────────────────────────────   │
│  Đang tiết kiệm: 28.000.000đ tổng cộng  │  ← summary chip
│                                          │
│  [Goal Progress Card — Mua laptop 65%]  │
│  [Goal Progress Card — Du lịch 32%]     │
│  [Goal Progress Card — Quỹ khẩn cấp 88%]│
│                                          │
│                          [ + Thêm ]  ←  FAB
└──────────────────────────────────────────┘
```

**Goal Detail Bottom Sheet:**

```
┌──────────────────────────────────────────┐
│  ▬▬▬▬▬                                   │
│  🎯  Mua laptop                          │
│                                          │
│          ┌────────────────────┐          │
│          │    ◯◯◯  65%        │          │  ← large circular ring
│          │  13.0M / 20.0M     │          │     Primary colour
│          └────────────────────┘          │
│                                          │
│  Dự kiến hoàn thành: Tháng 8/2026       │
│  (Còn 7.000.000đ · ~3 tháng nữa)        │
│                                          │
│  ─── Lịch sử đóng góp ──────────────    │
│  [mini bar chart — 6 months]             │
│  T10  T11  T12  T1   T2   T3            │
│  1.2M 0.8M 1.5M 1.0M 2.0M 1.5M         │
│                                          │
│  Đóng góp thêm:  [ 500.000đ       ▶ ]  │
│                                          │
│  [ Xoá mục tiêu ]    [ Cập nhật ]       │
└──────────────────────────────────────────┘
```

**Goal states:**

| State           | Visual                                                       |
| --------------- | ------------------------------------------------------------ |
| In progress     | `Primary` ring, normal card                                  |
| Achieved (100%) | `Inflow` ring, emerald `Success Bg`, 🏆 icon, micro-confetti |
| Behind pace     | `Warning` ring + "Đang chậm tiến độ" caption                 |
| Paused          | Greyed card, "Tạm dừng" badge                                |

**Set Goal Sheet** (FAB tap):

1. Goal name (text field)
2. Target amount (number picker)
3. Target date (month/year picker)
4. Starting amount (optional)

**Empty state:**

```
  🎯
  "Chưa có mục tiêu nào.
   Bạn đang tiết kiệm cho điều gì?"
  [ Tạo mục tiêu đầu tiên ]
```

---

### 5.6 Kế hoạch — Định kỳ (Subscriptions)

**Purpose:** Track recurring charges, get reminders before due dates.

```
┌──────────────────────────────────────────┐
│  [ Ngân sách ] [ Mục tiêu ] [ Định kỳ ] │
│  ─────────────────────────────────────   │
│  ┌──────────────────────────────────┐    │
│  │  Tổng định kỳ hàng tháng         │    │  ← summary card
│  │  ─ 350.000đ / tháng             │    │
│  │  3 khoản  ·  2 cần thanh toán   │    │
│  └──────────────────────────────────┘    │
│                                          │
│  ─── Cần thanh toán ────────────────    │  ← overdue + due soon
│  [Sub Card — Netflix  Hôm nay ⚠]       │
│  [Sub Card — Spotify  3 ngày nữa]       │
│                                          │
│  ─── Tháng này ─────────────────────    │
│  [Sub Card — iCloud+  15/4 ✓ Đã trả]   │
│  [Sub Card — Gym  20/4]                 │
│                                          │
│                          [ + Thêm ]  ←  FAB
└──────────────────────────────────────────┘
```

**Subscription Detail Bottom Sheet:**

```
┌──────────────────────────────────────────┐
│  ▬▬▬▬▬                                   │
│  ┌────┐  Netflix                         │
│  │ 🎬 │  Hàng tháng  ·  ─ 130.000đ      │
│  └────┘                                  │
│                                          │
│  Ngày thanh toán tiếp:  28/4/2026        │
│  [ Hôm nay ⚠ ]                          │  ← due-date chip
│                                          │
│  Lịch sử:                                │
│  ✓ 28/3    ✓ 28/2    ✓ 28/1            │
│                                          │
│  [ Xoá định kỳ ]   [ ✅ Đánh dấu đã trả ]│
└──────────────────────────────────────────┘
```

**Mark as paid:** swipe right on any sub card → emerald flash + "✅ Đã thanh toán" snackbar → `next_charge_date` advances to next cycle.

**Add Subscription Sheet:**

1. Name (text) + icon picker (emoji or from preset list)
2. Amount (number picker)
3. Frequency: `Hàng tuần | Hàng tháng | Hàng năm`
4. First charge date (date picker)

**Empty state:**

```
  🔄
  "Chưa có phí định kỳ nào.
   Thêm để Mai nhắc bạn trước khi đến hạn!"
  [ Thêm phí định kỳ ]
```

---

### 5.7 Analytics (Phân tích)

**Purpose:** Period comparisons, category trends, spending vs average.

```
┌──────────────────────────────────────────┐
│  Phân tích                               │
│  ─────────────────────────────────────   │
│  [  So sánh  ]  [  Xu hướng  ]          │  ← top tabs
│                                          │
│  ─── So sánh ───────────────────────    │
│  [ Tuần này vs Tuần trước  ▾ ]          │  ← period pair selector
│                                          │
│  ┌──────────┐        ┌──────────┐        │
│  │ Tuần này │        │ Tuần tr. │        │
│  │ 1.200.000│        │  980.000 │        │
│  │  ↑ +22%  │        │          │        │
│  └──────────┘        └──────────┘        │
│                                          │
│  [  Grouped bar chart — Vico  ]          │
│                                          │
│  Danh mục      Tuần này  Tuần tr.   Δ   │
│  Ăn uống       450k      380k    +18%   │
│  Cà phê        200k      150k    +33%   │
│  Di chuyển     300k      280k     +7%   │
└──────────────────────────────────────────┘
```

```
│  ─── Xu hướng ──────────────────────    │
│  Chi tiêu 8 tuần gần nhất               │
│  [ Line chart — Vico ]                  │
│                                          │
│  Trung bình / tuần   1.050.000đ         │
│  Cao nhất            1.450.000đ         │
│  Thấp nhất             780.000đ         │
│                                          │
│  ┌──────────────────────────────────┐    │
│  │  ⚠  Tuần này cao hơn TB 14% ↑   │    │  ← callout card, Warning bg
│  └──────────────────────────────────┘    │
```

**Chart library:** `Vico` (Compose-native, MIT licence). Cache backend response locally 5 min (Room).

---

### 5.8 User Profile (Hồ sơ)

**Purpose:** Personal dashboard and configuration entry point.

```
┌──────────────────────────────────────────┐
│  Hồ sơ                                   │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │  ┌────┐  Nguyễn Văn A             │  │  ← gradient header
│  │  │ 👤 │  @nva_chiwi                │  │
│  │  └────┘  Thành viên từ 04/2026     │  │
│  └────────────────────────────────────┘  │
│                                          │
│  ─── Hoạt động ───────────────────────   │
│  🔥 Chuỗi tiết kiệm: 5 tuần              │
│  🎯 Mục tiêu hoàn thành: 2               │
│  🏆 Hạng: Người chi tiêu thông thái      │
│                                          │
│  ─── Menu ────────────────────────────   │
│  ⚙  Cài đặt hệ thống                    │  → navigates to Settings
│  📊 Báo cáo định kỳ                     │
│  💬 Hỗ trợ từ Mai                       │
│  📦 Xuất dữ liệu (CSV)                  │
│  🚪 Đăng xuất                           │
└──────────────────────────────────────────┘
```

---

### 5.9 Settings (Cài đặt)

**Purpose:** Granular control over app behavior and data.

```
┌──────────────────────────────────────────┐
│  Cài đặt                          Lưu    │
│                                          │
│  ─── Ghi nhận giao dịch ─────────────   │
│  Tự động ghi thông báo      [ ON  ]     │
│  Hỏi lại trước khi ghi      [ ON  ]     │
│  Ngân hàng đang theo dõi (5)  →         │  ← Bank allowlist selection
│  Thời gian tự huỷ (giây)    [ 60  ]     │
│                                          │
│  ─── Trợ lý ảo (Mai) ────────────────   │
│  Tông giọng:      [ Thân thiện ▾ ]      │
│  Tần suất nudge:   [ Hàng ngày  ▾ ]      │
│  Giờ im lặng      22:00 – 07:00         │
│                                          │
│  ─── Bảo mật & Dữ liệu ──────────────   │
│  Khoá ứng dụng (Biometric)  [ ON  ]     │
│  Ẩn số tiền trên Dashboard  [ OFF ]     │
│  Xoá bộ nhớ đệm (12MB)      [ Clear ]   │
│                                          │
│  ─── Kết nối ────────────────────────   │
│  Telegram ID: 123456789                 │
│  Backend: chiwi.mydomain.com            │
└──────────────────────────────────────────┘
```

**Bank Allowlist Selector:**
A sub-screen with a checklist of bank package names.

- [x] Vietcombank (com.VCB)
- [x] Techcombank (com.TCB)
- [ ] MoMo (com.momo)
- [ ] Add custom package...

---

## 6. Nudge System (Behavioral Notifications)

The Behavioral Agent (backend `src/agents/behavioral.py`) emits structured nudges. The mobile app surfaces them two ways:

### 6.1 In-App Nudge Cards (Dashboard)

Nudge cards appear in the "Gợi ý từ Mai" section of the Dashboard (Section 5.1). Max 2 visible at once. Cards are persisted locally until dismissed or 24 h elapsed.

**Priority order** (highest first):

1. Overdue subscription (rose)
2. Budget exceeded (rose)
3. Near-budget warning 90% (amber)
4. Spending spike (amber)
5. Impulse detection (violet)
6. Subscription due in 3 days (amber)
7. Goal milestone (indigo)
8. Saving streak (emerald)

### 6.2 Push Notifications

Android push notification design for each nudge type:

```
┌────────────────────────────────────────────────┐
│ 💳  ChiWi · Cảnh báo ngân sách                 │
│                                                │
│ Ngân sách Ăn uống đã dùng 92%.                │
│ Còn 160.000đ cho 8 ngày còn lại.              │
│                                                │
│ [ Xem ngân sách ]   [ Bỏ qua ]                │
└────────────────────────────────────────────────┘
```

**Notification templates by type:**

| Type                  | Icon | Title                     | Body                                                            |
| --------------------- | ---- | ------------------------- | --------------------------------------------------------------- |
| Budget warning        | 💳   | "Cảnh báo ngân sách"      | "[Category] đã dùng [%]. Còn [amount] cho [N] ngày."            |
| Budget exceeded       | 🚨   | "Vượt ngân sách"          | "[Category] đã vượt [amount]. Cân nhắc điều chỉnh nhé!"         |
| Spending spike        | 📈   | "Chi tiêu tăng đột biến"  | "Tuần này chi [category] cao hơn tuần trước [%]."               |
| Impulse detection     | 💡   | "Ghi nhận chi tiêu"       | "Vừa có [N] giao dịch [category] trong [time]. Mọi thứ ổn chứ?" |
| Subscription reminder | 🔔   | "Phí định kỳ sắp đến hạn" | "[Name] ─ [amount] sẽ đến hạn [date]."                          |
| Goal milestone        | 🏆   | "Tiến độ mục tiêu"        | "Bạn đã đạt [%] mục tiêu [name]! Còn [amount] nữa thôi."        |
| Saving streak         | 🔥   | "Chuỗi tiết kiệm"         | "[N] tuần liên tiếp chi tiêu dưới ngân sách. Tuyệt vời!"        |

### 6.3 Notification Channels (Android)

```kotlin
channels:
  chiwi_nudge         — "Gợi ý từ Mai"        — importance MEDIUM (no sound)
  chiwi_budget_alert  — "Cảnh báo ngân sách"  — importance HIGH (sound once)
  chiwi_subscription  — "Phí định kỳ"          — importance DEFAULT
  chiwi_capture       — "Ghi giao dịch"        — importance HIGH
```

Users can disable individual channels via System Settings without affecting others.

### 6.4 Quiet Hours

Configured in Profile (default 22:00–07:00 local time). Nudges generated during quiet hours are queued and delivered at 07:01. Subscription reminders due _today_ bypass quiet hours from 08:00 onwards.

---

## 7. Interaction Patterns

### 7.1 Snackbar Feedback

Top snackbar (below status bar — nav bar occupies bottom):

| Trigger                  | Message                           | Duration   |
| ------------------------ | --------------------------------- | ---------- |
| Transaction sent         | "✅ Đã ghi [amount]"              | 2 s        |
| Transaction deleted      | "🗑️ Đã xoá" + **Hoàn tác** action | 5 s        |
| Subscription marked paid | "✅ Đã thanh toán [name]"         | 2 s        |
| Goal contribution saved  | "🎯 Đã cộng [amount] vào [goal]"  | 2 s        |
| Budget saved             | "💰 Đã lưu ngân sách [category]"  | 2 s        |
| Offline queued           | "📴 Sẽ ghi khi có mạng"           | 3 s        |
| Sync error               | "⚠ Không thể kết nối — thử lại"   | persistent |

### 7.2 Undo Delete

Transaction delete → 5-second snackbar with Undo. Backend call deferred 5 s. Tap Undo cancels the call.

### 7.3 Budget Progress Animation

When a Budget Progress Card becomes visible (scroll into view or initial load), the bar animates from 0 to fill width over 600 ms using `EaseOutCubic`. Colour transitions animate over 300 ms when the % crosses 70% or 90%.

### 7.4 Goal Ring Animation

Circular ring draws from 0° to target angle over 800 ms using `EaseOutBack` (slight overshoot for a satisfying feel). On 100% achievement: ring flashes `Inflow` emerald + particle confetti (Compose `Canvas`-based, 1-time only).

### 7.5 Swipe Actions

- **Subscription card — swipe right:** Emerald overlay, ✅ icon reveals. Release to "mark paid".
- **Subscription card — swipe left:** Rose overlay, 🗑 icon reveals. Release to open delete confirmation.
- **Nudge card — swipe up / right:** Dismiss. No backend call — dismissed state stored in local `DataStore`.
- Transaction list swipe is handled via the Transaction Detail sheet (no inline swipe on the list to avoid accidental actions).

### 7.6 Empty States

| Screen                      | Message                                                               | Illustration             |
| --------------------------- | --------------------------------------------------------------------- | ------------------------ |
| Dashboard (no transactions) | "Chưa có giao dịch nào. Bật thông báo ngân hàng để Mai tự ghi nhé!"   | Waving character         |
| Budget (none set)           | "Chưa có ngân sách nào. Đặt ngân sách để Mai giúp bạn theo dõi nhé!"  | Wallet illustration      |
| Goals (none set)            | "Bạn đang tiết kiệm cho điều gì? Tạo mục tiêu đầu tiên đi!"           | Flag/target illustration |
| Subscriptions (none)        | "Chưa có phí định kỳ. Thêm để Mai nhắc bạn trước khi đến hạn!"        | Calendar illustration    |
| Analytics (not enough data) | "Cần ít nhất 2 tuần dữ liệu để so sánh. Mai sẽ thông báo khi đủ nhé!" | Bar chart illustration   |

### 7.7 Loading States

- **Shimmer placeholders** (matching content shape) during initial load — never spinners in content areas
- Transaction card skeleton: grey rectangles at icon + text + amount positions
- Budget progress card skeleton: icon + two grey bars
- Goal ring skeleton: grey circle ring placeholder
- Charts: grey rectangle while data loads → animate data in via `Vico` built-in entry animation

### 7.8 Pull to Refresh

Standard `SwipeRefresh` on all main content screens. Syncs from backend and updates Room cache.

---

## 8. Notification Capture — Technical Notes (Android)

```
NotificationListenerService
    ↓ filters by known bank package names / notification patterns
LocalQuickParser (regex, no network)
    ↓ produces NotificationPreview
CaptureViewModel
    ↓ posts to ConfirmationSheetActivity (or Composable overlay)
    ↓ on confirm → TransactionSendUseCase
        ↓ if online → POST /api/webhook/notification
        ↓ if offline → Room:pending_transactions
WorkManager (periodic, 5 min)
    ↓ retries pending_transactions (max 3)
    ↓ after 3 failures → mark "failed", show Dashboard badge
```

**Bank package filter list** (expandable, loaded from remote config):

```
com.vietcombank.vcbdigibank
com.techcombank.mb.ios
com.mservice.momotransfer
vn.com.agribank.agribankplus
com.bidv.smartbanking
... (add per bank)
```

**Permission flow (first launch):**

1. Notification Access (`Settings > Notification Access`) — show rationale card before directing
2. Battery optimisation exemption (`Settings > Battery`) — show rationale card
3. Notification permission (Android 13+, `POST_NOTIFICATIONS`)

---

## 9. API Contract (Mobile ↔ Backend)

All requests carry `X-User-Id: {telegram_user_id}` header.

### 9.1 Transactions

| Method   | Path                          | Purpose                                               |
| -------- | ----------------------------- | ----------------------------------------------------- |
| `POST`   | `/api/webhook/notification`   | Submit captured bank notification                     |
| `GET`    | `/api/transactions`           | Fetch list (`period`, `category_id`, `page`, `limit`) |
| `GET`    | `/api/transactions/{id}`      | Fetch single transaction                              |
| `DELETE` | `/api/transactions/{id}`      | Delete transaction                                    |
| `POST`   | `/api/transactions/{id}/lock` | Confirm/lock a transaction                            |

### 9.2 Dashboard & Analytics

| Method | Path                     | Purpose                                        |
| ------ | ------------------------ | ---------------------------------------------- |
| `GET`  | `/api/dashboard/summary` | Totals + category breakdown for period         |
| `GET`  | `/api/analytics/compare` | Period comparison (`period_a`, `period_b`)     |
| `GET`  | `/api/analytics/trend`   | Trend series (`period=weekly\|monthly`, `n=8`) |

### 9.3 Budget

| Method   | Path                | Purpose                         |
| -------- | ------------------- | ------------------------------- |
| `GET`    | `/api/budgets`      | List all budgets for user       |
| `POST`   | `/api/budgets`      | Create budget for a category    |
| `PUT`    | `/api/budgets/{id}` | Update budget amount / settings |
| `DELETE` | `/api/budgets/{id}` | Remove budget                   |

### 9.4 Goals

| Method   | Path              | Purpose                        |
| -------- | ----------------- | ------------------------------ |
| `GET`    | `/api/goals`      | List all goals                 |
| `POST`   | `/api/goals`      | Create goal                    |
| `PUT`    | `/api/goals/{id}` | Update goal / add contribution |
| `DELETE` | `/api/goals/{id}` | Remove goal                    |

### 9.5 Subscriptions

| Method   | Path                                | Purpose                               |
| -------- | ----------------------------------- | ------------------------------------- |
| `GET`    | `/api/subscriptions`                | List subscriptions (active, upcoming) |
| `POST`   | `/api/subscriptions`                | Create subscription                   |
| `PUT`    | `/api/subscriptions/{id}`           | Update subscription                   |
| `POST`   | `/api/subscriptions/{id}/mark-paid` | Advance next_charge_date              |
| `DELETE` | `/api/subscriptions/{id}`           | Deactivate subscription               |

### 9.6 Profile & Nudges

| Method | Path                       | Purpose                                         |
| ------ | -------------------------- | ----------------------------------------------- |
| `GET`  | `/api/profile`             | User profile and notification preferences       |
| `PUT`  | `/api/profile`             | Update preferences (nudge toggles, quiet hours) |
| `GET`  | `/api/nudges/pending`      | Fetch undelivered nudges for in-app display     |
| `POST` | `/api/nudges/{id}/dismiss` | Mark nudge as dismissed                         |

> **Implementation status:** `POST /api/webhook/notification` and `POST /api/webhook/telegram` already exist. All other endpoints need to be added as new FastAPI routes.

---

## 10. Accessibility

- Minimum contrast ratio: **4.5:1** for body text (WCAG AA)
- All interactive elements: minimum **48 × 48 dp** touch target
- Amount colours (rose/emerald) are **never the sole differentiator** — always paired with `─`/`+` prefix and directional icon
- Progress bars have `semanticsRole = "progressbar"` with `stateDescription = "X phần trăm"`
- All icons have `contentDescription`; decorative icons use `contentDescription = null`
- Support dynamic font sizes (no hard-clipping text containers)
- TalkBack: transaction cards announce as "[merchant] [direction] [amount] [category] [time]"
- TalkBack: budget cards announce as "[category] ngân sách [percent] phần trăm. Còn [amount]."
- TalkBack: goal rings announce as "[name] [percent] phần trăm. Còn [remaining]."

---

## 11. Design File Checklist (Figma)

- [x] Colour styles defined per Section 2.1 (including gradient tokens)
- [x] Text styles defined per Section 2.2
- [x] 8-dp grid enabled on all frames
- [ ] **Components:** Transaction Card, Summary Header Card (gradient), Budget Progress Card (3 states), Goal Progress Card (ring), Subscription Card (5 due-date states), Nudge Card (6 types), Period Selector, Primary Button, Destructive Button, Snackbar, Confirmation Sheet, Section Chip Tab Bar
- [ ] **Screens (390 × 844 baseline, also at 360 × 800 and 412 × 915):**
  - [ ] Dashboard (with nudge cards, mini budget, donut, recent transactions)
  - [ ] Notification Capture Bottom Sheet (all states)
  - [ ] Transaction List + Transaction Detail Sheet
  - [ ] Kế hoạch — Ngân sách (list + Budget Detail Sheet + Set Budget Sheet)
  - [ ] Kế hoạch — Mục tiêu (list + Goal Detail Sheet + Set Goal Sheet)
  - [ ] Kế hoạch — Định kỳ (list + Sub Detail Sheet + Add Sub Sheet)
  - [ ] Analytics (So sánh + Xu hướng tabs)
  - [x] User Profile (Section 5.8)
  - [x] Settings (Section 5.9)
- [ ] Empty states illustrated (all 5 screens)
- [ ] Loading skeleton frames (all content areas)
- [ ] Nudge push notification mockup (6 types)
- [ ] Dark mode variants: `Neutral 50` → `#121212`, `Surface` → `#1E1E2E`, gradient → `#4F46E5` → `#1E1B4B`, text colours adjusted for contrast
- [ ] Swipe gesture overlays (subscription card swipe states)
- [ ] Goal ring animation storyboard (0% → fill → 100% confetti)
