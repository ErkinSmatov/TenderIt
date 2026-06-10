# Phase 4 — Document Vault: Discussion Context

**Created:** 2026-06-11  
**Status:** Ready for planning  
**Requirements covered:** DOCS-01, DOCS-02, DOCS-03, DOCS-04, DOCS-05

---

## Summary

Phase 4 даёт пользователю хранилище документов компании на MinIO. Загрузка через
multipart upload на бэкенд → стриминг в MinIO → метаданные в PostgreSQL.
Доступ к файлам — через pre-signed URL (15 мин, генерирует бэкенд).
Предупреждения об истечении — UI-уровень (бейджи на странице документов).
DOCS-05 (авто-подстановка) реализуется как GET /api/documents/attachable — Phase 5
вызывает его при создании черновика заявки.

---

## Decisions

### 1. MinIO-библиотека и инициализация

**Решение:** `minio` (официальная Python-библиотека) обёрнутая через `asyncio.to_thread()`.

**Почему не `aioboto3`:**  
`config.py` уже хранит `minio_endpoint = "localhost:9000"` без схемы — это формат
minio-клиента. Переход на boto3 потребовал бы переформатирования endpoint в URL.
`minio` проще, нативно поддерживает pre-signed URL без лишней конфигурации.

**Инициализация бакета:**  
В `lifespan`-контексте `main.py` при старте приложения:

```python
from app.services.minio_service import ensure_bucket_exists

@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(ensure_bucket_exists)
    yield
    await engine.dispose()
```

Функция `ensure_bucket_exists` проверяет `bucket_exists("tenderit-documents")`,
создаёт если нет. Идемпотентна — безопасна при повторных стартах.

**Bucket name:** `tenderit-documents` (единственный бакет в v1).

**Object key:** `documents/{user_id}/{uuid4}{ext}` — изолирует файлы по пользователям,
исключает коллизии при параллельных загрузках.

---

### 2. Категории документов

**Решение:** 5 фиксированных значений из DOCS-02, хранятся как `TEXT` (не PG ENUM type).

| Slug | Русское название |
|------|----------------|
| `ustav` | Устав |
| `license` | Лицензия |
| `certificate` | Сертификат |
| `registration` | Свидетельство о регистрации |
| `other` | Прочее |

**Почему `TEXT`, а не `ENUM`:**  
PostgreSQL ENUM requires migration to add values. TEXT даёт такую же валидацию
через Pydantic `Literal` / enum и не требует ALTER TYPE при добавлении категорий в v2.

**Pydantic схема:**

```python
from enum import Enum

class DocumentCategory(str, Enum):
    USTAV = "ustav"
    LICENSE = "license"
    CERTIFICATE = "certificate"
    REGISTRATION = "registration"
    OTHER = "other"
```

**Phase 5 use-case:** при создании черновика заявки Phase 5 вызывает
`GET /api/documents/attachable` — возвращает все не-истёкшие документы пользователя,
сгруппированные по категории. Phase 5 может фильтровать по нужным категориям.

---

### 3. Ограничение размера файла

**Решение:** 20 МБ максимум на один файл.

**Валидация:** на бэкенде, до отправки в MinIO:
- Читаем `Content-Length` заголовок (FastAPI `UploadFile` + `max_size` guard)
- Если больше 20 MB → HTTP 413 с понятным сообщением
- Frontend показывает ошибку через `Alert`

**Принятые форматы (MIME-whitelist):**
Не ограничиваем — DOCS-01 говорит "любой формат". Принимаем всё, что присылает
браузер. Фактически будет PDF/DOCX/PNG — не нужно ограничивать на уровне MIME.

---

### 4. Доступ к файлам (Pre-signed URL)

**Решение:** Backend генерирует временный URL от MinIO (TTL = 15 минут).

**Флоу скачивания:**
```
GET /api/documents/{id}/url  →  {url: "http://minio:9000/tenderit-documents/documents/42/uuid.pdf?X-Amz-..."}
```

1. Backend проверяет: `document.user_id == current_user.id` (IDOR-защита)
2. Вызывает `minio.presigned_get_object(...)` с `expires=timedelta(minutes=15)`
3. Возвращает `{"url": "...", "expires_in": 900}`
4. Frontend открывает URL в новой вкладке или инициирует download

**MinIO остаётся приватным** — никаких публичных бакетов, прямых URL без подписи.

---

### 5. База данных

**Таблица `documents`:**

```sql
documents
  id            SERIAL PRIMARY KEY
  user_id       INT NOT NULL REFERENCES users(id) ON DELETE CASCADE
  file_name     VARCHAR(500) NOT NULL       -- оригинальное имя файла (для отображения)
  file_key      VARCHAR(1000) NOT NULL      -- MinIO object key: "documents/{user_id}/{uuid}.ext"
  file_size     INT NOT NULL                -- байты
  mime_type     VARCHAR(200) NOT NULL
  category      VARCHAR(50) NOT NULL        -- DocumentCategory enum slug
  expires_at    TIMESTAMPTZ                 -- nullable; NULL = бессрочный
  uploaded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
```

**Удаление:** жёсткое (hard delete). Удаляем объект из MinIO + строку из БД.
Phase 5 при добавлении FK на `application_documents.document_id` добавит CASCADE или
soft-delete по необходимости — это вне скопа Phase 4.

**Индексы:**
- `user_id` — для `GET /api/documents`
- `(user_id, expires_at)` — для запроса истекающих документов

---

### 6. Предупреждения об истечении (DOCS-03)

**Решение:** UI-уровень, запрос на бэкенде, без ARQ-задач.

**Логика:** при `GET /api/documents` бэкенд добавляет поле `expiry_status`:
- `"ok"` — не истекает или expires_at IS NULL
- `"warning_14"` — истекает через 8–14 дней
- `"warning_7"` — истекает через 1–7 дней
- `"expired"` — expires_at < now()

Frontend рендерит бейджи/алерты по `expiry_status`.

**Почему не ARQ push-уведомления в Phase 4:**  
Phase 6 (Notifications) — правильное место для Telegram/WhatsApp алертов об
истечении. Phase 4 обеспечивает визуальное предупреждение в UI.

---

### 7. DOCS-05 — Авто-подстановка (заглушка для Phase 5)

**Реализация в Phase 4:** endpoint `GET /api/documents/attachable`.

```python
# Возвращает документы пользователя: не истёкшие + expires_at IS NULL
# Используется Phase 5 при создании черновика заявки
```

Возвращает `List[DocumentResponse]` — только документы, которые можно подставить
(expires_at IS NULL OR expires_at > now()). Phase 5 вызывает этот endpoint и
включает все возвращённые документы в черновик заявки.

**Бизнес-правило:** документ с `expiry_status == "expired"` НЕ включается в авто-подстановку, но остаётся в хранилище (пользователь видит его с бейджем "Истёк").

---

### 8. API-маршруты Phase 4

| Метод | Путь | Назначение |
|-------|------|-----------|
| `POST` | `/api/documents` | Загрузить документ (multipart/form-data) |
| `GET` | `/api/documents` | Список всех документов пользователя |
| `GET` | `/api/documents/attachable` | Список не-истёкших (для Phase 5) |
| `GET` | `/api/documents/{id}/url` | Pre-signed URL для скачивания |
| `PATCH` | `/api/documents/{id}` | Обновить category / expires_at |
| `DELETE` | `/api/documents/{id}` | Удалить документ + файл из MinIO |

---

### 9. Фронтенд

**Новая страница:** `/documents` в `(dashboard)` layout.

**Компоненты:**
- `DocumentUploadForm` — dropzone + поля category/expires_at + кнопка загрузки
- `DocumentCard` — карточка с именем файла, категорией, датой, бейджем истечения + скачать/удалить
- `DocumentVault` — список карточек + суммарный алерт если есть истекающие

**Навигация:** добавить "Документы" в `Sidebar.tsx` (иконка `FileText` из lucide).

---

## Wave Plan

| Wave | Содержание | Gate |
|------|-----------|------|
| Wave 0 | `minio_service.py` + `ensure_bucket_exists` + lifespan hook + `Document` ORM + Alembic migration 0003 | MinIO локально запущен |
| Wave 1 | Backend routes: upload, list, attachable, url, patch, delete + Pydantic schemas + unit tests | После Wave 0 |
| Wave 2 | Frontend: `/documents` страница + DocumentUploadForm + DocumentCard + expiry badges | После Wave 1 |
| Wave 3 | Sidebar nav link + интеграционный тест end-to-end | После Wave 2 |

---

## Паттерны из предыдущих фаз

- SQLAlchemy 2.x async + `asyncio.to_thread()` для синхронного minio-клиента
- Alembic: `backend/alembic/versions/0003_create_documents.py`
- `models/__init__.py` должен импортировать `Document` (без этого Alembic не видит модель)
- `get_current_user` из `deps.py` на всех роутах — `user_id` ВСЕГДА из JWT
- Pydantic схемы в `backend/app/schemas/documents.py`
- `asyncio.to_thread()` аналогично тому, как `goszakup_service.py` обёртывает httpx (async I/O)
- React Hook Form + shadcn `Input/Button/Card/Alert` — паттерн из `CompanyProfileForm`
- `api.ts` уже имеет `apiFetch` — для multipart нужен отдельный хелпер без `Content-Type: application/json`

---

## Ограничения и не-цели Phase 4

**В Phase 4:**
- Загрузка, просмотр, редактирование метаданных, удаление документов
- Предупреждения об истечении в UI (бейджи)
- Endpoint `/api/documents/attachable` для Phase 5

**Не в Phase 4 (Phase 5+):**
- Привязка документов к конкретной заявке
- ARQ-задача для push-уведомлений об истечении документов (Phase 6)
- Версионирование документов (v2)
- Bulk upload (v2)
