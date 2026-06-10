---
phase: 04-document-vault
plan: "02"
subsystem: backend
tags: [fastapi, minio, documents, idor, tdd, crud]
dependency_graph:
  requires: [04-01-document-vault-infrastructure]
  provides: [documents-api, document-crud, idor-protected-routes]
  affects: [backend/app/routers/documents.py, backend/app/services/document_service.py, backend/app/main.py, backend/tests/test_documents.py]
tech_stack:
  added: [python-multipart>=0.0.9]
  patterns: [module-level-minio-reference, idor-404-pattern, tdd-red-green, asyncio.to_thread, service-layer-expiry]
key_files:
  created:
    - backend/app/routers/documents.py
  modified:
    - backend/app/services/document_service.py
    - backend/app/main.py
    - backend/tests/test_documents.py
decisions:
  - "module-level import (import minio_service as module) instead of from-import for _minio_client — enables patch('app.services.minio_service._minio_client') in tests"
  - "to_response() builds dict manually before model_validate() — Pydantic v2 model_validate() does not accept 'update' kwarg unlike model_copy()"
  - "attachable route declared before /{doc_id}/url — FastAPI uses declaration-order matching (RESEARCH.md Finding #4)"
  - "IDOR returns 404 (not 403) for cross-user access — avoids leaking document existence (T-04-01)"
  - "MinIO delete before DB delete in delete_document — orphaned file preferred over orphaned metadata (Pitfall 5)"
metrics:
  duration: "~8 min"
  completed: "2026-06-11"
  tasks_completed: 3
  tasks_total: 3
  files_created: 1
  files_modified: 3
---

# Phase 4 Plan 02: Document Vault API Routes (Wave 1) Summary

**One-liner:** 6 auth-gated CRUD routes for Document Vault with IDOR protection (404 for cross-user), 413 pre-upload size check, pre-signed URL TTL 15 min, and MinIO mock integration tests.

## Completed Tasks

| # | Task | Commit | Type | Key Output |
|---|------|--------|------|-----------|
| TDD RED | Реальные тесты вместо stub/skip | a930c24 | test | test_documents.py с 8 integration тестами, все падают 404 |
| 1 | document_service CRUD + upload/list роуты | 82380c3 | feat | list_user_documents, list_attachable, get_user_document, create_document, delete_document, to_response; POST/GET /documents |
| 2 | attachable/url/patch/delete роуты + router registration | 82380c3 | feat | GET /attachable (ДО /{id}/url), GET /{id}/url, PATCH /{id}, DELETE /{id}; main.py include_router |
| 3 | Полные unit-тесты с MinIO-моком | a930c24 | test | 8 integration тестов зелёные, вся сюита 61 passed |

*Примечание: Task 2 и Task 3 были реализованы в рамках Task 1 (TDD RED+GREEN цикл охватил все 6 роутов и все тесты одновременно).*

## TDD Gate Compliance

Task 1 следовал RED/GREEN циклу:
- **RED commit:** a930c24 — `test(04-02): add failing tests for documents router (TDD RED)` — 8 тестов падали с 404 (роутер не существовал)
- **GREEN commit:** 82380c3 — `feat(04-02): implement document_service CRUD + upload/list routes (TDD GREEN)` — все 9 тестов (включая Wave 0) зелёные

## What Was Built

### document_service.py — CRUD функции
- `list_user_documents(db, user_id)` — SELECT с WHERE user_id, ORDER BY uploaded_at DESC
- `list_attachable_documents(db, user_id)` — фильтр: expires_at IS NULL OR expires_at > now()
- `get_user_document(db, user_id, doc_id)` — SELECT с WHERE id AND user_id (IDOR-safe)
- `create_document(db, user_id, ...)` — INSERT + commit + refresh
- `delete_document(db, user_id, doc_id)` — MinIO remove_object FIRST, потом db.delete (Pitfall 5)
- `to_response(doc)` — dict construction + model_validate (Pydantic v2 compatible)

### documents.py router — 6 роутов

| Маршрут | Статус | Особенности |
|---------|--------|-------------|
| POST /documents | 201 | 413 до put_object, uuid4 в ключе, file.file напрямую (no read()) |
| GET /documents | 200 | список с expiry_status |
| GET /documents/attachable | 200 | объявлен ДО /{id}/url (Finding #4) |
| GET /documents/{id}/url | 200 | presigned_get_object TTL 15 мин, IDOR→404 |
| PATCH /documents/{id} | 200 | partial update category/expires_at, IDOR→404 |
| DELETE /documents/{id} | 204 | MinIO→DB порядок, IDOR→404 |

### Threat Mitigations Applied

| Threat | Mitigation |
|--------|-----------|
| T-04-01 IDOR | get_user_document фильтрует по user_id; возвращает 404 (не 403) |
| T-04-02 DoS | file.size > MAX_FILE_SIZE проверяется ДО put_object |
| T-04-03 Path traversal | uuid4 в object_key, оригинальное имя только в file_name |
| T-04-05 EoP | user_id из current_user.id (JWT), никогда из тела |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pydantic v2 model_validate() не принимает update= аргумент**
- **Found during:** Task 1 (первый запуск теста upload_success)
- **Issue:** `DocumentResponse.model_validate(doc, update={...})` бросает TypeError — Pydantic v2 `model_validate` не имеет параметра `update`
- **Fix:** Заменено на ручное построение словаря с полями ORM + вычисленным `expiry_status`, затем `model_validate(dict)`
- **Files modified:** backend/app/services/document_service.py
- **Commit:** 82380c3

**2. [Rule 2 - Missing Dependency] python-multipart не установлен**
- **Found during:** Task 1 (первый запуск тестов)
- **Issue:** FastAPI требует python-multipart для UploadFile/Form; без него RuntimeError при старте
- **Fix:** `pip install python-multipart` (уже в pyproject.toml из Plan 01, но не установлен в текущем env)
- **Files modified:** нет (уже в pyproject.toml)
- **Commit:** нет (системная зависимость)

**3. [Rule 3 - Blocking] Прямой from-import _minio_client блокирует тестовый мок**
- **Found during:** Task 1 (test_upload_success падал: mock_minio.put_object.assert_called_once() — 0 вызовов)
- **Issue:** `from app.services.minio_service import _minio_client` копирует ссылку на объект; `patch("app.services.minio_service._minio_client")` заменяет имя в источнике, но не обновляет скопированную ссылку в роутере
- **Fix:** Заменено на `import app.services.minio_service as minio_service`, доступ через `minio_service._minio_client` — атрибут модуля, патч работает правильно
- **Files modified:** backend/app/routers/documents.py, backend/app/services/document_service.py
- **Commit:** 82380c3

## Known Stubs

None — все 6 роутов реализованы полностью и протестированы.

## Threat Flags

None — все угрозы из threat_model плана закрыты:
- T-04-01: IDOR через get_user_document (user_id filter + 404)
- T-04-02: size check перед put_object → 413
- T-04-03: uuid4 в object_key
- T-04-05: user_id из JWT (get_current_user), нет в body

## Self-Check

**Files:**
- backend/app/routers/documents.py: FOUND
- backend/app/services/document_service.py: FOUND (CRUD added)
- backend/app/main.py: FOUND (documents.router registered)
- backend/tests/test_documents.py: FOUND (8 integration tests)

**Commits:**
- a930c24: test(04-02) TDD RED — FOUND
- 82380c3: feat(04-02) TDD GREEN — FOUND

## Self-Check: PASSED
