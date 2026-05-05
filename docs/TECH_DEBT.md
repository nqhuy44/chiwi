# Technical Debt & Future Roadmap

This document tracks known limitations, technical debt, and planned architectural enhancements for the ChiWi ecosystem.

## 1. Android: In-App Transaction Capture (Accessibility Service)

### Problem
When a user is actively using a banking or payment app (e.g., MoMo, VCB) to perform an outflow transaction, the source app may suppress system notifications since the user is already in the foreground. This causes the `NotificationListenerService` to miss the transaction event.

### Proposed Solution: `ChiWiAccessibilityService`
Implement an Android `AccessibilityService` to monitor the window content of specific financial applications.

- **Mechanics**:
  - Listen for `TYPE_WINDOW_STATE_CHANGED` and `TYPE_WINDOW_CONTENT_CHANGED` events.
  - Filter by package names (com.mservice.momoplus, com.vcb, etc.).
  - Traverse the `AccessibilityNodeInfo` tree to identify "Transaction Success" patterns.
  - Extract `amount`, `merchant/description`, and `timestamp` directly from the screen text.
- **Workflow**:
  1. Identify a "Success" screen.
  2. Scrape transaction details.
  3. Send to `POST /api/mobile/analyze-notification` with a new source flag `source: "accessibility"`.
  4. Prompt user for confirmation within the ChiWi app.

### Considerations
- **Privacy**: Requires sensitive permissions. Must implement strict package filtering to ensure non-financial apps are never inspected.
- **Battery**: Event-driven processing should minimize impact, but constant UI tree traversal can be resource-intensive.
- **Play Store Compliance**: Google has strict policies on Accessibility Service usage. If distribution is via Play Store, this must be clearly justified as a financial automation feature.

---

## 2. SMS Fallback Ingestion

### Problem
Legacy banking notifications or areas with poor data connectivity may rely on SMS.

### Proposed Solution
Implement a `BroadcastReceiver` for `android.provider.Telephony.SMS_RECEIVED`.
- Extract sender and body.
- Match against known bank SMS shortcodes.
- Forward to the ingestion pipeline.

---

## 3. Real-time Dashboard Sync (WebSockets)

### Problem
The mobile app currently relies on polling or manual refresh to update the dashboard after a transaction is approved.

### Proposed Solution
Implement WebSockets or Server-Sent Events (SSE) to push dashboard invalidation signals to the mobile client immediately after a `TransactionDocument` is persisted.
