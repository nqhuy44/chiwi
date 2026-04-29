"""
ChiWi Scheduled Worker

Runs cron-based jobs:
- Daily 08:00: Behavioral analysis (per profiled user)
- Weekly Monday 09:00: Report generation
- Hourly: Budget threshold checks

Phase 3.1 wires the behavioral fan-out plumbing only — for each user
listed in `config/user_profiles.json`, ``run_behavioral_analysis`` would
call ``_collect_triggers`` (Phase 3.2 territory) and dispatch any
resulting nudges through the orchestrator's ``scheduled`` route.
"""

import asyncio
import logging
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo



from src.core.config import settings
from src.core.dependencies import container
from src.core.profiles import get_profile
from src.core.spending_avg import SCOPE_TOTAL, compute_avg, compute_avg_all_categories
from src.core.utils import get_budget_window, get_date_range
from src.db.repositories.budget_repo import effective_limit

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trigger detection helpers
# ---------------------------------------------------------------------------


async def _subscription_triggers(user_id: str) -> list[dict]:
    """Fire subscription_reminder when next_charge_date ≤ 48 h away."""
    sub_repo = container.subscription_repo
    if not sub_repo:
        return []

    triggers: list[dict] = []
    upcoming = await sub_repo.find_upcoming(user_id, within_hours=48)
    for sub in upcoming:
        next_date = sub.next_charge_date
        triggers.append(
            {
                "nudge_type": "subscription_reminder",
                "trigger_data": {
                    "subscription_name": sub.name,
                    "merchant_name": sub.merchant_name,
                    "amount": sub.amount,
                    "period": sub.period,
                    "next_charge_date": next_date.strftime("%d/%m/%Y")
                    if next_date
                    else None,
                    "reason": "upcoming_charge",
                },
            }
        )
    return triggers


async def _budget_triggers(user_id: str) -> list[dict]:
    """Fire budget_warning (≥70%) or budget_exceeded (≥100%) for active budgets."""
    budget_repo = container.budget_repo
    txn_repo = container.transaction_repo
    if not budget_repo or not txn_repo:
        return []

    profile = await get_profile(user_id)
    now_utc = datetime.now(UTC).replace(tzinfo=None)

    budgets = await budget_repo.find_by_user(user_id)
    triggers: list[dict] = []

    for budget in budgets:
        # Silenced budgets are tracked but never fire nudges
        if budget.is_silenced:
            continue

        period = budget.period or "monthly"
        start_date, _ = get_budget_window(period, timezone=profile.timezone)
        if not start_date:
            continue

        category_id = budget.category_id or ""
        limit = effective_limit(budget, now_utc)
        if limit <= 0:
            continue

        txns = await txn_repo.find_by_user(
            user_id=user_id, start_date=start_date, end_date=now_utc, limit=200
        )
        spent = sum(
            t.amount
            for t in txns
            if t.direction == "outflow"
            and (t.category_id or "").lower() == category_id.lower()
        )

        usage_pct = (spent / limit) * 100
        is_temp = budget.temp_limit is not None

        if usage_pct >= 100:
            triggers.append(
                {
                    "nudge_type": "budget_exceeded",
                    "trigger_data": {
                        "category": category_id,
                        "limit_amount": round(limit),
                        "spent_amount": round(spent),
                        "usage_pct": round(usage_pct, 1),
                        "is_temp_override": is_temp,
                        "reason": "budget_exceeded",
                    },
                }
            )
        elif usage_pct >= 70:
            triggers.append(
                {
                    "nudge_type": "budget_warning",
                    "trigger_data": {
                        "category": category_id,
                        "limit_amount": round(limit),
                        "spent_amount": round(spent),
                        "usage_pct": round(usage_pct, 1),
                        "is_temp_override": is_temp,
                        "reason": "budget_at_70pct",
                    },
                }
            )

    return triggers


async def _spending_alert_trigger(user_id: str) -> dict | None:
    """Fire spending_alert when any category this week spikes >1.5× its 4-week average."""
    txn_repo = container.transaction_repo
    if not txn_repo:
        return None

    profile = await get_profile(user_id)
    _, cat_results = await compute_avg_all_categories(
        txn_repo, user_id, period="weekly", timezone=profile.timezone
    )

    spikes = [
        r for r in cat_results
        if r.has_baseline and r.pct_diff is not None and r.pct_diff >= 50
    ]
    if not spikes:
        return None

    top = max(spikes, key=lambda r: r.pct_diff or 0)
    return {
        "nudge_type": "spending_alert",
        "trigger_data": {
            "top_category": top.scope,
            "this_week_total": top.current,
            "weekly_avg": top.average,
            "spike_ratio": top.ratio,
            "pct_diff": top.pct_diff,
            "periods_used": top.periods_used,
            "reason": "category_spike",
        },
    }


async def _impulse_detection_trigger(user_id: str) -> dict | None:
    """Fire impulse_detection when ≥3 outflow transactions occurred in the last 24 h."""
    txn_repo = container.transaction_repo
    if not txn_repo:
        return None

    now_utc = datetime.now(UTC).replace(tzinfo=None)
    since = now_utc - timedelta(hours=24)

    txns = await txn_repo.find_by_user(
        user_id=user_id, start_date=since, end_date=now_utc, limit=50
    )
    outflows = [t for t in txns if t.direction == "outflow"]

    if len(outflows) < 3:
        return None

    return {
        "nudge_type": "impulse_detection",
        "trigger_data": {
            "count": len(outflows),
            "total_amount": round(sum(t.amount for t in outflows)),
            "reason": "multiple_purchases_24h",
        },
    }


async def _saving_streak_trigger(user_id: str) -> dict | None:
    """Fire saving_streak when ≥3 consecutive days of spending below the 14-day daily average."""
    txn_repo = container.transaction_repo
    if not txn_repo:
        return None

    profile = await get_profile(user_id)
    tz = ZoneInfo(profile.timezone)
    today_local = datetime.now(tz).date()

    # Need per-day totals — compute individually for streak detection
    baseline = await compute_avg(
        txn_repo, user_id, period="daily",
        scope=SCOPE_TOTAL, timezone=profile.timezone,
    )
    if not baseline.has_baseline or baseline.average == 0:
        return None

    # Check individual past days
    now_utc = datetime.now(UTC).replace(tzinfo=None)
    since = now_utc - timedelta(days=8)
    txns = await txn_repo.find_by_user(
        user_id=user_id, start_date=since, end_date=now_utc, limit=200
    )

    by_day: dict[date, float] = defaultdict(float)
    for t in txns:
        if t.direction == "outflow":
            raw_ts = t.transaction_time
            if raw_ts:
                local_dt = raw_ts.astimezone(tz) if raw_ts.tzinfo else raw_ts
                by_day[local_dt.date()] += t.amount

    streak = 0
    for i in range(1, 8):
        check_day = today_local - timedelta(days=i)
        day_total = by_day.get(check_day, 0)
        if day_total < baseline.average:
            streak += 1
        else:
            break

    if streak < 3:
        return None

    return {
        "nudge_type": "saving_streak",
        "trigger_data": {
            "streak_days": streak,
            "daily_avg": baseline.average,
            "periods_used": baseline.periods_used,
            "reason": "below_average_streak",
        },
    }


async def _goal_progress_triggers(user_id: str) -> list[dict]:
    """Fire goal_progress when an active goal crosses a 25/50/75% milestone."""
    goal_repo = container.goal_repo
    if not goal_repo:
        return []

    goals = await goal_repo.find_by_user(user_id, status="active")
    triggers: list[dict] = []

    for goal in goals:
        target = goal.target_amount
        current = goal.current_amount
        if target <= 0 or current <= 0:
            continue

        progress_pct = (current / target) * 100

        for milestone in (75, 50, 25):
            if progress_pct >= milestone:
                triggers.append(
                    {
                        "nudge_type": "goal_progress",
                        "trigger_data": {
                            "goal_name": goal.name,
                            "target_amount": round(target),
                            "current_amount": round(current),
                            "progress_pct": round(progress_pct, 1),
                            "milestone": milestone,
                            "reason": f"goal_milestone_{milestone}pct",
                        },
                    }
                )
                break

    return triggers


# ---------------------------------------------------------------------------
# Trigger collector
# ---------------------------------------------------------------------------


async def _collect_triggers(user_id: str) -> list[dict]:
    """Return a list of nudge payloads for ``user_id``.

    Each payload follows the ``scheduled`` event contract:
        {nudge_type, trigger_data: {...}}
    """
    triggers: list[dict] = []

    triggers.extend(await _subscription_triggers(user_id))
    triggers.extend(await _budget_triggers(user_id))

    alert = await _spending_alert_trigger(user_id)
    if alert:
        triggers.append(alert)

    impulse = await _impulse_detection_trigger(user_id)
    if impulse:
        triggers.append(impulse)

    streak = await _saving_streak_trigger(user_id)
    if streak:
        triggers.append(streak)

    triggers.extend(await _goal_progress_triggers(user_id))

    return triggers


# ---------------------------------------------------------------------------
# Scheduled jobs
# ---------------------------------------------------------------------------


async def _refresh_dashboard_caches() -> None:
    """Proactively recompute and cache the dashboard for all profiled users.

    Called after run_behavioral_analysis so the Android app home screen is
    always warm when the user opens it after the worker cycle.
    """
    dashboard_service = container.dashboard_service
    if not dashboard_service:
        return
    for user_id in await container.user_repo.list_active_user_ids():
        try:
            await dashboard_service.invalidate(user_id)
            await dashboard_service.get_or_compute(user_id)
            logger.info("Dashboard cache refreshed for user_id=%s", user_id)
        except Exception:
            logger.exception("Dashboard cache refresh failed for user_id=%s", user_id)


async def run_behavioral_analysis() -> None:
    """Fan-out: invoke the Behavioral Agent for every profiled user."""
    user_ids = await container.user_repo.list_active_user_ids()
    if not user_ids:
        logger.info("No user profiles configured — skipping behavioral run")
        return

    orchestrator = container.orchestrator
    for user_id in user_ids:
        profile = await get_profile(user_id)
        # We no longer skip if chat_id is missing, as nudges can be delivered via mobile app
        if profile.nudge_frequency == "off":
            continue

        triggers = await _collect_triggers(user_id)
        for trigger in triggers:
            payload = {
                "user_id": user_id,
                "chat_id": profile.chat_id,  # May be None, BehavioralAgent handles it
                "nudge_type": trigger["nudge_type"],
                "trigger_data": trigger.get("trigger_data") or {},
            }
            result = await orchestrator.route("scheduled", payload)
            logger.info(
                "Nudge dispatched user_id=%s type=%s status=%s reason=%s",
                user_id,
                trigger["nudge_type"],
                result.get("status"),
                result.get("blocked_reason") or "-",
            )

    await _refresh_dashboard_caches()


async def run_weekly_reports() -> None:
    """Weekly report generation for all profiled users.

    Generates a last_week summary for each user and delivers it via Telegram (if enabled).
    Intended to be triggered by Cloud Scheduler every Monday 09:00.
    """
    user_ids = await container.user_repo.list_active_user_ids()
    if not user_ids:
        logger.info("No user profiles configured — skipping weekly reports")
        return

    orchestrator = container.orchestrator
    for user_id in user_ids:
        profile = await get_profile(user_id)
        try:
            result = await orchestrator.route("report", {
                "user_id": user_id,
                "period": "last_week",
                "user_timezone": profile.timezone,
            })
            report_text = result.get("response_text", "")
            if report_text and result.get("status") != "error":
                if container.telegram and profile.chat_id:
                    await container.telegram.send_message(profile.chat_id, report_text)
                else:
                    logger.info("Weekly report generated but Telegram delivery skipped (disabled or no chat_id)")
            
            logger.info(
                "Weekly report user=%s status=%s", user_id, result.get("status")
            )
        except Exception:
            logger.exception("Weekly report failed for user_id=%s", user_id)


async def run_budget_checks() -> None:
    """Hourly maintenance: clear expired temp overrides from all active budgets.

    Budget threshold nudges (≥70%, ≥100%) are triggered via _collect_triggers
    inside run_behavioral_analysis. This job handles only DB housekeeping.
    """
    budget_repo = container.budget_repo
    if not budget_repo:
        logger.warning("budget_repo not available — skipping budget checks")
        return

    user_ids = await container.user_repo.list_active_user_ids()
    now_utc = datetime.now(UTC).replace(tzinfo=None)
    cleared = 0

    for user_id in user_ids:
        try:
            budgets = await budget_repo.find_by_user(user_id)
            for budget in budgets:
                temp_expires = budget.temp_limit_expires_at
                if budget.temp_limit is None or not temp_expires:
                    continue
                exp = temp_expires.replace(tzinfo=None) if temp_expires.tzinfo else temp_expires
                if now_utc > exp:
                    await budget_repo.clear_temp_override(str(budget.id), user_id)
                    cleared += 1
                    logger.info(
                        "Cleared expired temp override: budget=%s user=%s category=%s",
                        budget.id,
                        user_id,
                        budget.category_id,
                    )
        except Exception:
            logger.exception("Budget check failed for user_id=%s", user_id)

    logger.info("Budget checks done — %d expired temp overrides cleared", cleared)


_JOBS = {
    "behavioral": run_behavioral_analysis,
    "reports": run_weekly_reports,
    "budget": run_budget_checks,
}


async def main(job: str = "all") -> None:
    """One-shot entry point for Cloud Run Jobs (triggered by Cloud Scheduler).

    Pass --job <name> to run a single job:
        behavioral  — daily nudge fan-out (08:00 ICT)
        reports     — weekly summary per user (Mon 09:00 ICT)
        budget      — hourly temp-override cleanup

    Omit --job (or pass 'all') to run every job sequentially — useful for
    local / docker-compose development where a single container handles all work.
    """
    logger.info("ChiWi worker started (job=%s)", job)
    await container.startup()

    targets = list(_JOBS.items()) if job == "all" else [(job, _JOBS[job])]
    failed = False
    for name, fn in targets:
        try:
            await fn()
        except Exception:
            logger.exception("Job '%s' failed", name)
            failed = True

    await container.shutdown()
    if failed:
        raise RuntimeError("One or more worker jobs failed — see logs above")
    logger.info("ChiWi worker finished (job=%s)", job)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ChiWi scheduled worker")
    parser.add_argument(
        "--job",
        choices=[*_JOBS.keys(), "all"],
        default="all",
        help="Which job to run (default: all)",
    )
    args = parser.parse_args()
    asyncio.run(main(job=args.job))
