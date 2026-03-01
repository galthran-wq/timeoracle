# digitalgulag — High-Level Architecture & Task Breakdown

## Context

digitalgulag is an AI-powered personal time tracker. A Rust daemon running on the user's machine captures activity data (active windows, URLs, app usage) and streams it to a server. On the server, an AI agent analyzes the raw data and produces a human-readable timeline — automatically labeling what you were doing without manual input. External sources (Oura ring, etc.) fill in offline/physical activity gaps. The frontend is a calendar-like view of your AI-generated day.

## Architecture Overview

```
┌─────────────┐     ┌─────────────┐
│  Oura API   │     │ GitHub API  │
└──────┬──────┘     └──────┬──────┘
       │                   │
       │   ┌───────────────┘
       │   │  (called on-demand by agent via skill tools)
       ▼   ▼
┌──────────────────────────────────────────┐
│             FastAPI Server               │
│                                          │
│  ┌────────────┐  ┌────────────────────┐  │
│  │ Ingestion  │  │ Skills Framework   │  │
│  │ API        │  │ (Oura, GitHub)     │  │
│  └─────┬──────┘  └────────┬───────────┘  │
│        │                  │              │
│        ▼                  │              │
│  ┌──────────────┐         │              │
│  │ PostgreSQL   │         │              │
│  │ activity_events        │              │
│  │ user_integrations      │              │
│  │ integration_cache      │              │
│  │ chats                  │              │
│  │ timeline_entries       │              │
│  └──────┬───────┘         │              │
│         │                 │              │
│         ▼                 ▼              │
│  ┌────────────────────────────────────┐  │
│  │  LangGraph AI Agent (ReAct)       │  │
│  │  - Loads skill tools per user     │  │
│  │  - Streams via WebSocket          │  │
│  │  - Redis checkpointing            │  │
│  │  - Cron / manual / chat modes     │  │
│  └──────────┬─────────────────────┘  │  │
│             │                        │  │
│             ▼                        │  │
│  ┌───────────────────┐  ┌─────────┐ │  │
│  │ Timeline API      │  │  Redis  │ │  │
│  │ Chat API          │  │ (state) │ │  │
│  │ WebSocket         │  └─────────┘ │  │
│  └───────────────────┘              │  │
└──────────────┬───────────────────────┘  │
               │                          │
    ┌──────────┴──────────┐               │
    │                     │               │
    ▼                     ▼               │
┌────────┐         ┌───────────┐          │
│ Vue 3  │◄─ws────►│ Rust      │──────────┘
│ Calendar│        │ Daemon    │
│ + Chat │         │ (Linux/   │
│ UI     │         │  macOS)   │
└────────┘         └───────────┘
```

## Data Model (core tables beyond existing `users`)

- **activity_events** — raw stream from daemon: `(user_id, timestamp, event_type, app_name, window_title, url, metadata_json)`
- **user_integrations** — per-user integration credentials: `(user_id, source, credentials_encrypted, scopes, is_enabled, token_expires_at)`
- **integration_cache** — transparent cache of external API responses: `(user_id, source, data_type, date, data_json, expires_at)`
- **chats** — conversation sessions: `(user_id, name, date, trigger, llm_model, skills_used, total_input_tokens, total_output_tokens)`
- **timeline_entries** — AI-generated calendar blocks: `(user_id, date, start_time, end_time, label, category, source_summary, confidence, edited_by_user, chat_id)`

---

## Task 1: Rust Daemon — Activity Capture

### Goal
A lightweight background process that silently captures what the user is doing on their computer and reliably delivers that data to the digitalgulag server.

### Requirements
- Runs on Linux (X11 + Wayland) and macOS
- Captures: active window title, application name, and (where possible) browser URL
- Detects idle periods (no keyboard/mouse input for configurable threshold)
- Authenticates with the server using the user's JWT token
- Buffers events locally when the server is unreachable, flushes when connection resumes
- Minimal CPU/memory footprint — must not noticeably impact the user's machine
- Configurable polling interval (default ~5 seconds)
- Configurable ignore list (skip certain apps from tracking)

### High-Level Implementation Plan
1. **Project setup**: Create a new Rust crate (`daemon/`) with a workspace layout. Dependencies: `tokio` (async runtime), `reqwest` (HTTP client), `serde`/`serde_json` (serialization), `dirs` (config paths), platform-specific crates.
2. **Platform abstraction layer**: Define a trait `ActivitySource` with `fn get_active_window() -> WindowInfo`. Implement separately:
   - **Linux**: Use `xcb` crate for X11, `wayland-client` or D-Bus (`org.freedesktop.portal`) for Wayland.
   - **macOS**: Use `core-graphics` crate (`CGWindowListCopyWindowInfo`) and accessibility APIs.
3. **Idle detection**: Monitor last input time. Linux: read from `/proc/interrupts` or X11 screensaver extension. macOS: `CGEventSourceSecondsSinceLastEventType`.
4. **Event loop**: Tokio-based loop — poll every N seconds, diff against last state, emit `ActivityEvent` structs when the active window changes or periodically.
5. **Local buffer**: SQLite file in `~/.digitalgulag/buffer.db`. Write events there first. A separate flush task sends batches to `POST /api/activity/events` and deletes on success.
6. **Auth**: Read JWT from `~/.digitalgulag/config.toml`. Provide a `digitalgulag-daemon login` CLI command that hits the server's login endpoint and stores the token.
7. **Service installation**: Provide `digitalgulag-daemon install` command that writes a systemd unit file (Linux) or LaunchAgent plist (macOS).
8. **Config**: TOML file at `~/.digitalgulag/config.toml` — server URL, token, poll interval, ignore list.

---

## Task 2: Activity Ingestion API

### Goal
Server-side endpoints that receive raw activity data from daemons, validate it, and store it efficiently for later AI processing.

### Requirements
- Accept batches of activity events from authenticated users
- Validate event schema (required fields, timestamp sanity)
- Store events in PostgreSQL with proper indexing for time-range queries
- Allow users to query their own raw events (for debugging and transparency)
- Handle high write throughput (a user generates ~1 event every 5 seconds)

### High-Level Implementation Plan
1. **Database model**: Create SQLAlchemy model `ActivityEvent` in `server/src/models/postgres/activity_events.py`. Columns: `id (UUID)`, `user_id (FK)`, `timestamp (DateTime, indexed)`, `event_type (String)`, `app_name`, `window_title`, `url (nullable)`, `metadata (JSONB)`. Add composite index on `(user_id, timestamp)`.
2. **Alembic migration**: Generate migration for the `activity_events` table.
3. **Repository**: `ActivityEventRepository` in `server/src/repositories/activity_events.py` — methods: `bulk_create(events)`, `get_by_time_range(user_id, start, end)`, `get_latest(user_id, limit)`.
4. **Schemas**: Pydantic models in `server/src/schemas/` — `ActivityEventCreate`, `ActivityEventResponse`, `ActivityEventBatch`.
5. **API endpoints** in `server/src/api/activity.py`:
   - `POST /api/activity/events` — accepts a list of events, bulk inserts. Returns count of inserted events.
   - `GET /api/activity/events?start=...&end=...` — returns user's events in a time range, paginated.
6. **Wire into FastAPI**: Register the router in `main.py`.

---

## Task 3: Skills Framework + Integrations (Oura, GitHub)

### Goal
A pluggable skill system where each external integration provides LangChain tools the AI agent can call on-demand. When the agent runs for a user, it dynamically loads tools from the user's connected integrations. Each integration is a "skill" — a bundle of LangChain tools + agent instructions + credential schema.

### Requirements
- Skills are LangChain `BaseTool` subclasses (same pattern as gb_gpt tools)
- Tools handle caching internally — check `integration_cache` before hitting external APIs
- User connects/disconnects integrations via OAuth
- Credentials encrypted at rest (Fernet symmetric encryption)
- Oura Ring and GitHub as first two integrations

### High-Level Implementation Plan
1. **Credential encryption** (`server/src/core/encryption.py`): Fernet symmetric encryption using `CREDENTIAL_ENCRYPTION_KEY` env var. Functions: `encrypt_credentials(dict) -> bytes`, `decrypt_credentials(bytes) -> dict`.
2. **Database models**:
   - `UserIntegrationModel` (`server/src/models/postgres/user_integrations.py`): `id`, `user_id (FK)`, `source`, `credentials_encrypted (LargeBinary)`, `scopes (JSONB)`, `is_enabled`, `connected_at`, `last_used_at`, `token_expires_at`. Unique on `(user_id, source)`.
   - `IntegrationCacheModel` (`server/src/models/postgres/integration_cache.py`): `id`, `user_id (FK)`, `source`, `data_type`, `date (Date)`, `data (JSONB)`, `fetched_at`, `expires_at`. Unique on `(user_id, source, data_type, date)`. Tools check this before hitting external APIs.
3. **Alembic migration** for both tables.
4. **Repositories**: `UserIntegrationRepository`, `IntegrationCacheRepository` — following existing ABC + concrete pattern.
5. **Skill framework** (`server/src/skills/`):
   - `base.py` — `BaseSkill` ABC with: `name`, `display_name`, `description`, `auth_type`, `credential_schema`, `get_tools(context) -> list[BaseTool]`, `get_agent_instructions() -> str`. Plus `SkillContext` dataclass (user_id, session, decrypted credentials, cache_repo).
   - `__init__.py` — `SkillRegistry` (dict mapping source names to skill instances), `register_all_skills()` called at startup.
6. **Oura skill** (`server/src/skills/oura/`):
   - `client.py` — Oura API v2 HTTP client (aiohttp). Endpoints: `/v2/usercollection/daily_sleep`, `/daily_activity`, `/daily_readiness`.
   - `tools.py` — 3 LangChain `BaseTool` subclasses:
     - `GetOuraSleep`: Fetch sleep data for a date. Cache TTL: 6h.
     - `GetOuraActivity`: Fetch activity/steps for a date. Cache TTL: 2h.
     - `GetOuraReadiness`: Fetch readiness score. Cache TTL: 6h.
   - Auth: OAuth2 (server exchanges authorization code for access_token + refresh_token).
   - Agent instructions: markdown explaining when to call each tool.
7. **GitHub skill** (`server/src/skills/github/`):
   - `client.py` — GitHub API HTTP client.
   - `tools.py` — 2 LangChain `BaseTool` subclasses:
     - `GetGitHubCommits`: Fetch commits for a date across user's repos. Cache TTL: 1h.
     - `GetGitHubPullRequests`: Fetch PRs opened/merged/reviewed. Cache TTL: 1h.
   - Auth: OAuth App (server exchanges code for token).
   - Agent instructions: cross-reference commits with VS Code sessions for richer labels.
8. **Schemas** (`server/src/schemas/integrations.py`): `IntegrationSummary`, `IntegrationListResponse`, `OAuthAuthorizeResponse`, `OAuthCallbackRequest`, `IntegrationConnectResponse`, `IntegrationDisconnectResponse`.
9. **API endpoints** (`server/src/api/integrations.py`, prefix `/api/integrations`):
   - `GET /` — list available integrations + user's connection status.
   - `GET /{source}/oauth/authorize` — get OAuth authorization URL.
   - `POST /{source}/oauth/callback` — handle OAuth callback, exchange code for tokens.
   - `DELETE /{source}/disconnect` — remove integration + clear cache.
   - `POST /{source}/refresh` — invalidate cached data.
10. **Config additions**: `credential_encryption_key`, `oura_client_id`, `oura_client_secret`, `github_client_id`, `github_client_secret`.
11. **Wire into FastAPI**: Register router in `main.py`, call `register_all_skills()` at startup.

---

## Task 4: AI Agent — Conversational Timeline (LangGraph)

### Goal
A conversational AI agent (modeled after gb_gpt's architecture) that generates timelines from activity data + skill tools, streams responses via WebSocket, and supports follow-up chat. When a user opens the web app, an initial prompt generates the calendar; the user can then continue chatting — asking questions about their day, requesting adjustments, drilling into specific time blocks.

### Requirements
- LangGraph ReAct pattern: `agent → tools → agent` loop (same as gb_gpt `react/graph.py`)
- WebSocket streaming with `astream_events(version="v2")` (same as gb_gpt `websocket.py`)
- Redis checkpointing for conversation persistence (same as gb_gpt `redis_chain_memory.py`)
- Dynamic tool loading: built-in tools + skill tools from user's connected integrations
- Activity data pre-processed into compact session summaries for the prompt
- Three execution modes: cron (end-of-day auto), manual trigger, real-time chat
- User edits to timeline entries persist and are preserved on re-generation

### High-Level Implementation Plan
1. **Dependencies**: `anthropic`, `langchain-anthropic`, `langgraph`, `langchain-core`, `redis[hiredis]`.
2. **Database models**:
   - `ChatModel` (`server/src/models/postgres/chats.py`): `id`, `user_id (FK)`, `name`, `date`, `trigger`, `llm_model`, `skills_used (JSONB)`, `total_input_tokens`, `total_output_tokens`, `total_cost_usd`, `created_at`. Modeled after gb_gpt's `ChatModel`.
   - `TimelineEntryModel` (`server/src/models/postgres/timeline_entries.py`): `id`, `user_id (FK)`, `date`, `start_time`, `end_time`, `label`, `category`, `source_summary`, `confidence`, `edited_by_user`, `chat_id (FK)`, `created_at`, `updated_at`. Indexed on `(user_id, date)`.
3. **Alembic migration** for both tables.
4. **Redis setup**: Add Redis service to `docker-compose.yaml`. Port `AsyncRedisSaver` checkpointer from gb_gpt.
5. **Activity preprocessor** (`server/src/agent/preprocessor.py`): Query `activity_events` for a user+date, cluster consecutive same-app events into sessions (merge gaps <2min), output compact text summary for the agent prompt.
6. **Prompt builder** (`server/src/agent/prompts.py`): Composable system prompt — role description + date + activity summary + skill instructions (dynamically loaded per user's connected integrations).
7. **Built-in tools** (`server/src/agent/tools/`):
   - `SaveTimelineEntries` — agent calls this to output structured timeline entries (writes to DB).
   - `GetActivitySessions` — re-query activity data for a different time range.
   - `GetExistingTimeline` — load previously generated entries (for edits/follow-ups).
8. **LangGraph agent** (`server/src/agent/graph.py`): ReAct pattern with `StateGraph(AgentState)`, `agent` and `tools` nodes, conditional edges. `llm.bind_tools(builtin_tools + skill_tools)`.
9. **Chain builder** (`server/src/agent/chain_builder.py`): Load user's integrations → decrypt credentials → build `SkillContext` → get tools + instructions → compile LangGraph with Redis checkpointer.
10. **Generation manager** (`server/src/agent/generation_manager.py`): Port from gb_gpt — manages generation state, Redis pub/sub + local async queues for streaming events to WebSocket clients.
11. **WebSocket handler** (`server/src/api/websocket.py`): Port from gb_gpt — `WebSocketConnection` class, authenticate, subscribe to chat, forward events (token, tool_start, tool_end, done, error). Stop/cancellation support.
12. **REST endpoints** (`server/src/api/timeline.py`):
   - `POST /api/timeline/generate` — trigger generation for a date (creates chat + runs agent).
   - `GET /api/timeline` — fetch timeline entries for a day or date range.
   - `PATCH /api/timeline/{id}` — user edits entry (sets `edited_by_user=true`).
   - `DELETE /api/timeline/{id}` — remove entry.
13. **Chat REST endpoints** (`server/src/api/chats.py`): List, get (with messages from Redis checkpoint), delete.
14. **LLM configuration** (`server/src/agent/llm.py`): `ChatAnthropic` instance, rate limiting via semaphore.
15. **Context management** (`server/src/agent/token_utils.py`): Token counting + history trimming. Port from gb_gpt.
16. **Cron job**: Background task for end-of-day auto-generation + expired `integration_cache` cleanup.
17. **Wire into FastAPI**: Register WebSocket route + REST routers in `main.py`.

---

## Task 5: Frontend — Calendar UI

### Goal
A clean calendar interface where users see their AI-generated timeline and can interact with it — review what they did, correct mistakes, and trigger new analyses.

### Requirements
- Day view: 24-hour vertical timeline with colored blocks for each activity
- Week view: condensed daily summaries
- Activity blocks show label, category, and time range
- Click a block to see details: AI reasoning, raw source events, confidence score
- Inline editing: rename, recategorize, adjust start/end times
- "Generate" button to trigger AI analysis for a date
- Authentication: login/register pages using existing JWT backend
- Integration settings page: connect/disconnect external sources
- Responsive layout (desktop-first, functional on mobile)

### High-Level Implementation Plan
1. **API client layer**: `client/src/api/` — Axios (or fetch wrapper) configured with JWT auth header from Pinia store. Modules: `auth.ts`, `activity.ts`, `timeline.ts`, `integrations.ts`.
2. **Auth store + pages**:
   - Pinia store `client/src/stores/auth.ts`: holds JWT, user info, login/logout/register actions.
   - Pages: `LoginView.vue`, `RegisterView.vue`. Redirect to calendar after auth.
3. **Router setup**: `/login`, `/register`, `/` (day view), `/week` (week view), `/settings` (integrations). Auth guard on protected routes.
4. **Day view** (`client/src/views/DayView.vue`):
   - Vertical axis: hours 0-24. Each `TimelineEntry` rendered as a positioned block (`top` = start time, `height` = duration).
   - Color-coded by category (work, communication, browsing, rest, etc.).
   - Date picker to navigate between days.
   - "Generate Timeline" button → calls `POST /api/timeline/generate`, refreshes view.
5. **Week view** (`client/src/views/WeekView.vue`):
   - 7 columns, each showing stacked category totals for the day. Click a day → navigate to day view.
6. **Detail panel** (`client/src/components/EntryDetail.vue`):
   - Slide-out or modal when clicking a block. Shows: label, category, time range, confidence, source summary.
   - Edit form: inline-editable label and category, draggable time handles.
   - Save → `PATCH /api/timeline/{id}`.
7. **Settings page** (`client/src/views/SettingsView.vue`):
   - List of available integrations. Connect/disconnect buttons. Shows last sync time.
8. **Styling**: Use a lightweight CSS framework or utility classes. Keep it minimal and clean — the timeline blocks themselves are the main UI element.

---

## Task 6: Polish & Ops

### Goal
Make the product installable, reliable, and ready for real daily use.

### Requirements
- Easy daemon installation on Linux and macOS
- Production deployment is stable and monitored
- New users can go from zero to seeing their first timeline with minimal friction

### High-Level Implementation Plan
1. **Daemon packaging**:
   - Linux: `.deb` package via `cargo-deb`, plus a shell install script. Systemd service included.
   - macOS: Homebrew formula or downloadable binary + install script. LaunchAgent plist included.
   - Both: `digitalgulag-daemon setup` wizard — prompts for server URL, authenticates, installs service.
2. **Production hardening**:
   - Rate limiting on ingestion endpoint (per-user, token bucket).
   - CORS config for the frontend domain.
   - Input sanitization on all endpoints.
   - Graceful error responses (no stack traces in prod).
3. **Monitoring**:
   - Add Prometheus metrics: events ingested/sec, timeline generations/day, integration sync success/failure.
   - Grafana dashboard for operational visibility.
4. **Onboarding flow**:
   - After first login, frontend shows a setup wizard: "Install the daemon" (platform-specific instructions) → "Connect integrations" (optional) → "Generate your first timeline".

---

## Execution Order

```
1 (Daemon) ──────┐
                  ├──→ 3 (Skills + Integrations) ──→ 4 (AI Agent + Chat) ──→ 6 (Polish)
2 (Ingest API) ──┘

5 (Frontend) ─── starts early with mocks, integrates with 4 (WebSocket chat + calendar)
```

Tasks 1 and 2 are done. Task 3 depends on 2 (needs server patterns). Task 4 depends on 3 (agent uses skills). Task 4 also touches Task 5 since WebSocket chat needs frontend work. Task 6 is last.
