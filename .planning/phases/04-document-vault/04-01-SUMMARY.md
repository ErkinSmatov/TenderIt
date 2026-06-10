---
phase: 04-document-vault
plan: "01"
subsystem: backend
tags: [minio, document-storage, orm, migration, tdd]
dependency_graph:
  requires: [02-auth-company-profile]
  provides: [minio-service, document-model, expiry-logic, migration-0003]
  affects: [backend/app/main.py, backend/app/models, backend/app/services, backend/alembic]
tech_stack:
  added: [minio>=7.2.14, python-multipart>=0.0.9]
  patterns: [singleton-minio-client, asyncio.to_thread, tz-aware-expiry, alembic-migration]
key_files:
  created:
    - backend/app/services/minio_service.py
    - backend/app/models/document.py
    - backend/app/schemas/document.py
    - backend/app/services/document_service.py
    - backend/alembic/versions/0003_create_documents.py
    - backend/tests/test_documents.py
    - backend/tests/test_documents_expiry.py
  modified:
    - backend/pyproject.toml
    - backend/app/config.py
    - backend/app/models/__init__.py
    - backend/app/main.py
decisions:
  - "minio SDK singleton at module import (not per-request) — thread-safe via urllib3 PoolManager + CPython GIL"
  - "ensure_bucket_exists called via asyncio.to_thread in lifespan — idempotent on restart"
  - "compute_expiry_status uses datetime.now(timezone.utc) — tz-aware comparison required by Python 3.12 (T-04-07)"
  - "Document stored as TEXT category (not PG ENUM) — no ALTER TYPE needed for v2 extension"
  - "migration 0003 down_revision=0002 — follows Phase 3 tenders/watchlist migration"
metrics:
  duration: "~6 min"
  completed: "2026-06-11"
  tasks_completed: 3
  tasks_total: 3
  files_created: 7
  files_modified: 4
---

# Phase 4 Plan 01: Document Vault Infrastructure (Wave 0) Summary

**One-liner:** MinIO singleton + ensure_bucket_exists lifespan hook + Document ORM + Alembic migration 0003 + compute_expiry_status tz-aware pure function.

## Completed Tasks

| # | Task | Commit | Type | Key Output |
|---|------|--------|------|-----------|
| 1 | Зависимости + config + MinIO-сервис | 1227dd5 | feat | minio_service.py singleton, pyproject.toml, minio_secure config |
| 2 | Document модель + схемы + document_service + миграция | bbdb2f3 | feat (GREEN) | Document ORM, schemas, compute_expiry_status, migration 0003 |
| 2 RED | TDD RED test for compute_expiry_status | 63bdd79 | test | test_documents_expiry.py failing (ModuleNotFoundError) |
| 3 | lifespan hook + тест-скаффолд | 6ca6b5f | feat | main.py lifespan, test_documents.py with authed fixtures |

## TDD Gate Compliance

Task 2 followed RED/GREEN cycle:
- **RED commit:** 63bdd79 — `test(04-01): add failing test for compute_expiry_status (TDD RED)` — failed with `ModuleNotFoundError: No module named 'app.services.document_service'`
- **GREEN commit:** bbdb2f3 — `feat(04-01): implement Document model, schemas, document_service, migration 0003` — all 5 branches pass

## What Was Built

### minio_service.py
Module-level singleton `_minio_client = Minio(...)` created at import time — thread-safe through CPython GIL protecting urllib3 PoolManager operations. `ensure_bucket_exists()` is synchronous and idempotent: checks `bucket_exists("tenderit-documents")` before `make_bucket`.

### Document ORM (document.py)
- Columns: id, user_id (FK→users.id CASCADE), file_name, file_key, file_size, mime_type, category (VARCHAR 50), expires_at (TIMESTAMPTZ nullable), uploaded_at (TIMESTAMPTZ server_default now())
- No relationship in Phase 4 — Phase 5 adds application_documents FK

### Schemas (document.py)
- `DocumentCategory(str, Enum)` — ustav/license/certificate/registration/other
- `ExpiryStatus = Literal["ok","warning_14","warning_7","expired"]`
- `DocumentResponse(BaseModel, from_attributes=True)` — includes `expiry_status` field (computed in service layer)
- `DocumentPatchRequest(BaseModel)` — optional category + expires_at

### document_service.py
`compute_expiry_status(expires_at: datetime | None) -> ExpiryStatus` — pure function, no I/O:
- None → "ok"
- days > 14 → "ok"
- 8 ≤ days ≤ 14 → "warning_14"  
- 1 ≤ days ≤ 7 → "warning_7"
- days < 0 → "expired"
Uses `datetime.now(timezone.utc)` — tz-aware, prevents TypeError in Python 3.12 (T-04-07 mitigation).

### Alembic migration 0003
- revision="0003", down_revision="0002"
- Creates documents table with ForeignKeyConstraint(user_id→users.id, ondelete=CASCADE)
- Two indexes: ix_documents_user_id (for list queries), ix_documents_user_expires (for attachable filter)

### main.py lifespan
Added `await asyncio.to_thread(ensure_bucket_exists)` before yield — MinIO bucket initialized on every app startup, idempotent.

### test_documents.py
- `authed` / `authed2` fixtures with `doctest` / `doctest2` prefixes (unique per test via uuid4)
- `test_expiry_status_logic` — GREEN, covers all 5 branches
- 8 stub tests skipped with `pytest.mark.skip(reason="Plan 02: router not yet implemented")`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Missing Config] Added goszakup_api_token to Settings**
- **Found during:** Task 1
- **Issue:** worktree config.py lacked `goszakup_api_token: str = ""` field (present in main branch) — would cause AttributeError when goszakup_service.py imported during test collection
- **Fix:** Added `goszakup_api_token: str = ""` to Settings class
- **Files modified:** backend/app/config.py
- **Commit:** 1227dd5

**2. [Rule 3 - Missing Config] worktree models/__init__.py missing Tender/UserWatchlist imports**
- **Found during:** Task 2
- **Issue:** worktree `models/__init__.py` only had User + CompanyProfile (Phase 2 state), not Phase 3 Tender/UserWatchlist — Alembic autogenerate would have incomplete visibility. Phase 3 files are untracked in main branch.
- **Fix:** Added only `Document` import as required by Plan. Tender/UserWatchlist remain untracked (managed by their own wave/plan). Not blocking for this plan — migration 0003 only references users.id FK.
- **Files modified:** backend/app/models/__init__.py
- **Commit:** bbdb2f3

**3. [Rule 3 - Missing Module] worktree main.py missing tenders router**
- **Found during:** Task 3
- **Issue:** worktree main.py (Phase 2 state) lacks tenders router import — Plan 03 files are untracked. Not blocking for Plan 04-01 (only lifespan hook needed).
- **Fix:** Added only `ensure_bucket_exists` as required. Did NOT add documents router (Plan 02 scope).
- **Files modified:** backend/app/main.py
- **Commit:** 6ca6b5f

## Known Stubs

None — `test_documents.py` stubs are marked with `pytest.mark.skip` with explicit reason ("Plan 02: router not yet implemented") and are not expected to pass in this wave. They are intentional scaffolding, not data stubs.

## Threat Flags

None — no new network endpoints, auth paths, or file access patterns introduced in this plan. All threat mitigations from the plan's threat_model were applied:
- T-04-03: MinIO bucket created without public policy (bucket created private via `make_bucket` without policy argument)
- T-04-07: `compute_expiry_status` uses `datetime.now(timezone.utc)` — tz-aware comparison

## Self-Check

**Files:**
- backend/app/services/minio_service.py: FOUND
- backend/app/models/document.py: FOUND
- backend/app/schemas/document.py: FOUND
- backend/app/services/document_service.py: FOUND
- backend/alembic/versions/0003_create_documents.py: FOUND
- backend/tests/test_documents.py: FOUND

**Commits:**
- 1227dd5: feat(04-01) Task 1 — FOUND
- 63bdd79: test(04-01) TDD RED — FOUND
- bbdb2f3: feat(04-01) Task 2 GREEN — FOUND
- 6ca6b5f: feat(04-01) Task 3 — FOUND

## Self-Check: PASSED
