# Feature: Subscription Tracking & Synchronization

## Overview
ChiWi provides automated and manual tracking for recurring payments (Netflix, Spotify, Gym, etc.). To ensure a seamless cross-platform experience, the system uses a **Backend-Driven UI** approach for icons and standardized **Naive UTC** for database queries.

## 1. Icon Synchronization (Backend-Driven)
Previously, the Android app and Backend used separate logic for mapping merchants to icons, leading to inconsistencies (e.g., Spotify showing 🎵 on one screen and 🎧 on another).

### Current Implementation
- **Source of Truth**: The Backend (`src/core/categories.py`) is the single source of truth for merchant icons.
- **Mapping Logic**:
  - `resolve_merchant_icon(merchant_name, category_name)` matches the merchant name against a predefined list.
  - If no specific merchant match is found, it falls back to the category's default emoji.
- **Payload**: The `icon` field (Emoji string) is injected into:
  - `MobileSubscriptionItem` (Subscription List)
  - `MobileUpcomingSubscription` (Dashboard)
  - `MobileJustPaidSubscription` (Dashboard)
  - `MobileTransactionItem` (Transaction History)
- **Android UI**: The app prioritizes the server-provided `icon`. If null, it falls back to a local Material Icon set.

## 2. Transaction Visibility (Filtering & Timezones)
A common issue was transactions not appearing in the "Subscription Detail" history due to naming mismatches (e.g., subscription is "Spotify Premium" but transaction is "Spotify").

### Direct Linking
- Transactions are now filtered by `subscription_id` instead of merchant name.
- This ensures that 100% of linked transactions are visible in the subscription's history, regardless of the raw text or merchant name extracted by AI.

### Standardized UTC Queries
- **Problem**: MongoDB stores dates as naive UTC. If queries use "aware" datetimes (with timezone info), MongoDB might return empty results due to comparison mismatches.
- **Solution**: All date calculation utilities (`get_sliding_window`, `get_date_range` in `src/core/utils.py`) now return **Naive UTC** `datetime` objects.
- **Implementation**:
  ```python
  def _to_naive_utc(dt: datetime) -> datetime:
      if dt.tzinfo is not None:
          return dt.astimezone(UTC).replace(tzinfo=None)
      return dt
  ```

## 3. Mobile API Integration
- **Endpoint**: `GET /api/mobile/transactions`
- **New Parameter**: `subscription_id` (optional).
- **Behavior**: When provided, the API filters specifically for transactions linked to that subscription, ignoring other query parameters if necessary for history precision.
