# ChiWi — System Architecture

## Overview

ChiWi is a **zero-effort, proactive personal finance management system** powered by a Multi-Agent AI Swarm. It automatically captures financial transactions from bank notifications, classifies them using AI, and proactively nudges the user toward healthier spending habits.

The system follows a **"Think-First"** strategy: an orchestrator identifies the correct specialized agent before any execution occurs.

## Design Principles

| Principle | Description |
|---|---|
| **Zero-Effort** | Financial tracking should never feel like a second job. Use ambient data (notifications) and natural language (chat). |
| **Proactive** | The system observes patterns and nudges the user — it doesn't wait for a query. |
| **Privacy-First** | All PII is masked before reaching any LLM. Self-hosted on user's infrastructure. |
| **Agent Specialization** | Each AI agent has a single responsibility with its own system prompt, toolset, and evaluation criteria. |
| **Async-Native** | All I/O, database, and LLM calls are fully asynchronous. |

## High-Level Architecture

```mermaid
graph TD
    subgraph Input Layer
        A1["📱 Android Notification<br/>(MacroDroid/Tasker)"]
        A2["📱 iOS Shortcut<br/>(SMS Automation)"]
        A3["💬 Telegram Chat<br/>(Direct Message)"]
        A4["🎤 Voice Message<br/>(Speech-to-Text)"]
    end

    subgraph API Gateway
        B["🚀 FastAPI Gateway<br/>(Auth + PII Masking)"]
    end

    subgraph Orchestration Layer
        C{"🧠 Agent Orchestrator<br/>(LangGraph)"}
    end

    subgraph Agent Swarm
        D["🔍 Ingestion Agent<br/>(The Collector)"]
        E["💬 Conversational Agent<br/>(The Interface)"]
        F["🏷️ Context & Tagging Agent<br/>(The Classifier)"]
        G["🧠 Behavioral Agent<br/>(The Psychologist)"]
        H["📊 Reporting Agent<br/>(The Strategist)"]
    end

    subgraph Data Layer
        I[("🗄️ MongoDB<br/>(Transactions + Metadata)")]
        J[("⚡ Redis<br/>(Session + State)")]
    end

    subgraph Output Layer
        K["📲 Telegram Bot<br/>(Notifications + Inline Buttons)"]
        L["📈 Telegram Mini App<br/>(Dashboard Charts)"]
    end

    A1 & A2 --> B
    A3 & A4 --> B
    B --> C
    C --> D & E
    D & E --> F
    F --> I
    I --> G
    G --> K
    I --> H
    H --> L
    C <--> J
```

## Component Responsibilities

### 1. Input Layer
Captures financial events from multiple sources (bank notifications, direct chat, voice) and forwards them as structured HTTP requests to the API Gateway.

### 2. API Gateway (FastAPI)
- **Authentication**: Validates Telegram `user_id` / `chat_id` against an allow-list.
- **PII Masking**: Strips account numbers, phone numbers, and sensitive identifiers before forwarding to any LLM agent.
- **Rate Limiting**: Protects against abuse and controls API cost.
- **Routing**: Dispatches incoming events to the Agent Orchestrator.

### 3. Agent Orchestrator (LangGraph)
The central brain that implements a **"Think-First"** routing pattern:
1. Classifies the incoming event type (notification, chat message, voice, scheduled trigger).
2. Selects the appropriate agent pipeline.
3. Manages multi-agent collaboration and data handoff.
4. Handles conversation state via Redis.

### 4. Agent Swarm
Five specialized agents, each with a distinct system prompt and toolset. See [AGENTS.md](./AGENTS.md) for full documentation.

### 5. Data Layer
- **MongoDB**: Primary persistent storage for transactions, user profiles, category mappings, and agent-generated metadata.
- **Redis**: Ephemeral state management — conversation history, session context, agent intermediate results, and rate-limit counters.

### 6. Output Layer
- **Telegram Bot**: Primary user interface for confirmations, nudges, and quick interactions via inline buttons.
- **Telegram Mini App**: Rich visual dashboard with charts and reports for deeper financial insights.

## Deployment Architecture

```mermaid
graph LR
    subgraph Docker Host ["🐳 Docker Compose (Self-Hosted)"]
        APP["chiwi-api<br/>FastAPI + Uvicorn"]
        MONGO["chiwi-mongo<br/>MongoDB 7.x"]
        REDIS["chiwi-redis<br/>Redis 7.x"]
        WORKER["chiwi-worker<br/>Scheduled Jobs"]
    end

    TG["Telegram Bot API"] <--> APP
    APP <--> MONGO
    APP <--> REDIS
    WORKER <--> MONGO
    WORKER <--> REDIS
    GEMINI["Google Gemini API"] <--> APP
```

All services are containerized and orchestrated via `docker-compose.yaml`. The system is designed to run entirely on a single self-hosted machine (e.g., home server, VPS).

## Directory Structure

```
chiwi/
├── src/
│   ├── agents/           # Individual agent logic
│   │   ├── ingestion.py
│   │   ├── conversational.py
│   │   ├── tagging.py
│   │   ├── behavioral.py
│   │   └── reporting.py
│   ├── api/              # FastAPI endpoints
│   │   ├── routes/
│   │   │   ├── webhook.py
│   │   │   ├── chat.py
│   │   │   └── health.py
│   │   └── middleware/
│   │       ├── auth.py
│   │       └── pii_mask.py
│   ├── core/             # Orchestrator and shared utilities
│   │   ├── orchestrator.py
│   │   ├── config.py
│   │   └── schemas.py
│   ├── db/               # Database models and repositories
│   │   ├── models/
│   │   └── repositories/
│   ├── services/         # External service integrations
│   │   ├── telegram.py
│   │   ├── gemini.py
│   │   └── redis_client.py
│   └── main.py           # Application entrypoint
├── scripts/
│   └── setup.sh
├── tests/
├── docs/
├── docker-compose.yaml
├── Dockerfile
├── Makefile
├── .env.example
├── requirements.txt
└── CLAUDE.md
```

## Security Model

| Layer | Mechanism |
|---|---|
| **Transport** | HTTPS for all external communication (Telegram webhook, Gemini API) |
| **Authentication** | Telegram `user_id` allow-list at Gateway level |
| **PII Protection** | Account numbers and phone numbers stripped before LLM calls |
| **Data at Rest** | MongoDB encryption enabled |
| **Secrets** | All credentials via environment variables (`.env`), never hardcoded |
| **AI Privacy** | Gemini API configured to not use data for model training |
