---
phase: 04-document-vault
plan: "03"
subsystem: frontend
tags: [nextjs, react-query, shadcn, document-vault, multipart-upload, expiry-badges]
dependency_graph:
  requires: [04-02-document-vault-api-routes]
  provides: [documents-page, document-upload-ui, document-vault-ui, documents-nav-item]
  affects:
    - frontend/src/types/document.ts
    - frontend/src/lib/api.ts
    - frontend/src/components/documents/DocumentCard.tsx
    - frontend/src/components/documents/DocumentUploadForm.tsx
    - frontend/src/components/documents/DocumentVault.tsx
    - frontend/src/app/(dashboard)/documents/page.tsx
    - frontend/src/components/layout/Sidebar.tsx
tech_stack:
  added: []
  patterns:
    - uploadFile-no-content-type
    - useRef-for-file-input
    - react-query-invalidate-on-mutation
    - expiry-badge-by-status
    - summary-alert-expiring-docs
key_files:
  created:
    - frontend/src/types/document.ts
    - frontend/src/components/documents/DocumentCard.tsx
    - frontend/src/components/documents/DocumentUploadForm.tsx
    - frontend/src/components/documents/DocumentVault.tsx
    - frontend/src/app/(dashboard)/documents/page.tsx
  modified:
    - frontend/src/lib/api.ts
    - frontend/src/components/layout/Sidebar.tsx
decisions:
  - "uploadFile exported as named function (not added to api object) — keeps multipart separate from JSON apiFetch"
  - "useRef for file input — RHF register does not natively support file inputs, ref approach avoids wrapper complexity"
  - "client-side 20MB validation before API call — fast feedback without network round-trip"
  - "DocumentVault expiring count uses expiry_status !== 'ok' — covers warning_14, warning_7, and expired in one filter"
metrics:
  duration: "~12 min"
  completed: "2026-06-10"
  tasks_completed: 2
  tasks_total: 3
  files_created: 5
  files_modified: 2
---

# Phase 4 Plan 03: Document Vault Frontend UI Summary

**One-liner:** Full Document Vault frontend with multipart upload form (file + category + expiry), DocumentCard with ExpiryBadge, DocumentVault summary alert, /documents page with react-query, and Sidebar nav item.

## Completed Tasks

| # | Task | Commit | Type | Key Output |
|---|------|--------|------|-----------|
| 1 | Типы + uploadFile хелпер + DocumentCard | 1ac45b0 | feat | document.ts types, uploadFile (no Content-Type), DocumentCard with ExpiryBadge |
| 2 | DocumentUploadForm + DocumentVault + страница + Sidebar nav | afbc194 | feat | Upload form (FormData+ref), Vault container with expiry Alert, /documents page, Sidebar FileText nav |

## What Was Built

### `frontend/src/types/document.ts`

- `DocumentCategory` — union type: 'ustav' | 'license' | 'certificate' | 'registration' | 'other'
- `ExpiryStatus` — union type: 'ok' | 'warning_14' | 'warning_7' | 'expired'
- `DocumentResponse` — full interface mirroring backend schema
- `CATEGORY_LABELS` — Record mapping categories to Russian UI labels

### `frontend/src/lib/api.ts` — `uploadFile` helper

- `export async function uploadFile<T>(path, formData, didRetry?)` — named export, NOT in `api` object
- No `Content-Type` header set — browser adds `multipart/form-data; boundary=...` automatically
- Handles 401 silent refresh (same pattern as `apiFetch`) + single retry
- Error throws `err.detail ?? 'Upload error'`

### `frontend/src/components/documents/DocumentCard.tsx`

- Props: `{ document: DocumentResponse, onDownload, onDelete }`
- Internal `LabelValue` helper (copied from TenderCard pattern)
- Internal `formatDate` helper (copied from TenderCard pattern)
- Internal `ExpiryBadge({ status })`:
  - `ok` — null (not rendered)
  - `warning_14` — Badge variant `secondary` "Истекает через 14 дней"
  - `warning_7` — Badge variant `outline` "Истекает через 7 дней"
  - `expired` — Badge variant `destructive` "Истёк"
- Buttons: Download (outline), Delete (ghost + destructive color)

### `frontend/src/components/documents/DocumentUploadForm.tsx`

- File input via `ref` (not RHF register) — avoids RHF's lack of native file support
- Category via `select` with RHF register + zod enum validation
- `expires_at` via `Input type="date"` (optional)
- Client-side file size check (> 20MB) before API call
- On submit: builds `new FormData()`, calls `uploadFile('/api/documents', formData)`
- On success: `queryClient.invalidateQueries(['documents'])` + reset form + clear file input
- Error Alert pattern (apiError state, from CompanyProfileForm)

### `frontend/src/components/documents/DocumentVault.tsx`

- Props: `{ documents: DocumentResponse[], onDownload, onDelete }`
- Summary Alert shown when `documents.filter(d => d.expiry_status !== 'ok').length > 0`
- Alert uses correct grammatical form for count (1 / 2+)
- Empty state: "Нет загруженных документов" paragraph
- Renders `<DocumentCard>` list with `space-y-3`

### `frontend/src/app/(dashboard)/documents/page.tsx`

- `useQuery<DocumentResponse[]>({ queryKey: ['documents'], queryFn: () => api.get('/api/documents'), retry: false })`
- `onDownload(id)`: `api.get('/api/documents/'+id+'/url')` then `window.open(url, '_blank')`
- `onDelete(id)`: `api.delete('/api/documents/'+id)` then `queryClient.invalidateQueries(['documents'])`
- Error Alert when query fails
- Layout: `<div className="space-y-6 max-w-2xl">`

### `frontend/src/components/layout/Sidebar.tsx`

- Added `FileText` to lucide-react import
- Added `{ href: '/documents', label: 'Документы', icon: FileText }` to navItems after профиль

## Threat Mitigations Applied

| Threat | Mitigation |
|--------|-----------|
| T-04-06 Content-Type tampering | `uploadFile` does NOT set Content-Type — browser adds boundary automatically |
| T-04-03 URL disclosure | `onDownload` opens pre-signed URL in new tab; URL obtained fresh per request (TTL 15 min from backend) |
| T-04-05 EoP via user_id | UI never sends user_id — backend extracts it from JWT cookie (credentials:'include') |

## Checkpoint Status

**Task 3 (checkpoint:human-verify) requires manual verification.**

The UI build is complete — all 2 auto tasks executed and committed. The checkpoint is awaiting human approval.

### To verify:
1. Ensure backend + frontend running, MinIO + PostgreSQL up, user logged in
2. Open app — "Документы" nav item visible in sidebar — click navigates to /documents
3. Upload PDF with category "Устав", no expiry — card appears, no expiry badge
4. Upload file with "Лицензия" + expiry 5 days out — badge "Истекает через 7 дней" + summary Alert
5. Click "Скачать" — file opens in new tab
6. Click "Удалить" — card disappears from list
7. Try file > 20MB — client-side error "Файл превышает 20 МБ"

## Deviations from Plan

None — plan executed exactly as written.

The node_modules symlink (`frontend/node_modules` pointing to main repo's `frontend/node_modules`) was created in the worktree to allow tsc/build to run. This is tooling infrastructure, not a code change.

## Known Stubs

None — all components are wired to real API endpoints from Plan 02.

## Threat Flags

None — no new security surface beyond what the threat_model covers.

## Self-Check

**Files:**
- frontend/src/types/document.ts: FOUND
- frontend/src/lib/api.ts: FOUND (uploadFile added)
- frontend/src/components/documents/DocumentCard.tsx: FOUND
- frontend/src/components/documents/DocumentUploadForm.tsx: FOUND
- frontend/src/components/documents/DocumentVault.tsx: FOUND
- frontend/src/app/(dashboard)/documents/page.tsx: FOUND
- frontend/src/components/layout/Sidebar.tsx: FOUND (FileText + Documents nav item)

**Commits:**
- 1ac45b0: feat(04-03) Task 1 — FOUND
- afbc194: feat(04-03) Task 2 — FOUND

**Build:** npm run build completed with /documents route (7.19 kB) — PASSED
**TypeScript:** tsc --noEmit exits 0 — PASSED

## Self-Check: PASSED
