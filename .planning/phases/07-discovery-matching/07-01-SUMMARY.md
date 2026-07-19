---
phase: 07-discovery-matching
plan: 01
subsystem: backend
tags: [database, migrations, orm, pydantic, discovery]
dependency_graph:
  requires: []
  provides:
    - alembic migrations 0005-0007
    - ClientFilter ORM model
    - TenderMatch ORM model
    - ClientFilterCreate/Response Pydantic schemas
    - TenderMatchResponse Pydantic schema
  affects:
    - backend/app/models/tender.py (extended)
    - all Phase 7 plans (import from these models)
tech_stack:
  added: []
  patterns:
    - SQLAlchemy 2.x mapped_column + Mapped[T] ORM pattern
    - postgresql.ARRAY(Text) for keyword/code arrays
    - Pydantic v2 field_validator + ConfigDict(from_attributes=True)
    - Alembic down_revision chain (0004 → 0005 → 0006 → 0007)
key_files:
  created:
    - backend/alembic/versions/0005_extend_tenders_source_fields.py
    - backend/alembic/versions/0006_create_client_filters.py
    - backend/alembic/versions/0007_create_tender_matches.py
    - backend/app/models/client_filter.py
    - backend/app/models/tender_match.py
    - backend/app/schemas/client_filter.py
    - backend/app/schemas/tender_match.py
  modified:
    - backend/app/models/tender.py
decisions:
  - "D-01 honored: no UNIQUE(source, external_number) — existing UNIQUE(number_anno) sufficient"
  - "D-02 honored: no profitability column in tender_matches"
  - "D-10 honored: UNIQUE(user_id) on client_filters — one filter set per user"
  - "D-11 honored: status values matched|notified|skipped|participating stored as TEXT"
  - "T-07-04 mitigated: @field_validator rejects keywords > 20 at schema level"
  - "Pitfall 4 avoided: end_date used as deadline (no new deadline_at column)"
metrics:
  duration: "~4 minutes"
  completed: "2026-07-19"
  tasks_completed: 2
  files_created: 7
  files_modified: 1
---

# Phase 7 Plan 01: DB Schema Foundation Summary

**One-liner:** Three Alembic migrations (0005-0007) + Tender ORM extension + ClientFilter/TenderMatch ORM models + Pydantic schemas establishing the complete DB foundation for Phase 7 discovery & matching.

## What Was Built

### Task 1: Alembic Migrations 0005-0007 + Extend Tender ORM

Three migration files applied cleanly (`alembic upgrade head` from 0004 → 0007):

**Migration 0005** — extends `tenders` table with three nullable/defaulted columns:
- `source TEXT NOT NULL DEFAULT 'goszakup'` — multi-source support (sk.kz deferred to v2 per D-01)
- `region TEXT nullable` — region exact-match filter
- `spgz_code TEXT nullable` — СПГЗ classifier code (goszakup field name confirmed in 07-02)

**Migration 0006** — creates `client_filters` table:
- `UNIQUE(user_id)` constraint — one filter set per user (D-10)
- `keywords TEXT[] NOT NULL DEFAULT '{}'` — ILIKE matching
- `spgz_codes TEXT[] NOT NULL DEFAULT '{}'` — exact match
- `ON DELETE CASCADE` from `users(id)` (T-07-schema-02)

**Migration 0007** — creates `tender_matches` table:
- `UNIQUE(user_id, tender_id)` — dedup under concurrent ARQ runs (T-07-schema-01, Pitfall 3)
- `idx_tender_matches_user_id` — fast list queries per user
- `idx_tender_matches_status` — fast worker query for unnotified matches
- Status as TEXT (same pattern as Application — easy v2 extension)
- `ON DELETE CASCADE` from both `users(id)` and `tenders(id)`

**Tender ORM extended** with `source`, `region`, `spgz_code` columns after `created_at`.

### Task 2: ORM Models + Pydantic Schemas

**`ClientFilter`** ORM model:
- `ARRAY(Text)` columns for keywords/spgz_codes
- Nullable Decimal fields for amount range
- No relationships (data record only)

**`TenderMatch`** ORM model:
- `String(50)` status field with `server_default="matched"`
- `notified_at`/`decided_at` timestamp tracking
- No eager relationships (lazy="noload" pattern)

**`ClientFilterCreate`** Pydantic schema:
- All fields optional with empty/None defaults
- `@field_validator('keywords')` enforces max 20 items (T-07-04 DoS guard)
- NEVER accepts `user_id` in request body (mirrors T-05-02 pattern)

**`ClientFilterResponse`** extends `ClientFilterCreate` with `id`, `user_id`, timestamps. `ConfigDict(from_attributes=True)` for ORM → Pydantic.

**`TenderMatchResponse`** Pydantic schema:
- Core match fields + denormalized tender fields for frontend display
- `tender_name_ru`, `customer_name_ru`, `total_sum`, `end_date`, `region` all nullable
- `end_date` = submission deadline (Pitfall 4 avoided — no `deadline_at` column added)

## Verification Results

| Check | Result |
|-------|--------|
| `alembic current` | `0007 (head)` |
| `tenders.source` NOT NULL DEFAULT 'goszakup' | CONFIRMED |
| `tenders.region` nullable | CONFIRMED |
| `tenders.spgz_code` nullable | CONFIRMED |
| `uq_client_filters_user_id` UNIQUE constraint | CONFIRMED |
| `uq_tender_matches_user_tender` UNIQUE constraint | CONFIRMED |
| `idx_tender_matches_user_id` index | CONFIRMED |
| `idx_tender_matches_status` index | CONFIRMED |
| All four modules import cleanly | CONFIRMED |
| `ClientFilterCreate(keywords=['a']*21)` raises ValidationError | CONFIRMED |
| `TenderMatchResponse` has nullable tender fields | CONFIRMED |
| `pytest tests/ -x` (112 tests) | 112 passed, 3 skipped (network-gated) |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 29e231c | feat(07-01): Alembic migrations 0005-0007 + extend Tender ORM |
| Task 2 | 50cb484 | feat(07-01): ClientFilter + TenderMatch ORM models + Pydantic schemas |

## Deviations from Plan

None — plan executed exactly as written.

All locked decisions (D-01, D-02, D-10, D-11) honored. All pitfalls (Pitfall 3, Pitfall 4, Pitfall 7) documented in code comments.

## Known Stubs

None — this plan creates DB schema only. No data-flow stubs.

## Threat Flags

No new threat surface beyond what the plan's threat model covers. All three T-07-* threats are mitigated as specified:
- T-07-04: `@field_validator('keywords')` in `ClientFilterCreate`
- T-07-schema-01: `UNIQUE(user_id, tender_id)` in migration 0007
- T-07-schema-02: `ON DELETE CASCADE` from `users(id)` in migration 0006

## Self-Check: PASSED

All created files verified to exist. Both commits verified in git log.
