---
phase: 07-discovery-matching
plan: "05"
subsystem: frontend
tags: [discovery, tender-match, sidebar, middleware, typescript, react-query]
dependency_graph:
  requires:
    - "07-03: GET/PUT /api/discovery/filters, GET /api/discovery/matches, POST /api/discovery/{id}/participate, POST /api/discovery/{id}/skip"
    - "07-04: create_discovery_draft in application_service"
  provides:
    - "TenderMatchStatus, TenderMatchResponse, ClientFilterResponse TypeScript types"
    - "TenderMatchStatusBadge component (4 states)"
    - "TenderMatchCard component with participate/skip mutations"
    - "/discovery page: discovery feed with useQuery"
    - "/discovery-filters page: filter settings form with useMutation"
    - "Sidebar extended: /discovery nav item + Telegram bot external link"
    - "middleware.ts: /discovery and /discovery-filters in protectedRoutes"
  affects:
    - "frontend/src/components/layout/Sidebar.tsx"
    - "frontend/src/middleware.ts"
    - "frontend/.env.example"
tech_stack:
  added: []
  patterns:
    - "useQuery({ queryKey: ['discovery-matches'], queryFn: () => api.get(...), retry: false })"
    - "useMutation({ mutationFn: ..., onSuccess: () => queryClient.invalidateQueries(...) })"
    - "STATUS_CONFIG Record<TenderMatchStatus, StatusConfig> — mirrors ApplicationStatusBadge pattern exactly"
    - "Button visibility: isActionable = status !== 'participating' && status !== 'skipped'"
key_files:
  created:
    - frontend/src/types/discovery.ts
    - frontend/src/components/discovery/TenderMatchStatusBadge.tsx
    - frontend/src/components/discovery/TenderMatchCard.tsx
    - frontend/src/app/(dashboard)/discovery/page.tsx
    - frontend/src/app/(dashboard)/discovery-filters/page.tsx
  modified:
    - frontend/src/components/layout/Sidebar.tsx
    - frontend/src/middleware.ts
    - frontend/.env.example
decisions:
  - "Sidebar Telegram bot link uses NEXT_PUBLIC_TELEGRAM_BOT_USERNAME (D-08), placed in bottom section before Logout"
  - "Discovery feed sorts newest-first by created_at, mirrors applications/page.tsx pattern"
  - "Both /discovery and /discovery-filters added to protectedRoutes (Research pitfall 6)"
  - "node_modules symlinked from main repo into worktree frontend to enable tsc --noEmit"
metrics:
  duration: "~20 minutes"
  completed_date: "2026-07-20"
  tasks_completed: 2
  files_created: 5
  files_modified: 3
---

# Phase 7 Plan 05: Discovery Frontend Summary

**One-liner:** Complete frontend for discovery matching — TypeScript types, TenderMatchStatusBadge + TenderMatchCard components, /discovery feed page, /discovery-filters settings form, Sidebar extension with /discovery nav + Telegram bot link, middleware route protection.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | TypeScript types + components + Sidebar + middleware + .env.example | `473f3ae` | `discovery.ts`, `TenderMatchStatusBadge.tsx`, `TenderMatchCard.tsx`, `Sidebar.tsx`, `middleware.ts`, `.env.example` |
| 2 | Discovery feed page + Filter settings page | `2b9a1a8` | `(dashboard)/discovery/page.tsx`, `(dashboard)/discovery-filters/page.tsx` |

---

## What Was Built

### Task 1: TypeScript types + components + Sidebar + middleware + .env.example

**`frontend/src/types/discovery.ts`:**
- `TenderMatchStatus` = `'matched' | 'notified' | 'skipped' | 'participating'`
- `TenderMatchResponse` — full match record with denormalized tender fields (tender_name_ru, customer_name_ru, total_sum, end_date, region)
- `ClientFilterResponse` — filter settings with keywords, spgz_codes, region, min/max amount

**`frontend/src/components/discovery/TenderMatchStatusBadge.tsx`:**
- STATUS_CONFIG mirrors ApplicationStatusBadge.tsx exactly
- matched → Новый (blue), notified → Уведомлён (amber), participating → Участвуем (green), skipped → Пропущен (gray)

**`frontend/src/components/discovery/TenderMatchCard.tsx`:**
- Shows: title, customer, amount (formatted with ru-RU locale + ₸), deadline, region, goszakup source badge, status badge
- "Участвуем" button: POST /api/discovery/{id}/participate → redirect to /applications/{id} on success; hidden when status is 'participating' or 'skipped'
- "Пропустить" button: POST /api/discovery/{id}/skip → invalidates 'discovery-matches' query; hidden when status is 'skipped' or 'participating'
- Both buttons show loading state ("Подождите...") while pending

**`frontend/src/components/layout/Sidebar.tsx`:**
- Added Sparkles and ExternalLink imports from lucide-react
- Added `{ href: '/discovery', label: 'Подборка', icon: Sparkles }` to navItems array (after /applications)
- Added Telegram bot link (`https://t.me/${NEXT_PUBLIC_TELEGRAM_BOT_USERNAME}`) in bottom section before Logout button, opens in new tab

**`frontend/src/middleware.ts`:**
- Added '/discovery' and '/discovery-filters' to protectedRoutes array (Research pitfall 6 fix)

**`frontend/.env.example`:**
- Added `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME=your_bot_username` with comment

### Task 2: Discovery feed page + Filter settings page

**`frontend/src/app/(dashboard)/discovery/page.tsx`:**
- `useQuery<TenderMatchResponse[]>({ queryKey: ['discovery-matches'], queryFn: () => api.get('/api/discovery/matches'), retry: false })`
- Sorts newest-first by created_at
- Loading state: `<p>Загрузка...</p>`
- Error state: Alert with destructive styling
- Empty state: dashed border box with link to /discovery-filters
- List state: maps to `<TenderMatchCard key={match.id} match={match} />`

**`frontend/src/app/(dashboard)/discovery-filters/page.tsx`:**
- `useQuery` fetches current filter (retry: false — 404 means no filter yet)
- `useEffect` pre-fills form from loaded filter
- `useMutation` calls `api.put('/api/discovery/filters', data)` on submit
- On success: invalidates 'discovery-filters' query + shows "Фильтры сохранены" for 3 seconds
- Form fields: keywords (comma-separated), СПГЗ коды (comma-separated), регион, сумма от/до
- Parses comma-separated strings to arrays; converts amounts to floats; sends null for empty fields

---

## Verification Results

| Check | Result |
|-------|--------|
| `tsc --noEmit` (worktree) | PASSED — no errors |
| `/discovery` in middleware.ts protectedRoutes | CONFIRMED |
| `/discovery-filters` in middleware.ts protectedRoutes | CONFIRMED |
| TenderMatchStatusBadge — 4 statuses | CONFIRMED (matched, notified, participating, skipped) |
| TenderMatchCard button visibility logic | CONFIRMED (hidden when participating or skipped) |
| Sidebar has Sparkles + /discovery nav item | CONFIRMED |
| Sidebar has ExternalLink + Telegram bot link | CONFIRMED |
| NEXT_PUBLIC_TELEGRAM_BOT_USERNAME in .env.example | CONFIRMED |

---

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

The only operational note: `node_modules` are in the main repo (`/Users/smatov/GitLab/TenderIt/frontend/node_modules/`) but not in the worktree. Created a symlink `frontend/node_modules → main-repo/frontend/node_modules` in the worktree to enable `tsc --noEmit`. This is a worktree infrastructure detail, not a code deviation.

---

## Known Stubs

None — all components and pages wire to real backend endpoints built in 07-03.

---

## Threat Surface Scan

All STRIDE threats from the plan's threat model are mitigated:

| Threat ID | Mitigation Applied |
|-----------|-------------------|
| T-07-mw-01 | `/discovery` and `/discovery-filters` added to protectedRoutes in middleware.ts; unauthenticated requests redirected to /login |
| T-07-mw-02 | POST /api/discovery/{id}/participate is IDOR-protected server-side (07-03); frontend cannot access another user's match |
| T-07-ext-04 | NEXT_PUBLIC_TELEGRAM_BOT_USERNAME controls only the display link; no security risk in client-side exposure |

No new threat surface introduced beyond the plan's threat model.

## Self-Check: PASSED

### Files exist:
- `frontend/src/types/discovery.ts` — CREATED
- `frontend/src/components/discovery/TenderMatchStatusBadge.tsx` — CREATED
- `frontend/src/components/discovery/TenderMatchCard.tsx` — CREATED
- `frontend/src/app/(dashboard)/discovery/page.tsx` — CREATED
- `frontend/src/app/(dashboard)/discovery-filters/page.tsx` — CREATED
- `frontend/src/components/layout/Sidebar.tsx` — MODIFIED
- `frontend/src/middleware.ts` — MODIFIED
- `frontend/.env.example` — MODIFIED

### Commits exist:
- `473f3ae` — feat(07-05): TypeScript types + discovery components + Sidebar + middleware (Task 1)
- `2b9a1a8` — feat(07-05): discovery feed page + filter settings page (Task 2)

### TypeScript: PASSED (tsc --noEmit → no errors)
