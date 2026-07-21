---
phase: 06-notifications
plan: "02"
subsystem: frontend
tags: [telegram, notifications, watchlist, react-query, polling, sidebar]
status: partial — awaiting human-verify checkpoint (Task 3)
dependency_graph:
  requires:
    - "06-01 (GET /api/notifications/status, POST /api/notifications/telegram/link-token, DELETE /api/notifications/telegram)"
    - "tenders.py DELETE /api/watchlist/{number_anno}"
  provides:
    - "TelegramConnectCard component — connect/disconnect/polling via refetchInterval v5"
    - "WatchlistSettingsTable component — delete-only rows, shared ['watchlist'] cache"
    - "/settings/notifications page — TelegramConnectCard + WatchlistSettingsTable"
    - "Sidebar Bell 'Настройки' nav entry"
  affects:
    - "DashboardWatchlist (shares ['watchlist'] queryKey — invalidate in WatchlistSettingsTable also refreshes dashboard)"
tech_stack:
  added: []
  patterns:
    - "refetchInterval v5 function form: (query) => ... — NOT (data, error) => ..."
    - "pollingActive + 60s setTimeout guard for bounded polling"
    - "useMutation with dynamic mutationFn for per-row delete with deletingId tracking"
    - "Shared React Query cache key ['watchlist'] across DashboardWatchlist + WatchlistSettingsTable"
key_files:
  created:
    - "frontend/src/components/notifications/TelegramConnectCard.tsx"
    - "frontend/src/components/notifications/WatchlistSettingsTable.tsx"
    - "frontend/src/app/(dashboard)/settings/notifications/page.tsx"
  modified:
    - "frontend/src/components/layout/Sidebar.tsx"
decisions:
  - "D-02 honored: WatchlistSettingsTable delete-only (no toggle enable/disable) — api.delete only"
  - "D-01 honored: no WhatsApp block anywhere in frontend"
  - "pollingActive gated with 60s auto-timeout to prevent indefinite polling (T-06-FE-04)"
  - "page.tsx has no QueryClientProvider — dashboard layout already provides it via Providers.tsx"
  - "staleTime: 0 on notification-status useQuery prevents stale cache during polling window"
metrics:
  duration: "~12 min"
  completed_date: "2026-07-21"
  tasks_completed: 2
  tasks_total: 3
  files_created: 3
  files_modified: 1
---

# Phase 06 Plan 02: Notifications Settings Frontend Summary

**One-liner:** Notifications settings UI — TelegramConnectCard with deep-link connect/polling/disconnect, WatchlistSettingsTable with per-row delete, `/settings/notifications` page assembly, and Sidebar Bell nav entry.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | TelegramConnectCard + WatchlistSettingsTable | `a5d2575` | components/notifications/TelegramConnectCard.tsx, WatchlistSettingsTable.tsx |
| 2 | /settings/notifications page + Sidebar Bell | `71737f5` | app/(dashboard)/settings/notifications/page.tsx, components/layout/Sidebar.tsx |
| 3 | Human verification | PENDING | — checkpoint not yet passed |

## Verification Results (Tasks 1 + 2)

- TypeScript compilation: 0 errors (`tsc --noEmit` exits 0)
- `refetchInterval` uses v5 function form `(query) => ...` — confirmed by grep
- `pollingActive` referenced 4 times in TelegramConnectCard (state declaration + set + read in refetchInterval + useEffect)
- No `(data, error) =>` v4 syntax anywhere in TelegramConnectCard
- No `whatsapp` string in any notification component (D-01)
- WatchlistSettingsTable: queryKey `['watchlist']` (shared cache with DashboardWatchlist)
- WatchlistSettingsTable: `api.delete('/api/watchlist/${numberAnno}')` — no toggle endpoints
- Sidebar: `Bell` imported + used in navItems (2 matches); `settings/notifications` + `Настройки` present
- page.tsx: TelegramConnectCard on line 15, WatchlistSettingsTable on line 16 (correct order)
- No layout.tsx under settings/notifications
- No QueryClientProvider in page.tsx

## Acceptance Criteria Verified (Tasks 1 + 2)

| Criteria | Status |
|----------|--------|
| TelegramConnectCard: refetchInterval >= 1 match | PASS |
| TelegramConnectCard: pollingActive >= 2 matches | PASS (4 matches) |
| TelegramConnectCard: (query) v5 syntax | PASS |
| TelegramConnectCard: no (data, error) v4 syntax | PASS |
| TelegramConnectCard: no whatsapp string | PASS |
| WatchlistSettingsTable: queryKey ['watchlist'] | PASS |
| WatchlistSettingsTable: api.delete watchlist path | PASS |
| WatchlistSettingsTable: Удалить + Trash2 present | PASS (3 matches) |
| Both files: 'use client' first line | PASS |
| Sidebar: settings/notifications >= 1 match | PASS |
| Sidebar: Bell >= 2 matches | PASS |
| Sidebar: Настройки >= 1 match | PASS |
| page.tsx: TelegramConnectCard before WatchlistSettingsTable | PASS |
| page.tsx: no QueryClientProvider | PASS |
| No layout.tsx under settings/ | PASS |
| TypeScript: 0 errors | PASS |

## Deviations from Plan

None — Tasks 1 and 2 executed exactly as specified.

## Known Stubs

None — TelegramConnectCard and WatchlistSettingsTable wire directly to live backend endpoints from Plan 06-01.

## Threat Flags

No new threat surface beyond the plan's `<threat_model>`:
- T-06-FE-02: `rel="noopener noreferrer"` applied to "Открыть Telegram" anchor link
- T-06-FE-03: DELETE call uses URL path from GET /api/watchlist response — no user-injected number_anno
- T-06-FE-04: 60s timeout bounds polling; pollingActive gate prevents unnecessary queries

## Self-Check: PASSED

All 4 expected files found. Both task commits (`a5d2575`, `71737f5`) verified in git log.

---

*Note: This summary is partial — Task 3 (human-verify checkpoint) is pending. SUMMARY will be updated after checkpoint passes.*
