from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

# --- Agent Communication ---


class AgentMessage(BaseModel):
    agent_id: str
    event_type: str
    payload: dict
    metadata: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    chat_id: str


# --- Ingestion ---


class NotificationPayload(BaseModel):
    """Raw bank notification forwarded from the Android app.

    The Android app captures the notification text verbatim and sends it here.
    All AI parsing (amount, merchant, direction) is done server-side by the
    Ingestion Agent so parsing logic can be improved without a mobile release.
    """
    raw_text: str
    bank_hint: str | None = None   # optional bank name hint from Android (e.g. "Vietcombank")
    timestamp: str                  # ISO8601, when the notification was received on device


class ParsedTransaction(BaseModel):
    is_transaction: bool
    amount: float | None = None
    currency: str = "VND"
    direction: Literal["inflow", "outflow"] | None = None
    merchant_name: str | None = None
    transaction_time: datetime | None = None
    bank_name: str | None = None
    raw_text: str
    confidence: Literal["high", "medium", "low"] = "low"


# --- Tagging ---


class EnrichedTransaction(BaseModel):
    user_id: str
    source: str
    amount: float
    currency: str = "VND"
    direction: Literal["inflow", "outflow"]
    raw_text: str
    merchant_name: str | None = None
    category_name: str | None = None
    tags: list[str] = Field(default_factory=list)
    transaction_time: datetime
    agent_confidence: Literal["high", "medium", "low"] = "low"
    ai_metadata: dict = Field(default_factory=dict)


# --- Behavioral ---


class UserProfile(BaseModel):
    """Personalization profile loaded from `config/user_profiles.json`.

    Drives the Behavioral Agent's nudge tone and analogies. Stored outside
    the codebase so the user can tweak occupation/hobbies without redeploying.
    """

    occupation: str = ""
    hobbies: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    communication_tone: Literal["friendly", "playful", "formal", "concise"] = "friendly"
    nudge_frequency: Literal["off", "daily", "weekly"] = "daily"
    language: str = "vi"
    # IANA timezone for this user. All data is stored UTC; this is used
    # for day-boundary math (reports, budgets) and for formatting dates
    # in Gemini-generated narratives. Overrides settings.business_timezone.
    timezone: str = "Asia/Ho_Chi_Minh"
    # Required for the worker to deliver scheduled nudges. Stored in the
    # profile file rather than the DB so the user can edit it directly.
    chat_id: str = ""
    extras: dict = Field(default_factory=dict)


class NudgeRequest(BaseModel):
    user_id: str
    chat_id: str
    nudge_type: str
    trigger_data: dict = Field(default_factory=dict)


class NudgeResult(BaseModel):
    nudge_id: str
    message: str
    sent: bool
    blocked_reason: str | None = None


# --- Reporting ---


class ReportRequest(BaseModel):
    user_id: str
    report_type: Literal[
        "summary", "daily_summary", "weekly_summary", "monthly_report", "goal_progress"
    ]
    period: str  # e.g., "today", "this_week", "this_month"


class AnalysisRequest(BaseModel):
    user_id: str
    analysis_type: Literal["compare", "trend", "deep_dive"]
    period: str  # e.g., "this_week", "this_month"
    compare_period: str | None = None  # e.g., "last_week"
    category_filter: str | None = None  # e.g., "Ăn uống"


# --- Subscriptions ---


class SetSubscriptionRequest(BaseModel):
    user_id: str
    name: str
    merchant_name: str
    amount: float
    period: str  # "weekly" | "monthly" | "yearly"
    next_charge_date: datetime | None = None


# --- API Responses ---


class NotificationResponse(BaseModel):
    status: str
    transaction_id: str | None = None
    parsed: dict | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "chiwi"
    version: str = "0.1.0"


# --- Mobile API ---


class MobilePeriodStats(BaseModel):
    inflow: float
    outflow: float
    net: float
    tx_count: int


class MobileCategoryItem(BaseModel):
    name: str
    icon: str
    amount: float
    tx_count: int
    percent: float


class MobileTransactionItem(BaseModel):
    id: str
    amount: float
    direction: Literal["inflow", "outflow"]
    merchant: str | None
    category: str | None
    icon: str
    note: str
    timestamp: datetime
    locked: bool
    source: str


class MobileBudgetAlert(BaseModel):
    category: str
    icon: str
    spent: float
    limit: float
    percent_used: int


class MobileUpcomingSubscription(BaseModel):
    name: str
    amount: float
    due_in_days: int


class MobileDashboardResponse(BaseModel):
    computed_at: datetime
    is_cached: bool
    periods: dict[str, MobilePeriodStats]
    top_categories: list[MobileCategoryItem]
    recent_transactions: list[MobileTransactionItem]
    budget_alerts: list[MobileBudgetAlert]
    upcoming_subscriptions: list[MobileUpcomingSubscription]


class MobileTransactionListResponse(BaseModel):
    transactions: list[MobileTransactionItem]
    next_cursor: str | None
    total_in_period: int


class MobileBudgetItem(BaseModel):
    id: str
    category: str
    icon: str
    period: str
    limit: float
    spent: float
    remaining: float
    percent_used: int
    window_start: datetime
    window_end: datetime
    alert_enabled: bool


class MobileBudgetListResponse(BaseModel):
    budgets: list[MobileBudgetItem]


class MobileGoalItem(BaseModel):
    id: str
    name: str
    target_amount: float
    saved_amount: float
    percent_achieved: int
    monthly_needed: float | None
    deadline: datetime | None
    on_track: bool


class MobileGoalListResponse(BaseModel):
    goals: list[MobileGoalItem]


class MobileSubscriptionItem(BaseModel):
    id: str
    name: str
    amount: float
    period: str
    next_charge_date: datetime
    due_in_days: int
    is_overdue: bool


class MobileSubscriptionListResponse(BaseModel):
    subscriptions: list[MobileSubscriptionItem]
    monthly_total: float


class MobileNudgeItem(BaseModel):
    id: str
    type: str
    body: str
    sent_at: datetime


class MobileNudgeListResponse(BaseModel):
    nudges: list[MobileNudgeItem]


class MobileCategorySpendingResponse(BaseModel):
    period: str
    total_outflow: float
    breakdown: list[MobileCategoryItem]
