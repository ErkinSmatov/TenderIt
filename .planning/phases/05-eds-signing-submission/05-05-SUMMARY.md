---
phase: 05-eds-signing-submission
plan: 05
subsystem: ui
tags: [react, next.js, react-query, tailwind, applications, status-badge]

# Dependency graph
requires:
  - phase: 05-01
    provides: GET /api/applications and GET /api/applications/{id} backend endpoints
  - phase: 05-03
    provides: ApplicationStatus, ApplicationResponse types; ApplicationWizard (create flow)
  - phase: 05-04
    provides: ARQ auto-submission state transitions (waiting → submitting → submitted | error)
provides:
  - APPL-05 applications history list at /applications (react-query, newest-first, empty/error state)
  - APPL-04 detail page at /applications/{id} with 30s polling for live status updates
  - APPL-06 error surface showing raw portal error_message + signed-submission retention note
  - Six-state Russian status badge (draft/signed/waiting/submitting/submitted/error)
  - ApplicationCard component with error surface
  - Sidebar "Заявки" nav link to /applications
affects: [06-notifications, frontend-layout]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "refetchInterval: 30000 on detail page for live status polling without WebSocket overhead"
    - "buttonVariants helper used on Link elements (Button lacks asChild support in this project)"
    - "Custom status badge with inline Tailwind (not CVA variants) for per-state animate-pulse control"

key-files:
  created:
    - frontend/src/components/applications/ApplicationStatusBadge.tsx
    - frontend/src/components/applications/ApplicationCard.tsx
    - frontend/src/app/(dashboard)/applications/page.tsx
    - frontend/src/app/(dashboard)/applications/[id]/page.tsx
  modified:
    - frontend/src/components/layout/Sidebar.tsx

key-decisions:
  - "Used buttonVariants instead of Button asChild — the project's Button component does not support asChild prop (no Radix Slot)"
  - "Custom status badge with direct Tailwind classes instead of CVA Badge variants — allows per-status animate-pulse without adding new Badge variants"
  - "Sidebar isActive uses exact pathname match (pathname === href) consistent with existing pattern — sub-page active state left as enhancement"

patterns-established:
  - "refetchInterval pattern: useQuery({ refetchInterval: 30000 }) for live-updating detail pages without WebSocket overhead"
  - "Error surface pattern: Alert variant=destructive with AlertTitle + two AlertDescription blocks (message + retention note)"

requirements-completed: [APPL-01, APPL-02, APPL-05, APPL-06]

# Metrics
duration: ~20min
completed: 2026-07-19
---

# Phase 05 Plan 05: Application Status UI Summary

**Six-state Russian status badge + applications list/detail pages with 30s polling and portal error surface, closing the user-visible read side of the EDS signing pipeline**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-19T~start
- **Completed:** 2026-07-19
- **Tasks:** 2 of 3 (Task 3 is human-verify checkpoint — stopped as planned)
- **Files modified:** 5

## Accomplishments

- ApplicationStatusBadge: maps all six state-machine statuses to Russian labels and Tailwind colour classes; "Отправляется" pulses via animate-pulse
- ApplicationCard: renders tender_id linked to detail, status badge, created_at in ru-RU locale; shows destructive Alert with error_message when status=error (APPL-06)
- /applications list page: fetches GET /api/applications with react-query, sorted newest-first, empty state "Пока нет заявок", error alert, link to create new
- /applications/[id] detail page: refetchInterval 30s (APPL-04), lots table with unit/total prices, document count, state-history timeline (created_at/ready_at/submitted_at), error surface with portal message + retention note (APPL-06)
- Sidebar "Заявки" link added with ClipboardList icon between Тендеры and Профиль

## Task Commits

1. **Task 1: Status badge + application card** — `4108259` (feat)
2. **Task 2: Applications list + detail + Sidebar nav** — `3bc5c30` (feat)

## Files Created/Modified

- `frontend/src/components/applications/ApplicationStatusBadge.tsx` — Six-state badge with Russian labels and per-status Tailwind colours (animate-pulse on submitting)
- `frontend/src/components/applications/ApplicationCard.tsx` — Card with tender_id link, status badge, ru-RU date, destructive Alert for error_message
- `frontend/src/app/(dashboard)/applications/page.tsx` — History list page (APPL-05): useQuery → GET /api/applications, sorted newest-first, empty + error states
- `frontend/src/app/(dashboard)/applications/[id]/page.tsx` — Detail page (APPL-04, APPL-06): 30s polling, lots, documents, timeline, error surface
- `frontend/src/components/layout/Sidebar.tsx` — Added "Заявки" nav entry with ClipboardList icon to /applications

## Decisions Made

- **buttonVariants on Link instead of Button asChild:** The project's Button component is a plain forwardRef without Radix Slot/asChild support. Used `buttonVariants({ size: 'sm' })` applied to a `<Link>` directly — same visual result, no type error.
- **Custom status badge instead of CVA Badge variants:** animate-pulse needed only for the `submitting` state; adding a per-status variant to the shared Badge component would pollute its API. A self-contained ApplicationStatusBadge with a `Record<ApplicationStatus, StatusConfig>` lookup is cleaner.
- **Exact `isActive` match in Sidebar:** Kept `pathname === href` consistent with the pre-existing Sidebar pattern. Prefix matching for /applications/* sub-pages is left as a minor UX enhancement for a future plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed Button asChild — prop not supported**
- **Found during:** Task 2 (list page implementation)
- **Issue:** Button component does not accept `asChild` prop (no Radix Slot); TypeScript error TS2322
- **Fix:** Replaced `<Button asChild>` with `<Link className={cn(buttonVariants({ size: 'sm' }))}>` — identical visual output
- **Files modified:** frontend/src/app/(dashboard)/applications/page.tsx
- **Verification:** tsc --noEmit exits 0
- **Committed in:** 3bc5c30 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Minimal — purely a TypeScript prop compatibility fix, no behaviour change.

## Issues Encountered

- Worktree was branched before Phase 05 work landed on master. Resolved by fast-forward merge of master into the worktree branch before implementing.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All five plans in Phase 05 will be complete once Task 3 (human verify checkpoint) is approved.
- The EDS signing + submission pipeline is complete: create (05-03) → sign (NCALayer) → auto-submit (05-04) → status UI (05-05).
- Phase 06 (Notifications) can begin after human verification approves this plan.

---
*Phase: 05-eds-signing-submission*
*Completed: 2026-07-19*
