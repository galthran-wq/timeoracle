# TimeOracle

AI-powered personal time tracker. Rust daemon captures computer activity, FastAPI server analyzes it with AI, Vue 3 calendar UI displays the timeline.

## Architecture

```
Rust Daemon (Linux/macOS)  ──►  FastAPI Server  ──►  PostgreSQL
  captures: window, app,         ingestion API        activity_events
  URL, idle state                AI agent              timeline_entries
  buffers in SQLite              integrations          integration_events
                                      │
External APIs (Oura, etc.) ─────────►─┘
                                      │
                              Vue 3 Calendar UI
```

## Project Structure

```
server/          FastAPI backend (Python 3.12+)
  src/api/         API routers (users.py, activity.py)
  src/core/        Config, auth (JWT), database, metrics
  src/models/      SQLAlchemy models (postgres/)
  src/repositories/ Data access layer
  src/schemas/     Pydantic request/response models
  alembic/         Database migrations
  tests/           Pytest tests
  scripts/         CLI tools (create_user, make_superuser)

client/          Vue 3 frontend (TypeScript, Vite, Pinia)
daemon/          Rust activity capture daemon (Tokio, SQLite buffer)
monitoring/      Prometheus + Grafana config
nginx/           Reverse proxy configs (dev + prod)
```

## Tech Stack

| Layer      | Tech                                                  |
|------------|-------------------------------------------------------|
| Backend    | FastAPI 0.104, SQLAlchemy 2.0, asyncpg, Alembic       |
| Auth       | JWT (python-jose), bcrypt (passlib)                    |
| Frontend   | Vue 3.5, Vite 7, Pinia 3, TypeScript 5.8              |
| Daemon     | Rust, Tokio, reqwest, rusqlite, clap                   |
| Database   | PostgreSQL 15                                          |
| Infra      | Docker Compose, Nginx, Prometheus, Grafana             |

## Development Commands

```bash
# Docker dev environment
make dev-up                      # start all services
make dev-down                    # stop
make dev-logs server             # tail server logs
make dev-db                      # psql shell

# Migrations
make dev-make-migrations "name"  # generate alembic migration
# or inside server/: alembic revision --autogenerate -m "name"
# apply: alembic upgrade head

# Testing (server)
cd server
uv sync --extra dev              # install deps
uv run alembic upgrade head      # apply migrations
uv run python -m pytest -v       # run tests

# Users
make dev-user user@example.com password
make dev-superuser admin@example.com
```

## Server Conventions

### Code Organization

Pattern: **Model → Schema → Repository → API Router → main.py registration**

- **Models** (`src/models/postgres/`): SQLAlchemy declarative models inheriting `Base` from `src.core.database`. UUID PKs with `as_uuid=True`. Export new models in `__init__.py`.
- **Schemas** (`src/schemas/`): Pydantic v2 models. Use `from_attributes = True` for ORM conversion. Separate request/response classes.
- **Repositories** (`src/repositories/`): Abstract interface (ABC) + concrete class taking `AsyncSession`. All DB ops are async. Use `select()` queries. Commit + rollback in try/except.
- **API** (`src/api/`): `APIRouter` with prefix and tag. Dependency injection via `Depends()` for session, repo, and auth. Register in `main.py` with `app.include_router()`.

### Auth Pattern

```python
from src.core.auth import get_current_user
current_user: UserModel = Depends(get_current_user)    # requires JWT
current_user: UserModel = Depends(get_current_superuser)  # requires admin
```

### Database

- Async throughout: `AsyncSession`, `create_async_engine`
- Connection string: `postgresql+asyncpg://...` from `settings.postgres_url`
- Session via `get_postgres_session()` generator (DI)
- `server_default=func.now()` for timestamps (not Python-side defaults) — needed for bulk inserts

### Testing

- pytest with `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed)
- `conftest.py`: creates/drops tables per test, overrides DB session dependency
- Use `httpx.AsyncClient` with `ASGITransport` for API tests
- Tests run against real PostgreSQL (CI uses postgres:15-alpine service)

### Error Handling

- `ValueError` → HTTP 400
- Auth failures → HTTP 401
- Generic exceptions → HTTP 500 (log server-side, don't leak details to client)

## CI

GitHub Actions workflow (`.github/workflows/server-tests.yml`):
- Triggers on `server/**` changes to main or PRs
- PostgreSQL 15 service container
- `uv sync --frozen --extra dev` → `alembic upgrade head` → `pytest -v`

## Key Configuration

- Server config: `src/core/config.py` — `pydantic_settings.BaseSettings`, reads from env vars or `.env` file
- ENV=test loads `.env.test`, ENV=production loads `.env.prod`, default loads `.env`
- Docker services configured in `docker-compose.yaml` + override files
- Dev postgres exposed on port `$DEV_POSTGRES_PORT` (default 5444)

## Task Roadmap

See `PLAN.md` for full details. Order:

1. Rust Daemon + Ingestion API (parallel) — **done**
2. External Integrations (Oura first)
3. AI Agent (depends on 1+2)
4. Frontend Calendar UI (starts early with mocks)
5. Polish & Ops
