# CLAUDE.md — ChiWi Project Context

## Project Vision & Persona
- **Goal**: Zero-effort, proactive personal finance via Multi-Agent Swarm.
- **Tone**: UI/User interactions in Vietnamese; Code/Comments in English.
- **Core Strategy**: "Think-First" — Identify the correct agent before execution.

## Tech Stack & Architecture
- **Backend**: Python (FastAPI, Asynchronous).
- **Agents**: LangGraph/CrewAI for orchestration.
- **LLM**: Gemini 2.5 Flash (Parsing) & 2.5 Pro (Logic).
- **Storage**: MongoDB (Data), Redis (State/Session).
- **Infra**: Docker-centric, self-hosted.

## Coding Standards
- **Async**: Use `async/await` for all I/O, database, and LLM calls.
- **Typing**: Strict type hinting using Pydantic models for all data schemas.
- **Security**: Mask PII (account numbers, sensitive IDs) before any LLM API call.
- **Structure**:
  - `src/agents/`: Individual agent logic (Parsing, Tagging, etc.).
  - `src/api/`: FastAPI endpoints.
  - `src/core/`: Orchestrator and shared utilities.
- **Validation**: Every transaction must have `chat_id` and `timestamp` validation.

## Development Workflow Commands
- **Run**: `uvicorn src.main:app --reload`
- **Docker**: `docker-compose up --build`
- **Lint**: `black . && isort .`
- **Makefile**: for local start and build

## Token Optimization Rules
- **Conciseness**: Provide only the modified code snippets unless a full file is requested.
- **Narrow Focus**: Analyze one agent logic at a time to keep context small.
- **Ignore**: Do not read `/logs`, `/data`, or `.env` files.
- **State**: Assume Redis handles conversation memory; don't re-summarize history unless asked.