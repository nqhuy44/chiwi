# ANTIGRAVITY.md

This file provides guidance to the Antigravity AI Agent when working with code in this repository.

## Project Overview

ChiWi — zero-effort, proactive personal finance via a multi-agent swarm.
- **Communication**: All user-facing chat and explanation must be in **Vietnamese**.
- **Documentation/Code**: All artifacts, plans, code, comments, logs, and markdown files must be in **English**.
- **Tone**: Short, professional, and straight to the point.

Deeper design docs live in `docs/` (`ARCHITECTURE.md`, `AGENTS.md`, `DATABASE.md`, `FLOWS.md`, per-feature `FEATURE_*.md`). Prefer reading those for domain/flow questions before inferring from code.

## Common Commands

Dev loop (all via `Makefile`, which uses the project's `.venv`):

- `make setup` — create `.venv`, install deps, copy `.env.example` -> `.env`
- `make run` — `uvicorn src.main:app --reload`
- `make ngrok` — start ngrok tunnel on port 8000
- `make webhook-set` — auto-detect ngrok URL and register with Telegram
- `make webhook-delete` — remove Telegram webhook
- `make lint` — `black . && isort .`
- `make test` — unit tests (excludes `integration` marker)
- `make test-integration` — tests that hit real Gemini/etc.; requires a real `.env`
- `make test-all` — everything
- `make test-cov` / `make test-report` — coverage + HTML report in `reports/`
- `make docker-up` / `make docker-down` / `make docker-logs` — full stack via `docker-compose.yaml`

Single test example: `.venv/bin/pytest tests/unit/test_tagging_agent.py -v`.

Integration tests are gated by the `integration` pytest marker (see `pytest.ini`). `asyncio_mode = auto`, so `async def test_*` works without decorators.

## Architecture

FastAPI app (`src/main.py`) + a separate cron worker process (`src/worker.py`, started as its own docker service). Both share the code in `src/`.

**Lifecycle / DI**: `src/core/dependencies.py` defines a singleton `AppContainer` constructed during FastAPI `lifespan` startup. It owns the Mongo client, `RedisClient`, `GeminiService`, `TelegramService`, all repositories, and the `Orchestrator`. Do **not** instantiate these directly inside route handlers or agents; accept them via constructor injection.

**Think-First Orchestrator** (`src/core/orchestrator.py`): Every inbound event is classified by `classify_event()` then dispatched by `route()`. The six agents are composed by the orchestrator — agents should not call each other directly.

**Event pipelines**:
- `notification` -> Ingestion -> Tagging -> TransactionRepository.insert.
- `chat` / `voice` -> Conversational -> Tagging -> store. (Implemented)
- `report` -> Reporting (Gemini Flash) -> narrative summary via Telegram. (Implemented; handles empty data gracefully)
- `analysis` -> Analytics (Gemini Pro) -> period comparison / trend analysis via Telegram. (Implemented; handles empty data gracefully)
- `scheduled` -> Behavioral -> Telegram nudge. (Phase 3)
- `correction` -> direct DB update + learning. (Phase 3)

**LLM Tiering**: Use `GeminiService.call_flash()` for parsing/classification and `call_pro()` for reasoning/behavioral. Both enforce JSON response and handle retries/failures gracefully (return `{}` instead of throwing exceptions).

**PII Masking**: Before any LLM call that touches user content, run `mask_pii()` from `src/api/middleware/pii_mask.py`.

**Persistence**: MongoDB (via `motor`) for durable data. Redis (`src/services/redis_client.py`) is for session state and hot caches.

**Schemas**: All cross-boundary data goes through Pydantic models in `src/core/schemas.py`.

## Conventions

- All I/O (DB, Redis, HTTP, Gemini) is `async`/`await`.
- Clean Code & SOLID principles. No hardcoded credentials.
- Tests live under `tests/unit/` (mocked, hermetic) and `tests/integration/` (real external APIs).
- Spending categories are configured in `config/categories.json`. They feed both the TaggingAgent prompt and the DB seed.
- **Period Validation**: `get_date_range` in `src/core/utils.py` returns `(None, None)` for unsupported periods. The `Orchestrator` catches this and returns a friendly error message to the user.
- **Empty Data**: Agents are instructed via system prompts (`reporting.md`, `analytics.md`) to handle cases with 0 transactions by providing encouraging, persona-consistent feedback rather than failing or showing empty tables.

## Testing Debt

The following areas need unit test coverage (tracked for future implementation):

- `tests/unit/test_analytics_agent.py` — mock Gemini response, verify structured output for compare/trend
- `tests/unit/test_orchestrator.py` — verify `request_analysis` intent routes to AnalyticsAgent
- `tests/unit/test_utils.py` — verify `get_comparison_ranges()` returns correct date pairs
- `tests/unit/test_webhook.py` — verify guard clauses (stale message filter, dedup, rate limiting)
- `tests/unit/test_reporting_agent.py` — verify HTML-formatted report generation
