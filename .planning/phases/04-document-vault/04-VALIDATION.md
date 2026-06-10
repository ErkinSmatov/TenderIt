---
phase: 4
slug: document-vault
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-11
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) + vitest / jest (frontend, if added) |
| **Config file** | `backend/pytest.ini` |
| **Quick run command** | `cd backend && pytest tests/test_documents.py -x -q` |
| **Full suite command** | `cd backend && pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/test_documents.py -x -q`
- **After every plan wave:** Run `cd backend && pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|--------|
| 04-minio-service | Wave 0 | 0 | DOCS-01 | IDOR | ensure_bucket_exists is idempotent | unit | `pytest tests/test_documents.py -x -q` | ⬜ pending |
| 04-document-model | Wave 0 | 0 | DOCS-01..05 | — | N/A | migration | `alembic upgrade head` | ⬜ pending |
| 04-upload-endpoint | Wave 1 | 1 | DOCS-01 | IDOR | user_id from JWT only, not body | unit | `pytest tests/test_documents.py::test_upload -x -q` | ⬜ pending |
| 04-list-endpoint | Wave 1 | 1 | DOCS-02,03 | IDOR | returns only current user's docs | unit | `pytest tests/test_documents.py::test_list -x -q` | ⬜ pending |
| 04-presigned-url | Wave 1 | 1 | DOCS-01 | IDOR | doc.user_id == current_user.id check | unit | `pytest tests/test_documents.py::test_presigned -x -q` | ⬜ pending |
| 04-delete-endpoint | Wave 1 | 1 | DOCS-04 | IDOR | cannot delete another user's doc | unit | `pytest tests/test_documents.py::test_delete_idor -x -q` | ⬜ pending |
| 04-expiry-status | Wave 1 | 1 | DOCS-03 | — | expired doc not in /attachable | unit | `pytest tests/test_documents.py::test_expiry_status -x -q` | ⬜ pending |
| 04-attachable-endpoint | Wave 1 | 1 | DOCS-05 | IDOR | only non-expired docs returned | unit | `pytest tests/test_documents.py::test_attachable -x -q` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_documents.py` — stubs for DOCS-01..DOCS-05
- [ ] `backend/tests/conftest.py` — extend with MinIO mock fixture (respx or pytest-mock)
- [ ] `python-multipart` added to `pyproject.toml` (required for FastAPI UploadFile)
- [ ] `minio` added to `pyproject.toml`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| File upload UI — drag-and-drop works | DOCS-01 | Browser DOM interaction | Upload a PDF from /documents page, verify file appears in list |
| Expiry badge shown in UI at 7-day / 14-day threshold | DOCS-03 | Date-dependent UI state | Set expires_at = now()+6 days via DB, reload /documents, verify red badge |
| Pre-signed URL opens correct file in browser | DOCS-01 | Browser file rendering | Click download on a document card, verify PDF opens |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
