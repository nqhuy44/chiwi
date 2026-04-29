# ChiWi — Tech Stack

## Core Stack

| Component | Technology | Version | Justification |
|---|---|---|---|
| **Language** | Python | 3.12+ | Rich AI/ML ecosystem, native async support, Pydantic integration |
| **Web Framework** | FastAPI | 0.115+ | High performance async API, automatic OpenAPI docs, Pydantic-native validation |
| **Agent Orchestration** | Plain async dispatch | — | Think-First pattern via `Orchestrator.route()` — no LangGraph dependency needed |
| **LLM Provider** | Google Gemini | 2.5 Flash / 2.5 Pro | Massive context window, native JSON mode, strong Vietnamese language support, cost-effective |
| **Database** | MongoDB + Beanie | 8.x / 1.28+ | ODM for type-safe document modeling and Pydantic-based validation |
| **Cache / State** | Redis | 8.x | Sub-millisecond latency for session management, merchant cache, rate limiting, dashboard cache |
| **Interface** | Telegram Bot API | Latest | Zero UI development effort, cross-platform, built-in notification system |
| **Dashboard** | Android App (separate repo) | — | Native mobile dashboard consuming `/api/mobile/*` REST endpoints |
| **Cron Scheduling** | supercronic | 0.2.33 | Container-native cron daemon — runs in foreground, handles signals, supports `CRON_TZ` |
| **Containerization** | Docker + Compose | 27+ / 2.x | Reproducible builds, single-command deployment, self-hosted on VM |
| **CI/CD** | GitHub Actions | — | Build → push Docker Hub → SSH deploy to VM on every push to `main` |

## AI / LLM Strategy

| Use Case | Model | Rationale |
|---|---|---|
| **Transaction Parsing** | Gemini 2.5 Flash | Low latency (~200ms), cheap ($0.075/1M input tokens), handles structured extraction |
| **Behavioral Analysis** | Gemini 2.5 Pro | Deeper reasoning for pattern recognition and financial advice |
| **Voice Transcription** | Gemini 2.5 Flash | Multi-modal capability for speech-to-text |
| **Report Generation** | Gemini 2.5 Pro | Complex financial narrative and long-form content generation |

### Cost Analysis (Personal Use)

With ~50 transactions/day:

| Tier | Monthly Cost | Note |
|---|---|---|
| **Free Tier** (Flash) | $0 | 15 RPM, 1M TPM — sufficient for personal use |
| **Pay-as-you-go** (Flash) | < $1 | If exceeding free tier |
| **Pay-as-you-go** (Pro) | ~$2-5 | For behavioral analysis + reporting |

## Python Dependencies

### Core

| Package | Purpose |
|---|---|
| `fastapi` | Web framework & API endpoints |
| `uvicorn` | ASGI server |
| `pydantic` | Data validation & schema definitions (v2.x) |
| `beanie` | Async ODM for MongoDB (Pydantic-based) |
| `google-genai` | Gemini LLM integration (v1.x SDK) |
| `redis[hiredis]` | Async Redis client with C-extension performance |
| `python-telegram-bot` | Telegram Bot API wrapper |
| `httpx` | Async HTTP client for webhook/external calls |
| `pyjwt` | JWT token management for mobile auth |
| `passlib[bcrypt]` | Secure password hashing |

### Development

| Package | Purpose |
|---|---|
| `black` | Code formatter |
| `isort` | Import sorter |
| `pytest` | Testing framework |
| `pytest-asyncio` | Async test support |
| `mongomock_motor` | Mock MongoDB driver for Beanie unit tests |
| `mypy` | Static type checking |

## Infrastructure

### Docker Services

```yaml
# docker-compose.yaml
services:
  api:                  # FastAPI + Uvicorn (port 8000)
  worker-behavioral:    # supercronic — behavioral nudges, daily 08:00 ICT
  worker-budget:        # supercronic — budget temp-override cleanup, hourly
  worker-reports:       # supercronic — weekly summary report, Monday 09:00 ICT
```

All four share the same Docker image (`docker.io/nqh44/chiwi:<sha>`). Workers are differentiated only by their `command: supercronic /app/cron/worker-<name>.cron` override. MongoDB and Redis run as separate containers on the same host.

### Deployment Pipeline

1. Push to `main` → GitHub Actions `build-push` job builds and pushes image to Docker Hub tagged `:<sha7>` + `:latest`.
2. `deploy` job SSHes into the VM, pins `docker-compose.yaml` to the exact SHA image, runs `docker compose up -d`, and prunes old images.
3. Verifies all 4 containers reach `running` state within 60 s.
4. Smoke-tests `https://<VM_DOMAIN>/health` from the GitHub runner.

### Environment Variables

All configuration via `.env` file. See `.env.example` for template.

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio API key |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token |
| `TELEGRAM_ALLOWED_USER_IDS` | Comma-separated list of authorized Telegram user IDs |
| `MONGODB_URI` | MongoDB connection string |
| `REDIS_URL` | Redis connection string |
| `LOG_LEVEL` | Application log level (DEBUG, INFO, WARN, ERROR) |
| `PII_MASK_ENABLED` | Enable/disable PII masking (default: true) |

## Build & Run Commands

```bash
# Local Development
make setup          # Install dependencies, create .env from template
make run            # uvicorn src.main:app --reload
make lint           # black . && isort .
make test           # pytest tests/

# Docker
make docker-build   # docker-compose build
make docker-up      # docker-compose up -d
make docker-down    # docker-compose down
make docker-logs    # docker-compose logs -f
```
