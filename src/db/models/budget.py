from datetime import UTC, datetime
from typing import Literal
from beanie import Document
from pydantic import Field


class BudgetDocument(Document):
    """Mutable budget config. Every change to this document also creates
    a BudgetEventDocument for the audit trail."""

    user_id: str
    category_id: str                        # stable category slug
    limit_amount: float                     # base recurring limit
    period: Literal["daily", "weekly", "monthly"]
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None      # set whenever limit_amount changes

    # Silence — still tracks but never fires a nudge notification.
    # System can still reference budget status in behavioral analysis / criticism.
    is_silenced: bool = False
    silenced_at: datetime | None = None

    # Temporary override — replaces limit_amount for exactly one cycle.
    # Expires automatically when temp_limit_expires_at passes.
    temp_limit: float | None = None
    temp_limit_expires_at: datetime | None = None
    temp_limit_reason: str | None = None

    class Settings:
        name = "budgets"


class BudgetEventDocument(Document):
    """Immutable audit log of every user action on a budget."""

    user_id: str
    budget_id: str                          # references BudgetDocument._id
    category_id: str
    event_type: Literal[
        "created",
        "limit_updated",                    # base limit changed up or down
        "temp_override_set",                # temporary single-cycle override
        "silenced",                         # user silenced notifications
        "unsilenced",                       # user re-enabled notifications
        "disabled",                         # budget turned off entirely
        "reactivated",                      # budget turned back on
    ]
    old_value: dict = Field(default_factory=dict)   # snapshot of changed fields before
    new_value: dict = Field(default_factory=dict)   # snapshot of changed fields after
    reason: str | None = None                       # user-provided context if any
    triggered_by: Literal["user", "system"] = "user"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "budget_events"
