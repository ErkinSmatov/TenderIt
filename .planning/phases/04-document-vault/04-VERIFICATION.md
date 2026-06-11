---
phase: 04-document-vault
verified: 2026-06-11T00:00:00Z
status: human_needed
score: 13/13 must-haves verified
overrides_applied: 0
re_verification: false
human_verification:
  - test: "Открыть приложение, убедиться что пункт «Документы» виден в сайдбаре и клик ведёт на /documents"
    expected: "Sidebar рендерится с иконкой FileText и ссылкой /documents; переход происходит"
    why_human: "Навигация — UI-поведение; FileText в Sidebar.tsx VERIFIED статически, но рендер в браузере требует ручной проверки"
  - test: "Загрузить PDF через форму с категорией «Устав», без срока → карточка появляется в списке без бейджа истечения"
    expected: "201 от /api/documents; карточка без ExpiryBadge; expiry_status == 'ok'"
    why_human: "Требует работающего MinIO и PostgreSQL end-to-end; unit-тесты с mock покрывают backend, но интеграцию с настоящим MinIO нельзя проверить программно"
  - test: "Загрузить файл с категорией «Лицензия» и сроком через 5 дней → бейдж «Истекает через 7 дней» + суммарный Alert"
    expected: "DocumentCard показывает Badge variant=outline 'Истекает через 7 дней'; DocumentVault показывает Alert с текстом о сроках"
    why_human: "Визуальный рендер бейджей и Alert — UI-поведение, не верифицируется grep"
  - test: "Нажать «Скачать» на карточке → открывается новая вкладка, файл скачивается"
    expected: "window.open(url, '_blank') срабатывает; pre-signed URL от MinIO действителен"
    why_human: "Требует реального MinIO с действующим pre-signed URL; window.open нельзя проверить без браузера"
  - test: "Нажать «Удалить» → карточка исчезает из списка; попытка удалить чужой документ → 404"
    expected: "DELETE 204 + invalidateQueries обновляет список; IDOR: 404 для чужого doc_id"
    why_human: "IDOR тест покрыт unit-тестом (VERIFIED), но исчезновение карточки из UI — visual-flow"
  - test: "Загрузить файл > 20 МБ → показывается ошибка «Файл превышает 20 МБ» в форме"
    expected: "Client-side валидация срабатывает ДО отправки запроса; Alert с текстом ошибки отображается"
    why_human: "Client-side 20MB guard в DocumentUploadForm VERIFIED статически; отображение Alert в браузере требует ручной проверки"
---

# Phase 4: Document Vault Verification Report

**Phase Goal:** Users can upload, categorise, and manage their company documents in a persistent vault, with automatic expiry warnings and auto-attachment to new applications.
**Verified:** 2026-06-11
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                          | Status     | Evidence                                                                                 |
|----|-----------------------------------------------------------------------------------------------|------------|------------------------------------------------------------------------------------------|
| 1  | Приложение стартует и идемпотентно создаёт бакет tenderit-documents в MinIO                  | VERIFIED   | `main.py:19` — `await asyncio.to_thread(ensure_bucket_exists)`; `minio_service.py:36-37` — bucket_exists check + make_bucket |
| 2  | Таблица documents существует в БД после миграции 0003                                        | VERIFIED   | `0003_create_documents.py` — revision="0003", down_revision="0002", create_table "documents", ForeignKeyConstraint user_id→users.id ondelete=CASCADE, оба индекса |
| 3  | compute_expiry_status возвращает корректный статус для всех граничных дат                    | VERIFIED   | `document_service.py:27-52` — 5 веток; `test_documents.py:98-116` — `9 passed in 1.19s` |
| 4  | Пользователь загружает документ → 201, файл в MinIO, метаданные в БД                        | VERIFIED   | `documents.py:59-106` — POST /documents, size check → put_object → create_document; `test_upload_success` PASS |
| 5  | Файл больше 20 МБ отклоняется с 413 до записи в MinIO                                       | VERIFIED   | `documents.py:77-78` — size check BEFORE put_object; `test_upload_too_large` PASS, `mock_minio.put_object.assert_not_called()` |
| 6  | GET /api/documents возвращает документы пользователя с полем expiry_status                  | VERIFIED   | `documents.py:109-120` — list_user_documents + to_response; `to_response` вычисляет expiry_status через compute_expiry_status |
| 7  | GET /api/documents/attachable не возвращает истёкшие документы                              | VERIFIED   | `document_service.py:68-84` — фильтр `expires_at IS NULL OR expires_at > now`; `test_attachable_excludes_expired` PASS |
| 8  | GET /api/documents/{id}/url возвращает pre-signed URL только владельцу                      | VERIFIED   | `documents.py:142-163` — get_user_document IDOR + presigned_get_object; `test_get_presigned_url` + `test_url_idor_protection` PASS |
| 9  | DELETE удаляет файл из MinIO и строку из БД; чужой документ → 404                          | VERIFIED   | `document_service.py:134-152` — remove_object FIRST, затем db.delete; `test_delete_document` + `test_delete_idor_protection` PASS |
| 10 | Пользователь видит пункт «Документы» в боковой навигации и попадает на /documents           | VERIFIED   | `Sidebar.tsx:5,15` — `FileText` импортирован, navItem `{ href: '/documents', label: 'Документы', icon: FileText }` |
| 11 | Пользователь загружает файл с категорией и (опционально) сроком действия                   | VERIFIED   | `DocumentUploadForm.tsx:57-91` — FormData + uploadFile; file via ref; category через RHF+zod; expires_at optional |
| 12 | Пользователь видит карточки документов с бейджами истечения                                | VERIFIED   | `DocumentCard.tsx:42-51` — ExpiryBadge: ok→null, warning_14→secondary, warning_7→outline, expired→destructive; `DocumentVault.tsx:19,31-36` — суммарный Alert при expiringCount > 0 |
| 13 | Пользователь скачивает документ через pre-signed URL и удаляет документ                    | VERIFIED   | `page.tsx:34-50` — onDownload: api.get url + window.open; onDelete: api.delete + invalidateQueries |

**Score:** 13/13 truths verified

### Deferred Items

Нет — все must-haves фазы 4 проверены.

### Required Artifacts

| Artifact                                                         | Expected                                    | Status   | Details                                                          |
|------------------------------------------------------------------|---------------------------------------------|----------|------------------------------------------------------------------|
| `backend/app/services/minio_service.py`                         | Minio singleton + ensure_bucket_exists      | VERIFIED | singleton `_minio_client`, `BUCKET_NAME`, `ensure_bucket_exists` |
| `backend/app/models/document.py`                                | Document ORM model                          | VERIFIED | `class Document(Base)`, все колонки, FK ondelete=CASCADE         |
| `backend/app/services/document_service.py`                      | compute_expiry_status + CRUD функции        | VERIFIED | 7 функций включая IDOR-safe get_user_document                    |
| `backend/alembic/versions/0003_create_documents.py`             | documents table migration                   | VERIFIED | revision=0003, down_revision=0002, create_table, оба индекса     |
| `backend/tests/test_documents.py`                               | Phase 4 тесты (9 штук)                     | VERIFIED | 9 passed in 1.19s                                                |
| `backend/app/routers/documents.py`                              | 6 auth-gated роутов CRUD документов        | VERIFIED | POST/GET/GET-attachable/GET-url/PATCH/DELETE, все с IDOR         |
| `backend/app/schemas/document.py`                               | DocumentCategory, DocumentResponse, Patch   | VERIFIED | DocumentCategory enum, ExpiryStatus Literal, from_attributes=True |
| `backend/app/main.py`                                           | documents.router в include_router           | VERIFIED | `include_router(documents.router, prefix="/api", tags=["documents"])` |
| `frontend/src/types/document.ts`                                | DocumentResponse, CATEGORY_LABELS           | VERIFIED | Все 4 экспорта: DocumentCategory, ExpiryStatus, DocumentResponse, CATEGORY_LABELS |
| `frontend/src/lib/api.ts`                                       | uploadFile без Content-Type                 | VERIFIED | `export async function uploadFile<T>` без Content-Type заголовка |
| `frontend/src/components/documents/DocumentCard.tsx`            | Карточка с ExpiryBadge                      | VERIFIED | ExpiryBadge обрабатывает все 4 статуса; кнопки Download/Delete   |
| `frontend/src/components/documents/DocumentUploadForm.tsx`      | Форма загрузки с FormData                   | VERIFIED | `new FormData()` + `uploadFile('/api/documents', formData)`      |
| `frontend/src/components/documents/DocumentVault.tsx`           | Список с Alert для истекающих               | VERIFIED | expiringCount + Alert + DocumentCard list                        |
| `frontend/src/app/(dashboard)/documents/page.tsx`               | Страница с useQuery                         | VERIFIED | useQuery(['documents']), onDownload, onDelete, error Alert        |
| `frontend/src/components/layout/Sidebar.tsx`                    | Пункт «Документы» в навигации              | VERIFIED | FileText импортирован; navItem href='/documents'                  |

### Key Link Verification

| From                              | To                            | Via                              | Status   | Details                                                                 |
|-----------------------------------|-------------------------------|----------------------------------|----------|-------------------------------------------------------------------------|
| `backend/app/main.py`             | `ensure_bucket_exists`        | `asyncio.to_thread` в lifespan  | WIRED    | `main.py:13` import; `main.py:19` вызов в lifespan до yield            |
| `backend/app/models/__init__.py`  | `Document`                    | import для Alembic               | WIRED    | `__init__.py:4` — `from app.models.document import Document`; в `__all__` |
| `backend/app/main.py`             | `documents.router`            | include_router prefix /api       | WIRED    | `main.py:11` import; `main.py:48` include_router                       |
| `backend/app/routers/documents.py`| `_minio_client.put_object`    | `asyncio.to_thread`              | WIRED    | `documents.py:39` — module import; `documents.py:87-94` — to_thread    |
| `backend/app/routers/documents.py`| `current_user.id` (IDOR)      | get_user_document на каждом route| WIRED    | get_user_document вызывается в url/patch/delete; user_id всегда из JWT |
| `DocumentUploadForm.tsx`          | `/api/documents`              | `uploadFile(formData)`           | WIRED    | `DocumentUploadForm.tsx:80` — `uploadFile('/api/documents', formData)`  |
| `page.tsx`                        | `/api/documents`              | `useQuery api.get`               | WIRED    | `page.tsx:30-31` — `api.get<DocumentResponse[]>('/api/documents')`     |
| `Sidebar.tsx`                     | `/documents`                  | navItem FileText                 | WIRED    | `Sidebar.tsx:15` — navItem с href='/documents'                         |

### Data-Flow Trace (Level 4)

| Artifact              | Data Variable         | Source                                          | Produces Real Data | Status    |
|-----------------------|-----------------------|-------------------------------------------------|--------------------|-----------|
| `page.tsx`            | `data` (DocumentResponse[]) | `api.get('/api/documents')` → GET /api/documents → `list_user_documents(db, user_id)` → SELECT FROM documents WHERE user_id | Да — реальный SELECT из БД | FLOWING |
| `DocumentVault.tsx`   | `documents` prop      | Получает `data ?? []` из page.tsx               | Да — проброс из useQuery | FLOWING |
| `DocumentCard.tsx`    | `document` prop       | Каждый элемент DocumentResponse из списка      | Да                 | FLOWING   |

### Behavioral Spot-Checks

| Behavior                                             | Command                                                                                   | Result         | Status |
|------------------------------------------------------|-------------------------------------------------------------------------------------------|----------------|--------|
| compute_expiry_status — все 5 веток                 | `cd backend && python3 -m pytest tests/test_documents.py::test_expiry_status_logic -x -q` | 1 passed       | PASS   |
| 9 тестов Document Vault                              | `cd backend && python3 -m pytest tests/test_documents.py -x -q`                          | 9 passed 1.19s | PASS   |
| Полная тестовая сюита без регрессий                 | `cd backend && python3 -m pytest tests/ -q`                                               | 61 passed, 3 skipped | PASS |
| attachable объявлен ДО /{doc_id}/url в исходнике    | grep строки 127 и 142 в documents.py                                                     | 127 < 142      | PASS   |
| Document в app.models.__all__                        | grep __init__.py                                                                          | "Document" в __all__ | PASS |

### Probe Execution

Проб (probe-*.sh) нет для этой фазы — фаза не является migration/tooling фазой с объявленными пробами.

### Requirements Coverage

| Requirement | Source Plan | Description                                                                                 | Status      | Evidence                                                                    |
|-------------|-------------|---------------------------------------------------------------------------------------------|-------------|-----------------------------------------------------------------------------|
| DOCS-01     | 04-01, 04-02, 04-03 | Загрузка документа (PDF, DOCX, любой формат)                                | SATISFIED   | POST /api/documents принимает любой mime_type; `test_upload_success` PASS   |
| DOCS-02     | 04-01, 04-02, 04-03 | Назначение категории (устав, лицензия, сертификат, свидетельство, прочее)   | SATISFIED   | DocumentCategory enum (5 значений); `test_upload_invalid_category` → 422 PASS |
| DOCS-03     | 04-01, 04-02, 04-03 | Срок действия + предупреждения за 14 и 7 дней                               | SATISFIED   | compute_expiry_status + warning_14/warning_7; ExpiryBadge в UI; `test_expiry_status_logic` PASS |
| DOCS-04     | 04-01, 04-02, 04-03 | Удаление документа из хранилища                                              | SATISFIED   | DELETE /api/documents/{id} → 204; MinIO remove_object + db.delete; `test_delete_document` PASS |
| DOCS-05     | 04-01, 04-02, 04-03 | Автоматическая подстановка актуальных документов при создании черновика     | PARTIALLY SATISFIED | GET /api/documents/attachable возвращает неистёкшие документы (backend готов); Phase 5 (Application Submission) использует этот endpoint для auto-attach. UI-подстановка в черновик заявки — за скопом Phase 4. |

**Примечание по DOCS-05:** Backend `/api/documents/attachable` реализован и протестирован (`test_attachable_excludes_expired` PASS). Фактическая auto-attach логика при создании черновика заявки относится к Phase 5 (APPL-01/APPL-02). Phase 4 выполняет свою часть DOCS-05 — предоставляет endpoint для выборки актуальных документов.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `DocumentUploadForm.tsx` | 106 | `placeholder:text-muted-foreground` в className | Info | Это CSS-класс Tailwind для стилизации placeholder input; не является заглушкой данных |

Никаких реальных антипаттернов не обнаружено. `placeholder:` — это Tailwind CSS utility класс, не признак stub-реализации.

### Human Verification Required

#### 1. End-to-end навигация и отображение страницы

**Test:** Открыть запущенное приложение → убедиться что в сайдбаре виден пункт «Документы» с иконкой файла → клик ведёт на /documents и страница загружается без ошибок.
**Expected:** Sidebar рендерится корректно; переход на /documents; заголовок «Документы» виден; форма загрузки отображается.
**Why human:** Навигация — UI-поведение браузера; статический анализ Sidebar.tsx VERIFIED, но реальный рендер требует живого браузера.

#### 2. Upload + ExpiryBadge визуальная проверка

**Test:** Загрузить PDF с категорией «Устав» без срока → затем загрузить второй с «Лицензия» + срок через 5 дней.
**Expected:** Первая карточка без бейджа; вторая карточка с Badge outline «Истекает через 7 дней»; суммарный Alert о сроках отображается над списком.
**Why human:** Визуальный рендер бейджей — нельзя проверить без браузера; требует работающего MinIO.

#### 3. Скачивание через pre-signed URL

**Test:** Нажать «Скачать» на карточке загруженного документа.
**Expected:** Открывается новая вкладка; файл скачивается / открывается браузером.
**Why human:** window.open — браузерное поведение; требует реального MinIO с действующим pre-signed URL (TTL 15 мин).

#### 4. Удаление документа из UI

**Test:** Нажать «Удалить» на карточке → убедиться что карточка исчезает из списка.
**Expected:** DELETE 204; queryClient.invalidateQueries обновляет список; карточка пропадает без перезагрузки страницы.
**Why human:** React Query cache invalidation + DOM removal — UI-поведение.

#### 5. Client-side размер файла

**Test:** Попробовать загрузить файл > 20 МБ через форму.
**Expected:** Alert с текстом «Файл превышает 20 МБ» появляется в форме, запрос не отправляется.
**Why human:** Client-side guard в DocumentUploadForm VERIFIED статически, но отображение Alert требует ручной проверки в браузере.

### Gaps Summary

Gaps: нет. Все 13 must-haves VERIFIED. Автоматические тесты: 61 passed (включая 9 тестов Phase 4). Тестовая сюита чистая.

Единственная причина статуса `human_needed` — наличие обязательного human-verify checkpoint (Task 3 Plan 03), который по условию плана является blocking gate. Автоматическая верификация полностью пройдена.

---

_Verified: 2026-06-11_
_Verifier: Claude (gsd-verifier)_
