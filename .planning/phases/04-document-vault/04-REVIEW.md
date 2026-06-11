---
phase: 04-document-vault
reviewed: 2026-06-11T00:00:00Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - backend/alembic/versions/0003_create_documents.py
  - backend/app/config.py
  - backend/app/main.py
  - backend/app/models/__init__.py
  - backend/app/models/document.py
  - backend/app/routers/documents.py
  - backend/app/schemas/document.py
  - backend/app/services/document_service.py
  - backend/app/services/minio_service.py
  - backend/pyproject.toml
  - backend/tests/test_documents.py
  - backend/tests/test_documents_expiry.py
  - frontend/src/app/(dashboard)/documents/page.tsx
  - frontend/src/components/documents/DocumentCard.tsx
  - frontend/src/components/documents/DocumentUploadForm.tsx
  - frontend/src/components/documents/DocumentVault.tsx
  - frontend/src/components/layout/Sidebar.tsx
  - frontend/src/lib/api.ts
  - frontend/src/types/document.ts
findings:
  critical: 4
  warning: 5
  info: 3
  total: 12
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-06-11
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Phase 4 implements the Document Vault: MinIO-backed file storage with CRUD endpoints, expiry tracking, and a Next.js frontend. IDOR protection is correctly implemented (user_id always from JWT, `get_user_document` always filters by `user_id`). Route ordering for `attachable` vs `{doc_id}` is handled correctly.

However, four critical issues were found: the 20 MB size guard is bypassable when the client omits a part Content-Length header; there is no file type allowlist (any executable or script can be uploaded); the `PATCH` endpoint cannot clear an expiry date due to a null-handling flaw; and the internal MinIO `file_key` is exposed in every API response. Five warnings round out correctness and robustness gaps.

---

## Critical Issues

### CR-01: File size limit is bypassable when `file.size` is None

**File:** `backend/app/routers/documents.py:77`

**Issue:** The guard `if file.size is not None and file.size > MAX_FILE_SIZE` only fires when Starlette has populated `UploadFile.size`. Starlette derives `size` from the `Content-Length` header of the multipart part — a header the client can omit. When omitted, `file.size` is `None`, the guard is skipped, and `put_object` is called with length `-1` (the MinIO SDK streaming-unknown-size sentinel). A client can upload a file of arbitrary size (gigabytes) to MinIO with no restriction. The 20 MB limit (T-04-02) is effectively not enforced for such clients.

**Fix:** Read and limit the stream before uploading, regardless of the declared size:

```python
# In upload_document, before put_object
CHUNK = 64 * 1024
total = 0
chunks: list[bytes] = []
while True:
    chunk = await file.read(CHUNK)
    if not chunk:
        break
    total += len(chunk)
    if total > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Файл превышает 20 МБ")
    chunks.append(chunk)

data = b"".join(chunks)
await asyncio.to_thread(
    minio_service._minio_client.put_object,
    minio_service.BUCKET_NAME,
    object_key,
    io.BytesIO(data),
    len(data),
    file.content_type or "application/octet-stream",
)
```

Alternatively, configure Starlette's `MAX_REQUEST_BODY_SIZE` at the middleware level so the guard is enforced before reaching the handler.

---

### CR-02: No file type allowlist — arbitrary files accepted (including executables)

**File:** `backend/app/routers/documents.py:81-82`

**Issue:** The extension is extracted from the client-supplied filename and embedded directly into the MinIO object key. Neither the extension nor the `content_type` is validated against any allowlist. A user can upload `malware.exe`, `shell.sh`, `exploit.php`, or any other file type. If MinIO is ever misconfigured as public (or a presigned URL is shared), a receiver can directly execute the downloaded file. The `mime_type` stored in the DB is also entirely client-controlled and unverified.

**Fix:** Enforce an allowlist of accepted MIME types and extensions before the MinIO upload:

```python
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/png",
    "image/jpeg",
}

ext = os.path.splitext(file.filename or "")[1].lower()
if ext not in ALLOWED_EXTENSIONS:
    raise HTTPException(status_code=415, detail="Тип файла не поддерживается")
ct = file.content_type or ""
if ct not in ALLOWED_MIME_TYPES:
    raise HTTPException(status_code=415, detail="Тип файла не поддерживается")
```

---

### CR-03: `PATCH /documents/{doc_id}` cannot clear `expires_at` (unclearing flaw)

**File:** `backend/app/routers/documents.py:184-185`

**Issue:** The patch handler applies `body.expires_at` only when it is `not None`:

```python
if body.expires_at is not None:
    doc.expires_at = body.expires_at
```

`DocumentPatchRequest` declares `expires_at: datetime | None = None`. In JSON, both `{}` (omitted) and `{"expires_at": null}` (explicit null) produce `body.expires_at == None` in Pydantic v2, so the two cases are indistinguishable. A client can never remove an expiry date from a document — sending `{"expires_at": null}` is silently ignored. Once a document has an expiry date set, it is permanently stuck with it, which means the "permanent document" state is unreachable after the first PATCH.

**Fix:** Use Pydantic v2's `model_fields_set` or a sentinel pattern to distinguish "not provided" from "explicitly null":

```python
from typing import Annotated
from pydantic import BaseModel

# In schemas/document.py:
_UNSET = object()

class DocumentPatchRequest(BaseModel):
    model_config = {"populate_by_name": True}
    category: DocumentCategory | None = None
    expires_at: datetime | None | Literal["__unset__"] = "__unset__"
```

Or, more idiomatically, check `model_fields_set`:

```python
# In router:
if "expires_at" in body.model_fields_set:
    doc.expires_at = body.expires_at   # sets to None (clear) or a new datetime
```

This requires the Pydantic model to keep the default as a sentinel (e.g., `expires_at: datetime | None = None` is fine, but `model_fields_set` must be checked at the call site).

---

### CR-04: `file_key` (internal MinIO object key) exposed in every API response

**File:** `backend/app/schemas/document.py:49`

**Issue:** `DocumentResponse` includes the `file_key` field (`documents/{user_id}/{uuid}ext`). This field is the internal MinIO storage path. Exposing it to the client:

1. Leaks the user_id embedded in the key prefix (`documents/42/...`), allowing user enumeration via documents.
2. If MinIO bucket policy is ever loosened or misconfigured, an attacker knowing the key can access objects directly, bypassing the presigned-URL TTL mechanism entirely.
3. The frontend does not use `file_key` anywhere — it calls `/url` to get a presigned URL. The field is purely an information leak.

**Fix:** Remove `file_key` from `DocumentResponse`:

```python
class DocumentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    file_name: str
    # file_key removed — internal storage detail, not for clients
    file_size: int
    mime_type: str
    category: DocumentCategory
    expires_at: datetime | None
    uploaded_at: datetime
    expiry_status: ExpiryStatus
```

Update `to_response()` in `document_service.py` to omit `file_key` from the dict. Keep `file_key` only in the ORM model and internal service functions.

---

## Warnings

### WR-01: `compute_expiry_status` misclassifies documents expiring today

**File:** `backend/app/services/document_service.py:45-51`

**Issue:** `delta.days` is the integer floor of the timedelta in days. When a document expires in, say, 30 minutes, `delta` is approximately `timedelta(seconds=1800)` and `delta.days == 0`. The function returns `"warning_7"` instead of `"expired"`. Documents that expired within the same calendar day (but have `expires_at < now`) return `"warning_7"` until midnight, because `(expires_at - now).days` is `-1` only after a full day has elapsed. Specifically, `timedelta(hours=-2).days == -1` but `timedelta(minutes=-30).days == 0`.

Wait — re-checking: `timedelta(minutes=-30).days` is actually `-1` in Python (timedelta stores negative values as a negative days count minus the seconds component). Let me clarify the actual boundary:

The real bug is `days == 0`: a document expiring in less than 24 hours but more than 0 minutes returns `"warning_7"`, which is correct in intent but the docstring claims `1 ≤ days ≤ 7`. The `list_attachable_documents` filter uses `expires_at > now` (correct), but the badge shown in the UI via `compute_expiry_status` will show `"warning_7"` for a document expiring in 2 hours rather than `"expired"`. The inconsistency between badge state and attachable-filter state is confusing and could mislead users.

**Fix:** Use `total_seconds()` for the boundary check:

```python
def compute_expiry_status(expires_at: datetime | None) -> ExpiryStatus:
    if expires_at is None:
        return "ok"
    now = datetime.now(timezone.utc)
    diff = expires_at - now
    total_secs = diff.total_seconds()
    if total_secs <= 0:
        return "expired"
    days = diff.days  # safe: total_seconds > 0 so days >= 0
    if days < 7:
        return "warning_7"
    if days < 14:
        return "warning_14"
    return "ok"
```

---

### WR-02: `expires_at` submitted as date-only string may fail with `TypeError` at runtime

**File:** `frontend/src/components/documents/DocumentUploadForm.tsx:76` / `backend/app/routers/documents.py:63`

**Issue:** The form's `<input type="date">` produces a string like `"2026-12-31"` (no time, no timezone). FastAPI parses this form field as `datetime` (declared on line 63). Pydantic v2 parses `"2026-12-31"` as `datetime(2026, 12, 31, 0, 0, 0)` — a **naive** (timezone-unaware) datetime. When this value is stored in a `TIMESTAMPTZ` column and later retrieved, asyncpg returns a tz-aware datetime. The `compute_expiry_status` function then compares `expires_at` (tz-aware, from DB) to `datetime.now(timezone.utc)` (tz-aware), which works. However, during the same request — before the round-trip — `to_response(doc)` is called with `doc.expires_at` that was set from the naive input, and the comparison `expires_at - now` where `expires_at` is naive will raise `TypeError: can't subtract offset-naive and offset-aware datetimes` in Python 3.12.

**Fix (backend):** Normalize the incoming `expires_at` to UTC on ingestion:

```python
from datetime import timezone as tz

# In upload_document and patch_document, after receiving expires_at:
if expires_at is not None and expires_at.tzinfo is None:
    expires_at = expires_at.replace(tzinfo=tz.utc)
```

**Fix (frontend):** Append `T00:00:00Z` when building the FormData to send a proper ISO datetime:

```typescript
if (data.expires_at) {
  formData.append('expires_at', data.expires_at + 'T00:00:00Z')
}
```

---

### WR-03: No atomicity between MinIO upload and DB insert — orphaned files on DB failure

**File:** `backend/app/routers/documents.py:87-105`

**Issue:** The upload route calls `put_object` (line 87) and then `create_document` (line 96) as two separate, non-atomic operations. If `create_document` raises — for example, due to a DB connection failure, constraint violation, or commit error — the MinIO object has already been written and will never be cleaned up. There is no compensating delete and no retry mechanism. Over time this leads to storage growth with unreferenced files.

**Fix (short term):** Wrap the upload in a try/except and delete the MinIO object if the DB insert fails:

```python
await asyncio.to_thread(
    minio_service._minio_client.put_object, ...
)
try:
    doc = await create_document(db=db, ...)
except Exception:
    await asyncio.to_thread(
        minio_service._minio_client.remove_object,
        minio_service.BUCKET_NAME,
        object_key,
    )
    raise HTTPException(status_code=500, detail="Ошибка при сохранении документа")
```

**Fix (long term):** Consider a two-phase approach: write MinIO object with a "pending" prefix, commit DB record, then rename/move the object — or use a background cleanup job for objects with no DB counterpart.

---

### WR-04: Hardcoded default secrets in config — both use the same weak value

**File:** `backend/app/config.py:19-21`

**Issue:** Both `secret_key` and `jwt_secret` default to `"change-me-in-production"`. They share the identical default value. If the application is deployed without a `.env` file (or with an incomplete one), both secrets are simultaneously trivially guessable. An attacker who knows the default can forge JWT tokens and bypass all authentication. The identical default for two distinct secrets is a particularly bad pattern — it increases the blast radius of a single deployment mistake.

**Fix:** There is no safe default for a cryptographic secret. The application should fail at startup if the key is the default placeholder in a non-debug context:

```python
from pydantic import model_validator

class Settings(BaseSettings):
    ...
    jwt_secret: str = "change-me-in-production"

    @model_validator(mode="after")
    def validate_secrets(self) -> "Settings":
        if not self.debug and self.jwt_secret == "change-me-in-production":
            raise ValueError("jwt_secret must be set in production (debug=False)")
        return self
```

---

### WR-05: `file_size` stored as `0` when `file.size` is `None`

**File:** `backend/app/routers/documents.py:101`

**Issue:** `file_size=file.size or 0` stores `0` when the multipart parser did not populate `UploadFile.size`. A `file_size` of `0` is indistinguishable from an empty file. The frontend and any future Phase 5 code that relies on `file_size` for display or validation cannot distinguish "unknown size" from "empty file." This is a data quality problem that compounds CR-01 (the size is also not enforced in this path).

**Fix:** After the streaming read suggested in CR-01, the actual size is known (`len(data)`). Use that:

```python
file_size=len(data),  # actual bytes written, always accurate
```

---

## Info

### IN-01: `file_key` used in frontend `DocumentResponse` type but never consumed

**File:** `frontend/src/types/document.ts:22`

**Issue:** `DocumentResponse` declares `file_key: string`. No frontend component reads or uses this field — download uses `/url` endpoint, display uses `file_name`. This is dead data in the type and a symptom of CR-04 (the backend should not send it at all).

**Fix:** Remove `file_key` from the TypeScript type after removing it from the backend response schema (see CR-04).

---

### IN-02: Russian pluralization in `DocumentVault` is incomplete

**File:** `frontend/src/components/documents/DocumentVault.tsx:36`

**Issue:** The pluralization `expiringCount === 1 ? 'документ требует' : 'документ(а) требуют'` is only a two-branch split. Russian has three plural forms: 1 (документ требует), 2-4 (документа требуют), 5+ (документов требуют). The current text `"документ(а) требуют"` is not natural Russian for any count. For `expiringCount = 2` the correct text is "2 документа требуют внимания", not "2 документ(а) требуют".

**Fix:**

```typescript
function pluralDoc(n: number): string {
  if (n % 10 === 1 && n % 100 !== 11) return `${n} документ требует`
  if ([2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100)) return `${n} документа требуют`
  return `${n} документов требуют`
}
// Usage: {pluralDoc(expiringCount)} внимания — ...
```

---

### IN-03: Silent swallow of download and delete errors in `DocumentsPage`

**File:** `frontend/src/app/(dashboard)/documents/page.tsx:42-50`

**Issue:** Both `onDownload` and `onDelete` catch all errors and do nothing. The user receives no feedback when a delete or download fails — the document list stays unchanged and no error message is shown. This is especially problematic for delete: the user clicks "Удалить", nothing happens, and the document is still visible. The user has no way to know whether the operation succeeded or failed.

**Fix:** Surface errors to the user with a `useState` error message or a toast notification:

```typescript
const [actionError, setActionError] = useState<string>('')

async function onDelete(id: number) {
  try {
    await api.delete('/api/documents/' + id)
    await queryClient.invalidateQueries({ queryKey: ['documents'] })
  } catch (err) {
    setActionError(err instanceof Error ? err.message : 'Не удалось удалить документ')
  }
}
```

---

_Reviewed: 2026-06-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
