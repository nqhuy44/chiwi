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

**Lifecycle / DI.** `src/core/dependencies.py` defines a singleton `AppContainer` constructed during FastAPI `lifespan` startup. It owns the Mongo client, `RedisClient`, `GeminiService`, `TelegramService`, all repositories, and the `Orchestrator`. Routes reach services via `container.orchestrator` / `container.<service>` — do **not** instantiate these directly inside route handlers or agents; accept them via constructor injection instead (see how `Orchestrator` takes `gemini`, `redis`, `transaction_repo`).

**Think-First orchestrator** (`src/core/orchestrator.py`). Every inbound event is first classified by `classify_event()` into one of `notification | chat | voice | scheduled | report | analysis | correction`, then dispatched by `route()` to a per-event pipeline. New event sources must extend both the classifier and the `match` in `route()`. The six agents (`src/agents/{ingestion,tagging,conversational,behavioral,reporting,analytics}.py`) are composed by the orchestrator — agents should not call each other directly.

**Event pipelines.**
- `notification` → Ingestion (Gemini Flash, parse) → skip if `is_transaction=False` → Tagging (Redis merchant cache → Gemini Flash fallback) → `TransactionRepository.insert`.
- `chat` / `voice` → Conversational → Tagging → store. (Implemented)
- `report` → Reporting (Gemini Flash) → narrative summary via Telegram. (Implemented; handles empty data gracefully)
- `analysis` → Analytics (Gemini Pro) → period comparison / trend analysis via Telegram. (Implemented; handles empty data gracefully)
- `scheduled` → Behavioral → Telegram nudge. *(stubbed; Phase 3)*
- `correction` → direct DB update + learning. *(stubbed; Phase 3)*

**LLM tiering.** Use `google-genai` (v1.x) with `GeminiService.call_flash()` for parsing/classification (cheap, temp 0.1) and `call_pro()` for reasoning/behavioral (temp 0.3). Both enforce `response_mime_type="application/json"` and retry 429s with exponential backoff — callers get `{}` on failure, never an exception.

**PII masking is mandatory.** Before any LLM call that touches user content, run `mask_pii()` from `src/api/middleware/pii_mask.py`, gated by `settings.pii_mask_enabled`. See `IngestionAgent.parse` for the pattern.

**Persistence.** MongoDB via `motor` (async) for durable data — document models in `src/db/models/` (`transaction`, `user`, `category`, `budget`, `nudge`, `report`), accessed only through repositories in `src/db/repositories/`. Redis (`src/services/redis_client.py`) is for session state and hot caches (e.g. merchant → category in `TaggingAgent.enrich`).

**Schemas.** All cross-boundary data (agent I/O, webhook payloads, API responses) goes through Pydantic models in `src/core/schemas.py`. Add new contracts there, not inline.

**Auth.** `/api/webhook/notification` requires an `X-User-Id` header that must be in `settings.allowed_user_ids` (derived from `TELEGRAM_ALLOWED_USER_IDS`, comma-separated).

## Conventions

- All I/O (DB, Redis, HTTP, Gemini) is `async`/`await`. Don't introduce blocking calls into request paths or agents.
- Put configurable values in `.env` / `src/core/config.py:Settings`; don't hardcode.
- Tests live under `tests/unit/` (mocked, hermetic) and `tests/integration/` (real external APIs). Mark integration tests with `@pytest.mark.integration` so `make test` stays hermetic.
- Spending categories are configured in `config/categories.json` (override with `CATEGORIES_FILE`). They feed both the `TaggingAgent` prompt (`{{CATEGORIES}}` placeholder) and the DB seed — add new categories there, not in Python.
- Every transaction path must carry `chat_id` / `user_id` and a `timestamp` — validate at the edge.
- **Period Validation**: `get_date_range` in `src/core/utils.py` returns `(None, None)` for unsupported periods. The `Orchestrator` catches this and returns a friendly error message to the user.
- **Empty Data**: Agents are instructed via system prompts (`reporting.md`, `analytics.md`) to handle cases with 0 transactions by providing encouraging, persona-consistent feedback rather than failing or showing empty tables.

## Testing Debt

The following areas need unit test coverage (tracked for future implementation):

- `tests/unit/test_analytics_agent.py` — mock Gemini response, verify structured output for compare/trend
- `tests/unit/test_orchestrator.py` — verify `request_analysis` intent routes to AnalyticsAgent
- `tests/unit/test_utils.py` — verify `get_comparison_ranges()` returns correct date pairs
- `tests/unit/test_webhook.py` — verify guard clauses (stale message filter, dedup, rate limiting)
- `tests/unit/test_reporting_agent.py` — verify HTML-formatted report generation
