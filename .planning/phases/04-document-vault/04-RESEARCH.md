# Phase 4: Document Vault — Research

**Researched:** 2026-06-11
**Domain:** MinIO Python SDK, FastAPI multipart upload, SQLAlchemy 2.x async, Next.js file input
**Confidence:** HIGH (все ключевые API верифицированы через inspect на установленных пакетах)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

1. **MinIO-библиотека:** `minio` (официальная) + `asyncio.to_thread()` — НЕ aioboto3
2. **Инициализация бакета:** в `lifespan` FastAPI через `ensure_bucket_exists()`
3. **Имя бакета:** `tenderit-documents`
4. **Object key:** `documents/{user_id}/{uuid4}{ext}`
5. **Категории (5 фиксированных):** ustav, license, certificate, registration, other — хранятся как TEXT
6. **Лимит файла:** 20 МБ, валидация на бэкенде до MinIO upload
7. **Доступ:** pre-signed URL (TTL 15 мин), MinIO остаётся приватным
8. **Удаление:** hard delete (MinIO объект + строка БД)
9. **Предупреждения об истечении:** UI-уровень, поле `expiry_status` в API-ответе
10. **DOCS-05:** GET /api/documents/attachable — заглушка для Phase 5

### DB Schema (locked)
```
documents
  id SERIAL PRIMARY KEY
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE
  file_name VARCHAR(500) NOT NULL
  file_key VARCHAR(1000) NOT NULL
  file_size INT NOT NULL
  mime_type VARCHAR(200) NOT NULL
  category VARCHAR(50) NOT NULL
  expires_at TIMESTAMPTZ (nullable)
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

### API Routes (locked)
| Метод | Путь |
|-------|------|
| POST | /api/documents |
| GET | /api/documents |
| GET | /api/documents/attachable |
| GET | /api/documents/{id}/url |
| PATCH | /api/documents/{id} |
| DELETE | /api/documents/{id} |

### Deferred Ideas (OUT OF SCOPE)

- Привязка документов к конкретной заявке (Phase 5)
- ARQ push-уведомления об истечении (Phase 6)
- Версионирование документов (v2)
- Bulk upload (v2)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Описание | Research Support |
|----|----------|-----------------|
| DOCS-01 | Загрузка документа компании (любой формат) | FastAPI UploadFile + minio.put_object() — паттерн верифицирован |
| DOCS-02 | Категоризация документа (5 фиксированных категорий) | Pydantic str.Enum + TEXT колонка — паттерн из codebase |
| DOCS-03 | Срок действия + предупреждение за 14 и 7 дней | `expiry_status` вычисляется в сервисном слое сравнением с `datetime.now(UTC)` |
| DOCS-04 | Удаление документа | `minio.remove_object()` + DELETE SQL — API верифицирован |
| DOCS-05 | Авто-подстановка актуальных документов при создании заявки | GET /api/documents/attachable — фильтр `expires_at IS NULL OR expires_at > now()` |
</phase_requirements>

---

## Summary

Phase 4 строит хранилище документов поверх MinIO с метаданными в PostgreSQL. Все ключевые API верифицированы на установленных пакетах.

**Критическая находка #1:** `minio` **отсутствует в `pyproject.toml`**. Его нужно добавить явно (`minio>=7.2.14`). Текущая последняя версия на PyPI — 7.2.20. [VERIFIED: PyPI + pip show]

**Критическая находка #2:** `python-multipart` **отсутствует в `pyproject.toml`**. FastAPI требует его для парсинга `multipart/form-data`. Starlette делает явный `assert multipart is not None` при попытке парсить форму — без него POST /api/documents упадёт с 500. [VERIFIED: starlette source]

**Критическая находка #3:** `UploadFile.size` надёжно заполняется стартовым Starlette-парсером multipart ещё до вызова обработчика. Можно проверять `file.size > 20MB` без чтения файла. Starlette ищет файл к позиции 0 после записи — `file.file` (SpooledTemporaryFile) готов к чтению. [VERIFIED: starlette 0.41.3 source]

**Критическая находка #4:** `minio.put_object()` принимает `length=-1` с обязательным `part_size >= 5MB` для неизвестного размера, либо `length=file.size` когда размер известен. Для нашего случая (знаем `file.size`) — используем `length=file.size`. [VERIFIED: minio 7.2.14 source + get_part_info()]

**Primary recommendation:** Создать `app/services/minio_service.py` с одним глобальным `Minio` клиентом, инициализированным при старте. Все вызовы MinIO оборачивать через `asyncio.to_thread()`. Валидацию размера делать через `file.size` в обработчике.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Хранение файлов | MinIO (Storage) | — | Бинарные данные не хранятся в PG |
| Метаданные документа | Database/PostgreSQL | — | Структурированные данные, нужны запросы |
| Загрузка файла | API/Backend | Browser | Браузер → multipart → FastAPI → MinIO |
| Pre-signed URL | API/Backend | MinIO | Backend генерирует, MinIO подписывает |
| Валидация размера | API/Backend | — | Security — клиент не доверяется |
| expiry_status | API/Backend | — | Вычисляется в service layer, а не в БД |
| UI-бейджи истечения | Browser/Client | — | Рендеринг по полю из API |
| Навигация (Sidebar) | Browser/Client | — | Клиентский компонент |

---

## Standard Stack

### Core

| Библиотека | Версия | Назначение | Примечание |
|-----------|--------|-----------|-----------|
| `minio` | 7.2.20 | MinIO Python SDK — upload, presign, delete | **Добавить в pyproject.toml** [VERIFIED: PyPI] |
| `python-multipart` | latest | Парсинг multipart/form-data в FastAPI | **Добавить в pyproject.toml** [VERIFIED: starlette source] |

Все остальные зависимости уже в `pyproject.toml`: `fastapi`, `sqlalchemy`, `alembic`, `asyncpg`, `pydantic`.

**Установка:**
```bash
# backend/pyproject.toml — добавить в dependencies:
"minio>=7.2.14",
"python-multipart>=0.0.9",
```

**Версии (верифицированы):**
- `minio`: 7.2.14 установлен глобально; PyPI latest — 7.2.20 [VERIFIED: npm view / pip show / PyPI]
- `python-multipart`: не установлен; FastAPI рекомендует `>=0.0.9` [CITED: fastapi docs]

---

## Architecture Patterns

### System Architecture Diagram

```
Browser                     FastAPI Backend               MinIO / PostgreSQL
─────────                   ──────────────               ─────────────────────
POST multipart/form-data ──► auth (JWT cookie)
                             │
                             ▼
                          UploadFile.size check
                          (> 20MB → 413)
                             │
                             ▼
                          asyncio.to_thread(
                            minio.put_object(
                              BUCKET, key, file.file, file.size
                            )
                          )                     ──────────► MinIO: store object
                             │
                             ▼
                          INSERT INTO documents  ──────────► PostgreSQL: store metadata
                             │
                             ▼
                          DocumentResponse ◄─────────────── return to browser

GET /api/documents/{id}/url
                         ──► auth + IDOR check (document.user_id == current_user.id)
                             │
                             ▼
                          asyncio.to_thread(
                            minio.presigned_get_object(
                              BUCKET, key, expires=timedelta(minutes=15)
                            )
                          )
                             │
                             ▼
                          {"url": "...", "expires_in": 900} ──► browser opens URL

DELETE /api/documents/{id}
                         ──► auth + IDOR check
                             │
                             ├── asyncio.to_thread(minio.remove_object(BUCKET, key))
                             │
                             └── DELETE FROM documents WHERE id=? AND user_id=?
```

### Recommended Project Structure

```
backend/app/
├── models/
│   ├── __init__.py          # добавить: from app.models.document import Document
│   └── document.py          # новый ORM-класс Document
├── schemas/
│   └── document.py          # новый: DocumentCategory, DocumentResponse, etc.
├── services/
│   └── minio_service.py     # новый: Minio client + ensure_bucket_exists + helpers
├── routers/
│   └── documents.py         # новый: все 6 маршрутов
└── main.py                  # добавить: ensure_bucket_exists в lifespan + include_router

backend/alembic/versions/
└── 0003_create_documents.py # новая Alembic-миграция

frontend/src/
├── app/(dashboard)/
│   └── documents/
│       └── page.tsx         # новая страница /documents
├── components/
│   └── documents/
│       ├── DocumentUploadForm.tsx
│       ├── DocumentCard.tsx
│       └── DocumentVault.tsx
└── components/layout/
    └── Sidebar.tsx           # добавить "Документы" + FileText иконку
```

### Pattern 1: MinIO Client (Singleton)

**Что:** Единственный экземпляр `Minio` создаётся при импорте модуля. Безопасен для передачи между потоками через `asyncio.to_thread()` — `urllib3.PoolManager` thread-safe, словарные операции в `_region_map` защищены GIL CPython. [VERIFIED: minio + urllib3 source]

```python
# backend/app/services/minio_service.py
from minio import Minio
from app.config import settings

# Singleton — создаётся один раз при импорте модуля
_minio_client = Minio(
    endpoint=settings.minio_endpoint,     # "localhost:9000" (без схемы)
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=False,                          # HTTP для local dev; True в production
)

BUCKET_NAME = "tenderit-documents"


def ensure_bucket_exists() -> None:
    """Идемпотентная инициализация бакета. Вызывается из lifespan."""
    if not _minio_client.bucket_exists(BUCKET_NAME):
        _minio_client.make_bucket(BUCKET_NAME)
```

### Pattern 2: Lifespan Integration

```python
# backend/app/main.py — добавить в lifespan
import asyncio
from app.services.minio_service import ensure_bucket_exists

@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(ensure_bucket_exists)
    yield
    await engine.dispose()
```

### Pattern 3: Upload Handler

**Критично:** `UploadFile.size` доступен до вызова `file.read()`. `file.file` (SpooledTemporaryFile) позиционирован на 0 стартовым парсером. [VERIFIED: starlette 0.41.3 source]

```python
# Source: starlette 0.41.3 source + minio 7.2.14 source (verified)
import asyncio
import uuid
import os
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from app.services.minio_service import _minio_client, BUCKET_NAME

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

@router.post("/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    category: DocumentCategory = Form(...),
    expires_at: datetime | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    # Валидация размера — ДО чтения файла, .size заполнен starlette
    if file.size is not None and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Файл превышает 20 МБ")

    ext = os.path.splitext(file.filename or "")[1].lower()
    object_key = f"documents/{current_user.id}/{uuid.uuid4()}{ext}"

    # asyncio.to_thread — синхронный MinIO SDK в пуле потоков
    # file.file — SpooledTemporaryFile, уже на позиции 0 (starlette seeked)
    await asyncio.to_thread(
        _minio_client.put_object,
        BUCKET_NAME,
        object_key,
        file.file,                                         # BinaryIO, seeked to 0
        file.size if file.size is not None else -1,       # length; -1 только если size=None
        file.content_type or "application/octet-stream",
    )
    # ... INSERT INTO documents ...
```

**Важно:** При `length=-1` (случай `file.size is None`) необходимо добавить `part_size=5*1024*1024`. Но в нашем случае `file.size` всегда будет заполнен после multipart парсинга. [VERIFIED: minio get_part_info()]

### Pattern 4: Pre-signed URL

```python
# Source: minio 7.2.14 source (verified)
from datetime import timedelta

@router.get("/documents/{doc_id}/url")
async def get_document_url(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    doc = await db.get(Document, doc_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Документ не найден")

    url: str = await asyncio.to_thread(
        _minio_client.presigned_get_object,
        BUCKET_NAME,
        doc.file_key,
        timedelta(minutes=15),   # expires parameter
    )
    return {"url": url, "expires_in": 900}
```

### Pattern 5: Delete (MinIO + DB)

```python
# Source: minio 7.2.14 source (verified)
@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    doc = await db.get(Document, doc_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Документ не найден")

    # Сначала MinIO, потом БД
    await asyncio.to_thread(_minio_client.remove_object, BUCKET_NAME, doc.file_key)
    await db.delete(doc)
    await db.commit()
    return Response(status_code=204)
```

### Pattern 6: expiry_status в Service Layer

**Решение: сервисный слой**, а не SQLAlchemy hybrid_property. Причины:
- `hybrid_property` для вычислений с `datetime.now()` плохо работает с async SQLAlchemy (требует синхронного контекста)
- Pydantic `@computed_field` или `@model_validator` удобнее, но нужен `now()` в момент сериализации
- Чище всего: функция в `document_service.py` добавляет `expiry_status` к объекту

```python
# backend/app/services/document_service.py
from datetime import datetime, timezone, timedelta
from typing import Literal

ExpiryStatus = Literal["ok", "warning_14", "warning_7", "expired"]

def compute_expiry_status(expires_at: datetime | None) -> ExpiryStatus:
    """Вычислить статус срока действия документа.

    ok         — expires_at IS NULL или истекает > 14 дней
    warning_14 — истекает через 8–14 дней
    warning_7  — истекает через 1–7 дней
    expired    — expires_at < now()
    """
    if expires_at is None:
        return "ok"
    now = datetime.now(timezone.utc)
    delta = expires_at - now
    days = delta.days
    if days < 0:
        return "expired"
    if days <= 7:
        return "warning_7"
    if days <= 14:
        return "warning_14"
    return "ok"
```

Pydantic-схема включает `expiry_status` как обычное поле — сервис добавляет его перед возвратом:

```python
class DocumentResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    file_name: str
    file_key: str
    file_size: int
    mime_type: str
    category: DocumentCategory
    expires_at: datetime | None
    uploaded_at: datetime
    expiry_status: ExpiryStatus  # добавляется в сервисном слое
```

### Pattern 7: ORM Model

```python
# backend/app/models/document.py
from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=False)
    mime_type: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
```

### Pattern 8: Alembic Migration 0003

Формат из codebase: `0002` использует `revision: str = "0002"`. Migration 0003 следует тому же паттерну.

```python
# backend/alembic/versions/0003_create_documents.py
"""create_documents

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-11
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("file_key", sa.String(1000), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("uploaded_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_user_id", "documents", ["user_id"])
    op.create_index("ix_documents_user_expires", "documents", ["user_id", "expires_at"])

def downgrade() -> None:
    op.drop_index("ix_documents_user_expires", "documents")
    op.drop_index("ix_documents_user_id", "documents")
    op.drop_table("documents")
```

### Pattern 9: Frontend — multipart upload без apiFetch

**Критично:** `apiFetch` принудительно выставляет `Content-Type: application/json`. Для `FormData` нужен отдельный хелпер без этого заголовка — браузер сам выставит `multipart/form-data; boundary=...`. [VERIFIED: api.ts source]

```typescript
// frontend/src/lib/api.ts — добавить отдельную функцию
export async function uploadFile<T>(path: string, formData: FormData): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    // НЕ выставляем Content-Type — браузер добавит boundary автоматически
    body: formData,
  })
  if (res.status === 401) {
    // silent refresh + retry (аналогично apiFetch)
    const refreshed = await fetch(`${BASE}/api/auth/refresh`, { method: 'POST', credentials: 'include' })
    if (!refreshed.ok) { useAuthStore.getState().clearAuth(); throw new Error('Session expired') }
    return uploadFile<T>(path, formData)
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Upload error')
  }
  return res.json() as Promise<T>
}
```

### Pattern 10: Sidebar — добавление "Документы"

```typescript
// frontend/src/components/layout/Sidebar.tsx — изменить navItems
import { LayoutDashboard, Search, Building2, FileText, LogOut } from 'lucide-react'

const navItems = [
  { href: '/dashboard', label: 'Обзор', icon: LayoutDashboard },
  { href: '/tenders', label: 'Тендеры', icon: Search },
  { href: '/profile', label: 'Профиль', icon: Building2 },
  { href: '/documents', label: 'Документы', icon: FileText },  // добавить
]
```

### Pattern 11: DocumentCard с Badge

```typescript
// shadcn Badge компонент уже есть в /components/ui/badge.tsx
// Variants: default, secondary, destructive, outline, ghost, link
// [VERIFIED: badge.tsx source]

import { Badge } from '@/components/ui/badge'

function ExpiryBadge({ status }: { status: ExpiryStatus }) {
  if (status === 'ok') return null
  const config = {
    warning_14: { variant: 'secondary' as const, label: 'Истекает через 14 дней' },
    warning_7:  { variant: 'outline' as const,   label: 'Истекает через 7 дней' },
    expired:    { variant: 'destructive' as const, label: 'Истёк' },
  }
  const { variant, label } = config[status]
  return <Badge variant={variant}>{label}</Badge>
}
```

### Anti-Patterns to Avoid

- **Не передавать `user_id` из тела запроса.** user_id ВСЕГДА из `get_current_user`. Обход через query param тоже запрещён.
- **Не создавать Minio() внутри каждой функции.** Это дорогостоящий объект с connection pool. Singleton при старте.
- **Не использовать `length=-1` без `part_size`.** Вызовет `ValueError: valid part size must be provided`. [VERIFIED: get_part_info source]
- **Не ставить `Content-Type: multipart/form-data` вручную.** Браузер должен добавить boundary — без него парсер упадёт.
- **Не удалять строку из БД до удаления из MinIO.** Если MinIO упадёт после удаления строки — файл-сирота. Порядок: MinIO → БД.
- **Не делать pre-signed URL с долгим TTL.** 15 минут — как решено в CONTEXT.md. Длинный TTL — security risk.
- **Не загружать весь файл в память через `file.read()` перед передачей в MinIO.** Передавать `file.file` (SpooledTemporaryFile) напрямую — MinIO SDK читает его потоково.

---

## Don't Hand-Roll

| Проблема | Не строить | Использовать | Почему |
|----------|-----------|-------------|--------|
| Pre-signed URL с HMAC подписью | Собственный подписчик URL | `minio.presigned_get_object()` | Сложность HMAC-SHA256 + правильный canonical form |
| Streaming upload в object storage | Buffered BytesIO | `minio.put_object(file.file, length)` | SDK сам управляет multipart, чанками, retry |
| MIME detection | python-magic / вручную | Принимать `file.content_type` из браузера | DOCS-01 не ограничивает форматы; v1 MVP |
| UUID generation | `random` или `time()` | `uuid.uuid4()` | Collision-free, cryptographically random |
| expiry_status в PG GENERATED COLUMN | `GENERATED ALWAYS AS ...` | Python вычисление в сервисе | Нельзя использовать `now()` в PG generated columns стабильно |

---

## Common Pitfalls

### Pitfall 1: python-multipart отсутствует в зависимостях

**Что ломается:** `POST /api/documents` возвращает 500 с `AssertionError: The python-multipart library must be installed`.
**Почему:** FastAPI/Starlette требует `python-multipart` для парсинга `UploadFile`. Он не включён в `fastapi` как обязательная зависимость.
**Как избежать:** Добавить `"python-multipart>=0.0.9"` в `pyproject.toml` в Wave 0.
**Warning sign:** `AssertionError` в логах на первом же тестовом запросе.

### Pitfall 2: minio client с `secure=True` на localhost

**Что ломается:** Все запросы к MinIO падают с SSL error на `localhost:9000`.
**Почему:** По умолчанию `secure=True` в Minio(). Локальный MinIO в docker-compose работает на HTTP.
**Как избежать:** `Minio(..., secure=False)` в dev. В production — `secure=True` + реальный TLS.
**Предложение:** добавить `minio_secure: bool = False` в `Settings`.

### Pitfall 3: IDOR — document.user_id не проверяется

**Что ломается:** Пользователь A получает/удаляет/скачивает документы пользователя B.
**Почему:** Простой `await db.get(Document, doc_id)` не фильтрует по `user_id`.
**Как избежать:** Каждый route возвращает 404 если `doc.user_id != current_user.id`. Используем `select(Document).where(Document.id == doc_id, Document.user_id == current_user.id)`.

### Pitfall 4: File.file position не на 0

**Что ломается:** MinIO получает 0 байт или неполный файл.
**Почему:** Если код где-то вызвал `await file.read()` ДО `put_object`, позиция смещается.
**Как избежать:** Передавать `file.file` напрямую в `put_object` без промежуточного `read()`. Если нужно прочитать для валидации — сделать `await file.seek(0)` после.

### Pitfall 5: Удаление из MinIO после удаления строки в БД

**Что ломается:** При сбое MinIO-вызова файл остаётся в MinIO навсегда (нет ссылки для очистки).
**Как избежать:** Всегда: сначала `remove_object()`, потом `db.delete()` + `db.commit()`.

### Pitfall 6: Document не импортирован в models/__init__.py

**Что ломается:** Alembic autogenerate не видит модель Document, migration не создаётся.
**Как избежать:** Добавить `from app.models.document import Document` в `models/__init__.py` в Wave 0.

### Pitfall 7: expires_at timezone-naive datetime

**Что ломается:** Сравнение `expires_at < datetime.now()` даёт TypeError в Python 3.12 (можно сравнивать только tz-aware с tz-aware).
**Как избежать:** В `compute_expiry_status` использовать `datetime.now(timezone.utc)`. В Pydantic-схеме `expires_at: datetime | None` при `from_attributes=True` вернёт tz-aware datetime из `TIMESTAMPTZ` колонки PostgreSQL.

---

## Runtime State Inventory

Фаза 4 — greenfield (новые таблицы и объекты MinIO). Не переименование.

**Nothing found in any category** — verified: нет существующих данных в `documents` таблице (таблица ещё не создана), нет MinIO объектов в `tenderit-documents` бакете (бакет ещё не создан).

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| MinIO (docker) | File storage | ✗ (не запущен) | — | docker compose up minio |
| PostgreSQL | DB | ✗ (не запущен) | — | docker compose up postgres |
| Python `minio` lib | minio_service.py | ✓ (глобально) | 7.2.14 | — |
| Python `python-multipart` | FastAPI forms | ✗ | — | Добавить в pyproject.toml |
| `pytest`, `pytest-asyncio` | Tests | ✓ | 9.0.3 / 1.3.0 | — |

**Missing dependencies with no fallback:**
- `python-multipart` — нужно добавить в `pyproject.toml` (Wave 0)
- MinIO сервис — нужен `docker compose up minio` перед тестами

**Missing dependencies with fallback:**
- `minio` Python lib — 7.2.14 глобально, но проект использует pip install; добавить `minio>=7.2.14` в pyproject.toml

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| Config file | `backend/pytest.ini` (asyncio_mode = auto) |
| Quick run | `cd backend && pytest tests/test_documents.py -x` |
| Full suite | `cd backend && pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behaviour | Test Type | Automated Command | File |
|--------|-----------|-----------|-------------------|------|
| DOCS-01 | Upload file → 201, DB record created, MinIO put called | unit (mock MinIO) | `pytest tests/test_documents.py::test_upload_success -x` | ❌ Wave 0 |
| DOCS-01 | Upload > 20MB → 413 | unit (mock MinIO) | `pytest tests/test_documents.py::test_upload_too_large -x` | ❌ Wave 0 |
| DOCS-02 | Upload with invalid category → 422 | unit | `pytest tests/test_documents.py::test_upload_invalid_category -x` | ❌ Wave 0 |
| DOCS-03 | GET /api/documents returns expiry_status correctly | unit | `pytest tests/test_documents.py::test_expiry_status_logic -x` | ❌ Wave 0 |
| DOCS-04 | DELETE removes from DB + MinIO | unit (mock MinIO) | `pytest tests/test_documents.py::test_delete_document -x` | ❌ Wave 0 |
| DOCS-04 | DELETE другого пользователя → 404 (IDOR) | unit | `pytest tests/test_documents.py::test_delete_idor_protection -x` | ❌ Wave 0 |
| DOCS-05 | GET /attachable возвращает только не-истёкшие | unit | `pytest tests/test_documents.py::test_attachable_excludes_expired -x` | ❌ Wave 0 |
| DOCS-01 | GET /documents/{id}/url → 200 с presigned URL | unit (mock MinIO) | `pytest tests/test_documents.py::test_get_presigned_url -x` | ❌ Wave 0 |
| DOCS-01 | GET /documents/{id}/url другого пользователя → 404 (IDOR) | unit | `pytest tests/test_documents.py::test_url_idor_protection -x` | ❌ Wave 0 |

### MinIO Mock Pattern

MinIO клиент — синхронный, вызывается через `asyncio.to_thread()`. Мокировать через `unittest.mock.patch`:

```python
# Source: паттерн из test_tenders.py (respx mock) + unittest.mock
from unittest.mock import MagicMock, patch
import pytest
import io

@pytest.mark.asyncio
async def test_upload_success(authed):
    """DOCS-01: Успешная загрузка → 201, MinIO.put_object вызван."""
    mock_result = MagicMock()
    mock_result.object_name = "documents/1/test-uuid.pdf"

    with patch("app.services.minio_service._minio_client") as mock_minio:
        mock_minio.put_object.return_value = mock_result
        mock_minio.bucket_exists.return_value = True

        form_data = {"category": "ustav"}
        files = {"file": ("test.pdf", io.BytesIO(b"fake pdf content"), "application/pdf")}
        resp = await authed.post("/api/documents", data=form_data, files=files)

    assert resp.status_code == 201
    body = resp.json()
    assert body["category"] == "ustav"
    assert body["file_name"] == "test.pdf"
    mock_minio.put_object.assert_called_once()


@pytest.mark.asyncio
async def test_upload_too_large(authed):
    """DOCS-01: Файл > 20MB → 413."""
    # Симулировать файл с size > 20MB через кастомный UploadFile
    # Или через мок на file.size
    large_content = b"x" * (21 * 1024 * 1024)  # 21 MB
    form_data = {"category": "other"}
    files = {"file": ("large.pdf", io.BytesIO(large_content), "application/pdf")}

    with patch("app.services.minio_service._minio_client"):
        resp = await authed.post("/api/documents", data=form_data, files=files)

    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_expiry_status_logic():
    """DOCS-03: expiry_status вычисляется корректно — pure unit test."""
    from datetime import datetime, timezone, timedelta
    from app.services.document_service import compute_expiry_status

    now = datetime.now(timezone.utc)
    assert compute_expiry_status(None) == "ok"
    assert compute_expiry_status(now + timedelta(days=30)) == "ok"
    assert compute_expiry_status(now + timedelta(days=10)) == "warning_14"
    assert compute_expiry_status(now + timedelta(days=5)) == "warning_7"
    assert compute_expiry_status(now - timedelta(days=1)) == "expired"


@pytest.mark.asyncio
async def test_delete_idor_protection(authed, authed2):
    """DOCS-04: Пользователь A не может удалить документ пользователя B."""
    # 1. authed загружает документ
    with patch("app.services.minio_service._minio_client") as mock_minio:
        mock_minio.put_object.return_value = MagicMock()
        resp = await authed.post("/api/documents",
                                  data={"category": "other"},
                                  files={"file": ("f.pdf", io.BytesIO(b"data"), "application/pdf")})
    doc_id = resp.json()["id"]

    # 2. authed2 пытается удалить — должен получить 404
    with patch("app.services.minio_service._minio_client"):
        del_resp = await authed2.delete(f"/api/documents/{doc_id}")
    assert del_resp.status_code == 404


@pytest.mark.asyncio
async def test_attachable_excludes_expired(authed):
    """DOCS-05: GET /attachable не возвращает истёкшие документы."""
    from datetime import datetime, timezone, timedelta

    with patch("app.services.minio_service._minio_client") as mock_minio:
        mock_minio.put_object.return_value = MagicMock()
        # Загрузить истёкший документ
        expired = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        await authed.post("/api/documents",
                           data={"category": "license", "expires_at": expired},
                           files={"file": ("expired.pdf", io.BytesIO(b"data"), "application/pdf")})
        # Загрузить актуальный документ
        await authed.post("/api/documents",
                           data={"category": "ustav"},
                           files={"file": ("valid.pdf", io.BytesIO(b"data"), "application/pdf")})

    resp = await authed.get("/api/documents/attachable")
    assert resp.status_code == 200
    names = [d["file_name"] for d in resp.json()]
    assert "valid.pdf" in names
    assert "expired.pdf" not in names
```

### Sampling Rate

- **Per task commit:** `cd backend && pytest tests/test_documents.py -x`
- **Per wave merge:** `cd backend && pytest tests/ -x`
- **Phase gate:** Full suite green перед `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_documents.py` — все тесты Phase 4
- [ ] `backend/app/models/document.py` — ORM модель
- [ ] `backend/app/schemas/document.py` — Pydantic схемы
- [ ] `backend/app/services/minio_service.py` — MinIO singleton + ensure_bucket_exists
- [ ] `backend/app/services/document_service.py` — compute_expiry_status + CRUD функции
- [ ] `backend/alembic/versions/0003_create_documents.py` — migration

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | JWT cookie (get_current_user dep) — уже реализован |
| V3 Session Management | no | Не меняется в этой фазе |
| V4 Access Control | yes | IDOR-проверка: `document.user_id == current_user.id` на каждом route |
| V5 Input Validation | yes | Pydantic: category (Enum), expires_at (datetime), file.size (int) |
| V6 Cryptography | yes | MinIO pre-signed URL (HMAC-SHA256) — не hand-roll, только SDK |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| IDOR (доступ к чужим документам) | Tampering / Info Disclosure | Фильтр по `user_id` в каждом SELECT/DELETE |
| Path traversal в object_key | Tampering | uuid4 в имени ключа; оригинальное имя файла только в `file_name` колонке |
| Oversized upload (DoS) | Denial of Service | Проверка `file.size > 20MB` до MinIO upload |
| Signed URL утечка | Info Disclosure | TTL = 15 мин; MinIO приватный (нет bucket policy public) |
| Direct MinIO access | Info Disclosure | MinIO не публичный; только backend генерирует pre-signed URLs |

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|-----------------|--------|
| `aioboto3` для S3-совместимых | `minio` SDK + `asyncio.to_thread()` | Проще, нет переформатирования endpoint |
| PostgreSQL ENUM type | TEXT + Pydantic Literal/Enum | Безболезненное добавление категорий в v2 |
| `length=-1` всегда | `length=file.size` когда известен | Нет лишнего multipart overhead |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | MinIO singleton (один экземпляр на приложение) потокобезопасен в CPython из-за GIL | Patterns #1 | Если используется не CPython (Jython/PyPy без GIL), `_region_map` нужна блокировка. В CPython 3.11 GIL защищает dict операции. [ASSUMED: GIL behaviour] |
| A2 | `file.size` надёжно заполняется starlette до вызова обработчика | Patterns #3 | Если starlette изменит поведение в будущей версии — нужна fallback: `await file.seek(0, 2); size = file.tell(); await file.seek(0)`. Сейчас проверено на starlette 0.41.3. [VERIFIED] |

---

## Open Questions

1. **`minio_secure` в config.py**
   - Что знаем: текущий `Settings` не имеет `minio_secure` — hard-code `secure=False` в minio_service.py для dev
   - Что неясно: нужен ли `secure=True` в prod окружении (зависит от деплоя)
   - Рекомендация: добавить `minio_secure: bool = False` в `Settings` → `Minio(..., secure=settings.minio_secure)`

2. **Что делать при сбое MinIO во время upload (after partial write)**
   - Что знаем: minio SDK сам управляет retry на уровне TCP; если `put_object` выбрасывает исключение — файл не записан (атомично)
   - Что неясно: нужен ли cleanup на стороне приложения
   - Рекомендация: если `put_object` бросает — просто вернуть 503, никаких сирот не будет (MinIO rollbacks incomplete multipart uploads)

---

## Sources

### Primary (HIGH confidence)
- `minio` 7.2.14 source (inspect) — `put_object`, `presigned_get_object`, `remove_object`, `bucket_exists`, `make_bucket`, `Minio.__init__` signatures
- `starlette` 0.41.3 source (inspect) — `UploadFile.size` population, form parser `seek(0)`, `SpooledTemporaryFile`
- `fastapi` 0.115.6 source (inspect) — `UploadFile` class definition
- `minio.helpers.get_part_info` (inspect) — `length=-1` behavior verification
- Project codebase: `config.py`, `main.py`, `models/`, `deps.py`, `routers/tenders.py`, `tests/`, `pyproject.toml`, `docker-compose.yml`

### Secondary (MEDIUM confidence)
- PyPI JSON API — minio latest version 7.2.20

### Tertiary (LOW confidence)
- `python-multipart` required version — `>=0.0.9` [CITED: fastapi docs, not re-verified in this session]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — верифицированы через inspect + PyPI
- Architecture: HIGH — все API calls проверены на живом коде
- Pitfalls: HIGH — выявлены из source analysis, не из гипотез
- Frontend patterns: HIGH — компоненты прочитаны напрямую из codebase

**Research date:** 2026-06-11
**Valid until:** 2026-07-11 (minio SDK стабилен; starlette API стабилен в minor версиях)
