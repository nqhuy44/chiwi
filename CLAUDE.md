# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

ChiWi — zero-effort, proactive personal finance via a multi-agent swarm. All user-facing copy is **Vietnamese**; code, comments, and logs are **English**.

Deeper design docs live in `docs/` (`ARCHITECTURE.md`, `AGENTS.md`, `DATABASE.md`, `FLOWS.md`, per-feature `FEATURE_*.md`). Prefer reading those for domain/flow questions before inferring from code.

## Common commands

Dev loop (all via `Makefile`, which uses the project's `.venv`):

- `make setup` — create `.venv`, install deps, copy `.env.example` → `.env`
- `make run` — `uvicorn src.main:app --reload`
- `make ngrok` — start ngrok tunnel on port 8000
- `make webhook-set` — auto-detect ngrok URL and register with Telegram
- `make webhook-delete` — remove Telegram webhook
- `make lint` — `black . && isort .`
- `make test` — unit tests (excludes `integration` marker)
- `make test-integration` — tests that hit real Gemini/etc.; requires a real `.env`
- `make test-all` — everything
- `make test-cov` / `make test-report` — coverage + HTML report in `reports/`
- `make docker-up` / `make docker-down` / `make docker-logs` — full stack (api + mongo + redis + worker) via `docker-compose.yaml`

Single test: `.venv/bin/pytest tests/test_ingestion_agent.py::TestName::test_case -v`.

Integration tests are gated by the `integration` pytest marker (see `pytest.ini`). `asyncio_mode = auto`, so `async def test_*` works without decorators.

## Architecture

FastAPI app (`src/main.py`) + a separate cron worker process (`src/worker.py`, started as its own docker service). Both share the code in `src/`.

**Lifecycle / DI.** `src/core/dependencies.py` defines a singleton `AppContainer` constructed during FastAPI `lifespan` startup. It owns the Mongo client, `RedisClient`, `GeminiService`, `TelegramService`, all repositories (`transaction_repo`, `user_repo`, `budget_repo`, `goal_repo`, `correction_repo`, `nudge_repo`, `subscription_repo`), and the `Orchestrator`. Routes reach services via `container.orchestrator` / `container.<service>` — do **not** instantiate these directly inside route handlers or agents; accept them via constructor injection instead (see how `Orchestrator` takes `gemini`, `redis`, `transaction_repo`, `budget_repo`, `goal_repo`, `correction_repo`, `nudge_repo`, `subscription_repo`).

**Think-First orchestrator** (`src/core/orchestrator.py`). Every inbound event is first classified by `classify_event()` into one of `notification | chat | voice | scheduled | report | analysis | correction`, then dispatched by `route()` to a per-event pipeline. New event sources must extend both the classifier and the `match` in `route()`. The six agents (`src/agents/{ingestion,tagging,conversational,behavioral,reporting,analytics}.py`) are composed by the orchestrator — agents should not call each other directly.

> **Android app integration:** The Android app (separate repository, in development) is a **sensor only** — it captures raw bank notification text via `NotificationListenerService` and POSTs it verbatim to `POST /api/webhook/notification` with an `X-User-Id` header. All AI parsing (amount, merchant, direction, timestamp) is done server-side by the **Ingestion Agent** using Gemini Flash. This means parsing improvements and new bank format support only require a backend deploy, never a mobile release. The Android app also handles: local offline queue (retry when backend unreachable), auth header injection. Visual dashboard features (charts, drill-downs) will be built into the Android app in a future phase.

**Event pipelines.**
- `notification` → Ingestion Agent (Gemini Flash: parse raw bank text) → Tagging → store. Source is `"android"`.
- `chat` / `voice` → Conversational (Gemini Pro) → branch on intent:
  - `log_transaction` → Tagging → store
  - `request_report` → re-enters the `report` pipeline
  - `request_analysis` → re-enters the `analysis` pipeline
  - `ask_balance` → `_handle_ask_balance` sums inflow/outflow for a period
  - `ask_category` → `_handle_ask_category` lists top-level categories
  - `set_budget` → `_handle_set_budget` inserts a `BudgetDocument` for the cycle
  - `set_goal` → `_handle_set_goal` inserts a `GoalDocument`
  - `set_subscription` → `_handle_set_subscription` inserts a `SubscriptionDocument` (sets `anchor_day` from the parsed charge date)
  - `list_subscriptions` → `_handle_list_subscriptions` returns active subscriptions
  - `query_subscription` → `_handle_query_subscription` returns single-subscription payment status (last charged, next charge, paid-this-period flag computed in VN timezone)
  - `mark_subscription_paid` → `_handle_mark_subscription_paid` advances next_charge_date
  - `cancel_subscription` → `_handle_cancel_subscription` soft-deletes the subscription
  - `update_subscription` → `_handle_update_subscription` deactivates old record, inserts new one with `replaces_id`
  - `general_chat` → LLM-authored response_text
- `report` → Reporting (Gemini Flash) → narrative summary via Telegram. Handles empty data gracefully.
- `analysis` → Analytics (Gemini Pro) → period comparison / trend analysis via Telegram. Handles empty data gracefully.
- `scheduled` → Behavioral Agent → Telegram nudge. Trigger detection runs in `worker.py:_collect_triggers` (subscription reminders, budget warnings, spending spikes, impulse detection, saving streak, goal milestones). Anti-spam: quiet hours, daily limit, 24 h dedup by nudge type. Manual `/nudge` commands bypass spam check.
- `correction` → `_handle_correction` updates `category_id` (sets `user_corrected=True`), invalidates the Redis merchant cache, and records a `CorrectionDocument` so future tagging re-evaluates with the override. *(Implemented; Telegram inline-button UX to emit these events is still TODO.)*

**Tagging Agent memory model** (`src/agents/tagging.py`). Three layers, tried in order:
1. Redis merchant cache — hot lookup, 7-day TTL.
2. MongoDB historical memory — `TransactionRepository.find_by_merchant` returns the 5 most recent transactions for `(user_id, merchant)`. `_majority_category` short-circuits the LLM *only when in-pattern*: current direction must match history's dominant direction, current amount within `median / 3 … median × 3`. **User-corrected entries** (`user_corrected=True`) outweigh auto-tags — if any exist in history, only corrected entries vote, and a single correction is enough to win.
3. Gemini Flash with the full history rendered as "Previous classifications for this merchant", including `(user-corrected)` annotations.

**LLM tiering.** Use `google-genai` (v1.x) with `GeminiService.call_flash()` for parsing/classification (cheap, temp 0.1) and `call_pro()` for reasoning/behavioral (temp 0.3). Both enforce `response_mime_type="application/json"` and retry 429s with exponential backoff — callers get `{}` on failure, never an exception.

**PII masking is mandatory.** Before any LLM call that touches user content, run `mask_pii()` from `src/api/middleware/pii_mask.py`, gated by `settings.pii_mask_enabled`. Apply at the top of every agent `process_*` / `analyze` method that receives user-supplied text.

**Persistence.** MongoDB via `motor` (async) for durable data — document models in `src/db/models/` (`transaction`, `user`, `category`, `budget`, `goal`, `nudge`, `report`, `correction`), accessed only through repositories in `src/db/repositories/` (`transaction_repo`, `user_repo`, `budget_repo`, `goal_repo`, `correction_repo`). Redis (`src/services/redis_client.py`) is for session state and hot caches (e.g. merchant → category in `TaggingAgent.enrich`); corrections invalidate the merchant cache via `delete_merchant_cache`.

**Schemas.** All cross-boundary data (agent I/O, webhook payloads, API responses) goes through Pydantic models in `src/core/schemas.py`. Add new contracts there, not inline.

**Auth.** Access is gated on `UserDocument.is_active`. Telegram webhook resolves the sender's `chat_id` to a `UserDocument` via `user_repo.find_by_chat_id()` and rejects inactive accounts. The Android notification endpoint (`POST /api/webhook/notification`) resolves `X-User-Id` via `user_repo.find_by_id()` with the same active check. Mobile REST endpoints (`/api/mobile/*`) use JWT (`Authorization: Bearer <token>`); the `get_current_user` dependency verifies the token, looks up the user, and rejects inactive accounts. To disable a user, set `UserDocument.is_active = False` — no config change or redeploy needed.

## Conventions

- All I/O (DB, Redis, HTTP, Gemini) is `async`/`await`. Don't introduce blocking calls into request paths or agents.
- Put configurable values in `.env` / `src/core/config.py:Settings`; don't hardcode.
- Don't generate test case except when the user requires.
- Tests live under `tests/unit/` (mocked, hermetic) and `tests/integration/` (real external APIs). Mark integration tests with `@pytest.mark.integration` so `make test` stays hermetic.
- Spending categories are configured in `config/categories.json` (override with `CATEGORIES_FILE`). They feed both the `TaggingAgent` prompt (`{{CATEGORIES}}` placeholder) and the DB seed — add new categories there, not in Python.
- Every transaction path must carry `chat_id` / `user_id` and a `timestamp` — validate at the edge.
- **Timezone**: storage is always UTC; day-boundary math uses `settings.business_timezone` (default `Asia/Ho_Chi_Minh`). `src/core/utils.py` helpers (`get_date_range`, `get_budget_window`, `get_comparison_ranges`) already handle the conversion — callers pass period labels ("today", "this_week", etc.) and get UTC instants back, so don't reinvent day math outside these helpers. The Conversational prompt receives `{{CURRENT_TIMESTAMP}}` in local time with offset so Gemini resolves "hôm qua"/"sáng nay" against Vietnamese time; `datetime.fromisoformat` preserves the offset when the payload lands back in the orchestrator.
- **Period Validation**: `get_date_range` in `src/core/utils.py` returns `(None, None)` for unsupported periods. The `Orchestrator` catches this and returns a friendly error message to the user. For budgets, use `get_budget_window(budget_period)` — it returns the *full* cycle (Mon-Sun for `"weekly"`, 1st-last for `"monthly"`), whereas `get_date_range("this_week"/"this_month")` ends at `now`.
- **Empty Data**: Agents are instructed via system prompts (`reporting.md`, `analytics.md`) to handle cases with 0 transactions by providing encouraging, persona-consistent feedback rather than failing or showing empty tables.
- **Conversational response_text**: For intents that return computed data (`ask_balance`, `set_budget`, `set_goal`, `request_report`, `request_analysis`), the prompt tells Gemini to leave `response_text` empty — the orchestrator handler writes the authoritative reply so numbers/IDs can't be hallucinated. Only `log_transaction` and `general_chat` use the LLM's `response_text` directly.
- **Correction learning loop**: `_handle_correction` both updates the transaction and invalidates Redis. The next tagging pass for that merchant sees the corrected entry (`user_corrected=True`) in Mongo history, and `TaggingAgent._majority_category` weights corrected entries above auto-tags. Don't bypass this path — always go through the `correction` event so the Redis invalidation + audit record stay consistent.

## Testing Debt

The following areas need unit test coverage (tracked for future implementation):

- `tests/unit/test_ingestion_agent.py` — mock Gemini Flash, verify `ParsedTransaction` fields for VCB/TCB/MoMo formats; `is_transaction=False` for non-financial text; `bank_hint` is forwarded.
- `tests/unit/test_orchestrator.py` — `Orchestrator.__init__` now takes `budget_repo`, `goal_repo`, `correction_repo`, `nudge_repo`, `subscription_repo`. Verify all intents (including subscription ones) route to the right handlers. Verify `notification` event routes to Ingestion → Tagging → store.
- `tests/unit/test_analytics_agent.py` — mock Gemini response, verify structured output for compare/trend.
- `tests/unit/test_tagging_agent.py` — outlier-aware majority (direction mismatch + amount outlier bail out), user-corrected entries short-circuit with a single vote.
- `tests/unit/test_utils.py` — verify `get_comparison_ranges()` and `get_budget_window()` return correct date pairs.
- `tests/unit/test_webhook.py` — verify guard clauses (stale message filter, dedup, rate limiting) and command routing (`/nudge`, `/start`, `/help`). Verify `/api/webhook/notification` rejects unknown `X-User-Id`.
- `tests/unit/test_reporting_agent.py` — verify HTML-formatted report generation.
- `tests/unit/test_subscription_repo.py` — verify `_advance_date` anchors end-of-month correctly across months (Jan 31 → Feb 28 → Mar 31), leap-year Feb 29, and short months (Apr 30 → May 31); verify `anchor_day=None` fallback uses `current.day`.
- `tests/unit/test_worker.py` — mock repos, verify `_collect_triggers` returns correct trigger types for budget warnings, spending spikes, and impulse detection; verify empty repos return empty trigger list.
