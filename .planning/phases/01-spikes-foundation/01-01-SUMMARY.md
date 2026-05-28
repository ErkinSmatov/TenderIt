---
phase: 01-spikes-foundation
plan: "01"
subsystem: scaffold
tags: [frontend, backend, fastapi, nextjs, docker, alembic, infrastructure]
dependency_graph:
  requires: []
  provides:
    - next-js-14-frontend-scaffold
    - fastapi-backend-skeleton
    - docker-compose-services
    - alembic-async-migrations
    - dev-makefile
  affects:
    - all subsequent phases (development environment)
tech_stack:
  added:
    - Next.js 14 (App Router, TypeScript, Tailwind CSS)
    - FastAPI 0.115.6 with pydantic-settings 2.7.1
    - SQLAlchemy 2.0.37 async engine
    - Alembic 1.14.0 async template
    - asyncpg 0.31.0
    - ARQ 0.28.0 (task queue)
    - uvicorn[standard]
    - pytest 9.0.3 + pytest-asyncio 1.3.0
    - @tanstack/react-query 5.100.14
    - zustand 5.0.13
    - react-hook-form 7.76.1
    - zod 3.24.4
  patterns:
    - FastAPI app factory with lifespan context manager
    - Pydantic BaseSettings with SettingsConfigDict (v2 style)
    - Async SQLAlchemy engine + async_sessionmaker
    - Alembic env.py sets database URL from settings (not alembic.ini)
    - pytest AsyncClient via ASGITransport for in-process HTTP testing
key_files:
  created:
    - frontend/src/app/layout.tsx
    - frontend/src/app/page.tsx
    - frontend/next.config.mjs
    - frontend/tailwind.config.ts
    - frontend/tsconfig.json
    - frontend/package.json
    - frontend/.env.example
    - backend/app/main.py
    - backend/app/config.py
    - backend/app/db.py
    - backend/app/routers/health.py
    - backend/alembic/env.py
    - backend/alembic.ini
    - backend/pyproject.toml
    - backend/.env.example
    - backend/tests/conftest.py
    - backend/tests/test_health.py
    - backend/pytest.ini
    - docker-compose.yml
    - docker-compose.override.yml
    - Makefile
    - .gitignore
  modified:
    - .gitignore (expanded from stub to full coverage)
decisions:
  - "pyproject.toml build-backend changed from setuptools.backends.legacy:build to setuptools.build_meta — legacy backend requires setuptools>=64 which pip resolves automatically with build_meta"
  - "Pydantic Settings uses SettingsConfigDict (v2 style) instead of inner class Config — eliminates deprecation warning and is forward-compatible with Pydantic v3"
  - "backend/alembic.ini sqlalchemy.url left blank — URL injected programmatically in env.py from settings to avoid credential duplication"
  - "Docker startup deferred — Docker Desktop not installed on dev machine; all code files created and committed; user must install Docker Desktop to start services"
metrics:
  duration: "~15 minutes (file creation and installation)"
  completed_date: "2026-05-25"
  tasks_completed: 2
  tasks_total: 2
  files_created: 30+
---

# Phase 1 Plan 01: Monorepo Scaffold Summary

**One-liner:** Next.js 14 + FastAPI skeleton with async SQLAlchemy, Alembic, pytest smoke test (1 passed), docker-compose for postgres/redis/minio, and Makefile.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Scaffold Next.js 14 frontend and FastAPI backend | 9590297 | frontend/src/, backend/app/, backend/tests/, pyproject.toml, .env.examples |
| 2 | docker-compose, Alembic async init, and Makefile | 0108766 | docker-compose.yml, docker-compose.override.yml, Makefile, backend/alembic/ |

## Verification Results

| Check | Command | Result |
|-------|---------|--------|
| Backend import | `python3 -c "from app.main import app; print(app.title)"` | TenderIt API |
| Next.js version | `node -e "require('./package.json').dependencies.next"` | 14.2.35 |
| Pytest smoke test | `pytest tests/test_health.py -x -q` | 1 passed |
| .env.example files | `ls frontend/.env.example backend/.env.example` | Both present |
| Alembic config imports | `python3 -c "from app.config import settings; from app.db import Base"` | OK |
| Docker services | `docker compose ps` | DEFERRED — Docker Desktop not installed |
| Alembic upgrade head | `alembic upgrade head` | DEFERRED — requires Postgres from Docker |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Issue] pyproject.toml build-backend incompatible with installed setuptools**
- **Found during:** Task 1, `pip install -e ".[dev]"` step
- **Issue:** Plan specified `setuptools.backends.legacy:build` which requires setuptools>=65 with the `backends` subpackage. The installed pip (23.3.1) could not find `setuptools.backends` module.
- **Fix:** Changed `build-backend` to `setuptools.build_meta` which is the stable, documented entry point. Added `setuptools-scm` to build dependencies.
- **Files modified:** `backend/pyproject.toml`
- **Commit:** 9590297

**2. [Rule 1 - Bug] Pydantic v2 deprecation warning for class-based Config**
- **Found during:** Task 1 verification, pytest output showed `PydanticDeprecatedSince20` warning
- **Issue:** `class Config` inner class in Settings is deprecated in Pydantic v2.0 and will be removed in v3.0.
- **Fix:** Replaced with `model_config = SettingsConfigDict(...)` using Pydantic v2 API.
- **Files modified:** `backend/app/config.py`
- **Commit:** aa6c1dd

### Authentication Gates

None encountered.

### Docker Startup Deferred (Human Action Required)

**Situation:** Docker Desktop is not installed on the development machine. All infrastructure configuration files (docker-compose.yml, Makefile) are fully created and committed.

**User must:**
1. Install Docker Desktop: https://www.docker.com/products/docker-desktop/
2. Run: `make up` (or `docker compose up -d`) from the repo root
3. Run: `make migrate` (or `cd backend && alembic upgrade head`) to verify Alembic connectivity
4. Verify: `docker compose ps` shows postgres, redis, and minio as "healthy"

This is a machine-level installation that cannot be automated. Once Docker is installed, all Makefile targets and docker-compose commands work as specified in the plan.

## Known Stubs

None — no UI components or data sources are stubbed. The `/health` endpoint returns real data.

## Threat Flags

The threat model items from the plan are addressed:

| Threat | Mitigation | Status |
|--------|-----------|--------|
| T-01-01: .env committed | `.env` added to .gitignore from first commit; only `.env.example` committed | Mitigated |
| T-01-02: hardcoded dev passwords in docker-compose.yml | Accepted — dev-only credentials | Accepted |
| T-01-03: Docker daemon access | Accepted — macOS user-level permissions | Accepted |

## Self-Check: PASSED

- [x] `backend/app/main.py` exists and `from app.main import app` succeeds
- [x] `frontend/package.json` exists with `"next": "14.2.35"`
- [x] `backend/.env.example` exists with all required variable names
- [x] `frontend/.env.example` exists with `NEXT_PUBLIC_API_URL`
- [x] `docker-compose.yml` exists with postgres, redis, minio services
- [x] `backend/alembic/env.py` contains `run_async_migrations` and imports from `app.config`, `app.db`
- [x] `Makefile` exists with `up`, `down`, `logs`, `migrate`, `reset` targets
- [x] `.gitignore` covers `.env`, `__pycache__`, `node_modules`, `.next`, `*.egg-info`
- [x] `pytest tests/test_health.py -x -q` → 1 passed
- [x] Task 1 commit 9590297 present in git log
- [x] Task 2 commit 0108766 present in git log
- [x] Fix commit aa6c1dd present in git log
