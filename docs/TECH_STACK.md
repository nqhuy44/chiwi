# ChiWi — Tech Stack

## Core Stack

| Component | Technology | Version | Justification |
|---|---|---|---|
| **Language** | Python | 3.12+ | Rich AI/ML ecosystem, native async support, Pydantic integration |
| **Web Framework** | FastAPI | 0.115+ | High performance async API, automatic OpenAPI docs, Pydantic-native validation |
| **Agent Orchestration** | LangGraph | 0.4+ | Stateful multi-agent workflows with conditional routing, built-in checkpointing |
| **LLM Provider** | Google Gemini | 2.5 Flash / 2.5 Pro | Massive context window, native JSON mode, strong Vietnamese language support, cost-effective |
| **Database** | MongoDB | 8.x | Schema-less design for unpredictable AI metadata, high write throughput |
| **Cache / State** | Redis | 8.x | Sub-millisecond latency for session management, conversation memory, rate limiting |
| **Interface** | Telegram Bot API | Latest | Zero UI development effort, cross-platform, built-in notification system |
| **Dashboard** | Telegram Mini App | - | Rich visual charts within Telegram, no separate app deployment |
| **Containerization** | Docker + Compose | 27+ / 2.x | Reproducible builds, single-command deployment, self-hosted friendly |

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
| `pydantic` | Data validation & schema definitions |
| `langgraph` | Multi-agent orchestration |
| `langchain-google-genai` | Gemini LLM integration |
| `motor` | Async MongoDB driver |
| `redis[hiredis]` | Async Redis client with C-extension performance |
| `python-telegram-bot` | Telegram Bot API wrapper |
| `httpx` | Async HTTP client for webhook/external calls |

### Development

| Package | Purpose |
|---|---|
| `black` | Code formatter |
| `isort` | Import sorter |
| `pytest` | Testing framework |
| `pytest-asyncio` | Async test support |
| `mypy` | Static type checking |

## Infrastructure

### Docker Services

```yaml
# docker-compose.yaml (conceptual)
services:
  chiwi-api:       # FastAPI app (port 8000)
  chiwi-mongo:     # MongoDB (port 27017)
  chiwi-redis:     # Redis (port 6379)
  chiwi-worker:    # Scheduled tasks (cron-based)
```

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
