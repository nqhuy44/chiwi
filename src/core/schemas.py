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
    source: str  # "macrodroid", "tasker", "ios_shortcut"
    app_package: str | None = None
    notification_title: str | None = None
    notification_text: str
    timestamp: str


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


class NudgeRequest(BaseModel):
    user_id: str
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


# --- API Responses ---


class WebhookResponse(BaseModel):
    status: str
    transaction_id: str | None = None
    parsed: dict | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "chiwi"
    version: str = "0.1.0"
