---
phase: 04-document-vault
fixed_at: 2026-06-11T00:00:00Z
review_path: .planning/phases/04-document-vault/04-REVIEW.md
iteration: 1
findings_in_scope: 9
fixed: 9
skipped: 0
status: all_fixed
---

# Phase 4: Code Review Fix Report

**Fixed at:** 2026-06-11
**Source review:** .planning/phases/04-document-vault/04-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 9 (CR-01, CR-02, CR-03, CR-04, WR-01, WR-02, WR-03, WR-04, WR-05)
- Fixed: 9
- Skipped: 0

## Fixed Issues

### CR-01: File size limit bypassable when file.size is None

**Files modified:** `backend/app/routers/documents.py`
**Commit:** be12ede
**Applied fix:** Replaced the conditional `file.size is not None` guard with a streaming read loop (64KB chunks) that accumulates bytes and raises 413 if `total > MAX_FILE_SIZE` at any point. `put_object` now receives `io.BytesIO(data)` with exact length — never `-1`. Size is always enforced regardless of whether the client sends a part Content-Length header.

---

### CR-02: No file type allowlist

**Files modified:** `backend/app/routers/documents.py`
**Commit:** be12ede
**Applied fix:** Added `ALLOWED_EXTENSIONS` and `ALLOWED_MIME_TYPES` module-level constants. Validation runs before stream reading: extension check on `os.path.splitext(file.filename)`, MIME check on `file.content_type`. Both return 415 Unsupported Media Type on mismatch. Allowed types: PDF, DOC/DOCX, XLS/XLSX, PNG, JPG/JPEG.

---

### CR-03: PATCH cannot clear expires_at

**Files modified:** `backend/app/routers/documents.py`
**Commit:** be12ede
**Applied fix:** Replaced `if body.expires_at is not None` with `if "expires_at" in body.model_fields_set`. Pydantic v2 populates `model_fields_set` only when a field is explicitly provided in the request body. Explicit `null` now clears the field; omitting the field leaves it unchanged. WR-02 UTC normalization is also applied inside this branch.

---

### CR-04: file_key exposed in API response

**Files modified:** `backend/app/schemas/document.py`, `backend/app/services/document_service.py`, `frontend/src/types/document.ts`
**Commit:** 7345241
**Applied fix:** Removed `file_key: str` field from `DocumentResponse` Pydantic schema. Removed `"file_key": doc.file_key` from the dict in `to_response()`. Removed `file_key: string` from the TypeScript `DocumentResponse` interface. `file_key` is retained in the ORM model and all internal service functions that need it (delete, presigned URL generation).

---

### WR-01: compute_expiry_status misclassifies sub-24h expiry

**Files modified:** `backend/app/services/document_service.py`
**Commit:** 9c35865
**Applied fix:** Changed the expired boundary check from `if days < 0` to `if diff.total_seconds() <= 0`. `delta.days` is 0 for a document expiring in less than 24h but more than 0 seconds, causing it to show `warning_7` instead of `expired`. `total_seconds()` is negative the instant `expires_at < now`, independent of sub-day granularity. `days` is still used for the warning thresholds (safe since we only reach that branch when `total_seconds > 0`).

---

### WR-02: Naive expires_at causes TypeError

**Files modified:** `backend/app/routers/documents.py`, `frontend/src/components/documents/DocumentUploadForm.tsx`
**Commit:** be12ede (backend), b1653f2 (frontend)
**Applied fix (backend):** Added UTC normalization in both `upload_document` and `patch_document` — if `expires_at.tzinfo is None`, replace with `expires_at.replace(tzinfo=tz.utc)`. Applied after receiving the value, before any comparison or DB write.
**Applied fix (frontend):** Changed `formData.append('expires_at', data.expires_at)` to `formData.append('expires_at', data.expires_at + 'T00:00:00Z')`. `input[type=date]` produces a date-only string; appending `T00:00:00Z` makes it a valid ISO 8601 datetime with UTC timezone.

---

### WR-03: No rollback on DB insert failure after MinIO upload

**Files modified:** `backend/app/routers/documents.py`
**Commit:** be12ede
**Applied fix:** Wrapped `create_document(...)` in `try/except Exception`. On exception, `remove_object` is called on MinIO (via `asyncio.to_thread`) to clean up the already-uploaded object, then raises `HTTPException(500)`. This prevents orphaned MinIO objects when the DB commit fails.

---

### WR-04: Default jwt_secret not validated at startup

**Files modified:** `backend/app/config.py`
**Commit:** 3c121dd
**Applied fix:** Added `@model_validator(mode="after") def validate_secrets(self)` to `Settings`. Raises `ValueError` if `jwt_secret == "change-me-in-production"` and `debug=False`. `debug=True` (local dev and test environment) is exempt so the existing test suite continues to pass without `.env`. The default placeholder constant is extracted to `_DEFAULT_SECRET` to avoid repetition.

---

### WR-05: file_size stored as 0 when file.size is None

**Files modified:** `backend/app/routers/documents.py`
**Commit:** be12ede
**Applied fix:** Covered by CR-01 fix. After the streaming read loop, `data = b"".join(chunks)` always contains the exact file bytes. `file_size=len(data)` is passed to `create_document` — always accurate, never 0.

---

## Skipped Issues

None — all findings were fixed.

---

_Fixed: 2026-06-11_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
