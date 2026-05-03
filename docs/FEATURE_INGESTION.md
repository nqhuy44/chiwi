# Feature: Auto Transaction Ingestion

## Summary

Automatically captures bank transaction notifications from Android (MacroDroid/Tasker) and iOS (Shortcuts) devices, parses them using Gemini AI, and stores structured financial data — all with zero manual input.

## User Story

> As a user, I want my bank notifications to be automatically captured and logged so that I never have to manually record a transaction.

## How It Works

1. **Android**: ChiWi native app intercepts bank notifications via `NotificationListenerService`.
2. **Analysis**: The native app sends the raw text to `POST /api/mobile/analyze-notification`.
3. **Ingestion Agent**: Gemini Flash extracts the transaction amount, merchant, time, and direction.
4. **Tagging Agent**: Classifies category based on historical context.
5. **Confirmation**: The Android app presents the parsed transaction to the user for confirmation.
6. **Approval**: Upon confirmation, the app sends `POST /api/mobile/approve-pending` to persist the transaction in the database.
7. **iOS**: Shortcuts automation triggers on bank SMS → sends content to ChiWi API via "Get Contents of URL" (Legacy/Fallback).

## API Contract

The primary endpoints for ingestion have been migrated to the Mobile API. Please refer to `MOBILE_API.md` for full request/response schemas:
- `POST /api/mobile/analyze-notification`
- `POST /api/mobile/approve-pending`

(Legacy webhook `/api/webhook/notification` is retained for iOS Shortcuts support).

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
| Non-financial notification | Agent returns `is_transaction: false`, silently ignored by mobile app |
| Duplicate (same amount + 5 min window) | (Handled by backend transaction repository logic) |
| Low confidence parse | User manually corrects fields in the mobile app before approval |
| Missing permissions | Mobile app prompts user to enable Notification Access in System Settings |

## Setup Guide (Android)

1. Open the ChiWi Android App.
2. Go to **Profile** (Cài đặt).
3. Toggle **Tự động phát hiện** (Auto-detect).
4. Grant **Notification Access** (Quyền truy cập thông báo) in Android System Settings when prompted.
5. Select the specific banking apps to monitor in the **Chọn ứng dụng theo dõi** menu.
