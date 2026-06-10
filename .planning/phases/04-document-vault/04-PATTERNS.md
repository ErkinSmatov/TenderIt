# Phase 4: Document Vault — Pattern Map

**Mapped:** 2026-06-11
**Files analyzed:** 11 new/modified files
**Analogs found:** 11 / 11

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/services/minio_service.py` | service | file-I/O | `backend/app/services/redis_service.py` | role-match (singleton + helper funcs) |
| `backend/app/services/document_service.py` | service | CRUD | `backend/app/services/tender_service.py` | exact (async service functions + pure utility) |
| `backend/app/models/document.py` | model | CRUD | `backend/app/models/tender.py` | exact |
| `backend/app/schemas/document.py` | schema | request-response | `backend/app/schemas/tender.py` | exact |
| `backend/app/routers/documents.py` | controller | request-response | `backend/app/routers/tenders.py` | exact (auth + IDOR + CRUD) |
| `backend/alembic/versions/0003_create_documents.py` | migration | CRUD | `backend/alembic/versions/0002_create_tenders_watchlist.py` | exact |
| `backend/app/main.py` (modify) | config | request-response | itself (lifespan hook already exists) | self-modify |
| `backend/app/models/__init__.py` (modify) | config | — | itself | self-modify |
| `frontend/src/app/(dashboard)/documents/page.tsx` | component | request-response | `frontend/src/app/(dashboard)/tenders/page.tsx` | exact (useQuery + error alerts) |
| `frontend/src/components/documents/DocumentUploadForm.tsx` | component | file-I/O | `frontend/src/components/profile/CompanyProfileForm.tsx` | role-match (RHF + zod + shadcn) |
| `frontend/src/components/documents/DocumentCard.tsx` | component | request-response | `frontend/src/components/tenders/TenderCard.tsx` | exact (Card + LabelValue + badge) |
| `frontend/src/components/documents/DocumentVault.tsx` | component | request-response | `frontend/src/app/(dashboard)/tenders/page.tsx` | role-match (list container) |
| `frontend/src/lib/api.ts` (modify) | utility | file-I/O | itself (extend with uploadFile) | self-modify |
| `frontend/src/components/layout/Sidebar.tsx` (modify) | component | — | itself | self-modify |

---

## Pattern Assignments

### `backend/app/services/minio_service.py` (service, file-I/O)

**Analog:** `backend/app/services/redis_service.py` — singleton клиент + набор вспомогательных функций

**Imports pattern** (redis_service.py lines 1-6):
```python
import secrets
from typing import Optional
import redis.asyncio as aioredis
from app.config import settings
```

**Singleton pattern** (redis_service.py lines 9-15 — адаптировать для Minio):
```python
# redis_service: клиент создаётся внутри async generator per-request
# Для MinIO: singleton создаётся при импорте модуля (thread-safe через urllib3 PoolManager)
# НЕ копировать async generator — MinIO синхронный, не нужен yield-паттерн
async def get_redis():
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()
```

**Целевой паттерн для minio_service.py** (из RESEARCH.md Pattern 1):
```python
from minio import Minio
from app.config import settings

_minio_client = Minio(
    endpoint=settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=False,  # добавить settings.minio_secure: bool = False в config.py
)

BUCKET_NAME = "tenderit-documents"

def ensure_bucket_exists() -> None:
    if not _minio_client.bucket_exists(BUCKET_NAME):
        _minio_client.make_bucket(BUCKET_NAME)
```

**Helper-функции — копировать структуру из redis_service.py** (lines 18-68):
каждая функция принимает клиент + параметры, возвращает значение. Для MinIO: все I/O вызовы оборачивать через `await asyncio.to_thread(...)`.

---

### `backend/app/services/document_service.py` (service, CRUD)

**Analog:** `backend/app/services/tender_service.py`

**Imports pattern** (tender_service.py lines 17-27):
```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.tender import Tender, UserWatchlist
from app.services.goszakup_service import fetch_tender_by_number_anno
```

**Адаптация для document_service.py:**
```python
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.document import Document
from app.services.minio_service import _minio_client, BUCKET_NAME
import asyncio
```

**Pure utility function pattern** (tender_service.py lines 36-49 — `_parse_gz_date`):
```python
def _parse_gz_date(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=_ALMATY_TZ)
    except (ValueError, TypeError):
        return None
```

**Применить тот же паттерн для `compute_expiry_status`** (RESEARCH.md Pattern 6):
```python
ExpiryStatus = Literal["ok", "warning_14", "warning_7", "expired"]

def compute_expiry_status(expires_at: datetime | None) -> ExpiryStatus:
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

**Async CRUD pattern** (tender_service.py lines 52-106 — `get_or_fetch_tender`):
```python
async def get_or_fetch_tender(db: AsyncSession, number_anno: str) -> Optional[Tender]:
    result = await db.execute(select(Tender).where(Tender.number_anno == number_anno))
    existing = result.scalar_one_or_none()
    # ... business logic
    await db.commit()
    return upsert_result.scalar_one()
```

**IDOR-safe delete pattern** (tender_service.py lines 143-166 — `remove_from_watchlist`):
```python
async def remove_from_watchlist(db: AsyncSession, user_id: int, number_anno: str) -> bool:
    del_result = await db.execute(
        delete(UserWatchlist).where(
            UserWatchlist.user_id == user_id,
            UserWatchlist.tender_id == tender.id,
        )
    )
    await db.commit()
    return del_result.rowcount > 0
```

**Адаптация для documents: порядок удаления** (RESEARCH.md Pitfall 5):
Сначала `await asyncio.to_thread(_minio_client.remove_object, BUCKET_NAME, doc.file_key)`, затем `await db.delete(doc)` + `await db.commit()`.

---

### `backend/app/models/document.py` (model, CRUD)

**Analog:** `backend/app/models/tender.py`

**Imports pattern** (tender.py lines 10-26):
```python
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base
```

**Адаптация для document.py** (из RESEARCH.md Pattern 7):
```python
from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base
```

**ORM model pattern** (tender.py lines 30-69 — `Mapped` + `mapped_column`):
```python
class Tender(Base):
    __tablename__ = "tenders"

    id: Mapped[int] = mapped_column(primary_key=True)
    number_anno: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name_ru: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # ...
    cached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

**Целевая модель Document** (RESEARCH.md Pattern 7 — уже верифицирован):
```python
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

**Ключевое отличие от Tender:** Document использует `DateTime(timezone=True)` для `expires_at` и `uploaded_at`. Нет `relationship` в Phase 4 (Phase 5 добавит).

---

### `backend/app/schemas/document.py` (schema, request-response)

**Analog:** `backend/app/schemas/tender.py`

**Imports + BaseModel pattern** (tender.py lines 1-15):
```python
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator
```

**Response schema pattern** (tender.py lines 27-43 — `TenderResponse`):
```python
class TenderResponse(BaseModel):
    model_config = {"from_attributes": True}

    number_anno: str
    name_ru: Optional[str] = None
    # ...
    cached_at: datetime
```

**Целевые схемы** (RESEARCH.md Pattern 6):
```python
from enum import Enum
from typing import Literal

class DocumentCategory(str, Enum):
    USTAV = "ustav"
    LICENSE = "license"
    CERTIFICATE = "certificate"
    REGISTRATION = "registration"
    OTHER = "other"

ExpiryStatus = Literal["ok", "warning_14", "warning_7", "expired"]

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
    expiry_status: ExpiryStatus  # добавляется в сервисном слое, не в ORM

class DocumentUploadRequest(BaseModel):
    # NOTE: не BaseModel — этот endpoint использует Form(), не JSON body
    # category и expires_at передаются как Form fields в роутере напрямую
    pass

class DocumentPatchRequest(BaseModel):
    category: DocumentCategory | None = None
    expires_at: datetime | None = None
```

**Валидация через Field** (tender.py lines 47-55 — `WatchlistAddRequest`):
```python
class WatchlistAddRequest(BaseModel):
    number_anno: str = Field(min_length=1, max_length=100)

    @field_validator("number_anno")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Номер тендера не может быть пустым")
        return stripped
```

---

### `backend/app/routers/documents.py` (controller, request-response)

**Analog:** `backend/app/routers/tenders.py`

**Imports pattern** (tenders.py lines 1-29):
```python
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.tender import TenderResponse, WatchlistAddRequest, WatchlistEntryResponse
from app.services.tender_service import (
    add_to_watchlist, get_or_fetch_tender, list_watchlist, remove_from_watchlist,
)

router = APIRouter()
```

**Auth dependency pattern** (tenders.py lines 34-38 — на каждом route):
```python
@router.get("/tenders/{number_anno}", response_model=TenderResponse)
async def get_tender(
    number_anno: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TenderResponse:
```

**404 + IDOR-safe pattern** (tenders.py lines 44-51):
```python
tender = await get_or_fetch_tender(db, number_anno.strip())
if tender is None:
    raise HTTPException(status_code=404, detail="...")
return TenderResponse.model_validate(tender)
```

**DELETE → 204 pattern** (tenders.py lines 79-96):
```python
@router.delete("/watchlist/{number_anno}", status_code=204)
async def remove_watchlist_entry(...) -> Response:
    removed = await remove_from_watchlist(db, current_user.id, number_anno.strip())
    if not removed:
        raise HTTPException(status_code=404, detail="...")
    return Response(status_code=204)
```

**Адаптация для documents.py** — добавить:
1. `UploadFile = File(...)` + `Form(...)` для multipart (RESEARCH.md Pattern 3)
2. Импорт `asyncio`, `uuid`, `os` для upload handler
3. Проверку `file.size > MAX_FILE_SIZE` до MinIO вызова
4. `GET /api/documents/attachable` — статический путь, объявить ДО `/{id}/url` во избежание конфликта

**Порядок маршрутов** (критично — FastAPI routing):
```python
router.get("/documents")          # список
router.get("/documents/attachable")  # ПЕРЕД /{id}/url !
router.post("/documents")         # upload
router.get("/documents/{id}/url") # presigned URL
router.patch("/documents/{id}")   # обновление метаданных
router.delete("/documents/{id}")  # удаление
```

---

### `backend/alembic/versions/0003_create_documents.py` (migration, CRUD)

**Analog:** `backend/alembic/versions/0002_create_tenders_watchlist.py`

**Header pattern** (0002 lines 1-21):
```python
"""create_tenders_watchlist

Revision ID: 0002
Revises: 861194df635a
Create Date: 2026-06-10
...
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "861194df635a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

**Адаптация для 0003:**
```python
revision: str = "0003"
down_revision: Union[str, None] = "0002"
```

**create_table + TIMESTAMPTZ pattern** (0002 lines 25-56):
```python
op.create_table(
    "tenders",
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("cached_at", sa.TIMESTAMP(timezone=True),
              server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id"),
)
op.create_index("ix_tenders_number_anno", "tenders", ["number_anno"], unique=True)
```

**Целевая миграция 0003** (RESEARCH.md Pattern 8 — полный текст верифицирован):
```python
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
        sa.Column("uploaded_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
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

---

### `backend/app/main.py` (modify — lifespan hook)

**Analog:** сам файл (lines 1-17)

**Текущий lifespan** (main.py lines 14-17):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()
```

**Целевой lifespan** (добавить до `yield`):
```python
import asyncio
from app.services.minio_service import ensure_bucket_exists

@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(ensure_bucket_exists)
    yield
    await engine.dispose()
```

**include_router** (main.py lines 40-43 — добавить по аналогии):
```python
from app.routers import auth, company, health, tenders, documents  # добавить documents
# ...
application.include_router(documents.router, prefix="/api", tags=["documents"])
```

---

### `backend/app/models/__init__.py` (modify)

**Текущий файл** (lines 1-5):
```python
from app.models.user import User  # noqa: F401
from app.models.company_profile import CompanyProfile  # noqa: F401
from app.models.tender import Tender, UserWatchlist  # noqa: F401

__all__ = ["User", "CompanyProfile", "Tender", "UserWatchlist"]
```

**Добавить** (по тому же паттерну):
```python
from app.models.document import Document  # noqa: F401
# в __all__: добавить "Document"
```

---

### `frontend/src/app/(dashboard)/documents/page.tsx` (component, request-response)

**Analog:** `frontend/src/app/(dashboard)/tenders/page.tsx`

**'use client' + imports pattern** (tenders/page.tsx lines 1-29):
```typescript
'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
```

**useQuery pattern** (tenders/page.tsx lines 57-67):
```typescript
const { data: tender, error: tenderError, isLoading } = useQuery<Tender>({
  queryKey: ['tender', queryNumber],
  queryFn: () => api.get<Tender>(`/api/tenders/${encodeURIComponent(queryNumber!)}`),
  enabled: queryNumber !== null,
  retry: false,
})
```

**Адаптация для documents/page.tsx:**
```typescript
// queryKey: ['documents'] — всегда enabled (список всех документов)
const { data: documents, error, isLoading, refetch } = useQuery<DocumentResponse[]>({
  queryKey: ['documents'],
  queryFn: () => api.get<DocumentResponse[]>('/api/documents'),
  retry: false,
})
```

**Alert error pattern** (tenders/page.tsx lines 130-140):
```typescript
{tenderError && !is404 && (
  <Alert className="text-destructive border-destructive/50 bg-destructive/10 text-sm">
    Не удалось загрузить данные. Проверьте соединение и попробуйте ещё раз.
  </Alert>
)}
```

**Page layout pattern** (tenders/page.tsx lines 87-93):
```typescript
return (
  <div className="space-y-6 max-w-2xl">
    <div>
      <h1 className="text-xl font-semibold">Поиск тендеров</h1>
      <p className="text-sm text-muted-foreground mt-0.5">...</p>
    </div>
    ...
  </div>
)
```

---

### `frontend/src/components/documents/DocumentUploadForm.tsx` (component, file-I/O)

**Analog:** `frontend/src/components/profile/CompanyProfileForm.tsx`

**Imports pattern** (CompanyProfileForm.tsx lines 1-12):
```typescript
'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert } from '@/components/ui/alert'
```

**Zod schema pattern** (CompanyProfileForm.tsx lines 14-24):
```typescript
const profileSchema = z.object({
  bin: z.string().regex(/^\d{12}$/, 'Введите 12 цифр'),
  company_name: z.string().min(1, 'Обязательное поле').max(500, 'Не более 500 символов'),
})
type ProfileFormValues = z.infer<typeof profileSchema>
```

**RHF setup pattern** (CompanyProfileForm.tsx lines 38-54):
```typescript
const [apiError, setApiError] = useState<string>('')
const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<ProfileFormValues>({
  resolver: zodResolver(profileSchema),
  defaultValues: { bin: initialData.bin ?? '' },
})
```

**Submit + error handling pattern** (CompanyProfileForm.tsx lines 56-70):
```typescript
const onSubmit = async (data: ProfileFormValues) => {
  setApiError('')
  try {
    await api.put('/api/company/profile', data)
    setSavedAt(new Date())
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Ошибка сохранения'
    setApiError(message)
  }
}
```

**Адаптация для DocumentUploadForm.tsx:**
1. Заменить `api.put(...)` на `uploadFile('/api/documents', formData)` (импортировать из `@/lib/api`)
2. Данные формы собирать через `new FormData()` — file берётся из `<input type="file">`, не через RHF register (RHF register не поддерживает file inputs нативно)
3. Предпочтительный паттерн: использовать `ref` на `<input type="file">` + RHF для остальных полей

**Alert pattern** (CompanyProfileForm.tsx lines 123-133):
```typescript
{apiError && (
  <Alert className="text-destructive border-destructive/50 bg-destructive/10 text-xs py-2">
    {apiError}
  </Alert>
)}
{savedAt && (
  <Alert className="text-sm border-primary/30 bg-primary/10 text-primary py-2">
    Профиль сохранён
  </Alert>
)}
```

---

### `frontend/src/components/documents/DocumentCard.tsx` (component, request-response)

**Analog:** `frontend/src/components/tenders/TenderCard.tsx`

**Imports + Card pattern** (TenderCard.tsx lines 1-16):
```typescript
import type { ReactNode } from 'react'
import type { Tender } from '@/types/tender'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
```

**LabelValue helper pattern** (TenderCard.tsx lines 38-45 — переиспользовать):
```typescript
interface Field {
  label: string
  value: ReactNode
}

function LabelValue({ label, value }: Field) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</span>
      <span className="text-sm text-foreground">{value}</span>
    </div>
  )
}
```

**Card layout pattern** (TenderCard.tsx lines 52-117):
```typescript
export default function TenderCard({ tender, children }: TenderCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base leading-snug">{tender.name_ru ?? '—'}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <LabelValue label="Заказчик" value={tender.customer_name_ru ?? '—'} />
          ...
        </div>
        {children && <div>{children}</div>}
      </CardContent>
    </Card>
  )
}
```

**ExpiryBadge добавить** (RESEARCH.md Pattern 11):
```typescript
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

**formatDate helper** (TenderCard.tsx lines 23-31 — копировать напрямую):
```typescript
function formatDate(isoOrRaw: string | null): string {
  if (!isoOrRaw) return '—'
  const d = new Date(isoOrRaw)
  if (isNaN(d.getTime())) return '—'
  const day = String(d.getDate()).padStart(2, '0')
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const year = d.getFullYear()
  return `${day}.${month}.${year}`
}
```

---

### `frontend/src/components/documents/DocumentVault.tsx` (component, request-response)

**Analog:** `frontend/src/app/(dashboard)/tenders/page.tsx` (list-container паттерн)

Контейнер принимает `documents: DocumentResponse[]`, рендерит:
1. Суммарный `Alert` если есть документы с `expiry_status !== 'ok'`
2. Список `<DocumentCard>` в CSS grid или `space-y-3`

**Alert pattern для суммарного предупреждения:**
```typescript
// если есть истекающие — показать Alert с предупреждением
const expiringCount = documents.filter(d => d.expiry_status !== 'ok').length
{expiringCount > 0 && (
  <Alert className="text-sm border-orange-500/50 bg-orange-500/10">
    {expiringCount} документ(а) требуют внимания — проверьте сроки действия
  </Alert>
)}
```

---

### `frontend/src/lib/api.ts` (modify — добавить uploadFile)

**Analog:** сам файл (lines 1-53)

**Текущий apiFetch pattern** (api.ts lines 5-44):
```typescript
async function apiFetch<T>(path: string, init?: RequestInit, didRetry = false): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })

  if (res.status === 401) {
    if (didRetry) {
      useAuthStore.getState().clearAuth()
      throw new Error('Session expired')
    }
    const refreshed = await fetch(`${BASE}/api/auth/refresh`, { method: 'POST', credentials: 'include' })
    if (!refreshed.ok) {
      useAuthStore.getState().clearAuth()
      throw new Error('Session expired')
    }
    return apiFetch<T>(path, init, true)
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'API error')
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}
```

**Добавить после apiFetch** (RESEARCH.md Pattern 9):
```typescript
export async function uploadFile<T>(path: string, formData: FormData, didRetry = false): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    // НЕ ставить Content-Type — браузер сам добавит multipart/form-data; boundary=...
    body: formData,
  })
  if (res.status === 401) {
    if (didRetry) { useAuthStore.getState().clearAuth(); throw new Error('Session expired') }
    const refreshed = await fetch(`${BASE}/api/auth/refresh`, { method: 'POST', credentials: 'include' })
    if (!refreshed.ok) { useAuthStore.getState().clearAuth(); throw new Error('Session expired') }
    return uploadFile<T>(path, formData, true)
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Upload error')
  }
  return res.json() as Promise<T>
}
```

**Экспортировать** через именованный экспорт (как в api.ts lines 46-53):
```typescript
export const api = {
  get: ...,
  post: ...,
  put: ...,
  delete: ...,
  // НЕ добавлять upload сюда — uploadFile экспортируется отдельно
}
```

---

### `frontend/src/components/layout/Sidebar.tsx` (modify)

**Analog:** сам файл (lines 1-75)

**Текущий navItems** (Sidebar.tsx lines 5, 11-15):
```typescript
import { LayoutDashboard, Search, Building2, LogOut } from 'lucide-react'

const navItems = [
  { href: '/dashboard', label: 'Обзор', icon: LayoutDashboard },
  { href: '/tenders', label: 'Тендеры', icon: Search },
  { href: '/profile', label: 'Профиль', icon: Building2 },
]
```

**Изменение — добавить FileText** (RESEARCH.md Pattern 10):
```typescript
import { LayoutDashboard, Search, Building2, FileText, LogOut } from 'lucide-react'

const navItems = [
  { href: '/dashboard', label: 'Обзор', icon: LayoutDashboard },
  { href: '/tenders', label: 'Тендеры', icon: Search },
  { href: '/profile', label: 'Профиль', icon: Building2 },
  { href: '/documents', label: 'Документы', icon: FileText },
]
```

Остальной JSX — без изменений (lines 17-75 Sidebar.tsx).

---

## Shared Patterns

### Аутентификация — JWT из cookie

**Source:** `backend/app/deps.py` lines 10-28
**Apply to:** Все 6 роутов в `documents.py`

```python
async def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(access_token, settings.jwt_secret, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user
```

**Правило:** `user_id` ВСЕГДА из `current_user.id` (JWT). Никогда из тела запроса, query param или path param.

---

### IDOR-защита

**Source:** `backend/app/routers/tenders.py` lines 79-96, `backend/app/services/tender_service.py` lines 143-166
**Apply to:** `GET /documents/{id}/url`, `PATCH /documents/{id}`, `DELETE /documents/{id}`

```python
# Паттерн для каждого route с doc_id:
doc = await db.get(Document, doc_id)
if not doc or doc.user_id != current_user.id:
    raise HTTPException(status_code=404, detail="Документ не найден")
```

Возвращать 404 (не 403) — не раскрывать существование чужого ресурса.

---

### Error handling — HTTPException

**Source:** `backend/app/routers/tenders.py` lines 44-51, 65-70, 88-93
**Apply to:** Все routes в `documents.py`

```python
# 404 pattern:
if result is None:
    raise HTTPException(status_code=404, detail="...")

# 413 pattern (только upload):
if file.size is not None and file.size > MAX_FILE_SIZE:
    raise HTTPException(status_code=413, detail="Файл превышает 20 МБ")

# 204 return pattern:
return Response(status_code=204)
```

---

### SQLAlchemy async session

**Source:** `backend/app/routers/tenders.py` lines 34-38
**Apply to:** Все routes в `documents.py`

```python
db: AsyncSession = Depends(get_db)
```

Каждый route получает сессию через DI. `await db.commit()` только в сервисном слое (не в роутере напрямую) — если логика несложная, можно в роутере, но консистентно с tender_service паттерном.

---

### asyncio.to_thread для синхронных I/O вызовов

**Source:** CONTEXT.md Decision 1, RESEARCH.md Pattern 1-5
**Apply to:** `minio_service.py` и все MinIO вызовы в `document_service.py` / `documents.py`

```python
import asyncio

# Каждый синхронный MinIO вызов:
await asyncio.to_thread(_minio_client.put_object, BUCKET_NAME, key, file.file, file.size, content_type)
await asyncio.to_thread(_minio_client.presigned_get_object, BUCKET_NAME, key, timedelta(minutes=15))
await asyncio.to_thread(_minio_client.remove_object, BUCKET_NAME, key)
await asyncio.to_thread(ensure_bucket_exists)
```

---

### React Query + invalidation

**Source:** `frontend/src/app/(dashboard)/tenders/page.tsx` lines 57-79
**Apply to:** `documents/page.tsx`, `DocumentVault.tsx`, `DocumentUploadForm.tsx`

```typescript
import { useQuery, useQueryClient } from '@tanstack/react-query'

// После успешного upload / delete:
const queryClient = useQueryClient()
queryClient.invalidateQueries({ queryKey: ['documents'] })
```

---

### shadcn/ui компоненты

**Source:** `frontend/src/components/profile/CompanyProfileForm.tsx` lines 7-12
**Apply to:** Все frontend компоненты Phase 4

Доступные компоненты (верифицированы в codebase):
- `Card, CardContent, CardHeader, CardTitle` — из `@/components/ui/card`
- `Button` — из `@/components/ui/button`
- `Input` — из `@/components/ui/input`
- `Label` — из `@/components/ui/label`
- `Alert` — из `@/components/ui/alert`
- `Badge` — из `@/components/ui/badge` (верифицировано RESEARCH.md)

---

## No Analog Found

Нет файлов без аналога — все новые файлы покрыты существующими паттернами кодовой базы. Паттерны для MinIO и multipart upload верифицированы через inspect пакетов (RESEARCH.md HIGH confidence).

---

## Metadata

**Analog search scope:** `backend/app/services/`, `backend/app/models/`, `backend/app/routers/`, `backend/app/schemas/`, `backend/alembic/versions/`, `frontend/src/`, `frontend/src/components/`, `frontend/src/lib/`
**Files scanned:** 14 файлов прочитано напрямую
**Pattern extraction date:** 2026-06-11
